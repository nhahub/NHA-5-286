"""
Purpose: Tests for report/ package — ReportModel building and format exporters.
Owner: @Shema
"""

# --- model ---

# def test_build_report_model_maps_terminal_status_verbatim() -> None:
#     -> state["terminal_status"]="FAIL" → report_model.terminal_status == "FAIL" (no reclassification)

# def test_determine_terminal_status_all_pass() -> None:
#     -> stats.unexpected==0 → "PASS"

# def test_determine_terminal_status_any_fail() -> None:
#     -> stats.unexpected>0 and failure classified → "FAIL"

# def test_determine_terminal_status_blocked_on_no_url() -> None:
#     -> target_url=None → "BLOCKED"

# def test_defect_candidates_only_for_application_failures() -> None:
#     -> failure_type="Application" → defect_candidates is non-empty
#     -> failure_type="Test" → defect_candidates is empty

# def test_build_report_model_never_calls_agents() -> None:
#     -> build_report_model must not make any LLM calls (mock assertion)

# --- exporters ---

# def test_export_markdown_writes_report_md() -> None:
#     -> Given a ReportModel and temp run_dir, report.md is created

# def test_export_markdown_contains_run_id() -> None:
#     -> report.md content contains the run_id string

# def test_export_html_writes_index_html() -> None:
#     -> Given a ReportModel and temp run_dir, html-report/index.html is created

# def test_export_pdf_writes_report_pdf() -> None:
#     -> Given an html_path, report.pdf is written to run_dir (may be skipped if Chromium not available)
