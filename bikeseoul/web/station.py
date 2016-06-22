""":mod:`bikeseoul.web.station` --- Station pages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
import json
from datetime import datetime
from pathlib import Path

import requests
from flask import (Blueprint, Response, current_app, redirect, render_template,
                   stream_with_context, url_for, jsonify, abort)
from sqlalchemy.sql.functions import random, func

from ..station import Station, StationStatus
from .db import session
from .util import request_wants_json


bp = Blueprint('station', __name__)

BIKESEOUL_REALTIME_STATUS_URL = \
    "https://www.bikeseoul.com/app/station/getStationRealtimeStatus.do"


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
    stations = session.query(Station).all()
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
            for s in status.data['realtimeList']:
                for station in stations:
                    if s['stationName'] == station.name:
                        row[station.name] = s['parkingBikeTotCnt']
            yield str(row['timestamp'].timestamp()) + ',' + \
                ','.join([row.get(s.name, '') for s in stations]) + '\n'
    return Response(stream_with_context(generate()), mimetype='text/csv')


@bp.route('/stations/<int:station_id>/')
def station_detail(station_id):
    station = get_station(station_id)
    if station:
        q = get_statuses(10)
        statuses = []
        for status in q:
            for s in status.data['realtimeList']:
                if s['stationName'] == station.name:
                    s['timestamp'] = status.timestamp
                    statuses.append(s)
        stations = get_stations()
        return render_template('station_detail.html', stations=stations,
                               station=station, statuses=statuses)
    else:
        abort(404)


@bp.route('/stations/update/')
def update_stations():
    status = get_status()
    stations = build_stations(status)
    for station in stations:
        old_station = get_station(station.id)
        if old_station:
            session.delete(old_station)
        session.add(station)
        session.commit()
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
