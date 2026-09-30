"""
app/utils/geo.py
-----------------
Small pure geo helpers used by duplicate detection and the heatmap/hotspots.
"""
import math
from typing import Tuple

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bounding_box(lat: float, lng: float, radius_m: float) -> Tuple[float, float, float, float]:
    """(min_lat, max_lat, min_lng, max_lng) that fully contains the circle.
    Used as a cheap SQL pre-filter before the exact haversine check."""
    dlat = math.degrees(radius_m / EARTH_RADIUS_M)
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    dlng = math.degrees(radius_m / (EARTH_RADIUS_M * cos_lat))
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng
