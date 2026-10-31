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



from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import ChainableUndefined, Environment, FileSystemLoader

if TYPE_CHECKING:
    from contracts.report import ReportModel
from llm.errors import redact
from report.model import build_report_model

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = Path(__file__).parent / "templates"


# ------------------------------------------------------------------ template helpers
def md_cell(value: Any) -> str:
    """Make text safe inside a Markdown table cell."""
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def fence(text: Any, lang: str = "") -> str:
    """Fence a block so backticks inside the text cannot close it early."""
    text = str(text or "")
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{lang}\n{text}\n{ticks}"


def _env(autoescape: bool) -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=autoescape,  # HTML: ON (text comes from untrusted sites and LLMs). Markdown: off.
        undefined=ChainableUndefined,  # a missing field must never crash the report
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["md_cell"] = md_cell
    env.filters["fence"] = fence
    return env


def render_markdown(model: ReportModel | Mapping[str, Any]) -> str:
    return _env(False).get_template("report.md.j2").render(r=model)


_LOGO_URI: str | None = None


def _logo_uri() -> str:
    """The Bugle logo as a data URI so report.html stays a single self-contained file."""
    global _LOGO_URI
    if _LOGO_URI is None:
        try:
            import base64

            png = (PROJECT_ROOT / "ui" / "assets" / "bugle-logo-light.png").read_bytes()
            _LOGO_URI = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        except OSError:
            _LOGO_URI = ""
    return _LOGO_URI


def render_html(model: ReportModel | Mapping[str, Any]) -> str:
    return _env(True).get_template("report.html.j2").render(r=model, logo=_logo_uri())


# ----------------------------------------------------------------------- writers
def write_reports(model: ReportModel | Mapping[str, Any], run_dir: Path) -> Path:
    """Write report.md and report.html next to the run's other files. Returns the Markdown path."""
    run_dir.mkdir(parents=True, exist_ok=True)
    md_path = run_dir / "report.md"
    md_path.write_text(render_markdown(model), encoding="utf-8")
    (run_dir / "report.html").write_text(render_html(model), encoding="utf-8")
    return md_path


def export_report(model: ReportModel | Mapping[str, Any], run_dir: Path | str | None = None) -> str:
    """Convenience helper to export reports and return the Markdown report path."""
    if run_dir is None:
        run_id = str(model.get("run_id") or "unknown")
        target_dir = PROJECT_ROOT / "runs" / _safe_run_id(run_id)
    else:
        target_dir = Path(run_dir)
    return str(write_reports(model, target_dir))


def export_pdf(model: ReportModel | Mapping[str, Any], pdf_path: Path) -> Path:
    """Print the already-rendered HTML with Chromium. Needs the Python 'playwright' package."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "PDF export needs the Python package 'playwright' (pip install playwright) "
            "and a browser (playwright install chromium)"
        ) from exc
    html = render_html(model)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")  # no network: the HTML is fully self-contained
            page.pdf(path=str(pdf_path), format="A4", print_background=True)
        finally:
            browser.close()
    return pdf_path


# ---------------------------------------------------------------- LangGraph node
def _safe_run_id(raw: Any) -> str:
    """A run id becomes a folder name: never let it contain path separators or '..'."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", str(raw or "unknown")).strip(".")
    return cleaned or "unknown"


