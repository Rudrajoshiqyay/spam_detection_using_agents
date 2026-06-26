"""
Negative Signal Framework — positive signals raise risk, negative signals lower it.

Ensures trusted context (known device, recurring payment, salary credit) reduces
false positives rather than being ignored.

All signals defined in the weight dicts have corresponding detection logic.
"""

from typing import Dict, Any, List, Optional

from app.models.transaction import Transaction
from app.models.user_profile import UserProfile


# Positive signals (fraud indicators) — weights sum influence on risk
_POSITIVE_SIGNAL_WEIGHTS = {
    "new_device": 18,
    "new_location": 15,
    "velocity_spike": 20,
    "high_amount": 15,
    "impossible_travel": 30,
    "suspicious_travel": 20,
    "new_merchant_high_risk_cat": 10,
    "international_unexpected": 12,
    "night_transaction_high_amount": 8,
    "first_time_merchant": 6,
    "micro_transaction_burst": 22,
    "fraud_pattern_match": 25,
    "kill_chain_match": 20,
}

# Negative signals (trust indicators) — weights reduce final score
_NEGATIVE_SIGNAL_WEIGHTS = {
    "known_device": 12,
    "known_merchant": 10,
    "recurring_payment_pattern": 15,
    "trusted_location": 12,
    "salary_credit_pattern": 18,
    "daytime_transaction": 5,
    "within_usual_spend_range": 10,
    "long_account_history": 8,
    "merchant_trusted": 8,
    "within_cohort_normal": 7,
}

# High-risk merchant categories (shared with merchant_reputation.py)
_HIGH_RISK_CATEGORIES = {"gambling", "crypto", "wire_transfer", "cash_advance", "adult", "pawnshop"}


