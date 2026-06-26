"""
Bank-Grade Fraud Detection Pipeline — LangGraph orchestration.

Full flow (Section 34):
  Transaction → Feature Store → Fast Screening → Fraud Pattern Matching →
  Sequence Intelligence → Kill Chain Matching → Cohort Analysis →
  Graph Intelligence → Parallel Agents → Consensus → Evidence Builder →
  Investigation → Counterfactual → Explainability → Analyst → Storytelling →
  Final Decision

Parallel agents run concurrently via asyncio.gather (LangGraph Fan-Out pattern).
"""

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import TypedDict, Optional, Any

from langgraph.graph import StateGraph, END

from app.models.transaction import Transaction
from app.models.user_profile import UserProfile
from app.models.evidence import InvestigationPackage
from app.models.fraud_decision import (
    FraudDetectionResult, FraudDecision, ConsensusResult,
    ExplainabilityResult, AnalystRecommendation, CounterfactualResult
)
from app.services.feature_store import feature_store
from app.services.fast_screening import screen
from app.services.fraud_patterns import match_patterns
from app.services.sequence_intelligence import analyze_sequences
from app.services.kill_chain import match_kill_chains
from app.services.cohort_analysis import analyze_cohort
from app.services.risk_delta import calculate_risk_deltas
from app.services.device_reputation import get_device_trust
from app.services.merchant_reputation import get_merchant_reputation
from app.services.geo_velocity import calculate_geo_velocity
from app.services.negative_signals import evaluate_signals
from app.services.graph_intelligence import fraud_graph
from app.services.evidence_builder import build_investigation_package
from app.services.evidence_reliability import score_evidence_reliability
from app.services.consensus_engine import compute_consensus
from app.agents.behavior_agent import run_behavior_agent
from app.agents.device_agent import run_device_agent
from app.agents.geo_agent import run_geo_agent
from app.agents.merchant_agent import run_merchant_agent
from app.agents.graph_agent import run_graph_agent
from app.agents.investigation_agent import run_investigation_agent
from app.agents.counterfactual_agent import run_counterfactual_agent
from app.agents.explainability_agent import run_explainability_agent
from app.agents.analyst_agent import run_analyst_agent
from app.agents.storytelling_agent import run_storytelling_agent


# ---------------------------------------------------------------------------
# Module-level configuration and state
# ---------------------------------------------------------------------------

_logger = logging.getLogger(__name__)

_AGENT_TIMEOUT_SECS = 30.0          # Per-agent LLM call timeout
_PIPELINE_TIMEOUT_SECS = 120.0      # End-to-end pipeline timeout
_ENABLE_STORYTELLING = True         # Set False to skip storytelling for faster responses
_DEDUP_MAX_SIZE = 10_000

_background_tasks: set = set()      # Holds fire-and-forget task refs to prevent GC cancellation
_graph_lock = threading.Lock()      # Serializes access to the shared fraud_graph singleton
_seen_transaction_ids: set = set()  # In-memory dedup (bounded to _DEDUP_MAX_SIZE)


# ---------------------------------------------------------------------------
# Pipeline State
# ---------------------------------------------------------------------------

class PipelineState(TypedDict):
    transaction: Transaction
    profile: UserProfile
    latency: dict                       # stage → elapsed_ms

    # Stage 1
    features: dict
    screening: dict
    should_investigate: bool

    # Pre-agent deterministic analysis
    pattern_result: dict
    sequence_result: dict
    kill_chain_result: dict
    cohort_result: dict
    delta_result: dict
    device_result: dict
    merchant_result: dict
    geo_result: dict
    signal_result: dict
    graph_result: dict

    # Evidence
    package: Optional[InvestigationPackage]
    reliability: dict

    # Parallel agent outputs
    behavior_risk: dict
    device_risk: dict
    geo_risk: dict
    merchant_risk: dict
    graph_risk: dict

    # Post-agent
    consensus: Optional[ConsensusResult]
    investigation: dict
    counterfactual: Optional[CounterfactualResult]
    explainability: Optional[ExplainabilityResult]
    analyst_recommendation: Optional[AnalystRecommendation]
    story: str

    # Final
    result: Optional[FraudDetectionResult]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _svc_fallback(service: str, exc: BaseException) -> dict:
    _logger.warning("Deterministic service '%s' failed, using empty result: %s", service, exc)
    return {}


