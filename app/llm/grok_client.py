"""
Shared, lazy-initialized Groq LLM clients with centralized exponential retry.

Two clients:
  _fast  — llama-3.1-8b-instant        (5 parallel analysis agents — low latency)
  _deep  — llama-3.3-70b-versatile     (investigation / explainability — high reasoning)

Agents call fast_ainvoke() / deep_ainvoke() instead of .ainvoke() directly so that
retry logic lives here once rather than being duplicated across all 10 agents.

Retry policy:
  - Retries on HTTP 429 (rate limit) and 500/502/503/504 (transient server errors)
  - Exponential backoff: 0.5 s → 2 s → 8 s (3 attempts max)
  - Non-retryable errors (400, 401, 422, …) are re-raised immediately
"""

import logging
from typing import Any, List, Optional

from langchain_groq import ChatGroq
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.config import settings

_logger = logging.getLogger(__name__)

_fast: Optional[ChatGroq] = None
_deep: Optional[ChatGroq] = None


# ---------------------------------------------------------------------------
# Retry predicate — groq SDK mirrors openai SDK error hierarchy
# ---------------------------------------------------------------------------

def _is_retryable(exc: BaseException) -> bool:
    """True only for transient Groq errors that are worth retrying."""
    try:
        from groq import RateLimitError, APIStatusError
        if isinstance(exc, RateLimitError):
            return True
        if isinstance(exc, APIStatusError) and exc.status_code in (500, 502, 503, 504):
            return True
    except ImportError:
        pass
    return False


# ---------------------------------------------------------------------------
# Retry-wrapped invoke (single implementation, shared by both clients)
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
    before_sleep=before_sleep_log(_logger, logging.WARNING),
    reraise=True,
)
async def _invoke(llm: ChatGroq, messages: List[Any]) -> Any:
    return await llm.ainvoke(messages)


# ---------------------------------------------------------------------------
# Client accessors
# ---------------------------------------------------------------------------

def get_fast_llm() -> ChatGroq:
    """Return shared fast client, initializing on first call."""
    global _fast
    if _fast is None:
        _fast = ChatGroq(
            model=settings.fast_model,
            groq_api_key=settings.groq_api_key,
            max_tokens=400,
        )
        _logger.debug("Fast LLM client initialized (model=%s)", settings.fast_model)
    return _fast


def get_deep_llm() -> ChatGroq:
    """Return shared deep client, initializing on first call."""
    global _deep
    if _deep is None:
        _deep = ChatGroq(
            model=settings.deep_model,
            groq_api_key=settings.groq_api_key,
            max_tokens=1500,
        )
        _logger.debug("Deep LLM client initialized (model=%s)", settings.deep_model)
    return _deep


# ---------------------------------------------------------------------------
# Public async helpers used by all agents
# ---------------------------------------------------------------------------

async def fast_ainvoke(messages: List[Any]) -> Any:
    """Invoke the fast LLM with centralized retry. Prefer this over get_fast_llm().ainvoke()."""
    return await _invoke(get_fast_llm(), messages)


async def deep_ainvoke(messages: List[Any]) -> Any:
    """Invoke the deep LLM with centralized retry. Prefer this over get_deep_llm().ainvoke()."""
    return await _invoke(get_deep_llm(), messages)


def reset_clients() -> None:
    """Force re-initialization on next access. For tests only."""
    global _fast, _deep
    _fast = None
    _deep = None


# ---------------------------------------------------------------------------
# Startup logging
# ---------------------------------------------------------------------------

def log_startup_info() -> None:
    """Emit a structured startup summary for the LLM layer."""
    _logger.info(
        "LLM provider: %s | fast_model: %s | deep_model: %s | mock: %s",
        "MockLLM" if settings.mock_llm else "Groq (groq.com)",
        settings.fast_model,
        settings.deep_model,
        "enabled" if settings.mock_llm else "disabled",
    )
