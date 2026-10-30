"""Visual design system for the dashboard: theme tokens, CSS and pure HTML/SVG renderers.

Everything here is presentation only. Renderers receive data that the callers read from real run state or
persisted history; they never compute workflow results and never call the workflow.
"""

from __future__ import annotations
import base64
import html
from pathlib import Path

esc = html.escape

THEMES = {
    "Dark": {"bg": "#0a0c11", "surface": "#10141b", "surface2": "#161b24", "text": "#e7eaf0", "muted": "#8a93a6",
             "line": "#222937", "accent": "#7b8cff", "soft": "#1a2133", "ok": "#34d399", "warn": "#fbbf24",
             "bad": "#f87171", "info": "#60a5fa", "violet": "#a78bfa", "glow": "rgba(123,140,255,.16)"},
    "Blue": {"bg": "#0a1224", "surface": "#0f1b33", "surface2": "#132341", "text": "#e8efff", "muted": "#8fa1c4",
             "line": "#20365a", "accent": "#5b9bff", "soft": "#17294b", "ok": "#34d399", "warn": "#fbbf24",
             "bad": "#fb7185", "info": "#38bdf8", "violet": "#a78bfa", "glow": "rgba(91,155,255,.18)"},
    "Light": {"bg": "#f5f6fa", "surface": "#ffffff", "surface2": "#f8f9fc", "text": "#101828", "muted": "#667085",
              "line": "#e3e6ee", "accent": "#4f46e5", "soft": "#eef0ff", "ok": "#059669", "warn": "#b45309",
              "bad": "#dc2626", "info": "#2563eb", "violet": "#7c3aed", "glow": "rgba(79,70,229,.10)"},
}

ICONS = {
    "overview": '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "workflow": '<circle cx="6" cy="5" r="2"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="12" r="2"/><path d="M6 7v10M8 5h4a4 4 0 0 1 4 4v1M8 19h4a4 4 0 0 0 4-4v-1"/>',
    "results": '<path d="m3 17 2 2 4-4M3 7l2 2 4-4M13 6h8M13 12h8M13 18h8"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8"/>',
    "chart": '<path d="M3 3v18h18"/><path d="m7 15 4-4 3 3 5-6"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>', "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "alert": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>',
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.7 4H7.3a2 2 0 0 0-1.8 1.1z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "zap": '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
}


def icon(name: str, size: int = 18) -> str:
    return (f"<svg class='ico' width='{size}' height='{size}' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
            f"stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>{ICONS.get(name, '')}</svg>")


def _mask(name: str) -> str:
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.8' "
           f"stroke-linecap='round' stroke-linejoin='round'>{ICONS[name].replace(chr(34), chr(39))}</svg>")
    return "url(\"data:image/svg+xml;utf8," + svg.replace("<", "%3C").replace(">", "%3E").replace("#", "%23") + "\")"


# Menu follows the QC cycle: understand the flow, see the big picture, start a test, approve fixes, read reports, track trends.
NAV_ORDER = [("Workflow", "workflow"), ("Dashboard", "overview"), ("Create & Run", "play"),
             ("Fix Approval", "shield"), ("Reports", "file"), ("Analytics", "chart"), ("Settings", "settings")]

_ASSETS = Path(__file__).parent / "assets"


def _logo_uri(name: str) -> str:
    try:
        return "data:image/png;base64," + base64.b64encode((_ASSETS / name).read_bytes()).decode("ascii")
    except OSError:
        return ""


def brand_html() -> str:
    """Sidebar brand: full logo when expanded, head-only icon when collapsed; light/dark art follows the theme."""
    imgs = "".join(
        f"<img class='logo-{mode} {cls}' src='{_logo_uri(f'bugle-{kind}-{mode}.png')}' alt='Bugle'>"
        for kind, cls in (("logo", "sb-full"), ("icon", "sb-short")) for mode in ("light", "dark"))
    return f"<div class='brand'>{imgs}</div><div class='brand-sub sb-full'>Bugle Automation</div>"


def theme_css(theme: str) -> str:
    c = THEMES.get(theme, THEMES["Dark"])
    values = ";".join(f"--app-{k}:{v}" for k, v in c.items())
    gradio_vars = (
        f"--body-background-fill:{c['bg']};--background-fill-primary:{c['surface']};--background-fill-secondary:{c['soft']};"
        f"--block-background-fill:transparent;--block-border-color:{c['line']};--border-color-primary:{c['line']};"
        f"--body-text-color:{c['text']};--body-text-color-subdued:{c['muted']};--block-label-text-color:{c['muted']};"
        f"--block-title-text-color:{c['text']};--block-info-text-color:{c['muted']};--input-background-fill:{c['surface2']};"
        f"--input-border-color:{c['line']};--input-placeholder-color:{c['muted']};--panel-background-fill:{c['surface']};"
        f"--table-even-background-fill:{c['surface']};--table-odd-background-fill:{c['surface2']};--table-border-color:{c['line']};"
        f"--table-row-focus:{c['soft']};--button-secondary-background-fill:{c['surface2']};--button-secondary-text-color:{c['text']};"
        f"--button-secondary-border-color:{c['line']};--checkbox-background-color:{c['surface2']};--checkbox-border-color:{c['line']};"
        f"--neutral-100:{c['soft']};--color-accent:{c['accent']};--slider-color:{c['accent']};--shadow-drop:none;"
        f"color-scheme:{'light' if theme == 'Light' else 'dark'}"
    )
    selector = "html:root, html body, html body.dark, html .dark, html .gradio-container"
    hide = ".logo-dark" if theme == "Light" else ".logo-light"
    return f"<style>:root{{{values}}} {selector}{{{values};{gradio_vars}}} {hide}{{display:none!important}}</style>"


def request_layout_css(show_progress: bool) -> str:
    columns = "minmax(0,3fr) minmax(0,2fr)" if show_progress else "minmax(0,1fr)"
    return (f"<style>#request-layout{{--request-layout-columns:{columns}!important}}"
            f"@media(max-width:1100px){{#request-layout{{--request-layout-columns:minmax(0,1fr)!important}}}}</style>")


def collapsed_css() -> str:
    return ("<style>#app-layout{--sb-w:68px}#app-sidebar{padding:18px 8px!important}.sb-full,.session-mode{display:none!important}"
            ".sb-short{display:block!important}.brand{justify-content:center;padding:0 0 14px!important}"
            "#sidebar-navigation label{justify-content:center!important;padding:11px 0!important;font-size:0!important}"
            "#sidebar-navigation label span{font-size:0!important}#sidebar-navigation label::before{margin:0!important}</style>")


# --------------------------------------------------------------------------------------- components
STATUS_TONE = {
    "PASS": "ok", "PASSED": "ok", "COMPLETED": "ok", "APPROVED": "ok", "LIVE": "info",
    "FAIL": "bad", "FAILED": "bad", "ERROR": "bad", "REJECTED": "bad",
    "BLOCKED": "warn", "WAITING FOR APPROVAL": "warn", "PENDING": "warn", "RUNNING": "info",
    "MOCK": "violet", "SIMULATED": "violet", "NOT RUN": "mute", "NOT_RUN": "mute", "SKIPPED": "mute", "UNKNOWN": "mute",
}


def badge(text: object, tone: str | None = None) -> str:
    label = str(text if text not in (None, "") else "—")
    tone = tone or STATUS_TONE.get(label.upper(), "mute")
    return f"<span class='badge b-{tone}'>{esc(label)}</span>"


def page_head(title: str, subtitle: str, icon_name: str, extra: str = "") -> str:
    return (f"<div class='page-head'><div class='ph-icon'>{icon(icon_name, 22)}</div><div class='ph-text'><h1>{esc(title)}</h1>"
            f"<p>{esc(subtitle)}</p></div><div class='ph-extra'>{extra}</div></div>")


def kpi(label: str, value: str, sub: str = "", tone: str = "", icon_name: str = "activity") -> str:
    return (f"<div class='kpi {('k-' + tone) if tone else ''}'><div class='kpi-top'><span class='kpi-label'>{esc(label)}</span>"
            f"<span class='kpi-ico'>{icon(icon_name, 16)}</span></div><div class='kpi-value'>{esc(value)}</div>"
            f"<div class='kpi-sub'>{esc(sub)}</div></div>")


def kpi_row(*cards: str) -> str:
    return f"<div class='kpi-row'>{''.join(cards)}</div>"


def empty(title: str, text: str, icon_name: str = "inbox") -> str:
    return (f"<div class='empty'><div class='empty-ico'>{icon(icon_name, 26)}</div><div class='empty-title'>{esc(title)}</div>"
            f"<div class='empty-text'>{esc(text)}</div></div>")


def panel(title: str, body: str, sub: str = "", right: str = "") -> str:
    head = (f"<div class='panel-head'><div><div class='panel-title'>{esc(title)}</div>"
            f"{f'<div class=panel-sub>{esc(sub)}</div>' if sub else ''}</div><div>{right}</div></div>")
    return f"<div class='panel'>{head}<div class='panel-body'>{body}</div></div>"


def note(text: str, tone: str = "info") -> str:
    return f"<div class='note n-{tone}'>{text}</div>"


def table(headers: list[str], rows: list[list[str]], raw_cols: tuple[int, ...] = ()) -> str:
    """Rows hold plain text, except columns listed in raw_cols which carry trusted HTML (badges)."""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c if i in raw_cols else esc(str(c))}</td>" for i, c in enumerate(r)) + "</tr>"
                   for r in rows)
    return f"<div class='tbl-wrap'><table class='tbl'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def diff_html(patch: str) -> str:
    lines = []
    for raw in (patch or "").splitlines() or ["(empty patch)"]:
        kind = "add" if raw.startswith("+") and not raw.startswith("+++") else \
               "del" if raw.startswith("-") and not raw.startswith("---") else \
               "hunk" if raw.startswith("@@") else "meta" if raw.startswith(("+++", "---", "diff", "index")) else "ctx"
        lines.append(f"<div class='dl dl-{kind}'><span class='dl-gut'>{esc(raw[:1]) if kind in ('add', 'del') else ''}</span>"
                     f"<span class='dl-code'>{esc(raw[1:] if kind in ('add', 'del') else raw) or '&nbsp;'}</span></div>")
    return f"<div class='diff'>{''.join(lines)}</div>"


# ------------------------------------------------------------------------------------------- charts
def _pct(a: float, b: float) -> float:
    return a / b * 100 if b else 0


def donut(segments: list[tuple[str, float, str]], center: str, center_sub: str = "") -> str:
    """segments: (label, value, tone). Returns donut + legend, or an empty state when there is no data."""
    total = sum(v for _, v, _ in segments)
    if not total:
        return empty("No data in this range", "Run a test to populate this chart.", "chart")
    r, c, off, arcs = 54, 2 * 3.14159265 * 54, 0.0, []
    for label, value, tone in segments:
        if not value:
            continue
        length = value / total * c
        arcs.append(f"<circle cx='70' cy='70' r='{r}' fill='none' stroke-width='16' class='s-{tone}' "
                    f"stroke-dasharray='{length:.2f} {c - length:.2f}' stroke-dashoffset='{-off:.2f}' transform='rotate(-90 70 70)'>"
                    f"<title>{esc(label)}: {value:g}</title></circle>")
        off += length
    legend = "".join(f"<div class='lg'><i class='dot d-{t}'></i><span>{esc(l)}</span><b>{v:g}</b>"
                     f"<em>{_pct(v, total):.0f}%</em></div>" for l, v, t in segments)
    return (f"<div class='donut-wrap'><svg viewBox='0 0 140 140' class='donut'><circle cx='70' cy='70' r='{r}' fill='none' "
            f"stroke-width='16' class='track'/>{''.join(arcs)}<text x='70' y='68' class='dc-main'>{esc(center)}</text>"
            f"<text x='70' y='85' class='dc-sub'>{esc(center_sub)}</text></svg><div class='legend'>{legend}</div></div>")


