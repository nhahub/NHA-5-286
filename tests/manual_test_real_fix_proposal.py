
from getpass import getpass
from uuid import uuid4

from agents.fix_proposal import run_fix_proposal

from llm.settings import (
    LLMSettings,
    validate_settings,
    register_run_credentials,
    release_run_credentials,
    model_factory_for,
)


def main():
    # 1. Read the user's LLM configuration
    provider = input(
        "Provider (Groq/Gemini/OpenRouter): "
    ).strip()

    model = input("Model name: ").strip()

    # Hidden input. Leave blank to use an environment key.
    api_key = getpass(
        "API key (Enter to use environment): "
    )

    # 2. Test the real provider connection
    print("\nChecking LLM connection...")

    valid, message = validate_settings(
        provider, model, api_key
    )

    print(message)

    if not valid:
        return

    # 3. Give this test its own thread ID
    thread_id = str(uuid4())

    settings = LLMSettings(
        provider=provider,
        model=model,
        api_key=api_key,
        validated=True,
    )

    # 4. Prepare simulated failure evidence
    state = {
        "failure_analysis": {
            "failure_type": "Test",
            "subtype": "SELECTOR",
            "root_cause": (
                "The Login button locator does not "
                "match the sample page snapshot."
            ),
            "evidence": (
                "Locator Login timed out. "
                "Snapshot shows a Sign in button."
            ),
            "application_bug": False,
            "fix_required": True,
        },
        "execution_evidence": [
            {
                "scenario_name": "Invalid Login",
                "error_message": "Login locator timed out",
                "failed_step": "Click Login button",
                "page_snapshot": {
                    "html": (
                        "<button aria-label='Sign in'>"
                        "Sign in</button>"
                    )
                },
            }
        ],
        "test_request": {
            "requirements": (
                "Test invalid login and verify "
                "the error message."
            )
        },
        "models_used": {},
    }

    spec_code = """
import { test, expect } from '@support/evidence';

test('Invalid Login', async ({ page }) => {
    await page.goto('https://example.com/login');

    await page.getByRole('button', {
        name: 'Login'
    }).click();

    await expect(
        page.getByText('Invalid credentials')
    ).toBeVisible();
});
"""

    # 5. Register credentials for this run
    register_run_credentials(thread_id, settings)

    try:
        print("\nCalling Real Fix Proposal LLM...")

        result = run_fix_proposal(
            state,
            spec_code=spec_code,
            model=settings.model_string,
            model_factory=model_factory_for(thread_id),
        )

        print("\n=== FIX PROPOSAL RESULT ===")
        print("Reason:", result["fix_proposal"]["reason"])
        print("Risky:", result["fix_proposal"]["risky"])
        print("Patch:")
        print(result["fix_proposal"]["patch_diff"])

        print(
            "Model used:",
            result["models_used"]["fix_proposal"]
        )

        print("\nREAL LLM TEST COMPLETED")

    finally:
        # Always release credentials after this test
        release_run_credentials(thread_id)


if __name__ == "__main__":
    main()
