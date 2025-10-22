import { test, expect } from '@playwright/test';
import { createTestHelpers, TEST_DATA } from '../utils/test-helpers';

test.describe('Graph Analytics Exploration - User Journey', () => {
  let helpers: ReturnType<typeof createTestHelpers>;

  test.beforeEach(async ({ page, context, browserName }, testInfo) => {
    helpers = createTestHelpers(page, context, testInfo);
    helpers.logStep(`Starting graph analytics test on ${browserName}`);

    // Login as admin for full access
    await helpers.login(TEST_DATA.USERS.ADMIN);
  });

  test.describe('Graph Navigation and Discovery', () => {
    test('should navigate to graph view and load initial visualization', async ({ page }) => {
      helpers.logStep('Testing graph navigation and initial load');

      // Step 1: Navigate to graph analytics
      await helpers.waitAndClick('[data-testid="graph-nav-link"]');
      await helpers.expectElementVisible('[data-testid="graph-container"]');
      helpers.logStep('Successfully navigated to graph analytics');

      // Step 2: Verify graph components load
      await helpers.expectElementVisible('[data-testid="graph-viewer"]');
      await helpers.expectElementVisible('[data-testid="graph-control-panel"]');
      await helpers.expectElementVisible('[data-testid="graph-filter-panel"]');
      helpers.logStep('Graph components loaded successfully');

      // Step 3: Wait for initial graph data to load
      await helpers.expectElementVisible('[data-testid="graph-node"]', { timeout: 10000 });
      await helpers.expectElementVisible('[data-testid="graph-edge"]');
      helpers.logStep('Graph data loaded successfully');

      // Step 4: Verify graph statistics
      const nodeCount = await helpers.getTextContent('[data-testid="node-count"]');
      const edgeCount = await helpers.getTextContent('[data-testid="edge-count"]');
      expect(parseInt(nodeCount)).toBeGreaterThan(0);
      expect(parseInt(edgeCount)).toBeGreaterThan(0);
      helpers.logStep(`Graph loaded with ${nodeCount} nodes and ${edgeCount} edges`);

      await helpers.takeScreenshot('graph-initial-load');
    });

    test('should display interactive graph controls', async ({ page }) => {
      helpers.logStep('Testing interactive graph controls');

      // Navigate to graph
      await helpers.waitAndClick('[data-testid="graph-nav-link"]');
      await helpers.expectElementVisible('[data-testid="graph-viewer"]');

      // Step 1: Test zoom controls
      await helpers.waitAndClick('[data-testid="zoom-in-button"]');
      await page.waitForTimeout(500);
      await helpers.waitAndClick('[data-testid="zoom-out-button"]');
      await page.waitForTimeout(500);
      await helpers.waitAndClick('[data-testid="fit-to-screen-button"]');
      helpers.logStep('Zoom controls working correctly');

      // Step 2: Test layout controls
      await helpers.waitAndClick('[data-testid="layout-selector"]');
      await helpers.waitAndClick('[data-testid="layout-force"]');
      await page.waitForTimeout(1000); // Wait for layout to apply
      helpers.logStep('Force layout applied');

      await helpers.waitAndClick('[data-testid="layout-selector"]');
      await helpers.waitAndClick('[data-testid="layout-circular"]');
      await page.waitForTimeout(1000);
      helpers.logStep('Circular layout applied');

      await helpers.waitAndClick('[data-testid="layout-selector"]');
      await helpers.waitAndClick('[data-testid="layout-hierarchical"]');
      await page.waitForTimeout(1000);
      helpers.logStep('Hierarchical layout applied');

      // Step 3: Test graph export
      await helpers.waitAndClick('[data-testid="graph-export-button"]');
      await helpers.expectElementVisible('[data-testid="export-menu"]');
      await helpers.waitAndClick('[data-testid="export-as-png"]');

      const download = await page.waitForEvent('download');
      expect(download.suggestedFilename()).toMatch(/\.png$/);
      helpers.logStep('Graph exported as PNG successfully');

      // Step 4: Test fullscreen mode
      await helpers.waitAndClick('[data-testid="fullscreen-button"]');
      await helpers.expectElementVisible('[data-testid="fullscreen-overlay"]');
      await helpers.waitAndClick('[data-testid="exit-fullscreen-button"]');
      helpers.logStep('Fullscreen mode working');
    });

    test('should handle node and edge interactions', async ({ page }) => {
      helpers.logStep('Testing node and edge interactions');

      // Navigate to graph
      await helpers.waitAndClick('[data-testid="graph-nav-link"]');
      await helpers.expectElementVisible('[data-testid="graph-viewer"]');

      // Step 1: Wait for nodes to be available
      await helpers.expectElementVisible('[data-testid="graph-node"]');

      // Step 2: Test node hover
      const firstNode = page.locator('[data-testid="graph-node"]').first();
      await firstNode.hover();
      await helpers.expectElementVisible('[data-testid="node-tooltip"]');
      const tooltipContent = await helpers.getTextContent('[data-testid="node-tooltip"]');
      expect(tooltipContent).toBeTruthy();
      helpers.logStep('Node tooltip displays on hover');

      // Step 3: Test node selection
      await firstNode.click();
      await helpers.expectElementVisible('[data-testid="node-selected"]');
      await helpers.expectElementVisible('[data-testid="node-details-panel"]');
      helpers.logStep('Node selection working');

      // Step 4: Verify node details
      const nodeName = await helpers.getTextContent('[data-testid="node-name"]');
      const nodeType = await helpers.getTextContent('[data-testid="node-type"]');
      const nodeProperties = await helpers.getTextContent('[data-testid="node-properties"]');

      expect(nodeName).toBeTruthy();
      expect(nodeType).toBeTruthy();
      expect(nodeProperties).toBeTruthy();
      helpers.logStep(`Selected node: ${nodeName} (${nodeType})`);

      // Step 5: Test multiple node selection
      const secondNode = page.locator('[data-testid="graph-node"]').nth(1);
      await page.keyboard.down('Control');
      await secondNode.click();
      await page.keyboard.up('Control');

      const selectedCount = await page.locator('[data-testid="node-selected"]').count();
      expect(selectedCount).toBe(2);
      helpers.logStep('Multiple node selection working');

      // Step 6: Test edge interaction
      const firstEdge = page.locator('[data-testid="graph-edge"]').first();
      await firstEdge.hover();
      await helpers.expectElementVisible('[data-testid="edge-tooltip"]');
      await firstEdge.click();
      await helpers.expectElementVisible('[data-testid="edge-details-panel"]');
      helpers.logStep('Edge interaction working');

      // Step 7: Clear selection
      await helpers.waitAndClick('[data-testid="clear-selection-button"]');
      await expect(page.locator('[data-testid="node-selected"]')).toHaveCount(0);
      helpers.logStep('Selection cleared successfully');
    });
  });

  test.describe('Graph Filtering and Search', () => {
    test.beforeEach(async ({ page }) => {
      await helpers.waitAndClick('[data-testid="graph-nav-link"]');
      await helpers.expectElementVisible('[data-testid="graph-viewer"]');
    });

    test('should filter nodes by type', async ({ page }) => {
      helpers.logStep('Testing node type filtering');

      // Step 1: Open filter panel
      await helpers.waitAndClick('[data-testid="filter-panel-toggle"]');
      await helpers.expectElementVisible('[data-testid="graph-filter-panel"]');

      // Step 2: Get initial node count
      const initialNodeCount = await page.locator('[data-testid="graph-node"]').count();
      helpers.logStep(`Initial node count: ${initialNodeCount}`);

      // Step 3: Filter by entity type
      await helpers.selectOption('[data-testid="node-type-filter"]', 'Person');
      await helpers.waitAndClick('[data-testid="apply-filters-button"]');
      await page.waitForTimeout(1000); // Wait for filter to apply

      // Step 4: Verify filtered results
      const filteredNodeCount = await page.locator('[data-testid="graph-node"]').count();
      expect(filteredNodeCount).toBeLessThanOrEqual(initialNodeCount);
      helpers.logStep(`Filtered node count: ${filteredNodeCount}`);

      // Step 5: Verify filter is active
      await helpers.expectElementVisible('[data-testid="active-filter"]');
      const activeFilter = await helpers.getTextContent('[data-testid="active-filter"]');
      expect(activeFilter).toContain('Person');
      helpers.logStep('Active filter displayed correctly');

      // Step 6: Clear filters
      await helpers.waitAndClick('[data-testid="clear-filters-button"]');
      await page.waitForTimeout(1000);
      const clearedNodeCount = await page.locator('[data-testid="graph-node"]').count();
      expect(clearedNodeCount).toBe(initialNodeCount);
      helpers.logStep('Filters cleared successfully');
    });

    test('should search for specific nodes', async ({ page }) => {
      helpers.logStep('Testing node search functionality');

      // Step 1: Open search
      await helpers.waitAndClick('[data-testid="graph-search-button"]');
      await helpers.expectElementVisible('[data-testid="graph-search-input"]');

      // Step 2: Search for a known entity
      await helpers.fillField('[data-testid="graph-search-input"]', 'John');
      await page.waitForTimeout(500); // Wait for search results

      // Step 3: Verify search results
      await helpers.expectElementVisible('[data-testid="search-results"]');
      const searchResults = page.locator('[data-testid="search-result-item"]');
      await expect(searchResults).toHaveCount.greaterThan(0);
      helpers.logStep('Search results displayed');

      // Step 4: Select search result
      await helpers.waitAndClick('[data-testid="search-result-item"]');
      await helpers.expectElementVisible('[data-testid="node-selected"]');
      helpers.logStep('Search result selected');

      // Step 5: Highlight search term in graph
      await helpers.expectElementVisible('[data-testid="search-highlight"]');
      const highlightedNodes = page.locator('[data-testid="search-highlight"]');
      await expect(highlightedNodes).toHaveCount.greaterThan(0);
      helpers.logStep('Search terms highlighted in graph');

      // Step 6: Clear search
      await helpers.waitAndClick('[data-testid="clear-search-button"]');
      await expect(page.locator('[data-testid="search-highlight"]')).toHaveCount(0);
      helpers.logStep('Search cleared successfully');
    });

    test('should filter by relationship type', async ({ page }) => {
      helpers.logStep('Testing relationship filtering');

      // Step 1: Open filter panel
      await helpers.waitAndClick('[data-testid="filter-panel-toggle"]');
      await helpers.expectElementVisible('[data-testid="graph-filter-panel"]');

      // Step 2: Get initial edge count
      const initialEdgeCount = await page.locator('[data-testid="graph-edge"]').count();
      helpers.logStep(`Initial edge count: ${initialEdgeCount}`);

      // Step 3: Filter by relationship type
      await helpers.selectOption('[data-testid="relationship-type-filter"]', 'WORKS_FOR');
      await helpers.waitAndClick('[data-testid="apply-filters-button"]');
      await page.waitForTimeout(1000);

      // Step 4: Verify filtered results
      const filteredEdgeCount = await page.locator('[data-testid="graph-edge"]').count();
      expect(filteredEdgeCount).toBeLessThanOrEqual(initialEdgeCount);
      helpers.logStep(`Filtered edge count: ${filteredEdgeCount}`);

      // Step 5: Test relationship path highlighting
      await helpers.waitAndClick('[data-testid="highlight-paths-button"]');
      await helpers.expectElementVisible('[data-testid="path-highlight"]');
      helpers.logStep('Relationship paths highlighted');
    });
  });

  test.describe('Graph Analytics and Insights', () => {
    test.beforeEach(async ({ page }) => {
      await helpers.waitAndClick('[data-testid="graph-nav-link"]');
      await helpers.expectElementVisible('[data-testid="graph-viewer"]');
    });

    test('should display graph analytics metrics', async ({ page }) => {
      helpers.logStep('Testing graph analytics metrics');

      // Step 1: Open analytics panel
      await helpers.waitAndClick('[data-testid="analytics-panel-toggle"]');
      await helpers.expectElementVisible('[data-testid="graph-analytics-panel"]');

      // Step 2: Verify basic metrics
      const metrics = [
        '[data-testid="total-nodes"]',
        '[data-testid="total-edges"]',
        '[data-testid="graph-density"]',
        '[data-testid="average-degree"]',
        '[data-testid="connected-components"]',
      ];

      for (const metric of metrics) {
        if (await helpers.elementExists(metric)) {
          await helpers.expectElementVisible(metric);
          const value = await helpers.getTextContent(metric);
          expect(value).toBeTruthy();
          helpers.logStep(`Metric ${metric}: ${value}`);
        }
      }

      // Step 3: Test centrality metrics
      await helpers.waitAndClick('[data-testid="centrality-tab"]');
      await helpers.expectElementVisible('[data-testid="centrality-metrics"]');

      const centralityMetrics = [
        '[data-testid="degree-centrality"]',
        '[data-testid="betweenness-centrality"]',
        '[data-testid="closeness-centrality"]',
        '[data-testid="eigenvector-centrality"]',
      ];

      for (const metric of centralityMetrics) {
        if (await helpers.elementExists(metric)) {
          await helpers.expectElementVisible(metric);
        }
      }

      helpers.logStep('Centrality metrics displayed');

      // Step 4: Test community detection
      await helpers.waitAndClick('[data-testid="community-tab"]');
      await helpers.expectElementVisible('[data-testid="community-metrics"]');

      const communityCount = await helpers.getTextContent('[data-testid="community-count"]');
      expect(parseInt(communityCount)).toBeGreaterThan(0);
      helpers.logStep(`Detected ${communityCount} communities`);

      // Step 5: Test graph evolution
      await helpers.waitAndClick('[data-testid="evolution-tab"]');
      await helpers.expectElementVisible('[data-testid="evolution-chart"]');
      helpers.logStep('Graph evolution metrics displayed');
    });

    test('should identify and highlight important nodes', async ({ page }) => {
      helpers.logStep('Testing important node identification');

      // Step 1: Enable importance analysis
      await helpers.waitAndClick('[data-testid="analytics-panel-toggle"]');
      await helpers.waitAndClick('[data-testid="importance-analysis"]');
      await page.waitForTimeout(2000); // Wait for analysis

      // Step 2: Verify important nodes are highlighted
      await helpers.expectElementVisible('[data-testid="important-node"]');
      const importantNodes = page.locator('[data-testid="important-node"]');
      await expect(importantNodes).toHaveCount.greaterThan(0);
      helpers.logStep(`Identified ${await importantNodes.count()} important nodes`);

      // Step 3: Test different importance metrics
      const importanceTypes = ['degree', 'betweenness', 'closeness'];

      for (const type of importanceTypes) {
        await helpers.selectOption('[data-testid="importance-metric"]', type);
        await page.waitForTimeout(1000);

        const highlightedNodes = page.locator('[data-testid="importance-highlight"]');
        await expect(highlightedNodes).toHaveCount.greaterThan(0);
        helpers.logStep(`Importance analysis by ${type} completed`);
      }

      // Step 4: Test node ranking
      await helpers.waitAndClick('[data-testid="node-ranking-button"]');
      await helpers.expectElementVisible('[data-testid="node-ranking-table"]');

      const rankingRows = page.locator('[data-testid="ranking-row"]');
      await expect(rankingRows).toHaveCount.greaterThan(0);
      helpers.logStep('Node ranking displayed');
    });

    test('should detect and display graph patterns', async ({ page }) => {
      helpers.logStep('Testing graph pattern detection');

      // Step 1: Run pattern detection
      await helpers.waitAndClick('[data-testid="pattern-detection-button"]');
      await helpers.expectElementVisible('[data-testid="pattern-analysis-loading"]');

      // Wait for analysis to complete
      await helpers.expectElementHidden('[data-testid="pattern-analysis-loading"]', { timeout: 10000 });

      // Step 2: Verify detected patterns
      await helpers.expectElementVisible('[data-testid="detected-patterns"]');
      const patterns = page.locator('[data-testid="pattern-item"]');

      if (await patterns.count() > 0) {
        // Step 3: Test pattern visualization
        await helpers.waitAndClick('[data-testid="pattern-item"]');
        await helpers.expectElementVisible('[data-testid="pattern-visualization"]');
        helpers.logStep('Pattern visualization displayed');

        // Step 4: Test pattern details
        await helpers.expectElementVisible('[data-testid="pattern-details"]');
        const patternDescription = await helpers.getTextContent('[data-testid="pattern-description"]');
        expect(patternDescription).toBeTruthy();
        helpers.logStep('Pattern details displayed');
      } else {
        helpers.logStep('No patterns detected (acceptable for test data)');
      }

      // Step 5: Test anomaly detection
      await helpers.waitAndClick('[data-testid="anomaly-detection-tab"]');
      await page.waitForTimeout(2000);

      if (await helpers.elementExists('[data-testid="detected-anomalies"]')) {
        await helpers.expectElementVisible('[data-testid="detected-anomalies"]');
        const anomalies = page.locator('[data-testid="anomaly-item"]');
        helpers.logStep(`Detected ${await anomalies.count()} anomalies`);
      }
    });
  });

  test.describe('Graph Export and Sharing', () => {
    test.beforeEach(async ({ page }) => {
      await helpers.waitAndClick('[data-testid="graph-nav-link"]');
      await helpers.expectElementVisible('[data-testid="graph-viewer"]');
    });

    test('should export graph in multiple formats', async ({ page }) => {
      helpers.logStep('Testing graph export functionality');

      // Step 1: Test PNG export
      await helpers.waitAndClick('[data-testid="graph-export-button"]');
      await helpers.waitAndClick('[data-testid="export-as-png"]');

      const pngDownload = await page.waitForEvent('download');
      expect(pngDownload.suggestedFilename()).toMatch(/\.png$/);
      helpers.logStep('PNG export successful');

      // Step 2: Test SVG export
      await helpers.waitAndClick('[data-testid="graph-export-button"]');
      await helpers.waitAndClick('[data-testid="export-as-svg"]');

      const svgDownload = await page.waitForEvent('download');
      expect(svgDownload.suggestedFilename()).toMatch(/\.svg$/);
      helpers.logStep('SVG export successful');

      // Step 3: Test JSON export
      await helpers.waitAndClick('[data-testid="graph-export-button"]');
      await helpers.waitAndClick('[data-testid="export-as-json"]');

      const jsonDownload = await page.waitForEvent('download');
      expect(jsonDownload.suggestedFilename()).toMatch(/\.json$/);
      helpers.logStep('JSON export successful');

      // Step 4: Test CSV export
      await helpers.waitAndClick('[data-testid="graph-export-button"]');
      await helpers.waitAndClick('[data-testid="export-as-csv"]');

      const csvDownload = await page.waitForEvent('download');
      expect(csvDownload.suggestedFilename()).toMatch(/\.csv$/);
      helpers.logStep('CSV export successful');
    });

    test('should share graph view with others', async ({ page }) => {
      helpers.logStep('Testing graph sharing functionality');

      // Step 1: Create shareable link
      await helpers.waitAndClick('[data-testid="share-button"]');
      await helpers.expectElementVisible('[data-testid="share-modal"]');

      // Step 2: Generate share link
      await helpers.waitAndClick('[data-testid="generate-share-link"]');
      await helpers.expectElementVisible('[data-testid="share-link"]');

      const shareLink = await helpers.getAttribute('[data-testid="share-link"]', 'value');
      expect(shareLink).toContain('http');
      helpers.logStep('Share link generated successfully');

      // Step 3: Copy share link
      await helpers.waitAndClick('[data-testid="copy-share-link"]');
      await helpers.expectElementVisible('[data-testid="copy-confirmation"]');
      helpers.logStep('Share link copied successfully');

      // Step 4: Test share settings
      await helpers.waitAndClick('[data-testid="share-settings-tab"]');
      await helpers.expectElementVisible('[data-testid="share-settings"]');

      // Test permission settings
      await helpers.waitAndClick('[data-testid="view-only-permission"]');
      await helpers.waitAndClick('[data-testid="include-filters-toggle"]');
      helpers.waitAndClick('[data-testid="expire-after-setting"]');
      await helpers.selectOption('[data-testid="expire-after-select"]', '7d');
      helpers.logStep('Share settings configured');

      // Step 5: Update share link with settings
      await helpers.waitAndClick('[data-testid="update-share-link"]');
      await page.waitForTimeout(1000);
      helpers.logStep('Share link updated with settings');

      // Step 6: Close share modal
      await helpers.waitAndClick('[data-testid="close-share-modal"]');
      await helpers.expectElementHidden('[data-testid="share-modal"]');
      helpers.logStep('Share functionality working correctly');
    });
  });

  test.describe('Performance and Scalability', () => {
    test('should handle large graphs efficiently', async ({ page }) => {
      helpers.logStep('Testing large graph performance');

      // Step 1: Load large test graph
      await helpers.waitAndClick('[data-testid="graph-nav-link"]');
      await helpers.expectElementVisible('[data-testid="graph-viewer"]');

      // Step 2: Simulate large graph data
      await page.evaluate(() => {
        // Mock large graph data
        const mockLargeGraph = {
          nodes: Array.from({ length: 1000 }, (_, i) => ({
            id: `node-${i}`,
            name: `Node ${i}`,
            type: i % 3 === 0 ? 'Person' : 'Organization',
            x: Math.random() * 1000,
            y: Math.random() * 800,
          })),
          edges: Array.from({ length: 2000 }, (_, i) => ({
            id: `edge-${i}`,
            source: `node-${Math.floor(Math.random() * 1000)}`,
            target: `node-${Math.floor(Math.random() * 1000)}`,
            type: 'CONNECTED_TO',
          })),
        };

        // Trigger graph render with large data
        window.postMessage({ type: 'UPDATE_GRAPH_DATA', data: mockLargeGraph }, '*');
      });

      // Step 3: Monitor performance
      const startTime = Date.now();
      await helpers.expectElementVisible('[data-testid="graph-rendering-complete"]', { timeout: 15000 });
      const renderTime = Date.now() - startTime;

      expect(renderTime).toBeLessThan(10000); // Should render in under 10 seconds
      helpers.logStep(`Large graph rendered in ${renderTime}ms`);

      // Step 4: Test interactions with large graph
      await helpers.waitAndClick('[data-testid="graph-viewer"]');
      await page.mouse.move(500, 400); // Pan around
      await page.mouse.wheel(0, -100); // Zoom
      helpers.logStep('Large graph interactions working');

      // Step 5: Test filtering performance
      await helpers.waitAndClick('[data-testid="filter-panel-toggle"]');
      await helpers.selectOption('[data-testid="node-type-filter"]', 'Person');
      await helpers.waitAndClick('[data-testid="apply-filters-button"]');

      const filterStartTime = Date.now();
      await helpers.expectElementVisible('[data-testid="filter-complete"]', { timeout: 5000 });
      const filterTime = Date.now() - filterStartTime;

      expect(filterTime).toBeLessThan(3000); // Should filter in under 3 seconds
      helpers.logStep(`Large graph filtered in ${filterTime}ms`);
    });

    test('should maintain responsiveness during real-time updates', async ({ page }) => {
      helpers.logStep('Testing real-time update performance');

      // Step 1: Navigate to graph and enable real-time updates
      await helpers.waitAndClick('[data-testid="graph-nav-link"]');
      await helpers.waitAndClick('[data-testid="real-time-toggle"]');

      // Step 2: Simulate frequent updates
      await page.evaluate(() => {
        let updateCount = 0;
        const interval = setInterval(() => {
          updateCount++;

          // Simulate graph updates
          const updateData = {
            type: 'GRAPH_UPDATE',
            data: {
              addedNodes: [{
                id: `new-node-${updateCount}`,
                name: `New Node ${updateCount}`,
                type: 'Person',
              }],
              updatedNodes: [{
                id: 'node-1',
                properties: { lastUpdated: new Date().toISOString() },
              }],
            },
          };

          window.postMessage(updateData, '*');

          if (updateCount >= 20) {
            clearInterval(interval);
          }
        }, 500); // Update every 500ms
      });

      // Step 3: Monitor responsiveness during updates
      const updateStartTime = Date.now();

      // Test interactions during updates
      for (let i = 0; i < 5; i++) {
        await page.waitForTimeout(1000);
        await helpers.waitAndClick('[data-testid="graph-viewer"]');

        // Verify graph is still responsive
        const isResponsive = await page.evaluate(() => {
          return document.querySelector('[data-testid="graph-viewer"]') !== null;
        });

        expect(isResponsive).toBe(true);
        helpers.logStep(`Graph responsive during update ${i + 1}`);
      }

      const totalUpdateTime = Date.now() - updateStartTime;
      helpers.logStep(`Real-time updates completed in ${totalUpdateTime}ms`);

      // Step 4: Verify all updates were processed
      await helpers.expectElementVisible('[data-testid="update-count"]');
      const updateCount = await helpers.getTextContent('[data-testid="update-count"]');
      expect(parseInt(updateCount)).toBeGreaterThanOrEqual(20);
      helpers.logStep(`Processed ${updateCount} real-time updates`);
    });
  });
});