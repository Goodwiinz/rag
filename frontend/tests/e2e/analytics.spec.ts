import { test, expect } from '@playwright/test';

test.describe('Analytics Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.fill('[data-testid="email-input"]', 'test@example.com');
    await page.fill('[data-testid="password-input"]', 'password123');
    await page.click('[data-testid="login-button"]');
    await page.waitForURL('/dashboard');
  });

  test('displays RAG triad metrics', async ({ page }) => {
    await page.goto('/analytics/overview');

    // Wait for metrics to load
    await page.waitForSelector('[data-testid="metrics-overview"]');

    // Check for metric cards
    await expect(page.locator('[data-testid="answer-relevancy-card"]')).toBeVisible();
    await expect(page.locator('[data-testid="faithfulness-card"]')).toBeVisible();
    await expect(page.locator('[data-testid="contextual-relevancy-card"]')).toBeVisible();

    // Check metric values are displayed
    await expect(page.locator('[data-testid="answer-relevancy-value"]')).toBeVisible();
    await expect(page.locator('[data-testid="faithfulness-value"]')).toBeVisible();
    await expect(page.locator('[data-testid="contextual-relevancy-value"]')).toBeVisible();
  });

  test('allows date range filtering', async ({ page }) => {
    await page.goto('/analytics/overview');

    // Open date range picker
    await page.click('[data-testid="date-range-picker"]');

    // Select custom date range
    await page.click('[data-testid="custom-range"]');
    await page.fill('[data-testid="start-date"]', '2024-01-01');
    await page.fill('[data-testid="end-date"]', '2024-01-31');
    await page.click('[data-testid="apply-range"]');

    // Wait for data to refresh
    await page.waitForLoadState('networkidle');

    // Verify date range is applied
    await expect(page.locator('[data-testid="current-range"]')).toContainText('Jan 1, 2024 - Jan 31, 2024');
  });

  test('displays performance charts', async ({ page }) => {
    await page.goto('/analytics/performance');

    // Wait for charts to load
    await page.waitForSelector('[data-testid="performance-chart"]');

    // Check chart is rendered
    await expect(page.locator('[data-testid="line-chart"]')).toBeVisible();

    // Test chart interactions
    await page.hover('[data-testid="chart-point"]');
    await expect(page.locator('[data-testid="chart-tooltip"]')).toBeVisible();
  });

  test('supports keyboard navigation', async ({ page }) => {
    await page.goto('/analytics/overview');

    // Tab through metric cards
    await page.keyboard.press('Tab');
    await expect(page.locator('[data-testid="answer-relevancy-card"]:focus')).toBeVisible();

    await page.keyboard.press('Tab');
    await expect(page.locator('[data-testid="faithfulness-card"]:focus')).toBeVisible();

    // Activate card with Enter
    await page.keyboard.press('Enter');
    await expect(page.locator('[data-testid="metric-details-modal"]')).toBeVisible();
  });

  test('provides accessible data tables', async ({ page }) => {
    await page.goto('/analytics/performance');

    // Wait for table to load
    await page.waitForSelector('[data-testid="data-table"]');

    // Check table accessibility
    await expect(page.locator('table')).toHaveAttribute('role', 'table');
    await expect(page.locator('thead')).toBeVisible();
    await expect(page.locator('tbody')).toBeVisible();

    // Test table sorting
    await page.click('[data-testid="sort-header-latency"]');
    await expect(page.locator('[data-testid="sort-indicator"]')).toBeVisible();
  });

  test('handles real-time updates', async ({ page }) => {
    await page.goto('/analytics/overview');

    // Wait for initial load
    await page.waitForSelector('[data-testid="real-time-metrics"]');

    // Mock WebSocket message
    await page.evaluate(() => {
      // Simulate WebSocket message
      const event = new CustomEvent('real-time-update', {
        detail: {
          answer_relevancy: 88.5,
          faithfulness: 93.2,
          contextual_relevancy: 81.7,
        },
      });
      window.dispatchEvent(event);
    });

    // Check if metrics update
    await expect(page.locator('[data-testid="real-time-indicator"]')).toBeVisible();
  });

  test('exports data correctly', async ({ page }) => {
    await page.goto('/analytics/overview');

    // Click export button
    await page.click('[data-testid="export-button"]');

    // Select export format
    await page.click('[data-testid="export-format-csv"]');

    // Start download
    const downloadPromise = page.waitForEvent('download');
    await page.click('[data-testid="confirm-export"]');

    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/analytics.*\.csv$/);
  });

  test('supports different chart views', async ({ page }) => {
    await page.goto('/analytics/performance');

    // Switch to bar chart view
    await page.click('[data-testid="chart-view-bar"]');
    await expect(page.locator('[data-testid="bar-chart"]')).toBeVisible();

    // Switch to pie chart view
    await page.click('[data-testid="chart-view-pie"]');
    await expect(page.locator('[data-testid="pie-chart"]')).toBeVisible();

    // Switch back to line chart
    await page.click('[data-testid="chart-view-line"]');
    await expect(page.locator('[data-testid="line-chart"]')).toBeVisible();
  });

  test('displays loading states', async ({ page }) => {
    // Intercept API calls to simulate loading
    await page.route('/api/analytics/rag-triad*', route => {
      // Delay response
      setTimeout(() => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ metrics: { answer_relevancy: 85 } }),
      }), 2000);
    });

    await page.goto('/analytics/overview');

    // Check loading skeleton
    await expect(page.locator('[data-testid="loading-skeleton"]')).toBeVisible();

    // Wait for content to load
    await page.waitForSelector('[data-testid="metrics-overview"]', { timeout: 5000 });
    await expect(page.locator('[data-testid="loading-skeleton"]')).not.toBeVisible();
  });

  test('handles error states gracefully', async ({ page }) => {
    // Mock API error
    await page.route('/api/analytics/rag-triad*', route => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal server error' }),
      });
    });

    await page.goto('/analytics/overview');

    // Check error message
    await expect(page.locator('[data-testid="error-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="retry-button"]')).toBeVisible();

    // Test retry functionality
    await page.unroute('/api/analytics/rag-triad*');
    await page.click('[data-testid="retry-button"]');

    // Should load successfully after retry
    await expect(page.locator('[data-testid="metrics-overview"]')).toBeVisible();
  });

  test('maintains state during navigation', async ({ page }) => {
    await page.goto('/analytics/overview');

    // Apply filters
    await page.click('[data-testid="filter-modalities"]');
    await page.check('[data-testid="filter-text"]');
    await page.check('[data-testid="filter-image"]');
    await page.click('[data-testid="apply-filters"]');

    // Navigate to another page
    await page.goto('/evaluation');
    await page.waitForLoadState('networkidle');

    // Navigate back
    await page.goBack();

    // Filters should be maintained
    await expect(page.locator('[data-testid="active-filters"]')).toContainText('Text, Image');
  });
});

