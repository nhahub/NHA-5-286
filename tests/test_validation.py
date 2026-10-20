"""Purpose: Tests for validation/validator.py (unit + integration)."""
from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path
import pytest
from subprocess import CompletedProcess
from agents.codegen import failing_scenario_ids
from validation import validator
from validation.validator import (
    Issue, ToolchainError, lint_source, parse_tsc_output, validate_all, validate_spec_file, missing_spec_issues
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
    (GOOD + "test.describe('group', () => {});\n", "no-describe"),
    (GOOD.replace("  await page.goto", "  await page.evaluate(() => 1);\n  await page.goto"), "no-evaluate"),
    (GOOD.replace("  await page.goto", "  await page.$eval('a', (e) => e);\n  await page.goto"), "no-evaluate"),
    (GOOD.replace("toHaveTitle(/Example/)", "toHaveTitle(/Example/, { timeout: 1000 })"), "no-custom-timeout"),
    (GOOD.replace("  await page.goto", "  test.setTimeout(60000);\n  await page.goto"), "no-custom-timeout"),
    (GOOD.replace("goto('https://example.com')", "goto('https://example.com', { waitUntil: 'networkidle' })"),
     "no-networkidle"),
    (GOOD.replace("  await page.goto", "  const x: any = 1;\n  await page.goto"), "no-any"),
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

# ---- missing specs (pure) -------------------------------------------------------
PLAN = [{"name": "Add todo"}, {"name": "Complete todo"}]


def test_missing_spec_is_reported_with_expected_file_name() -> None:
    issues = missing_spec_issues(PLAN, ["runs/x/tests/s1-add-todo.spec.ts"])
    assert [(i.rule, i.file) for i in issues] == [("missing-spec", "s2-complete-todo.spec.ts")]


def test_blocked_scenarios_never_count_as_missing() -> None:
    plan = [{"name": "Login", "status": "BLOCKED: missing test data"}]
    assert missing_spec_issues(plan, []) == []


def test_missing_spec_error_maps_back_to_its_scenario() -> None:
    # Contract between validator.py and codegen.py: only the missing scenario is regenerated
    issues = missing_spec_issues(PLAN, ["runs/x/tests/s1-add-todo.spec.ts"])
    assert failing_scenario_ids([i.format() for i in issues], {"s1", "s2"}) == {"s2"}


def test_windows_paths_in_errors_still_map_to_scenario() -> None:
    error = r"[TS2339] C:\proj\runs\a\tests\s2-complete-todo.spec.ts:7 boom"
    assert failing_scenario_ids([error], {"s1", "s2"}) == {"s2"}


def test_validate_all_flags_a_missing_scenario(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(validator, "validate_files", lambda files: [])
    out = validate_all({
        "generated_test_files": ["runs/a/tests/s1-add-todo.spec.ts"],
        "test_plan": PLAN,
    })
    assert out["validation_status"] == "invalid"
    assert out["validation_errors"] == [
        "[missing-spec] s2-complete-todo.spec.ts no spec file was generated for this scenario"
    ]
    assert out["generation_retry_count"] == 1


def test_no_files_with_a_plan_reports_missing_specs_not_no_files() -> None:
    out = validate_all({"generated_test_files": [], "test_plan": PLAN})
    assert all(e.startswith("[missing-spec]") for e in out["validation_errors"])
    assert len(out["validation_errors"]) == 2


# ---- playwright --list handling (monkeypatched) -----------------------------------
def _fake_npx(returncode: int, output: str):
    return lambda args, extra_env=None: CompletedProcess(args, returncode, stdout=output, stderr="")


FILES = [Path("runs/a/tests/s1-a.spec.ts"), Path("runs/a/tests/s2-b.spec.ts")]


def test_list_with_no_tests_is_a_toolchain_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(validator, "_run_npx", _fake_npx(1, "Error: No tests found."))
    with pytest.raises(ToolchainError):
        validator._list_tests(FILES, Path("runs/a"))


def test_list_failure_is_attributed_to_the_named_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(validator, "_run_npx", _fake_npx(1, "Error in s2-b.spec.ts:3 duplicate title"))
    issues = validator._list_tests(FILES, Path("runs/a"))
    assert [i.file for i in issues] == ["s2-b.spec.ts"]


def test_unattributable_list_failure_regenerates_everything(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(validator, "_run_npx", _fake_npx(1, "something broke"))
    issues = validator._list_tests(FILES, Path("runs/a"))
    assert failing_scenario_ids([i.format() for i in issues], {"s1", "s2"}) == {"s1", "s2"}


# ---- reference specs (real tsc + playwright --list) --------------------------------
@pytest.mark.integration
def test_reference_specs_follow_our_own_rules(spec_dir: Path) -> None:
    # The reference specs are injected into the codegen prompt, so they must pass the validator
    copies: list[Path] = []
    for spec in sorted((validator.PROJECT_ROOT / "reference").glob("*.spec.ts")):
        dest = spec_dir / spec.name
        shutil.copy(spec, dest)
        copies.append(dest)
    assert copies, "no reference specs found"
    assert validator.validate_files(copies, run_dir=spec_dir.parent) == []