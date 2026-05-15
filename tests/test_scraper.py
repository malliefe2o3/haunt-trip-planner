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
