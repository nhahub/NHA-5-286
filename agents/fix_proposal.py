"""
Purpose: Fix Proposal agent — proposes the minimal patch that repairs a failing test without hiding real bugs.
Reads: failure_analysis, execution_evidence, test code
Writes: fix_proposal
Must not: apply its own patch or change anything outside the spec file
"""


from pathlib import Path
from collections.abc import Callable
from agents.codegen import spec_file_name
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.exceptions import OutputParserException
from contracts.analysis import FailureAnalysis, FixProposal
import json
from typing import Any, Mapping
from contracts.evidence import Evidence
from llm.client import record_model_used, structured_chain_with_json_fallback
import subprocess
import difflib
from tempfile import TemporaryDirectory
import re
from pydantic import BaseModel, Field
from llm.retry import call_with_backoff
from healing.patch_guard import (
    FailureTarget,
    PatchVerdict,
    apply_diff_text,
    check_patch,
    locate_failure,
    make_rejection,
    snapshot_text,
)

MAX_SNAPSHOT_IN_CONTEXT = 12_000


class PatchRejected(ValueError):
    """The proposed fix does not address the diagnosed failure (decided deterministically, before approval)."""

    def __init__(self, verdict: PatchVerdict) -> None:
        super().__init__(verdict.message)
        self.verdict = verdict


class RawFix(BaseModel):
    """What the model returns. The system builds the unified diff itself: models write hunk headers badly."""

    reason: str = Field(min_length=3)
    risky: bool = False
    fixed_code: str | None = None   # the complete corrected spec file (preferred)
    patch_diff: str | None = None   # optional ready-made diff (used only when fixed_code is absent)


def build_patch_diff(original: str, fixed: str, spec_filename: str) -> str:
    """Unified diff from the original to the fixed spec, in the exact form validate_patch_on_copy expects."""
    lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        fixed.splitlines(keepends=True),
        fromfile=f"a/{spec_filename}",
        tofile=f"b/{spec_filename}",
        n=3,
    )
    out: list[str] = []
    for line in lines:
        out.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
    return "".join(out)




def build_failure_context(state: Mapping[str, Any],*, spec_code: str, spec_filename: str,
                          failing_location: dict | None = None, snapshot: str = "") -> str:
    """
    Prepare failure information for the Fix Proposal LLM.
    Does not modify any files.
    """

    analysis = FailureAnalysis.model_validate(
        state["failure_analysis"]
    )

    if (
        analysis.failure_type != "Test"
        or not analysis.fix_required
    ):
        raise ValueError(
            "Failure is not eligible for a test fix."
        )

    evidence_items = state.get("execution_evidence") or []

    if not evidence_items:
        raise ValueError("Missing execution evidence.")

    if not spec_code.strip():
        raise ValueError("Missing failing test code.")

    evidence = [
        Evidence.model_validate(item).model_dump()
        for item in evidence_items
    ]

    context = {
        "failure_analysis": analysis.model_dump(),
        "execution_evidence": evidence,
        "test_plan": state.get("test_plan", []),
        "original_requirements": (
            (state.get("test_request") or {})
            .get("requirements", "")
        ),
        "spec_code": spec_code,
        "spec_filename": spec_filename,
        "failing_location": failing_location,
        "page_snapshot": snapshot[:MAX_SNAPSHOT_IN_CONTEXT] or None,
        "patch_instruction": (
        f"Return fixed_code: the COMPLETE corrected content of {spec_filename}, "
        "changing only the failing line/locator in failing_location. Use only names, labels and roles that appear "
        "in page_snapshot. Never use force: true or any forced interaction. "
        "Do not write a diff; the system builds it."
),
    }

    return json.dumps(
        context,
        indent=2,
        ensure_ascii=False,
    )

