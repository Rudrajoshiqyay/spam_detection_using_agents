"""
Explainability Agent — generates three levels of explanation:
  1. human_explanation     — plain English (for customers)
  2. analyst_explanation   — technical detail (for fraud analysts)
  3. executive_explanation — board-level 1-2 sentences
"""

import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._agent_base import parse_llm_json, sanitize, sanitize_list, SUMMARY_MAX_CHARS
from app.agents._llm_clients import deep_ainvoke
from app.models.evidence import InvestigationPackage
from app.models.fraud_decision import (
    ConsensusResult, CounterfactualResult, ExplainabilityResult,
)

_logger = logging.getLogger(__name__)
_AGENT_NAME = "explainability"

_SYSTEM = """You are a fraud explainability agent. Generate three levels of explanation.
Return ONLY a JSON object:
{
  "human_explanation": "<plain English, 1-2 sentences, no jargon>",
  "analyst_explanation": "<technical detail with signal names and scores, 2-3 sentences>",
  "executive_explanation": "<1-2 sentence board summary with business impact>",
  "contributing_factors": [<3-5 key factors as short strings>]
}"""


async def run_explainability_agent(
    package: InvestigationPackage,
    consensus: ConsensusResult,
    counterfactual: CounterfactualResult,
    investigation_result: dict,
) -> ExplainabilityResult:
    from app.agents.mock_llm import is_mock, mock_explainability
    if is_mock():
        data = mock_explainability(package, consensus, counterfactual, investigation_result)
        return ExplainabilityResult(
            risk_score=consensus.risk_score,
            confidence_score=consensus.confidence_score,
            contributing_factors=data["contributing_factors"],
            evidence_summary=package.evidence_summary,
            matched_fraud_pattern=package.matched_pattern,
            human_explanation=data["human_explanation"],
            analyst_explanation=data["analyst_explanation"],
            executive_explanation=data["executive_explanation"],
        )

    t0 = time.perf_counter()
    # Cap evidence items to top 6 with truncated descriptions
    fraud_evidence = "\n".join(
        f"  - {sanitize(e.description, 150)}"
        for e in package.evidence_items[:6]
        if e.contributes_to_fraud
    )
    summary_line = sanitize(package.evidence_summary.split("\n")[0] if package.evidence_summary else "", 200)
    prompt = (
        f"FRAUD ANALYSIS RESULTS:\n"
        f"Transaction: {summary_line}\n"
        f"Risk Score: {consensus.risk_score:.0f}/100\n"
        f"Confidence: {consensus.confidence_score:.0f}/100\n"
        f"Investigation verdict: {sanitize(str(investigation_result.get('investigation_verdict', 'unknown')), 60)}\n\n"
        f"Primary contributor: {sanitize(counterfactual.primary_contributor, 80)} "
        f"(weight: {counterfactual.contribution_score:.0f})\n"
        f"Fraud pattern: {sanitize(str(package.matched_pattern or 'none'), 80)}\n"
        f"Kill chain: {sanitize(str(package.matched_kill_chain or 'none'), 80)}\n\n"
        f"Key evidence:\n{fraud_evidence}\n\n"
        f"Positive signals: {sanitize_list(package.positive_signals)}\n"
        f"Trust signals: {sanitize_list(package.negative_signals)}\n\n"
        f"Generate three levels of explanation and return JSON."
    )

    try:
        resp = await deep_ainvoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
        )
        data = parse_llm_json(resp.content, _AGENT_NAME)
        if data is not None:
            factors = data.get("contributing_factors", package.positive_signals[:5])
            if not isinstance(factors, list):
                factors = package.positive_signals[:5]
            result = ExplainabilityResult(
                risk_score=consensus.risk_score,
                confidence_score=consensus.confidence_score,
                contributing_factors=[str(f)[:100] for f in factors[:5]],
                evidence_summary=package.evidence_summary,
                matched_fraud_pattern=package.matched_pattern,
                human_explanation=sanitize(
                    data.get("human_explanation", "Transaction flagged as potentially suspicious."), 500
                ),
                analyst_explanation=sanitize(
                    data.get("analyst_explanation", f"Risk score {consensus.risk_score:.0f}/100."), 800
                ),
                executive_explanation=sanitize(
                    data.get("executive_explanation", f"Transaction flagged with {consensus.risk_score:.0f}/100 risk."), 400
                ),
            )
            _logger.debug(
                "Agent %s: LLM success in %.0fms txn=%s",
                _AGENT_NAME, (time.perf_counter() - t0) * 1000, package.transaction_id,
            )
            return result
    except Exception as exc:
        _logger.warning(
            "Agent %s: LLM call failed after %.0fms for txn=%s — using fallback. %s: %s",
            _AGENT_NAME, (time.perf_counter() - t0) * 1000,
            package.transaction_id, type(exc).__name__, exc,
        )

    risk = consensus.risk_score
    _logger.debug("Agent %s: fallback risk=%.0f", _AGENT_NAME, risk)
    return ExplainabilityResult(
        risk_score=risk,
        confidence_score=consensus.confidence_score,
        contributing_factors=package.positive_signals[:5],
        evidence_summary=package.evidence_summary,
        matched_fraud_pattern=package.matched_pattern,
        human_explanation="This transaction was flagged because it shows unusual patterns for your account.",
        analyst_explanation=(
            f"Risk score {risk:.0f}/100. Primary driver: {counterfactual.primary_contributor}. "
            f"Signals: {package.positive_signals[:3]}."
        ),
        executive_explanation=(
            f"Transaction scored {risk:.0f}/100 fraud risk. "
            f"Recommended action based on {len(package.evidence_items)} evidence signals."
        ),
    )
