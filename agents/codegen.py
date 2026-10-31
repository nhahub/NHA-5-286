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
from pathlib import Path, PureWindowsPath
from typing import Any, Protocol

from pydantic import BaseModel, Field, field_validator

from llm.errors import LLM_FATAL_TAG, BudgetExceededError, LLMUnavailableError, redact

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
_PLACEHOLDER = re.compile(r"\{\{\s*\w+\s*\}\}")


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
    prompt = (
        template.replace("{{evidence_import}}", EVIDENCE_IMPORT)
        .replace("{{reference_examples}}", "\n\n".join(examples))
    )
    # Fail loudly on an unknown {{placeholder}}; a bare "{{" inside example code is fine.
    leftover = _PLACEHOLDER.findall(prompt)
    if leftover:
        raise CodegenError(f"unreplaced placeholders in codegen prompt: {sorted(set(leftover))}")
    return prompt


def scenario_id(index: int, scenario: Mapping[str, Any]) -> str:
    """Stable id: the scenario's own `id` if P1 adds one, otherwise s1, s2, ..."""
    raw = re.sub(r"[^A-Za-z0-9]", "", str(scenario.get("id") or ""))
    return raw.lower() or f"s{index + 1}"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50] or "scenario"


def spec_file_name(sid: str, scenario_name: str) -> str:
    return f"{sid}-{slugify(scenario_name)}.spec.ts"


# Accepts bare file names and full paths, including Windows drive letters ("C:\...").
_ERROR_FILE = re.compile(r"^\[[^\]]+\]\s+(?P<file>.+?\.spec\.ts)")


def _sid_from_name(path_like: str) -> str:
    """Scenario id = prefix of the file base name; PureWindowsPath handles / and \\ both."""
    return PureWindowsPath(path_like).name.split("-", 1)[0]


def _sid_from_error(error: str) -> str | None:
    match = _ERROR_FILE.match(error)
    return _sid_from_name(match["file"]) if match else None


def failing_scenario_ids(validation_errors: Sequence[str], known_ids: set[str]) -> set[str]:
    """Attribute validator errors to scenarios via the filename prefix.
    Any error that cannot be attributed means we regenerate everything."""
    failing: set[str] = set()
    for error in validation_errors:
        sid = _sid_from_error(error)
        if sid not in known_ids:
            return set(known_ids)
        failing.add(sid)
    return failing


def errors_for(sid: str, validation_errors: Sequence[str]) -> list[str]:
    """This scenario's own errors; if it has none, the errors that name no file at all.
    Keeps the model from 'fixing' problems that belong to another scenario's file."""
    own = [e for e in validation_errors if _sid_from_error(e) == sid]
    return own or [e for e in validation_errors if _sid_from_error(e) is None]


