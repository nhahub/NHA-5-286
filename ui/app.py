"""Responsive Gradio 6 dashboard for AI assisted test automation."""

from __future__ import annotations
import html
import os
import re
import textwrap
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape
import gradio as gr

from uuid import uuid4
from langgraph.types import Command
from graph.build_graph import build_graph
from llm.settings import (
    LLMSettings, check_static, effective_key, register_run_credentials, release_run_credentials, validate_settings,
)



ROOT = Path(__file__).resolve().parents[1]

WORKFLOW = build_graph()


EXPORT_DIR = ROOT / "runs" / "mock_reports"



THEMES = {

    "Light": {"bg": "#f3f6fc", "surface": "#ffffff", "surface2": "#f8fafe", "text": "#142641", "muted": "#5a6e8c", "line": "#d3deef", "accent": "#2867d9", "soft": "#e8f0ff"},

    "Blue": {"bg": "#0c1424", "surface": "#14243e", "surface2": "#10213a", "text": "#e8efff", "muted": "#aebfdf", "line": "#315280", "accent": "#5b91ff", "soft": "#1a3157"},

    "Dark": {"bg": "#0d1016", "surface": "#151e2c", "surface2": "#101a29", "text": "#edf1f7", "muted": "#aebbd0", "line": "#33496a", "accent": "#7096ff", "soft": "#202e4e"},

}



CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
:root {--app-gap:14px;--app-card-pad:20px}
html,body {margin:0!important; overflow-x:hidden!important}
/* Gradio adds nested wrappers with their own padding/min-height, which caused extra scrolling. */
.gradio-container > .main, .gradio-container > .main > .wrap, .gradio-container .contain {
 padding:0!important;min-height:0!important;height:auto!important;gap:0!important}
.gradio-container .main .wrap, .gradio-container .fillable {padding:0!important}
.gradio-container .app {padding:0!important;min-height:0!important}
body,.gradio-container {background:var(--app-bg)!important;color:var(--app-text)!important;font-family:'DM Sans',sans-serif!important}
.gradio-container {max-width:100%!important;padding:0!important;min-height:100vh!important}
/* Gradio can vertically center its outer layout; force an ordinary top-aligned document flow. */
.gradio-container, .gradio-container > .main, .gradio-container > .main > .wrap, .gradio-container .contain,
.gradio-container .gap, .gradio-container .app, .gradio-container .app-shell {
 align-content:start!important;justify-content:flex-start!important;
}
.app-shell {width:100%!important;max-width:none!important;box-sizing:border-box!important;padding:20px 20px 20px!important;
 min-height:0!important;height:auto!important;margin:0!important;gap:0!important;align-self:start!important;
 background:var(--app-bg)!important}
#user-request-page {margin:0!important;padding:0!important;min-height:0!important;gap:0!important;justify-content:flex-start!important}
#request-layout {margin:0!important;padding:0!important;gap:14px!important;align-items:start!important;
 display:grid!important;grid-template-columns:var(--request-layout-columns,minmax(0,7fr) minmax(0,3fr))!important}
#request-card-column,#progress-card-column {margin:0!important;padding:0!important;min-width:0!important;
 width:auto!important;max-width:none!important;flex:none!important;gap:0!important;align-self:start!important}
.card {background:var(--app-surface)!important;color:var(--app-text)!important;
 border:1px solid var(--app-line)!important;border-radius:16px!important;padding:20px!important;
 box-shadow:0 2px 10px rgba(12,30,55,.05)!important;margin:0 0 14px!important;min-width:0!important;overflow:visible!important}
#request-layout .card {margin:0!important}
/* gr.Group nests a second .card wrapper; style only the outer one. */
.card .card {border:0!important;padding:0!important;box-shadow:none!important;background:transparent!important;margin:0!important}
.gradio-container .fillable,.gradio-container .app {max-width:none!important;width:100%!important;margin:0!important}
.card > .styler, .card > div {gap:10px!important}
.page-head h1 {color:var(--app-text)!important}
.metric {flex:1 1 140px}
.card .dataframe, .card [data-testid=dataframe], .card .table-wrap {background:var(--app-surface)!important;border-color:var(--app-line)!important}
.card .prose, .card .prose * {color:var(--app-text)!important}
.card-title {font-size:18px;font-weight:700;margin:0 0 4px;color:var(--app-text)!important}
.muted,.card .muted,.page-head p {color:var(--app-muted)!important;font-size:12px!important;line-height:1.4!important}
.card .form, .card .styler,.card .block.padded {background:transparent!important;border-color:transparent!important;box-shadow:none!important}
.card label,.card label span,.card span,.card .prose {color:var(--app-text)!important}
.card input:not([type=radio]):not([type=checkbox]),.card textarea,
.card [role=combobox],.card [data-testid=dropdown],.card select,
.card .secondary-wrap,.card .wrap, .card .input-container {
 background:var(--app-surface2)!important;color:var(--app-text)!important;border-color:var(--app-line)!important;
 box-shadow:none!important}
.card input::placeholder,.card textarea::placeholder {color:var(--app-muted)!important;opacity:1!important}
.card input:not([type=radio]):not([type=checkbox]),.card textarea {padding:9px 12px!important}
.card [role=combobox] {padding:7px 10px!important;min-height:39px!important}
.card [role=combobox] *, .card [data-testid=dropdown] * {color:var(--app-text)!important}
/* The old gray blocks are Gradio radio/dropdown/checkbox wrappers, not card backgrounds. */
.card label:has(input[type=radio]),.card label:has(input[type=checkbox]),
.card .radio-group label,.card .checkbox-group label,
.card [role=radiogroup] label,.card .radio-group,.card .checkbox-group {
 background:transparent!important;color:var(--app-text)!important;border-color:transparent!important;
 box-shadow:none!important}
.card label:has(input[type=radio]:checked),.card [role=radiogroup] label:has(input:checked) {
 background:var(--app-soft)!important;color:var(--app-accent)!important;border:1px solid var(--app-line)!important}
.card input[type=radio],.card input[type=checkbox],.card input[type=range] {accent-color:var(--app-accent)!important}
.card button.secondary,.card button[aria-label*=Reset] {background:var(--app-soft)!important;color:var(--app-text)!important;border-color:var(--app-line)!important}
#browser-control {min-width:0!important}
#browser-control .wrap,#browser-control [role=combobox],#browser-control [data-testid=dropdown] {background:var(--app-surface2)!important;box-shadow:none!important}
/* Controls use a clear two-column grid, no narrow triple-column label wrapping. */
#scenario-controls {gap:10px!important;align-items:start!important;margin-top:4px!important}
#scenario-controls > .form {display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;
 gap:10px 20px!important;align-items:start!important;min-width:0!important;width:100%!important}
#scenario-controls > .form > * {min-width:0!important;width:100%!important;max-width:none!important;flex:none!important;margin:0!important}
#scenario-controls label {font-size:13px!important}
#execution-mode-control {margin-top:0!important}
#execution-mode-control .wrap {background:transparent!important}
#start-testing {width:100%!important;background:var(--app-accent)!important;color:#fff!important;border:0!important;min-height:42px!important}
.step {display:flex;align-items:center;padding:8px 10px;border:1px solid var(--app-line);border-radius:8px;margin:4px 0;
 background:var(--app-surface2);color:var(--app-text)!important;font-size:12px;line-height:1.25}
