
from typing import Any, Mapping


def mock_apply_fix(state: Mapping[str, Any]) -> dict:
    """
    Simulate applying an approved fix.

    Does not modify real Playwright files.
    """

    decision = state.get("approval_decision")
    proposal = state.get("fix_proposal") or {}
    retries = state.get("healing_retry_count", 0)

    if decision != "approved":
        return {
            "terminal_status": "FAIL",
            "errors": [
                *state.get("errors", []),
                "Fix was not approved."
            ]
        }

    if retries >= 2:
        return {
            "terminal_status": "FAIL",
            "errors": [
                *state.get("errors", []),
                "Maximum healing attempts reached."
            ]
        }

    if not proposal.get("patch_diff"):
        return {
            "terminal_status": "FAIL",
            "errors": [
                *state.get("errors", []),
                "No proposed patch found."
            ]
        }

    return {
        "healing_retry_count": retries + 1,
        "generated_test_files": list(
            state.get("generated_test_files") or []
        ),
        "mock_fix_applied": True
    }
