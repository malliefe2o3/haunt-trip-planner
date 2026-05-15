import json
import pytest
from unittest.mock import patch
from hauntplanner import create_app


@pytest.fixture(autouse=True)
def reset_state():
    """Reset module-level state before each test."""
    import hauntplanner
    hauntplanner._reset_state()
    yield
    hauntplanner._reset_state()


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


def test_locations_page_returns_200(client):
    response = client.get("/locations")
    assert response.status_code == 200


def test_setup_page_returns_200(client):
    response = client.get("/setup")
    assert response.status_code == 200


def test_attractions_page_returns_200(client):
    response = client.get("/attractions")
    assert response.status_code == 200


def test_review_page_returns_200(client):
    response = client.get("/review")
    assert response.status_code == 200


def test_itinerary_page_returns_200(client):
    response = client.get("/itinerary")
    assert response.status_code == 200


def test_export_page_returns_200(client):
    response = client.get("/export-view")
    assert response.status_code == 200


def test_loading_page_returns_200(client):
    response = client.get("/loading")
    assert response.status_code == 200


def test_api_save_settings(client):
    response = client.post(
        "/api/settings",
        data=json.dumps({"claude_api_key": "sk-ant-test123"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_api_save_trip(client):
    with patch("hauntplanner.geocode_address", return_value=(41.88, -87.63)):
        trip_data = {
            "date_range": {"start": "2026-10-01", "end": "2026-10-14"},
            "home_base": "Chicago, IL",
            "blackout_dates": ["2026-10-05"],
            "segments": [],
        }
        response = client.post(
            "/api/trip",
            data=json.dumps(trip_data),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"


def test_api_save_trip_with_segments(client):
    with patch("hauntplanner.geocode_address", return_value=(41.88, -87.63)):
        trip_data = {
            "date_range": {"start": "2026-10-01", "end": "2026-10-14"},
            "home_base": "Chicago, IL",
            "blackout_dates": [],
            "segments": [
                {
                    "date_range": {"start": "2026-10-01", "end": "2026-10-07"},
                    "start_location": "Chicago, IL",
                    "end_location": "Indianapolis, IN",
                }
            ],
        }
        response = client.post(
            "/api/trip",
            data=json.dumps(trip_data),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"


def test_api_add_attraction(client):
    with patch("hauntplanner.geocode_address", return_value=(41.88, -87.63)):
        response = client.post(
            "/api/attractions",
            data=json.dumps({
                "name": "Test Haunt",
                "address": "123 Main St",
                "schedule_url": "https://example.com",
                "assigned_dates": [],
            }),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.get_json()["status"] == "ok"
        assert response.get_json()["name"] == "Test Haunt"


def test_api_optimize_returns_itinerary(client):
    response = client.post("/api/optimize")
    assert response.status_code == 200
    data = response.get_json()
    assert "scheduled" in data
    assert "unscheduled" in data


def test_api_eligible_dates_no_trip(client):
    response = client.get("/api/eligible-dates?name=Test")
    assert response.status_code == 200
    assert response.get_json()["dates"] == []


def test_api_discover_no_trip(client):
    response = client.post("/api/discover")
    assert response.status_code == 200
    data = response.get_json()
    assert "gaps" in data
    assert "suggestions" in data


def test_api_export_returns_html(client):
    response = client.get("/api/export?title=My+Trip")
    assert response.status_code == 200
    assert b"<!DOCTYPE html>" in response.data


def test_api_schedule_no_trip(client):
    response = client.put(
        "/api/schedule",
        data=json.dumps({"name": "X", "schedule": []}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_api_adjust_no_trip(client):
    response = client.post(
        "/api/adjust",
        data=json.dumps({"name": "X", "date": "2026-10-01"}),
        content_type="application/json",
    )
    assert response.status_code == 400


def test_full_workflow(client):
    with patch("hauntplanner.geocode_address", return_value=(41.88, -87.63)):
        # 1. Save trip
        client.post(
            "/api/trip",
            data=json.dumps({
                "date_range": {"start": "2026-10-01", "end": "2026-10-14"},
                "home_base": "Chicago, IL",
                "blackout_dates": [],
                "segments": [],
            }),
            content_type="application/json",
        )

        # 2. Add attractions
        for name in ["Haunt A", "Haunt B"]:
            client.post(
                "/api/attractions",
                data=json.dumps({
                    "name": name,
                    "address": "123 Test St",
                    "schedule_url": "https://{}.com".format(name.lower().replace(" ", "")),
                    "assigned_dates": [],
                }),
                content_type="application/json",
            )

        # 3. Set schedules manually
        for name in ["Haunt A", "Haunt B"]:
            client.put(
                "/api/schedule",
                data=json.dumps({
                    "name": name,
                    "schedule": [
                        {
                            "date": "2026-10-03",
                            "open_time": "19:00",
                            "close_time": "23:00",
                            "price": 25.0,
                            "ticket_url": None,
                        },
                        {
                            "date": "2026-10-04",
                            "open_time": "19:00",
                            "close_time": "23:00",
                            "price": 30.0,
                            "ticket_url": None,
                        },
                    ],
                }),
                content_type="application/json",
            )

        # 4. Optimize
        resp = client.post("/api/optimize")
        assert resp.status_code == 200
        assert len(resp.get_json()["scheduled"]) > 0

        # 5. Adjust
        resp = client.post(
            "/api/adjust",
            data=json.dumps({"name": "Haunt A", "date": "2026-10-04"}),
            content_type="application/json",
        )
        assert resp.status_code == 200

        # 6. Export
        resp = client.get("/api/export?title=Test+Trip")
        assert b"Test Trip" in resp.data


def test_api_schedule_not_found(client):
    """Test PUT /api/schedule with a name that doesn't exist in the trip."""
    with patch("hauntplanner.geocode_address", return_value=(41.88, -87.63)):
        # Create a trip first
        client.post(
            "/api/trip",
            data=json.dumps({
                "date_range": {"start": "2026-10-01", "end": "2026-10-14"},
                "home_base": "Chicago, IL",
                "blackout_dates": [],
                "segments": [],
            }),
            content_type="application/json",
        )

        response = client.put(
            "/api/schedule",
            data=json.dumps({"name": "Nonexistent Haunt", "schedule": []}),
            content_type="application/json",
        )
        assert response.status_code == 404
