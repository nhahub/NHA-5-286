"""
Purpose: Tests for ui/app.py — Gradio form wiring and input validation.
"""

# def test_build_ui_returns_gradio_blocks() -> None:
#     -> build_ui() returns a gr.Blocks instance without raising

# def test_handle_submit_rejects_unchecked_authorization() -> None:
#     -> authorization=False → handle_submit raises or returns an error message before graph invocation

# def test_handle_submit_rejects_invalid_model_string() -> None:
#     -> planner_model="gpt-4o" (no provider prefix) → returns validation error, graph not invoked

# def test_handle_submit_accepts_empty_url_and_url_in_requirements() -> None:
#     -> url="", requirements containing one HTTPS URL → accepted; URL extracted by intake

# def test_handle_submit_builds_test_request_with_correct_fields() -> None:
#     -> Captures the TestRequest passed to the graph and asserts field mapping is correct

# def test_api_keys_not_visible_in_ui_components() -> None:
#     -> No Gradio component in build_ui() has "key" or "secret" in its label (keys are env-only)
