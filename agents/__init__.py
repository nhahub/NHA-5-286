"""
Purpose: Agents package — the four LLM agents: Planner, Code Generation, Failure Analyzer, Fix Proposal.
"""
from agents.codegen import (
    CodegenBackend,
    CodegenError,
    CodegenResult,
    build_user_payload,
    errors_for,
    failing_scenario_ids,
    generatable_scenarios,
    load_prompt,
    run_codegen,
    scenario_id,
    slugify,
    spec_file_name,
    strip_code_fences,
    write_spec,
)

__all__ = [
    "CodegenBackend",
    "CodegenError",
    "CodegenResult",
    "build_user_payload",
    "errors_for",
    "failing_scenario_ids",
    "generatable_scenarios",
    "load_prompt",
    "run_codegen",
    "scenario_id",
    "slugify",
    "spec_file_name",
    "strip_code_fences",
    "write_spec",
]
