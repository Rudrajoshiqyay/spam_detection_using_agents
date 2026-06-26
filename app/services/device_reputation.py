"""
Device Reputation Engine — dynamic trust score with decay logic.

Trust score: 1.0 = fully trusted, 0.0 = high-risk device.
"""

import logging
import time
from typing import Dict, Any

from app.services.feature_store import feature_store

_logger = logging.getLogger(__name__)

# Safe defaults returned when the feature store is unreachable
_SAFE_DEVICE_DEFAULTS: dict = {
    "trust_score": 0.5,
    "fraud_count": 0,
    "account_count": 1,
    "age_days": 0,
    "last_seen_ts": 0,
}


async def get_device_trust(device_id: str, user_id: str, profile) -> Dict[str, Any]:
    try:
        rep = await feature_store.get_device_reputation(device_id)
    except Exception as exc:
        _logger.warning(
            "DeviceReputation: feature_store unavailable for device=%r user=%r — "
            "using safe defaults. %s: %s",
            device_id, user_id, type(exc).__name__, exc,
        )
        rep = dict(_SAFE_DEVICE_DEFAULTS)

    age_days = float(rep.get("age_days", 0))
    fraud_count = float(rep.get("fraud_count", 0))
    account_count = float(rep.get("account_count", 1))
    historical_trust = float(rep.get("trust_score", 0.5))

    is_known = device_id in profile.known_devices

    # --- Base trust from age ---
    if is_known:
        age_trust = min(1.0, 0.5 + age_days / 365)
    else:
        age_trust = 0.1    # new/unknown device starts low

    # --- Fraud penalty (exponential) ---
    fraud_penalty = min(0.9, fraud_count * 0.3)

    # --- Multi-account penalty ---
    multi_account_penalty = min(0.4, max(0.0, (account_count - 1) * 0.1))

    # --- Decay logic: trust decays if device not seen recently ---
    last_seen_ts = float(rep.get("last_seen_ts", 0))
    days_since_seen = (time.time() - last_seen_ts) / 86400 if last_seen_ts else 999
    decay_factor = max(0.5, 1.0 - days_since_seen * 0.002)   # -0.2% per day

    raw_trust = (age_trust - fraud_penalty - multi_account_penalty) * decay_factor
    trust_score = max(0.0, min(1.0, raw_trust))

    risk_score = round((1.0 - trust_score) * 100, 2)

    return {
        "device_id": device_id,
        "device_trust_score": round(trust_score, 3),
        "device_risk_score": risk_score,
        "is_known_device": is_known,
        "age_days": age_days,
        "fraud_associations": int(fraud_count),
        "account_count": int(account_count),
        "days_since_last_seen": round(days_since_seen, 1),
        "signals": _build_signals(is_known, fraud_count, account_count, age_days),
    }


def _build_signals(is_known: bool, fraud_count: float, account_count: float, age_days: float) -> list:
    signals = []
    if not is_known:
        signals.append("unrecognized_device")
    if fraud_count > 0:
        signals.append(f"device_has_{int(fraud_count)}_fraud_association(s)")
    if account_count > 2:
        signals.append(f"device_used_by_{int(account_count)}_accounts")
    if age_days < 7:
        signals.append("very_new_device")
    if is_known and age_days > 180:
        signals.append("long_trusted_device")
    return signals
