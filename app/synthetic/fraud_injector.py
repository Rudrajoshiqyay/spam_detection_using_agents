"""
Fraud Injection Layer — transforms normal transactions into specific fraud scenarios.

Each injector function takes a Transaction + UserProfile and returns a modified
Transaction with fraud signals embedded, plus injection metadata.

Supported scenarios:
  account_takeover    — new device + new location + large transfer
  card_testing        — burst of micro-transactions then large purchase
  money_mule          — rapid incoming + outgoing transfers
  synthetic_identity  — fake profile + shared device signals
  velocity_attack     — high-frequency burst with escalating amounts
  merchant_abuse      — concentration at high-risk / chargeback-heavy merchant
"""

import uuid
import random
import copy
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple

from app.models.transaction import Transaction
from app.models.user_profile import UserProfile
from app.synthetic.device_generator import generate_device
from app.synthetic.geo_generator import generate_location, _CITY_DB
from app.synthetic.merchant_generator import generate_merchant


# ------------------------------------------------------------------
# 1. Account Takeover Injection
# ------------------------------------------------------------------

def inject_account_takeover(
    txn: Transaction,
    profile: UserProfile,
    target_amount_multiplier: float = 15.0,
) -> Tuple[Transaction, Dict]:
    injected = txn.model_copy(deep=True)
    avg = profile.spending_profile.avg_transaction_amount

    # New suspicious device
    bad_device = generate_device("suspicious")
    injected.device_id = bad_device["device_id"]
    injected.device_type = bad_device["device_type"]
    injected.ip_address = bad_device["ip_address"]

    # New unexpected location (international)
    geo = generate_location(mode="impossible", prev_city=txn.location_city, prev_timestamp=txn.timestamp)
    injected.location_city = geo["city"]
    injected.location_country = geo["country"]
    injected.latitude = geo["lat"]
    injected.longitude = geo["lon"]
    injected.is_international = geo["is_international"]

    # Inflated amount
    injected.amount = round(avg * target_amount_multiplier * random.uniform(0.8, 1.2), 2)
    injected.transaction_type = "transfer"
    injected.channel = "online"
    injected.card_present = False
    injected.merchant_id = f"mch_wire_{uuid.uuid4().hex[:6]}"
    injected.merchant_name = "International Wire Service"
    injected.merchant_category = "wire_transfer"

    return injected, {
        "fraud_type": "account_takeover",
        "injected_signals": ["new_device", "new_international_location", "large_amount", "wire_transfer"],
        "original_amount": txn.amount,
        "injected_amount": injected.amount,
    }


# ------------------------------------------------------------------
# 2. Card Testing Injection
# ------------------------------------------------------------------

def inject_card_testing_series(
    profile: UserProfile,
    base_timestamp: datetime = None,
    micro_count: int = 4,
) -> Tuple[List[Transaction], Dict]:
    if base_timestamp is None:
        base_timestamp = datetime.now(timezone.utc)

    # Use a single stolen card (new device, consistent IP)
    bad_device = generate_device("suspicious")
    geo = generate_location(mode="normal")
    merchant_online = generate_merchant("ecommerce")

    series = []
    # Micro-transactions (< 50 INR)
    for i in range(micro_count):
        ts = base_timestamp + timedelta(minutes=i * 3 + random.randint(0, 2))
        series.append(Transaction(
            transaction_id=f"txn_ct_{uuid.uuid4().hex[:10]}",
            user_id=profile.user_id,
            amount=random.uniform(1.0, 49.0),
            currency="INR",
            merchant_id=merchant_online["merchant_id"],
            merchant_name=merchant_online["merchant_name"],
            merchant_category=merchant_online["merchant_category"],
            device_id=bad_device["device_id"],
            device_type=bad_device["device_type"],
            ip_address=bad_device["ip_address"],
            latitude=geo["lat"],
            longitude=geo["lon"],
            location_city=geo["city"],
            location_country=geo["country"],
            timestamp=ts,
            transaction_type="purchase",
            channel="online",
            is_international=False,
            card_present=False,
        ))

    # Large purchase after testing
    merchant_big = generate_merchant("electronics")
    big_ts = base_timestamp + timedelta(minutes=micro_count * 3 + 5)
    avg = profile.spending_profile.avg_transaction_amount
    series.append(Transaction(
        transaction_id=f"txn_ct_big_{uuid.uuid4().hex[:8]}",
        user_id=profile.user_id,
        amount=round(avg * random.uniform(8, 15), 2),
        currency="INR",
        merchant_id=merchant_big["merchant_id"],
        merchant_name=merchant_big["merchant_name"],
        merchant_category=merchant_big.get("merchant_category", "electronics"),
        device_id=bad_device["device_id"],
        device_type=bad_device["device_type"],
        ip_address=bad_device["ip_address"],
        latitude=geo["lat"],
        longitude=geo["lon"],
        location_city=geo["city"],
        location_country=geo["country"],
        timestamp=big_ts,
        transaction_type="purchase",
        channel="online",
        is_international=False,
        card_present=False,
    ))

    return series, {
        "fraud_type": "card_testing",
        "micro_transaction_count": micro_count,
        "total_transactions": len(series),
        "injected_signals": ["micro_transactions", "rapid_succession", "new_device", "large_purchase_after_testing"],
    }


