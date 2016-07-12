""":mod:`bikeseoul.web.user` --- User pages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from flask import Blueprint, render_template, request

from ..station import Station
from .db import session


bp = Blueprint('user', __name__)


@bp.route('/')
def home():
    """Home."""
    stations = session.query(Station).all()
    return render_template('home.html', stations=stations)

@bp.route('/search/', methods=['POST'])
def search():
    """Search."""
    q = '%{}%'.format(request.form['query'])
    stations = session.query(Station) \
                      .filter(Station.name.like(q) | Station.address.like(q)) \
                      .all()
    return render_template('search.html', stations=stations)
