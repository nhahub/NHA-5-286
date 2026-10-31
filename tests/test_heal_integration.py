"""Heal path with a stub model: analyze -> fix proposal -> approval -> apply fix, on a real spec file."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from agents.analyzer import RawFailureAnalysis, run_analyzer
from agents.codegen import spec_file_name
from agents.fix_proposal import RawFix, run_fix_proposal, read_failed_spec_code
from graph.nodes import apply_fix_node, fix_approval_node
from graph.routing import route_after_analyze, route_after_apply_fix, route_after_fix_approval, route_after_fix_proposal

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "itest-heal-run"
NAME = "Invalid password shows error"
BROKEN = "import { test, expect } from '@support/evidence';\n\ntest('Invalid password shows error', async ({ page }) => {\n  await page.goto('https://example.com');\n  await page.getByLabel('Username').fill('a');\n  await expect(page.getByText('Invalid')).toBeVisible();\n});\n"
FIXED = BROKEN.replace("getByLabel('Username')", "getByPlaceholder('Username')")


@pytest.fixture
def run_dir():
    path = ROOT / "runs" / RUN_ID
    (path / "tests").mkdir(parents=True, exist_ok=True)
    spec = path / "tests" / spec_file_name("s1", NAME)
    spec.write_text(BROKEN, encoding="utf-8", newline="\n")
    yield spec
    shutil.rmtree(path, ignore_errors=True)


class _FixLLM:
    def __init__(self, result):
        self.result = result

    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return self.result

    def __or__(self, other):  # prompt | llm
        return self


def test_failure_to_applied_fix_reaches_revalidation(run_dir, monkeypatch):
    import agents.analyzer as analyzer_module
    import agents.fix_proposal as fix_module

    state = {
        "run_id": RUN_ID, "mock_mode": False, "errors": [], "models_used": {}, "healing_retry_count": 0,
        "test_request": {"requirements": "login", "auto_heal_mode": "manual"},
        "test_plan": [{"name": NAME}],
        "generated_test_files": [str(run_dir)],
        "execution_result": {"stats": {"unexpected": 1}},
        "execution_evidence": [{"scenario_name": NAME, "error_message": "locator.fill: Timeout waiting for getByLabel('Username')"}],
    }

    monkeypatch.setattr(analyzer_module, "build_analyzer_agent", lambda **kw: object())
    monkeypatch.setattr(analyzer_module, "_invoke_analyzer", lambda **kw: RawFailureAnalysis(
        failure_type="Test", root_cause="The username label selector does not match.", evidence="fill timed out",
        application_bug=False, fix_required=True, subtype="SELECTOR", confidence="medium"))
    state.update(run_analyzer(state, model="openrouter:m", model_factory=lambda _m: None))
    assert route_after_analyze(state) == "fix_proposal"  # medium confidence is enough to try a fix

    monkeypatch.setattr(fix_module, "build_fix_proposal_agent",
                        lambda **kw: _FixLLM(RawFix(reason="Use the placeholder locator", risky=False, fixed_code=FIXED)))
    spec_code, spec_filename = read_failed_spec_code(state)
    state.update(run_fix_proposal(state, spec_code=spec_code, spec_filename=spec_filename,
                                  model="openrouter:m", model_factory=lambda _m: None))
    assert route_after_fix_proposal(state) == "fix_approval"
    assert "+  await page.getByPlaceholder('Username')" in state["fix_proposal"]["patch_diff"]

    # manual mode: the approval node would interrupt; simulate the human decision
    state["approval_decision"] = "approved"
    assert route_after_fix_approval(state) == "apply_fix"
    state.update(apply_fix_node(state))
    assert run_dir.read_text(encoding="utf-8") == FIXED
    assert state["healing_retry_count"] == 1
    assert route_after_apply_fix(state) == "validate"


def test_auto_heal_applies_non_risky_fix_without_interrupt(run_dir):
    state = {"mock_mode": False, "test_request": {"auto_heal_mode": "auto"}, "fix_proposal": {"risky": False, "patch_diff": "x"}}
    assert fix_approval_node(state) == {"approval_decision": "auto"}
