import { test, expect } from '@support/evidence';

test('Mark a todo item as complete', async ({ page }) => {
  await page.goto('https://demo.playwright.dev/todomvc');

  const input = page.getByPlaceholder('What needs to be done?');
  await input.fill('Finish report');
  await input.press('Enter');

  const item = page.getByTestId('todo-item').filter({ hasText: 'Finish report' });
  await expect(item).not.toHaveClass(/completed/);

  await item.getByRole('checkbox').check();
  await expect(item).toHaveClass(/completed/);
});