"""
Purpose: Thin LangGraph node wrappers that delegate to service and agent functions; all exception catching goes here.
Reads: TestRunState
Writes: TestRunState
Must not: perform routing decisions (routing lives in routing.py) or contain agent logic
"""

# def node_intake(state: TestRunState) -> TestRunState:
#     -> Delegates to intake.url_resolver, intake.safety, intake.model_resolver
#     -> Catches all exceptions into state["errors"]

# def node_planner(state: TestRunState) -> TestRunState:
#     -> Delegates to agents.planner.run_planner
#     -> Catches all exceptions into state["errors"]

# def node_codegen(state: TestRunState) -> TestRunState:
#     -> Delegates to agents.codegen.run_codegen
#     -> Catches all exceptions into state["errors"]

# def node_validate(state: TestRunState) -> TestRunState:
#     -> Delegates to validation.validator.validate_all
#     -> Catches all exceptions into state["errors"]

# def node_human_code_review(state: TestRunState) -> TestRunState:
#     -> Delegates to healing.human_review.present_for_review
#     -> Catches all exceptions into state["errors"]

# def node_execute(state: TestRunState) -> TestRunState:
#     -> Delegates to execution.runner.run_execute
#     -> Catches all exceptions into state["errors"]

# def node_analyze(state: TestRunState) -> TestRunState:
#     -> Delegates to agents.analyzer.run_analyzer
#     -> Catches all exceptions into state["errors"]

# def node_fix_proposal(state: TestRunState) -> TestRunState:
#     -> Delegates to agents.fix_proposal.run_fix_proposal
#     -> Catches all exceptions into state["errors"]

# def node_apply_fix(state: TestRunState) -> TestRunState:
#     -> Delegates to healing.apply_fix.run_apply_fix
#     -> Catches all exceptions into state["errors"]

# def node_report(state: TestRunState) -> TestRunState:
#     -> Delegates to report.model.build_report_model and report.exporters
#     -> Always runs, even when state["errors"] is non-empty
#     -> Catches all exceptions; if report itself crashes, writes an emergency plain-text report
