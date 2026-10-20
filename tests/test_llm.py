"""Purpose: Tests for llm/client.py (fake chat models; no network, no API keys)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from agents.codegen import run_codegen
from llm import client
from llm.client import (
    BudgetExceededError,
    CodegenLLMBackend,
    LLMUnavailableError,
    OutputParseError,
    RunBudget,
    get_model,
    get_model_with_fallback,
    parse_codegen_output,
    parse_model_string,
    record_model_used,
    select_codegen_tools,
)

GOOD_JSON = '{"scenario_id": "s1", "code": "import { test } from \'@support/evidence\';"}'


@pytest.fixture(autouse=True)
def _isolate_client(monkeypatch: pytest.MonkeyPatch):
    """Every test starts clean, and a real API key in your shell can never be reached."""
    client.clear_model_cache()
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    yield
    client.clear_model_cache()


# ----------------------------------------------------------------------- fakes
class FakeModel:
    """Stands in for a chat model: replays scripted replies, records every call."""

    def __init__(self, *replies: AIMessage | Exception) -> None:
        self.replies = list(replies)
        self.calls: list[list] = []
        self.bound: list[str] | None = None

    def bind_tools(self, tools):
        self.bound = [t.name for t in tools]
        return self

    def invoke(self, messages):
        self.calls.append(list(messages))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def ai(text: str = "", **kwargs) -> AIMessage:
    return AIMessage(content=text, **kwargs)


def backend(primary: FakeModel, fallback: FakeModel | None = None, **kwargs) -> CodegenLLMBackend:
    models = {"openai:primary": primary, "openai:fallback": fallback}
    return CodegenLLMBackend(
        "openai:primary",
        "openai:fallback" if fallback else None,
        model_factory=lambda name: models[name],
        **kwargs,
    )


@tool
def browser_snapshot() -> str:
    """Return the accessibility snapshot."""
    return "- button 'Log in'"


@tool
def browser_generate_locator(element: str) -> str:
    """Return a locator for an element."""
    return f"page.getByRole('button', {{ name: '{element}' }})"


@tool
def save_test_file(path: str) -> str:
    """Not allowed for codegen."""
    return "saved"


@tool("browser_snapshot")
async def async_snapshot() -> str:
    """Async-only tool, like the MCP adapter tools."""
    return "- button 'Log in'"


@tool("browser_snapshot")
def crashing_snapshot() -> str:
    """Always fails."""
    raise RuntimeError("browser crashed")


# --------------------------------------------------------------- model creation
@pytest.mark.parametrize("bad", ["gpt-4o", "openai:", ":gpt-4o", "", "   "])
def test_malformed_model_string_raises_value_error(bad: str) -> None:
    with pytest.raises(ValueError, match="provider:model"):
        parse_model_string(bad)


def test_local_providers_are_refused() -> None:
    with pytest.raises(ValueError, match="hosted models only"):
        parse_model_string("ollama:llama3")


def test_get_model_requires_the_api_key() -> None:
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        get_model("openai:gpt-4o")


def test_get_model_initialises_once_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    created: list[str] = []
    # **kw: get_model now also passes a timeout
    monkeypatch.setattr(client, "init_chat_model", lambda s, **kw: created.append(s) or object())
    assert get_model("openai:gpt-4o") is get_model("openai:gpt-4o")
    assert created == ["openai:gpt-4o"]


def test_chain_skips_a_model_that_cannot_initialise() -> None:
    def factory(name: str):
        if name == "openai:primary":
            raise RuntimeError("missing API key")
        return FakeModel()

    chain = get_model_with_fallback("openai:primary", "openai:fallback", factory=factory)
    assert chain.model_names == ["openai:fallback"]


def test_chain_raises_when_nothing_initialises() -> None:
    def factory(name: str):
        raise RuntimeError("missing API key")

    with pytest.raises(LLMUnavailableError, match="no usable model"):
        get_model_with_fallback("openai:primary", "openai:fallback", factory=factory)


def test_record_model_used_returns_partial_update_without_mutating() -> None:
    state = {"models_used": {"planner": "openai:gpt-4o"}, "run_id": "r1"}
    update = record_model_used("codegen", "openai:primary", state)
    assert update == {"models_used": {"planner": "openai:gpt-4o", "codegen": "openai:primary"}}
    assert state["models_used"] == {"planner": "openai:gpt-4o"}


# ---------------------------------------------------------------------- parsing
def test_parse_plain_fenced_and_prefixed_json() -> None:
    expected = parse_codegen_output(GOOD_JSON)
    assert parse_codegen_output(f"```json\n{GOOD_JSON}\n```") == expected
    assert parse_codegen_output(f"Here you go:\n{GOOD_JSON}") == expected


def test_parse_ignores_braces_around_the_json() -> None:
    noisy = "Here {you} go:\n" + GOOD_JSON + "\nDone {ok}"
    assert parse_codegen_output(noisy) == parse_codegen_output(GOOD_JSON)


def test_fences_inside_the_code_field_are_stripped() -> None:
    raw = '{"scenario_id": "s1", "code": "```ts\\nconst a = 1;\\n```"}'
    assert parse_codegen_output(raw).code == "const a = 1;"


@pytest.mark.parametrize("bad", ["no json here", '{"scenario_id": "s1"}', '{"scenario_id": 1, "code": ""}', "[1, 2]", '{"code": '])
def test_parse_rejects_invalid_output(bad: str) -> None:
    with pytest.raises(OutputParseError):
        parse_codegen_output(bad)


# ---------------------------------------------------------------------- backend
def test_generate_returns_result_and_model_used() -> None:
    primary = FakeModel(ai(GOOD_JSON))
    result, model = backend(primary).generate("SYSTEM", "PAYLOAD")
    assert result.scenario_id == "s1"
    assert model == "openai:primary"
    assert [type(m).__name__ for m in primary.calls[0]] == ["SystemMessage", "HumanMessage"]


def test_one_retry_passes_the_parse_error_back_to_the_model() -> None:
    primary = FakeModel(ai("sorry, no json"), ai(GOOD_JSON))
    result, model = backend(primary).generate("S", "P")
    assert result.scenario_id == "s1" and model == "openai:primary"
    retry_prompt = primary.calls[1][-1].content
    assert "could not be used" in retry_prompt and "no JSON object" in retry_prompt
    assert len(primary.calls) == 2


def test_falls_back_after_the_single_retry_fails() -> None:
    primary = FakeModel(ai("bad"), ai("still bad"))
    fallback = FakeModel(ai(GOOD_JSON))
    result, model = backend(primary, fallback).generate("S", "P")
    assert model == "openai:fallback" and result.scenario_id == "s1"
    assert len(primary.calls) == 2  # exactly one retry, no more


def test_falls_back_when_the_primary_call_raises() -> None:
    primary = FakeModel(ConnectionError("provider down"))
    fallback = FakeModel(ai(GOOD_JSON))
    assert backend(primary, fallback).generate("S", "P")[1] == "openai:fallback"


def test_all_models_failing_raises_llm_unavailable() -> None:
    with pytest.raises(LLMUnavailableError, match="all models failed"):
        backend(FakeModel(ConnectionError("down")), FakeModel(ConnectionError("down too"))).generate("S", "P")


def test_api_keys_never_leak_into_failure_messages() -> None:
    primary = FakeModel(RuntimeError("Incorrect API key provided: sk-abcd1234efgh5678"))
    with pytest.raises(LLMUnavailableError) as info:
        backend(primary).generate("S", "P")
    assert "sk-abcd" not in str(info.value)


def test_backend_works_with_run_codegen(tmp_path: Path) -> None:
    # The contract between llm/client.py and agents/codegen.py
    primary = FakeModel(ai('{"scenario_id": "s1", "code": "// x"}'))
    state = {"run_id": "r1", "test_plan": [{"name": "Add"}], "target_url": None}
    out = run_codegen(state, backend=backend(primary), runs_root=tmp_path, system_prompt="p")
    assert [Path(p).name for p in out["generated_test_files"]] == ["s1-add.spec.ts"]
    assert out["models_used"] == {"codegen": "openai:primary"} and out["errors"] == []


# ------------------------------------------------------------------------ tools
def test_only_the_two_browser_tools_are_bound() -> None:
    primary = FakeModel(ai(GOOD_JSON))
    backend(primary, tools=[browser_snapshot, browser_generate_locator, save_test_file]).generate("S", "P")
    assert primary.bound == ["browser_snapshot", "browser_generate_locator"]


def test_select_codegen_tools_filters_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="llm.client"):
        selected = select_codegen_tools([browser_snapshot, save_test_file])
    assert [t.name for t in selected] == ["browser_snapshot"]
    assert "save_test_file" in caplog.text and "browser_generate_locator" in caplog.text


def test_tool_calls_are_executed_and_results_fed_back() -> None:
    call = {"name": "browser_generate_locator", "args": {"element": "Log in"}, "id": "c1"}
    primary = FakeModel(ai("", tool_calls=[call]), ai(GOOD_JSON))
    result, _ = backend(primary, tools=[browser_snapshot, browser_generate_locator]).generate("S", "P")
    assert result.scenario_id == "s1"
    tool_message = primary.calls[1][-1]
    assert tool_message.tool_call_id == "c1" and "getByRole" in tool_message.content


def test_async_only_tools_are_supported() -> None:
    # The real MCP adapter tools only implement the async interface
    call = {"name": "browser_snapshot", "args": {}, "id": "c1"}
    primary = FakeModel(ai("", tool_calls=[call]), ai(GOOD_JSON))
    backend(primary, tools=[async_snapshot]).generate("S", "P")
    assert "button" in primary.calls[1][-1].content


def test_a_crashing_tool_is_reported_to_the_model_not_raised() -> None:
    call = {"name": "browser_snapshot", "args": {}, "id": "c1"}
    primary = FakeModel(ai("", tool_calls=[call]), ai(GOOD_JSON))
    backend(primary, tools=[crashing_snapshot]).generate("S", "P")
    assert "browser crashed" in primary.calls[1][-1].content


def test_unknown_tool_call_gets_an_error_message_not_an_exception() -> None:
    call = {"name": "delete_everything", "args": {}, "id": "c9"}
    primary = FakeModel(ai("", tool_calls=[call]), ai(GOOD_JSON))
    backend(primary, tools=[browser_snapshot]).generate("S", "P")
    assert "unknown tool" in primary.calls[1][-1].content


def test_runaway_tool_calls_are_capped_then_the_model_must_answer() -> None:
    call = {"name": "browser_snapshot", "args": {}, "id": "c1"}
    looping = [ai("", tool_calls=[call]) for _ in range(client.MAX_TOOL_ROUNDS + 1)]
    primary = FakeModel(*looping, ai(GOOD_JSON))
    result, _ = backend(primary, tools=[browser_snapshot]).generate("S", "P")
    assert result.scenario_id == "s1"
    assert len(primary.calls) == client.MAX_TOOL_ROUNDS + 2


# ------------------------------------------------------------ logging and budget
def test_token_usage_is_logged_and_accumulated(caplog: pytest.LogCaptureFixture) -> None:
    primary = FakeModel(
        ai(GOOD_JSON, usage_metadata={"input_tokens": 120, "output_tokens": 30, "total_tokens": 150})
    )
    b = backend(primary)
    with caplog.at_level(logging.INFO, logger="llm.client"):
        b.generate("S", "P")
    assert "llm_usage" in caplog.text and "total_tokens=150" in caplog.text
    assert b.usage["openai:primary"].total_tokens == 150


def test_budget_exceeded_is_not_failed_over() -> None:
    budget = RunBudget(max_calls=1)
    primary = FakeModel(ai("bad"), ai(GOOD_JSON))  # first reply forces a retry -> second call
    fallback = FakeModel(ai(GOOD_JSON))
    with pytest.raises(BudgetExceededError):
        backend(primary, fallback, budget=budget).generate("S", "P")
    assert fallback.calls == []


def test_token_budget_blocks_the_next_call() -> None:
    budget = RunBudget(max_tokens=100)
    primary = FakeModel(ai(GOOD_JSON, usage_metadata={"input_tokens": 90, "output_tokens": 20, "total_tokens": 110}))
    b = backend(primary, budget=budget)
    b.generate("S", "P")
    with pytest.raises(BudgetExceededError, match="max_tokens_per_run"):
        b.generate("S", "P")


def test_one_budget_is_shared_across_agents() -> None:
    budget = RunBudget(max_calls=1)  # the spec caps agent calls per RUN, not per agent
    first = backend(FakeModel(ai(GOOD_JSON)), budget=budget)
    second = backend(FakeModel(ai(GOOD_JSON)), budget=budget)
    first.generate("S", "P")
    with pytest.raises(BudgetExceededError):
        second.generate("S", "P")