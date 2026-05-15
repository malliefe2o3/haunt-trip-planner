import math
import re
import time as time_module
from geopy.geocoders import Nominatim

_geolocator = Nominatim(user_agent="haunt-trip-planner")
_geocode_cache: dict[str, tuple[float, float]] = {}


def _extract_fallbacks(address: str) -> list[str]:
    parts = [p.strip() for p in address.split(",")]
    fallbacks = []
    if len(parts) >= 3:
        fallbacks.append(", ".join(parts[-2:]))
    zip_match = re.search(r"\b\d{5}\b", address)
    if zip_match:
        fallbacks.append(zip_match.group())
    return fallbacks


def geocode_address(address: str) -> tuple[float, float]:
    if address in _geocode_cache:
        return _geocode_cache[address]

    attempts = [address] + _extract_fallbacks(address)
    for attempt in attempts:
        time_module.sleep(1)
        location = _geolocator.geocode(attempt)
        if location is not None:
            result = (location.latitude, location.longitude)
            _geocode_cache[address] = result
            return result

    raise ValueError(f"Could not geocode address: {address}")


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 3958.8  # Earth radius in miles
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def drive_time_minutes(distance_miles: float) -> float:
    if distance_miles <= 0:
        return 0.0
    mph = 40.0 if distance_miles <= 10 else 50.0
    return (distance_miles / mph) * 60


def find_nearby(
    center: tuple[float, float],
    points: list[tuple[str, float, float]],
    radius_miles: float,
) -> list[tuple[str, float, float, float]]:
    results = []
    for name, lat, lng in points:
        dist = haversine_miles(center[0], center[1], lat, lng)
        if dist <= radius_miles:
            results.append((name, lat, lng, dist))
    return results
