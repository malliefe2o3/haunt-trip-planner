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
