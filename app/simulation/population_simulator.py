"""
Population Simulator — generates an entire population of synthetic users
with realistic distributions across persona types, income, geography, and devices.

Instead of independent users, produces a correlated PopulationProfile where
city density, device penetration, and income brackets match real patterns.
"""

import random
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from app.simulation.persona_agent import (
    PersonaType, PERSONA_DEFINITIONS, create_persona_user,
    _PERSONA_TO_USER_TYPE, _PERSONA_TO_RISK, _PERSONA_WEIGHTS,
)
from app.simulation.world_builder import (
    WORLD_CITIES, DOMESTIC_CITIES, ALL_COUNTRIES,
    get_merchant_by_category, MERCHANT_CATEGORIES,
)


# ── Population distribution — single source of truth is persona_agent._PERSONA_WEIGHTS ──

POPULATION_WEIGHTS: Dict[PersonaType, float] = _PERSONA_WEIGHTS

# City population weights for domestic users (tier 1 = more users)
_CITY_TIER_WEIGHTS = {1: 0.55, 2: 0.35, 3: 0.10}


@dataclass
class PopulationProfile:
    population_id: str
    total_users: int

    # Distribution counts
    persona_distribution: Dict[str, int]      # persona_type → count
    persona_distribution_pct: Dict[str, float]

    # Income distribution (INR monthly)
    income_p25: float
    income_median: float
    income_p75: float
    income_p95: float

    # Geographic distribution
    top_cities: List[Dict]                    # [{city, country, user_count}]
    country_distribution: Dict[str, int]
    international_user_pct: float            # % with frequent intl travel

    # Device distribution
    device_type_distribution: Dict[str, float]   # mobile/desktop/tablet
    avg_devices_per_user: float
    multi_device_pct: float

    # Merchant preference aggregate
    top_merchant_categories: List[str]

    # Fraud exposure estimate
    high_risk_persona_pct: float
    estimated_fraud_rate: float               # baseline before campaigns

    # Users (raw list for downstream use)
    users: List[Dict] = field(default_factory=list, repr=False)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _weighted_city() -> Dict:
    """Pick a domestic city weighted by tier (tier 1 cities get more users)."""
    city = random.choices(
        DOMESTIC_CITIES,
        weights=[_CITY_TIER_WEIGHTS.get(c.get("tier", 3), 0.10) for c in DOMESTIC_CITIES],
    )[0]
    return city


def _income_for_persona(persona_type: PersonaType) -> float:
    p = PERSONA_DEFINITIONS[persona_type]
    lo, hi = p.income_range
    # Log-normal within range
    mid = (lo + hi) / 2
    sigma = 0.4
    sample = random.lognormvariate(0, sigma)
    # Clamp to [lo, hi]
    return max(lo, min(hi, lo + (hi - lo) * (sample / (sample + 1))))


# ── Main builder ──────────────────────────────────────────────────────────────

