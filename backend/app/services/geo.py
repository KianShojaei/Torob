"""Distance and travel-time helpers (master prompt §5.4).

No routing API is used: the master prompt allows a haversine + travel-time
fallback. Distances are straight-line; travel time applies a mode-specific
detour factor and speed, which is honest and works offline.
"""
from __future__ import annotations

import math

EARTH_R = 6371.0088  # km

MODES = {
    "walk": {"speed_kmh": 4.6, "detour": 1.25},
    "car": {"speed_kmh": 22.0, "detour": 1.35},
    "metro": {"speed_kmh": 26.0, "detour": 1.45},
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def travel_minutes(distance_km: float, mode: str = "car") -> int:
    cfg = MODES.get(mode, MODES["car"])
    if not math.isfinite(distance_km):
        return 0
    km = distance_km * cfg["detour"]
    minutes = km / cfg["speed_kmh"] * 60
    return max(3, int(round(minutes + 3)))  # +3 min for parking/entry


def best_mode(distance_km: float) -> str:
    if distance_km <= 1.2:
        return "walk"
    if distance_km <= 7:
        return "car"
    return "car"


def describe_distance(distance_km: float, minutes: int, mode: str) -> str:
    if not math.isfinite(distance_km):
        return "فاصله نامشخص"
    if distance_km < 1:
        return f"{int(round(distance_km * 1000 / 50) * 50)} متر · {minutes} دقیقه پیاده"
    label = {"walk": "پیاده", "car": "با ماشین", "metro": "با مترو"}.get(mode, "با ماشین")
    return f"{distance_km:.1f} کیلومتر · {minutes} دقیقه {label}"


def bbox(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon
