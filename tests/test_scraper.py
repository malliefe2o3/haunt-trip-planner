from datetime import date, time
from unittest.mock import patch, MagicMock
from scraper import (
    parse_dates_from_text,
    parse_times_from_text,
    parse_prices_from_text,
    find_ticket_links,
    scrape_schedule,
    ScrapedSchedule,
    llm_parse_schedule,
    scrape_schedule_with_llm,
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
