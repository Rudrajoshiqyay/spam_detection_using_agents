"""
Adversarial Agent — applies evasion mutations to fraud transactions.

Mutations make fraud harder to detect by mimicking legitimate patterns.
Each mutation adds to the attack_difficulty score (0-100).

Strategies:
  - reduce_amount         : split large txn into smaller ones below threshold
  - slow_velocity         : add time delays between rapid transactions
  - use_trusted_device    : replace attacker device with victim's known device
  - use_trusted_merchant  : route through low-risk merchant category
  - change_timing         : move transactions to victim's normal active hours
  - add_noise_txns        : insert legit-looking transactions around fraud
  - mimic_location        : use victim's home city instead of overseas
  - reduce_frequency      : spread transactions over longer time window
"""

import random
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

from app.simulation.world_builder import DOMESTIC_CITIES, get_merchant_by_category


# ── Difficulty scoring per mutation ──────────────────────────────────────────

MUTATION_DIFFICULTY: Dict[str, float] = {
    "reduce_amount":       15.0,
    "slow_velocity":       12.0,
    "use_trusted_device":  25.0,
    "use_trusted_merchant":18.0,
    "change_timing":       10.0,
    "add_noise_txns":      20.0,
    "mimic_location":      15.0,
    "reduce_frequency":    8.0,
}

# Max total difficulty
_MAX_DIFFICULTY = 100.0


# ── Mutation Implementations ──────────────────────────────────────────────────

def _reduce_amount(txn: Dict, victim_avg: float = 1000.0) -> Dict:
    """Keep amount below 2× victim's average to avoid amount anomaly."""
    threshold = victim_avg * 1.8
    if txn["amount"] > threshold:
        txn = dict(txn)
        txn["amount"] = round(min(txn["amount"], threshold) * random.uniform(0.7, 0.95), 2)
        txn["_mutation"] = txn.get("_mutation", []) + ["reduce_amount"]
    return txn


def _slow_velocity(txns: List[Dict], min_gap_minutes: int = 30) -> List[Dict]:
    """Spread transactions to avoid velocity triggers."""
    result = []
    prev_ts = None
    for txn in txns:
        txn = dict(txn)
        if prev_ts is not None:
            ts = datetime.fromisoformat(txn["timestamp"].replace("Z", "+00:00"))
            expected_min = prev_ts + timedelta(minutes=min_gap_minutes)
            if ts < expected_min:
                ts = expected_min + timedelta(minutes=random.randint(0, 15))
                txn["timestamp"] = ts.isoformat()
        prev_ts = datetime.fromisoformat(txn["timestamp"].replace("Z", "+00:00"))
        txn["_mutation"] = txn.get("_mutation", []) + ["slow_velocity"]
        result.append(txn)
    return result


def _use_trusted_device(txn: Dict, known_devices: List[str]) -> Dict:
    """Replace unknown attacker device with victim's known device."""
    if not known_devices:
        return txn
    txn = dict(txn)
    txn["device_id"] = random.choice(known_devices)
    txn["_mutation"] = txn.get("_mutation", []) + ["use_trusted_device"]
    return txn


def _use_trusted_merchant(txn: Dict) -> Dict:
    """Route through a low-risk merchant category."""
    low_risk_cats = ["grocery", "utilities", "medical", "mobile_recharge", "streaming"]
    cat = random.choice(low_risk_cats)
    m = get_merchant_by_category(cat)
    txn = dict(txn)
    txn["merchant_id"] = m["merchant_id"]
    txn["merchant_name"] = m["merchant_name"]
    txn["merchant_category"] = cat
    txn["_mutation"] = txn.get("_mutation", []) + ["use_trusted_merchant"]
    return txn


def _change_timing(txn: Dict, active_hours: List[int] = None) -> Dict:
    """Move transaction timestamp into victim's normal active hours."""
    if not active_hours:
        active_hours = [9, 10, 11, 12, 13, 18, 19, 20]
    txn = dict(txn)
    ts = datetime.fromisoformat(txn["timestamp"].replace("Z", "+00:00"))
    new_hour = random.choice(active_hours)
    ts = ts.replace(hour=new_hour, minute=random.randint(0, 59))
    txn["timestamp"] = ts.isoformat()
    txn["_mutation"] = txn.get("_mutation", []) + ["change_timing"]
    return txn


def _mimic_location(txn: Dict, home_city: str = None, home_country: str = "India") -> Dict:
    """Use victim's home city instead of foreign location."""
    if home_city:
        city_data = next((c for c in DOMESTIC_CITIES if c["city"] == home_city), None)
    else:
        city_data = None

    if not city_data:
        city_data = random.choice(DOMESTIC_CITIES)

    txn = dict(txn)
    txn["location_city"] = city_data["city"]
    txn["location_country"] = "India"
    txn["is_international"] = False
    txn["_mutation"] = txn.get("_mutation", []) + ["mimic_location"]
    return txn


def _reduce_frequency(txns: List[Dict], spread_days: int = 7) -> List[Dict]:
    """Spread burst transactions across multiple days."""
    if not txns:
        return txns
    first_ts = datetime.fromisoformat(txns[0]["timestamp"].replace("Z", "+00:00"))
    result = []
    for i, txn in enumerate(txns):
        txn = dict(txn)
        offset_hours = int((spread_days * 24 / max(len(txns), 1)) * i)
        new_ts = first_ts + timedelta(hours=offset_hours + random.randint(0, 6))
        txn["timestamp"] = new_ts.isoformat()
        txn["_mutation"] = txn.get("_mutation", []) + ["reduce_frequency"]
        result.append(txn)
    return result


