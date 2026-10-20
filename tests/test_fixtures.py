"""
Working test that loads every fixture file and validates it against its contract.
Pydantic raises ValidationError on any field mismatch, so a clean run confirms
the fixtures satisfy the contracts verbatim.
"""
import json
import pathlib

import pytest
from pydantic import ValidationError

from contracts.analysis import FailureAnalysis, FixProposal
from contracts.evidence import Evidence
from contracts.report import ReportModel, ScenarioResult
from contracts.scenario import Scenario, TestRequest

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"
TEST_DATA = pathlib.Path(__file__).parent.parent / "test_data"


def load(directory: pathlib.Path, name: str):
    return json.loads((directory / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# scenarios.json  →  list[Scenario]
# ---------------------------------------------------------------------------

def test_scenarios_fixture_validates():
    data = load(FIXTURES, "scenarios.json")
    assert isinstance(data, list), "scenarios.json must be a JSON array"
    assert len(data) >= 1, "must contain at least one scenario"
    for item in data:
        scenario = Scenario.model_validate(item)
        assert scenario.name
        assert isinstance(scenario.steps, list)
        assert scenario.expected_result


def test_scenarios_cap_not_exceeded():
    data = load(FIXTURES, "scenarios.json")
    assert len(data) <= 5, "scenario_cap maximum is 5"


# ---------------------------------------------------------------------------
# analysis.json  →  FailureAnalysis
# ---------------------------------------------------------------------------

def test_analysis_fixture_validates():
    data = load(FIXTURES, "analysis.json")
    fa = FailureAnalysis.model_validate(data)
    assert fa.failure_type in {"Test", "Application", "Environment", "Infrastructure"}
    assert fa.root_cause
    assert fa.evidence
    assert isinstance(fa.application_bug, bool)
    assert isinstance(fa.fix_required, bool)


def test_analysis_subtype_only_for_test_class():
    data = load(FIXTURES, "analysis.json")
    fa = FailureAnalysis.model_validate(data)
    if fa.subtype is not None:
        assert fa.failure_type == "Test", "subtype is only valid for Test class"
        assert fa.subtype in {"SELECTOR", "TIMING", "ASSERTION"}


# ---------------------------------------------------------------------------
# results.json  —  structural check (Playwright JSON reporter format)
# ---------------------------------------------------------------------------

def test_results_fixture_structure():
    data = load(FIXTURES, "results.json")
    assert "config" in data
    assert "suites" in data
    assert "stats" in data
    stats = data["stats"]
    assert "expected" in stats and "unexpected" in stats
    assert stats["expected"] == 2, "fixture must have 2 passing scenarios"
    assert stats["unexpected"] == 1, "fixture must have 1 failing scenario"


def test_results_fixture_has_timeout_error():
    data = load(FIXTURES, "results.json")
    error_messages = []
    for suite in data.get("suites", []):
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                for result in test.get("results", []):
                    for err in result.get("errors", []):
                        error_messages.append(err.get("message", ""))
    assert any(
        "TimeoutError" in msg for msg in error_messages
    ), "results.json must contain a genuine Playwright TimeoutError"


# ---------------------------------------------------------------------------
# page_snapshot.json  —  accessibility tree structural check
# ---------------------------------------------------------------------------

def test_page_snapshot_is_accessibility_tree():
    data = load(FIXTURES, "page_snapshot.json")
    assert data.get("role") == "WebArea", "root node must have role 'WebArea'"
    assert "name" in data
    assert "children" in data
    assert isinstance(data["children"], list)


def test_page_snapshot_has_interactive_elements():
    data = load(FIXTURES, "page_snapshot.json")
    roles = set()

    def collect_roles(node):
        roles.add(node.get("role"))
        for child in node.get("children", []):
            collect_roles(child)

    collect_roles(data)
    assert "textbox" in roles or "button" in roles, "snapshot must contain interactive elements"


# ---------------------------------------------------------------------------
# state_full.json  —  required keys and terminal_status enum
# ---------------------------------------------------------------------------

REQUIRED_STATE_KEYS = {
    "run_id", "test_request", "target_url", "test_plan", "generated_test_files",
    "validation_status", "validation_errors", "generation_retry_count",
    "human_review_decision", "human_review_count", "reviewer_note", "edited_code",
    "execution_result", "execution_evidence", "failure_analysis", "failure_type",
    "fix_proposal", "approval_decision", "healing_retry_count", "models_used",
    "terminal_status", "errors", "report_path",
}

def test_state_full_has_all_required_keys():
    data = load(FIXTURES, "state_full.json")
    missing = REQUIRED_STATE_KEYS - data.keys()
    assert not missing, f"state_full.json is missing keys: {missing}"


def test_state_full_terminal_status_is_valid():
    data = load(FIXTURES, "state_full.json")
    assert data["terminal_status"] in {"PASS", "FAIL", "BLOCKED", "ERROR"}


def test_state_full_execution_evidence_items_validate():
    data = load(FIXTURES, "state_full.json")
    for item in data.get("execution_evidence", []):
        Evidence.model_validate(item)


def test_state_full_fix_proposal_validates():
    data = load(FIXTURES, "state_full.json")
    if data.get("fix_proposal") is not None:
        FixProposal.model_validate(data["fix_proposal"])


# ---------------------------------------------------------------------------
# test_data/fixtures.json  —  structural check
# ---------------------------------------------------------------------------

def test_test_data_fixtures_structure():
    data = load(TEST_DATA, "fixtures.json")
    assert "sample_requirements" in data
    assert isinstance(data["sample_requirements"], list)
    assert len(data["sample_requirements"]) >= 1

    ids = [r["id"] for r in data["sample_requirements"]]
    assert len(set(ids)) == len(ids)  # ids are unique
    for req in data["sample_requirements"]:
        assert {"id", "text", "authorization", "expected_terminal_status"} <= req.keys()
        assert req["expected_terminal_status"] in {"PASS", "FAIL", "BLOCKED", "ERROR"}

    # Credentials: only environment variable NAMES, never values
    assert data["credentials_env"] == {"username": "TEST_USERNAME", "password": "TEST_PASSWORD"}
    assert "users" not in data  # no literal credentials in committed data
