"""
Purpose: Tests for agents/ package — Planner, Code Generation, Failure Analyzer, Fix Proposal.
Owner: @Shema
"""

# --- planner ---

# def test_planner_output_validates_as_scenario_list() -> None:
#     -> With a mocked LLM returning valid JSON, run_planner returns a non-empty list[Scenario]

# def test_planner_respects_scenario_cap() -> None:
#     -> scenario_cap=2: planner must not return more than 2 scenarios

# def test_planner_does_not_write_playwright_code() -> None:
#     -> Planner output must contain no "await page." strings

# --- codegen ---

# def test_codegen_output_is_saved_spec_file() -> None:
#     -> With a mocked LLM, run_codegen writes a .spec.ts file and returns its path in generated_test_files

# def test_codegen_includes_validation_errors_on_retry() -> None:
#     -> When validation_errors is non-empty, the prompt sent to the model contains the errors

# --- analyzer ---

# def test_analyzer_output_validates_as_failure_analysis() -> None:
#     -> With a mocked LLM returning valid JSON, run_analyzer produces a FailureAnalysis

# def test_unknown_failure_class_becomes_error() -> None:
#     -> Analyzer output with failure_type="Unknown" → failure_type set to "ERROR" by pre_classifier

# def test_subtype_rejected_for_non_test_class() -> None:
#     -> failure_type="Application", subtype="SELECTOR" → FailureAnalysis raises ValidationError

# --- fix_proposal ---

# def test_fix_proposal_output_validates() -> None:
#     -> With a mocked LLM, run_fix_proposal produces a FixProposal with patch_diff, reason, risky

# def test_assertion_subtype_forces_risky_true() -> None:
#     -> When failure_analysis.subtype == "ASSERTION", fix_proposal.risky must be True
