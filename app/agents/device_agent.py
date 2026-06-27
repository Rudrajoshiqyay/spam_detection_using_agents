"""Device Agent — analyzes device trust and reputation signals."""

import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._agent_base import (
    VALID_DEVICE_VERDICTS,
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
_AGENT_NAME = "device"
_VERDICT_KEY = "device_verdict"

_SYSTEM = """You are a fraud detection device analysis agent. Analyze device signals and return ONLY a JSON object:
{
  "risk_score": <0-100 integer>,
  "confidence": <0.0-1.0 float>,
  "key_findings": [<list of 1-3 short strings>],
  "device_verdict": "<trusted|suspicious|high_risk>"
}
No explanation outside the JSON."""


async def run_device_agent(package: InvestigationPackage) -> dict:
    from app.agents.mock_llm import is_mock, mock_device
    if is_mock():
        return mock_device(package)

    t0 = time.perf_counter()
    trust = package.device_trust_score
    prompt = (
        f"DEVICE ANALYSIS:\n"
        f"Device trust score: {trust:.3f} (0=no trust, 1=fully trusted)\n"
        f"Known device: {trust > 0.7}\n"
        f"Graph signals: {sanitize_list(package.graph_signals)}\n"
        f"Positive signals: {sanitize_list(package.positive_signals)}\n"
        f"Negative signals: {sanitize_list(package.negative_signals)}\n\n"
        f"Evidence summary:\n{sanitize(package.evidence_summary, SUMMARY_MAX_CHARS)}\n\n"
        f"Analyze device risk and return JSON."
    )

    try:
        resp = await fast_ainvoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
        )
        data = parse_llm_json(resp.content, _AGENT_NAME)
        if data is not None:
            result = build_parallel_output(
                data, _AGENT_NAME, _VERDICT_KEY, VALID_DEVICE_VERDICTS, "suspicious"
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

    score = round((1.0 - trust) * 100, 1)
    confidence = compute_fallback_confidence(score, len(package.evidence_items), bool(package.matched_pattern))
    verdict = "high_risk" if score > 70 else ("suspicious" if score > 40 else "trusted")
    _logger.debug("Agent %s: fallback score=%.0f confidence=%.3f", _AGENT_NAME, score, confidence)
    return {
        "risk_score": score,
        "confidence": confidence,
        "key_findings": ["device_trust_score_used"],
        "device_verdict": verdict,
    }
