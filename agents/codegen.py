"""
Purpose: Code Generation agent. Turns each Scenario into one validated-ready Playwright .spec.ts file.
Reads: test_plan, target_url, generated_test_files, validation_errors, reviewer_note, run_id, errors, models_used
Writes: generated_test_files, models_used["codegen"], errors
Must not: execute tests, hardcode credentials, touch application code
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = PROJECT_ROOT / "prompts" / "codegen.md"
REFERENCE_DIR = PROJECT_ROOT / "reference"
EVIDENCE_IMPORT = "@support/evidence"
MAX_ERRORS_IN_PAYLOAD = 20


class CodegenError(RuntimeError):
    """A scenario could not be turned into a spec file."""


# ------------------------------------------------------------------ output contract
_FENCE = re.compile(r"^```(?:typescript|ts)?[ \t]*\n(?P<body>.*?)\n```[ \t]*$", re.S)


def strip_code_fences(text: str) -> str:
    """Models sometimes wrap code in a Markdown fence despite instructions."""
    stripped = text.strip()
    match = _FENCE.match(stripped)
    return match["body"] if match else stripped


class CodegenResult(BaseModel):
    scenario_id: str
    code: str = Field(min_length=1)

    @field_validator("code")
    @classmethod
    def _clean_code(cls, value: str) -> str:
        cleaned = strip_code_fences(value)
        if not cleaned:
            raise ValueError("code must not be empty")
        return cleaned


class CodegenBackend(Protocol):
    """Implemented in llm/client.py (P5): model choice, fallback, MCP tools, parse retry."""

    def generate(self, system_prompt: str, user_payload: str) -> tuple[CodegenResult, str]:
        """Return the structured result and the model string actually used."""
        ...


# ------------------------------------------------------------------ pure helpers
def load_prompt(prompt_path: Path = PROMPT_PATH, reference_dir: Path = REFERENCE_DIR) -> str:
    template = prompt_path.read_text(encoding="utf-8")
    examples = [
        f"### {spec.name}\n\n```typescript\n{spec.read_text(encoding='utf-8').rstrip()}\n```"
        for spec in sorted(reference_dir.glob("*.spec.ts"))
    ]
    if not examples:
        raise CodegenError(f"no reference specs found in {reference_dir}")
    return (
        template.replace("{{evidence_import}}", EVIDENCE_IMPORT)
        .replace("{{reference_examples}}", "\n\n".join(examples))
    )


def scenario_id(index: int, scenario: Mapping[str, Any]) -> str:
    """Stable id: the scenario's own `id` if P1 adds one, otherwise s1, s2, ..."""
    raw = re.sub(r"[^A-Za-z0-9]", "", str(scenario.get("id") or ""))
    return raw.lower() or f"s{index + 1}"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50] or "scenario"


def spec_file_name(sid: str, scenario_name: str) -> str:
    return f"{sid}-{slugify(scenario_name)}.spec.ts"


_ERROR_FILE = re.compile(r"^\[[^\]]+\]\s+(?P<file>[^\s:]+\.spec\.ts)")


def failing_scenario_ids(validation_errors: Sequence[str], known_ids: set[str]) -> set[str]:
    """Attribute validator errors to scenarios via the filename prefix.
    Any error that cannot be attributed means we regenerate everything."""
    failing: set[str] = set()
    for error in validation_errors:
        match = _ERROR_FILE.match(error)
        sid = match["file"].split("-", 1)[0] if match else None
        if sid not in known_ids:
            return set(known_ids)
        failing.add(sid)
    return failing


def build_user_payload(
    scenario: Mapping[str, Any],
    sid: str,
    target_url: str | None,
    previous_code: str | None = None,
    validation_errors: Sequence[str] = (),
    reviewer_note: str | None = None,
) -> str:
    payload = {
        "scenario": {**{k: v for k, v in scenario.items() if k != "status"}, "id": sid},
        "target_url": target_url,
        "previous_code": previous_code,
        "validation_errors": list(validation_errors)[:MAX_ERRORS_IN_PAYLOAD],
        "reviewer_note": reviewer_note,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def write_spec(tests_dir: Path, file_name: str, code: str) -> Path:
    tests_dir.mkdir(parents=True, exist_ok=True)
    path = tests_dir / file_name
    path.write_text(code.rstrip() + "\n", encoding="utf-8")
    return path


def generate_one(
    backend: CodegenBackend,
    system_prompt: str,
    *,
    scenario: Mapping[str, Any],
    sid: str,
    target_url: str | None,
    previous_code: str | None,
    validation_errors: Sequence[str],
    reviewer_note: str | None,
) -> tuple[str, str]:
    payload = build_user_payload(scenario, sid, target_url, previous_code, validation_errors, reviewer_note)
    result, model = backend.generate(system_prompt, payload)
    if result.scenario_id.casefold() != sid:
        raise CodegenError(f"model returned scenario_id {result.scenario_id!r}, expected {sid!r}")
    return result.code, model


def _resolve_url(raw: Any) -> str | None:
    """state['target_url'] may be a plain string or a {url, source} mapping."""
    return raw.get("url") if isinstance(raw, Mapping) else raw


def _existing_files(paths: Sequence[str] | None) -> dict[str, Path]:
    return {Path(p).name.split("-", 1)[0]: Path(p) for p in (paths or [])}


def _select_scenarios(ids: list[str], existing: dict[str, Path], errors: Sequence[str]) -> set[str]:
    if not existing or not errors:
        return set(ids)  # first pass, or a human-requested regeneration
    return {i for i in ids if i not in existing} | failing_scenario_ids(errors, set(ids))


# ------------------------------------------------------------------ LangGraph node
def run_codegen(
    state: Mapping[str, Any],
    *,
    backend: CodegenBackend,
    runs_root: Path = PROJECT_ROOT / "runs",
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """LangGraph node. Returns a partial state update and never raises."""
    errors = list(state.get("errors", []))
    try:
        scenarios = list(state.get("test_plan") or [])
        if not scenarios:
            raise CodegenError("test_plan is empty")
        prompt = system_prompt or load_prompt()
        ids = [scenario_id(i, s) for i, s in enumerate(scenarios)]
        files = _existing_files(state.get("generated_test_files"))
        validation_errors = list(state.get("validation_errors") or [])
        todo = _select_scenarios(ids, files, validation_errors)
        tests_dir = Path(runs_root) / str(state["run_id"]) / "tests"
        target_url = _resolve_url(state.get("target_url"))
        model_used: str | None = None

        for sid, scenario in zip(ids, scenarios):
            if sid not in todo:
                continue
            try:
                previous = files[sid].read_text(encoding="utf-8") if sid in files and files[sid].is_file() else None
                code, model_used = generate_one(
                    backend, prompt, scenario=scenario, sid=sid, target_url=target_url,
                    previous_code=previous, validation_errors=validation_errors if previous else (),
                    reviewer_note=state.get("reviewer_note"),
                )
                files[sid] = write_spec(tests_dir, spec_file_name(sid, scenario["name"]), code)
            except Exception as exc:  # one bad scenario must not stop the others
                logger.exception("codegen failed for scenario %s", sid)
                errors.append(f"codegen[{sid}]: {exc}")

        update: dict[str, Any] = {
            "generated_test_files": [str(files[i]) for i in ids if i in files],
            "errors": errors,
        }
        if model_used:
            update["models_used"] = {**state.get("models_used", {}), "codegen": model_used}
        return update
    except Exception as exc:  # node invariant: catch into state.errors, the report still runs
        logger.exception("codegen node failed")
        return {"errors": [*errors, f"codegen: {exc}"]}
