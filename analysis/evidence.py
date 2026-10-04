"""
Purpose: Normalise raw Playwright JSON execution output into structured Evidence objects for the Failure Analyzer.
Reads: execution_result (raw Playwright JSON reporter dict)
Writes: execution_evidence state field
Must not: classify failures or propose fixes
"""

# def parse_playwright_results(results_json: dict) -> list[dict]:
#     -> Walks the Playwright JSON reporter structure (config → suites → specs → tests → results)
#     -> Returns a flat list of per-test result dicts

# def normalise_evidence(raw_result: dict, spec_code: str | None = None) -> Evidence:
#     -> Maps Playwright result fields to Evidence model fields
#     -> Sets scenario_name from the spec title chain
#     -> Extracts screenshot_path and trace_path from result.attachments

# def extract_error_message(result: dict) -> str | None:
#     -> Pulls the first error.message from result.errors (e.g. "TimeoutError: locator.click: ...")
#     -> Returns None when result.errors is empty (passing test)
