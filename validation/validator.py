"""
Purpose: Deterministic validator — checks that generated .spec.ts files compile and use the Playwright API correctly.
Reads: generated_test_files
Writes: validation_status, validation_errors, generation_retry_count
Must not: rewrite code or judge business correctness
"""

import re
import subprocess
from pathlib import Path
from typing import List, Tuple
from graph.state import TestRunState


def check_evidence_fixture_import(file_path: Path) -> List[str]:
    """
    Checks that the spec file imports test and expect from the evidence fixture,
    never directly from @playwright/test.
    """
    errors = []
    if not file_path.exists():
        return [f"File not found: {file_path.as_posix()}"]

    content = file_path.read_text(encoding="utf-8")

    # Check for direct forbidden import from @playwright/test
    if re.search(r"import\s+.*?\b(test|expect)\b.*?from\s+['\"]@playwright/test['\"]", content):
        errors.append(
            f"Rule Violation in {file_path.name}: Direct import from '@playwright/test' is forbidden. "
            f"Must import {{ test, expect }} from the custom evidence fixture."
        )

    # Check for presence of custom evidence fixture import
    if "evidence.fixture" not in content and "fixtures/" not in content:
        errors.append(
            f"Rule Violation in {file_path.name}: Spec file must import test/expect from the evidence fixture."
        )

    return errors


def validate_spec_file(file_path: str) -> Tuple[bool, List[str]]:
    """
    Runs tsc --noEmit and lint checks on a single spec file.
    Returns (True, []) on success; (False, [errors]) on failure.
    """
    path = Path(file_path)
    errors: List[str] = []

    # 1. Lint Rule: Check Evidence Fixture Import
    import_errors = check_evidence_fixture_import(path)
    errors.extend(import_errors)

    # 2. TypeScript Type Check (tsc --noEmit)
    try:
        cmd = ["npx", "tsc", "--noEmit"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            check=False
        )
        if result.returncode != 0:
            output = result.stdout or result.stderr
            # Extract error lines specific to this file or standard TypeScript TS-errors
            for line in output.splitlines():
                if path.name in line or "error TS" in line:
                    errors.append(line.strip())
            if not errors and output.strip():
                errors.append(output.strip())
    except subprocess.TimeoutExpired:
        errors.append(f"TypeScript compilation check timed out for {path.name}.")
    except Exception as e:
        errors.append(f"Failed to execute tsc: {str(e)}")

    is_valid = len(errors) == 0
    return is_valid, errors


def validate_all(state: TestRunState) -> dict:
    """
    LangGraph node function for deterministic validation.
    Iterates over generated_test_files, checks compilation/linting,
    and updates validation_status, validation_errors, and generation_retry_count.
    """
    generated_files = state.get("generated_test_files", [])
    if not generated_files:
        return {
            "validation_status": "invalid",
            "validation_errors": ["No generated test files provided for validation."],
        }

    all_errors: List[str] = []
    for file_path in generated_files:
        _, errors = validate_spec_file(file_path)
        all_errors.extend(errors)

    is_valid = len(all_errors) == 0
    validation_status = "valid" if is_valid else "invalid"

    # Increment retry counter only on failed validation
    current_retry_count = state.get("generation_retry_count", 0)

    return {
        "validation_status": validation_status,
        "validation_errors": all_errors,
        "generation_retry_count": current_retry_count,
    }
