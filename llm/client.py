"""
Purpose: Initialise and cache hosted chat models, apply call-time fallback, and run the
         Code Generation LLM call (tool loop, structured parse, one retry, usage logging).
Reads: environment API keys; per call, the system prompt and the user payload
Writes: N/A (returns a CodegenResult plus the model string used); record_model_used
        returns a partial state update
Must not: hard-code credentials, expose API keys to agents, or use local/self-hosted models
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, TypeVar

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from pydantic import ValidationError

from agents.codegen import CodegenResult
from llm.errors import (  # noqa: F401  (re-exported: tests and callers import them from llm.client)
    BudgetExceededError,
    LLMError,
    LLMUnavailableError,
    OutputParseError,
    redact,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Spec section 3: the Code Generation agent gets these two browser tools and nothing else.
# save_test_file is deliberately absent: the system saves the returned code itself.
CODEGEN_TOOLS: tuple[str, ...] = ("browser_snapshot", "browser_generate_locator")

MAX_TOOL_ROUNDS = 4  # tool-calling rounds per attempt before the model must answer
MAX_PARSE_RETRIES = 1  # spec: one retry that includes the validation error
MAX_TOOL_OUTPUT_CHARS = 6_000  # page snapshots can be huge; bound what goes back to the model
MAX_ERROR_CHARS = 600
REQUEST_TIMEOUT_S = 90  # one hung provider call must not freeze the whole run

PROVIDER_KEY_VARS: Mapping[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "google_genai": ("GOOGLE_API_KEY",),
    "google-genai": ("GOOGLE_API_KEY",),
    "groq": ("GROQ_API_KEY",),
    "mistralai": ("MISTRAL_API_KEY",),
    "cohere": ("COHERE_API_KEY",),
}
# Self-hosted runtimes other than Ollama stay unsupported. Ollama (local) is allowed on purpose.
LOCAL_PROVIDERS = frozenset({"llamacpp", "llama-cpp", "llama_cpp", "vllm", "gpt4all"})

RETRY_TEMPLATE = (
    "Your previous reply could not be used: {error}\n"
    'Reply again with exactly one JSON object {{"scenario_id": "...", "code": "..."}} '
    "and nothing else. Keep following every rule in the system prompt."
)
FINAL_ANSWER_NUDGE = (
    "The tool budget is used up. Reply now with the JSON object only, "
    "based on what you already know."
)


# ------------------------------------------------------------------- model creation
_MODEL_CACHE: dict[str, BaseChatModel] = {}
_CACHE_LOCK = threading.Lock()


def clear_model_cache() -> None:
    with _CACHE_LOCK:
        _MODEL_CACHE.clear()


def parse_model_string(model_string: str) -> tuple[str, str]:
    """Split 'provider:model' and reject malformed or local-provider strings."""
    provider, sep, name = (model_string or "").strip().partition(":")
    provider, name = provider.strip().lower(), name.strip()
    if not sep or not provider or not name:
        raise ValueError(f"model must use the 'provider:model' format, got {model_string!r}")
    if provider in LOCAL_PROVIDERS:
        raise ValueError(f"local or self-hosted provider '{provider}' is not supported")
    return provider, name


def get_model(model_string: str) -> BaseChatModel:
    """Initialise (once) and return the chat model for a 'provider:model' string.

    Raises ValueError for a malformed string or a local provider, and RuntimeError when the
    provider's API key is missing. Key values are never logged or put in messages.
    """
    provider, _ = parse_model_string(model_string)
    cache_key = model_string.strip()
    with _CACHE_LOCK:
        cached = _MODEL_CACHE.get(cache_key)
        if cached is not None:
            return cached
        key_vars = PROVIDER_KEY_VARS.get(provider)
        if key_vars and not any(os.environ.get(var) for var in key_vars):
            raise RuntimeError(f"missing API key for provider '{provider}': set {' or '.join(key_vars)}")
        model = init_chat_model(cache_key, timeout=REQUEST_TIMEOUT_S)
        _MODEL_CACHE[cache_key] = model
        return model


class FallbackChain:
    """Ordered candidate models. `run` fails over at call time, not at initialisation time."""

    def __init__(self, candidates: Sequence[tuple[str, BaseChatModel]]) -> None:
        if not candidates:
            raise LLMUnavailableError("no model candidates")
        self._candidates = list(candidates)

    @property
    def model_names(self) -> list[str]:
        return [name for name, _ in self._candidates]

    def run(self, attempt: Callable[[str, BaseChatModel], T]) -> tuple[T, str]:
        """Try each model in order; return (result, model string actually used)."""
        failures: list[str] = []
        only_bad_output = True
        for name, model in self._candidates:
            try:
                return attempt(name, model), name
            except BudgetExceededError:
                raise  # a spent budget is a run-level condition; another model will not fix it
            except Exception as exc:  # unavailable model, auth error, or invalid output after its retry
                only_bad_output = only_bad_output and isinstance(exc, OutputParseError)
                safe = redact(str(exc))  # provider errors can echo part of an API key
                logger.warning("model %s failed (%s); trying next candidate", name, safe)
                failures.append(f"{name}: {safe}")
        message = "all models failed: " + " | ".join(failures)
        if only_bad_output:
            # The models answered but not in the required shape: that is one bad request, not an unavailable
            # provider, so only this call fails and the caller can carry on with its other work.
            raise OutputParseError(message)
        raise LLMUnavailableError(message)


def get_model_with_fallback(
    primary: str,
    fallback: str | None = None,
    *,
    factory: Callable[[str], BaseChatModel] = get_model,
) -> FallbackChain:
    """Resolve the primary and optional fallback model into a FallbackChain.

    Initialisation failures are logged and skipped; if no model initialises at all this raises
    LLMUnavailableError so intake can set terminal_status = ERROR before any spend. Failures that
    only appear when the model is called (bad key, outage, invalid output) are handled later by
    FallbackChain.run.
    """
    names = [primary] + ([fallback] if fallback and fallback != primary else [])
    candidates: list[tuple[str, BaseChatModel]] = []
    failures: list[str] = []
    for name in names:
        try:
            candidates.append((name, factory(name)))
        except (ValueError, RuntimeError) as exc:
            safe = redact(str(exc))
            logger.warning("model %s could not be initialised: %s", name, safe)
            failures.append(f"{name}: {safe}")
    if not candidates:
        raise LLMUnavailableError("no usable model: " + " | ".join(failures))
    return FallbackChain(candidates)


def record_model_used(agent_name: str, model_string: str, state: Mapping[str, Any]) -> dict[str, Any]:
    """Partial state update recording which model an agent used. Never mutates `state`."""
    return {"models_used": {**state.get("models_used", {}), agent_name: model_string}}


# ----------------------------------------------------------------------- accounting
@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0

    def add(self, other: TokenUsage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.total_tokens += other.total_tokens
        self.calls += other.calls


def usage_from_message(message: BaseMessage) -> TokenUsage:
    meta = getattr(message, "usage_metadata", None) or {}
    inp, out = int(meta.get("input_tokens") or 0), int(meta.get("output_tokens") or 0)
    return TokenUsage(inp, out, int(meta.get("total_tokens") or inp + out), 1)


@dataclass
class RunBudget:
    """Shared across agents for one run: max_tokens_per_run and a cap on LLM calls."""

    max_tokens: int | None = None
    max_calls: int | None = None
    tokens_used: int = 0
    calls_made: int = 0

    def check(self) -> None:
        if self.max_calls is not None and self.calls_made >= self.max_calls:
            raise BudgetExceededError(f"agent call cap reached ({self.max_calls})")
        if self.max_tokens is not None and self.tokens_used >= self.max_tokens:
            raise BudgetExceededError(f"max_tokens_per_run reached ({self.max_tokens})")

    def record(self, usage: TokenUsage) -> None:
        self.calls_made += 1
        self.tokens_used += usage.total_tokens


# --------------------------------------------------------------------------- parsing
def _drop_reasoning(text: str) -> str:
    """Reasoning models (e.g. qwen3) may emit their thinking before a closing </think>; keep only the answer."""
    return text.rsplit("</think>", 1)[-1].lstrip() if "</think>" in text else text


def message_text(message: BaseMessage) -> str:
    """Plain text of a reply; some providers return a list of content blocks."""
    content = message.content
    if isinstance(content, str):
        return _drop_reasoning(content)
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, Mapping) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return _drop_reasoning("".join(parts))


_FENCE = re.compile(r"^```(?:json)?[ \t]*\n(?P<body>.*?)\n```[ \t]*$", re.S)


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    fenced = _FENCE.match(stripped)
    if fenced:
        stripped = fenced["body"].strip()
    decoder = json.JSONDecoder()
    last_error: json.JSONDecodeError | None = None
    # Try every '{' in turn: the reply may contain braces BEFORE the real JSON object
    for match in re.finditer(r"\{", stripped):
        try:
            data, _ = decoder.raw_decode(stripped[match.start():])
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(data, dict):
            return data
    if last_error is not None:
        raise OutputParseError(f"invalid JSON: {last_error}") from last_error
    raise OutputParseError("the reply contains no JSON object")


_CODE_FENCE = re.compile(r"```(?:typescript|ts|javascript|js)?\s*\n(?P<body>.*?)```", re.S)


def _code_without_json(text: str, user_payload: str) -> CodegenResult | None:
    """Some models return the Playwright file directly (fenced or bare) instead of {"scenario_id", "code"}.
    The scenario id is known from the request, so the file can be used as is; the validator still checks it."""
    try:
        scenario_id = str(json.loads(user_payload)["scenario"]["id"])
    except (ValueError, KeyError, TypeError):
        return None
    fenced = _CODE_FENCE.search(text)
    code = (fenced["body"] if fenced else text).strip()
    if "import" not in code or "test(" not in code:
        return None
    return CodegenResult(scenario_id=scenario_id, code=code)


def structured_chain_with_json_fallback(prompt: Any, llm: Any, schema: type) -> Any:
    """prompt | llm.with_structured_output(schema), plus a fallback for providers that return an empty or unparsed
    structured reply (free reasoning models often spend their tokens thinking and answer with nothing).

    The fallback asks for one plain JSON object and validates it against the SAME schema. Only parse-type errors
    trigger it, never rate limits or auth errors, so it cannot double the requests sent to a limited quota."""
    from langchain_core.exceptions import OutputParserException
    from langchain_core.runnables import RunnableLambda

    def plain_json(prompt_value: Any) -> Any:
        messages = [*prompt_value.to_messages(), HumanMessage(content=(
            "Reply with ONLY one JSON object that matches this JSON schema, with no other text and no Markdown:\n"
            + json.dumps(schema.model_json_schema())))]
        return schema.model_validate(extract_json_object(message_text(llm.invoke(messages))))

    primary = prompt | llm.with_structured_output(schema)
    return primary.with_fallbacks([prompt | RunnableLambda(plain_json)],
                                  exceptions_to_handle=(ValueError, OutputParserException))


def parse_codegen_output(text: str) -> CodegenResult:
    data = extract_json_object(text)
    try:
        return CodegenResult.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'object'}: {e['msg']}" for e in exc.errors())
        raise OutputParseError(problems[:MAX_ERROR_CHARS]) from exc


# ---------------------------------------------------------------------------- tools
def select_codegen_tools(tools: Sequence[BaseTool]) -> list[BaseTool]:
    """Keep only the two tools the Code Generation agent may use."""
    selected = [t for t in tools if t.name in CODEGEN_TOOLS]
    dropped = sorted({t.name for t in tools} - set(CODEGEN_TOOLS))
    if dropped:
        logger.warning("dropping tools not allowed for codegen: %s", dropped)
    missing = sorted(set(CODEGEN_TOOLS) - {t.name for t in selected})
    if missing:
        logger.warning("codegen tools not available: %s", missing)
    return selected


def _run_coroutine(factory: Callable[[], Any]) -> Any:
    """Run a coroutine from sync code, even if an event loop is already running.

    TODO(P5/P3): each call creates a NEW event loop. If the MCP browser session is tied to
    one long-lived loop, tool calls will fail or lose the open page. Agree who owns the MCP
    session before relying on this with the real Playwright MCP server.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(factory())).result()


