"""
Purpose: Planner agent — inspects the live site and decides what is worth testing, how many scenarios, and positive vs negative coverage.
Reads: target_url, requirements (from test_request)
Writes: test_plan
Must not: write Playwright code, exceed the scenario_cap, invent credentials
"""

def generate_plan(request, llm_client=None, mock_mode=False):

    if mock_mode:
        return mock_generate_plan(request)

    # return real_generate_plan(request, llm_client)   //call llm
    raise NotImplementedError(
        "Real Planner is not implemented yet."
    )



from contracts.scenario import Scenario


def mock_generate_plan(request):
    scenario = Scenario(
        name="Invalid Login",
        steps=[
            {
                "action": "navigate",
                "target": request.get("url") or "https://example.com/login"
            },
            {
                "action": "fill",
                "target": "username",
                "value": "invalid_user"
            },
            {
                "action": "fill",
                "target": "password",
                "value": "wrong_password"
            },
            {
                "action": "click",
                "target": "Login"
            },
            {
                "action": "verify",
                "target": "Invalid credentials"
            }
        ],
        expected_result="Error message displayed"
    )

    return [scenario.model_dump()]


# def build_planner_agent(model: str, mcp_tools: list) -> Runnable:
#     -> Creates a LangChain agent with the planner system prompt (prompts/planner.md),
#        structured output (list[Scenario]), and allowed MCP tools:
#        browser_navigate, browser_snapshot, browser_click, browser_type

# def run_planner(state: TestRunState) -> TestRunState:
#     -> LangGraph node function
#     -> Reads target_url and requirements from state
#     -> Calls build_planner_agent, invokes it, validates output as list[Scenario]
#     -> One retry with validation error on structured-output failure
#     -> Writes test_plan; records model used in models_used["planner"]
