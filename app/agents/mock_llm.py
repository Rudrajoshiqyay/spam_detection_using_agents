"""
Mock LLM helper — returns deterministic, realistic-looking responses
when MOCK_LLM=true. Lets the full pipeline run without an API key.
"""

from app.agents._agent_base import geo_risk_score, graph_risk_score
from app.config import settings


def is_mock() -> bool:
    # startup validation (validate_production_config) ensures MOCK_LLM=false
    # implies a valid Groq key, so checking the key prefix here is redundant
    return settings.mock_llm


def mock_behavior(package) -> dict:
    score = min(100, package.behavior_similarity_score * 0.6 + package.cohort_deviation_score * 0.4)
    return {
        "risk_score": round(score),
        "confidence": 0.82,
        "key_findings": _top_signals(package.positive_signals, 2) or ["behavior_within_cohort_range"],
        "behavior_verdict": "high_risk" if score > 70 else ("suspicious" if score > 40 else "normal"),
    }


def mock_device(package) -> dict:
    score = round((1.0 - package.device_trust_score) * 100)
    return {
        "risk_score": score,
        "confidence": 0.85,
        "key_findings": _top_signals(package.positive_signals, 2) or ["device_trust_evaluated"],
        "device_verdict": "high_risk" if score > 70 else ("suspicious" if score > 40 else "trusted"),
    }


def mock_geo(package) -> dict:
    score = round(geo_risk_score(package.geo_velocity_score, package.risk_deltas.get("location", 0)))
    return {
        "risk_score": score,
        "confidence": 0.88,
        "key_findings": (
            ["impossible_travel_detected"] if score > 80
            else (["new_location"] if score > 30 else ["location_normal"])
        ),
        "geo_verdict": "impossible" if score > 80 else ("unusual" if score > 30 else "normal"),
    }


def mock_merchant(package) -> dict:
    score = round((1.0 - package.merchant_reputation_score) * 100)
    return {
        "risk_score": score,
        "confidence": 0.80,
        "key_findings": ["high_risk_merchant"] if score > 60 else ["merchant_reputable"],
        "merchant_verdict": "high_risk" if score > 70 else ("risky" if score > 40 else "trusted"),
    }


def mock_graph(package) -> dict:
    score = round(graph_risk_score(package.graph_risk_score, package.kill_chain_similarity))
    return {
        "risk_score": score,
        "confidence": 0.78,
        "key_findings": package.graph_signals[:2] or ["no_network_anomalies"],
        "network_verdict": "fraud_ring" if score > 70 else ("suspicious" if score > 35 else "clean"),
    }


def mock_investigation(package, consensus) -> dict:
    prob = consensus.risk_score / 100.0
    verdict = (
        "definite_fraud" if prob > 0.85 else
        "likely_fraud" if prob > 0.65 else
        "suspicious" if prob > 0.40 else
        "legitimate"
    )
    return {
        "investigation_verdict": verdict,
        "fraud_probability": round(prob, 3),
        "primary_fraud_type": package.matched_pattern,
        "key_evidence": [e.description for e in package.evidence_items[:3]],
        "investigation_notes": (
            f"Risk score {consensus.risk_score:.0f}/100 with {consensus.confidence_score:.0f}% confidence. "
            f"{'Pattern ' + package.matched_pattern + ' matched.' if package.matched_pattern else 'No specific pattern matched.'} "
            f"{'Kill chain ' + package.matched_kill_chain + ' detected at stage ' + str(package.kill_chain_stage) + '.' if package.matched_kill_chain else ''}"
        ).strip(),
    }


