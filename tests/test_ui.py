"""
Purpose: Tests for ui/app.py — Gradio form wiring and input validation.
"""

# def test_build_ui_returns_gradio_blocks() -> None:
#     -> build_ui() returns a gr.Blocks instance without raising

# def test_handle_submit_rejects_unchecked_authorization() -> None:
#     -> authorization=False → handle_submit raises or returns an error message before graph invocation

# def test_handle_submit_rejects_invalid_model_string() -> None:
#     -> planner_model="gpt-4o" (no provider prefix) → returns validation error, graph not invoked

# def test_handle_submit_accepts_empty_url_and_url_in_requirements() -> None:
#     -> url="", requirements containing one HTTPS URL → accepted; URL extracted by intake

# def test_handle_submit_builds_test_request_with_correct_fields() -> None:
#     -> Captures the TestRequest passed to the graph and asserts field mapping is correct

# def test_api_keys_not_visible_in_ui_components() -> None:
#     -> No Gradio component in build_ui() has "key" or "secret" in its label (keys are env-only)


def test_clear_history_removes_logs_and_reports_but_keeps_specs(tmp_path, monkeypatch):
    from ui import history as H

    runs = tmp_path / "runs"
    (runs / "r1" / "tests").mkdir(parents=True)
    (runs / "r1" / "report.md").write_text("x")
    (runs / "r1" / "report.html").write_text("x")
    (runs / "r1" / "tests" / "s1.spec.ts").write_text("x")
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "a.pdf").write_text("x")
    log = runs / "ui_history.jsonl"
    log.write_text("{}\n")
    monkeypatch.setattr(H, "RUNS_DIR", runs)
    monkeypatch.setenv("QC_UI_HISTORY", str(log))

    assert H.clear_history((exports,)) == 4
    assert not log.exists() and not (runs / "r1" / "report.md").exists() and not (exports / "a.pdf").exists()
    assert (runs / "r1" / "tests" / "s1.spec.ts").exists()
