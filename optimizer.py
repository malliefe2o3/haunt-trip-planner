# optimizer.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, datetime, timedelta
from typing import Optional, Dict, List, Tuple

from models import Attraction, Trip, Leg, Location
from geocoder import haversine_miles, drive_time_minutes


# ---------------------------------------------------------------------------
# Phase 1: filter_eligible_dates
# ---------------------------------------------------------------------------

def filter_eligible_dates(trip: Trip) -> Dict[str, List[date]]:
    """Return dict mapping attraction name → list of eligible dates."""
    trip_start, trip_end = trip.date_range

    result: Dict[str, List[date]] = {}

    for attraction in trip.attractions:
        # If assigned_dates is set, lock to those only
        if attraction.assigned_dates is not None:
            result[attraction.name] = sorted(attraction.assigned_dates)
            continue

        # Collect all scheduled dates
        all_dates = [entry.date for entry in attraction.schedule]

        # Remove out-of-range dates
        in_range = [d for d in all_dates if trip_start <= d <= trip_end]

        # Remove blackout dates
        eligible = [d for d in in_range if d not in trip.blackout_dates]

        # If legs exist, restrict to dates within the attraction's assigned leg
        if trip.legs:
            leg = _assign_leg(attraction, trip.legs, eligible)
            if leg is not None:
                leg_start, leg_end = leg.date_range
                eligible = [d for d in eligible if leg_start <= d <= leg_end]

        result[attraction.name] = sorted(eligible)

    return result


def _assign_leg(attraction: Attraction, legs: List[Leg], eligible_dates: List[date]) -> Optional[Leg]:
    """Find the leg whose start_location is nearest to the attraction.
    Tiebreak: leg with more open dates in its range."""
    if not legs:
        return None

    def leg_score(leg: Leg) -> Tuple[float, int]:
        dist = haversine_miles(
            attraction.lat, attraction.lng,
            leg.start_location.lat, leg.start_location.lng,
        )
        # Count how many eligible dates fall in this leg's range
        leg_start, leg_end = leg.date_range
        count = sum(1 for d in eligible_dates if leg_start <= d <= leg_end)
        return (dist, -count)  # sort by dist asc, then by count desc

    return min(legs, key=leg_score)


# ---------------------------------------------------------------------------
# Phase 2: build_clusters
# ---------------------------------------------------------------------------

def build_clusters(attractions: List[Attraction], radius_miles: float = 20.0) -> List[List[Attraction]]:
    """Union-Find clustering: group attractions within radius_miles of each other (transitive)."""
    n = len(attractions)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            dist = haversine_miles(
                attractions[i].lat, attractions[i].lng,
                attractions[j].lat, attractions[j].lng,
            )
            if dist <= radius_miles:
                union(i, j)

    # Group by root
    groups: Dict[int, List[Attraction]] = {}
    for i, attraction in enumerate(attractions):
        root = find(i)
        groups.setdefault(root, []).append(attraction)

    return list(groups.values())


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ItineraryEntry:
    attraction: Attraction
    date: date
    arrival_time: time
    open_time: time
    close_time: time
    price: Optional[float] = None
    ticket_url: Optional[str] = None
    bumped: bool = False
    bump_reason: str = ""


@dataclass
class ItineraryResult:
    scheduled: Dict[date, List[ItineraryEntry]]
    unscheduled: List[Tuple[Attraction, str]]


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def _time_to_minutes(t: time) -> int:
    """Convert time to minutes since midnight. time(0,0) treated as 24*60=1440."""
    if t == time(0, 0):
        return 24 * 60
    return t.hour * 60 + t.minute


