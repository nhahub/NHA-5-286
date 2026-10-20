
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from graph.state import TestRunState
from graph.nodes import fix_proposal_node, fix_approval_node
from graph.routing import (
    route_after_fix_proposal,
    route_after_fix_approval,
)


class FakeLLM:
    def with_structured_output(self, schema):
        def respond(prompt):
            return {
                "patch_diff": (
                    "--- a/s2-invalid-login.spec.ts\n"
                    "+++ b/s2-invalid-login.spec.ts\n"
                    "@@ -1 +1 @@\n"
                    "-await expect(error).toBeVisible();\n"
                    "+await expect(error).toBeHidden();\n"
                ),
                "reason": "Change the assertion",
                "risky": False,
            }

        return RunnableLambda(respond)


# Build an isolated integration graph
builder = StateGraph(TestRunState)

builder.add_node("fix_proposal", fix_proposal_node)
builder.add_node("fix_approval", fix_approval_node)

builder.add_node(
    "apply_stub",
    lambda state: {"terminal_status": "APPLY_STUB"},
)
builder.add_node(
    "report_stub",
    lambda state: {"terminal_status": "REPORT_STUB"},
)

builder.add_edge(START, "fix_proposal")

builder.add_conditional_edges(
    "fix_proposal",
    route_after_fix_proposal,
    {
        "fix_approval": "fix_approval",
        "report": "report_stub",
    },
)

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


project_root = Path(__file__).resolve().parents[1]
runs_dir = project_root / "runs"
runs_dir.mkdir(exist_ok=True)

with TemporaryDirectory(
    dir=runs_dir,
    prefix="p4_integration_",
) as temp_dir:

    run_dir = Path(temp_dir)
    tests_dir = run_dir / "tests"
    tests_dir.mkdir()

    spec_file = tests_dir / "s2-invalid-login.spec.ts"
    original_code = "await expect(error).toBeVisible();\n"
    spec_file.write_text(original_code, encoding="utf-8")

    state = {
        "run_id": run_dir.name,
        "mock_mode": False,
        "terminal_status": "FAIL",
        "failure_type": "Test",
        "test_request": {
            "codegen_model": "fake:test-model",
            "requirements": "Test invalid login",
        },
        "generated_test_files": [str(spec_file)],
        "execution_evidence": [
            {
                "scenario_name": "Invalid Login",
                "error_message": "Assertion failed",
            }
        ],
        "failure_analysis": {
            "failure_type": "Test",
            "subtype": "ASSERTION",
            "root_cause": "Incorrect assertion",
            "evidence": "Assertion failed",
            "application_bug": False,
            "fix_required": True,
            "confidence": "high",
        },
        "models_used": {},
    }

    with patch(
        "graph.nodes.model_factory_for",
        return_value=lambda model: FakeLLM(),
    ):
        for decision in ("approved", "rejected"):
            config = {
                "configurable": {
                    "thread_id": f"p4-integrated-{decision}"
                }
            }

            # Real Fix Proposal -> Human Interrupt
            paused = graph.invoke(state, config=config)

            assert paused.get("__interrupt__"), paused

            request = paused["__interrupt__"][0].value

            assert request["type"] == "fix_approval"
            assert request["risky"] is True
            assert request["patch_diff"]

            # No fix before human approval
            assert spec_file.read_text(
                encoding="utf-8"
            ) == original_code

            print(f"{decision.upper()} - Interrupt: PASSED")

            # Resume with the human decision
            result = graph.invoke(
                Command(resume=decision),
                config=config,
            )

            assert result["approval_decision"] == decision

            expected_status = (
                "APPLY_STUB"
                if decision == "approved"
                else "REPORT_STUB"
            )

            assert result["terminal_status"] == expected_status

            # Even the approved branch uses a harmless stub
            assert spec_file.read_text(
                encoding="utf-8"
            ) == original_code

            print(f"{decision.upper()} - Routing: PASSED")

print("REAL FIX PROPOSAL + HUMAN APPROVAL TEST PASSED")
