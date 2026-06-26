"""
Geo Velocity Engine — calculates travel feasibility between consecutive locations.

Uses the Haversine formula to compute great-circle distance.
"""

import math
from typing import Dict, Any, Optional
from datetime import datetime

# Speed thresholds in km/h
_SPEED_IMPOSSIBLE = 900       # faster than commercial aircraft
_SPEED_SUSPICIOUS = 250       # requires flight
_SPEED_DRIVING_LIMIT = 130    # high-speed road

# City approximate coordinates (lat, lon)
_CITY_COORDS: Dict[str, tuple] = {
    "Mumbai": (19.076, 72.878),
    "Delhi": (28.704, 77.102),
    "Bangalore": (12.972, 77.594),
    "Chennai": (13.083, 80.270),
    "Hyderabad": (17.387, 78.491),
    "Pune": (18.520, 73.856),
    "Kolkata": (22.573, 88.364),
    "London": (51.508, -0.128),
    "New York": (40.713, -74.006),
    "Dubai": (25.204, 55.270),
    "Singapore": (1.353, 103.820),
    "Bangkok": (13.757, 100.502),
    "Paris": (48.857, 2.347),
    "Tokyo": (35.690, 139.692),
    "Sydney": (-33.869, 151.209),
    "Guangzhou": (23.130, 113.260),
    "Hong Kong": (22.320, 114.169),
    "Toronto": (43.700, -79.420),
    "San Francisco": (37.775, -122.419),
    "Berlin": (52.520, 13.405),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_geo_velocity(
    current_lat: float,
    current_lon: float,
    current_city: str,
    current_ts: datetime,
    prev_lat: Optional[float],
    prev_lon: Optional[float],
    prev_city: Optional[str],
    prev_ts: Optional[datetime],
) -> Dict[str, Any]:
    if prev_lat is None or prev_lon is None or prev_ts is None:
        return {
            "geo_velocity_score": 0.0,
            "required_speed_kmh": 0.0,
            "distance_km": 0.0,
            "elapsed_minutes": 0.0,
            "is_impossible_travel": False,
            "is_suspicious_travel": False,
            "verdict": "no_prior_location",
        }

    distance_km = _haversine_km(prev_lat, prev_lon, current_lat, current_lon)
    elapsed_seconds = (current_ts - prev_ts).total_seconds()
    elapsed_minutes = elapsed_seconds / 60.0

    if elapsed_seconds <= 0:
        required_speed = float("inf")
    else:
        required_speed = distance_km / (elapsed_seconds / 3600.0)

    is_impossible = required_speed > _SPEED_IMPOSSIBLE and distance_km > 100
    is_suspicious = required_speed > _SPEED_SUSPICIOUS and distance_km > 50

    if is_impossible:
        score = 100.0
        verdict = f"impossible_travel: {prev_city} → {current_city} in {elapsed_minutes:.0f}min requires {required_speed:.0f}km/h"
    elif is_suspicious:
        score = min(90.0, 40 + (required_speed / _SPEED_IMPOSSIBLE) * 50)
        verdict = f"suspicious_travel: {required_speed:.0f}km/h required"
    elif distance_km > 500:
        score = 20.0
        verdict = "distant_location_but_feasible"
    else:
        score = 0.0
        verdict = "normal"

    return {
        "geo_velocity_score": round(score, 2),
        "required_speed_kmh": round(required_speed, 1) if required_speed != float("inf") else 99999,
        "distance_km": round(distance_km, 1),
        "elapsed_minutes": round(elapsed_minutes, 1),
        "from_city": prev_city,
        "to_city": current_city,
        "is_impossible_travel": is_impossible,
        "is_suspicious_travel": is_suspicious,
        "verdict": verdict,
    }
