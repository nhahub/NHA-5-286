
from agents.fix_proposal import select_failed_spec_file


# Simulated LangGraph State
state = {
    "generated_test_files": [
        "runs/123/tests/s1-valid-login.spec.ts",
        "runs/123/tests/s2-invalid-login.spec.ts",
    ],
    "execution_evidence": [
        {
            "scenario_name": "Valid Login",
            "error_message": None,
        },
        {
            "scenario_name": "Invalid Login",
            "error_message": "Locator timed out",
        },
    ],
}


# Select the failed test file
selected_file = select_failed_spec_file(state)

print("Selected file:", selected_file.name)

assert selected_file.name == "s2-invalid-login.spec.ts"

print("FAILED SPEC SELECTION TEST PASSED")
