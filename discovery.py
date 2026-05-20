# discovery.py
import json
import os
import re
from dataclasses import dataclass
from datetime import date, time, timedelta
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Set

import requests
from bs4 import BeautifulSoup

from models import Trip, Attraction, ScheduleEntry, default_duration_for_name
from geocoder import haversine_miles, drive_time_minutes, geocode_address
from optimizer import ItineraryResult
from scraper import scrape_schedule

DB_PATH = os.path.join(os.path.dirname(__file__), "haunt_database.json")

DIRECTORY_URLS = {
    "TheScareFactor": "https://www.thescarefactor.com",
    "HauntedHouseAssociation": "https://www.hauntedhouseassociation.org",
    "HauntedHouseRatings": "https://www.hauntedhouseratings.com",
}


@dataclass
class DiscoverySuggestion:
    attraction: Attraction
    suggested_date: Optional[date]  # Python 3.9 compatible
    distance_miles: float
    suggestion_type: str  # "gap_filler" or "densifier"
    website_url: str


def deduplicate_attractions(attractions: List[Attraction]) -> List[Attraction]:
    unique: List[Attraction] = []
    for a in attractions:
        is_dupe = False
        for u in unique:
            name_sim = SequenceMatcher(None, a.name.lower(), u.name.lower()).ratio()
            dist = haversine_miles(a.lat, a.lng, u.lat, u.lng)
            if name_sim > 0.7 and dist < 1.0:
                is_dupe = True
                break
        if not is_dupe:
            unique.append(a)
    return unique


def find_gap_nights(trip: Trip, scheduled_dates: Set[date]) -> List[date]:
    gaps = []
    start, end = trip.date_range
    current = start
    while current <= end:
        if current not in scheduled_dates and current not in trip.blackout_dates:
            gaps.append(current)
        current += timedelta(days=1)
    return gaps


def find_densify_opportunities(
    itinerary: ItineraryResult,
    candidates: List[Attraction],
    radius_miles: float = 20.0,
) -> List[DiscoverySuggestion]:
    suggestions = []

    for d, entries in itinerary.scheduled.items():
        if not entries:
            continue
        last_entry = entries[-1]
        last_arrival_min = last_entry.arrival_time.hour * 60 + last_entry.arrival_time.minute
        last_done_min = last_arrival_min + 45

        for candidate in candidates:
            dist = haversine_miles(
                last_entry.attraction.lat, last_entry.attraction.lng,
                candidate.lat, candidate.lng,
            )
            if dist > radius_miles:
                continue

            cand_entry = next((e for e in candidate.schedule if e.date == d), None)
            if cand_entry is None:
                continue

            dt = drive_time_minutes(dist)
            cand_arrival_min = last_done_min + int(dt)

            close_min = cand_entry.close_time.hour * 60 + cand_entry.close_time.minute
            if cand_entry.close_time == time(0, 0):
                close_min = 24 * 60
            latest_allowed = close_min - 45

            if cand_arrival_min <= latest_allowed:
                suggestions.append(DiscoverySuggestion(
                    attraction=candidate,
                    suggested_date=d,
                    distance_miles=dist,
                    suggestion_type="densifier",
                    website_url=candidate.schedule_url,
                ))

    return suggestions


def scrape_directory(directory_name: str, state: str) -> List[dict]:
    try:
        url = DIRECTORY_URLS.get(directory_name)
        if not url:
            return []
        response = requests.get(
            f"{url}/search?state={state}",
            timeout=15,
            headers={"User-Agent": "HauntTripPlanner/1.0"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        listings = []
        for item in soup.select(".listing, .haunt-card, .attraction-item, article"):
            name_el = item.select_one("h2, h3, .name, .title")
            addr_el = item.select_one(".address, .location")
            link_el = item.select_one("a[href]")
            if name_el:
                listings.append({
                    "name": name_el.get_text(strip=True),
                    "address": addr_el.get_text(strip=True) if addr_el else "",
                    "url": link_el["href"] if link_el else "",
                    "source": directory_name,
                })
        return listings
    except Exception:
        return []


def _load_haunt_database() -> List[dict]:
    try:
        with open(DB_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return []


def _extract_state(address: str) -> Optional[str]:
    state_pattern = r"\b([A-Z]{2})\b"
    parts = address.split(",")
    for part in reversed(parts):
        match = re.search(state_pattern, part.strip())
        if match:
            return match.group(1)
    return None


def _dates_for_season(typical_season: dict, typical_days: List[str], year: int) -> List[date]:
    try:
        start_parts = typical_season["start"].split("-")
        end_parts = typical_season["end"].split("-")
        start = date(year, int(start_parts[0]), int(start_parts[1]))
        end = date(year, int(end_parts[0]), int(end_parts[1]))
    except (ValueError, KeyError):
        return []

    day_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    target_days = {day_map[d.lower()] for d in typical_days if d.lower() in day_map}
    if not target_days:
        target_days = {4, 5}

    dates = []
    current = start
    while current <= end:
        if current.weekday() in target_days:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def discover_with_schedules(
    trip: Trip,
    existing_names: Set[str],
    radius_miles: float = 50.0,
) -> List[DiscoverySuggestion]:
    trip_start, trip_end = trip.date_range
    trip_year = trip_start.year
    trip_dates = set()
    current = trip_start
    while current <= trip_end:
        if current not in trip.blackout_dates:
            trip_dates.add(current)
        current += timedelta(days=1)

    state = _extract_state(trip.home_base.address)
    db = _load_haunt_database()
    nearby_states = {state} if state else set()

    suggestions = []
    seen_names: Set[str] = set()

    for entry in db:
        name_lower = entry["name"].lower()
        if name_lower in existing_names or name_lower in seen_names:
            continue
        if not entry.get("address"):
            continue

        if state and entry.get("state") not in nearby_states:
            continue

        seen_names.add(name_lower)

        try:
            lat, lng = geocode_address(entry["address"])
        except Exception:
            continue

        dist = haversine_miles(trip.home_base.lat, trip.home_base.lng, lat, lng)
        if dist > radius_miles:
            continue

        season_dates = _dates_for_season(
            entry.get("typical_season", {}),
            entry.get("typical_days", ["friday", "saturday"]),
            trip_year,
        )
        matching_dates = sorted(d for d in season_dates if d in trip_dates)

        if not matching_dates:
            if entry.get("website"):
                try:
                    sched = scrape_schedule(entry["website"], trip_year)
                    matching_dates = sorted(d for d in sched.dates if d in trip_dates)
                except Exception:
                    pass

        if not matching_dates:
            continue

        dur = entry.get("estimated_duration_min", default_duration_for_name(entry["name"]))
        schedule_entries = []
        for d in matching_dates:
            schedule_entries.append(ScheduleEntry(
                date=d,
                open_time=time(19, 0),
                close_time=time(23, 0),
                duration_min=dur,
            ))

        attraction = Attraction(
            name=entry["name"],
            address=entry["address"],
            lat=lat, lng=lng,
            schedule_url=entry.get("website", ""),
            schedule=schedule_entries,
        )

        suggestions.append(DiscoverySuggestion(
            attraction=attraction,
            suggested_date=matching_dates[0],
            distance_miles=dist,
            suggestion_type="database_match",
            website_url=entry.get("website", ""),
        ))

    suggestions.sort(key=lambda s: s.distance_miles)
    return suggestions
