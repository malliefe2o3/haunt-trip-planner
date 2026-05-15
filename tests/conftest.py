# tests/conftest.py
import pytest
from datetime import date, time
from models import Location, ScheduleEntry, Attraction, Segment, Trip


@pytest.fixture
def sample_location():
    return Location(address="123 Main St, Springfield, IL", lat=39.7817, lng=-89.6501)


@pytest.fixture
def sample_schedule_entries():
    return [
        ScheduleEntry(
            date=date(2026, 10, 2),
            open_time=time(19, 0),
            close_time=time(23, 0),
            price=25.0,
            ticket_url="https://example.com/tickets",
        ),
        ScheduleEntry(
            date=date(2026, 10, 3),
            open_time=time(19, 0),
            close_time=time(0, 0),
            price=30.0,
            ticket_url="https://example.com/tickets",
        ),
    ]


@pytest.fixture
def sample_attraction(sample_location, sample_schedule_entries):
    return Attraction(
        name="Haunted Hollow",
        address=sample_location.address,
        lat=sample_location.lat,
        lng=sample_location.lng,
        schedule_url="https://hauntedhollowil.com/schedule",
        assigned_dates=None,
        schedule=sample_schedule_entries,
    )


@pytest.fixture
def sample_segment():
    return Segment(
        date_range=(date(2026, 10, 1), date(2026, 10, 7)),
        start_location=Location("Chicago, IL", 41.8781, -87.6298),
        end_location=Location("Chicago, IL", 41.8781, -87.6298),
    )


@pytest.fixture
def sample_trip(sample_attraction, sample_segment):
    return Trip(
        date_range=(date(2026, 10, 1), date(2026, 10, 14)),
        home_base=Location("Chicago, IL", 41.8781, -87.6298),
        blackout_dates=[date(2026, 10, 5)],
        segments=[sample_segment],
        attractions=[sample_attraction],
    )
