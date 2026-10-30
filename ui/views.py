"""Page renderers that depend only on persisted history (Overview, Analytics, persisted reports)."""

from __future__ import annotations
from datetime import datetime

from ui import design as D
from ui import history as H


def _fmt_time(iso: str | None) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return "—"


def _fmt_ms(ms: float | None) -> str:
    return "—" if not ms else (f"{ms / 1000:.1f}s" if ms < 60000 else f"{ms / 60000:.1f}m")


def _short_url(url: str, n: int = 38) -> str:
    return url if len(url) <= n else url[:n - 1] + "…"


def _mode_badge(rec: dict) -> str:
    return D.badge("Mock" if rec.get("mock") else "Live", "violet" if rec.get("mock") else "info")


def recent_runs_table(records: list[dict], limit: int = 8) -> str:
    rows = []
    for r in sorted(records, key=lambda r: r.get("started") or "", reverse=True)[:limit]:
        rows.append([_fmt_time(r.get("started")), D.badge(r.get("status")), _mode_badge(r), _short_url(r.get("url") or "—"),
                     f"{r.get('passed', 0)} / {r.get('failed', 0)} / {r.get('skipped', 0)}",
                     "UI run" if r.get("source") == "ui" else "Report file"])
    if not rows:
        return D.empty("No runs recorded yet", "Start a test from Create & Run. Runs appear here as soon as they are recorded.", "inbox")
    return D.table(["Started", "Status", "Mode", "Application", "Pass / Fail / Other", "Source"], rows, raw_cols=(1, 2))


def overview_html(records: list[dict], pending: int) -> str:
    s = H.summarize(records)
    rate = f"{s['success_rate']:.0f}%" if s["success_rate"] is not None else "—"
    kpis = D.kpi_row(
        D.kpi("Total test runs", str(s["runs"]), f"{s['ui_runs']} from this UI · {s['runs'] - s['ui_runs']} report files", "", "activity"),
        D.kpi("Passed runs", str(s["passed_runs"]), "terminal status PASS", "ok", "check"),
        D.kpi("Failed runs", str(s["failed_runs"]), "terminal status FAIL", "bad", "x"),
        D.kpi("Success rate", rate, f"of {s['finished']} finished runs" if s["finished"] else "no finished runs yet", "info", "chart"),
        D.kpi("Awaiting approval", str(pending), "human decision required" if pending else "nothing pending",
              "warn" if pending else "", "shield"),
    )
    note = ""
    if s["mock_runs"]:
        note = D.note(f"{s['mock_runs']} of these runs were <b>mock-mode</b> simulations (no real LLM or browser). They are labelled "
                      "<i>Mock</i> everywhere and are not real test results.", "violet")
    return (f"<div class='stack'>{kpis}{note}{D.panel('Recent activity', recent_runs_table(records), 'Most recent runs, newest first. Open Reports for full results.')}</div>")


