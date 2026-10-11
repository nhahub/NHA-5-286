import { test, expect } from '@support/evidence';

test('Add a new todo item', async ({ page }) => {
  await page.goto('https://demo.playwright.dev/todomvc');

  const input = page.getByPlaceholder('What needs to be done?');
  await input.fill('Buy groceries');
  await input.press('Enter');

  const item = page.getByTestId('todo-item');
  await expect(item).toHaveCount(1);
  await expect(item).toContainText('Buy groceries');
});