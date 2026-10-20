import { test, expect } from '@support/evidence';

test('Empty input does not create a todo item', async ({ page }) => {
  await page.goto('https://demo.playwright.dev/todomvc');

  const input = page.getByPlaceholder('What needs to be done?');
  await expect(input).toBeVisible(); // the page is ready, so a count of 0 is meaningful

  await input.press('Enter');
  await expect(page.getByTestId('todo-item')).toHaveCount(0);

  // Control step: a real item is added, and it is the only one in the list
  await input.fill('Control item');
  await input.press('Enter');
  await expect(page.getByTestId('todo-item')).toHaveCount(1);
});