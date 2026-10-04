"""
Purpose: Tests for llm/ package — model initialisation and MCP tool filtering.
Owner: @Shema
"""

# --- client ---

# def test_get_model_requires_provider_prefix() -> None:
#     -> get_model("gpt-4o") raises ValueError (no "openai:" prefix)

# def test_get_model_with_fallback_returns_fallback_on_primary_failure() -> None:
#     -> primary unavailable, fallback="openai:gpt-4o-mini" → returns fallback model

# def test_get_model_with_fallback_raises_when_both_fail() -> None:
#     -> Both primary and fallback fail → raises RuntimeError (caller sets ERROR)

# --- mcp_client ---

# def test_agent_tools_filtered_to_allowed_list() -> None:
#     -> get_agent_tools("planner", ...) returns only browser_navigate, browser_snapshot, browser_click, browser_type

# def test_codegen_does_not_get_run_playwright_tests() -> None:
#     -> "codegen" tool list must not contain "run_playwright_tests"

# def test_unknown_agent_name_raises() -> None:
#     -> get_agent_tools("unknown_agent", ...) raises KeyError

# def test_all_four_agent_tool_lists_defined() -> None:
#     -> AGENT_TOOLS keys == {"planner", "codegen", "analyzer", "fix_proposal"}