def build_fix_proposal_agent(model: str,mcp_tools: list,*,model_factory: Callable[[str], BaseChatModel],) -> Runnable:
    """
    Build a Fix Proposal agent with structured output.

    This function does not apply patches or modify files.
    """

    if mcp_tools:
        raise NotImplementedError(
            "Fix Proposal tools are not connected yet."
        )

    prompt_path = (
        Path(__file__).resolve().parents[1]
        / "prompts"
        / "fix_proposal.md"
    )

    system_prompt = prompt_path.read_text(
        encoding="utf-8"
    )

    # SystemMessage keeps the prompt literal: the JSON example in it contains braces that
    # ChatPromptTemplate would otherwise treat as template variables.
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_prompt),
        ("human", "{failure_context}"),
    ])

    llm = model_factory(model)

    return structured_chain_with_json_fallback(prompt, llm, RawFix)

def validate_and_flag_proposal( raw_proposal: dict,analysis_data: dict,) -> dict:

    analysis = FailureAnalysis.model_validate(
        analysis_data
    )

    if (
        analysis.failure_type != "Test"
        or not analysis.fix_required
    ):
        raise ValueError(
            "This failure is not eligible for a test fix."
        )

    proposal = FixProposal.model_validate(
        raw_proposal
    )

    # Initial conservative risk rules
    if analysis.subtype not in ("SELECTOR", "TIMING"):
        proposal = proposal.model_copy(
            update={"risky": True}
        )

    return proposal.model_dump()

def validate_patch_on_copy(
    patch_diff: str,
    spec_code: str,
    spec_filename: str,
) -> None:
    """
    Validate a unified diff against a temporary copy.

    Never modifies the original spec file.
    Raises ValueError when the patch is invalid.
    """

    # Allow a single Playwright spec file only.
    if (
        not spec_filename.endswith(".spec.ts")
        or Path(spec_filename).name != spec_filename
    ):
        raise ValueError("Invalid spec filename.")

    lines = patch_diff.splitlines()

    expected_headers = [
        f"--- a/{spec_filename}",
        f"+++ b/{spec_filename}",
    ]

    headers = [
        line for line in lines
        if line.startswith(("--- ", "+++ "))
    ]

    if lines[:2] != expected_headers or headers != expected_headers:
        raise ValueError(
            "Patch must target exactly the expected spec file."
        )

    if (
        not any(line.startswith("@@ -") for line in lines[2:])
        or any(line.startswith("diff --git ") for line in lines)
    ):
        raise ValueError("Invalid unified diff format.")

    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / spec_filename

        temp_path.write_bytes(
            spec_code.encode("utf-8")
        )

        try:
             result = subprocess.run(
            ["git", "apply", "--check", "-"],
            input=patch_diff.encode("utf-8"),
            capture_output=True,
            cwd=temp_dir,
            timeout=10,
            check=False,
        )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Git is required for patch validation."
            ) from exc

        if result.returncode != 0:
            raise ValueError(
                "Patch cannot be applied cleanly: "
               + result.stderr.decode("utf-8", errors="replace").strip()[:300]
            )

def _rejected(code: str, message: str, target: FailureTarget | None, subtype: str | None, *,
              attempts: int = 0, codes: tuple[str, ...] = ()) -> dict:
    """State update for a fix that could not be proposed safely. Clearing fix_proposal keeps routing on 'report'."""
    return {
        "fix_proposal": None,
        "fix_rejection": make_rejection(code, message, target=target, subtype=subtype, codes=codes, attempts=attempts),
    }


def _failure_target(state: Mapping[str, Any], spec_code: str, subtype: str | None):
    """(target, DOM snapshot text, early rejection or None) for the first failed scenario, before any LLM call."""
    item = next((e for e in (state.get("execution_evidence") or [])
                 if isinstance(e, Mapping) and e.get("error_message")), None)
    if item is None:
        return None, "", None  # build_failure_context reports the missing evidence
    snapshot = snapshot_text(item.get("page_snapshot"))
    target = locate_failure(item.get("error_message"), spec_code)
    if target is None:
        return None, snapshot, _rejected(
            "unlocated_failure", "The failing line could not be identified from the error message and call log, so "
            "no fix can be checked against the failure.", None, subtype)
    if target.ambiguous:
        return target, snapshot, _rejected(
            "ambiguous_failure", "The failing locator appears on several lines and none can be tied to the failure.",
            target, subtype)
    if subtype == "SELECTOR" and not snapshot.strip():
        return target, snapshot, _rejected(
            "insufficient_evidence", "No DOM snapshot was captured for this failure, so a selector change would be a "
            "guess. No patch was proposed.", target, subtype)
    return target, snapshot, None


