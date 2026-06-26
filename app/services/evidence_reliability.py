"""
Evidence Reliability Framework — scores and weights each evidence item.

Strong  → Impossible Travel, Shared Fraud Device, Fraud Ring Membership
Medium  → Merchant Reputation, Behavior Deviation, Pattern Match
Weak    → Transaction Time, Merchant Novelty, Cohort Deviation
"""

from typing import List, Dict, Any

from app.models.evidence import InvestigationPackage, EvidenceItem, EvidenceStrength


_STRENGTH_BASE = {
    EvidenceStrength.strong: 0.90,
    EvidenceStrength.medium: 0.65,
    EvidenceStrength.weak: 0.35,
}

_TYPE_RELIABILITY = {
    "impossible_travel": 0.98,
    "fraud_ring": 0.93,
    "shared_device": 0.90,
    "kill_chain": 0.80,
    "fraud_pattern": 0.78,
    "sequence": 0.72,
    "merchant_reputation": 0.68,
    "behavior_deviation": 0.65,
    "transaction_time": 0.40,
    "merchant_novelty": 0.35,
}


def score_evidence_reliability(package: InvestigationPackage) -> Dict[str, Any]:
    scored_items = []
    total_fraud_weight = 0.0
    total_trust_weight = 0.0
    strong_fraud_count = 0
    weak_only = True

    for item in package.evidence_items:
        base = _STRENGTH_BASE.get(item.strength, 0.5)
        type_key = item.type.split(":")[0]
        type_rel = _TYPE_RELIABILITY.get(type_key, base)
        final_reliability = (base * 0.4 + type_rel * 0.6)

        scored = {
            "type": item.type,
            "strength": item.strength.value,
            "reliability_score": round(final_reliability, 3),
            "contributes_to_fraud": item.contributes_to_fraud,
            "description": item.description,
        }
        scored_items.append(scored)

        if item.contributes_to_fraud:
            total_fraud_weight += final_reliability
            if item.strength == EvidenceStrength.strong:
                strong_fraud_count += 1
                weak_only = False
            elif item.strength == EvidenceStrength.medium:
                weak_only = False
        else:
            total_trust_weight += final_reliability

    # Overall evidence strength verdict
    if strong_fraud_count >= 2:
        evidence_verdict = "overwhelming"
    elif strong_fraud_count == 1:
        evidence_verdict = "strong"
    elif not weak_only and total_fraud_weight > total_trust_weight:
        evidence_verdict = "moderate"
    elif total_fraud_weight > 0:
        evidence_verdict = "weak"
    else:
        evidence_verdict = "insufficient"

    net_fraud_confidence = min(1.0, max(0.0, total_fraud_weight - total_trust_weight * 0.5))

    return {
        "scored_evidence": scored_items,
        "evidence_verdict": evidence_verdict,
        "net_fraud_confidence": round(net_fraud_confidence, 3),
        "strong_fraud_count": strong_fraud_count,
        "total_fraud_weight": round(total_fraud_weight, 3),
        "total_trust_weight": round(total_trust_weight, 3),
    }