.step-dot {display:inline-block;flex:none;width:8px;height:8px;border-radius:50%;background:#95a0b2;margin-right:8px}
.step-status {margin-left:auto;color:var(--app-muted);padding-left:10px;text-align:right;white-space:normal;flex:0 1 auto;min-width:0}
.step > .step-name {flex:1 1 auto;min-width:0}
.metric {min-width:0;overflow-wrap:anywhere}
.status-running .step-dot {background:var(--app-accent)}.status-completed .step-dot {background:#27ae80}
.status-failed .step-dot {background:#d94f5c}.status-waiting-for-approval .step-dot {background:#e8a33d}.status-skipped .step-dot {background:#d5a642}
.page-head {margin:0 0 12px}.page-head h1{margin:0 0 4px;font-size:23px}
.metric {background:var(--app-surface);border:1px solid var(--app-line);border-radius:12px;padding:15px}
.metric-value{font-size:23px;font-weight:700}.metric-label{font-size:11px;color:var(--app-muted);margin-top:3px}
.status-note{padding:12px 14px;background:var(--app-soft);border:1px solid var(--app-line);border-radius:10px;color:var(--app-text)}
/* Simple full-width sidebar navigation with a narrow active indicator, no radio pills. */
/* App frame: a grid of [sidebar | content]; collapsing only changes --sb-w so content reflows. */
#app-layout {display:grid!important;grid-template-columns:var(--sb-w,216px) minmax(0,1fr)!important;gap:0!important;
 align-items:start!important;margin:0!important;padding:0!important;flex-wrap:nowrap!important;width:100%!important;max-width:100%!important}
#app-layout > * {min-width:0!important;max-width:none!important;flex:none!important}
#app-sidebar {background:var(--app-surface)!important;color:var(--app-text)!important;border-right:1px solid var(--app-line)!important;
 width:var(--sb-w,216px)!important;padding:20px 12px!important;box-sizing:border-box!important;gap:0!important;
 position:sticky!important;top:0!important;height:100vh!important;overflow-y:auto!important;overflow-x:hidden!important;align-self:start!important}
#app-sidebar > * {background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important;margin:0!important}
#sidebar-toggle {min-width:0!important;width:100%!important;margin:0 0 10px!important;padding:6px 0!important;min-height:34px!important;
 background:var(--app-soft)!important;color:var(--app-text)!important;border:1px solid var(--app-line)!important;border-radius:8px!important}
.sb-short {display:none}
.sidebar-project-title {font-size:17px;font-weight:700;letter-spacing:-.3px;line-height:1.3;
 padding:0 12px 16px;margin:0 0 14px;border-bottom:1px solid var(--app-line);color:var(--app-text)!important}
#sidebar-navigation,#sidebar-navigation .form,#sidebar-navigation .wrap,#sidebar-navigation .radio-group {
 background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important;gap:3px!important}
#sidebar-navigation [data-testid=block-info],#sidebar-navigation .label-wrap{display:none!important}
#sidebar-navigation label {display:flex!important;align-items:center!important;width:100%!important;min-height:44px!important;
 box-sizing:border-box!important;white-space:nowrap!important;line-height:1.2!important;
 padding:11px 12px!important;margin:0!important;border:0!important;border-left:3px solid transparent!important;
 background:transparent!important;color:var(--app-muted)!important;border-radius:7px!important;
 font-size:13px!important;font-weight:600!important;box-shadow:none!important}
#sidebar-navigation label:hover {background:var(--app-soft)!important;color:var(--app-text)!important}
#sidebar-navigation label:has(input:checked) {background:var(--app-soft)!important;
 color:var(--app-accent)!important;border-left-color:var(--app-accent)!important}
