"""
Purpose: Tests for report/ package — ReportModel building and format exporters.
"""
from __future__ import annotations

# --- model ---

# def test_build_report_model_maps_terminal_status_verbatim() -> None:
#     -> state["terminal_status"]="FAIL" → report_model.terminal_status == "FAIL" (no reclassification)

# def test_determine_terminal_status_all_pass() -> None:
#     -> stats.unexpected==0 → "PASS"

# def test_determine_terminal_status_any_fail() -> None:
#     -> stats.unexpected>0 and failure classified → "FAIL"

# def test_determine_terminal_status_blocked_on_no_url() -> None:
#     -> target_url=None → "BLOCKED"

# def test_defect_candidates_only_for_application_failures() -> None:
#     -> failure_type="Application" → defect_candidates is non-empty
#     -> failure_type="Test" → defect_candidates is empty

# def test_build_report_model_never_calls_agents() -> None:
#     -> build_report_model must not make any LLM calls (mock assertion)

# --- exporters ---

# def test_export_markdown_writes_report_md() -> None:
#     -> Given a ReportModel and temp run_dir, report.md is created

# def test_export_markdown_contains_run_id() -> None:
#     -> report.md content contains the run_id string

# def test_export_html_writes_index_html() -> None:
#     -> Given a ReportModel and temp run_dir, html-report/index.html is created

# def test_export_pdf_writes_report_pdf() -> None:
#     -> Given an html_path, report.pdf is written to run_dir (may be skipped if Chromium not available)

import json
from pathlib import Path

from report.exporters import fence, md_cell, render_html, render_markdown, run_report, write_reports
from report.model import build_report_model, decide_terminal_status, parse_playwright_results

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "report_model.json"
SECRET = "sk-abcd1234efgh5678"

PLAYWRIGHT_JSON = {
    "stats": {"duration": 41700},
    "suites": [{"title": "root", "suites": [{"specs": [
        {"file": "s1-add-todo.spec.ts", "ok": True,
         "tests": [{"status": "expected", "results": [{"duration": 6200}]}]},
        {"file": "s2-counter.spec.ts", "ok": False,
         "tests": [{"status": "unexpected", "results": [{"duration": 12900}]}]},
    ]}]}],
}


def make_state(tmp_path: Path) -> dict:
    tests_dir = tmp_path / "runs" / "r1" / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "s1-add-todo.spec.ts").write_text("// s1\n", encoding="utf-8")
    (tests_dir / "s2-counter.spec.ts").write_text("// s2\n", encoding="utf-8")
    return {
        "run_id": "r1",
        "test_request": {"requirements": "اختبر إضافة عنصر وتحديث العداد"},
        "target_url": {"url": "https://demo.playwright.dev/todomvc", "source": "field"},
        "test_plan": [
            {"name": "Add todo", "steps": [{"action": "navigate", "target": "https://x"}], "expected_result": "added"},
            {"name": "Counter", "steps": [], "expected_result": "updates"},
            {"name": "Login", "steps": [], "status": "BLOCKED: missing test data"},
        ],
        "generated_test_files": [str(tests_dir / "s1-add-todo.spec.ts"), str(tests_dir / "s2-counter.spec.ts")],
        "execution_result": PLAYWRIGHT_JSON,
        "failure_analysis": {"failure_type": "Application", "root_cause": "Counter does not update.",
                             "evidence": "expected 1 item left", "application_bug": True, "fix_required": False,
                             "confidence": "high"},
        "failure_type": "Application",
        "models_used": {"codegen": "openai:gpt-4o"},
        "generation_retry_count": 1,
        "healing_retry_count": {"s2": 1},
        "errors": [],
    }


# ---- model: status and counts
def test_model_counts_and_status(tmp_path: Path) -> None:
    model = build_report_model(make_state(tmp_path))
    assert model["terminal_status"] == "FAIL"
    assert model["counts"] == {"total": 3, "passed": 1, "failed": 1, "blocked": 1}
    assert [s["status"] for s in model["scenarios"]] == ["PASSED", "FAILED", "BLOCKED"]
    assert model["scenarios"][2]["blocked_reason"] == "missing test data"
    assert model["duration_s"] == 41.7
    assert model["attempts"] == {"generation_retries": 1, "healing": {"s2": 1}}


def test_application_failure_becomes_a_defect_candidate(tmp_path: Path) -> None:
    model = build_report_model(make_state(tmp_path))
    assert model["failure_analysis"][0]["scenario_id"] == "s2"
    assert model["defect_candidates"] == [{"scenario_id": "s2", "summary": "Counter does not update."}]


