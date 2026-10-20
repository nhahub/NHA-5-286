
from contracts.analysis import FailureAnalysis, FixProposal


def mock_analyze(state: dict) -> dict:
    """Return a simulated test selector failure."""

    analysis = FailureAnalysis(
        failure_type="Test",
        root_cause="Login button selector has changed.",
        evidence="MOCK: Playwright could not find #login-btn.",
        application_bug=False,
        fix_required=True,
        subtype="SELECTOR",
    )

    return {
        "failure_analysis": analysis.model_dump(),
        "failure_type": analysis.failure_type,
    }



def mock_propose_fix(state: dict) -> dict:
    from contracts.analysis import FixProposal

    risky = state.get("mock_risky", False)

    if risky:
        proposal = FixProposal(
            patch_diff=(
                "--- a/login.spec.ts\n"
                "+++ b/login.spec.ts\n"
                "-await expect(error).toBeVisible();\n"
                "+await expect(error).toBeHidden();"
            ),
            reason="MOCK: Proposed assertion change.",
            risky=True,
        )
    else:
        proposal = FixProposal(
            patch_diff=(
                "--- a/login.spec.ts\n"
                "+++ b/login.spec.ts\n"
                "-await page.locator('#login-btn').click();\n"
                "+await page.getByRole('button', "
                "{ name: 'Login' }).click();"
            ),
            reason="MOCK: Update outdated selector.",
            risky=False,
        )

    return {"fix_proposal": proposal.model_dump()}
