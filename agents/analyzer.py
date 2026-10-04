"""
Purpose: Failure Analyzer agent — classifies each failure as Test / Application / Environment / Infrastructure and decides whether it is fixable.
Owner: @Shema
Reads: execution_evidence, test_plan, test code
Writes: failure_analysis, failure_type
Must not: apply a fix or assert a cause the evidence does not support
"""

# def build_analyzer_agent(model: str, mcp_tools: list) -> Runnable:
#     -> Creates a LangChain agent with the analyzer system prompt (prompts/analyzer.md),
#        structured output (FailureAnalysis), and allowed MCP tools:
#        get_results, read_test_file, browser_snapshot

# def run_analyzer(state: TestRunState) -> TestRunState:
#     -> LangGraph node function
#     -> Calls build_analyzer_agent; validates output as FailureAnalysis with one retry
#     -> Passes result through analysis.pre_classifier.classify() for deterministic failure_type validation
#     -> Unknown or malformed failure_type values end as ERROR, never as a guess
#     -> Writes failure_analysis and failure_type; records model in models_used["analyzer"]
