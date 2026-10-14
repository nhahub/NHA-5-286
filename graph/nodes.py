"""
Purpose: Thin LangGraph node wrappers that delegate to service and agent functions; all exception catching goes here.
Reads: TestRunState
Writes: TestRunState
Must not: perform routing decisions (routing lives in routing.py) or contain agent logic
"""


from uuid import uuid4
from graph.state import TestRunState


def intake_node(state: TestRunState) -> dict:
    request = state.get("test_request") or {}

    url = request.get("url")
    requirements = request.get("requirements")

    if not url or not requirements:
        return {
            "terminal_status": "BLOCKED",
            "errors": [
                *state.get("errors", []),
                "URL and requirements are required.",
            ],
        }

    return {
        "run_id": state.get("run_id") or str(uuid4()),
        "target_url": url,
        "errors": state.get("errors", []),
    }


def planner_node(state: TestRunState) -> dict:
    from agents.planner import generate_plan

    scenarios = generate_plan(
        request=state["test_request"],
        sandbox_mode=state.get("sandbox_mode", False),
    )

    return {"test_plan": scenarios}


def codegen_node(state: TestRunState) -> dict:
    from agents.codegen import run_codegen

    if state.get("sandbox_mode", False):
        from llm.mock_codegen_backend import MockCodegenBackend

        return run_codegen(
            state,
            backend=MockCodegenBackend(),
        )

    raise NotImplementedError(
        "Real CodeGen backend is not connected yet."
    )


def validate_node(state: TestRunState) -> dict:
    if state.get("sandbox_mode", False):
        return {
            "validation_status": "valid",
            "validation_errors": [],
        }

    from validation.validator import validate_all

    return validate_all(state)


def execute_node(state: TestRunState) -> dict:
    if state.get("sandbox_mode", False):
        from execution.mock_runner import mock_run_execute

        return mock_run_execute(state)

    raise NotImplementedError(
        "Real execution runner is not connected yet."
    )


def analyze_node(state: TestRunState) -> dict:
    if state.get("sandbox_mode", False):
        from analysis.mock_failure import mock_analyze

        return mock_analyze(state)

    raise NotImplementedError(
        "Real Analyzer is not connected yet."
    )


def fix_proposal_node(state: TestRunState) -> dict:
    if state.get("sandbox_mode", False):
        from analysis.mock_failure import mock_propose_fix

        return mock_propose_fix(state)

    raise NotImplementedError(
        "Real Fix Proposal is not connected yet."
    )


def fix_approval_node(state: TestRunState) -> dict:
    from healing.mock_fix_approval import mock_fix_approval_node

    return mock_fix_approval_node(state)


def apply_fix_node(state: TestRunState) -> dict:
    if state.get("sandbox_mode", False):
        from healing.mock_apply_fix import mock_apply_fix

        return mock_apply_fix(state)

    raise NotImplementedError(
        "Real Apply Fix is not connected yet."
    )


def report_node(state: TestRunState) -> dict:
    return {
        "terminal_status": state.get("terminal_status") or "ERROR"
    }



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


