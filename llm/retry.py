"""
Purpose: Retry an LLM call that failed because of a provider rate limit or a transient network fault.
Reads: N/A
Writes: N/A
Must not: retry validation or authentication errors, or loop forever
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")

_TRANSIENT = ("429", "rate limit", "rate-limited", "temporarily", "timeout", "timed out", "503", "502", "overloaded", "connection")


def is_transient(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return any(marker in text for marker in _TRANSIENT)


def call_with_backoff(fn: Callable[[], T], *, attempts: int = 5, base_delay: float = 15.0, sleep=time.sleep) -> T:
    """Call fn(); on a transient error wait (15s, 30s, 45s, ... capped at 60s) and try again."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            if attempt == attempts or not is_transient(exc):
                raise
            delay = min(base_delay * attempt, 60.0)
            logger.warning("transient LLM error (%s); retry %d/%d in %.0fs", type(exc).__name__, attempt, attempts - 1, delay)
            sleep(delay)
    raise AssertionError("unreachable")
