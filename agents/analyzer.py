
"""
Purpose: Failure Analyzer agent.

Responsibilities:
- Analyze execution evidence and classify failures.
- Validate model output against the project contracts.
- Apply deterministic failure-class validation.
- Retry once when model output or validation fails.

Reads:
- execution_result
- execution_evidence
- test_plan
- failed Playwright spec code

Writes:
- failure_analysis
- failure_type
- models_used["analyzer"] on success

Safety:
- Never apply fixes or modify project files.
- Never guess an unsupported failure class.
- Never expose API credentials.
- Preserve sandbox and non-Gemini provider behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from analysis.pre_classifier import classify
from agents.fix_proposal import read_failed_spec_code
from contracts.analysis import FailureAnalysis
from llm.client import record_model_used


class RawFailureAnalysis(BaseModel):
    """Intermediate schema for validating model-generated analysis."""

    failure_type: str
    root_cause: str = Field(min_length=10)
    evidence: str = Field(min_length=1)
    application_bug: bool
    fix_required: bool
    subtype: str | None = None
    confidence: Literal["low", "medium", "high"] = "low"
    ruled_out: list[str] = Field(default_factory=list)
    suggested_fix: str | None = None


def build_failure_context(state: dict) -> str:
    """Build a JSON context containing the available execution evidence."""

    execution_result = state.get("execution_result") or {}
    execution_evidence = state.get("execution_evidence") or []
    test_plan = state.get("test_plan") or []

    try:
        spec_code, spec_filename = read_failed_spec_code(state)
        spec_context = (
            f"Spec filename: {spec_filename}\n"
            f"Spec code:\n{spec_code}"
        )
    except (ValueError, KeyError, OSError) as exc:
        spec_context = (
            "Spec code unavailable. "
            f"Reason: {type(exc).__name__}: {exc}"
        )

    context = {
        "run_id": state.get("run_id"),
        "target_url": state.get("target_url"),
        "execution_result": execution_result,
        "execution_evidence": execution_evidence,
        "test_plan": test_plan,
        "spec_context": spec_context,
    }

    return json.dumps(
        context,
        indent=2,
        ensure_ascii=False,
        default=str,
    )


def _load_system_prompt() -> str:
    """Load the canonical analyzer instructions."""

    prompt_path = (
        Path(__file__).resolve().parents[1]
        / "prompts"
        / "analyzer.md"
    )
    return prompt_path.read_text(encoding="utf-8")


def build_analyzer_agent(
    model: str,
    mcp_tools: list,
    *,
    model_factory,
):
    """Build the existing LangChain structured-output analyzer."""

    if mcp_tools:
        raise NotImplementedError(
            "Analyzer MCP tools are not implemented yet."
        )

    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=_load_system_prompt()),
            (
                "human",
                "Analyze the following execution context:\n"
                "{failure_context}\n\n"
                "Validation feedback from the previous attempt:\n"
                "{retry_feedback}",
            ),
        ]
    )

    llm = model_factory(model)
    structured_llm = llm.with_structured_output(RawFailureAnalysis)

    return prompt | structured_llm


def _build_interactions_input(
    failure_context: str,
    retry_feedback: str,
) -> str:
    """Build a complete text input for Gemini Interactions API."""

    return (
        f"{_load_system_prompt()}\n\n"
        "Analyze the following execution context:\n"
        f"{failure_context}\n\n"
        "Validation feedback from the previous attempt:\n"
        f"{retry_feedback}\n\n"
        "Return only a JSON object that follows the supplied schema. "
        "Do not include Markdown fences or additional commentary."
    )


def _invoke_gemini_interactions(
    *,
    model: str,
    model_factory,
    failure_context: str,
    retry_feedback: str,
) -> RawFailureAnalysis:
    """Call Gemini Interactions API using the current run's credentials."""

    client_factory = getattr(
        model_factory,
        "gemini_interactions_client",
        None,
    )

    if client_factory is None:
        raise RuntimeError(
            "Gemini Interactions client is not configured for this run. "
            "Update model_factory_for() in llm/settings.py."
        )

    # Keep the project model string for registry validation.
    client = client_factory(model)

    # Interactions API expects the provider's model name, not the
    # project's provider:model identifier.
    if ":" not in model:
        raise ValueError("Invalid Gemini model identifier.")

    provider, model_name = model.split(":", 1)
    if provider != "google_genai" or not model_name.strip():
        raise ValueError("Invalid Gemini model identifier.")

    response = client.interactions.create(
        model=model_name,
        input=_build_interactions_input(
            failure_context=failure_context,
            retry_feedback=retry_feedback,
        ),
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": RawFailureAnalysis.model_json_schema(),
        },
    )

    output_text = getattr(response, "output_text", None)
    if not isinstance(output_text, str) or not output_text.strip():
        raise ValueError(
            "Gemini Interactions returned empty or invalid text output."
        )

    # Validate the provider response before project classification.
    return RawFailureAnalysis.model_validate_json(output_text)


