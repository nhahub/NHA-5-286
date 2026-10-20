
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from graph.state import TestRunState
from graph.nodes import fix_approval_node


builder = StateGraph(TestRunState)

builder.add_node("approval", fix_approval_node)
builder.add_edge(START, "approval")
builder.add_edge("approval", END)

graph = builder.compile(checkpointer=InMemorySaver())


def test_decision(decision: str):
    config = {
        "configurable": {
            "thread_id": f"sandbox-{decision}-test"
        }
    }

    initial_state = {
        "sandbox_mode": True,
        "run_id": f"test-{decision}",
        "fix_proposal": {
            "reason": "MOCK: Proposed assertion change.",
            "patch_diff": "MOCK PATCH",
            "risky": True
        }
    }

    paused = graph.invoke(initial_state, config=config)

    assert paused.get("__interrupt__"), "Graph did not pause"

    print(f"\n{decision.upper()}")
    print("Paused:", True)

    completed = graph.invoke(
        Command(resume=decision),
        config=config
    )

    assert completed["approval_decision"] == decision

    print("Decision:", completed["approval_decision"])


test_decision("approved")
test_decision("rejected")