# ---------------------------------------------------------------------------
# Node Implementations
# ---------------------------------------------------------------------------

async def node_feature_retrieval(state: PipelineState) -> dict:
    t0 = time.perf_counter()
    txn = state["transaction"]
    profile = state["profile"]

    try:
        features = await feature_store.get_user_features(txn.user_id)
        txn_count_1h = await feature_store.get_txn_count_window(txn.user_id, 3600)
        txn_count_24h = await feature_store.get_txn_count_window(txn.user_id, 86400)
        features["txn_count_1h"] = txn_count_1h
        features["txn_count_24h"] = txn_count_24h
    except Exception as e:
        _logger.warning(
            "Feature store unavailable for user %s, using empty features: %s", txn.user_id, e
        )
        features = {"txn_count_1h": 0, "txn_count_24h": 0}

    # Seed defaults if first-time user
    if "avg_amount_30d" not in features:
        features.setdefault("avg_amount_30d", profile.spending_profile.avg_transaction_amount)
        features.setdefault("avg_amount_7d", profile.spending_profile.avg_transaction_amount)
        features.setdefault("std_amount_30d", profile.spending_profile.avg_transaction_amount * 0.5)
        features.setdefault("merchant_diversity", 10)
        features.setdefault("geo_frequency", 2)
        features.setdefault("merchant_frequency", 0)
        features.setdefault("merchant_frequencies", {})
        features["known_devices"] = features.get("known_devices", profile.known_devices)
        features["known_locations"] = features.get("known_locations", profile.known_locations)

    elapsed = (time.perf_counter() - t0) * 1000
    return {"features": features, "latency": {**state.get("latency", {}), "feature_retrieval_ms": round(elapsed, 2)}}


async def node_fast_screening(state: PipelineState) -> dict:
    t0 = time.perf_counter()
    txn = state["transaction"]
    profile = state["profile"]
    features = state["features"]

    device_rep = await feature_store.get_device_reputation(txn.device_id)
    merchant_rep = await feature_store.get_merchant_reputation(txn.merchant_id)

    screening = screen(
        txn, profile, features, device_rep, merchant_rep,
        txn_count_1h=int(features.get("txn_count_1h", 0)),
        txn_count_24h=int(features.get("txn_count_24h", 0)),
    )
    elapsed = (time.perf_counter() - t0) * 1000
    return {
        "screening": screening,
        "should_investigate": screening["should_investigate"],
        "latency": {**state.get("latency", {}), "fast_screening_ms": round(elapsed, 2)},
    }


