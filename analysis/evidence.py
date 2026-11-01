
import json
import re
from pathlib import Path
from typing import Any

from contracts.evidence import ConsoleEntry, Evidence, NetworkEntry


def parse_playwright_results(results_json: dict) -> list[dict]:
    """Flatten nested Playwright suites into individual test results."""
    if not isinstance(results_json, dict):
        return []

    parsed: list[dict] = []

    def visit_suite(suite: dict, parent_title: str = "") -> None:
        suite_title = str(suite.get("title") or parent_title)

        for spec in suite.get("specs", []):
            if not isinstance(spec, dict):
                continue

            scenario_name = str(
                spec.get("title") or suite_title or "Unknown scenario"
            )

            for test in spec.get("tests", []):
                if not isinstance(test, dict):
                    continue

                for result in test.get("results", []):
                    if not isinstance(result, dict):
                        continue

                    parsed.append({
                        **result,
                        "scenario_name": scenario_name,
                    })

        for child in suite.get("suites", []):
            if isinstance(child, dict):
                visit_suite(child, suite_title)

    for suite in results_json.get("suites", []):
        if isinstance(suite, dict):
            visit_suite(suite)

    return parsed


def extract_error_message(result: dict) -> str | None:
    """Extract error messages from a Playwright result."""
    errors = result.get("errors", [])

    if isinstance(errors, list):
        messages = [
            error["message"]
            for error in errors
            if isinstance(error, dict)
            and isinstance(error.get("message"), str)
            and error["message"]
        ]

        if messages:
            return "\n".join(messages)

    fallback = result.get("error")
    if isinstance(fallback, dict):
        fallback = fallback.get("message")

    return fallback if isinstance(fallback, str) and fallback else None


def _read_attachment(
    attachment: dict,
    run_dir: str | Path | None,
) -> str | None:
    """Read a text attachment safely."""
    raw_path = attachment.get("path")

    if not isinstance(raw_path, str) or not raw_path:
        return None

    path = Path(raw_path)

    if not path.is_absolute() and run_dir is not None:
        path = Path(run_dir) / path

    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def _attachment_path(
    attachment: dict,
    run_dir: str | Path | None,
) -> str | None:
    raw_path = attachment.get("path")

    if not isinstance(raw_path, str) or not raw_path:
        return None

    path = Path(raw_path)

    if not path.is_absolute() and run_dir is not None:
        path = Path(run_dir) / path

    return str(path.resolve())


# Playwright writes the page's accessibility tree into the "error-context" attachment when a test fails.
_SNAPSHOT_SECTION = re.compile(r"#\s*Page snapshot\s*\n+```(?:yaml)?[ \t]*\n(?P<body>.*?)```", re.S | re.I)
MAX_SNAPSHOT_CHARS = 20_000
_HEADER_SECRET = re.compile(
    r"(?im)\b(authorization|proxy-authorization|cookie|set-cookie|x-api-key|api[-_]?key|x-auth-token)\b[ \t]*[:=][ \t]*[^\n]+")
_BEARER = re.compile(r"(?i)\bbearer[ \t]+[A-Za-z0-9._~+/=-]{8,}")
_KEY_VALUE_SECRET = re.compile(
    r'(?i)("?(?:password|passwd|token|access_token|refresh_token|client_secret|secret)"?[ \t]*[:=][ \t]*)("[^"\n]*"|[^\s"]+)')


def sanitize_snapshot(text: str) -> str:
    """Remove actual secrets from DOM text (passwords, tokens, API keys, cookies, authorization headers) while
    leaving the visible UI text that selectors depend on (labels, roles, names such as 'Admin') untouched."""
    from llm.errors import redact

    text = redact(text)  # API keys from the environment and the passwords registered for the active runs
    text = _HEADER_SECRET.sub(lambda m: f"{m.group(1)}: [redacted]", text)
    text = _BEARER.sub("Bearer [redacted]", text)
    return _KEY_VALUE_SECRET.sub(lambda m: m.group(1) + "[redacted]", text)


def _snapshot_from_error_context(content: str | None) -> dict | None:
    match = _SNAPSHOT_SECTION.search(content or "")
    if not match or not match["body"].strip():
        return None
    return {"aria": sanitize_snapshot(match["body"])[:MAX_SNAPSHOT_CHARS], "source": "error-context"}


def _parse_entries(
    content: str | None,
    model: type[ConsoleEntry] | type[NetworkEntry],
) -> list[Any]:
    if not content:
        return []

    try:
        entries = json.loads(content)
    except json.JSONDecodeError:
        return []

    if not isinstance(entries, list):
        return []

    parsed = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        try:
            parsed.append(model.model_validate(entry))
        except Exception:
            continue

    return parsed


def normalise_evidence(
    raw_result: dict,
    spec_code: str | None = None,
    run_dir: str | Path | None = None,
) -> Evidence:
    """Convert one Playwright result into a structured Evidence object."""
    if not isinstance(raw_result, dict):
        return Evidence(scenario_name="Unknown scenario")

    attachments = raw_result.get("attachments", [])
    if not isinstance(attachments, list):
        attachments = []

    screenshot_path = None
    trace_path = None
    console_logs = []
    network_errors = []
    final_url = None
    error_context = None

    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue

        name = str(attachment.get("name", ""))
        lower_name = name.lower()
        saved_path = _attachment_path(attachment, run_dir)

        if name == "screenshot" or (
            "screenshot" in lower_name
            and lower_name.endswith((".png", ".jpg", ".jpeg"))
        ):
            screenshot_path = saved_path

        elif "trace" in lower_name and (
            lower_name.endswith(".zip") or lower_name == "trace"
        ):
            trace_path = saved_path

        elif name == "console.json":
            console_logs.extend(
                _parse_entries(
                    _read_attachment(attachment, run_dir),
                    ConsoleEntry,
                )
            )

        elif name == "network.json":
            network_errors.extend(
                _parse_entries(
                    _read_attachment(attachment, run_dir),
                    NetworkEntry,
                )
            )

        elif name == "error-context":
            error_context = _read_attachment(attachment, run_dir)

        elif name == "final-url.txt":
            content = _read_attachment(attachment, run_dir)
            if content:
                final_url = content.strip() or None

    scenario_name = (
        raw_result.get("scenario_name")
        or raw_result.get("title")
        or "Unknown scenario"
    )

    # A snapshot provided by the evidence collector always wins; the Playwright attachment is only a fallback.
    provided = raw_result.get("page_snapshot")
    page_snapshot = provided if isinstance(provided, dict) and provided else _snapshot_from_error_context(error_context)

    return Evidence(
        scenario_name=str(scenario_name),
        error_message=extract_error_message(raw_result),
        failed_step=raw_result.get("failed_step"),
        spec_code=spec_code or raw_result.get("spec_code"),
        page_snapshot=page_snapshot,
        screenshot_path=screenshot_path,
        trace_path=trace_path,
        console_log=console_logs,
        network_errors=network_errors,
        final_url=final_url,
    )
