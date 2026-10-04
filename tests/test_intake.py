"""
Purpose: Tests for intake/ package — URL resolution, safety checks, and model resolution.
Owner: @Shema
"""

# --- url_resolver ---

# def test_url_field_takes_priority_over_requirements_text() -> None:
#     -> url="https://a.com", requirements containing "https://b.com" → resolves to "https://a.com", source="field"

# def test_single_url_extracted_from_requirements() -> None:
#     -> url=None, requirements="test https://example.com login" → resolves to "https://example.com", source="requirements"

# def test_multiple_urls_in_requirements_is_blocked() -> None:
#     -> url=None, two URLs in requirements → (None, "BLOCKED: ambiguous target URL")

# def test_no_url_anywhere_is_blocked() -> None:
#     -> url=None, requirements with no URL → (None, "BLOCKED: no target URL provided")

# --- safety ---

# def test_https_url_passes_safety_check() -> None:
#     -> "https://example.com" → (True, "")

# def test_http_url_blocked_by_default() -> None:
#     -> "http://example.com" with allow_http=False → (False, reason)

# def test_localhost_blocked() -> None:
#     -> "https://localhost:3000" → (False, reason)

# def test_private_ip_blocked() -> None:
#     -> "https://192.168.1.1" → (False, reason)

# def test_loopback_blocked() -> None:
#     -> "https://127.0.0.1" → (False, reason)

# --- model_resolver ---

# def test_override_takes_priority_over_default() -> None:
#     -> test_request with planner_model="openai:gpt-4o-mini" overrides DEFAULT_MODEL

# def test_invalid_model_string_format_rejected() -> None:
#     -> "gpt-4o" (no provider prefix) → validate_model_string returns False

# def test_no_model_and_no_key_raises() -> None:
#     -> With DEFAULT_MODEL unset and no override, resolve_models raises (stops run as ERROR)