def _minutes_to_time(minutes: int) -> time:
    """Convert minutes since midnight to time object (clamp to same day)."""
    minutes = minutes % (24 * 60)
    return time(minutes // 60, minutes % 60)


# ---------------------------------------------------------------------------
# Phase 3: assign_dates
# ---------------------------------------------------------------------------

def assign_dates(
    clusters: List[List[Attraction]],
    eligible: Dict[str, List[date]],
    trip: Trip,
) -> Dict[str, Optional[date]]:
    """Assign a single date to each attraction.

    Strategy:
    - Score each cluster by: (min eligible dates across members, then travel distance)
    - Process clusters in ascending scarcity order
    - Within a cluster, assign attractions with fewest dates first
    - Pick the date where most cluster members are also open
    - Enforce: different clusters can't share a date
    """
    assignment: Dict[str, Optional[date]] = {a.name: None for cluster in clusters for a in cluster}
    used_dates: set = set()  # dates claimed by completed clusters

    def cluster_scarcity(cluster: List[Attraction]) -> Tuple[int, float]:
        # min eligible dates in cluster
        min_dates = min(len(eligible.get(a.name, [])) for a in cluster)
        # average distance from trip start_location
        avg_dist = sum(
            haversine_miles(trip.start_location.lat, trip.start_location.lng, a.lat, a.lng)
            for a in cluster
        ) / len(cluster)
        return (min_dates, avg_dist)

    sorted_clusters = sorted(clusters, key=cluster_scarcity)

    for cluster in sorted_clusters:
        # Sort attractions within cluster by fewest eligible dates first
        sorted_attractions = sorted(cluster, key=lambda a: len(eligible.get(a.name, [])))

        # Collect candidate dates for cluster (union of all member eligible dates)
        candidate_dates: List[date] = []
        for a in cluster:
            for d in eligible.get(a.name, []):
                if d not in candidate_dates:
                    candidate_dates.append(d)
        candidate_dates = sorted(d for d in candidate_dates if d not in used_dates)

        if not candidate_dates:
            # No dates available for this cluster
            continue

        # Pick the date where the most cluster members are open
        def date_coverage(d: date) -> int:
            return sum(1 for a in cluster if d in eligible.get(a.name, []))

        best_date = max(candidate_dates, key=date_coverage)
        used_dates.add(best_date)

        # Assign all attractions in cluster that are open on best_date
        for a in sorted_attractions:
            if best_date in eligible.get(a.name, []):
                assignment[a.name] = best_date

    return assignment


# ---------------------------------------------------------------------------
# Phase 4: assign_time_slots
# ---------------------------------------------------------------------------

def assign_time_slots(attractions: List[Attraction], target_date: date) -> List[ItineraryEntry]:
    """Build timed entries for attractions on a given date.

    - Sort by opening time
    - First haunt: arrival = open time
    - Subsequent: arrival = prev_arrival + 45min + drive_time
    - Hard constraint: arrival <= close_time - 45min, else bumped
    """
    # Collect entries that have a schedule for target_date
    dated: List[Tuple[Attraction, time, time, Optional[float], Optional[str]]] = []
    for a in attractions:
        for entry in a.schedule:
            if entry.date == target_date:
                dated.append((a, entry.open_time, entry.close_time, entry.price, entry.ticket_url))
                break

    if not dated:
        return []

    # Sort by open_time (treat midnight as 24:00 for sorting)
    dated.sort(key=lambda x: _time_to_minutes(x[1]))

    entries: List[ItineraryEntry] = []
    prev_attraction: Optional[Attraction] = None
    prev_arrival_min: Optional[int] = None

    for a, open_time, close_time, price, ticket_url in dated:
        close_min = _time_to_minutes(close_time)

        if prev_arrival_min is None:
            # First attraction
            arrival_min = _time_to_minutes(open_time)
        else:
            # drive from prev to this attraction
            dist = haversine_miles(prev_attraction.lat, prev_attraction.lng, a.lat, a.lng)
            drive_min = drive_time_minutes(dist)
            arrival_min = prev_arrival_min + 45 + round(drive_min)

        # Check hard constraint: must arrive at least 45min before close
        entry = ItineraryEntry(
            attraction=a,
            date=target_date,
            arrival_time=_minutes_to_time(arrival_min),
            open_time=open_time,
            close_time=close_time,
            price=price,
            ticket_url=ticket_url,
        )

        if arrival_min > close_min - 45:
            entry.bumped = True
            entry.bump_reason = (
                f"Would arrive at {_minutes_to_time(arrival_min).strftime('%H:%M')}, "
                f"but close is {close_time.strftime('%H:%M')} (need 45 min minimum)"
            )
        else:
            prev_attraction = a
            prev_arrival_min = arrival_min

        entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# Phase 4: optimize
# ---------------------------------------------------------------------------

def optimize(trip: Trip) -> ItineraryResult:
    """Run full pipeline: filter → cluster → assign_dates → assign_time_slots."""
    eligible = filter_eligible_dates(trip)
    clusters = build_clusters(trip.attractions)
    date_assignment = assign_dates(clusters, eligible, trip)

    # Group attractions by assigned date
    by_date: Dict[date, List[Attraction]] = {}
    for a in trip.attractions:
        d = date_assignment.get(a.name)
        if d is not None:
            by_date.setdefault(d, []).append(a)

    scheduled: Dict[date, List[ItineraryEntry]] = {}
    unscheduled: List[Tuple[Attraction, str]] = []

    for d, attractions in by_date.items():
        entries = assign_time_slots(attractions, d)
        day_scheduled = []
        for entry in entries:
            if entry.bumped:
                unscheduled.append((entry.attraction, entry.bump_reason))
            else:
                day_scheduled.append(entry)
        if day_scheduled:
            scheduled[d] = day_scheduled

    # Attractions with no date assigned
    for a in trip.attractions:
        if date_assignment.get(a.name) is None:
            unscheduled.append((a, "No eligible dates found"))

    return ItineraryResult(scheduled=scheduled, unscheduled=unscheduled)


# ---------------------------------------------------------------------------
# Phase 5: reoptimize
# ---------------------------------------------------------------------------

def reoptimize(trip: Trip, locked: Dict[str, date]) -> ItineraryResult:
    """Re-run optimize with manual locks applied to attractions."""
    for attraction in trip.attractions:
        if attraction.name in locked:
            attraction.assigned_dates = [locked[attraction.name]]
        else:
            attraction.assigned_dates = None
    return optimize(trip)
