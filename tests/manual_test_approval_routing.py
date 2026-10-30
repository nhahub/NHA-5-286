
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from graph.state import TestRunState
from graph.nodes import fix_approval_node, apply_fix_node
from graph.routing import route_after_fix_approval


def report_node(state):
    return {
        "terminal_status": (
            "PASS"
            if state.get("mock_fix_applied")
            else "FAIL"
        )
    }


builder = StateGraph(TestRunState)

builder.add_node("approval", fix_approval_node)
builder.add_node("apply_fix", apply_fix_node)
builder.add_node("report", report_node)

builder.add_edge(START, "approval")

builder.add_conditional_edges(
    "approval",
    route_after_fix_approval,
    {
        "apply_fix": "apply_fix",
        "report": "report"
    }
)

builder.add_edge("apply_fix", "report")
builder.add_edge("report", END)

graph = builder.compile(checkpointer=InMemorySaver())


def test_decision(decision: str):
    config = {
        "configurable": {
            "thread_id": f"approval-routing-{decision}"
        }
    }

    state = {
        "mock_mode": True,
        "run_id": f"run-{decision}",
        "generated_test_files": ["mock.spec.ts"],
        "healing_retry_count": 0,
        "fix_proposal": {
            "patch_diff": "MOCK PATCH",
            "reason": "Test routing",
            "risky": True
        }
    }

    paused = graph.invoke(state, config=config)

    assert paused.get("__interrupt__")

    result = graph.invoke(
        Command(resume=decision),
        config=config
    )

    print(f"\n{decision.upper()}")
    print("Decision:", result["approval_decision"])
    print("Fix Applied:", result.get("mock_fix_applied", False))
    print("Healing Count:", result.get("healing_retry_count", 0))
    print("Final Status:", result["terminal_status"])


test_decision("approved")
test_decision("rejected")