def _invoke_tool(tool: BaseTool, args: Mapping[str, Any]) -> Any:
    try:
        return tool.invoke(dict(args))
    except NotImplementedError:  # MCP adapter tools are async-only
        return _run_coroutine(lambda: tool.ainvoke(dict(args)))


def _truncate(text: str) -> str:
    if len(text) <= MAX_TOOL_OUTPUT_CHARS:
        return text
    return text[:MAX_TOOL_OUTPUT_CHARS] + f"\n...[truncated {len(text) - MAX_TOOL_OUTPUT_CHARS} chars]"


# ---------------------------------------------------------------------------- backend
class CodegenLLMBackend:
    """Satisfies agents.codegen.CodegenBackend."""

    def __init__(
        self,
        primary_model: str,
        fallback_model: str | None = None,
        *,
        tools: Sequence[BaseTool] = (),
        budget: RunBudget | None = None,
        agent_name: str = "codegen",
        model_factory: Callable[[str], BaseChatModel] = get_model,
    ) -> None:
        # Fails fast (LLMUnavailableError) when no model can be initialised, before any spend.
        self._chain = get_model_with_fallback(primary_model, fallback_model, factory=model_factory)
        self._tools = select_codegen_tools(tools)
        self._tools_by_name = {t.name: t for t in self._tools}
        self._budget = budget
        self._agent_name = agent_name
        self.usage: dict[str, TokenUsage] = {}  # per model string, for the report

    def generate(self, system_prompt: str, user_payload: str) -> tuple[CodegenResult, str]:
        return self._chain.run(lambda name, model: self._attempt(name, model, system_prompt, user_payload))

    # -- one model, with its single parse retry
    def _attempt(self, name: str, model: BaseChatModel, system_prompt: str, user_payload: str) -> CodegenResult:
        tooled = model.bind_tools(self._tools) if self._tools else model
        messages: list[BaseMessage] = [SystemMessage(content=system_prompt), HumanMessage(content=user_payload)]
        for attempt in range(MAX_PARSE_RETRIES + 1):
            reply = self._complete(name, tooled, model, messages)
            text = message_text(reply)
            try:
                return parse_codegen_output(text)
            except OutputParseError as exc:
                plain = _code_without_json(text, user_payload)
                if plain is not None:  # the model answered with the spec itself instead of the JSON wrapper
                    return plain
                logger.warning("codegen output from %s rejected (attempt %d): %s", name, attempt + 1, exc)
                if attempt == MAX_PARSE_RETRIES:
                    raise
                messages.append(HumanMessage(content=RETRY_TEMPLATE.format(error=exc)))
        raise AssertionError("unreachable")

    # -- tool loop: call the model until it answers without requesting tools
    def _complete(self, name: str, tooled: Any, plain: Any, messages: list[BaseMessage]) -> AIMessage:
        calls: list[Mapping[str, Any]] = []
        for round_no in range(MAX_TOOL_ROUNDS + 1):
            reply = self._invoke(name, tooled, messages)
            messages.append(reply)
            calls = list(getattr(reply, "tool_calls", None) or [])
            if not calls:
                return reply
            if round_no == MAX_TOOL_ROUNDS:
                break
            messages.extend(self._run_tool_call(call) for call in calls)
        # Rounds exhausted: answer the pending calls (providers require it), then force an answer.
        messages.extend(
            ToolMessage(content="error: tool budget exhausted", tool_call_id=c["id"], name=c["name"])
            for c in calls
        )
        messages.append(HumanMessage(content=FINAL_ANSWER_NUDGE))
        reply = self._invoke(name, plain, messages)
        messages.append(reply)
        return reply

    def _invoke(self, name: str, llm: Any, messages: list[BaseMessage]) -> AIMessage:
        if self._budget:
            self._budget.check()
        reply = llm.invoke(list(messages))
        usage = usage_from_message(reply)
        self.usage.setdefault(name, TokenUsage()).add(usage)
        if self._budget:
            self._budget.record(usage)
        logger.info(
            "llm_usage agent=%s model=%s input_tokens=%d output_tokens=%d total_tokens=%d",
            self._agent_name, name, usage.input_tokens, usage.output_tokens, usage.total_tokens,
        )
        return reply

    def _run_tool_call(self, call: Mapping[str, Any]) -> ToolMessage:
        tool_name, call_id = str(call.get("name", "")), str(call.get("id", ""))
        tool = self._tools_by_name.get(tool_name)
        if tool is None:
            content = f"error: unknown tool '{tool_name}'"
        else:
            try:
                output = _invoke_tool(tool, call.get("args") or {})
                content = _truncate(output if isinstance(output, str) else json.dumps(output, default=str))
            except Exception as exc:  # a failing tool is information for the model, not a crash
                logger.warning("tool %s failed: %s", tool_name, redact(str(exc)))
                content = redact(f"error: {exc}")[:MAX_ERROR_CHARS]
        return ToolMessage(content=content, tool_call_id=call_id, name=tool_name)