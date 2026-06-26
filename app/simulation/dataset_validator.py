"""
Dataset Quality Validator — scores synthetic datasets on diversity and realism.

Quality dimensions:
  1. Persona diversity     — all 8 persona types represented
  2. Fraud type diversity  — all fraud types present
  3. City distribution     — transactions spread across 10+ cities
  4. Country distribution  — at least 3 countries
  5. Merchant category coverage — 15+ unique categories
  6. Temporal spread       — transactions across multiple days
  7. Amount realism        — log-normal fit (not flat/uniform)
  8. Fraud rate validity   — 2-15% fraud rate (realistic)
  9. Attack difficulty spread — easy/medium/hard all present

Score 0-100. Datasets below 60 are rejected for training.
"""

import math
from collections import Counter
from typing import List, Dict, Any, Optional


MIN_QUALITY_SCORE = 60.0

PERSONA_TYPES = {
    "student", "salaried_employee", "business_owner",
    "frequent_traveler", "senior_citizen", "gig_worker",
    "high_net_worth", "crypto_trader",
}

FRAUD_TYPES = {
    "account_takeover", "card_testing", "money_mule",
    "velocity_fraud", "synthetic_identity", "merchant_abuse",
}


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _coverage_score(found: set, expected: set, weight: float) -> float:
    if not expected:
        return weight
    return weight * len(found & expected) / len(expected)


def _shannon_entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total == 0:
        return 0.0
    return -sum(
        (v / total) * math.log2(v / total)
        for v in counter.values() if v > 0
    )


def _is_log_normal(amounts: List[float]) -> bool:
    """Very rough check: log-normal implies log(amounts) is roughly normal → low CV."""
    if len(amounts) < 20:
        return True  # skip check for small samples
    logs = [math.log(max(a, 1)) for a in amounts]
    mean = sum(logs) / len(logs)
    var = sum((x - mean) ** 2 for x in logs) / len(logs)
    cv = math.sqrt(var) / max(abs(mean), 1e-9)
    return cv < 2.0  # coefficient of variation under 2 suggests non-pathological


# ── Dimension scorers ─────────────────────────────────────────────────────────

def _score_persona_diversity(records: List[Dict]) -> Dict:
    found = {r.get("persona_type") for r in records if r.get("persona_type")}
    score = _coverage_score(found, PERSONA_TYPES, 15.0)
    return {
        "dimension": "persona_diversity",
        "score": round(score, 2),
        "max": 15.0,
        "found": sorted(found),
        "missing": sorted(PERSONA_TYPES - found),
    }


def _score_fraud_type_diversity(records: List[Dict]) -> Dict:
    found = {r.get("fraud_type") for r in records if r.get("fraud_type") and r.get("is_fraud")}
    score = _coverage_score(found, FRAUD_TYPES, 15.0)
    return {
        "dimension": "fraud_type_diversity",
        "score": round(score, 2),
        "max": 15.0,
        "found": sorted(found),
        "missing": sorted(FRAUD_TYPES - found),
    }


def _score_city_distribution(records: List[Dict]) -> Dict:
    cities = Counter(r.get("location_city", "Unknown") for r in records)
    n_cities = len(cities)
    # Target: 10+ cities for full score
    score = min(10.0, (n_cities / 10) * 10.0)
    entropy = _shannon_entropy(cities)
    # Bonus for even distribution (high entropy)
    score = min(10.0, score * (1 + entropy * 0.05))
    return {
        "dimension": "city_distribution",
        "score": round(score, 2),
        "max": 10.0,
        "unique_cities": n_cities,
        "top_cities": cities.most_common(5),
    }


def _score_country_distribution(records: List[Dict]) -> Dict:
    countries = Counter(r.get("location_country", "Unknown") for r in records)
    n_countries = len(countries)
    # Target: 5+ countries
    score = min(10.0, (n_countries / 5) * 10.0)
    return {
        "dimension": "country_distribution",
        "score": round(score, 2),
        "max": 10.0,
        "unique_countries": n_countries,
        "countries": list(countries.keys()),
    }


def _score_merchant_category_coverage(records: List[Dict]) -> Dict:
    cats = {r.get("merchant_category") for r in records if r.get("merchant_category")}
    n_cats = len(cats)
    # Target: 15+ categories
    score = min(10.0, (n_cats / 15) * 10.0)
    return {
        "dimension": "merchant_category_coverage",
        "score": round(score, 2),
        "max": 10.0,
        "unique_categories": n_cats,
        "categories": sorted(cats),
    }


def _score_temporal_spread(records: List[Dict]) -> Dict:
    dates = set()
    for r in records:
        ts = r.get("timestamp") or r.get("created_at")
        if ts:
            date_str = str(ts)[:10]
            dates.add(date_str)
    n_days = len(dates)
    # Target: 7+ days
    score = min(10.0, (n_days / 7) * 10.0)
    return {
        "dimension": "temporal_spread",
        "score": round(score, 2),
        "max": 10.0,
        "unique_days": n_days,
    }


