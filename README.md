# Haunt Trip Planner

A local web app that helps haunted attraction enthusiasts optimize multi-night haunt trips. Enter your trip dates, locations, and a list of haunted attractions — the app scrapes schedules, geocodes addresses, and produces an optimized itinerary that maximizes the number of haunts visited while respecting distance, schedule, and timing constraints.

## Features

- **Trip planning** with date ranges, trip segments, blackout dates, and home base location
- **Auto-weekend segments** — Fri/Sat/Sun automatically grouped for scheduling
- **Schedule scraping** — regex-based parser extracts dates, hours, prices, and ticket links from haunt websites
- **Proximity clustering** — groups nearby attractions (within 20 miles) for same-night scheduling
- **Itinerary optimization** — prioritizes by schedule scarcity, travel efficiency, and cluster density
- **Drive time estimates** — suggested arrival times with drive calculations (40mph ≤10mi, 50mph 11-20mi)
- **Discovery engine** — suggests haunts you haven't listed that could fill gaps or densify nights
- **CSV import** — bulk add attractions and schedule data
- **Export** — print-friendly view or standalone HTML download with prices, ticket links, and trip totals

## Setup

**Requirements:** Python 3.9+ ([download Python here](https://www.python.org/downloads/) if you don't have it)

### 1. Download the code

[**Download ZIP**](https://github.com/malliefe2o3/haunt-trip-planner/archive/refs/heads/main.zip)

Once downloaded, unzip the folder and note where it is on your computer (e.g. your Downloads folder).

### 2. Open a terminal

- **Mac:** Open the **Terminal** app (search for "Terminal" in Spotlight)
- **Windows:** Open **Command Prompt** (search for "cmd" in the Start menu)

**Important:** These are terminal commands, not Python — don't type them into Python itself.

### 3. Navigate to the folder and run

Replace the path below with wherever you unzipped the folder:

```bash
cd ~/Downloads/haunt-trip-planner-main
python -m pip install -r requirements.txt
python hauntplanner.py
```

On Windows, Command Prompt already starts in your user folder. Type each line one at a time, pressing Enter after each:
```
cd Downloads
cd haunt-trip-planner-main
python -m pip install -r requirements.txt
python hauntplanner.py
```

> **"No such file" error?** The unzipped folder name can vary — check what it's actually called in your Downloads folder and use that name instead.

### 4. Open the app

Once running, you'll see a line that says `Running on http://127.0.0.1:5000`. Copy that URL and paste it into your browser to open the app.

## How It Works

1. **Dates** — Set your trip window, optional segments, and blackout dates
2. **Locations** — Set your home base and segment-specific start/end locations
3. **Attractions** — Add haunts manually or import via CSV
4. **Review** — Verify scraped schedule data, edit as needed, import schedule CSVs
5. **Itinerary** — View optimized schedule with arrival times, prices, and drive estimates
6. **Export** — Print or download your itinerary as a standalone HTML file

## CSV Formats

**Attractions CSV** (import on Attractions page):
```
Name,Address,Schedule URL,Scheduled Date (Optional)
Haunted Hollow,"123 Main St, Springfield, IL",https://hauntedhollowil.com,
```

**Schedule CSV** (import on Review page):
```
Name,Date,Open,Close,Price,Ticket URL
Haunted Hollow,2026-10-03,19:00,23:00,25,https://hauntedhollowil.com/tickets
```