def _invoke_analyzer(
    *,
    model: str,
    model_factory,
    analyzer,
    failure_context: str,
    retry_feedback: str,
) -> RawFailureAnalysis:
    """Invoke the correct backend while preserving existing providers."""

    if model.startswith("google_genai:"):
        return _invoke_gemini_interactions(
            model=model,
            model_factory=model_factory,
            failure_context=failure_context,
            retry_feedback=retry_feedback,
        )

    from llm.retry import call_with_backoff

    result = call_with_backoff(
        lambda: analyzer.invoke(
            {
                "failure_context": failure_context,
                "retry_feedback": retry_feedback,
            }
        )
    )

    if isinstance(result, RawFailureAnalysis):
        return result

    if isinstance(result, BaseModel):
        return RawFailureAnalysis.model_validate(result.model_dump())

    if isinstance(result, dict):
        return RawFailureAnalysis.model_validate(result)

    raise ValueError("Analyzer returned an unsupported output type.")


def run_analyzer(
    state: dict,
    *,
    model: str,
    model_factory,
) -> dict:
    """Analyze execution failure with one retry and safe validation."""

    failure_context = build_failure_context(state)

    # MCP integration is intentionally not enabled yet.
    analyzer = None
    if not model.startswith("google_genai:"):
        analyzer = build_analyzer_agent(
            model=model,
            mcp_tools=[],
            model_factory=model_factory,
        )

    retry_feedback = ""
    last_error = None

    for attempt in range(2):
        try:
            raw_analysis = _invoke_analyzer(
                model=model,
                model_factory=model_factory,
                analyzer=analyzer,
                failure_context=failure_context,
                retry_feedback=retry_feedback,
            )

            raw_data = raw_analysis.model_dump()

            # Unknown failure classes must never be guessed.
            classified = classify(raw_data)

            if classified["failure_type"] == "ERROR":
                return {
                    "failure_analysis": None,
                    "failure_type": "ERROR",
                    "terminal_status": "ERROR",
                    "errors": [
                        *(state.get("errors") or []),
                        (
                            "Failure Analyzer returned an unknown "
                            "failure class."
                        ),
                    ],
                }

            # Enforce the canonical project contract.
            analysis = FailureAnalysis.model_validate(classified)

            analysis_dict = analysis.model_dump()
            # Record which scenario this analysis is about, so the report and the healing counter can name it.
            try:
                from agents.fix_proposal import select_failed_spec_file

                analysis_dict["scenario_id"] = select_failed_spec_file(state).name.split("-", 1)[0]
            except (ValueError, KeyError, OSError):
                pass

            updates = {
                "failure_analysis": analysis_dict,
                "failure_type": analysis.failure_type,
            }
            updates.update(
                record_model_used("analyzer", model, state)
            )

            return updates

        except Exception as exc:
            last_error = exc
            retry_feedback = (
                "Your previous output or request failed validation. "
                f"Error type: {type(exc).__name__}. "
                f"Details: {exc}. "
                "Return a corrected result following the schema exactly."
            )

    return {
        "failure_analysis": None,
        "failure_type": "ERROR",
        "terminal_status": "ERROR",
        "errors": [
            *(state.get("errors") or []),
            (
                "Failure Analyzer failed after one retry: "
                f"{type(last_error).__name__}: {last_error}"
            ),
        ],
    }
