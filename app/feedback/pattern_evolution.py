"""
Pattern Evolution Agent — discovers emerging fraud behaviors from feedback
and updates the fraud pattern library + kill chain definitions.

Core (always runs): deterministic signal weight adjustment from feedback stats.
Optional: LLM-generated new pattern discovery (run periodically, not on hot path).
"""

import json
import logging
import os
import re
import tempfile
from typing import Dict, Any, Optional
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents._llm_clients import get_fast_llm
from app.feedback.feedback_store import (
    get_feedback_stats, get_recent_feedback, record_pattern_update,
)

_logger = logging.getLogger(__name__)

_PATTERNS_PATH = Path(__file__).parent.parent / "data" / "fraud_patterns.json"

# Max analyst feedback records the LLM discovery window may inspect
_MAX_FEEDBACK_WINDOW = 200

# Prompt injection guard — same pattern used in evidence_builder and all agents
_INJECTION_RE = re.compile(
    r"ignore\s+(?:previous|above|all)\s+(?:instructions?|prompts?|context|rules?|system)",
    re.IGNORECASE,
)

_SYSTEM_PROMPT = (
    "You are a fraud pattern analyst. Analyze missed fraud cases to identify "
    "emerging patterns. Return only valid JSON matching the requested schema. "
    "Do not include any commentary outside the JSON object."
)


def _safe_notes(text: Optional[str], maxlen: int = 200) -> str:
    """Sanitize free-text analyst notes before they enter the LLM context."""
    if not text:
        return ""
    s = str(text)[:maxlen]
    return _INJECTION_RE.sub("[REDACTED]", s)


def _load_patterns() -> Dict[str, Any]:
    try:
        with open(_PATTERNS_PATH) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data).__name__}")
        return data
    except FileNotFoundError:
        _logger.error(
            "PatternEvolution: patterns file not found at %s — adjustments skipped",
            _PATTERNS_PATH,
        )
        return {}
    except (json.JSONDecodeError, ValueError) as exc:
        _logger.error(
            "PatternEvolution: failed to parse patterns file — %s: %s",
            type(exc).__name__, exc,
        )
        return {}


def _atomic_write_patterns(patterns: Dict[str, Any]) -> None:
    """Write to a temp file then os.replace() to prevent partial-write corruption."""
    dir_ = _PATTERNS_PATH.parent
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", dir=dir_, suffix=".tmp", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(patterns, tmp, indent=2)
            tmp_path = tmp.name
        os.replace(tmp_path, _PATTERNS_PATH)
        _logger.debug("PatternEvolution: patterns written atomically to %s", _PATTERNS_PATH)
    except Exception:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


# ------------------------------------------------------------------
# CORE: Deterministic pattern weight adjustment
# ------------------------------------------------------------------

