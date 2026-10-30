"""Command line entry point for the QC AI web interface."""
from __future__ import annotations

import argparse


def run_headless(url: str | None, requirements: str) -> int:
    """Run the real workflow without the UI. Needs DEFAULT_MODEL (provider:model) and its API key in the environment."""
    import os
    from uuid import uuid4

    from graph.build_graph import build_graph
    from llm.settings import LLMSettings, PROVIDERS, register_run_credentials

    model_string = os.environ.get("DEFAULT_MODEL", "").strip()
    prefix, _, model = model_string.partition(":")
    provider = next((name for name, spec in PROVIDERS.items() if spec.prefix == prefix), None)
    if provider is None or not model:
        print("Set DEFAULT_MODEL to 'groq:<model>', 'google_genai:<model>' or 'openrouter:<model>'.")
        return 2

    thread_id = str(uuid4())
    register_run_credentials(thread_id, LLMSettings(provider, model, "", True))
    request = {
        "url": url, "requirements": requirements, "authorization": True,
        "planner_model": model_string, "codegen_model": model_string, "healer_model": model_string,
        "scenario_cap": int(os.environ.get("SCENARIO_CAP", "3")),
    }
    state = {"test_request": request, "healing_retry_count": 0, "errors": [], "mock_mode": False}
    graph = build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    for update in graph.stream(state, config=config, stream_mode="updates"):
        for node in update:
            print(f"[{node}] done", flush=True)
    result = graph.get_state(config).values
    if graph.get_state(config).next:
        result = {**result, "__interrupt__": True}
    if result.get("__interrupt__"):
        print("A proposed fix needs human approval; re-run from the UI to approve or reject it.")
        return 3
    print(f"Status: {result.get('terminal_status')}  Report: {result.get('report_path')}")
    return 0 if result.get("terminal_status") == "PASS" else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="AI powered browser test automation")
    parser.add_argument("--ui", action="store_true", help="launch the browser interface")
    parser.add_argument("--headless", action="store_true", help="run a test without the UI (workflow required)")
    parser.add_argument("--url", help="application URL")
    parser.add_argument("--requirements", help="plain language test requirements")
    args = parser.parse_args()

    if args.headless:
        if not (args.requirements or "").strip():
            parser.error("--headless requires --requirements")
        raise SystemExit(run_headless(args.url, args.requirements))
    if args.ui or not args.headless:
        from ui.app import launch
        launch()


if __name__ == "__main__":
    main()
