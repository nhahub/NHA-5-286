"""
Purpose: Build the ReportModel from final TestRunState; the LLM contributes explanation text only.
Owner: @Shema
Reads: all TestRunState fields
Writes: terminal_status, report_path state fields
Must not: reclassify a failure, change a result, call an agent, or re-run a test
"""

# def build_report_model(state: TestRunState) -> ReportModel:
#     -> Maps state fields to ReportModel; reads terminal_status verbatim from state
#     -> Derives ScenarioResult list from test_plan + execution_evidence + failure_analysis
#     -> Populates defect_candidates from Application-class failures only (for future issue-tracker integration)
#     -> Duration comes from execution_result timestamps (execution node, not the agent)
#     -> models_used copied verbatim from state["models_used"]

# def determine_terminal_status(state: TestRunState) -> str:
#     -> Pure function: derives PASS / FAIL / BLOCKED / ERROR from Playwright JSON + workflow state
#     -> PASS: all scenarios passed
#     -> FAIL: at least one failure classified and identified
#     -> BLOCKED: no target URL / missing test data / generation failure / review rejected or timed out / app unreachable
#     -> ERROR: node crash / no usable LLM / MCP server down
#     -> Never guesses; if state is ambiguous returns ERROR
