"""
Purpose: TestRunState TypedDict — the single shared state object
passed through every LangGraph node.

Reads: N/A (type definition only)
Writes: N/A (type definition only)
Must not: contain business logic.
"""

from __future__ import annotations

from typing import TypedDict


class TestRunState(TypedDict):
    # =====================================================
    # 1. Run Information
    # =====================================================

    run_id: str
    test_request: dict
    target_url: str | None

    # =====================================================
    # 2. Planning
    # =====================================================

    test_plan: list[dict]

    # =====================================================
    # 3. Code Generation & Validation
    # =====================================================

    generated_test_files: list[str]

    validation_status: str | None
    validation_errors: list[str]

    generation_retry_count: int

    # =====================================================
    # 4. Human Code Review
    # =====================================================

    human_review_decision: str | None
    human_review_count: int

    reviewer_note: str | None
    edited_code: str | None

    # =====================================================
    # 5. Execution
    # =====================================================

    execution_result: dict | None
    execution_evidence: list[dict]

    # =====================================================
    # 6. Failure Analysis
    # =====================================================

    failure_analysis: dict | None
    failure_type: str | None

    # =====================================================
    # 7. Fix Proposal & Human Fix Approval
    # =====================================================

    fix_proposal: dict | None

    # "approved" | "rejected" | None
    approval_decision: str | None

    # Supports a single counter or per-scenario counters.
    healing_retry_count: int | dict[str, int]

    # =====================================================
    # 8. Models
    # =====================================================

    models_used: dict[str, str]

    # =====================================================
    # 9. Final Report
    # =====================================================

    terminal_status: str | None
    errors: list[str]
    report_path: str | None

    # =====================================================
    # 10. Sandbox Mode
    # =====================================================

    sandbox_mode: bool

    mock_fix_applied: bool
    mock_execution_outcome: str
    mock_risky: bool
    mock_fixes_needed: int