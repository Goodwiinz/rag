import { test, expect } from '@playwright/test';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

test.describe('Dashboard Performance Tests', () => {
  let helpers: ReturnType<typeof createTestHelpers>;

  test.beforeEach(async ({ page, context }, testInfo) => {
    helpers = createTestHelpers(page, context, testInfo);
    await helpers.login(TEST_DATA.USERS.ADMIN);
  });

  test.describe('Page Load Performance', () => {
    test('should load analytics dashboard within performance thresholds', async ({ page }) => {
      helpers.logStep('Testing analytics dashboard load performance');

      // Start performance monitoring
      const navigationStart = await page.evaluate(() => performance.now());

      // Navigate to analytics dashboard
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Wait for all critical content to load
      await page.waitForLoadState('networkidle');
      await helpers.expectElementVisible('[data-testid="metric-card"]');
      await helpers.expectElementVisible('[data-testid="chart"]');

      const navigationEnd = await page.evaluate(() => performance.now());
      const loadTime = navigationEnd - navigationStart;

      // Performance assertions
      expect(loadTime).toBeLessThan(3000); // Should load in under 3 seconds
      helpers.logStep(`Dashboard loaded in ${loadTime.toFixed(2)}ms`);

      // Get detailed performance metrics
      const metrics = await page.evaluate(() => {
        const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
        const paint = performance.getEntriesByType('paint');

        return {
          domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
          loadComplete: navigation.loadEventEnd - navigation.loadEventStart,
          firstPaint: paint.find(p => p.name === 'first-paint')?.startTime || 0,
          firstContentfulPaint: paint.find(p => p.name === 'first-contentful-paint')?.startTime || 0,
          firstMeaningfulPaint: navigation.domContentLoadedEventEnd - navigation.navigationStart,
          timeToInteractive: navigation.loadEventEnd - navigation.navigationStart,
        };
      });

      // Log performance metrics
      Object.entries(metrics).forEach(([metric, value]) => {
        helpers.logStep(`${metric}: ${value.toFixed(2)}ms`);
      });

      // Performance thresholds
      expect(metrics.firstContentfulPaint).toBeLessThan(1500); // 1.5s for FCP
      expect(metrics.domContentLoaded).toBeLessThan(2000); // 2s for DOM ready
      expect(metrics.timeToInteractive).toBeLessThan(5000); // 5s for TTI

      // Take performance screenshot
      await helpers.takeScreenshot('performance-dashboard-loaded');
    });

    test('should handle large datasets efficiently', async ({ page }) => {
      helpers.logStep('Testing performance with large datasets');

      // Mock large dataset response
      await page.route('**/api/v1/analytics/**', async route => {
        const largeData = {
          metrics: Array.from({ length: 1000 }, (_, i) => ({
            id: `metric-${i}`,
            name: `Metric ${i}`,
            value: Math.random() * 1000,
            timestamp: new Date().toISOString(),
          })),
          charts: Array.from({ length: 50 }, (_, i) => ({
            id: `chart-${i}`,
            type: 'line',
            data: Array.from({ length: 500 }, (_, j) => ({
              x: j,
              y: Math.random() * 100,
            })),
          })),
        };

        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(largeData),
        });
      });

      const startTime = Date.now();

      // Navigate to analytics dashboard
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Wait for data to render
      await helpers.expectElementVisible('[data-testid="metric-card"]');
      await helpers.expectElementVisible('[data-testid="chart"]');

      const renderTime = Date.now() - startTime;

      // Should handle large datasets efficiently
      expect(renderTime).toBeLessThan(5000); // 5 seconds max for large datasets
      helpers.logStep(`Large dataset rendered in ${renderTime}ms`);

      // Test interaction performance
      const interactionStart = Date.now();
      await helpers.waitAndClick('[data-testid="metric-card"]');
      const interactionTime = Date.now() - interactionStart;

      expect(interactionTime).toBeLessThan(1000); // Interactions should be fast
      helpers.logStep(`Interaction completed in ${interactionTime}ms`);

      // Restore normal API behavior
      await page.unroute('**/api/v1/analytics/**');
    });

    test('should maintain performance during rapid navigation', async ({ page }) => {
      helpers.logStep('Testing performance during rapid navigation');

      const navigationTimes: number[] = [];

      // Perform rapid navigation between pages
      const pages = [
        '[data-testid="analytics-nav-link"]',
        '[data-testid="graph-nav-link"]',
        '[data-testid="documents-nav-link"]',
        '[data-testid="dashboard-nav-link"]',
      ];

      for (let i = 0; i < 3; i++) {
        for (const pageSelector of pages) {
          const startTime = Date.now();

          try {
            await helpers.waitAndClick(pageSelector);
            await page.waitForLoadState('networkidle');
            await page.waitForTimeout(500); // Brief pause

            const navigationTime = Date.now() - startTime;
            navigationTimes.push(navigationTime);
          } catch (error) {
            // Skip if navigation target doesn't exist
            continue;
          }
        }
      }

      // Analyze navigation performance
      if (navigationTimes.length > 0) {
        const avgTime = navigationTimes.reduce((a, b) => a + b, 0) / navigationTimes.length;
        const maxTime = Math.max(...navigationTimes);

        helpers.logStep(`Average navigation time: ${avgTime.toFixed(2)}ms`);
        helpers.logStep(`Max navigation time: ${maxTime.toFixed(2)}ms`);

        // Navigation should be consistently fast
        expect(avgTime).toBeLessThan(2000); // 2 seconds average
        expect(maxTime).toBeLessThan(4000); // 4 seconds maximum
      }

      helpers.logStep('Rapid navigation performance test completed');
    });
  });

  test.describe('Memory Performance', () => {
    test('should not cause memory leaks during extended use', async ({ page }) => {
      helpers.logStep('Testing memory usage during extended use');

      // Navigate to analytics dashboard
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Monitor memory usage over time
      const memoryMeasurements: number[] = [];

      for (let i = 0; i < 10; i++) {
        // Perform various interactions
        await helpers.waitAndClick('[data-testid="refresh-button"]');
        await page.waitForTimeout(1000);

        await helpers.waitAndClick('[data-testid="filter-dropdown"]');
        await page.waitForTimeout(500);
        await helpers.waitAndClick('[data-testid="filter-option-all"]');
        await page.waitForTimeout(500);

        // Measure memory usage
        const memoryInfo = await page.evaluate(() => {
          return (performance as any).memory || {
            usedJSHeapSize: 0,
            totalJSHeapSize: 0,
          };
        });

        memoryMeasurements.push(memoryInfo.usedJSHeapSize);
        helpers.logStep(`Memory usage at iteration ${i + 1}: ${(memoryInfo.usedJSHeapSize / 1024 / 1024).toFixed(2)}MB`);

        // Force garbage collection if available
        await page.evaluate(() => {
          if ((window as any).gc) {
            (window as any).gc();
          }
        });
      }

      // Analyze memory growth
      if (memoryMeasurements.length > 1) {
        const initialMemory = memoryMeasurements[0];
        const finalMemory = memoryMeasurements[memoryMeasurements.length - 1];
        const memoryGrowth = finalMemory - initialMemory;

        helpers.logStep(`Initial memory: ${(initialMemory / 1024 / 1024).toFixed(2)}MB`);
        helpers.logStep(`Final memory: ${(finalMemory / 1024 / 1024).toFixed(2)}MB`);
        helpers.logStep(`Memory growth: ${(memoryGrowth / 1024 / 1024).toFixed(2)}MB`);

        // Memory growth should be reasonable
        expect(memoryGrowth).toBeLessThan(50 * 1024 * 1024); // 50MB max growth
      }

      helpers.logStep('Memory usage test completed');
    });

    test('should efficiently manage DOM nodes', async ({ page }) => {
      helpers.logStep('Testing DOM node management');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Monitor DOM node count
      const getNodeCount = async () => {
        return await page.evaluate(() => document.querySelectorAll('*').length);
      };

      const initialNodeCount = await getNodeCount();
      helpers.logStep(`Initial DOM nodes: ${initialNodeCount}`);

      // Perform operations that might create DOM nodes
      for (let i = 0; i < 5; i++) {
        await helpers.waitAndClick('[data-testid="refresh-button"]');
        await page.waitForTimeout(1000);

        await helpers.waitAndClick('[data-testid="filter-dropdown"]');
        await page.waitForTimeout(500);
        await helpers.waitAndClick('[data-testid="filter-option-all"]');
        await page.waitForTimeout(500);
      }

      const finalNodeCount = await getNodeCount();
      const nodeGrowth = finalNodeCount - initialNodeCount;

      helpers.logStep(`Final DOM nodes: ${finalNodeCount}`);
      helpers.logStep(`DOM node growth: ${nodeGrowth}`);

      // DOM node growth should be controlled
      expect(nodeGrowth).toBeLessThan(1000); // Max 1000 additional nodes
      expect(finalNodeCount).toBeLessThan(5000); // Max 5000 total nodes
    });
  });

  test.describe('Network Performance', () => {
    test('should optimize API requests and caching', async ({ page }) => {
      helpers.logStep('Testing API request optimization');

      let apiCallCount = 0;

      // Intercept and count API calls
      await page.route('**/api/v1/**', route => {
        apiCallCount++;
        route.continue();
      });

      // Navigate to analytics dashboard
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      const initialApiCalls = apiCallCount;
      helpers.logStep(`Initial API calls: ${initialApiCalls}`);

      // Refresh dashboard
      await helpers.waitAndClick('[data-testid="refresh-button"]');
      await page.waitForTimeout(2000);

      const refreshApiCalls = apiCallCount - initialApiCalls;
      helpers.logStep(`API calls during refresh: ${refreshApiCalls}`);

      // Navigate away and back
      await helpers.waitAndClick('[data-testid="dashboard-nav-link"]');
      await page.waitForTimeout(1000);

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await page.waitForTimeout(1000);

      const returnApiCalls = apiCallCount - initialApiCalls - refreshApiCalls;
      helpers.logStep(`API calls on return: ${returnApiCalls}`);

      // Should use cached data when appropriate
      expect(returnApiCalls).toBeLessThanOrEqual(refreshApiCalls);

      helpers.logStep('API optimization test completed');
    });

    test('should handle slow network gracefully', async ({ page }) => {
      helpers.logStep('Testing slow network handling');

      // Simulate slow network
      await page.route('**/api/v1/**', async route => {
        await new Promise(resolve => setTimeout(resolve, 2000)); // 2 second delay
        route.continue();
      });

      const startTime = Date.now();

      // Navigate to analytics dashboard
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');

      // Should show loading indicators during slow network
      await helpers.expectElementVisible('[data-testid="loading-indicator"]');
      await helpers.expectElementVisible('[data-testid="loading-skeleton"]');

      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');
      const loadTime = Date.now() - startTime;

      // Should still complete within reasonable time
      expect(loadTime).toBeLessThan(10000); // 10 seconds max on slow network
      helpers.logStep(`Slow network load completed in ${loadTime}ms`);

      // Should not show error states due to timeout
      expect(await helpers.elementExists('[data-testid="error-state"]')).toBeFalsy();

      // Restore normal network
      await page.unroute('**/api/v1/**');

      helpers.logStep('Slow network handling test completed');
    });
  });

  test.describe('Rendering Performance', () => {
    test('should maintain 60fps during animations', async ({ page }) => {
      helpers.logStep('Testing animation performance');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Test chart animations
      const chart = page.locator('[data-testid="chart"]').first();
      if (await chart.count() > 0) {
        // Monitor frame rate during animation
        const frameMetrics = await page.evaluate(() => {
          return new Promise(resolve => {
            const frames: number[] = [];
            let frameCount = 0;
            const maxFrames = 60;

            function recordFrame() {
              frames.push(performance.now());
              frameCount++;

              if (frameCount < maxFrames) {
                requestAnimationFrame(recordFrame);
              } else {
                // Calculate average frame time
                const frameTimes = [];
                for (let i = 1; i < frames.length; i++) {
                  frameTimes.push(frames[i] - frames[i - 1]);
                }
                const avgFrameTime = frameTimes.reduce((a, b) => a + b, 0) / frameTimes.length;
                const fps = 1000 / avgFrameTime;
                resolve(fps);
              }
            }

            // Start animation by triggering chart update
            const chart = document.querySelector('[data-testid="chart"]');
            if (chart) {
              chart.dispatchEvent(new Event('mouseenter'));
            }

            recordFrame();
          });
        });

        const fps = frameMetrics as number;
        helpers.logStep(`Animation FPS: ${fps.toFixed(1)}`);

        // Should maintain reasonable frame rate
        expect(fps).toBeGreaterThan(30); // Minimum 30fps
      }

      helpers.logStep('Animation performance test completed');
    });

    test('should efficiently render large lists', async ({ page }) => {
      helpers.logStep('Testing large list rendering performance');

      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Navigate to data table view if available
      const dataTableTab = page.locator('[data-testid="data-table-tab"]');
      if (await dataTableTab.count() > 0) {
        await dataTableTab.click();
        await helpers.expectElementVisible('[data-testid="data-table"]');

        // Test scrolling performance
        const scrollStart = Date.now();

        // Scroll through the table
        await page.evaluate(() => {
          const table = document.querySelector('[data-testid="data-table"]');
          if (table) {
            table.scrollTop = table.scrollHeight;
          }
        });

        await page.waitForTimeout(1000);

        const scrollTime = Date.now() - scrollStart;
        helpers.logStep(`Large list scroll time: ${scrollTime}ms`);

        // Scrolling should be responsive
        expect(scrollTime).toBeLessThan(2000); // 2 seconds max
      }

      helpers.logStep('Large list rendering test completed');
    });
  });

  test.describe('Resource Loading Performance', () => {
    test('should optimize resource loading', async ({ page }) => {
      helpers.logStep('Testing resource loading optimization');

      const resourceMetrics: any[] = [];

      // Monitor resource loading
      page.on('response', response => {
        if (response.url().includes('/api/v1/')) {
          resourceMetrics.push({
            url: response.url(),
            status: response.status(),
            size: parseInt(response.headers()['content-length'] || '0'),
            timing: Date.now(),
          });
        }
      });

      // Navigate to analytics dashboard
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Analyze resource loading
      const totalSize = resourceMetrics.reduce((sum, resource) => sum + resource.size, 0);
      const avgResponseTime = resourceMetrics.length > 0
        ? resourceMetrics.reduce((sum, resource) => sum + 1, 0) / resourceMetrics.length
        : 0;

      helpers.logStep(`Total API response size: ${(totalSize / 1024).toFixed(2)}KB`);
      helpers.logStep(`Number of API calls: ${resourceMetrics.length}`);

      // Should optimize resource usage
      expect(totalSize).toBeLessThan(5 * 1024 * 1024); // 5MB max total
      expect(resourceMetrics.length).toBeLessThan(20); // Max 20 API calls

      // Test compression
      const compressedResponses = resourceMetrics.filter(r =>
        r.headers && r.headers['content-encoding']?.includes('gzip')
      );
      const compressionRatio = compressedResponses.length / Math.max(resourceMetrics.length, 1);

      helpers.logStep(`Compression ratio: ${(compressionRatio * 100).toFixed(1)}%`);

      helpers.logStep('Resource loading optimization test completed');
    });

    test('should implement proper caching strategies', async ({ page }) => {
      helpers.logStep('Testing caching strategies');

      let cacheHeaders: any[] = [];

      // Monitor cache headers
      await page.route('**/api/v1/**', async route => {
        const response = await route.continue();
        const headers = response.headers();
        cacheHeaders.push({
          url: route.request().url(),
          cacheControl: headers['cache-control'],
          etag: headers['etag'],
          lastModified: headers['last-modified'],
        });
      });

      // Load page first time
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');
      await helpers.expectElementVisible('[data-testid="analytics-dashboard"]');

      // Load page second time
      await helpers.waitAndClick('[data-testid="refresh-button"]');
      await page.waitForTimeout(2000);

      // Analyze caching
      const cachedResponses = cacheHeaders.filter(headers =>
        headers.cacheControl?.includes('max-age') ||
        headers.etag ||
        headers.lastModified
      );

      const cacheUtilization = cachedResponses.length / Math.max(cacheHeaders.length, 1);
      helpers.logStep(`Cache utilization: ${(cacheUtilization * 100).toFixed(1)}%`);

      // Should implement caching for static resources
      expect(cacheUtilization).toBeGreaterThan(0.5); // At least 50% of responses should be cacheable

      helpers.logStep('Caching strategy test completed');
    });
  });

  test.describe('Critical Rendering Path', () => {
    test('should prioritize above-the-fold content', async ({ page }) => {
      helpers.logStep('Testing critical rendering path optimization');

      // Enable request interception to analyze loading order
      const requests: any[] = [];

      page.on('request', request => {
        requests.push({
          url: request.url(),
          resourceType: request.resourceType(),
          timestamp: Date.now(),
        });
      });

      const startTime = Date.now();

      // Navigate to analytics dashboard
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');

      // Wait for critical content to be visible
      await helpers.expectElementVisible('[data-testid="dashboard-header"]');
      const headerTime = Date.now() - startTime;

      await helpers.expectElementVisible('[data-testid="metric-card"]');
      const metricTime = Date.now() - startTime;

      // Analyze loading sequence
      const cssRequests = requests.filter(r => r.resourceType === 'stylesheet');
      const jsRequests = requests.filter(r => r.resourceType === 'script');
      const apiRequests = requests.filter(r => r.url.includes('/api/v1/'));

      helpers.logStep(`Header visible in: ${headerTime}ms`);
      helpers.logStep(`Metrics visible in: ${metricTime}ms`);
      helpers.logStep(`CSS requests: ${cssRequests.length}`);
      helpers.logStep(`JS requests: ${jsRequests.length}`);
      helpers.logStep(`API requests: ${apiRequests.length}`);

      // Critical content should load quickly
      expect(headerTime).toBeLessThan(1000); // Header in 1 second
      expect(metricTime).toBeLessThan(2500); // Metrics in 2.5 seconds

      helpers.logStep('Critical rendering path test completed');
    });

    test('should implement progressive enhancement', async ({ page }) => {
      helpers.logStep('Testing progressive enhancement');

      // Disable JavaScript to test basic functionality
      await page.context().route('**/*.js', route => route.abort());

      await page.goto('/dashboard');

      // Should show basic content without JavaScript
      await expect(page.locator('body')).toContainText('Analytics Dashboard');

      // Re-enable JavaScript
      await page.context().unroute('**/*.js');
      await page.reload();

      await helpers.login(TEST_DATA.USERS.ADMIN);
      await helpers.waitAndClick('[data-testid="analytics-nav-link"]');

      // Should enhance with JavaScript
      await helpers.expectElementVisible('[data-testid="metric-card"]');
      await helpers.expectElementVisible('[data-testid="chart"]');

      helpers.logStep('Progressive enhancement test completed');
    });
  });
});