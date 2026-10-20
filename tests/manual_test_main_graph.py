
from graph.build_graph import build_graph

graph = build_graph()

state = {
    "mock_mode": True,
    "mock_execution_outcome": "PASS",
    "test_request": {
        "url": "https://example.com/login",
        "requirements": "Test invalid login",
        "scenario_cap": 1,
        "authorization": True,
    },
    "errors": [],
}

config = {
    "configurable": {
        "thread_id": "main-graph-pass-001"
    }
}

result = graph.invoke(state, config=config)

print("Terminal Status:", result.get("terminal_status"))
print("Execution:", result.get("execution_result", {}).get("status"))
print("Interrupted:", bool(result.get("__interrupt__")))
print("Errors:", result.get("errors"))
