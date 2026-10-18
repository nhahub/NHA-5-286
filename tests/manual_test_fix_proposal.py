
from langchain_core.runnables import RunnableLambda

from agents.fix_proposal import run_fix_proposal


# Fake LLM for testing without API keys
class FakeLLM:

    def with_structured_output(self, schema):
        def respond(prompt):
            messages = prompt.to_messages()

            assert "Fix Proposal" in messages[0].content
            assert "Wrong assertion" in messages[1].content

            return {
                "patch_diff": (
                    "--- a/login.spec.ts\n"
                    "+++ b/login.spec.ts\n"
                    "@@ -1 +1 @@\n"
                    "-await expect(error).toBeVisible();\n"
                    "+await expect(error).toBeHidden();\n"
                ),
                "reason": "Change expected behavior",
                "risky": False,
            }

        return RunnableLambda(respond)


state = {
    "failure_analysis": {
        "failure_type": "Test",
        "subtype": "ASSERTION",
        "root_cause": "Wrong assertion",
        "evidence": "Assertion failed",
        "application_bug": False,
        "fix_required": True,
    },
    "execution_evidence": [
        {
            "scenario_name": "Invalid Login",
            "error_message": "Assertion failed",
            "failed_step": "Verify error message",
        }
    ],
    "test_request": {
        "requirements": "Verify invalid login error"
    },
    "models_used": {},
}

result = run_fix_proposal(
    state,
    spec_code="await expect(error).toBeVisible();\n",
    spec_filename="login.spec.ts",
    model="fake:test-model",
    model_factory=lambda name: FakeLLM(),
)

assert result["fix_proposal"]["risky"] is True
assert result["models_used"]["fix_proposal"] == "fake:test-model"

print("Reason:", result["fix_proposal"]["reason"])
print("Risky:", result["fix_proposal"]["risky"])
print("Model:", result["models_used"]["fix_proposal"])
print("TEST PASSED")
