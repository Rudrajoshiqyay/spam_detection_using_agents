"""Merchant Agent — analyzes merchant reputation and transaction context."""

import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._agent_base import (
    VALID_MERCHANT_VERDICTS,
    build_parallel_output,
    compute_fallback_confidence,
    parse_llm_json,
    sanitize,
    sanitize_list,
    SUMMARY_MAX_CHARS,
)
from app.agents._llm_clients import get_fast_llm
from app.models.evidence import InvestigationPackage

_logger = logging.getLogger(__name__)
_AGENT_NAME = "merchant"
_VERDICT_KEY = "merchant_verdict"

_SYSTEM = """You are a fraud detection merchant analysis agent. Analyze merchant signals and return ONLY a JSON object:
{
  "risk_score": <0-100 integer>,
  "confidence": <0.0-1.0 float>,
  "key_findings": [<list of 1-3 short strings>],
  "merchant_verdict": "<trusted|risky|high_risk>"
}
No explanation outside the JSON."""


async def run_merchant_agent(package: InvestigationPackage) -> dict:
    from app.agents.mock_llm import is_mock, mock_merchant
    if is_mock():
        return mock_merchant(package)

    t0 = time.perf_counter()
    rep = package.merchant_reputation_score
    merchant_sigs = [s for s in package.positive_signals if any(k in s for k in ("merchant", "refund"))]
    prompt = (
        f"MERCHANT ANALYSIS:\n"
        f"Merchant reputation score: {rep:.3f} (0=high risk, 1=trusted)\n"
        f"Merchant delta: {package.risk_deltas.get('merchant', 0):.3f}\n"
        f"Pattern matched: {sanitize(str(package.matched_pattern), 80)}\n"
        f"Merchant signals: {sanitize_list(merchant_sigs)}\n"
        f"Trust signals: {sanitize_list([s for s in package.negative_signals if 'merchant' in s])}\n\n"
        f"Evidence summary:\n{sanitize(package.evidence_summary, SUMMARY_MAX_CHARS)}\n\n"
        f"Analyze merchant risk and return JSON."
    )

    try:
        resp = await get_fast_llm().ainvoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
        )
        data = parse_llm_json(resp.content, _AGENT_NAME)
        if data is not None:
            result = build_parallel_output(
                data, _AGENT_NAME, _VERDICT_KEY, VALID_MERCHANT_VERDICTS, "risky"
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

    score = round((1.0 - rep) * 100, 1)
    confidence = compute_fallback_confidence(score, len(package.evidence_items), bool(package.matched_pattern))
    verdict = "high_risk" if score > 70 else ("risky" if score > 40 else "trusted")
    _logger.debug("Agent %s: fallback score=%.0f confidence=%.3f", _AGENT_NAME, score, confidence)
    return {
        "risk_score": score,
        "confidence": confidence,
        "key_findings": ["merchant_reputation_score_used"],
        "merchant_verdict": verdict,
    }
