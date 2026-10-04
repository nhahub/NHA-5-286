"""
Purpose: Structured output contracts for the Failure Analyzer and Fix Proposal agents.
Owner: @Shema
Reads: execution_evidence, test_plan, test code
Writes: failure_analysis, failure_type, fix_proposal state fields
Must not: apply any fix, modify files, or reclassify failures
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator

FailureClass = Literal["Test", "Application", "Environment", "Infrastructure"]
TestSubtype = Literal["SELECTOR", "TIMING", "ASSERTION"]


class FailureAnalysis(BaseModel):
    """Verbatim field names mandated by the spec (section 3)."""

    failure_type: FailureClass
    root_cause: str
    evidence: str
    application_bug: bool
    fix_required: bool
    subtype: TestSubtype | None = None

    @model_validator(mode="after")
    def subtype_only_for_test_class(self) -> "FailureAnalysis":
        if self.subtype is not None and self.failure_type != "Test":
            raise ValueError("subtype is only valid when failure_type is 'Test'")
        return self


class FixProposal(BaseModel):
    """Output of the Fix Proposal agent: a minimal patch with a risk flag."""

    patch_diff: str
    reason: str
    risky: bool

    @model_validator(mode="after")
    def assertion_subtype_is_always_risky(self) -> "FixProposal":
        # Enforcement happens at build time in the fix_proposal node;
        # the model itself cannot know the subtype, so risky must already be True.
        return self