def columns(items: list[tuple[str, float]], tone: str = "accent", unit: str = "") -> str:
    """Vertical bar chart (e.g. runs per day)."""
    if not items or not any(v for _, v in items):
        return empty("No data in this range", "Run a test to populate this chart.", "chart")
    items = items[-30:]
    top = max(v for _, v in items) or 1
    w, h, pad = 560, 190, 28
    slot = (w - pad) / len(items)
    bars, labels = [], []
    for i, (label, v) in enumerate(items):
        bh = v / top * (h - 50)
        bw = min(slot * .64, 46)
        x = pad + i * slot + (slot - bw) / 2
        bars.append(f"<rect x='{x:.1f}' y='{h - 24 - bh:.1f}' width='{bw:.1f}' height='{max(bh, 1.5):.1f}' rx='3' class='s-fill-{tone}'>"
                    f"<title>{esc(label)}: {v:g}{unit}</title></rect>")
        bars.append(f"<text x='{x + bw / 2:.1f}' y='{h - 28 - bh:.1f}' class='bar-val'>{v:g}</text>") if len(items) <= 14 else None
        if len(items) <= 10 or i % max(len(items) // 7, 1) == 0:
            labels.append(f"<text x='{x + bw / 2:.1f}' y='{h - 8}' class='axis'>{esc(label[5:] if len(label) == 10 else label)}</text>")
    grid = "".join(f"<line x1='{pad}' x2='{w}' y1='{y}' y2='{y}' class='grid'/>" for y in (h - 24, (h - 24) * .66, (h - 24) * .33))
    return f"<svg viewBox='0 0 {w} {h}' class='chart'>{grid}{''.join(b for b in bars if b)}{''.join(labels)}</svg>"


def hbars(items: list[tuple[str, float, str]], unit: str = "") -> str:
    if not items or not any(v for _, v, _ in items):
        return empty("No data in this range", "Nothing recorded for this metric yet.", "chart")
    top = max(v for _, v, _ in items) or 1
    rows = "".join(f"<div class='hb'><span class='hb-l'>{esc(l)}</span><div class='hb-t'><div class='hb-f s-fill-{t}' "
                   f"style='width:{max(v / top * 100, 2):.1f}%'></div></div><b>{v:g}{unit}</b></div>" for l, v, t in items)
    return f"<div class='hbars'>{rows}</div>"


# ------------------------------------------------------------------------------------- workflow graph
# Mirrors the architecture diagram. Tracked nodes use the UI tracker's stage name; the rest are static context.
# key: (tracker stage, title, role, x, y, kind)   kind: llm = LLM agent, det = deterministic node, rep = report
GRAPH_NODES = {
    "intake": ("Intake", "1 · Intake", "resolve URL · safety checks · model check", 260, 92, "det"),
    "planner": ("Planner", "2 · Planner Agent", "requirement → scenarios", 260, 176, "llm"),
    "codegen": ("Code Generator", "3 · Code Generation Agent", "scenarios → .spec.ts", 260, 260, "llm"),
    "validate": ("Validation", "4 · Validate", "tsc + lint · 2 regeneration tries", 260, 344, "det"),
    "execute": ("Execution", "6 · Execute", "run_playwright_tests · no LLM", 260, 428, "det"),
    "analyze": ("Analyzer", "7 · Failure Analyzer Agent", "Test · Application · Environment · Infra", 330, 590, "llm"),
    "fix_proposal": ("Fix Proposal", "8 · Fix Proposal Agent", "test code only · risky = assertion", 330, 674, "llm"),
    "fix_approval": ("Human Approval", "9a · Approval gate", "needed when the fix is risky", 330, 758, "det"),
    "apply_fix": ("Apply Fix (Healing)", "9b · Apply Fix", "auto, or after approval if risky", 330, 842, "det"),
    "report": ("Report Generation", "10 · Report", "PASS / FAIL / BLOCKED / ERROR · Markdown, HTML", 120, 950, "rep"),
}
NW, NH = 340, 54
ROUTING = [
    ("Intake", "Planner", "target URL resolved, consent given, run not BLOCKED / ERROR", "Report otherwise"),
    ("Planner", "Code Generation", "at least one scenario was planned", "Report otherwise"),
    ("Validation", "Execution", "validation_status is valid", "Code Generation again (max 2 tries), then Report as BLOCKED"),
    ("Execution", "Failure Analyzer", "some test failed", "Report on PASS, BLOCKED or ERROR"),
    ("Failure Analyzer", "Fix Proposal", "failure class is Test and fewer than 2 heals (live: high-confidence analysis that needs a fix)",
     "Report otherwise"),
    ("Fix Proposal", "Approval gate", "a non-empty patch exists", "Report otherwise"),
    ("Approval gate", "Apply Fix", "human approved, or auto-heal is on and the fix is not risky", "Report on reject, empty patch or error"),
    ("Apply Fix", "Validation", "patch applied (re-validate and rerun, max 2 per test)", "Report otherwise"),
]


def workflow_svg(status: dict[str, str] | None, notes: dict[str, str] | None = None, counts: dict[str, int] | None = None) -> str:
    status, notes, counts = status or {}, notes or {}, counts or {}
    W = NW

    def x(k): return GRAPH_NODES[k][3]
    def y(k): return GRAPH_NODES[k][4]
    def cx(k): return x(k) + W / 2
    def bot(k): return y(k) + NH

    def line(x1, y1, x2, y2, cls="e-solid"):
        return f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' class='{cls}' marker-end='url(#arr)'/>"

    def path(d, cls, arrow=True):
        m = " marker-end='url(#arr)'" if arrow else ""
        return f"<path d='{d}' class='{cls}'{m}/>"

    def box(title, role, bx, by, bw, bh, kind):
        return (f"<g class='gnode g-static k-{kind}'><rect x='{bx}' y='{by}' width='{bw}' height='{bh}' rx='10' class='gbox'/>"
                f"<text x='{bx + bw / 2}' y='{by + 22}' class='gtitle' text-anchor='middle'>{esc(title)}</text>"
                f"<text x='{bx + bw / 2}' y='{by + 40}' class='grole' text-anchor='middle'>{esc(role)}</text></g>")

    ctx = [
        box("Input", "URL (optional) + requirement + consent", 260, 14, W, 50, "det"),
        box("5 · Human Review", "off · optional", 40, 260, 170, 54, "opt"),
        (f"<g class='gnode g-static k-mcp'><rect x='640' y='160' width='300' height='188' rx='10' class='gbox'/>"
         f"<text x='790' y='186' class='gtitle' text-anchor='middle'>Playwright MCP</text>"
         f"<text x='790' y='204' class='grole' text-anchor='middle'>official · browser tools bound per agent</text>"
         f"<text x='790' y='232' class='grole' text-anchor='middle'>planner: navigate · snapshot · click · type</text>"
         f"<text x='790' y='252' class='grole' text-anchor='middle'>codegen: snapshot · generate_locator</text>"
         f"<text x='790' y='282' class='grole' text-anchor='middle'>page text = data only, never instructions</text></g>"),
        (f"<g class='gnode g-static k-det'><rect x='640' y='404' width='300' height='96' rx='10' class='gbox'/>"
         f"<text x='790' y='430' class='gtitle' text-anchor='middle'>Local tools</text>"
         f"<text x='790' y='450' class='grole' text-anchor='middle'>save / read test file · run tests · get results</text>"
         f"<text x='790' y='476' class='gtitle' text-anchor='middle'>Chromium → target site</text></g>"),
    ]
    dcx, dcy = cx("execute"), 540
    diamond = (f"<g class='gnode g-static k-det'><polygon points='{dcx},{dcy - 34} {dcx + 84},{dcy} {dcx},{dcy + 34} {dcx - 84},{dcy}' class='gbox'/>"
               f"<text x='{dcx}' y='{dcy + 4}' class='gtitle' text-anchor='middle'>Route results</text></g>")

    edges = [
        line(cx("intake"), 64, cx("intake"), y("intake")),
        line(cx("intake"), bot("intake"), cx("planner"), y("planner"), "e-cond"),
        line(cx("planner"), bot("planner"), cx("codegen"), y("codegen"), "e-cond"),
        line(cx("codegen"), bot("codegen"), cx("validate"), y("validate")),
        line(cx("validate"), bot("validate"), cx("execute"), y("execute"), "e-cond"),
        line(cx("execute"), bot("execute"), dcx, dcy - 34),
        line(x("planner") + W, y("planner") + 27, 640, 220),
        line(x("codegen") + W, y("codegen") + 27, 640, 300),
        line(210, 287, 260, 287, "e-opt"),
        line(x("execute") + W, y("execute") + 27, 640, 452),
        path(f"M {dcx + 84} {dcy} H 560 V 617 H {x('analyze') + W}", "e-cond"),
        line(cx("analyze"), bot("analyze"), cx("fix_proposal"), y("fix_proposal"), "e-cond"),
        line(cx("fix_proposal"), bot("fix_proposal"), cx("fix_approval"), y("fix_approval"), "e-cond"),
        line(cx("fix_approval"), bot("fix_approval"), cx("apply_fix"), y("apply_fix"), "e-cond"),
        path(f"M {x('apply_fix')} {y('apply_fix') + 27} H 215 V {y('validate') + 27} H {x('validate') - 4}", "e-loop"),
        path(f"M {dcx - 84} {dcy} H 150 V 946", "e-exit"),
        path(f"M {x('apply_fix') + W / 2 + 80} {bot('apply_fix')} V 930 H 460 V 946", "e-exit"),
    ]
    labels = (f"<text x='{dcx + 96}' y='{dcy - 8}' class='e-label e-label-cond'>fail</text>"
              f"<text x='224' y='{dcy - 8}' class='e-label'>pass / other</text>"
              f"<text x='24' y='{y('validate') + 80}' class='e-label e-label-loop'>re-validate + rerun · max 2 per test</text>"
              f"<text x='{x('analyze') + 8}' y='{y('analyze') - 6}' class='e-label'>Test class only</text>")

    nodes = []
    for key, (stage, title, role, nx, ny, kind) in GRAPH_NODES.items():
        st = str(status.get(stage, "Not run")).strip().lower() or "not run"
        cls = st.replace(" ", "-")
        note_txt = notes.get(stage, "")
        label = {"not run": "Not run", "waiting for approval": "Awaiting decision"}.get(st, st.title())
        extra = f" · {note_txt}" if note_txt else ""
        w = 360 if key == "report" else W
        gate = (f"<text x='{nx + w - 8}' y='{ny - 6}' class='gate' text-anchor='end'>HUMAN GATE</text>" if key == "fix_approval" else "")
        visits = (f"<text x='{nx + w - 10}' y='{ny + 17}' class='visits' text-anchor='end'>×{counts[stage]}</text>"
                  if counts.get(stage, 0) > 1 else "")
        nodes.append(
            f"<g class='gnode g-{cls} k-{kind}'><title>{esc(title)} — {esc(label + extra)}</title>"
            f"<rect x='{nx}' y='{ny}' width='{w}' height='{NH}' rx='10' class='gbox'/>{gate}"
            f"<circle cx='{nx + 14}' cy='{ny + 17}' r='4.5' class='gdot'/>"
            f"<text x='{nx + 26}' y='{ny + 21}' class='gtitle'>{esc(title)}</text>"
            f"<text x='{nx + 14}' y='{ny + 40}' class='grole'>{esc(role)}</text>"
            f"<text x='{nx + w - 12}' y='{ny + 21}' class='gstat' text-anchor='end'>{esc((label + extra)[:22])}</text>{visits}</g>")
    defs = ("<defs><marker id='arr' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='6' markerHeight='6' orient='auto-start-reverse'>"
            "<path d='M0 0 10 5 0 10z' class='arrow'/></marker></defs>")
    return (f"<svg viewBox='0 0 960 1020' class='wf' role='img' aria-label='Bugle workflow'>{defs}"
            f"{''.join(edges)}{labels}{''.join(ctx)}{diamond}{''.join(nodes)}</svg>")


def workflow_legend() -> str:
    return ("<div class='wf-legend'><span><i class='lg-box llm'></i>LLM agent</span>"
            "<span><i class='lg-box det'></i>deterministic node or tool</span>"
            "<span><i class='lg-box opt'></i>optional (off)</span>"
            "<span><i class='lg-line cond'></i>conditional routing</span>"
            "<span><i class='lg-line loop'></i>heal loop</span>"
            "<span><i class='lg-line exit'></i>exit to the report</span>"
            "<span class='sep'></span>"
            "<span><i class='dot d-mute'></i>not run</span><span><i class='dot d-info'></i>running</span>"
            "<span><i class='dot d-ok'></i>completed</span><span><i class='dot d-warn'></i>awaiting approval</span>"
            "<span><i class='dot d-bad'></i>failed</span></div>"
            "<div class='wf-legend'><span>Every path ends at the report.</span></div>")


def routing_table() -> str:
    return table(["From", "Goes to", "When", "Otherwise"], [list(r) for r in ROUTING])


# --------------------------------------------------------------------------------------------- CSS
_NAV_ICON_CSS = "".join(
    f"#sidebar-navigation label:nth-of-type({i})::before{{-webkit-mask-image:{_mask(ic)};mask-image:{_mask(ic)}}}"
    for i, (_, ic) in enumerate(NAV_ORDER, 1))

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
:root{--font:'Inter',ui-sans-serif,system-ui,'Segoe UI',Roboto,sans-serif;--mono:'JetBrains Mono',ui-monospace,Consolas,monospace;
 --r:12px;--sb-w:236px}
html,body{margin:0!important;overflow-x:hidden!important}
body,.gradio-container{background:var(--app-bg)!important;color:var(--app-text)!important;font-family:var(--font)!important;
 font-size:14px;-webkit-font-smoothing:antialiased}
.gradio-container{max-width:100%!important;padding:0!important;min-height:100vh!important}
.gradio-container>.main,.gradio-container>.main>.wrap,.gradio-container .contain,.gradio-container .fillable,.gradio-container .app{
 padding:0!important;min-height:0!important;height:auto!important;max-width:none!important;width:100%!important;margin:0!important}
.gradio-container .gap{gap:0!important}
footer{display:none!important}
.style-holder{display:none!important;margin:0!important;padding:0!important;height:0!important;min-height:0!important;border:0!important}
/* ------- frame */
#app-layout{display:grid!important;grid-template-columns:var(--sb-w) minmax(0,1fr)!important;gap:0!important;align-items:start!important;
 margin:0!important;padding:0!important;flex-wrap:nowrap!important;width:100%!important}
#app-layout>*{min-width:0!important;max-width:none!important;flex:none!important}
#app-sidebar{background:var(--app-surface)!important;border-right:1px solid var(--app-line)!important;width:var(--sb-w)!important;
 padding:18px 12px!important;box-sizing:border-box!important;gap:0!important;position:sticky!important;top:0!important;height:100vh!important;
 overflow-y:auto!important;overflow-x:hidden!important;align-self:start!important;transition:width .2s}
