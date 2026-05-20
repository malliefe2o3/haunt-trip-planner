# optimizer.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time, datetime, timedelta
from typing import Optional, Dict, List, Tuple

from models import Attraction, Trip, Segment, Location
from geocoder import haversine_miles, drive_time_minutes


# ---------------------------------------------------------------------------
# Auto-weekend segments
# ---------------------------------------------------------------------------

def _generate_weekend_segments(trip: Trip) -> List[Segment]:
    trip_start, trip_end = trip.date_range
    user_covered = set()
    for seg in trip.segments:
        s, e = seg.date_range
        cur = s
        while cur <= e:
            user_covered.add(cur)
            cur += timedelta(days=1)

    weekends: List[Segment] = []
    cur = trip_start
    while cur <= trip_end:
        if cur.weekday() == 4 and cur not in user_covered:  # Friday
            fri = cur
            sun = fri + timedelta(days=2)
            seg_end = min(sun, trip_end)
            start_dates_covered = any(
                fri <= d <= seg_end for d in user_covered
            )
            if not start_dates_covered:
                weekends.append(Segment(
                    date_range=(fri, seg_end),
                    start_location=trip.home_base,
                    end_location=trip.home_base,
                ))
        cur += timedelta(days=1)

    return weekends


def _all_segments(trip: Trip) -> List[Segment]:
    return trip.segments + _generate_weekend_segments(trip)


# ---------------------------------------------------------------------------
# Phase 1: filter_eligible_dates
# ---------------------------------------------------------------------------

def filter_eligible_dates(trip: Trip) -> Dict[str, List[date]]:
    trip_start, trip_end = trip.date_range
    all_segs = _all_segments(trip)

    result: Dict[str, List[date]] = {}

    for attraction in trip.attractions:
        if attraction.assigned_dates is not None:
            result[attraction.name] = sorted(attraction.assigned_dates)
            continue

        all_dates = [entry.date for entry in attraction.schedule]
        in_range = [d for d in all_dates if trip_start <= d <= trip_end]
        eligible = [d for d in in_range if d not in trip.blackout_dates]

        if all_segs:
            segment = _assign_segment(attraction, all_segs, eligible)
            if segment is not None:
                seg_start, seg_end = segment.date_range
                eligible = [d for d in eligible if seg_start <= d <= seg_end]

        result[attraction.name] = sorted(eligible)

    return result


def _assign_segment(
    attraction: Attraction, segments: List[Segment], eligible_dates: List[date]
) -> Optional[Segment]:
    if not segments:
        return None

    best = None
    best_score = (float("inf"), 0)

    for seg in segments:
        dist = haversine_miles(
            attraction.lat, attraction.lng,
            seg.start_location.lat, seg.start_location.lng,
        )
        seg_start, seg_end = seg.date_range
        count = sum(1 for d in eligible_dates if seg_start <= d <= seg_end)
        if count == 0:
            continue
        score = (dist, -count)
        if score < best_score:
            best_score = score
            best = seg

    return best


def _get_segment_for_date(trip: Trip, d: date) -> Optional[Segment]:
    for seg in _all_segments(trip):
        seg_start, seg_end = seg.date_range
        if seg_start <= d <= seg_end:
            return seg
    return None


def _get_reference_location(trip: Trip, d: date) -> Location:
    seg = _get_segment_for_date(trip, d)
    if seg is not None:
        return seg.start_location
    return trip.home_base


def _is_segment_final_day(trip: Trip, d: date) -> bool:
    for seg in _all_segments(trip):
        if seg.date_range[1] == d:
            return True
    return False


def _get_end_location_for_date(trip: Trip, d: date) -> Optional[Location]:
    for seg in _all_segments(trip):
        if seg.date_range[1] == d:
            return seg.end_location
    return None

MAX_END_DRIVE_MILES = 50.0


# ---------------------------------------------------------------------------
# Phase 2: build_clusters
# ---------------------------------------------------------------------------

def build_clusters(attractions: List[Attraction], radius_miles: float = 20.0) -> List[List[Attraction]]:
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
    drive_time_min: Optional[int] = None
    duration_min: int = 45
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
    if t == time(0, 0):
        return 24 * 60
    return t.hour * 60 + t.minute


