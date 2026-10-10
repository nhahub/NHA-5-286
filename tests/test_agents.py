"""
Purpose: Tests for agents/ package — Planner, Code Generation, Failure Analyzer, Fix Proposal.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from agents.codegen import run_codegen


# --- planner ---

# def test_planner_output_validates_as_scenario_list() -> None:
#     -> With a mocked LLM returning valid JSON, run_planner returns a non-empty list[Scenario]

# def test_planner_respects_scenario_cap() -> None:
#     -> scenario_cap=2: planner must not return more than 2 scenarios

# def test_planner_does_not_write_playwright_code() -> None:
#     -> Planner output must contain no "await page." strings

# --- codegen ---


def test_codegen_output_is_saved_spec_file(tmp_path, monkeypatch) -> None:
    """With a mocked LLM, run_codegen writes a .spec.ts file and returns its path in generated_test_files"""
    # توجيه مجلد التشغيل إلى مسار مؤقت للاختبار
    monkeypatch.setattr("agents.codegen.Path", lambda p: tmp_path / p if str(p).startswith("runs") else Path(p))
    
    mock_state = {
        "run_id": "test_run_mock",
        "test_plan": [{"title": "Test Scenario 1", "steps": ["Navigate to page"]}],
        "validation_errors": [],
        "generated_test_files": []
    }

    # محاكاة استجابة نموذج الذكاء الاصطناعي (LLM)
    with patch("agents.codegen.invoke_llm_codegen", return_value="import { test, expect } from '../../fixtures/evidence.fixture';\n\ntest('sample', async ({ page }) => {});") as mock_llm:
        updated_state = run_codegen(mock_state)
        
        assert mock_llm.called
        generated_files = updated_state.get("generated_test_files", [])
        assert len(generated_files) > 0
        
        # التحقق من أن الملف تم كتابته فعلياً على النظام
        spec_path = Path(generated_files[0])
        assert spec_path.exists()
        assert spec_path.suffix == ".spec.ts"
        content = spec_path.read_text(encoding="utf-8")
        assert "evidence.fixture" in content

def test_codegen_includes_validation_errors_on_retry(tmp_path, monkeypatch) -> None:
    """When validation_errors is non-empty, the prompt sent to the model contains the errors"""
    monkeypatch.setattr("agents.codegen.Path", lambda p: tmp_path / p if str(p).startswith("runs") else Path(p))
    
    sample_errors = [
        "TypeScript Compilation Error: Property 'click' does not exist",
        "Lint Error: Missing mandatory import from 'fixtures/evidence.fixture'"
    ]
    
    mock_state = {
        "run_id": "test_run_retry",
        "test_plan": [{"title": "Retry Scenario", "steps": ["Fix errors"]}],
        "validation_errors": sample_errors,
        "generated_test_files": []
    }

    captured_prompts = []

    def mock_invoke_with_tracking(prompt, *args, **kwargs):
        captured_prompts.append(prompt)
        return "import { test, expect } from '../../fixtures/evidence.fixture';\n"

    with patch("agents.codegen.invoke_llm_codegen", side_effect=mock_invoke_with_tracking):
        run_codegen(mock_state)
        
        assert len(captured_prompts) > 0
        prompt_sent = captured_prompts[0]
        
        # التأكد من أن أخطاء التحقق تم تضمينها في الـ Prompt لكي يتعامل معها النموذج في محاولة الإصلاح
        for error in sample_errors:
            assert error in prompt_sent
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
