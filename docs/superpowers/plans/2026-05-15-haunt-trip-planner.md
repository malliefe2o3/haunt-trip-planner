# Haunt Trip Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a downloadable Python/Flask app that optimizes multi-night haunted attraction trips with schedule scraping, proximity-based clustering, and itinerary generation.

**Architecture:** Flask monolith serving a spooky-themed web UI. Backend modules for geocoding (Nominatim), schedule scraping (regex + optional Claude API), itinerary optimization (constraint filtering → clustering → date/time assignment), and haunt discovery (multi-directory scraping). All data lives in memory — no database.

**Tech Stack:** Python 3.8+, Flask, requests, BeautifulSoup4, geopy, anthropic SDK (optional)

---

## File Structure

```
trip-planner/
├── hauntplanner.py              # Entry point — creates Flask app, runs server
├── requirements.txt             # Dependencies
├── models.py                    # Dataclasses: Trip, Leg, Attraction, ScheduleEntry, Location
├── geocoder.py                  # Nominatim geocoding + haversine distance + drive time
├── scraper.py                   # Tier 1 regex parser + Tier 2 LLM parser
├── optimizer.py                 # Phases 1-5: filtering, clustering, date/time assignment, re-opt
├── discovery.py                 # Multi-directory scraping, gap-fill + densify suggestions
├── exporter.py                  # Standalone HTML export generation
├── templates/
│   ├── base.html                # Base template with spooky theme, nav, fog animation
│   ├── setup.html               # Screen 1: trip dates, locations, legs, blackouts
│   ├── attractions.html         # Screen 2: add attractions form
│   ├── loading.html             # Screen 3: scraping progress
│   ├── review.html              # Screen 4: schedule review + inline editing
│   ├── itinerary.html           # Screen 5+6: itinerary view + adjustment panel
│   └── export.html              # Screen 7: print-optimized view
├── static/
│   ├── style.css                # Spooky theme: dark bg, cobwebs, drip effects, fog
│   └── app.js                   # Frontend logic: form handling, fetch calls, DOM updates
└── tests/
    ├── conftest.py              # Shared fixtures: sample trips, attractions, schedules
    ├── test_models.py           # Data model validation
    ├── test_geocoder.py         # Geocoding, distance, drive time
    ├── test_scraper.py          # Regex parsing + LLM parsing
    ├── test_optimizer.py        # All optimizer phases
    ├── test_discovery.py        # Directory scraping + suggestion logic
    ├── test_exporter.py         # HTML export generation
    └── test_app.py              # Flask route integration tests
```

---

### Task 1: Project Setup + Data Models

**Files:**
- Create: `requirements.txt`
- Create: `models.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Create requirements.txt**

```
Flask==3.1.1
requests==2.32.3
beautifulsoup4==4.13.4
geopy==2.4.1
anthropic==0.52.0
pytest==8.3.5
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully.

- [ ] **Step 3: Write test fixtures in conftest.py**

```python
# tests/conftest.py
import pytest
from datetime import date, time
from models import Location, ScheduleEntry, Attraction, Leg, Trip


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
def sample_leg():
    return Leg(
        date_range=(date(2026, 10, 1), date(2026, 10, 7)),
        start_location=Location("Chicago, IL", 41.8781, -87.6298),
        end_location=Location("Chicago, IL", 41.8781, -87.6298),
    )


@pytest.fixture
def sample_trip(sample_attraction, sample_leg):
    return Trip(
        date_range=(date(2026, 10, 1), date(2026, 10, 14)),
        start_location=Location("Chicago, IL", 41.8781, -87.6298),
        end_location=Location("Chicago, IL", 41.8781, -87.6298),
        blackout_dates=[date(2026, 10, 5)],
        legs=[sample_leg],
        attractions=[sample_attraction],
    )
```

- [ ] **Step 4: Write failing tests for data models**

```python
# tests/test_models.py
from datetime import date, time
from models import Location, ScheduleEntry, Attraction, Leg, Trip


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


def test_leg_fields(sample_leg):
    assert sample_leg.date_range == (date(2026, 10, 1), date(2026, 10, 7))
    assert sample_leg.start_location.address == "Chicago, IL"


def test_trip_fields(sample_trip):
    assert sample_trip.date_range == (date(2026, 10, 1), date(2026, 10, 14))
    assert len(sample_trip.blackout_dates) == 1
    assert len(sample_trip.legs) == 1
    assert len(sample_trip.attractions) == 1


def test_trip_no_legs():
    trip = Trip(
        date_range=(date(2026, 10, 1), date(2026, 10, 14)),
        start_location=Location("Chicago, IL", 41.8781, -87.6298),
        end_location=Location("Chicago, IL", 41.8781, -87.6298),
        blackout_dates=[],
        legs=[],
        attractions=[],
    )
    assert trip.legs == []
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 6: Implement data models**

```python
# models.py
from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional


@dataclass
class Location:
    address: str
    lat: float
    lng: float


@dataclass
class ScheduleEntry:
    date: date
    open_time: time
    close_time: time
    price: Optional[float] = None
    ticket_url: Optional[str] = None


@dataclass
class Attraction:
    name: str
    address: str
    lat: float
    lng: float
    schedule_url: str
    assigned_dates: Optional[list[date]] = None
    schedule: list[ScheduleEntry] = field(default_factory=list)


@dataclass
class Leg:
    date_range: tuple[date, date]
    start_location: Location
    end_location: Location


@dataclass
class Trip:
    date_range: tuple[date, date]
    start_location: Location
    end_location: Location
    blackout_dates: list[date] = field(default_factory=list)
    legs: list[Leg] = field(default_factory=list)
    attractions: list[Attraction] = field(default_factory=list)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_models.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt models.py tests/conftest.py tests/test_models.py
git commit -m "feat: add project setup and data models"
```

---

### Task 2: Geocoder Module

**Files:**
- Create: `geocoder.py`
- Create: `tests/test_geocoder.py`

- [ ] **Step 1: Write failing tests for geocoder**

```python
# tests/test_geocoder.py
import math
from geocoder import geocode_address, haversine_miles, drive_time_minutes, find_nearby


def test_haversine_known_distance():
    # Chicago to Springfield IL is ~185 miles
    dist = haversine_miles(41.8781, -87.6298, 39.7817, -89.6501)
    assert 180 < dist < 190


def test_haversine_same_point():
    dist = haversine_miles(41.8781, -87.6298, 41.8781, -87.6298)
    assert dist == 0.0


def test_haversine_short_distance():
    # Two points ~10 miles apart (approx)
    dist = haversine_miles(41.8781, -87.6298, 41.8781, -87.4800)
    assert 5 < dist < 15


def test_drive_time_short_distance():
    # 8 miles at 40 mph = 12 minutes
    minutes = drive_time_minutes(8.0)
    assert minutes == 12.0


def test_drive_time_medium_distance():
    # 15 miles at 50 mph = 18 minutes
    minutes = drive_time_minutes(15.0)
    assert minutes == 18.0


def test_drive_time_zero():
    minutes = drive_time_minutes(0.0)
    assert minutes == 0.0


def test_find_nearby_within_radius():
    center = (41.8781, -87.6298)
    points = [
        ("A", 41.88, -87.63),   # very close
        ("B", 41.90, -87.65),   # close
        ("C", 39.78, -89.65),   # far away (~185 miles)
    ]
    nearby = find_nearby(center, points, radius_miles=20.0)
    names = [n[0] for n in nearby]
    assert "A" in names
    assert "B" in names
    assert "C" not in names


def test_find_nearby_empty():
    center = (41.8781, -87.6298)
    nearby = find_nearby(center, [], radius_miles=20.0)
    assert nearby == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_geocoder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'geocoder'`

- [ ] **Step 3: Implement geocoder module**

```python
# geocoder.py
import math
import time as time_module
from geopy.geocoders import Nominatim

_geolocator = Nominatim(user_agent="haunt-trip-planner")
_geocode_cache: dict[str, tuple[float, float]] = {}


def geocode_address(address: str) -> tuple[float, float]:
    if address in _geocode_cache:
        return _geocode_cache[address]
    time_module.sleep(1)  # Nominatim rate limit
    location = _geolocator.geocode(address)
    if location is None:
        raise ValueError(f"Could not geocode address: {address}")
    result = (location.latitude, location.longitude)
    _geocode_cache[address] = result
    return result


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 3958.8  # Earth radius in miles
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def drive_time_minutes(distance_miles: float) -> float:
    if distance_miles <= 0:
        return 0.0
    mph = 40.0 if distance_miles <= 10 else 50.0
    return (distance_miles / mph) * 60


def find_nearby(
    center: tuple[float, float],
    points: list[tuple[str, float, float]],
    radius_miles: float,
) -> list[tuple[str, float, float, float]]:
    results = []
    for name, lat, lng in points:
        dist = haversine_miles(center[0], center[1], lat, lng)
        if dist <= radius_miles:
            results.append((name, lat, lng, dist))
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_geocoder.py -v`
Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add geocoder.py tests/test_geocoder.py
git commit -m "feat: add geocoder with haversine distance and drive time"
```

---

### Task 3: Schedule Scraper — Tier 1 (Regex/Heuristic)

**Files:**
- Create: `scraper.py`
- Create: `tests/test_scraper.py`

- [ ] **Step 1: Write failing tests for Tier 1 scraper**

```python
# tests/test_scraper.py
from datetime import date, time
from scraper import (
    parse_dates_from_text,
    parse_times_from_text,
    parse_prices_from_text,
    find_ticket_links,
    scrape_schedule,
    ScrapedSchedule,
)


def test_parse_explicit_date_list():
    text = "Open Oct 4, 5, 11, 12, 18, 19"
    dates = parse_dates_from_text(text, year=2026)
    assert date(2026, 10, 4) in dates
    assert date(2026, 10, 19) in dates
    assert len(dates) == 6


def test_parse_date_range():
    text = "Open September 27 - November 2"
    dates = parse_dates_from_text(text, year=2026)
    assert date(2026, 9, 27) in dates
    assert date(2026, 11, 2) in dates
    assert len(dates) == 37


def test_parse_day_of_week_rule():
    text = "Every Friday and Saturday in October"
    dates = parse_dates_from_text(text, year=2026)
    # Oct 2026: Fri 2,9,16,23,30 + Sat 3,10,17,24,31 = 10 dates
    assert len(dates) == 10
    assert all(d.weekday() in (4, 5) for d in dates)


def test_parse_time_range_standard():
    text = "7:00 PM - 12:00 AM"
    times = parse_times_from_text(text)
    assert times == [(time(19, 0), time(0, 0))]


def test_parse_time_range_no_minutes():
    text = "7PM-Midnight"
    times = parse_times_from_text(text)
    assert times == [(time(19, 0), time(0, 0))]


def test_parse_time_dusk():
    text = "Dusk to 11PM"
    times = parse_times_from_text(text)
    assert times == [(time(18, 30), time(23, 0))]


def test_parse_prices_single():
    text = "General Admission $25"
    prices = parse_prices_from_text(text)
    assert 25.0 in prices


def test_parse_prices_day_specific():
    text = "Fri/Sat $30, Sun-Thu $20"
    prices = parse_prices_from_text(text)
    assert 30.0 in prices
    assert 20.0 in prices


def test_find_ticket_links():
    html = '''
    <a href="https://example.com/about">About</a>
    <a href="https://example.com/buy-tickets">Buy Tickets</a>
    <a href="https://www.eventbrite.com/e/haunted-123">Eventbrite</a>
    '''
    links = find_ticket_links(html)
    assert "https://example.com/buy-tickets" in links
    assert "https://www.eventbrite.com/e/haunted-123" in links
    assert "https://example.com/about" not in links


def test_scraped_schedule_confidence_green():
    s = ScrapedSchedule(
        dates=[date(2026, 10, 4)],
        time_ranges=[(time(19, 0), time(23, 0))],
        prices=[25.0],
        ticket_urls=["https://example.com/tickets"],
    )
    assert s.confidence == "green"


def test_scraped_schedule_confidence_yellow():
    s = ScrapedSchedule(
        dates=[date(2026, 10, 4)],
        time_ranges=[(time(19, 0), time(23, 0))],
        prices=[],
        ticket_urls=[],
    )
    assert s.confidence == "yellow"


def test_scraped_schedule_confidence_red():
    s = ScrapedSchedule(dates=[], time_ranges=[], prices=[], ticket_urls=[])
    assert s.confidence == "red"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_scraper.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scraper'`

