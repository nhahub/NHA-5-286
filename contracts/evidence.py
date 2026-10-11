"""
Purpose: Normalised execution evidence collected by the execute node from Playwright output.
Reads: Playwright JSON results, run artifacts
Writes: execution_evidence state field
Must not: classify failures or propose fixes
"""
from typing import Literal
from pydantic import BaseModel, Field

class ConsoleEntry(BaseModel):
    type: Literal["error", "warning", "pageerror"]
    text: str

class NetworkEntry(BaseModel):
    kind: Literal["http_error", "request_failed"]
    status: int | None = None
    method: str
    url: str
    failure: str | None = None

class Evidence(BaseModel):
    scenario_name: str
    error_message: str | None = None
    failed_step: str | None = None
    spec_code: str | None = None
    page_snapshot: dict | None = None
    screenshot_path: str | None = None
    trace_path: str | None = None
    console_log: list[ConsoleEntry] = Field(default_factory=list)
    network_errors: list[NetworkEntry] = Field(default_factory=list)
    final_url: str | None = None
