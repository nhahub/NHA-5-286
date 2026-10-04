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
