# hauntplanner.py
from __future__ import annotations

import json
from datetime import date, time
from typing import Optional, List, Dict

from flask import Flask, render_template, request, jsonify

from models import Trip, Location, Attraction, ScheduleEntry, Segment
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
                "drive_time_min": e.drive_time_min,
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

    @app.route("/locations")
    def locations_page():
        return render_template("locations.html")

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

        home_addr = data.get("home_base", "")
        try:
            home_coords = geocode_address(home_addr) if home_addr else (0.0, 0.0)
        except Exception:
            home_coords = (0.0, 0.0)
        home_base = Location(home_addr, home_coords[0], home_coords[1])

        segments = []  # type: List[Segment]
        for seg_data in data.get("segments", []):
            seg_dr = seg_data["date_range"]
            seg_start = date.fromisoformat(seg_dr["start"])
            seg_end = date.fromisoformat(seg_dr["end"])

            s_addr = seg_data.get("start_location", home_addr)
            e_addr = seg_data.get("end_location", home_addr)

            try:
                s_coords = geocode_address(s_addr) if s_addr else home_coords
            except Exception:
                s_coords = home_coords

            try:
                e_coords = geocode_address(e_addr) if e_addr else home_coords
            except Exception:
                e_coords = home_coords

            segments.append(Segment(
                date_range=(seg_start, seg_end),
                start_location=Location(s_addr, s_coords[0], s_coords[1]),
                end_location=Location(e_addr, e_coords[0], e_coords[1]),
            ))

        _trip = Trip(
            date_range=(start_date, end_date),
            home_base=home_base,
            blackout_dates=blackouts,
            segments=segments,
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
            _trip = Trip(
                date_range=(date(2026, 10, 1), date(2026, 10, 31)),
                home_base=Location("", 0.0, 0.0),
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

        existing_names = {a.name.lower() for a in _trip.attractions}

        scheduled_dates = set(_itinerary.scheduled.keys())
        gaps = find_gap_nights(_trip, scheduled_dates)

        all_suggestions = find_densify_opportunities(_itinerary, _trip.attractions)
        filtered = [s for s in all_suggestions if s.attraction.name.lower() not in existing_names]

        return jsonify({
            "gaps": [str(d) for d in gaps],
            "suggestions": [
                {
                    "name": s.attraction.name,
                    "address": s.attraction.address,
                    "date": str(s.suggested_date) if s.suggested_date else None,
                    "distance": round(s.distance_miles, 1),
                    "type": s.suggestion_type,
                    "url": s.website_url,
                }
                for s in filtered
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
