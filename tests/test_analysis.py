"""
Purpose: Tests for analysis/ package — evidence normalisation and failure-class pre-classification.
Owner: @Shema
"""

# --- evidence ---

# def test_parse_playwright_results_returns_flat_list() -> None:
#     -> Given results.json fixture, parse_playwright_results returns 3 items (one per spec)

# def test_normalise_evidence_sets_error_message_on_failure() -> None:
#     -> Given the failed result from results.json, error_message contains "TimeoutError"

# def test_normalise_evidence_sets_none_on_pass() -> None:
#     -> Given a passing result, error_message is None

# def test_extract_error_message_returns_none_for_empty_errors() -> None:
#     -> result with errors=[] → None

# --- pre_classifier ---

# def test_valid_failure_classes_pass_through() -> None:
#     -> "Test", "Application", "Environment", "Infrastructure" → returned unchanged

# def test_unknown_class_becomes_error() -> None:
#     -> "Flaky", "Unknown", "" → returned as "ERROR"

# def test_valid_subtype_for_test_class_passes() -> None:
#     -> failure_type="Test", subtype="TIMING" → subtype returned as "TIMING"

# def test_subtype_cleared_for_non_test_class() -> None:
#     -> failure_type="Application", subtype="SELECTOR" → subtype returned as None

# def test_invalid_subtype_cleared() -> None:
#     -> failure_type="Test", subtype="CRASH" → subtype returned as None (not an error)
