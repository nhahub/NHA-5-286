"""
Purpose: Input contract (TestRequest) and Planner output contract (Scenario).
Reads: test_request state field
Writes: test_plan state field
Must not: contain execution logic or business rules
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


class TestRequest(BaseModel):
    url: str | None = None
    requirements: str
    scenario_cap: int = 3
    planner_model: str | None = None
    codegen_model: str | None = None
    healer_model: str | None = None
    fallback_model: str | None = None
    authorization: bool

    @field_validator("scenario_cap")
    @classmethod
    def cap_between_1_and_5(cls, v: int) -> int:
        if not (1 <= v <= 5):
            raise ValueError("scenario_cap must be between 1 and 5")
        return v


class TestStep(BaseModel):
    action: str
    target: str | None = None
    value: str | None = None


class Scenario(BaseModel):
    name: str
    steps: list[TestStep]
    expected_result: str
    status: Literal["PASS", "FAIL", "BLOCKED"] | None = None