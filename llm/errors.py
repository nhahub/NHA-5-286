"""
Purpose: Error types and helpers shared by llm/client.py and agents/codegen.py.
         Kept in its own module so the two files never import each other in a circle.
Reads: environment (only to find secret values that must be hidden)
Writes: N/A
Must not: log or return API key values
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable

# Prefix of a state.errors entry that means "the LLM layer is down for the whole run".
# P5's routing turns it into terminal_status = ERROR instead of retrying generation.
LLM_FATAL_TAG = "llm-fatal"


class LLMError(RuntimeError):
    """Base class for LLM-layer failures."""


class LLMUnavailableError(LLMError):
    """No configured model could be initialised, or every model failed."""


class BudgetExceededError(LLMError):
    """max_tokens_per_run or the cap on agent calls was reached. Never retried or failed over."""


class OutputParseError(ValueError):
    """The model reply was not a valid structured result."""


# Common key shapes: OpenAI/Anthropic "sk-...", Google "AIza...", and "Bearer <token>" headers.
_SECRET = re.compile(r"(sk-[A-Za-z0-9_\-*.]{4,}|AIza[0-9A-Za-z_\-]{20,}|Bearer\s+\S+)")


def redact(text: str) -> str:
    """Hide API keys in a message before it is logged or stored in state.errors."""
    for name, value in os.environ.items():
        if "API_KEY" in name.upper() and len(value) >= 8:
            text = text.replace(value, "[redacted]")  # the exact key values from this environment
    return _SECRET.sub("[redacted]", text)


def has_fatal_llm_error(errors: Iterable[str]) -> bool:
    """True if any recorded error says the LLM layer failed for the whole run (for P5's routing)."""
    return any(str(e).startswith(LLM_FATAL_TAG) for e in errors)