def _score_amount_realism(records: List[Dict]) -> Dict:
    amounts = [r.get("amount", 0) for r in records if r.get("amount", 0) > 0]
    if not amounts:
        return {"dimension": "amount_realism", "score": 0.0, "max": 10.0}
    is_realistic = _is_log_normal(amounts)
    mean_amt = sum(amounts) / len(amounts)
    score = 10.0 if is_realistic else 4.0
    return {
        "dimension": "amount_realism",
        "score": score,
        "max": 10.0,
        "is_log_normal": is_realistic,
        "mean_amount": round(mean_amt, 2),
        "min": round(min(amounts), 2),
        "max_amount": round(max(amounts), 2),
    }


def _score_fraud_rate(records: List[Dict]) -> Dict:
    total = len(records)
    fraud_count = sum(1 for r in records if r.get("is_fraud"))
    fraud_rate = fraud_count / total if total else 0
    # Target: 2-15% fraud rate
    in_range = 0.02 <= fraud_rate <= 0.15
    if in_range:
        score = 10.0
    elif 0.01 <= fraud_rate <= 0.25:
        score = 5.0  # slightly off but acceptable
    else:
        score = 0.0
    return {
        "dimension": "fraud_rate_validity",
        "score": score,
        "max": 10.0,
        "fraud_rate": round(fraud_rate, 4),
        "in_range": in_range,
        "fraud_count": fraud_count,
        "total": total,
    }


def _score_difficulty_spread(records: List[Dict]) -> Dict:
    easy = medium = hard = 0
    for r in records:
        d = r.get("attack_difficulty", 0)
        if d < 33:
            easy += 1
        elif d < 66:
            medium += 1
        else:
            hard += 1
    has_all = easy > 0 and medium > 0 and hard > 0
    score = 10.0 if has_all else (5.0 if (easy > 0 or medium > 0 or hard > 0) else 0.0)
    return {
        "dimension": "difficulty_spread",
        "score": score,
        "max": 10.0,
        "easy": easy,
        "medium": medium,
        "hard": hard,
    }


# ── Main validator ────────────────────────────────────────────────────────────

def validate_dataset(
    records: List[Dict],
    raise_if_below: float = None,
) -> Dict[str, Any]:
    """
    Score a synthetic dataset on 9 quality dimensions.

    Args:
        records: list of transaction dicts (from campaign/ring/behavior generators)
        raise_if_below: if set, raises ValueError if quality score < threshold

    Returns:
        {
          "quality_score": float,       # 0-100
          "passed": bool,               # >= MIN_QUALITY_SCORE
          "dimensions": [...]           # per-dimension scores
          "recommendations": [...]      # actionable improvement hints
        }
    """
    if not records:
        return {
            "quality_score": 0.0,
            "passed": False,
            "dimensions": [],
            "recommendations": ["Dataset is empty — generate transactions first."],
        }

    dimensions = [
        _score_persona_diversity(records),
        _score_fraud_type_diversity(records),
        _score_city_distribution(records),
        _score_country_distribution(records),
        _score_merchant_category_coverage(records),
        _score_temporal_spread(records),
        _score_amount_realism(records),
        _score_fraud_rate(records),
        _score_difficulty_spread(records),
    ]

    total = sum(d["score"] for d in dimensions)
    max_possible = sum(d["max"] for d in dimensions)
    quality_score = round((total / max_possible) * 100, 1) if max_possible else 0.0
    passed = quality_score >= MIN_QUALITY_SCORE

    # Build recommendations for failed dimensions
    recommendations = []
    for d in dimensions:
        if d["score"] < d["max"] * 0.6:
            dim = d["dimension"]
            if dim == "persona_diversity" and d.get("missing"):
                recommendations.append(
                    f"Add transactions for persona types: {', '.join(d['missing'][:3])}"
                )
            elif dim == "fraud_type_diversity" and d.get("missing"):
                recommendations.append(
                    f"Add fraud campaigns for: {', '.join(d['missing'][:3])}"
                )
            elif dim == "city_distribution":
                recommendations.append(
                    f"Increase city spread — only {d.get('unique_cities', 0)} cities found (need 10+)"
                )
            elif dim == "fraud_rate_validity":
                fr = d.get("fraud_rate", 0)
                if fr < 0.02:
                    recommendations.append("Fraud rate too low (<2%) — inject more fraud campaigns")
                else:
                    recommendations.append("Fraud rate too high (>15%) — add more legitimate transactions")
            elif dim == "temporal_spread":
                recommendations.append(
                    f"Spread over more days — only {d.get('unique_days', 0)} days found (need 7+)"
                )
            elif dim == "difficulty_spread":
                recommendations.append(
                    "Apply adversarial mutations — no difficulty variation in fraud transactions"
                )
            elif dim == "merchant_category_coverage":
                recommendations.append(
                    f"Only {d.get('unique_categories', 0)} merchant categories — add behavior from more persona types"
                )

    if not passed and not recommendations:
        recommendations.append(f"Quality score {quality_score} below minimum {MIN_QUALITY_SCORE} — increase dataset size")

    return {
        "quality_score": quality_score,
        "passed": passed,
        "record_count": len(records),
        "dimensions": dimensions,
        "recommendations": recommendations,
        "min_required": MIN_QUALITY_SCORE,
    }
