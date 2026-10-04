"""
Purpose: Deterministic routing functions — plain Python if-statements reading TestRunState; no LLM calls.
Owner: @Shema
Reads: terminal_status, validation_status, generation_retry_count, failure_type, healing_retry_count, approval_decision, execution_result
Writes: N/A (returns edge label strings only)
Must not: call any LLM, modify state, or guess the next node
"""

# Routing rules taken verbatim from the spec §4 Routing Rules:

# def route_after_intake(state: TestRunState) -> str:
#     -> If target_url is None or no usable model/key: return "report" (BLOCKED or ERROR)
#     -> Else: return "planner"

# def route_after_validate(state: TestRunState) -> str:
#     -> If validation_status == "valid": return "execute"
#     -> If invalid and generation_retry_count < 2: return "codegen"
#     -> If invalid after 2 retries and human_review_mode on: return "human_code_review"
#     -> If invalid after 2 retries and human_review_mode off: return "report" (BLOCKED)

# def route_after_execute(state: TestRunState) -> str:
#     -> If all tests passed: return "report" (PASS)
#     -> If app unreachable or run crashed: return "report" (BLOCKED or ERROR)
#     -> If any failure: return "analyze"

# def route_after_analyze(state: TestRunState) -> str:
#     -> If failure_type == "Test" and healing_retry_count < 2: return "fix_proposal"
#     -> If failure_type in {"Application", "Environment", "Infrastructure"}: return "report" (FAIL, no healing)

# def route_after_fix_proposal(state: TestRunState) -> str:
#     -> If approval_decision == "approved" or (auto_heal_mode and not fix_proposal.risky): return "apply_fix"
#     -> If approval_decision == "rejected": return "report" (FAIL)

# def route_after_apply_fix(state: TestRunState) -> str:
#     -> Always: return "validate"  (patched files must be re-validated before re-execution)
