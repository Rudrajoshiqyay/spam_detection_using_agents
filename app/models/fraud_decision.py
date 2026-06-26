from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime, timezone


class FraudDecision(str, Enum):
    approved = "APPROVED"
    monitoring = "MONITORING"
    step_up_auth = "STEP_UP_AUTH"
    temporary_hold = "TEMPORARY_HOLD"
    blocked = "BLOCKED"
    escalated = "ESCALATED"


class AgentRisk(BaseModel):
    agent: str
    risk_score: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)       # agent weight / certainty (0–1)
    key_findings: List[str] = []


class ConsensusResult(BaseModel):
    # All scores on 0–100 scale (risk score and percentage-based agreement/confidence)
    risk_score: float = Field(ge=0, le=100)
    agreement_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    agent_risks: List[AgentRisk] = []


class CounterfactualResult(BaseModel):
    primary_contributor: str
    contribution_score: float = Field(ge=0, le=100)
    counterfactuals: Dict[str, float] = {}   # factor → risk_if_removed


class ExplainabilityResult(BaseModel):
    # risk_score and confidence_score both on 0–100 scale
    risk_score: float = Field(ge=0, le=100)
    confidence_score: float = Field(ge=0, le=100)
    contributing_factors: List[str]
    evidence_summary: str
    matched_fraud_pattern: Optional[str]
    human_explanation: str
    analyst_explanation: str
    executive_explanation: str


class AnalystRecommendation(BaseModel):
    recommended_action: FraudDecision
    reason: str
    confidence: float = Field(ge=0, le=1)       # recommendation certainty (0–1)
    supporting_evidence: List[str] = []


class FraudDetectionResult(BaseModel):
    transaction_id: str
    user_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Stage 1
    pre_risk_score: float = Field(ge=0, le=100)
    routed_to_deep_investigation: bool

    # Consensus
    consensus: ConsensusResult

    # Explainability
    explainability: ExplainabilityResult
    counterfactual: Optional[CounterfactualResult] = None

    # Final decision
    analyst_recommendation: AnalystRecommendation
    final_decision: FraudDecision
    story: str = ""

    # Latency breakdown (ms)
    latency_breakdown: Dict[str, float] = {}
    total_latency_ms: float = 0.0
