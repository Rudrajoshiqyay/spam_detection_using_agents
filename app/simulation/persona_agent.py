"""
Persona Agent — generates rich behavioral personas for synthetic users.

8 persona types, each with distinct spending, timing, device, and travel patterns.
Outputs UserProfile-compatible objects with full behavioral characteristics.
"""

import random
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Tuple

from app.models.user_profile import (
    UserProfile, UserType, RiskCategory,
    SpendingProfile, TravelProfile, AdaptiveThresholds,
)


class PersonaType(str, Enum):
    student             = "student"
    salaried_employee   = "salaried_employee"
    business_owner      = "business_owner"
    frequent_traveler   = "frequent_traveler"
    senior_citizen      = "senior_citizen"
    gig_worker          = "gig_worker"
    high_net_worth      = "high_net_worth"
    crypto_trader       = "crypto_trader"


@dataclass
class PersonaProfile:
    persona_type: PersonaType
    income_range: Tuple[int, int]           # (min_monthly_INR, max_monthly_INR)
    avg_txn_amount: float
    std_txn_amount: float
    max_txn_amount: float
    monthly_limit: float
    active_hours: List[int]                 # hours of day when active (0-23)
    txn_per_day: float                      # average transactions per day
    preferred_merchants: List[str]          # merchant categories
    payment_methods: List[str]              # upi, credit_card, debit_card, netbanking, cash
    travel_frequency: str                   # rare/occasional/frequent/very_frequent
    frequent_countries: List[str]
    device_count_range: Tuple[int, int]
    device_type_weights: Dict[str, float]   # mobile/desktop/tablet weights
    risk_baseline: float                    # 0-1 inherent risk
    salary_day: int                         # day of month salary credited (0 = none)
    weekend_multiplier: float               # spending multiplier on weekends
    night_activity: bool                    # active after midnight?
    cohort_name: str


# ── Persona Definitions ──────────────────────────────────────────────────────

