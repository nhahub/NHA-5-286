"""
Purpose: Structured output contracts for the Failure Analyzer and Fix Proposal agents.
Reads: execution_evidence, test_plan, test code
Writes: failure_analysis, failure_type, fix_proposal state fields
Must not: apply any fix, modify files, or reclassify failures
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


FailureClass = Literal[
    "Test",
    "Application",
    "Environment",
    "Infrastructure",
]

TestSubtype = Literal["SELECTOR", "TIMING", "ASSERTION"]

Confidence = Literal["low", "medium", "high"]


class FailureAnalysis(BaseModel):
    """Structured output of the Failure Analyzer."""

    failure_type: FailureClass

    root_cause: str = Field(min_length=10)
    evidence: str = Field(min_length=1)

    application_bug: bool
    fix_required: bool

    subtype: TestSubtype | None = None

    # P4 Safety Guard:
    # Missing confidence defaults to low.
    confidence: Confidence = "low"

    # P5 additional analysis information
    ruled_out: list[str] = Field(default_factory=list)
    suggested_fix: str | None = None

    @model_validator(mode="after")
    def check_subtype_rules(self) -> "FailureAnalysis":

        if self.subtype is not None and self.failure_type != "Test":
            raise ValueError(
                "subtype is only valid when failure_type is 'Test'"
            )

        if self.failure_type == "Test" and self.subtype is None:
            raise ValueError(
                "subtype is required when failure_type is 'Test'"
            )

        return self


class FixProposal(BaseModel):
    """Output of Fix Proposal: a minimal patch with a risk flag."""

    patch_diff: str
    reason: str
    risky: bool