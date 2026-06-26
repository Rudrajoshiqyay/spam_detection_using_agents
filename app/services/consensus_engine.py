"""
Consensus Engine — aggregates all agent risk scores into a final verdict.

Inputs : behavior_risk, device_risk, geo_risk, merchant_risk, graph_risk
Outputs: risk_score, agreement_score, confidence_score

Formulas:
  weighted_risk   = weighted_average(present_agent_scores)
                    Missing agents: weight redistributed to present agents.
                    If ALL agents missing: falls back to pre_risk_score.
  agreement_score = 100 - (std_dev(present_scores) * 1.5)
                    Penalised 10 points per missing agent.
  confidence_score = agreement_score * evidence_reliability_factor
"""

import logging
import math
from typing import Dict, Any, List

from app.models.fraud_decision import AgentRisk, ConsensusResult

_logger = logging.getLogger(__name__)

# Agent weights reflect signal quality. Must sum to 1.0.
_AGENT_WEIGHTS: Dict[str, float] = {
    "behavior": 0.25,
    "device": 0.20,
    "geo": 0.20,
    "merchant": 0.15,
    "graph": 0.20,
}


def compute_consensus(
    behavior_risk: Dict[str, Any],
    device_risk: Dict[str, Any],
    geo_risk: Dict[str, Any],
    merchant_risk: Dict[str, Any],
    graph_risk: Dict[str, Any],
    evidence_reliability: Dict[str, Any],
    pre_risk_score: float,
    signal_result: Dict[str, Any],
) -> ConsensusResult:
    agent_sources = {
        "behavior": behavior_risk,
        "device": device_risk,
        "geo": geo_risk,
        "merchant": merchant_risk,
        "graph": graph_risk,
    }

    # Separate agents that returned a real score from those that failed/timed out.
    present_scores: Dict[str, float] = {}
    missing_agents: List[str] = []

    for agent, source in agent_sources.items():
        if "risk_score" in source:
            present_scores[agent] = float(source["risk_score"])
        else:
            missing_agents.append(agent)

    if missing_agents:
        _logger.warning(
            "ConsensusEngine: %d agent(s) missing scores — %s. "
            "Redistributing weight among present agents.",
            len(missing_agents), missing_agents,
        )

    # Weighted risk with proportional redistribution for missing agents.
    # This avoids biasing the consensus toward 50 (old sentinel) when agents
    # fail: the present agents' relative weights are preserved.
    if present_scores:
        total_present_weight = sum(_AGENT_WEIGHTS[a] for a in present_scores)
        weighted_risk = sum(
            score * (_AGENT_WEIGHTS[agent] / total_present_weight)
            for agent, score in present_scores.items()
        )
    else:
        # All agents failed — fall back to Stage-1 pre-screening score.
        weighted_risk = pre_risk_score
        _logger.error(
            "ConsensusEngine: ALL agents missing scores — using pre_risk_score=%.1f as fallback.",
            pre_risk_score,
        )

    # Blend with pre_risk_score (Stage 1 is deterministic, high confidence)
    signal_risk = float(signal_result.get("signal_risk_score", 50))
    blended_risk = weighted_risk * 0.70 + pre_risk_score * 0.20 + signal_risk * 0.10

    # Agreement score: lower std = higher agreement.
    scores_list = list(present_scores.values())
    if len(scores_list) >= 2:
        mean = sum(scores_list) / len(scores_list)
        variance = sum((s - mean) ** 2 for s in scores_list) / len(scores_list)
        std_dev = math.sqrt(variance)
        base_agreement = max(0.0, 100.0 - std_dev * 1.5)
    elif len(scores_list) == 1:
        base_agreement = 60.0  # single agent — moderate confidence
    else:
        base_agreement = 0.0   # no agents — no agreement

    # Penalise 10 points per missing agent so callers know the estimate is weaker.
    agreement_score = max(0.0, base_agreement - len(missing_agents) * 10.0)

    # Confidence score = agreement * evidence reliability factor
    reliability_factor = evidence_reliability.get("net_fraud_confidence", 0.5)
    evidence_verdict = evidence_reliability.get("evidence_verdict", "weak")
    verdict_boost = {
        "overwhelming": 1.0,
        "strong": 0.90,
        "moderate": 0.75,
        "weak": 0.55,
        "insufficient": 0.40,
    }.get(evidence_verdict, 0.60)

    confidence_score = min(100.0, agreement_score * verdict_boost * (0.5 + reliability_factor * 0.5))

    # Build per-agent report. Missing agents are shown with pre_risk_score
    # as their display value and an explicit "agent_unavailable" finding so
    # consumers can distinguish missing from low-risk.
    agent_risks = []
    for agent in _AGENT_WEIGHTS:
        if agent in present_scores:
            score = present_scores[agent]
            findings = _extract_findings(
                agent, behavior_risk, device_risk, geo_risk, merchant_risk, graph_risk
            )
        else:
            score = pre_risk_score  # best available prior; clearly flagged below
            findings = ["agent_unavailable"]
        agent_risks.append(
            AgentRisk(
                agent=agent,
                risk_score=round(score, 2),
                # `confidence` field stores agent weight (architectural constant).
                # For LLM confidence, see key_findings[0] or per-agent outputs.
                confidence=round(_AGENT_WEIGHTS[agent], 2),
                key_findings=findings,
            )
        )

    return ConsensusResult(
        risk_score=round(min(100.0, blended_risk), 2),
        agreement_score=round(agreement_score, 2),
        confidence_score=round(confidence_score, 2),
        agent_risks=agent_risks,
    )


def _extract_findings(
    agent: str, behavior, device, geo, merchant, graph
) -> List[str]:
    source = {
        "behavior": behavior,
        "device": device,
        "geo": geo,
        "merchant": merchant,
        "graph": graph,
    }[agent]
    return source.get("key_findings", [])
