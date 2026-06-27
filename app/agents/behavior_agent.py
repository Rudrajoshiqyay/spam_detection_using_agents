"""Behavior Agent — analyzes transaction against user's behavioral baseline."""

import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._agent_base import (
    VALID_BEHAVIOR_VERDICTS,
    build_parallel_output,
    compute_fallback_confidence,
    parse_llm_json,
    sanitize,
    sanitize_list,
    SUMMARY_MAX_CHARS,
)
from app.agents._llm_clients import fast_ainvoke
from app.models.evidence import InvestigationPackage

_logger = logging.getLogger(__name__)
_AGENT_NAME = "behavior"
_VERDICT_KEY = "behavior_verdict"

_SYSTEM = """You are a fraud detection behavior analysis agent. Analyze the evidence package and return ONLY a JSON object with these exact keys:
{
  "risk_score": <0-100 integer>,
  "confidence": <0.0-1.0 float>,
  "key_findings": [<list of 1-3 short strings>],
  "behavior_verdict": "<normal|suspicious|high_risk>"
}
No explanation outside the JSON."""


async def run_behavior_agent(package: InvestigationPackage) -> dict:
    from app.agents.mock_llm import is_mock, mock_behavior
    if is_mock():
        return mock_behavior(package)

    t0 = time.perf_counter()
    prompt = (
        f"EVIDENCE PACKAGE:\n{sanitize(package.evidence_summary, SUMMARY_MAX_CHARS)}\n\n"
        f"Behavior similarity score: {package.behavior_similarity_score:.1f}/100\n"
        f"Risk deltas: {sanitize_list(list(package.risk_deltas.items()), max_items=6)}\n"
        f"Cohort: {sanitize(str(package.cohort), 80)}, "
        f"deviation: {package.cohort_deviation_score:.1f}, "
        f"percentile: {package.cohort_percentile:.1f}\n"
        f"Active sequences: {sanitize_list(package.active_sequences)}\n\n"
        f"Analyze behavioral anomalies and return JSON."
    )

    try:
        resp = await fast_ainvoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
        )
        data = parse_llm_json(resp.content, _AGENT_NAME)
        if data is not None:
            result = build_parallel_output(
                data, _AGENT_NAME, _VERDICT_KEY, VALID_BEHAVIOR_VERDICTS, "suspicious"
            )
            _logger.debug(
                "Agent %s: LLM success in %.0fms txn=%s risk=%.0f conf=%.2f",
                _AGENT_NAME, (time.perf_counter() - t0) * 1000,
                package.transaction_id, result["risk_score"], result["confidence"],
            )
            return result
    except Exception as exc:
        _logger.warning(
            "Agent %s: LLM call failed after %.0fms for txn=%s — using fallback. %s: %s",
            _AGENT_NAME, (time.perf_counter() - t0) * 1000,
            package.transaction_id, type(exc).__name__, exc,
        )

    score = min(100.0, package.behavior_similarity_score * 0.6 + package.cohort_deviation_score * 0.4)
    confidence = compute_fallback_confidence(score, len(package.evidence_items), bool(package.matched_pattern))
    signals = package.positive_signals[:2] or ["behavior_fallback_scoring"]
    verdict = "high_risk" if score > 70 else ("suspicious" if score > 40 else "normal")
    _logger.debug("Agent %s: fallback score=%.0f confidence=%.3f", _AGENT_NAME, score, confidence)
    return {
        "risk_score": round(score, 1),
        "confidence": confidence,
        "key_findings": signals,
        "behavior_verdict": verdict,
    }
