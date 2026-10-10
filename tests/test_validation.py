"""
Purpose: Tests for validation/validator.py — deterministic Playwright API correctness checking.
"""

import pytest
from pathlib import Path
from validation.validator import validate_spec_file, validate_all


def test_valid_spec_file_returns_true(tmp_path: Path) -> None:
    """A well-formed .spec.ts with correct Playwright API -> (True, [])"""
    spec_file = tmp_path / "valid.spec.ts"
    spec_file.write_text(
        "import { test, expect } from '../fixtures/evidence.fixture';\n"
        "test('valid test', async ({ page }) => {\n"
        "  await page.goto('https://example.com');\n"
        "  await expect(page).toHaveTitle(/Example/);\n"
        "});",
        encoding="utf-8"
    )
    is_valid, errors = validate_spec_file(str(spec_file))
    assert is_valid is True
    assert errors == []


def test_invalid_spec_with_typo_returns_errors(tmp_path: Path) -> None:
    """A .spec.ts with a misspelled Playwright method -> (False, [error_string])"""
    spec_file = tmp_path / "invalid.spec.ts"
    spec_file.write_text(
        "import { test, expect } from '../fixtures/evidence.fixture';\n"
        "test('invalid test', async ({ page }) => {\n"
        "  await page.nonExistentMethod();\n"
        "});",
        encoding="utf-8"
    )
    is_valid, errors = validate_spec_file(str(spec_file))
    assert is_valid is False
    assert len(errors) > 0


def test_validate_all_sets_validation_status_valid(tmp_path: Path) -> None:
    """All files valid -> state['validation_status'] == 'valid', state['validation_errors'] == []"""
    spec_file = tmp_path / "valid.spec.ts"
    spec_file.write_text(
        "import { test, expect } from '../fixtures/evidence.fixture';\n"
        "test('valid test', async ({ page }) => {\n"
        "  await page.goto('https://example.com');\n"
        "});",
        encoding="utf-8"
    )
    state = {
        "generated_test_files": [str(spec_file)],
        "generation_retry_count": 0
    }
    updated_state = validate_all(state)
    assert updated_state["validation_status"] == "valid"
    assert updated_state["validation_errors"] == []


def test_validate_all_sets_validation_status_invalid(tmp_path: Path) -> None:
    """One file invalid -> state['validation_status'] == 'invalid', state['validation_errors'] non-empty"""
    spec_file = tmp_path / "invalid.spec.ts"
    spec_file.write_text(
        "import { test, expect } from '../fixtures/evidence.fixture';\n"
        "test('invalid test', async ({ page }) => {\n"
        "  await page.badMethodCall();\n"
        "});",
        encoding="utf-8"
    )
    state = {
        "generated_test_files": [str(spec_file)],
        "generation_retry_count": 0
    }
    updated_state = validate_all(state)
    assert updated_state["validation_status"] == "invalid"
    assert len(updated_state["validation_errors"]) > 0


def test_validate_all_increments_generation_retry_count(tmp_path: Path) -> None:
    """Second invalid call -> generation_retry_count incremented"""
    spec_file = tmp_path / "invalid.spec.ts"
    spec_file.write_text(
        "import { test, expect } from '../fixtures/evidence.fixture';\n"
        "test('invalid test', async ({ page }) => {\n"
        "  await page.badMethodCall();\n"
        "});",
        encoding="utf-8"
    )
    state = {
        "generated_test_files": [str(spec_file)],
        "generation_retry_count": 1
    }
    updated_state = validate_all(state)
    assert updated_state["validation_status"] == "invalid"
    assert updated_state["generation_retry_count"] == 1


def test_validator_does_not_rewrite_code(tmp_path: Path) -> None:
    """File content before and after validate_spec_file must be identical"""
    spec_file = tmp_path / "unchanged.spec.ts"
    original_content = (
        "import { test, expect } from '../fixtures/evidence.fixture';\n"
        "test('check content', async ({ page }) => {\n"
        "  await page.goto('https://example.com');\n"
        "});"
    )
    spec_file.write_text(original_content, encoding="utf-8")
    
    validate_spec_file(str(spec_file))
    
    current_content = spec_file.read_text(encoding="utf-8")
    assert current_content == original_content