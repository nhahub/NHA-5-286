"""
Purpose: Deterministic routing functions for LangGraph orchestration.
Reads: TestRunState
Writes: N/A (pure routing functions returning target node names)
Must not: mutate state, make LLM calls, or guess ambiguous routing outcomes
"""
from __future__ import annotations

from typing import Any

from llm.errors import has_fatal_llm_error
from .state import TestRunState


def route_after_intake(state: TestRunState) -> str:
    """Route to planner if target URL is resolved; otherwise route directly to report."""
    target = state.get("target_url")
    # target_url may be a tuple (url, source) or string or dict
    if isinstance(target, (tuple, list)) and len(target) >= 1:
        has_url = bool(target[0])
    elif isinstance(target, dict):
        has_url = bool(target.get("url"))
    else:
        has_url = bool(target)

    if not has_url or state.get("errors") or has_fatal_llm_error(state.get("errors", [])):
        return "report"
    return "planner"


def route_after_validate(state: TestRunState) -> str:
    """Route after code validation: execute if valid; retry codegen (max 2 retries);
    human review if enabled; or report when retries exhausted or all scenarios blocked."""
    if has_fatal_llm_error(state.get("errors", [])):
        return "report"

    # All scenarios blocked: nothing to execute or generate
    plan = state.get("test_plan") or []
    if plan and all(str(s.get("status", "")).upper().startswith("BLOCKED") for s in plan):
        return "report"

    status = state.get("validation_status")
    if status == "valid":
        # Only execute if generated test files exist
        if not state.get("generated_test_files"):
            return "report"
        return "execute"

    if status == "error" or status != "invalid":
        return "report"

    # Bounded retries: max 2 retries (retry_count 0 and 1 -> codegen)
    retry_count = int(state.get("generation_retry_count") or 0)
    if retry_count < 2:
        return "codegen"

    if state.get("human_review_mode", False):
        return "human_code_review"

    return "report"


def route_after_execute(state: TestRunState) -> str:
    """Route to analyzer on any test failure; otherwise route directly to report."""
    if has_fatal_llm_error(state.get("errors", [])):
        return "report"

    result = state.get("execution_result")
    if not result:
        return "report"

    # Check Playwright reporter JSON stats
    stats = result.get("stats") if isinstance(result, dict) else None
    if isinstance(stats, dict) and stats.get("unexpected", 0) > 0:
        return "analyze"

    status = str(result.get("status", "")).lower() if isinstance(result, dict) else ""
    if status in {"failed", "fail"}:
        return "analyze"

    return "report"


def route_after_analyze(state: TestRunState) -> str:
    """Route to fix proposal only for healable 'Test' failures with adequate confidence.
    Prevent healing if failure class is not 'Test', confidence is 'low', or max 2 healing attempts reached."""
    if has_fatal_llm_error(state.get("errors", [])):
        return "report"

    if state.get("failure_type") != "Test":
        return "report"

    analysis = state.get("failure_analysis")
    confidence = (
        analysis.get("confidence")
        if isinstance(analysis, dict)
        else getattr(analysis, "confidence", None)
    )
    if str(confidence).lower() == "low":
        return "report"

    healing_retries = state.get("healing_retry_count", 0)
    if isinstance(healing_retries, dict):
        if max(healing_retries.values(), default=0) >= 2:
            return "report"
    elif int(healing_retries or 0) >= 2:
        return "report"

    return "fix_proposal"


def route_after_fix_proposal(state: TestRunState) -> str:
    """Route to apply_fix if approved or auto-approved (and not low confidence / risky)."""
    if has_fatal_llm_error(state.get("errors", [])):
        return "report"

    approval = state.get("approval_decision")
    if approval == "approved":
        return "apply_fix"

    if approval == "auto":
        # Low confidence prevents automatic healing
        analysis = state.get("failure_analysis")
        confidence = (
            analysis.get("confidence")
            if isinstance(analysis, dict)
            else getattr(analysis, "confidence", None)
        )
        if str(confidence).lower() == "low":
            return "report"

        # Risky patches (e.g. assertion changes) require human approval and cannot auto-heal
        proposal = state.get("fix_proposal")
        risky = (
            proposal.get("risky")
            if isinstance(proposal, dict)
            else getattr(proposal, "risky", False)
        )
        if risky:
            return "report"

        return "apply_fix"

    return "report"


def route_after_apply_fix(state: TestRunState) -> str:
    """After a patch is applied, always validate compiler / lint correctness."""
    return "validate"
