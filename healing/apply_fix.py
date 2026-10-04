"""
Purpose: Apply Fix service — applies an approved patch to the spec file and increments the heal counter.
Owner: @Shema
Reads: fix_proposal, approval_decision
Writes: generated_test_files, healing_retry_count
Must not: apply an unapproved risky patch or exceed 2 heal attempts per test
"""

# def apply_patch(spec_path: str, patch_diff: str) -> bool:
#     -> Applies a unified-diff patch to the spec file using the `patch` stdlib or unidiff library
#     -> Returns True on clean apply; False if the patch cannot be applied cleanly

# def run_apply_fix(state: TestRunState) -> TestRunState:
#     -> LangGraph node function
#     -> Guards: healing_retry_count < 2 and (approval_decision == "approved" or (auto_heal_mode == "auto" and not fix_proposal.risky))
#     -> Calls apply_patch; updates generated_test_files with the patched path
#     -> Increments healing_retry_count
#     -> On failure to apply: sets terminal_status to FAIL and routes to report