#app-sidebar>*{background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important;margin:0!important}
.brand{display:flex;align-items:center;justify-content:center;padding:2px 8px 4px}.brand img{display:block;width:100%;max-width:150px;height:auto}
.brand img.sb-short{width:38px}.brand-sub{text-align:center;font-weight:600;font-size:11px;letter-spacing:1.4px;text-transform:uppercase;color:var(--app-muted);padding:0 0 16px}
.brand-mark{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;color:#fff;font-weight:700;font-size:13px;letter-spacing:.5px;
 background:linear-gradient(135deg,var(--app-accent),var(--app-violet));box-shadow:0 4px 16px var(--app-glow);flex:none}
.brand-name{font-weight:700;font-size:15px;letter-spacing:-.2px;line-height:1.15}.brand-name small{display:block;font-weight:500;font-size:11px;color:var(--app-muted);letter-spacing:0}
.sb-short{display:none!important}
#sidebar-toggle{min-width:0!important;width:100%!important;margin:0 0 12px!important;padding:5px 0!important;min-height:30px!important;
 background:transparent!important;color:var(--app-muted)!important;border:1px solid var(--app-line)!important;border-radius:8px!important;font-size:12px!important}
#sidebar-toggle:hover{color:var(--app-text)!important;background:var(--app-soft)!important}
.nav-cap{font-size:10.5px;font-weight:600;letter-spacing:.9px;text-transform:uppercase;color:var(--app-muted);padding:6px 10px 6px}
#sidebar-navigation,#sidebar-navigation .form,#sidebar-navigation .wrap,#sidebar-navigation .radio-group{
 background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important;gap:2px!important}
