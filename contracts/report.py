# """
# Purpose: Report model that drives deterministic template rendering; LLM contributes explanation text only.
# Reads: all TestRunState fields
# Writes: terminal_status, report_path state fields
# Must not: reclassify a failure or change a result to make the report tidy
# """


"""
Purpose: The report_model contract: the single structure every report format reads
         (Markdown, HTML, PDF now; JSON and Word in phase 2).
Reads: N/A (type definitions only)
Writes: N/A (type definitions only)
Must not: contain logic. Plain TypedDicts are used on purpose: report_model is built by our own
          deterministic code (report/model.py), never by an LLM, so it needs no runtime validation.
"""
from __future__ import annotations

from typing import Literal, TypedDict

SCHEMA_VERSION = 1  # bump when a field is renamed or removed (the phase 2 JSON export carries it)

TerminalStatus = Literal["PASS", "FAIL", "BLOCKED", "ERROR"]
ScenarioStatus = Literal["PASSED", "FAILED", "BLOCKED", "NOT_RUN"]


class ReportTarget(TypedDict, total=False):
    url: str | None
    source: str | None  # "field" or "requirements"


class ReportCounts(TypedDict, total=False):
    total: int
    passed: int
    failed: int
    blocked: int


class ReportAttempts(TypedDict, total=False):
    generation_retries: int  # regeneration attempts after the first generation
    healing: dict[str, int]  # heal attempts per scenario id


class ReportStep(TypedDict, total=False):
    action: str | None
    target: str | None
    value: str | None


class ReportScenario(TypedDict, total=False):
    id: str
    name: str
    status: ScenarioStatus
    duration_s: float | None
    blocked_reason: str | None
    steps: list[ReportStep]
    expected_result: str | None


# Backwards compatibility alias for contracts/__init__.py and tests
ScenarioResult = ReportScenario


class ReportAnalysis(TypedDict, total=False):
    scenario_id: str
    failure_type: str
    subtype: str | None
    confidence: str | None
    application_bug: bool
    fix_required: bool
    root_cause: str
    evidence: str
    explanation: str | None  # optional LLM text: the only free text the LLM contributes


class ReportEvidence(TypedDict, total=False):
    scenario_id: str
    final_url: str | None
    screenshot: str | None
    trace: str | None
    console_errors: list[dict]  # {"type", "text"}
    failed_requests: list[dict]  # {"method", "url", "status", "failure"}


class ReportPatch(TypedDict, total=False):
    scenario_id: str
    applied: bool
    risky: bool
    approval: str | None
    reason: str
    requirement: str | None  # the original requirement, shown beside the diff
    diff: str


class ReportFixRejection(TypedDict, total=False):
    scenario_id: str
    code: str
    message: str
    failing_line: int | None
    failing_locator: str | None


class ReportCode(TypedDict, total=False):
    file: str
    patched: bool
    code: str


class DefectCandidate(TypedDict, total=False):
    scenario_id: str
    summary: str  # Application failures only; nothing is filed automatically (future phase)


class ReportModel(TypedDict, total=False):
    schema_version: int
    run_id: str
    terminal_status: TerminalStatus
    target_url: ReportTarget
    requirements_text: str
    requirements_note: str | None
    duration_s: float | None
    counts: ReportCounts
    attempts: ReportAttempts
    models_used: dict[str, str]
    scenarios: list[ReportScenario]
    failure_analysis: list[ReportAnalysis]
    evidence: list[ReportEvidence]
    patches: list[ReportPatch]
    fix_rejection: ReportFixRejection | None
    generated_code: list[ReportCode]
    defect_candidates: list[DefectCandidate]
    errors: list[str]

# from __future__ import annotations

# from typing import Literal

# from pydantic import BaseModel

# TerminalStatus = Literal["PASS", "FAIL", "BLOCKED", "ERROR"]


# class ScenarioResult(BaseModel):
#     name: str
#     status: Literal["PASS", "FAIL", "BLOCKED"]
#     failure_type: str | None = None
#     subtype: str | None = None
#     root_cause: str | None = None
#     heal_attempts: int = 0


# class ReportModel(BaseModel):
#     run_id: str
#     terminal_status: TerminalStatus
#     target_url: str | None = None
#     requirements: str
#     duration_seconds: float | None = None
#     generation_attempts: int = 0
#     heal_attempts: int = 0
#     models_used: dict[str, str] = {}
#     scenarios: list[ScenarioResult] = []
#     defect_candidates: list[str] = []
#     report_path: str | None = None
#     errors: list[str] = []