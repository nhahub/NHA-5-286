"""
Purpose: Normalised execution evidence collected by the execute node from Playwright output.
Reads: Playwright JSON results, run artifacts
Writes: execution_evidence state field
Must not: classify failures or propose fixes
"""
from __future__ import annotations

from pydantic import BaseModel


class Evidence(BaseModel):
    scenario_name: str
    error_message: str | None = None
    failed_step: str | None = None
    spec_code: str | None = None
    page_snapshot: dict | None = None
    screenshot_path: str | None = None
    trace_path: str | None = None
    console_log: list[str] = []
