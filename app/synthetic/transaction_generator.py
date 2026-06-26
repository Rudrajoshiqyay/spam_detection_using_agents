"""
Transaction Generator — produces realistic transaction streams.

Supports:
  - Single transaction generation
  - Batch generation (JSON / JSONL)
  - Continuous stream simulation
  - Time-series generation (respects behavioral time-of-day patterns)
"""

import math
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from app.models.transaction import Transaction
from app.models.user_profile import UserProfile
from app.synthetic.merchant_generator import generate_merchant_pool, _MERCHANT_TEMPLATES
from app.synthetic.device_generator import generate_device
from app.synthetic.geo_generator import generate_location


# Module-level merchant pool (shared across calls for referential integrity)
_MERCHANT_POOL: List[Dict] = []


def _get_merchant_pool() -> List[Dict]:
    global _MERCHANT_POOL
    if not _MERCHANT_POOL:
        _MERCHANT_POOL = generate_merchant_pool(60)
    return _MERCHANT_POOL


def _log_normal_amount(mean: float, std: float) -> float:
    """Sample from log-normal distribution for realistic transaction amounts."""
    sigma = math.sqrt(math.log(1 + (std / mean) ** 2))
    mu = math.log(mean) - sigma ** 2 / 2
    return max(1.0, round(random.lognormvariate(mu, sigma), 2))


def _pick_merchant(profile: UserProfile) -> Dict:
    pool = _get_merchant_pool()
    preferred = profile.spending_profile.preferred_categories

    # Weight merchants by category match
    weights = []
    for m in pool:
        cat = m["merchant_category"]
        match = any(p in cat or cat in p for p in preferred)
        weights.append(3.0 if match else 1.0)

    return random.choices(pool, weights=weights)[0]


def _pick_hour(profile: UserProfile) -> int:
    typical = profile.spending_profile.typical_transaction_hours
    if typical and random.random() < 0.80:
        return random.choice(typical)
    return random.randint(0, 23)


def generate_transaction(
    profile: UserProfile,
    home_city: str = "Mumbai",
    base_timestamp: datetime = None,
    geo_mode: str = "normal",
    amount_override: float = None,
    merchant_override: Dict = None,
    device_override: str = None,
) -> Transaction:
    if base_timestamp is None:
        base_timestamp = datetime.now(timezone.utc)

    # Merchant
    merchant = merchant_override or _pick_merchant(profile)

    # Amount (log-normal around user's average)
    if amount_override is not None:
        amount = amount_override
    else:
        sp = profile.spending_profile
        amount = _log_normal_amount(sp.avg_transaction_amount, sp.avg_transaction_amount * 0.6)
        amount = min(amount, sp.max_transaction_amount)

    # Device
    if device_override:
        device_id = device_override
        device_type = "mobile"
    else:
        # 85% known device, 15% new
        if profile.known_devices and random.random() < 0.85:
            device_id = random.choice(profile.known_devices)
            device_type = "mobile"
        else:
            dev = generate_device("new")
            device_id = dev["device_id"]
            device_type = dev["device_type"]

    # Location
    geo = generate_location(home_city=home_city, mode=geo_mode)

    # Timestamp — pick realistic hour
    hour = _pick_hour(profile)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    timestamp = base_timestamp.replace(hour=hour, minute=minute, second=second, microsecond=0)

    return Transaction(
        transaction_id=f"txn_{uuid.uuid4().hex[:12]}",
        user_id=profile.user_id,
        amount=amount,
        currency="INR",
        merchant_id=merchant["merchant_id"],
        merchant_name=merchant["merchant_name"],
        merchant_category=merchant["merchant_category"],
        device_id=device_id,
        device_type=device_type,
        ip_address=f"103.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
        latitude=geo["lat"],
        longitude=geo["lon"],
        location_city=geo["city"],
        location_country=geo["country"],
        timestamp=timestamp,
        transaction_type="purchase",
        channel="online" if merchant.get("is_online") else random.choice(["online", "in-store"]),
        is_international=geo["is_international"],
        card_present=not merchant.get("is_online", False),
    )


def generate_transaction_batch(
    profiles: List[UserProfile],
    count: int,
    fraud_rate: float = 0.0,
    start_date: datetime = None,
    span_days: int = 7,
) -> List[Dict[str, Any]]:
    """Generate a batch of transactions across multiple users over a time span."""
    if start_date is None:
        start_date = datetime.now(timezone.utc) - timedelta(days=span_days)

    results = []
    for i in range(count):
        profile = random.choice(profiles)
        # Random timestamp within span
        offset_seconds = random.randint(0, span_days * 86400)
        ts = start_date + timedelta(seconds=offset_seconds)

        txn = generate_transaction(profile, base_timestamp=ts)
        results.append({
            "transaction": txn.model_dump(mode="json"),
            "user_id": profile.user_id,
            "is_fraud": False,
            "fraud_type": None,
        })

    return results


def transactions_to_jsonl(transactions: List[Dict[str, Any]]) -> str:
    """Serialize transaction batch to JSONL format."""
    import json
    lines = []
    for t in transactions:
        lines.append(json.dumps(t, default=str))
    return "\n".join(lines)
