"""Geo Agent — analyzes location and travel velocity signals."""

import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._agent_base import (
    VALID_GEO_VERDICTS,
    build_parallel_output,
    compute_fallback_confidence,
    geo_risk_score,
    parse_llm_json,
    sanitize,
    sanitize_list,
    SUMMARY_MAX_CHARS,
)
from app.agents._llm_clients import fast_ainvoke
from app.models.evidence import InvestigationPackage

_logger = logging.getLogger(__name__)
_AGENT_NAME = "geo"
_VERDICT_KEY = "geo_verdict"

_SYSTEM = """You are a fraud detection geo-location analysis agent. Analyze location and travel signals and return ONLY a JSON object:
{
  "risk_score": <0-100 integer>,
  "confidence": <0.0-1.0 float>,
  "key_findings": [<list of 1-3 short strings>],
  "geo_verdict": "<normal|unusual|impossible>"
}
No explanation outside the JSON."""


async def run_geo_agent(package: InvestigationPackage) -> dict:
    from app.agents.mock_llm import is_mock, mock_geo
    if is_mock():
        return mock_geo(package)

    t0 = time.perf_counter()
    loc_delta = package.risk_deltas.get("location", 0.0)
    geo_sigs = [s for s in package.positive_signals if any(k in s for k in ("travel", "location", "geo", "international"))]
    prompt = (
        f"GEO ANALYSIS:\n"
        f"Geo velocity score: {package.geo_velocity_score:.1f}/100\n"
        f"Location delta: {loc_delta:.3f}\n"
        f"Evidence summary:\n{sanitize(package.evidence_summary, SUMMARY_MAX_CHARS)}\n\n"
        f"Geo-related signals: {sanitize_list(geo_sigs)}\n"
        f"Location trust signals: {sanitize_list([s for s in package.negative_signals if 'location' in s])}\n\n"
        f"Analyze geo-location risk and return JSON."
    )

    try:
        resp = await fast_ainvoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
        )
        data = parse_llm_json(resp.content, _AGENT_NAME)
        if data is not None:
            result = build_parallel_output(
                data, _AGENT_NAME, _VERDICT_KEY, VALID_GEO_VERDICTS, "normal"
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

    # Unified formula — same as mock_geo in mock_llm.py
    loc_delta = package.risk_deltas.get("location", 0.0)
    score = geo_risk_score(package.geo_velocity_score, loc_delta)
    confidence = compute_fallback_confidence(score, len(package.evidence_items), bool(package.matched_pattern))
    verdict = "impossible" if score > 80 else ("unusual" if score > 30 else "normal")
    _logger.debug("Agent %s: fallback score=%.0f confidence=%.3f", _AGENT_NAME, score, confidence)
    return {
        "risk_score": round(score, 1),
        "confidence": confidence,
        "key_findings": ["geo_velocity_score_used"],
        "geo_verdict": verdict,
    }
