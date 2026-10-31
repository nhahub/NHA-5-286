"""
Purpose: Preflight entry point. Runs BEFORE the LangGraph workflow and before any LLM call, so a wrong URL or a
         wrong login never costs tokens. Deterministic: HTTP + a throwaway browser, no model anywhere.
Reads: URL, optional username/password (in memory), the skip-authentication choice.
Writes: nothing. Returns a PreflightResult; the caller decides whether the graph may start.
Must not: import an LLM client, put a credential in the result, or inherit credentials from the environment.
"""
from __future__ import annotations

import time

from intake.safety import is_safe_url
from llm.errors import redact
from preflight import login
from preflight.accessibility import check_access
from preflight.result import (
    AUTH_MISSING, AUTH_NOT_REQUIRED, AUTH_OK, AUTH_REJECTED, AUTH_SKIPPED, AUTH_UNKNOWN, FAILED, INCONCLUSIVE,
    NOT_CHECKED, PASS, REACHABLE, UNREACHABLE, PreflightResult,
)


def _finish(started: float, **fields) -> PreflightResult:
    fields["message"] = redact(fields["message"])
    return PreflightResult(duration_ms=int((time.monotonic() - started) * 1000), **fields)


def run_preflight(url: str, username: str = "", password: str = "", skip_auth: bool = False) -> PreflightResult:
    """The credentials must already be registered for this run (llm.run_auth) so that redact() can scrub them."""
    started = time.monotonic()
    username, password = (username or "").strip(), password or ""

    safe, reason = is_safe_url(url)
    if not safe:
        return _finish(started, status=FAILED, url_status=NOT_CHECKED, auth_status=AUTH_UNKNOWN,
                       error_category="blocked_url", message=reason)

    access = check_access(url)
    if not access.ok:
        return _finish(started, status=FAILED, url_status=UNREACHABLE, auth_status=AUTH_UNKNOWN,
                       error_category=access.category, http_status=access.http_status, message=access.message)

    if access.category == "forbidden":  # reachable, but we cannot tell if this is a login wall or bot protection
        return _finish(started, status=INCONCLUSIVE, url_status=REACHABLE, auth_status=AUTH_UNKNOWN,
                       error_category="forbidden", http_status=403,
                       message="The website refused automated access (HTTP 403). Preflight cannot tell whether it "
                               "needs a login or blocks automation, so nothing was assumed.")

    if access.category == "unauthorized":  # HTTP-level authentication (e.g. Basic): not something the tests can use
        if skip_auth:
            return _finish(started, status=FAILED, url_status=REACHABLE, auth_status=AUTH_UNKNOWN,
                           error_category="unauthorized", http_status=401,
                           message="This URL answers HTTP 401, so it is an access-controlled page, not a login page. "
                                   "Untick the skip option and enter credentials, or use the login page's URL.")
        if not (username and password):
            return _finish(started, status=FAILED, url_status=REACHABLE, auth_status=AUTH_MISSING,
                           error_category="credentials_missing", http_status=401,
                           message="This website requires authentication (HTTP 401). Enter your username and "
                                   "password and try again.")
        return _finish(started, status=INCONCLUSIVE, url_status=REACHABLE, auth_status=AUTH_UNKNOWN,
                       error_category="http_auth_unsupported", http_status=401,
                       message="This website uses HTTP-level authentication (HTTP 401), which Preflight and the "
                               "generated tests do not support yet. Nothing was concluded about your credentials.")

    if skip_auth:
        return _finish(started, status=PASS, url_status=REACHABLE, auth_status=AUTH_SKIPPED, auth_skipped=True,
                       http_status=access.http_status,
                       message="The website is reachable. Authentication validation was skipped by your choice; the "
                               "site is NOT confirmed as authenticated, so only logged-out behaviour will be tested.")

    outcome = login.check_login(url, username, password)
    common = dict(url_status=REACHABLE, http_status=access.http_status, error_category=outcome.category,
                  message=outcome.message)
    if outcome.state == login.PUBLIC:
        note = " The credentials you entered were not needed and will not be used." if (username or password) else ""
        return _finish(started, status=PASS, auth_status=AUTH_NOT_REQUIRED, **{**common, "message": outcome.message + note})
    if outcome.state == login.AUTHENTICATED:
        return _finish(started, status=PASS, auth_status=AUTH_OK, auth_required=True, **common)
    if outcome.state == login.MISSING:
        return _finish(started, status=FAILED, auth_status=AUTH_MISSING, **common)
    if outcome.state == login.REJECTED:
        return _finish(started, status=FAILED, auth_status=AUTH_REJECTED, **common)
    return _finish(started, status=INCONCLUSIVE, auth_status=AUTH_UNKNOWN, **common)
