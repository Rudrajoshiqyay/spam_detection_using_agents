"""
Fraud Evolution Agent — fraud adapts after detection (spec §10).

Each campaign has:
  campaign_generation: which wave (1, 2, 3 ...)
  attack_version:      specific variant within a generation
  difficulty_score:    0-100 (increases per generation)

Flow:
  Generation 1: basic attack → detected
  Generation 2: adapted (smaller amounts, known device)
  Generation 3: sophisticated (trusted merchant, delayed timing)
  Generation 4: APT-level (noise txns, location mimic, slow velocity)

The EvolutionTracker stores detected campaigns and generates
the next generation with progressively harder evasion.
"""

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from app.simulation.adversarial_agent import (
    AdversarialAgent, MUTATION_DIFFICULTY,
    _reduce_amount, _slow_velocity, _use_trusted_device,
    _use_trusted_merchant, _change_timing, _add_noise_txns,
    _mimic_location, _reduce_frequency,
)
from app.simulation.fraud_campaign_agent import generate_campaign, CAMPAIGN_GENERATORS
from app.simulation.persona_agent import create_persona_user


# ── Generation definitions ────────────────────────────────────────────────────

@dataclass
class FraudGeneration:
    campaign_type: str
    campaign_id: str
    generation: int           # 1-based
    attack_version: int       # 1-based within generation
    difficulty_score: float   # 0-100
    mutations_used: List[str]
    transactions: List[Dict]
    parent_campaign_id: Optional[str] = None
    detection_rate: Optional[float] = None  # if known from evaluation


# Generation difficulty bands
_GEN_DIFFICULTY = {
    1: (10.0, 30.0),   # basic — easy to detect
    2: (30.0, 55.0),   # adapted — moderate
    3: (55.0, 75.0),   # sophisticated — hard
    4: (75.0, 95.0),   # APT-level — very hard
}

# Mutations available per generation (cumulative)
_GEN_MUTATIONS = {
    1: [],                                                                  # no evasion
    2: ["reduce_amount", "slow_velocity"],
    3: ["reduce_amount", "slow_velocity", "use_trusted_device", "change_timing"],
    4: ["reduce_amount", "slow_velocity", "use_trusted_device", "change_timing",
        "use_trusted_merchant", "add_noise_txns", "mimic_location", "reduce_frequency"],
}


def _apply_gen_mutations(
    transactions: List[Dict],
    generation: int,
    victim_user: Dict = None,
) -> tuple:
    """Apply generation-appropriate mutations. Returns (txns, mutations, difficulty)."""
    if not transactions:
        return transactions, [], 0.0

    txns = [dict(t) for t in transactions]
    available = _GEN_MUTATIONS.get(generation, [])
    if not available:
        return txns, [], random.uniform(*_GEN_DIFFICULTY.get(1, (10, 30)))

    user_id = txns[0].get("user_id", "unknown")
    known_devices = []
    home_city = None
    active_hours = [9, 10, 11, 12, 18, 19, 20]
    victim_avg = 1000.0

    if victim_user:
        meta = victim_user.get("metadata", {})
        profile = victim_user.get("profile")
        persona = victim_user.get("persona")
        known_devices = profile.known_devices if profile else []
        home_city = meta.get("home_city")
        active_hours = persona.active_hours if persona else active_hours
        victim_avg = meta.get("avg_amount", 1000.0)

    applied = []

    if "reduce_amount" in available:
        txns = [_reduce_amount(t, victim_avg) for t in txns]
        applied.append("reduce_amount")

    if "slow_velocity" in available and len(txns) > 1:
        txns = _slow_velocity(txns)
        applied.append("slow_velocity")

    if "use_trusted_device" in available and known_devices:
        txns = [_use_trusted_device(t, known_devices) for t in txns]
        applied.append("use_trusted_device")

    if "change_timing" in available:
        txns = [_change_timing(t, active_hours) for t in txns]
        applied.append("change_timing")

    if "use_trusted_merchant" in available:
        txns = [
            _use_trusted_merchant(t) if random.random() < 0.4 else t
            for t in txns
        ]
        applied.append("use_trusted_merchant")

    if "add_noise_txns" in available:
        txns = _add_noise_txns(txns, user_id, noise_count=random.randint(2, 5))
        applied.append("add_noise_txns")

    if "mimic_location" in available and home_city:
        txns = [_mimic_location(t, home_city) for t in txns]
        applied.append("mimic_location")

    if "reduce_frequency" in available and len(txns) > 3:
        txns = _reduce_frequency(txns, spread_days=random.randint(3, 10))
        applied.append("reduce_frequency")

    low, high = _GEN_DIFFICULTY.get(generation, (10, 90))
    difficulty = round(random.uniform(low, high), 1)

    return txns, applied, difficulty


# ── Evolution Tracker ─────────────────────────────────────────────────────────

