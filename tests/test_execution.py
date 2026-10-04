"""
Purpose: Tests for execution/ package — Playwright test runner and evidence collection.
"""

# --- runner ---

# def test_run_execute_writes_execution_result() -> None:
#     -> With a mocked subprocess, run_execute sets state["execution_result"]

# def test_run_execute_writes_execution_evidence() -> None:
#     -> With a mocked result, run_execute sets state["execution_evidence"] as list

# def test_run_execute_sets_blocked_on_unreachable_app() -> None:
#     -> When Playwright reports connection refused, terminal_status becomes BLOCKED

# def test_collect_evidence_maps_timeout_error() -> None:
#     -> Given results.json fixture, collect_evidence returns Evidence with error_message containing "TimeoutError"

# def test_collect_evidence_attaches_screenshot_path() -> None:
#     -> Given a result with screenshot attachment, Evidence.screenshot_path is set

# --- tools ---

# def test_save_test_file_writes_within_run_folder() -> None:
#     -> save_test_file with a path inside runs/ writes file and returns absolute path

# def test_save_test_file_rejects_path_traversal() -> None:
#     -> save_test_file with "../../etc/passwd" raises (path traversal guard)

# def test_read_test_file_returns_content() -> None:
#     -> Creates a temp .spec.ts, read_test_file returns its content

# def test_get_results_parses_results_json() -> None:
#     -> Given the results.json fixture path, get_results returns a dict with "stats"
