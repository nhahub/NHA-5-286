"""
Purpose: Build the report_model from the final run state, and decide the terminal status.
Reads: the whole state (test_request, target_url, test_plan, generated_test_files, execution_result,
       execution_evidence, failure_analysis, failure_type, fix_proposal, approval_decision, counters,
       models_used, errors, terminal_status)
Writes: N/A (pure functions; run_report in exporters.py puts terminal_status and report_path in the state)
Must not: re-run tests, call agents, change a result, or reclassify a failure
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agents.codegen import scenario_id
from llm.errors import LLM_FATAL_TAG, redact

SCHEMA_VERSION = 1
if TYPE_CHECKING:
    from contracts.report import ReportModel


def _is_blocked(scenario: Mapping[str, Any]) -> bool:
    return str(scenario.get("status") or "").upper().startswith("BLOCKED")


def _sid_from_name(name: str) -> str:
    base = Path(name).name
    return base.split("-", 1)[0] if "-" in base else base.split(".", 1)[0]


def generatable_scenarios(plan: Sequence[Mapping[str, Any]]) -> list[tuple[str, Mapping[str, Any]]]:
    return [(scenario_id(i, s), s) for i, s in enumerate(plan) if not _is_blocked(s)]

MAX_CODE_CHARS = 20_000  # a report must stay readable and small
FAILURE_CLASSES = ("Test", "Application", "Environment", "Infrastructure")
VALID_STATUSES = ("PASS", "FAIL", "BLOCKED", "ERROR")
# codegen writes "codegen[s1]: ..." for ONE scenario it could not generate: that is BLOCKED, not a crash
_SCENARIO_LEVEL_ERROR = re.compile(r"^codegen\[")


# ----------------------------------------------------------------- input adapters
# ASSUMPTIONS about other people's state shapes live in this section. If P1/P3/P4 change a shape,
# change ONLY these helpers (requirements_text, parse_playwright_results, _evidence_items, _target).
def requirements_text(state: Mapping[str, Any]) -> str:
    request = state.get("test_request") or {}
    for key in ("requirements", "requirement", "text"):
        if request.get(key):
            return str(request[key])
    return ""


def _is_not_english(text: str) -> bool:
    return any(ord(ch) > 127 and ch.isalpha() for ch in text)


def _target(state: Mapping[str, Any]) -> dict[str, Any]:
    raw = state.get("target_url")
    if isinstance(raw, Mapping):
        return {"url": raw.get("url"), "source": raw.get("source")}
    if isinstance(raw, (tuple, list)) and len(raw) == 2:
        return {"url": raw[0], "source": raw[1]}
    return {"url": raw if isinstance(raw, str) else None, "source": None}


def parse_playwright_results(raw: Any) -> dict[str, dict[str, Any]]:
    """Playwright JSON reporter output -> {scenario_id: {"status": passed|failed|skipped, "duration_s"}}.
    The scenario id is the prefix of the spec file name (s1-add-todo.spec.ts -> s1)."""
    found: dict[str, dict[str, Any]] = {}

    def add(sid: str, status: str, seconds: float) -> None:
        if not sid:
            return
        old = found.get(sid)
        if old is None:
            found[sid] = {"status": status, "duration_s": seconds}
            return
        order = {"failed": 2, "skipped": 1, "passed": 0}
        if order[status] > order[old["status"]]:
            old["status"] = status
        old["duration_s"] += seconds

    def walk(suite: Mapping[str, Any]) -> None:
        for spec in suite.get("specs") or []:
            tests = spec.get("tests") or []
            statuses = [t.get("status") for t in tests]
            millis = sum(r.get("duration") or 0 for t in tests for r in t.get("results") or [])
            if "unexpected" in statuses or spec.get("ok") is False:
                status = "failed"
            elif statuses and all(s == "skipped" for s in statuses):
                status = "skipped"
            else:
                status = "passed"
            add(_sid_from_name(str(spec.get("file") or suite.get("file") or "")), status, millis / 1000)
        for child in suite.get("suites") or []:
            walk(child)

    if isinstance(raw, Mapping):
        for suite in raw.get("suites") or []:
            walk(suite)
    return found


def load_execution_results(raw: Any) -> Any:
    """The real executor keeps only the stats and a path in state; read the Playwright JSON it points to.

    Only a file literally named results.json is read, and only when the state itself has no suites.
    """
    if not isinstance(raw, Mapping) or raw.get("suites"):
        return raw
    path = raw.get("results_path")
    if isinstance(path, str) and Path(path).name == "results.json":
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return raw
        if isinstance(data, Mapping):
            return {**data, **{k: v for k, v in raw.items() if k not in data}}
    return raw


def _total_duration(raw: Any) -> float | None:
    stats = raw.get("stats") if isinstance(raw, Mapping) else None
    millis = stats.get("duration") if isinstance(stats, Mapping) else None
    return round(millis / 1000, 1) if isinstance(millis, (int, float)) else None


def _evidence_items(raw: Any) -> list[dict[str, Any]]:
    """execution_evidence (P3) -> report evidence. Handles both dicts and Evidence models."""
    items: list[dict[str, Any]] = []
    for e in raw or []:
        if hasattr(e, "model_dump"):
            e = e.model_dump()
        if not isinstance(e, Mapping):
            continue
        items.append({
            "scenario_id": str(e.get("scenario_id") or e.get("scenario_name") or ""),
            "final_url": e.get("final_url"),
            "screenshot": e.get("screenshot") or e.get("screenshot_path"),
            "trace": e.get("trace") or e.get("trace_path"),
            "console_errors": list(e.get("console_errors") or e.get("console") or e.get("console_log") or []),
            "failed_requests": list(e.get("failed_requests") or e.get("network") or e.get("network_errors") or []),
        })
    return items


def _healing(raw: Any) -> dict[str, int]:
    """healing_retry_count is a per-test dict; an old plain int is shown under 'all'."""
    if isinstance(raw, Mapping):
        return {str(k): int(v) for k, v in raw.items() if v}
    return {"all": int(raw)} if isinstance(raw, int) and raw else {}


# ------------------------------------------------------------------------ builders
def _scenario_ids(plan: Sequence[Mapping[str, Any]]) -> list[str]:
    """Same ids codegen used. Scenarios that never got code (BLOCKED) get a positional id."""
    by_object = {id(s): sid for sid, s in generatable_scenarios(plan)}
    return [by_object.get(id(s), f"s{i + 1}") for i, s in enumerate(plan)]


def _scenario(scenario: Mapping[str, Any], sid: str, files: Mapping[str, Path],
              results: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": sid,
        "name": str(scenario.get("name") or sid),
        "duration_s": None,
        "blocked_reason": None,
        "expected_result": scenario.get("expected_result"),
        "steps": [
            {"action": s.get("action"), "target": s.get("target"), "value": s.get("value")}
            for s in scenario.get("steps") or [] if isinstance(s, Mapping)
        ],
    }
    if _is_blocked(scenario):
        item["status"] = "BLOCKED"
        item["blocked_reason"] = str(scenario.get("status") or "").partition(":")[2].strip() or "blocked"
    elif sid in results:
        result = results[sid]
        item["status"] = {"passed": "PASSED", "failed": "FAILED"}.get(result["status"], "NOT_RUN")
        item["duration_s"] = round(result["duration_s"], 1)
    elif sid not in files:
        item["status"] = "BLOCKED"
        item["blocked_reason"] = "could not generate"
    else:
        item["status"] = "NOT_RUN"
    return item


def _counts(scenarios: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    def n(status: str) -> int:
        return sum(1 for s in scenarios if s["status"] == status)

    return {"total": len(scenarios), "passed": n("PASSED"), "failed": n("FAILED"), "blocked": n("BLOCKED")}


def decide_terminal_status(state: Mapping[str, Any], scenarios: Sequence[Mapping[str, Any]]) -> str:
    """Deterministic status from the spec: PASS all passed; FAIL a scenario failed and the cause is
    identified; BLOCKED a scenario could not run; ERROR the system itself broke.
    OPEN QUESTION (the spec is silent): a mix of FAILED and BLOCKED. Here FAIL wins; P5 may change it."""
    preset = state.get("terminal_status")
    if preset in VALID_STATUSES:  # set earlier by intake or the router: never overwritten
        return str(preset)
    errors = [str(e) for e in state.get("errors") or []]
    if state.get("validation_status") == "error" or any(
        e.startswith(LLM_FATAL_TAG) or not _SCENARIO_LEVEL_ERROR.match(e) for e in errors
    ):
        return "ERROR"  # node crash, no usable LLM, or broken tooling
    statuses = {s["status"] for s in scenarios}
    if not statuses:
        return "ERROR"
    if "FAILED" in statuses:
        analysis = state.get("failure_analysis")
        failure_type = state.get("failure_type") or (analysis or {}).get("failure_type")
        # "never a guess": a failure without an identified, valid class is an ERROR
        return "FAIL" if analysis and failure_type in FAILURE_CLASSES else "ERROR"
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if "NOT_RUN" in statuses:
        return "ERROR"  # a scenario neither ran nor was blocked: something broke
    return "PASS"


def build_report_model(state: Mapping[str, Any]) -> ReportModel:
    plan = list(state.get("test_plan") or [])
    ids = _scenario_ids(plan)
    files = {_sid_from_name(str(p)): Path(str(p)) for p in state.get("generated_test_files") or []}
    results = parse_playwright_results(load_execution_results(state.get("execution_result")))
    scenarios = [_scenario(s, sid, files, results) for s, sid in zip(plan, ids)]

    text = requirements_text(state)
    failed = [s["id"] for s in scenarios if s["status"] == "FAILED"]
    analysis = state.get("failure_analysis")
    failure_analysis: list[dict[str, Any]] = []
    defects: list[dict[str, str]] = []
    if isinstance(analysis, Mapping):
        sid = str(analysis.get("scenario_id") or (failed[0] if len(failed) == 1 else ""))
        failure_type = str(state.get("failure_type") or analysis.get("failure_type") or "")
        failure_analysis.append({
            "scenario_id": sid,
            "failure_type": failure_type,
            "subtype": analysis.get("subtype"),
            "confidence": analysis.get("confidence"),
            "application_bug": bool(analysis.get("application_bug")),
            "fix_required": bool(analysis.get("fix_required")),
            "root_cause": redact(str(analysis.get("root_cause") or "")),
            "evidence": redact(str(analysis.get("evidence") or "")),
            "explanation": analysis.get("explanation"),
        })
        if failure_type == "Application":  # the future issue-tracker integration reads this
            defects.append({"scenario_id": sid, "summary": redact(str(analysis.get("root_cause") or ""))})

    patches: list[dict[str, Any]] = []
    proposal = state.get("fix_proposal")
    if isinstance(proposal, Mapping):
        approval = state.get("approval_decision")
        patches.append({
            "scenario_id": failure_analysis[0]["scenario_id"] if failure_analysis else "",
            "applied": approval in ("approved", "auto"),
            "risky": bool(proposal.get("risky")),
            "approval": approval,
            "reason": str(proposal.get("reason") or ""),
            "requirement": text or None,
            "diff": str(proposal.get("patch_diff") or ""),
        })

    rejection = state.get("fix_rejection")
    fix_rejection = None
    if isinstance(rejection, Mapping) and rejection.get("code"):
        fix_rejection = {
            "scenario_id": failure_analysis[0]["scenario_id"] if failure_analysis else "",
            "code": str(rejection.get("code")),
            "message": redact(str(rejection.get("message") or "")),
            "failing_line": rejection.get("failing_line"),
            "failing_locator": redact(str(rejection["failing_locator"])) if rejection.get("failing_locator") else None,
        }

    patched_ids = {p["scenario_id"] for p in patches if p["applied"]}
    code: list[dict[str, Any]] = []
    for sid in ids:
        path = files.get(sid)
        if path is None:
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            body = "(file not readable)"
        if len(body) > MAX_CODE_CHARS:
            body = body[:MAX_CODE_CHARS] + "\n// ... truncated"
        code.append({"file": path.name, "patched": sid in patched_ids or "" in patched_ids, "code": body})

    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(state.get("run_id") or "unknown"),
        "terminal_status": decide_terminal_status(state, scenarios),
        "target_url": _target(state),
        "requirements_text": text,
        "requirements_note": (
            "The requirements were not written in English; all other text in this report is in English."
            if _is_not_english(text) else None
        ),
        "duration_s": _total_duration(state.get("execution_result")),
        "counts": _counts(scenarios),
        "attempts": {
            "generation_retries": int(state.get("generation_retry_count") or 0),
            "healing": _healing(state.get("healing_retry_count")),
        },
        "models_used": dict(state.get("models_used") or {}),
        "scenarios": scenarios,
        "failure_analysis": failure_analysis,
        "evidence": _evidence_items(state.get("execution_evidence")),
        "patches": patches,
        "fix_rejection": fix_rejection,
        "generated_code": code,
        "defect_candidates": defects,
        "errors": [redact(str(e)) for e in state.get("errors") or []],
    }

# """Build a deterministic report model from the final workflow state."""

# from __future__ import annotations

# from datetime import datetime
# from typing import Any

# from contracts.report import ReportModel, ScenarioResult


# VALID_TERMINAL_STATUSES = {"PASS", "FAIL", "BLOCKED", "ERROR"}


# def _as_dict(value: Any) -> dict:
#     """Convert supported model objects to dictionaries."""
#     if isinstance(value, dict):
#         return value
#     if hasattr(value, "model_dump"):
#         return value.model_dump()
#     return {}


# def _get_name(item: dict, index: int) -> str:
#     return str(
#         item.get("name")
#         or item.get("scenario_name")
#         or item.get("id")
#         or f"Scenario {index + 1}"
#     )


# def determine_terminal_status(state: dict) -> str:
#     """Determine a terminal status without guessing ambiguous outcomes."""
#     existing = state.get("terminal_status")

#     if existing in VALID_TERMINAL_STATUSES:
#         return existing

#     if state.get("errors"):
#         return "ERROR"

#     if not state.get("target_url"):
#         return "BLOCKED"

#     execution = _as_dict(state.get("execution_result"))
#     execution_status = str(execution.get("status", "")).lower()

#     if execution_status in {"passed", "pass", "success"}:
#         return "PASS"

#     if execution_status in {"failed", "failure", "fail"}:
#         analysis = _as_dict(state.get("failure_analysis"))
#         if analysis.get("failure_type") or state.get("failure_type"):
#             return "FAIL"
#         return "ERROR"

#     return "ERROR"


# def build_report_model(state: dict) -> ReportModel:
#     """Build the report using existing workflow results; never rerun tests."""
#     plan = state.get("test_plan") or []
#     evidence = state.get("execution_evidence") or []
#     analysis = _as_dict(state.get("failure_analysis"))
#     execution = _as_dict(state.get("execution_result"))

#     failure_type = (
#         analysis.get("failure_type")
#         or state.get("failure_type")
#     )
#     subtype = analysis.get("subtype")
#     root_cause = analysis.get("root_cause")

#     scenarios = []

#     for index, raw_scenario in enumerate(plan):
#         scenario = _as_dict(raw_scenario)
#         name = _get_name(scenario, index)

#         matching_evidence = [
#             _as_dict(item)
#             for item in evidence
#             if (
#                 _as_dict(item).get("scenario_name") == name
#                 or _as_dict(item).get("scenario_id") == scenario.get("id")
#             )
#         ]

#         scenario_status = str(
#             scenario.get("status", "")
#         ).upper()

#         for item in matching_evidence:
#             candidate = str(
#                 item.get("status")
#                 or item.get("result")
#                 or ""
#             ).upper()

#             if candidate in {"PASS", "PASSED", "SUCCESS"}:
#                 scenario_status = "PASS"
#                 break
#             if candidate in {"FAIL", "FAILED", "ERROR"}:
#                 scenario_status = "FAIL"
#             elif candidate == "BLOCKED" and scenario_status not in {
#                 "PASS", "FAIL"
#             }:
#                 scenario_status = "BLOCKED"

#         if scenario_status in {"PASSED", "SUCCESS"}:
#             scenario_status = "PASS"
#         elif scenario_status in {"FAILED", "ERROR"}:
#             scenario_status = "FAIL"

#         if scenario_status not in {"PASS", "FAIL", "BLOCKED"}:
#             overall = state.get("terminal_status")
#             if overall == "PASS":
#                 scenario_status = "PASS"
#             elif overall == "FAIL" and failure_type:
#                 scenario_status = "FAIL"
#             else:
#                 scenario_status = "BLOCKED"

#         scenarios.append(
#             ScenarioResult(
#                 name=name,
#                 status=scenario_status,
#                 failure_type=failure_type if scenario_status == "FAIL" else None,
#                 subtype=subtype if scenario_status == "FAIL" else None,
#                 root_cause=root_cause if scenario_status == "FAIL" else None,
#                 heal_attempts=int(state.get("healing_retry_count") or 0),
#             )
#         )

#     duration = None
#     started = execution.get("started_at") or execution.get("start_time")
#     finished = execution.get("finished_at") or execution.get("end_time")

#     if started and finished:
#         try:
#             start_dt = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
#             end_dt = datetime.fromisoformat(str(finished).replace("Z", "+00:00"))
#             duration = max(0.0, (end_dt - start_dt).total_seconds())
#         except (ValueError, TypeError):
#             duration = None

#     fix_proposal = _as_dict(state.get("fix_proposal"))
#     defect_candidates = []

#     if failure_type == "Application":
#         description = (
#             fix_proposal.get("description")
#             or analysis.get("root_cause")
#             or analysis.get("application_bug")
#         )
#         if description:
#             defect_candidates.append(str(description))

#     terminal_status = state.get("terminal_status")
#     if terminal_status not in VALID_TERMINAL_STATUSES:
#         terminal_status = determine_terminal_status(state)

#     return ReportModel(
#         run_id=str(state.get("run_id") or "unknown"),
#         terminal_status=terminal_status,
#         target_url=state.get("target_url"),
#         requirements=str(
#             _as_dict(state.get("test_request")).get("requirements") or ""
#         ),
#         duration_seconds=duration,
#         generation_attempts=int(state.get("generation_retry_count") or 0),
#         heal_attempts=int(state.get("healing_retry_count") or 0),
#         models_used=state.get("models_used") or {},
#         scenarios=scenarios,
#         defect_candidates=defect_candidates,
#         report_path=state.get("report_path"),
#         errors=[str(error) for error in (state.get("errors") or [])],
#     )
