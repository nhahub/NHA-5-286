"""
Purpose: Focused unit tests for graph/ package — state shape, deterministic routing,
         retry bounds, low confidence healing prevention, and graph compilation.
"""
from __future__ import annotations
import pytest
from graph.build_graph import build_graph
from graph.routing import (
    route_after_analyze,
    route_after_apply_fix,
    route_after_execute,
    route_after_fix_proposal,
    route_after_intake,
    route_after_validate,
    route_after_fix_approval
)
from graph.state import TestRunState

EXPECTED_STATE_KEYS = {
    "run_id",
    "test_request",
    "target_url",
    "test_plan",
    "generated_test_files",
    "validation_status",
    "validation_errors",
    "generation_retry_count",
    "human_review_decision",
    "human_review_count",
    "reviewer_note",
    "edited_code",
    "execution_result",
    "execution_evidence",
    "failure_analysis",
    "failure_type",
    "fix_proposal",
    "approval_decision",
    "healing_retry_count",
    "models_used",
    "terminal_status",
    "errors",
    "report_path",
    "mock_mode",
    "sandbox_mode",
    "mock_fix_applied",
    "mock_execution_outcome",
    "mock_risky",
    "mock_fixes_needed",
}


# ---------------------------------------------------------------------------
# State shape
# ---------------------------------------------------------------------------

def test_test_run_state_has_all_required_keys() -> None:
    # TestRunState is a TypedDict; verify its declared annotations cover every spec key.
    declared = set(TestRunState.__annotations__.keys())
    missing = EXPECTED_STATE_KEYS - declared
    assert not missing, f"TestRunState missing fields: {missing}"
    assert len(declared) == 31  # 29 spec fields + the optional fix_rejection and applied_patches


# ---------------------------------------------------------------------------
# Routing after intake
# ---------------------------------------------------------------------------

def test_route_after_intake_no_url_returns_report() -> None:
    assert route_after_intake({"target_url": None}) == "report"
    assert route_after_intake({"target_url": (None, "BLOCKED: missing")}) == "report"


def test_route_after_intake_valid_returns_planner() -> None:
    assert route_after_intake({"target_url": "https://example.com"}) == "planner"
    assert route_after_intake({"target_url": ("https://example.com", "field")}) == "planner"


def test_route_after_intake_errors_returns_report() -> None:
    assert route_after_intake({"target_url": "https://example.com", "errors": ["intake: SSRF blocked"]}) == "report"


def test_route_after_intake_fatal_llm_error_returns_report() -> None:
    assert route_after_intake({
        "target_url": "https://example.com",
        "errors": ["llm-fatal[intake]: no models available"],
    }) == "report"


# ---------------------------------------------------------------------------
# Routing after validate
# ---------------------------------------------------------------------------

def test_route_after_validate_valid_returns_execute() -> None:
    state = {
        "validation_status": "valid",
        "generated_test_files": ["runs/r1/tests/s1.spec.ts"],
    }
    assert route_after_validate(state) == "execute"


def test_route_after_validate_invalid_first_retry_returns_codegen() -> None:
    state = {
        "validation_status": "invalid",
        "generation_retry_count": 0,
        "generated_test_files": ["runs/r1/tests/s1.spec.ts"],
    }
    assert route_after_validate(state) == "codegen"


def test_route_after_validate_invalid_second_retry_returns_codegen() -> None:
    state = {
        "validation_status": "invalid",
        "generation_retry_count": 1,
        "generated_test_files": ["runs/r1/tests/s1.spec.ts"],
    }
    assert route_after_validate(state) == "codegen"


@pytest.mark.xfail(
    reason="Human Code Review node is not implemented yet",
    strict=True,
)
def test_route_after_validate_invalid_after_2_retries_human_review_on() -> None:
    state = {
        "validation_status": "invalid",
        "generation_retry_count": 2,
        "human_review_mode": True,
        "generated_test_files": ["runs/r1/tests/s1.spec.ts"],
    }
    assert route_after_validate(state) == "human_code_review"


def test_route_after_validate_invalid_after_2_retries_human_review_off() -> None:
    state = {
        "validation_status": "invalid",
        "generation_retry_count": 2,
        "human_review_mode": False,
        "generated_test_files": ["runs/r1/tests/s1.spec.ts"],
    }
    assert route_after_validate(state) == "report"


def test_route_after_validate_all_scenarios_blocked_returns_report() -> None:
    state = {
        "test_plan": [
            {"id": "s1", "name": "Scenario 1", "status": "BLOCKED: missing auth"},
            {"id": "s2", "name": "Scenario 2", "status": "BLOCKED: captcha"},
        ],
        "validation_status": "valid",
    }
    assert route_after_validate(state) == "report"


def test_route_after_validate_no_generated_files_returns_report() -> None:
    state = {
        "validation_status": "valid",
        "generated_test_files": [],
    }
    assert route_after_validate(state) == "report"


# ---------------------------------------------------------------------------
# Routing after execute
# ---------------------------------------------------------------------------

def test_route_after_execute_all_passed_returns_report() -> None:
    state = {
        "execution_result": {
            "stats": {"expected": 3, "unexpected": 0},
            "status": "passed",
        }
    }
    assert route_after_execute(state) == "report"


