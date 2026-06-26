"""
Counterfactual Analysis Agent — determines which factors drove the fraud classification
by asking: what would the risk be if this factor were removed?
"""

import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._agent_base import parse_llm_json, sanitize, sanitize_list, SUMMARY_MAX_CHARS
from app.agents._llm_clients import get_fast_llm
from app.models.evidence import InvestigationPackage
from app.models.fraud_decision import ConsensusResult, CounterfactualResult

_logger = logging.getLogger(__name__)
_AGENT_NAME = "counterfactual"

_SYSTEM = """You are a counterfactual reasoning agent for fraud detection.
Determine which factor contributed MOST to the fraud classification.
Return ONLY a JSON object:
{
  "primary_contributor": "<factor name>",
  "contribution_score": <0-100>,
  "counterfactuals": {
    "<factor>": <risk_if_removed_0_to_100>,
    ...
  },
  "reasoning": "<1 sentence>"
}"""

# Signal → estimated contribution weight (0–100)
_SIGNAL_WEIGHTS = {
    "impossible_travel": 95,
    "fraud_pattern_match": 85,
    "kill_chain_match": 80,
    "new_device": 70,
    "velocity_spike": 65,
    "high_amount": 60,
    "new_location": 55,
    "international_unexpected": 50,
    "unusual_location": 50,
}


def _deterministic_counterfactual(
    package: InvestigationPackage, consensus: ConsensusResult
) -> CounterfactualResult:
    """Signal-weight-based fallback when LLM is unavailable."""
    if not package.positive_signals:
        return CounterfactualResult(
            primary_contributor="no_signals",
            contribution_score=0.0,
            counterfactuals={},
        )
    primary = max(
        package.positive_signals,
        key=lambda s: _SIGNAL_WEIGHTS.get(s, 30),
        default="unknown",
    )
    active = {k: v for k, v in _SIGNAL_WEIGHTS.items() if k in package.positive_signals}
    counterfactuals = {
        k: max(0.0, consensus.risk_score - v * 0.5)
        for k, v in active.items()
    }
    return CounterfactualResult(
        primary_contributor=primary,
        contribution_score=float(min(100, _SIGNAL_WEIGHTS.get(primary, 50))),
        counterfactuals=counterfactuals,
    )


async def run_counterfactual_agent(
    package: InvestigationPackage,
    consensus: ConsensusResult,
) -> CounterfactualResult:
    from app.agents.mock_llm import is_mock
    if is_mock():
        active = {k: v for k, v in _SIGNAL_WEIGHTS.items() if k in package.positive_signals}
        primary = max(
            package.positive_signals,
            key=lambda s: _SIGNAL_WEIGHTS.get(s, 30),
            default="unknown",
        )
        return CounterfactualResult(
            primary_contributor=primary,
            contribution_score=float(min(100, _SIGNAL_WEIGHTS.get(primary, 50))),
            counterfactuals={
                k: max(0.0, consensus.risk_score - v * 0.4)
                for k, v in active.items()
            },
        )

    t0 = time.perf_counter()
    factors: dict = {}
    if "new_device" in package.positive_signals:
        factors["device_was_known"] = "device recognized"
    if any(s in package.positive_signals for s in ("new_location", "unusual_location")):
        factors["location_was_known"] = "location familiar"
    if "high_amount" in package.positive_signals:
        factors["amount_was_normal"] = "amount within usual range"
    if package.matched_pattern:
        factors["no_pattern_match"] = "no fraud pattern matched"
    if package.geo_velocity_score > 50:
        factors["travel_was_feasible"] = "travel physically possible"
    if package.graph_risk_score > 40:
        factors["no_graph_risk"] = "no network connections to fraud"
    if not factors:
        factors["no_anomalies"] = "transaction looked normal"

    scenarios = "\n".join(f"  - If {sanitize(k, 60)}: {sanitize(v, 80)}" for k, v in factors.items())
    prompt = (
        f"FRAUD DECISION: Risk score {consensus.risk_score:.0f}/100\n\n"
        f"ACTIVE POSITIVE SIGNALS: {sanitize_list(package.positive_signals)}\n"
        f"ACTIVE NEGATIVE SIGNALS: {sanitize_list(package.negative_signals)}\n\n"
        f"COUNTERFACTUAL SCENARIOS TO EVALUATE:\n{scenarios}\n\n"
        f"Current primary risk drivers:\n"
        f"- Pre-risk score: {package.pre_risk_score:.1f}\n"
        f"- Behavior similarity: {package.behavior_similarity_score:.1f}\n"
        f"- Geo velocity: {package.geo_velocity_score:.1f}\n"
        f"- Graph risk: {package.graph_risk_score:.1f}\n"
        f"- Matched pattern: {sanitize(str(package.matched_pattern or 'none'), 80)}\n\n"
        f"Determine which factor contributed most to this decision and return JSON."
    )

    try:
        resp = await get_fast_llm().ainvoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
        )
        data = parse_llm_json(resp.content, _AGENT_NAME)
        if data is not None:
            raw_score = data.get("contribution_score", 50)
            contribution = max(0.0, min(100.0, float(raw_score) if isinstance(raw_score, (int, float, str)) else 50.0))
            raw_cf = data.get("counterfactuals", {})
            counterfactuals = {
                str(k): max(0.0, min(100.0, float(v)))
                for k, v in raw_cf.items()
                if isinstance(v, (int, float))
            } if isinstance(raw_cf, dict) else {}
            result = CounterfactualResult(
                primary_contributor=sanitize(str(data.get("primary_contributor", "unknown")), 100),
                contribution_score=contribution,
                counterfactuals=counterfactuals,
            )
            _logger.debug(
                "Agent %s: LLM success in %.0fms txn=%s contributor=%s score=%.0f",
                _AGENT_NAME, (time.perf_counter() - t0) * 1000,
                package.transaction_id, result.primary_contributor, result.contribution_score,
            )
            return result
    except Exception as exc:
        _logger.warning(
            "Agent %s: LLM call failed after %.0fms for txn=%s — using fallback. %s: %s",
            _AGENT_NAME, (time.perf_counter() - t0) * 1000,
            package.transaction_id, type(exc).__name__, exc,
        )

    result = _deterministic_counterfactual(package, consensus)
    _logger.debug(
        "Agent %s: fallback contributor=%s score=%.0f",
        _AGENT_NAME, result.primary_contributor, result.contribution_score,
    )
    return result