class EvolutionTracker:
    """
    Tracks campaign lineage and generates next-generation attacks.

    In production this would be backed by a DB.
    For demo, stored in memory per session.
    """

    def __init__(self):
        self.lineage: Dict[str, List[FraudGeneration]] = {}  # campaign_type → generations

    def register_generation(self, gen: FraudGeneration):
        self.lineage.setdefault(gen.campaign_type, []).append(gen)

    def get_latest_generation(self, campaign_type: str) -> Optional[FraudGeneration]:
        history = self.lineage.get(campaign_type, [])
        if not history:
            return None
        return max(history, key=lambda g: g.generation)

    def get_next_generation_number(self, campaign_type: str) -> int:
        latest = self.get_latest_generation(campaign_type)
        return (latest.generation + 1) if latest else 1

    def evolve_campaign(
        self,
        campaign_type: str = None,
        victim_user: Dict = None,
        force_generation: int = None,
    ) -> FraudGeneration:
        """Generate the next evolutionary generation of a fraud campaign."""
        if campaign_type is None:
            campaign_type = random.choice(list(CAMPAIGN_GENERATORS.keys()))

        gen_num = force_generation or self.get_next_generation_number(campaign_type)
        parent = self.get_latest_generation(campaign_type)

        # Generate base campaign
        victim = victim_user or create_persona_user()
        campaign = generate_campaign(campaign_type, victim_user=victim)
        base_txns = campaign["transactions"]

        # Apply generation-appropriate mutations
        mutated_txns, mutations, difficulty = _apply_gen_mutations(
            base_txns, gen_num, victim_user=victim
        )

        # Tag every transaction with evolution metadata
        campaign_id = f"evo_{campaign_type[:4]}_g{gen_num}_{uuid.uuid4().hex[:8]}"
        attack_version = len(self.lineage.get(campaign_type, [])) + 1

        for txn in mutated_txns:
            txn["campaign_id"] = campaign_id
            txn["campaign_generation"] = gen_num
            txn["attack_version"] = attack_version
            txn["attack_difficulty"] = difficulty
            txn["mutations_applied"] = txn.get("_mutation", mutations)

        fraud_gen = FraudGeneration(
            campaign_type=campaign_type,
            campaign_id=campaign_id,
            generation=gen_num,
            attack_version=attack_version,
            difficulty_score=difficulty,
            mutations_used=mutations,
            transactions=mutated_txns,
            parent_campaign_id=parent.campaign_id if parent else None,
        )

        self.register_generation(fraud_gen)
        return fraud_gen

    def generate_full_evolution_arc(
        self,
        campaign_type: str = None,
        num_generations: int = 4,
        victim_user: Dict = None,
    ) -> List[FraudGeneration]:
        """
        Generate a complete evolution arc from basic to APT-level.
        Returns all generations in order.
        """
        if campaign_type is None:
            campaign_type = random.choice(list(CAMPAIGN_GENERATORS.keys()))

        victim = victim_user or create_persona_user()
        arc = []
        for gen_num in range(1, num_generations + 1):
            fg = self.evolve_campaign(
                campaign_type=campaign_type,
                victim_user=victim,
                force_generation=gen_num,
            )
            arc.append(fg)
        return arc

    def get_lineage_summary(self, campaign_type: str = None) -> Dict[str, Any]:
        """Summary of all tracked campaign lineages."""
        if campaign_type:
            gens = self.lineage.get(campaign_type, [])
            return {
                "campaign_type": campaign_type,
                "generations": [_gen_to_dict(g) for g in gens],
            }
        return {
            ct: [_gen_to_dict(g) for g in gens]
            for ct, gens in self.lineage.items()
        }


def _gen_to_dict(g: FraudGeneration) -> Dict:
    return {
        "campaign_id": g.campaign_id,
        "generation": g.generation,
        "attack_version": g.attack_version,
        "difficulty_score": g.difficulty_score,
        "mutations_used": g.mutations_used,
        "transaction_count": len(g.transactions),
        "parent_campaign_id": g.parent_campaign_id,
    }


# ── Module-level singleton ────────────────────────────────────────────────────

_default_tracker: Optional[EvolutionTracker] = None


def get_evolution_tracker() -> EvolutionTracker:
    global _default_tracker
    if _default_tracker is None:
        _default_tracker = EvolutionTracker()
    return _default_tracker


def generate_evolved_campaign(
    campaign_type: str = None,
    num_generations: int = 4,
    victim_user: Dict = None,
) -> Dict[str, Any]:
    """
    Top-level function: generate a full evolution arc and return all generations.
    """
    tracker = get_evolution_tracker()
    arc = tracker.generate_full_evolution_arc(
        campaign_type=campaign_type,
        num_generations=num_generations,
        victim_user=victim_user,
    )
    all_txns = []
    gen_summaries = []
    for fg in arc:
        all_txns.extend(fg.transactions)
        gen_summaries.append(_gen_to_dict(fg))

    return {
        "campaign_type": arc[0].campaign_type if arc else campaign_type,
        "num_generations": len(arc),
        "generations": gen_summaries,
        "total_transactions": len(all_txns),
        "difficulty_progression": [g.difficulty_score for g in arc],
        "transactions": all_txns,
    }
