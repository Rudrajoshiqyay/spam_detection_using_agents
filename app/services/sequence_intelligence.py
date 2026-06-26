"""
Sequence Intelligence Engine — detects suspicious event chains via sliding window.

Latency target: < 15 ms (operates on Redis-cached event list).
"""

import time
from typing import List, Dict, Any

from app.models.transaction import Transaction
from app.models.user_profile import UserProfile


# Known suspicious sequences with detection rules.
# Note: merchant_abuse requires cross-account data not available per-transaction;
# it is detected at the graph layer instead and intentionally omitted here.
_SEQUENCES = {
    "account_takeover": {
        "description": "New device → password reset → contact change → large transfer",
        "required_events": ["new_device_login", "large_transfer"],
        "supporting_events": ["password_reset", "contact_change"],
        "window_hours": 24,
        "base_risk": 85,
    },
    "card_testing": {
        "description": "3+ micro-transactions followed by large purchase",
        "required_events": ["micro_transaction"],
        "min_micro_count": 3,
        "window_hours": 2,
        "base_risk": 75,
    },
    "refund_fraud": {
        "description": "Alternating purchase-refund pattern",
        "required_events": ["purchase", "refund"],
        "min_cycle_count": 2,
        "window_hours": 72,
        "base_risk": 65,
    },
    "velocity_burst": {
        "description": "Rapid succession of transactions within 1 hour",
        "min_txn_count": 5,
        "window_hours": 1,
        "base_risk": 60,
    },
}


def _classify_event(txn: Transaction, profile: UserProfile, features: dict) -> dict:
    """Classify the current transaction as an event type."""
    avg_amt = float(features.get("avg_amount_30d",
                                  profile.spending_profile.avg_transaction_amount))
    is_micro = txn.amount < 100
    is_large = txn.amount > avg_amt * 4
    is_new_device = txn.device_id not in profile.known_devices
    location_key = f"{txn.location_city}:{txn.location_country}"
    is_new_location = location_key not in profile.known_locations

    return {
        "type": txn.transaction_type,
        "amount": txn.amount,
        "is_micro": is_micro,
        "is_large": is_large,
        "is_new_device": is_new_device,
        "is_new_location": is_new_location,
        "merchant_id": txn.merchant_id,
        "device_id": txn.device_id,
        "timestamp": txn.timestamp.timestamp(),
        "event_labels": _assign_labels(txn, is_micro, is_large, is_new_device),
    }


def _assign_labels(txn: Transaction, is_micro: bool, is_large: bool, is_new_device: bool) -> list:
    labels = [txn.transaction_type]
    if is_micro:
        labels.append("micro_transaction")
    if is_large:
        labels.append("large_transfer")
    if is_new_device:
        labels.append("new_device_login")
    return labels


def _check_card_testing(events: List[dict], window_hours: int) -> float:
    now = time.time()
    cutoff = now - window_hours * 3600
    recent = [e for e in events if e.get("timestamp", 0) > cutoff]

    micro_count = sum(1 for e in recent if e.get("is_micro"))
    has_large = any(e.get("is_large") for e in recent)

    if micro_count >= 3 and has_large:
        return min(1.0, (micro_count - 2) / 3 * 0.8 + 0.2)
    return 0.0


def _check_refund_fraud(events: List[dict], window_hours: int) -> float:
    now = time.time()
    cutoff = now - window_hours * 3600
    recent = [e for e in events if e.get("timestamp", 0) > cutoff]

    types = [e.get("type", "") for e in recent]
    cycle_count = 0
    i = 0
    while i < len(types) - 1:
        if types[i] == "purchase" and types[i + 1] == "refund":
            cycle_count += 1
            i += 2
        else:
            i += 1

    if cycle_count >= 2:
        return min(1.0, cycle_count / 4)
    return 0.0


def _check_velocity_burst(events: List[dict]) -> float:
    """Count transactions in the last hour INCLUDING the current transaction."""
    now = time.time()
    one_hour_ago = now - 3600
    # events already includes the current transaction (appended by analyze_sequences)
    count = sum(1 for e in events if e.get("timestamp", 0) > one_hour_ago)
    if count >= 5:
        return min(1.0, (count - 4) / 6)
    return 0.0


def _check_account_takeover(events: List[dict]) -> float:
    """
    Score ATO likelihood based on number of distinct ATO signals present,
    rather than a flat 0.7 for any combination of new-device + large-transfer.
    """
    ato_signals_found = 0
    has_new_device = any("new_device_login" in e.get("event_labels", []) for e in events)
    has_large_transfer = any("large_transfer" in e.get("event_labels", []) for e in events)

    if has_new_device:
        ato_signals_found += 1
    if has_large_transfer:
        ato_signals_found += 1

    # Additional ATO indicators from event labels
    for e in events:
        labels = e.get("event_labels", [])
        if "password_reset" in labels:
            ato_signals_found += 1
        if "contact_change" in labels:
            ato_signals_found += 1
        if e.get("is_new_location"):
            ato_signals_found += 1

    if has_new_device and has_large_transfer:
        # Scale by signal count: 2 signals → 0.5, 3 → 0.75, 4+ → 1.0
        return min(1.0, ato_signals_found * 0.25)
    return 0.0


def analyze_sequences(
    txn: Transaction,
    profile: UserProfile,
    features: dict,
    recent_events: List[dict],
) -> Dict[str, Any]:
    current_event = _classify_event(txn, profile, features)

    # Include current transaction in all checks (was missing in velocity_burst)
    all_events = recent_events + [current_event]

    triggered_sequences = []
    max_risk = 0.0

    # Card testing
    ct_score = _check_card_testing(all_events, 2)
    if ct_score > 0:
        triggered_sequences.append({
            "sequence": "card_testing",
            "score": round(ct_score, 3),
            "risk": round(_SEQUENCES["card_testing"]["base_risk"] * ct_score, 1),
        })
        max_risk = max(max_risk, _SEQUENCES["card_testing"]["base_risk"] * ct_score)

    # Refund fraud
    rf_score = _check_refund_fraud(all_events, 72)
    if rf_score > 0:
        triggered_sequences.append({
            "sequence": "refund_fraud",
            "score": round(rf_score, 3),
            "risk": round(_SEQUENCES["refund_fraud"]["base_risk"] * rf_score, 1),
        })
        max_risk = max(max_risk, _SEQUENCES["refund_fraud"]["base_risk"] * rf_score)

    # Velocity burst
    vb_score = _check_velocity_burst(all_events)
    if vb_score > 0:
        triggered_sequences.append({
            "sequence": "velocity_burst",
            "score": round(vb_score, 3),
            "risk": round(_SEQUENCES["velocity_burst"]["base_risk"] * vb_score, 1),
        })
        max_risk = max(max_risk, _SEQUENCES["velocity_burst"]["base_risk"] * vb_score)

    # Account takeover — proportional to signal count
    ato_score = _check_account_takeover(all_events)
    if ato_score > 0:
        triggered_sequences.append({
            "sequence": "account_takeover",
            "score": round(ato_score, 3),
            "risk": round(_SEQUENCES["account_takeover"]["base_risk"] * ato_score, 1),
        })
        max_risk = max(max_risk, _SEQUENCES["account_takeover"]["base_risk"] * ato_score)

    return {
        "active_sequences": [s["sequence"] for s in triggered_sequences],
        "sequence_details": triggered_sequences,
        "sequence_risk_score": round(max_risk, 2),
        "current_event": current_event,
        "total_events_analyzed": len(all_events),
    }
