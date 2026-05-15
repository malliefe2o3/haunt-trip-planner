import math
from geocoder import geocode_address, haversine_miles, drive_time_minutes, find_nearby


def test_haversine_known_distance():
    # Chicago to Springfield IL is ~179 miles straight-line (haversine)
    dist = haversine_miles(41.8781, -87.6298, 39.7817, -89.6501)
    assert 175 < dist < 185


def test_haversine_same_point():
    dist = haversine_miles(41.8781, -87.6298, 41.8781, -87.6298)
    assert dist == 0.0


def test_haversine_short_distance():
    # Two points ~10 miles apart (approx)
    dist = haversine_miles(41.8781, -87.6298, 41.8781, -87.4800)
    assert 5 < dist < 15


def test_drive_time_short_distance():
    # 8 miles at 40 mph = 12 minutes
    minutes = drive_time_minutes(8.0)
    assert minutes == 12.0


def test_drive_time_medium_distance():
    # 15 miles at 50 mph = 18 minutes
    minutes = drive_time_minutes(15.0)
    assert minutes == 18.0


def test_drive_time_zero():
    minutes = drive_time_minutes(0.0)
    assert minutes == 0.0


def test_find_nearby_within_radius():
    center = (41.8781, -87.6298)
    points = [
        ("A", 41.88, -87.63),   # very close
        ("B", 41.90, -87.65),   # close
        ("C", 39.78, -89.65),   # far away (~185 miles)
    ]
    nearby = find_nearby(center, points, radius_miles=20.0)
    names = [n[0] for n in nearby]
    assert "A" in names
    assert "B" in names
    assert "C" not in names


def test_find_nearby_empty():
    center = (41.8781, -87.6298)
    nearby = find_nearby(center, [], radius_miles=20.0)
    assert nearby == []
