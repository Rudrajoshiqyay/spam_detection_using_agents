"""Graph Agent — analyzes network/graph intelligence signals."""

import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._agent_base import (
    VALID_GRAPH_VERDICTS,
    build_parallel_output,
    compute_fallback_confidence,
    graph_risk_score,
    parse_llm_json,
    sanitize,
    sanitize_list,
    SUMMARY_MAX_CHARS,
)
from app.agents._llm_clients import fast_ainvoke
from app.models.evidence import InvestigationPackage

_logger = logging.getLogger(__name__)
_AGENT_NAME = "graph"
_VERDICT_KEY = "network_verdict"

_SYSTEM = """You are a fraud detection graph network analysis agent. Analyze network signals and return ONLY a JSON object:
{
  "risk_score": <0-100 integer>,
  "confidence": <0.0-1.0 float>,
  "key_findings": [<list of 1-3 short strings>],
  "network_verdict": "<clean|suspicious|fraud_ring>"
}
No explanation outside the JSON."""


async def run_graph_agent(package: InvestigationPackage) -> dict:
    from app.agents.mock_llm import is_mock, mock_graph
    if is_mock():
        return mock_graph(package)

    t0 = time.perf_counter()
    graph_sigs = [s for s in package.positive_signals if any(k in s for k in ("ring", "device", "network", "graph"))]
    prompt = (
        f"GRAPH NETWORK ANALYSIS:\n"
        f"Graph risk score: {package.graph_risk_score:.1f}/100\n"
        f"Graph signals: {sanitize_list(package.graph_signals)}\n"
        f"Kill chain: {sanitize(str(package.matched_kill_chain), 80)} at stage {sanitize(str(package.kill_chain_stage), 60)}\n"
        f"Kill chain similarity: {package.kill_chain_similarity:.3f}\n"
        f"Graph-related signals: {sanitize_list(graph_sigs)}\n\n"
        f"Evidence summary:\n{sanitize(package.evidence_summary, SUMMARY_MAX_CHARS)}\n\n"
        f"Analyze network/graph risk and return JSON."
    )

    try:
        resp = await fast_ainvoke(
            [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
        )
        data = parse_llm_json(resp.content, _AGENT_NAME)
        if data is not None:
            result = build_parallel_output(
                data, _AGENT_NAME, _VERDICT_KEY, VALID_GRAPH_VERDICTS, "clean"
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

    # Unified formula — same as mock_graph in mock_llm.py
    score = graph_risk_score(package.graph_risk_score, package.kill_chain_similarity)
    confidence = compute_fallback_confidence(score, len(package.evidence_items), bool(package.matched_pattern))
    verdict = "fraud_ring" if score > 70 else ("suspicious" if score > 35 else "clean")
    _logger.debug("Agent %s: fallback score=%.0f confidence=%.3f", _AGENT_NAME, score, confidence)
    return {
        "risk_score": round(score, 1),
        "confidence": confidence,
        "key_findings": package.graph_signals[:2] or ["no_network_anomalies"],
        "network_verdict": verdict,
    }
