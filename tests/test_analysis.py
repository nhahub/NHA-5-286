"""
Purpose: Tests for analysis/ package — evidence normalisation and failure-class pre-classification.
"""


from analysis.evidence import (
    extract_error_message,
    normalise_evidence,
    parse_playwright_results,
)
from analysis.pre_classifier import classify


def test_parse_playwright_results_returns_flat_list() -> None:
    results = {
        "suites": [
            {
                "title": "Login",
                "specs": [
                    {
                        "title": "valid login",
                        "tests": [
                            {
                                "results": [
                                    {"status": "passed", "errors": []},
                                    {
                                        "status": "failed",
                                        "errors": [{"message": "TimeoutError"}],
                                    },
                                ]
                            }
                        ],
                    }
                ],
            }
        ]
    }

    parsed = parse_playwright_results(results)

    assert len(parsed) == 2
    assert parsed[0]["scenario_name"] == "valid login"


def test_normalise_evidence_sets_error_message_on_failure() -> None:
    evidence = normalise_evidence({
        "scenario_name": "Login",
        "errors": [{"message": "TimeoutError: locator.click"}],
    })

    assert evidence.scenario_name == "Login"
    assert "TimeoutError" in evidence.error_message


def test_normalise_evidence_sets_none_on_pass() -> None:
    evidence = normalise_evidence({
        "scenario_name": "Login",
        "errors": [],
    })

    assert evidence.error_message is None


def test_extract_error_message_returns_none_for_empty_errors() -> None:
    assert extract_error_message({"errors": []}) is None


def test_valid_failure_classes_pass_through() -> None:
    for failure_type in (
        "Test",
        "Application",
        "Environment",
        "Infrastructure",
    ):
        assert classify({"failure_type": failure_type})["failure_type"] == failure_type


def test_unknown_class_becomes_error() -> None:
    for failure_type in ("Flaky", "Unknown", ""):
        assert classify({"failure_type": failure_type})["failure_type"] == "ERROR"


def test_valid_subtype_for_test_class_passes() -> None:
    result = classify({"failure_type": "Test", "subtype": "TIMING"})
    assert result["subtype"] == "TIMING"


def test_subtype_cleared_for_non_test_class() -> None:
    result = classify({
        "failure_type": "Application",
        "subtype": "SELECTOR",
    })
    assert result["subtype"] is None


def test_invalid_subtype_cleared() -> None:
    result = classify({"failure_type": "Test", "subtype": "CRASH"})
    assert result["subtype"] is None
