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


# ---------------------------------------------------------------------------
# Phase 3-4: assign_dates and assign_time_slots
# ---------------------------------------------------------------------------

from optimizer import assign_dates, assign_time_slots, optimize, ItineraryEntry, ItineraryResult


def test_assign_dates_scarcity_first():
    # A open only Oct 3, B open Oct 3, 4, 5 → A gets Oct 3, B gets a different date
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3)])
    b = _make_attraction("B", 36.16, -86.78, [date(2026, 10, 3), date(2026, 10, 4), date(2026, 10, 5)])
    trip = _make_trip([a, b])
    eligible = filter_eligible_dates(trip)
    clusters = build_clusters([a, b])
    assignment = assign_dates(clusters, eligible, trip)
    assert assignment["A"] == date(2026, 10, 3)
    assert assignment["B"] != date(2026, 10, 3)


def test_assign_dates_respects_cluster_separation():
    # A and B in different clusters → assigned to different dates
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3), date(2026, 10, 4)])
    b = _make_attraction("B", 36.16, -86.78, [date(2026, 10, 3), date(2026, 10, 4)])
    trip = _make_trip([a, b])
    eligible = filter_eligible_dates(trip)
    clusters = build_clusters([a, b])  # A and B are far apart → different clusters
    assignment = assign_dates(clusters, eligible, trip)
    assert assignment["A"] != assignment["B"]


def test_assign_time_slots_single():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3)])
    entries = assign_time_slots([a], date(2026, 10, 3))
    assert len(entries) == 1
    assert entries[0].arrival_time == time(19, 0)


def test_assign_time_slots_multiple():
    # A opens 19:00, B opens 20:00, ~1mi apart
    a = Attraction(
        name="A", address="A address", lat=41.88, lng=-87.63,
        schedule_url="https://a.com",
        schedule=[ScheduleEntry(date=date(2026, 10, 3), open_time=time(19, 0), close_time=time(23, 0))],
    )
    b = Attraction(
        name="B", address="B address", lat=41.89, lng=-87.64,
        schedule_url="https://b.com",
        schedule=[ScheduleEntry(date=date(2026, 10, 3), open_time=time(20, 0), close_time=time(23, 0))],
    )
    entries = assign_time_slots([a, b], date(2026, 10, 3))
    scheduled = [e for e in entries if not e.bumped]
    assert len(scheduled) == 2
    # B arrival = 19:00 + 45min + drive_time(~1mi at 40mph = 1.5min) ≈ 19:46-19:47
    b_entry = next(e for e in scheduled if e.attraction.name == "B")
    assert b_entry.arrival_time.hour == 19
    assert 46 <= b_entry.arrival_time.minute <= 48


def test_assign_time_slots_rejects_late_arrival():
    # B closes 20:00; would arrive ~19:47, only 13min before close < 45min → bumped
    a = Attraction(
        name="A", address="A address", lat=41.88, lng=-87.63,
        schedule_url="https://a.com",
        schedule=[ScheduleEntry(date=date(2026, 10, 3), open_time=time(19, 0), close_time=time(23, 0))],
    )
    b = Attraction(
        name="B", address="B address", lat=41.89, lng=-87.64,
        schedule_url="https://b.com",
        schedule=[ScheduleEntry(date=date(2026, 10, 3), open_time=time(20, 0), close_time=time(20, 0))],
    )
    entries = assign_time_slots([a, b], date(2026, 10, 3))
    b_entry = next(e for e in entries if e.attraction.name == "B")
    assert b_entry.bumped is True


def test_optimize_full_pipeline():
    # A and B close together, C far away → A and B should be on the same date
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3), date(2026, 10, 4)])
    b = _make_attraction("B", 41.89, -87.64, [date(2026, 10, 3), date(2026, 10, 4)])
    c = _make_attraction("C", 36.16, -86.78, [date(2026, 10, 3), date(2026, 10, 4)])
    trip = _make_trip([a, b, c])
    result = optimize(trip)
    assert isinstance(result, ItineraryResult)
    # A and B should be on the same date (they're in the same cluster)
    ab_dates = {}
    for d, entries in result.scheduled.items():
        for entry in entries:
            if entry.attraction.name in ("A", "B"):
                ab_dates[entry.attraction.name] = d
    if "A" in ab_dates and "B" in ab_dates:
        assert ab_dates["A"] == ab_dates["B"]


# ---------------------------------------------------------------------------
# Phase 5: reoptimize
# ---------------------------------------------------------------------------

from optimizer import reoptimize


def test_reoptimize_locks_manual_assignment():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3), date(2026, 10, 4), date(2026, 10, 5)])
    trip = _make_trip([a])
    result = reoptimize(trip, locked={"A": date(2026, 10, 4)})
    # A must appear on Oct 4
    assert date(2026, 10, 4) in result.scheduled
    assert any(e.attraction.name == "A" for e in result.scheduled[date(2026, 10, 4)])


def test_reoptimize_returns_changed_entries():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3), date(2026, 10, 4)])
    b = _make_attraction("B", 36.16, -86.78, [date(2026, 10, 3), date(2026, 10, 4)])
    trip = _make_trip([a, b])
    result = reoptimize(trip, locked={})
    assert isinstance(result, ItineraryResult)
    total = sum(len(entries) for entries in result.scheduled.values())
    assert total >= 1