#sidebar-navigation [data-testid=block-info],#sidebar-navigation .label-wrap{display:none!important}
#sidebar-navigation label{display:flex!important;align-items:center!important;gap:11px!important;width:100%!important;min-height:40px!important;
 box-sizing:border-box!important;white-space:nowrap!important;padding:9px 11px!important;margin:0!important;border:0!important;
 background:transparent!important;color:var(--app-muted)!important;border-radius:9px!important;font-size:13.5px!important;
 font-weight:500!important;box-shadow:none!important;cursor:pointer;transition:background .15s,color .15s;position:relative}
#sidebar-navigation label::before{content:'';width:17px;height:17px;flex:none;background:currentColor;-webkit-mask-size:contain;mask-size:contain;
 -webkit-mask-repeat:no-repeat;mask-repeat:no-repeat;-webkit-mask-position:center;mask-position:center}
#sidebar-navigation label:hover{background:var(--app-soft)!important;color:var(--app-text)!important}
#sidebar-navigation label:has(input:checked){background:var(--app-soft)!important;color:var(--app-text)!important;font-weight:600!important}
#sidebar-navigation label:has(input:checked)::after{content:'';position:absolute;left:-12px;top:9px;bottom:9px;width:3px;border-radius:0 3px 3px 0;background:var(--app-accent)}
#sidebar-navigation label:has(input:checked)::before{color:var(--app-accent)}
#sidebar-navigation label span{color:inherit!important}
#sidebar-navigation input[type=radio]{position:absolute!important;opacity:0!important;width:1px!important;height:1px!important}
.session-mode{font-size:12px;color:var(--app-muted);margin:18px 6px 0;padding:14px 8px 0;border-top:1px solid var(--app-line)}
.session-mode b{color:var(--app-text)!important;display:block;margin-top:4px}
.app-shell{width:100%!important;max-width:1480px!important;box-sizing:border-box!important;padding:22px 32px 48px!important;margin:0 auto!important;gap:16px!important}
.topbar{display:flex!important;align-items:center;justify-content:space-between;gap:12px!important;margin:0 0 4px!important;flex-wrap:nowrap!important}
.topbar>*{min-width:0!important}.topbar button{min-width:200px!important;white-space:nowrap!important;height:36px!important}
.gradio-container .file-preview-holder,.gradio-container [data-testid=file] {min-height:0!important}
.crumb{font-size:12.5px;color:var(--app-muted);display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.crumb b{color:var(--app-text);font-weight:600}
.page-col{gap:16px!important;margin:0!important;padding:0!important}
/* ------- page head */
.page-head{display:flex;align-items:center;gap:14px;margin:0 0 4px}
.ph-icon{width:44px;height:44px;border-radius:12px;display:grid;place-items:center;color:var(--app-accent);background:var(--app-soft);
 border:1px solid var(--app-line);flex:none}
.ph-text h1{margin:0;font-size:22px;font-weight:700;letter-spacing:-.4px;color:var(--app-text)!important}
.ph-text p{margin:3px 0 0;color:var(--app-muted)!important;font-size:13px;line-height:1.45}
.ph-extra{margin-left:auto}
/* ------- panels */
.panel,.card{background:var(--app-surface)!important;border:1px solid var(--app-line)!important;border-radius:var(--r)!important;
 box-shadow:0 1px 0 rgba(255,255,255,.02) inset,0 8px 24px -16px rgba(0,0,0,.45)!important;min-width:0!important;overflow:visible!important}
.card{padding:20px!important;margin:0!important}
.card .card{border:0!important;padding:0!important;box-shadow:none!important;background:transparent!important}
.panel-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:16px 20px 0}
.panel-title{font-weight:600;font-size:14.5px;color:var(--app-text)}.panel-sub{font-size:12.5px;color:var(--app-muted);margin-top:2px;line-height:1.45}
.panel-body{padding:14px 20px 18px}
.card-title{font-size:15px;font-weight:600;margin:0 0 3px;color:var(--app-text)!important}
.muted,.card .muted{color:var(--app-muted)!important;font-size:12.5px!important;line-height:1.5!important;margin:0 0 8px}
.grid-2{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:16px!important}
.grid-3{display:grid!important;grid-template-columns:minmax(0,1.4fr) minmax(0,1fr)!important;gap:16px!important}
.grid-2>*,.grid-3>*{min-width:0!important;width:auto!important;max-width:none!important;flex:none!important}
/* ------- kpis */
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px}
.kpi{background:var(--app-surface);border:1px solid var(--app-line);border-radius:var(--r);padding:15px 17px;position:relative;overflow:hidden;
 transition:transform .15s,border-color .15s}
