"""
Purpose: Assemble and compile the LangGraph StateGraph from all node and routing functions.
Reads: N/A (builder; no state access)
Writes: N/A (returns a compiled graph object)
Must not: hard-code model names, API keys, or routing logic (routing lives in routing.py)
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from graph.state import TestRunState

from graph.nodes import (
    intake_node,
    planner_node,
    codegen_node,
    validate_node,
    execute_node,
    analyze_node,
    fix_proposal_node,
    fix_approval_node,
    apply_fix_node,
    report_node,
)

from graph.routing import (
    route_after_intake,
    route_after_validate,
    route_after_execute,
    route_after_analyze,
    route_after_fix_approval,
    route_after_fix_proposal,
    route_after_apply_fix,
)


def build_graph():
    graph = StateGraph(TestRunState)

    graph.add_node("intake", intake_node)
    graph.add_node("planner", planner_node)
    graph.add_node("codegen", codegen_node)
    graph.add_node("validate", validate_node)
    graph.add_node("execute", execute_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("fix_proposal", fix_proposal_node)
    graph.add_node("fix_approval", fix_approval_node)
    graph.add_node("apply_fix", apply_fix_node)
    graph.add_node("report", report_node)

    graph.add_edge(START, "intake")

    graph.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "planner": "planner",
            "report": "report",
        },
    )

    graph.add_edge("planner", "codegen")
    graph.add_edge("codegen", "validate")

    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {
            "execute": "execute",
            "report": "report",
        },
    )

    graph.add_conditional_edges(
        "execute",
        route_after_execute,
        {
            "analyze": "analyze",
            "report": "report",
        },
    )

    graph.add_conditional_edges(
        "analyze",
        route_after_analyze,
        {
            "fix_proposal": "fix_proposal",
            "report": "report",
        },
    )

    graph.add_conditional_edges(
    "fix_proposal",
    route_after_fix_proposal,
    {
        "fix_approval": "fix_approval",
        "report": "report",
    },
)

    graph.add_conditional_edges(
        "fix_approval",
        route_after_fix_approval,
        {
            "apply_fix": "apply_fix",
            "report": "report",
        },
    )

    graph.add_conditional_edges(
        "apply_fix",
        route_after_apply_fix,
        {
            "validate": "validate",
            "report": "report",
        },
    )

    graph.add_edge("report", END)

    return graph.compile(
        checkpointer=InMemorySaver()
    )


# def build_graph() -> CompiledStateGraph:
#     -> Creates StateGraph(TestRunState)
#     -> Adds nodes: intake, planner, codegen, validate, human_code_review, execute,
#        analyze, fix_proposal, apply_fix, report
#     -> Sets entry point to "intake"
#     -> Adds conditional edges using routing functions from routing.py
#     -> Sets "report" as the terminal node (all paths end here)
#     -> Calls graph.compile() and returns the compiled graph
#     -> The graph guarantees: every path ends at report, including crashes (see spec §4 invariants)
