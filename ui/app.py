"""Responsive Gradio 6 dashboard for AI assisted test automation."""

from __future__ import annotations



import html

import os

import re

import textwrap

import zipfile

from datetime import datetime, timezone

from pathlib import Path

from xml.sax.saxutils import escape



import gradio as gr



ROOT = Path(__file__).resolve().parents[1]

EXPORT_DIR = ROOT / "runs" / "sandbox_reports"



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
.step-status {margin-left:auto;color:var(--app-muted);padding-left:8px;white-space:nowrap}
.status-running .step-dot {background:var(--app-accent)}.status-completed .step-dot {background:#27ae80}
.status-failed .step-dot {background:#d94f5c}.status-skipped .step-dot {background:#d5a642}
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

STAGES = ["Intake", "Planner", "Code Generator", "Validation", "Execution", "Evidence Collection", "Analyzer", "Fix Proposal", "Report Generation"]

STAGE_STATUSES = {"not run", "running", "completed", "failed", "skipped"}





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





def render_progress(statuses: dict[str, str] | None = None) -> str:

    statuses = statuses or {}

    markup = []

    for stage in STAGES:

        raw_status = str(statuses.get(stage, "Not run")).strip().lower()

        status = raw_status if raw_status in STAGE_STATUSES else "not run"

        markup.append(

            f"<div class='step status-{status.replace(' ', '-')}'><span class='step-dot'></span>"

            f"{html.escape(stage)}<span class='step-status'>{status.title()}</span></div>"

        )

    return "".join(markup)





def metric_card(value: str, label: str) -> str:

    return f"<div class='metric'><div class='metric-value'>{html.escape(value)}</div><div class='metric-label'>{html.escape(label)}</div></div>"





def set_theme(theme: str) -> tuple[str, str]:

    return theme_css(theme), theme





def navigate(page: str) -> tuple[gr.update, gr.update, gr.update]:

    return (gr.update(visible=page == "User Request"), gr.update(visible=page == "Results & Reports"), gr.update(visible=page == "Settings"))





def session_mode_label(use_sandbox: bool) -> str:

    sandbox_enabled = use_sandbox is True or str(use_sandbox).strip().lower() in {"true", "1", "yes", "on"}

    mode = "Sandbox mode" if sandbox_enabled else "Live mode (workflow unavailable)"

    return f"<div class='session-mode'>Session mode<br><b>{mode}</b></div>"





def save_llm_settings(provider: str, model: str, api_key: str) -> tuple[str, dict]:

    if not (model or "").strip():

        return "Enter a model name before saving.", {}

    # Session-scoped only. Never expose this dict in report content, logs, or component values.

    return f"Saved {provider} settings for this UI session. The API key stays masked and is not exported.", {

        "provider": provider, "model": model.strip(), "api_key": api_key or ""

    }





def _scenario_names(requirements: str, limit: int) -> list[str]:

    chunks = [s.strip(" .\n\t-•") for s in re.split(r"\n+|(?<=[.!?])\s+", requirements) if s.strip(" .\n\t-•")]

    chunks = chunks[:limit]

    return chunks or ["Review requested behavior"]





def build_sandbox_run(url: str, requirements: str, browser: str, mode: str, maximum: int, timeout: int) -> dict:

    """Make run metadata and a scenario outline; no browser or AI work is executed."""

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    scenarios = []

    for i, name in enumerate(_scenario_names(requirements, int(maximum)), 1):

        scenarios.append({

            "Scenario ID": f"S-{i:03d}", "Scenario Name": name,

            "Status": "Not run", "Duration": "—", "Error Summary": "Not executed in sandbox mode",

            "Test Steps": [name], "Expected Result": "Behavior matches the requirement.",

            "Actual Result": "Not observed; browser execution is not implemented.",

            "Error Message": "No execution error; this is a preview scenario.",

            "Evidence Path": "Not available", "Analysis": "No runtime evidence was collected.",

            "Proposed Fix": "Not generated.",

        })

    return {"run_id": f"sandbox-{datetime.now().strftime('%Y%m%d-%H%M%S')}", "created_at": timestamp,

            "mode": "Sandbox preview — no test executed", "url": url.strip(), "requirements": requirements.strip(),

            "browser": browser, "execution_mode": mode, "timeout_seconds": int(timeout),

            "scenarios": scenarios, "passed": 0, "failed": 0, "skipped": 0,

            "execution_time": "Not executed", "stages": {stage: "Not run" for stage in STAGES}}





def validate_and_prepare(url: str, requirements: str, browser: str, mode: str,

                         maximum: float, timeout: float, authorization: bool, use_sandbox: bool):

    errors = []

    if not (url or "").strip():

        errors.append("Enter an application URL.")

    elif not re.match(r"^https?://[^\s/]+", url.strip(), re.I):

        errors.append("Enter a complete URL beginning with https:// or http://.")

    if not (requirements or "").strip():

        errors.append("Describe at least one test requirement.")

    if not authorization:

        errors.append("Confirm that you are authorized to test this application.")

    if errors:

        return "### Please correct these items\n" + "\n".join(f"- {e}" for e in errors), None, *(gr.update() for _ in range(8))



    if not use_sandbox:

        return ("### Live workflow unavailable\nSandbox is off, but this project does not yet have a connected AI workflow or browser runner. "

                "Enable **Use sandbox** in Settings to prepare a clearly labeled preview."), None, *(gr.update() for _ in range(8))



    run = build_sandbox_run(url, requirements, browser, mode, int(maximum), int(timeout))

    status = ("<div class='status-note'><b>Sandbox preview ready</b><br>" +

              "The request was validated and a report preview was prepared. No AI agents or browser tests ran.</div>")

    stages = render_progress(run["stages"])

    table = [[s["Scenario ID"], s["Scenario Name"], s["Status"], s["Duration"], s["Error Summary"]] for s in run["scenarios"]]

    metric_values = [str(len(run["scenarios"])), "0", "0", "0", "Not executed"]

    # Keep run-scoped content isolated in gr.State, while updating visible outputs.

    labels = ["Total Scenarios", "Passed", "Failed", "Skipped", "Execution Time"]

    cards = [gr.update(value=metric_card(value, label)) for value, label in zip(metric_values, labels)]

    return status, run, gr.update(value=stages), *cards, gr.update(value=table), gr.update(value="")





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





def preview_report(run: dict | None) -> str:

    if not run:

        return "No run is selected. Start a sandbox preview first."

    lines = [f"# Test Run Report — {run['run_id']}", f"**Mode:** {run['mode']}  ", f"**Created:** {run['created_at']}  ",

             f"**Application:** {run['url']}  ", f"**Browser:** {run['browser']} · {run['execution_mode']} · Timeout {run['timeout_seconds']}s", "",

             "> Sandbox preview: no AI agents or browser tests were executed.", "", "## Requirements", run["requirements"], "",

             "## Summary", f"- Total scenarios: {len(run['scenarios'])}", "- Passed: 0", "- Failed: 0", "- Skipped: 0", "- Execution time: Not executed", "",

             "## Scenario results", "| ID | Scenario | Status | Duration | Error summary |", "|---|---|---|---|---|"]

    lines.extend(f"| {s['Scenario ID']} | {s['Scenario Name']} | {s['Status']} | {s['Duration']} | {s['Error Summary']} |" for s in run["scenarios"])

    return "\n".join(lines)





def _safe(value: object) -> str:

    return str(value if value is not None else "")





def _write_pdf(path: Path, run: dict) -> None:

    """Write a small standards-compliant, text-only PDF without a runtime dependency."""

    text_lines = [f"Test Run Report - {run['run_id']}", run["mode"], f"Created: {run['created_at']}", f"URL: {run['url']}",

                  f"Browser: {run['browser']} / {run['execution_mode']}", "No browser test was executed.", "", "Requirements:"]

    text_lines += textwrap.wrap(run["requirements"], 90) or [""]

    text_lines += ["", f"Summary: {len(run['scenarios'])} scenarios; 0 passed; 0 failed; 0 skipped; not executed.", "", "Scenarios:"]

    for s in run["scenarios"]:

        text_lines += textwrap.wrap(f"{s['Scenario ID']} | {s['Scenario Name']} | {s['Status']} | {s['Error Summary']}", 90)

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

            ascii_line = line.encode("ascii", "replace").decode().replace("\\\\", "\\\\\\\\").replace("(", "\\\\(").replace(")", "\\\\)")

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

    paragraphs = [f"Test Run Report — {run['run_id']}", run["mode"], f"Created: {run['created_at']}",

                  f"Application: {run['url']}", f"Browser: {run['browser']} / {run['execution_mode']}",

                  "Sandbox preview: no AI agents or browser tests were executed.", "Requirements", run["requirements"],

                  "Summary", f"Total scenarios: {len(run['scenarios'])}; Passed: 0; Failed: 0; Skipped: 0; Execution time: Not executed", "Scenario results"]

    for s in run["scenarios"]:

        paragraphs.append(" | ".join([s["Scenario ID"], s["Scenario Name"], s["Status"], s["Duration"], s["Error Summary"]]))

    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{escape(p)}</w:t></w:r></w:p>' for p in paragraphs)

    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'''

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as doc:

        doc.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')

        doc.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')

        doc.writestr("word/document.xml", document)





def export_report(run: dict | None, format_name: str) -> tuple[str, str | None]:

    if not run:

        return "Create a sandbox preview before exporting.", None

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

        for row in [["Run ID", run["run_id"]], ["Mode", run["mode"]], ["Created", run["created_at"]], ["Application URL", run["url"]], ["Requirements", run["requirements"]], ["Browser", run["browser"]], ["Execution mode", run["execution_mode"]], ["Total scenarios", len(run["scenarios"])], ["Passed", 0], ["Failed", 0], ["Skipped", 0], ["Execution time", "Not executed"]]: summary.append(row)

        scenarios = book.create_sheet("Scenarios"); scenarios.append(["Scenario ID", "Scenario Name", "Status", "Duration", "Error Summary"])

        for s in run["scenarios"]: scenarios.append([s[k] for k in ["Scenario ID", "Scenario Name", "Status", "Duration", "Error Summary"]])

        failures = book.create_sheet("Failure Analysis"); failures.append(["Scenario ID", "Scenario Name", "Analysis", "Error Message", "Proposed Fix"])

        for s in run["scenarios"]: failures.append([s["Scenario ID"], s["Scenario Name"], s["Analysis"], s["Error Message"], s["Proposed Fix"]])

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





def build_ui() -> gr.Blocks:

    with gr.Blocks(title="QC AI · Test Automation") as demo:

        theme_state = gr.State("Blue")

        run_state = gr.State(None)

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

                                    maximum = gr.Slider(1, 10, value=3, step=1, label="Maximum number of scenarios")

                                    mode = gr.Radio(["Headless", "Visible Browser"], value="Headless", label="Execution mode", elem_id="execution-mode-control")

                                    timeout = gr.Slider(10, 180, value=30, step=5, label="Timeout (seconds)")

                                authorization = gr.Checkbox(label="I am authorized to test this application.")

                                start = gr.Button("Start Testing", variant="primary", size="lg", elem_id="start-testing")

                                request_status = gr.Markdown()

                        with gr.Column(visible=True, elem_id="progress-card-column") as progress_panel:

                            with gr.Group(elem_classes="card"):

                                gr.HTML("<div class='card-title'>Execution progress</div><p class='muted'>Workflow stages are shown as not run in sandbox mode.</p>")

                                progress = gr.HTML(render_progress())

                                gr.Markdown("Sandbox mode does not call LLM providers or launch a browser.", elem_classes="muted")

                with gr.Column(visible=False) as results_page:

                    gr.HTML("<div class='page-head'><h1>Results & Reports</h1><p>Review the latest request and export its generated report data.</p></div>")

                    with gr.Row():

                        metric_total = gr.HTML("<div class='metric'><div class='metric-value'>—</div><div class='metric-label'>Total Scenarios</div></div>")

                        metric_pass = gr.HTML("<div class='metric'><div class='metric-value'>—</div><div class='metric-label'>Passed</div></div>")

                        metric_fail = gr.HTML("<div class='metric'><div class='metric-value'>—</div><div class='metric-label'>Failed</div></div>")

                        metric_skip = gr.HTML("<div class='metric'><div class='metric-value'>—</div><div class='metric-label'>Skipped</div></div>")

                        metric_time = gr.HTML("<div class='metric'><div class='metric-value' style='font-size:16px'>—</div><div class='metric-label'>Execution Time</div></div>")

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

                    gr.HTML("<div class='page-head'><h1>Settings</h1><p>Configure appearance, sandbox behavior, and your LLM connection.</p></div>")

                    with gr.Group(elem_classes="card"):

                        gr.HTML("<div class='card-title'>Appearance</div><p class='muted'>Choose a theme for this active UI session.</p>")

                        settings_theme = gr.Radio(["Light", "Blue", "Dark"], value="Blue", label="Dashboard theme")

                    with gr.Group(elem_classes="card"):

                        gr.HTML("<div class='card-title'>Execution mode</div><p class='muted'>Sandbox prepares a report preview from your request. It does not run agents or open a browser.</p>")

                        use_sandbox = gr.Checkbox(value=True, label="Use sandbox")

                        show_progress = gr.Checkbox(value=True, label="Show execution progress")

                    with gr.Group(elem_classes="card"):

                        gr.HTML("<div class='card-title'>LLM configuration</div><p class='muted'>Credentials are stored only for this active UI session. They are not shown in reports or exports.</p>")

                        llm_provider = gr.Dropdown(["Groq", "Gemini", "OpenRouter", "Ollama"], value="OpenRouter", label="Provider")

                        llm_model = gr.Textbox(label="Model name", placeholder="Enter the provider's model identifier")

                        llm_api_key = gr.Textbox(label="API key", type="password", placeholder="Masked and session-only; usually optional for Ollama")

                        save_llm_btn = gr.Button("Save LLM settings")

                        llm_status = gr.Markdown()

                        llm_state = gr.State({})

        sidebar_toggle.click(toggle_sidebar, inputs=[sidebar_collapsed, nav], outputs=[sidebar_collapsed, collapse_style, nav, sidebar_toggle])

        nav.change(navigate, inputs=nav, outputs=[request_page, results_page, settings_page])

        settings_theme.change(set_theme, inputs=settings_theme, outputs=[theme_style, theme_state])

        use_sandbox.change(session_mode_label, inputs=use_sandbox, outputs=session_mode)

        show_progress.change(progress_visibility, inputs=show_progress, outputs=[progress_panel, layout_style])

        save_llm_btn.click(save_llm_settings, inputs=[llm_provider, llm_model, llm_api_key], outputs=[llm_status, llm_state])

        start.click(validate_and_prepare, inputs=[url, requirements, browser, mode, maximum, timeout, authorization, use_sandbox],

                    outputs=[request_status, run_state, progress, metric_total, metric_pass, metric_fail, metric_skip, metric_time, scenarios_table, scenario_info])

        scenarios_table.select(scenario_details, inputs=run_state, outputs=scenario_info)

        preview_btn.click(preview_report, inputs=run_state, outputs=report_preview)

        export_btn.click(export_report, inputs=[run_state, export_format], outputs=[export_status, export_file])

    return demo





def launch() -> None:

    build_ui().launch(server_name="127.0.0.1", server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")), theme=gr.themes.Base(), css=CSS)





if __name__ == "__main__":

    launch()
