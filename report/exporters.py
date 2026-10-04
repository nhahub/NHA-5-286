"""
Purpose: Render ReportModel to Markdown, Playwright HTML, and PDF (Chromium page.pdf) — MVP exports.
Reads: ReportModel, Jinja2 templates in report/templates/
Writes: report.md, html-report/, report.pdf inside runs/<run_id>/
Must not: reclassify a failure, change a result, call an agent, or re-run a test
"""

# def export_markdown(report_model: ReportModel, run_dir: str) -> str:
#     -> Loads report/templates/report.md.j2 via Jinja2
#     -> Renders with report_model dict and writes report.md to run_dir
#     -> Returns absolute path to report.md

# def export_html(run_dir: str) -> str:
#     -> Loads report/templates/report.html.j2 via Jinja2; writes html-report/index.html
#     -> Returns absolute path to html-report/

# def export_pdf(html_path: str, run_dir: str) -> str:
#     -> Uses Chromium (via Playwright Python sync API) to call page.pdf() on the HTML report
#     -> Writes report.pdf to run_dir; returns absolute path
#     -> PDF export uses the same report_model; never re-runs tests or calls agents (see spec §10)
