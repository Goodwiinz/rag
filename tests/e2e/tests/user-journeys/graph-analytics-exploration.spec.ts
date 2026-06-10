import { test, expect } from '@playwright/test';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

/**
 * User Journey Tests - Graph & Analytics
 * Tests graph analytics and data exploration
 */

test.describe('Graph Analytics Exploration - User Journey', () => {
  let helpers: ReturnType<typeof createTestHelpers>;

  test.beforeEach(async ({ page, context, browserName }, testInfo) => {
    helpers = createTestHelpers(page, context, testInfo);
    helpers.logStep(`Starting graph analytics test on ${browserName}`);
  });

  test.describe('Authenticated Access', () => {
    test.beforeEach(async () => {
      await helpers.login(TEST_DATA.USERS.ADMIN);
    });

    test('should access analytics page', async ({ page }) => {
      await page.goto('/analytics');
      await expect(page).toHaveURL(/.*analytics/);
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
      helpers.logStep('Analytics page loaded successfully');
    });

    test('should access dashboard with overview', async ({ page }) => {
      await page.goto('/dashboard');
      await expect(page).toHaveURL(/.*dashboard/);
      await expect(page.locator('h1')).toContainText('Overview');
      helpers.logStep('Dashboard overview loaded');
    });
  });

  test.describe('Auth Guards', () => {
    test('should redirect unauthenticated users', async ({ page }) => {
      await page.goto('/analytics');
      await page.waitForURL(/.*login/, { timeout: 10000 });
      await expect(page).toHaveURL(/.*login/);
      helpers.logStep('Correctly redirected to login');
    });
  });
});
