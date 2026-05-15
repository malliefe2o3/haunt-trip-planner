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
    # Use str(d.day) instead of %-d for macOS Python 3.9 compatibility
    return d.strftime(f"%A, %B {d.day}, %Y")


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
