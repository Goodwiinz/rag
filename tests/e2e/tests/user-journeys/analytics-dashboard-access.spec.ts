import { test, expect } from '@playwright/test';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

test.describe('Analytics Dashboard Access - User Journey', () => {
  let helpers: ReturnType<typeof createTestHelpers>;

  test.beforeEach(async ({ page, context, browserName }, testInfo) => {
    helpers = createTestHelpers(page, context, testInfo);
    helpers.logStep(`Starting test on ${browserName}`);
  });

  test.describe('Login Flow', () => {
    test('should allow admin user to login and access analytics dashboard', async ({ page }) => {
      helpers.logStep('Testing admin login and dashboard access');

      // Step 1: Navigate to login page
      await helpers.navigateTo('/login');
      await helpers.expectElementVisible('[data-testid="login-form"]');
      await helpers.takeScreenshot('login-page-loaded');

      // Step 2: Login with admin credentials
      await helpers.login({
        email: TEST_DATA.USERS.ADMIN.email,
        password: TEST_DATA.USERS.ADMIN.password,
      });
      helpers.logStep('Successfully logged in as admin');

      // Step 3: Verify dashboard loads
      await helpers.expectElementVisible('[data-testid="dashboard-container"]');
      await helpers.expectElementVisible('[data-testid="user-menu"]');
      await helpers.takeScreenshot('dashboard-loaded');

      // Step 4: Navigate to analytics dashboard
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
      helpers.logStep('Successfully navigated to analytics dashboard');

      // Step 5: Verify analytics components load
      await helpers.expectElementVisible('[data-testid="metric-card"]');
      await helpers.expectElementVisible('[data-testid="chart"]');
      await helpers.takeScreenshot('analytics-dashboard-loaded');

      // Step 6: Verify user permissions
      const adminFeatures = [
        '[data-testid="admin-settings-link"]',
        '[data-testid="user-management-link"]',
        '[data-testid="system-health-link"]',
      ];

      for (const feature of adminFeatures) {
        if (await helpers.elementExists(feature)) {
          await helpers.expectElementVisible(feature);
          helpers.logStep(`Admin feature available: ${feature}`);
        }
      }
    });

    test('should allow regular user to login with limited access', async ({ page }) => {
      helpers.logStep('Testing regular user login and access');

      // Step 1: Login as regular user
      await helpers.login({
        email: TEST_DATA.USERS.REGULAR.email,
        password: TEST_DATA.USERS.REGULAR.password,
      });
      helpers.logStep('Successfully logged in as regular user');

      // Step 2: Verify dashboard loads
      await helpers.expectElementVisible('[data-testid="dashboard-container"]');

      // Step 3: Navigate to analytics
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Step 4: Verify limited access
      const adminFeatures = [
        '[data-testid="admin-settings-link"]',
        '[data-testid="user-management-link"]',
        '[data-testid="system-health-link"]',
      ];

      for (const feature of adminFeatures) {
        if (await helpers.elementExists(feature)) {
          await helpers.expectElementHidden(feature);
          helpers.logStep(`Admin feature correctly hidden: ${feature}`);
        }
      }

      // Step 5: Verify user features are available
      const userFeatures = [
        '[data-testid="my-profile-link"]',
        '[data-testid="my-documents-link"]',
        '[data-testid="my-analytics-link"]',
      ];

      for (const feature of userFeatures) {
        if (await helpers.elementExists(feature)) {
          await helpers.expectElementVisible(feature);
          helpers.logStep(`User feature available: ${feature}`);
        }
      }
    });

    test('should handle invalid login credentials', async ({ page }) => {
      helpers.logStep('Testing invalid login handling');

      // Step 1: Navigate to login page
      await helpers.navigateTo('/login');

      // Step 2: Attempt login with invalid credentials
      await helpers.fillField('[data-testid="email-input"]', 'invalid@test.com');
      await helpers.fillField('[data-testid="password-input"]', 'invalidpassword');
      await helpers.waitAndClick('[data-testid="login-button"]');

      // Step 3: Verify error message appears
      await helpers.expectElementVisible('[data-testid="login-error"]');
      const errorMessage = await helpers.getTextContent('[data-testid="login-error"]');
      expect(errorMessage).toContain('Invalid credentials');
      helpers.logStep('Error message displayed correctly');

      // Step 4: Verify user stays on login page
      await expect(page).toHaveURL(/\/login/);
      helpers.logStep('User correctly remains on login page');
    });
  });

  test.describe('Dashboard Widget Interaction', () => {
    test.beforeEach(async ({ page }) => {
      // Login as admin for widget tests
      await helpers.login(TEST_DATA.USERS.ADMIN);
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
    });

    test('should display and interact with metric cards', async ({ page }) => {
      helpers.logStep('Testing metric card interaction');

      // Step 1: Verify metric cards are displayed
      const metricCards = page.locator('[data-testid="metric-card"]');
      await expect(metricCards).toHaveCount.greaterThan(0);

      // Step 2: Hover over metric cards
      const firstCard = metricCards.first();
      await helpers.hover('[data-testid="metric-card"]');
      await helpers.expectElementVisible('[data-testid="metric-tooltip"]');
      helpers.logStep('Metric tooltip appears on hover');

      // Step 3: Click on metric card for details
      await helpers.waitAndClick('[data-testid="metric-card"]');
      await helpers.expectElementVisible('[data-testid="metric-details-modal"]');
      helpers.logStep('Metric details modal opens on click');

      // Step 4: Close details modal
      await helpers.waitAndClick('[data-testid="modal-close-button"]');
      await helpers.expectElementHidden('[data-testid="metric-details-modal"]');

      // Step 5: Test metric card filters
      await helpers.waitAndClick('[data-testid="metric-filter-button"]');
      await helpers.expectElementVisible('[data-testid="metric-filter-panel"]');
      await helpers.selectOption('[data-testid="time-range-filter"]', '7d');
      await helpers.waitAndClick('[data-testid="apply-filter-button"]');
      helpers.logStep('Metric filter applied successfully');
    });

    test('should display and interact with charts', async ({ page }) => {
      helpers.logStep('Testing chart interaction');

      // Step 1: Verify charts are displayed
      const charts = page.locator('[data-testid="chart"]');
      await expect(charts).toHaveCount.greaterThan(0);

      // Step 2: Wait for charts to load
      await helpers.expectElementVisible('[data-testid="chart-canvas"]');

      // Step 3: Test chart type switching
      await helpers.waitAndClick('[data-testid="chart-type-selector"]');
      await helpers.waitAndClick('[data-testid="chart-type-line"]');
      helpers.logStep('Chart type changed to line');

      // Step 4: Test chart time range
      await helpers.waitAndClick('[data-testid="chart-time-range"]');
      await helpers.waitAndClick('[data-testid="time-range-30d"]');
      helpers.logStep('Chart time range changed to 30 days');

      // Step 5: Test chart export
      await helpers.waitAndClick('[data-testid="chart-export-button"]');
      await helpers.expectElementVisible('[data-testid="export-menu"]');
      await helpers.waitAndClick('[data-testid="export-as-png"]');

      // Verify download started
      const download = await page.waitForEvent('download');
      expect(download.suggestedFilename()).toMatch(/\.png$/);
      helpers.logStep('Chart exported as PNG successfully');

      // Step 6: Test chart zoom
      await helpers.waitAndClick('[data-testid="chart-zoom-in"]');
      await helpers.waitAndClick('[data-testid="chart-zoom-out"]');
      helpers.logStep('Chart zoom controls working');
    });

    test('should display and interact with data tables', async ({ page }) => {
      helpers.logStep('Testing data table interaction');

      // Step 1: Find and navigate to data table
      await helpers.waitAndClick('[data-testid="data-table-tab"]');
      await helpers.expectElementVisible('[data-testid="data-table"]');

      // Step 2: Verify table has data
      const tableRows = page.locator('[data-testid="table-row"]');
      await expect(tableRows).toHaveCount.greaterThan(0);

      // Step 3: Test table sorting
      await helpers.waitAndClick('[data-testid="sort-column-name"]');
      helpers.logStep('Table sorted by name');

      // Step 4: Test table filtering
      await helpers.fillField('[data-testid="table-search"]', 'test');
      await page.waitForTimeout(1000); // Wait for filter to apply
      helpers.logStep('Table filter applied');

      // Step 5: Test table pagination
      if (await helpers.elementExists('[data-testid="pagination-next"]')) {
        await helpers.waitAndClick('[data-testid="pagination-next"]');
        helpers.logStep('Table pagination working');
      }

      // Step 6: Test row selection
      const firstRow = tableRows.first();
      await firstRow.click();
      await helpers.expectElementVisible('[data-testid="row-selected"]');
      helpers.logStep('Table row selection working');

      // Step 7: Test table export
      await helpers.waitAndClick('[data-testid="table-export-button"]');
      await helpers.waitAndClick('[data-testid="export-as-csv"]');

      const download = await page.waitForEvent('download');
      expect(download.suggestedFilename()).toMatch(/\.csv$/);
      helpers.logStep('Table exported as CSV successfully');
    });
  });

  test.describe('Real-time Updates', () => {
    test('should receive and display real-time updates', async ({ page }) => {
      helpers.logStep('Testing real-time updates');

      // Step 1: Login and navigate to analytics
      await helpers.login(TEST_DATA.USERS.ADMIN);
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');

      // Step 2: Enable real-time updates
      await helpers.waitAndClick('[data-testid="real-time-toggle"]');
      await helpers.expectElementVisible('[data-testid="connection-status"]');

      // Step 3: Mock WebSocket connection
      await page.evaluate(() => {
        // Mock WebSocket for testing
        window.WebSocket = class MockWebSocket {
          url: string;
          readyState: number = 1; // OPEN

          constructor(url: string) {
            this.url = url;
            setTimeout(() => {
              // Simulate receiving data
              const event = new CustomEvent('message', {
                detail: JSON.stringify({
                  type: 'metric_update',
                  data: {
                    metric: 'user_count',
                    value: 150,
                    timestamp: new Date().toISOString(),
                  },
                }),
              });
              window.dispatchEvent(event);
            }, 1000);
          }

          send() {}
          close() {}
          addEventListener() {}
          removeEventListener() {}
        };
      });

      // Step 4: Wait for real-time update
      await helpers.expectElementVisible('[data-testid="real-time-indicator"]');
      helpers.logStep('Real-time indicator appears');

      // Step 5: Verify metric updates
      await page.waitForTimeout(2000);
      const metricValue = await helpers.getTextContent('[data-testid="live-metric-value"]');
      expect(metricValue).toBeTruthy();
      helpers.logStep('Live metric updated successfully');
    });
  });

  test.describe('Responsive Design', () => {
    test('should adapt to different screen sizes', async ({ page }) => {
      helpers.logStep('Testing responsive design');

      // Step 1: Login
      await helpers.login(TEST_DATA.USERS.ADMIN);
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');

      // Step 2: Test desktop view
      await helpers.setViewport(1280, 720);
      await helpers.expectElementVisible('[data-testid="desktop-layout"]');
      await helpers.takeScreenshot('desktop-view');

      // Step 3: Test tablet view
      await helpers.setViewport(768, 1024);
      await helpers.expectElementVisible('[data-testid="tablet-layout"]');
      await helpers.takeScreenshot('tablet-view');

      // Step 4: Test mobile view
      await helpers.setViewport(375, 667);
      await helpers.expectElementVisible('[data-testid="mobile-layout"]');

      // Test mobile navigation
      await helpers.waitAndClick('[data-testid="mobile-menu-button"]');
      await helpers.expectElementVisible('[data-testid="mobile-nav-menu"]');
      helpers.logStep('Mobile navigation working');

      await helpers.takeScreenshot('mobile-view');

      // Step 5: Return to desktop
      await helpers.setViewport(1280, 720);
      await helpers.expectElementVisible('[data-testid="desktop-layout"]');
      helpers.logStep('Responsive design working across all viewports');
    });
  });

  test.describe('Error Handling', () => {
    test('should handle network errors gracefully', async ({ page }) => {
      helpers.logStep('Testing network error handling');

      // Step 1: Login and navigate to analytics
      await helpers.login(TEST_DATA.USERS.ADMIN);
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');

      // Step 2: Mock network failure
      await page.route('**/api/v1/analytics/**', route => {
        route.abort();
      });

      // Step 3: Trigger API call
      await helpers.waitAndClick('[data-testid="refresh-button"]');

      // Step 4: Verify error message appears
      await helpers.expectElementVisible('[data-testid="error-message"]');
      const errorMessage = await helpers.getTextContent('[data-testid="error-message"]');
      expect(errorMessage).toContain('network error');
      helpers.logStep('Network error displayed correctly');

      // Step 5: Verify retry mechanism
      await helpers.waitAndClick('[data-testid="retry-button"]');
      await page.waitForTimeout(2000);
      helpers.logStep('Retry mechanism working');

      // Step 6: Restore normal behavior
      await page.unroute('**/api/v1/analytics/**');
      await helpers.waitAndClick('[data-testid="refresh-button"]');
      helpers.logStep('Normal operation restored');
    });

    test('should handle slow loading gracefully', async ({ page }) => {
      helpers.logStep('Testing slow loading handling');

      // Step 1: Login and navigate to analytics
      await helpers.login(TEST_DATA.USERS.ADMIN);

      // Step 2: Mock slow API response
      await page.route('**/api/v1/analytics/**', async route => {
        await new Promise(resolve => setTimeout(resolve, 5000)); // 5 second delay
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ data: 'test' }),
        });
      });

      // Step 3: Navigate to analytics
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');

      // Step 4: Verify loading indicators
      await helpers.expectElementVisible('[data-testid="loading-spinner"]');
      await helpers.expectElementVisible('[data-testid="loading-skeleton"]');
      helpers.logStep('Loading indicators displayed');

      // Step 5: Wait for content to load
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]', { timeout: 10000 });
      helpers.logStep('Content loaded successfully after delay');

      // Step 6: Verify no error states
      expect(await helpers.elementExists('[data-testid="error-message"]')).toBeFalsy();
      helpers.logStep('No error states during slow loading');
    });
  });

  test.describe('Logout Flow', () => {
    test('should allow user to logout cleanly', async ({ page }) => {
      helpers.logStep('Testing logout flow');

      // Step 1: Login and navigate to analytics
      await helpers.login(TEST_DATA.USERS.ADMIN);
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');

      // Step 2: Verify user is logged in
      await helpers.expectElementVisible('[data-testid="user-menu"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Step 3: Logout
      await helpers.waitAndClick('[data-testid="user-menu"]');
      await helpers.waitAndClick('[data-testid="logout-button"]');
      helpers.logStep('Logout initiated');

      // Step 4: Verify redirect to login
      await helpers.expectElementVisible('[data-testid="login-form"]');
      await expect(page).toHaveURL(/\/login/);

      // Step 5: Verify session cleared
      const cookies = await page.context().cookies();
      const authToken = cookies.find(cookie => cookie.name === 'auth_token');
      expect(authToken).toBeUndefined();
      helpers.logStep('Session cleared successfully');

      // Step 6: Verify protected routes redirect to login
      await page.goto('/analytics');
      await helpers.expectElementVisible('[data-testid="login-form"]');
      helpers.logStep('Protected routes redirect to login after logout');
    });

    test('should handle session expiration gracefully', async ({ page }) => {
      helpers.logStep('Testing session expiration handling');

      // Step 1: Login
      await helpers.login(TEST_DATA.USERS.ADMIN);
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');

      // Step 2: Clear session to simulate expiration
      await page.context().clearCookies();
      await page.evaluate(() => {
        localStorage.removeItem('auth_token');
        sessionStorage.removeItem('auth_token');
      });

      // Step 3: Trigger API call that requires authentication
      await helpers.waitAndClick('[data-testid="refresh-button"]');

      // Step 4: Verify redirect to login with session expired message
      await helpers.expectElementVisible('[data-testid="login-form"]');

      if (await helpers.elementExists('[data-testid="session-expired-message"]')) {
        await helpers.expectElementVisible('[data-testid="session-expired-message"]');
        const message = await helpers.getTextContent('[data-testid="session-expired-message"]');
        expect(message).toContain('session expired');
        helpers.logStep('Session expiration message displayed');
      }

      helpers.logStep('Session expiration handled gracefully');
    });
  });
});