async def node_pre_agent_analysis(state: PipelineState) -> dict:
    """Run all deterministic pre-agent services concurrently."""
    t0 = time.perf_counter()
    txn = state["transaction"]
    profile = state["profile"]
    features = state["features"]

    recent_events = await feature_store.get_recent_events(txn.user_id, 20)

    # return_exceptions=True prevents one service failure from aborting all others
    _svc_names = ("pattern", "sequence", "cohort", "delta", "device", "merchant")
    _svc_results = await asyncio.gather(
        asyncio.to_thread(match_patterns, txn, profile, features, recent_events),
        asyncio.to_thread(analyze_sequences, txn, profile, features, recent_events),
        asyncio.to_thread(analyze_cohort, txn, profile, features),
        asyncio.to_thread(calculate_risk_deltas, txn, profile, features),
        get_device_trust(txn.device_id, txn.user_id, profile),
        get_merchant_reputation(txn.merchant_id, txn.merchant_category),
        return_exceptions=True,
    )
    (
        pattern_result, sequence_result, cohort_result,
        delta_result, device_result, merchant_result,
    ) = [
        r if not isinstance(r, BaseException) else _svc_fallback(_svc_names[i], r)
        for i, r in enumerate(_svc_results)
    ]

    # Geo velocity (needs last known position from features)
    prev_lat = features.get("last_lat")
    prev_lon = features.get("last_lon")
    prev_city = features.get("last_city")
    prev_ts_str = features.get("last_txn_ts")
    prev_ts = None
    if prev_ts_str:
        try:
            prev_ts = datetime.fromisoformat(str(prev_ts_str))
        except Exception as e:
            _logger.warning(
                "Could not parse last_txn_ts %r for user %s: %s", prev_ts_str, txn.user_id, e
            )
            prev_ts = None

    geo_result = calculate_geo_velocity(
        txn.latitude, txn.longitude, txn.location_city, txn.timestamp,
        float(prev_lat) if prev_lat else None,
        float(prev_lon) if prev_lon else None,
        prev_city, prev_ts,
    )

    # Kill chain (needs sequence result); lock guards shared singleton
    with _graph_lock:
        graph_signals_lite = fraud_graph.analyze(
            txn.user_id, txn.device_id, txn.ip_address, txn.merchant_id
        )

    kill_chain_result = match_kill_chains(txn, profile, features, sequence_result, graph_signals_lite)

    signal_result = evaluate_signals(
        txn, profile, features, delta_result, device_result,
        merchant_result, geo_result, pattern_result, kill_chain_result,
    )

    elapsed = (time.perf_counter() - t0) * 1000
    return {
        "pattern_result": pattern_result,
        "sequence_result": sequence_result,
        "kill_chain_result": kill_chain_result,
        "cohort_result": cohort_result,
        "delta_result": delta_result,
        "device_result": device_result,
        "merchant_result": merchant_result,
        "geo_result": geo_result,
        "signal_result": signal_result,
        "graph_result": graph_signals_lite,
        "latency": {**state.get("latency", {}), "pre_agent_analysis_ms": round(elapsed, 2)},
    }


async def node_build_evidence(state: PipelineState) -> dict:
    t0 = time.perf_counter()
    package = build_investigation_package(
        txn=state["transaction"],
        profile=state["profile"],
        screening_result=state["screening"],
        features=state["features"],
        pattern_result=state["pattern_result"],
        sequence_result=state["sequence_result"],
        kill_chain_result=state["kill_chain_result"],
        cohort_result=state["cohort_result"],
        delta_result=state["delta_result"],
        device_result=state["device_result"],
        merchant_result=state["merchant_result"],
        geo_result=state["geo_result"],
        signal_result=state["signal_result"],
        graph_result=state["graph_result"],
    )
    reliability = score_evidence_reliability(package)
    elapsed = (time.perf_counter() - t0) * 1000
    return {
        "package": package,
        "reliability": reliability,
        "latency": {**state.get("latency", {}), "evidence_build_ms": round(elapsed, 2)},
    }


async def node_parallel_agents(state: PipelineState) -> dict:
    """All 5 analysis agents run in parallel — no sequential execution."""
    t0 = time.perf_counter()
    package = state["package"]

    behavior_risk, device_risk, geo_risk, merchant_risk, graph_risk = await asyncio.gather(
        asyncio.wait_for(run_behavior_agent(package), timeout=_AGENT_TIMEOUT_SECS),
        asyncio.wait_for(run_device_agent(package), timeout=_AGENT_TIMEOUT_SECS),
        asyncio.wait_for(run_geo_agent(package), timeout=_AGENT_TIMEOUT_SECS),
        asyncio.wait_for(run_merchant_agent(package), timeout=_AGENT_TIMEOUT_SECS),
        asyncio.wait_for(run_graph_agent(package), timeout=_AGENT_TIMEOUT_SECS),
    )

    elapsed = (time.perf_counter() - t0) * 1000
    return {
        "behavior_risk": behavior_risk,
        "device_risk": device_risk,
        "geo_risk": geo_risk,
        "merchant_risk": merchant_risk,
        "graph_risk": graph_risk,
        "latency": {**state.get("latency", {}), "parallel_agents_ms": round(elapsed, 2)},
    }


