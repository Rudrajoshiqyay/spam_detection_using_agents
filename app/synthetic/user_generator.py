"""
User Generator — produces realistic synthetic banking users.

Outputs UserProfile-compatible objects plus demographic metadata.
All distributions are grounded in Indian banking demographics (INR ecosystem).
"""

import random
import uuid
from typing import List, Dict, Any

from app.models.user_profile import (
    UserProfile, UserType, RiskCategory,
    SpendingProfile, TravelProfile, AdaptiveThresholds,
)


# ------------------------------------------------------------------
# Static pools
# ------------------------------------------------------------------

_CITIES = [
    ("Mumbai", "India", 19.076, 72.878),
    ("Delhi", "India", 28.704, 77.102),
    ("Bangalore", "India", 12.972, 77.594),
    ("Pune", "India", 18.520, 73.856),
    ("Chennai", "India", 13.083, 80.270),
    ("Hyderabad", "India", 17.387, 78.491),
    ("Kolkata", "India", 22.573, 88.364),
    ("Ahmedabad", "India", 23.033, 72.585),
    ("Jaipur", "India", 26.912, 75.787),
    ("Surat", "India", 21.170, 72.831),
]

_INTL_CITIES = [
    ("Dubai", "UAE"), ("London", "UK"), ("Singapore", "Singapore"),
    ("New York", "USA"), ("Bangkok", "Thailand"), ("Kuala Lumpur", "Malaysia"),
]

_USER_TYPE_WEIGHTS = {
    UserType.student: 0.22,
    UserType.working_professional: 0.40,
    UserType.traveler: 0.12,
    UserType.business_owner: 0.10,
    UserType.retired: 0.08,
    UserType.high_net_worth: 0.05,
    UserType.high_risk: 0.03,
}

# (avg_amount, std_amount, max_amount, monthly_limit)
_SPEND_PARAMS: Dict[UserType, tuple] = {
    UserType.student:              (400,   300,   3000,    10000),
    UserType.working_professional: (1800,  1500,  30000,   80000),
    UserType.traveler:             (5000,  6000,  80000,   250000),
    UserType.business_owner:       (18000, 25000, 500000,  2000000),
    UserType.retired:              (900,   600,   8000,    20000),
    UserType.high_net_worth:       (50000, 80000, 5000000, 10000000),
    UserType.high_risk:            (700,   500,   5000,    15000),
}

_PREFERRED_CATEGORIES: Dict[UserType, List[str]] = {
    UserType.student:              ["food", "education", "entertainment", "clothing", "transport"],
    UserType.working_professional: ["restaurants", "groceries", "transport", "clothing", "electronics"],
    UserType.traveler:             ["airlines", "hotels", "restaurants", "entertainment", "shopping"],
    UserType.business_owner:       ["wholesale", "suppliers", "travel", "restaurants", "technology"],
    UserType.retired:              ["groceries", "medical", "utilities", "restaurants", "clothing"],
    UserType.high_net_worth:       ["luxury", "travel", "fine_dining", "investments", "real_estate"],
    UserType.high_risk:            ["gambling", "cash_advance", "electronics", "gaming"],
}

_TYPICAL_HOURS: Dict[UserType, List[int]] = {
    UserType.student:              [10, 11, 12, 13, 14, 18, 19, 20, 21],
    UserType.working_professional: [8, 9, 12, 13, 18, 19, 20, 21],
    UserType.traveler:             [7, 8, 9, 10, 12, 13, 17, 18, 19, 20, 21, 22],
    UserType.business_owner:       [9, 10, 11, 12, 14, 15, 16, 17],
    UserType.retired:              [9, 10, 11, 12, 14, 15, 16],
    UserType.high_net_worth:       [10, 11, 12, 14, 15, 16, 19, 20],
    UserType.high_risk:            [0, 1, 2, 3, 22, 23],
}

_THRESHOLDS: Dict[UserType, Dict] = {
    UserType.student:              {"amount_multiplier": 4.0, "max_txn_per_hour": 4,  "geo_change_tolerance_km": 50,   "new_device_risk_weight": 0.35, "new_merchant_risk_weight": 0.10},
    UserType.working_professional: {"amount_multiplier": 4.5, "max_txn_per_hour": 6,  "geo_change_tolerance_km": 100,  "new_device_risk_weight": 0.30, "new_merchant_risk_weight": 0.12},
    UserType.traveler:             {"amount_multiplier": 5.0, "max_txn_per_hour": 8,  "geo_change_tolerance_km": 5000, "new_device_risk_weight": 0.15, "new_merchant_risk_weight": 0.08},
    UserType.business_owner:       {"amount_multiplier": 6.0, "max_txn_per_hour": 15, "geo_change_tolerance_km": 500,  "new_device_risk_weight": 0.25, "new_merchant_risk_weight": 0.12},
    UserType.retired:              {"amount_multiplier": 3.0, "max_txn_per_hour": 3,  "geo_change_tolerance_km": 30,   "new_device_risk_weight": 0.40, "new_merchant_risk_weight": 0.15},
    UserType.high_net_worth:       {"amount_multiplier": 8.0, "max_txn_per_hour": 10, "geo_change_tolerance_km": 8000, "new_device_risk_weight": 0.20, "new_merchant_risk_weight": 0.10},
    UserType.high_risk:            {"amount_multiplier": 2.0, "max_txn_per_hour": 3,  "geo_change_tolerance_km": 30,   "new_device_risk_weight": 0.50, "new_merchant_risk_weight": 0.30},
}


