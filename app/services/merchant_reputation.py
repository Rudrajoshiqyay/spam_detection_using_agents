"""
Merchant Reputation Engine — dynamic merchant trust/risk score.
"""

import logging
from typing import Dict, Any

from app.services.feature_store import feature_store

_logger = logging.getLogger(__name__)

# Safe defaults returned when the feature store is unreachable
_SAFE_MERCHANT_DEFAULTS: dict = {
    "reputation_score": 0.5,
    "chargeback_rate": 0.02,
    "refund_rate": 0.05,
    "fraud_associations": 0,
    "transaction_volume": 0,
    "customer_diversity": 0,
}


async def get_merchant_reputation(merchant_id: str, merchant_category: str) -> Dict[str, Any]:
    try:
        rep = await feature_store.get_merchant_reputation(merchant_id)
    except Exception as exc:
        _logger.warning(
            "MerchantReputation: feature_store unavailable for merchant=%r — "
            "using safe defaults. %s: %s",
            merchant_id, type(exc).__name__, exc,
        )
        rep = dict(_SAFE_MERCHANT_DEFAULTS)

    chargeback_rate = float(rep.get("chargeback_rate", 0.02))
    refund_rate = float(rep.get("refund_rate", 0.05))
    fraud_assoc = float(rep.get("fraud_associations", 0))
    txn_volume = float(rep.get("transaction_volume", 100))
    customer_diversity = float(rep.get("customer_diversity", 10))
    historical_score = float(rep.get("reputation_score", 0.7))

    # High-risk categories have base penalty
    high_risk_cats = {"gambling", "crypto", "wire_transfer", "cash_advance", "adult", "pawnshop"}
    cat_penalty = 0.2 if merchant_category.lower() in high_risk_cats else 0.0

    # Chargeback threshold: > 1% is concerning, > 3% is high risk
    cb_penalty = min(0.5, chargeback_rate * 10)
    refund_penalty = min(0.3, refund_rate * 3)
    fraud_penalty = min(0.4, fraud_assoc * 0.1)

    # Volume and diversity boost trust
    volume_boost = min(0.2, txn_volume / 10000)
    diversity_boost = min(0.1, customer_diversity / 100)

    reputation_score = max(0.0, min(1.0,
        historical_score
        - cat_penalty
        - cb_penalty
        - refund_penalty
        - fraud_penalty
        + volume_boost
        + diversity_boost
    ))
    risk_score = round((1.0 - reputation_score) * 100, 2)

    return {
        "merchant_id": merchant_id,
        "merchant_reputation_score": round(reputation_score, 3),
        "merchant_risk_score": risk_score,
        "chargeback_rate": chargeback_rate,
        "refund_rate": refund_rate,
        "fraud_associations": int(fraud_assoc),
        "is_high_risk_category": bool(cat_penalty),
        "signals": _build_signals(chargeback_rate, fraud_assoc, cat_penalty, reputation_score),
    }


def _build_signals(cb: float, fraud_assoc: float, cat_penalty: float, score: float) -> list:
    signals = []
    if cb > 0.03:
        signals.append(f"high_chargeback_rate_{cb:.1%}")
    if fraud_assoc > 0:
        signals.append(f"merchant_has_{int(fraud_assoc)}_fraud_association(s)")
    if cat_penalty > 0:
        signals.append("high_risk_merchant_category")
    if score > 0.8:
        signals.append("trusted_merchant")
    return signals
