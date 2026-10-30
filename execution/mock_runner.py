
from typing import Any, Mapping

from contracts.evidence import Evidence


def mock_run_execute(state: Mapping[str, Any]) -> dict:
    """
    Simulate execution without opening a browser.
    """

    scenarios = state.get("test_plan") or []
    files = state.get("generated_test_files") or []

    if not scenarios or not files:
        return {
            "terminal_status": "BLOCKED",
            "errors": [
                *state.get("errors", []),
                "No scenarios or test files."
            ]
        }

    requested_outcome = state.get(
        "mock_execution_outcome", "PASS"
    )

    # Mock mode only: `mock_fixes_needed` lets tests simulate several healing cycles. When it is
    # absent the original behaviour applies (one applied fix makes the rerun pass).
    needed = state.get("mock_fixes_needed")
    if needed is None:
        fix_applied = state.get("mock_fix_applied", False)
    else:
        fix_applied = state.get("healing_retry_count", 0) >= int(needed)

    # A simulated approved fix makes the rerun pass.
    passed = requested_outcome == "PASS" or fix_applied

    status = "PASS" if passed else "FAIL"

    tests = []
    evidence = []

    for index, scenario in enumerate(scenarios):
        name = scenario["name"]

        tests.append({
            "scenario_id": f"s{index + 1}",
            "scenario_name": name,
            "status": "passed" if passed else "failed",
            "duration_ms": 1200,
            "simulated": True
        })

        item = Evidence(
            scenario_name=name,
            error_message=(
                None if passed
                else "MOCK: Login button selector not found."
            ),
            failed_step=(
                None if passed
                else "Click Login button"
            ),
            spec_code=None,
            page_snapshot=None,
            screenshot_path=None,
            trace_path=None,
            console_log=[],
            network_errors=[],
            final_url=None
        )

        evidence.append(item.model_dump())

    return {
        "execution_result": {
            "status": status,
            "tests": tests,
            "simulated": True,
            "rerun": bool(state.get("healing_retry_count", 0) or state.get("mock_fix_applied", False))
        },
        "execution_evidence": evidence,
        "terminal_status": status
    }
