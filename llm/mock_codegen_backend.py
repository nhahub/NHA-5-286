
import json

from agents.codegen import CodegenResult


class MockCodegenBackend:
    def generate(
        self,
        system_prompt: str,
        user_payload: str
    ) -> tuple[CodegenResult, str]:

        payload = json.loads(user_payload)
        sid = payload["scenario"]["id"]

        code = """
import { test, expect } from '@support/evidence';

test('Invalid Login', async ({ page }) => {
    await page.goto('https://example.com/login');

    await page.getByLabel('Username').fill(
        process.env.TEST_USERNAME ?? 'invalid_user'
    );

    await page.getByLabel('Password').fill(
        process.env.TEST_PASSWORD ?? ''
    );

    await page.getByRole('button', { name: 'Login' }).click();

    await expect(
        page.getByText('Invalid credentials')
    ).toBeVisible();
});
"""

        return (
            CodegenResult(
                scenario_id=sid,
                code=code
            ),
            "mock-codegen"
        )
