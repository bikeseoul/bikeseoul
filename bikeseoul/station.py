""":mod:`bikeseoul.station` --- Station
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""
from sqlalchemy.schema import Column
from sqlalchemy.types import Boolean, Integer, UnicodeText, Float, DateTime
from sqlalchemy.dialects.postgres import JSONB

from .orm import Base


class Station(Base):
    """Bike rental station."""

    id = Column(Integer, primary_key=True, autoincrement=False)
    name = Column(UnicodeText)
    address = Column(UnicodeText)
    longitude = Column(Float)
    latitude = Column(Float)
    rack_count = Column(Integer)
    in_service = Column(Boolean)

    __tablename__ = 'stations'


class StationStatus(Base):
    """Station status at given time."""

    id = Column(Integer, primary_key=True)
    data = Column(JSONB)
    timestamp = Column(DateTime(timezone=True))

    __tablename__ = 'station_statuses'
