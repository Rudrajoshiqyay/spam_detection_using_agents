"""
Scenario Builder Agent — builds complete fraud simulation environments.

Given a high-level scenario description, automatically generates:
  - N synthetic users
  - M transactions with configurable fraud rate
  - Fraud ring structure (shared devices across accounts)
  - Kill chain sequences

Designed for hackathon demo impact: one call produces a full testable dataset.
"""

import logging
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from app.models.user_profile import UserType
from app.synthetic.user_generator import generate_user_batch
from app.synthetic.transaction_generator import generate_transaction, generate_transaction_batch
from app.synthetic.fraud_injector import (
    inject_account_takeover,
    inject_card_testing_series,
    inject_money_mule,
    inject_velocity_attack,
    inject_merchant_abuse,
    inject_synthetic_identity,
)
from app.synthetic.device_generator import generate_device

_logger = logging.getLogger(__name__)


@dataclass
class ScenarioConfig:
    name: str
    description: str
    user_count: int = 100
    transaction_count: int = 1000
    fraud_rate: float = 0.05          # fraction of transactions that are fraudulent (0 < x < 1)
    fraud_ring_count: int = 0         # number of coordinated fraud rings
    compromised_account_count: int = 0
    span_days: int = 7
    fraud_types: List[str] = field(default_factory=lambda: ["account_takeover"])
    seed: Optional[int] = None        # set for deterministic/reproducible output

    def __post_init__(self):
        if not (0 < self.fraud_rate < 1):
            raise ValueError(f"fraud_rate must be in (0, 1), got {self.fraud_rate}")
        if self.span_days < 1:
            raise ValueError(f"span_days must be >= 1, got {self.span_days}")
        if self.user_count < 1:
            raise ValueError(f"user_count must be >= 1, got {self.user_count}")
        if self.transaction_count < 1:
            raise ValueError(f"transaction_count must be >= 1, got {self.transaction_count}")
        if self.fraud_ring_count < 0:
            raise ValueError(f"fraud_ring_count must be >= 0, got {self.fraud_ring_count}")
        if self.compromised_account_count < 0:
            raise ValueError(f"compromised_account_count must be >= 0, got {self.compromised_account_count}")
        if not self.fraud_types:
            raise ValueError("fraud_types must contain at least one type")


# Pre-built scenario configs
PRESET_SCENARIOS: Dict[str, ScenarioConfig] = {
    "small_demo": ScenarioConfig(
        name="small_demo",
        description="Small dataset for quick demo (50 users, 200 txns, mixed fraud)",
        user_count=50,
        transaction_count=200,
        fraud_rate=0.10,
        fraud_ring_count=1,
        compromised_account_count=5,
        span_days=7,
        fraud_types=["account_takeover", "card_testing", "velocity_attack"],
    ),
    "fraud_ring_campaign": ScenarioConfig(
        name="fraud_ring_campaign",
        description="Large-scale account takeover campaign with fraud rings",
        user_count=1000,
        transaction_count=10000,
        fraud_rate=0.05,
        fraud_ring_count=5,
        compromised_account_count=50,
        span_days=30,
        fraud_types=["account_takeover", "synthetic_identity", "merchant_abuse"],
    ),
    "card_testing_wave": ScenarioConfig(
        name="card_testing_wave",
        description="Wave of card testing attacks from stolen card data",
        user_count=200,
        transaction_count=2000,
        fraud_rate=0.15,
        fraud_ring_count=0,
        compromised_account_count=30,
        span_days=14,
        fraud_types=["card_testing", "velocity_attack"],
    ),
    "mule_network": ScenarioConfig(
        name="mule_network",
        description="Money mule network laundering funds through multiple accounts",
        user_count=300,
        transaction_count=3000,
        fraud_rate=0.08,
        fraud_ring_count=3,
        compromised_account_count=20,
        span_days=30,
        fraud_types=["money_mule", "merchant_abuse"],
    ),
    "stress_test": ScenarioConfig(
        name="stress_test",
        description="High-volume stress test — 5000 users, 50000 transactions, low fraud rate",
        user_count=5000,
        transaction_count=50000,
        fraud_rate=0.02,
        fraud_ring_count=10,
        compromised_account_count=200,
        span_days=90,
        fraud_types=["account_takeover", "card_testing", "velocity_attack", "synthetic_identity"],
    ),
    "fraud_heavy": ScenarioConfig(
        name="fraud_heavy",
        description="Fraud-heavy scenario for detection stress — 500 users, 3000 transactions, 30% fraud",
        user_count=500,
        transaction_count=3000,
        fraud_rate=0.30,
        fraud_ring_count=5,
        compromised_account_count=100,
        span_days=14,
        fraud_types=["account_takeover", "card_testing", "money_mule", "synthetic_identity", "velocity_attack", "merchant_abuse"],
    ),
}


