import { test, expect } from '@playwright/test';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

/**
 * User Journey Tests - Real-time Features
 * Tests real-time monitoring and diagnostics
 */

test.describe('Real-time Monitoring - User Journey', () => {
  let helpers: ReturnType<typeof createTestHelpers>;

  test.beforeEach(async ({ page, context, browserName }, testInfo) => {
    helpers = createTestHelpers(page, context, testInfo);
    helpers.logStep(`Starting real-time monitoring test on ${browserName}`);
  });

  test.describe('Authenticated Access', () => {
    test.beforeEach(async () => {
      await helpers.login(TEST_DATA.USERS.ADMIN);
    });

    test('should access diagnostics page', async ({ page }) => {
      await page.goto('/diagnostics');
      await expect(page).toHaveURL(/.*diagnostics/);
      await helpers.expectElementVisible('[data-testid="diagnostics-page"]');
      helpers.logStep('Diagnostics page loaded successfully');
    });

    test('should access dashboard and see live status', async ({ page }) => {
      await page.goto('/dashboard');
      await expect(page).toHaveURL(/.*dashboard/);
      
      // Check for live status indicator
      await expect(page.locator('text=Live')).toBeVisible();
      helpers.logStep('Dashboard shows live status');
    });
  });

  test.describe('Auth Guards', () => {
    test('should redirect unauthenticated users', async ({ page }) => {
      await page.goto('/diagnostics');
      await page.waitForURL(/.*login/, { timeout: 10000 });
      await expect(page).toHaveURL(/.*login/);
      helpers.logStep('Correctly redirected to login');
    });
  });
});