def run_fix_proposal( state: Mapping[str, Any], *, spec_code: str,spec_filename: str, model: str,
model_factory: Callable[[str], BaseChatModel]) -> dict:
    """
    Generate and validate a fix proposal.
    Never applies or writes the patch.
    """

    subtype = (state.get("failure_analysis") or {}).get("subtype")

    # 1. Locate the failure and check the DOM evidence BEFORE any LLM call, so a hopeless request costs nothing
    target, snapshot, early_rejection = _failure_target(state, spec_code, subtype)
    if early_rejection is not None:
        return early_rejection

    # 2. Prepare failure context
    context = build_failure_context(
        state,
        spec_code=spec_code,
        spec_filename=spec_filename,
        failing_location=(
            {"line": target.line, "code": target.line_text.strip(), "locator": target.locator}
            if target else None
        ),
        snapshot=snapshot,
    )

    # 3. Build the LLM agent
    agent = build_fix_proposal_agent(
        model=model,
        mcp_tools=[],
        model_factory=model_factory,
    )


    # 4. Generate a fix with at most one retry
    original_context = context

    for attempt in range(2):
        try:
            response = call_with_backoff(
                lambda: agent.invoke({"failure_context": context})
            )

            # 4. Validate structured output and build the diff ourselves
            data = (
                response.model_dump()
                if isinstance(response, BaseModel)
                else dict(response)
            )
            fixed_code = data.get("fixed_code")
            if fixed_code:
                from agents.codegen import normalize_model_code

                fixed_code = normalize_model_code(fixed_code)
            if fixed_code and fixed_code.strip():
                if fixed_code.strip() == spec_code.strip():
                    raise ValueError("fixed_code is identical to the original spec.")
                patch_diff = build_patch_diff(spec_code, fixed_code, spec_filename)
                proposed_text = fixed_code
            else:
                patch_diff = data.get("patch_diff") or ""
                proposed_text = apply_diff_text(patch_diff, spec_code, spec_filename) if patch_diff.strip() else ""

            # Deterministic pre-approval guard: does this patch address THIS failure? (no LLM, no healing attempt used)
            if target is not None and proposed_text:
                verdict = check_patch(
                    spec_code, proposed_text, target=target, subtype=subtype, snapshot=snapshot,
                    lint_name=spec_filename,
                    skip_lint_rules=(
                        frozenset({"hardcoded-secret"})  # login page under test: fake literal input is expected
                        if (state.get("test_request") or {}).get("auth_skipped") else frozenset()
                    ),
                )
                if not verdict.ok:
                    raise PatchRejected(verdict)

            raw_proposal = FixProposal.model_validate({
                "patch_diff": patch_diff,
                "reason": data.get("reason"),
                "risky": bool(data.get("risky", False)),
            }).model_dump()

            # 5. Enforce risk rules
            proposal = validate_and_flag_proposal(
                raw_proposal,
                state["failure_analysis"],
            )

            # 6. Check patch without modifying real files
            validate_patch_on_copy(
                patch_diff=proposal["patch_diff"],
                spec_code=spec_code,
                spec_filename=spec_filename,
            )

        except (ValueError, OutputParserException) as exc:

            # Both attempts failed
            if attempt == 1:
                if isinstance(exc, PatchRejected):
                    # Not a system error: the diagnosis stands, but no safe fix could be proposed. The run stays FAIL
                    # and no healing attempt is used (that counter only moves in apply_fix, after approval).
                    return {
                        **_rejected(exc.verdict.code or "rejected", exc.verdict.message, target, subtype,
                                    attempts=2, codes=exc.verdict.codes),
                        **record_model_used("fix_proposal", model, state),
                    }
                raise ValueError(
                    "Fix Proposal failed validation "
                    "after 2 attempts."
                ) from exc

            # First attempt failed: tell the LLM why
            if isinstance(exc, PatchRejected):
                context = (
                    original_context
                    + "\n\nYour previous fixed_code was REJECTED before approval: "
                    + f"{exc.verdict.message[:600]}\n"
                    + "Change only the failing line/locator in failing_location, use only names that appear in "
                      "page_snapshot, never use force: true, and return the complete corrected file."
                )
                continue
            context = (
                original_context
                + "\n\nYour previous proposal failed "
                  "validation.\n"
                + f"Validation error: {str(exc)[:350]}\n"
                + "Generate a corrected FixProposal. "
                  "The unified diff must target exactly "
                + f"{spec_filename}, use correct hunk "
                  "line counts, and match the original "
                  "spec code exactly. Do not change "
                  "any other file."
            )
            continue

        # 7. Return only after successful validation
        return {
            "fix_proposal": proposal,
            "fix_rejection": None,
            **record_model_used(
                "fix_proposal",
                model,
                state,
            ),
        }


