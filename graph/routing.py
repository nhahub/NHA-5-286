"""
Purpose: Deterministic routing functions for LangGraph orchestration.

Reads: TestRunState
Writes: N/A

Must not:
- Mutate state.
- Make LLM calls.
- Apply patches.
- Bypass Human Fix Approval.
"""

from __future__ import annotations

from llm.errors import has_fatal_llm_error
from graph.state import TestRunState


# =========================================================
# Shared safety helpers
# =========================================================

def _is_terminal_error(state: TestRunState) -> bool:
    """Stop routing when the run is blocked or has a fatal error."""

    if state.get("terminal_status") in ("ERROR", "BLOCKED"):
        return True

    return has_fatal_llm_error(state.get("errors") or [])


def _healing_limit_reached(state: TestRunState) -> bool:
    """Enforce a maximum of two healing attempts."""

    retries = state.get("healing_retry_count") or 0

    if isinstance(retries, dict):
        analysis = state.get("failure_analysis") or {}

        if isinstance(analysis, dict):
            scenario_id = analysis.get("scenario_id")

            if scenario_id and scenario_id in retries:
                return int(retries[scenario_id]) >= 2

        # Conservative fallback when a failed scenario
        # cannot be identified unambiguously.
        return max(retries.values(), default=0) >= 2

    return int(retries) >= 2


# =========================================================
# 1. Intake -> Planner / Report
# =========================================================

def route_after_intake(state: TestRunState) -> str:

    if _is_terminal_error(state):
        return "report"

    if state.get("errors"):
        return "report"

    target = state.get("target_url")

    if isinstance(target, dict):
        has_url = bool(target.get("url"))

    elif isinstance(target, (tuple, list)):
        has_url = bool(target[0]) if target else False

    else:
        has_url = bool(target)

    if not has_url:
        return "report"

    return "planner"


# =========================================================
# 2. Validate -> Execute / Report
# =========================================================

def route_after_validate(state: TestRunState) -> str:

    if _is_terminal_error(state):
        return "report"

    status = state.get("validation_status")

    # Invalid generated code may be regenerated,
    # but retries must be bounded.
    if status == "invalid":
        retries = int(state.get("generation_retry_count") or 0)

        if retries < 2:
            return "codegen"

        # Human Code Review is not implemented yet.
        return "report"

    if status != "valid":
        return "report"

    # Do not execute when all planned scenarios are blocked.
    test_plan = state.get("test_plan")

    if isinstance(test_plan, list) and test_plan:
        all_blocked = all(
            isinstance(scenario, dict)
            and str(scenario.get("status", ""))
            .strip()
            .upper()
            .startswith("BLOCKED")
            for scenario in test_plan
        )

        if all_blocked:
            return "report"

    # Do not execute without generated test files.
    generated_files = state.get("generated_test_files")

    if not generated_files:
        return "report"

    return "execute"
# =========================================================
# 3. Execute -> Analyze / Report
# =========================================================

def route_after_execute(state: TestRunState) -> str:

    if _is_terminal_error(state):
        return "report"

    # Preserve existing Sandbox behavior.
    if state.get("sandbox_mode", False):

        status = state.get("terminal_status")

        if status == "FAIL":
            return "analyze"

        return "report"

    # Real Playwright execution
    result = state.get("execution_result")

    if isinstance(result, dict):

        stats = result.get("stats")

        if isinstance(stats, dict):
            if stats.get("unexpected", 0) > 0:
                return "analyze"

        status = str(result.get("status") or "").lower()

        if status in ("fail", "failed", "failure"):
            return "analyze"

        if status in ("pass", "passed", "success"):
            return "report"

    return "report"


# =========================================================
# 4. Analyze -> Fix Proposal / Report
# =========================================================

def route_after_analyze(state: TestRunState) -> str:

    # Stop after terminal errors.
    if _is_terminal_error(state):
        return "report"

    # Only test-code failures can be healed.
    if state.get("failure_type") != "Test":
        return "report"

    # Maximum two healing attempts.
    if _healing_limit_reached(state):
        return "report"

    # Preserve the working Sandbox behavior.
    if state.get("sandbox_mode", False):
        return "fix_proposal"

    # Real Analyzer output.
    analysis = state.get("failure_analysis")

    if not isinstance(analysis, dict):
        return "report"

    if analysis.get("failure_type") != "Test":
        return "report"

    if analysis.get("fix_required") is not True:
        return "report"

    # Only high-confidence analysis may reach the healer.
    if analysis.get("confidence", "low") != "high":
        return "report"

    return "fix_proposal"


# =========================================================
# 5. Fix Proposal -> Human Approval / Report
# =========================================================

def route_after_fix_proposal(state: TestRunState) -> str:

    if _is_terminal_error(state):
        return "report"

    proposal = state.get("fix_proposal")

    if not isinstance(proposal, dict):
        return "report"

    patch_diff = proposal.get("patch_diff")

    if not isinstance(patch_diff, str):
        return "report"

    if not patch_diff.strip():
        return "report"

    # Every generated patch must go through Human Approval.
    return "fix_approval"


# =========================================================
# 6. Human Approval -> Apply Fix / Report
# =========================================================

def route_after_fix_approval(state: TestRunState) -> str:

    if _is_terminal_error(state):
        return "report"

    proposal = state.get("fix_proposal")

    if not isinstance(proposal, dict):
        return "report"

    patch_diff = proposal.get("patch_diff")

    if not isinstance(patch_diff, str):
        return "report"

    if not patch_diff.strip():
        return "report"

    # Explicit human approval is mandatory.
    # Rejected, missing, or "auto" decisions cannot proceed.
    if state.get("approval_decision") != "approved":
        return "report"

    return "apply_fix"


# =========================================================
# 7. Apply Fix -> Validate / Report
# =========================================================

def route_after_apply_fix(state: TestRunState) -> str:

    if _is_terminal_error(state):
        return "report"

    # Sandbox needs an explicit indication
    # that the mock fix was applied successfully.
    if state.get("sandbox_mode", False):

        if state.get("mock_fix_applied"):
            return "validate"

        return "report"

    # Real Apply Fix must return an error/terminal status
    # when patch application fails.
    # This needs an integration test once implemented.
    return "validate"