- [ ] **Step 3: Implement Tier 1 scraper**

```python
# scraper.py
import re
import calendar
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

MONTH_NAMES = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTH_ABBREVS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
ALL_MONTHS = {**MONTH_NAMES, **MONTH_ABBREVS}

DAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3,
    "fri": 4, "sat": 5, "sun": 6,
}

TICKET_KEYWORDS = ["ticket", "buy", "purchase", "admission", "book"]
TICKET_PLATFORMS = ["eventbrite.com", "hauntpay.com", "feartickets.com", "etix.com"]


@dataclass
class ScrapedSchedule:
    dates: list[date]
    time_ranges: list[tuple[time, time]]
    prices: list[float]
    ticket_urls: list[str]

    @property
    def confidence(self) -> str:
        has_dates = len(self.dates) > 0
        has_times = len(self.time_ranges) > 0
        has_prices = len(self.prices) > 0
        if has_dates and has_times and has_prices:
            return "green"
        if has_dates or has_times:
            return "yellow"
        return "red"


def parse_dates_from_text(text: str, year: int) -> list[date]:
    dates = set()
    _parse_day_of_week_rules(text, year, dates)
    _parse_date_ranges(text, year, dates)
    _parse_explicit_date_lists(text, year, dates)
    return sorted(dates)


def _parse_day_of_week_rules(text: str, year: int, dates: set[date]) -> None:
    pattern = r"every\s+((?:(?:and|&|,|\s)+(?:" + "|".join(DAY_NAMES.keys()) + r"))+)\s+in\s+(\w+)"
    for match in re.finditer(pattern, text, re.IGNORECASE):
        days_text = match.group(1)
        month_text = match.group(2).lower()
        if month_text not in ALL_MONTHS:
            continue
        month = ALL_MONTHS[month_text]
        target_days = set()
        for day_name, day_num in DAY_NAMES.items():
            if re.search(r'\b' + day_name + r'\b', days_text, re.IGNORECASE):
                target_days.add(day_num)
        _, num_days = calendar.monthrange(year, month)
        for d in range(1, num_days + 1):
            dt = date(year, month, d)
            if dt.weekday() in target_days:
                dates.add(dt)


def _parse_date_ranges(text: str, year: int, dates: set[date]) -> None:
    month_re = "|".join(ALL_MONTHS.keys())
    pattern = rf"({month_re})\s+(\d{{1,2}})\s*[-–—to]+\s*(?:({month_re})\s+)?(\d{{1,2}})"
    for match in re.finditer(pattern, text, re.IGNORECASE):
        start_month = ALL_MONTHS[match.group(1).lower()]
        start_day = int(match.group(2))
        end_month_str = match.group(3)
        end_month = ALL_MONTHS[end_month_str.lower()] if end_month_str else start_month
        end_day = int(match.group(4))
        start = date(year, start_month, start_day)
        end = date(year, end_month, end_day)
        current = start
        while current <= end:
            dates.add(current)
            current += timedelta(days=1)


def _parse_explicit_date_lists(text: str, year: int, dates: set[date]) -> None:
    month_re = "|".join(ALL_MONTHS.keys())
    pattern = rf"({month_re})\s+([\d,\s]+)"
    for match in re.finditer(pattern, text, re.IGNORECASE):
        month = ALL_MONTHS[match.group(1).lower()]
        day_nums = re.findall(r"\d+", match.group(2))
        for d in day_nums:
            day = int(d)
            if 1 <= day <= 31:
                try:
                    dates.add(date(year, month, day))
                except ValueError:
                    pass


def parse_times_from_text(text: str) -> list[tuple[time, time]]:
    text = text.lower().replace("midnight", "12:00 am").replace("noon", "12:00 pm")
    if "dusk" in text:
        text = text.replace("dusk", "6:30 pm")

    time_pattern = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)"
    times_found = re.findall(time_pattern, text, re.IGNORECASE)

    results = []
    for i in range(0, len(times_found) - 1, 2):
        open_t = _to_time(times_found[i])
        close_t = _to_time(times_found[i + 1])
        results.append((open_t, close_t))
    return results


def _to_time(match_groups: tuple[str, str, str]) -> time:
    hour = int(match_groups[0])
    minute = int(match_groups[1]) if match_groups[1] else 0
    ampm = match_groups[2].lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    return time(hour % 24, minute)


def parse_prices_from_text(text: str) -> list[float]:
    pattern = r"\$\s*(\d+(?:\.\d{2})?)"
    return [float(p) for p in re.findall(pattern, text)]


def find_ticket_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        link_text = a_tag.get_text().lower()
        if any(kw in link_text for kw in TICKET_KEYWORDS):
            links.add(href)
            continue
        if any(platform in href.lower() for platform in TICKET_PLATFORMS):
            links.add(href)
    return sorted(links)


def fetch_page(url: str) -> tuple[str, str]:
    response = requests.get(url, timeout=15, headers={"User-Agent": "HauntTripPlanner/1.0"})
    response.raise_for_status()
    html = response.text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return html, text


def scrape_schedule(url: str, year: int) -> ScrapedSchedule:
    html, text = fetch_page(url)
    return ScrapedSchedule(
        dates=parse_dates_from_text(text, year),
        time_ranges=parse_times_from_text(text),
        prices=parse_prices_from_text(text),
        ticket_urls=find_ticket_links(html),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_scraper.py -v`
Expected: All 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: add Tier 1 regex/heuristic schedule scraper"
```

---

### Task 4: Schedule Scraper — Tier 2 (LLM-Assisted)

**Files:**
- Modify: `scraper.py`
- Modify: `tests/test_scraper.py`

- [ ] **Step 1: Write failing tests for Tier 2 LLM parser**

Add to `tests/test_scraper.py`:

```python
from unittest.mock import patch, MagicMock
from scraper import llm_parse_schedule, scrape_schedule_with_llm


