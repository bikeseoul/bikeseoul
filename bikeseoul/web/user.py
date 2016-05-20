""":mod:`bikeseoul.web.user` --- User pages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from flask import Blueprint, render_template


bp = Blueprint('user', __name__)


@bp.route('/')
def home():
    """Home."""
    return render_template('home.html')
