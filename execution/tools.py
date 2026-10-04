"""
Purpose: Local tool definitions exposed with the @tool decorator for agent use; run_playwright_tests is excluded from agent tool lists.
Owner: @Shema
Reads: file system (spec files, results)
Writes: file system (spec files via save_test_file)
Must not: expose run_playwright_tests as a tool choosable by a model
"""

# @tool
# def save_test_file(path: str, content: str) -> str:
#     -> Writes content to path inside the current run folder (runs/<run_id>/tests/)
#     -> Returns the saved absolute path
#     -> Raises if path escapes the run folder (path traversal guard)

# @tool
# def read_test_file(path: str) -> str:
#     -> Reads and returns the content of a .spec.ts file within the run folder
#     -> Raises if path escapes the run folder

# @tool
# def get_results(run_dir: str) -> dict:
#     -> Reads results.json from run_dir and returns it as a parsed dict
