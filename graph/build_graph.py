"""
Purpose: Assemble and compile the LangGraph StateGraph from all node and routing functions.
Reads: N/A (builder; no state access)
Writes: N/A (returns a compiled graph object)
Must not: hard-code model names, API keys, or routing logic (routing lives in routing.py)
"""

# def build_graph() -> CompiledStateGraph:
#     -> Creates StateGraph(TestRunState)
#     -> Adds nodes: intake, planner, codegen, validate, human_code_review, execute,
#        analyze, fix_proposal, apply_fix, report
#     -> Sets entry point to "intake"
#     -> Adds conditional edges using routing functions from routing.py
#     -> Sets "report" as the terminal node (all paths end here)
#     -> Calls graph.compile() and returns the compiled graph
#     -> The graph guarantees: every path ends at report, including crashes (see spec §4 invariants)

"""
Purpose: Assemble and compile the LangGraph StateGraph.
"""

from langgraph.graph import END, START, StateGraph

from .nodes import (
    node_analyze,
    node_apply_fix,
    node_codegen,
    node_execute,
    node_fix_proposal,
    node_human_code_review,
    node_intake,
    node_planner,
    node_report,
    node_validate,
)

from .routing import (
    route_after_analyze,
    route_after_apply_fix,
    route_after_execute,
    route_after_fix_proposal,
    route_after_intake,
    route_after_validate,
)

from .state import TestRunState


def build_graph():
    graph = StateGraph(TestRunState)

    # ----------------------------------------
    # Add nodes
    # ----------------------------------------

    graph.add_node("intake", node_intake)
    graph.add_node("planner", node_planner)
    graph.add_node("codegen", node_codegen)
    graph.add_node("validate", node_validate)
    graph.add_node(
        "human_code_review",
        node_human_code_review,
    )
    graph.add_node("execute", node_execute)
    graph.add_node("analyze", node_analyze)
    graph.add_node(
        "fix_proposal",
        node_fix_proposal,
    )
    graph.add_node(
        "apply_fix",
        node_apply_fix,
    )
    graph.add_node("report", node_report)

    # ----------------------------------------
    # Start
    # ----------------------------------------

    graph.add_edge(START, "intake")

    # ----------------------------------------
    # Intake
    # ----------------------------------------

    graph.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "planner": "planner",
            "report": "report",
        },
    )

    # ----------------------------------------
    # Planner -> Codegen
    # ----------------------------------------

    graph.add_edge("planner", "codegen")

    # ----------------------------------------
    # Validation
    # ----------------------------------------

    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {
            "execute": "execute",
            "codegen": "codegen",
            "human_code_review": "human_code_review",
            "report": "report",
        },
    )

    # ----------------------------------------
    # Human review
    # ----------------------------------------

    graph.add_edge(
        "human_code_review",
        "validate",
    )

    # ----------------------------------------
    # Execution
    # ----------------------------------------

    graph.add_conditional_edges(
        "execute",
        route_after_execute,
        {
            "report": "report",
            "analyze": "analyze",
        },
    )

    # ----------------------------------------
    # Failure analysis
    # ----------------------------------------

    graph.add_conditional_edges(
        "analyze",
        route_after_analyze,
        {
            "fix_proposal": "fix_proposal",
            "report": "report",
        },
    )

    # ----------------------------------------
    # Fix proposal
    # ----------------------------------------

    graph.add_conditional_edges(
        "fix_proposal",
        route_after_fix_proposal,
        {
            "apply_fix": "apply_fix",
            "report": "report",
        },
    )

    # ----------------------------------------
    # Apply fix -> Validate again
    # ----------------------------------------

    graph.add_conditional_edges(
        "apply_fix",
        route_after_apply_fix,
        {
            "validate": "validate",
        },
    )

    # ----------------------------------------
    # Report is terminal
    # ----------------------------------------

    graph.add_edge("report", END)

    return graph.compile()