"""
Purpose: Apply Fix service — applies an approved patch to the spec file and increments the heal counter.
Reads: fix_proposal, approval_decision
Writes: generated_test_files, healing_retry_count
Must not: apply an unapproved risky patch or exceed 2 heal attempts per test
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

MAX_HEAL_ATTEMPTS = 2
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def apply_patch(spec_path: str | Path, patch_diff: str) -> bool:
    """Apply a unified diff to one spec file. Returns False (file untouched) if it does not apply cleanly."""
    spec = Path(spec_path)
    if not spec.is_file():
        return False
    with TemporaryDirectory() as temp_dir:
        temp_spec = Path(temp_dir) / spec.name
        temp_spec.write_bytes(spec.read_bytes())
        try:
            result = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", "-"],
                input=patch_diff.encode("utf-8"),
                capture_output=True,
                cwd=temp_dir,
                timeout=10,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        if result.returncode != 0:
            return False
        patched = temp_spec.read_bytes()
    spec.write_bytes(patched)
    return True


def _fail(state: Mapping[str, Any], message: str) -> dict:
    return {
        "terminal_status": "FAIL",
        "errors": [*(state.get("errors") or []), message],
    }


def _heal_count(state: Mapping[str, Any]) -> int:
    retries = state.get("healing_retry_count") or 0
    if isinstance(retries, dict):
        return max(retries.values(), default=0)
    return int(retries)


def run_apply_fix(state: Mapping[str, Any]) -> dict:
    """LangGraph node body. Patches only the failed spec inside this run's tests directory."""
    from agents.fix_proposal import (
        read_failed_spec_code,
        select_failed_spec_file,
        validate_patch_on_copy,
    )

    proposal = state.get("fix_proposal") or {}
    patch_diff = proposal.get("patch_diff")
    request = state.get("test_request") or {}

    approved = state.get("approval_decision") == "approved"
    auto_ok = (
        state.get("approval_decision") == "auto"
        and request.get("auto_heal_mode") == "auto"
        and proposal.get("risky") is False
    )
    if not (approved or auto_ok):
        return _fail(state, "Fix was not approved.")

    if _heal_count(state) >= MAX_HEAL_ATTEMPTS:
        return _fail(state, "Maximum healing attempts reached.")

    if not isinstance(patch_diff, str) or not patch_diff.strip():
        return _fail(state, "No proposed patch found.")

    try:
        spec_code, spec_filename = read_failed_spec_code(state)  # also confines the path to runs/<run_id>/tests
        validate_patch_on_copy(patch_diff, spec_code, spec_filename)
        selected = select_failed_spec_file(state)
        spec_path = selected if selected.is_absolute() else PROJECT_ROOT / selected
        if not apply_patch(spec_path, patch_diff):
            return _fail(state, "Patch could not be applied cleanly.")
    except (ValueError, RuntimeError, OSError) as exc:
        return _fail(state, f"Apply fix failed: {exc}")

    retries = state.get("healing_retry_count") or 0
    if isinstance(retries, dict):
        key = str((state.get("failure_analysis") or {}).get("scenario_id") or spec_filename)
        new_retries: int | dict[str, int] = {**retries, key: int(retries.get(key, 0)) + 1}
    else:
        new_retries = int(retries) + 1

    return {
        "healing_retry_count": new_retries,
        "generated_test_files": list(state.get("generated_test_files") or []),
    }
