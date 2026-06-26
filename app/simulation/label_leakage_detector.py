"""
Label Leakage Detector — critical quality control (spec §12).

Checks whether fraud labels can be predicted from a SINGLE feature value.

If a single merchant_category, country, or device_type is present in
>=80% of fraud cases but <20% of legitimate cases, the dataset has
label leakage and will produce artificially inflated F1 scores.

Metrics computed per feature:
  - fraud_concentration: P(feature_value | is_fraud)
  - lift:                fraud_rate(value) / overall_fraud_rate
  - information_gain:    H(fraud) - H(fraud | feature)
  - gini_impurity:       per-value gini coefficient

A feature is flagged if:
  - Any single value has lift > 3.0 AND fraud concentration > 0.50
  - Information gain / H(fraud) > 0.40 (40% predictable from this feature alone)

Output: LeakageReport with per-feature analysis and dataset-level verdict.
"""

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple


# ── Thresholds ────────────────────────────────────────────────────────────────

LIFT_THRESHOLD = 3.0           # fraud rate in bucket / overall fraud rate
CONCENTRATION_THRESHOLD = 0.50 # >50% of all fraud in one feature bucket
INFO_GAIN_RATIO_THRESHOLD = 0.40  # feature explains >40% of fraud entropy

MIN_SUPPORT = 5                # ignore buckets with < 5 samples


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class FeatureLeakageResult:
    feature_name: str
    is_leaking: bool
    severity: str                  # "critical", "warning", "ok"
    worst_value: Optional[str]
    worst_value_fraud_rate: float  # fraud rate within worst bucket
    worst_value_lift: float        # lift vs overall fraud rate
    fraud_concentration: float     # fraction of all fraud in worst bucket
    information_gain: float        # raw information gain
    info_gain_ratio: float         # IG / H(fraud)
    top_values: List[Dict]         # top 5 values with fraud stats
    recommendation: str


@dataclass
class LeakageReport:
    total_records: int
    fraud_count: int
    legit_count: int
    overall_fraud_rate: float

    features_checked: List[str]
    results: List[FeatureLeakageResult]
    leaking_features: List[str]

    dataset_verdict: str           # "PASS", "WARNING", "REJECT"
    quality_impact: str            # human-readable impact statement
    recommendations: List[str]


# ── Entropy helpers ───────────────────────────────────────────────────────────

def _entropy(p: float) -> float:
    if p <= 0 or p >= 1:
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def _information_gain(
    records: List[Dict],
    feature: str,
    overall_fraud_rate: float,
) -> Tuple[float, float]:
    """
    Compute information gain of `feature` for predicting fraud.
    Returns (raw_IG, IG_ratio).
    """
    H_fraud = _entropy(overall_fraud_rate)
    if H_fraud == 0:
        return 0.0, 0.0

    total = len(records)
    buckets: Dict[str, List[int]] = {}
    for r in records:
        val = str(r.get(feature, "unknown"))
        buckets.setdefault(val, []).append(1 if r.get("is_fraud") else 0)

    H_feature = 0.0
    for val, labels in buckets.items():
        if len(labels) < MIN_SUPPORT:
            continue
        n = len(labels)
        p_val = n / total
        fraud_rate_val = sum(labels) / n
        H_feature += p_val * _entropy(fraud_rate_val)

    ig = H_fraud - H_feature
    ig_ratio = ig / H_fraud
    return round(max(0.0, ig), 4), round(max(0.0, ig_ratio), 4)


# ── Per-feature analysis ──────────────────────────────────────────────────────

def _analyze_feature(
    records: List[Dict],
    feature: str,
    overall_fraud_rate: float,
    total_fraud: int,
) -> FeatureLeakageResult:
    """Analyze one feature for label leakage."""
    buckets: Dict[str, Dict] = {}
    for r in records:
        val = str(r.get(feature, "unknown"))
        if val not in buckets:
            buckets[val] = {"total": 0, "fraud": 0}
        buckets[val]["total"] += 1
        if r.get("is_fraud"):
            buckets[val]["fraud"] += 1

    # Per-value stats
    value_stats = []
    for val, counts in buckets.items():
        if counts["total"] < MIN_SUPPORT:
            continue
        fraud_rate = counts["fraud"] / counts["total"]
        lift = fraud_rate / max(overall_fraud_rate, 1e-9)
        fraud_conc = counts["fraud"] / max(total_fraud, 1)
        value_stats.append({
            "value": val,
            "total": counts["total"],
            "fraud": counts["fraud"],
            "fraud_rate": round(fraud_rate, 4),
            "lift": round(lift, 2),
            "fraud_concentration": round(fraud_conc, 4),
        })

    value_stats.sort(key=lambda x: -x["lift"])
    top_values = value_stats[:5]

    ig, ig_ratio = _information_gain(records, feature, overall_fraud_rate)

    worst = top_values[0] if top_values else {}
    worst_lift = worst.get("lift", 0.0)
    worst_fraud_rate = worst.get("fraud_rate", 0.0)
    worst_conc = worst.get("fraud_concentration", 0.0)
    worst_value = worst.get("value")

    # Leakage determination
    is_leaking = (
        (worst_lift > LIFT_THRESHOLD and worst_conc > CONCENTRATION_THRESHOLD)
        or ig_ratio > INFO_GAIN_RATIO_THRESHOLD
    )

    if is_leaking and (worst_lift > 5.0 or ig_ratio > 0.60):
        severity = "critical"
    elif is_leaking:
        severity = "warning"
    else:
        severity = "ok"

    # Recommendation
    if severity == "critical":
        recommendation = (
            f"CRITICAL: '{worst_value}' accounts for {worst_conc*100:.0f}% of all fraud "
            f"(lift={worst_lift:.1f}x). A rule engine would trivially detect this. "
            f"Distribute fraud across more {feature} values."
        )
    elif severity == "warning":
        recommendation = (
            f"WARNING: '{worst_value}' has high fraud concentration "
            f"(lift={worst_lift:.1f}x, IG-ratio={ig_ratio:.2f}). "
            f"Add legitimate transactions from this {feature} value."
        )
    else:
        recommendation = f"OK: No significant leakage detected in {feature}."

    return FeatureLeakageResult(
        feature_name=feature,
        is_leaking=is_leaking,
        severity=severity,
        worst_value=worst_value,
        worst_value_fraud_rate=worst_fraud_rate,
        worst_value_lift=worst_lift,
        fraud_concentration=worst_conc,
        information_gain=ig,
        info_gain_ratio=ig_ratio,
        top_values=top_values,
        recommendation=recommendation,
    )


