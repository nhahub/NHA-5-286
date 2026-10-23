"""
Purpose: Shared LLM error types and redaction helpers
used by LLM clients, agents, reports, and orchestration.

Kept in a separate module to avoid circular imports
between llm/client.py and agents/codegen.py.

Reads: environment (only to identify secrets for redaction)
Writes: N/A
Must not: log or expose API keys
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable


# Prefix used to identify fatal LLM errors in state.errors.
# Routing uses this tag to stop retries and report an ERROR.
LLM_FATAL_TAG = "llm-fatal"


class LLMError(RuntimeError):
    """Base class for LLM-layer failures."""


class LLMUnavailableError(LLMError):
    """No configured model could be initialized, or every model failed."""


class BudgetExceededError(LLMError):
    """
    The maximum token budget or agent-call limit was reached.

    This error must not be retried or trigger model fallback.
    """


class OutputParseError(ValueError):
    """The model response could not be parsed into the required structure."""


# Common API key patterns:
# - OpenAI / Anthropic: sk-...
# - Google: AIza...
# - Authorization headers: Bearer <token>
_SECRET = re.compile(
    r"(sk-[A-Za-z0-9_\-*.]{4,}|"
    r"AIza[0-9A-Za-z_\-]{20,}|"
    r"Bearer\s+\S+)"
)


def redact(text: str) -> str:
    """
    Remove API keys from error messages before storing
    them in state.errors or displaying them in reports.
    """

    if not text:
        return ""

    text = str(text)

    # Redact exact API key values from environment variables.
    for name, value in os.environ.items():
        if "API_KEY" in name.upper() and len(value) >= 8:
            text = text.replace(value, "[redacted]")

    # Redact recognizable secret patterns.
    return _SECRET.sub("[redacted]", text)


def has_fatal_llm_error(errors: Iterable[str]) -> bool:
    """
    Check whether state.errors contains a fatal LLM error.

    Used by LangGraph routing to stop the workflow
    instead of retrying an unavailable LLM.
    """

    return any(
        str(error).startswith(LLM_FATAL_TAG)
        for error in errors
    )