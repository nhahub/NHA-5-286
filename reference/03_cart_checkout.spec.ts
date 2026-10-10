import { test, expect } from '../fixtures/evidence.fixture';

test.describe('E-commerce Cart', () => {
  test('Add item to cart successfully', async ({ page }) => {
    await page.goto('https://example.com/products');
    
    // Click add to cart for the first product
    await page.locator('[data-testid="add-to-cart-btn"]').first().click();
    
    // Verify cart badge updated
    const cartBadge = page.locator('.cart-badge');
    await expect(cartBadge).toHaveText('1');
    
    // Navigate to cart
    await page.getByRole('link', { name: 'Shopping Cart' }).click();
    
    // Assert item is in cart
    await expect(page.getByRole('table')).toContainText('Product');
  });
});