"""Run history for the dashboard: persisted UI run records, legacy report files, and analytics aggregation.

Only data that really exists is aggregated. Nothing here calls an agent, a model or the workflow.
"""

from __future__ import annotations
import json
import os
import re
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "runs"
FINAL_STATUSES = ("PASS", "FAIL", "BLOCKED", "ERROR")
_LOCK = threading.Lock()


def history_path() -> Path:
    """UI run records. Overridable (tests point it at a temporary file) so they never pollute real history."""
    override = os.getenv("QC_UI_HISTORY")
    return Path(override) if override else RUNS_DIR / "ui_history.jsonl"


def save_record(record: dict) -> None:
    """Append one run snapshot; a later line for the same run id supersedes the earlier one."""
    try:
        path = history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK, path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # history is a convenience; never break a workflow because it could not be written


def _ui_records() -> list[dict]:
    path = history_path()
    if not path.is_file():
        return []
    latest: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("id"):
            latest[rec["id"]] = rec
    return list(latest.values())


def _field(text: str, label: str) -> str | None:
    m = re.search(rf"\|\s*\*\*{re.escape(label)}\*\*\s*\|\s*(.*?)\s*\|", text)
    return m.group(1) if m else None


def _report_file_records(skip_run_ids: set[str]) -> list[dict]:
    """Legacy `runs/<id>/report.md` files, parsed read-only."""
    records = []
    if not RUNS_DIR.is_dir():
        return records
    for md in RUNS_DIR.glob("*/report.md"):
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
            run_id = _field(text, "Run ID") or md.parent.name
            if run_id in skip_run_ids:
                continue
            counts = re.search(r"\|\s*Total\s*\|\s*Passed\s*\|\s*Failed\s*\|\s*Blocked\s*\|\s*\n\|[-| ]+\|\s*\n\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)", text)
            total, passed, failed, blocked = (int(x) for x in counts.groups()) if counts else (0, 0, 0, 0)
            heal = _field(text, "Healing attempts") or "none"
            models = re.findall(r"^\|\s*(\w+)\s*\|\s*([^|]+?)\s*\|\s*$", text.split("## Models used")[-1].split("##")[0], re.M)
            started = datetime.fromtimestamp(md.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
            records.append({
                "id": f"file:{md.parent.name}", "run_id": run_id, "source": "report", "started": started, "ended": started,
                "mock": any("mock" in m[1].lower() for m in models), "status": (_field(text, "Status") or "UNKNOWN").upper(),
                "url": _field(text, "Target URL") or "", "total": total, "passed": passed, "failed": failed,
                "skipped": max(total - passed - failed - blocked, 0), "duration_ms": None,
                "healing": int(heal) if heal.isdigit() else 0, "failure_type": None, "fix_proposed": False,
                "decisions": [], "trail": [], "validation_failed": False,
                "report_dir": md.parent.name,
            })
        except OSError:
            continue
    return records


def load_records() -> list[dict]:
    ui = _ui_records()
    records = ui + _report_file_records({r.get("run_id") for r in ui})
    return sorted(records, key=lambda r: r.get("started") or "")


def _when(rec: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(rec["started"])
    except (KeyError, TypeError, ValueError):
        return None


def filter_records(records: list[dict], window: str = "All time", source: str = "All sources",
                   include_mock: bool = True) -> list[dict]:
    days = {"Last 24 hours": 1, "Last 7 days": 7, "Last 30 days": 30}.get(window)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days) if days else None
    out = []
    for rec in records:
        if source == "UI runs" and rec.get("source") != "ui":
            continue
        if source == "Report files" and rec.get("source") != "report":
            continue
        if not include_mock and rec.get("mock"):
            continue
        when = _when(rec)
        if cutoff and (when is None or when < cutoff):
            continue
        out.append(rec)
    return out


def summarize(records: list[dict]) -> dict:
    """Every number the dashboards show, computed from the given records only."""
    finished = [r for r in records if r.get("status") in FINAL_STATUSES]
    status = Counter(r.get("status") or "UNKNOWN" for r in records)
    ui = [r for r in records if r.get("source") == "ui"]
    durations = [r["duration_ms"] for r in ui if r.get("duration_ms")]
    scenarios = {k: sum(int(r.get(k) or 0) for r in records) for k in ("total", "passed", "failed", "skipped")}
    per_day: Counter = Counter()
    for r in records:
        when = _when(r)
        if when:
            per_day[when.astimezone().date().isoformat()] += 1
    decisions = Counter(d for r in ui for d in r.get("decisions") or [])
    nodes = Counter(re.sub(r" \(.*\)$", "", step) for r in ui for step in r.get("trail") or [])
    return {
        "runs": len(records), "finished": len(finished), "status": status,
        "passed_runs": status.get("PASS", 0), "failed_runs": status.get("FAIL", 0),
        "success_rate": (status.get("PASS", 0) / len(finished) * 100) if finished else None,
        "scenarios": scenarios, "per_day": dict(sorted(per_day.items())),
        "avg_duration_ms": (sum(durations) / len(durations)) if durations else None, "duration_runs": len(durations),
        "failure_types": Counter(r["failure_type"] for r in ui if r.get("failure_type")),
        "validation_failures": sum(1 for r in ui if r.get("validation_failed")),
        "fix_proposed": sum(1 for r in ui if r.get("fix_proposed")),
        "healing_runs": sum(1 for r in ui if int(r.get("healing") or 0) > 0),
        "decisions": decisions, "nodes": nodes, "ui_runs": len(ui),
        "mock_runs": sum(1 for r in records if r.get("mock")),
    }


def list_report_dirs() -> list[str]:
    if not RUNS_DIR.is_dir():
        return []
    dirs = [p for p in RUNS_DIR.iterdir() if p.is_dir() and ((p / "report.md").is_file() or (p / "report.html").is_file())]
    return [p.name for p in sorted(dirs, key=lambda p: p.stat().st_mtime, reverse=True)]


def report_file(run_dir: str, name: str) -> Path | None:
    """Resolve a persisted report file; only `report.md` / `report.html` inside `runs/<dir>/` are ever served."""
    if name not in ("report.md", "report.html") or not re.fullmatch(r"[A-Za-z0-9_.-]+", run_dir or ""):
        return None
    path = (RUNS_DIR / run_dir / name).resolve()
    if RUNS_DIR.resolve() not in path.parents or not path.is_file():
        return None
    return path



def clear_history(extra_dirs: tuple[Path, ...] = ()) -> int:
    """Delete recorded history: the UI run log, saved report.md / report.html files and exported reports.

    Test specs, traces and other run artifacts are left alone. Returns the number of files removed.
    """
    removed = 0
    targets = [history_path()]
    if RUNS_DIR.is_dir():
        for run_dir in RUNS_DIR.iterdir():
            if run_dir.is_dir():
                targets += [run_dir / "report.md", run_dir / "report.html"]
    for folder in extra_dirs:
        if folder.is_dir():
            targets += [f for f in folder.iterdir() if f.is_file()]
    with _LOCK:
        for path in targets:
            try:
                if path.is_file():
                    path.unlink()
                    removed += 1
            except OSError:
                continue
    return removed
