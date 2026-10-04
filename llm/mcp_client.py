"""
Purpose: Connect to the official Playwright MCP server and return per-agent filtered tool lists.
Reads: N/A (spawns MCP subprocess)
Writes: N/A (returns tool objects)
Must not: expose the unfiltered MCP tool list to any agent; each agent receives only its allowed tools (spec §3)
"""

# Per spec §3 — allowed tools per agent:
# AGENT_TOOLS: dict[str, list[str]] = {
#     "planner":      ["browser_navigate", "browser_snapshot", "browser_click", "browser_type"],
#     "codegen":      ["browser_snapshot", "browser_generate_locator", "save_test_file"],
#     "analyzer":     ["get_results", "read_test_file", "browser_snapshot"],
#     "fix_proposal": ["read_test_file", "browser_generate_locator", "save_test_file"],
# }

# async def connect_mcp() -> MultiServerMCPClient:
#     -> Starts the official Playwright MCP server subprocess
#     -> Connects via langchain-mcp-adapters MultiServerMCPClient
#     -> Returns the connected client; caller is responsible for closing it

# def get_agent_tools(agent_name: str, mcp_client: MultiServerMCPClient) -> list:
#     -> Fetches all tools from mcp_client; filters to AGENT_TOOLS[agent_name]
#     -> Raises KeyError if agent_name is not in AGENT_TOOLS
#     -> Merges local tools (save_test_file, read_test_file, get_results) where applicable
