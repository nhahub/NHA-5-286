"""Purpose: Tests for validation/validator.py (unit + integration)."""
from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from validation import validator
from validation.validator import (
    Issue, ToolchainError, lint_source, parse_tsc_output, validate_all, validate_spec_file,
)

GOOD = """import { test, expect } from '@support/evidence';

test('valid test', async ({ page }) => {
  await page.goto('https://example.com');
  await expect(page).toHaveTitle(/Example/);
});
"""


def rules(source: str) -> set[str]:
    return {i.rule for i in lint_source(source, "x.spec.ts")}


# ---- lint (pure) ------------------------------------------------------------
def test_clean_source_has_no_issues() -> None:
    assert rules(GOOD) == set()


def test_commented_out_violations_are_ignored() -> None:
    assert rules(GOOD + "// test.only('x');\n/* page.waitForTimeout(1) */\n") == set()


@pytest.mark.parametrize("source, rule", [
    (GOOD.replace("@support/evidence", "@playwright/test"), "no-direct-playwright-import"),
    ("import {\n  test,\n  expect,\n} from '@playwright/test';\n" + GOOD.split("\n", 1)[1],
     "no-direct-playwright-import"),
    (GOOD.split("\n", 1)[1], "evidence-import"),
    (GOOD.replace("test('valid", "test.only('valid"), "no-only-skip"),
    (GOOD.replace("  await page.goto", "  await page.waitForTimeout(500);\n  await page.goto"), "no-fixed-wait"),
    (GOOD.replace("  await page.goto", "  const u = process.env.PASSWORD;\n  await page.goto"), "env-credentials"),
    (GOOD.replace("  await page.goto", "  await page.getByLabel('Password').fill('hunter2');\n  await page.goto"),
     "hardcoded-secret"),
    (GOOD + GOOD.split("\n", 2)[2], "single-test"),
])
def test_lint_rule_fires(source: str, rule: str) -> None:
    assert rule in rules(source)


def test_lint_reports_line_numbers() -> None:
    src = GOOD.replace("  await page.goto", "  await page.waitForTimeout(500);\n  await page.goto")
    issue = next(i for i in lint_source(src, "x.spec.ts") if i.rule == "no-fixed-wait")
    assert issue.line == 4


# ---- tsc parsing (pure) -------------------------------------------------------
def test_parse_tsc_output_keeps_only_target_files() -> None:
    target = (validator.PROJECT_ROOT / "runs/_pytest/a/tests/x.spec.ts").resolve()
    out = (
        "runs/_pytest/a/tests/x.spec.ts(3,9): error TS2339: Property 'nope' does not exist.\n"
        "support/evidence.ts(1,1): error TS2304: unrelated\n"
    )
    issues = parse_tsc_output(out, {target})
    assert [(i.rule, i.line) for i in issues] == [("TS2339", 3)]


# ---- node behaviour (monkeypatched) -------------------------------------------
def test_validate_all_invalid_increments_retry_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(validator, "validate_files", lambda files: [Issue("r", "boom", "a.spec.ts", 3)])
    out = validate_all({"generated_test_files": ["a.spec.ts"], "generation_retry_count": 1})
    assert out["validation_status"] == "invalid"
    assert out["generation_retry_count"] == 2
    assert out["validation_errors"] == ["[r] a.spec.ts:3 boom"]


def test_validate_all_valid_leaves_retry_count_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(validator, "validate_files", lambda files: [])
    out = validate_all({"generated_test_files": ["a.spec.ts"], "generation_retry_count": 1})
    assert out == {"validation_status": "valid", "validation_errors": []}


def test_validate_all_without_files_is_invalid() -> None:
    out = validate_all({"generated_test_files": []})
    assert out["validation_status"] == "invalid"
    assert out["generation_retry_count"] == 1


def test_toolchain_failure_is_an_error_not_a_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(files: list[str]) -> list[Issue]:
        raise ToolchainError("npx not found")
    monkeypatch.setattr(validator, "validate_files", boom)
    out = validate_all({"generated_test_files": ["a.spec.ts"], "errors": ["old"]})
    assert out["validation_status"] == "error"
    assert out["errors"] == ["old", "validator: npx not found"]
    assert "generation_retry_count" not in out


# ---- integration (real tsc + playwright) --------------------------------------
@pytest.fixture
def spec_dir() -> Iterator[Path]:
    run = validator.PROJECT_ROOT / "runs" / "_pytest" / uuid.uuid4().hex
    (run / "tests").mkdir(parents=True)
    yield run / "tests"
    shutil.rmtree(run, ignore_errors=True)


@pytest.mark.integration
def test_valid_spec_passes(spec_dir: Path) -> None:
    spec = spec_dir / "valid.spec.ts"
    spec.write_text(GOOD, encoding="utf-8")
    assert validate_spec_file(str(spec)) == (True, [])


@pytest.mark.integration
def test_misspelled_playwright_method_is_reported(spec_dir: Path) -> None:
    spec = spec_dir / "bad.spec.ts"
    spec.write_text(GOOD.replace("page.goto('https://example.com')", "page.nonExistentMethod()"), encoding="utf-8")
    ok, errors = validate_spec_file(str(spec))
    assert ok is False
    assert any("TS2339" in e and "bad.spec.ts" in e for e in errors)


@pytest.mark.integration
def test_validator_does_not_rewrite_code(spec_dir: Path) -> None:
    spec = spec_dir / "unchanged.spec.ts"
    spec.write_text(GOOD, encoding="utf-8")
    validate_spec_file(str(spec))
    assert spec.read_text(encoding="utf-8") == GOOD