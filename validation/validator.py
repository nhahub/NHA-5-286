"""
Purpose: Deterministic validator. Checks that generated .spec.ts files follow our lint rules,
         type-check under tsc, and are loadable by `playwright test --list`.
Reads: generated_test_files, generation_retry_count, test_plan (only to detect missing specs)
Writes: validation_status, validation_errors, generation_retry_count
Must not: rewrite code or judge business correctness
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agents.codegen import _sid_from_name, generatable_scenarios, spec_file_name

if TYPE_CHECKING:  # graph/state.py is owned by P5; keep this module importable without it
    from graph.state import TestRunState  # noqa: F401

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_MODULE = "@support/evidence"
SUBPROCESS_TIMEOUT_S = 90
MAX_REPORTED_ISSUES = 20


class ToolchainError(RuntimeError):
    """The validation tooling itself is broken (not the generated code)."""


@dataclass(frozen=True)
class Issue:
    rule: str
    message: str
    file: str
    line: int | None = None

    def format(self) -> str:
        # Always "[rule] <base file name>[:line] message": codegen.py parses this to find the scenario
        where = f"{self.file}:{self.line}" if self.line else self.file
        return f"[{self.rule}] {where} {self.message}"


# --------------------------------------------------------------------------- lint
_IMPORT = re.compile(r"import\s+(?P<what>[^;]*?)\s+from\s+['\"](?P<mod>[^'\"]+)['\"]", re.S)
_LINE_COMMENT = re.compile(r"(?m)(^|\s)//.*$")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)

# Every hard rule in prompts/codegen.md must have a matching rule here.
_PATTERN_RULES: tuple[tuple[str, str, str], ...] = (
    ("no-only-skip", r"\b(?:test|test\.describe)\.(?:only|skip|fixme)\b",
     "test.only/skip/fixme is forbidden"),
    ("no-describe", r"\btest\.describe\b",
     "test.describe is forbidden; use exactly one test() per file"),
    ("no-fixed-wait", r"\bwaitForTimeout\s*\(",
     "waitForTimeout is forbidden; use web-first assertions"),
    ("no-evaluate", r"\.(?:evaluate|evaluateHandle|\$eval|\$\$eval)\s*\(",
     "page.evaluate/evaluateHandle/$eval is forbidden; use locator actions"),
    ("no-custom-timeout", r"\btest\.(?:setTimeout|slow)\s*\(|\btimeout\s*:",
     "custom timeouts are forbidden; the global timeouts are fixed"),
    ("no-networkidle", r"networkidle",
     "never wait for 'networkidle'; use web-first assertions"),
    ("env-credentials", r"process\.env\.(?:USERNAME|PASSWORD)\b",
     "use process.env.TEST_USERNAME / TEST_PASSWORD"),
    ("hardcoded-secret", r"(?i)password[^\n]*\.fill\(\s*['\"`]",
     "password must come from process.env.TEST_PASSWORD, not a literal"),
    ("no-any", r":\s*any\b|\bas\s+any\b", "avoid the 'any' type"),
)


def _strip_comments(source: str) -> str:
    no_block = _BLOCK_COMMENT.sub(lambda m: "\n" * m.group().count("\n"), source)
    return _LINE_COMMENT.sub(r"\1", no_block)


def lint_source(source: str, file: str) -> list[Issue]:
    code = _strip_comments(source)
    issues: list[Issue] = []

    def add(rule: str, message: str, index: int | None = None) -> None:
        line = code.count("\n", 0, index) + 1 if index is not None else None
        issues.append(Issue(rule, message, file, line))

    imports = list(_IMPORT.finditer(code))
    if not any(m["mod"] == EVIDENCE_MODULE and re.search(r"\btest\b", m["what"]) for m in imports):
        add("evidence-import", f"must import {{ test, expect }} from '{EVIDENCE_MODULE}'")
    for m in imports:
        if m["mod"] == "@playwright/test" and re.search(r"\b(?:test|expect)\b", m["what"]):
            add("no-direct-playwright-import",
                "import test/expect from the evidence fixture, not '@playwright/test'", m.start())

    for rule, pattern, message in _PATTERN_RULES:
        for m in re.finditer(pattern, code):
            add(rule, message, m.start())

    test_calls = len(re.findall(r"(?<![.\w])test\s*\(", code))
    if test_calls != 1:
        add("single-test", f"expected exactly one test() call, found {test_calls}")
    return issues


# --------------------------------------------------------------------- subprocesses
def _run_npx(args: list[str], extra_env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    npx = shutil.which("npx")  # resolves npx.cmd on Windows
    if npx is None:
        raise ToolchainError("npx not found on PATH; is Node.js installed?")
    try:
        return subprocess.run(
            [npx, *args], cwd=PROJECT_ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=SUBPROCESS_TIMEOUT_S,
            check=False, env={**os.environ, **(extra_env or {})},
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolchainError(f"'npx {' '.join(args[:2])}' timed out after {SUBPROCESS_TIMEOUT_S}s") from exc
    except OSError as exc:
        raise ToolchainError(f"could not start npx: {exc}") from exc


_TSC_LINE = re.compile(r"^(?P<file>.+?)\((?P<line>\d+),\d+\): error (?P<code>TS\d+): (?P<msg>.+)$")


def parse_tsc_output(output: str, files: set[Path]) -> list[Issue]:
    """Keep only diagnostics located in the given spec files."""
    issues: list[Issue] = []
    for raw in output.splitlines():
        m = _TSC_LINE.match(raw.strip())
        if m and (PROJECT_ROOT / m["file"]).resolve() in files:
            issues.append(Issue(m["code"], m["msg"], Path(m["file"]).name, int(m["line"])))
    return issues


def _typecheck(files: list[Path]) -> list[Issue]:
    cfg = PROJECT_ROOT / f"tsconfig.validate.{uuid.uuid4().hex}.json"
    cfg.write_text(json.dumps({"extends": "./tsconfig.json", "include": [],
                               "files": [str(f) for f in files]}), encoding="utf-8")
    try:
        proc = _run_npx(["tsc", "-p", cfg.name, "--noEmit", "--pretty", "false"])
    finally:
        cfg.unlink(missing_ok=True)
    if proc.returncode == 0:
        return []
    issues = parse_tsc_output(proc.stdout + proc.stderr, {f.resolve() for f in files})
    if not issues:  # tsc failed, but not because of the generated specs
        raise ToolchainError(f"tsc failed outside the generated specs: {(proc.stdout + proc.stderr).strip()[:500]}")
    return issues


def _list_tests(files: list[Path], run_dir: Path) -> list[Issue]:
    names = [f.name for f in files]
    # Base names act as file filters, so only these specs are loaded
    proc = _run_npx(["playwright", "test", "--list", *names], {"RUN_DIR": str(run_dir)})
    if proc.returncode == 0:
        return []
    output = (proc.stdout + proc.stderr).strip()
    if "No tests found" in output:  # config problem (testDir / RUN_DIR), not a generated-code problem
        raise ToolchainError(f"playwright found no tests; check testDir/RUN_DIR in playwright.config.ts: {output[:300]}")
    # Attribute the failure to the spec(s) named in the output. If none is named, use a file name
    # that does not end in .spec.ts so codegen treats the error as unattributable and regenerates all.
    named = [n for n in names if n in output]
    return [Issue("playwright-list", output[:800], n) for n in (named or ["playwright"])]


# ------------------------------------------------------------------------- public
def missing_spec_issues(test_plan: Sequence[Mapping[str, Any]] | None, paths: Sequence[str | Path]) -> list[Issue]:
    """A scenario that should have a spec but has none must fail validation,
    otherwise a run could end as PASS with a scenario that never ran."""
    have = {_sid_from_name(str(p)) for p in paths}
    issues: list[Issue] = []
    for sid, scenario in generatable_scenarios(list(test_plan or [])):
        if sid not in have:
            # The expected file name lets codegen attribute the error to this scenario only
            name = spec_file_name(sid, str(scenario.get("name") or sid))
            issues.append(Issue("missing-spec", "no spec file was generated for this scenario", name))
    return issues


def validate_files(paths: Sequence[str | Path], run_dir: Path | None = None) -> list[Issue]:
    issues: list[Issue] = []
    specs: list[Path] = []
    for p in map(Path, paths):
        if not p.is_file():
            issues.append(Issue("file-missing", "file not found", p.name))
        elif not p.name.endswith(".spec.ts"):
            issues.append(Issue("file-name", "generated file must end with .spec.ts", p.name))
        else:
            issues.extend(lint_source(p.read_text(encoding="utf-8"), p.name))
            specs.append(p.resolve())
    if specs:
        issues.extend(_typecheck(specs))
        if not issues:  # `--list` would only repeat compile errors
            issues.extend(_list_tests(specs, run_dir or specs[0].parent.parent))
    return issues


def validate_spec_file(file_path: str) -> tuple[bool, list[str]]:
    issues = validate_files([file_path])
    return not issues, [i.format() for i in issues]


def validate_all(state: Mapping[str, Any]) -> dict[str, Any]:
    """LangGraph node. Returns a partial state update."""
    files = list(state.get("generated_test_files") or [])
    retries = state.get("generation_retry_count", 0)
    missing = missing_spec_issues(state.get("test_plan"), files)
    if not files:
        errors = [i.format() for i in missing] or ["[no-files] no generated test files to validate"]
        return {"validation_status": "invalid",
                "validation_errors": errors[:MAX_REPORTED_ISSUES],
                "generation_retry_count": retries + 1}
    try:
        issues = [*missing, *validate_files(files)]
    except ToolchainError as exc:
        return {"validation_status": "error",
                "errors": [*state.get("errors", []), f"validator: {exc}"]}
    if not issues:
        return {"validation_status": "valid", "validation_errors": []}
    return {"validation_status": "invalid",
            "validation_errors": [i.format() for i in issues[:MAX_REPORTED_ISSUES]],
            "generation_retry_count": retries + 1}