import { test, expect } from '@playwright/test';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

test.describe('Analytics Dashboard - Visual Regression Tests', () => {
  let helpers: ReturnType<typeof createTestHelpers>;

  test.beforeEach(async ({ page, context }, testInfo) => {
    helpers = createTestHelpers(page, context, testInfo);

    // Login and navigate to analytics dashboard
    await helpers.login(TEST_DATA.USERS.ADMIN);
    await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
    await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

    // Wait for all components to load
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000); // Additional wait for animations
  });

  test.describe('Dashboard Layout Visual Tests', () => {
    test('should match analytics dashboard layout snapshot', async ({ page }) => {
      helpers.logStep('Testing analytics dashboard layout visual regression');

      // Take full page screenshot
      await expect(page).toHaveScreenshot('analytics-dashboard-full-layout.png', {
        fullPage: true,
        animations: 'disabled',
        caret: 'hide',
      });

      // Test specific sections
      const headerSection = page.locator('[data-testid="dashboard-header"]');
      await expect(headerSection).toHaveScreenshot('dashboard-header.png', {
        animations: 'disabled',
      });

      const sidebarSection = page.locator('[data-testid="dashboard-sidebar"]');
      await expect(sidebarSection).toHaveScreenshot('dashboard-sidebar.png', {
        animations: 'disabled',
      });

      const mainContent = page.locator('[data-testid="dashboard-main-content"]');
      await expect(mainContent).toHaveScreenshot('dashboard-main-content.png', {
        animations: 'disabled',
      });

      helpers.logStep('Dashboard layout visual regression tests completed');
    });

    test('should match metric cards visual appearance', async ({ page }) => {
      helpers.logStep('Testing metric cards visual regression');

      // Wait for metric cards to be fully rendered
      await helpers.expectElementVisible('[data-testid="metric-card"]');
      await page.waitForTimeout(1000);

      // Test individual metric card
      const firstMetricCard = page.locator('[data-testid="metric-card"]').first();
      await expect(firstMetricCard).toHaveScreenshot('metric-card-default.png', {
        animations: 'disabled',
      });

      // Test metric card hover state
      await firstMetricCard.hover();
      await page.waitForTimeout(300);
      await expect(firstMetricCard).toHaveScreenshot('metric-card-hover.png', {
        animations: 'disabled',
      });

      // Test metric card with trend up
      const trendUpCard = page.locator('[data-testid="metric-card"]').filter({ hasText: '↑' }).first();
      if (await trendUpCard.count() > 0) {
        await expect(trendUpCard).toHaveScreenshot('metric-card-trend-up.png', {
          animations: 'disabled',
        });
      }

      // Test metric card with trend down
      const trendDownCard = page.locator('[data-testid="metric-card"]').filter({ hasText: '↓' }).first();
      if (await trendDownCard.count() > 0) {
        await expect(trendDownCard).toHaveScreenshot('metric-card-trend-down.png', {
          animations: 'disabled',
        });
      }

      helpers.logStep('Metric cards visual regression tests completed');
    });

    test('should match charts visual appearance', async ({ page }) => {
      helpers.logStep('Testing charts visual regression');

      // Wait for charts to render
      await helpers.expectElementVisible('[data-testid="chart"]');
      await page.waitForTimeout(2000);

      // Test line chart
      const lineChart = page.locator('[data-testid="chart"]').filter({ has: page.locator('svg') }).first();
      await expect(lineChart).toHaveScreenshot('line-chart-default.png', {
        animations: 'disabled',
      });

      // Test bar chart
      const barChart = page.locator('[data-testid="bar-chart"]');
      if (await barChart.count() > 0) {
        await expect(barChart).toHaveScreenshot('bar-chart-default.png', {
          animations: 'disabled',
        });
      }

      // Test pie chart
      const pieChart = page.locator('[data-testid="pie-chart"]');
      if (await pieChart.count() > 0) {
        await expect(pieChart).toHaveScreenshot('pie-chart-default.png', {
          animations: 'disabled',
        });
      }

      helpers.logStep('Charts visual regression tests completed');
    });

    test('should match data tables visual appearance', async ({ page }) => {
      helpers.logStep('Testing data tables visual regression');

      // Navigate to data table view if available
      const dataTableTab = page.locator('[data-testid="data-table-tab"]');
      if (await dataTableTab.count() > 0) {
        await dataTableTab.click();
        await helpers.expectElementVisible('[data-testid="data-table"]');
        await page.waitForTimeout(1000);

        // Test data table
        const dataTable = page.locator('[data-testid="data-table"]');
        await expect(dataTable).toHaveScreenshot('data-table-default.png', {
          animations: 'disabled',
        });

        // Test table header
        const tableHeader = page.locator('[data-testid="table-header"]');
        await expect(tableHeader).toHaveScreenshot('table-header.png', {
          animations: 'disabled',
        });

        // Test table rows
        const tableRows = page.locator('[data-testid="table-row"]');
        if (await tableRows.count() > 0) {
          await expect(tableRows.first()).toHaveScreenshot('table-row-default.png', {
            animations: 'disabled',
          });

          // Test row hover
          await tableRows.first().hover();
          await page.waitForTimeout(300);
          await expect(tableRows.first()).toHaveScreenshot('table-row-hover.png', {
            animations: 'disabled',
          });

          // Test row selection
          await tableRows.first().click();
          await page.waitForTimeout(300);
          await expect(tableRows.first()).toHaveScreenshot('table-row-selected.png', {
            animations: 'disabled',
          });
        }
      }

      helpers.logStep('Data tables visual regression tests completed');
    });
  });

  test.describe('Component State Visual Tests', () => {
    test('should match loading states visual appearance', async ({ page }) => {
      helpers.logStep('Testing loading states visual regression');

      // Trigger loading state by refreshing
      await page.reload();

      // Test skeleton loading
      await helpers.expectElementVisible('[data-testid="loading-skeleton"]');
      await expect(page.locator('[data-testid="loading-skeleton"]')).toHaveScreenshot('loading-skeleton.png', {
        animations: 'disabled',
      });

      // Test spinner
      await helpers.expectElementVisible('[data-testid="loading-spinner"]');
      await expect(page.locator('[data-testid="loading-spinner"]')).toHaveScreenshot('loading-spinner.png', {
        animations: 'disabled',
      });

      helpers.logStep('Loading states visual regression tests completed');
    });

    test('should match empty states visual appearance', async ({ page }) => {
      helpers.logStep('Testing empty states visual regression');

      // Navigate to a section that might have empty state
      await helpers.waitAndClick('[data-testid="filter-reset-button"]');
      await page.waitForTimeout(1000);

      // Check for empty state
      const emptyState = page.locator('[data-testid="empty-state"]');
      if (await emptyState.count() > 0) {
        await expect(emptyState).toHaveScreenshot('empty-state.png', {
          animations: 'disabled',
        });
      }

      helpers.logStep('Empty states visual regression tests completed');
    });

    test('should match error states visual appearance', async ({ page }) => {
      helpers.logStep('Testing error states visual regression');

      // Mock an API error to trigger error state
      await page.route('**/api/v1/analytics/**', route => {
        route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Internal Server Error' }),
        });
      });

      // Trigger API call
      await helpers.waitAndClick('[data-testid="refresh-button"]');
      await page.waitForTimeout(2000);

      // Test error state
      const errorState = page.locator('[data-testid="error-state"]');
      if (await errorState.count() > 0) {
        await expect(errorState).toHaveScreenshot('error-state.png', {
          animations: 'disabled',
        });
      }

      // Restore normal behavior
      await page.unroute('**/api/v1/analytics/**');

      helpers.logStep('Error states visual regression tests completed');
    });

    test('should match interactive states visual appearance', async ({ page }) => {
      helpers.logStep('Testing interactive states visual regression');

      // Test button states
      const primaryButton = page.locator('[data-testid="primary-button"]').first();
      if (await primaryButton.count() > 0) {
        await expect(primaryButton).toHaveScreenshot('button-default.png', {
          animations: 'disabled',
        });

        await primaryButton.hover();
        await page.waitForTimeout(300);
        await expect(primaryButton).toHaveScreenshot('button-hover.png', {
          animations: 'disabled',
        });

        await primaryButton.focus();
        await page.waitForTimeout(300);
        await expect(primaryButton).toHaveScreenshot('button-focus.png', {
          animations: 'disabled',
        });
      }

      // Test filter states
      const filterDropdown = page.locator('[data-testid="filter-dropdown"]');
      if (await filterDropdown.count() > 0) {
        // Default state
        await expect(filterDropdown).toHaveScreenshot('filter-dropdown-closed.png', {
          animations: 'disabled',
        });

        // Open state
        await filterDropdown.click();
        await page.waitForTimeout(300);
        await expect(filterDropdown).toHaveScreenshot('filter-dropdown-open.png', {
          animations: 'disabled',
        });
      }

      helpers.logStep('Interactive states visual regression tests completed');
    });
  });

  test.describe('Responsive Design Visual Tests', () => {
    test('should match desktop layout visual appearance', async ({ page }) => {
      helpers.logStep('Testing desktop layout visual regression');

      // Set desktop viewport
      await page.setViewportSize({ width: 1280, height: 720 });
      await page.waitForTimeout(1000);

      await expect(page).toHaveScreenshot('analytics-dashboard-desktop.png', {
        fullPage: true,
        animations: 'disabled',
      });

      helpers.logStep('Desktop layout visual regression test completed');
    });

    test('should match tablet layout visual appearance', async ({ page }) => {
      helpers.logStep('Testing tablet layout visual regression');

      // Set tablet viewport
      await page.setViewportSize({ width: 768, height: 1024 });
      await page.waitForTimeout(1000);

      await expect(page).toHaveScreenshot('analytics-dashboard-tablet.png', {
        fullPage: true,
        animations: 'disabled',
      });

      helpers.logStep('Tablet layout visual regression test completed');
    });

    test('should match mobile layout visual appearance', async ({ page }) => {
      helpers.logStep('Testing mobile layout visual regression');

      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      await page.waitForTimeout(1000);

      await expect(page).toHaveScreenshot('analytics-dashboard-mobile.png', {
        fullPage: true,
        animations: 'disabled',
      });

      // Test mobile navigation
      const mobileMenuButton = page.locator('[data-testid="mobile-menu-button"]');
      if (await mobileMenuButton.count() > 0) {
        await mobileMenuButton.click();
        await page.waitForTimeout(500);
        await expect(page.locator('[data-testid="mobile-nav-menu"]')).toHaveScreenshot('mobile-nav-menu-open.png', {
          animations: 'disabled',
        });
      }

      helpers.logStep('Mobile layout visual regression test completed');
    });

    test('should match widescreen layout visual appearance', async ({ page }) => {
      helpers.logStep('Testing widescreen layout visual regression');

      // Set widescreen viewport
      await page.setViewportSize({ width: 1920, height: 1080 });
      await page.waitForTimeout(1000);

      await expect(page).toHaveScreenshot('analytics-dashboard-widescreen.png', {
        fullPage: true,
        animations: 'disabled',
      });

      helpers.logStep('Widescreen layout visual regression test completed');
    });
  });

  test.describe('Theme and Style Visual Tests', () => {
    test('should match light theme visual appearance', async ({ page }) => {
      helpers.logStep('Testing light theme visual regression');

      // Ensure light theme is active
      await page.emulateMedia({ colorScheme: 'light' });
      await page.waitForTimeout(1000);

      await expect(page).toHaveScreenshot('analytics-dashboard-light-theme.png', {
        fullPage: true,
        animations: 'disabled',
      });

      helpers.logStep('Light theme visual regression test completed');
    });

    test('should match dark theme visual appearance', async ({ page }) => {
      helpers.logStep('Testing dark theme visual regression');

      // Switch to dark theme if available
      const themeToggle = page.locator('[data-testid="theme-toggle"]');
      if (await themeToggle.count() > 0) {
        await themeToggle.click();
        await page.waitForTimeout(1000);

        await expect(page).toHaveScreenshot('analytics-dashboard-dark-theme.png', {
          fullPage: true,
          animations: 'disabled',
        });
      } else {
        // Emulate dark theme if toggle not available
        await page.emulateMedia({ colorScheme: 'dark' });
        await page.waitForTimeout(1000);

        await expect(page).toHaveScreenshot('analytics-dashboard-dark-theme.png', {
          fullPage: true,
          animations: 'disabled',
        });
      }

      helpers.logStep('Dark theme visual regression test completed');
    });

    test('should match high contrast mode visual appearance', async ({ page }) => {
      helpers.logStep('Testing high contrast mode visual regression');

      // Emulate high contrast preferences
      await page.emulateMedia({
        colorScheme: 'light',
        forcedColors: 'active',
      });
      await page.waitForTimeout(1000);

      await expect(page).toHaveScreenshot('analytics-dashboard-high-contrast.png', {
        fullPage: true,
        animations: 'disabled',
      });

      helpers.logStep('High contrast mode visual regression test completed');
    });

    test('should match reduced motion visual appearance', async ({ page }) => {
      helpers.logStep('Testing reduced motion visual regression');

      // Emulate reduced motion preferences
      await page.emulateMedia({
        reducedMotion: 'reduce',
      });
      await page.waitForTimeout(1000);

      await expect(page).toHaveScreenshot('analytics-dashboard-reduced-motion.png', {
        fullPage: true,
        animations: 'disabled',
      });

      helpers.logStep('Reduced motion visual regression test completed');
    });
  });

  test.describe('Data Visualization Visual Tests', () => {
    test('should match chart color schemes', async ({ page }) => {
      helpers.logStep('Testing chart color scheme visual regression');

      // Wait for charts to render
      await helpers.expectElementVisible('[data-testid="chart"]');
      await page.waitForTimeout(2000);

      // Test chart with default colors
      const chart = page.locator('[data-testid="chart"]').first();
      await expect(chart).toHaveScreenshot('chart-default-colors.png', {
        animations: 'disabled',
      });

      // Test chart color variations if available
      const colorSchemeButton = page.locator('[data-testid="chart-color-scheme"]');
      if (await colorSchemeButton.count() > 0) {
        await colorSchemeButton.click();
        await page.waitForTimeout(500);

        const colorOption1 = page.locator('[data-testid="color-scheme-option-1"]');
        if (await colorOption1.count() > 0) {
          await colorOption1.click();
          await page.waitForTimeout(1000);
          await expect(chart).toHaveScreenshot('chart-color-scheme-1.png', {
            animations: 'disabled',
          });
        }
      }

      helpers.logStep('Chart color scheme visual regression tests completed');
    });

    test('should match graph visualization appearance', async ({ page }) => {
      helpers.logStep('Testing graph visualization visual regression');

      // Navigate to graph section if available
      const graphTab = page.locator('[data-testid="graph-tab"]');
      if (await graphTab.count() > 0) {
        await graphTab.click();
        await helpers.expectElementVisible('[data-testid="graph-viewer"]');
        await page.waitForTimeout(2000);

        // Test graph visualization
        const graphViewer = page.locator('[data-testid="graph-viewer"]');
        await expect(graphViewer).toHaveScreenshot('graph-visualization-default.png', {
          animations: 'disabled',
        });

        // Test different layouts if available
        const layoutSelector = page.locator('[data-testid="layout-selector"]');
        if (await layoutSelector.count() > 0) {
          await layoutSelector.click();

          const forceLayout = page.locator('[data-testid="layout-force"]');
          if (await forceLayout.count() > 0) {
            await forceLayout.click();
            await page.waitForTimeout(1500);
            await expect(graphViewer).toHaveScreenshot('graph-layout-force.png', {
              animations: 'disabled',
            });
          }

          const circularLayout = page.locator('[data-testid="layout-circular"]');
          if (await circularLayout.count() > 0) {
            await circularLayout.click();
            await page.waitForTimeout(1500);
            await expect(graphViewer).toHaveScreenshot('graph-layout-circular.png', {
              animations: 'disabled',
            });
          }
        }
      }

      helpers.logStep('Graph visualization visual regression tests completed');
    });
  });

  test.describe('Form and Input Visual Tests', () => {
    test('should match form input visual states', async ({ page }) => {
      helpers.logStep('Testing form input visual regression');

      // Test filter form inputs
      const filterInput = page.locator('[data-testid="filter-input"]');
      if (await filterInput.count() > 0) {
        // Default state
        await expect(filterInput).toHaveScreenshot('input-default.png', {
          animations: 'disabled',
        });

        // Focus state
        await filterInput.focus();
        await page.waitForTimeout(300);
        await expect(filterInput).toHaveScreenshot('input-focus.png', {
          animations: 'disabled',
        });

        // Filled state
        await filterInput.fill('test input');
        await page.waitForTimeout(300);
        await expect(filterInput).toHaveScreenshot('input-filled.png', {
          animations: 'disabled',
        });
      }

      // Test dropdown/select inputs
      const selectInput = page.locator('[data-testid="select-input"]');
      if (await selectInput.count() > 0) {
        // Closed state
        await expect(selectInput).toHaveScreenshot('select-closed.png', {
          animations: 'disabled',
        });

        // Open state
        await selectInput.click();
        await page.waitForTimeout(500);
        await expect(selectInput).toHaveScreenshot('select-open.png', {
          animations: 'disabled',
        });
      }

      helpers.logStep('Form input visual regression tests completed');
    });

    test('should match notification and message visual appearance', async ({ page }) => {
      helpers.logStep('Testing notification visual regression');

      // Test success notification
      await page.evaluate(() => {
        const notification = document.createElement('div');
        notification.setAttribute('data-testid', 'success-notification');
        notification.textContent = 'Operation completed successfully';
        notification.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999;';
        document.body.appendChild(notification);
      });

      await expect(page.locator('[data-testid="success-notification"]')).toHaveScreenshot('notification-success.png', {
        animations: 'disabled',
      });

      // Test warning notification
      await page.evaluate(() => {
        const notification = document.createElement('div');
        notification.setAttribute('data-testid', 'warning-notification');
        notification.textContent = 'Warning: This is a warning message';
        notification.style.cssText = 'position: fixed; top: 80px; right: 20px; z-index: 9999;';
        document.body.appendChild(notification);
      });

      await expect(page.locator('[data-testid="warning-notification"]')).toHaveScreenshot('notification-warning.png', {
        animations: 'disabled',
      });

      // Test error notification
      await page.evaluate(() => {
        const notification = document.createElement('div');
        notification.setAttribute('data-testid', 'error-notification');
        notification.textContent = 'Error: An error occurred';
        notification.style.cssText = 'position: fixed; top: 140px; right: 20px; z-index: 9999;';
        document.body.appendChild(notification);
      });

      await expect(page.locator('[data-testid="error-notification"]')).toHaveScreenshot('notification-error.png', {
        animations: 'disabled',
      });

      helpers.logStep('Notification visual regression tests completed');
    });
  });
});