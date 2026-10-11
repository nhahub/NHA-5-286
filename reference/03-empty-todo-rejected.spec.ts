import { test, expect } from '@support/evidence';

test('Empty input does not create a todo item', async ({ page }) => {
  await page.goto('https://demo.playwright.dev/todomvc');

  await page.getByPlaceholder('What needs to be done?').press('Enter');

  await expect(page.getByTestId('todo-item')).toHaveCount(0);
});