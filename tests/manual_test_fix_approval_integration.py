
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from graph.state import TestRunState
from graph.nodes import fix_approval_node
from graph.routing import route_after_fix_approval


# Build a small test graph
builder = StateGraph(TestRunState)

builder.add_node("fix_approval", fix_approval_node)

# Safe placeholders: no patch is actually applied
builder.add_node(
    "apply_stub",
    lambda state: {"terminal_status": "APPLY_STUB"},
)

builder.add_node(
    "report_stub",
    lambda state: {"terminal_status": "REPORT_STUB"},
)

builder.add_edge(START, "fix_approval")

builder.add_conditional_edges(
    "fix_approval",
    route_after_fix_approval,
    {
        "apply_fix": "apply_stub",
        "report": "report_stub",
    },
)

builder.add_edge("apply_stub", END)
builder.add_edge("report_stub", END)

graph = builder.compile(checkpointer=InMemorySaver())


# A proposal with the same structure as Real Fix Proposal
state = {
    "run_id": "p4-approval-test",
    "fix_proposal": {
        "patch_diff": (
            "--- a/login.spec.ts\n"
            "+++ b/login.spec.ts\n"
            "@@ -1 +1 @@\n"
            "-old_locator\n"
            "+new_locator\n"
        ),
        "reason": "Fix outdated selector",
        "risky": False,
    },
}


for decision in ("approved", "rejected"):
    config = {
        "configurable": {
            "thread_id": f"p4-{decision}"
        }
    }

    # First call must pause for human approval
    paused = graph.invoke(state, config=config)

    assert "__interrupt__" in paused
    assert paused["__interrupt__"]

    request = paused["__interrupt__"][0].value

    assert request["type"] == "fix_approval"
    assert request["patch_diff"] == state["fix_proposal"]["patch_diff"]

    print(f"Human Approval Interrupt ({decision}): PASSED")

    # Simulate the human decision
    result = graph.invoke(
        Command(resume=decision),
        config=config,
    )

    assert result["approval_decision"] == decision

    if decision == "approved":
        assert result["terminal_status"] == "APPLY_STUB"
    else:
        assert result["terminal_status"] == "REPORT_STUB"

    print(f"{decision.upper()} Routing: PASSED")


print("HUMAN FIX APPROVAL TESTS PASSED")
