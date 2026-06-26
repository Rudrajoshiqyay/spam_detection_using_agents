"""
Behavioral Similarity Engine — no ML training required.

Compares a Historical User Profile Vector against the Current Transaction Vector
using cosine similarity and z-score deviation.

Higher score = more anomalous (0 = identical behavior, 100 = completely foreign).
"""

import math
from typing import Dict, Any

from app.models.transaction import Transaction
from app.models.user_profile import UserProfile


def _cosine_similarity(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(x ** 2 for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _normalize(value: float, min_val: float, max_val: float) -> float:
    if max_val == min_val:
        return 0.5
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


def build_profile_vector(profile: UserProfile, features: dict) -> list:
    """Historical user behavior encoded as a 7-dimensional vector."""
    avg_amt = profile.spending_profile.avg_transaction_amount
    max_amt = profile.spending_profile.max_transaction_amount or (avg_amt * 5)

    hour_diversity = len(profile.spending_profile.typical_transaction_hours) / 24.0
    geo_diversity = min(1.0, len(profile.travel_profile.frequent_countries) / 10.0)

    travel_map = {"rare": 0.05, "occasional": 0.30, "frequent": 0.65, "very_frequent": 0.95}
    # Safely handle both string values and TravelFrequency enum objects
    travel_freq = profile.travel_profile.travel_frequency
    travel_key = travel_freq.value if hasattr(travel_freq, "value") else str(travel_freq)
    travel_score = travel_map.get(travel_key, 0.05)

    device_count = min(1.0, len(profile.known_devices) / 5.0)

    merchant_diversity = float(features.get("merchant_diversity", 5)) / 50.0

    return [
        _normalize(avg_amt, 0, max_amt),           # typical spend
        hour_diversity,                             # time-of-day diversity
        geo_diversity,                              # geo diversity
        travel_score,                               # travel frequency
        device_count,                               # device diversity
        min(1.0, merchant_diversity),               # merchant diversity
        0.1 if not profile.fraud_history else 0.8, # fraud baseline
    ]


def build_transaction_vector(txn: Transaction, features: dict, profile: UserProfile) -> list:
    """Current transaction encoded in the same 7-dimensional space."""
    max_amt = profile.spending_profile.max_transaction_amount or (
        profile.spending_profile.avg_transaction_amount * 5
    )
    amount_norm = _normalize(txn.amount, 0, max_amt)

    txn_hour = txn.timestamp.hour
    typical_hours = profile.spending_profile.typical_transaction_hours
    hour_score = 1.0 if txn_hour in typical_hours else 0.0

    location_key = f"{txn.location_city}:{txn.location_country}"
    is_known_geo = location_key in profile.known_locations
    geo_norm = 0.8 if is_known_geo else 0.2

    is_international = txn.is_international
    travel_score = 0.8 if is_international else 0.1

    is_known_device = txn.device_id in profile.known_devices
    device_score = 0.9 if is_known_device else 0.1

    # merchant diversity proxy from features
    merchant_diversity = float(features.get("merchant_diversity", 5)) / 50.0

    # Fraud history proxy: reflects whether account has been flagged before.
    # Uses the profile vector's same dimension (index 6) for vector alignment.
    fraud_proxy = 0.8 if profile.fraud_history else 0.1

    return [
        amount_norm,
        hour_score,
        geo_norm,
        travel_score,
        device_score,
        min(1.0, merchant_diversity),
        fraud_proxy,
    ]


def calculate_behavior_similarity(
    txn: Transaction,
    profile: UserProfile,
    features: dict,
) -> Dict[str, Any]:
    profile_vec = build_profile_vector(profile, features)
    txn_vec = build_transaction_vector(txn, features, profile)

    cosine_sim = _cosine_similarity(profile_vec, txn_vec)
    # anomaly score: 0 = normal, 100 = completely anomalous
    anomaly_score = round((1.0 - max(0.0, cosine_sim)) * 100, 2)

    # Z-score deviation on amount
    avg_amt = float(features.get("avg_amount_30d", profile.spending_profile.avg_transaction_amount))
    std_amt = float(features.get("std_amount_30d", avg_amt * 0.5)) or 1.0
    z_score = abs(txn.amount - avg_amt) / std_amt

    # Euclidean distance
    distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(profile_vec, txn_vec)))

    # Final score — blend cosine anomaly + z-score contribution
    z_contribution = min(50.0, z_score * 8)
    final_score = min(100.0, anomaly_score * 0.6 + z_contribution * 0.4)

    return {
        "behavior_similarity_score": round(final_score, 2),
        "cosine_similarity": round(cosine_sim, 4),
        "z_score_amount": round(z_score, 2),
        "euclidean_distance": round(distance, 4),
        "profile_vector": profile_vec,
        "transaction_vector": txn_vec,
    }
