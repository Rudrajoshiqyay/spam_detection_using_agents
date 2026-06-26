from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from enum import Enum


class UserType(str, Enum):
    student = "student"
    working_professional = "working_professional"
    traveler = "traveler"
    business_owner = "business_owner"
    retired = "retired"
    high_net_worth = "high_net_worth"
    high_risk = "high_risk"


class RiskCategory(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class TravelFrequency(str, Enum):
    rare = "rare"
    occasional = "occasional"
    frequent = "frequent"
    very_frequent = "very_frequent"


class AccountStatus(str, Enum):
    active = "active"
    suspended = "suspended"
    frozen = "frozen"
    closed = "closed"


class SpendingProfile(BaseModel):
    avg_transaction_amount: float = Field(ge=0)
    max_transaction_amount: float = Field(ge=0)
    monthly_spend_limit: float = Field(ge=0)
    preferred_categories: List[str] = []
    typical_transaction_hours: List[int] = []   # hours of day (0-23)

    @field_validator("typical_transaction_hours")
    @classmethod
    def validate_hours(cls, v: List[int]) -> List[int]:
        for h in v:
            if not (0 <= h <= 23):
                raise ValueError(f"Transaction hour {h} must be 0–23")
        return v


class TravelProfile(BaseModel):
    frequent_countries: List[str] = []
    frequent_cities: List[str] = []
    travel_frequency: TravelFrequency = TravelFrequency.rare
    avg_trip_duration_days: float = Field(default=0, ge=0)


class AdaptiveThresholds(BaseModel):
    amount_multiplier: float = Field(default=3.0, gt=0)
    velocity_window_minutes: int = Field(default=60, gt=0)
    max_txn_per_hour: int = Field(default=5, gt=0)
    geo_change_tolerance_km: float = Field(default=100, ge=0)
    new_device_risk_weight: float = Field(default=0.3, ge=0, le=1)
    new_merchant_risk_weight: float = Field(default=0.15, ge=0, le=1)


class UserProfile(BaseModel):
    user_id: str
    user_type: UserType
    risk_category: RiskCategory
    spending_profile: SpendingProfile
    travel_profile: TravelProfile
    thresholds: AdaptiveThresholds
    known_devices: List[str] = []
    known_locations: List[str] = []     # "city:country" format
    account_age_days: int = Field(default=365, ge=0)
    total_transactions: int = Field(default=0, ge=0)
    fraud_history: bool = False
    account_status: AccountStatus = AccountStatus.active
