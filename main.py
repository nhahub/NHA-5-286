"""Command line entry point for the QC AI web interface."""
from __future__ import annotations

import argparse


def _read_credentials() -> tuple[str, str]:
    """Optional credentials for a login-protected site. Never taken from the command line (it shows in process
    listings): only BUGLE_AUTH_USERNAME / BUGLE_AUTH_PASSWORD, removed from this process's environment once read."""
    import os

    return os.environ.pop("BUGLE_AUTH_USERNAME", ""), os.environ.pop("BUGLE_AUTH_PASSWORD", "")


def run_headless(url: str | None, requirements: str, skip_auth: bool = False) -> int:
    """Run the real workflow without the UI. Needs DEFAULT_MODEL (provider:model) and its API key in the environment."""
    import os
    from uuid import uuid4

    from graph.build_graph import build_graph
    from llm.run_auth import AuthConfig, build_auth, public_request_fields, register_run_auth, release_run_auth
    from preflight import run_preflight
    from llm.settings import LLMSettings, PROVIDERS, register_run_credentials, release_run_credentials

    model_string = os.environ.get("DEFAULT_MODEL", "").strip()
    prefix, _, model = model_string.partition(":")
    provider = next((name for name, spec in PROVIDERS.items() if spec.prefix == prefix), None)
    if provider is None or not model:
        print("Set DEFAULT_MODEL to 'groq:<model>', 'google_genai:<model>' or 'openrouter:<model>'.")
        return 2

    username, password = _read_credentials()
    if bool(username) != bool(password) and not skip_auth:
        print("Set both BUGLE_AUTH_USERNAME and BUGLE_AUTH_PASSWORD, or neither.")
        return 2

    thread_id = str(uuid4())
    candidate = AuthConfig()
    if username and password and not skip_auth:
        candidate = build_auth("username_password", {"username": username, "password": password})
        register_run_auth(thread_id, candidate)  # lets redact() scrub the values while Preflight runs
    try:
        preflight = run_preflight(url or "", username if candidate.required else "",
                                  password if candidate.required else "", skip_auth=skip_auth)
    except BaseException:
        release_run_auth(thread_id)
        raise
    del username, password
    if not preflight.passed:
        release_run_auth(thread_id)
        print(f"Preflight {preflight.status}: {preflight.message}  (no AI model was called)")
        return 4
    auth = candidate if preflight.auth_required else AuthConfig()
    if not auth.required:
        release_run_auth(thread_id)
    print(f"Preflight PASS: {preflight.message}", flush=True)

    register_run_credentials(thread_id, LLMSettings(provider, model, "", True))
    request = {
        **public_request_fields(auth, preflight.auth_skipped),
        "url": url, "requirements": requirements, "authorization": True,
        "planner_model": model_string, "codegen_model": model_string, "healer_model": model_string,
        "scenario_cap": int(os.environ.get("SCENARIO_CAP", "3")),
    }
    state = {"test_request": request, "healing_retry_count": 0, "errors": [], "mock_mode": False}
    graph = build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    try:
        for update in graph.stream(state, config=config, stream_mode="updates"):
            for node in update:
                print(f"[{node}] done", flush=True)
        result = graph.get_state(config).values
        if graph.get_state(config).next:
            result = {**result, "__interrupt__": True}
    finally:  # success, failure, exception or Ctrl+C: nothing secret outlives the run
        release_run_auth(thread_id)
        release_run_credentials(thread_id)
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
    parser.add_argument("--skip-auth", action="store_true",
                        help="I'm testing the login page itself: skip authentication validation (the URL must still "
                             "be reachable). Credentials, if needed, come from BUGLE_AUTH_USERNAME / "
                             "BUGLE_AUTH_PASSWORD, never from arguments")
    args = parser.parse_args()

    if args.headless:
        if not (args.requirements or "").strip():
            parser.error("--headless requires --requirements")
        raise SystemExit(run_headless(args.url, args.requirements, args.skip_auth))
    if args.ui or not args.headless:
        from ui.app import launch
        launch()


if __name__ == "__main__":
    main()
