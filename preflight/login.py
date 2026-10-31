"""
Purpose: Step 2 of Preflight: does the page ask for a login, and if credentials were given, do they work?
         A real login attempt in a throwaway headless browser. Separate from the Playwright test execution.
Reads: the URL and, in memory only, the username and password the user typed.
Writes: nothing (no files, no traces, no screenshots).
Must not: use an LLM, guess when the page is ambiguous, or put a credential in any message it returns.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

NAV_TIMEOUT_MS = 20_000
SETTLE_MS = 6_000
DECISION_MS = 12_000
POLL_MS = 400
ACTION_TIMEOUT_MS = 8_000

_ERROR_TEXT = re.compile(
    r"invalid|incorrect|wrong|failed|denied|unauthori[sz]ed|not recogni[sz]ed|does not match|doesn't match|"
    r"try again|no account|locked|disabled", re.I)
_LOGOUT = re.compile(r"log\s*-?\s*out|sign\s*-?\s*out|log\s*off", re.I)
_MFA = re.compile(r"verification code|one[- ]time|\botp\b|two[- ]factor|\b2fa\b|\bmfa\b|authenticator|security code", re.I)
_LOGINISH_PATH = re.compile(r"log\s*-?\s*in|sign\s*-?\s*in|signin|auth|sso|session", re.I)
_CAPTCHA = "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], .g-recaptcha, .h-captcha, .cf-turnstile, [data-sitekey]"
_PASSWORD = "input[type=password]:visible"
_USERNAME_TYPES = {"", "text", "email", "tel"}

PUBLIC = "public"
MISSING = "missing"
AUTHENTICATED = "authenticated"
REJECTED = "rejected"
INCONCLUSIVE = "inconclusive"
BROWSER_ERROR = "browser_error"


@dataclass(frozen=True)
class LoginOutcome:
    state: str
    message: str
    category: str | None = None


def _lines(page) -> set[str]:
    return {line.strip() for line in page.inner_text("body").splitlines() if line.strip()}


def _settle(page, PlaywrightTimeout) -> None:
    for wait in (lambda: page.wait_for_load_state("networkidle", timeout=SETTLE_MS),
                 lambda: page.wait_for_selector(_PASSWORD, state="visible", timeout=1_500)):
        try:
            wait()
        except PlaywrightTimeout:
            pass  # a quiet or slow page is fine; what is (not) visible is judged afterwards


def _same_path(a: str, b: str) -> bool:
    pa, pb = urlsplit(a), urlsplit(b)
    return pa.netloc == pb.netloc and pa.path.rstrip("/") == pb.path.rstrip("/")


def _classify(page, login_url: str, baseline: set[str]) -> LoginOutcome | None:
    """One look at the page after submitting. None means 'not decided yet'."""
    password_visible = page.locator(_PASSWORD).count() > 0
    new_lines = [line for line in _lines(page) if line not in baseline]
    if page.locator("input[autocomplete='one-time-code']:visible").count() or _MFA.search(" ".join(new_lines)):
        return LoginOutcome(INCONCLUSIVE, "The site asked for a second verification step (code or MFA), which "
                            "Preflight cannot complete.", "mfa")
    if password_visible and any(_ERROR_TEXT.search(line) for line in new_lines):
        return LoginOutcome(REJECTED, "The website rejected the username or password.", "credentials_rejected")
    moved = not _same_path(page.url, login_url)
    logout = page.locator("a:visible, button:visible").filter(has_text=_LOGOUT).count() > 0
    if not password_visible and (moved or logout):
        return LoginOutcome(AUTHENTICATED, "Login succeeded.")
    return None


def _inspect(page, url: str, username: str, password: str, PlaywrightTimeout) -> LoginOutcome:
    page.set_default_timeout(ACTION_TIMEOUT_MS)
    page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
    _settle(page, PlaywrightTimeout)
    login_url = page.url

    fields = page.locator(_PASSWORD)
    count = fields.count()
    if count == 0:
        if not _same_path(login_url, url) and _LOGINISH_PATH.search(urlsplit(login_url).path):
            return LoginOutcome(INCONCLUSIVE, "The site redirected to what looks like a login page, but no password "
                                "field was found (a multi-step or unusual login). Preflight cannot validate it.",
                                "login_form_not_found")
        return LoginOutcome(PUBLIC, "The page opens without asking for a login.")
    if count > 1:
        return LoginOutcome(INCONCLUSIVE, "The page has several password fields (for example sign-in plus "
                            "registration), so it is unclear which form is the login.", "ambiguous_form")
    if not (username and password):
        return LoginOutcome(MISSING, "This website asks for a login. Enter your username and password and try again.",
                            "credentials_missing")
    if page.locator(_CAPTCHA).count():
        return LoginOutcome(INCONCLUSIVE, "The login form is protected by a captcha, which Preflight cannot solve.",
                            "captcha")

    password_field = fields.first
    form = password_field.locator("xpath=ancestor::form[1]")
    scope = form if form.count() else page
    inputs = scope.locator("input:visible")
    kinds = [(inputs.nth(i).get_attribute("type") or "").lower() for i in range(inputs.count())]
    pw_index = next((i for i, k in enumerate(kinds) if k == "password"), None)
    candidates = [i for i in range(pw_index or 0) if kinds[i] in _USERNAME_TYPES]
    if pw_index is None or not candidates:
        return LoginOutcome(INCONCLUSIVE, "No username field was found next to the password field (a multi-step "
                            "login?). Preflight cannot validate it.", "login_form_not_found")

    baseline = _lines(page)
    inputs.nth(candidates[-1]).fill(username)
    password_field.fill(password)
    submit = scope.locator("button[type=submit]:visible, input[type=submit]:visible, button:not([type]):visible")
    if submit.count():
        submit.first.click()
    else:
        password_field.press("Enter")

    deadline = time.monotonic() + DECISION_MS / 1000
    while time.monotonic() < deadline:
        page.wait_for_timeout(POLL_MS)
        try:
            outcome = _classify(page, login_url, baseline)
        except Exception:  # the page is navigating; look again on the next tick
            continue
        if outcome:
            return outcome
    return LoginOutcome(INCONCLUSIVE, "Preflight could not tell whether the login worked: the page showed neither "
                        "a clear error nor a clear sign of being signed in. Nothing was concluded about your "
                        "credentials.", "ambiguous_result")


def check_login(url: str, username: str, password: str) -> LoginOutcome:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                return _inspect(browser.new_context().new_page(), url, username, password, PlaywrightTimeout)
            finally:
                browser.close()
    except PlaywrightError:
        return LoginOutcome(INCONCLUSIVE, "The browser could not open or operate the page, so login detection was "
                            "not possible. Nothing was concluded about your credentials.", "browser_error")
