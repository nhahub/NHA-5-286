
from langchain_core.runnables import RunnableLambda
from agents.fix_proposal import run_fix_proposal


class FakeLLM:
    def __init__(self):
        self.calls = 0

    def with_structured_output(self, schema):

        def respond(prompt):
            self.calls += 1

            if self.calls == 2:
                message = prompt.to_messages()[-1].content
                assert "previous proposal failed" in message

            invalid_patch = (
                "--- a/login.spec.ts\n"
                "+++ b/login.spec.ts\n"
                "@@ -1,2 +1,2 @@\n"
                "-await expect(error).toBeVisible();\n"
                "+await expect(error).toBeHidden();\n"
            )

            valid_patch = (
                "--- a/login.spec.ts\n"
                "+++ b/login.spec.ts\n"
                "@@ -1 +1 @@\n"
                "-await expect(error).toBeVisible();\n"
                "+await expect(error).toBeHidden();\n"
            )

            return {
                "patch_diff": (
                    invalid_patch if self.calls == 1
                    else valid_patch
                ),
                "reason": "Correct the assertion",
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

fake_llm = FakeLLM()

result = run_fix_proposal(
    state,
    spec_code="await expect(error).toBeVisible();\n",
    spec_filename="login.spec.ts",
    model="fake:test-model",
    model_factory=lambda name: fake_llm,
)

assert fake_llm.calls == 2
assert result["fix_proposal"]["risky"] is True
assert result["models_used"]["fix_proposal"] == "fake:test-model"

print("LLM Calls:", fake_llm.calls)
print("Risky:", result["fix_proposal"]["risky"])
print("ONE RETRY TEST PASSED")



# Test: Both attempts fail

bad_llm = FakeLLM()

try:
    run_fix_proposal(
        state,
        spec_code="await expect(error).toHaveText('wrong');\n",
        spec_filename="login.spec.ts",
        model="fake:test-model",
        model_factory=lambda name: bad_llm,
    )

except ValueError as exc:
    assert "after 2 attempts" in str(exc)

else:
    raise AssertionError(
        "Agent returned a proposal after two failed attempts!"
    )

assert bad_llm.calls == 2

print("Failed Attempts:", bad_llm.calls)
print("DOUBLE FAILURE TEST PASSED")
