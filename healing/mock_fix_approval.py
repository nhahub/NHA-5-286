
from langgraph.types import interrupt


def mock_fix_approval_node(state: dict) -> dict:
    """
    Pause the graph and request human approval.
    Does not apply any patch.
    """

    proposal = state.get("fix_proposal") or {}

    decision = interrupt({
        "type": "fix_approval",
        "run_id": state.get("run_id"),
        "reason": proposal.get("reason"),
        "patch_diff": proposal.get("patch_diff"),
        "risky": proposal.get("risky", False),
        "message": "Approve or reject the proposed fix."
    })

    if decision not in ("approved", "rejected"):
        raise ValueError(
            "Human decision must be approved or rejected."
        )

    return {
        "approval_decision": decision
    }
