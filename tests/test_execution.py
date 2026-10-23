
"""
Purpose: Tests for execution/ package — Playwright test runner and evidence collection.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import execution.runner as runner


# --- runner ---


def test_run_playwright_tests_reads_json_report(
    monkeypatch, tmp_path
):
    """Read Playwright's JSON report and retain process output."""
    monkeypatch.setattr(runner, "_REPO_ROOT", tmp_path)

    import shutil

    monkeypatch.setattr(shutil, "which", lambda _: "npx")

    expected_report = {
        "stats": {"expected": 1, "unexpected": 0},
        "suites": [],
    }

    def fake_subprocess_run(command, **kwargs):
        run_path = Path(kwargs["env"]["RUN_DIR"])
        (run_path / "results.json").write_text(
            json.dumps(expected_report),
            encoding="utf-8",
        )

        assert "playwright" in str(command).lower()
        assert kwargs["env"]["TARGET_URL"] == "http://example.com"

        return SimpleNamespace(
            returncode=0,
            stdout="1 passed",
            stderr="",
        )

    monkeypatch.setattr(runner.subprocess, "run", fake_subprocess_run)

    result = runner.run_playwright_tests(
        ["test.spec.ts"],
        str(tmp_path / "test-run"),
        target_url="http://example.com",
    )

    assert result["stats"]["expected"] == 1
    assert result["runner_exit_code"] == 0
    assert result["runner_stdout"] == "1 passed"
    assert (tmp_path / "test-run" / "results.json").exists()


def test_run_execute_writes_execution_result(
    monkeypatch, tmp_path
):
    """Return the execution summary in the state update."""
    monkeypatch.setattr(runner, "_REPO_ROOT", tmp_path)

    monkeypatch.setattr(
        runner,
        "run_playwright_tests",
        lambda *args, **kwargs: {
            "stats": {"expected": 1, "unexpected": 0},
            "suites": [],
            "runner_exit_code": 0,
            "runner_stdout": "1 passed",
            "runner_stderr": "",
        },
    )

    result = runner.run_execute({
        "run_id": "test-run",
        "generated_test_files": ["test.spec.ts"],
        "target_url": "http://example.com",
        "errors": [],
    })

    assert "execution_result" in result
    assert result["execution_result"]["exit_code"] == 0
    assert result["execution_result"]["stats"]["expected"] == 1


def test_run_execute_writes_execution_evidence(
    monkeypatch, tmp_path
):
    """Convert failed Playwright results into evidence."""
    monkeypatch.setattr(runner, "_REPO_ROOT", tmp_path)

    monkeypatch.setattr(
        runner,
        "run_playwright_tests",
        lambda *args, **kwargs: {
            "stats": {"unexpected": 1},
            "suites": [
                {
                    "title": "Login",
                    "specs": [
                        {
                            "title": "Invalid login",
                            "tests": [
                                {
                                    "results": [
                                        {
                                            "errors": [
                                                {"message": "Login failed"}
                                            ],
                                            "attachments": [],
                                        }
                                    ]
                                }
                            ],
                        }
                    ],
                }
            ],
            "runner_exit_code": 1,
            "runner_stdout": "",
            "runner_stderr": "",
        },
    )

    result = runner.run_execute({
        "run_id": "test-evidence",
        "generated_test_files": ["test.spec.ts"],
        "errors": [],
    })

    assert isinstance(result["execution_evidence"], list)
    assert len(result["execution_evidence"]) == 1
    assert result["execution_evidence"][0]["scenario_name"] == "Invalid login"
    assert result["execution_evidence"][0]["error_message"] == "Login failed"