def analytics_html(window: str, source: str, include_mock: bool) -> str:
    all_records = H.load_records()
    records = H.filter_records(all_records, window, source, include_mock)
    s = H.summarize(records)
    if not records:
        return D.empty("No runs match these filters",
                       "Widen the time range, include mock runs, or start a test. Charts only ever show recorded runs.", "chart")
    rate = f"{s['success_rate']:.0f}%" if s["success_rate"] is not None else "—"
    approvals = s["decisions"]
    kpis = D.kpi_row(
        D.kpi("Runs", str(s["runs"]), f"{s['finished']} finished", "", "activity"),
        D.kpi("Success rate", rate, "PASS / finished runs", "ok", "check"),
        D.kpi("Avg execution time", _fmt_ms(s["avg_duration_ms"]),
              f"from {s['duration_runs']} timed UI run(s)" if s["duration_runs"] else "no timed runs", "info", "clock"),
        D.kpi("Validation failures", str(s["validation_failures"]), "UI runs with a failed validation", "bad" if s["validation_failures"] else "", "alert"),
        D.kpi("Fix proposals", str(s["fix_proposed"]), f"{s['healing_runs']} run(s) healed", "", "zap"),
        D.kpi("Approvals / rejections", f"{approvals.get('approved', 0)} / {approvals.get('rejected', 0)}", "human decisions", "warn", "shield"),
    )
    tone = {"PASS": "ok", "FAIL": "bad", "BLOCKED": "warn", "ERROR": "bad", "PENDING": "info", "NOT_RUN": "mute"}
    dist = D.donut([(k.title().replace("_", " "), v, tone.get(k, "mute")) for k, v in s["status"].most_common()],
                   str(s["runs"]), "RUNS")
    days = D.columns([(d, c) for d, c in s["per_day"].items()], "accent")
    ui = [r for r in records if r.get("source") == "ui" and r.get("duration_ms")][-20:]
    times = D.columns([(f"#{i}", round(r["duration_ms"] / 1000, 1)) for i, r in enumerate(ui, 1)], "info", "s") if ui else \
        D.empty("No timed runs", "Execution time is recorded for UI runs that executed tests.", "clock")
    ftypes = D.hbars([(k, v, "bad") for k, v in s["failure_types"].most_common()])
    appr = D.donut([("Approved", approvals.get("approved", 0), "ok"), ("Rejected", approvals.get("rejected", 0), "bad")],
                   str(sum(approvals.values())), "DECISIONS")
    nodes = D.hbars([(k, v, "accent") for k, v in s["nodes"].most_common()])
    sc = s["scenarios"]
    scen = D.donut([("Passed", sc["passed"], "ok"), ("Failed", sc["failed"], "bad"), ("Not run / skipped", sc["skipped"], "mute")],
                   str(sc["total"]), "SCENARIOS")
    notes = [f"Range: <b>{D.esc(window)}</b> · Source: <b>{D.esc(source)}</b> · {s['ui_runs']} UI run(s), {s['runs'] - s['ui_runs']} report file(s)."]
    if s["mock_runs"]:
        notes.append(f"{s['mock_runs']} run(s) are mock-mode simulations. Untick “Include mock runs” to hide them.")
    notes.append("Failure categories, node counts, approvals, validation and timing come only from UI runs; report files carry status and scenario counts only.")
    grid = (f"<div class='grid-2'>{D.panel('Pass vs. fail distribution', dist, 'Terminal status of each run')}"
            f"{D.panel('Runs over time', days, 'Runs started per day')}"
            f"{D.panel('Scenario outcomes', scen, 'Across all runs in range')}"
            f"{D.panel('Execution time per run', times, 'Seconds, last 20 timed UI runs')}"
            f"{D.panel('Failure categories', ftypes, 'Analyzer classification, UI runs')}"
            f"{D.panel('Human approval vs. rejection', appr, 'Decisions submitted through the approval gate')}"
            f"{D.panel('AI workflow node executions', nodes, 'Times each LangGraph node ran, UI runs')}</div>")
    return f"<div class='stack'>{kpis}{grid}<div class='note'>{'<br>'.join(notes)}</div></div>"


def persisted_reports_table() -> str:
    dirs = H.list_report_dirs()
    if not dirs:
        return D.empty("No persisted reports", "Report files appear as runs/<run id>/report.md or report.html.", "file")
    by_dir = {r.get("report_dir"): r for r in H.load_records() if r.get("source") == "report"}
    rows = []
    for d in dirs[:30]:
        rec = by_dir.get(d, {})
        files = ", ".join(n for n in ("report.md", "report.html") if H.report_file(d, n))
        rows.append([d, D.badge(rec.get("status")) if rec else "—", _fmt_time(rec.get("started")), rec.get("url") or "—", files])
    more = f"<div class='muted' style='margin-top:8px'>Showing 30 of {len(dirs)}.</div>" if len(dirs) > 30 else ""
    return D.table(["Run folder", "Status", "Written", "Application", "Files"], rows, raw_cols=(1,)) + more
