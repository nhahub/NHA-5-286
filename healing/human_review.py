"""
Purpose: Human Code Review checkpoint — presents generated code and validation errors; blocks the run until the reviewer decides.
Owner: @Shema
Reads: generated_test_files, validation_errors
Writes: human_review_decision, edited_code, reviewer_note, human_review_count
Must not: skip validation or alter application code
"""

# def present_for_review(state: TestRunState) -> TestRunState:
#     -> LangGraph node function (interrupt node)
#     -> Emits the generated code and validation errors to the UI review panel
#     -> Blocks for up to 30 minutes; on timeout sets terminal_status = BLOCKED (review timeout)
#     -> human_review_mode == "off" sets BLOCKED immediately (suitable for CI runs)
#     -> Maximum 2 rounds per scenario (human_review_count); auto-BLOCKED after that

# def apply_review_decision(
#     decision: str,
#     edited_code: str | None,
#     reviewer_note: str | None,
#     state: TestRunState,
# ) -> TestRunState:
#     -> Maps reviewer action to state updates:
#        "edit_and_resubmit" → writes edited_code, returns to validate
#        "regenerate_with_note" → writes reviewer_note, returns to codegen
#        "skip_scenario"       → marks scenario BLOCKED (could not generate); continues others
#        "reject"              → sets terminal_status = FAIL, routes to report
