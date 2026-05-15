# tests/test_discovery.py
from datetime import date, time
from unittest.mock import patch, MagicMock
from models import Location, ScheduleEntry, Attraction, Trip
from discovery import (
    deduplicate_attractions,
    find_gap_nights,
    find_densify_opportunities,
    DiscoverySuggestion,
)
from optimizer import ItineraryResult, ItineraryEntry


def _make_attraction(name, lat, lng, schedule_dates):
    return Attraction(
        name=name, address=f"{name} addr", lat=lat, lng=lng,
        schedule_url=f"https://{name.lower()}.com",
        schedule=[
            ScheduleEntry(date=d, open_time=time(19, 0), close_time=time(23, 0))
            for d in schedule_dates
        ],
    )


def test_deduplicate_same_name_close_location():
    a1 = _make_attraction("Haunted Hollow", 41.88, -87.63, [date(2026, 10, 3)])
    a2 = _make_attraction("Haunted Hollow", 41.881, -87.631, [date(2026, 10, 3)])
    result = deduplicate_attractions([a1, a2])
    assert len(result) == 1


def test_deduplicate_different_names():
    a1 = _make_attraction("Haunted Hollow", 41.88, -87.63, [date(2026, 10, 3)])
    a2 = _make_attraction("Screamville", 41.88, -87.63, [date(2026, 10, 3)])
    result = deduplicate_attractions([a1, a2])
    assert len(result) == 2


def test_find_gap_nights():
    trip = Trip(
        date_range=(date(2026, 10, 1), date(2026, 10, 5)),
        start_location=Location("Chicago", 41.87, -87.63),
        end_location=Location("Chicago", 41.87, -87.63),
        blackout_dates=[date(2026, 10, 2)],
        legs=[], attractions=[],
    )
    scheduled_dates = {date(2026, 10, 1), date(2026, 10, 4)}
    gaps = find_gap_nights(trip, scheduled_dates)
    assert date(2026, 10, 3) in gaps
    assert date(2026, 10, 5) in gaps
    assert date(2026, 10, 2) not in gaps  # blackout
    assert date(2026, 10, 1) not in gaps  # already scheduled


def test_find_densify_opportunities():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3)])
    entry = ItineraryEntry(
        attraction=a, date=date(2026, 10, 3),
        arrival_time=time(19, 0), open_time=time(19, 0), close_time=time(23, 0),
    )
    result = ItineraryResult(
        scheduled={date(2026, 10, 3): [entry]},
        unscheduled=[],
    )

    candidate = _make_attraction("B", 41.89, -87.64, [date(2026, 10, 3)])
    candidate.schedule[0].open_time = time(20, 0)
    candidate.schedule[0].close_time = time(23, 30)

    densify = find_densify_opportunities(result, [candidate])
    assert len(densify) == 1
    assert densify[0].attraction.name == "B"
    assert densify[0].suggested_date == date(2026, 10, 3)


def test_find_densify_rejects_far_attraction():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3)])
    entry = ItineraryEntry(
        attraction=a, date=date(2026, 10, 3),
        arrival_time=time(19, 0), open_time=time(19, 0), close_time=time(23, 0),
    )
    result = ItineraryResult(
        scheduled={date(2026, 10, 3): [entry]},
        unscheduled=[],
    )

    candidate = _make_attraction("Far", 39.78, -89.65, [date(2026, 10, 3)])
    densify = find_densify_opportunities(result, [candidate])
    assert len(densify) == 0
