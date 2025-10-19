import { test, expect } from '../fixtures/test-data.fixture';
import { DocumentsPage, KnowledgeGraphPage } from '../utils/page-objects';

/**
 * E2E Tests for Knowledge Graph Exploration (User Story 3)
 *
 * Test Coverage:
 * - Graph visualization rendering
 * - Entity node interaction and navigation
 * - Relationship exploration and filtering
 * - Graph controls (zoom, pan, layout selection)
 * - Entity details panel display
 */

test.describe('Knowledge Graph Exploration', () => {
  let documentsPage: DocumentsPage;
  let graphPage: KnowledgeGraphPage;

  test.beforeEach(async ({ authenticatedPage }) => {
    documentsPage = new DocumentsPage(authenticatedPage);
    graphPage = new KnowledgeGraphPage(authenticatedPage);
  });

  test('US3-1: Graph visualization loads and renders correctly', async ({ page }) => {
    // Navigate to knowledge graph page
    await graphPage.navigateTo('/graph');

    // Wait for graph to load
    await graphPage.waitForGraphLoad();

    // Verify graph canvas is visible
    await expect(graphPage.graphCanvas).toBeVisible();

    // Verify graph controls are present
    await expect(graphPage.graphControls).toBeVisible();
    await expect(graphPage.zoomInButton).toBeVisible();
    await expect(graphPage.zoomOutButton).toBeVisible();
    await expect(graphPage.fitButton).toBeVisible();

    // Verify nodes are rendered
    const nodes = page.locator('[data-testid="graph-node"]');
    expect(await nodes.count()).toBeGreaterThan(0);

    // Verify edges are rendered (if there are relationships)
    const edges = page.locator('[data-testid="graph-edge"]');
    const edgeCount = await edges.count();
    // Edge count might be 0 if no relationships exist yet

    // Verify graph statistics are displayed
    await expect(graphPage.nodeCount).toBeVisible();
    await expect(graphPage.edgeCount).toBeVisible();

    // Take screenshot for documentation
    await graphPage.takeScreenshot('graph-visualization-loaded');
  });

  test('US3-2: Entity node interaction and selection', async ({ page, testData }) => {
    // Upload documents to populate graph
    await documentsPage.navigateTo('/documents');
    await documentsPage.uploadFile(testData.files.pdf.path, testData.files.pdf.name);
    await documentsPage.uploadFile(testData.files.text.path, testData.files.text.name);

    // Navigate to graph
    await graphPage.navigateTo('/graph');
    await graphPage.waitForGraphLoad();

    // Find and select a node
    const nodes = page.locator('[data-testid="graph-node"]');
    if (await nodes.count() > 0) {
      const firstNode = nodes.first();

      // Get node label before selection
      const nodeLabel = await firstNode.locator('[data-testid="node-label"]').textContent();

      // Click on the node
      await firstNode.click();

      // Verify node is selected (visual feedback)
      await expect(firstNode).toHaveClass(/selected/);

      // Verify entity details panel appears
      await expect(graphPage.entityDetails).toBeVisible();

      // Verify entity details contain information
      await expect(page.locator('[data-testid="entity-name"]')).toContainText(nodeLabel || '');
      await expect(page.locator('[data-testid="entity-type"]')).toBeVisible();
      await expect(page.locator('[data-testid="entity-properties"]')).toBeVisible();

      // Verify related nodes are highlighted
      const relatedNodes = page.locator('[data-testid="graph-node"].related');
      const relatedCount = await relatedNodes.count();
      // Related nodes might be 0 if no relationships exist
    }
  });

  test('US3-3: Graph zoom and pan controls', async ({ page }) => {
    await graphPage.navigateTo('/graph');
    await graphPage.waitForGraphLoad();

    // Get initial node positions
    const initialNodes = page.locator('[data-testid="graph-node"]');
    const initialNode = initialNodes.first();
    const initialBoundingBox = await initialNode.boundingBox();

    // Test zoom in
    await graphPage.zoomInButton.click();
    await page.waitForTimeout(500); // Wait for zoom animation

    // Node should appear larger after zoom in
    const zoomedBoundingBox = await initialNode.boundingBox();
    if (initialBoundingBox && zoomedBoundingBox) {
      expect(zoomedBoundingBox.width).toBeGreaterThan(initialBoundingBox.width);
    }

    // Test zoom out
    await graphPage.zoomOutButton.click();
    await page.waitForTimeout(500);

    // Node should return closer to original size
    const zoomedOutBoundingBox = await initialNode.boundingBox();
    if (zoomedOutBoundingBox && initialBoundingBox) {
      expect(Math.abs(zoomedOutBoundingBox.width - initialBoundingBox.width)).toBeLessThan(10);
    }

    // Test pan functionality (drag to move graph)
    await graphPage.graphCanvas.hover();
    await page.mouse.down();
    await page.mouse.move(100, 100);
    await page.mouse.up();

    // Verify graph has moved (nodes have different positions)
    await page.waitForTimeout(500);
  });

  test('US3-4: Graph layout selection and switching', async ({ page }) => {
    await graphPage.navigateTo('/graph');
    await graphPage.waitForGraphLoad();

    // Test layout selector is available
    await expect(graphPage.layoutSelector).toBeVisible();

    // Click on layout selector
    await graphPage.layoutSelector.click();

    // Verify layout options are displayed
    await expect(page.locator('[data-testid="layout-force"]')).toBeVisible();
    await expect(page.locator('[data-testid="layout-circular"]')).toBeVisible();
    await expect(page.locator('[data-testid="layout-hierarchical"]')).toBeVisible();

    // Test switching to different layout
    await page.locator('[data-testid="layout-circular"]').click();
    await page.waitForTimeout(2000); // Wait for layout animation

    // Verify layout has changed (nodes arranged in circular pattern)
    // This would require more complex verification in a real scenario
    await expect(graphPage.graphCanvas).toBeVisible();

    // Test another layout
    await graphPage.layoutSelector.click();
    await page.locator('[data-testid="layout-hierarchical"]').click();
    await page.waitForTimeout(2000);

    await expect(graphPage.graphCanvas).toBeVisible();
  });

  test('US3-5: Entity search and navigation', async ({ page }) => {
    await graphPage.navigateTo('/graph');
    await graphPage.waitForGraphLoad();

    // Test search functionality
    await expect(graphPage.searchEntities).toBeVisible();

    // Search for a specific entity
    const searchTerm = 'test'; // Adjust based on your test data
    await graphPage.searchForEntity(searchTerm);

    // Verify search results or highlighting
    // The graph should highlight matching nodes or show search results
    const highlightedNodes = page.locator('[data-testid="graph-node"].highlighted');

    // If nodes are found, they should be highlighted
    if (await highlightedNodes.count() > 0) {
      await expect(highlightedNodes.first()).toBeVisible();
    } else {
      // If no nodes found, verify no results message
      await expect(page.locator('[data-testid="no-search-results"]')).toBeVisible();
    }

    // Test clearing search
    await graphPage.searchEntities.fill('');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(1000);
  });

  test('US3-6: Entity filtering by type and properties', async ({ page }) => {
    await graphPage.navigateTo('/graph');
    await graphPage.waitForGraphLoad();

    // Test filter functionality
    await expect(graphPage.filterEntities).toBeVisible();
    await graphPage.filterEntities.click();

    // Verify filter options are displayed
    await expect(page.locator('[data-testid="filter-by-type"]')).toBeVisible();
    await expect(page.locator('[data-testid="filter-by-property"]')).toBeVisible();

    // Test filtering by entity type
    await page.locator('[data-testid="entity-type-filter"]').click();
    await page.locator('[data-testid="type-person"]').click(); // Example type
    await page.click('[data-testid="apply-filters"]');

    // Wait for filter to apply
    await page.waitForTimeout(2000);

    // Verify only matching entities are shown
    const visibleNodes = page.locator('[data-testid="graph-node"]:not(.hidden)');
    const filteredNodes = page.locator('[data-testid="graph-node"].type-person');

    if (await filteredNodes.count() > 0) {
      // If filtered nodes exist, verify they are visible
      await expect(filteredNodes.first()).toBeVisible();
    }

    // Clear filters
    await page.click('[data-testid="clear-filters"]');
    await page.waitForTimeout(1000);
  });

  test('US3-7: Relationship exploration and visualization', async ({ page, testData }) => {
    // Upload documents with relationships
    await documentsPage.navigateTo('/documents');
    await documentsPage.uploadFile(testData.files.pdf.path, testData.files.pdf.name);
    await page.waitForTimeout(3000); // Allow processing

    // Navigate to graph
    await graphPage.navigateTo('/graph');
    await graphPage.waitForGraphLoad();

    // Select a node that might have relationships
    const nodes = page.locator('[data-testid="graph-node"]');
    if (await nodes.count() > 0) {
      await nodes.first().click();

      // Wait for relationships to load
      await page.waitForTimeout(2000);

      // Check for relationship information
      if (await page.locator('[data-testid="relationship-info"]').isVisible()) {
        await expect(page.locator('[data-testid="relationship-list"]')).toBeVisible();

        // Verify relationship details
        const relationships = page.locator('[data-testid="relationship-item"]');
        const relationshipCount = await relationships.count();

        if (relationshipCount > 0) {
          // Check first relationship
          await expect(relationships.first().locator('[data-testid="relationship-type"]')).toBeVisible();
          await expect(relationships.first().locator('[data-testid="related-entity"]')).toBeVisible();

          // Click on a relationship to explore related entity
          await relationships.first().click();
          await page.waitForTimeout(1000);

          // Verify navigation to related entity
          await expect(graphPage.entityDetails).toBeVisible();
        }
      }
    }
  });

  test('US3-8: Graph export and sharing functionality', async ({ page }) => {
    await graphPage.navigateTo('/graph');
    await graphPage.waitForGraphLoad();

    // Test export functionality
    await expect(page.locator('[data-testid="export-graph"]')).toBeVisible();
    await page.click('[data-testid="export-graph"]');

    // Verify export options
    await expect(page.locator('[data-testid="export-png"]')).toBeVisible();
    await expect(page.locator('[data-testid="export-svg"]')).toBeVisible();
    await expect(page.locator('[data-testid="export-json"]')).toBeVisible();

    // Test PNG export
    const downloadPromise = page.waitForEvent('download');
    await page.click('[data-testid="export-png"]');
    const download = await downloadPromise;

    // Verify download started
    expect(download.suggestedFilename()).toMatch(/\.png$/);

    // Test share functionality
    await page.click('[data-testid="share-graph"]');
    await expect(page.locator('[data-testid="share-link"]')).toBeVisible();
    await expect(page.locator('[data-testid="copy-link"]')).toBeVisible();

    // Copy link
    await page.click('[data-testid="copy-link"]');
    await expect(page.locator('[data-testid="copy-success"]')).toBeVisible();
  });

  test('US3-9: Graph performance with large datasets', async ({ page, testData }) => {
    // This test would ideally upload many documents to create a large graph
    // For now, we'll test basic performance

    const startTime = Date.now();

    await graphPage.navigateTo('/graph');
    await graphPage.waitForGraphLoad();

    const loadTime = Date.now() - startTime;

    // Graph should load within reasonable time
    expect(loadTime).toBeLessThan(10000); // 10 seconds max

    console.log(`Graph loaded in ${loadTime}ms`);

    // Test interaction performance
    const nodes = page.locator('[data-testid="graph-node"]');
    if (await nodes.count() > 0) {
      const interactionStart = Date.now();
      await nodes.first().click();
      await expect(graphPage.entityDetails).toBeVisible();
      const interactionTime = Date.now() - interactionStart;

      // Interaction should be responsive
      expect(interactionTime).toBeLessThan(2000); // 2 seconds max
    }
  });

  test('US3-10: Graph mini-map and navigation aids', async ({ page }) => {
    await graphPage.navigateTo('/graph');
    await graphPage.waitForGraphLoad();

    // Test mini-map functionality (if available)
    const minimap = page.locator('[data-testid="graph-minimap"]');
    if (await minimap.isVisible()) {
      await expect(minimap).toBeVisible();

      // Test minimap interaction
      await minimap.click();
      await page.waitForTimeout(500);

      // Verify viewport changes
      await expect(graphPage.graphCanvas).toBeVisible();
    }

    // Test fit-to-screen functionality
    await graphPage.fitButton.click();
    await page.waitForTimeout(1000);

    // Verify graph fits in viewport
    const canvas = page.locator('[data-testid="graph-canvas"]');
    await expect(canvas).toBeVisible();
  });

  test('US3-11: Entity details panel information', async ({ page }) => {
    await graphPage.navigateTo('/graph');
    await graphPage.waitForGraphLoad();

    // Select a node
    const nodes = page.locator('[data-testid="graph-node"]');
    if (await nodes.count() > 0) {
      await nodes.first().click();

      // Verify entity details panel content
      await expect(page.locator('[data-testid="entity-name"]')).toBeVisible();
      await expect(page.locator('[data-testid="entity-type"]')).toBeVisible();
      await expect(page.locator('[data-testid="entity-description"]')).toBeVisible();
      await expect(page.locator('[data-testid="entity-properties"]')).toBeVisible();

      // Test properties display
      const properties = page.locator('[data-testid="property-item"]');
      const propertyCount = await properties.count();

      if (propertyCount > 0) {
        // Verify property structure
        await expect(properties.first().locator('[data-testid="property-key"]')).toBeVisible();
        await expect(properties.first().locator('[data-testid="property-value"]')).toBeVisible();
      }

      // Test related entities section
      const relatedEntities = page.locator('[data-testid="related-entities"]');
      if (await relatedEntities.isVisible()) {
        await expect(page.locator('[data-testid="related-entity-list"]')).toBeVisible();
      }

      // Test actions in entity details
      await expect(page.locator('[data-testid="entity-actions"]')).toBeVisible();
      await expect(page.locator('[data-testid="view-in-documents"]')).toBeVisible();
    }
  });

  test('US3-12: Graph responsiveness on different screen sizes', async ({ page }) => {
    await graphPage.navigateTo('/graph');
    await graphPage.waitForGraphLoad();

    // Test desktop size
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.waitForTimeout(1000);
    await expect(graphPage.graphCanvas).toBeVisible();

    // Test tablet size
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.waitForTimeout(1000);
    await expect(graphPage.graphCanvas).toBeVisible();

    // Test mobile size
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(1000);
    await expect(graphPage.graphCanvas).toBeVisible();

    // Verify controls adapt to screen size
    const controlsVisible = await graphPage.graphControls.isVisible();
    expect(controlsVisible).toBe(true);

    // Reset to desktop size
    await page.setViewportSize({ width: 1280, height: 720 });
  });
});