def test_route_after_execute_any_failure_returns_analyze() -> None:
    state = {
        "execution_result": {
            "stats": {"expected": 2, "unexpected": 1},
            "status": "failed",
        }
    }
    assert route_after_execute(state) == "analyze"


def test_route_after_execute_no_result_returns_report() -> None:
    assert route_after_execute({}) == "report"


# ---------------------------------------------------------------------------
# Routing after analyze (healing rules & low confidence prevention)
# ---------------------------------------------------------------------------

def test_route_after_analyze_test_class_healable_returns_fix_proposal() -> None:
    state = {
        "failure_type": "Test",
        "healing_retry_count": 0,
        "failure_analysis": {
            "failure_type": "Test",
            "fix_required": True,
            "confidence": "high",
        },
    }

    assert route_after_analyze(state) == "fix_proposal"


def test_route_after_analyze_environment_class_returns_report() -> None:
    state = {
        "failure_type": "Environment",
        "healing_retry_count": 0,
        "failure_analysis": {"confidence": "high"},
    }
    assert route_after_analyze(state) == "report"


def test_route_after_analyze_application_class_returns_report() -> None:
    state = {
        "failure_type": "Application",
        "healing_retry_count": 0,
        "failure_analysis": {"confidence": "high"},
    }
    assert route_after_analyze(state) == "report"


def test_route_after_analyze_low_confidence_prevents_healing() -> None:
    state = {
        "failure_type": "Test",
        "healing_retry_count": 0,
        "failure_analysis": {"confidence": "low"},
    }
    assert route_after_analyze(state) == "report"


def test_route_after_analyze_max_healing_retries_returns_report() -> None:
    state = {
        "failure_type": "Test",
        "healing_retry_count": 2,
        "failure_analysis": {"confidence": "high"},
    }
    assert route_after_analyze(state) == "report"


def test_route_after_analyze_per_scenario_healing_cap_returns_report() -> None:
    state = {
        "failure_type": "Test",
        "healing_retry_count": {"s1": 2},
        "failure_analysis": {"confidence": "high"},
    }
    assert route_after_analyze(state) == "report"


# ---------------------------------------------------------------------------
# Routing after fix proposal
# ---------------------------------------------------------------------------

def test_route_after_fix_proposal_valid_patch_requires_human_approval() -> None:
    state = {
        "fix_proposal": {"patch_diff": "example patch diff"},
    }
    assert route_after_fix_proposal(state) == "fix_approval"


def test_route_after_fix_proposal_existing_approval_cannot_skip_review() -> None:
    state = {
        "approval_decision": "approved",
        "fix_proposal": {"patch_diff": "example patch diff"},
    }
    assert route_after_fix_proposal(state) == "fix_approval"


def test_route_after_fix_proposal_auto_high_confidence_requires_approval() -> None:
    state = {
        "approval_decision": "auto",
        "fix_proposal": {
            "patch_diff": "example patch diff",
            "risky": False,
        },
        "failure_analysis": {"confidence": "high"},
    }
    assert route_after_fix_proposal(state) == "fix_approval"


def test_route_after_fix_proposal_missing_patch_returns_report() -> None:
    state = {
        "fix_proposal": {},
    }
    assert route_after_fix_proposal(state) == "report"


def test_route_after_fix_proposal_empty_patch_returns_report() -> None:
    state = {
        "fix_proposal": {"patch_diff": "   "},
    }
    assert route_after_fix_proposal(state) == "report"

# ---------------------------------------------------------------------------
# Routing after Human Fix Approval
# ---------------------------------------------------------------------------

def test_route_after_fix_approval_approved_applies_fix() -> None:
    state = {
        "approval_decision": "approved",
        "fix_proposal": {"patch_diff": "example patch diff"},
    }
    assert route_after_fix_approval(state) == "apply_fix"


def test_route_after_fix_approval_rejected_returns_report() -> None:
    state = {
        "approval_decision": "rejected",
        "fix_proposal": {"patch_diff": "example patch diff"},
    }
    assert route_after_fix_approval(state) == "report"


def test_route_after_fix_approval_auto_returns_report() -> None:
    state = {
        "approval_decision": "auto",
        "fix_proposal": {"patch_diff": "example patch diff"},
    }
    assert route_after_fix_approval(state) == "report"


def test_route_after_fix_approval_missing_patch_returns_report() -> None:
    state = {
        "approval_decision": "approved",
        "fix_proposal": {},
    }
    assert route_after_fix_approval(state) == "report"

# ---------------------------------------------------------------------------
# Routing after apply fix
# ---------------------------------------------------------------------------

def test_route_after_apply_fix_always_returns_validate() -> None:
    assert route_after_apply_fix({}) == "validate"


# ---------------------------------------------------------------------------
# Graph compilation & structure
# ---------------------------------------------------------------------------

def test_build_graph_compiles_without_error() -> None:
    compiled = build_graph()
    assert compiled is not None


def test_graph_has_all_ten_nodes() -> None:
    compiled = build_graph()
    expected_nodes = {
        "intake",
        "planner",
        "codegen",
        "validate",
        "fix_approval",
        "execute",
        "analyze",
        "fix_proposal",
        "apply_fix",
        "report",
    }
    assert expected_nodes.issubset(set(compiled.nodes.keys()))
