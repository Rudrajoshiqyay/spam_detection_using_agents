"""Shared LLM clients for all agents — thin re-export from app.llm.grok_client."""
from app.llm.grok_client import (
    get_fast_llm,
    get_deep_llm,
    reset_clients,
    fast_ainvoke,
    deep_ainvoke,
)

__all__ = ["get_fast_llm", "get_deep_llm", "reset_clients", "fast_ainvoke", "deep_ainvoke"]
