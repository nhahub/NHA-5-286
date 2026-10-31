"""
Purpose: Per-run authentication for the application under test (not the LLM key; see llm/settings.py).
Reads: values the user typed in the UI (or supplied to the headless runner); nothing is read from the environment.
Writes: an in-memory registry keyed by thread_id. Secret values never enter LangGraph state, checkpoints, history,
        results or reports; only the non-secret description (`public_request_fields`) travels in test_request.
Must not: write secrets to disk or logs, or share a registered value between runs.

Adding a method (API key, bearer token, ...) means adding one entry to AUTH_METHODS: its fields and the
environment variable each field is handed to the Playwright process as. Nothing else in the flow is method specific.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import quote

REDACTED = "[redacted]"
MIN_SECRET_LENGTH = 3  # shorter values would mangle ordinary text when scrubbed


@dataclass(frozen=True)
class AuthField:
    key: str       # name of the form field, e.g. "username"
    env: str       # environment variable the generated tests read, e.g. "TEST_USERNAME"
    label: str


@dataclass(frozen=True)
class AuthMethod:
    key: str
    label: str
    fields: tuple[AuthField, ...]


AUTH_METHODS: dict[str, AuthMethod] = {
    "username_password": AuthMethod("username_password", "Username and password", (
        AuthField("username", "TEST_USERNAME", "Username"),
        AuthField("password", "TEST_PASSWORD", "Password"),
    )),
}
NO_AUTH = "none"

# Every environment variable any method can set; all are removed from the child process unless the run needs them.
ALL_AUTH_ENV_NAMES: frozenset[str] = frozenset(f.env for m in AUTH_METHODS.values() for f in m.fields)


class AuthError(ValueError):
    """Authentication was requested but is incomplete or unknown (the message never contains a value)."""


@dataclass(frozen=True)
class AuthConfig:
    method: str = NO_AUTH
    secrets: Mapping[str, str] = field(default_factory=dict, repr=False)  # env name -> value

    @property
    def required(self) -> bool:
        return self.method != NO_AUTH

    def env(self) -> dict[str, str]:
        return dict(self.secrets)

    def env_names(self) -> list[str]:
        return list(self.secrets)

    def public(self) -> dict:
        """Safe description for the planner/codegen prompts and the request: names only, never values."""
        return {"required": self.required, "method": self.method, "env_vars": self.env_names()}


def build_auth(method: str, values: Mapping[str, str | None]) -> AuthConfig:
    """Validate the user's input for one method; raises AuthError naming the missing fields (not their values)."""
    spec = AUTH_METHODS.get(method)
    if spec is None:
        raise AuthError(f"Unknown authentication method '{method}'.")
    missing = [f.label for f in spec.fields if not (values.get(f.key) or "").strip()]
    if missing:
        raise AuthError("Authentication is required: enter " + " and ".join(m.lower() for m in missing) + ".")
    return AuthConfig(method, {f.env: str(values[f.key]) for f in spec.fields})


def public_request_fields(config: AuthConfig, skipped: bool = False) -> dict:
    """What goes into test_request: whether auth is needed, by which method, and whether the user chose to skip
    authentication validation. No values."""
    return {"auth_required": config.required, "auth_method": config.method, "auth_skipped": bool(skipped)}


def auth_prompt_info(request: Mapping | None) -> dict:
    """Prompt-safe authentication description built from test_request alone (planner, codegen, validator)."""
    request = request or {}
    required = bool(request.get("auth_required"))
    method = request.get("auth_method") if required else NO_AUTH
    spec = AUTH_METHODS.get(method or "")
    return {"required": required, "method": method or NO_AUTH, "skipped": bool(request.get("auth_skipped")),
            "env_vars": [f.env for f in spec.fields] if spec else []}


# ------------------------------------------------------------------ per-run registry
_REGISTRY: dict[str, AuthConfig] = {}
_LOCK = threading.Lock()


def register_run_auth(thread_id: str, config: AuthConfig) -> None:
    if config.required:
        with _LOCK:
            _REGISTRY[thread_id] = config


def get_run_auth(thread_id: str | None) -> AuthConfig | None:
    with _LOCK:
        return _REGISTRY.get(thread_id or "")


def release_run_auth(thread_id: str | None) -> None:
    with _LOCK:
        _REGISTRY.pop(thread_id or "", None)


def release_all_run_auth() -> None:
    with _LOCK:
        _REGISTRY.clear()


def child_env(base: Mapping[str, str], thread_id: str | None, required: bool) -> dict[str, str]:
    """Environment for the Playwright process. Auth variables inherited from the parent shell are always removed;
    only this run's own secrets are added back, and only when the run requires authentication."""
    env = {k: v for k, v in base.items() if k not in ALL_AUTH_ENV_NAMES}
    if required:
        config = get_run_auth(thread_id)
        if config is None or not config.required:
            raise AuthError("Authentication is required for this run but no credentials are registered for it.")
        env.update(config.env())
    return env


# ------------------------------------------------------------------ redaction
def _variants(value: str) -> set[str]:
    return {value, json.dumps(value)[1:-1], quote(value, safe=""), quote(value)}


def secret_values() -> list[str]:
    """Every registered secret value (all active runs) plus its JSON and URL-encoded forms, longest first."""
    with _LOCK:
        values = [v for c in _REGISTRY.values() for v in c.secrets.values() if len(v) >= MIN_SECRET_LENGTH]
    return sorted({x for v in values for x in _variants(v) if x}, key=len, reverse=True)


def scrub(text: str) -> str:
    """Replace every registered secret value in the text. Safe to call when nothing is registered."""
    if not text:
        return text
    for value in secret_values():
        text = text.replace(value, REDACTED)
    return text
