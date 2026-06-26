"""
Evidence Builder Service — aggregates, compresses, and packages all signals
into a single investigation package for LLM agents.

Agents NEVER query databases directly — they only receive this package.
This reduces latency (one I/O pass) and token usage (compressed context).
"""

import re
from typing import Dict, Any

from app.models.transaction import Transaction
from app.models.user_profile import UserProfile
from app.models.evidence import InvestigationPackage, EvidenceItem, EvidenceStrength

# Regex-based prompt injection guard (same pattern as app/agents/_agent_base.py)
_INJECTION_RE = re.compile(
    r"ignore\s+(?:previous|above|all)\s+(?:instructions?|prompts?|context|rules?|system)",
    re.IGNORECASE,
)


def _safe_str(value: Any, maxlen: int = 120) -> str:
    """Truncate and redact potential prompt-injection content from free-text fields."""
    s = str(value)[:maxlen]
    s = _INJECTION_RE.sub("[REDACTED]", s)
    return s


def _fmt_signals(signals: list) -> str:
    """Render a signal list as a clean comma-separated string, not Python repr."""
    return ", ".join(str(s) for s in signals) if signals else "none"


def build_investigation_package(
    txn: Transaction,
    profile: UserProfile,
    screening_result: dict,
    features: dict,
    pattern_result: dict,
    sequence_result: dict,
    kill_chain_result: dict,
    cohort_result: dict,
    delta_result: dict,
    device_result: dict,
    merchant_result: dict,
    geo_result: dict,
    signal_result: dict,
    graph_result: dict,
) -> InvestigationPackage:
    evidence_items: list[EvidenceItem] = []

    # --- Strong evidence ---
    if geo_result.get("is_impossible_travel"):
        evidence_items.append(EvidenceItem(
            type="impossible_travel",
            description=geo_result.get("verdict", "Impossible travel detected"),
            value=geo_result.get("required_speed_kmh"),
            strength=EvidenceStrength.strong,
            reliability_score=0.98,
            contributes_to_fraud=True,
        ))

    if graph_result.get("fraud_ring_detected"):
        evidence_items.append(EvidenceItem(
            type="fraud_ring",
            description="Account connected to fraud ring via shared device",
            value=graph_result.get("graph_signals"),
            strength=EvidenceStrength.strong,
            reliability_score=0.92,
            contributes_to_fraud=True,
        ))

    if graph_result.get("shared_device_flag"):
        evidence_items.append(EvidenceItem(
            type="shared_device",
            description="Device used by multiple accounts",
            value=graph_result.get("graph_signals"),
            strength=EvidenceStrength.strong,
            reliability_score=0.90,
            contributes_to_fraud=True,
        ))

    # --- Medium evidence ---
    if pattern_result.get("pattern_matched"):
        evidence_items.append(EvidenceItem(
            type="fraud_pattern",
            description=f"Matched fraud pattern: {pattern_result['matched_pattern']}",
            value={"pattern": pattern_result["matched_pattern"], "similarity": pattern_result["similarity"]},
            strength=EvidenceStrength.medium,
            reliability_score=0.78,
            contributes_to_fraud=True,
        ))

    if kill_chain_result.get("matched_kill_chain"):
        evidence_items.append(EvidenceItem(
            type="kill_chain",
            description=f"Kill chain: {kill_chain_result['matched_kill_chain']} at stage {kill_chain_result['kill_chain_stage']}",
            value=kill_chain_result,
            strength=EvidenceStrength.medium,
            reliability_score=0.75,
            contributes_to_fraud=True,
        ))

    if sequence_result.get("sequence_risk_score", 0) > 30:
        evidence_items.append(EvidenceItem(
            type="sequence",
            description=f"Suspicious sequences: {', '.join(sequence_result.get('active_sequences', []))}",
            value=sequence_result.get("active_sequences"),
            strength=EvidenceStrength.medium,
            reliability_score=0.72,
            contributes_to_fraud=True,
        ))

    if merchant_result.get("merchant_risk_score", 0) > 40:
        evidence_items.append(EvidenceItem(
            type="merchant_reputation",
            description=f"High-risk merchant: score {merchant_result['merchant_risk_score']:.0f}/100",
            value=merchant_result.get("merchant_risk_score"),
            strength=EvidenceStrength.medium,
            reliability_score=0.70,
            contributes_to_fraud=True,
        ))

    if delta_result.get("risk_delta_score", 0) > 50:
        evidence_items.append(EvidenceItem(
            type="behavior_deviation",
            description=delta_result.get("human_summary", "Significant behavior deviation"),
            value=delta_result.get("deltas"),
            strength=EvidenceStrength.medium,
            reliability_score=0.68,
            contributes_to_fraud=True,
        ))

    # --- Weak evidence ---
    if txn.timestamp.hour < 4:
        evidence_items.append(EvidenceItem(
            type="transaction_time",
            description=f"Late-night transaction at {txn.timestamp.hour:02d}:00",
            value=txn.timestamp.hour,
            strength=EvidenceStrength.weak,
            reliability_score=0.40,
            contributes_to_fraud=True,
        ))

    if features.get("merchant_frequency", 1) == 0:
        evidence_items.append(EvidenceItem(
            type="merchant_novelty",
            description="First transaction at this merchant",
            value=txn.merchant_name,
            strength=EvidenceStrength.weak,
            reliability_score=0.35,
            contributes_to_fraud=True,
        ))

    # --- Negative (trust) evidence ---
    for sig in signal_result.get("negative_signals", []):
        evidence_items.append(EvidenceItem(
            type=f"trust_signal:{sig}",
            description=f"Trust signal: {sig.replace('_', ' ')}",
            value=sig,
            strength=EvidenceStrength.weak,
            reliability_score=0.60,
            contributes_to_fraud=False,
        ))

    # --- Build compressed evidence summary (token-efficient for LLM) ---
    # All free-text fields from external data are sanitized to prevent prompt injection.
    summary_lines = [
        f"TXN: {txn.amount} {txn.currency} at {_safe_str(txn.merchant_name, 60)} ({_safe_str(txn.merchant_category, 40)})",
        f"USER: {profile.user_type.value}, risk={profile.risk_category.value}, acct_age={profile.account_age_days}d",
        f"DEVICE: known={txn.device_id in profile.known_devices}, trust={device_result.get('device_trust_score', 0.5):.2f}",
        f"LOCATION: {_safe_str(txn.location_city, 40)}/{_safe_str(txn.location_country, 20)}, known={f'{txn.location_city}:{txn.location_country}' in profile.known_locations}",
        f"SCREENING: pre_risk={screening_result.get('pre_risk_score', 0):.1f}, flags={_fmt_signals(screening_result.get('flags', []))}",
        f"PATTERN: {pattern_result.get('matched_pattern') or 'none'} (sim={pattern_result.get('similarity', 0):.2f})",
        f"KILL_CHAIN: {kill_chain_result.get('matched_kill_chain') or 'none'} stage={kill_chain_result.get('kill_chain_stage') or 'n/a'}",
        f"SEQUENCES: {_fmt_signals(sequence_result.get('active_sequences') or [])}",
        f"COHORT: {cohort_result.get('cohort')}, deviation={cohort_result.get('cohort_deviation_score', 0):.1f}, p{cohort_result.get('cohort_percentile', 50):.0f}",
        f"DELTAS: {_safe_str(delta_result.get('human_summary', 'normal'), 120)}",
        f"GEO: {_safe_str(geo_result.get('verdict', 'ok'), 80)}, impossible={geo_result.get('is_impossible_travel', False)}",
        f"GRAPH: risk={graph_result.get('graph_risk_score', 0):.1f}, signals={_fmt_signals(graph_result.get('graph_signals') or [])}",
        f"SIGNALS: pos=[{_fmt_signals(signal_result.get('positive_signals', []))}] neg=[{_fmt_signals(signal_result.get('negative_signals', []))}]",
    ]

    return InvestigationPackage(
        transaction_id=txn.transaction_id,
        user_id=txn.user_id,
        pre_risk_score=screening_result.get("pre_risk_score", 0),
        features=features,
        matched_pattern=pattern_result.get("matched_pattern"),
        pattern_similarity=pattern_result.get("similarity", 0.0),
        matched_kill_chain=kill_chain_result.get("matched_kill_chain"),
        kill_chain_stage=kill_chain_result.get("kill_chain_stage"),
        kill_chain_similarity=kill_chain_result.get("kill_chain_similarity", 0.0),
        active_sequences=sequence_result.get("active_sequences", []),
        sequence_risk_score=sequence_result.get("sequence_risk_score", 0.0),
        cohort=cohort_result.get("cohort"),
        cohort_deviation_score=cohort_result.get("cohort_deviation_score", 0.0),
        cohort_percentile=cohort_result.get("cohort_percentile", 50.0),
        risk_deltas=delta_result.get("deltas", {}),
        device_trust_score=device_result.get("device_trust_score", 0.5),
        merchant_reputation_score=merchant_result.get("merchant_reputation_score", 0.5),
        geo_velocity_score=geo_result.get("geo_velocity_score", 0.0),
        graph_risk_score=graph_result.get("graph_risk_score", 0.0),
        graph_signals=graph_result.get("graph_signals", []),
        behavior_similarity_score=screening_result.get("behavior_detail", {}).get("behavior_similarity_score", 0.0),
        evidence_items=evidence_items,
        evidence_summary="\n".join(summary_lines),
        positive_signals=signal_result.get("positive_signals", []),
        negative_signals=signal_result.get("negative_signals", []),
    )
