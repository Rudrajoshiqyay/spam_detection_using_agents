from pydantic import BaseModel, ConfigDict, Field
from typing import Dict, Any
from datetime import datetime, timezone
from enum import Enum


class DeviceType(str, Enum):
    mobile = "mobile"
    desktop = "desktop"
    tablet = "tablet"
    pos = "pos"


class TransactionType(str, Enum):
    purchase = "purchase"
    refund = "refund"
    transfer = "transfer"
    withdrawal = "withdrawal"


class Channel(str, Enum):
    online = "online"
    in_store = "in-store"
    atm = "atm"


class Transaction(BaseModel):
    # use_enum_values stores the underlying str so plain-string inputs serialize cleanly
    model_config = ConfigDict(use_enum_values=True)

    transaction_id: str
    user_id: str
    amount: float = Field(gt=0)
    currency: str = "INR"
    merchant_id: str
    merchant_name: str
    merchant_category: str
    device_id: str
    device_type: DeviceType = DeviceType.mobile
    ip_address: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    location_city: str
    location_country: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    transaction_type: TransactionType = TransactionType.purchase
    channel: Channel = Channel.online
    is_international: bool = False
    card_present: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
