"""
Purpose: CLI entry point that wires configuration, the LangGraph orchestrator, and the Gradio UI together.
Owner: @Shema
Reads: CLI arguments
Writes: N/A
Must not: contain business logic; delegate entirely to graph/ and ui/
"""

# def main() -> None: -> parses --headless / --ui flags; builds the compiled graph; either launches Gradio or runs headless
# def run_headless(url: str | None, requirements: str, authorization: bool) -> dict: -> builds TestRequest, invokes compiled_graph.invoke(), prints terminal_status and report_path