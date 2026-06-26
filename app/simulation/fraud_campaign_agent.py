"""
Fraud Campaign Agent — generates coordinated fraud attack sequences.

Each campaign has a campaign_id, attack_type, and a series of transactions
that form a narrative arc (probe → escalate → cash-out or similar).

Supported campaigns:
  - account_takeover       (ATO)
  - card_testing_series    (enumerate valid cards)
  - money_mule             (layered transfers)
  - velocity_attack        (burst spending)
  - synthetic_identity     (fabricated user profile)
  - cross_border_fraud     (international laundering)
"""

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from app.simulation.persona_agent import (
    PersonaType, PERSONA_DEFINITIONS, create_persona_user, _PERSONA_TO_RISK
)
from app.simulation.world_builder import (
    WORLD_CITIES, get_merchant_by_category, get_high_risk_merchant,
    DOMESTIC_CITIES, INTL_CITIES,
)
from app.simulation.ground_truth_store import GroundTruthRecord


# ── Campaign building blocks ─────────────────────────────────────────────────

def _base_txn_dict(
    user_id: str,
    amount: float,
    merchant_cat: str,
    city: str,
    country: str,
    device_id: str,
    timestamp: datetime,
    campaign_id: str,
    fraud_type: str,
    ring_id: Optional[str] = None,
) -> Dict[str, Any]:
    merchant = get_merchant_by_category(merchant_cat)
    return {
        "transaction_id": f"txn_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "amount": round(amount, 2),
        "currency": "INR",
        "merchant_id": merchant["merchant_id"],
        "merchant_name": merchant["merchant_name"],
        "merchant_category": merchant_cat,
        "device_id": device_id,
        "ip_address": f"103.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
        "location_city": city,
        "location_country": country,
        "timestamp": timestamp.isoformat(),
        "channel": "online",
        "is_international": country != "India",
        # Ground truth tags
        "is_fraud": True,
        "fraud_type": fraud_type,
        "campaign_id": campaign_id,
        "ring_id": ring_id,
        "expected_label": "BLOCKED",
    }


# ── Account Takeover Campaign ────────────────────────────────────────────────

def generate_ato_campaign(victim_user: Dict) -> Dict[str, Any]:
    """ATO: new device login → profile-change → drain account."""
    campaign_id = f"camp_ato_{uuid.uuid4().hex[:8]}"
    user_id = victim_user["metadata"]["user_id"]
    attacker_device = f"dev_atk_{uuid.uuid4().hex[:10]}"
    start_time = datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 48))
    transactions = []

    # Phase 1: Low-value probe (attacker tests access)
    for i in range(2):
        ts = start_time + timedelta(minutes=i * 3)
        txn = _base_txn_dict(
            user_id, random.uniform(50, 200),
            "mobile_recharge", "Bangalore", "India", attacker_device, ts,
            campaign_id, "account_takeover",
        )
        txn["phase"] = "probe"
        transactions.append(txn)

    # Phase 2: Profile update (change email/phone — simulated as API-level)

    # Phase 3: Drain high-value
    for i in range(3):
        ts = start_time + timedelta(minutes=15 + i * 5)
        amount = random.uniform(15_000, 50_000)
        merchant_cat = random.choice(["wire_transfer", "cryptocurrency", "jewelry"])
        city_data = random.choice(INTL_CITIES)
        txn = _base_txn_dict(
            user_id, amount, merchant_cat,
            city_data["city"], city_data["country"], attacker_device, ts,
            campaign_id, "account_takeover",
        )
        txn["phase"] = "drain"
        transactions.append(txn)

    return {
        "campaign_id": campaign_id,
        "campaign_type": "account_takeover",
        "user_id": user_id,
        "attacker_device": attacker_device,
        "transactions": transactions,
        "metadata": {"victim_persona": victim_user["metadata"]["persona_type"]},
    }


# ── Card Testing Campaign ─────────────────────────────────────────────────────

def generate_card_testing_campaign(victim_user: Dict = None) -> Dict[str, Any]:
    """Rapid micro-transactions to test if stolen cards are valid."""
    campaign_id = f"camp_ct_{uuid.uuid4().hex[:8]}"
    user_id = (victim_user or create_persona_user())["metadata"]["user_id"]
    device_id = f"dev_ct_{uuid.uuid4().hex[:10]}"
    start_time = datetime.now(timezone.utc) - timedelta(minutes=random.randint(5, 120))
    transactions = []

    # 10-20 micro transactions in rapid succession
    n = random.randint(10, 20)
    for i in range(n):
        ts = start_time + timedelta(seconds=i * random.randint(10, 45))
        amount = round(random.uniform(1.0, 99.0), 2)
        txn = _base_txn_dict(
            user_id, amount, "gaming",
            random.choice(DOMESTIC_CITIES)["city"], "India", device_id, ts,
            campaign_id, "card_testing",
        )
        txn["phase"] = "test"
        txn["expected_label"] = "BLOCKED" if i > 5 else "ESCALATED"
        transactions.append(txn)

    return {
        "campaign_id": campaign_id,
        "campaign_type": "card_testing_series",
        "user_id": user_id,
        "device_id": device_id,
        "transactions": transactions,
        "metadata": {"test_count": n},
    }


