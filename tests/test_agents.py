"""
Purpose: Tests for agents/ package — Planner, Code Generation, Failure Analyzer, Fix Proposal.
"""



# --- planner ---

# def test_planner_output_validates_as_scenario_list() -> None:
#     -> With a mocked LLM returning valid JSON, run_planner returns a non-empty list[Scenario]

# def test_planner_respects_scenario_cap() -> None:
#     -> scenario_cap=2: planner must not return more than 2 scenarios

# def test_planner_does_not_write_playwright_code() -> None:
#     -> Planner output must contain no "await page." strings

# --- codegen ---
"""Purpose: Tests for agents/codegen.py (no LLM, no Node)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agents.codegen import (
    CodegenError, CodegenResult, build_user_payload, failing_scenario_ids, load_prompt,
    run_codegen, scenario_id, slugify, spec_file_name, strip_code_fences,
)


class FakeBackend:
    def __init__(self, fail_ids: tuple[str, ...] = (), wrong_id: bool = False) -> None:
        self.calls: list[dict] = []
        self.fail_ids, self.wrong_id = set(fail_ids), wrong_id

    def generate(self, system_prompt: str, user_payload: str):
        data = json.loads(user_payload)
        sid = data["scenario"]["id"]
        self.calls.append(data)
        if sid in self.fail_ids:
            raise RuntimeError("llm down")
        return CodegenResult(scenario_id="zzz" if self.wrong_id else sid, code=f"// code for {sid}\n"), "openai:gpt-4o"


PLAN = [
    {"name": "First one", "steps": [], "expected_result": "a", "status": None},
    {"name": "Second one", "steps": [], "expected_result": "b", "status": None},
]


def make_state(**extra) -> dict:
    return {"run_id": "r1", "test_plan": PLAN, "target_url": "https://demo.playwright.dev/todomvc", **extra}


def run(state: dict, backend: FakeBackend, tmp_path: Path) -> dict:
    return run_codegen(state, backend=backend, runs_root=tmp_path, system_prompt="PROMPT")


# ---- pure helpers
def test_load_prompt_fills_placeholders(tmp_path: Path) -> None:
    prompt = tmp_path / "p.md"
    prompt.write_text("import from '{{evidence_import}}'\n{{reference_examples}}", encoding="utf-8")
    refs = tmp_path / "ref"
    refs.mkdir()
    (refs / "01-a.spec.ts").write_text("// example a\n", encoding="utf-8")
    text = load_prompt(prompt, refs)
    assert "@support/evidence" in text and "// example a" in text and "{{" not in text


def test_load_prompt_without_references_raises(tmp_path: Path) -> None:
    prompt = tmp_path / "p.md"
    prompt.write_text("x", encoding="utf-8")
    with pytest.raises(CodegenError):
        load_prompt(prompt, tmp_path)


def test_ids_and_file_names() -> None:
    assert scenario_id(0, {}) == "s1"
    assert scenario_id(0, {"id": "S-7"}) == "s7"
    assert slugify("Add a new todo item!") == "add-a-new-todo-item"
    assert spec_file_name("s1", "Add a new todo") == "s1-add-a-new-todo.spec.ts"
    assert slugify("???") == "scenario"


def test_failing_scenario_ids_attribution() -> None:
    ids = {"s1", "s2", "s3"}
    assert failing_scenario_ids(["[no-fixed-wait] s2-x.spec.ts:4 msg"], ids) == {"s2"}
    assert failing_scenario_ids(["[TS2339] s1-a.spec.ts:3 m", "[single-test] s3-c.spec.ts m"], ids) == {"s1", "s3"}
    assert failing_scenario_ids(["[no-files] nothing"], ids) == ids  # unattributable -> everything


def test_strip_code_fences_and_result_validation() -> None:
    assert strip_code_fences("```typescript\nconst a = 1;\n```") == "const a = 1;"
    assert CodegenResult(scenario_id="s1", code="```ts\nx\n```").code == "x"
    with pytest.raises(ValidationError):
        CodegenResult(scenario_id="s1", code="   ")


def test_payload_drops_status_and_caps_errors() -> None:
    payload = json.loads(build_user_payload(PLAN[0], "s1", None, validation_errors=["e"] * 50))
    assert "status" not in payload["scenario"] and payload["scenario"]["id"] == "s1"
    assert len(payload["validation_errors"]) == 20


# ---- node
def test_first_pass_generates_every_scenario(tmp_path: Path) -> None:
    backend = FakeBackend()
    out = run(make_state(), backend, tmp_path)
    names = [Path(p).name for p in out["generated_test_files"]]
    assert names == ["s1-first-one.spec.ts", "s2-second-one.spec.ts"]
    assert all(Path(p).is_file() for p in out["generated_test_files"])
    assert out["models_used"] == {"codegen": "openai:gpt-4o"}
    assert out["errors"] == [] and "generation_retry_count" not in out


def test_retry_regenerates_only_the_failing_scenario(tmp_path: Path) -> None:
    first = run(make_state(), FakeBackend(), tmp_path)
    s1_before = Path(first["generated_test_files"][0]).read_text(encoding="utf-8")
    backend = FakeBackend()
    retry = make_state(
        generated_test_files=first["generated_test_files"],
        validation_errors=["[no-fixed-wait] s2-second-one.spec.ts:4 waitForTimeout is forbidden"],
    )
    out = run(retry, backend, tmp_path)
    assert [c["scenario"]["id"] for c in backend.calls] == ["s2"]
    assert backend.calls[0]["previous_code"] == "// code for s2\n"
    assert backend.calls[0]["validation_errors"][0].startswith("[no-fixed-wait]")
    assert Path(out["generated_test_files"][0]).read_text(encoding="utf-8") == s1_before
    assert len(out["generated_test_files"]) == 2


def test_one_failing_scenario_does_not_stop_the_others(tmp_path: Path) -> None:
    out = run(make_state(), FakeBackend(fail_ids=("s1",)), tmp_path)
    assert [Path(p).name for p in out["generated_test_files"]] == ["s2-second-one.spec.ts"]
    assert any("codegen[s1]" in e and "llm down" in e for e in out["errors"])


def test_mismatched_scenario_id_is_recorded_not_raised(tmp_path: Path) -> None:
    out = run(make_state(), FakeBackend(wrong_id=True), tmp_path)
    assert out["generated_test_files"] == []
    assert len(out["errors"]) == 2


def test_empty_plan_is_recorded_not_raised(tmp_path: Path) -> None:
    out = run({"run_id": "r1", "test_plan": [], "errors": ["old"]}, FakeBackend(), tmp_path)
    assert out["errors"] == ["old", "codegen: test_plan is empty"]


def test_missing_run_id_is_recorded_not_raised(tmp_path: Path) -> None:
    out = run({"test_plan": PLAN}, FakeBackend(), tmp_path)
    assert any(e.startswith("codegen") for e in out["errors"])


# --- analyzer ---

# def test_analyzer_output_validates_as_failure_analysis() -> None:
#     -> With a mocked LLM returning valid JSON, run_analyzer produces a FailureAnalysis

# def test_unknown_failure_class_becomes_error() -> None:
#     -> Analyzer output with failure_type="Unknown" → failure_type set to "ERROR" by pre_classifier

# def test_subtype_rejected_for_non_test_class() -> None:
#     -> failure_type="Application", subtype="SELECTOR" → FailureAnalysis raises ValidationError

# --- fix_proposal ---

# def test_fix_proposal_output_validates() -> None:
#     -> With a mocked LLM, run_fix_proposal produces a FixProposal with patch_diff, reason, risky

# def test_assertion_subtype_forces_risky_true() -> None:
#     -> When failure_analysis.subtype == "ASSERTION", fix_proposal.risky must be True
