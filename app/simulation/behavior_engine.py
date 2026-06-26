"""
Behavior Engine — generates persona-driven transactions with realistic spending distributions.

Wraps the transaction generator with persona-specific merchant selection,
amount sampling, device selection, and location patterns.
"""

import math
import random
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.models.transaction import Transaction
from app.models.user_profile import UserProfile
from app.simulation.persona_agent import PersonaProfile, PersonaType
from app.simulation.temporal_simulator import TimeSlot
from app.simulation.world_builder import (
    WORLD_CITIES, get_city, get_merchant_pool,
    get_merchant_by_category, MERCHANT_CATEGORIES,
)


def _log_normal(mean: float, std: float) -> float:
    if mean <= 0:
        return 1.0
    sigma = math.sqrt(math.log(1 + (std / mean) ** 2)) if std > 0 else 0.3
    mu = math.log(mean) - sigma ** 2 / 2
    return max(1.0, round(random.lognormvariate(mu, sigma), 2))


def _pick_merchant(persona: PersonaProfile, slot_type: str) -> Dict:
    """Pick a merchant weighted by persona preferences and slot context."""
    # Slot-specific overrides
    slot_category_map = {
        "salary_credit": ["p2p_transfer", "investments"],
        "night_food_delivery": ["food_delivery"],
        "weekend_shopping": ["ecommerce", "clothing", "electronics", "entertainment"],
        "bill_payment": ["utilities", "insurance", "mobile_recharge"],
    }

    if slot_type in slot_category_map:
        cat = random.choice(slot_category_map[slot_type])
        return get_merchant_by_category(cat)

    # Persona preference: 75% preferred, 25% random
    if random.random() < 0.75 and persona.preferred_merchants:
        cat = random.choice(persona.preferred_merchants)
        # Map persona merchant names to actual categories
        cat_map = {
            "food_delivery": "food_delivery",
            "grocery": "grocery",
            "transport": "transport",
            "restaurants": "restaurants",
            "clothing": "clothing",
            "electronics": "electronics",
            "entertainment": "entertainment",
            "education": "education",
            "medical": "medical",
            "utilities": "utilities",
            "luxury": "luxury",
            "airlines": "airlines",
            "hotels": "hotels",
            "wire_transfer": "wire_transfer",
            "cryptocurrency": "cryptocurrency",
            "gaming": "gaming",
            "b2b_suppliers": "b2b_suppliers",
            "wholesale": "wholesale",
            "technology": "electronics",
            "fine_dining": "restaurants",
            "streaming": "streaming",
            "investments": "investments",
            "real_estate": "real_estate",
            "jewelry": "jewelry",
            "mobile_recharge": "mobile_recharge",
            "fuel": "fuel",
            "art": "luxury",
            "travel": "airlines",
        }
        resolved = cat_map.get(cat, cat)
        if resolved in MERCHANT_CATEGORIES:
            return get_merchant_by_category(resolved)

    pool = get_merchant_pool()
    return random.choice(pool)


def _pick_device(profile: UserProfile, persona: PersonaProfile) -> tuple:
    """Returns (device_id, device_type). 85% uses known device."""
    types = list(persona.device_type_weights.keys())
    weights = list(persona.device_type_weights.values())
    device_type = random.choices(types, weights=weights)[0]

    if profile.known_devices and random.random() < 0.85:
        return random.choice(profile.known_devices), device_type
    return f"dev_new_{uuid.uuid4().hex[:10]}", device_type


def _pick_location(profile: UserProfile, persona: PersonaProfile) -> Dict:
    """Pick location based on persona travel patterns."""
    home_loc = profile.known_locations[0] if profile.known_locations else "Mumbai:India"
    home_city = home_loc.split(":")[0]
    home_data = get_city(home_city)

    freq = persona.travel_frequency
    roll = random.random()

    if freq == "very_frequent":
        if roll < 0.40:
            # Home city
            return {**home_data, "is_international": False}
        elif roll < 0.70:
            # Known domestic city
            domestic = [c for c in WORLD_CITIES if c["country"] == "India" and c["city"] != home_city]
            city = random.choice(domestic) if domestic else home_data
            return {**city, "is_international": False}
        else:
            # International
            if persona.frequent_countries:
                country = random.choice([c for c in persona.frequent_countries if c != "India"] or ["UAE"])
                options = [c for c in WORLD_CITIES if c["country"] == country]
                city = random.choice(options) if options else get_city("Dubai")
            else:
                city = random.choice([c for c in WORLD_CITIES if c["country"] != "India"])
            return {**city, "is_international": True}

    elif freq == "frequent":
        if roll < 0.60:
            return {**home_data, "is_international": False}
        elif roll < 0.80:
            domestic = [c for c in WORLD_CITIES if c["country"] == "India"]
            return {**random.choice(domestic), "is_international": False}
        else:
            intl = [c for c in WORLD_CITIES if c["country"] != "India"]
            city = random.choice(intl)
            return {**city, "is_international": True}

    elif freq == "occasional":
        if roll < 0.80:
            return {**home_data, "is_international": False}
        elif roll < 0.95:
            domestic = [c for c in WORLD_CITIES if c["country"] == "India"]
            return {**random.choice(domestic), "is_international": False}
        else:
            intl = [c for c in WORLD_CITIES if c["country"] != "India"]
            return {**random.choice(intl), "is_international": True}

    else:  # rare
        if roll < 0.90:
            return {**home_data, "is_international": False}
        domestic = [c for c in WORLD_CITIES if c["country"] == "India"]
        return {**random.choice(domestic), "is_international": False}