def mock_explainability(package, consensus, counterfactual, investigation) -> dict:
    risk = consensus.risk_score
    factors = package.positive_signals[:4] or ["no_strong_signals"]
    return {
        "human_explanation": (
            f"This transaction was flagged because it shows {'several unusual patterns' if risk > 60 else 'some minor anomalies'} compared to your normal behavior."
            + (f" We detected a {package.matched_pattern.replace('_', ' ')} pattern." if package.matched_pattern else "")
        ),
        "analyst_explanation": (
            f"Risk score: {risk:.0f}/100 (confidence {consensus.confidence_score:.0f}%). "
            f"Primary driver: {counterfactual.primary_contributor}. "
            f"Active signals: {factors}. "
            f"Pattern: {package.matched_pattern or 'none'}. Kill chain: {package.matched_kill_chain or 'none'}."
        ),
        "executive_explanation": (
            f"Transaction scored {risk:.0f}/100 on fraud risk assessment. "
            f"{'Immediate action recommended.' if risk > 75 else ('Monitoring advised.' if risk > 45 else 'Transaction appears legitimate.')}"
        ),
        "contributing_factors": factors,
    }


def mock_analyst(package, consensus, investigation) -> dict:
    risk = consensus.risk_score
    if risk <= 25:   action = "APPROVED"
    elif risk <= 45: action = "MONITORING"
    elif risk <= 60: action = "STEP_UP_AUTH"
    elif risk <= 75: action = "TEMPORARY_HOLD"
    elif risk <= 90: action = "BLOCKED"
    else:            action = "ESCALATED"

    reasons = {
        "APPROVED": "Transaction passed all checks with low risk score.",
        "MONITORING": "Slightly elevated risk — flagged for review without blocking.",
        "STEP_UP_AUTH": "Risk level warrants additional authentication before proceeding.",
        "TEMPORARY_HOLD": "Significant risk signals detected — transaction held pending review.",
        "BLOCKED": "High fraud probability — transaction blocked to protect the customer.",
        "ESCALATED": (
            f"Critical risk score {risk:.0f}/100"
            f"{' with fraud ring indicators' if package.graph_risk_score > 60 else ''}. "
            f"Requires immediate analyst review."
        ),
    }
    return {
        "recommended_action": action,
        "reason": reasons[action],
        "confidence": 0.85,
        "supporting_evidence": package.positive_signals[:3],
    }


def mock_story(package, consensus, explainability, recommendation, counterfactual) -> str:
    risk = consensus.risk_score
    action = (
        recommendation.get("recommended_action", "MONITORING")
        if isinstance(recommendation, dict)
        else recommendation.recommended_action.value
    )

    story_parts = [
        f"## Fraud Investigation Report — Transaction {package.transaction_id}",
        "",
        f"**Risk Score: {risk:.0f}/100 | Decision: {action} | Confidence: {consensus.confidence_score:.0f}%**",
        "",
        "### What Happened",
    ]

    if package.matched_pattern:
        story_parts.append(
            f"The system detected a **{package.matched_pattern.replace('_', ' ').title()}** pattern "
            f"with {package.pattern_similarity:.0%} similarity."
        )
    if package.matched_kill_chain:
        story_parts.append(
            f"The transaction matches the **{package.matched_kill_chain.replace('_', ' ').title()}** "
            f"kill chain at stage: *{package.kill_chain_stage}*."
        )
    if package.active_sequences:
        story_parts.append(f"Suspicious sequences identified: {', '.join(package.active_sequences)}.")

    story_parts += ["", "### Key Evidence"]
    for e in package.evidence_items[:4]:
        icon = "🔴" if e.strength.value == "strong" else ("🟡" if e.strength.value == "medium" else "⚪")
        story_parts.append(f"- {icon} **{e.type.replace('_', ' ').title()}**: {e.description}")

    story_parts += ["", "### Why This Decision"]
    story_parts.append(
        f"The primary contributor to this risk score was "
        f"**{counterfactual.primary_contributor.replace('_', ' ')}** "
        f"(weight: {counterfactual.contribution_score:.0f}/100)."
    )
    if package.negative_signals:
        story_parts.append(
            f"Trust signals that reduced the risk score: {', '.join(package.negative_signals[:3])}."
        )

    story_parts += ["", "### Agent Analysis"]
    for ar in consensus.agent_risks:
        bar = "█" * int(ar.risk_score / 10) + "░" * (10 - int(ar.risk_score / 10))
        story_parts.append(f"- **{ar.agent.title()} Agent**: {bar} {ar.risk_score:.0f}/100")

    return "\n".join(story_parts)


def _top_signals(signals: list, n: int) -> list:
    return signals[:n] if signals else []