def generate_population(
    total_users: int = 1000,
    persona_override: Dict[PersonaType, float] = None,
    domestic_only: bool = False,
) -> PopulationProfile:
    """
    Generate a correlated synthetic population.

    Args:
        total_users: total number of synthetic users to create.
        persona_override: custom persona weight distribution (overrides defaults).
        domestic_only: if True, all users placed in Indian cities.

    Returns:
        PopulationProfile with .users list populated.
    """
    weights = persona_override or POPULATION_WEIGHTS
    persona_types = list(weights.keys())
    persona_weights = list(weights.values())

    # Normalise weights
    w_sum = sum(persona_weights)
    persona_weights = [w / w_sum for w in persona_weights]

    # Assign persona type to each user
    assigned_types = random.choices(persona_types, weights=persona_weights, k=total_users)

    # Count distribution
    persona_counts: Dict[str, int] = {}
    for pt in assigned_types:
        persona_counts[pt.value] = persona_counts.get(pt.value, 0) + 1

    users: List[Dict] = []
    incomes: List[float] = []
    device_type_counts: Dict[str, int] = {"mobile": 0, "desktop": 0, "tablet": 0}
    total_devices = 0
    multi_device_users = 0
    city_counts: Dict[str, Dict] = {}
    country_counts: Dict[str, int] = {}
    merchant_cat_counts: Dict[str, int] = {}
    high_risk_count = 0

    for pt in assigned_types:
        persona_def = PERSONA_DEFINITIONS[pt]

        # City assignment
        if domestic_only or pt in (
            PersonaType.student, PersonaType.senior_citizen,
            PersonaType.gig_worker, PersonaType.salaried_employee,
        ):
            city_data = _weighted_city()
        else:
            # Some traveler/HNI/business users start from Tier-1 cities
            city_data = random.choices(
                DOMESTIC_CITIES,
                weights=[_CITY_TIER_WEIGHTS.get(c.get("tier", 3), 0.10) for c in DOMESTIC_CITIES],
            )[0]

        city_key = city_data["city"]
        if city_key not in city_counts:
            city_counts[city_key] = {"city": city_key, "country": city_data["country"], "user_count": 0}
        city_counts[city_key]["user_count"] += 1

        country = city_data["country"]
        country_counts[country] = country_counts.get(country, 0) + 1

        # Create user
        user = create_persona_user(pt, home_city=city_key, home_country=country)
        income = _income_for_persona(pt)
        user["metadata"]["monthly_income"] = round(income)
        incomes.append(income)

        # Device stats
        n_devices = user["metadata"]["device_count"]
        total_devices += n_devices
        if n_devices > 1:
            multi_device_users += 1
        dt_weights = persona_def.device_type_weights
        for dt, w in dt_weights.items():
            device_type_counts[dt] = device_type_counts.get(dt, 0) + round(w * n_devices)

        # Merchant preferences
        for cat in persona_def.preferred_merchants[:3]:
            merchant_cat_counts[cat] = merchant_cat_counts.get(cat, 0) + 1

        # Risk flag
        if persona_def.risk_baseline > 0.20:
            high_risk_count += 1

        users.append(user)

    # Sort incomes for percentiles
    sorted_incomes = sorted(incomes)
    n = len(sorted_incomes)

    def pct(p: float) -> float:
        idx = max(0, min(n - 1, int(p * n)))
        return round(sorted_incomes[idx])

    # Top cities
    top_cities = sorted(city_counts.values(), key=lambda x: -x["user_count"])[:10]

    # Device distribution
    total_dt = sum(device_type_counts.values()) or 1
    device_dist = {k: round(v / total_dt, 3) for k, v in device_type_counts.items()}

    # International pct
    intl_travelers = sum(
        1 for u in users
        if u["metadata"]["persona_type"] in (
            PersonaType.frequent_traveler.value,
            PersonaType.business_owner.value,
            PersonaType.high_net_worth.value,
        )
    )

    # Top merchant categories
    top_cats = sorted(merchant_cat_counts.items(), key=lambda x: -x[1])[:8]

    # Estimated baseline fraud rate
    high_risk_pct = round(high_risk_count / total_users, 3)
    estimated_fraud_rate = round(high_risk_pct * 0.15 + 0.02, 3)  # floor 2%

    return PopulationProfile(
        population_id=f"pop_{uuid.uuid4().hex[:10]}",
        total_users=total_users,
        persona_distribution=persona_counts,
        persona_distribution_pct={k: round(v / total_users, 3) for k, v in persona_counts.items()},
        income_p25=pct(0.25),
        income_median=pct(0.50),
        income_p75=pct(0.75),
        income_p95=pct(0.95),
        top_cities=top_cities,
        country_distribution=country_counts,
        international_user_pct=round(intl_travelers / total_users, 3),
        device_type_distribution=device_dist,
        avg_devices_per_user=round(total_devices / total_users, 2),
        multi_device_pct=round(multi_device_users / total_users, 3),
        top_merchant_categories=[c for c, _ in top_cats],
        high_risk_persona_pct=high_risk_pct,
        estimated_fraud_rate=estimated_fraud_rate,
        users=users,
    )


def population_to_dict(pop: PopulationProfile) -> Dict[str, Any]:
    """Serializable summary (without full user list)."""
    return {
        "population_id": pop.population_id,
        "total_users": pop.total_users,
        "persona_distribution": pop.persona_distribution,
        "persona_distribution_pct": pop.persona_distribution_pct,
        "income": {
            "p25": pop.income_p25,
            "median": pop.income_median,
            "p75": pop.income_p75,
            "p95": pop.income_p95,
        },
        "top_cities": pop.top_cities,
        "country_distribution": pop.country_distribution,
        "international_user_pct": pop.international_user_pct,
        "device_type_distribution": pop.device_type_distribution,
        "avg_devices_per_user": pop.avg_devices_per_user,
        "multi_device_pct": pop.multi_device_pct,
        "top_merchant_categories": pop.top_merchant_categories,
        "high_risk_persona_pct": pop.high_risk_persona_pct,
        "estimated_fraud_rate": pop.estimated_fraud_rate,
    }
