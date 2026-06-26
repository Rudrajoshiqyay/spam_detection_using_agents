"""
Fast Screening Layer — Stage 1 of the two-stage detection pipeline.

Target latency: < 20 ms (all operations are in-memory or Redis hits).
Transactions below threshold bypass LangGraph entirely.
"""

import logging
import time
from typing import Dict, Any

from app.models.transaction import Transaction
from app.models.user_profile import UserProfile
from app.services.behavioral_similarity import calculate_behavior_similarity
from app.config import settings

_logger = logging.getLogger(__name__)

# Baseline new-device risk weight used to normalise device_novelty score.
# Represents the default value of AdaptiveThresholds.new_device_risk_weight.
# If the profile threshold equals this baseline the score is 25 (full novelty
# risk); lower thresholds scale down proportionally, higher thresholds scale up.
_DEVICE_NOVELTY_BASELINE: float = 0.3


def screen(
    txn: Transaction,
    profile: UserProfile,
    features: dict,
    device_rep: dict,
    merchant_rep: dict,
    txn_count_1h: int,
    txn_count_24h: int,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    scores: Dict[str, float] = {}
    flags: list = []

    avg_amt = float(features.get("avg_amount_30d", profile.spending_profile.avg_transaction_amount))
    std_amt = float(features.get("std_amount_30d", avg_amt * 0.5)) or 1.0
    max_amt = profile.spending_profile.max_transaction_amount or avg_amt * 10

    # 1. Velocity checks
    if txn_count_1h > profile.thresholds.max_txn_per_hour:
        ratio = txn_count_1h / profile.thresholds.max_txn_per_hour
        scores["velocity_1h"] = min(40.0, ratio * 20)
        flags.append(f"velocity_spike:{txn_count_1h}_txns_in_1h")
    else:
        scores["velocity_1h"] = 0.0

    # 2. Amount anomaly
    z = (txn.amount - avg_amt) / std_amt
    if z > 2:
        scores["amount_anomaly"] = min(35.0, z * 8)
        flags.append(f"amount_anomaly:z={z:.1f}")
    elif txn.amount > max_amt:
        scores["amount_anomaly"] = 40.0
        flags.append("amount_exceeds_profile_max")
    else:
        scores["amount_anomaly"] = 0.0

    # 3. Device novelty
    if txn.device_id not in profile.known_devices:
        # Scale device novelty score proportionally to the profile's risk weight.
        # A weight equal to the baseline (0.3) produces the standard score of 25.
        scores["device_novelty"] = min(50.0, 25.0 * profile.thresholds.new_device_risk_weight / _DEVICE_NOVELTY_BASELINE)
        flags.append("new_device")
    else:
        scores["device_novelty"] = 0.0

    # 4. Merchant risk
    merchant_risk = (1.0 - float(merchant_rep.get("merchant_reputation_score", 0.7))) * 20
    scores["merchant_risk"] = round(merchant_risk, 2)
    if merchant_risk > 10:
        flags.append(f"merchant_risk:{merchant_risk:.0f}")

    # 5. Location check
    location_key = f"{txn.location_city}:{txn.location_country}"
    if location_key not in profile.known_locations:
        scores["location"] = 20.0
        flags.append("new_location")
        if txn.is_international and txn.location_country not in profile.travel_profile.frequent_countries:
            scores["location"] = 30.0
            flags.append("unexpected_international")
    else:
        scores["location"] = 0.0

    # 6. Rule matching
    rule_score = 0.0
    if txn.amount < 50 and txn.channel == "online":
        rule_score += 15.0   # possible card testing
        flags.append("micro_online_transaction")
    if txn.timestamp.hour < 4:
        rule_score += 8.0
        flags.append("late_night_transaction")
    if txn.transaction_type == "refund" and txn.amount > avg_amt * 2:
        rule_score += 20.0
        flags.append("large_refund")
    scores["rule_match"] = min(30.0, rule_score)

    # 7. Behavioral similarity
    sim_result = calculate_behavior_similarity(txn, profile, features)
    behavior_score = sim_result["behavior_similarity_score"] * 0.25
    scores["behavior_similarity"] = round(behavior_score, 2)

    # Composite pre-risk score (weighted)
    weights = {
        "velocity_1h": 0.20,
        "amount_anomaly": 0.25,
        "device_novelty": 0.20,
        "merchant_risk": 0.10,
        "location": 0.15,
        "rule_match": 0.05,
        "behavior_similarity": 0.05,
    }
    raw_score = sum(scores.get(k, 0) * w * (100 / max(v, 1)) for k, (v, w) in {
        "velocity_1h": (40, weights["velocity_1h"]),
        "amount_anomaly": (35, weights["amount_anomaly"]),
        "device_novelty": (30, weights["device_novelty"]),
        "merchant_risk": (20, weights["merchant_risk"]),
        "location": (30, weights["location"]),
        "rule_match": (30, weights["rule_match"]),
        "behavior_similarity": (25, weights["behavior_similarity"]),
    }.items())
    pre_risk_score = round(min(100.0, raw_score), 2)

    # Feedback loop closure: analyst-confirmed fraud history elevates future risk scores.
    # risk_elevation is written by reputation_updater.update_user_risk_score() and
    # persists in the feature store between transactions.
    risk_elevation = float(features.get("risk_elevation", 0.0))
    if risk_elevation > 0:
        elevation_boost = round(min(25.0, risk_elevation * 0.25), 2)
        pre_risk_score = round(min(100.0, pre_risk_score + elevation_boost), 2)
        scores["feedback_elevation"] = elevation_boost
        flags.append(f"feedback_risk_elevation:{elevation_boost:.1f}")
    else:
        scores["feedback_elevation"] = 0.0

    elapsed_ms = (time.perf_counter() - t0) * 1000
    should_investigate = pre_risk_score >= settings.fast_screening_threshold

    return {
        "pre_risk_score": pre_risk_score,
        "should_investigate": should_investigate,
        "component_scores": scores,
        "flags": flags,
        "behavior_detail": sim_result,
        "screening_latency_ms": round(elapsed_ms, 2),
        "routing_decision": "DEEP_INVESTIGATION" if should_investigate else "AUTO_APPROVE",
    }
