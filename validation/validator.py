"""
Purpose: Deterministic validator — checks that generated .spec.ts files compile and use the Playwright API correctly.
Owner: @Shema
Reads: generated_test_files
Writes: validation_status, validation_errors, generation_retry_count
Must not: rewrite code or judge business correctness
"""

# def validate_spec_file(file_path: str) -> tuple[bool, list[str]]:
#     -> Runs tsc --noEmit on the spec file; parses compiler errors into a list of strings
#     -> Returns (True, []) on success; (False, [error_lines]) on failure

# def validate_all(state: TestRunState) -> TestRunState:
#     -> LangGraph node function
#     -> Calls validate_spec_file for each path in generated_test_files
#     -> Writes validation_status ("valid" | "invalid") and validation_errors
#     -> Increments generation_retry_count when returning "invalid" after a retry path
