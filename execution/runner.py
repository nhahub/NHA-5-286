"""
Purpose: Execute node — invokes Playwright and collects execution_result and execution_evidence without diagnosing anything.
Owner: @Shema
Reads: generated_test_files
Writes: execution_result, execution_evidence
Must not: diagnose failures or modify any code
"""

# def run_playwright_tests(spec_files: list[str], run_dir: str) -> dict:
#     -> Calls `playwright test <spec_files>` via subprocess with JSON reporter
#     -> Called directly by the execute node only — never chosen by a model (see spec §3)
#     -> Returns raw Playwright JSON reporter output as a dict

# def collect_evidence(results: dict, run_dir: str) -> list[Evidence]:
#     -> Iterates Playwright JSON suites/specs/tests; maps each result to an Evidence object
#     -> Attaches screenshot_path and trace_path from result attachments

# def run_execute(state: TestRunState) -> TestRunState:
#     -> LangGraph node function
#     -> Calls run_playwright_tests; calls collect_evidence
#     -> Writes execution_result and execution_evidence
#     -> On subprocess crash or app-unreachable error: sets terminal_status to BLOCKED or ERROR