async def node_consensus(state: PipelineState) -> dict:
    t0 = time.perf_counter()
    consensus = compute_consensus(
        behavior_risk=state["behavior_risk"],
        device_risk=state["device_risk"],
        geo_risk=state["geo_risk"],
        merchant_risk=state["merchant_risk"],
        graph_risk=state["graph_risk"],
        evidence_reliability=state["reliability"],
        pre_risk_score=state["screening"]["pre_risk_score"],
        signal_result=state["signal_result"],
    )
    elapsed = (time.perf_counter() - t0) * 1000
    return {
        "consensus": consensus,
        "latency": {**state.get("latency", {}), "consensus_ms": round(elapsed, 2)},
    }


async def node_investigation(state: PipelineState) -> dict:
    t0 = time.perf_counter()

    # Run investigation + counterfactual in parallel
    investigation, counterfactual = await asyncio.gather(
        asyncio.wait_for(
            run_investigation_agent(state["package"], state["consensus"]),
            timeout=_AGENT_TIMEOUT_SECS,
        ),
        asyncio.wait_for(
            run_counterfactual_agent(state["package"], state["consensus"]),
            timeout=_AGENT_TIMEOUT_SECS,
        ),
    )

    elapsed = (time.perf_counter() - t0) * 1000
    return {
        "investigation": investigation,
        "counterfactual": counterfactual,
        "latency": {**state.get("latency", {}), "investigation_ms": round(elapsed, 2)},
    }


async def node_explainability(state: PipelineState) -> dict:
    t0 = time.perf_counter()
    explainability = await asyncio.wait_for(
        run_explainability_agent(
            state["package"], state["consensus"],
            state["counterfactual"], state["investigation"],
        ),
        timeout=_AGENT_TIMEOUT_SECS,
    )
    elapsed = (time.perf_counter() - t0) * 1000
    return {
        "explainability": explainability,
        "latency": {**state.get("latency", {}), "explainability_ms": round(elapsed, 2)},
    }


async def node_analyst(state: PipelineState) -> dict:
    t0 = time.perf_counter()
    analyst_recommendation = await asyncio.wait_for(
        run_analyst_agent(
            state["package"], state["consensus"],
            state["explainability"], state["investigation"],
        ),
        timeout=_AGENT_TIMEOUT_SECS,
    )
    elapsed = (time.perf_counter() - t0) * 1000
    return {
        "analyst_recommendation": analyst_recommendation,
        "latency": {**state.get("latency", {}), "analyst_ms": round(elapsed, 2)},
    }


async def node_storytelling(state: PipelineState) -> dict:
    t0 = time.perf_counter()
    story = await asyncio.wait_for(
        run_storytelling_agent(
            state["package"], state["consensus"], state["explainability"],
            state["analyst_recommendation"], state["counterfactual"],
        ),
        timeout=_AGENT_TIMEOUT_SECS,
    )
    elapsed = (time.perf_counter() - t0) * 1000
    return {
        "story": story,
        "latency": {**state.get("latency", {}), "storytelling_ms": round(elapsed, 2)},
    }


async def node_final_decision(state: PipelineState) -> dict:
    latency = state.get("latency", {})
    total_ms = sum(latency.values())

    result = FraudDetectionResult(
        transaction_id=state["transaction"].transaction_id,
        user_id=state["transaction"].user_id,
        pre_risk_score=state["screening"]["pre_risk_score"],
        routed_to_deep_investigation=state["should_investigate"],
        consensus=state["consensus"],
        explainability=state["explainability"],
        counterfactual=state["counterfactual"],
        analyst_recommendation=state["analyst_recommendation"],
        final_decision=state["analyst_recommendation"].recommended_action,
        story=state.get("story", ""),
        latency_breakdown=latency,
        total_latency_ms=round(total_ms, 2),
    )

    # Use task-set pattern to prevent GC cancellation of the background update
    _task = asyncio.create_task(_update_feature_store(state))
    _background_tasks.add(_task)
    _task.add_done_callback(_background_tasks.discard)

    return {"result": result}


