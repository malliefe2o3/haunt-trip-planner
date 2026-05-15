# tests/test_optimizer.py
import pytest
from datetime import date, time
from models import Location, ScheduleEntry, Attraction, Leg, Trip
from optimizer import filter_eligible_dates, build_clusters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_attraction(name, lat, lng, schedule_dates, assigned_dates=None):
    return Attraction(
        name=name, address=f"{name} address", lat=lat, lng=lng,
        schedule_url=f"https://{name.lower().replace(' ', '')}.com",
        assigned_dates=assigned_dates,
        schedule=[ScheduleEntry(date=d, open_time=time(19, 0), close_time=time(23, 0)) for d in schedule_dates],
    )


def _make_trip(attractions, blackout_dates=None, legs=None):
    return Trip(
        date_range=(date(2026, 10, 1), date(2026, 10, 14)),
        start_location=Location("Chicago, IL", 41.8781, -87.6298),
        end_location=Location("Chicago, IL", 41.8781, -87.6298),
        blackout_dates=blackout_dates or [], legs=legs or [], attractions=attractions,
    )


# ---------------------------------------------------------------------------
# Phase 1-2: filter_eligible_dates and build_clusters
# ---------------------------------------------------------------------------

def test_filter_removes_blackout_dates():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3), date(2026, 10, 5)])
    trip = _make_trip([a], blackout_dates=[date(2026, 10, 5)])
    eligible = filter_eligible_dates(trip)
    assert eligible["A"] == [date(2026, 10, 3)]


def test_filter_removes_out_of_range_dates():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 9, 30), date(2026, 10, 3)])
    trip = _make_trip([a])
    eligible = filter_eligible_dates(trip)
    assert eligible["A"] == [date(2026, 10, 3)]


def test_filter_locks_assigned_dates():
    a = _make_attraction(
        "A", 41.88, -87.63,
        [date(2026, 10, 3), date(2026, 10, 7), date(2026, 10, 10)],
        assigned_dates=[date(2026, 10, 3)],
    )
    trip = _make_trip([a])
    eligible = filter_eligible_dates(trip)
    assert eligible["A"] == [date(2026, 10, 3)]


def test_filter_with_legs():
    # Leg covers Oct 1-7; attraction open Oct 3 and Oct 10
    # Oct 3 is in the leg's range, Oct 10 is outside → only Oct 3 eligible
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3), date(2026, 10, 10)])
    leg = Leg(
        date_range=(date(2026, 10, 1), date(2026, 10, 7)),
        start_location=Location("Chicago, IL", 41.8781, -87.6298),
        end_location=Location("Chicago, IL", 41.8781, -87.6298),
    )
    trip = _make_trip([a], legs=[leg])
    eligible = filter_eligible_dates(trip)
    assert eligible["A"] == [date(2026, 10, 3)]


def test_cluster_nearby_attractions():
    # A and B are ~1mi apart; C is ~185mi away (Nashville vs Chicago)
    a = _make_attraction("A", 41.8781, -87.6298, [date(2026, 10, 3)])
    b = _make_attraction("B", 41.8881, -87.6398, [date(2026, 10, 3)])
    c = _make_attraction("C", 36.1627, -86.7816, [date(2026, 10, 3)])  # Nashville
    clusters = build_clusters([a, b, c], radius_miles=20.0)
    # Find which clusters each attraction ended up in
    cluster_sets = [frozenset(att.name for att in cluster) for cluster in clusters]
    assert frozenset(["A", "B"]) in cluster_sets
    assert any("C" in cs and "A" not in cs for cs in cluster_sets)


def test_cluster_transitive():
    # A near B, B near C (each ~10mi), radius=12mi → all 3 in one cluster
    a = _make_attraction("A", 41.00, -87.00, [date(2026, 10, 3)])
    b = _make_attraction("B", 41.145, -87.00, [date(2026, 10, 3)])   # ~10mi from A
    c = _make_attraction("C", 41.29, -87.00, [date(2026, 10, 3)])    # ~10mi from B, ~20mi from A
    clusters = build_clusters([a, b, c], radius_miles=12.0)
    assert len(clusters) == 1
    assert len(clusters[0]) == 3


def test_cluster_solo():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3)])
    clusters = build_clusters([a])
    assert len(clusters) == 1
    assert len(clusters[0]) == 1