def build_user_payload(
    scenario: Mapping[str, Any],
    sid: str,
    target_url: str | None,
    previous_code: str | None = None,
    validation_errors: Sequence[str] = (),
    reviewer_note: str | None = None,
    authentication: Mapping[str, Any] | None = None,
) -> str:
    payload = {
        "scenario": {**{k: v for k, v in scenario.items() if k != "status"}, "id": sid},
        "target_url": target_url,
        "previous_code": previous_code,
        "validation_errors": list(validation_errors)[:MAX_ERRORS_IN_PAYLOAD],
        "reviewer_note": reviewer_note,
        "authentication": dict(authentication or {"required": False, "method": "none", "env_vars": []}),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


_NEWLINE_ENTITY = re.compile(r"&#?(?:x0*[aA]|0*10);")


def normalize_model_code(code: str) -> str:
    """Some models write a line break as an entity (&10; or &#10;), or as a literal backslash-n when the whole
    file is on one line. Restore real line breaks so the file compiles; correct files are returned unchanged."""
    code = _NEWLINE_ENTITY.sub("\n", code)
    if "\n" not in code.strip() and "\\n" in code:
        code = code.replace("\\n", "\n")
    return code


def write_spec(tests_dir: Path, file_name: str, code: str) -> Path:
    tests_dir.mkdir(parents=True, exist_ok=True)
    path = tests_dir / file_name
    path.write_text(normalize_model_code(code).rstrip() + "\n", encoding="utf-8")
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
    authentication: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    payload = build_user_payload(scenario, sid, target_url, previous_code, validation_errors, reviewer_note,
                                 authentication)
    result, model = backend.generate(system_prompt, payload)
    if result.scenario_id.casefold() != sid:
        raise CodegenError(f"model returned scenario_id {result.scenario_id!r}, expected {sid!r}")
    return result.code, model


def _resolve_url(raw: Any) -> str | None:
    """state['target_url'] may be a plain string or a {url, source} mapping."""
    return raw.get("url") if isinstance(raw, Mapping) else raw


def _existing_files(paths: Sequence[str] | None) -> dict[str, Path]:
    return {_sid_from_name(p): Path(p) for p in (paths or [])}


def _is_blocked(scenario: Mapping[str, Any]) -> bool:
    """Scenarios already marked BLOCKED (e.g. missing test data) get no code."""
    return str(scenario.get("status") or "").upper().startswith("BLOCKED")


def generatable_scenarios(plan: Sequence[Mapping[str, Any]]) -> list[tuple[str, Mapping[str, Any]]]:
    """(id, scenario) pairs for scenarios that need code; shared with the validator."""
    indexed = [(i, s) for i, s in enumerate(plan) if not _is_blocked(s)]
    ids = [scenario_id(i, s) for i, s in indexed]
    # If the Planner repeats an id, fall back to positional ids so no file overwrites another
    if len(set(ids)) != len(ids):
        logger.warning("duplicate scenario ids from the Planner; using positional ids")
        ids = [f"s{i + 1}" for i, _ in indexed]
    return list(zip(ids, (s for _, s in indexed)))


def _select_scenarios(ids: list[str], existing: dict[str, Path], errors: Sequence[str]) -> set[str]:
    if not existing or not errors:
        return set(ids)  # first pass, or a human-requested regeneration
    return {i for i in ids if i not in existing} | failing_scenario_ids(errors, set(ids))


def _merge_models(previous: Any, seen: Sequence[str]) -> str:
    """Keep every model used across retries (e.g. primary + fallback), without duplicates."""
    earlier = [m for m in str(previous or "").split(", ") if m]
    return ", ".join(dict.fromkeys([*earlier, *seen]))


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
        all_scenarios = list(state.get("test_plan") or [])
        if not all_scenarios:
            raise CodegenError("test_plan is empty")

        pairs = generatable_scenarios(all_scenarios)
        if not pairs:
            # Not a crash: every scenario is BLOCKED, so the report ends as BLOCKED, not ERROR.
            logger.warning("all scenarios are BLOCKED; nothing to generate")
            return {"generated_test_files": [], "errors": errors}
        ids = [sid for sid, _ in pairs]
        scenarios = [s for _, s in pairs]

        prompt = system_prompt or load_prompt()
        files = _existing_files(state.get("generated_test_files"))
        validation_errors = list(state.get("validation_errors") or [])
        todo = _select_scenarios(ids, files, validation_errors)
        tests_dir = Path(runs_root) / str(state["run_id"]) / "tests"
        target_url = _resolve_url(state.get("target_url"))
        models_seen: list[str] = []
        from llm.run_auth import auth_prompt_info

        authentication = auth_prompt_info(state.get("test_request"))  # names only, never values

        for sid, scenario in zip(ids, scenarios):
            if sid not in todo:
                continue
            try:
                file_name = spec_file_name(sid, str(scenario.get("name") or sid))
                previous = files[sid].read_text(encoding="utf-8") if sid in files and files[sid].is_file() else None
                code, model = generate_one(
                    backend, prompt, scenario=scenario, sid=sid, target_url=target_url,
                    previous_code=previous,
                    validation_errors=errors_for(sid, validation_errors) if previous else (),
                    reviewer_note=state.get("reviewer_note"),
                    authentication=authentication,
                )
                if model not in models_seen:
                    models_seen.append(model)
                files[sid] = write_spec(tests_dir, file_name, code)
            except (LLMUnavailableError, BudgetExceededError) as exc:
                # The LLM layer is down or the budget is spent for the WHOLE run: retrying the
                # remaining scenarios would only repeat the failure. Stop and mark it with a tag
                # that the router turns into terminal_status = ERROR.
                safe = redact(str(exc))
                logger.error("LLM unavailable during codegen, stopping: %s", safe)
                errors.append(f"{LLM_FATAL_TAG}[codegen]: {safe}")
                break
            except Exception as exc:  # one bad scenario must not stop the others
                logger.exception("codegen failed for scenario %s", sid)
                # TODO(P5): agree on a state field for BLOCKED "could not generate" scenarios.
                errors.append(f"codegen[{sid}]: {redact(str(exc))}")

        update: dict[str, Any] = {
            "generated_test_files": [str(files[i]) for i in ids if i in files],
            "errors": errors,
        }
        if models_seen:
            models_used = dict(state.get("models_used") or {})
            models_used["codegen"] = _merge_models(models_used.get("codegen"), models_seen)
            update["models_used"] = models_used
        return update
    except Exception as exc:  # node invariant: catch into state.errors, the report still runs
        logger.exception("codegen node failed")
        return {"errors": [*errors, f"codegen: {redact(str(exc))}"]}