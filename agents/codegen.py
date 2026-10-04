"""
Purpose: Code Generation agent — writes a single .spec.ts Playwright test file for one scenario.
Reads: test_plan, validation_errors, reviewer_note
Writes: generated_test_files
Must not: execute tests, hardcode credentials, touch application code
"""

# def build_codegen_agent(model: str, mcp_tools: list) -> Runnable:
#     -> Creates a LangChain agent with the codegen system prompt (prompts/codegen.md),
#        structured output (file path string), and allowed MCP tools:
#        browser_snapshot, browser_generate_locator, save_test_file

# def run_codegen(state: TestRunState) -> TestRunState:
#     -> LangGraph node function; iterates over test_plan scenarios
#     -> Passes validation_errors and reviewer_note when retrying after failed validation
#     -> Writes each generated file path into generated_test_files
#     -> Increments generation_retry_count on each codegen retry call (max 2)
#     -> Records model used in models_used["codegen"]
