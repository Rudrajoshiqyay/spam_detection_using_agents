"""
Geo Generator — produces location data with travel pattern support.

Supports:
  normal       — transaction from home city or nearby
  international — transaction from frequent travel destination
  impossible   — transaction that requires physically impossible speed
  cross_border — legitimate cross-border activity
"""

import math
import random
from typing import Dict, Any, Literal
from datetime import datetime, timedelta, timezone


GeoMode = Literal["normal", "international", "impossible", "cross_border"]

_CITY_DB = {
    "Mumbai":       {"country": "India",     "lat": 19.076,  "lon": 72.878},
    "Delhi":        {"country": "India",     "lat": 28.704,  "lon": 77.102},
    "Bangalore":    {"country": "India",     "lat": 12.972,  "lon": 77.594},
    "Pune":         {"country": "India",     "lat": 18.520,  "lon": 73.856},
    "Chennai":      {"country": "India",     "lat": 13.083,  "lon": 80.270},
    "Hyderabad":    {"country": "India",     "lat": 17.387,  "lon": 78.491},
    "London":       {"country": "UK",        "lat": 51.508,  "lon": -0.128},
    "Dubai":        {"country": "UAE",       "lat": 25.204,  "lon": 55.270},
    "Singapore":    {"country": "Singapore", "lat": 1.353,   "lon": 103.820},
    "New York":     {"country": "USA",       "lat": 40.713,  "lon": -74.006},
    "Bangkok":      {"country": "Thailand",  "lat": 13.757,  "lon": 100.502},
    "Kuala Lumpur": {"country": "Malaysia",  "lat": 3.140,   "lon": 101.686},
    "Paris":        {"country": "France",    "lat": 48.857,  "lon": 2.347},
    "Sydney":       {"country": "Australia", "lat": -33.869, "lon": 151.209},
}

_DOMESTIC_CITIES = ["Mumbai", "Delhi", "Bangalore", "Pune", "Chennai", "Hyderabad"]
_INTL_CITIES = ["London", "Dubai", "Singapore", "New York", "Bangkok", "Kuala Lumpur"]


def generate_location(
    home_city: str = "Mumbai",
    mode: GeoMode = "normal",
    prev_city: str = None,
    prev_timestamp: datetime = None,
) -> Dict[str, Any]:
    if mode == "normal":
        # 80% home city, 20% nearby domestic
        city = home_city if random.random() < 0.80 else random.choice(_DOMESTIC_CITIES)
    elif mode == "international":
        city = random.choice(_INTL_CITIES)
    elif mode == "impossible":
        # Far from previous location with very short elapsed time
        city = random.choice(_INTL_CITIES)
        if prev_city and prev_city == city:
            city = [c for c in _INTL_CITIES if c != prev_city][0]
    else:  # cross_border
        city = random.choice(_INTL_CITIES)

    info = _CITY_DB.get(city, _CITY_DB["Mumbai"])

    result = {
        "city": city,
        "country": info["country"],
        "lat": info["lat"] + random.uniform(-0.05, 0.05),
        "lon": info["lon"] + random.uniform(-0.05, 0.05),
        "is_international": info["country"] != "India",
    }

    # Velocity metadata for impossible travel
    if mode == "impossible" and prev_city and prev_timestamp:
        prev_info = _CITY_DB.get(prev_city, _CITY_DB["Mumbai"])
        dist = _haversine(prev_info["lat"], prev_info["lon"], info["lat"], info["lon"])
        # Set elapsed to make it impossible (5-15 minutes for intercontinental)
        elapsed_min = random.randint(5, 15)
        result["prev_city"] = prev_city
        result["prev_timestamp"] = prev_timestamp.isoformat()
        result["distance_km"] = round(dist, 1)
        result["elapsed_minutes"] = elapsed_min
        result["required_speed_kmh"] = round(dist / (elapsed_min / 60), 1)
        result["is_impossible_travel"] = True

    return result


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