def _minutes_to_time(minutes: int) -> time:
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
    assignment: Dict[str, Optional[date]] = {a.name: None for cluster in clusters for a in cluster}
    used_dates: set = set()

    def cluster_scarcity(cluster: List[Attraction]) -> Tuple[int, float]:
        min_dates = min(len(eligible.get(a.name, [])) for a in cluster)
        avg_dist = sum(
            haversine_miles(trip.home_base.lat, trip.home_base.lng, a.lat, a.lng)
            for a in cluster
        ) / len(cluster)
        return (min_dates, avg_dist)

    sorted_clusters = sorted(clusters, key=cluster_scarcity)

    for cluster in sorted_clusters:
        sorted_attractions = sorted(cluster, key=lambda a: len(eligible.get(a.name, [])))

        candidate_dates: List[date] = []
        for a in cluster:
            for d in eligible.get(a.name, []):
                if d not in candidate_dates:
                    candidate_dates.append(d)
        candidate_dates = sorted(d for d in candidate_dates if d not in used_dates)

        if not candidate_dates:
            continue

        def date_score(d: date) -> Tuple[int, float]:
            coverage = sum(1 for a in cluster if d in eligible.get(a.name, []))
            ref_loc = _get_reference_location(trip, d)
            centroid_lat = sum(a.lat for a in cluster) / len(cluster)
            centroid_lng = sum(a.lng for a in cluster) / len(cluster)
            dist_to_ref = haversine_miles(centroid_lat, centroid_lng, ref_loc.lat, ref_loc.lng)
            avg_inter_dist = 0.0
            if len(cluster) > 1:
                pairs = 0
                for i in range(len(cluster)):
                    if d not in eligible.get(cluster[i].name, []):
                        continue
                    for j in range(i + 1, len(cluster)):
                        if d not in eligible.get(cluster[j].name, []):
                            continue
                        avg_inter_dist += haversine_miles(
                            cluster[i].lat, cluster[i].lng,
                            cluster[j].lat, cluster[j].lng,
                        )
                        pairs += 1
                if pairs > 0:
                    avg_inter_dist /= pairs

            end_penalty = 0.0
            if _is_segment_final_day(trip, d):
                end_loc = _get_end_location_for_date(trip, d)
                if end_loc is not None:
                    dist_to_end = haversine_miles(centroid_lat, centroid_lng, end_loc.lat, end_loc.lng)
                    if dist_to_end > MAX_END_DRIVE_MILES:
                        end_penalty = 1000.0

            return (-coverage, dist_to_ref + avg_inter_dist + end_penalty)

        best_date = min(candidate_dates, key=date_score)
        used_dates.add(best_date)

        for a in sorted_attractions:
            if best_date in eligible.get(a.name, []):
                assignment[a.name] = best_date

    return assignment


# ---------------------------------------------------------------------------
# Phase 4: assign_time_slots
# ---------------------------------------------------------------------------

def assign_time_slots(
    attractions: List[Attraction],
    target_date: date,
    trip: Optional[Trip] = None,
) -> List[ItineraryEntry]:
    dated: List[Tuple[Attraction, time, time, Optional[float], Optional[str], int]] = []
    for a in attractions:
        for entry in a.schedule:
            if entry.date == target_date:
                dated.append((a, entry.open_time, entry.close_time, entry.price, entry.ticket_url, entry.duration_min))
                break

    if not dated:
        return []

    end_loc = None
    is_final = False
    if trip is not None and _is_segment_final_day(trip, target_date):
        end_loc = _get_end_location_for_date(trip, target_date)
        is_final = True

    if is_final and end_loc is not None:
        dated.sort(key=lambda x: (
            _time_to_minutes(x[1]),
            haversine_miles(x[0].lat, x[0].lng, end_loc.lat, end_loc.lng),
        ))
    else:
        dated.sort(key=lambda x: _time_to_minutes(x[1]))

    entries: List[ItineraryEntry] = []
    prev_attraction: Optional[Attraction] = None
    prev_arrival_min: Optional[int] = None
    prev_duration: int = 45

    for a, open_time, close_time, price, ticket_url, dur_min in dated:
        close_min = _time_to_minutes(close_time)
        cur_drive_min = None

        if prev_arrival_min is None:
            arrival_min = _time_to_minutes(open_time)
        else:
            dist = haversine_miles(prev_attraction.lat, prev_attraction.lng, a.lat, a.lng)
            drive_min = drive_time_minutes(dist)
            cur_drive_min = round(drive_min)
            arrival_min = prev_arrival_min + prev_duration + cur_drive_min

        entry = ItineraryEntry(
            attraction=a,
            date=target_date,
            arrival_time=_minutes_to_time(arrival_min),
            open_time=open_time,
            close_time=close_time,
            price=price,
            ticket_url=ticket_url,
            drive_time_min=cur_drive_min,
            duration_min=dur_min,
        )

        if arrival_min > close_min - dur_min:
            entry.bumped = True
            entry.bump_reason = (
                f"Would arrive at {_minutes_to_time(arrival_min).strftime('%H:%M')}, "
                f"but close is {close_time.strftime('%H:%M')} (need {dur_min} min minimum)"
            )
        else:
            prev_attraction = a
            prev_arrival_min = arrival_min
            prev_duration = dur_min

        entries.append(entry)

    if is_final and end_loc is not None:
        scheduled = [e for e in entries if not e.bumped]
        if scheduled:
            last = scheduled[-1]
            dist_to_end = haversine_miles(
                last.attraction.lat, last.attraction.lng,
                end_loc.lat, end_loc.lng,
            )
            if dist_to_end > MAX_END_DRIVE_MILES:
                last.bumped = True
                last.bump_reason = (
                    f"Too far from segment end location "
                    f"({dist_to_end:.0f} mi, max {MAX_END_DRIVE_MILES:.0f} mi)"
                )

    return entries


