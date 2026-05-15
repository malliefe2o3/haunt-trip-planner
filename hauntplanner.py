# hauntplanner.py
from __future__ import annotations

import json
from datetime import date, time
from typing import Optional, List, Dict

from flask import Flask, render_template, request, jsonify

from models import Trip, Location, Attraction, ScheduleEntry, Leg
from geocoder import geocode_address
from scraper import scrape_schedule_with_llm
from optimizer import optimize, reoptimize, filter_eligible_dates, ItineraryResult
from discovery import find_gap_nights, find_densify_opportunities
from exporter import generate_export_html

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_trip = None  # type: Optional[Trip]
_itinerary = None  # type: Optional[ItineraryResult]
_api_key = None  # type: Optional[str]


def _reset_state() -> None:
    """Reset module-level globals (used between test runs)."""
    global _trip, _itinerary, _api_key
    _trip = None
    _itinerary = None
    _api_key = None


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_itinerary(result):
    # type: (ItineraryResult) -> dict
    scheduled = {}  # type: Dict[str, list]
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


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    app = Flask(__name__)

    @app.before_request
    def _ensure_state():
        """Ensure module-level state is accessible (no-op, just for clarity)."""
        pass

    # ------------------------------------------------------------------
    # Page routes
    # ------------------------------------------------------------------

    @app.route("/")
    @app.route("/setup")
    def setup_page():
        return render_template("setup.html")

    @app.route("/attractions")
    def attractions_page():
        return render_template("attractions.html")

    @app.route("/loading")
    def loading_page():
        return render_template("loading.html")

    @app.route("/review")
    def review_page():
        return render_template("review.html")

    @app.route("/itinerary")
    def itinerary_page():
        return render_template("itinerary.html")

    @app.route("/export-view")
    def export_page():
        return render_template("export.html")

    # ------------------------------------------------------------------
    # API routes
    # ------------------------------------------------------------------

    @app.route("/api/settings", methods=["POST"])
    def api_settings():
        global _api_key
        data = request.get_json(force=True)
        _api_key = data.get("claude_api_key")
        return jsonify({"status": "ok"})

    @app.route("/api/trip", methods=["POST"])
    def api_trip():
        global _trip
        data = request.get_json(force=True)

        dr = data["date_range"]
        start_date = date.fromisoformat(dr["start"])
        end_date = date.fromisoformat(dr["end"])

        blackouts = [date.fromisoformat(d) for d in data.get("blackout_dates", [])]

        try:
            start_coords = geocode_address(data["start_location"])
        except Exception:
            start_coords = (0.0, 0.0)

        try:
            end_coords = geocode_address(data["end_location"])
        except Exception:
            end_coords = (0.0, 0.0)

        start_loc = Location(data["start_location"], start_coords[0], start_coords[1])
        end_loc = Location(data["end_location"], end_coords[0], end_coords[1])

        legs = []  # type: List[Leg]
        for leg_data in data.get("legs", []):
            leg_dr = leg_data["date_range"]
            leg_start = date.fromisoformat(leg_dr["start"])
            leg_end = date.fromisoformat(leg_dr["end"])

            try:
                ls_coords = geocode_address(leg_data["start_location"])
            except Exception:
                ls_coords = (0.0, 0.0)

            try:
                le_coords = geocode_address(leg_data["end_location"])
            except Exception:
                le_coords = (0.0, 0.0)

            legs.append(Leg(
                date_range=(leg_start, leg_end),
                start_location=Location(leg_data["start_location"], ls_coords[0], ls_coords[1]),
                end_location=Location(leg_data["end_location"], le_coords[0], le_coords[1]),
            ))

        _trip = Trip(
            date_range=(start_date, end_date),
            start_location=start_loc,
            end_location=end_loc,
            blackout_dates=blackouts,
            legs=legs,
            attractions=_trip.attractions if _trip else [],
        )

        return jsonify({"status": "ok"})

    @app.route("/api/attractions", methods=["POST"])
    def api_attractions():
        global _trip
        data = request.get_json(force=True)

        try:
            coords = geocode_address(data["address"])
        except Exception:
            coords = (0.0, 0.0)

        assigned = None  # type: Optional[List[date]]
        if data.get("assigned_dates"):
            assigned = [date.fromisoformat(d) for d in data["assigned_dates"]]

        attraction = Attraction(
            name=data["name"],
            address=data["address"],
            lat=coords[0],
            lng=coords[1],
            schedule_url=data.get("schedule_url", ""),
            assigned_dates=assigned if assigned else None,
            schedule=[],
        )

        if _trip is None:
            # Create a minimal trip to hold attractions
            _trip = Trip(
                date_range=(date(2026, 10, 1), date(2026, 10, 31)),
                start_location=Location("", 0.0, 0.0),
                end_location=Location("", 0.0, 0.0),
                attractions=[attraction],
            )
        else:
            _trip.attractions.append(attraction)

        return jsonify({"status": "ok", "name": attraction.name})

    @app.route("/api/scrape", methods=["POST"])
    def api_scrape():
        global _trip
        if _trip is None:
            return jsonify({"error": "No trip configured"}), 400

        results = []
        year = _trip.date_range[0].year

        for attraction in _trip.attractions:
            if not attraction.schedule_url:
                results.append({
                    "name": attraction.name,
                    "confidence": "red",
                    "dates": [],
                    "time_ranges": [],
                    "prices": [],
                    "ticket_urls": [],
                })
                continue

            try:
                scraped = scrape_schedule_with_llm(
                    attraction.schedule_url, year, _api_key
                )
                results.append({
                    "name": attraction.name,
                    "confidence": scraped.confidence,
                    "dates": [str(d) for d in scraped.dates],
                    "time_ranges": [
                        [t[0].isoformat(), t[1].isoformat()]
                        for t in scraped.time_ranges
                    ],
                    "prices": scraped.prices,
                    "ticket_urls": scraped.ticket_urls,
                })
            except Exception as exc:
                results.append({
                    "name": attraction.name,
                    "confidence": "red",
                    "dates": [],
                    "time_ranges": [],
                    "prices": [],
                    "ticket_urls": [],
                    "error": str(exc),
                })

        return jsonify({"results": results})

    @app.route("/api/schedule", methods=["PUT"])
    def api_schedule():
        global _trip
        if _trip is None:
            return jsonify({"error": "No trip configured"}), 400

        data = request.get_json(force=True)
        name = data["name"]

        attraction = None  # type: Optional[Attraction]
        for a in _trip.attractions:
            if a.name == name:
                attraction = a
                break

        if attraction is None:
            return jsonify({"error": f"Attraction '{name}' not found"}), 404

        entries = []  # type: List[ScheduleEntry]
        for entry_data in data["schedule"]:
            entries.append(ScheduleEntry(
                date=date.fromisoformat(entry_data["date"]),
                open_time=time.fromisoformat(entry_data["open_time"]),
                close_time=time.fromisoformat(entry_data["close_time"]),
                price=entry_data.get("price"),
                ticket_url=entry_data.get("ticket_url"),
            ))

        attraction.schedule = entries
        return jsonify({"status": "ok"})

    @app.route("/api/optimize", methods=["POST"])
    def api_optimize():
        global _trip, _itinerary
        if _trip is None:
            _itinerary = ItineraryResult(scheduled={}, unscheduled=[])
            return jsonify(_serialize_itinerary(_itinerary))

        _itinerary = optimize(_trip)
        return jsonify(_serialize_itinerary(_itinerary))

    @app.route("/api/eligible-dates", methods=["GET"])
    def api_eligible_dates():
        global _trip
        if _trip is None:
            return jsonify({"dates": []})

        name = request.args.get("name", "")
        eligible = filter_eligible_dates(_trip)
        dates = eligible.get(name, [])
        return jsonify({"dates": [str(d) for d in dates]})

    @app.route("/api/adjust", methods=["POST"])
    def api_adjust():
        global _trip, _itinerary
        if _trip is None:
            return jsonify({"error": "No trip configured"}), 400

        data = request.get_json(force=True)
        locked = {data["name"]: date.fromisoformat(data["date"])}
        _itinerary = reoptimize(_trip, locked)
        return jsonify(_serialize_itinerary(_itinerary))

    @app.route("/api/discover", methods=["POST"])
    def api_discover():
        global _trip, _itinerary
        if _trip is None or _itinerary is None:
            return jsonify({"gaps": [], "suggestions": []})

        scheduled_dates = set(_itinerary.scheduled.keys())
        gaps = find_gap_nights(_trip, scheduled_dates)

        suggestions = find_densify_opportunities(_itinerary, _trip.attractions)
        return jsonify({
            "gaps": [str(d) for d in gaps],
            "suggestions": [
                {
                    "name": s.attraction.name,
                    "date": str(s.suggested_date) if s.suggested_date else None,
                    "distance": round(s.distance_miles, 1),
                    "type": s.suggestion_type,
                    "url": s.website_url,
                }
                for s in suggestions
            ],
        })

    @app.route("/api/export", methods=["GET"])
    def api_export():
        global _itinerary
        title = request.args.get("title", "Haunt Trip")
        if _itinerary is None:
            _itinerary = ItineraryResult(scheduled={}, unscheduled=[])
        html = generate_export_html(_itinerary, title)
        return html, 200, {"Content-Type": "text/html"}

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
