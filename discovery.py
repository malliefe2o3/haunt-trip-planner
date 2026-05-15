# discovery.py
from dataclasses import dataclass
from datetime import date, time, timedelta
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Set

import requests
from bs4 import BeautifulSoup

from models import Trip, Attraction, ScheduleEntry
from geocoder import haversine_miles, drive_time_minutes
from optimizer import ItineraryResult

DIRECTORY_URLS = {
    "TheScareFactor": "https://www.thescarefactor.com",
    "HauntWorld": "https://www.hauntworld.com",
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
