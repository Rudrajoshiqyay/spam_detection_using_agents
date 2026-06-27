"""
Analyst Recommendation Agent — simulates a human fraud analyst decision.

Actions: APPROVED | MONITORING | STEP_UP_AUTH | TEMPORARY_HOLD | BLOCKED | ESCALATED
"""

import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._agent_base import (
    _clamp_float,
    compute_fallback_confidence,
    parse_llm_json,
    sanitize,
    sanitize_list,
)
from app.agents._llm_clients import deep_ainvoke
from app.models.evidence import InvestigationPackage
from app.models.fraud_decision import (
    AnalystRecommendation, ConsensusResult, ExplainabilityResult, FraudDecision,
)

_logger = logging.getLogger(__name__)
_AGENT_NAME = "analyst"

_SYSTEM = """You are a senior fraud analyst at a bank making the final action recommendation.
Actions available: APPROVED, MONITORING, STEP_UP_AUTH, TEMPORARY_HOLD, BLOCKED, ESCALATED.

Guidelines:
- 0-25 risk: APPROVED
- 26-45 risk: MONITORING
- 46-60 risk: STEP_UP_AUTH
- 61-75 risk: TEMPORARY_HOLD
- 76-90 risk: BLOCKED
- 91-100 risk OR fraud_ring/kill_chain detected: ESCALATED

Return ONLY a JSON object:
{
  "recommended_action": "<one of the 6 actions>",
  "reason": "<1-2 sentence reason>",
  "confidence": <0.0-1.0>,
  "supporting_evidence": [<2-3 key evidence strings>]
}"""


async def run_analyst_agent(
    package: InvestigationPackage,
    consensus: ConsensusResult,
    explainability: ExplainabilityResult,
    investigation_result: dict,
) -> AnalystRecommendation:
    from app.agents.mock_llm import is_mock, mock_analyst
    if is_mock():
        data = mock_analyst(package, consensus, investigation_result)
        action = FraudDecision(data["recommended_action"])
        return AnalystRecommendation(
            recommended_action=action,
            reason=data["reason"],
            confidence=data["confidence"],
            supporting_evidence=data["supporting_evidence"],
        )

    t0 = time.perf_counter()
    fraud_ring = any("fraud_ring" in s or "ring" in s for s in package.graph_signals)
    prompt = (
        f"ANALYST DECISION REQUEST:\n"
        f"Risk Score: {consensus.risk_score:.0f}/100\n"
        f"Confidence: {consensus.confidence_score:.0f}/100\n"
        f"Agreement: {consensus.agreement_score:.0f}/100\n\n"
        f"Investigation verdict: {sanitize(str(investigation_result.get('investigation_verdict', 'unknown')), 60)}\n"
        f"Fraud probability: {investigation_result.get('fraud_probability', 0):.1%}\n"
        f"Primary fraud type: {sanitize(str(investigation_result.get('primary_fraud_type', 'unknown')), 80)}\n\n"
        f"Fraud ring detected: {fraud_ring}\n"
        f"Kill chain matched: {package.matched_kill_chain is not None}\n"
        f"Kill chain stage: {sanitize(str(package.kill_chain_stage or 'N/A'), 60)}\n\n"
        f"Contributing factors: {sanitize_list(explainability.contributing_factors)}\n"
        f"Human explanation: {sanitize(explainability.human_explanation, 300)}\n\n"
        f"Trust signals present: {sanitize_list(package.negative_signals)}\n\n"
        f"Make your action recommendation and return JSON."
    )

    try:
        resp = await deep_ainvoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
        )
        data = parse_llm_json(resp.content, _AGENT_NAME)
        if data is not None:
            action_str = str(data.get("recommended_action", "MONITORING")).upper()
            try:
                action = FraudDecision(action_str)
            except ValueError:
                action = _fallback_action(consensus.risk_score)
            confidence = _clamp_float(data.get("confidence", 0.75), 0.0, 1.0, 0.75, "confidence", _AGENT_NAME)
            result = AnalystRecommendation(
                recommended_action=action,
                reason=sanitize(str(data.get("reason", "Based on risk assessment.")), 400),
                confidence=confidence,
                supporting_evidence=[str(e)[:100] for e in data.get("supporting_evidence", [])[:3]
                                     if isinstance(data.get("supporting_evidence"), list)],
            )
            _logger.debug(
                "Agent %s: LLM success in %.0fms txn=%s action=%s",
                _AGENT_NAME, (time.perf_counter() - t0) * 1000,
                package.transaction_id, result.recommended_action.value,
            )
            return result
    except Exception as exc:
        _logger.warning(
            "Agent %s: LLM call failed after %.0fms for txn=%s — using fallback. %s: %s",
            _AGENT_NAME, (time.perf_counter() - t0) * 1000,
            package.transaction_id, type(exc).__name__, exc,
        )

    action = _fallback_action(consensus.risk_score)
    confidence = compute_fallback_confidence(
        consensus.risk_score, len(package.evidence_items), bool(package.matched_pattern)
    )
    _logger.debug("Agent %s: fallback action=%s", _AGENT_NAME, action.value)
    return AnalystRecommendation(
        recommended_action=action,
        reason=f"Risk score {consensus.risk_score:.0f}/100 triggers {action.value} protocol.",
        confidence=confidence,
        supporting_evidence=package.positive_signals[:3],
    )


def _fallback_action(risk_score: float) -> FraudDecision:
    if risk_score <= 25:
        return FraudDecision.approved
    elif risk_score <= 45:
        return FraudDecision.monitoring
    elif risk_score <= 60:
        return FraudDecision.step_up_auth
    elif risk_score <= 75:
        return FraudDecision.temporary_hold
    elif risk_score <= 90:
        return FraudDecision.blocked
    else:
        return FraudDecision.escalated
