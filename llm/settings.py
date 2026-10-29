"""
Purpose: Session LLM settings from the UI: provider mapping, credential validation, and a per-run
         credential registry so agents use the model the user selected.
Reads: UI-supplied provider/model/API key; environment keys as a fallback when no key is typed
Writes: N/A (in-memory registry only; keys never enter graph state, reports, logs, or messages)
Must not: log or return an API key, silently substitute another provider, or allow local models
"""
from __future__ import annotations

import importlib.util
import threading
from dataclasses import dataclass, field
from typing import Callable

from langchain_core.language_models import BaseChatModel

import os

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class ProviderSpec:
    ui_name: str
    prefix: str  # provider prefix used in the project's "provider:model" strings
    package: str | None  # python module that must be importable
    env_var: str | None
    requires_key: bool = True
    unsupported_reason: str | None = None


PROVIDERS: dict[str, ProviderSpec] = {
    "Groq": ProviderSpec("Groq", "groq", "langchain_groq", "GROQ_API_KEY"),
    "Gemini": ProviderSpec("Gemini", "google_genai", "langchain_google_genai", "GOOGLE_API_KEY"),
    "OpenRouter": ProviderSpec("OpenRouter", "openrouter", "langchain_openai", "OPENROUTER_API_KEY"),
    "Ollama": ProviderSpec(
        "Ollama", "ollama", None, None, requires_key=False,
        unsupported_reason="Ollama runs models on the local machine; this project allows hosted models only.",
    ),
}


@dataclass
class LLMSettings:
    provider: str = ""
    model: str = ""
    api_key: str = field(default="", repr=False)  # excluded from repr so it cannot leak via logging
    validated: bool = False

    @property
    def model_string(self) -> str:
        spec = PROVIDERS.get(self.provider)
        return f"{spec.prefix}:{self.model}" if spec and self.model else ""

    def public(self) -> dict:
        """Safe-to-display view; never includes the key."""
        return {"provider": self.provider, "model": self.model, "validated": self.validated,
                "key_source": "entered" if self.api_key else "environment"}


def _redact(text: str, key: str) -> str:
    text = str(text)
    return text.replace(key, "***") if key else text


def effective_key(provider: str, api_key: str) -> str:
    spec = PROVIDERS[provider]
    return (api_key or "").strip() or (os.environ.get(spec.env_var, "") if spec.env_var else "")


def build_model(provider: str, model: str, api_key: str) -> BaseChatModel:
    """Create a chat model with the user's key passed directly (not through os.environ)."""
    from langchain.chat_models import init_chat_model

    spec = PROVIDERS[provider]
    key = effective_key(provider, api_key)
    if spec.prefix == "openrouter":
        return init_chat_model(f"openai:{model}", api_key=key, base_url=OPENROUTER_BASE_URL)
    return init_chat_model(f"{spec.prefix}:{model}", api_key=key)


def check_static(provider: str, model: str, api_key: str) -> str | None:
    """Return a problem description, or None when the settings are structurally usable."""
    spec = PROVIDERS.get(provider)
    if spec is None:
        return f"Unknown provider '{provider}'."
    if spec.unsupported_reason:
        return spec.unsupported_reason
    if not (model or "").strip():
        return "Enter a model name."
    if spec.package and importlib.util.find_spec(spec.package) is None:
        return (f"The {provider} integration is unavailable: Python package '{spec.package}' is not installed "
                f"(pip install {spec.package.replace('_', '-')}).")
    if spec.requires_key and not effective_key(provider, api_key):
        return f"No API key: enter one, or set {spec.env_var} in the environment."
    return None


def validate_settings(
    provider: str, model: str, api_key: str,
    *, factory: Callable[[str, str, str], BaseChatModel] = build_model,
) -> tuple[bool, str]:
    """Check the credentials with one tiny real provider call. Returns (ok, message without secrets)."""
    problem = check_static(provider, model, api_key)
    if problem:
        return False, problem
    key = effective_key(provider, api_key)
    try:
        llm = factory(provider, model.strip(), api_key)
        llm.invoke("Reply with the single word: ok")
    except Exception as exc:  # auth, unknown model, network, quota ...
        return False, f"{provider} rejected the request ({type(exc).__name__}): {_redact(exc, key)[:300]}"
    return True, f"{provider} model '{model.strip()}' responded; credentials are valid."


# ----------------------------------------------------------------- per-run registry
_REGISTRY: dict[str, LLMSettings] = {}
_LOCK = threading.Lock()


def register_run_credentials(thread_id: str, settings: LLMSettings) -> None:
    with _LOCK:
        _REGISTRY[thread_id] = settings


def release_run_credentials(thread_id: str) -> None:
    with _LOCK:
        _REGISTRY.pop(thread_id, None)


def model_factory_for(thread_id: str | None) -> Callable[[str], BaseChatModel]:
    """Factory compatible with llm.client's `model_factory`: resolves 'prefix:model' using the
    credentials the user registered for this run. Raises if none are registered (no silent fallback)."""

    def factory(model_string: str) -> BaseChatModel:
        with _LOCK:
            settings = _REGISTRY.get(thread_id or "")
        if settings is None:
            raise RuntimeError("no LLM credentials registered for this run")
        if model_string != settings.model_string:
            raise RuntimeError(f"model '{model_string}' is not the model selected in Settings "
                               f"('{settings.model_string}')")
        return build_model(settings.provider, settings.model, settings.api_key)


    factory.gemini_interactions_client = (
        lambda model_string: gemini_interactions_client_for(
            thread_id,
            model_string,
        )
    )

    return factory





def gemini_interactions_client_for(
    thread_id: str | None,
    model_string: str,
):
    """Create a Gemini Interactions client using this run's registered credentials."""

    from google import genai

    with _LOCK:
        settings = _REGISTRY.get(thread_id or "")

    if settings is None:
        raise RuntimeError("no LLM credentials registered for this run")

    if settings.provider != "Gemini":
        raise RuntimeError("Gemini Interactions requires the Gemini provider")

    if model_string != settings.model_string:
        raise RuntimeError(
            "model does not match the model selected in Settings"
        )

    key = effective_key(settings.provider, settings.api_key)

    if not key:
        raise RuntimeError("Gemini API key is not configured")

    return genai.Client(api_key=key)