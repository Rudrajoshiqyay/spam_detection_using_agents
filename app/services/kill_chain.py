"""
Fraud Kill Chain Library — maps current events to known attack progression paths.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

_logger = logging.getLogger(__name__)

_KILL_CHAINS: dict = {}


def load_kill_chains() -> None:
    global _KILL_CHAINS
    path = Path(__file__).parent.parent / "data" / "kill_chains.json"
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data).__name__}")
        _KILL_CHAINS = data
        _logger.info("KillChain: loaded %d chains from %s", len(_KILL_CHAINS), path)
    except FileNotFoundError:
        _logger.error(
            "KillChain: kill_chains.json not found at %s — kill chain matching disabled", path
        )
        _KILL_CHAINS = {}
    except (json.JSONDecodeError, ValueError) as exc:
        _logger.error(
            "KillChain: failed to parse %s — %s: %s — kill chain matching disabled",
            path, type(exc).__name__, exc,
        )
        _KILL_CHAINS = {}


def _score_stage_match(stage: dict, active_signals: List[str]) -> float:
    stage_signals = stage.get("signals", [])
    if not stage_signals:
        return 0.0
    matched = sum(1 for s in stage_signals if s in active_signals)
    return matched / len(stage_signals)


def _detect_kill_chain_stage(
    chain: dict, active_signals: List[str]
) -> tuple[Optional[str], float, int]:
    """Returns (stage_name, confidence, stage_index)."""
    stages = chain.get("stages", [])
    best_stage = None
    best_score = 0.0
    best_idx = -1

    for stage in stages:
        score = _score_stage_match(stage, active_signals)
        if score > best_score:
            best_score = score
            best_stage = stage["stage"]
            best_idx = stage["index"]

    return best_stage, best_score, best_idx


def _build_active_signals(txn, profile, features: dict, sequence_result: dict) -> List[str]:
    """Translate transaction context into signal strings matching kill chain schemas."""
    signals = []

    if txn.device_id not in profile.known_devices:
        signals.append("new_device_login")
        signals.append("new_ip_login")

    if profile.account_age_days < 30:
        signals.append("account_age_very_new")

    avg_amt = float(features.get("avg_amount_30d", profile.spending_profile.avg_transaction_amount))
    if txn.amount > avg_amt * 5:
        signals.append("large_transfer")
        signals.append("high_amount")

    txn_count_1h = int(features.get("txn_count_1h", 0))
    if txn_count_1h > 3:
        signals.append("rapid_internal_transfers")
        signals.append("outgoing_transfer_burst")

    if txn.is_international:
        signals.append("international")

    if txn.transaction_type == "refund":
        signals.append("refund_pattern")

    # From sequence intelligence
    for seq in sequence_result.get("active_sequences", []):
        if seq == "account_takeover":
            signals.extend(["new_device_added", "contact_info_changed"])
        if seq == "velocity_burst":
            signals.extend(["rapid_dispersal", "fund_collection_central_account"])

    return signals


def match_kill_chains(
    txn,
    profile,
    features: dict,
    sequence_result: dict,
    graph_signals: Optional[dict] = None,
) -> Dict[str, Any]:
    if not _KILL_CHAINS:
        load_kill_chains()

    active_signals = _build_active_signals(txn, profile, features, sequence_result)

    if graph_signals:
        if graph_signals.get("shared_device_flag"):
            active_signals.extend(["shared_device_across_accounts", "multiple_accounts_same_device"])
        if graph_signals.get("fraud_ring_detected"):
            active_signals.extend(["coordinated_transaction_timing", "same_merchant_concentration"])

    best_chain = None
    best_stage = None
    best_similarity = 0.0
    best_stage_idx = -1
    chain_results = {}

    for chain_id, chain in _KILL_CHAINS.items():
        stage, score, idx = _detect_kill_chain_stage(chain, active_signals)
        chain_results[chain_id] = {"stage": stage, "similarity": round(score, 3), "stage_index": idx}
        if score > best_similarity:
            best_similarity = score
            best_chain = chain_id
            best_stage = stage
            best_stage_idx = idx

    # Risk amplification based on progression stage (later = more dangerous)
    stage_risk_multiplier = 1.0 + (best_stage_idx * 0.2) if best_stage_idx >= 0 else 1.0
    kill_chain_risk = min(100.0, best_similarity * 100 * stage_risk_multiplier)

    return {
        "matched_kill_chain": best_chain if best_similarity > 0.3 else None,
        "kill_chain_stage": best_stage,
        "kill_chain_similarity": round(best_similarity, 3),
        "kill_chain_risk_score": round(kill_chain_risk, 2),
        "stage_index": best_stage_idx,
        "all_chain_results": chain_results,
        "active_signals": active_signals,
    }