def _write_fallback(run_dir: Path, status: str, errors: list[str]) -> str | None:
    """Last resort: a plain report so that every path still ends with a report file."""
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "report.md"
        lines = ["# Test Run Report", "", f"**Status:** {status}", "", "## System errors", ""]
        lines += [f"- {e}" for e in errors] or ["- unknown"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return str(path)
    except OSError:
        return None


def run_report(state: Mapping[str, Any], *, runs_root: Path = PROJECT_ROOT / "runs") -> dict[str, Any]:
    """LangGraph node. Returns a partial state update and never raises."""
    run_dir = Path(runs_root) / _safe_run_id(state.get("run_id"))
    try:
        model = build_report_model(state)
        path = write_reports(model, run_dir)
        return {"terminal_status": model["terminal_status"], "report_path": str(path)}
    except Exception as exc:  # node invariant: catch into state.errors, the report still runs
        logger.exception("report node failed")
        errors = [*(str(e) for e in state.get("errors") or []), f"report: {redact(str(exc))}"]
        return {
            "terminal_status": "ERROR",  # the system itself broke
            "report_path": _write_fallback(run_dir, "ERROR", [redact(e) for e in errors]),
            "errors": errors,
        }

# """Export a ReportModel to Markdown using the existing report template."""

# from datetime import datetime, timezone
# from pathlib import Path

# from report.model import ReportModel


# def _get_value(obj, key, default=None):
#     if isinstance(obj, dict):
#         return obj.get(key, default)
#     return getattr(obj, key, default)


# def _render_markdown(report_model, generated_at):
#     """Render the current report model without requiring Jinja2."""
#     scenarios = _get_value(report_model, "scenarios", []) or []
#     models_used = _get_value(report_model, "models_used", {}) or {}
#     errors = _get_value(report_model, "errors", []) or []
#     defects = _get_value(report_model, "defect_candidates", []) or []

#     lines = [
#         "# AI Test Run Report",
#         "",
#         f"**Run ID:** {_get_value(report_model, 'run_id', 'unknown')}",
#         f"**Status:** {_get_value(report_model, 'terminal_status', 'ERROR')}",
#         f"**URL:** {_get_value(report_model, 'target_url') or 'N/A'}",
#         f"**Duration:** {float(_get_value(report_model, 'duration_seconds') or 0):.1f}s",
#         f"**Generated:** {generated_at}",
#         "",
#         "---",
#         "",
#         "## Requirements",
#         "",
#         f"> {_get_value(report_model, 'requirements', '')}",
#         "",
#         "---",
#         "",
#         "## Summary",
#         "",
#         "| Metric | Value |",
#         "|---|---|",
#         f"| Terminal status | **{_get_value(report_model, 'terminal_status', 'ERROR')}** |",
#         f"| Total scenarios | {len(scenarios)} |",
#         f"| Generation attempts | {_get_value(report_model, 'generation_attempts', 0)} |",
#         f"| Heal attempts | {_get_value(report_model, 'heal_attempts', 0)} |",
#         "",
#         "---",
#         "",
#         "## Scenario Results",
#         "",
#         "| Scenario | Status | Failure type | Subtype | Root cause |",
#         "|---|---|---|---|---|",
#     ]

#     for scenario in scenarios:
#         values = [
#             _get_value(scenario, "name", "Unnamed"),
#             _get_value(scenario, "status", "BLOCKED"),
#             _get_value(scenario, "failure_type") or "—",
#             _get_value(scenario, "subtype") or "—",
#             _get_value(scenario, "root_cause") or "—",
#         ]
#         values = [str(value).replace("|", "\\|").replace("\n", " ") for value in values]
#         lines.append("| " + " | ".join(values) + " |")

#     lines.extend(["", "---", "", "## Models Used", ""])

#     for agent, model in models_used.items():
#         lines.append(f"- **{agent}**: `{model}`")

#     if defects:
#         lines.extend(["", "---", "", "## Defect Candidates", ""])
#         lines.extend(f"- {item}" for item in defects)

#     if errors:
#         lines.extend(["", "---", "", "## Errors", ""])
#         lines.extend(f"- `{item}`" for item in errors)

#     lines.extend([
#         "",
#         "---",
#         "",
#         "*AI Test Automation · Application code is never changed automatically.*",
#         "",
#     ])

#     return "\n".join(lines)


# def export_markdown(report_model, run_dir):
#     """Write report.md and return its absolute path."""
#     output_dir = Path(run_dir)
#     output_dir.mkdir(parents=True, exist_ok=True)

#     generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
#     content = _render_markdown(report_model, generated_at)

#     report_path = output_dir / "report.md"
#     report_path.write_text(content, encoding="utf-8")

#     return str(report_path.resolve())


# def export_report(report_model):
#     """Export Markdown to runs/<run_id>/report.md."""
#     run_id = str(_get_value(report_model, "run_id", "unknown"))
#     run_dir = Path("runs") / run_id
#     return export_markdown(report_model, run_dir)