def _add_noise_txns(
    txns: List[Dict],
    user_id: str,
    noise_count: int = 3,
) -> List[Dict]:
    """Insert legit-looking transactions around the fraud sequence."""
    if not txns:
        return txns

    first_ts = datetime.fromisoformat(txns[0]["timestamp"].replace("Z", "+00:00"))
    noise = []
    for i in range(noise_count):
        offset = timedelta(hours=random.randint(-24, -1))
        ts = first_ts + offset
        cat = random.choice(["grocery", "food_delivery", "transport", "restaurants"])
        m = get_merchant_by_category(cat)
        noise.append({
            "transaction_id": f"txn_noise_{i}_{user_id[:6]}",
            "user_id": user_id,
            "amount": round(random.uniform(100, 1500), 2),
            "merchant_id": m["merchant_id"],
            "merchant_name": m["merchant_name"],
            "merchant_category": cat,
            "device_id": txns[0].get("device_id", f"dev_{user_id[:8]}"),
            "timestamp": ts.isoformat(),
            "is_fraud": False,
            "fraud_type": None,
            "ring_id": txns[0].get("ring_id"),
            "campaign_id": txns[0].get("campaign_id"),
            "expected_label": "APPROVED",
            "_mutation": ["add_noise_txns"],
        })

    combined = noise + txns
    combined.sort(key=lambda x: x["timestamp"])
    return combined


# ── Adversarial Mutation Engine ───────────────────────────────────────────────

class AdversarialAgent:
    """
    Applies evasion mutations to a fraud campaign or ring's transactions.
    Returns mutated transactions with `attack_difficulty` (0-100) per transaction.
    """

    def __init__(
        self,
        victim_avg_amount: float = 1000.0,
        known_devices: List[str] = None,
        home_city: str = None,
        active_hours: List[int] = None,
        difficulty_target: float = None,   # 0-100; None=random
    ):
        self.victim_avg_amount = victim_avg_amount
        self.known_devices = known_devices or []
        self.home_city = home_city
        self.active_hours = active_hours or [9, 10, 11, 12, 18, 19, 20]
        self.difficulty_target = difficulty_target or random.uniform(20, 90)

    def mutate(self, transactions: List[Dict]) -> List[Dict]:
        """Apply mutations to the transaction list. Returns mutated list."""
        if not transactions:
            return transactions

        user_id = transactions[0].get("user_id", "unknown")
        txns = [dict(t) for t in transactions]
        applied_difficulty = 0.0
        applied_mutations = []

        # Select mutations based on difficulty target
        candidates = list(MUTATION_DIFFICULTY.items())
        random.shuffle(candidates)

        for mutation_name, diff_score in candidates:
            if applied_difficulty >= self.difficulty_target:
                break

            if mutation_name == "reduce_amount":
                txns = [_reduce_amount(t, self.victim_avg_amount) for t in txns]
                applied_difficulty += diff_score
                applied_mutations.append(mutation_name)

            elif mutation_name == "slow_velocity":
                txns = _slow_velocity(txns)
                applied_difficulty += diff_score
                applied_mutations.append(mutation_name)

            elif mutation_name == "use_trusted_device" and self.known_devices:
                txns = [_use_trusted_device(t, self.known_devices) for t in txns]
                applied_difficulty += diff_score
                applied_mutations.append(mutation_name)

            elif mutation_name == "use_trusted_merchant":
                # Apply to 50% of transactions to maintain partial fraud signal
                txns = [
                    _use_trusted_merchant(t) if random.random() < 0.5 else t
                    for t in txns
                ]
                applied_difficulty += diff_score * 0.5
                applied_mutations.append(mutation_name)

            elif mutation_name == "change_timing":
                txns = [_change_timing(t, self.active_hours) for t in txns]
                applied_difficulty += diff_score
                applied_mutations.append(mutation_name)

            elif mutation_name == "add_noise_txns":
                txns = _add_noise_txns(txns, user_id)
                applied_difficulty += diff_score
                applied_mutations.append(mutation_name)

            elif mutation_name == "mimic_location":
                txns = [_mimic_location(t, self.home_city) for t in txns]
                applied_difficulty += diff_score
                applied_mutations.append(mutation_name)

            elif mutation_name == "reduce_frequency" and len(txns) > 3:
                txns = _reduce_frequency(txns)
                applied_difficulty += diff_score
                applied_mutations.append(mutation_name)

        final_difficulty = min(_MAX_DIFFICULTY, applied_difficulty)

        # Tag every transaction with attack_difficulty
        for txn in txns:
            txn["attack_difficulty"] = round(final_difficulty, 1)
            txn["mutations_applied"] = txn.get("_mutation", [])

        return txns, applied_mutations, final_difficulty


def apply_adversarial_mutations(
    transactions: List[Dict],
    victim_user: Dict = None,
    difficulty_target: float = None,
) -> Dict[str, Any]:
    """
    Top-level function: apply adversarial mutations to a transaction list.

    Returns:
        {
          "transactions": [...mutated...],
          "mutations_applied": [...],
          "attack_difficulty": float,
        }
    """
    kwargs = {}
    if victim_user:
        meta = victim_user.get("metadata", {})
        profile = victim_user.get("profile")
        kwargs["victim_avg_amount"] = meta.get("avg_amount", 1000.0)
        kwargs["known_devices"] = profile.known_devices if profile else []
        kwargs["home_city"] = meta.get("home_city")
        persona = victim_user.get("persona")
        kwargs["active_hours"] = persona.active_hours if persona else None

    if difficulty_target is not None:
        kwargs["difficulty_target"] = difficulty_target

    agent = AdversarialAgent(**kwargs)
    mutated_txns, mutations, difficulty = agent.mutate(transactions)

    return {
        "transactions": mutated_txns,
        "mutations_applied": mutations,
        "attack_difficulty": difficulty,
    }
