"""
Shared utilities for all AI fraud detection agents.

Provides:
  - ParallelAgentOutput  — Pydantic model; validates/clamps raw LLM dicts
  - build_parallel_output() — factory: raw dict → validated output dict
  - sanitize()           — truncate + redact prompt injection
  - sanitize_list()      — safe list sanitization for prompt inclusion
  - parse_llm_json()     — extract first JSON object from LLM text
  - compute_fallback_confidence() — evidence-based confidence (not hardcoded)

All agents use these utilities instead of implementing their own.
"""

import json
import logging
import re
import time
from typing import Any, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROMPT_MAX_CHARS = 2000       # Hard cap on any single text field in a prompt
SUMMARY_MAX_CHARS = 800       # evidence_summary truncation limit
LIST_ITEM_MAX_CHARS = 120     # Per-item limit for signal/finding lists
LIST_MAX_ITEMS = 10           # Max items from any list in a prompt

# Known prompt injection prefix patterns (targeted, low false-positive)
_INJECTION_RE = re.compile(
    r'(?:'
    r'ignore\s+(?:previous|above|all)\s+(?:instructions?|prompts?|context)'
    r'|disregard\s+(?:previous|above|all)\s+(?:instructions?|prompts?)'
    r'|you\s+are\s+now\s+(?:a|an)\s+'
    r'|\[INST\]'
    r'|\[/INST\]'
    r'|<\|im_start\|>'
    r'|<\|im_end\|>'
    r')',
    re.IGNORECASE,
)

_JSON_RE = re.compile(r'\{.*\}', re.DOTALL)

# Valid verdict sets per agent type
VALID_BEHAVIOR_VERDICTS: Set[str] = {"normal", "suspicious", "high_risk"}
VALID_DEVICE_VERDICTS: Set[str] = {"trusted", "suspicious", "high_risk"}
VALID_GEO_VERDICTS: Set[str] = {"normal", "unusual", "impossible"}
VALID_MERCHANT_VERDICTS: Set[str] = {"trusted", "risky", "high_risk"}
VALID_GRAPH_VERDICTS: Set[str] = {"clean", "suspicious", "fraud_ring"}
VALID_INVESTIGATION_VERDICTS: Set[str] = {
    "legitimate", "suspicious", "likely_fraud", "definite_fraud"
}


# ---------------------------------------------------------------------------
# Typed contract for the 5 parallel analysis agents
# ---------------------------------------------------------------------------

class ParallelAgentOutput(BaseModel):
    """
    Validated output contract for the 5 parallel analysis agents.
    Enforces field bounds before the dict reaches the consensus engine.
    """
    model_config = ConfigDict(frozen=True)

    risk_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    key_findings: List[str] = Field(default_factory=list)
    verdict: str = "unknown"

    def to_dict(self, verdict_key: str) -> dict:
        """Return the legacy dict format with agent-specific verdict key name."""
        return {
            "risk_score": self.risk_score,
            "confidence": self.confidence,
            "key_findings": self.key_findings,
            verdict_key: self.verdict,
        }


# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

def sanitize(text: Any, max_chars: int = SUMMARY_MAX_CHARS) -> str:
    """
    Truncate text to max_chars and redact known prompt injection patterns.
    Returns a safe string for inclusion in LLM prompts.
    """
    if not isinstance(text, str):
        return str(text)[:max_chars] if text is not None else ""
    safe = _INJECTION_RE.sub("[REDACTED]", text)
    if len(safe) > max_chars:
        safe = safe[:max_chars] + "…[truncated]"
    return safe


def sanitize_list(items: Any, max_items: int = LIST_MAX_ITEMS,
                  max_item_chars: int = LIST_ITEM_MAX_CHARS) -> List[str]:
    """Sanitize a list of strings for prompt inclusion."""
    if not isinstance(items, list):
        return []
    result = []
    for item in items[:max_items]:
        if isinstance(item, str):
            result.append(sanitize(item, max_item_chars))
        elif item is not None:
            result.append(str(item)[:max_item_chars])
    return result


# ---------------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------------

