import { test, expect } from '@playwright/test';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

/**
 * User Journey Tests - Analytics Dashboard
 * Tests core user flows that match the actual frontend
 */

test.describe('Analytics Dashboard Access - User Journey', () => {
  let helpers: ReturnType<typeof createTestHelpers>;

  test.beforeEach(async ({ page, context, browserName }, testInfo) => {
    helpers = createTestHelpers(page, context, testInfo);
    helpers.logStep(`Starting test on ${browserName}`);
  });

  test.describe('Login Flow', () => {
    test('should allow admin user to login and access dashboard', async ({ page }) => {
      helpers.logStep('Testing admin login and dashboard access');

      // Step 1: Navigate to login page
      await helpers.navigateTo('/login');
      await helpers.expectElementVisible('[data-testid="email-input"]');
      await helpers.takeScreenshot('login-page-loaded');

      // Step 2: Login with admin credentials
      await helpers.login({
        email: TEST_DATA.USERS.ADMIN.email,
        password: TEST_DATA.USERS.ADMIN.password,
      });
      helpers.logStep('Successfully logged in as admin');

      // Step 3: Verify dashboard loaded (check for Overview heading)
      await expect(page.locator('h1')).toContainText('Overview');
      await helpers.takeScreenshot('dashboard-loaded');

      // Step 4: Navigate to analytics dashboard
      await page.goto(`${helpers.page.evaluate(() => location.origin)}/analytics`);
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
      helpers.logStep('Successfully navigated to analytics dashboard');
    });

    test('should allow regular user to login with limited access', async ({ page }) => {
      helpers.logStep('Testing regular user login and access');

      // Step 1: Login as regular user
      await helpers.login({
        email: TEST_DATA.USERS.USER.email,
        password: TEST_DATA.USERS.USER.password,
      });
      helpers.logStep('Successfully logged in as regular user');

      // Step 2: Verify dashboard loads
      await expect(page.locator('h1')).toContainText('Overview');

      // Step 3: Navigate to analytics
      await page.goto(`${helpers.page.evaluate(() => location.origin)}/analytics`);
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
    });

    test('should handle invalid login credentials', async ({ page }) => {
      helpers.logStep('Testing invalid login handling');

      // Step 1: Navigate to login page
      await helpers.navigateTo('/login');

      // Step 2: Attempt login with invalid credentials
      await helpers.fillField('[data-testid="email-input"]', 'invalid@test.com');
      await helpers.fillField('[data-testid="password-input"]', 'invalidpassword');
      await helpers.waitAndClick('[data-testid="login-button"]');

      // Step 3: Verify error message appears (error div with role="alert")
      await helpers.expectElementVisible('[role="alert"]');
      helpers.logStep('Error message displayed correctly');

      // Step 4: Verify user stays on login page
      await expect(page).toHaveURL(/.*login/);
      helpers.logStep('User correctly remains on login page');
    });
  });

  test.describe('Dashboard Navigation', () => {
    test.beforeEach(async ({ page }) => {
      // Login as admin for navigation tests
      await helpers.login(TEST_DATA.USERS.ADMIN);
    });

    test('should navigate to dashboard and see quick actions', async ({ page }) => {
      helpers.logStep('Testing dashboard quick actions');

      // Dashboard should show quick actions
      await expect(page.locator('text=Upload')).toBeVisible();
      await expect(page.locator('text=Search')).toBeVisible();
      await expect(page.locator('text=Chat')).toBeVisible();
      await expect(page.locator('text=arXiv')).toBeVisible();
      helpers.logStep('Quick actions are visible');
    });

    test('should navigate to analytics page', async ({ page }) => {
      helpers.logStep('Testing analytics navigation');

      await page.goto(`${helpers.page.evaluate(() => location.origin)}/analytics`);
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
      helpers.logStep('Analytics page loaded');
    });
  });

  test.describe('Authentication Guards', () => {
    test('should redirect to login when accessing dashboard unauthenticated', async ({ page }) => {
      helpers.logStep('Testing auth guard on dashboard');

      await page.goto(`${helpers.page.evaluate(() => location.origin)}/dashboard`);
      await page.waitForURL(/.*login/, { timeout: 10000 });
      await expect(page).toHaveURL(/.*login/);
      helpers.logStep('Correctly redirected to login');
    });

    test('should redirect to login when accessing analytics unauthenticated', async ({ page }) => {
      helpers.logStep('Testing auth guard on analytics');

      await page.goto(`${helpers.page.evaluate(() => location.origin)}/analytics`);
      await page.waitForURL(/.*login/, { timeout: 10000 });
      await expect(page).toHaveURL(/.*login/);
      helpers.logStep('Correctly redirected to login');
    });
  });
});
