import { test, expect } from '../fixtures/evidence.fixture';
import testData from '../test_data/fixtures.json';

test.describe('Authentication', () => {
  test('Successful login with valid credentials', async ({ page }) => {
    // Navigate to the target URL
    await page.goto('https://example.com/login');
    
    // Fill credentials
    await page.getByRole('textbox', { name: 'Username' }).fill(testData.users.standard.username);
    await page.getByRole('textbox', { name: 'Password' }).fill(testData.users.standard.password);
    
    // Submit
    await page.getByRole('button', { name: 'Log in' }).click();
    
    // Assert successful login
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  });
});