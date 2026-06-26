"""
Evaluation Engine — computes accuracy/precision/recall/F1 by comparing
ground_truth_store labels against detection pipeline results.

Stratified by:
  - fraud_type (per fraud category)
  - attack_difficulty band (Easy 0-33, Medium 33-66, Hard 66-100)
  - persona_type
"""

from typing import Dict, Any, List, Optional
from app.simulation.ground_truth_store import (
    get_all_records, get_stats, GroundTruthRecord,
)


# ── Decision normalizer ────────────────────────────────────────────────────────

def _normalize_decision(decision: str) -> str:
    """Map pipeline decision strings to binary FRAUD / LEGIT."""
    if decision is None:
        return "LEGIT"
    d = decision.upper()
    if d in ("BLOCKED", "FRAUD", "REJECT", "DECLINED"):
        return "FRAUD"
    if d in ("ESCALATED", "REVIEW", "MANUAL_REVIEW"):
        return "FRAUD"  # treat escalations as positive detections
    return "LEGIT"


def _difficulty_band(score: float) -> str:
    if score < 33:
        return "easy"
    elif score < 66:
        return "medium"
    return "hard"


# ── Confusion matrix utilities ─────────────────────────────────────────────────

def _build_cm(records: List[GroundTruthRecord], results: Dict[str, str]) -> Dict:
    """
    results: {transaction_id: pipeline_decision_string}
    Returns confusion matrix counts + derived metrics.
    """
    tp = fp = tn = fn = 0

    for rec in records:
        pred_raw = results.get(rec.transaction_id, "APPROVED")
        pred = _normalize_decision(pred_raw)
        actual = "FRAUD" if rec.is_fraud else "LEGIT"

        if actual == "FRAUD" and pred == "FRAUD":
            tp += 1
        elif actual == "LEGIT" and pred == "FRAUD":
            fp += 1
        elif actual == "LEGIT" and pred == "LEGIT":
            tn += 1
        else:
            fn += 1

    total = tp + fp + tn + fn
    accuracy  = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    fpr = fp / (fp + tn) if (fp + tn) else 0.0  # false positive rate

    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "total": total,
        "accuracy":  round(accuracy,  4),
        "precision": round(precision, 4),
        "recall":    round(recall,    4),
        "f1":        round(f1,        4),
        "fpr":       round(fpr,       4),
    }


# ── Stratified evaluation ─────────────────────────────────────────────────────

async def evaluate(
    detection_results: Dict[str, str],
    limit: int = 50_000,
) -> Dict[str, Any]:
    """
    detection_results: mapping of transaction_id → pipeline decision string.

    Returns:
    {
      "overall": {tp, fp, tn, fn, accuracy, precision, recall, f1, fpr},
      "by_fraud_type": {fraud_type: {metrics}},
      "by_difficulty": {easy/medium/hard: {metrics}},
      "by_persona": {persona_type: {metrics}},
      "summary": {total_evaluated, coverage_pct},
    }
    """
    records = await get_all_records(limit=limit)
    if not records:
        return {
            "overall": _empty_metrics(),
            "by_fraud_type": {},
            "by_difficulty": {},
            "by_persona": {},
            "summary": {"total_evaluated": 0, "coverage_pct": 0.0},
        }

    coverage = sum(1 for r in records if r.transaction_id in detection_results)
    coverage_pct = round(coverage / len(records), 4) if records else 0.0

    # Overall
    overall = _build_cm(records, detection_results)

    # By fraud type
    by_type: Dict[str, List[GroundTruthRecord]] = {}
    for r in records:
        key = r.fraud_type or "legitimate"
        by_type.setdefault(key, []).append(r)
    by_fraud_type = {k: _build_cm(v, detection_results) for k, v in by_type.items()}

    # By difficulty band
    by_diff_raw: Dict[str, List[GroundTruthRecord]] = {"easy": [], "medium": [], "hard": []}
    for r in records:
        band = _difficulty_band(r.attack_difficulty)
        by_diff_raw[band].append(r)
    by_difficulty = {k: _build_cm(v, detection_results) for k, v in by_diff_raw.items() if v}

    # By persona
    by_persona_raw: Dict[str, List[GroundTruthRecord]] = {}
    for r in records:
        key = r.persona_type or "unknown"
        by_persona_raw.setdefault(key, []).append(r)
    by_persona = {k: _build_cm(v, detection_results) for k, v in by_persona_raw.items()}

    return {
        "overall": overall,
        "by_fraud_type": by_fraud_type,
        "by_difficulty": by_difficulty,
        "by_persona": by_persona,
        "summary": {
            "total_evaluated": len(records),
            "coverage_pct": coverage_pct,
        },
    }


def _empty_metrics() -> Dict:
    return {
        "tp": 0, "fp": 0, "tn": 0, "fn": 0, "total": 0,
        "accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0, "fpr": 0.0,
    }


# ── Lightweight in-memory evaluation (no DB required) ─────────────────────────

def evaluate_batch(
    ground_truth: List[Dict],        # list of {transaction_id, is_fraud, fraud_type, attack_difficulty, persona_type}
    detection_results: Dict[str, str],  # {txn_id: pipeline_decision}
) -> Dict[str, Any]:
    """
    Evaluate a batch without touching the DB.
    Useful for validating a freshly-generated dataset before storing.
    """
    records = [
        GroundTruthRecord(
            transaction_id=r["transaction_id"],
            is_fraud=r.get("is_fraud", False),
            fraud_type=r.get("fraud_type"),
            campaign_id=r.get("campaign_id"),
            ring_id=r.get("ring_id"),
            attack_difficulty=r.get("attack_difficulty", 0.0),
            expected_label=r.get("expected_label", "APPROVED"),
            persona_type=r.get("persona_type"),
            amount=r.get("amount", 0.0),
        )
        for r in ground_truth
    ]

    # Simulate detection_results if empty (for pure quality check)
    if not detection_results:
        detection_results = {r.transaction_id: r.expected_label for r in records}

    overall = _build_cm(records, detection_results)
    return {"overall": overall, "record_count": len(records)}
