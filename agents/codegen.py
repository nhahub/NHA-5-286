"""
Purpose: Code Generation agent — writes a single .spec.ts Playwright test file for one scenario.
Reads: test_plan, validation_errors, reviewer_note
Writes: generated_test_files
Must not: execute tests, hardcode credentials, touch application code
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from contracts.scenario import Scenario
from graph.state import TestRunState


def load_codegen_prompt() -> str:
    """Loads the Code Generation system prompt from prompts/codegen.md."""
    prompt_path = Path(__file__).parent.parent / "prompts" / "codegen.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    
    # Fallback inline system prompt if file is missing
    return (
        "You are the Code Generation agent. Write a single Playwright TypeScript .spec.ts "
        "test file for one scenario. Do not hardcode credentials. Do not execute tests."
    )


def generate_scenario_code(
    scenario: Scenario,
    run_id: str,
    llm_client: Any,
    validation_errors: Optional[List[str]] = None,
    reviewer_note: Optional[str] = None,
) -> str:
    """
    Generates a Playwright TypeScript test file for a single scenario.
    """
    system_prompt = load_codegen_prompt()
    
    # Target file output path specification
    target_dir = Path("runs") / run_id / "tests"
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{scenario.id}.spec.ts"

    # Construct input contextual details
    payload = (
        f"Target Spec Path: {file_path.as_posix()}\n"
        f"Scenario ID: {scenario.id}\n"
        f"Scenario Title: {scenario.title}\n"
        f"Steps:\n" + "\n".join([f"- {step}" for step in scenario.steps]) + "\n"
        f"Expected Result: {scenario.expected_result}\n"
    )

    if validation_errors:
        payload += (
            "\n--- PREVIOUS VALIDATION ERRORS ---\n"
            "Fix ONLY these specific errors without breaking other functionality:\n"
            + "\n".join([f"- {err}" for err in validation_errors]) + "\n"
        )

    if reviewer_note:
        payload += f"\n--- HUMAN REVIEWER NOTE ---\n{reviewer_note}\n"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=payload),
    ]

    # Execute LLM call
    response = llm_client.invoke(messages)
    
    generated_code = ""
    if hasattr(response, "content") and isinstance(response.content, str):
        generated_code = response.content

    # Clean code block markdown fences if present
    if "```typescript" in generated_code:
        generated_code = generated_code.split("```typescript")[1].split("```")[0].strip()
    elif "```ts" in generated_code:
        generated_code = generated_code.split("```ts")[1].split("```")[0].strip()
    elif "```" in generated_code:
        generated_code = generated_code.split("```")[1].split("```")[0].strip()

    # Write file locally
    file_path.write_text(generated_code, encoding="utf-8")
    return file_path.as_posix()


def run_codegen(state: TestRunState) -> Dict[str, Any]:
    """
    LangGraph orchestrator node function for Code Generation.
    Processes all scenarios in test_plan, updates generated_test_files,
    increments regeneration count on retries, and logs model usage.
    """
    run_id = state.get("run_id", "default_run")
    test_plan = state.get("test_plan")

    if not test_plan or not getattr(test_plan, "scenarios", None):
        return {
            "errors": ["run_codegen: No scenarios found in state.test_plan"],
            "terminal_status": "BLOCKED",
        }

    # Extract LLM client configured specifically for codegen or generic fallback
    llm_client = state.get("llm_clients", {}).get("codegen") or state.get("llm_client")
    
    # Retrieve validation errors and reviewer note if this execution is a regeneration retry
    validation_errors = state.get("validation_errors")
    reviewer_note = state.get("reviewer_note")
    
    # Manage retry counter
    current_retry_count = state.get("generation_retry_count", 0)
    if validation_errors or reviewer_note:
        current_retry_count += 1

    generated_files: List[str] = []

    # Iterate through scenarios and generate spec files
    for scenario in test_plan.scenarios:
        generated_path = generate_scenario_code(
            scenario=scenario,
            run_id=run_id,
            llm_client=llm_client,
            validation_errors=validation_errors,
            reviewer_note=reviewer_note,
        )
        generated_files.append(generated_path)

    # Track model metadata
    models_used = state.get("models_used", {}).copy()
    model_name = getattr(llm_client, "model_name", None) or getattr(llm_client, "model", "default_codegen_model")
    models_used["codegen"] = model_name

    return {
        "generated_test_files": generated_files,
        "generation_retry_count": current_retry_count,
        "validation_status": None,  # Reset status so validate node re-evaluates
        "models_used": models_used,
    }

