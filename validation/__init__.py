"""
Purpose: Validation package — deterministic Playwright API correctness checker.
Owner: P2. This file only re-exports the public names of validation/validator.py; it contains no logic.
Note: tests that patch the validator (for example monkeypatch.setattr on validate_files) must patch the
      MODULE (`from validation import validator`), not the names re-exported here.
"""
from validation.validator import (
    Issue,
    ToolchainError,
    lint_source,
    missing_spec_issues,
    parse_tsc_output,
    validate_all,
    validate_files,
    validate_spec_file,
)

__all__ = [
    "Issue",
    "ToolchainError",
    "lint_source",
    "missing_spec_issues",
    "parse_tsc_output",
    "validate_all",
    "validate_files",
    "validate_spec_file",
]
