"""
Purpose: Gradio web interface — MVP two-field form (URL + requirements) with a collapsible LLM configuration section.
Owner: @Shema
Reads: user form inputs
Writes: test_request (passed as TestRequest to the graph entry point)
Must not: call agents directly, display API keys, accept model strings not in provider:model format, or accept a URL that bypasses safety checks
"""

# def build_ui() -> gr.Blocks:
#     -> Constructs a Gradio Blocks layout:
#        - Application URL field (optional, text)
#        - Test requirements textbox (required, accepts English or Arabic)
#        - Authorization checkbox (required; fixed disclaimer: "system may propose test-code fixes; application code is never changed automatically")
#        - Collapsible "LLM Configurations (Optional)" section with four model fields:
#          Planner Model, Code Generation Model, Healer Model, Global Fallback Model
#        - Run button
#        - Status / progress area
#        - Report output area (Markdown preview + download links)

# def handle_submit(
#     url: str,
#     requirements: str,
#     authorization: bool,
#     planner_model: str,
#     codegen_model: str,
#     healer_model: str,
#     fallback_model: str,
# ) -> gr.update:
#     -> Validates authorization checkbox is checked
#     -> Builds TestRequest; invokes compiled graph; streams status to UI
#     -> Returns report Markdown and download links on completion

# def launch() -> None:
#     -> Calls build_ui().launch(server_port=GRADIO_SERVER_PORT)
