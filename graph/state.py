"""
Purpose: TestRunState TypedDict — the single shared state object passed through every LangGraph node.
Reads: N/A (type definition only)
Writes: N/A (type definition only)
Must not: contain business logic
"""

# All field names taken verbatim from the spec (§4 Shared State):
#
# class TestRunState(TypedDict):
#     run_id: str                          # unique run id; names runs/<run_id>/ folder
#     test_request: dict                   # TestRequest model as dict
#     target_url: str | None               # resolved URL with source annotation
#     test_plan: list[dict]                # list of Scenario dicts from the Planner
#     generated_test_files: list[str]      # paths of the .spec.ts files
#     validation_status: str | None        # "valid" | "invalid" | None
#     validation_errors: list[str]         # compiler / API errors from the validator
#     generation_retry_count: int          # regeneration attempts, max 2
#     human_review_decision: str | None    # "edit_and_resubmit" | "regenerate_with_note" | "skip_scenario" | "reject" | None
#     human_review_count: int              # review rounds per scenario, max 2
#     reviewer_note: str | None            # note written by the reviewer for codegen
#     edited_code: str | None             # code edited by the reviewer
#     execution_result: dict | None        # raw Playwright JSON reporter output
#     execution_evidence: list[dict]       # list of normalised Evidence dicts
#     failure_analysis: dict | None        # FailureAnalysis dict from the Analyzer
#     failure_type: str | None             # validated failure class (Test/Application/Environment/Infrastructure)
#     fix_proposal: dict | None            # FixProposal dict from the Fix Proposal agent
#     approval_decision: str | None        # "approved" | "rejected" | "auto" | None
#     healing_retry_count: int             # heal attempts, max 2, counted per test
#     models_used: dict[str, str]          # {agent_name: model_string} for the report
#     terminal_status: str | None          # "PASS" | "FAIL" | "BLOCKED" | "ERROR" | None
#     errors: list[str]                    # node crash messages; report still runs
#     report_path: str | None             # path to the rendered report file

"""
Purpose: TestRunState TypedDict — the single shared state object
passed through every LangGraph node.

Must not: contain business logic.
"""

from typing import TypedDict


class TestRunState(TypedDict):
    # Run
    run_id: str
    test_request: dict
    target_url: str | None

    # Planning
    test_plan: list[dict]

    # Code generation / validation
    generated_test_files: list[str]
    validation_status: str | None
    validation_errors: list[str]
    generation_retry_count: int

    # Human code review
    human_review_decision: str | None
    human_review_count: int
    reviewer_note: str | None
    edited_code: str | None

    # Execution
    execution_result: dict | None
    execution_evidence: list[dict]

    # Failure analysis
    failure_analysis: dict | None
    failure_type: str | None

    # Healing
    fix_proposal: dict | None
    approval_decision: str | None
    healing_retry_count: int

    # Models
    models_used: dict[str, str]

    # Final state
    terminal_status: str | None
    errors: list[str]
    report_path: str | None