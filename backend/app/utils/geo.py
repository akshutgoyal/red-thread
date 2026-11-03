from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any

EARTH_RADIUS_M = 6_371_000.0


def parse_coordinates(latitude: Any, longitude: Any) -> tuple[float, float] | None:
    """Parse documented coordinates without inventing a location."""
    try:
        lat = float(str(latitude).strip())
        lon = float(str(longitude).strip())
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    if lat == 0.0 and lon == 0.0:
        return None
    return round(lat, 7), round(lon, 7)


def format_gps_point(latitude: float, longitude: float) -> str:
    return f"{latitude:.6f},{longitude:.6f}"


def haversine_meters(
    first: tuple[float, float], second: tuple[float, float]
) -> float:
    lat1, lon1 = map(radians, first)
    lat2, lon2 = map(radians, second)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(min(1.0, sqrt(value)))