test.describe('Analytics Responsiveness', () => {
  test('displays correctly on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 }); // iPhone SE
    await page.goto('/analytics/overview');

    // Check mobile layout
    await expect(page.locator('[data-testid="mobile-navigation"]')).toBeVisible();
    await expect(page.locator('[data-testid="metrics-grid"]')).toHaveClass(/mobile/);

    // Check hamburger menu works
    await page.click('[data-testid="mobile-menu-button"]');
    await expect(page.locator('[data-testid="mobile-menu"]')).toBeVisible();
  });

  test('displays correctly on tablet', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 }); // iPad
    await page.goto('/analytics/overview');

    // Check tablet layout
    await expect(page.locator('[data-testid="sidebar"]')).toBeVisible();
    await expect(page.locator('[data-testid="metrics-grid"]')).toHaveClass(/tablet/);
  });

  test('displays correctly on desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 }); // Desktop
    await page.goto('/analytics/overview');

    // Check desktop layout
    await expect(page.locator('[data-testid="sidebar"]')).toBeVisible();
    await expect(page.locator('[data-testid="metrics-grid"]')).toHaveClass(/desktop/);
  });
});

test.describe('Analytics Performance', () => {
  test('loads within performance budget', async ({ page }) => {
    const startTime = Date.now();

    await page.goto('/analytics/overview');
    await page.waitForSelector('[data-testid="metrics-overview"]');

    const loadTime = Date.now() - startTime;
    expect(loadTime).toBeLessThan(3000); // 3 seconds budget
  });

  test('handles large datasets efficiently', async ({ page }) => {
    // Mock large dataset
    await page.route('/api/analytics/usage*', route => {
      const largeDataset = Array.from({ length: 10000 }, (_, i) => ({
        id: i,
        query: `Query ${i}`,
        timestamp: new Date().toISOString(),
        count: Math.floor(Math.random() * 100),
      }));

      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: largeDataset }),
      });
    });

    await page.goto('/analytics/usage');

    // Should handle virtual scrolling
    await expect(page.locator('[data-testid="virtual-table"]')).toBeVisible();

    // Check if virtual scrolling works
    await page.mouse.wheel(0, 1000);
    await page.waitForTimeout(100); // Allow for debounce

    // Should only render visible items
    const visibleRows = await page.locator('[data-testid="table-row"]').count();
    expect(visibleRows).toBeLessThan(50); // Should not render all 10,000 rows
  });
});