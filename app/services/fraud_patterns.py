"""
Fraud Pattern Library — structured template matching.

Runs before LLM investigation. Scores the current transaction + context
against each known fraud pattern using a weighted signal match.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from app.models.transaction import Transaction
from app.models.user_profile import UserProfile

_logger = logging.getLogger(__name__)

_PATTERNS: dict = {}


def load_patterns() -> None:
    global _PATTERNS
    path = Path(__file__).parent.parent / "data" / "fraud_patterns.json"
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data).__name__}")
        _PATTERNS = data
        _logger.info("FraudPatterns: loaded %d patterns from %s", len(_PATTERNS), path)
    except FileNotFoundError:
        _logger.error(
            "FraudPatterns: pattern file not found at %s — pattern matching disabled", path
        )
        _PATTERNS = {}
    except (json.JSONDecodeError, ValueError) as exc:
        _logger.error(
            "FraudPatterns: failed to parse %s — %s: %s — pattern matching disabled",
            path, type(exc).__name__, exc,
        )
        _PATTERNS = {}


def _build_signal_map(
    txn: Transaction,
    profile: UserProfile,
    features: dict,
    sequence_events: list,
) -> Dict[str, float]:
    """Convert raw signals into a normalized 0-1 map."""
    avg_amt = float(features.get("avg_amount_30d", profile.spending_profile.avg_transaction_amount))
    std_amt = float(features.get("std_amount_30d", avg_amt * 0.5)) or 1.0

    txn_count_1h = int(features.get("txn_count_1h", 0))
    txn_count_24h = int(features.get("txn_count_24h", 0))
    location_key = f"{txn.location_city}:{txn.location_country}"

    # Count recent micro-transactions (< 100)
    micro_txn_count = sum(1 for e in sequence_events if float(e.get("amount", 999)) < 100)

    # Refund ratio from recent events
    refund_count = sum(1 for e in sequence_events if e.get("type") == "refund")
    purchase_count = max(1, len(sequence_events) - refund_count)
    refund_ratio = refund_count / purchase_count

    return {
        "new_device": 1.0 if txn.device_id not in profile.known_devices else 0.0,
        "unusual_location": 1.0 if location_key not in profile.known_locations else 0.0,
        "high_amount": min(1.0, max(0.0, (txn.amount - avg_amt) / (std_amt * 3))),
        "velocity_spike": min(1.0, txn_count_1h / (profile.thresholds.max_txn_per_hour + 1)),
        "micro_transactions": min(1.0, micro_txn_count / 4),
        "rapid_succession": min(1.0, txn_count_1h / 5),
        "high_txn_count_1h": min(1.0, txn_count_1h / 10),
        "amount_escalation": 1.0 if txn.amount > avg_amt * 5 else 0.0,
        "multiple_merchants": min(1.0, float(features.get("merchant_diversity", 1)) / 10),
        "multiple_locations": min(1.0, float(features.get("geo_frequency", 1)) / 5),
        "refund_purchase_ratio": min(1.0, refund_ratio),
        "same_merchant_refund": 1.0 if refund_count > 0 else 0.0,
        "pattern_repetition": 1.0 if refund_ratio > 0.5 else 0.0,
        "merchant_concentration": 1.0 if float(features.get("merchant_diversity", 5)) < 2 else 0.0,
        "multiple_accounts": 0.0,   # enriched by graph service
        "shared_device_merchant": 0.0,
        "account_creation_recent": 1.0 if profile.account_age_days < 30 else 0.0,
        "incoming_transfers_only": 0.0,
        "rapid_outgoing_transfers": min(1.0, txn_count_1h / 3),
        "shared_devices": 0.0,      # enriched by graph service
        "shared_merchants": 0.0,
        "coordinated_timing": 0.0,
        "graph_centrality": 0.0,
        "multiple_accounts_same_device": 0.0,
        "international": 1.0 if txn.is_international else 0.0,
        "online_channel": 1.0 if txn.channel == "online" else 0.0,
        "moderate_amounts": 1.0 if 100 < txn.amount < 5000 else 0.0,
        "night_transaction": 1.0 if txn.timestamp.hour < 5 or txn.timestamp.hour > 22 else 0.0,
        "new_merchant": 1.0 if float(features.get("merchant_frequency", 0)) == 0 else 0.0,
    }


def match_patterns(
    txn: Transaction,
    profile: UserProfile,
    features: dict,
    sequence_events: list,
    graph_signals: Optional[dict] = None,
) -> Dict[str, Any]:
    if not _PATTERNS:
        load_patterns()

    signal_map = _build_signal_map(txn, profile, features, sequence_events)

    # Enrich with graph signals
    if graph_signals:
        signal_map["shared_devices"] = float(graph_signals.get("shared_device_flag", 0))
        signal_map["multiple_accounts_same_device"] = float(graph_signals.get("multi_account_device", 0))
        signal_map["graph_centrality"] = float(graph_signals.get("centrality_score", 0))

    best_pattern = None
    best_score = 0.0
    all_scores = {}

    for pattern_id, pattern in _PATTERNS.items():
        pattern_signals: dict = pattern["signals"]
        total_weight = sum(pattern_signals.values())
        weighted_match = sum(
            signal_map.get(sig, 0.0) * weight
            for sig, weight in pattern_signals.items()
        )
        score = weighted_match / total_weight if total_weight > 0 else 0.0
        all_scores[pattern_id] = round(score, 3)

        if score > best_score:
            best_score = score
            best_pattern = pattern_id

    min_threshold = _PATTERNS.get(best_pattern, {}).get("min_match_score", 0.6) if best_pattern else 0.6
    matched = best_score >= min_threshold

    return {
        "matched_pattern": best_pattern if matched else None,
        "similarity": round(best_score, 3),
        "all_pattern_scores": all_scores,
        "pattern_matched": matched,
        "pattern_severity": _PATTERNS.get(best_pattern, {}).get("severity", "unknown") if matched else None,
    }