.kpi:hover{transform:translateY(-1px);border-color:var(--app-accent)}
.kpi-top{display:flex;justify-content:space-between;align-items:center;color:var(--app-muted);font-size:12.5px;font-weight:500}
.kpi-ico{display:grid;place-items:center;width:28px;height:28px;border-radius:8px;background:var(--app-soft);color:var(--app-accent)}
.kpi-value{font-size:28px;font-weight:700;letter-spacing:-.8px;margin-top:8px;color:var(--app-text);font-variant-numeric:tabular-nums}
.kpi-sub{font-size:12px;color:var(--app-muted);margin-top:2px;min-height:16px}
.k-ok .kpi-value{color:var(--app-ok)}.k-ok .kpi-ico{color:var(--app-ok)}.k-bad .kpi-value{color:var(--app-bad)}.k-bad .kpi-ico{color:var(--app-bad)}
.k-warn .kpi-ico{color:var(--app-warn)}.k-info .kpi-ico{color:var(--app-info)}
.metric{background:transparent!important;border:0!important;padding:0!important}
/* ------- badges, notes, empty */
.badge{display:inline-flex;align-items:center;gap:6px;padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:600;letter-spacing:.2px;
 border:1px solid transparent;white-space:nowrap}
.badge::before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}
.b-ok{color:var(--app-ok);background:color-mix(in srgb,var(--app-ok) 13%,transparent);border-color:color-mix(in srgb,var(--app-ok) 30%,transparent)}
.b-bad{color:var(--app-bad);background:color-mix(in srgb,var(--app-bad) 13%,transparent);border-color:color-mix(in srgb,var(--app-bad) 30%,transparent)}
.b-warn{color:var(--app-warn);background:color-mix(in srgb,var(--app-warn) 13%,transparent);border-color:color-mix(in srgb,var(--app-warn) 30%,transparent)}
.b-info{color:var(--app-info);background:color-mix(in srgb,var(--app-info) 13%,transparent);border-color:color-mix(in srgb,var(--app-info) 30%,transparent)}
.b-violet{color:var(--app-violet);background:color-mix(in srgb,var(--app-violet) 13%,transparent);border-color:color-mix(in srgb,var(--app-violet) 30%,transparent)}
.b-mute{color:var(--app-muted);background:var(--app-surface2);border-color:var(--app-line)}
.note{padding:12px 15px;border-radius:10px;border:1px solid var(--app-line);background:var(--app-surface2);font-size:13px;line-height:1.55;color:var(--app-text)}
.n-warn{border-color:color-mix(in srgb,var(--app-warn) 45%,transparent);background:color-mix(in srgb,var(--app-warn) 9%,transparent)}
.n-bad{border-color:color-mix(in srgb,var(--app-bad) 45%,transparent);background:color-mix(in srgb,var(--app-bad) 9%,transparent)}
.n-violet{border-color:color-mix(in srgb,var(--app-violet) 40%,transparent);background:color-mix(in srgb,var(--app-violet) 8%,transparent)}
.n-info{border-color:color-mix(in srgb,var(--app-info) 40%,transparent);background:color-mix(in srgb,var(--app-info) 8%,transparent)}
.empty{display:flex;flex-direction:column;align-items:center;text-align:center;padding:34px 16px;gap:6px}
.empty-ico{width:52px;height:52px;border-radius:14px;display:grid;place-items:center;background:var(--app-soft);color:var(--app-accent);border:1px dashed var(--app-line)}
.empty-title{font-weight:600;font-size:14px;margin-top:6px}.empty-text{color:var(--app-muted);font-size:12.5px;max-width:420px;line-height:1.5}
/* ------- tables */
.tbl-wrap{overflow-x:auto;border:1px solid var(--app-line);border-radius:10px}
.tbl{width:100%;border-collapse:collapse;font-size:13px}
.tbl th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.7px;color:var(--app-muted);font-weight:600;padding:10px 14px;background:var(--app-surface2);border-bottom:1px solid var(--app-line)}
.tbl td{padding:11px 14px;border-bottom:1px solid var(--app-line);vertical-align:top;color:var(--app-text);overflow-wrap:anywhere}
.tbl td:first-child{white-space:nowrap}.tbl tr:last-child td{border-bottom:0}.tbl tbody tr:hover td{background:var(--app-surface2)}
.mono{font-family:var(--mono);font-size:12px}
/* ------- progress steps (Create & Run) */
.step{display:flex;align-items:center;padding:9px 12px;border:1px solid var(--app-line);border-radius:9px;margin:5px 0;background:var(--app-surface2);
 color:var(--app-text)!important;font-size:12.5px;line-height:1.25;transition:border-color .2s,background .2s}
