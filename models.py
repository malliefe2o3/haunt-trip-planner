# models.py
from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional


@dataclass
class Location:
    address: str
    lat: float
    lng: float


SIX_FLAGS_MIN_DURATION = 180

@dataclass
class ScheduleEntry:
    date: date
    open_time: time
    close_time: time
    price: Optional[float] = None
    ticket_url: Optional[str] = None
    duration_min: int = 45


def default_duration_for_name(name: str) -> int:
    if "six flags" in name.lower():
        return SIX_FLAGS_MIN_DURATION
    return 45


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