async def adjust_pattern_weights_from_feedback() -> Dict[str, Any]:
    """
    CORE — No LLM needed.
    Lowers match thresholds and boosts signal weights for fraud types
    with ≥3 false negatives in the feedback window.
    Nudges thresholds upward for types with zero recent misses to prevent
    permanent convergence to the 0.45 floor.
    """
    stats = await get_feedback_stats()
    missed_types = stats.get("missed_fraud_types", {})
    adjustments = []

    patterns = _load_patterns()
    if not patterns:
        return {"adjustments_made": 0, "details": [], "source": "deterministic_feedback_analysis"}

    patterns_changed = False

    for fraud_type, pattern_data in patterns.items():
        miss_count = missed_types.get(fraud_type, 0)
        old_threshold = pattern_data.get("min_match_score", 0.65)
        old_signals: Dict[str, float] = dict(pattern_data.get("signals", {}))

        if miss_count >= 3:
            # Boost signal weights by 10% per miss, capped at 1.5× original
            boost = round(min(1.5, 1.0 + miss_count * 0.10), 3)
            new_signals = {k: round(min(1.0, v * boost), 4) for k, v in old_signals.items()}
            new_threshold = round(max(0.45, old_threshold - miss_count * 0.02), 3)

            patterns[fraud_type]["min_match_score"] = new_threshold
            if new_signals:
                patterns[fraud_type]["signals"] = new_signals
            patterns_changed = True

            adjustment = {
                "pattern": fraud_type,
                "misses": miss_count,
                "old_threshold": old_threshold,
                "new_threshold": new_threshold,
                "signal_boost": boost,
                "signals_updated": len(new_signals),
            }
            adjustments.append(adjustment)
            _logger.info(
                "PatternEvolution: adjusted %r — miss_count=%d threshold %.3f→%.3f boost=%.3f",
                fraud_type, miss_count, old_threshold, new_threshold, boost,
            )

            # Write audit trail to pattern_updates table
            await record_pattern_update(
                pattern_name=fraud_type,
                update_type="threshold_and_signal_boost",
                old_config={"min_match_score": old_threshold, "signals": old_signals},
                new_config={"min_match_score": new_threshold, "signals": new_signals},
                reason=f"{miss_count} false negatives in recent feedback window",
            )

        elif miss_count == 0 and old_threshold < 0.75:
            # Gradual recovery: nudge threshold up when no recent misses
            new_threshold = round(min(0.75, old_threshold + 0.01), 3)
            patterns[fraud_type]["min_match_score"] = new_threshold
            patterns_changed = True
            _logger.debug(
                "PatternEvolution: threshold recovery %r %.3f→%.3f",
                fraud_type, old_threshold, new_threshold,
            )

    if patterns_changed:
        _atomic_write_patterns(patterns)

    return {
        "adjustments_made": len(adjustments),
        "details": adjustments,
        "source": "deterministic_feedback_analysis",
    }


# ------------------------------------------------------------------
# OPTIONAL: LLM-based pattern discovery
# ------------------------------------------------------------------

async def discover_emerging_patterns(
    feedback_window: int = 100,
) -> Dict[str, Any]:
    """
    OPTIONAL — Uses LLM to analyze recent false negatives and propose new patterns.
    Only run periodically (e.g., daily batch) — not on the hot path.
    """
    feedback_window = min(feedback_window, _MAX_FEEDBACK_WINDOW)
    recent = await get_recent_feedback(feedback_window)
    false_negatives = [f for f in recent if f.get("outcome_label") == "false_negative"]

    if len(false_negatives) < 5:
        return {
            "new_patterns_discovered": 0,
            "message": "Insufficient false negatives for pattern discovery",
            "source": "llm_pattern_discovery",
        }

    # Sanitize all analyst notes before injecting into LLM context
    fn_summary = [
        f"fraud_type={_safe_notes(f.get('fraud_type_confirmed'), 50)}, "
        f"risk_score={f.get('system_risk_score')}, "
        f"notes={_safe_notes(f.get('notes'), 200)}"
        for f in false_negatives[:20]
    ]

    prompt = f"""Review these missed fraud cases and identify emerging patterns the system failed to detect:

{chr(10).join(fn_summary)}

Return a JSON object:
{{
  "emerging_patterns": [
    {{
      "pattern_name": "<name>",
      "description": "<what was missed>",
      "suggested_signals": {{"signal_name": <weight_0_to_1>}},
      "confidence": <0.0-1.0>
    }}
  ],
  "recommendation": "<1-2 sentences>"
}}"""

    try:
        llm = get_fast_llm()
        resp = await llm.ainvoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        match = re.search(r'\{.*\}', resp.content, re.DOTALL)
        if not match:
            raise ValueError("LLM response contained no JSON block")
        result = json.loads(match.group())
        emerging = result.get("emerging_patterns", [])
        if not isinstance(emerging, list):
            raise ValueError(f"emerging_patterns must be a list, got {type(emerging).__name__}")
        return {
            "new_patterns_discovered": len(emerging),
            "patterns": emerging,
            "recommendation": result.get("recommendation", ""),
            "source": "llm_pattern_discovery",
        }
    except Exception as exc:
        _logger.warning(
            "PatternEvolution: LLM discovery failed — %s: %s", type(exc).__name__, exc
        )

    return {
        "new_patterns_discovered": 0,
        "message": "LLM analysis failed — deterministic adjustment still applied",
        "source": "llm_pattern_discovery",
    }
