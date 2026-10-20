"""
Purpose: Thin LangGraph node wrappers.

Reads: TestRunState
Writes: Partial TestRunState updates

Must not:
- Perform routing decisions.
- Contain agent logic.
- Bypass Human Fix Approval.
"""

from uuid import uuid4

from langchain_core.runnables import RunnableConfig

from agents.codegen import run_codegen
from agents.fix_proposal import (
    read_failed_spec_code,
    run_fix_proposal,
)

from graph.state import TestRunState

from llm.client import CodegenLLMBackend
from llm.settings import model_factory_for

from llm.errors import (
    LLMUnavailableError,
    BudgetExceededError,
    LLM_FATAL_TAG,
    redact,
)

from execution.mock_runner import mock_run_execute

from analysis.mock_failure import (
    mock_analyze,
    mock_propose_fix,
)

from healing.mock_fix_approval import mock_fix_approval_node
from healing.mock_apply_fix import mock_apply_fix


# =========================================================
# 1. INTAKE
# =========================================================

def intake_node(state: TestRunState) -> dict:
    request = state.get("test_request") or {}

    url = request.get("url")
    requirements = request.get("requirements")

    if not url or not requirements:
        return {
            "terminal_status": "BLOCKED",
            "errors": [
                *(state.get("errors") or []),
                "URL and requirements are required.",
            ],
        }

    return {
        "run_id": state.get("run_id") or str(uuid4()),
        "target_url": url,
        "errors": state.get("errors") or [],
    }


# =========================================================
# 2. PLANNER
# =========================================================

def planner_node(state: TestRunState) -> dict:
    from agents.planner import generate_plan

    scenarios = generate_plan(
        request=state["test_request"],
        sandbox_mode=state.get("sandbox_mode", False),
    )

    return {
        "test_plan": scenarios,
    }


# =========================================================
# 3. CODEGEN
# =========================================================

def codegen_node(
    state: TestRunState,
    config: RunnableConfig | None = None,
) -> dict:

    # Sandbox mode
    if state.get("sandbox_mode", False):
        from llm.mock_codegen_backend import MockCodegenBackend

        return run_codegen(
            state,
            backend=MockCodegenBackend(),
        )

    # Real LLM mode
    request = state.get("test_request") or {}

    model = request.get("codegen_model")

    if not model:
        raise ValueError(
            "No codegen model selected; configure one in Settings."
        )

    thread_id = (
        ((config or {}).get("configurable") or {})
        .get("thread_id")
    )

    backend = CodegenLLMBackend(
        model,
        request.get("fallback_model"),
        model_factory=model_factory_for(thread_id),
    )

    return run_codegen(
        state,
        backend=backend,
    )


# =========================================================
# 4. VALIDATE
# =========================================================

def validate_node(state: TestRunState) -> dict:

    if state.get("sandbox_mode", False):
        return {
            "validation_status": "valid",
            "validation_errors": [],
        }

    from validation.validator import validate_all

    return validate_all(state)


# =========================================================
# 5. EXECUTE
# =========================================================

def execute_node(state: TestRunState) -> dict:

    if state.get("sandbox_mode", False):
        return mock_run_execute(state)

    raise NotImplementedError(
        "Real execution runner is not connected yet."
    )


# =========================================================
# 6. FAILURE ANALYZER
# =========================================================

def analyze_node(state: TestRunState) -> dict:

    if state.get("sandbox_mode", False):
        return mock_analyze(state)

    raise NotImplementedError(
        "Real Analyzer is not connected yet."
    )


# =========================================================
# 7. FIX PROPOSAL
# =========================================================

def fix_proposal_node(
    state: TestRunState,
    config: RunnableConfig | None = None,
) -> dict:

    # Preserve Sandbox behavior
    if state.get("sandbox_mode", False):
        return mock_propose_fix(state)

    try:
        # Selected model from Gradio Settings
        request = state.get("test_request") or {}

        model = request.get("codegen_model")

        if not model:
            raise ValueError(
                "No model selected for Fix Proposal."
            )

        # Get the current LangGraph thread
        thread_id = (
            ((config or {}).get("configurable") or {})
            .get("thread_id")
        )

        if not thread_id:
            raise ValueError(
                "Missing LangGraph thread_id."
            )

        # Read the failed Playwright spec safely
        spec_code, spec_filename = read_failed_spec_code(
            state
        )

        # Call the real Fix Proposal LLM
        return run_fix_proposal(
            state,
            spec_code=spec_code,
            spec_filename=spec_filename,
            model=model,
            model_factory=model_factory_for(thread_id),
        )

    except (
        LLMUnavailableError,
        BudgetExceededError,
    ) as exc:

        return {
            "errors": [
                *(state.get("errors") or []),
                f"{LLM_FATAL_TAG}[fix_proposal]: "
                f"{redact(str(exc))}",
            ],
            "terminal_status": "ERROR",
        }

    except Exception as exc:

        return {
            "errors": [
                *(state.get("errors") or []),
                f"fix_proposal: {redact(str(exc))}",
            ],
            "terminal_status": "ERROR",
        }


# =========================================================
# 8. HUMAN FIX APPROVAL
# =========================================================

def fix_approval_node(state: TestRunState) -> dict:
    """
    Uses LangGraph interrupt() to request human approval.

    Despite the helper's name, mock_fix_approval_node
    implements the actual interrupt/resume mechanism.
    """

    return mock_fix_approval_node(state)


# =========================================================
# 9. APPLY FIX
# =========================================================

def apply_fix_node(state: TestRunState) -> dict:

    if state.get("sandbox_mode", False):
        return mock_apply_fix(state)

    raise NotImplementedError(
        "Real Apply Fix is not connected yet."
    )


# =========================================================
# 10. REPORT - P5 INTEGRATION
# =========================================================

def report_node(state: TestRunState) -> dict:
    """
    Generate the final report using P5's implementation.

    The report must not modify test results or apply fixes.
    """

    from report.exporters import run_report

    return run_report(state)