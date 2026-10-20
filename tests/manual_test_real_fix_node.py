
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from langchain_core.runnables import RunnableLambda

from graph.nodes import fix_proposal_node
from graph.routing import route_after_fix_proposal


class FakeLLM:
    def with_structured_output(self, schema):

        def respond(prompt):
            return {
                "patch_diff": (
                    "--- a/s2-invalid-login.spec.ts\n"
                    "+++ b/s2-invalid-login.spec.ts\n"
                    "@@ -1 +1 @@\n"
                    "-await page.locator('#login').click();\n"
                    "+await page.getByRole('button', "
                    "{ name: 'Sign in' }).click();\n"
                ),
                "reason": "Fix outdated selector",
                "risky": False,
            }

        return RunnableLambda(respond)


project_root = Path(__file__).resolve().parents[1]
runs_dir = project_root / "runs"
runs_dir.mkdir(exist_ok=True)

with TemporaryDirectory(
    dir=runs_dir,
    prefix="p4_node_",
) as temp_dir:

    run_dir = Path(temp_dir)
    tests_dir = run_dir / "tests"
    tests_dir.mkdir()

    spec_file = tests_dir / "s2-invalid-login.spec.ts"

    spec_file.write_text(
        "await page.locator('#login').click();\n",
        encoding="utf-8",
    )

    state = {
        "run_id": run_dir.name,
        "sandbox_mode": False,
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
                "error_message": "Locator timed out",
            }
        ],
        "failure_analysis": {
            "failure_type": "Test",
            "subtype": "SELECTOR",
            "root_cause": "Outdated selector",
            "evidence": "Locator timed out",
            "application_bug": False,
            "fix_required": True,
            "confidence": "high",
        },
        "models_used": {},
    }

    # Replace the real model factory only during this test.
    with patch(
        "graph.nodes.model_factory_for",
        return_value=lambda model: FakeLLM(),
    ):
        result = fix_proposal_node(
            state,
            config={
                "configurable": {
                    "thread_id": "p4-test-thread"
                }
            },
        )

    assert "fix_proposal" in result, result

    assert result["fix_proposal"]["risky"] is False

    assert (
        result["models_used"]["fix_proposal"]
        == "fake:test-model"
    )

    # Make sure routing sends successful fixes to approval.
    next_node = route_after_fix_proposal({
        **state,
        **result,
    })

    assert next_node == "fix_approval"

    # Original file must remain unchanged.
    assert spec_file.read_text(encoding="utf-8") == (
        "await page.locator('#login').click();\n"
    )

    print("Real Node: PASSED")
    print("Patch Validation: PASSED")
    print("Next Node:", next_node)
    print("Original File: UNCHANGED")
    print("REAL FIX NODE TEST PASSED")
