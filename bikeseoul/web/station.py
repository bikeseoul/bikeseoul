""":mod:`bikeseoul.web.station` --- Station pages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
import json
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

import requests
from flask import (Blueprint, Response, current_app, redirect, render_template,
                   request, stream_with_context, url_for, jsonify, abort)
from lxml import html
from sqlalchemy.sql.functions import random, func

from ..station import Station, StationStatus
from .db import session
from .util import request_wants_json


bp = Blueprint('station', __name__)

NAVER_MAP_BIKE_ROUTE = "http://map.naver.com/?menu=route&mapMode=0&slng={origin.longitude}&slat={origin.latitude}&elng={dest.longitude}&elat={dest.latitude}&pathType=2&dtPathType=0"  # noqa
BIKESEOUL_REALTIME_STATUS_URL = "https://www.bikeseoul.com/app/station/getStationRealtimeStatus.do"  # noqa
BIKESEOUL_SEARCH_VIEW_URL = "https://www.bikeseoul.com/app/station/moveStationSearchView.do?currentPageNo={}"  # noqa


def get_stations():
    stations = session.query(Station) \
                      .order_by(Station.name) \
                      .all()
    return stations


def get_station(station_id):
    station = session.query(Station).get(station_id)
    return station


def get_status():
    r = requests.get(BIKESEOUL_REALTIME_STATUS_URL)
    return r.json()


def build_stations(status):
    stations = []
    for s in status['realtimeList']:
        station = Station(
            id=int(s['stationId'].split('-')[1]),
            name=s['stationName'],
            address=None,
            longitude=float(s['stationLongitude']),
            latitude=float(s['stationLatitude']),
            rack_count=int(s['rackTotCnt']),
            in_service=s['stationUseYn'] == 'Y',
        )
        stations.append(station)
    return stations


@bp.route('/stations/')
def list_stations():
    stations = session.query(Station).order_by(Station.name).all()
    if request_wants_json():
        return jsonify(stations=[station.as_dict() for station in stations])
    else:
        return render_template('stations.html', stations=stations)


def get_statuses(granularity):
    q = session.query(StationStatus) \
               .order_by(StationStatus.timestamp.asc()) \
               .subquery('c')
    q = session.query(StationStatus,
                      func.row_number().over().label("row_number")) \
               .select_entity_from(q) \
               .subquery()
    q = session.query(StationStatus) \
               .select_entity_from(q) \
               .filter(q.c.row_number % granularity == 0)
    return q


@bp.route('/machine-learning/csv/')
def machine_learning_csv():
    def generate():
        stations = get_stations()
        statuses = get_statuses(10)
        yield 'timestamp,' + \
              ','.join([station.name for station in stations]) + '\n'
        for status in statuses:
            row = dict()
            row['timestamp'] = status.timestamp
            for station in stations:
                s = get_status_for_station(station, status)
                if s:
                    row[station.name] = s['parkingBikeTotCnt']
            yield str(row['timestamp'].timestamp()) + ',' + \
                ','.join([row.get(st.name, '') for st in stations]) + '\n'
    return Response(stream_with_context(generate()), mimetype='text/csv')


def get_status_for_station(station, status):
    for s in status.data['realtimeList']:
        if s['stationName'] == station.name:
            return s


@bp.route('/stations/<int:station_id>/')
def station_detail(station_id):
    station = get_station(station_id)
    if station:
        stations = get_stations()
        latest_status = session.query(StationStatus) \
                               .order_by(StationStatus.timestamp.desc()) \
                               .first()  # FIXME
        if current_app.config.get('USE_PREDICTION', False) and latest_status:
            import boto3
            client = boto3.client('machinelearning')
            prediction = client.predict(
                MLModelId=current_app.config('AMAZON_ML_MODEL_ID'),  # FIXME
                Record=build_record_for_prediction(latest_status, stations),
                PredictEndpoint=current_app.config['AMAZON_ML_ENDPOINT']
            )
        else:
            prediction = None
        if latest_status:
            latest_station_status = get_status_for_station(station,
                                                           latest_status)
        else:
            latest_station_status = None
        station_statuses = []
        if current_app.config.get('USE_CHART', False):
            for status in get_statuses(10):
                s = get_status_for_station(station, status)
                if s:
                    s['timestamp'] = status.timestamp
                    station_statuses.append(s)
        return render_template('station_detail.html', stations=stations,
                               station=station, statuses=station_statuses,
                               latest_station_status=latest_station_status,
                               prediction=prediction)
    else:
        abort(404)


@bp.route('/stations/<int:station_id>/to/search/', methods=['POST'])
def search_destination_station(station_id):
    station = get_station(station_id)
    if not station:
        abort(404)
    query = request.form['query']
    stations = session.query(Station) \
                      .filter(Station.name.contains(query) |
                              Station.address.contains(query)) \
                      .all()
    results = [{'name': station.name, 'id': station.id} for station in stations]
    return jsonify(results=results)


@bp.route('/stations/<int:origin_id>/to/<int:dest_id>/')
def route_stations(origin_id, dest_id):
    origin = get_station(origin_id)
    dest = get_station(dest_id)
    if not (origin or dest):
        abort(404)
    return redirect(NAVER_MAP_BIKE_ROUTE.format(origin=origin, dest=dest))


def build_record_for_prediction(status, stations):
    record = {
        'timestamp': str(status.timestamp.timestamp() + 60 * 30)  # FIXME
    }
    for station in stations:
        status = get_status_for_station(station, status)
        if status:
            record[station.name] = status['parkingBikeTotCnt']
    return record


def update_station_statuses(status):
    station_status = StationStatus(
        data=status,
        timestamp=datetime.utcnow(),
    )
    session.add(station_status)
    session.commit()


def update_station_list(status):
    stations = build_stations(status)
    for station in stations:
        old_station = get_station(station.id)
        if old_station:
            session.delete(old_station)
        session.add(station)
    session.commit()


def update_station_addresses():
    page = 1
    while True:
        with urlopen(BIKESEOUL_SEARCH_VIEW_URL.format(page)) as f:
            tree = html.parse(f)
        stations = tree.xpath('//*[@id="container"]/table/tbody/tr[*]')
        if stations:
            for station in stations:
                name = station.xpath('td[1]/a/text()')[0]
                address = station.xpath('td[5]/span/text()')[0]
                s = session.query(Station).filter(Station.name == name).one()
                s.address = address
                session.add(s)
        else:
            break
        page += 1
    session.commit()


@bp.route('/stations/update/')
def update_stations():
    status = get_status()
    update_station_statuses(status)
    update_station_list(status)
    update_station_addresses()
    return redirect(url_for('.list_stations'))


@bp.route('/stations/random/')
def random_station():
    station = session.query(Station).order_by(random()).limit(1).one()
    return redirect(url_for('.station_detail', station_id=station.id))


@bp.route('/stations/statuses/')
def list_station_statuses():
    statuses = session.query(StationStatus) \
                      .order_by(StationStatus.timestamp.desc()) \
                      .limit(60 * 24)
    return render_template('station_statuses.html', statuses=statuses)


@bp.route('/stations/statuses/import/')
def import_station_statuses():
    p = Path(current_app.config['STATION_STATUS_DIRECTORY'])
    for path in p.iterdir():
        timestamp = datetime.utcfromtimestamp(int(path.parts[-1]))
        if not session.query(StationStatus) \
                      .filter_by(timestamp=timestamp) \
                      .count():
            with path.open() as f:
                data = json.loads(f.read())
            station_status = StationStatus(
                data=data,
                timestamp=timestamp,
            )
            session.add(station_status)
    session.commit()
    return str(session.query(StationStatus).count())