def test_run_execute_sets_blocked_on_unreachable_app(
    monkeypatch, tmp_path
):
    """Mark execution as blocked when the target cannot be reached."""
    monkeypatch.setattr(runner, "_REPO_ROOT", tmp_path)

    monkeypatch.setattr(
        runner,
        "run_playwright_tests",
        lambda *args, **kwargs: {
            "stats": {},
            "suites": [],
            "runner_exit_code": 1,
            "runner_stdout": "Error: connect ECONNREFUSED",
            "runner_stderr": "",
        },
    )

    result = runner.run_execute({
        "run_id": "test-blocked",
        "generated_test_files": ["test.spec.ts"],
        "errors": [],
    })

    assert result["terminal_status"] == "BLOCKED"
    assert "execution_result" in result


def test_run_execute_sets_error_when_no_results_are_produced(
    monkeypatch, tmp_path
):
    """Report an execution error if Playwright fails before returning results."""
    monkeypatch.setattr(runner, "_REPO_ROOT", tmp_path)

    monkeypatch.setattr(
        runner,
        "run_playwright_tests",
        lambda *args, **kwargs: {
            "stats": {},
            "suites": [],
            "runner_exit_code": 1,
            "runner_stdout": "",
            "runner_stderr": "Playwright configuration error",
        },
    )

    result = runner.run_execute({
        "run_id": "test-no-results",
        "generated_test_files": ["test.spec.ts"],
        "errors": [],
    })

    assert result["terminal_status"] == "ERROR"
    assert any(
    "failed before producing usable test results" in error
    for error in result["errors"]
    )


def test_run_execute_handles_timeout(
    monkeypatch, tmp_path
):
    """Convert a Playwright subprocess timeout into an error update."""
    monkeypatch.setattr(runner, "_REPO_ROOT", tmp_path)

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd="npx playwright test",
            timeout=600,
        )

    monkeypatch.setattr(runner, "run_playwright_tests", raise_timeout)

    result = runner.run_execute({
        "run_id": "test-timeout",
        "generated_test_files": ["test.spec.ts"],
        "errors": [],
    })

    assert result["terminal_status"] == "ERROR"
    assert any(
        "execution limit" in error
        for error in result["errors"]
    )


def test_run_execute_rejects_missing_run_id():
    """Do not start execution without a run identifier."""
    result = runner.run_execute({
        "generated_test_files": ["test.spec.ts"],
        "errors": [],
    })

    assert result["terminal_status"] == "ERROR"
    assert any("missing run_id" in error for error in result["errors"])


def test_collect_evidence_maps_timeout_error(tmp_path):
    """Preserve a Playwright TimeoutError in the evidence."""
    results = {
        "suites": [
            {
                "title": "Checkout",
                "specs": [
                    {
                        "title": "Submit order",
                        "tests": [
                            {
                                "results": [
                                    {
                                        "errors": [
                                            {
                                                "message": (
                                                    "TimeoutError: locator.click: "
                                                    "Timeout 10000ms exceeded"
                                                )
                                            }
                                        ],
                                        "attachments": [],
                                    }
                                ]
                            }
                        ],
                    }
                ],
            }
        ]
    }

    evidence = runner.collect_evidence(results, str(tmp_path))

    assert len(evidence) == 1
    assert "TimeoutError" in evidence[0].error_message


def test_collect_evidence_attaches_screenshot_path(tmp_path):
    """Extract the screenshot path from a Playwright attachment."""
    screenshot = tmp_path / "failure.png"
    screenshot.write_bytes(b"test-image")

    results = {
        "suites": [
            {
                "title": "Login",
                "specs": [
                    {
                        "title": "Invalid login",
                        "tests": [
                            {
                                "results": [
                                    {
                                        "errors": [],
                                        "attachments": [
                                            {
                                                "name": "screenshot",
                                                "path": str(screenshot),
                                            }
                                        ],
                                    }
                                ]
                            }
                        ],
                    }
                ],
            }
        ]
    }

    evidence = runner.collect_evidence(results, str(tmp_path))

    assert len(evidence) == 1
    assert evidence[0].screenshot_path == str(screenshot.resolve())
