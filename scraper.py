import json
import re
import calendar
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

try:
    import anthropic
except ImportError:
    anthropic = None

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

LLM_PROMPT = """Extract the schedule information from this haunted attraction page text.
Return a JSON object with these fields:
- "dates": list of dates in YYYY-MM-DD format when the attraction is open
- "time_ranges": list of [open_time, close_time] pairs in HH:MM 24-hour format
- "prices": list of ticket prices as numbers (no $ sign)
- "ticket_urls": list of URLs where tickets can be purchased

Only return the JSON object, no other text."""


@dataclass
class ScrapedSchedule:
    dates: list
    time_ranges: list
    prices: list
    ticket_urls: list
    duration_min: Optional[int] = None

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


def parse_dates_from_text(text: str, year: int) -> list:
    dates = set()
    _parse_day_of_week_rules(text, year, dates)
    _parse_date_ranges(text, year, dates)
    _parse_explicit_date_lists(text, year, dates)
    return sorted(dates)


def _parse_day_of_week_rules(text: str, year: int, dates: set) -> None:
    # Build alternation of all day name keys, longest first to avoid partial matches
    day_keys = sorted(DAY_NAMES.keys(), key=len, reverse=True)
    day_alt = "|".join(day_keys)
    # Pattern: "Every <day> [and <day>]* in <month>"
    pattern = (
        r"every\s+"
        r"((?:(?:" + day_alt + r")(?:\s*(?:and|&|,)\s*)?)+)"
        r"\s+in\s+(\w+)"
    )
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


def _parse_date_ranges(text: str, year: int, dates: set) -> None:
    month_re = "|".join(sorted(ALL_MONTHS.keys(), key=len, reverse=True))
    pattern = rf"({month_re})\s+(\d{{1,2}})\s*[-–—]|(?:to)\s*(?:({month_re})\s+)?(\d{{1,2}})"
    # Use a two-step approach: find "Month Day - [Month] Day" patterns
    range_pattern = (
        rf"({month_re})\s+(\d{{1,2}})"
        r"\s*[-–—to]+\s*"
        rf"(?:({month_re})\s+)?(\d{{1,2}})"
    )
    for match in re.finditer(range_pattern, text, re.IGNORECASE):
        start_month_str = match.group(1)
        start_day = int(match.group(2))
        end_month_str = match.group(3)
        end_day = int(match.group(4))
        start_month = ALL_MONTHS[start_month_str.lower()]
        end_month = ALL_MONTHS[end_month_str.lower()] if end_month_str else start_month
        try:
            start = date(year, start_month, start_day)
            end = date(year, end_month, end_day)
        except ValueError:
            continue
        current = start
        while current <= end:
            dates.add(current)
            current += timedelta(days=1)


def _parse_explicit_date_lists(text: str, year: int, dates: set) -> None:
    month_re = "|".join(sorted(ALL_MONTHS.keys(), key=len, reverse=True))
    # Match "Month day, day, day..." — stop at a word that is not a digit or comma
    pattern = rf"({month_re})\s+((?:\d{{1,2}}(?:\s*,\s*)?)+)"
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


def parse_times_from_text(text: str) -> list:
    # Normalize special words before regex matching
    text_norm = text.lower()
    text_norm = text_norm.replace("midnight", "12:00 am")
    text_norm = text_norm.replace("noon", "12:00 pm")
    text_norm = text_norm.replace("dusk", "6:30 pm")

    # Match times like "7:00 PM", "7PM", "6:30 pm"
    time_pattern = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)"
    times_found = re.findall(time_pattern, text_norm, re.IGNORECASE)

    results = []
    for i in range(0, len(times_found) - 1, 2):
        open_t = _to_time(times_found[i])
        close_t = _to_time(times_found[i + 1])
        results.append((open_t, close_t))
    return results


def _to_time(match_groups: tuple) -> time:
    hour = int(match_groups[0])
    minute = int(match_groups[1]) if match_groups[1] else 0
    ampm = match_groups[2].lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    return time(hour % 24, minute)


def parse_prices_from_text(text: str) -> list:
    pattern = r"\$\s*(\d+(?:\.\d{2})?)"
    return [float(p) for p in re.findall(pattern, text)]


def parse_duration_from_text(text: str) -> Optional[int]:
    patterns = [
        r"(\d+)\s*[-–—to]+\s*(\d+)\s*min(?:ute)?s?\s*(?:long|duration|walkthrough|experience|tour)",
        r"(?:duration|walkthrough|experience|tour|lasts?|takes?|approximately|approx\.?|about|around)\s*[:.]?\s*(\d+)\s*[-–—to]+\s*(\d+)\s*min",
        r"(?:duration|walkthrough|experience|tour|lasts?|takes?|approximately|approx\.?|about|around)\s*[:.]?\s*(\d+)\s*min",
        r"(\d+)\s*min(?:ute)?s?\s*(?:walkthrough|experience|tour|long)",
        r"(\d+)\s*[-–—]\s*(\d+)\s*min(?:ute)?s?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 2 and groups[1]:
                return (int(groups[0]) + int(groups[1])) // 2
            return int(groups[0])
    hour_pattern = r"(?:duration|walkthrough|experience|tour|lasts?|takes?)\s*[:.]?\s*(\d+(?:\.\d+)?)\s*hours?"
    match = re.search(hour_pattern, text, re.IGNORECASE)
    if match:
        return round(float(match.group(1)) * 60)
    return None


def find_ticket_links(html: str) -> list:
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


def fetch_page(url: str) -> tuple:
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
        duration_min=parse_duration_from_text(text),
    )


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
