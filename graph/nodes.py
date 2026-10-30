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
from graph.state import TestRunState, is_mock_mode
from llm.client import CodegenLLMBackend
from llm.settings import model_factory_for

from llm.errors import (
    LLMUnavailableError,
    BudgetExceededError,
    LLM_FATAL_TAG,
    redact,
)

from execution.mock_runner import mock_run_execute
from execution.runner import run_execute


from agents.analyzer import run_analyzer

from analysis.mock_failure import (
    mock_analyze,
    mock_propose_fix,
)

from healing.mock_fix_approval import mock_fix_approval_node
from healing.mock_apply_fix import mock_apply_fix


# =========================================================
# 1. INTAKE
# =========================================================

def _blocked(state: TestRunState, message: str) -> dict:
    return {
        "terminal_status": "BLOCKED",
        "errors": [*(state.get("errors") or []), message],
    }


def intake_node(state: TestRunState) -> dict:
    from intake.safety import is_safe_url
    from intake.url_resolver import resolve_url

    request = state.get("test_request") or {}
    requirements = (request.get("requirements") or "").strip()

    if not requirements:
        return _blocked(state, "URL and requirements are required.")

    url, source = resolve_url(request)

    if not url:
        return _blocked(state, source)

    if not is_mock_mode(state):
        if request.get("authorization") is not True:
            return _blocked(
                state,
                "BLOCKED: authorization to test this site was not confirmed.",
            )

        safe, reason = is_safe_url(url)

        if not safe:
            return _blocked(state, reason)

        if not request.get("codegen_model"):
            return {
                "terminal_status": "ERROR",
                "errors": [
                    *(state.get("errors") or []),
                    "No usable model selected; configure one in Settings.",
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

def _crash(state: TestRunState, node: str, exc: Exception) -> dict:
    fatal = isinstance(exc, (LLMUnavailableError, BudgetExceededError))
    tag = f"{LLM_FATAL_TAG}[{node}]: " if fatal else f"{node}: "
    return {
        "errors": [*(state.get("errors") or []), f"{tag}{redact(str(exc))}"],
        "terminal_status": "ERROR",
    }


def planner_node(
    state: TestRunState,
    config: RunnableConfig | None = None,
) -> dict:
    from agents.planner import generate_plan

    request = state["test_request"]

    if is_mock_mode(state):
        return {"test_plan": generate_plan(request=request, mock_mode=True)}

    try:
        model = request.get("planner_model") or request.get("codegen_model")

        if not model:
            raise ValueError("No planner model selected; configure one in Settings.")

        thread_id = ((config or {}).get("configurable") or {}).get("thread_id")

        scenarios = generate_plan(
            request=request,
            mock_mode=False,
            model=model,
            model_factory=model_factory_for(thread_id),
            target_url=state.get("target_url"),
        )
    except Exception as exc:
        return _crash(state, "planner", exc)

    return {
        "test_plan": scenarios,
        "models_used": {**(state.get("models_used") or {}), "planner": model},
    }


# =========================================================
# 3. CODEGEN
# =========================================================

def codegen_node(
    state: TestRunState,
    config: RunnableConfig | None = None,
) -> dict:
    if is_mock_mode(state):
        from llm.mock_codegen_backend import MockCodegenBackend

        return run_codegen(
            state,
            backend=MockCodegenBackend(),
        )

    # Real LLM mode
    try:
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
    except Exception as exc:
        return _crash(state, "codegen", exc)

    return run_codegen(
        state,
        backend=backend,
    )


# =========================================================
# 4. VALIDATE
# =========================================================

def validate_node(state: TestRunState) -> dict:
    if is_mock_mode(state):
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
    if is_mock_mode(state):
        return mock_run_execute(state)
    return run_execute(state)


# =========================================================
# 6. FAILURE ANALYZER
# =========================================================

def analyze_node(
    state: TestRunState,
    config: RunnableConfig | None = None,
) -> dict:

    if is_mock_mode(state):
        return mock_analyze(state)

    try:
        # Selected model from Gradio Settings
        request = state.get("test_request") or {}

        model = request.get("codegen_model")

        if not model:
            raise ValueError(
                "No model selected for Failure Analyzer."
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

        # Call the real Failure Analyzer LLM
        return run_analyzer(
            state,
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
                f"{LLM_FATAL_TAG}[analyzer]: "
                f"{redact(str(exc))}",
            ],
            "terminal_status": "ERROR",
        }

    except Exception as exc:

        return {
            "errors": [
                *(state.get("errors") or []),
                f"analyzer: {redact(str(exc))}",
            ],
            "terminal_status": "ERROR",
        }


# =========================================================
# 7. FIX PROPOSAL
# =========================================================

def fix_proposal_node(
    state: TestRunState,
    config: RunnableConfig | None = None,
) -> dict:

    if is_mock_mode(state):
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
    Non-risky fixes are applied automatically only when the request sets
    auto_heal_mode="auto"; everything else pauses for a human decision via
    LangGraph interrupt() (implemented in mock_fix_approval_node).
    """

    proposal = state.get("fix_proposal") or {}
    request = state.get("test_request") or {}

    if (
        not is_mock_mode(state)
        and request.get("auto_heal_mode") == "auto"
        and proposal.get("risky") is False
    ):
        return {"approval_decision": "auto"}

    return mock_fix_approval_node(state)


# =========================================================
# 9. APPLY FIX
# =========================================================

def apply_fix_node(state: TestRunState) -> dict:
    if is_mock_mode(state):
        return mock_apply_fix(state)

    from healing.apply_fix import run_apply_fix

    try:
        return run_apply_fix(state)
    except Exception as exc:
        return _crash(state, "apply_fix", exc)


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