def test_llm_parse_schedule_parses_json_response():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"dates": ["2026-10-04", "2026-10-05"], "time_ranges": [["19:00", "23:00"]], "prices": [25.0], "ticket_urls": ["https://example.com/tix"]}')]

    with patch("scraper.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        result = llm_parse_schedule("Some haunt page text", api_key="test-key")

    assert date(2026, 10, 4) in result.dates
    assert date(2026, 10, 5) in result.dates
    assert result.prices == [25.0]
    assert result.confidence in ("green", "yellow")


def test_llm_parse_schedule_returns_red_on_failure():
    with patch("scraper.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        mock_anthropic.Anthropic.return_value = mock_client

        result = llm_parse_schedule("Some text", api_key="test-key")

    assert result.confidence == "red"
    assert result.dates == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_scraper.py::test_llm_parse_schedule_parses_json_response tests/test_scraper.py::test_llm_parse_schedule_returns_red_on_failure -v`
Expected: FAIL — `ImportError: cannot import name 'llm_parse_schedule'`

- [ ] **Step 3: Implement Tier 2 LLM parser**

Add to `scraper.py`:

```python
import json

try:
    import anthropic
except ImportError:
    anthropic = None

LLM_PROMPT = """Extract the schedule information from this haunted attraction page text.
Return a JSON object with these fields:
- "dates": list of dates in YYYY-MM-DD format when the attraction is open
- "time_ranges": list of [open_time, close_time] pairs in HH:MM 24-hour format
- "prices": list of ticket prices as numbers (no $ sign)
- "ticket_urls": list of URLs where tickets can be purchased

Only return the JSON object, no other text."""


def llm_parse_schedule(page_text: str, api_key: str) -> ScrapedSchedule:
    if anthropic is None:
        return ScrapedSchedule(dates=[], time_ranges=[], prices=[], ticket_urls=[])
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": f"{LLM_PROMPT}\n\n---\n\n{page_text[:8000]}"}],
        )
        raw = response.content[0].text
        data = json.loads(raw)
        dates = [date.fromisoformat(d) for d in data.get("dates", [])]
        time_ranges = []
        for tr in data.get("time_ranges", []):
            parts = [time.fromisoformat(t) for t in tr]
            if len(parts) == 2:
                time_ranges.append((parts[0], parts[1]))
        return ScrapedSchedule(
            dates=dates,
            time_ranges=time_ranges,
            prices=[float(p) for p in data.get("prices", [])],
            ticket_urls=data.get("ticket_urls", []),
        )
    except Exception:
        return ScrapedSchedule(dates=[], time_ranges=[], prices=[], ticket_urls=[])


def scrape_schedule_with_llm(
    url: str, year: int, api_key: Optional[str] = None
) -> ScrapedSchedule:
    html, text = fetch_page(url)
    result = ScrapedSchedule(
        dates=parse_dates_from_text(text, year),
        time_ranges=parse_times_from_text(text),
        prices=parse_prices_from_text(text),
        ticket_urls=find_ticket_links(html),
    )
    if result.confidence != "green" and api_key:
        llm_result = llm_parse_schedule(text, api_key)
        if llm_result.confidence != "red":
            if not result.dates and llm_result.dates:
                result.dates = llm_result.dates
            if not result.time_ranges and llm_result.time_ranges:
                result.time_ranges = llm_result.time_ranges
            if not result.prices and llm_result.prices:
                result.prices = llm_result.prices
            if not result.ticket_urls and llm_result.ticket_urls:
                result.ticket_urls = llm_result.ticket_urls
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_scraper.py -v`
Expected: All 14 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: add Tier 2 LLM-assisted schedule parser"
```

---

### Task 5: Optimizer — Constraint Filtering + Proximity Clustering (Phases 1-2)

**Files:**
- Create: `optimizer.py`
- Create: `tests/test_optimizer.py`

- [ ] **Step 1: Write failing tests for Phases 1-2**

```python
# tests/test_optimizer.py
from datetime import date, time
from models import Location, ScheduleEntry, Attraction, Leg, Trip
from optimizer import filter_eligible_dates, build_clusters


def _make_attraction(name, lat, lng, schedule_dates, assigned_dates=None):
    return Attraction(
        name=name,
        address=f"{name} address",
        lat=lat,
        lng=lng,
        schedule_url=f"https://{name.lower().replace(' ', '')}.com",
        assigned_dates=assigned_dates,
        schedule=[
            ScheduleEntry(date=d, open_time=time(19, 0), close_time=time(23, 0))
            for d in schedule_dates
        ],
    )


def _make_trip(attractions, blackout_dates=None, legs=None):
    return Trip(
        date_range=(date(2026, 10, 1), date(2026, 10, 14)),
        start_location=Location("Chicago, IL", 41.8781, -87.6298),
        end_location=Location("Chicago, IL", 41.8781, -87.6298),
        blackout_dates=blackout_dates or [],
        legs=legs or [],
        attractions=attractions,
    )


def test_filter_removes_blackout_dates():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3), date(2026, 10, 5)])
    trip = _make_trip([a], blackout_dates=[date(2026, 10, 5)])
    eligible = filter_eligible_dates(trip)
    assert date(2026, 10, 5) not in eligible["A"]
    assert date(2026, 10, 3) in eligible["A"]


def test_filter_removes_out_of_range_dates():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 9, 30), date(2026, 10, 3)])
    trip = _make_trip([a])
    eligible = filter_eligible_dates(trip)
    assert date(2026, 9, 30) not in eligible["A"]
    assert date(2026, 10, 3) in eligible["A"]


def test_filter_locks_assigned_dates():
    a = _make_attraction(
        "A", 41.88, -87.63,
        [date(2026, 10, 3), date(2026, 10, 4)],
        assigned_dates=[date(2026, 10, 3)],
    )
    trip = _make_trip([a])
    eligible = filter_eligible_dates(trip)
    assert eligible["A"] == [date(2026, 10, 3)]


def test_filter_with_legs():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3), date(2026, 10, 10)])
    leg = Leg(
        date_range=(date(2026, 10, 1), date(2026, 10, 7)),
        start_location=Location("Chicago, IL", 41.8781, -87.6298),
        end_location=Location("Chicago, IL", 41.8781, -87.6298),
    )
    trip = _make_trip([a], legs=[leg])
    eligible = filter_eligible_dates(trip)
    assert date(2026, 10, 3) in eligible["A"]
    assert date(2026, 10, 10) not in eligible["A"]


def test_cluster_nearby_attractions():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3)])
    b = _make_attraction("B", 41.89, -87.64, [date(2026, 10, 3)])  # ~1 mile from A
    c = _make_attraction("C", 39.78, -89.65, [date(2026, 10, 3)])  # ~185 miles from A
    clusters = build_clusters([a, b, c], radius_miles=20.0)
    cluster_with_a = next(c for c in clusters if "A" in [x.name for x in c])
    assert "B" in [x.name for x in cluster_with_a]
    cluster_with_c = next(c for c in clusters if "C" in [x.name for x in c])
    assert len(cluster_with_c) == 1


def test_cluster_transitive():
    # A near B, B near C, but A not near C — all should cluster together
    a = _make_attraction("A", 41.80, -87.63, [date(2026, 10, 3)])
    b = _make_attraction("B", 41.95, -87.63, [date(2026, 10, 3)])  # ~10mi from A
    c = _make_attraction("C", 42.10, -87.63, [date(2026, 10, 3)])  # ~10mi from B, ~20mi from A
    clusters = build_clusters([a, b, c], radius_miles=12.0)
    assert len(clusters) == 1
    assert len(clusters[0]) == 3


def test_cluster_solo():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3)])
    clusters = build_clusters([a], radius_miles=20.0)
    assert len(clusters) == 1
    assert len(clusters[0]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_optimizer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'optimizer'`

- [ ] **Step 3: Implement Phases 1-2**

```python
# optimizer.py
from datetime import date, time, timedelta
from models import Trip, Attraction, Leg, Location, ScheduleEntry
from geocoder import haversine_miles, drive_time_minutes


def filter_eligible_dates(trip: Trip) -> dict[str, list[date]]:
    eligible: dict[str, list[date]] = {}
    trip_start, trip_end = trip.date_range

    for attraction in trip.attractions:
        if attraction.assigned_dates:
            eligible[attraction.name] = sorted(attraction.assigned_dates)
            continue

        valid_dates = set()
        for entry in attraction.schedule:
            if entry.date < trip_start or entry.date > trip_end:
                continue
            if entry.date in trip.blackout_dates:
                continue
            valid_dates.add(entry.date)

        if trip.legs:
            leg = _assign_to_leg(attraction, trip.legs)
            leg_start, leg_end = leg.date_range
            valid_dates = {d for d in valid_dates if leg_start <= d <= leg_end}

        eligible[attraction.name] = sorted(valid_dates)

    return eligible


def _assign_to_leg(attraction: Attraction, legs: list[Leg]) -> Leg:
    best_leg = legs[0]
    best_dist = float("inf")
    best_open_dates = 0

    for leg in legs:
        dist = haversine_miles(
            attraction.lat, attraction.lng,
            leg.start_location.lat, leg.start_location.lng,
        )
        leg_start, leg_end = leg.date_range
        open_in_leg = sum(
            1 for e in attraction.schedule if leg_start <= e.date <= leg_end
        )
        if dist < best_dist or (dist == best_dist and open_in_leg > best_open_dates):
            best_leg = leg
            best_dist = dist
            best_open_dates = open_in_leg

    return best_leg


def build_clusters(
    attractions: list[Attraction], radius_miles: float = 20.0
) -> list[list[Attraction]]:
    n = len(attractions)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            dist = haversine_miles(
                attractions[i].lat, attractions[i].lng,
                attractions[j].lat, attractions[j].lng,
            )
            if dist <= radius_miles:
                union(i, j)

    groups: dict[int, list[Attraction]] = {}
    for i in range(n):
        root = find(i)
        groups.setdefault(root, []).append(attractions[i])

    return list(groups.values())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_optimizer.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add optimizer.py tests/test_optimizer.py
git commit -m "feat: add optimizer Phases 1-2 (constraint filtering + clustering)"
```

---

### Task 6: Optimizer — Date Assignment + Time Slots (Phases 3-4)

**Files:**
- Modify: `optimizer.py`
- Modify: `tests/test_optimizer.py`

- [ ] **Step 1: Write failing tests for Phases 3-4**

Add to `tests/test_optimizer.py`:

```python
from optimizer import assign_dates, assign_time_slots, ItineraryEntry, optimize


def test_assign_dates_scarcity_first():
    # A is open only 1 night, B is open 3 nights — A should get its only night
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3)])
    b = _make_attraction("B", 41.89, -87.64, [date(2026, 10, 3), date(2026, 10, 4), date(2026, 10, 5)])
    trip = _make_trip([a, b])
    eligible = filter_eligible_dates(trip)
    clusters = build_clusters([a, b])
    assignments = assign_dates(clusters, eligible, trip)
    assert assignments["A"] == date(2026, 10, 3)
    assert assignments["B"] != date(2026, 10, 3)  # B pushed to another date


def test_assign_dates_respects_cluster_separation():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3), date(2026, 10, 4)])
    b = _make_attraction("B", 39.78, -89.65, [date(2026, 10, 3), date(2026, 10, 4)])  # far from A
    trip = _make_trip([a, b])
    eligible = filter_eligible_dates(trip)
    clusters = build_clusters([a, b])
    assignments = assign_dates(clusters, eligible, trip)
    assert assignments["A"] != assignments["B"]


def test_assign_time_slots_single():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3)])
    entries = assign_time_slots([a], date(2026, 10, 3))
    assert len(entries) == 1
    assert entries[0].arrival_time == time(19, 0)


def test_assign_time_slots_multiple():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3)])
    b = _make_attraction("B", 41.89, -87.64, [date(2026, 10, 3)])  # ~1 mile
    b.schedule[0].open_time = time(20, 0)
    b.schedule[0].close_time = time(23, 30)
    entries = assign_time_slots([a, b], date(2026, 10, 3))
    assert entries[0].attraction.name == "A"
    assert entries[0].arrival_time == time(19, 0)
    assert entries[1].attraction.name == "B"
    # A arrival 19:00 + 45 min walkthrough + ~1.5 min drive ≈ 19:47
    assert entries[1].arrival_time.hour == 19
    assert entries[1].arrival_time.minute >= 45


def test_assign_time_slots_rejects_late_arrival():
    # B closes at 20:00 — arrival at 19:47 is only 13 min before close, which is < 45 min
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3)])
    b = _make_attraction("B", 41.89, -87.64, [date(2026, 10, 3)])
    b.schedule[0].close_time = time(20, 0)  # too early to fit after A
    entries = assign_time_slots([a, b], date(2026, 10, 3))
    bumped = [e for e in entries if e.bumped]
    assert len(bumped) == 1
    assert bumped[0].attraction.name == "B"


def test_optimize_full_pipeline():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3), date(2026, 10, 4)])
    b = _make_attraction("B", 41.89, -87.64, [date(2026, 10, 3), date(2026, 10, 4)])
    c = _make_attraction("C", 39.78, -89.65, [date(2026, 10, 3), date(2026, 10, 4)])
    trip = _make_trip([a, b, c])
    result = optimize(trip)
    assert len(result.scheduled) > 0
    # A and B should be on the same date (they're close)
    a_date = next(d for d, entries in result.scheduled.items() if any(e.attraction.name == "A" for e in entries))
    b_date = next(d for d, entries in result.scheduled.items() if any(e.attraction.name == "B" for e in entries))
    assert a_date == b_date
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_optimizer.py::test_assign_dates_scarcity_first tests/test_optimizer.py::test_assign_time_slots_single tests/test_optimizer.py::test_optimize_full_pipeline -v`
Expected: FAIL — `ImportError: cannot import name 'assign_dates'`

- [ ] **Step 3: Implement Phases 3-4**

Add to `optimizer.py`:

```python
from dataclasses import dataclass


@dataclass
class ItineraryEntry:
    attraction: Attraction
    date: date
    arrival_time: time
    open_time: time
    close_time: time
    price: float | None = None
    ticket_url: str | None = None
    bumped: bool = False
    bump_reason: str = ""


@dataclass
class ItineraryResult:
    scheduled: dict[date, list[ItineraryEntry]]
    unscheduled: list[tuple[Attraction, str]]


def assign_dates(
    clusters: list[list[Attraction]],
    eligible: dict[str, list[date]],
    trip: Trip,
) -> dict[str, date | None]:
    assignments: dict[str, date | None] = {}
    used_dates_by_cluster: dict[int, set[date]] = {}
    date_to_cluster: dict[date, int] = {}

    scored_clusters = []
    for idx, cluster in enumerate(clusters):
        min_dates = min(len(eligible.get(a.name, [])) for a in cluster)
        centroid_lat = sum(a.lat for a in cluster) / len(cluster)
        centroid_lng = sum(a.lng for a in cluster) / len(cluster)
        dist_to_start = haversine_miles(
            centroid_lat, centroid_lng,
            trip.start_location.lat, trip.start_location.lng,
        )
        dist_to_end = haversine_miles(
            centroid_lat, centroid_lng,
            trip.end_location.lat, trip.end_location.lng,
        )
        travel_score = dist_to_start + dist_to_end
        scored_clusters.append((min_dates, travel_score, idx, cluster))

    scored_clusters.sort(key=lambda x: (x[0], x[1]))

    for _, _, cluster_idx, cluster in scored_clusters:
        used_dates_by_cluster[cluster_idx] = set()

        sorted_attractions = sorted(
            cluster, key=lambda a: len(eligible.get(a.name, []))
        )

        for attraction in sorted_attractions:
            avail = eligible.get(attraction.name, [])
            best_date = None
            best_score = float("inf")

            for d in avail:
                if d in date_to_cluster and date_to_cluster[d] != cluster_idx:
                    continue
                cluster_open_count = sum(
                    1 for a in cluster if d in eligible.get(a.name, [])
                )
                score = -cluster_open_count
                if score < best_score:
                    best_score = score
                    best_date = d

            assignments[attraction.name] = best_date
            if best_date is not None:
                date_to_cluster[best_date] = cluster_idx
                used_dates_by_cluster[cluster_idx].add(best_date)

    return assignments


def assign_time_slots(
    attractions: list[Attraction], target_date: date
) -> list[ItineraryEntry]:
    dated_attractions = []
    for a in attractions:
        entry = next((e for e in a.schedule if e.date == target_date), None)
        if entry:
            dated_attractions.append((a, entry))

    dated_attractions.sort(key=lambda x: x[1].open_time)

    entries: list[ItineraryEntry] = []
    for i, (attraction, sched) in enumerate(dated_attractions):
        if i == 0:
            arrival = sched.open_time
        else:
            prev_entry = entries[-1]
            if prev_entry.bumped:
                arrival = sched.open_time
            else:
                prev_attraction = prev_entry.attraction
                dist = haversine_miles(
                    prev_attraction.lat, prev_attraction.lng,
                    attraction.lat, attraction.lng,
                )
                dt = drive_time_minutes(dist)
                prev_minutes = prev_entry.arrival_time.hour * 60 + prev_entry.arrival_time.minute
                arrival_minutes = prev_minutes + 45 + int(dt)
                arrival = time(min(arrival_minutes // 60, 23), arrival_minutes % 60)

        close_minutes = sched.close_time.hour * 60 + sched.close_time.minute
        if sched.close_time == time(0, 0):
            close_minutes = 24 * 60
        arrival_minutes = arrival.hour * 60 + arrival.minute
        latest_allowed = close_minutes - 45

        bumped = arrival_minutes > latest_allowed
        entries.append(ItineraryEntry(
            attraction=attraction,
            date=target_date,
            arrival_time=arrival,
            open_time=sched.open_time,
            close_time=sched.close_time,
            price=sched.price,
            ticket_url=sched.ticket_url,
            bumped=bumped,
            bump_reason="Arrives too close to closing time" if bumped else "",
        ))

    return entries


def optimize(trip: Trip) -> ItineraryResult:
    eligible = filter_eligible_dates(trip)
    clusters = build_clusters(trip.attractions)
    assignments = assign_dates(clusters, eligible, trip)

    date_groups: dict[date, list[Attraction]] = {}
    unscheduled: list[tuple[Attraction, str]] = []

    for attraction in trip.attractions:
        assigned = assignments.get(attraction.name)
        if assigned is None:
            reason = "no eligible open dates within trip window"
            if eligible.get(attraction.name):
                reason = "couldn't fit — all eligible nights are full"
            unscheduled.append((attraction, reason))
        else:
            date_groups.setdefault(assigned, []).append(attraction)

    scheduled: dict[date, list[ItineraryEntry]] = {}
    bumped_attractions: list[tuple[Attraction, str]] = []

    for d in sorted(date_groups.keys()):
        entries = assign_time_slots(date_groups[d], d)
        good_entries = [e for e in entries if not e.bumped]
        bad_entries = [e for e in entries if e.bumped]
        scheduled[d] = good_entries
        for entry in bad_entries:
            bumped_attractions.append((entry.attraction, entry.bump_reason))

    unscheduled.extend(bumped_attractions)

    return ItineraryResult(scheduled=scheduled, unscheduled=unscheduled)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_optimizer.py -v`
Expected: All 13 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add optimizer.py tests/test_optimizer.py
git commit -m "feat: add optimizer Phases 3-4 (date assignment + time slots)"
```

---

### Task 7: Optimizer — Re-optimization (Phase 5)

**Files:**
- Modify: `optimizer.py`
- Modify: `tests/test_optimizer.py`

- [ ] **Step 1: Write failing tests for Phase 5**

Add to `tests/test_optimizer.py`:

```python
from optimizer import reoptimize


def test_reoptimize_locks_manual_assignment():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3), date(2026, 10, 4)])
    b = _make_attraction("B", 41.89, -87.64, [date(2026, 10, 3), date(2026, 10, 4)])
    trip = _make_trip([a, b])

    # First optimize normally
    original = optimize(trip)

    # Now lock A to Oct 4
    locked = {"A": date(2026, 10, 4)}
    result = reoptimize(trip, locked)

    a_date = None
    for d, entries in result.scheduled.items():
        for e in entries:
            if e.attraction.name == "A":
                a_date = d
    assert a_date == date(2026, 10, 4)