def test_test_class_failure_is_not_a_defect_candidate(tmp_path: Path) -> None:
    state = make_state(tmp_path)
    state["failure_type"] = "Test"
    state["failure_analysis"]["failure_type"] = "Test"
    assert build_report_model(state)["defect_candidates"] == []


def test_scenario_without_a_spec_file_is_blocked_could_not_generate(tmp_path: Path) -> None:
    state = make_state(tmp_path)
    state["generated_test_files"] = state["generated_test_files"][:1]
    state["execution_result"] = {"suites": [{"specs": [PLAYWRIGHT_JSON["suites"][0]["suites"][0]["specs"][0]]}]}
    model = build_report_model(state)
    assert model["scenarios"][1]["status"] == "BLOCKED"
    assert model["scenarios"][1]["blocked_reason"] == "could not generate"
    assert model["terminal_status"] == "BLOCKED"


def test_generated_code_is_included_and_patch_is_marked(tmp_path: Path) -> None:
    state = make_state(tmp_path)
    state["fix_proposal"] = {"patch_diff": "-a\n+b", "reason": "selector", "risky": False}
    state["approval_decision"] = "auto"
    model = build_report_model(state)
    assert [c["file"] for c in model["generated_code"]] == ["s1-add-todo.spec.ts", "s2-counter.spec.ts"]
    assert model["patches"][0]["applied"] is True
    assert model["patches"][0]["requirement"] == state["test_request"]["requirements"]
    assert [c["patched"] for c in model["generated_code"]] == [False, True]


def test_non_english_requirements_get_a_note_and_stay_verbatim(tmp_path: Path) -> None:
    model = build_report_model(make_state(tmp_path))
    assert model["requirements_text"] == "اختبر إضافة عنصر وتحديث العداد"
    assert "not written in English" in model["requirements_note"]
    state = make_state(tmp_path / "x")
    state["test_request"] = {"requirements": "Add an item"}
    assert build_report_model(state)["requirements_note"] is None


def test_secrets_are_redacted_in_errors_and_analysis(tmp_path: Path) -> None:
    state = make_state(tmp_path)
    state["errors"] = [f"codegen[s1]: bad key {SECRET}"]
    state["failure_analysis"]["root_cause"] = f"auth failed with {SECRET}"
    model = build_report_model(state)
    assert SECRET not in json.dumps(model, ensure_ascii=False)


# ---- terminal status rules
def scen(*statuses: str) -> list[dict]:
    return [{"status": s} for s in statuses]


def test_status_pass_when_everything_passed() -> None:
    assert decide_terminal_status({}, scen("PASSED", "PASSED")) == "PASS"


def test_status_keeps_a_preset_value() -> None:
    assert decide_terminal_status({"terminal_status": "BLOCKED"}, scen("PASSED")) == "BLOCKED"


def test_status_fatal_llm_error_is_error() -> None:
    assert decide_terminal_status({"errors": ["llm-fatal[codegen]: down"]}, scen("BLOCKED")) == "ERROR"


def test_status_validator_tooling_error_is_error() -> None:
    assert decide_terminal_status({"validation_status": "error"}, scen("PASSED")) == "ERROR"


def test_status_node_crash_is_error_but_one_scenario_codegen_failure_is_not() -> None:
    assert decide_terminal_status({"errors": ["report: boom"]}, scen("PASSED")) == "ERROR"
    assert decide_terminal_status({"errors": ["codegen[s2]: x"]}, scen("PASSED", "BLOCKED")) == "BLOCKED"


def test_status_failure_without_a_valid_class_is_error_never_a_guess() -> None:
    state = {"failure_analysis": {"failure_type": "Weird"}, "failure_type": "Weird"}
    assert decide_terminal_status(state, scen("FAILED")) == "ERROR"
    assert decide_terminal_status({}, scen("FAILED")) == "ERROR"


def test_status_empty_plan_and_not_run_are_errors() -> None:
    assert decide_terminal_status({}, []) == "ERROR"
    assert decide_terminal_status({}, scen("PASSED", "NOT_RUN")) == "ERROR"


# ---- playwright results parsing
def test_parse_playwright_results_handles_nesting_and_skips() -> None:
    raw = {"suites": [{"suites": [{"specs": [
        {"file": "s1-a.spec.ts", "ok": True, "tests": [{"status": "expected", "results": [{"duration": 1000}]}]},
        {"file": "s3-c.spec.ts", "ok": True, "tests": [{"status": "skipped", "results": []}]},
    ]}]}]}
    found = parse_playwright_results(raw)
    assert found["s1"] == {"status": "passed", "duration_s": 1.0}
    assert found["s3"]["status"] == "skipped"
    assert parse_playwright_results(None) == {}


