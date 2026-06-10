import { test, expect } from '@playwright/test';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

/**
 * User Journey Tests - Core Navigation
 * Tests basic navigation across the app
 */

test.describe('Core Navigation - User Journey', () => {
  let helpers: ReturnType<typeof createTestHelpers>;

  test.beforeEach(async ({ page, context, browserName }, testInfo) => {
    helpers = createTestHelpers(page, context, testInfo);
    helpers.logStep(`Starting navigation test on ${browserName}`);
  });

  test.describe('Authenticated Navigation', () => {
    test.beforeEach(async () => {
      await helpers.login(TEST_DATA.USERS.ADMIN);
    });

    test('should navigate to search page', async ({ page }) => {
      await page.goto('/search');
      await expect(page).toHaveURL(/.*search/);
      helpers.logStep('Search page loaded');
    });

    test('should navigate to chat page', async ({ page }) => {
      await page.goto('/chat');
      await expect(page).toHaveURL(/.*chat/);
      helpers.logStep('Chat page loaded');
    });

    test('should navigate to documents page', async ({ page }) => {
      await page.goto('/documents');
      await expect(page).toHaveURL(/.*documents/);
      helpers.logStep('Documents page loaded');
    });

    test('should navigate to analytics page', async ({ page }) => {
      await page.goto('/analytics');
      await expect(page).toHaveURL(/.*analytics/);
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
      helpers.logStep('Analytics page loaded');
    });

    test('should navigate to settings page', async ({ page }) => {
      await page.goto('/settings');
      await expect(page).toHaveURL(/.*settings/);
      helpers.logStep('Settings page loaded');
    });
  });

  test.describe('Auth Guards', () => {
    test('should redirect to login for protected routes', async ({ page }) => {
      const protectedRoutes = ['/dashboard', '/search', '/chat', '/documents', '/analytics', '/settings'];
      
      for (const route of protectedRoutes) {
        await page.goto(route);
        await page.waitForURL(/.*login/, { timeout: 10000 });
        await expect(page).toHaveURL(/.*login/);
        helpers.logStep(`Route ${route} correctly redirects to login`);
      }
    });
  });
});