.step-dot{display:inline-block;flex:none;width:8px;height:8px;border-radius:50%;background:var(--app-muted);margin-right:10px;opacity:.55}
.step-status{margin-left:auto;color:var(--app-muted);padding-left:10px;text-align:right;flex:0 1 auto;min-width:0}
.step>.step-name{flex:1 1 auto;min-width:0;font-weight:500}
.status-running{border-color:var(--app-info)}.status-running .step-dot{background:var(--app-info);opacity:1;animation:pulse 1.2s infinite}
.status-completed .step-dot{background:var(--app-ok);opacity:1}.status-failed{border-color:color-mix(in srgb,var(--app-bad) 50%,transparent)}
.status-failed .step-dot{background:var(--app-bad);opacity:1}.status-waiting-for-approval{border-color:var(--app-warn);background:color-mix(in srgb,var(--app-warn) 8%,var(--app-surface2))}
.status-waiting-for-approval .step-dot{background:var(--app-warn);opacity:1;animation:pulse 1.2s infinite}.status-skipped .step-dot{background:var(--app-warn);opacity:.35}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 transparent}50%{box-shadow:0 0 0 5px var(--app-glow)}}
/* ------- workflow svg */
.wf-card{padding:8px 4px 0}.wf{width:100%;height:auto;display:block;font-family:var(--font)}
.gbox{fill:var(--app-surface2);stroke:var(--app-line);stroke-width:1.2;transition:all .2s}
.gdot{fill:var(--app-muted);opacity:.5}.gtitle{font-size:12.5px;font-weight:600;fill:var(--app-text)}
.grole{font-size:10px;fill:var(--app-muted)}.gstat{font-size:10.5px;font-weight:600;fill:var(--app-muted)}
.visits{font-size:10px;fill:var(--app-muted);font-weight:600}.gate{font-size:9px;font-weight:700;letter-spacing:1px;fill:var(--app-warn)}
.g-running .gbox{stroke:var(--app-info);fill:color-mix(in srgb,var(--app-info) 10%,var(--app-surface2));stroke-width:1.8}.g-running .gdot{fill:var(--app-info);opacity:1;animation:blink 1.1s infinite}
.g-running .gstat{fill:var(--app-info)}
.g-completed .gbox{stroke:color-mix(in srgb,var(--app-ok) 60%,transparent)}.g-completed .gdot{fill:var(--app-ok);opacity:1}.g-completed .gstat{fill:var(--app-ok)}
.g-failed .gbox{stroke:var(--app-bad);fill:color-mix(in srgb,var(--app-bad) 9%,var(--app-surface2))}.g-failed .gdot{fill:var(--app-bad);opacity:1}.g-failed .gstat{fill:var(--app-bad)}
.g-waiting-for-approval .gbox{stroke:var(--app-warn);fill:color-mix(in srgb,var(--app-warn) 11%,var(--app-surface2));stroke-width:1.8}
.g-waiting-for-approval .gdot{fill:var(--app-warn);opacity:1;animation:blink 1.1s infinite}.g-waiting-for-approval .gstat{fill:var(--app-warn)}
.g-skipped{opacity:.55}.g-skipped .gstat{fill:var(--app-muted)}
@keyframes blink{50%{opacity:.25}}
.e-solid,.e-cond,.e-loop,.e-exit{fill:none;stroke-width:1.6}.e-solid{stroke:var(--app-muted)}.e-cond{stroke:var(--app-accent);stroke-dasharray:5 4}
.e-loop{stroke:var(--app-violet);stroke-dasharray:2 4;stroke-width:2}.e-exit{stroke:var(--app-warn);stroke-dasharray:3 5;opacity:.75;stroke-width:1.3}
.k-llm .gbox{fill:color-mix(in srgb,var(--app-violet) 22%,var(--app-surface2));stroke:var(--app-violet)}
.k-opt .gbox{stroke-dasharray:5 4}.k-rep .gbox{fill:color-mix(in srgb,var(--app-ok) 16%,var(--app-surface2));stroke:var(--app-ok)}
.g-static.k-opt .gbox{fill:transparent}.g-static.k-mcp .gbox{fill:color-mix(in srgb,var(--app-info) 8%,var(--app-surface2))}
.e-opt{fill:none;stroke:var(--app-muted);stroke-dasharray:3 4;stroke-width:1.4}.e-label-cond{fill:var(--app-accent)}
.lg-box{display:inline-block;width:14px;height:12px;border-radius:3px;border:1.5px solid var(--app-line);background:var(--app-surface2)}
.lg-box.llm{background:color-mix(in srgb,var(--app-violet) 35%,transparent);border-color:var(--app-violet)}.lg-box.opt{border-style:dashed}
.arrow{fill:var(--app-muted)}.e-label{font-size:9.5px;fill:var(--app-warn);opacity:.9}.e-label-loop{fill:var(--app-violet)}
.wf-legend{display:flex;flex-wrap:wrap;gap:6px 18px;padding:12px 6px 4px;font-size:11.5px;color:var(--app-muted);align-items:center}
.wf-legend span{display:inline-flex;align-items:center;gap:7px}.wf-legend .sep{flex:1}
.lg-line{display:inline-block;width:22px;height:0;border-top:2px solid var(--app-muted)}.lg-line.cond{border-top:2px dashed var(--app-accent)}
.lg-line.exit{border-top:2px dotted var(--app-warn)}.lg-line.loop{border-top:2px dotted var(--app-violet)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%}.d-ok{background:var(--app-ok)}.d-bad{background:var(--app-bad)}.d-warn{background:var(--app-warn)}
.d-info{background:var(--app-info)}.d-mute{background:var(--app-muted);opacity:.5}.d-accent{background:var(--app-accent)}.d-violet{background:var(--app-violet)}
/* ------- charts */
.donut-wrap{display:flex;align-items:center;gap:22px;flex-wrap:wrap}.donut{width:150px;height:150px;flex:none}
.track{stroke:var(--app-surface2)}.s-ok{stroke:var(--app-ok)}.s-bad{stroke:var(--app-bad)}.s-warn{stroke:var(--app-warn)}.s-info{stroke:var(--app-info)}.s-mute{stroke:var(--app-muted)}.s-violet{stroke:var(--app-violet)}.s-accent{stroke:var(--app-accent)}
.s-fill-ok{fill:var(--app-ok);background:var(--app-ok)}.s-fill-bad{fill:var(--app-bad);background:var(--app-bad)}.s-fill-warn{fill:var(--app-warn);background:var(--app-warn)}
.s-fill-info{fill:var(--app-info);background:var(--app-info)}.s-fill-accent{fill:var(--app-accent);background:var(--app-accent)}.s-fill-violet{fill:var(--app-violet);background:var(--app-violet)}.s-fill-mute{fill:var(--app-muted);background:var(--app-muted)}
.dc-main{font-size:20px;font-weight:700;fill:var(--app-text);text-anchor:middle}.dc-sub{font-size:8.5px;fill:var(--app-muted);text-anchor:middle;letter-spacing:.5px}
.legend{display:flex;flex-direction:column;gap:7px;min-width:150px;flex:1}.lg{display:flex;align-items:center;gap:9px;font-size:12.5px;color:var(--app-muted)}
.lg b{margin-left:auto;color:var(--app-text);font-variant-numeric:tabular-nums}.lg em{font-style:normal;width:38px;text-align:right;font-size:11.5px}
.chart{width:100%;height:auto;display:block}.grid{stroke:var(--app-line);stroke-width:1}.axis{font-size:9.5px;fill:var(--app-muted);text-anchor:middle}
.bar-val{font-size:9.5px;fill:var(--app-text);text-anchor:middle;font-weight:600}
.hbars{display:flex;flex-direction:column;gap:11px}.hb{display:grid;grid-template-columns:minmax(90px,150px) 1fr 46px;gap:12px;align-items:center;font-size:12.5px}
.hb-l{color:var(--app-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.hb-t{height:8px;background:var(--app-surface2);border-radius:99px;overflow:hidden}
.hb-f{height:100%;border-radius:99px}.hb b{text-align:right;font-variant-numeric:tabular-nums}
/* ------- diff */
.diff{border:1px solid var(--app-line);border-radius:10px;overflow:hidden;font-family:var(--mono);font-size:12px;background:var(--app-surface2)}
.dl{display:flex;line-height:1.65;white-space:pre-wrap;overflow-wrap:anywhere}.dl-gut{width:26px;flex:none;text-align:center;color:var(--app-muted);user-select:none}
.dl-add{background:color-mix(in srgb,var(--app-ok) 14%,transparent)}.dl-add .dl-gut{color:var(--app-ok)}.dl-del{background:color-mix(in srgb,var(--app-bad) 14%,transparent)}.dl-del .dl-gut{color:var(--app-bad)}
.dl-hunk{background:color-mix(in srgb,var(--app-info) 10%,transparent);color:var(--app-info)}.dl-meta{color:var(--app-muted)}.dl-code{padding-right:10px;flex:1}
.kv{display:grid;grid-template-columns:150px 1fr;gap:9px 16px;font-size:13px}.kv dt{color:var(--app-muted)}.kv dd{margin:0;overflow-wrap:anywhere}
.approval-box{border:1px solid var(--app-warn);border-radius:var(--r);background:color-mix(in srgb,var(--app-warn) 6%,var(--app-surface))}
.stack{display:flex;flex-direction:column;gap:14px}
.tag-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.log{font-family:var(--mono);font-size:12px;line-height:1.7;color:var(--app-muted)}.log b{color:var(--app-text);font-weight:500}
/* ------- gradio controls */
.card label,.card label span,.card span:not(.badge),.card .prose{color:var(--app-text)!important}
.card [data-testid=block-info],.card .info{color:var(--app-muted)!important}
.card input:not([type=radio]):not([type=checkbox]),.card textarea,.card select,.card [role=combobox],.card .secondary-wrap,.card .input-container{
 background:var(--app-surface2)!important;color:var(--app-text)!important;border:1px solid var(--app-line)!important;border-radius:9px!important;box-shadow:none!important}
.card input:focus,.card textarea:focus{border-color:var(--app-accent)!important;box-shadow:0 0 0 3px var(--app-glow)!important}
.card input:not([type=radio]):not([type=checkbox]),.card textarea{padding:10px 12px!important}
.card [role=combobox] *,.card [data-testid=dropdown] *{color:var(--app-text)!important}
.card input::placeholder,.card textarea::placeholder{color:var(--app-muted)!important;opacity:.8!important}
.card .form,.card .styler,.card .block,.card .block.padded{background:transparent!important;border-color:transparent!important;box-shadow:none!important}
.card label:has(input[type=radio]),.card label:has(input[type=checkbox]),.card .radio-group,.card .checkbox-group,.card [role=radiogroup]{background:transparent!important;border-color:transparent!important;box-shadow:none!important}
.card [role=radiogroup] label,.card .radio-group label{background:var(--app-surface2)!important;border:1px solid var(--app-line)!important;border-radius:8px!important;padding:7px 14px!important;transition:all .15s}
.card [role=radiogroup] label:has(input:checked),.card .radio-group label:has(input:checked){background:var(--app-soft)!important;border-color:var(--app-accent)!important;color:var(--app-accent)!important}
.card input[type=radio],.card input[type=checkbox],.card input[type=range]{accent-color:var(--app-accent)!important}
button.primary,.btn-primary{background:linear-gradient(180deg,var(--app-accent),color-mix(in srgb,var(--app-accent) 82%,#000))!important;color:#fff!important;border:0!important;
 border-radius:9px!important;font-weight:600!important;box-shadow:0 4px 14px -4px var(--app-glow)!important;transition:transform .12s,filter .15s}
button.primary:hover{filter:brightness(1.1);transform:translateY(-1px)}
button.secondary{background:var(--app-surface2)!important;color:var(--app-text)!important;border:1px solid var(--app-line)!important;border-radius:9px!important;font-weight:500!important}
button.secondary:hover{background:var(--app-soft)!important;border-color:var(--app-accent)!important}
button.stop{background:color-mix(in srgb,var(--app-bad) 16%,transparent)!important;color:var(--app-bad)!important;border:1px solid color-mix(in srgb,var(--app-bad) 50%,transparent)!important;border-radius:9px!important;font-weight:600!important}
button.stop:hover{background:var(--app-bad)!important;color:#fff!important}
#start-testing{min-height:44px!important;width:100%!important}
#approve-btn,#confirm-btn{background:var(--app-ok)!important;color:#04130c!important;border:0!important;font-weight:700!important;border-radius:9px!important}
#scenario-controls{gap:12px!important;align-items:start!important}
#scenario-controls>.form{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:12px 20px!important;min-width:0!important;width:100%!important}
#scenario-controls>.form>*{min-width:0!important;width:100%!important;max-width:none!important;flex:none!important;margin:0!important}
#request-layout{display:grid!important;grid-template-columns:var(--request-layout-columns,minmax(0,3fr) minmax(0,2fr))!important;gap:16px!important;align-items:start!important;margin:0!important;padding:0!important}
#request-card-column,#progress-card-column{margin:0!important;padding:0!important;min-width:0!important;width:auto!important;max-width:none!important;flex:none!important;gap:16px!important;align-self:start!important}
.dataframe,[data-testid=dataframe],.table-wrap{border-radius:10px!important}
.tabs>.tab-wrapper,.tab-wrapper{border-color:var(--app-line)!important}.tab-container button,.tabs button[role=tab]{color:var(--app-muted)!important;font-weight:500!important}
button[role=tab][aria-selected=true]{color:var(--app-text)!important;border-color:var(--app-accent)!important}
.prose,.prose *{color:var(--app-text)!important}.prose pre,.prose code{background:var(--app-surface2)!important;border-radius:8px}
@media(max-width:1100px){#request-layout{--request-layout-columns:minmax(0,1fr)!important}.grid-2,.grid-3{grid-template-columns:minmax(0,1fr)!important}}
@media(max-width:820px){.app-shell{padding:14px!important}#app-layout{grid-template-columns:minmax(0,1fr)!important}
 #app-sidebar{position:relative!important;width:100%!important;height:auto!important}#scenario-controls>.form{grid-template-columns:minmax(0,1fr)!important}}
""" + _NAV_ICON_CSS