# ---------------------------------------------------------------------------
# Phase 4: optimize
# ---------------------------------------------------------------------------

def _is_final_day(trip: Trip, d: date) -> bool:
    if d == trip.date_range[1]:
        return True
    return _is_segment_final_day(trip, d)


def optimize(trip: Trip) -> ItineraryResult:
    eligible = filter_eligible_dates(trip)
    clusters = build_clusters(trip.attractions)
    date_assignment = assign_dates(clusters, eligible, trip)

    by_date: Dict[date, List[Attraction]] = {}
    for a in trip.attractions:
        d = date_assignment.get(a.name)
        if d is not None:
            by_date.setdefault(d, []).append(a)

    scheduled: Dict[date, List[ItineraryEntry]] = {}
    unscheduled: List[Tuple[Attraction, str]] = []
    end_loc_bumped: List[Attraction] = []

    for d, day_attractions in by_date.items():
        entries = assign_time_slots(day_attractions, d, trip)
        day_scheduled = []
        for entry in entries:
            if entry.bumped:
                if "Too far from segment end location" in entry.bump_reason:
                    end_loc_bumped.append(entry.attraction)
                else:
                    unscheduled.append((entry.attraction, entry.bump_reason))
            else:
                day_scheduled.append(entry)
        if day_scheduled:
            scheduled[d] = day_scheduled

    for a in end_loc_bumped:
        non_final_dates = [
            d for d in eligible.get(a.name, [])
            if not _is_final_day(trip, d)
            and d not in scheduled
        ]
        if non_final_dates:
            best = min(non_final_dates)
            new_entries = assign_time_slots([a], best, trip)
            good = [e for e in new_entries if not e.bumped]
            if good:
                scheduled.setdefault(best, []).extend(good)
            else:
                unscheduled.append((a, "Too far from end location on all eligible dates"))
        else:
            non_final_shared = [
                d for d in eligible.get(a.name, [])
                if not _is_final_day(trip, d)
            ]
            placed = False
            for d in sorted(non_final_shared):
                existing = scheduled.get(d, [])
                test_attractions = [e.attraction for e in existing] + [a]
                new_entries = assign_time_slots(test_attractions, d, trip)
                good = [e for e in new_entries if not e.bumped]
                if any(e.attraction.name == a.name for e in good):
                    scheduled[d] = good
                    placed = True
                    break
            if not placed:
                unscheduled.append((a, "Too far from end location on all eligible dates"))

    for a in trip.attractions:
        if date_assignment.get(a.name) is None and a not in [x[0] for x in unscheduled]:
            unscheduled.append((a, "No eligible dates found"))

    return ItineraryResult(scheduled=scheduled, unscheduled=unscheduled)


# ---------------------------------------------------------------------------
# Phase 5: reoptimize
# ---------------------------------------------------------------------------

def reoptimize(trip: Trip, locked: Dict[str, date]) -> ItineraryResult:
    for attraction in trip.attractions:
        if attraction.name in locked:
            attraction.assigned_dates = [locked[attraction.name]]
        else:
            attraction.assigned_dates = None
    return optimize(trip)
