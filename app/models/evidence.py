from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class EvidenceStrength(str, Enum):
    strong = "strong"
    medium = "medium"
    weak = "weak"


# Reference constants for common evidence types.
# EvidenceItem.type is kept as str to support dynamic labels (e.g. "trust_signal:known_device").
class EvidenceType:
    IMPOSSIBLE_TRAVEL = "impossible_travel"
    FRAUD_RING = "fraud_ring"
    SHARED_DEVICE = "shared_device"
    FRAUD_PATTERN = "fraud_pattern"
    KILL_CHAIN = "kill_chain"
    SEQUENCE = "sequence"
    MERCHANT_REPUTATION = "merchant_reputation"
    BEHAVIOR_DEVIATION = "behavior_deviation"
    TRANSACTION_TIME = "transaction_time"
    MERCHANT_NOVELTY = "merchant_novelty"


class EvidenceItem(BaseModel):
    type: str
    description: str
    value: Any
    strength: EvidenceStrength
    reliability_score: float = Field(ge=0, le=1)
    contributes_to_fraud: bool = True


class InvestigationPackage(BaseModel):
    transaction_id: str
    user_id: str

    # Pre-computed signals (Stage 1)
    pre_risk_score: float = Field(ge=0, le=100)
    features: Dict[str, Any] = {}

    # Pattern analysis — similarity is 0–1 (fraction of signals matched)
    matched_pattern: Optional[str] = None
    pattern_similarity: float = Field(default=0.0, ge=0.0, le=1.0)
    matched_kill_chain: Optional[str] = None
    kill_chain_stage: Optional[str] = None
    kill_chain_similarity: float = Field(default=0.0, ge=0.0, le=1.0)

    # Sequence intelligence — risk score 0–100
    active_sequences: List[str] = []
    sequence_risk_score: float = Field(default=0.0, ge=0.0, le=100.0)

    # Cohort analysis — deviation and percentile on 0–100 scale
    cohort: Optional[str] = None
    cohort_deviation_score: float = Field(default=0.0, ge=0.0, le=100.0)
    cohort_percentile: float = Field(default=0.0, ge=0.0, le=100.0)

    # Delta signals
    risk_deltas: Dict[str, float] = {}

    # Reputation signals — trust probability 0–1; velocity risk 0–100
    device_trust_score: float = Field(default=0.5, ge=0.0, le=1.0)
    merchant_reputation_score: float = Field(default=0.5, ge=0.0, le=1.0)
    geo_velocity_score: float = Field(default=0.0, ge=0.0, le=100.0)

    # Graph signals — risk score 0–100
    graph_risk_score: float = Field(default=0.0, ge=0.0, le=100.0)
    graph_signals: List[str] = []

    # Behavior — anomaly score 0–100 (0 = normal, 100 = completely foreign)
    behavior_similarity_score: float = Field(default=0.0, ge=0.0, le=100.0)

    # All evidence items
    evidence_items: List[EvidenceItem] = []

    # Compressed summary for LLM (token-efficient)
    evidence_summary: str = ""
    positive_signals: List[str] = []
    negative_signals: List[str] = []
