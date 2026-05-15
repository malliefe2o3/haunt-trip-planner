# models.py
from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional


@dataclass
class Location:
    address: str
    lat: float
    lng: float


@dataclass
class ScheduleEntry:
    date: date
    open_time: time
    close_time: time
    price: Optional[float] = None
    ticket_url: Optional[str] = None


@dataclass
class Attraction:
    name: str
    address: str
    lat: float
    lng: float
    schedule_url: str
    assigned_dates: Optional[list[date]] = None
    schedule: list[ScheduleEntry] = field(default_factory=list)


@dataclass
class Segment:
    date_range: tuple[date, date]
    start_location: Location
    end_location: Location


@dataclass
class Trip:
    date_range: tuple[date, date]
    home_base: Location
    blackout_dates: list[date] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    attractions: list[Attraction] = field(default_factory=list)
