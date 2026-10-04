"""
Purpose: Report model that drives deterministic template rendering; LLM contributes explanation text only.
Owner: @Shema
Reads: all TestRunState fields
Writes: terminal_status, report_path state fields
Must not: reclassify a failure or change a result to make the report tidy
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

TerminalStatus = Literal["PASS", "FAIL", "BLOCKED", "ERROR"]


class ScenarioResult(BaseModel):
    name: str
    status: Literal["PASS", "FAIL", "BLOCKED"]
    failure_type: str | None = None
    subtype: str | None = None
    root_cause: str | None = None
    heal_attempts: int = 0


class ReportModel(BaseModel):
    run_id: str
    terminal_status: TerminalStatus
    target_url: str | None = None
    requirements: str
    duration_seconds: float | None = None
    generation_attempts: int = 0
    heal_attempts: int = 0
    models_used: dict[str, str] = {}
    scenarios: list[ScenarioResult] = []
    defect_candidates: list[str] = []
    report_path: str | None = None
    errors: list[str] = []