PERSONA_DEFINITIONS: Dict[PersonaType, PersonaProfile] = {

    PersonaType.student: PersonaProfile(
        persona_type=PersonaType.student,
        income_range=(5_000, 15_000),
        avg_txn_amount=350,
        std_txn_amount=280,
        max_txn_amount=3_000,
        monthly_limit=8_000,
        active_hours=[10, 11, 12, 13, 18, 19, 20, 21, 22, 23],
        txn_per_day=2.1,
        preferred_merchants=["food_delivery", "grocery", "entertainment", "education", "clothing", "transport"],
        payment_methods=["upi", "debit_card"],
        travel_frequency="rare",
        frequent_countries=["India"],
        device_count_range=(1, 2),
        device_type_weights={"mobile": 0.90, "desktop": 0.08, "tablet": 0.02},
        risk_baseline=0.10,
        salary_day=0,
        weekend_multiplier=1.5,
        night_activity=True,
        cohort_name="student",
    ),

    PersonaType.salaried_employee: PersonaProfile(
        persona_type=PersonaType.salaried_employee,
        income_range=(25_000, 100_000),
        avg_txn_amount=1_800,
        std_txn_amount=1_500,
        max_txn_amount=30_000,
        monthly_limit=80_000,
        active_hours=[8, 9, 12, 13, 18, 19, 20, 21],
        txn_per_day=3.2,
        preferred_merchants=["restaurants", "grocery", "transport", "clothing", "electronics", "utilities"],
        payment_methods=["upi", "credit_card", "debit_card"],
        travel_frequency="occasional",
        frequent_countries=["India"],
        device_count_range=(1, 3),
        device_type_weights={"mobile": 0.75, "desktop": 0.20, "tablet": 0.05},
        risk_baseline=0.08,
        salary_day=1,
        weekend_multiplier=1.8,
        night_activity=False,
        cohort_name="working_professional",
    ),

    PersonaType.business_owner: PersonaProfile(
        persona_type=PersonaType.business_owner,
        income_range=(150_000, 1_000_000),
        avg_txn_amount=18_000,
        std_txn_amount=25_000,
        max_txn_amount=500_000,
        monthly_limit=2_000_000,
        active_hours=[9, 10, 11, 12, 14, 15, 16, 17],
        txn_per_day=5.8,
        preferred_merchants=["wholesale", "b2b_suppliers", "travel", "restaurants", "technology", "wire_transfer"],
        payment_methods=["netbanking", "credit_card", "wire_transfer"],
        travel_frequency="occasional",
        frequent_countries=["India", "UAE", "Singapore"],
        device_count_range=(2, 5),
        device_type_weights={"mobile": 0.50, "desktop": 0.45, "tablet": 0.05},
        risk_baseline=0.15,
        salary_day=0,
        weekend_multiplier=0.6,
        night_activity=False,
        cohort_name="business_owner",
    ),

    PersonaType.frequent_traveler: PersonaProfile(
        persona_type=PersonaType.frequent_traveler,
        income_range=(80_000, 500_000),
        avg_txn_amount=5_000,
        std_txn_amount=6_000,
        max_txn_amount=80_000,
        monthly_limit=250_000,
        active_hours=[7, 8, 9, 10, 12, 13, 17, 18, 19, 20, 21, 22],
        txn_per_day=4.5,
        preferred_merchants=["airlines", "hotels", "restaurants", "entertainment", "luxury", "transport"],
        payment_methods=["credit_card", "upi"],
        travel_frequency="very_frequent",
        frequent_countries=["India", "UAE", "UK", "USA", "Singapore", "Thailand", "France"],
        device_count_range=(2, 4),
        device_type_weights={"mobile": 0.80, "desktop": 0.15, "tablet": 0.05},
        risk_baseline=0.12,
        salary_day=0,
        weekend_multiplier=2.0,
        night_activity=True,
        cohort_name="traveler",
    ),

    PersonaType.senior_citizen: PersonaProfile(
        persona_type=PersonaType.senior_citizen,
        income_range=(10_000, 40_000),
        avg_txn_amount=900,
        std_txn_amount=500,
        max_txn_amount=8_000,
        monthly_limit=20_000,
        active_hours=[9, 10, 11, 12, 14, 15, 16],
        txn_per_day=1.4,
        preferred_merchants=["grocery", "medical", "utilities", "restaurants", "clothing"],
        payment_methods=["debit_card", "netbanking", "upi"],
        travel_frequency="rare",
        frequent_countries=["India"],
        device_count_range=(1, 2),
        device_type_weights={"mobile": 0.55, "desktop": 0.40, "tablet": 0.05},
        risk_baseline=0.05,
        salary_day=0,
        weekend_multiplier=1.1,
        night_activity=False,
        cohort_name="retired",
    ),

    PersonaType.gig_worker: PersonaProfile(
        persona_type=PersonaType.gig_worker,
        income_range=(8_000, 35_000),
        avg_txn_amount=500,
        std_txn_amount=400,
        max_txn_amount=5_000,
        monthly_limit=15_000,
        active_hours=[7, 8, 9, 12, 13, 17, 18, 19, 20, 21, 22],
        txn_per_day=2.8,
        preferred_merchants=["fuel", "food_delivery", "grocery", "mobile_recharge", "transport"],
        payment_methods=["upi", "debit_card"],
        travel_frequency="occasional",
        frequent_countries=["India"],
        device_count_range=(1, 2),
        device_type_weights={"mobile": 0.95, "desktop": 0.04, "tablet": 0.01},
        risk_baseline=0.12,
        salary_day=0,
        weekend_multiplier=1.3,
        night_activity=True,
        cohort_name="gig_worker",
    ),

    PersonaType.high_net_worth: PersonaProfile(
        persona_type=PersonaType.high_net_worth,
        income_range=(500_000, 10_000_000),
        avg_txn_amount=50_000,
        std_txn_amount=80_000,
        max_txn_amount=5_000_000,
        monthly_limit=10_000_000,
        active_hours=[10, 11, 12, 14, 15, 16, 19, 20],
        txn_per_day=3.0,
        preferred_merchants=["luxury", "fine_dining", "travel", "investments", "art", "real_estate", "jewelry"],
        payment_methods=["credit_card", "wire_transfer", "netbanking"],
        travel_frequency="frequent",
        frequent_countries=["India", "UAE", "UK", "France", "Switzerland", "USA"],
        device_count_range=(2, 6),
        device_type_weights={"mobile": 0.60, "desktop": 0.30, "tablet": 0.10},
        risk_baseline=0.10,
        salary_day=0,
        weekend_multiplier=1.6,
        night_activity=False,
        cohort_name="high_net_worth",
    ),

    PersonaType.crypto_trader: PersonaProfile(
        persona_type=PersonaType.crypto_trader,
        income_range=(20_000, 500_000),
        avg_txn_amount=8_000,
        std_txn_amount=15_000,
        max_txn_amount=200_000,
        monthly_limit=500_000,
        active_hours=[0, 1, 2, 8, 9, 10, 14, 15, 20, 21, 22, 23],
        txn_per_day=6.5,
        preferred_merchants=["cryptocurrency", "gaming", "electronics", "food_delivery", "streaming"],
        payment_methods=["credit_card", "upi", "wire_transfer"],
        travel_frequency="occasional",
        frequent_countries=["India", "Singapore", "UAE"],
        device_count_range=(2, 5),
        device_type_weights={"mobile": 0.55, "desktop": 0.40, "tablet": 0.05},
        risk_baseline=0.35,
        salary_day=0,
        weekend_multiplier=1.2,
        night_activity=True,
        cohort_name="crypto_trader",
    ),
}

