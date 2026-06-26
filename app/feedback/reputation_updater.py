"""
Reputation Update Service — continuously updates device, merchant, and user
risk scores based on confirmed fraud outcomes from the Feedback Store.

CORE component: deterministic score updates, no LLM required.

Device and merchant IDs are read from the feedback record's device_id /
merchant_id fields (set at submission time). Notes are never parsed for IDs.

Uses a high-watermark (processed_at IS NULL) so each feedback record is
processed exactly once regardless of how many times this function is called.
"""

import logging
import time
from typing import Dict, Any, List

from app.services.feature_store import feature_store
from app.feedback.feedback_store import (
    get_unprocessed_feedback, mark_feedback_processed, OutcomeLabel,
)

_logger = logging.getLogger(__name__)


async def update_reputation_from_feedback(limit: int = 200) -> Dict[str, Any]:
    """
    Process unprocessed feedback records and update reputation scores in Redis.
    Records are marked processed after each run (idempotent high-watermark).

    On true_positive  → penalize device (-0.15) + merchant
    On false_positive → restore device (+0.10) + merchant
    On false_negative → penalize device (-0.20, higher because fraud was missed)
    """
    unprocessed = await get_unprocessed_feedback(limit)
    if not unprocessed:
        _logger.debug("ReputationUpdater: no unprocessed feedback records")
        return {"devices_updated": 0, "merchants_updated": 0, "skipped": 0, "processed": 0}

    updates: Dict[str, int] = {
        "devices_updated": 0, "merchants_updated": 0, "skipped": 0, "processed": 0,
    }
    processed_ids: List[str] = []

    for fb in unprocessed:
        outcome = fb.get("outcome_label", "unknown")
        fb_id = fb.get("id", "")
        device_id = fb.get("device_id")
        merchant_id = fb.get("merchant_id")

        try:
            if outcome == OutcomeLabel.true_positive:
                if device_id:
                    await _penalize_device(device_id, delta=0.15)
                    updates["devices_updated"] += 1
                if merchant_id:
                    await _penalize_merchant(merchant_id)
                    updates["merchants_updated"] += 1

            elif outcome == OutcomeLabel.false_positive:
                if device_id:
                    await _restore_device(device_id, delta=0.10)
                    updates["devices_updated"] += 1
                if merchant_id:
                    await _restore_merchant(merchant_id)
                    updates["merchants_updated"] += 1

            elif outcome == OutcomeLabel.false_negative:
                # Higher penalty: fraud occurred and was not caught
                if device_id:
                    await _penalize_device(device_id, delta=0.20)
                    updates["devices_updated"] += 1

            else:
                updates["skipped"] += 1
                processed_ids.append(fb_id)
                continue

            processed_ids.append(fb_id)
            updates["processed"] += 1
            _logger.debug(
                "ReputationUpdater: processed fb_id=%r outcome=%s device=%r merchant=%r",
                fb_id, outcome, device_id, merchant_id,
            )

        except Exception as exc:
            _logger.error(
                "ReputationUpdater: failed on fb_id=%r outcome=%r — %s: %s",
                fb_id, outcome, type(exc).__name__, exc,
            )
            updates["skipped"] += 1
            # Still mark processed to avoid infinite retry of broken records
            processed_ids.append(fb_id)

    await mark_feedback_processed(processed_ids)
    _logger.info(
        "ReputationUpdater: processed=%d devices=%d merchants=%d skipped=%d",
        updates["processed"], updates["devices_updated"],
        updates["merchants_updated"], updates["skipped"],
    )
    return updates


async def _penalize_device(device_id: str, delta: float = 0.15) -> None:
    try:
        rep = await feature_store.get_device_reputation(device_id)
    except Exception as exc:
        _logger.warning(
            "ReputationUpdater: get_device_reputation unavailable device=%r — %s: %s",
            device_id, type(exc).__name__, exc,
        )
        return
    old_trust = float(rep.get("trust_score", 0.5))
    old_fraud = float(rep.get("fraud_count", 0))
    await feature_store.set_device_reputation(device_id, {
        **rep,
        "trust_score": round(max(0.0, old_trust - delta), 4),
        "fraud_count": old_fraud + 1,
        "last_seen_ts": time.time(),
    })


async def _restore_device(device_id: str, delta: float = 0.10) -> None:
    try:
        rep = await feature_store.get_device_reputation(device_id)
    except Exception as exc:
        _logger.warning(
            "ReputationUpdater: get_device_reputation unavailable device=%r — %s: %s",
            device_id, type(exc).__name__, exc,
        )
        return
    old_trust = float(rep.get("trust_score", 0.5))
    await feature_store.set_device_reputation(device_id, {
        **rep,
        "trust_score": round(min(1.0, old_trust + delta), 4),
        "last_seen_ts": time.time(),
    })


async def _penalize_merchant(merchant_id: str) -> None:
    try:
        rep = await feature_store.get_merchant_reputation(merchant_id)
    except Exception as exc:
        _logger.warning(
            "ReputationUpdater: get_merchant_reputation unavailable merchant=%r — %s: %s",
            merchant_id, type(exc).__name__, exc,
        )
        return
    old_score = float(rep.get("reputation_score", 0.5))
    old_fraud = float(rep.get("fraud_associations", 0))
    await feature_store.set_merchant_reputation(merchant_id, {
        **rep,
        "reputation_score": round(max(0.0, old_score - 0.10), 4),
        "fraud_associations": old_fraud + 1,
    })


async def _restore_merchant(merchant_id: str) -> None:
    try:
        rep = await feature_store.get_merchant_reputation(merchant_id)
    except Exception as exc:
        _logger.warning(
            "ReputationUpdater: get_merchant_reputation unavailable merchant=%r — %s: %s",
            merchant_id, type(exc).__name__, exc,
        )
        return
    old_score = float(rep.get("reputation_score", 0.5))
    await feature_store.set_merchant_reputation(merchant_id, {
        **rep,
        "reputation_score": round(min(1.0, old_score + 0.10), 4),
    })


async def update_user_risk_score(user_id: str, confirmed_fraud: bool) -> Dict[str, Any]:
    """
    Update user risk profile in feature store based on confirmed outcome.
    risk_elevation is read by fast_screening.py to close the analyst feedback loop.
    """
    try:
        features = await feature_store.get_user_features(user_id)
    except Exception as exc:
        _logger.warning(
            "ReputationUpdater: get_user_features unavailable user=%r — %s: %s",
            user_id, type(exc).__name__, exc,
        )
        return {"user_id": user_id, "action": "skipped", "reason": str(exc)}

    fraud_flag_count = float(features.get("confirmed_fraud_count", 0))

    if confirmed_fraud:
        fraud_flag_count += 1
        risk_elevation = min(100.0, fraud_flag_count * 25)
        await feature_store.update_user_features(user_id, {
            "confirmed_fraud_count": fraud_flag_count,
            "risk_elevation": risk_elevation,
        })
        _logger.info(
            "ReputationUpdater: user=%r risk_elevation=%.0f confirmed_fraud_count=%.0f",
            user_id, risk_elevation, fraud_flag_count,
        )
        return {
            "user_id": user_id,
            "action": "risk_elevated",
            "fraud_count": fraud_flag_count,
            "risk_elevation": risk_elevation,
        }
    else:
        fp_count = float(features.get("false_positive_count", 0)) + 1
        await feature_store.update_user_features(user_id, {"false_positive_count": fp_count})
        return {"user_id": user_id, "action": "false_positive_noted", "fp_count": fp_count}