# ---- rendering
def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_markdown_has_every_section_and_keeps_arabic() -> None:
    md = render_markdown(load_fixture())
    for heading in ("# Test Run Report", "## Requirements", "## Summary", "## Models used", "## Scenarios",
                    "## Failure analysis", "## Evidence", "## Patches", "## Generated code",
                    "## Defect candidates"):
        assert heading in md
    assert "| **Status** | FAIL |" in md and "| 3 | 1 | 1 | 1 |" in md
    assert "شراء الخبز" in md


def test_markdown_and_html_show_the_same_facts() -> None:
    model = load_fixture()
    md, html = render_markdown(model), render_html(model)
    for fact in ("run-20261017-demo01", "FAIL", "Counter shows remaining items", "BLOCKED", "missing test data"):
        assert fact in md and fact in html


def test_a_crashed_run_still_renders_in_both_formats() -> None:
    model = {"terminal_status": "ERROR", "errors": ["codegen: boom"]}
    md, html = render_markdown(model), render_html(model)
    assert "| **Status** | ERROR |" in md and "codegen: boom" in md
    assert "codegen: boom" in html and "## Failure analysis" not in md


def test_html_escapes_untrusted_text() -> None:
    model = load_fixture()
    model["failure_analysis"][0]["root_cause"] = "<script>alert(1)</script>"
    model["scenarios"][0]["name"] = "<img src=x onerror=alert(1)>"
    html = render_html(model)
    assert "<script>" not in html and "<img src=x" not in html
    assert "&lt;script&gt;" in html


def test_md_cell_escapes_pipes_and_newlines() -> None:
    assert md_cell("a|b\nc") == "a\\|b c"


def test_fence_cannot_be_closed_by_backticks_in_the_text() -> None:
    out = fence("code with ``` inside", "ts")
    assert out.startswith("````ts\n") and out.endswith("\n````")


# ---- the node
def test_run_report_writes_both_files_and_returns_the_status(tmp_path: Path) -> None:
    out = run_report(make_state(tmp_path), runs_root=tmp_path / "out")
    assert out["terminal_status"] == "FAIL"
    assert Path(out["report_path"]).name == "report.md"
    assert (Path(out["report_path"]).parent / "report.html").is_file()


def test_run_report_never_raises_and_still_writes_a_report(tmp_path: Path) -> None:
    out = run_report({"run_id": "r9", "test_plan": 5, "errors": ["old"]}, runs_root=tmp_path)
    assert out["terminal_status"] == "ERROR"
    assert out["errors"][0] == "old" and out["errors"][-1].startswith("report:")
    assert "System errors" in Path(out["report_path"]).read_text(encoding="utf-8")


def test_run_id_cannot_escape_the_runs_folder(tmp_path: Path) -> None:
    out = run_report({"run_id": "../../evil", "test_plan": [{"name": "A"}]}, runs_root=tmp_path / "runs")
    assert (tmp_path / "runs") in Path(out["report_path"]).resolve().parents


def test_write_reports_does_not_change_the_model(tmp_path: Path) -> None:
    model = load_fixture()
    before = json.dumps(model, sort_keys=True)
    write_reports(model, tmp_path / "run")
    assert json.dumps(model, sort_keys=True) == before


def test_real_execution_result_with_results_path_gives_scenario_statuses(tmp_path) -> None:
    """The real executor stores stats + results_path only; the report must read results.json, not show NOT_RUN."""
    import json

    from report.model import build_report_model

    results = tmp_path / "results.json"
    results.write_text(json.dumps({
        "stats": {"expected": 1, "unexpected": 0, "duration": 1500},
        "suites": [{"file": "s1-login.spec.ts", "specs": [
            {"title": "Login", "file": "s1-login.spec.ts", "ok": True,
             "tests": [{"status": "expected", "results": [{"status": "passed", "duration": 1500}]}]}]}],
    }), encoding="utf-8")
    model = build_report_model({
        "run_id": "r1", "test_plan": [{"name": "Login", "steps": [], "expected_result": "ok"}],
        "generated_test_files": ["runs/r1/tests/s1-login.spec.ts"],
        "execution_result": {"stats": {"expected": 1}, "results_path": str(results)},
        "errors": [],
    })
    assert model["scenarios"][0]["status"] == "PASSED"
    assert model["terminal_status"] == "PASS"
