"""Investigation Agent — deep LLM investigation of the full evidence package."""

import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._agent_base import (
    VALID_INVESTIGATION_VERDICTS,
    parse_llm_json,
    sanitize,
    sanitize_list,
    _clamp_float,
    SUMMARY_MAX_CHARS,
)
from app.agents._llm_clients import get_deep_llm
from app.models.evidence import InvestigationPackage
from app.models.fraud_decision import ConsensusResult

_logger = logging.getLogger(__name__)
_AGENT_NAME = "investigation"

_SYSTEM = """You are a senior fraud investigator at a bank. Given evidence and agent consensus, perform a deep investigation.
Return ONLY a JSON object:
{
  "investigation_verdict": "<legitimate|suspicious|likely_fraud|definite_fraud>",
  "fraud_probability": <0.0-1.0>,
  "primary_fraud_type": "<type or null>",
  "key_evidence": [<list of 2-4 most important findings>],
  "investigation_notes": "<2-3 sentence professional assessment>"
}"""


def _build_investigation_result(
    verdict: str, fraud_prob: float, fraud_type, key_evidence: list, notes: str
) -> dict:
    """Build a validated investigation result dict."""
    v = verdict if verdict in VALID_INVESTIGATION_VERDICTS else "suspicious"
    p = max(0.0, min(1.0, float(fraud_prob))) if isinstance(fraud_prob, (int, float)) else 0.5
    e = [str(item)[:200] for item in key_evidence[:5]] if isinstance(key_evidence, list) else []
    return {
        "investigation_verdict": v,
        "fraud_probability": round(p, 3),
        "primary_fraud_type": str(fraud_type) if fraud_type else None,
        "key_evidence": e,
        "investigation_notes": sanitize(str(notes), 500),
    }


async def run_investigation_agent(
    package: InvestigationPackage,
    consensus: ConsensusResult,
) -> dict:
    from app.agents.mock_llm import is_mock, mock_investigation
    if is_mock():
        return mock_investigation(package, consensus)

    t0 = time.perf_counter()
    agent_breakdown = "\n".join(
        f"  {ar.agent}: {ar.risk_score:.0f}/100 — {ar.key_findings[:2]}"
        for ar in consensus.agent_risks
    )
    # Cap evidence items to top 5 with truncated descriptions
    top_evidence = "\n".join(
        f"  [{e.strength.value}] {e.type}: {sanitize(e.description, 120)}"
        for e in package.evidence_items[:5]
    )
    prompt = (
        f"FULL INVESTIGATION PACKAGE:\n{sanitize(package.evidence_summary, SUMMARY_MAX_CHARS)}\n\n"
        f"EVIDENCE ITEMS ({len(package.evidence_items)} total, top 5 shown):\n{top_evidence}\n\n"
        f"AGENT CONSENSUS:\n"
        f"  Risk Score: {consensus.risk_score:.1f}/100\n"
        f"  Agreement: {consensus.agreement_score:.1f}/100\n"
        f"  Confidence: {consensus.confidence_score:.1f}/100\n\n"
        f"AGENT BREAKDOWN:\n{agent_breakdown}\n\n"
        f"Fraud Pattern: {sanitize(str(package.matched_pattern or 'none'), 80)}\n"
        f"Kill Chain: {sanitize(str(package.matched_kill_chain or 'none'), 80)} "
        f"({sanitize(str(package.kill_chain_stage or 'n/a'), 60)})\n\n"
        f"Perform deep investigation and return JSON."
    )

    try:
        resp = await get_deep_llm().ainvoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
        )
        data = parse_llm_json(resp.content, _AGENT_NAME)
        if data is not None:
            result = _build_investigation_result(
                verdict=data.get("investigation_verdict", "suspicious"),
                fraud_prob=data.get("fraud_probability", consensus.risk_score / 100.0),
                fraud_type=data.get("primary_fraud_type"),
                key_evidence=data.get("key_evidence", []),
                notes=data.get("investigation_notes", ""),
            )
            _logger.debug(
                "Agent %s: LLM success in %.0fms txn=%s verdict=%s prob=%.3f",
                _AGENT_NAME, (time.perf_counter() - t0) * 1000,
                package.transaction_id, result["investigation_verdict"], result["fraud_probability"],
            )
            return result
    except Exception as exc:
        _logger.warning(
            "Agent %s: LLM call failed after %.0fms for txn=%s — using fallback. %s: %s",
            _AGENT_NAME, (time.perf_counter() - t0) * 1000,
            package.transaction_id, type(exc).__name__, exc,
        )

    prob = consensus.risk_score / 100.0
    _logger.debug("Agent %s: fallback prob=%.3f", _AGENT_NAME, prob)
    return {
        "investigation_verdict": (
            "definite_fraud" if prob > 0.85 else
            "likely_fraud" if prob > 0.65 else
            "suspicious" if prob > 0.40 else "legitimate"
        ),
        "fraud_probability": round(prob, 3),
        "primary_fraud_type": package.matched_pattern,
        "key_evidence": [sanitize(e.description, 150) for e in package.evidence_items[:3]],
        "investigation_notes": (
            f"Risk score {consensus.risk_score:.0f}/100 with "
            f"{consensus.confidence_score:.0f}% confidence."
        ),
    }
