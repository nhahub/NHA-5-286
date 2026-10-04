"""
Purpose: Initialise and cache LLM instances via init_chat_model using the provider:model format.
Reads: models_used, environment API keys
Writes: N/A (returns configured BaseChatModel objects)
Must not: hard-code credentials, expose API keys to agents, or use local/self-hosted models
"""

# def get_model(model_string: str) -> BaseChatModel:
#     -> Calls langchain.chat_models.init_chat_model(model_string)
#     -> Raises ValueError if model_string is not in provider:model format
#     -> Raises RuntimeError if the provider's API key is missing

# def get_model_with_fallback(primary: str, fallback: str | None) -> BaseChatModel:
#     -> Tries to initialise primary; on failure tries fallback
#     -> If both fail: raises so that intake can set terminal_status = ERROR before any spend
#     -> Used by all four agent builders

# def record_model_used(agent_name: str, model_string: str, state: TestRunState) -> TestRunState:
#     -> Appends {agent_name: model_string} to state["models_used"]; used by each agent node
