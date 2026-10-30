"""Real-mode building blocks: intake safety, planner, apply fix, approval routing."""
from __future__ import annotations

import pytest

from agents.planner import _PlannerOutput, generate_plan
from contracts.scenario import Scenario
from graph.nodes import apply_fix_node, fix_approval_node, intake_node
from graph.routing import route_after_apply_fix, route_after_fix_approval
from healing.apply_fix import apply_patch
from intake.safety import is_safe_url
from intake.url_resolver import resolve_url

REAL = {"mock_mode": False}


def test_resolve_url_sources() -> None:
    assert resolve_url({"url": "https://a.com", "requirements": "x"}) == ("https://a.com", "field")
    assert resolve_url({"requirements": "test https://a.com/login."}) == ("https://a.com/login", "requirements")
    assert resolve_url({"requirements": "https://a.com https://b.com"})[0] is None
    assert resolve_url({"requirements": "nothing"})[0] is None


@pytest.mark.parametrize("url", [
    "http://example.com", "https://localhost/x", "https://127.0.0.1", "https://192.168.1.5", "ftp://example.com",
])
def test_unsafe_urls_blocked(url: str) -> None:
    assert is_safe_url(url, allow_http=False)[0] is False


def test_intake_real_mode_requires_authorization_and_model() -> None:
    req = {"url": "https://93.184.216.34", "requirements": "r", "codegen_model": "groq:m"}
    assert intake_node({**REAL, "test_request": req})["terminal_status"] == "BLOCKED"
    ok = intake_node({**REAL, "test_request": {**req, "authorization": True}})
    assert "terminal_status" not in ok and ok["target_url"] == req["url"]
    no_model = {**req, "authorization": True, "codegen_model": None}
    assert intake_node({**REAL, "test_request": no_model})["terminal_status"] == "ERROR"


def test_intake_blocks_private_target() -> None:
    req = {"url": "https://10.0.0.1", "requirements": "r", "authorization": True, "codegen_model": "m"}
    assert intake_node({**REAL, "test_request": req})["terminal_status"] == "BLOCKED"


class _FakeLLM:
    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        step = {"action": "navigate", "target": "https://a.com"}
        s = Scenario(name=f"s{self.n}", steps=[step], expected_result="ok")
        self.n += 1
        return _PlannerOutput(scenarios=[s, s, s])

    n = 0


def test_real_planner_caps_scenarios(monkeypatch) -> None:
    monkeypatch.setattr("agents.planner.fetch_page_outline", lambda url: "outline")
    plan = generate_plan(
        {"url": "https://a.com", "requirements": "r", "scenario_cap": 2},
        model="groq:m", model_factory=lambda _m: _FakeLLM(),
    )
    assert len(plan) == 2


def test_real_planner_needs_model() -> None:
    with pytest.raises(ValueError):
        generate_plan({"requirements": "r"})


PATCH = "--- a/x.spec.ts\n+++ b/x.spec.ts\n@@ -1,2 +1,2 @@\n a\n-b\n+c\n"


def test_apply_patch_updates_file_or_leaves_it(tmp_path) -> None:
    spec = tmp_path / "x.spec.ts"
    spec.write_text("a\nb\n", encoding="utf-8", newline="\n")
    assert apply_patch(spec, PATCH) is True
    assert spec.read_text(encoding="utf-8") == "a\nc\n"
    assert apply_patch(spec, PATCH) is False  # already applied: no clean apply
    assert spec.read_text(encoding="utf-8") == "a\nc\n"


def test_real_apply_fix_requires_approval() -> None:
    out = apply_fix_node({**REAL, "fix_proposal": {"patch_diff": PATCH, "risky": False}, "approval_decision": "rejected"})
    assert out["terminal_status"] == "FAIL"
    assert route_after_apply_fix({**REAL, **out}) == "report"


def test_auto_approval_only_for_non_risky_with_auto_mode() -> None:
    base = {**REAL, "test_request": {"auto_heal_mode": "auto"}}
    safe = {**base, "fix_proposal": {"patch_diff": PATCH, "risky": False}}
    assert fix_approval_node(safe) == {"approval_decision": "auto"}
    assert route_after_fix_approval({**safe, "approval_decision": "auto"}) == "apply_fix"
    # manual mode (default) or risky: auto is never honoured
    manual = {**REAL, "test_request": {}, "fix_proposal": {"patch_diff": PATCH, "risky": False}, "approval_decision": "auto"}
    assert route_after_fix_approval(manual) == "report"
    risky = {**base, "fix_proposal": {"patch_diff": PATCH, "risky": True}, "approval_decision": "auto"}
    assert route_after_fix_approval(risky) == "report"
