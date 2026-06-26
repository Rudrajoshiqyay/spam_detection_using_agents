"""
Shared, lazy-initialized LLM clients for all agents.

Two clients are maintained:
  _fast  — claude-haiku for the 5 parallel analysis agents (low latency)
  _deep  — claude-sonnet for investigation / explainability (high reasoning)

Both are initialized on first call to avoid import-time failures when
the API key has not yet been configured.
"""

import logging
from typing import Optional

from langchain_anthropic import ChatAnthropic

from app.config import settings

_logger = logging.getLogger(__name__)

_fast: Optional[ChatAnthropic] = None
_deep: Optional[ChatAnthropic] = None


def get_fast_llm() -> ChatAnthropic:
    """Return the shared fast (haiku) client, initializing on first call."""
    global _fast
    if _fast is None:
        _fast = ChatAnthropic(
            model=settings.fast_model,
            api_key=settings.anthropic_api_key,
            max_tokens=400,
        )
        _logger.debug("Fast LLM client initialized (model=%s)", settings.fast_model)
    return _fast


def get_deep_llm() -> ChatAnthropic:
    """Return the shared deep (sonnet) client, initializing on first call."""
    global _deep
    if _deep is None:
        _deep = ChatAnthropic(
            model=settings.deep_model,
            api_key=settings.anthropic_api_key,
            max_tokens=800,
        )
        _logger.debug("Deep LLM client initialized (model=%s)", settings.deep_model)
    return _deep


def reset_clients() -> None:
    """Force re-initialization on next access. Intended for tests only."""
    global _fast, _deep
    _fast = None
    _deep = None