# Map PersonaType → UserType for compatibility with existing pipeline
_PERSONA_TO_USER_TYPE: Dict[PersonaType, UserType] = {
    PersonaType.student:           UserType.student,
    PersonaType.salaried_employee: UserType.working_professional,
    PersonaType.business_owner:    UserType.business_owner,
    PersonaType.frequent_traveler: UserType.traveler,
    PersonaType.senior_citizen:    UserType.retired,
    PersonaType.gig_worker:        UserType.working_professional,
    PersonaType.high_net_worth:    UserType.high_net_worth,
    PersonaType.crypto_trader:     UserType.high_risk,
}

_PERSONA_TO_RISK: Dict[PersonaType, RiskCategory] = {
    PersonaType.student:           RiskCategory.low,
    PersonaType.salaried_employee: RiskCategory.low,
    PersonaType.business_owner:    RiskCategory.medium,
    PersonaType.frequent_traveler: RiskCategory.medium,
    PersonaType.senior_citizen:    RiskCategory.low,
    PersonaType.gig_worker:        RiskCategory.low,
    PersonaType.high_net_worth:    RiskCategory.low,
    PersonaType.crypto_trader:     RiskCategory.high,
}

# Population distribution weights
_PERSONA_WEIGHTS = {
    PersonaType.student:           0.18,
    PersonaType.salaried_employee: 0.35,
    PersonaType.business_owner:    0.10,
    PersonaType.frequent_traveler: 0.10,
    PersonaType.senior_citizen:    0.10,
    PersonaType.gig_worker:        0.10,
    PersonaType.high_net_worth:    0.04,
    PersonaType.crypto_trader:     0.03,
}