# ── Money Mule Campaign ───────────────────────────────────────────────────────

def generate_money_mule_campaign(mule_users: List[Dict] = None) -> Dict[str, Any]:
    """Layered transfers through mule accounts to obscure origin."""
    campaign_id = f"camp_mm_{uuid.uuid4().hex[:8]}"

    if not mule_users:
        mule_users = [create_persona_user(PersonaType.gig_worker) for _ in range(3)]

    ring_id = f"ring_{uuid.uuid4().hex[:8]}"
    start_time = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 7))
    transactions = []

    # Injection into first mule
    victim_id = mule_users[0]["metadata"]["user_id"]
    inject_ts = start_time
    txn = _base_txn_dict(
        victim_id, random.uniform(80_000, 300_000),
        "wire_transfer", "Mumbai", "India",
        f"dev_{uuid.uuid4().hex[:10]}", inject_ts,
        campaign_id, "money_mule", ring_id,
    )
    txn["phase"] = "inject"
    transactions.append(txn)

    # Layer transfers through mules (start at index 1 — index 0 already got inject)
    for i, mule in enumerate(mule_users[1:], start=1):
        offset_hours = i * random.randint(2, 8)
        ts = start_time + timedelta(hours=offset_hours)
        amount = random.uniform(40_000, 150_000)
        txn = _base_txn_dict(
            mule["metadata"]["user_id"], amount,
            "p2p_transfer", "Delhi", "India",
            f"dev_{uuid.uuid4().hex[:10]}", ts,
            campaign_id, "money_mule", ring_id,
        )
        txn["phase"] = f"layer_{i}"
        transactions.append(txn)

    # Cash out
    cashout_ts = start_time + timedelta(days=random.randint(1, 3))
    txn = _base_txn_dict(
        mule_users[-1]["metadata"]["user_id"],
        random.uniform(50_000, 200_000),
        "cryptocurrency", "Singapore", "Singapore",
        f"dev_{uuid.uuid4().hex[:10]}", cashout_ts,
        campaign_id, "money_mule", ring_id,
    )
    txn["phase"] = "cashout"
    transactions.append(txn)

    return {
        "campaign_id": campaign_id,
        "campaign_type": "money_mule",
        "ring_id": ring_id,
        "mule_ids": [m["metadata"]["user_id"] for m in mule_users],
        "transactions": transactions,
    }


# ── Velocity Attack Campaign ──────────────────────────────────────────────────

def generate_velocity_attack_campaign(victim_user: Dict = None) -> Dict[str, Any]:
    """Burst of high-value transactions in very short time window."""
    campaign_id = f"camp_vel_{uuid.uuid4().hex[:8]}"
    user_id = (victim_user or create_persona_user())["metadata"]["user_id"]
    device_id = f"dev_vel_{uuid.uuid4().hex[:10]}"
    start_time = datetime.now(timezone.utc) - timedelta(minutes=random.randint(5, 30))
    transactions = []

    n = random.randint(8, 15)
    for i in range(n):
        ts = start_time + timedelta(seconds=i * random.randint(20, 90))
        amount = random.uniform(3_000, 25_000)
        cat = random.choice(["ecommerce", "electronics", "jewelry"])
        city = random.choice(DOMESTIC_CITIES)
        txn = _base_txn_dict(
            user_id, amount, cat,
            city["city"], "India", device_id, ts,
            campaign_id, "velocity_fraud",
        )
        txn["phase"] = "burst"
        transactions.append(txn)

    return {
        "campaign_id": campaign_id,
        "campaign_type": "velocity_attack",
        "user_id": user_id,
        "transactions": transactions,
    }


# ── Synthetic Identity Campaign ───────────────────────────────────────────────