#sidebar-navigation label:has(input:checked) span {color:var(--app-accent)!important}
#sidebar-navigation input[type=radio]{position:absolute!important;opacity:0!important;width:1px!important;height:1px!important}
.session-mode{font-size:12px;color:var(--app-muted);margin:20px 12px 0;padding-top:15px;border-top:1px solid var(--app-line)}
.session-mode b{color:var(--app-text)!important}
button.primary {background:var(--app-accent)!important;color:white!important}
footer{display:none!important}
/* Style-injection blocks must not take layout space (they caused the gap above the cards). */
.style-holder {display:none!important;margin:0!important;padding:0!important;height:0!important;min-height:0!important;border:0!important}
#scenario-controls label,#scenario-controls span {white-space:nowrap}
#execution-mode-control .wrap {flex-wrap:nowrap!important}
@media(max-width:1100px){#request-layout{--request-layout-columns:minmax(0,1fr)!important}}
@media(max-width:767px){.app-shell{padding:12px!important}
 #app-layout {grid-template-columns:minmax(0,1fr)!important}
 #app-sidebar {position:relative!important;width:100%!important;height:auto!important}
 #scenario-controls > .form {grid-template-columns:minmax(0,1fr)!important}}
"""

STAGES = ["Intake", "Planner", "Code Generator", "Validation", "Execution", "Evidence Collection", "Analyzer", "Fix Proposal", "Human Approval", "Apply Fix (Healing)", "Report Generation"]

STATUS_LABELS = {"waiting for approval": "Waiting for Approval"}

STAGE_STATUSES = {"not run", "running", "waiting for approval", "completed", "failed", "skipped"}





def theme_css(theme: str) -> str:

    c = THEMES.get(theme, THEMES["Blue"])

    values = ";".join(f"--app-{key}:{value}" for key, value in c.items())

    values += ";--app-gap:12px;--app-card-pad:14px;--app-sidebar-width:230px"

    # Map the palette onto Gradio's own variables so every built-in component (tables, sliders,
    # file drop zone, markdown, sidebar) follows the selected theme, in light and dark.
    gradio_vars = (
        f"--body-background-fill:{c['bg']};--background-fill-primary:{c['surface']};--background-fill-secondary:{c['soft']};"
        f"--block-background-fill:{c['surface']};--block-border-color:{c['line']};--border-color-primary:{c['line']};"
        f"--body-text-color:{c['text']};--body-text-color-subdued:{c['muted']};--block-label-text-color:{c['muted']};"
        f"--block-title-text-color:{c['text']};--block-info-text-color:{c['muted']};--input-background-fill:{c['surface2']};"
        f"--input-border-color:{c['line']};--input-placeholder-color:{c['muted']};--panel-background-fill:{c['surface']};"
        f"--table-even-background-fill:{c['surface']};--table-odd-background-fill:{c['surface2']};--table-border-color:{c['line']};"
        f"--table-row-focus:{c['soft']};--button-secondary-background-fill:{c['soft']};--button-secondary-text-color:{c['text']};"
        f"--button-secondary-border-color:{c['line']};--checkbox-background-color:{c['surface2']};--checkbox-border-color:{c['line']};"
        f"--neutral-100:{c['soft']};--color-accent:{c['accent']};--slider-color:{c['accent']};--shadow-drop:none;"
        f"color-scheme:{'light' if theme == 'Light' else 'dark'}"
    )
    selector = "html:root, html body, html body.dark, html .dark, html .gradio-container"
    return f"<style>:root{{{values}}} {selector}{{{values};{gradio_vars}}}</style>"





def request_layout_css(show_progress: bool) -> str:

    columns = "minmax(0,7fr) minmax(0,3fr)" if show_progress else "minmax(0,1fr)"

    return f"<style>#request-layout{{--request-layout-columns:{columns}!important}}@media(max-width:1100px){{#request-layout{{--request-layout-columns:minmax(0,1fr)!important}}}}</style>"





NAV_FULL = [("▦  User Request", "User Request"), ("▤  Reports", "Results & Reports"), ("⚙  Settings", "Settings")]

NAV_ICONS = [("▦", "User Request"), ("▤", "Results & Reports"), ("⚙", "Settings")]





def toggle_sidebar(collapsed: bool, page: str):

    """Switch between the full menu and a narrow icon-only rail; content reflows via --sb-w."""

    collapsed = not collapsed

    style = ("<style>#app-layout{--sb-w:64px}#app-sidebar{padding:20px 8px!important}.sb-full,.session-mode{display:none!important}"
             ".sb-short{display:inline!important}.sidebar-project-title{text-align:center;padding:0 0 12px!important}"
             "#sidebar-navigation label{justify-content:center!important;padding:11px 0!important}</style>") if collapsed else ""

    return (collapsed, style, gr.update(choices=NAV_ICONS if collapsed else NAV_FULL, value=page),
            gr.update(value="▶" if collapsed else "◀"))





def progress_visibility(show_progress: bool) -> tuple[gr.update, str]:

    shown = bool(show_progress)

    return gr.update(visible=shown), request_layout_css(shown)





def render_progress(statuses: dict[str, str] | None = None, notes: dict[str, str] | None = None) -> str:

    statuses = statuses or {}

    notes = notes or {}

    markup = []

    for stage in STAGES:

        raw_status = str(statuses.get(stage, "Not run")).strip().lower()

        status = raw_status if raw_status in STAGE_STATUSES else "not run"

        markup.append(

            f"<div class='step status-{status.replace(' ', '-')}'><span class='step-dot'></span>"

            f"<span class='step-name'>{html.escape(stage)}</span><span class='step-status'>{STATUS_LABELS.get(status, status.title())}{html.escape(' · ' + notes[stage]) if notes.get(stage) else ''}</span></div>"

        )

    return "".join(markup)





def metric_card(value: str, label: str) -> str:

    return f"<div class='metric'><div class='metric-value'>{html.escape(value)}</div><div class='metric-label'>{html.escape(label)}</div></div>"





def set_theme(theme: str) -> tuple[str, str]:

    return theme_css(theme), theme





def navigate(page: str) -> tuple[gr.update, gr.update, gr.update]:

    return (gr.update(visible=page == "User Request"), gr.update(visible=page == "Results & Reports"), gr.update(visible=page == "Settings"))





def session_mode_label(use_mock: bool) -> str:

    mocking_enabled = use_mock is True or str(use_mock).strip().lower() in {"true", "1", "yes", "on"}

    mode = "Mock mode (simulated, no real LLM)" if mocking_enabled else "Live mode (real agents only)"

    return f"<div class='session-mode'>Session mode<br><b>{mode}</b></div>"





def save_llm_settings(provider: str, model: str, api_key: str) -> tuple[str, dict]:

    """Validate the credentials with a real provider call, then keep them for this UI session only."""

    ok, message = validate_settings(provider, model or "", api_key or "")

    # Session-scoped only. Never expose this dict in report content, logs, or component values.
    state = {"provider": provider, "model": (model or "").strip(), "api_key": api_key or "", "validated": ok}

    if not ok:
        return f"**Not validated — live mode is unavailable with these settings.**\n\n{message}", state

    return f"**Validated.** {message} The API key stays masked, session-only, and is not exported.", state





def scenario_details(run: dict | None, evt: gr.SelectData) -> str:

    if not run or evt.index is None:

        return "Select a scenario row to inspect its details."

    index = evt.index[0] if isinstance(evt.index, (tuple, list)) else evt.index

    if not isinstance(index, int) or index >= len(run["scenarios"]):

        return "Select a scenario row to inspect its details."

    s = run["scenarios"][index]

    fields = [("Test Steps", "\n".join(f"{i}. {step}" for i, step in enumerate(s["Test Steps"], 1))),

              ("Expected Result", s["Expected Result"]), ("Actual Result", s["Actual Result"]),

              ("Error Message", s["Error Message"]), ("Screenshot / Evidence", s["Evidence Path"]),

              ("Analysis", s["Analysis"]), ("Proposed Fix", s["Proposed Fix"])]

    return "\n\n".join(f"### {name}\n{value}" for name, value in fields)





def _report_notice(run: dict) -> str:
    if run["simulated"]:
        return "SIMULATED mock run: agents, browser execution, and fixes are mocks. This is not a real test result."
    return "Live run."


def _report_facts(run: dict) -> list[tuple[str, str]]:
    models = ", ".join(f"{k}: {v}" for k, v in run["models_used"].items()) or "none recorded"
    return [("Run ID", run["run_id"]), ("Mode", run["mode"]), ("Created", run["created_at"]),
            ("Application URL", run["url"]), ("Requirements", run["requirements"]),
            ("Browser", f"{run['browser']} / {run['execution_mode']}"), ("Terminal status", run["terminal_status"]),
            ("Total scenarios", str(len(run["scenarios"]))), ("Passed", str(run["passed"])), ("Failed", str(run["failed"])),
            ("Skipped / not run", str(run["skipped"])), ("Execution time", run["execution_time"] + (" (simulated)" if run["simulated"] and run["execution_time"][0].isdigit() else "")),
            ("Healing attempts", f"{run['healing_attempts']} of {MAX_HEALING}"), ("Models used", models),
            ("Executed nodes", " > ".join(run["trail"]) or "none")]


def preview_report(run: dict | None) -> str:
    if not run:
        return "No run is selected. Start a test first."
    lines = [f"# Test Run Report — {run['run_id']}", f"> {_report_notice(run)}", ""]
    lines += [f"**{label}:** {value}  " for label, value in _report_facts(run)]
    lines += ["", "## Scenario results", "| ID | Scenario | Status | Duration | Error summary |", "|---|---|---|---|---|"]
    lines.extend(f"| {s['Scenario ID']} | {s['Scenario Name']} | {s['Status']} | {s['Duration']} | {s['Error Summary']} |"
                 for s in run["scenarios"])
    for s in run["scenarios"]:
        lines += ["", f"### {s['Scenario ID']} — {s['Scenario Name']} ({s['Status']})",
                  f"**Evidence**  \n{s['Evidence Path']}", f"**Analysis**  \n{s['Analysis']}", f"**Proposed fix**  \n{s['Proposed Fix']}"]
    if run["workflow_error"]:
        lines += ["", f"**Workflow error:** {run['workflow_error']}"]
    return "\n".join(lines)


def _safe(value: object) -> str:
    return str(value if value is not None else "")


def _plain_lines(run: dict) -> list[str]:
    """Report text without Markdown markup, shared by the PDF and Word writers."""
    lines = [f"Test Run Report - {run['run_id']}", _report_notice(run), ""]
    lines += [f"{label}: {value}" for label, value in _report_facts(run)]
    lines += ["", "Scenario results"]
    for s in run["scenarios"]:
        lines += [f"{s['Scenario ID']} | {s['Scenario Name']} | {s['Status']} | {s['Duration']} | {s['Error Summary']}",
                  "Evidence: " + s["Evidence Path"].replace("\n", "; "),
                  "Analysis: " + re.sub(r"\s+", " ", s["Analysis"]),
                  "Proposed fix: " + re.sub(r"[`\n]+", " ", s["Proposed Fix"])]
    if run["workflow_error"]:
        lines += ["", "Workflow error: " + re.sub(r"[*`]", "", run["workflow_error"])]
    return lines


def _write_pdf(path: Path, run: dict) -> None:
    """Write a small standards-compliant, text-only PDF without a runtime dependency."""
    text_lines: list[str] = []
    for line in _plain_lines(run):
        text_lines += textwrap.wrap(line, 90) or [""]
    pages = [text_lines[i:i + 48] for i in range(0, len(text_lines), 48)] or [[]]
    objects: list[bytes] = []
    page_ids = [4 + 2 * i for i in range(len(pages))]
    font_id = 3
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(("<< /Type /Pages /Kids [" + " ".join(f"{i} 0 R" for i in page_ids) + f"] /Count {len(pages)} >>").encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, page in enumerate(pages):
        page_id, content_id = 4 + 2*i, 5 + 2*i
        stream = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
        for line in page:
            ascii_line = line.encode("ascii", "replace").decode().replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream += [f"({ascii_line}) Tj", "T*"]
        stream.append("ET")
        payload = "\n".join(stream).encode("ascii")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode())
        objects.append(b"<< /Length " + str(len(payload)).encode() + b" >>\nstream\n" + payload + b"\nendstream")
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data)); data += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(data); data += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]: data += f"{offset:010d} 00000 n \n".encode()
    data += f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    path.write_bytes(data)


def _write_docx(path: Path, run: dict) -> None:
    paragraphs = _plain_lines(run)
    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{escape(p)}</w:t></w:r></w:p>' for p in paragraphs)
    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'''
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as doc:
        doc.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        doc.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        doc.writestr("word/document.xml", document)


def export_report(run: dict | None, format_name: str) -> tuple[str, str | None]:
    if not run:
        return "Run a test before exporting.", None
    if format_name not in {"PDF", "Word (.docx)", "Excel (.xlsx)"}:
        return "Choose PDF, Word, or Excel before exporting.", None
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", run["run_id"])
    if format_name == "Excel (.xlsx)":
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill
        except ImportError:
            return "Excel export requires openpyxl. Install it with `pip install openpyxl`.", None
        path = EXPORT_DIR / f"{stem}.xlsx"
        book = Workbook(); summary = book.active; summary.title = "Summary"
        summary.append(["Field", "Value"])
        summary.append(["Notice", _report_notice(run)])
        for row in _report_facts(run): summary.append(list(row))
        scenarios = book.create_sheet("Scenarios"); scenarios.append(["Scenario ID", "Scenario Name", "Status", "Duration", "Error Summary"])
        for s in run["scenarios"]: scenarios.append([s[k] for k in ["Scenario ID", "Scenario Name", "Status", "Duration", "Error Summary"]])
        failures = book.create_sheet("Failure Analysis"); failures.append(["Scenario ID", "Scenario Name", "Analysis", "Error Message", "Evidence", "Proposed Fix"])
        for s in run["scenarios"]: failures.append([s["Scenario ID"], s["Scenario Name"], s["Analysis"], s["Error Message"], s["Evidence Path"], s["Proposed Fix"]])
        for sheet in book.worksheets:
            sheet.freeze_panes = "A2"; sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]: cell.font = Font(bold=True, color="FFFFFF"); cell.fill = PatternFill("solid", fgColor="315EA8")
            for col in sheet.columns:
                width = min(60, max(14, max(len(_safe(c.value)) for c in col) + 2)); sheet.column_dimensions[col[0].column_letter].width = width
        book.save(path)
    elif format_name == "Word (.docx)":
        path = EXPORT_DIR / f"{stem}.docx"; _write_docx(path, run)
    else:
        path = EXPORT_DIR / f"{stem}.pdf"; _write_pdf(path, run)
    return f"Exported {format_name} report for {run['run_id']}.", str(path)


# ----------------------------------------------------------------------------- workflow
MAX_HEALING = 2

NODE_STAGE = {
    "intake": "Intake", "planner": "Planner", "codegen": "Code Generator", "validate": "Validation",
    "execute": "Execution", "analyze": "Analyzer", "fix_proposal": "Fix Proposal",
    "fix_approval": "Human Approval", "apply_fix": "Apply Fix (Healing)", "report": "Report Generation",
}


class StageTracker:
    """Per-run stage status derived only from LangGraph node events (no static previews)."""

    def __init__(self) -> None:
        self.status = {stage: "Not run" for stage in STAGES}
        self.count = {stage: 0 for stage in STAGES}
        self.note: dict[str, str] = {}
        self.errors_seen = 0
        self.history: list[dict] = []  # every pass through every stage, kept across retries/reruns

    ACTIVE = ("Running", "Waiting for Approval")

    def _set(self, stage: str, status: str, note: str | None = None) -> None:
        self.status[stage] = status
        if note is not None:
            self.note[stage] = note
        if status == "Skipped" or not self.count[stage]:
            return
        entry = next((h for h in reversed(self.history) if h["stage"] == stage and h["pass"] == self.count[stage]), None)
        if entry is None:
            entry = {"stage": stage, "pass": self.count[stage], "status": status, "note": ""}
            self.history.append(entry)
        entry["status"] = status
        if note is not None:
            entry["note"] = note

    def begin(self, node: str, note: str | None = None) -> None:
        stage = NODE_STAGE.get(node)
        if stage is None:
            return
        if self.status[stage] not in self.ACTIVE:
            self.count[stage] += 1  # a revisit (re-validation, rerun, second analysis) is a new pass
        waiting = note == "awaiting decision"
        self._set(stage, "Waiting for Approval" if waiting else "Running", note or "")
        if node == "execute":
            if self.status["Evidence Collection"] not in self.ACTIVE:
                self.count["Evidence Collection"] += 1
            self._set("Evidence Collection", "Running", "")

    def finish(self, node: str, update: dict) -> None:
        stage = NODE_STAGE.get(node)
        if stage is None:
            return
        if self.status[stage] not in self.ACTIVE:
            self.begin(node)
        terminal = update.get("terminal_status")
        failed, note = False, ""
        if node == "intake" and terminal in ("BLOCKED", "ERROR"):
            failed, note = True, terminal
        elif node == "validate" and update.get("validation_status") == "invalid":
            failed, note = True, "invalid"
        elif node == "execute":
            failed, note = terminal != "PASS", terminal or ""
        elif node == "apply_fix":
            failed = terminal == "FAIL"
            note = "not applied" if failed else f"attempt {update.get('healing_retry_count', '?')} of {MAX_HEALING}"
        elif node == "fix_approval":
            note = str(update.get("approval_decision") or "")
        elif node == "analyze":
            note = str(update.get("failure_type") or "")
        errors = update.get("errors")
        if isinstance(errors, list):
            if len(errors) > self.errors_seen:
                failed, note = True, (note or "error")
            self.errors_seen = max(self.errors_seen, len(errors))
        self._set(stage, "Failed" if failed else "Completed", note)
        if node == "execute":
            has_evidence = bool(update.get("execution_evidence"))
            self._set("Evidence Collection", "Completed" if has_evidence else "Skipped",
                      "" if has_evidence else "no evidence")

    def fail_running(self, reason: str) -> None:
        for stage, status in self.status.items():
            if status in self.ACTIVE:
                self._set(stage, "Failed", reason)

    def finalize(self) -> None:
        for stage, status in self.status.items():
            if status == "Not run":
                self.status[stage] = "Skipped"

    def view(self) -> tuple[dict[str, str], dict[str, str]]:
        notes = {}
        for stage in STAGES:
            parts = ["" if self.note.get(stage) == "awaiting decision" else self.note.get(stage, "")]
            if self.count[stage] > 1:
                parts.append(f"×{self.count[stage]}")
            notes[stage] = " ".join(p for p in parts if p)
        return dict(self.status), notes


RUNS: dict[str, dict] = {}  # thread_id -> UI-side run info; graph state itself lives in the checkpointer
_RUNS_LOCK = threading.Lock()
NOOP = gr.update()


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _scrub(text: object, info: dict | None) -> str:
    """Remove any API key from a message before it reaches the UI."""
    text = str(text)
    key = (info or {}).get("secret") or ""
    return text.replace(key, "***") if key else text


def _pending_interrupt(thread_id: str) -> dict | None:
    """The approval request this run is actually paused on, read from the checkpoint."""
    try:
        snapshot = WORKFLOW.get_state(_config(thread_id))
    except Exception:
        return None
    for task in snapshot.tasks:
        for item in task.interrupts:
            return dict(item.value) if isinstance(item.value, dict) else {"message": str(item.value)}
    return None


def _trail_label(node: str, update: dict) -> str:
    detail = None
    if node == "execute":
        detail = update.get("terminal_status")
    elif node == "validate":
        detail = update.get("validation_status")
    elif node == "analyze":
        detail = update.get("failure_type")
    elif node == "fix_approval":
        detail = update.get("approval_decision")
    elif node == "apply_fix" and "healing_retry_count" in update:
        detail = f"attempt {update['healing_retry_count']}"
    return f"{node} ({detail})" if detail else node


def _advance(thread_id: str, graph_input):
    """Drive the real graph one event at a time, updating the tracker; yields after each event."""
    info = RUNS[thread_id]
    tracker = info["tracker"]
    try:
        # "tasks" events say which node has really started; "updates" events carry what it returned.
        for mode, data in WORKFLOW.stream(graph_input, config=_config(thread_id), stream_mode=["tasks", "updates"]):
            if mode == "tasks":
                if "input" in data:
                    tracker.begin(data["name"])
                elif data.get("interrupts"):
                    tracker.begin(data["name"], "awaiting decision")
            else:
                for node, update in data.items():
                    if node == "__interrupt__":
                        continue
                    update = update or {}
                    tracker.finish(node, update)
                    info["trail"].append(_trail_label(node, update))
            yield
    except NotImplementedError as exc:
        stage = next((s for s, st in tracker.status.items() if st in tracker.ACTIVE), "a stage")
        info["error"] = (f"The live workflow stopped at **{stage}**: {_scrub(exc, info)} "
                         "No mock data was substituted.")
        tracker.fail_running("not implemented")
    except Exception as exc:
        info["error"] = f"{type(exc).__name__}: {_scrub(exc, info)}"
        tracker.fail_running("error")
    info["paused"] = info.get("error") is None and _pending_interrupt(thread_id) is not None
    if info["paused"]:
        tracker.begin("fix_approval", "awaiting decision")
    if not info["paused"]:
        tracker.finalize()
        info["ended"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        release_run_credentials(thread_id)
        info["secret"] = ""


def _snapshot_values(thread_id: str) -> dict:
    try:
        return dict(WORKFLOW.get_state(_config(thread_id)).values or {})
    except Exception:
        return {}


def _status_text(thread_id: str) -> str:
    info, values = RUNS[thread_id], _snapshot_values(thread_id)
    healing = values.get("healing_retry_count", 0)
    if info.get("error"):
        return f"### Workflow stopped\n{info['error']}"
    if info.get("paused"):
        return f"Workflow paused for human approval. Healing attempts used so far: {healing} of {MAX_HEALING}."
    label = "SIMULATED" if info["mock"] else "LIVE"
    return (f"Workflow completed: {values.get('terminal_status', 'UNKNOWN')} ({label}). "
            f"Healing attempts used: {healing} of {MAX_HEALING}.")


def _progress_html(thread_id: str) -> str:
    tracker = RUNS[thread_id]["tracker"]
    markup = render_progress(*tracker.view())
    passes = [h for h in tracker.history if tracker.count[h["stage"]] > 1]
    if passes:  # only stages that were repeated need a history; the rows above show the latest pass
        items = "".join(f"<div>{html.escape(h['stage'])} #{h['pass']}: {html.escape(h['status'])}"
                        f"{html.escape(' · ' + h['note']) if h['note'] else ''}</div>" for h in passes)
        markup += f"<div class='muted' style='margin-top:10px'><b>Pass history</b>{items}</div>"
    return markup


def approval_ui(session: dict | None):
    """Approve/Reject panel for the run's real pending interrupt (or hidden when none)."""
    payload = _pending_interrupt(session["thread_id"]) if session and session.get("thread_id") in RUNS else None
    if not payload:
        return gr.update(value="", visible=False), gr.update(visible=False)
    values = _snapshot_values(session["thread_id"])
    analysis = values.get("failure_analysis") or {}
    used = values.get("healing_retry_count", 0)
    subtype = f" / {analysis['subtype']}" if analysis.get("subtype") else ""
    details = (
        "### Human Fix Approval Required\n\n"
        f"**Healing attempt:** {used + 1} of {MAX_HEALING}\n\n"
        f"**Failure analysis:** {analysis.get('failure_type', '?')}{subtype} — {analysis.get('root_cause', 'n/a')}\n\n"
        f"**Risky:** {payload.get('risky')}\n\n"
        f"**Reason:** {payload.get('reason')}\n\n"
        "**Proposed Patch:**\n\n```diff\n" f"{payload.get('patch_diff', '')}\n```"
    )
    return gr.update(value=details, visible=True), gr.update(visible=True)


def _view(thread_id: str | None, status: str, session=NOOP, history=NOOP):
    """One UI frame: [status, session, progress, approval_details, approval_buttons, return_btn, history]."""
    if thread_id is None:
        return status, session, NOOP, NOOP, NOOP, NOOP, history
    details, buttons = approval_ui({"thread_id": thread_id})
    return status, session, _progress_html(thread_id), details, buttons, gr.update(visible=True), history


def start_graph_workflow(url, requirements, browser, mode, maximum, timeout, authorization, use_mock,
                         mock_outcome, mock_risky, mock_fixes=1, llm_cfg=None, history=None):
    """Start the LangGraph workflow and stream real node progress to the UI."""
    history = list(history or [])
    problems = []
    if not (url or "").strip():
        problems.append("Enter an application URL.")
    elif not re.match(r"^https?://[^\s/]+", url.strip(), re.I):
        problems.append("Enter a complete URL beginning with https:// or http://.")
    if not (requirements or "").strip():
        problems.append("Describe at least one test requirement.")
    if not authorization:
        problems.append("Confirm that you are authorized to test this application.")
    if problems:
        yield _view(None, "### Please correct these items\n" + "\n".join(f"- {p}" for p in problems))
        return

    llm_public, model_string, settings = None, None, None
    if not use_mock:
        cfg = llm_cfg or {}
        if not cfg.get("validated"):
            yield _view(None, "### Live mode needs validated LLM settings\nOpen **Settings → LLM configuration** and "
                              "save valid credentials, or enable **Use mock mode** for a simulated run. "
                              "No mock data is used in live mode.")
            return
        settings = LLMSettings(cfg["provider"], cfg["model"], cfg.get("api_key", ""), True)
        problem = check_static(settings.provider, settings.model, settings.api_key)
        if problem:
            yield _view(None, f"### LLM settings unusable\n{problem}")
            return
        model_string, llm_public = settings.model_string, settings.public()

    thread_id = str(uuid4())
    info = {"thread_id": thread_id, "tracker": StageTracker(), "trail": [], "error": None, "paused": False,
            "mock": bool(use_mock), "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ended": None, "lock": threading.Lock(), "llm": llm_public,
            "secret": effective_key(settings.provider, settings.api_key) if settings else "",
            "meta": {"url": url.strip(), "requirements": requirements.strip(), "browser": browser,
                     "execution_mode": mode, "timeout_seconds": int(timeout)}}
    with _RUNS_LOCK:
        RUNS[thread_id] = info
    history.append(thread_id)
    session = {"thread_id": thread_id, "waiting_for_approval": False}

    request = {"url": url.strip(), "requirements": requirements.strip(), "scenario_cap": int(maximum),
               "authorization": bool(authorization)}
    initial_state = {"test_request": request, "healing_retry_count": 0, "errors": []}
    if use_mock:
        initial_state.update(mock_mode=True, mock_execution_outcome=mock_outcome, mock_risky=bool(mock_risky),
                             mock_fixes_needed=int(mock_fixes))
    else:
        request.update(planner_model=model_string, codegen_model=model_string, healer_model=model_string)
        initial_state["mock_mode"] = False
        register_run_credentials(thread_id, settings)

    info["tracker"].begin("intake")
    yield _view(thread_id, "Workflow running…", session, history)
    for _ in _advance(thread_id, initial_state):
        yield _view(thread_id, "Workflow running…", session, history)
    session["waiting_for_approval"] = bool(info["paused"])
    yield _view(thread_id, _status_text(thread_id), session, history)


def resume_graph_workflow(session, decision):
    """Resume a paused run from its checkpoint with the human decision."""
    thread_id = (session or {}).get("thread_id")
    if thread_id not in RUNS or not _pending_interrupt(thread_id):
        yield _view(None, "No pending approval request.", session)
        return
    if decision not in ("approved", "rejected"):
        yield _view(thread_id, "Invalid approval decision. Choose Approve or Reject.", session)
        return
    info = RUNS[thread_id]
    if not info["lock"].acquire(blocking=False):
        yield _view(thread_id, "A decision for this run is already being processed.", session)
        return
    try:
        info["paused"] = False
        yield _view(thread_id, f"Fix {decision}; resuming workflow…", session)
        for _ in _advance(thread_id, Command(resume=decision)):
            yield _view(thread_id, "Workflow running…", session)
        session = {**session, "waiting_for_approval": bool(info["paused"])}
        yield _view(thread_id, _status_text(thread_id), session)
    finally:
        info["lock"].release()


def approve_workflow(session):
    yield from resume_graph_workflow(session, "approved")


def reject_workflow(session):
    yield from resume_graph_workflow(session, "rejected")


def select_run(thread_id):
    """Switch the active run (each run keeps its own checkpointed state)."""
    if not thread_id or thread_id not in RUNS:
        return NOOP, NOOP, NOOP, NOOP, NOOP
    session = {"thread_id": thread_id, "waiting_for_approval": bool(_pending_interrupt(thread_id))}
    details, buttons = approval_ui(session)
    return session, _status_text(thread_id), _progress_html(thread_id), details, buttons


# ------------------------------------------------------------------- results from real state
def _step_text(step: dict) -> str:
    return " ".join(str(v) for v in (step.get("action"), step.get("target"), step.get("value")) if v)


def build_run(thread_id: str) -> dict | None:
    """Assemble the results view model strictly from the run's checkpointed graph state."""
    info = RUNS.get(thread_id)
    if info is None:
        return None
    values = _snapshot_values(thread_id)
    plan = values.get("test_plan") or []
    result = values.get("execution_result") or {}
    simulated = bool(result.get("simulated")) or info["mock"]
    tag = " (simulated)" if simulated else ""
    tests = {t.get("scenario_name"): t for t in result.get("tests", [])}
    evidence = {e.get("scenario_name"): e for e in values.get("execution_evidence") or []}
    analysis, fix = values.get("failure_analysis"), values.get("fix_proposal")
    healing = values.get("healing_retry_count", 0)
    decision = values.get("approval_decision")
    terminal = values.get("terminal_status") or ("RUNNING" if not info.get("ended") else "UNKNOWN")

    analysis_text = None
    if analysis:
        subtype = f" / {analysis['subtype']}" if analysis.get("subtype") else ""
        analysis_text = f"{analysis['failure_type']}{subtype}: {analysis['root_cause']}\n\nEvidence: {analysis['evidence']}"
    fix_text = None
    if fix:
        fix_text = (f"{fix['reason']}  \nRisky: {fix['risky']} · Decision: {decision or 'pending'} · "
                    f"Applied healing attempts: {healing} of {MAX_HEALING}\n\n```diff\n{fix['patch_diff']}\n```")

    rows, total_ms = [], 0
    for plan_item in plan:
        name = plan_item.get("name", "Unnamed scenario")
        test, ev = tests.get(name), evidence.get(name) or {}
        if test:
            passed = test.get("status") == "passed"
            status, ms = ("Passed" if passed else "Failed"), int(test.get("duration_ms") or 0)
            total_ms += ms
        else:
            passed, status, ms = False, ("Blocked" if terminal in ("BLOCKED", "ERROR") else "Not run"), 0
        err = ev.get("error_message")
        evidence_lines = []
        if test and not passed:
            evidence_lines.append(f"Failed step: {ev.get('failed_step') or 'unknown'}")
        for label, key in (("Screenshot", "screenshot_path"), ("Trace", "trace_path"), ("Final URL", "final_url")):
            evidence_lines.append(f"{label}: {ev.get(key) or 'not captured'}")
        evidence_lines.append(f"Console entries: {len(ev.get('console_log') or [])} · "
                              f"Network errors: {len(ev.get('network_errors') or [])}")
        healed = passed and healing > 0
        if passed:
            actual = f"Passed{tag}" + (f" after {healing} healing attempt(s)" if healed else "")
        elif test:
            actual = f"Failed{tag}: {err or 'no error message'}"
        else:
            actual = "Not executed."
        rows.append({
            "Scenario ID": f"S-{len(rows) + 1:03d}", "Scenario Name": name, "Status": status,
            "Duration": f"{ms / 1000:.1f}s{tag}" if test else "—",
            "Error Summary": (err or "—") if test else ("Not executed" if status == "Not run" else f"Not executed ({terminal})"),
            "Test Steps": [_step_text(s) for s in plan_item.get("steps", [])] or [name],
            "Expected Result": plan_item.get("expected_result") or "Not specified",
            "Actual Result": actual,
            "Error Message": err or ("None" if test else "Not executed."),
            "Evidence Path": "\n".join(evidence_lines) if test else "No evidence collected.",
            "Analysis": (("Previously failed. " if healed else "") + analysis_text) if (analysis_text and (not passed or healed))
                        else ("No failure to analyse." if passed else "No analysis available."),
            "Proposed Fix": fix_text if (fix_text and (not passed or healed)) else ("Not needed." if passed else "Not generated."),
        })
    failed = sum(r["Status"] == "Failed" for r in rows)
    passed_n = sum(r["Status"] == "Passed" for r in rows)
    return {
        "run_id": values.get("run_id") or thread_id, "thread_id": thread_id, "created_at": info["started"],
        "mode": "Mock mode — simulated agents and browser" if info["mock"] else "Live",
        "simulated": info["mock"], "terminal_status": terminal, "healing_attempts": healing,
        "models_used": values.get("models_used") or {}, "errors": list(values.get("errors") or []),
        "trail": list(info["trail"]), "workflow_error": info.get("error"), "paused": bool(info.get("paused")),
        "llm": info.get("llm"), **info["meta"], "scenarios": rows,
        "passed": passed_n, "failed": failed, "skipped": len(rows) - passed_n - failed,
        "execution_time": f"{total_ms / 1000:.1f}s" if tests else "Not executed",
        "stages": dict(info["tracker"].status),
    }


def run_summary_markdown(run: dict | None) -> str:
    if not run:
        return "No run yet. Start a test from **User Request**."
    models = ", ".join(f"{k}: {v}" for k, v in run["models_used"].items()) or "none recorded"
    if run["simulated"]:
        llm = "Mock mode — no LLM provider is called; LLM settings are not used."
    else:
        llm = f"{run['llm']['provider']} · {run['llm']['model']} (key not shown)" if run["llm"] else "n/a"
    lines = [f"**Result:** {run['terminal_status']}" + (" — **awaiting your approval on the User Request page**" if run["paused"] else ""),
             f"**Mode:** {run['mode']}", f"**LLM:** {llm}", f"**Models used by agents:** {models}",
             f"**Healing attempts:** {run['healing_attempts']} of {MAX_HEALING}",
             f"**Executed nodes:** {' → '.join(run['trail']) or 'none'}"]
    if run["workflow_error"]:
        lines.append(f"**Workflow error:** {run['workflow_error']}")
    if run["errors"]:
        lines.append("**Recorded errors:** " + "; ".join(run["errors"]))
    return "  \n".join(lines)


def refresh_results(session, history):
    """Rebuild every Results & Reports component from the active run's graph state."""
    thread_id = (session or {}).get("thread_id")
    run = build_run(thread_id) if thread_id else None
    labels = ["Total Scenarios", "Passed", "Failed", "Skipped",
              "Execution Time (simulated)" if run and run["simulated"] else "Execution Time", "Healing Attempts"]
    values = ([str(len(run["scenarios"])), str(run["passed"]), str(run["failed"]), str(run["skipped"]),
               run["execution_time"], f"{run['healing_attempts']} / {MAX_HEALING}"] if run else ["—"] * 6)
    cards = [gr.update(value=metric_card(v, lbl)) for v, lbl in zip(values, labels)]
    table = [[s["Scenario ID"], s["Scenario Name"], s["Status"], s["Duration"], s["Error Summary"]]
             for s in run["scenarios"]] if run else []
    choices = [(f"{RUNS[t]['started'][11:19]} · {'Mock' if RUNS[t]['mock'] else 'Live'} · {RUNS[t]['meta']['url']}", t)
               for t in (history or []) if t in RUNS]
    return (run, *cards, gr.update(value=table), "Select a scenario row to inspect its details.",
            run_summary_markdown(run), gr.update(choices=choices, value=thread_id))


def build_ui() -> gr.Blocks:

    with gr.Blocks(title="QC AI · Test Automation") as demo:

        theme_state = gr.State("Blue")

        run_state = gr.State(None)

        run_history = gr.State([])

        sidebar_collapsed = gr.State(False)

        theme_style = gr.HTML(theme_css("Blue"), elem_classes="style-holder")

        collapse_style = gr.HTML("", elem_classes="style-holder")

        layout_style = gr.HTML(request_layout_css(True), elem_classes="style-holder")

        with gr.Row(elem_id="app-layout"):

            with gr.Column(elem_id="app-sidebar", scale=0):

                gr.HTML("<div class='sidebar-project-title'><span class='sb-short'>QC</span><span class='sb-full'>QC AI <span style='color:var(--app-accent)'>•</span><br>Test Automation</span></div>")

                sidebar_toggle = gr.Button("◀", elem_id="sidebar-toggle", size="sm")

                nav = gr.Radio(choices=[("▦  User Request", "User Request"), ("▤  Reports", "Results & Reports"), ("⚙  Settings", "Settings")], value="User Request", show_label=False, container=False, elem_classes="sidebar-nav", elem_id="sidebar-navigation")

                session_mode = gr.HTML(session_mode_label(True))

            with gr.Column(elem_classes="app-shell"):

                with gr.Column(visible=True, elem_id="user-request-page") as request_page:

                    with gr.Row(elem_id="request-layout", elem_classes="request-layout"):

                        with gr.Column(elem_id="request-card-column"):

                            with gr.Group(elem_classes="card"):

                                gr.HTML("<div class='card-title'>Test configuration</div><p class='muted'>Tell us which application and behaviors to cover.</p>")

                                url = gr.Textbox(label="Application URL", placeholder="https://your-app.example")

                                requirements = gr.Textbox(label="Test requirements", placeholder="Describe the user journey or behaviors to verify…", lines=2)

                                with gr.Row(elem_id="scenario-controls", equal_height=False):

                                    browser = gr.Dropdown(["Chromium", "Firefox", "WebKit"], value="Chromium", label="Browser", elem_id="browser-control")

                                    maximum = gr.Slider(1, 5, value=3, step=1, label="Maximum number of scenarios")

                                    mode = gr.Radio(["Headless", "Visible Browser"], value="Headless", label="Execution mode", elem_id="execution-mode-control")

                                    timeout = gr.Slider(10, 180, value=30, step=5, label="Timeout (seconds)")

                                authorization = gr.Checkbox(label="I am authorized to test this application.")

                                start = gr.Button("Start Testing", variant="primary", size="lg", elem_id="start-testing")

                                request_status = gr.Markdown()
                                

                                workflow_session = gr.State(None)

                                approval_details = gr.Markdown(
                                    visible=False,
                                    label="Human Fix Approval",
                                )

                                with gr.Row(visible=False) as approval_buttons:
                                    approve_btn = gr.Button(
                                        "Approve Fix",
                                        variant="primary",
                                    )

                                    reject_btn = gr.Button(
                                        "Reject Fix",
                                        variant="stop",
                                    )

                                return_btn = gr.Button("Return to Results", visible=False, elem_id="return-to-results")



                        with gr.Column(visible=True, elem_id="progress-card-column") as progress_panel:

                            with gr.Group(elem_classes="card"):

                                gr.HTML("<div class='card-title'>Execution progress</div><p class='muted'>Stages update live from the workflow nodes that actually execute, including approval, healing and reruns.</p>")

                                progress = gr.HTML(render_progress())

                                gr.Markdown("Mock-mode runs use simulated agents and a simulated browser. Live runs use the model selected in Settings and stop with a clear message at any stage that is not implemented yet.", elem_classes="muted")

                with gr.Column(visible=False) as results_page:

                    gr.HTML("<div class='page-head'><h1>Results & Reports</h1><p>Review the selected run's execution results, evidence, analysis and proposed fixes, and export its report.</p></div>")

                    with gr.Group(elem_classes="card"):

                        run_picker = gr.Dropdown([], label="Run", info="Each run keeps its own workflow state.", interactive=True)

                        run_summary = gr.Markdown("No run yet. Start a test from **User Request**.")

                    with gr.Row():

                        metric_total = gr.HTML("<div class='metric'><div class='metric-value'>—</div><div class='metric-label'>Total Scenarios</div></div>")

                        metric_pass = gr.HTML("<div class='metric'><div class='metric-value'>—</div><div class='metric-label'>Passed</div></div>")

                        metric_fail = gr.HTML("<div class='metric'><div class='metric-value'>—</div><div class='metric-label'>Failed</div></div>")

                        metric_skip = gr.HTML("<div class='metric'><div class='metric-value'>—</div><div class='metric-label'>Skipped</div></div>")

                        metric_time = gr.HTML("<div class='metric'><div class='metric-value' style='font-size:16px'>—</div><div class='metric-label'>Execution Time</div></div>")

                        metric_heal = gr.HTML("<div class='metric'><div class='metric-value'>—</div><div class='metric-label'>Healing Attempts</div></div>")

                    with gr.Group(elem_classes="card"):

                        gr.HTML("<div class='card-title'>Scenario results</div>")

                        scenarios_table = gr.Dataframe(headers=["Scenario ID", "Scenario Name", "Status", "Duration", "Error Summary"], datatype=["str"]*5, interactive=False, value=[])

                        scenario_info = gr.Markdown("Select a scenario row to inspect its details.")

                    with gr.Row():

                        with gr.Column(scale=2):

                            preview_btn = gr.Button("Preview Report")

                            report_preview = gr.Markdown("No report preview yet.")

                        with gr.Column(scale=1):

                            export_format = gr.Dropdown(["PDF", "Word (.docx)", "Excel (.xlsx)"], label="Export format", value="PDF")

                            export_btn = gr.Button("Export Report", variant="primary")

                            export_status = gr.Markdown()

                            export_file = gr.File(label="Download report")

                with gr.Column(visible=False) as settings_page:

                    gr.HTML("<div class='page-head'><h1>Settings</h1><p>Configure appearance, mock-mode behavior, and your LLM connection.</p></div>")

                    with gr.Group(elem_classes="card"):

                        gr.HTML("<div class='card-title'>Appearance</div><p class='muted'>Choose a theme for this active UI session.</p>")

                        settings_theme = gr.Radio(["Light", "Blue", "Dark"], value="Blue", label="Dashboard theme")

                    with gr.Group(elem_classes="card"):

                        gr.HTML("<div class='card-title'>Execution mode</div><p class='muted'>Mock mode runs the real LangGraph workflow with simulated agents (no real LLM or external calls), browser and fixes (clearly labeled). Turn it off for live mode, which uses your LLM settings and never falls back to mocks.</p>")

                        use_mock = gr.Checkbox(value=True, label="Use mock mode (no real LLM)")
                        

                        mock_outcome = gr.Radio(
                                choices=["PASS", "FAIL"],
                                value="PASS",
                                label="Mock execution outcome",
                            )

                        mock_risky = gr.Checkbox(
                                value=False,
                                label="Simulate risky fix",
                            )

                        mock_fixes = gr.Slider(1, 3, value=1, step=1, label="Mock mode: fixes needed before the rerun passes",
                                               info="Only applies when the outcome is FAIL. 1-2 heal successfully; 3 exhausts the 2-attempt limit and ends FAIL.")

                        show_progress = gr.Checkbox(value=True, label="Show execution progress")

                    with gr.Group(elem_classes="card"):

                        gr.HTML("<div class='card-title'>LLM configuration</div><p class='muted'>Used by live mode only. Credentials are validated with a real provider call, kept for this UI session only, and never shown in reports, exports or messages. Mock-mode runs do not call any provider.</p>")

                        llm_provider = gr.Dropdown(["Groq", "Gemini", "OpenRouter", "Ollama"], value="OpenRouter", label="Provider")

                        llm_model = gr.Textbox(label="Model name", placeholder="Enter the provider's model identifier (e.g. gemini-2.0-flash)")

                        llm_api_key = gr.Textbox(label="API key", type="password", placeholder="Masked and session-only; usually optional for Ollama")

                        save_llm_btn = gr.Button("Validate & save LLM settings")

                        llm_status = gr.Markdown()

                        llm_state = gr.State({})

        sidebar_toggle.click(toggle_sidebar, inputs=[sidebar_collapsed, nav], outputs=[sidebar_collapsed, collapse_style, nav, sidebar_toggle])

        nav.change(navigate, inputs=nav, outputs=[request_page, results_page, settings_page])

        settings_theme.change(set_theme, inputs=settings_theme, outputs=[theme_style, theme_state])

        use_mock.change(session_mode_label, inputs=use_mock, outputs=session_mode)

        show_progress.change(progress_visibility, inputs=show_progress, outputs=[progress_panel, layout_style])

        save_llm_btn.click(save_llm_settings, inputs=[llm_provider, llm_model, llm_api_key], outputs=[llm_status, llm_state])

       
        results_outputs = [run_state, metric_total, metric_pass, metric_fail, metric_skip, metric_time, metric_heal,
                           scenarios_table, scenario_info, run_summary, run_picker]

        run_outputs = [request_status, workflow_session, progress, approval_details, approval_buttons, return_btn, run_history]

        start.click(
            start_graph_workflow,
            inputs=[url, requirements, browser, mode, maximum, timeout, authorization, use_mock,
                    mock_outcome, mock_risky, mock_fixes, llm_state, run_history],
            outputs=run_outputs,
        ).then(refresh_results, inputs=[workflow_session, run_history], outputs=results_outputs)

        approve_btn.click(approve_workflow, inputs=workflow_session, outputs=run_outputs
        ).then(refresh_results, inputs=[workflow_session, run_history], outputs=results_outputs)

        reject_btn.click(reject_workflow, inputs=workflow_session, outputs=run_outputs
        ).then(refresh_results, inputs=[workflow_session, run_history], outputs=results_outputs)

        run_picker.input(
            select_run, inputs=run_picker,
            outputs=[workflow_session, request_status, progress, approval_details, approval_buttons],
        ).then(refresh_results, inputs=[workflow_session, run_history], outputs=results_outputs)

        return_btn.click(lambda: "Results & Reports", outputs=nav)

        scenarios_table.select(scenario_details, inputs=run_state, outputs=scenario_info)

        preview_btn.click(preview_report, inputs=run_state, outputs=report_preview)

        export_btn.click(export_report, inputs=[run_state, export_format], outputs=[export_status, export_file])

    return demo





def launch() -> None:

    build_ui().launch(server_name="127.0.0.1", server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")), theme=gr.themes.Base(), css=CSS)





if __name__ == "__main__":

    launch()