# ------------------------------------------------------------------
# 3. Money Mule Injection
# ------------------------------------------------------------------

def inject_money_mule(
    txn: Transaction,
    mule_profile: UserProfile,
    transfer_amount: float = None,
) -> Tuple[Transaction, Dict]:
    injected = txn.model_copy(deep=True)
    avg = mule_profile.spending_profile.avg_transaction_amount
    amount = transfer_amount or round(avg * random.uniform(20, 50), 2)

    injected.amount = amount
    injected.transaction_type = "transfer"
    injected.merchant_id = f"mch_p2p_{uuid.uuid4().hex[:6]}"
    injected.merchant_name = "P2P Transfer Service"
    injected.merchant_category = "wire_transfer"
    injected.channel = "online"

    return injected, {
        "fraud_type": "money_mule",
        "injected_signals": ["large_incoming_transfer", "immediate_outgoing_transfer", "account_age_new"],
        "transfer_amount": amount,
    }


# ------------------------------------------------------------------
# 4. Synthetic Identity Fraud Injection
# ------------------------------------------------------------------

def inject_synthetic_identity(
    txn: Transaction,
    shared_device_id: str = None,
) -> Tuple[Transaction, Dict]:
    injected = txn.model_copy(deep=True)

    # Use a shared device (multiple accounts using same device)
    injected.device_id = shared_device_id or f"dev_shared_{uuid.uuid4().hex[:8]}"
    injected.ip_address = f"45.{random.randint(0,100)}.{random.randint(0,255)}.{random.randint(1,254)}"

    return injected, {
        "fraud_type": "synthetic_identity",
        "injected_signals": ["shared_device", "shared_ip", "fake_profile"],
        "shared_device_id": injected.device_id,
    }


# ------------------------------------------------------------------
# 5. Velocity Attack Injection
# ------------------------------------------------------------------

def inject_velocity_attack(
    profile: UserProfile,
    base_timestamp: datetime = None,
    burst_count: int = 8,
) -> Tuple[List[Transaction], Dict]:
    if base_timestamp is None:
        base_timestamp = datetime.now(timezone.utc)

    device = generate_device("suspicious")
    geo = generate_location(mode="normal")
    avg = profile.spending_profile.avg_transaction_amount
    txns = []

    for i in range(burst_count):
        ts = base_timestamp + timedelta(minutes=i * random.uniform(2, 6))
        # Escalating amounts
        escalation = 1.0 + i * 0.4
        amount = round(avg * escalation * random.uniform(0.8, 1.2), 2)
        merchant = generate_merchant(random.choice(["ecommerce", "gaming", "gambling"]))

        txns.append(Transaction(
            transaction_id=f"txn_vel_{uuid.uuid4().hex[:10]}",
            user_id=profile.user_id,
            amount=amount,
            currency="INR",
            merchant_id=merchant["merchant_id"],
            merchant_name=merchant["merchant_name"],
            merchant_category=merchant["merchant_category"],
            device_id=device["device_id"],
            device_type=device["device_type"],
            ip_address=device["ip_address"],
            latitude=geo["lat"],
            longitude=geo["lon"],
            location_city=geo["city"],
            location_country=geo["country"],
            timestamp=ts,
            transaction_type="purchase",
            channel="online",
            is_international=False,
            card_present=False,
        ))

    return txns, {
        "fraud_type": "velocity_attack",
        "burst_count": burst_count,
        "injected_signals": ["velocity_spike", "escalating_amounts", "new_device", "high_risk_merchants"],
        "final_amount": txns[-1].amount if txns else 0,
    }


# ------------------------------------------------------------------
# 6. Merchant Abuse Injection
# ------------------------------------------------------------------

def inject_merchant_abuse(
    txn: Transaction,
    high_risk_category: str = "gambling",
) -> Tuple[Transaction, Dict]:
    injected = txn.model_copy(deep=True)
    bad_merchant = generate_merchant(high_risk_category)

    injected.merchant_id = bad_merchant["merchant_id"]
    injected.merchant_name = bad_merchant["merchant_name"]
    injected.merchant_category = bad_merchant["merchant_category"]
    injected.channel = "online"
    injected.card_present = False

    return injected, {
        "fraud_type": "merchant_abuse",
        "injected_signals": ["high_risk_merchant", "high_chargeback_merchant", "refund_abuse"],
        "merchant_category": high_risk_category,
        "merchant_risk_score": bad_merchant["risk_score"],
    }
