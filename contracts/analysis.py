"""
Purpose: Structured output contracts for the Failure Analyzer and Fix Proposal agents.
Reads: execution_evidence, test_plan, test code
Writes: failure_analysis, failure_type, fix_proposal state fields
Must not: apply any fix, modify files, or reclassify failures
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator

FailureClass = Literal["Test", "Application", "Environment", "Infrastructure"]
TestSubtype = Literal["SELECTOR", "TIMING", "ASSERTION"]
Confidence = Literal["low", "medium", "high"]


class FailureAnalysis(BaseModel):

    """Verbatim field names mandated by the spec (section 3)."""

    failure_type: FailureClass
    root_cause: str = Field(min_length=10)
    evidence: str = Field(min_length=1)
    application_bug: bool
    fix_required: bool
    subtype: TestSubtype | None = None
    # Optional extras: they do not break existing fixtures
    confidence: Confidence | None = None
    ruled_out: list[str] = Field(default_factory=list)
    suggested_fix: str | None = None

    @model_validator(mode="after")
    def check_subtype_rules(self) -> "FailureAnalysis":
        # subtype is only valid for Test failures
        if self.subtype is not None and self.failure_type != "Test":
            raise ValueError("subtype is only valid when failure_type is 'Test'")
        # ... and it is mandatory for Test failures
        if self.failure_type == "Test" and self.subtype is None:
            raise ValueError("subtype is required when failure_type is 'Test'")
        return self


class FixProposal(BaseModel):
    """Output of the Fix Proposal agent: a minimal patch with a risk flag."""

    patch_diff: str
    reason: str
    risky: bool

# NOTE: The previous model_validator was removed on purpose.
    # It only returned self and never validated anything, so it gave a false
    # sense of safety. This model cannot know the failure subtype, so it cannot
    # enforce "ASSERTION fixes are always risky" by itself.
    # That rule is enforced at build time in the fix_proposal node
    # (agents/fix_proposal.py), which sets risky=True for ASSERTION failures.
    





    ###@model_validator(mode="after")
    ###def assertion_subtype_is_always_risky(self) -> "FixProposal":
        # Enforcement happens at build time in the fix_proposal node;
        # the model itself cannot know the subtype, so risky must already be True.
     ###   return self