def test_reoptimize_returns_changed_entries():
    a = _make_attraction("A", 41.88, -87.63, [date(2026, 10, 3), date(2026, 10, 4)])
    b = _make_attraction("B", 41.89, -87.64, [date(2026, 10, 3), date(2026, 10, 4)])
    trip = _make_trip([a, b])

    locked = {"A": date(2026, 10, 4)}
    result = reoptimize(trip, locked)
    assert len(result.scheduled) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_optimizer.py::test_reoptimize_locks_manual_assignment tests/test_optimizer.py::test_reoptimize_returns_changed_entries -v`
Expected: FAIL — `ImportError: cannot import name 'reoptimize'`

- [ ] **Step 3: Implement Phase 5**

Add to `optimizer.py`:

```python
def reoptimize(trip: Trip, locked: dict[str, date]) -> ItineraryResult:
    for attraction in trip.attractions:
        if attraction.name in locked:
            attraction.assigned_dates = [locked[attraction.name]]
        else:
            attraction.assigned_dates = None
    return optimize(trip)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_optimizer.py -v`
Expected: All 15 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add optimizer.py tests/test_optimizer.py
git commit -m "feat: add optimizer Phase 5 (re-optimization with locked assignments)"
```

---

### Task 8: Discovery Engine

**Files:**
- Create: `discovery.py`
- Create: `tests/test_discovery.py`

- [ ] **Step 1: Write failing tests for discovery**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_discovery.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'discovery'`

- [ ] **Step 3: Implement discovery engine**

```python
# discovery.py
from dataclasses import dataclass
from datetime import date, time, timedelta
from difflib import SequenceMatcher

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
    suggested_date: date | None
    distance_miles: float
    suggestion_type: str  # "gap_filler" or "densifier"
    website_url: str


def deduplicate_attractions(attractions: list[Attraction]) -> list[Attraction]:
    unique: list[Attraction] = []
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


def find_gap_nights(trip: Trip, scheduled_dates: set[date]) -> list[date]:
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
    candidates: list[Attraction],
    radius_miles: float = 20.0,
) -> list[DiscoverySuggestion]:
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


def scrape_directory(directory_name: str, state: str) -> list[dict]:
    """Scrape a haunt directory for listings in a state. Returns raw listing dicts.
    Each directory has different HTML structure — this dispatches to the right parser."""
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


def discover_haunts(
    trip: Trip,
    itinerary: ItineraryResult,
    existing_names: set[str],
    state: str,
) -> list[DiscoverySuggestion]:
    """Run full discovery: scrape directories, deduplicate, find gaps + densifiers."""
    all_listings: list[dict] = []
    for directory_name in DIRECTORY_URLS:
        all_listings.extend(scrape_directory(directory_name, state))

    # Filter out attractions the user already has
    new_listings = [l for l in all_listings if l["name"] not in existing_names]

    # For a full implementation, each listing would be geocoded and schedule-scraped.
    # Return empty for now — the Flask routes will orchestrate the full pipeline.
    return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_discovery.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add discovery.py tests/test_discovery.py
git commit -m "feat: add discovery engine with multi-directory scraping and dedup"
```

---

### Task 9: HTML Exporter

**Files:**
- Create: `exporter.py`
- Create: `tests/test_exporter.py`

- [ ] **Step 1: Write failing tests for exporter**

```python
# tests/test_exporter.py
from datetime import date, time
from models import Attraction, ScheduleEntry
from optimizer import ItineraryResult, ItineraryEntry
from exporter import generate_export_html


def _make_entry(name, d, arrival, open_t, close_t, price=None, ticket_url=None):
    a = Attraction(
        name=name, address=f"{name} addr", lat=0, lng=0,
        schedule_url=f"https://{name.lower()}.com",
        schedule=[ScheduleEntry(date=d, open_time=open_t, close_time=close_t, price=price, ticket_url=ticket_url)],
    )
    return ItineraryEntry(
        attraction=a, date=d, arrival_time=arrival,
        open_time=open_t, close_time=close_t,
        price=price, ticket_url=ticket_url,
    )


def test_export_contains_attraction_name():
    entry = _make_entry("Haunted Hollow", date(2026, 10, 3), time(19, 0), time(19, 0), time(23, 0))
    result = ItineraryResult(scheduled={date(2026, 10, 3): [entry]}, unscheduled=[])
    html = generate_export_html(result, "Midwest Haunt Trip 2026")
    assert "Haunted Hollow" in html


def test_export_contains_date():
    entry = _make_entry("Haunted Hollow", date(2026, 10, 3), time(19, 0), time(19, 0), time(23, 0))
    result = ItineraryResult(scheduled={date(2026, 10, 3): [entry]}, unscheduled=[])
    html = generate_export_html(result, "Trip")
    assert "October" in html or "Oct" in html


def test_export_contains_price_and_link():
    entry = _make_entry(
        "Screamville", date(2026, 10, 3), time(19, 0), time(19, 0), time(23, 0),
        price=25.0, ticket_url="https://screamville.com/tickets",
    )
    result = ItineraryResult(scheduled={date(2026, 10, 3): [entry]}, unscheduled=[])
    html = generate_export_html(result, "Trip")
    assert "$25.00" in html
    assert "https://screamville.com/tickets" in html


def test_export_contains_nightly_subtotal():
    e1 = _make_entry("A", date(2026, 10, 3), time(19, 0), time(19, 0), time(23, 0), price=25.0)
    e2 = _make_entry("B", date(2026, 10, 3), time(20, 0), time(20, 0), time(23, 0), price=30.0)
    result = ItineraryResult(scheduled={date(2026, 10, 3): [e1, e2]}, unscheduled=[])
    html = generate_export_html(result, "Trip")
    assert "$55.00" in html


def test_export_contains_trip_total():
    e1 = _make_entry("A", date(2026, 10, 3), time(19, 0), time(19, 0), time(23, 0), price=25.0)
    e2 = _make_entry("B", date(2026, 10, 4), time(19, 0), time(19, 0), time(23, 0), price=30.0)
    result = ItineraryResult(
        scheduled={date(2026, 10, 3): [e1], date(2026, 10, 4): [e2]},
        unscheduled=[],
    )
    html = generate_export_html(result, "Trip")
    assert "$55.00" in html


def test_export_shows_unscheduled():
    a = Attraction(
        name="Ghost Manor", address="addr", lat=0, lng=0,
        schedule_url="https://ghostmanor.com", schedule=[],
    )
    result = ItineraryResult(scheduled={}, unscheduled=[(a, "no eligible open dates")])
    html = generate_export_html(result, "Trip")
    assert "Ghost Manor" in html
    assert "no eligible open dates" in html


def test_export_is_standalone_html():
    result = ItineraryResult(scheduled={}, unscheduled=[])
    html = generate_export_html(result, "Trip")
    assert "<!DOCTYPE html>" in html
    assert "<style>" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_exporter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'exporter'`

- [ ] **Step 3: Implement exporter**

```python
# exporter.py
from datetime import date
from optimizer import ItineraryResult


