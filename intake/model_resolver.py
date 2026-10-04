"""
Purpose: Resolve and validate model strings for each agent slot using the override → DEFAULT_MODEL → FALLBACK_MODEL chain.
Reads: test_request (model overrides), environment (DEFAULT_MODEL, FALLBACK_MODEL)
Writes: models_used state field
Must not: expose API keys, hard-code model names, or start a run without a usable model
"""

# def resolve_models(test_request: dict) -> dict[str, str]:
#     -> For each slot (planner, codegen, healer, global_fallback):
#        1. user override from test_request, 2. DEFAULT_MODEL, 3. FALLBACK_MODEL
#     -> Raises if no model and no key are configured (intake stops the run with ERROR before any spend)

# def validate_model_string(model_string: str) -> bool:
#     -> Checks provider:model format (e.g. "openai:gpt-4o"); returns False for bare names like "gpt-4o"

# def check_tool_calling_support(model_string: str) -> bool:
#     -> Probes the provider's capability list; agents require tool-calling support (MCP tools)