class ScenarioBuilder:
    def __init__(self, config: ScenarioConfig):
        self.config = config
        self.run_id = f"scenario_{uuid.uuid4().hex[:8]}"

    def build(self) -> Dict[str, Any]:
        """Build the complete scenario and return all generated data."""
        # Seed for reproducibility — must happen before any random calls
        random.seed(self.config.seed)

        start_time = datetime.now(timezone.utc) - timedelta(days=self.config.span_days)

        # 1. Generate users
        users_data = generate_user_batch(self.config.user_count)
        profiles = [u["profile"] for u in users_data]
        user_meta = [u["metadata"] for u in users_data]

        # Index meta by user_id to avoid O(n²) scan inside transaction loops
        user_meta_by_id: Dict[str, dict] = {m["user_id"]: m for m in user_meta}

        # 2. Build fraud rings (shared devices across accounts)
        fraud_ring_device_map: Dict[str, str] = {}  # user_id → shared_device_id
        ring_definitions = []
        if self.config.fraud_ring_count > 0 and self.config.compromised_account_count > 0:
            sample_size = min(self.config.compromised_account_count, len(profiles))
            compromised = random.sample(profiles, sample_size)
            ring_size = max(2, len(compromised) // self.config.fraud_ring_count)

            for i in range(self.config.fraud_ring_count):
                ring_members = compromised[i * ring_size:(i + 1) * ring_size]
                if len(ring_members) < 2:
                    _logger.warning(
                        "Ring %d has only %d member(s) — skipping (need at least 2). "
                        "Increase compromised_account_count or reduce fraud_ring_count.",
                        i + 1, len(ring_members),
                    )
                    continue
                shared_device = f"dev_ring_{uuid.uuid4().hex[:8]}"
                for p in ring_members:
                    fraud_ring_device_map[p.user_id] = shared_device
                ring_definitions.append({
                    "ring_id": f"ring_{i + 1}",
                    "shared_device": shared_device,
                    "member_count": len(ring_members),
                    "member_ids": [p.user_id for p in ring_members],
                })

        # 3. Choose compromised accounts for individual fraud injection
        fraud_user_ids = set(fraud_ring_device_map.keys())
        extra_needed = max(0, self.config.compromised_account_count - len(fraud_user_ids))
        if extra_needed > 0:
            remaining = [p for p in profiles if p.user_id not in fraud_user_ids]
            extra = random.sample(remaining, min(extra_needed, len(remaining)))
            fraud_user_ids.update(p.user_id for p in extra)

        # 4. Generate transactions
        all_transactions = []
        fraud_count_target = int(self.config.transaction_count * self.config.fraud_rate)
        legit_count = self.config.transaction_count - fraud_count_target

        # Legitimate transactions
        max_offset_secs = self.config.span_days * 86400 - 1
        for _ in range(legit_count):
            profile = random.choice(profiles)
            meta = user_meta_by_id.get(profile.user_id, user_meta[0])
            ts = start_time + timedelta(seconds=random.randint(0, max_offset_secs))
            try:
                txn = generate_transaction(profile, home_city=meta["home_city"], base_timestamp=ts)
                all_transactions.append({
                    "transaction": txn.model_dump(mode="json"),
                    "user_id": profile.user_id,
                    "is_fraud": False,
                    "fraud_type": None,
                })
            except Exception as e:
                _logger.warning("Skipped legit transaction for user %s: %s", profile.user_id, e)

        # Fraud transactions
        fraud_profiles = [p for p in profiles if p.user_id in fraud_user_ids]
        if not fraud_profiles:
            _logger.warning(
                "No compromised accounts found; falling back to first 5 profiles as fraud targets. "
                "Set compromised_account_count > 0 to designate specific accounts."
            )
            fraud_profiles = profiles[:5]

        fraud_types = self.config.fraud_types
        injected_count = 0
        while injected_count < fraud_count_target:
            fraud_type = random.choice(fraud_types)
            profile = random.choice(fraud_profiles)
            meta = user_meta_by_id.get(profile.user_id, user_meta[0])
            ts = start_time + timedelta(seconds=random.randint(0, max_offset_secs))

            try:
                base_txn = generate_transaction(profile, home_city=meta["home_city"], base_timestamp=ts)
                injected_txns, inject_meta = _apply_injection(
                    fraud_type, base_txn, profile,
                    fraud_ring_device_map.get(profile.user_id), ts,
                )
                for txn in injected_txns:
                    all_transactions.append({
                        "transaction": txn.model_dump(mode="json"),
                        "user_id": profile.user_id,
                        "is_fraud": True,
                        "fraud_type": fraud_type,
                        "injection_metadata": inject_meta,
                    })
                    injected_count += 1
                    if injected_count >= fraud_count_target:
                        break
            except Exception as e:
                # Log but do NOT increment injected_count — failed injection is not a success
                _logger.warning(
                    "Fraud injection failed (type=%s, user=%s): %s",
                    fraud_type, profile.user_id, e,
                )

        # Shuffle preserves the seed's reproducibility
        random.shuffle(all_transactions)

        # Compute summary from actual generated data (not from targets)
        actual_fraud = sum(1 for t in all_transactions if t["is_fraud"])
        actual_total = len(all_transactions)

        return {
            "run_id": self.run_id,
            "scenario_name": self.config.name,
            "description": self.config.description,
            "run_config": {
                "seed": self.config.seed,
                "user_count": self.config.user_count,
                "transaction_count": self.config.transaction_count,
                "fraud_rate": self.config.fraud_rate,
                "span_days": self.config.span_days,
                "fraud_types": self.config.fraud_types,
                "fraud_ring_count": self.config.fraud_ring_count,
                "compromised_account_count": self.config.compromised_account_count,
            },
            "summary": {
                "total_users": len(profiles),
                "total_transactions": actual_total,
                "fraud_transactions": actual_fraud,
                "legit_transactions": actual_total - actual_fraud,
                "actual_fraud_rate": round(actual_fraud / max(1, actual_total), 4),
                "fraud_rings": len(ring_definitions),
                "compromised_accounts": len(fraud_user_ids),
                "span_days": self.config.span_days,
                "fraud_types_used": list(set(t["fraud_type"] for t in all_transactions if t["is_fraud"])),
            },
            "fraud_rings": ring_definitions,
            "transactions": all_transactions,
            "users": user_meta,
        }


def _apply_injection(fraud_type, base_txn, profile, shared_device_id, ts):
    """Route to the correct injector and always return (List[Transaction], metadata)."""
    if fraud_type == "account_takeover":
        txn, meta = inject_account_takeover(base_txn, profile)
        return [txn], meta
    elif fraud_type == "card_testing":
        return inject_card_testing_series(profile, base_timestamp=ts)
    elif fraud_type == "money_mule":
        txn, meta = inject_money_mule(base_txn, profile)
        return [txn], meta
    elif fraud_type == "synthetic_identity":
        txn, meta = inject_synthetic_identity(base_txn, shared_device_id)
        return [txn], meta
    elif fraud_type == "velocity_attack":
        return inject_velocity_attack(profile, base_timestamp=ts)
    elif fraud_type == "merchant_abuse":
        txn, meta = inject_merchant_abuse(base_txn)
        return [txn], meta
    else:
        return [base_txn], {"fraud_type": fraud_type}


def build_scenario(name: str = "small_demo", custom_config: Dict = None) -> Dict[str, Any]:
    """Public entry point — build a named or custom scenario."""
    if custom_config:
        config = ScenarioConfig(**custom_config)
    elif name in PRESET_SCENARIOS:
        config = PRESET_SCENARIOS[name]
    else:
        raise ValueError(f"Unknown scenario '{name}'. Available: {list(PRESET_SCENARIOS.keys())}")

    builder = ScenarioBuilder(config)
    return builder.build()