async def node_auto_approve(state: PipelineState) -> dict:
    """Fast path: transaction below risk threshold, skip deep investigation."""
    screening = state["screening"]

    pre_risk = screening["pre_risk_score"]
    # Auto-approve: agents did not run. Agreement reflects screening confidence,
    # not agent consensus. Confidence decreases for higher pre_risk scores.
    screening_confidence = round(max(40.0, 90.0 - pre_risk * 0.8), 2)
    consensus = ConsensusResult(
        risk_score=pre_risk,
        agreement_score=round(max(50.0, 95.0 - pre_risk * 1.2), 2),
        confidence_score=screening_confidence,
        agent_risks=[],
    )
    explainability = ExplainabilityResult(
        risk_score=screening["pre_risk_score"],
        confidence_score=screening_confidence,
        contributing_factors=screening.get("flags", []),
        evidence_summary=f"Fast screening passed. Score: {screening['pre_risk_score']:.1f}/100",
        matched_fraud_pattern=None,
        human_explanation="Your transaction has been approved after automated security checks.",
        analyst_explanation=f"Transaction passed fast screening with risk score {screening['pre_risk_score']:.1f}/100. No suspicious signals detected.",
        executive_explanation=f"Low-risk transaction approved by automated screening ({screening['pre_risk_score']:.1f}/100).",
    )
    recommendation = AnalystRecommendation(
        recommended_action=FraudDecision.approved,
        reason="Transaction passed all fast screening checks with low risk score.",
        confidence=0.90,
        supporting_evidence=state["signal_result"].get("negative_signals", []),
    )

    latency = state.get("latency", {})
    total_ms = sum(latency.values())

    result = FraudDetectionResult(
        transaction_id=state["transaction"].transaction_id,
        user_id=state["transaction"].user_id,
        pre_risk_score=pre_risk,
        routed_to_deep_investigation=False,
        consensus=consensus,
        explainability=explainability,
        analyst_recommendation=recommendation,
        final_decision=FraudDecision.approved,
        story="Transaction approved after passing automated fast-screening with no suspicious signals detected.",
        latency_breakdown=latency,
        total_latency_ms=round(total_ms, 2),
    )
    return {"result": result, "consensus": consensus, "explainability": explainability,
            "analyst_recommendation": recommendation}


# ---------------------------------------------------------------------------
# Feature store update (async, post-decision)
# ---------------------------------------------------------------------------

async def _update_feature_store(state: PipelineState):
    txn = state["transaction"]
    profile = state["profile"]
    try:
        await feature_store.record_transaction(
            txn.user_id, txn.transaction_id, txn.amount, txn.timestamp.timestamp()
        )
        await feature_store.register_device(txn.user_id, txn.device_id)
        await feature_store.register_location(
            txn.user_id, f"{txn.location_city}:{txn.location_country}"
        )
        await feature_store.increment_merchant_count(txn.user_id, txn.merchant_id)
        await feature_store.push_event(txn.user_id, {
            "type": txn.transaction_type,
            "amount": txn.amount,
            "merchant": txn.merchant_id,
            "device": txn.device_id,
            "timestamp": txn.timestamp.timestamp(),
            "is_micro": txn.amount < 100,
            "is_large": txn.amount > profile.spending_profile.avg_transaction_amount * 4,
        })
        with _graph_lock:
            fraud_graph.add_transaction(
                txn.user_id, txn.device_id, txn.ip_address,
                txn.merchant_id, txn.amount, txn.timestamp.timestamp(),
            )
    except Exception as e:
        _logger.warning("Feature store update failed for %s: %s", txn.user_id, e)


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------