def _format_time(t) -> str:
    hour = t.hour
    minute = t.minute
    ampm = "AM" if hour < 12 else "PM"
    if hour == 0:
        hour = 12
    elif hour > 12:
        hour -= 12
    return f"{hour}:{minute:02d} {ampm}"


def _format_date(d: date) -> str:
    return d.strftime("%A, %B %-d, %Y")


def generate_export_html(result: ItineraryResult, title: str) -> str:
    lines = [
        "<!DOCTYPE html>",
        "<html><head>",
        f"<title>{title}</title>",
        "<style>",
        "body { font-family: Georgia, serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #1a1a1a; color: #e0e0e0; }",
        "h1 { color: #c0392b; text-align: center; border-bottom: 2px solid #4a0e0e; padding-bottom: 10px; }",
        "h2 { color: #8e44ad; margin-top: 30px; border-bottom: 1px solid #333; padding-bottom: 5px; }",
        ".haunt { margin: 12px 0; padding: 12px; background: #2a2a2a; border-left: 4px solid #8e44ad; border-radius: 4px; }",
        ".haunt-name { font-size: 1.1em; font-weight: bold; color: #e0e0e0; }",
        ".haunt-time { color: #aaa; margin-top: 4px; }",
        ".haunt-price a { color: #c0392b; text-decoration: none; }",
        ".haunt-price a:hover { text-decoration: underline; }",
        ".subtotal { text-align: right; color: #8e44ad; font-weight: bold; margin-top: 8px; padding-top: 8px; border-top: 1px solid #333; }",
        ".trip-total { text-align: right; font-size: 1.3em; color: #c0392b; font-weight: bold; margin-top: 20px; padding-top: 10px; border-top: 2px solid #4a0e0e; }",
        ".unscheduled { margin-top: 30px; padding: 15px; background: #2a1a1a; border: 1px solid #4a0e0e; border-radius: 4px; }",
        ".unscheduled h3 { color: #c0392b; }",
        "@media print { body { background: white; color: #222; } h1 { color: #8e44ad; } .haunt { background: #f9f9f9; border-left-color: #8e44ad; } }",
        "</style></head><body>",
        f"<h1>{title}</h1>",
    ]

    trip_total = 0.0

    for d in sorted(result.scheduled.keys()):
        entries = result.scheduled[d]
        lines.append(f"<h2>{_format_date(d)}</h2>")
        nightly_total = 0.0

        for entry in entries:
            lines.append('<div class="haunt">')
            lines.append(f'<div class="haunt-name">{entry.attraction.name}</div>')
            lines.append(f'<div class="haunt-time">Arrive: {_format_time(entry.arrival_time)} | Open: {_format_time(entry.open_time)} – {_format_time(entry.close_time)}</div>')
            if entry.price is not None:
                nightly_total += entry.price
                if entry.ticket_url:
                    lines.append(f'<div class="haunt-price">${entry.price:.2f} — <a href="{entry.ticket_url}">Buy Tickets</a></div>')
                else:
                    lines.append(f'<div class="haunt-price">${entry.price:.2f}</div>')
            lines.append("</div>")

        if nightly_total > 0:
            lines.append(f'<div class="subtotal">Nightly Total: ${nightly_total:.2f}</div>')
        trip_total += nightly_total

    if trip_total > 0:
        lines.append(f'<div class="trip-total">Trip Total: ${trip_total:.2f}</div>')

    if result.unscheduled:
        lines.append('<div class="unscheduled">')
        lines.append("<h3>Could Not Schedule</h3>")
        for attraction, reason in result.unscheduled:
            lines.append(f"<p><strong>{attraction.name}</strong> — {reason}</p>")
        lines.append("</div>")

    lines.append("</body></html>")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_exporter.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add exporter.py tests/test_exporter.py
git commit -m "feat: add standalone HTML itinerary exporter"
```

---

### Task 10: Flask App + API Routes

**Files:**
- Create: `hauntplanner.py`
- Create: `tests/test_app.py`

- [ ] **Step 1: Write failing tests for Flask routes**

```python
# tests/test_app.py
import json
import pytest
from hauntplanner import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


def test_setup_page_returns_200(client):
    response = client.get("/setup")
    assert response.status_code == 200


def test_attractions_page_returns_200(client):
    response = client.get("/attractions")
    assert response.status_code == 200