def create_persona_user(
    persona_type: PersonaType = None,
    home_city: str = None,
    home_country: str = "India",
) -> Dict[str, Any]:
    """Generate a single user from a persona definition."""
    from app.simulation.world_builder import WORLD_CITIES

    if persona_type is None:
        persona_type = random.choices(
            list(_PERSONA_WEIGHTS.keys()),
            weights=list(_PERSONA_WEIGHTS.values()),
        )[0]

    persona = PERSONA_DEFINITIONS[persona_type]

    # Home location
    if home_city is None:
        domestic = [c for c in WORLD_CITIES if c["country"] == "India"]
        chosen = random.choice(domestic)
        home_city = chosen["city"]
        home_lat, home_lon = chosen["lat"], chosen["lon"]
    else:
        city_data = next((c for c in WORLD_CITIES if c["city"] == home_city), None)
        home_lat = city_data["lat"] if city_data else 19.076
        home_lon = city_data["lon"] if city_data else 72.878

    # Amount variation per user (±30%)
    scale = random.uniform(0.7, 1.3)
    avg_amt = round(persona.avg_txn_amount * scale)
    max_amt = round(persona.max_txn_amount * random.uniform(0.8, 1.2))

    # Devices
    device_count = random.randint(*persona.device_count_range)
    known_devices = [f"dev_{uuid.uuid4().hex[:10]}" for _ in range(device_count)]

    # Known locations
    known_locations = [f"{home_city}:{home_country}"]
    if persona.travel_frequency in ("frequent", "very_frequent"):
        extra_countries = random.sample(
            [c for c in persona.frequent_countries if c != home_country],
            k=min(3, len([c for c in persona.frequent_countries if c != home_country]))
        )
        for country in extra_countries:
            intl_cities = [c for c in WORLD_CITIES if c["country"] == country]
            if intl_cities:
                city = random.choice(intl_cities)
                known_locations.append(f"{city['city']}:{country}")

    user_id = f"persona_{persona_type.value}_{uuid.uuid4().hex[:8]}"

    profile = UserProfile(
        user_id=user_id,
        user_type=_PERSONA_TO_USER_TYPE[persona_type],
        risk_category=_PERSONA_TO_RISK[persona_type],
        spending_profile=SpendingProfile(
            avg_transaction_amount=avg_amt,
            max_transaction_amount=max_amt,
            monthly_spend_limit=persona.monthly_limit,
            preferred_categories=persona.preferred_merchants,
            typical_transaction_hours=persona.active_hours,
        ),
        travel_profile=TravelProfile(
            frequent_countries=persona.frequent_countries,
            frequent_cities=[home_city],
            travel_frequency=persona.travel_frequency,
            avg_trip_duration_days=random.uniform(1, 14) if persona.travel_frequency != "rare" else 0,
        ),
        thresholds=AdaptiveThresholds(
            amount_multiplier=max_amt / max(avg_amt, 1),
            velocity_window_minutes=60,
            max_txn_per_hour=max(3, int(persona.txn_per_day * 0.5)),
            geo_change_tolerance_km=5000 if persona.travel_frequency in ("frequent", "very_frequent") else 200,
            new_device_risk_weight=0.20 if persona.device_count_range[1] > 3 else 0.35,
            new_merchant_risk_weight=0.10,
        ),
        known_devices=known_devices,
        known_locations=known_locations,
        account_age_days=random.randint(30, 2500),
        total_transactions=random.randint(10, 5000),
        fraud_history=persona_type == PersonaType.crypto_trader and random.random() < 0.1,
    )

    return {
        "profile": profile,
        "persona": persona,
        "metadata": {
            "user_id": user_id,
            "persona_type": persona_type.value,
            "home_city": home_city,
            "home_country": home_country,
            "home_lat": home_lat,
            "home_lon": home_lon,
            "avg_amount": avg_amt,
            "max_amount": max_amt,
            "device_count": device_count,
            "txn_per_day": persona.txn_per_day,
            "salary_day": persona.salary_day,
            "risk_baseline": persona.risk_baseline,
            "cohort": persona.cohort_name,
        },
    }


def create_persona_batch(
    count: int,
    persona_type: PersonaType = None,
) -> List[Dict[str, Any]]:
    return [create_persona_user(persona_type) for _ in range(count)]