def generate_user(user_type: UserType = None, seed: int = None) -> Dict[str, Any]:
    """Generate a single synthetic user. Returns both UserProfile and demographic metadata."""
    if seed is not None:
        random.seed(seed)

    if user_type is None:
        user_type = random.choices(
            list(_USER_TYPE_WEIGHTS.keys()),
            weights=list(_USER_TYPE_WEIGHTS.values()),
        )[0]

    user_id = f"syn_{user_type.value}_{uuid.uuid4().hex[:8]}"

    # Home location
    home_city, home_country, home_lat, home_lon = random.choice(_CITIES)

    # Spend params
    avg_amt, std_amt, max_amt, monthly_limit = _SPEND_PARAMS[user_type]
    # Add natural variation
    avg_amt = round(avg_amt * random.uniform(0.6, 1.6))
    max_amt = round(max_amt * random.uniform(0.8, 1.3))

    # Known devices (1-4)
    device_count = random.randint(1, 4)
    known_devices = [f"dev_{uuid.uuid4().hex[:8]}" for _ in range(device_count)]

    # Known locations
    known_locations = [f"{home_city}:{home_country}"]
    if user_type in (UserType.traveler, UserType.business_owner, UserType.high_net_worth):
        extra = random.sample(_INTL_CITIES, k=random.randint(1, 3))
        known_locations += [f"{c}:{co}" for c, co in extra]

    # Travel profile
    travel_freq_map = {
        UserType.student: "rare",
        UserType.working_professional: "occasional",
        UserType.traveler: "very_frequent",
        UserType.business_owner: "occasional",
        UserType.retired: "rare",
        UserType.high_net_worth: "frequent",
        UserType.high_risk: "rare",
    }
    freq_countries = [home_country]
    if user_type in (UserType.traveler, UserType.high_net_worth):
        freq_countries += [co for _, co in random.sample(_INTL_CITIES, k=3)]

    risk_cat = {
        UserType.student: RiskCategory.low,
        UserType.working_professional: RiskCategory.low,
        UserType.traveler: RiskCategory.medium,
        UserType.business_owner: RiskCategory.medium,
        UserType.retired: RiskCategory.low,
        UserType.high_net_worth: RiskCategory.low,
        UserType.high_risk: RiskCategory.high,
    }[user_type]

    thresholds_data = _THRESHOLDS[user_type]
    profile = UserProfile(
        user_id=user_id,
        user_type=user_type,
        risk_category=risk_cat,
        spending_profile=SpendingProfile(
            avg_transaction_amount=avg_amt,
            max_transaction_amount=max_amt,
            monthly_spend_limit=monthly_limit,
            preferred_categories=_PREFERRED_CATEGORIES[user_type],
            typical_transaction_hours=_TYPICAL_HOURS[user_type],
        ),
        travel_profile=TravelProfile(
            frequent_countries=freq_countries,
            frequent_cities=[home_city],
            travel_frequency=travel_freq_map[user_type],
            avg_trip_duration_days=random.uniform(0, 10),
        ),
        thresholds=AdaptiveThresholds(
            amount_multiplier=thresholds_data["amount_multiplier"],
            velocity_window_minutes=60,
            max_txn_per_hour=thresholds_data["max_txn_per_hour"],
            geo_change_tolerance_km=thresholds_data["geo_change_tolerance_km"],
            new_device_risk_weight=thresholds_data["new_device_risk_weight"],
            new_merchant_risk_weight=thresholds_data["new_merchant_risk_weight"],
        ),
        known_devices=known_devices,
        known_locations=known_locations,
        account_age_days=random.randint(30, 3650),
        total_transactions=random.randint(5, 5000),
        fraud_history=user_type == UserType.high_risk and random.random() < 0.4,
    )

    return {
        "profile": profile,
        "metadata": {
            "user_id": user_id,
            "user_type": user_type.value,
            "home_city": home_city,
            "home_country": home_country,
            "home_lat": home_lat,
            "home_lon": home_lon,
            "avg_amount": avg_amt,
            "device_count": device_count,
        },
    }


def generate_user_batch(count: int, user_type: UserType = None) -> List[Dict[str, Any]]:
    return [generate_user(user_type) for _ in range(count)]
