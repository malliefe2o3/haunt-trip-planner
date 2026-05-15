# Haunt Trip Planner — Design Spec

## Overview

A downloadable Python/Flask web application that helps haunted attraction enthusiasts optimize multi-night haunt trips. Users enter their trip dates, locations, and a list of haunted attractions; the app scrapes schedules, geocodes addresses, and produces an optimized itinerary that maximizes the number of haunts visited while respecting distance, schedule, and timing constraints.

The app runs locally (`python hauntplanner.py`, open localhost in browser), requires no accounts or paid API keys for core functionality, and outputs a printable/exportable itinerary.

## Architecture

**Stack:** Python 3 + Flask (monolith). Single process serves the web UI and handles all backend work.

**Components:**

1. **Web UI** — Flask serves HTML/CSS/JS. Dark, spooky-themed interface. Stepped flow guides users through input → review → itinerary → export.
2. **Schedule Scraper** — Two-tier system for extracting dates, hours, prices, and ticket links from attraction websites.
3. **Geocoder** — Converts addresses to lat/lng via OpenStreetMap Nominatim (free, no API key). Computes straight-line distances between attractions.
4. **Itinerary Optimizer** — Assigns attractions to dates and time slots using constraint filtering, proximity clustering, and a multi-factor prioritization algorithm.
5. **Discovery Engine** — Scrapes haunted attraction directories to suggest haunts the user hasn't listed, filling itinerary gaps and densifying nights with room for more.

**No external services required for core functionality.** Optional Claude API key upgrades schedule scraping accuracy.

## User Flow

### Screen 1: Trip Setup

- **Overall date range:** start date and end date pickers
- **Start and end locations:** address text fields (geocoded on submit)
- **Legs (optional):** user can add trip legs, each with its own date window and start/end locations. If no legs are defined, the entire trip is treated as one implicit leg.
- **Blackout dates:** date picker to mark dates when no attractions can be visited

### Screen 2: Add Attractions

For each attraction, user provides:
- **Name** (required) — text field
- **Address** (required) — text field, geocoded on submit
- **Schedule page URL** (required) — used by the scraper to extract dates, hours, prices, and ticket links
- **Assigned date or date window** (optional) — if the user already knows when they're visiting

Users can add as many attractions as they want. A "Submit" button triggers scraping and geocoding.

### Screen 3: Loading/Scraping

A loading screen while the app:
1. Scrapes each attraction's schedule URL for dates, hours, prices, and ticket page links
2. Geocodes all addresses via Nominatim (rate-limited to 1 req/sec, so this may take a moment with many attractions)

Note: the optimizer does NOT run yet — the user must review and confirm scraped data first.

### Screen 4: Schedule Review

