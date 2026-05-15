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
