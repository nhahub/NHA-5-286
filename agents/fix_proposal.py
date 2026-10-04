"""
Purpose: Fix Proposal agent — proposes the minimal patch that repairs a failing test without hiding real bugs.
Owner: @Shema
Reads: failure_analysis, execution_evidence, test code
Writes: fix_proposal
Must not: apply its own patch or change anything outside the spec file
"""

# def build_fix_proposal_agent(model: str, mcp_tools: list) -> Runnable:
#     -> Creates a LangChain agent with the fix_proposal system prompt (prompts/fix_proposal.md),
#        structured output (FixProposal), and allowed MCP tools:
#        read_test_file, browser_generate_locator, save_test_file

# def run_fix_proposal(state: TestRunState) -> TestRunState:
#     -> LangGraph node function
#     -> Calls build_fix_proposal_agent; validates output as FixProposal with one retry
#     -> Forces risky=True when failure_analysis.subtype == "ASSERTION" (assertion expected-value changes are always risky)
#     -> Writes fix_proposal; records model in models_used["fix_proposal"]