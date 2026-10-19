"""
Purpose: Thin LangGraph node wrappers that delegate to service and agent functions; all exception catching goes here.
Reads: TestRunState
Writes: TestRunState
Must not: perform routing decisions (routing lives in routing.py) or contain agent logic
"""

# def node_intake(state: TestRunState) -> TestRunState:
#     -> Delegates to intake.url_resolver, intake.safety, intake.model_resolver
#     -> Catches all exceptions into state["errors"]

# def node_planner(state: TestRunState) -> TestRunState:
#     -> Delegates to agents.planner.run_planner
#     -> Catches all exceptions into state["errors"]

# def node_codegen(state: TestRunState) -> TestRunState:
#     -> Delegates to agents.codegen.run_codegen
#     -> Catches all exceptions into state["errors"]

# def node_validate(state: TestRunState) -> TestRunState:
#     -> Delegates to validation.validator.validate_all
#     -> Catches all exceptions into state["errors"]

# def node_human_code_review(state: TestRunState) -> TestRunState:
#     -> Delegates to healing.human_review.present_for_review
#     -> Catches all exceptions into state["errors"]

# def node_execute(state: TestRunState) -> TestRunState:
#     -> Delegates to execution.runner.run_execute
#     -> Catches all exceptions into state["errors"]

# def node_analyze(state: TestRunState) -> TestRunState:
#     -> Delegates to agents.analyzer.run_analyzer
#     -> Catches all exceptions into state["errors"]

# def node_fix_proposal(state: TestRunState) -> TestRunState:
#     -> Delegates to agents.fix_proposal.run_fix_proposal
#     -> Catches all exceptions into state["errors"]

# def node_apply_fix(state: TestRunState) -> TestRunState:
#     -> Delegates to healing.apply_fix.run_apply_fix
#     -> Catches all exceptions into state["errors"]

# def node_report(state: TestRunState) -> TestRunState:
#     -> Delegates to report.model.build_report_model and report.exporters
#     -> Always runs, even when state["errors"] is non-empty
#     -> Catches all exceptions; if report itself crashes, writes an emergency plain-text report

"""
Purpose: Thin LangGraph node wrappers.

All exception catching happens here.
Nodes delegate the actual work to the responsible
service/agent.
"""

from .state import TestRunState


def _add_error(state: TestRunState, error: Exception) -> TestRunState:
    """Add a node error without stopping the whole workflow."""
    errors = list(state.get("errors", []))
    errors.append(str(error))
    state["errors"] = errors
    return state


def node_intake(state: TestRunState) -> TestRunState:
    try:
        from intake.url_resolver import resolve_url
        from intake.safety import check_safety
        from intake.model_resolver import resolve_models

        # Actual integration depends on P1's implemented APIs.
        state["target_url"] = resolve_url(state["test_request"])
        check_safety(state["target_url"])
        state["models_used"] = resolve_models()

        return state

    except Exception as exc:
        return _add_error(state, exc)


def node_planner(state: TestRunState) -> TestRunState:
    try:
        from agents.planner import run_planner

        state["test_plan"] = run_planner(
            state["test_request"],
            state["target_url"],
        )

        return state

    except Exception as exc:
        return _add_error(state, exc)


def node_codegen(state: TestRunState) -> TestRunState:
    try:
        from agents.codegen import run_codegen

        state["generated_test_files"] = run_codegen(
            state["test_plan"],
            state.get("reviewer_note"),
            state.get("edited_code"),
        )

        return state

    except Exception as exc:
        return _add_error(state, exc)


def node_validate(state: TestRunState) -> TestRunState:
    try:
        from validation.validator import validate_all

        result = validate_all(state["generated_test_files"])
        status = result.get("status")

        state["validation_status"] = status
        state["validation_errors"] = result.get("errors", [])

        if status == "invalid":
            state["generation_retry_count"] = (
                state.get("generation_retry_count", 0) + 1
            )

        elif status not in {"valid", "invalid", "error"}:
            state["validation_status"] = "error"
            state["errors"] = list(state.get("errors", [])) + [
                f"Unexpected validation status: {status}"
            ]

        return state

    except Exception as exc:
        state["validation_status"] = "error"
        state["errors"] = list(state.get("errors", [])) + [
            f"Validation tool error: {exc}"
        ]
        return state



def node_human_code_review(state: TestRunState) -> TestRunState:
    try:
        from healing.human_review import present_for_review

        result = present_for_review(
            state["generated_test_files"]
        )

        state["human_review_decision"] = result.get(
            "decision"
        )
        state["reviewer_note"] = result.get(
            "reviewer_note"
        )
        state["edited_code"] = result.get(
            "edited_code"
        )

        state["human_review_count"] = (
            state.get("human_review_count", 0) + 1
        )

        return state

    except Exception as exc:
        return _add_error(state, exc)


def node_execute(state: TestRunState) -> TestRunState:
    try:
        from execution.runner import run_execute

        result = run_execute(
            state["generated_test_files"]
        )

        state["execution_result"] = result

        return state

    except Exception as exc:
        return _add_error(state, exc)


def node_analyze(state: TestRunState) -> TestRunState:
    try:
        from agents.analyzer import run_analyzer

        result = run_analyzer(
            state["execution_result"],
            state["execution_evidence"],
            state["test_request"],
        )

        state["failure_analysis"] = result
        state["failure_type"] = result["failure_type"]

        return state

    except Exception as exc:
        return _add_error(state, exc)


def node_fix_proposal(state: TestRunState) -> TestRunState:
    try:
        from agents.fix_proposal import run_fix_proposal

        result = run_fix_proposal(
            state["failure_analysis"],
            state["generated_test_files"],
        )

        state["fix_proposal"] = result

        return state

    except Exception as exc:
        return _add_error(state, exc)


def node_apply_fix(state: TestRunState) -> TestRunState:
    try:
        from healing.apply_fix import run_apply_fix

        result = run_apply_fix(
            state["fix_proposal"],
            state["generated_test_files"],
        )

        state["generated_test_files"] = result.get(
            "generated_test_files",
            state["generated_test_files"],
        )

        state["healing_retry_count"] = (
            state.get("healing_retry_count", 0) + 1
        )

        return state

    except Exception as exc:
        return _add_error(state, exc)


def node_report(state: TestRunState) -> TestRunState:
    try:
        from report.exporters import run_report

        update = run_report(state)
        state.update(update)
        return state

    except Exception as exc:
        return _add_error(state, exc)