After scraping, each attraction displays:
- **Parsed dates and hours** for each open night
- **Ticket prices** per date (if pricing varies by night)
- **Ticket page link** (if found)
- **Confidence indicator:** green (parsed cleanly), yellow (partial — some data found), red (couldn't parse — manual entry needed)
- **Inline editing** to correct or fill in any field

User confirms the schedule data, then clicks "Generate Itinerary" to run the optimizer (brief loading state while it computes).

### Screen 5: Itinerary View

The optimized schedule, organized by date:

Each date section shows:
- Date header
- List of haunts for that night, each showing:
  - Attraction name
  - Suggested arrival time
  - Open and close times for that date
  - Ticket price for that date, hyperlinked to the ticket page if available
- **Nightly subtotal** (sum of ticket prices for that night)
- **Discovery suggestions** (if any) — haunts the user hasn't added that could fill a gap or fit into the night

**Trip total** displayed at the bottom (sum of all nightly subtotals).

**Unscheduled attractions:** If any attractions could not be scheduled (no eligible dates remaining, or couldn't fit within time constraints), they are listed separately with an explanation of why they couldn't be placed (e.g., "no open dates within your trip window", "couldn't fit — all eligible nights are full").

### Screen 6: Adjustment Panel

- User selects an attraction to adjust
- Dropdown shows only dates the attraction is open (per scraped schedule)
- On adjustment, the optimizer re-runs with the manual assignment locked as a constraint
- UI shows what changed vs. the previous itinerary

### Screen 7: Export/Print

- **Print view** — clean, high-contrast layout optimized for printing (hides UI controls, fits standard page widths)
- **HTML export** — download a standalone HTML file containing the full itinerary with all details (dates, times, prices, ticket links, totals). Can be opened in any browser and shared.

## Data Model

```
Trip
├── date_range: {start: date, end: date}
├── start_location: {address: str, lat: float, lng: float}
├── end_location: {address: str, lat: float, lng: float}
├── blackout_dates: [date]
├── legs: [
│     {date_range: {start, end},
│      start_location: {address, lat, lng},
│      end_location: {address, lat, lng}}
│   ]
└── attractions: [
      {name: str,
       address: str,
       lat: float,
       lng: float,
       schedule_url: str,
       assigned_dates: [date] | null,
       schedule: [
         {date: date,
          open_time: time,
          close_time: time,
          price: float | null,
          ticket_url: str | null}
       ]}
    ]
```

## Schedule Scraping

### Tier 1 — Regex/Heuristic Parser (always available)

1. Fetch page HTML with `requests`
2. Extract text content with BeautifulSoup
3. Pattern-match against common haunted attraction schedule formats:
   - Explicit date lists: "Oct 4, 5, 11, 12, 18, 19"
   - Day-of-week rules: "Every Friday & Saturday in October"
   - Date ranges: "September 27 – November 2"
   - Time ranges: "7:00 PM – 12:00 AM", "Dusk to Midnight"
   - Combined: "Fri & Sat Oct 4–Nov 2, 7pm–12am"
   - Prices: "$25 General Admission", "Fri/Sat $30, Sun-Thu $20"
   - Ticket links: URLs containing "ticket", "buy", or linking to known platforms (Eventbrite, HauntPay, FearTickets)
4. Assign confidence score based on completeness: green (dates + times + price), yellow (partial), red (failed)

### Tier 2 — LLM-Assisted Parser (optional, requires Claude API key)

- Activated when Tier 1 confidence is yellow or red
- Sends extracted page text to Claude API with a structured prompt requesting dates, hours, prices, and ticket URLs in JSON format
- Significantly better at parsing natural language descriptions, unusual formats, and edge cases
- User provides their own Claude API key in the app settings

### Both tiers feed into the Schedule Review screen for user verification and correction.

## Itinerary Optimization Algorithm

### Phase 1: Constraint Filtering

For each attraction:
1. Remove blackout dates from its schedule
2. Remove dates outside the trip date range
3. If legs exist, assign each attraction to the leg whose start location is geographically closest to the attraction. Then keep only dates within that leg's date window. If an attraction falls equidistant between two legs, prefer the leg with more open dates for that attraction.
4. Lock user-assigned dates as fixed constraints
5. Result: each attraction has a set of eligible dates

### Phase 2: Proximity Clustering

1. Compute straight-line distance between every pair of attractions using lat/lng coordinates
2. Group attractions within 20-mile radius into clusters (transitive — if A is near B and B is near C, all three cluster together)
3. Attractions more than 20 miles from all others form solo clusters
4. **Hard rule:** attractions from different clusters are never scheduled on the same date

### Phase 3: Date Assignment

Assign clusters to dates using these priorities (highest to lowest):

1. **Scarcity** — attractions with the fewest eligible open dates get scheduled first, on their earliest available date, so they don't get squeezed out
2. **Travel efficiency** — clusters closer to the leg's start location + end location get priority (sum of distances). Reduces dead miles.
3. **Round-trip optimization** — if a leg's start and end locations are the same, schedule farther clusters in the middle of the leg's date window and closer clusters at the start/end
4. **Cluster density** — prefer dates when the most attractions in the cluster are open simultaneously. Maximize haunts per night.

### Phase 4: Time Slot Assignment

For each date with assigned attractions:

1. Sort attractions by opening time (earliest to latest)
2. First attraction: suggested arrival = opening time
3. Each subsequent attraction:
   ```
   arrival = previous_arrival + 45 minutes (walkthrough) + drive_time
   ```
   Where drive_time:
   - distance / 40 mph if attractions are ≤ 10 miles apart
   - distance / 50 mph if attractions are 11–20 miles apart
4. **Hard constraint:** arrival must be no later than `closing_time - 45 minutes`. If an attraction can't fit, it gets bumped to the next eligible date and the algorithm re-runs.
5. Final sort order within a date: earliest opening to latest closing

### Phase 5: Re-optimization

When a user manually adjusts an attraction's date assignment:
1. Lock the manual assignment as an immutable constraint
2. Re-run Phases 1–4 with the new constraint
3. Only offer the user dates the attraction is actually open
4. Highlight what changed vs. the previous itinerary

## Discovery Engine

### Data Source

Scrape a haunted attraction directory (e.g., TheScareFactor.com) for attractions in the geographic region of the user's trip. Cache results for the session.

### Two Types of Suggestions

**Gap-fillers:** Nights within the trip window where nothing is scheduled and no blackout exists. Suggest haunts near the trip's locations that are open on those dates.

**Same-night densifiers:** Nights where the last scheduled haunt ends early enough to fit another. Check:
- Is the suggested haunt within 20 miles of the last scheduled haunt on that night?
- Can the user arrive at least 45 minutes before it closes (using the walkthrough + drive time formula)?
- Is it open on that date?

### Suggestion Display

Suggestions appear below the itinerary grouped by type. Each suggestion shows:
- Attraction name
- Distance from nearest scheduled haunt (or trip location for gap-fillers)
- Link to the attraction's website
- One-click "Add to Trip" button, which triggers schedule scraping for that attraction and re-runs the optimizer

## Geocoding & Distance

- **Geocoding:** OpenStreetMap Nominatim API (free, no key, rate-limited to 1 req/sec — batch with delays)
- **Distance:** Haversine formula on lat/lng coordinates for straight-line distance
- **"30-minute drive" proxy:** 20-mile radius
- **Drive time estimation:** distance / 40 mph (≤ 10 miles) or distance / 50 mph (11–20 miles)

## Visual Design

**Dark, spooky theme:**
- Dark background (deep blacks/charcoals)
- Accent colors: deep purples, blood reds, sickly greens
- Spooky design elements: cobweb accents, dripping text effects on headers, subtle fog/mist background animations
- Bold, readable typography that balances atmosphere with usability
- High-contrast text for accessibility despite the dark theme

**Print/export view:** Clean, high-contrast layout. Spooky branding retained but simplified for readability on paper (no animations, lighter background option).

## Technical Requirements

- **Python 3.8+**
- **Dependencies:** Flask, requests, BeautifulSoup4, geopy (Nominatim), anthropic SDK (optional)
- **No database** — all data lives in memory for the session
- **No accounts or auth**
- **Distribution:** GitHub repo with `requirements.txt` and a README explaining `pip install -r requirements.txt && python hauntplanner.py`
