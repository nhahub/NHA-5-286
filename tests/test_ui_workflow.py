"""Tests for the UI <-> LangGraph wiring (streaming progress, interrupt/resume, healing, LLM settings)."""
import pytest

import ui.app as app
from llm import settings as llm_settings


def _last(gen):
    frame = None
    for frame in gen:
        pass
    return frame


def _start(outcome="FAIL", fixes=1, use_mock=True, llm_cfg=None):
    return app.start_graph_workflow(
        "https://example.com/login", "Verify invalid login", "Chromium", "Headless", 3, 30,
        True, use_mock, outcome, False, fixes, llm_cfg, [],
    )


def _resume_all(session, decisions):
    for decision in decisions:
        if not app._pending_interrupt(session["thread_id"]):
            break
        session = _last(app.resume_graph_workflow(session, decision))[1]
    return session


def test_build_ui_returns_blocks():
    assert app.build_ui() is not None


def test_progress_streams_distinct_frames_and_waits_for_approval():
    frames = list(_start())
    assert len(frames) > 5  # one frame per node event, not a single final render
    assert "status-running" in frames[1][2]
    final = frames[-1]
    assert "status-waiting-for-approval" in final[2]
    assert final[1]["waiting_for_approval"] is True
    assert final[4]["visible"] is True  # approve/reject buttons shown from the real interrupt


def test_pass_run_skips_healing_stages():
    final = _last(_start("PASS"))
    run = app.build_run(final[1]["thread_id"])
    assert run["terminal_status"] == "PASS" and run["healing_attempts"] == 0
    assert run["stages"]["Analyzer"] == "Skipped"
    assert run["trail"][-1] == "report"


@pytest.mark.parametrize("fixes,decisions,status,heals", [
    (1, ["approved"], "PASS", 1),
    (2, ["approved", "approved"], "PASS", 2),
    (3, ["approved", "approved"], "FAIL", 2),  # limit of 2 healing attempts is enforced
    (1, ["rejected"], "FAIL", 0),
])
def test_healing_cycles_and_decisions(fixes, decisions, status, heals):
    session = _last(_start("FAIL", fixes))[1]
    session = _resume_all(session, decisions)
    run = app.build_run(session["thread_id"])
    assert (run["terminal_status"], run["healing_attempts"]) == (status, heals)
    assert not app._pending_interrupt(session["thread_id"])
    assert run["trail"].count("apply_fix (attempt 1)") == (1 if heals else 0)


def test_rerun_history_is_preserved():
    session = _resume_all(_last(_start("FAIL", 2))[1], ["approved", "approved"])
    tracker = app.RUNS[session["thread_id"]]["tracker"]
    executions = [h for h in tracker.history if h["stage"] == "Execution"]
    assert [h["status"] for h in executions] == ["Failed", "Failed", "Completed"]
    assert "Pass history" in app._progress_html(session["thread_id"])


def test_runs_keep_independent_state():
    first = _last(_start("FAIL", 1))[1]
    second = _last(_start("FAIL", 1))[1]
    _last(app.approve_workflow(first))
    assert app._pending_interrupt(second["thread_id"])  # the other run is still waiting
    assert app.build_run(first["thread_id"])["terminal_status"] == "PASS"
    assert app.build_run(second["thread_id"])["terminal_status"] == "FAIL"


def test_resume_without_pending_interrupt_is_rejected():
    session = _last(_start("PASS"))[1]
    assert _last(app.resume_graph_workflow(session, "approved"))[0] == "No pending approval request."


def test_results_use_real_state():
    session = _resume_all(_last(_start("FAIL", 1))[1], ["approved"])
    run = app.build_run(session["thread_id"])
    row = run["scenarios"][0]
    assert row["Status"] == "Passed" and "simulated" in row["Duration"]
    assert "SELECTOR" in row["Analysis"] and "diff" in row["Proposed Fix"]
    status, path = app.export_report(run, "Word (.docx)")
    assert path and "SIMULATED" in app.preview_report(run)


def test_live_mode_requires_validated_llm_and_never_mocks():
    frame = _last(_start(use_mock=False, llm_cfg=None))
    assert "validated LLM settings" in frame[0] and frame[1] is not llm_settings


def test_live_mode_stops_when_planner_fails_without_mock(monkeypatch):
    def failing_plan(*args, **kwargs):
        raise RuntimeError("provider rejected the request SECRET-KEY-123")

    monkeypatch.setattr("agents.planner.generate_plan", failing_plan)
    cfg = {"provider": "Gemini", "model": "m", "api_key": "SECRET-KEY-123", "validated": True}
    final = _last(_start(use_mock=False, llm_cfg=cfg))
    run = app.build_run(final[1]["thread_id"])
    assert "ERROR" in final[0] and "LIVE" in final[0]
    assert run["stages"]["Planner"] == "Failed" and run["execution_time"] == "Not executed"
    assert "SECRET-KEY-123" not in str(final) and "SECRET-KEY-123" not in app.preview_report(run)


def test_llm_validation_reports_problems_without_leaking_key():
    ok, msg = llm_settings.validate_settings("Nope", "llama3", "")
    assert not ok and "Unknown provider" in msg
    ok, msg = llm_settings.validate_settings("Groq", "m", "k")
    assert not ok and "langchain_groq" in msg  # package missing -> clear unavailable message

    def boom(provider, model, key):
        raise RuntimeError(f"401 bad key {key}")

    ok, msg = llm_settings.validate_settings("Gemini", "m", "TOPSECRET", factory=boom)
    assert not ok and "TOPSECRET" not in msg

    class Fake:
        def invoke(self, _):
            return "ok"

    ok, _ = llm_settings.validate_settings("Gemini", "m", "k", factory=lambda *a: Fake())
    assert ok


def test_registered_credentials_select_the_user_model():
    s = llm_settings.LLMSettings("Gemini", "gemini-x", "k", True)
    assert s.model_string == "google_genai:gemini-x" and "k" not in repr(s).replace("key", "")
    llm_settings.register_run_credentials("t1", s)
    with pytest.raises(RuntimeError):
        llm_settings.model_factory_for("t1")("google_genai:other")
    with pytest.raises(RuntimeError):
        llm_settings.model_factory_for("unknown")("google_genai:gemini-x")
