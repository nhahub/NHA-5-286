"""
Purpose: Central configuration loaded from environment variables; single source of truth for tunables.
Owner: @Shema
Reads: environment variables (DEFAULT_MODEL, FALLBACK_MODEL, MAX_TOKENS_PER_RUN, AUTO_HEAL_MODE, HUMAN_REVIEW_MODE, ALLOW_HTTP, SCENARIO_CAP)
Writes: N/A (read-only module)
Must not: contain agent logic, make LLM calls, or expose secrets
"""

# def load_config() -> dict: -> loads and validates all env vars; returns typed config dict
# def get_default_model() -> str: -> returns DEFAULT_MODEL; raises if not set and no usable model available
# def get_fallback_model() -> str | None: -> returns FALLBACK_MODEL or None if not configured
# def get_auto_heal_mode() -> str: -> returns "auto" or "manual" from AUTO_HEAL_MODE env var
# def get_human_review_mode() -> bool: -> returns True when HUMAN_REVIEW_MODE == "on"; False suits CI runs
# def get_max_tokens_per_run() -> int: -> returns MAX_TOKENS_PER_RUN; default 100000
# def allow_http() -> bool: -> returns True only when ALLOW_HTTP == "true"; HTTPS-only by default