def evaluate_signals(
    txn: Transaction,
    profile: UserProfile,
    features: dict,
    delta_result: dict,
    device_result: dict,
    merchant_result: dict,
    geo_result: dict,
    pattern_result: dict,
    kill_chain_result: dict,
    sequence_result: Optional[dict] = None,
    cohort_result: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Evaluate all fraud indicators (positive) and trust signals (negative).

    Parameters
    ----------
    sequence_result : optional
        Output from analyze_sequences(). Enables micro_transaction_burst detection.
    cohort_result : optional
        Output from analyze_cohort(). Enables within_cohort_normal detection.
    """
    positive: List[str] = []
    negative: List[str] = []
    positive_score = 0.0
    negative_score = 0.0

    avg_amt = float(features.get("avg_amount_30d", profile.spending_profile.avg_transaction_amount))
    std_amt = float(features.get("std_amount_30d", avg_amt * 0.5)) or 1.0

    # ----------------------------------------------------------------
    # Positive signals (fraud indicators)
    # ----------------------------------------------------------------

    if txn.device_id not in profile.known_devices:
        positive.append("new_device")
        positive_score += _POSITIVE_SIGNAL_WEIGHTS["new_device"]

    loc_key = f"{txn.location_city}:{txn.location_country}"
    if loc_key not in profile.known_locations:
        positive.append("new_location")
        positive_score += _POSITIVE_SIGNAL_WEIGHTS["new_location"]

    if int(features.get("txn_count_1h", 0)) > profile.thresholds.max_txn_per_hour:
        positive.append("velocity_spike")
        positive_score += _POSITIVE_SIGNAL_WEIGHTS["velocity_spike"]

    if txn.amount > avg_amt + 3 * std_amt:
        positive.append("high_amount")
        positive_score += _POSITIVE_SIGNAL_WEIGHTS["high_amount"]

    if geo_result.get("is_impossible_travel"):
        positive.append("impossible_travel")
        positive_score += _POSITIVE_SIGNAL_WEIGHTS["impossible_travel"]
    elif geo_result.get("is_suspicious_travel"):
        positive.append("suspicious_travel")
        positive_score += _POSITIVE_SIGNAL_WEIGHTS["suspicious_travel"]

    if txn.is_international and txn.location_country not in profile.travel_profile.frequent_countries:
        positive.append("international_unexpected")
        positive_score += _POSITIVE_SIGNAL_WEIGHTS["international_unexpected"]

    # Night transaction combined with high amount
    if txn.timestamp.hour < 5 and txn.amount > avg_amt * 2:
        positive.append("night_transaction_high_amount")
        positive_score += _POSITIVE_SIGNAL_WEIGHTS["night_transaction_high_amount"]

    # First-time merchant
    merchant_freqs_check: dict = features.get("merchant_frequencies", {})
    if int(merchant_freqs_check.get(txn.merchant_id, 0)) == 0:
        positive.append("first_time_merchant")
        positive_score += _POSITIVE_SIGNAL_WEIGHTS["first_time_merchant"]
        # Compound: first-time merchant in a high-risk category
        if txn.merchant_category.lower() in _HIGH_RISK_CATEGORIES:
            positive.append("new_merchant_high_risk_cat")
            positive_score += _POSITIVE_SIGNAL_WEIGHTS["new_merchant_high_risk_cat"]

    # Micro-transaction burst from sequence intelligence
    if sequence_result is not None:
        active_seqs = sequence_result.get("active_sequences", [])
        if "card_testing" in active_seqs:
            positive.append("micro_transaction_burst")
            positive_score += _POSITIVE_SIGNAL_WEIGHTS["micro_transaction_burst"]

    if pattern_result.get("pattern_matched"):
        positive.append("fraud_pattern_match")
        positive_score += _POSITIVE_SIGNAL_WEIGHTS["fraud_pattern_match"]

    if kill_chain_result.get("matched_kill_chain"):
        positive.append("kill_chain_match")
        positive_score += _POSITIVE_SIGNAL_WEIGHTS["kill_chain_match"]

    # ----------------------------------------------------------------
    # Negative signals (trust indicators)
    # ----------------------------------------------------------------

    if txn.device_id in profile.known_devices:
        negative.append("known_device")
        negative_score += _NEGATIVE_SIGNAL_WEIGHTS["known_device"]

    merchant_freqs: dict = features.get("merchant_frequencies", {})
    if int(merchant_freqs.get(txn.merchant_id, 0)) >= 3:
        negative.append("known_merchant")
        negative_score += _NEGATIVE_SIGNAL_WEIGHTS["known_merchant"]

    if loc_key in profile.known_locations:
        negative.append("trusted_location")
        negative_score += _NEGATIVE_SIGNAL_WEIGHTS["trusted_location"]

    if avg_amt * 0.5 <= txn.amount <= avg_amt * 1.5:
        negative.append("within_usual_spend_range")
        negative_score += _NEGATIVE_SIGNAL_WEIGHTS["within_usual_spend_range"]

    if profile.account_age_days > 365:
        negative.append("long_account_history")
        negative_score += _NEGATIVE_SIGNAL_WEIGHTS["long_account_history"]

    if merchant_result.get("merchant_reputation_score", 0) > 0.8:
        negative.append("merchant_trusted")
        negative_score += _NEGATIVE_SIGNAL_WEIGHTS["merchant_trusted"]

    txn_hour = txn.timestamp.hour
    if 9 <= txn_hour <= 21:
        negative.append("daytime_transaction")
        negative_score += _NEGATIVE_SIGNAL_WEIGHTS["daytime_transaction"]

    # Recurring payment: same merchant visited 10+ times historically (proxy)
    if int(merchant_freqs.get(txn.merchant_id, 0)) >= 10:
        negative.append("recurring_payment_pattern")
        negative_score += _NEGATIVE_SIGNAL_WEIGHTS["recurring_payment_pattern"]

    # Salary-like credit pattern: large regular deposits → established account
    # Proxy: account age > 180 days AND amount is within 2x average (not anomalous)
    if profile.account_age_days > 180 and txn.amount <= avg_amt * 2:
        negative.append("salary_credit_pattern")
        negative_score += _NEGATIVE_SIGNAL_WEIGHTS["salary_credit_pattern"]

    # Cohort normality: deviation score below 25 means the amount is typical for this user group
    if cohort_result is not None:
        if cohort_result.get("cohort_deviation_score", 100) < 25:
            negative.append("within_cohort_normal")
            negative_score += _NEGATIVE_SIGNAL_WEIGHTS["within_cohort_normal"]

    # ----------------------------------------------------------------
    # Final adjusted risk formula
    # ----------------------------------------------------------------
    # net_signal = positive - negative, scaled to 0-100
    max_possible = sum(_POSITIVE_SIGNAL_WEIGHTS.values())
    net = max(0.0, positive_score - negative_score)
    signal_risk_score = round(min(100.0, (net / max_possible) * 100), 2)

    return {
        "signal_risk_score": signal_risk_score,
        "positive_signals": positive,
        "negative_signals": negative,
        "positive_score_raw": round(positive_score, 2),
        "negative_score_raw": round(negative_score, 2),
        "net_signal_score": round(net, 2),
        "false_positive_reduction": len(negative) > 0,
    }