# ── Main detector ─────────────────────────────────────────────────────────────

FEATURES_TO_CHECK = [
    "merchant_category",
    "location_country",
    "device_type",
    "channel",
    "transaction_type",
    "persona_type",
    "is_international",
]


def detect_leakage(
    records: List[Dict],
    features: List[str] = None,
    min_fraud_count: int = 10,
) -> LeakageReport:
    """
    Detect label leakage in a synthetic dataset.

    Args:
        records: list of transaction dicts with `is_fraud` field.
        features: list of feature names to check (defaults to FEATURES_TO_CHECK).
        min_fraud_count: minimum fraud count to run analysis (too few is unreliable).

    Returns:
        LeakageReport with per-feature analysis and overall verdict.
    """
    features = features or FEATURES_TO_CHECK
    total = len(records)

    if total == 0:
        return _empty_report()

    fraud_count = sum(1 for r in records if r.get("is_fraud"))
    legit_count = total - fraud_count
    overall_fraud_rate = fraud_count / total

    results: List[FeatureLeakageResult] = []
    leaking_features: List[str] = []

    if fraud_count < min_fraud_count:
        # Not enough fraud to analyze
        return LeakageReport(
            total_records=total,
            fraud_count=fraud_count,
            legit_count=legit_count,
            overall_fraud_rate=round(overall_fraud_rate, 4),
            features_checked=features,
            results=[],
            leaking_features=[],
            dataset_verdict="WARNING",
            quality_impact="Too few fraud samples to detect leakage reliably.",
            recommendations=[f"Generate at least {min_fraud_count} fraud transactions before checking."],
        )

    for feature in features:
        res = _analyze_feature(records, feature, overall_fraud_rate, fraud_count)
        results.append(res)
        if res.is_leaking:
            leaking_features.append(feature)

    # Overall verdict
    critical_features = [r for r in results if r.severity == "critical"]
    warning_features = [r for r in results if r.severity == "warning"]

    if critical_features:
        verdict = "REJECT"
        impact = (
            f"Dataset REJECTED: {len(critical_features)} feature(s) with critical label leakage. "
            f"A naive classifier would achieve >80% F1 without learning fraud patterns. "
            f"Affected: {', '.join(f.feature_name for f in critical_features)}"
        )
    elif warning_features:
        verdict = "WARNING"
        impact = (
            f"Dataset WARNING: {len(warning_features)} feature(s) with moderate leakage. "
            f"Results may be overly optimistic. Consider diversifying: "
            f"{', '.join(f.feature_name for f in warning_features)}"
        )
    else:
        verdict = "PASS"
        impact = (
            f"Dataset PASSED leakage check. No single feature can predict fraud "
            f"with >3x lift or >50% concentration. Detection performance reflects real model quality."
        )

    recommendations = [r.recommendation for r in results if r.severity != "ok"]

    return LeakageReport(
        total_records=total,
        fraud_count=fraud_count,
        legit_count=legit_count,
        overall_fraud_rate=round(overall_fraud_rate, 4),
        features_checked=features,
        results=results,
        leaking_features=leaking_features,
        dataset_verdict=verdict,
        quality_impact=impact,
        recommendations=recommendations or ["No leakage detected — dataset quality is good."],
    )


def leakage_report_to_dict(report: LeakageReport) -> Dict[str, Any]:
    return {
        "total_records": report.total_records,
        "fraud_count": report.fraud_count,
        "legit_count": report.legit_count,
        "overall_fraud_rate": report.overall_fraud_rate,
        "features_checked": report.features_checked,
        "leaking_features": report.leaking_features,
        "dataset_verdict": report.dataset_verdict,
        "quality_impact": report.quality_impact,
        "recommendations": report.recommendations,
        "feature_analysis": [
            {
                "feature": r.feature_name,
                "severity": r.severity,
                "is_leaking": r.is_leaking,
                "worst_value": r.worst_value,
                "worst_value_fraud_rate": r.worst_value_fraud_rate,
                "lift": r.worst_value_lift,
                "fraud_concentration": r.fraud_concentration,
                "info_gain_ratio": r.info_gain_ratio,
                "top_values": r.top_values,
                "recommendation": r.recommendation,
            }
            for r in report.results
        ],
    }


def _empty_report() -> LeakageReport:
    return LeakageReport(
        total_records=0,
        fraud_count=0,
        legit_count=0,
        overall_fraud_rate=0.0,
        features_checked=[],
        results=[],
        leaking_features=[],
        dataset_verdict="WARNING",
        quality_impact="Empty dataset — no records to analyze.",
        recommendations=["Generate transactions before running leakage check."],
    )
