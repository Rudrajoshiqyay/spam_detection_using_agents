"""
Behavioral Cohort Analysis — compares user behavior against peer group averages.
"""

import json
import logging
import math
from pathlib import Path
from typing import Dict, Any

from app.models.transaction import Transaction
from app.models.user_profile import UserProfile

_logger = logging.getLogger(__name__)

# Minimal fallback cohort used when the data file is absent or corrupt.
# Prevents startup crash while allowing the pipeline to continue.
_DEFAULT_COHORT: dict = {
    "avg_transaction_amount": 150.0,
    "std_transaction_amount": 120.0,
    "p99_transaction_amount": 2000.0,
    "merchant_preferences": {},
    "typical_hours": list(range(8, 22)),
}

_COHORTS: dict = {}


def load_cohorts() -> None:
    global _COHORTS
    path = Path(__file__).parent.parent / "data" / "cohort_profiles.json"
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data).__name__}")
        _COHORTS = data
        _logger.info("CohortAnalysis: loaded %d cohorts from %s", len(_COHORTS), path)
    except FileNotFoundError:
        _logger.error(
            "CohortAnalysis: cohort_profiles.json not found at %s — using default cohort", path
        )
        _COHORTS = {"working_professional": _DEFAULT_COHORT}
    except (json.JSONDecodeError, ValueError) as exc:
        _logger.error(
            "CohortAnalysis: failed to parse %s — %s: %s — using default cohort",
            path, type(exc).__name__, exc,
        )
        _COHORTS = {"working_professional": _DEFAULT_COHORT}


def _map_user_type_to_cohort(user_type: str) -> str:
    mapping = {
        "student": "student",
        "working_professional": "working_professional",
        "traveler": "traveler",
        "business_owner": "business_owner",
        "retired": "retired",
        "high_net_worth": "high_net_worth",
        "high_risk": "working_professional",  # fallback
    }
    cohort = mapping.get(user_type, "working_professional")
    if user_type not in mapping:
        _logger.debug("CohortAnalysis: unknown user_type=%r — defaulting to working_professional", user_type)
    return cohort


def _normal_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def analyze_cohort(
    txn: Transaction,
    profile: UserProfile,
    features: dict,
) -> Dict[str, Any]:
    if not _COHORTS:
        load_cohorts()

    cohort_name = _map_user_type_to_cohort(profile.user_type.value)
    # Fallback to working_professional if named cohort is absent from loaded data
    cohort = _COHORTS.get(cohort_name) or _COHORTS.get("working_professional", _DEFAULT_COHORT)

    # Amount deviation from cohort
    cohort_avg = cohort["avg_transaction_amount"]
    cohort_std = cohort["std_transaction_amount"] or 1.0
    amount_z = (txn.amount - cohort_avg) / cohort_std

    percentile = _normal_cdf(amount_z) * 100

    # Deviation score: 0 = perfectly cohort-normal, 100 = extreme outlier
    deviation_score = min(100.0, abs(amount_z) * 20)

    # Category match
    preferred = set(cohort.get("merchant_preferences", {}).keys())
    merchant_cat = txn.merchant_category.lower()
    category_match = any(cat in merchant_cat for cat in preferred)

    # Time-of-day match
    typical_hours = cohort.get("typical_hours", list(range(8, 22)))
    time_match = txn.timestamp.hour in typical_hours

    # Adjust deviation for behavioral context matches
    if category_match:
        deviation_score *= 0.85
    if time_match:
        deviation_score *= 0.90

    # Check against cohort p99 threshold
    p99 = cohort.get("p99_transaction_amount", cohort_avg * 10)
    exceeds_p99 = txn.amount > p99

    return {
        "cohort": cohort_name,
        "cohort_deviation_score": round(deviation_score, 2),
        "cohort_percentile": round(percentile, 2),
        "amount_z_score": round(amount_z, 3),
        "cohort_avg_amount": cohort_avg,
        "exceeds_p99": exceeds_p99,
        "category_match": category_match,
        "time_match": time_match,
    }
