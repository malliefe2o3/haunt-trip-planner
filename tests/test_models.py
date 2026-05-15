# tests/test_models.py
from datetime import date, time
from models import Location, ScheduleEntry, Attraction, Segment, Trip


def test_location_fields(sample_location):
    assert sample_location.address == "123 Main St, Springfield, IL"
    assert sample_location.lat == 39.7817
    assert sample_location.lng == -89.6501


def test_schedule_entry_fields(sample_schedule_entries):
    entry = sample_schedule_entries[0]
    assert entry.date == date(2026, 10, 2)
    assert entry.open_time == time(19, 0)
    assert entry.close_time == time(23, 0)
    assert entry.price == 25.0
    assert entry.ticket_url == "https://example.com/tickets"


def test_schedule_entry_nullable_price():
    entry = ScheduleEntry(
        date=date(2026, 10, 4),
        open_time=time(19, 0),
        close_time=time(23, 0),
        price=None,
        ticket_url=None,
    )
    assert entry.price is None
    assert entry.ticket_url is None


def test_attraction_fields(sample_attraction):
    assert sample_attraction.name == "Haunted Hollow"
    assert sample_attraction.schedule_url == "https://hauntedhollowil.com/schedule"
    assert len(sample_attraction.schedule) == 2
    assert sample_attraction.assigned_dates is None


def test_attraction_with_assigned_dates(sample_attraction):
    sample_attraction.assigned_dates = [date(2026, 10, 2)]
    assert sample_attraction.assigned_dates == [date(2026, 10, 2)]


def test_segment_fields(sample_segment):
    assert sample_segment.date_range == (date(2026, 10, 1), date(2026, 10, 7))
    assert sample_segment.start_location.address == "Chicago, IL"


def test_trip_fields(sample_trip):
    assert sample_trip.date_range == (date(2026, 10, 1), date(2026, 10, 14))
    assert sample_trip.home_base.address == "Chicago, IL"
    assert len(sample_trip.blackout_dates) == 1
    assert len(sample_trip.segments) == 1
    assert len(sample_trip.attractions) == 1


def test_trip_no_segments():
    trip = Trip(
        date_range=(date(2026, 10, 1), date(2026, 10, 14)),
        home_base=Location("Chicago, IL", 41.8781, -87.6298),
        blackout_dates=[],
        segments=[],
        attractions=[],
    )
    assert trip.segments == []
