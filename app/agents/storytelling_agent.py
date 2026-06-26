"""
Storytelling Agent — generates a compelling, readable fraud narrative.
Designed for demo impact: makes the AI reasoning transparent and impressive.
"""

import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._agent_base import sanitize, sanitize_list
from app.agents._llm_clients import get_deep_llm
from app.models.evidence import InvestigationPackage
from app.models.fraud_decision import (
    AnalystRecommendation, ConsensusResult, CounterfactualResult, ExplainabilityResult,
)

_logger = logging.getLogger(__name__)
_AGENT_NAME = "storytelling"

_SYSTEM = """You are a fraud detection storytelling agent. Generate a clear, engaging narrative that explains the fraud investigation process and outcome.
Write 3-4 paragraphs. Be specific about signals. Use plain English. Make the AI's reasoning transparent.
This will be shown to bank executives and fraud analysts. Focus on clarity and insight."""


async def run_storytelling_agent(
    package: InvestigationPackage,
    consensus: ConsensusResult,
    explainability: ExplainabilityResult,
    analyst_recommendation: AnalystRecommendation,
    counterfactual: CounterfactualResult,
) -> str:
    from app.agents.mock_llm import is_mock, mock_story
    if is_mock():
        return mock_story(package, consensus, explainability, analyst_recommendation, counterfactual)

    t0 = time.perf_counter()
    lines = package.evidence_summary.split("\n")
    txn_line = sanitize(lines[0] if lines else "", 200)
    user_line = sanitize(lines[1] if len(lines) > 1 else "", 200)
    agent_scores = "\n".join(
        f"  {ar.agent}: {ar.risk_score:.0f}/100"
        for ar in consensus.agent_risks
    )
    prompt = (
        f"Generate a fraud investigation narrative for this case:\n\n"
        f"TRANSACTION: {txn_line}\n"
        f"USER: {user_line}\n\n"
        f"RISK SCORE: {consensus.risk_score:.0f}/100 (confidence: {consensus.confidence_score:.0f}%)\n"
        f"DECISION: {analyst_recommendation.recommended_action.value}\n\n"
        f"WHAT THE SYSTEM FOUND:\n"
        f"- Fraud pattern: {sanitize(str(package.matched_pattern or 'No pattern matched'), 80)}\n"
        f"- Kill chain: {sanitize(str(package.matched_kill_chain or 'None'), 80)} "
        f"at stage: {sanitize(str(package.kill_chain_stage or 'N/A'), 60)}\n"
        f"- Suspicious sequences: {sanitize_list(package.active_sequences or [])}\n"
        f"- Key positive signals: {sanitize_list(package.positive_signals[:4])}\n"
        f"- Key trust signals: {sanitize_list(package.negative_signals[:3])}\n\n"
        f"PRIMARY CONTRIBUTOR: {sanitize(counterfactual.primary_contributor, 80)} "
        f"({counterfactual.contribution_score:.0f}/100)\n\n"
        f"AGENT SCORES:\n{agent_scores}\n\n"
        f"ANALYST SAYS: {sanitize(analyst_recommendation.reason, 300)}\n\n"
        f"Write the investigation story now:"
    )

    try:
        resp = await get_deep_llm().ainvoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
        )
        _logger.debug(
            "Agent %s: LLM success in %.0fms txn=%s",
            _AGENT_NAME, (time.perf_counter() - t0) * 1000, package.transaction_id,
        )
        return resp.content
    except Exception as exc:
        _logger.warning(
            "Agent %s: LLM call failed after %.0fms for txn=%s — using fallback. %s: %s",
            _AGENT_NAME, (time.perf_counter() - t0) * 1000,
            package.transaction_id, type(exc).__name__, exc,
        )

    action = analyst_recommendation.recommended_action.value
    risk = consensus.risk_score
    return (
        f"The fraud detection system analyzed this transaction and assigned a risk score of {risk:.0f}/100. "
        f"{'Multiple suspicious signals were identified.' if risk > 50 else 'The transaction appeared within normal parameters.'} "
        f"The primary contributing factor was {sanitize(counterfactual.primary_contributor, 80)}. "
        f"Based on the evidence, the system recommends: {action}. "
        f"Analyst note: {sanitize(analyst_recommendation.reason, 200)}"
    )
