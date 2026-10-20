"""
Purpose: Deterministic routing functions — plain Python if-statements reading TestRunState; no LLM calls.
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



from graph.state import TestRunState, is_mock_mode


def route_after_execute(state: TestRunState) -> str:
    """
    Choose the next step after execution.
    This function does not modify state.
    """

    status = state.get("terminal_status")

    if status == "PASS":
        return "report"

    if status == "FAIL":
        return "analyze"

    if status in ("BLOCKED", "ERROR"):
        return "report"

    return "report"


def route_after_fix_approval(state: TestRunState) -> str:
    """
    Route to Apply Fix only when approval
    and a proposed patch are present.
    """

    # 1. Never apply a fix after terminal errors
    if state.get("terminal_status") in ("ERROR", "BLOCKED"):
        return "report"

    # 2. A fix proposal must exist
    proposal = state.get("fix_proposal")

    if not isinstance(proposal, dict):
        return "report"

    # 3. The patch cannot be empty
    patch_diff = proposal.get("patch_diff")

    if not isinstance(patch_diff, str) or not patch_diff.strip():
        return "report"

    # 4. Only explicit human approval can proceed
    if state.get("approval_decision") != "approved":
        return "report"

    return "apply_fix"


def route_after_intake(state: TestRunState) -> str:
    if state.get("terminal_status") in ("BLOCKED", "ERROR"):
        return "report"

    if not state.get("target_url"):
        return "report"

    return "planner"


def route_after_validate(state: TestRunState) -> str:
    if state.get("terminal_status") in ("BLOCKED", "ERROR"):
        return "report"

    if state.get("validation_status") == "valid":
        return "execute"

    return "report"



def route_after_analyze(state: TestRunState) -> str:

    # 1. Stop if the run already failed
    if state.get("terminal_status") in ("ERROR", "BLOCKED"):
        return "report"

    # 2. Only Test failures can be healed
    if state.get("failure_type") != "Test":
        return "report"

    # 3. Maximum two healing attempts
    if state.get("healing_retry_count", 0) >= 2:
        return "report"

    # 4. Preserve existing mock-mode behavior
    if is_mock_mode(state):
        return "fix_proposal"

    # 5. Check the real Analyzer output
    analysis = state.get("failure_analysis")

    if not isinstance(analysis, dict):
        return "report"

    if (
        analysis.get("failure_type") != "Test"
        or analysis.get("fix_required") is not True
    ):
        return "report"

    # 6. Allow high-confidence failures only
    if analysis.get("confidence", "low") != "high":
        return "report"

    return "fix_proposal"



def route_after_apply_fix(state: TestRunState) -> str:
    if state.get("mock_fix_applied"):
        return "validate"

    return "report"


def route_after_fix_proposal(state: TestRunState) -> str:
    """
    Only send a successfully generated fix
    to Human Fix Approval.
    """

    # Stop if the node reported a terminal error
    if state.get("terminal_status") in ("ERROR", "BLOCKED"):
        return "report"

    # Check that a proposed patch exists
    proposal = state.get("fix_proposal")

    if (
        not isinstance(proposal, dict)
        or not proposal.get("patch_diff")
    ):
        return "report"

    return "fix_approval"
