import { test, expect } from '../fixtures/evidence.fixture';

test.describe('Authentication - Negative', () => {
  test('Show error on invalid credentials', async ({ page }) => {
    await page.goto('https://example.com/login');
    
    await page.getByRole('textbox', { name: 'Username' }).fill('invalid_user');
    await page.getByRole('textbox', { name: 'Password' }).fill('wrong_password');
    await page.getByRole('button', { name: 'Log in' }).click();
    
    // Assert error message
    const errorAlert = page.locator('.alert-error');
    await expect(errorAlert).toBeVisible();
    await expect(errorAlert).toContainText('Invalid username or password');
  });
});