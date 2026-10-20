
from uuid import uuid4

from langgraph.types import Command

from graph.build_graph import build_graph


graph = build_graph()


def test_case(risky: bool, decision: str):
    thread_id = str(uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    state = {
        "sandbox_mode": True,
        "mock_execution_outcome": "FAIL",
        "mock_risky": risky,
        "test_request": {
            "url": "https://example.com/login",
            "requirements": "Test invalid login",
            "scenario_cap": 1,
            "authorization": True,
        },
        "healing_retry_count": 0,
        "errors": [],
    }

    print(
        f"\nCASE: risky={risky}, decision={decision}"
    )

    # -----------------------------------------
    # STEP 1: Start Main Graph
    # -----------------------------------------

    paused = graph.invoke(state, config=config)

    # -----------------------------------------
    # DEBUG: Check where the Graph stopped
    # -----------------------------------------

    print("\n--- DEBUG MAIN GRAPH ---")
    print("Terminal Status:", paused.get("terminal_status"))
    print("Execution:", paused.get("execution_result"))
    print("Failure Type:", paused.get("failure_type"))
    print("Fix Proposal:", paused.get("fix_proposal"))
    print("Errors:", paused.get("errors"))
    print("Interrupts:", paused.get("__interrupt__"))
    print("Next Nodes:", graph.get_state(config).next)
    print("------------------------")

    # -----------------------------------------
    # STEP 2: Verify Human Approval Interrupt
    # -----------------------------------------

    interrupts = paused.get("__interrupt__", [])

    assert interrupts, (
        "Graph did not pause for approval. "
        "Check the debug output above."
    )

    approval_data = interrupts[0].value

    assert approval_data["type"] == "fix_approval"
    assert approval_data["risky"] == risky

    print("Paused for approval:", True)
    print("Risky:", approval_data["risky"])
    print("Patch:", approval_data["patch_diff"])

    # -----------------------------------------
    # STEP 3: Resume with Human Decision
    # -----------------------------------------

    result = graph.invoke(
        Command(resume=decision),
        config=config
    )

    # -----------------------------------------
    # DEBUG: Check final result
    # -----------------------------------------

    print("\n--- DEBUG AFTER RESUME ---")
    print("Decision:", result.get("approval_decision"))
    print("Terminal Status:", result.get("terminal_status"))
    print("Execution:", result.get("execution_result"))
    print("Fix Applied:", result.get("mock_fix_applied"))
    print("Healing Count:", result.get("healing_retry_count"))
    print("Errors:", result.get("errors"))
    print("Next Nodes:", graph.get_state(config).next)
    print("--------------------------")

    # -----------------------------------------
    # STEP 4: Verify Expected Results
    # -----------------------------------------

    expected_status = (
        "PASS" if decision == "approved" else "FAIL"
    )

    assert result["terminal_status"] == expected_status, (
        f"Expected {expected_status}, "
        f"got {result['terminal_status']}"
    )

    if decision == "approved":
        assert result["mock_fix_applied"] is True
        assert result["healing_retry_count"] == 1
        assert result["execution_result"]["rerun"] is True

    else:
        assert not result.get("mock_fix_applied", False)
        assert result.get("healing_retry_count", 0) == 0

    print("\nTEST RESULT: PASSED")


# -----------------------------------------
# TEST ALL FOUR CASES
# -----------------------------------------

test_case(risky=False, decision="approved")
test_case(risky=False, decision="rejected")
test_case(risky=True, decision="approved")
test_case(risky=True, decision="rejected")

print("\nALL FOUR CASES PASSED")