def select_failed_spec_file(
    state: Mapping[str, Any],
) -> Path:
    """
    Match the failed scenario to its generated spec file.

    Does not read or modify any files.
    """

    # 1. Validate execution evidence
    evidence_items = [
        Evidence.model_validate(item)
        for item in (
            state.get("execution_evidence") or []
        )
    ]

    # 2. Identify failed scenarios
    failed_names = list(dict.fromkeys(
        item.scenario_name
        for item in evidence_items
        if item.error_message
    ))

    if not failed_names:
        raise ValueError("No failed scenario found in the evidence.")

    # One test is healed at a time; the first failed scenario goes first.
    scenario_name = failed_names[0]

    # 3. Match the scenario to its generated file
    matches = []

    for raw_path in (
        state.get("generated_test_files") or []
    ):
        path = Path(raw_path)

        parts = path.name.split("-", 1)

        if len(parts) != 2:
            continue

        sid = parts[0]

        expected_name = spec_file_name(
            sid,
            scenario_name,
        )

        if path.name == expected_name:
            matches.append(path)

    # 4. Reject missing or ambiguous matches
    if len(matches) != 1:
        raise ValueError(
            "Could not uniquely identify the "
            "failed spec file."
        )

    return matches[0]


def read_failed_spec_code(
    state: Mapping[str, Any],
) -> tuple[str, str]:
    """
    Read the failed spec file only if it belongs
    to the current run's tests directory.
    """

    run_id = str(state.get("run_id") or "")

    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("Invalid run ID.")

    # Identify the failed spec
    selected = select_failed_spec_file(state)

    project_root = Path(__file__).resolve().parents[1]
    runs_root = (project_root / "runs").resolve()

    allowed_dir = (
        runs_root / run_id / "tests"
    ).resolve()

    # Prevent the run directory from escaping runs/
    if not allowed_dir.is_relative_to(runs_root):
        raise ValueError("Unsafe run directory.")

    # Support both absolute and relative paths
    if selected.is_absolute():
        file_path = selected.resolve()
    else:
        file_path = (project_root / selected).resolve()

    # Allow one actual .spec.ts file in this run
    if (
        not file_path.name.endswith(".spec.ts")
        or file_path.parent != allowed_dir
        or not file_path.is_file()
    ):
        raise ValueError(
            "Failed spec file is missing or outside "
            "the current run."
        )

    spec_code = file_path.read_text(encoding="utf-8")

    if not spec_code.strip():
        raise ValueError("Failed spec file is empty.")

    return spec_code, file_path.name

# def build_fix_proposal_agent(model: str, mcp_tools: list) -> Runnable:
#     -> Creates a LangChain agent with the fix_proposal system prompt (prompts/fix_proposal.md),
#        structured output (FixProposal), and allowed MCP tools:
#        read_test_file, browser_generate_locator, save_test_file

# def run_fix_proposal(state: TestRunState) -> TestRunState:
#     -> LangGraph node function
#     -> Calls build_fix_proposal_agent; validates output as FixProposal with one retry
#     -> Forces risky=True when failure_analysis.subtype == "ASSERTION" (assertion expected-value changes are always risky)
#     -> Writes fix_proposal; records model in models_used["fix_proposal"]