def route_after_screening(state: PipelineState) -> str:
    if state["should_investigate"]:
        return "pre_agent_analysis"
    return "auto_approve"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("feature_retrieval", node_feature_retrieval)
    graph.add_node("fast_screening", node_fast_screening)
    graph.add_node("pre_agent_analysis", node_pre_agent_analysis)
    graph.add_node("build_evidence", node_build_evidence)
    graph.add_node("parallel_agents", node_parallel_agents)
    graph.add_node("consensus", node_consensus)
    graph.add_node("investigation", node_investigation)
    graph.add_node("explainability", node_explainability)
    graph.add_node("analyst", node_analyst)
    if _ENABLE_STORYTELLING:
        graph.add_node("storytelling", node_storytelling)
    graph.add_node("final_decision", node_final_decision)
    graph.add_node("auto_approve", node_auto_approve)

    graph.set_entry_point("feature_retrieval")
    graph.add_edge("feature_retrieval", "fast_screening")

    graph.add_conditional_edges(
        "fast_screening",
        route_after_screening,
        {"pre_agent_analysis": "pre_agent_analysis", "auto_approve": "auto_approve"},
    )

    graph.add_edge("pre_agent_analysis", "build_evidence")
    graph.add_edge("build_evidence", "parallel_agents")
    graph.add_edge("parallel_agents", "consensus")
    graph.add_edge("consensus", "investigation")
    graph.add_edge("investigation", "explainability")
    graph.add_edge("explainability", "analyst")
    if _ENABLE_STORYTELLING:
        graph.add_edge("analyst", "storytelling")
        graph.add_edge("storytelling", "final_decision")
    else:
        graph.add_edge("analyst", "final_decision")
    graph.add_edge("final_decision", END)
    graph.add_edge("auto_approve", END)

    return graph.compile()


# Lazy-initialized pipeline — deferred until first request to avoid import-time failures
_fraud_pipeline = None


def _get_pipeline() -> StateGraph:
    global _fraud_pipeline
    if _fraud_pipeline is None:
        _fraud_pipeline = build_pipeline()
    return _fraud_pipeline


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_fraud_detection(
    txn: Transaction,
    profile: UserProfile,
) -> FraudDetectionResult:
    if txn.user_id != profile.user_id:
        raise ValueError(
            f"user_id mismatch: transaction has '{txn.user_id}', profile has '{profile.user_id}'"
        )

    # Bounded in-memory dedup — evicts oldest half when full
    global _seen_transaction_ids
    if txn.transaction_id in _seen_transaction_ids:
        raise ValueError(f"Duplicate transaction_id: {txn.transaction_id}")
    if len(_seen_transaction_ids) >= _DEDUP_MAX_SIZE:
        half = list(_seen_transaction_ids)
        _seen_transaction_ids = set(half[len(half) // 2:])
    _seen_transaction_ids.add(txn.transaction_id)

    initial_state: PipelineState = {
        "transaction": txn,
        "profile": profile,
        "latency": {},
        "features": {},
        "screening": {},
        "should_investigate": True,
        "pattern_result": {},
        "sequence_result": {},
        "kill_chain_result": {},
        "cohort_result": {},
        "delta_result": {},
        "device_result": {},
        "merchant_result": {},
        "geo_result": {},
        "signal_result": {},
        "graph_result": {},
        "package": None,
        "reliability": {},
        "behavior_risk": {},
        "device_risk": {},
        "geo_risk": {},
        "merchant_risk": {},
        "graph_risk": {},
        "consensus": None,
        "investigation": {},
        "counterfactual": None,
        "explainability": None,
        "analyst_recommendation": None,
        "story": "",
        "result": None,
    }

    final_state = await asyncio.wait_for(
        _get_pipeline().ainvoke(initial_state), timeout=_PIPELINE_TIMEOUT_SECS
    )
    return final_state["result"]
