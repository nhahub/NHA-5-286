
"""
Purpose: Execute node — invokes Playwright and collects execution_result and execution_evidence without diagnosing anything.
Reads: generated_test_files
Writes: execution_result, execution_evidence
Must not: diagnose failures or modify any code
"""

# def run_playwright_tests(spec_files: list[str], run_dir: str) -> dict:
#     -> Calls `playwright test <spec_files>` via subprocess with JSON reporter
#     -> Called directly by the execute node only — never chosen by a model (see spec §3)
#     -> Returns raw Playwright JSON reporter output as a dict

# def collect_evidence(results: dict, run_dir: str) -> list[Evidence]:
#     -> Iterates Playwright JSON suites/specs/tests; maps each result to an Evidence object
#     -> Attaches screenshot_path and trace_path from result attachments

# def run_execute(state: TestRunState) -> TestRunState:
#     -> LangGraph node function
#     -> Calls run_playwright_tests; calls collect_evidence
#     -> Writes execution_result and execution_evidence
#     -> On subprocess crash or app-unreachable error: sets terminal_status to BLOCKED or ERROR


import json
import os
import subprocess
from pathlib import Path
from typing import Any
from analysis.evidence import parse_playwright_results, normalise_evidence
from contracts.evidence import ConsoleEntry, Evidence, NetworkEntry
from graph.state import TestRunState


_REPO_ROOT = Path(__file__).resolve().parent.parent
_RUN_TIMEOUT_SECONDS = 600


def _read_json(path: Path) -> dict:
    """Read a JSON file and return an empty dict if it is unavailable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _read_attachment(
    attachment: dict,
    run_dir: Path,
) -> Any:
    """Read an attachment when Playwright provides a file path."""
    attachment_path = attachment.get("path")

    if not isinstance(attachment_path, str) or not attachment_path:
        return None

    path = Path(attachment_path)

    if not path.is_absolute():
        path = run_dir / path

    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def run_playwright_tests(
    spec_files: list[str],
    run_dir: str,
    target_url: str | None = None,
) -> dict:
    """Run Playwright and return its JSON reporter output."""
    run_path = Path(run_dir).resolve()
    run_path.mkdir(parents=True, exist_ok=True)

    results_path = run_path / "results.json"
    results_path.unlink(missing_ok=True)

    env = os.environ.copy()
    env["RUN_DIR"] = str(run_path)

    if target_url:
        env["TARGET_URL"] = target_url
    else:
        env.pop("TARGET_URL", None)

    if not spec_files:
        raise ValueError("No generated Playwright spec files were provided.")

    tests_dir = (run_path / "tests").resolve()
    spec_paths: list[str] = []

    for spec in spec_files:
        spec_path = Path(spec)

        if spec_path.is_absolute():
            resolved_path = spec_path.resolve()
        else:
            resolved_path = (_REPO_ROOT / spec_path).resolve()

        try:
            relative_path = resolved_path.relative_to(tests_dir)
        except ValueError:
            if spec_path.is_absolute():
                spec_paths.append(str(resolved_path))
            else:
                spec_paths.append(spec_path.as_posix())
        else:
            spec_paths.append(relative_path.as_posix())

    command = ["npx", "playwright", "test", *spec_paths]

    if os.name == "nt":
        import shutil

        executable = shutil.which("npx")
        if executable is None:
            raise FileNotFoundError(
                "npx was not found. Install Node.js and project dependencies."
            )

        command[0] = executable
        completed = subprocess.run(
            subprocess.list2cmdline(command),
            cwd=_REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_RUN_TIMEOUT_SECONDS,
            shell=True,
        )
    else:
        completed = subprocess.run(
            command,
            cwd=_REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_RUN_TIMEOUT_SECONDS,
            check=False,
        )

    results = _read_json(results_path)

    if not results:
        results = {
            "stats": {},
            "suites": [],
            "runner_exit_code": completed.returncode,
            "stdout": completed.stdout[-5000:],
            "stderr": completed.stderr[-5000:],
        }

    results["runner_exit_code"] = completed.returncode
    results["runner_stdout"] = completed.stdout[-5000:]
    results["runner_stderr"] = completed.stderr[-5000:]

    return results



def collect_evidence(
    results: dict,
    run_dir: str,
) -> list[Evidence]:
    """Convert Playwright JSON results into normalized Evidence objects."""
    return [
        normalise_evidence(result, run_dir=run_dir)
        for result in parse_playwright_results(results)
    ]



def run_execute(state: TestRunState) -> dict:
    """Execute generated tests and return state updates."""
    run_id = state.get("run_id")

    if not isinstance(run_id, str) or not run_id.strip():
        return {
            "terminal_status": "ERROR",
            "errors": [
                *(state.get("errors") or []),
                "Execution failed: missing run_id.",
            ],
        }

    run_dir = _REPO_ROOT / "runs" / Path(run_id).name

    try:
        results = run_playwright_tests(
            state.get("generated_test_files") or [],
            str(run_dir),
            target_url=state.get("target_url"),
        )

        evidence = collect_evidence(results, str(run_dir))

        stats = results.get("stats", {})
        execution_result = {
            "exit_code": results.get("runner_exit_code"),
            "stats": stats if isinstance(stats, dict) else {},
            "results_path": str(run_dir / "results.json"),
            "stdout": results.get("runner_stdout", ""),
            "stderr": results.get("runner_stderr", ""),
        }

        combined_output = (
            str(results.get("runner_stdout", ""))
            + "\n"
            + str(results.get("runner_stderr", ""))
        ).lower()

        unreachable_markers = (
            "econnrefused",
            "connection refused",
            "err_connection_refused",
            "net::err_name_not_resolved",
        )

        if any(marker in combined_output for marker in unreachable_markers):
            return {
                "execution_result": execution_result,
                "execution_evidence": [
                    item.model_dump() for item in evidence
                ],
                "terminal_status": "BLOCKED",
            }

        if not results.get("suites") and results.get("runner_exit_code", 1) != 0:
            return {
                "execution_result": execution_result,
                "execution_evidence": [
                    item.model_dump() for item in evidence
                ],
                "terminal_status": "ERROR",
                "errors": [
                    *(state.get("errors") or []),
                    "Playwright failed before producing usable test results.",
                ],
            }

        return {
            "execution_result": execution_result,
            "execution_evidence": [
                item.model_dump() for item in evidence
            ],
        }

    except subprocess.TimeoutExpired:
        return {
            "terminal_status": "ERROR",
            "errors": [
                *(state.get("errors") or []),
                f"Playwright exceeded the {_RUN_TIMEOUT_SECONDS}-second execution limit.",
            ],
        }

    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "terminal_status": "ERROR",
            "errors": [
                *(state.get("errors") or []),
                f"Execution failed: {exc}",
            ],
        }
