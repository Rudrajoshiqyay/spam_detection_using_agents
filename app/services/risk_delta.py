"""
Risk Delta Engine — measures deviation from each behavioral baseline.

All deltas normalized to 0–1 before weighting.
Final delta_score: 0 = no deviation, 100 = extreme deviation.
"""

import math
from typing import Dict, Any

from app.models.transaction import Transaction
from app.models.user_profile import UserProfile


def _safe_z(value: float, mean: float, std: float) -> float:
    if std < 1e-6:
        return 0.0
    return abs(value - mean) / std


def calculate_risk_deltas(
    txn: Transaction,
    profile: UserProfile,
    features: dict,
) -> Dict[str, Any]:
    avg_amt_30d = float(features.get("avg_amount_30d", profile.spending_profile.avg_transaction_amount))
    std_amt_30d = float(features.get("std_amount_30d", avg_amt_30d * 0.5)) or 1.0

    # --- Amount delta ---
    amount_z = _safe_z(txn.amount, avg_amt_30d, std_amt_30d)
    amount_delta = min(1.0, amount_z / 5.0)   # z=5 → delta=1.0

    # --- Time delta ---
    typical_hours = profile.spending_profile.typical_transaction_hours
    txn_hour = txn.timestamp.hour
    if typical_hours:
        min_dist = min(abs(txn_hour - h) for h in typical_hours)
        # wrap-around distance on 24-hour clock
        min_dist = min(min_dist, 24 - min_dist)
        time_delta = min(1.0, min_dist / 12.0)
    else:
        time_delta = 0.0

    # --- Location delta ---
    location_key = f"{txn.location_city}:{txn.location_country}"
    location_delta = 0.0 if location_key in profile.known_locations else 0.7
    if txn.is_international and txn.location_country not in profile.travel_profile.frequent_countries:
        location_delta = 1.0

    # --- Device delta ---
    device_delta = 0.0 if txn.device_id in profile.known_devices else 0.8

    # --- Merchant delta ---
    merchant_freqs: dict = features.get("merchant_frequencies", {})
    merchant_visits = int(merchant_freqs.get(txn.merchant_id, 0))
    merchant_delta = 0.0 if merchant_visits >= 3 else (1.0 if merchant_visits == 0 else 0.4)

    # --- Velocity delta ---
    txn_count_1h = int(features.get("txn_count_1h", 0))
    max_per_hour = profile.thresholds.max_txn_per_hour
    if max_per_hour > 0 and txn_count_1h > max_per_hour:
        velocity_delta = min(1.0, max(0.0, (txn_count_1h - max_per_hour) / max_per_hour))
    else:
        velocity_delta = 0.0

    # --- Weighted composite score ---
    weights = {
        "amount": 0.30,
        "location": 0.25,
        "device": 0.20,
        "velocity": 0.15,
        "merchant": 0.05,
        "time": 0.05,
    }
    deltas = {
        "amount": amount_delta,
        "time": time_delta,
        "location": location_delta,
        "device": device_delta,
        "merchant": merchant_delta,
        "velocity": velocity_delta,
    }
    composite = sum(weights[k] * deltas[k] for k in weights)
    delta_score = round(composite * 100, 2)

    return {
        "risk_delta_score": delta_score,
        "deltas": {k: round(v, 3) for k, v in deltas.items()},
        "amount_z_score": round(amount_z, 2),
        "human_summary": _summarize(deltas, amount_z, txn),
    }


def _summarize(deltas: dict, amount_z: float, txn: Transaction) -> str:
    parts = []
    if deltas["amount"] > 0.5:
        parts.append(f"amount {txn.amount:.0f} is {amount_z:.1f}x std above average")
    if deltas["location"] > 0.5:
        parts.append(f"unusual location ({txn.location_city}, {txn.location_country})")
    if deltas["device"] > 0.5:
        parts.append("unrecognized device")
    if deltas["velocity"] > 0.5:
        parts.append("transaction velocity spike")
    if deltas["merchant"] > 0.5:
        parts.append("first-time merchant")
    return "; ".join(parts) if parts else "behavior within normal range"