def parse_llm_json(text: str, agent_name: str) -> Optional[dict]:
    """
    Extract the first JSON object from LLM response text.
    Returns None if no valid JSON object is found.
    """
    if not text:
        _logger.debug("Agent %s: empty LLM response", agent_name)
        return None
    match = _JSON_RE.search(text)
    if not match:
        _logger.debug("Agent %s: no JSON object found in LLM response (len=%d)", agent_name, len(text))
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as exc:
        _logger.debug("Agent %s: JSON parse failed — %s", agent_name, exc)
        return None


# ---------------------------------------------------------------------------
# Output validation / clamping
# ---------------------------------------------------------------------------

def _clamp_float(value: Any, lo: float, hi: float, default: float,
                 field: str, agent: str) -> float:
    """Parse a raw value as float and clamp it to [lo, hi]."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        _logger.debug("Agent %s: non-numeric %s=%r, using default %.2f", agent, field, value, default)
        return default
    clamped = max(lo, min(hi, v))
    if clamped != v:
        _logger.debug("Agent %s: %s=%.2f out of [%.0f, %.0f], clamped to %.2f", agent, field, v, lo, hi, clamped)
    return clamped


def build_parallel_output(
    data: dict,
    agent_name: str,
    verdict_key: str,
    valid_verdicts: Set[str],
    default_verdict: str,
) -> dict:
    """
    Build a validated, clamped output dict from a raw LLM response dict.
    Always returns a dict with correct types and in-range values.
    """
    risk_score = _clamp_float(data.get("risk_score"), 0.0, 100.0, 50.0, "risk_score", agent_name)
    confidence = _clamp_float(data.get("confidence"), 0.0, 1.0, 0.70, "confidence", agent_name)

    raw_findings = data.get("key_findings", [])
    if isinstance(raw_findings, list):
        findings = [str(f)[:LIST_ITEM_MAX_CHARS] for f in raw_findings[:5] if f is not None]
    elif isinstance(raw_findings, str):
        findings = [raw_findings[:LIST_ITEM_MAX_CHARS]]
    else:
        findings = []
    if not findings:
        findings = [f"{agent_name}_analysis_complete"]

    raw_verdict = str(data.get(verdict_key, default_verdict)).lower().strip()
    verdict = raw_verdict if raw_verdict in valid_verdicts else default_verdict

    output = ParallelAgentOutput(
        risk_score=round(risk_score, 1),
        confidence=round(confidence, 3),
        key_findings=findings,
        verdict=verdict,
    )
    return output.to_dict(verdict_key)


# ---------------------------------------------------------------------------
# Dynamic confidence (replaces hardcoded constants in fallbacks)
# ---------------------------------------------------------------------------

def compute_fallback_confidence(risk_score: float, evidence_count: int,
                                has_pattern_match: bool) -> float:
    """
    Compute a data-driven confidence for deterministic fallbacks.
    Replaces hardcoded 0.70–0.88 constants across agent fallbacks.

    Ranges from ~0.60 (no evidence, no pattern, borderline risk)
    to ~0.88 (rich evidence, pattern match, extreme score).
    """
    base = 0.60
    base += min(0.12, evidence_count * 0.015)
    if has_pattern_match:
        base += 0.08
    # Extreme scores (near 0 or 100) are more certain than borderline 50
    certainty = abs(risk_score - 50.0) / 50.0
    base += certainty * 0.08
    return round(min(0.88, base), 3)


# ---------------------------------------------------------------------------
# Shared scoring formulas (single source of truth for mock + fallback)
# ---------------------------------------------------------------------------

def geo_risk_score(geo_velocity: float, location_delta: float) -> float:
    """Unified geo risk blending — used by both mock_llm and geo_agent fallback."""
    return min(100.0, geo_velocity * 0.7 + location_delta * 30.0)


def graph_risk_score(graph_risk: float, kill_chain_similarity: float) -> float:
    """Unified graph risk blending — used by both mock_llm and graph_agent fallback."""
    return min(100.0, graph_risk * 0.7 + kill_chain_similarity * 30.0)