def _pick_amount(
    persona: PersonaProfile,
    profile: UserProfile,
    merchant: Dict,
    slot: TimeSlot,
) -> float:
    # Base amount from persona distribution
    base = _log_normal(persona.avg_txn_amount, persona.std_txn_amount)

    # Apply slot multiplier
    base *= slot.expected_amount_mult

    # Merchant category anchor: blend 60% persona, 40% merchant avg
    m_avg = merchant.get("avg_ticket", persona.avg_txn_amount)
    blended = base * 0.6 + m_avg * 0.4

    # Cap at persona max
    return min(blended, persona.max_txn_amount)


def generate_behavior_transaction(
    profile: UserProfile,
    persona: PersonaProfile,
    slot: TimeSlot,
    merchant_override: Dict = None,
    device_override: str = None,
    location_override: Dict = None,
) -> Transaction:
    """Generate a single transaction according to persona behavior and time slot."""
    merchant = merchant_override or _pick_merchant(persona, slot.slot_type)
    device_id, device_type = (device_override, "mobile") if device_override else _pick_device(profile, persona)
    location = location_override or _pick_location(profile, persona)
    amount = _pick_amount(persona, profile, merchant, slot)

    payment_method = random.choice(persona.payment_methods)
    channel = "online" if merchant.get("is_online") else random.choice(["online", "in-store"])

    return Transaction(
        transaction_id=f"txn_{uuid.uuid4().hex[:12]}",
        user_id=profile.user_id,
        amount=round(amount, 2),
        currency="INR",
        merchant_id=merchant["merchant_id"],
        merchant_name=merchant["merchant_name"],
        merchant_category=merchant["merchant_category"],
        device_id=device_id,
        device_type=device_type,
        ip_address=f"103.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
        latitude=location["lat"],
        longitude=location["lon"],
        location_city=location["city"],
        location_country=location["country"],
        timestamp=slot.timestamp,
        transaction_type="purchase" if slot.slot_type not in ("salary_credit", "bill_payment") else "transfer",
        channel=channel,
        is_international=location.get("is_international", False),
        card_present=not merchant.get("is_online", False),
        metadata={"slot_type": slot.slot_type, "payment_method": payment_method},
    )


def generate_persona_transaction_batch(
    users: List[Dict],  # list of {profile, persona, metadata}
    count: int,
    span_days: int = 30,
    start_date: datetime = None,
) -> List[Dict[str, Any]]:
    """Generate a realistic transaction batch from persona users with timeline simulation."""
    from app.simulation.temporal_simulator import generate_timeline

    if start_date is None:
        start_date = datetime.now(timezone.utc)

    # Build timeline for each user
    user_timelines = []
    for u in users:
        slots = generate_timeline(u["persona"], span_days=span_days,
                                  start_date=start_date)
        user_timelines.append((u, slots))

    # Flatten all (user, slot) pairs and sample `count`
    all_pairs = [(u, s) for u, slots in user_timelines for s in slots]
    if not all_pairs:
        return []

    sampled = random.sample(all_pairs, min(count, len(all_pairs)))
    sampled.sort(key=lambda x: x[1].timestamp)

    results = []
    for user_data, slot in sampled:
        txn = generate_behavior_transaction(
            profile=user_data["profile"],
            persona=user_data["persona"],
            slot=slot,
        )
        results.append({
            "transaction": txn,
            "user_id": user_data["metadata"]["user_id"],
            "persona_type": user_data["metadata"]["persona_type"],
            "is_fraud": False,
            "fraud_type": None,
            "campaign_id": None,
            "ring_id": None,
            "attack_difficulty": 0.0,
        })

    return results