def generate_synthetic_identity_campaign() -> Dict[str, Any]:
    """Fabricated user builds credit profile then commits fraud."""
    campaign_id = f"camp_si_{uuid.uuid4().hex[:8]}"
    fake_user = create_persona_user(PersonaType.salaried_employee)
    user_id = fake_user["metadata"]["user_id"]
    device_id = f"dev_si_{uuid.uuid4().hex[:10]}"
    start_time = datetime.now(timezone.utc) - timedelta(days=random.randint(30, 90))
    transactions = []

    # Credit building (legit-looking, low amounts)
    for i in range(15):
        ts = start_time + timedelta(days=i * 2, hours=random.randint(9, 20))
        amount = random.uniform(200, 2_000)
        cat = random.choice(["grocery", "restaurants", "transport", "mobile_recharge"])
        city = random.choice(DOMESTIC_CITIES)
        txn = _base_txn_dict(
            user_id, amount, cat,
            city["city"], "India", device_id, ts,
            campaign_id, "synthetic_identity",
        )
        txn["is_fraud"] = False
        txn["expected_label"] = "APPROVED"
        txn["phase"] = "credit_build"
        transactions.append(txn)

    # Fraud burst after profile established
    burst_start = start_time + timedelta(days=35)
    for i in range(5):
        ts = burst_start + timedelta(hours=i * 2)
        amount = random.uniform(20_000, 100_000)
        cat = random.choice(["electronics", "jewelry", "wire_transfer"])
        intl = random.choice(INTL_CITIES)
        txn = _base_txn_dict(
            user_id, amount, cat,
            intl["city"], intl["country"], device_id, ts,
            campaign_id, "synthetic_identity",
        )
        txn["phase"] = "fraud_burst"
        transactions.append(txn)

    return {
        "campaign_id": campaign_id,
        "campaign_type": "synthetic_identity",
        "user_id": user_id,
        "transactions": transactions,
    }


# ── Cross-Border Fraud Campaign ───────────────────────────────────────────────

def generate_cross_border_campaign(victim_user: Dict = None) -> Dict[str, Any]:
    """Rapid international transactions across incompatible locations."""
    campaign_id = f"camp_cb_{uuid.uuid4().hex[:8]}"
    user_id = (victim_user or create_persona_user())["metadata"]["user_id"]
    device_id = f"dev_cb_{uuid.uuid4().hex[:10]}"
    start_time = datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 6))
    transactions = []

    # Impossible travel sequence
    city_sequence = random.sample(
        [c for c in INTL_CITIES if c["country"] in ("UK", "USA", "Japan", "Australia", "Brazil")],
        k=min(4, 4)
    )

    for i, city in enumerate(city_sequence):
        ts = start_time + timedelta(minutes=i * 30)  # 30 min gaps = impossible travel
        amount = random.uniform(5_000, 50_000)
        cat = random.choice(["luxury", "airlines", "hotels", "electronics"])
        txn = _base_txn_dict(
            user_id, amount, cat,
            city["city"], city["country"], device_id, ts,
            campaign_id, "cross_border_fraud",
        )
        txn["phase"] = "intl_hop"
        transactions.append(txn)

    return {
        "campaign_id": campaign_id,
        "campaign_type": "cross_border_fraud",
        "user_id": user_id,
        "transactions": transactions,
    }


# ── Campaign Factory ──────────────────────────────────────────────────────────

CAMPAIGN_GENERATORS = {
    "account_takeover":   generate_ato_campaign,
    "card_testing":       generate_card_testing_campaign,
    "money_mule":         generate_money_mule_campaign,
    "velocity_attack":    generate_velocity_attack_campaign,
    "synthetic_identity": generate_synthetic_identity_campaign,
    "cross_border":       generate_cross_border_campaign,
}


def generate_campaign(
    campaign_type: str = None,
    victim_user: Dict = None,
) -> Dict[str, Any]:
    """Generate a fraud campaign of the given type (or random)."""
    if campaign_type is None:
        campaign_type = random.choice(list(CAMPAIGN_GENERATORS.keys()))

    gen_fn = CAMPAIGN_GENERATORS.get(campaign_type)
    if gen_fn is None:
        raise ValueError(f"Unknown campaign type: {campaign_type}")

    if campaign_type in ("account_takeover", "velocity_attack", "cross_border"):
        victim = victim_user or create_persona_user()
        return gen_fn(victim)
    elif campaign_type == "money_mule":
        return gen_fn()
    else:
        return gen_fn()


def campaign_to_ground_truth_records(campaign: Dict) -> List[GroundTruthRecord]:
    """Convert a campaign's transactions into GroundTruthRecord objects."""
    records = []
    for txn in campaign.get("transactions", []):
        records.append(GroundTruthRecord(
            transaction_id=txn["transaction_id"],
            is_fraud=txn.get("is_fraud", True),
            fraud_type=txn.get("fraud_type"),
            campaign_id=txn.get("campaign_id"),
            ring_id=txn.get("ring_id"),
            attack_difficulty=0.0,  # will be set by adversarial agent
            expected_label=txn.get("expected_label", "BLOCKED"),
            persona_type=campaign.get("metadata", {}).get("victim_persona"),
            amount=txn["amount"],
        ))
    return records
