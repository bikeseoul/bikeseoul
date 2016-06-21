""":mod:`bikeseoul.web.user` --- User pages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from flask import Blueprint, render_template

from ..station import Station
from .db import session


bp = Blueprint('user', __name__)


@bp.route('/')
def home():
    """Home."""
    stations = session.query(Station).all()
    return render_template('home.html', stations=stations)