def test_api_save_trip(client):
    trip_data = {
        "date_range": {"start": "2026-10-01", "end": "2026-10-14"},
        "start_location": "Chicago, IL",
        "end_location": "Chicago, IL",
        "blackout_dates": ["2026-10-05"],
        "legs": [],
    }
    response = client.post(
        "/api/trip",
        data=json.dumps(trip_data),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"


def test_api_add_attraction(client):
    # First save a trip
    trip_data = {
        "date_range": {"start": "2026-10-01", "end": "2026-10-14"},
        "start_location": "Chicago, IL",
        "end_location": "Chicago, IL",
        "blackout_dates": [],
        "legs": [],
    }
    client.post("/api/trip", data=json.dumps(trip_data), content_type="application/json")

    attraction_data = {
        "name": "Haunted Hollow",
        "address": "123 Main St, Springfield, IL",
        "schedule_url": "https://hauntedhollowil.com",
        "assigned_dates": [],
    }
    response = client.post(
        "/api/attractions",
        data=json.dumps(attraction_data),
        content_type="application/json",
    )
    assert response.status_code == 200


def test_api_optimize_returns_itinerary(client):
    response = client.post("/api/optimize")
    assert response.status_code == 200
    data = response.get_json()
    assert "scheduled" in data
    assert "unscheduled" in data


def test_api_export_returns_html(client):
    response = client.get("/api/export?title=My+Trip")
    assert response.status_code == 200
    assert b"<!DOCTYPE html>" in response.data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hauntplanner'`

- [ ] **Step 3: Implement Flask app**

```python
# hauntplanner.py
import json
from datetime import date, time
from flask import Flask, render_template, request, jsonify, Response

from models import Trip, Location, Leg, Attraction, ScheduleEntry
from geocoder import geocode_address
from scraper import scrape_schedule, scrape_schedule_with_llm
from optimizer import optimize, reoptimize, ItineraryResult
from exporter import generate_export_html

_trip: Trip | None = None
_itinerary: ItineraryResult | None = None
_api_key: str | None = None


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template("setup.html")

    @app.route("/setup")
    def setup():
        return render_template("setup.html")

    @app.route("/attractions")
    def attractions():
        return render_template("attractions.html")

    @app.route("/review")
    def review():
        return render_template("review.html")

    @app.route("/itinerary")
    def itinerary():
        return render_template("itinerary.html")

    @app.route("/export-view")
    def export_view():
        return render_template("export.html")

    @app.route("/api/settings", methods=["POST"])
    def save_settings():
        global _api_key
        data = request.get_json()
        _api_key = data.get("claude_api_key")
        return jsonify({"status": "ok"})

    @app.route("/api/trip", methods=["POST"])
    def save_trip():
        global _trip
        data = request.get_json()
        dr = data["date_range"]
        start_addr = data["start_location"]
        end_addr = data["end_location"]

        try:
            start_lat, start_lng = geocode_address(start_addr)
            end_lat, end_lng = geocode_address(end_addr)
        except ValueError:
            start_lat, start_lng = 0.0, 0.0
            end_lat, end_lng = 0.0, 0.0

        legs = []
        for leg_data in data.get("legs", []):
            try:
                ls_lat, ls_lng = geocode_address(leg_data["start_location"])
                le_lat, le_lng = geocode_address(leg_data["end_location"])
            except ValueError:
                ls_lat, ls_lng = 0.0, 0.0
                le_lat, le_lng = 0.0, 0.0
            legs.append(Leg(
                date_range=(
                    date.fromisoformat(leg_data["date_range"]["start"]),
                    date.fromisoformat(leg_data["date_range"]["end"]),
                ),
                start_location=Location(leg_data["start_location"], ls_lat, ls_lng),
                end_location=Location(leg_data["end_location"], le_lat, le_lng),
            ))

        _trip = Trip(
            date_range=(date.fromisoformat(dr["start"]), date.fromisoformat(dr["end"])),
            start_location=Location(start_addr, start_lat, start_lng),
            end_location=Location(end_addr, end_lat, end_lng),
            blackout_dates=[date.fromisoformat(d) for d in data.get("blackout_dates", [])],
            legs=legs,
            attractions=[],
        )
        return jsonify({"status": "ok"})

    @app.route("/api/attractions", methods=["POST"])
    def add_attraction():
        global _trip
        if _trip is None:
            return jsonify({"error": "No trip configured"}), 400

        data = request.get_json()
        try:
            lat, lng = geocode_address(data["address"])
        except ValueError:
            lat, lng = 0.0, 0.0

        attraction = Attraction(
            name=data["name"],
            address=data["address"],
            lat=lat,
            lng=lng,
            schedule_url=data["schedule_url"],
            assigned_dates=[date.fromisoformat(d) for d in data.get("assigned_dates", [])] or None,
        )
        _trip.attractions.append(attraction)
        return jsonify({"status": "ok", "index": len(_trip.attractions) - 1})

    @app.route("/api/scrape", methods=["POST"])
    def scrape_all():
        if _trip is None:
            return jsonify({"error": "No trip configured"}), 400

        year = _trip.date_range[0].year
        results = []
        for attraction in _trip.attractions:
            try:
                if _api_key:
                    scraped = scrape_schedule_with_llm(attraction.schedule_url, year, _api_key)
                else:
                    scraped = scrape_schedule(attraction.schedule_url, year)
                attraction.schedule = [
                    ScheduleEntry(
                        date=d,
                        open_time=scraped.time_ranges[0][0] if scraped.time_ranges else time(19, 0),
                        close_time=scraped.time_ranges[0][1] if scraped.time_ranges else time(23, 0),
                        price=scraped.prices[0] if scraped.prices else None,
                        ticket_url=scraped.ticket_urls[0] if scraped.ticket_urls else None,
                    )
                    for d in scraped.dates
                ]
                results.append({
                    "name": attraction.name,
                    "dates": [str(d) for d in scraped.dates],
                    "time_ranges": [
                        [tr[0].isoformat(), tr[1].isoformat()]
                        for tr in scraped.time_ranges
                    ],
                    "prices": scraped.prices,
                    "ticket_urls": scraped.ticket_urls,
                    "confidence": scraped.confidence,
                })
            except Exception as e:
                results.append({
                    "name": attraction.name,
                    "error": str(e),
                    "confidence": "red",
                })

        return jsonify({"results": results})

    @app.route("/api/schedule", methods=["PUT"])
    def update_schedule():
        if _trip is None:
            return jsonify({"error": "No trip configured"}), 400

        data = request.get_json()
        name = data["name"]
        attraction = next((a for a in _trip.attractions if a.name == name), None)
        if attraction is None:
            return jsonify({"error": f"Attraction '{name}' not found"}), 404

        attraction.schedule = [
            ScheduleEntry(
                date=date.fromisoformat(e["date"]),
                open_time=time.fromisoformat(e["open_time"]),
                close_time=time.fromisoformat(e["close_time"]),
                price=e.get("price"),
                ticket_url=e.get("ticket_url"),
            )
            for e in data["schedule"]
        ]
        return jsonify({"status": "ok"})

    @app.route("/api/optimize", methods=["POST"])
    def run_optimize():
        global _itinerary
        if _trip is None:
            return jsonify({"scheduled": {}, "unscheduled": []})

        _itinerary = optimize(_trip)
        return jsonify(_serialize_itinerary(_itinerary))

    @app.route("/api/eligible-dates")
    def eligible_dates():
        if _trip is None:
            return jsonify([])
        name = request.args.get("name")
        attraction = next((a for a in _trip.attractions if a.name == name), None)
        if attraction is None:
            return jsonify([])
        from optimizer import filter_eligible_dates
        eligible = filter_eligible_dates(_trip)
        return jsonify([str(d) for d in eligible.get(name, [])])

    @app.route("/api/adjust", methods=["POST"])
    def adjust():
        global _itinerary
        if _trip is None:
            return jsonify({"error": "No trip configured"}), 400

        data = request.get_json()
        locked = {data["name"]: date.fromisoformat(data["date"])}
        _itinerary = reoptimize(_trip, locked)
        return jsonify(_serialize_itinerary(_itinerary))

    @app.route("/api/discover", methods=["POST"])
    def discover():
        if _trip is None or _itinerary is None:
            return jsonify({"suggestions": []})
        from discovery import find_gap_nights, find_densify_opportunities
        scheduled_dates = set(_itinerary.scheduled.keys())
        gaps = find_gap_nights(_trip, scheduled_dates)
        # Discovery suggestions are returned for display — full directory
        # scraping and schedule fetching happens here in a production version.
        # For now, return gap dates so the UI can show open nights.
        return jsonify({
            "gap_dates": [str(d) for d in gaps],
            "suggestions": [],
        })

    @app.route("/api/export")
    def export():
        if _itinerary is None:
            html = generate_export_html(
                ItineraryResult(scheduled={}, unscheduled=[]),
                request.args.get("title", "Haunt Trip"),
            )
        else:
            html = generate_export_html(
                _itinerary,
                request.args.get("title", "Haunt Trip"),
            )
        return Response(html, mimetype="text/html")

    return app


def _serialize_itinerary(result: ItineraryResult) -> dict:
    scheduled = {}
    for d, entries in result.scheduled.items():
        scheduled[str(d)] = [
            {
                "name": e.attraction.name,
                "arrival_time": e.arrival_time.isoformat(),
                "open_time": e.open_time.isoformat(),
                "close_time": e.close_time.isoformat(),
                "price": e.price,
                "ticket_url": e.ticket_url,
            }
            for e in entries
        ]
    unscheduled = [
        {"name": a.name, "reason": reason}
        for a, reason in result.unscheduled
    ]
    return {"scheduled": scheduled, "unscheduled": unscheduled}


if __name__ == "__main__":
    app = create_app()
    print("Haunt Trip Planner running at http://localhost:5000")
    app.run(debug=True, port=5000)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/test_app.py -v`
Expected: All 7 tests PASS. (Some tests may need template files to exist — create minimal stubs first if needed.)

- [ ] **Step 5: Commit**

```bash
git add hauntplanner.py tests/test_app.py
git commit -m "feat: add Flask app with API routes for trip planning workflow"
```

---

### Task 11: Base Template + Spooky Theme

**Files:**
- Create: `templates/base.html`
- Create: `static/style.css`

- [ ] **Step 1: Create the spooky CSS theme**

```css
/* static/style.css */

/* === RESET + BASE === */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: #0d0d0d;
    color: #e0e0e0;
    min-height: 100vh;
    overflow-x: hidden;
}

/* === FOG ANIMATION === */
.fog {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    pointer-events: none;
    z-index: 0;
    overflow: hidden;
}
.fog::before, .fog::after {
    content: '';
    position: absolute;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at center, rgba(100,50,120,0.03) 0%, transparent 60%);
    animation: fogDrift 30s linear infinite;
}
.fog::after {
    animation-delay: -15s;
    background: radial-gradient(ellipse at center, rgba(50,80,50,0.03) 0%, transparent 60%);
}
@keyframes fogDrift {
    0% { transform: translate(-25%, -25%) rotate(0deg); }
    100% { transform: translate(-25%, -25%) rotate(360deg); }
}

/* === COBWEB CORNERS === */
.cobweb-tl, .cobweb-br {
    position: fixed;
    width: 120px;
    height: 120px;
    pointer-events: none;
    z-index: 1;
    opacity: 0.15;
}
.cobweb-tl {
    top: 0; left: 0;
    background: radial-gradient(ellipse at top left, rgba(200,200,200,0.3) 0%, transparent 70%);
    border-top: 1px solid rgba(200,200,200,0.1);
    border-left: 1px solid rgba(200,200,200,0.1);
}
.cobweb-br {
    bottom: 0; right: 0;
    background: radial-gradient(ellipse at bottom right, rgba(200,200,200,0.3) 0%, transparent 70%);
    border-bottom: 1px solid rgba(200,200,200,0.1);
    border-right: 1px solid rgba(200,200,200,0.1);
}

/* === LAYOUT === */
.container {
    position: relative;
    z-index: 2;
    max-width: 900px;
    margin: 0 auto;
    padding: 40px 20px;
}

/* === DRIP TEXT HEADER === */
h1 {
    font-size: 2.5em;
    font-weight: 900;
    text-align: center;
    color: #c0392b;
    text-shadow: 0 0 20px rgba(192,57,43,0.3);
    position: relative;
    margin-bottom: 40px;
}
h1::after {
    content: '';
    display: block;
    margin: 12px auto 0;
    width: 80%;
    height: 4px;
    background: linear-gradient(90deg, transparent, #4a0e0e, #8e44ad, #4a0e0e, transparent);
    border-radius: 2px;
}

h2 {
    font-size: 1.4em;
    color: #8e44ad;
    margin: 30px 0 15px;
    text-shadow: 0 0 10px rgba(142,68,173,0.2);
}

h3 { font-size: 1.1em; color: #bbb; margin-bottom: 10px; }

/* === CARDS === */
.card {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
    transition: border-color 0.2s;
}
.card:hover { border-color: #8e44ad; }

/* === FORMS === */
label {
    display: block;
    margin-bottom: 6px;
    color: #aaa;
    font-size: 0.9em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
input[type="text"], input[type="date"], input[type="url"], input[type="number"], select, textarea {
    width: 100%;
    padding: 10px 14px;
    background: #111;
    border: 1px solid #333;
    border-radius: 6px;
    color: #e0e0e0;
    font-size: 1em;
    margin-bottom: 16px;
    transition: border-color 0.2s;
}
input:focus, select:focus, textarea:focus {
    outline: none;
    border-color: #8e44ad;
    box-shadow: 0 0 8px rgba(142,68,173,0.2);
}

/* === BUTTONS === */
.btn {
    display: inline-block;
    padding: 12px 28px;
    font-size: 1em;
    font-weight: 700;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.btn-primary {
    background: linear-gradient(135deg, #8e44ad, #6c3483);
    color: white;
}
.btn-primary:hover {
    background: linear-gradient(135deg, #9b59b6, #7d3c98);
    box-shadow: 0 0 15px rgba(142,68,173,0.4);
}
.btn-danger {
    background: linear-gradient(135deg, #c0392b, #96281b);
    color: white;
}
.btn-danger:hover {
    box-shadow: 0 0 15px rgba(192,57,43,0.4);
}
.btn-secondary {
    background: #2a2a2a;
    color: #aaa;
    border: 1px solid #444;
}
.btn-secondary:hover { border-color: #8e44ad; color: #e0e0e0; }

/* === CONFIDENCE BADGES === */
.badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 0.8em; font-weight: 600; }
.badge-green { background: #1a4a1a; color: #4ecb71; }
.badge-yellow { background: #4a3a0e; color: #f5a623; }
.badge-red { background: #4a0e0e; color: #e85d75; }

/* === ITINERARY === */
.date-section { margin-bottom: 30px; }
.date-header {
    font-size: 1.2em;
    color: #c0392b;
    padding-bottom: 8px;
    border-bottom: 1px solid #2a2a2a;
    margin-bottom: 12px;
}
.haunt-entry {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: #1a1a1a;
    border-left: 4px solid #8e44ad;
    border-radius: 4px;
    margin-bottom: 8px;
}
.haunt-name { font-weight: 700; font-size: 1.05em; }
.haunt-time { color: #aaa; font-size: 0.9em; margin-top: 4px; }
.haunt-price a { color: #c0392b; text-decoration: none; }
.haunt-price a:hover { text-decoration: underline; }
.subtotal { text-align: right; color: #8e44ad; font-weight: 700; margin-top: 4px; }
.trip-total { text-align: right; font-size: 1.3em; color: #c0392b; font-weight: 700; margin-top: 20px; padding-top: 10px; border-top: 2px solid #4a0e0e; }

/* === SUGGESTIONS === */
.suggestion {
    padding: 12px 16px;
    background: #1a1a0d;
    border-left: 4px solid #4a7a2e;
    border-radius: 4px;
    margin-bottom: 8px;
}
.suggestion .btn { padding: 6px 14px; font-size: 0.85em; }

/* === LOADING === */
.loading { text-align: center; padding: 60px 0; }
.spinner {
    width: 50px; height: 50px;
    border: 4px solid #2a2a2a;
    border-top-color: #8e44ad;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 20px;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* === NAV === */
.nav {
    display: flex;
    justify-content: center;
    gap: 8px;
    margin-bottom: 30px;
    flex-wrap: wrap;
}
.nav a {
    padding: 8px 16px;
    color: #888;
    text-decoration: none;
    border-radius: 4px;
    font-size: 0.9em;
    transition: all 0.2s;
}
.nav a:hover { color: #e0e0e0; background: #1a1a1a; }
.nav a.active { color: #8e44ad; background: #1a1a1a; font-weight: 700; }

/* === PRINT === */
@media print {
    body { background: white; color: #222; }
    .fog, .cobweb-tl, .cobweb-br, .nav, .btn, .no-print { display: none; }
    .card { border: 1px solid #ddd; }
    .haunt-entry { border-left-color: #8e44ad; background: #f9f9f9; }
    h1 { color: #8e44ad; text-shadow: none; }
}
```

- [ ] **Step 2: Create the base template**

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Haunt Trip Planner{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <div class="fog"></div>
    <div class="cobweb-tl"></div>
    <div class="cobweb-br"></div>

    <div class="container">
        <h1>Haunt Trip Planner</h1>

        <nav class="nav no-print">
            <a href="/setup" class="{% if request.path == '/setup' or request.path == '/' %}active{% endif %}">Trip Setup</a>
            <a href="/attractions" class="{% if request.path == '/attractions' %}active{% endif %}">Attractions</a>
            <a href="/review" class="{% if request.path == '/review' %}active{% endif %}">Review</a>
            <a href="/itinerary" class="{% if request.path == '/itinerary' %}active{% endif %}">Itinerary</a>
            <a href="/export-view" class="{% if request.path == '/export-view' %}active{% endif %}">Export</a>
        </nav>

        {% block content %}{% endblock %}
    </div>

    <script src="{{ url_for('static', filename='app.js') }}"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 3: Run the app to verify the template renders**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -c "from hauntplanner import create_app; app = create_app(); app.test_client().get('/')"`
Expected: No errors. (May need to create stub templates for other pages first.)

- [ ] **Step 4: Commit**

```bash
git add templates/base.html static/style.css
git commit -m "feat: add base template with spooky dark theme, fog, and cobwebs"
```

---

### Task 12: Frontend — Trip Setup + Attractions Screens

**Files:**
- Create: `templates/setup.html`
- Create: `templates/attractions.html`
- Create: `static/app.js`

- [ ] **Step 1: Create trip setup template**

```html
<!-- templates/setup.html -->
{% extends "base.html" %}
{% block title %}Trip Setup — Haunt Trip Planner{% endblock %}
{% block content %}
<h2>Trip Setup</h2>

<div class="card">
    <h3>Trip Dates</h3>
    <label for="start-date">Start Date</label>
    <input type="date" id="start-date" required>
    <label for="end-date">End Date</label>
    <input type="date" id="end-date" required>
</div>

<div class="card">
    <h3>Locations</h3>
    <label for="start-location">Start Location</label>
    <input type="text" id="start-location" placeholder="e.g. Chicago, IL" required>
    <label for="end-location">End Location</label>
    <input type="text" id="end-location" placeholder="e.g. Chicago, IL" required>
</div>

<div class="card">
    <h3>Trip Legs <span style="color:#666; font-weight:normal; font-size:0.85em;">(optional)</span></h3>
    <div id="legs-container"></div>
    <button class="btn btn-secondary" onclick="addLeg()">+ Add Leg</button>
</div>

<div class="card">
    <h3>Blackout Dates</h3>
    <p style="color:#888; font-size:0.9em; margin-bottom:12px;">Click dates when you can't visit any attractions.</p>
    <div id="blackout-dates" style="display:flex; flex-wrap:wrap; gap:8px;"></div>
    <input type="date" id="blackout-picker" style="margin-top:12px; width:auto;">
    <button class="btn btn-secondary" onclick="addBlackout()" style="margin-left:8px;">+ Add Date</button>
</div>

<div class="card" style="border-color: #333;">
    <h3>Claude API Key <span style="color:#666; font-weight:normal; font-size:0.85em;">(optional — improves schedule scraping)</span></h3>
    <input type="text" id="api-key" placeholder="sk-ant-...">
</div>

<div style="text-align:center; margin-top:24px;">
    <button class="btn btn-primary" onclick="saveTrip()">Save Trip & Continue →</button>
</div>
{% endblock %}
```

- [ ] **Step 2: Create attractions template**

```html
<!-- templates/attractions.html -->
{% extends "base.html" %}
{% block title %}Add Attractions — Haunt Trip Planner{% endblock %}
{% block content %}
<h2>Add Attractions</h2>

<div id="attractions-list"></div>

<div class="card" id="add-form">
    <h3>New Attraction</h3>
    <label for="attr-name">Name</label>
    <input type="text" id="attr-name" placeholder="e.g. Haunted Hollow">
    <label for="attr-address">Address</label>
    <input type="text" id="attr-address" placeholder="e.g. 123 Main St, Springfield, IL">
    <label for="attr-url">Schedule Page URL</label>
    <input type="url" id="attr-url" placeholder="https://...">
    <label for="attr-dates">Assigned Dates <span style="color:#666; font-weight:normal;">(optional, comma-separated)</span></label>
    <input type="text" id="attr-dates" placeholder="e.g. 2026-10-04, 2026-10-05">
    <div style="margin-top:12px;">
        <button class="btn btn-secondary" onclick="addAttraction()">+ Add Attraction</button>
    </div>
</div>

<div style="text-align:center; margin-top:24px;">
    <button class="btn btn-primary" onclick="submitAttractions()">Scrape Schedules & Continue →</button>
</div>
{% endblock %}
```

- [ ] **Step 3: Create app.js with form handling**

```javascript
// static/app.js

let tripLegs = [];
let blackoutDates = [];
let attractions = [];

// === TRIP SETUP ===

function addLeg() {
    const container = document.getElementById('legs-container');
    const idx = tripLegs.length;
    tripLegs.push({});

    const legDiv = document.createElement('div');
    legDiv.className = 'card';
    legDiv.style.background = '#111';
    legDiv.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3>Leg ${idx + 1}</h3>
            <button class="btn btn-danger" style="padding:4px 10px; font-size:0.8em;" onclick="removeLeg(${idx}, this)">Remove</button>
        </div>
        <label>Start Date</label>
        <input type="date" class="leg-start-date" data-idx="${idx}">
        <label>End Date</label>
        <input type="date" class="leg-end-date" data-idx="${idx}">
        <label>Start Location</label>
        <input type="text" class="leg-start-loc" data-idx="${idx}" placeholder="Address">
        <label>End Location</label>
        <input type="text" class="leg-end-loc" data-idx="${idx}" placeholder="Address">
    `;
    container.appendChild(legDiv);
}

function removeLeg(idx, btn) {
    tripLegs.splice(idx, 1);
    btn.closest('.card').remove();
}

function addBlackout() {
    const picker = document.getElementById('blackout-picker');
    const d = picker.value;
    if (!d || blackoutDates.includes(d)) return;
    blackoutDates.push(d);
    renderBlackouts();
    picker.value = '';
}

function renderBlackouts() {
    const container = document.getElementById('blackout-dates');
    container.innerHTML = blackoutDates.map((d, i) =>
        `<span class="badge badge-red" style="cursor:pointer;" onclick="removeBlackout(${i})">${d} ×</span>`
    ).join('');
}

function removeBlackout(idx) {
    blackoutDates.splice(idx, 1);
    renderBlackouts();
}

async function saveTrip() {
    const legs = [];
    document.querySelectorAll('.leg-start-date').forEach(el => {
        const idx = parseInt(el.dataset.idx);
        const parent = el.closest('.card');
        legs.push({
            date_range: {
                start: parent.querySelector('.leg-start-date').value,
                end: parent.querySelector('.leg-end-date').value,
            },
            start_location: parent.querySelector('.leg-start-loc').value,
            end_location: parent.querySelector('.leg-end-loc').value,
        });
    });

    const apiKey = document.getElementById('api-key').value;
    if (apiKey) {
        await fetch('/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({claude_api_key: apiKey}),
        });
    }

    const resp = await fetch('/api/trip', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            date_range: {
                start: document.getElementById('start-date').value,
                end: document.getElementById('end-date').value,
            },
            start_location: document.getElementById('start-location').value,
            end_location: document.getElementById('end-location').value,
            blackout_dates: blackoutDates,
            legs: legs,
        }),
    });

    if (resp.ok) {
        window.location.href = '/attractions';
    }
}

// === ATTRACTIONS ===

async function addAttraction() {
    const name = document.getElementById('attr-name').value;
    const address = document.getElementById('attr-address').value;
    const url = document.getElementById('attr-url').value;
    const datesRaw = document.getElementById('attr-dates').value;
    const assignedDates = datesRaw ? datesRaw.split(',').map(d => d.trim()) : [];

    if (!name || !address || !url) return;

    const resp = await fetch('/api/attractions', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, address, schedule_url: url, assigned_dates: assignedDates}),
    });

    if (resp.ok) {
        attractions.push({name, address, url});
        renderAttractions();
        document.getElementById('attr-name').value = '';
        document.getElementById('attr-address').value = '';
        document.getElementById('attr-url').value = '';
        document.getElementById('attr-dates').value = '';
    }
}

function renderAttractions() {
    const container = document.getElementById('attractions-list');
    container.innerHTML = attractions.map((a, i) =>
        `<div class="card" style="border-left: 4px solid #8e44ad;">
            <strong>${a.name}</strong>
            <div style="color:#888; font-size:0.9em; margin-top:4px;">${a.address}</div>
        </div>`
    ).join('');
}

async function submitAttractions() {
    window.location.href = '/review';
}
```

- [ ] **Step 4: Start the app and verify setup page renders in browser**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python hauntplanner.py`
Open: http://localhost:5000
Expected: Dark-themed setup page with date pickers, location fields, legs, blackout dates, and API key field. Fog animation in background, cobweb corners visible.

- [ ] **Step 5: Commit**

```bash
git add templates/setup.html templates/attractions.html static/app.js
git commit -m "feat: add trip setup and attractions input screens"
```

---

### Task 13: Frontend — Loading, Schedule Review, Itinerary, and Export Screens

**Files:**
- Create: `templates/loading.html`
- Create: `templates/review.html`
- Create: `templates/itinerary.html`
- Create: `templates/export.html`
- Modify: `static/app.js`

- [ ] **Step 1: Create loading template**

```html
<!-- templates/loading.html -->
{% extends "base.html" %}
{% block title %}Scraping Schedules...{% endblock %}
{% block content %}
<div class="loading">
    <div class="spinner"></div>
    <h2>Scraping Schedules...</h2>
    <p style="color:#888;">Fetching dates, hours, and prices from attraction websites.</p>
    <p style="color:#666; font-size:0.9em; margin-top:8px;">This may take a moment due to rate limiting.</p>
    <div id="scrape-progress" style="margin-top:20px;"></div>
</div>
{% endblock %}
{% block scripts %}
<script>
(async function() {
    const resp = await fetch('/api/scrape', {method: 'POST'});
    if (resp.ok) {
        window.location.href = '/review';
    } else {
        document.getElementById('scrape-progress').innerHTML =
            '<p style="color:#e85d75;">Scraping failed. Please check your attraction URLs and try again.</p>';
    }
})();
</script>
{% endblock %}
```

- [ ] **Step 2: Create schedule review template**

```html
<!-- templates/review.html -->
{% extends "base.html" %}
{% block title %}Review Schedules — Haunt Trip Planner{% endblock %}
{% block content %}
<h2>Review Scraped Schedules</h2>
<p style="color:#888; margin-bottom:20px;">Verify the data below. Edit anything that looks wrong.</p>
<div id="review-container">
    <div class="loading">
        <div class="spinner"></div>
        <p>Loading scraped data...</p>
    </div>
</div>
<div style="text-align:center; margin-top:24px;">
    <button class="btn btn-primary" onclick="generateItinerary()">Generate Itinerary →</button>
</div>
{% endblock %}
{% block scripts %}
<script>
async function loadReview() {
    const resp = await fetch('/api/scrape', {method: 'POST'});
    const data = await resp.json();
    const container = document.getElementById('review-container');
    container.innerHTML = '';

    data.results.forEach((result, idx) => {
        const badgeClass = result.confidence === 'green' ? 'badge-green' :
                          result.confidence === 'yellow' ? 'badge-yellow' : 'badge-red';
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <strong style="font-size:1.1em;">${result.name}</strong>
                <span class="badge ${badgeClass}">${result.confidence}</span>
            </div>
            ${result.error ? `<p style="color:#e85d75;">${result.error}</p>` : ''}
            <label>Dates (YYYY-MM-DD, one per line)</label>
            <textarea id="dates-${idx}" rows="4" style="font-family:monospace;">${(result.dates || []).join('\n')}</textarea>
            <label>Opening Time</label>
            <input type="text" id="open-${idx}" value="${result.time_ranges?.[0]?.[0] || '19:00'}">
            <label>Closing Time</label>
            <input type="text" id="close-${idx}" value="${result.time_ranges?.[0]?.[1] || '23:00'}">
            <label>Price ($)</label>
            <input type="number" id="price-${idx}" value="${result.prices?.[0] || ''}" step="0.01">
            <label>Ticket URL</label>
            <input type="url" id="ticket-${idx}" value="${result.ticket_urls?.[0] || ''}">
        `;
        container.appendChild(card);
    });
}

async function generateItinerary() {
    // Save edited schedules back to server
    const cards = document.querySelectorAll('#review-container .card');
    for (let i = 0; i < cards.length; i++) {
        const name = cards[i].querySelector('strong').textContent;
        const datesText = document.getElementById(`dates-${i}`).value;
        const dates = datesText.split('\n').map(d => d.trim()).filter(d => d);
        const openTime = document.getElementById(`open-${i}`).value;
        const closeTime = document.getElementById(`close-${i}`).value;
        const price = parseFloat(document.getElementById(`price-${i}`).value) || null;
        const ticketUrl = document.getElementById(`ticket-${i}`).value || null;

        await fetch('/api/schedule', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name: name,
                schedule: dates.map(d => ({
                    date: d,
                    open_time: openTime,
                    close_time: closeTime,
                    price: price,
                    ticket_url: ticketUrl,
                })),
            }),
        });
    }

    await fetch('/api/optimize', {method: 'POST'});
    window.location.href = '/itinerary';
}

loadReview();
</script>
{% endblock %}
```

- [ ] **Step 3: Create itinerary template**

```html
<!-- templates/itinerary.html -->
{% extends "base.html" %}
{% block title %}Your Itinerary — Haunt Trip Planner{% endblock %}
{% block content %}
<h2>Your Haunt Itinerary</h2>
<div id="itinerary-container">
    <div class="loading"><div class="spinner"></div><p>Loading itinerary...</p></div>
</div>

<div class="card no-print" style="margin-top:30px;">
    <h3>Adjust Schedule</h3>
    <label for="adjust-name">Attraction</label>
    <select id="adjust-name"><option value="">Select...</option></select>
    <label for="adjust-date">Move to Date</label>
    <select id="adjust-date"><option value="">Select attraction first</option></select>
    <button class="btn btn-secondary" onclick="adjustSchedule()" style="margin-top:8px;">Re-optimize</button>
</div>
{% endblock %}
{% block scripts %}
<script>
async function loadItinerary() {
    const resp = await fetch('/api/optimize', {method: 'POST'});
    const data = await resp.json();
    renderItinerary(data);
}

function renderItinerary(data) {
    const container = document.getElementById('itinerary-container');
    let html = '';
    let tripTotal = 0;

    const dates = Object.keys(data.scheduled).sort();
    for (const d of dates) {
        const entries = data.scheduled[d];
        const dateObj = new Date(d + 'T00:00:00');
        const dateStr = dateObj.toLocaleDateString('en-US', {weekday:'long', month:'long', day:'numeric', year:'numeric'});
        html += `<div class="date-section"><div class="date-header">${dateStr}</div>`;
        let nightlyTotal = 0;

        for (const e of entries) {
            const arrival = formatTime(e.arrival_time);
            const open = formatTime(e.open_time);
            const close = formatTime(e.close_time);
            const priceHtml = e.price != null
                ? (e.ticket_url
                    ? `<span class="haunt-price">$${e.price.toFixed(2)} — <a href="${e.ticket_url}" target="_blank">Buy Tickets</a></span>`
                    : `<span class="haunt-price">$${e.price.toFixed(2)}</span>`)
                : '';
            nightlyTotal += e.price || 0;

            html += `<div class="haunt-entry">
                <div>
                    <div class="haunt-name">${e.name}</div>
                    <div class="haunt-time">Arrive: ${arrival} | Open: ${open} – ${close}</div>
                </div>
                <div>${priceHtml}</div>
            </div>`;
        }

        if (nightlyTotal > 0) {
            html += `<div class="subtotal">Nightly Total: $${nightlyTotal.toFixed(2)}</div>`;
        }
        tripTotal += nightlyTotal;
        html += '</div>';
    }

    if (tripTotal > 0) {
        html += `<div class="trip-total">Trip Total: $${tripTotal.toFixed(2)}</div>`;
    }

    if (data.unscheduled && data.unscheduled.length > 0) {
        html += '<div class="card" style="border-color:#4a0e0e; margin-top:24px;"><h3 style="color:#e85d75;">Could Not Schedule</h3>';
        for (const u of data.unscheduled) {
            html += `<p><strong>${u.name}</strong> — ${u.reason}</p>`;
        }
        html += '</div>';
    }

    container.innerHTML = html;
    populateAdjustDropdown(data);
    loadDiscoverySuggestions();
}

async function loadDiscoverySuggestions() {
    const resp = await fetch('/api/discover', {method: 'POST'});
    const data = await resp.json();
    if (data.gap_dates && data.gap_dates.length > 0) {
        const container = document.getElementById('itinerary-container');
        let html = '<div class="card" style="border-left: 4px solid #4a7a2e; margin-top:24px;">';
        html += '<h3 style="color:#4ecb71;">Open Nights</h3>';
        html += '<p style="color:#888; margin-bottom:12px;">These nights have no haunts scheduled:</p>';
        for (const d of data.gap_dates) {
            const dateObj = new Date(d + 'T00:00:00');
            const label = dateObj.toLocaleDateString('en-US', {weekday:'long', month:'long', day:'numeric'});
            html += `<div class="suggestion"><strong>${label}</strong> — Search for haunts near your route for this night</div>`;
        }
        html += '</div>';
        container.insertAdjacentHTML('beforeend', html);
    }
}

function populateAdjustDropdown(data) {
    const nameSelect = document.getElementById('adjust-name');
    nameSelect.innerHTML = '<option value="">Select...</option>';
    const allNames = new Set();
    for (const entries of Object.values(data.scheduled)) {
        for (const e of entries) allNames.add(e.name);
    }
    for (const name of allNames) {
        nameSelect.innerHTML += `<option value="${name}">${name}</option>`;
    }
    nameSelect.onchange = async function() {
        const dateSelect = document.getElementById('adjust-date');
        dateSelect.innerHTML = '<option value="">Loading...</option>';
        if (!this.value) { dateSelect.innerHTML = '<option value="">Select attraction first</option>'; return; }
        const resp = await fetch(`/api/eligible-dates?name=${encodeURIComponent(this.value)}`);
        const dates = await resp.json();
        dateSelect.innerHTML = '<option value="">Select date...</option>';
        for (const d of dates) {
            const dateObj = new Date(d + 'T00:00:00');
            const label = dateObj.toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric'});
            dateSelect.innerHTML += `<option value="${d}">${label}</option>`;
        }
    };
}

function formatTime(isoTime) {
    const [h, m] = isoTime.split(':').map(Number);
    const ampm = h >= 12 ? 'PM' : 'AM';
    const hour = h === 0 ? 12 : h > 12 ? h - 12 : h;
    return `${hour}:${String(m).padStart(2, '0')} ${ampm}`;
}

async function adjustSchedule() {
    const name = document.getElementById('adjust-name').value;
    const d = document.getElementById('adjust-date').value;
    if (!name || !d) return;

    const resp = await fetch('/api/adjust', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name, date: d}),
    });
    const data = await resp.json();
    renderItinerary(data);
}

loadItinerary();
</script>
{% endblock %}
```

- [ ] **Step 4: Create export template**

```html
<!-- templates/export.html -->
{% extends "base.html" %}
{% block title %}Export — Haunt Trip Planner{% endblock %}
{% block content %}
<h2>Export Your Itinerary</h2>

<div class="card">
    <label for="export-title">Itinerary Title</label>
    <input type="text" id="export-title" value="Haunt Trip 2026" placeholder="My Haunt Trip">
</div>

<div style="display:flex; gap:12px; justify-content:center; margin-top:20px;">
    <button class="btn btn-primary" onclick="printItinerary()">Print</button>
    <button class="btn btn-secondary" onclick="downloadHtml()">Download HTML</button>
</div>
{% endblock %}
{% block scripts %}
<script>
function printItinerary() {
    window.print();
}

async function downloadHtml() {
    const title = document.getElementById('export-title').value || 'Haunt Trip';
    const resp = await fetch(`/api/export?title=${encodeURIComponent(title)}`);
    const html = await resp.text();
    const blob = new Blob([html], {type: 'text/html'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title.replace(/\s+/g, '-').toLowerCase()}.html`;
    a.click();
    URL.revokeObjectURL(url);
}
</script>
{% endblock %}
```

- [ ] **Step 5: Update app.js submitAttractions to trigger scraping flow**

Add to `static/app.js`, replacing the existing `submitAttractions` function:

```javascript
async function submitAttractions() {
    if (attractions.length === 0) {
        alert('Add at least one attraction before continuing.');
        return;
    }
    window.location.href = '/review';
}
```

- [ ] **Step 6: Start the app and test the full flow in browser**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python hauntplanner.py`
Open: http://localhost:5000
Test: Walk through setup → attractions → review → itinerary → export. Verify spooky theme renders correctly on all screens.

- [ ] **Step 7: Commit**

```bash
git add templates/loading.html templates/review.html templates/itinerary.html templates/export.html static/app.js
git commit -m "feat: add loading, review, itinerary, and export screens"
```

---

### Task 14: Integration Test + Final Polish

**Files:**
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write integration test for full workflow**

Add to `tests/test_app.py`:

```python
from unittest.mock import patch


def test_full_workflow(client):
    # 1. Save trip
    trip_data = {
        "date_range": {"start": "2026-10-01", "end": "2026-10-14"},
        "start_location": "Chicago, IL",
        "end_location": "Chicago, IL",
        "blackout_dates": [],
        "legs": [],
    }
    resp = client.post("/api/trip", data=json.dumps(trip_data), content_type="application/json")
    assert resp.status_code == 200

    # 2. Add attractions (mock geocoding to avoid network calls)
    with patch("hauntplanner.geocode_address", return_value=(41.88, -87.63)):
        for name in ["Haunt A", "Haunt B"]:
            resp = client.post(
                "/api/attractions",
                data=json.dumps({
                    "name": name,
                    "address": "123 Test St",
                    "schedule_url": f"https://{name.lower().replace(' ', '')}.com",
                    "assigned_dates": [],
                }),
                content_type="application/json",
            )
            assert resp.status_code == 200

    # 3. Manually set schedules (skip scraping)
    for name in ["Haunt A", "Haunt B"]:
        resp = client.put(
            "/api/schedule",
            data=json.dumps({
                "name": name,
                "schedule": [
                    {"date": "2026-10-03", "open_time": "19:00", "close_time": "23:00", "price": 25.0, "ticket_url": None},
                    {"date": "2026-10-04", "open_time": "19:00", "close_time": "23:00", "price": 30.0, "ticket_url": None},
                ],
            }),
            content_type="application/json",
        )
        assert resp.status_code == 200

    # 4. Optimize
    resp = client.post("/api/optimize")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["scheduled"]) > 0

    # 5. Adjust
    resp = client.post(
        "/api/adjust",
        data=json.dumps({"name": "Haunt A", "date": "2026-10-04"}),
        content_type="application/json",
    )
    assert resp.status_code == 200

    # 6. Export
    resp = client.get("/api/export?title=Test+Trip")
    assert resp.status_code == 200
    assert b"<!DOCTYPE html>" in resp.data
    assert b"Test Trip" in resp.data
```

- [ ] **Step 2: Run all tests**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python -m pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_app.py
git commit -m "feat: add integration test for full trip planning workflow"
```

- [ ] **Step 4: Final manual test**

Run: `cd /Users/mallierust/Desktop/Claude/trip-planner && python hauntplanner.py`

Test the full flow:
1. Open http://localhost:5000
2. Enter trip dates (Oct 1–14, 2026), Chicago as start/end
3. Add 2-3 real or fake haunts with addresses and URLs
4. Review scraped schedules, correct any errors
5. Generate itinerary — verify dates, times, prices, totals
6. Adjust an attraction's date — verify re-optimization
7. Export as HTML — open the downloaded file
8. Print view — verify clean layout

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: final polish and integration verification"
```
