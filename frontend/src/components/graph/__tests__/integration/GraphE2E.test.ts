/**
 * Graph E2E Tests - Integration Testing
 *
 * End-to-end tests verify complete graph functionality from API to UI.
 * Tests user journeys without validating algorithm implementations.
 */

import { test, expect } from '@playwright/test';
import { GraphLayoutData, GraphFilters } from '../../../../types/graph-api';

// Mock API responses for testing
const mockGraphData: GraphLayoutData = {
  nodes: [
    {
      id: 'person-1',
      label: 'John Doe',
      type: 'person',
      confidence: 0.95,
      metadata: { age: 30, location: 'New York' },
      position: { x: 100, y: 100 },
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      document_ids: ['doc-1', 'doc-2'],
      entity_count: 5
    },
    {
      id: 'org-1',
      label: 'Acme Corporation',
      type: 'organization',
      confidence: 0.9,
      metadata: { industry: 'Technology', founded: 2010 },
      position: { x: 300, y: 200 },
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      document_ids: ['doc-2', 'doc-3'],
      entity_count: 3
    },
    {
      id: 'location-1',
      label: 'New York',
      type: 'location',
      confidence: 0.98,
      metadata: { population: '8M', country: 'USA' },
      position: { x: 200, y: 300 },
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      document_ids: ['doc-1'],
      entity_count: 7
    }
  ],
  edges: [
    {
      id: 'edge-1',
      source: 'person-1',
      target: 'org-1',
      type: 'works_for',
      weight: 0.9,
      confidence: 0.95,
      metadata: { position: 'Senior Engineer', start_date: '2020-01-01' },
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      document_ids: ['doc-2']
    },
    {
      id: 'edge-2',
      source: 'person-1',
      target: 'location-1',
      type: 'lives_in',
      weight: 0.85,
      confidence: 0.9,
      metadata: { address: '123 Main St' },
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      document_ids: ['doc-1']
    },
    {
      id: 'edge-3',
      source: 'org-1',
      target: 'location-1',
      type: 'located_in',
      weight: 0.8,
      confidence: 0.85,
      metadata: { headquarters: true },
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      document_ids: ['doc-3']
    }
  ],
  layout: {
    algorithm: 'force_directed',
    dimensions: { width: 800, height: 600 },
    bounds: { minX: 0, minY: 0, maxX: 800, maxY: 600 },
    parameters: { iterations: 100 }
  },
  metadata: {
    total_nodes: 3,
    total_edges: 3,
    rendering_time_ms: 45,
    layout_algorithm: 'force_directed',
    generated_at: '2024-01-01T00:00:00Z'
  }
};

const mockEntityDetails = {
  entity: mockGraphData.nodes[0],
  relationships: mockGraphData.edges.filter(e => e.source === 'person-1' || e.target === 'person-1'),
  documents: [
    {
      id: 'doc-1',
      title: 'Employee Profile',
      snippet: 'John Doe works as a Senior Engineer...',
      page_number: 1,
      confidence: 0.9,
      relevance_score: 0.95
    }
  ],
  related_entities: [
    {
      entity: mockGraphData.nodes[1],
      relationship: mockGraphData.edges[0],
      strength: 0.9,
      similarity_score: 0.85
    }
  ],
  mention_contexts: [
    {
      document_id: 'doc-1',
      snippet: 'John Doe lives in New York',
      page_number: 1,
      confidence: 0.9,
      context_before: 'Employee information:',
      context_after: 'Contact details available.',
      position: { start: 0, end: 20 }
    }
  ],
  timeline: [
    {
      timestamp: '2024-01-01T00:00:00Z',
      type: 'created' as const,
      description: 'Entity created from document processing'
    }
  ]
};

const mockAnalyticsData = {
  centralities: [
    {
      nodeId: 'person-1',
      degree: 2,
      normalized_degree: 0.67,
      betweenness: 0.5,
      normalized_betweenness: 0.75,
      closeness: 0.8,
      normalized_closeness: 0.85,
      eigenvector: 0.7,
      normalized_eigenvector: 0.8,
      pageRank: 0.6,
      katz: 0.65
    }
  ],
  communities: [
    {
      communityId: 'community-1',
      nodeCount: 3,
      edgeCount: 3,
      density: 1.0,
      modularity: 0.3,
      dominantEntityType: 'person',
      averageConfidence: 0.94,
      topNodes: [
        { nodeId: 'person-1', centrality: 0.8, role: 'hub' as const }
      ],
      topRelationships: [
        { edgeId: 'edge-1', weight: 0.9, frequency: 5 }
      ],
      metadata: {
        color: '#ff6b6b',
        label: 'Primary Network',
        description: 'Main entity cluster'
      }
    }
  ],
  pathfinding: {
    shortest_paths: {
      'org-1-location-1': ['org-1', 'person-1', 'location-1']
    },
    all_pairs: {}
  },
  statistics: {
    total_nodes: 3,
    total_edges: 3,
    average_degree: 2.0,
    density: 1.0,
    clustering_coefficient: 1.0,
    connected_components: 1,
    largest_component_size: 3,
    average_path_length: 1.33,
    diameter: 2,
    assortativity: 0.0,
    transitivity: 1.0
  },
  timestamp: '2024-01-01T00:00:00Z',
  computation_time_ms: 120
};

// Setup API mocking
test.beforeEach(async ({ page }) => {
  // Intercept and mock API calls
  await page.route('**/api/v1/layout', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockGraphData)
    });
  });

  await page.route('**/api/v1/entities/person-1', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockEntityDetails)
    });
  });

  await page.route('**/api/v1/analytics', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mockAnalyticsData)
    });
  });

  await page.route('**/api/v1/entities/search', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        entities: mockGraphData.nodes.filter(node =>
          node.label.toLowerCase().includes(route.request().postDataJSON()?.query?.toLowerCase() || '')
        )
      })
    });
  });

  // Mock WebSocket connections
  await page.route('**/ws/**', (route) => {
    route.fulfill({
      status: 101,
      headers: {
        'Connection': 'Upgrade',
        'Upgrade': 'websocket'
      }
    });
  });
});

test.describe('Knowledge Graph E2E Tests', () => {
  test('should load and display graph visualization', async ({ page }) => {
    await page.goto('/knowledge-graph');

    // Wait for graph to load
    await expect(page.locator('[role="img"]')).toBeVisible();
    await expect(page.getByText('Loading graph data')).not.toBeVisible();

    // Verify graph container is present
    const graphContainer = page.locator('.knowledge-graph-viewer');
    await expect(graphContainer).toBeVisible();

    // Check that graph is rendered (vis-network creates canvas)
    const canvas = page.locator('canvas');
    await expect(canvas).toBeVisible();
  });

  test('should display entity details when node is clicked', async ({ page }) => {
    await page.goto('/knowledge-graph');

    // Wait for graph to load
    await page.locator('[role="img"]').waitFor();

    // Simulate clicking on a node (this would require mocking the vis-network click event)
    // For E2E, we might need to click on the canvas at specific coordinates
    await page.locator('canvas').click({ position: { x: 100, y: 100 } });

    // Wait for entity details panel to appear
    await expect(page.locator('.entity-details-panel')).toBeVisible();
    await expect(page.getByText('John Doe')).toBeVisible();
    await expect(page.getByText('person')).toBeVisible();

    // Verify entity information is displayed
    await expect(page.getByText('95.0%')).toBeVisible(); // Confidence
    await expect(page.getByText('2')).toBeVisible(); // Relationships
  });

  test('should apply filters and update graph', async ({ page }) => {
    await page.goto('/knowledge-graph');

    // Wait for initial load
    await page.locator('[role="img"]').waitFor();

    // Open filter panel
    await page.getByRole('button', { name: /filters/i }).click();

    // Apply entity type filter
    await page.getByLabel('Entity Types').selectOption('person');

    // Apply confidence filter
    await page.getByLabel('Min Confidence').fill('0.9');

    // Apply filters
    await page.getByRole('button', { name: /apply filters/i }).click();

    // Verify loading state
    await expect(page.getByText('Loading graph data')).toBeVisible();
    await expect(page.getByText('Loading graph data')).not.toBeVisible({ timeout: 5000 });

    // Graph should still be visible after filtering
    await expect(page.locator('[role="img"]')).toBeVisible();
  });

  test('should display analytics dashboard', async ({ page }) => {
    await page.goto('/knowledge-graph');

    // Navigate to analytics tab
    await page.getByRole('tab', { name: 'Analytics' }).click();

    // Wait for analytics to load
    await expect(page.getByText('Total Nodes')).toBeVisible();
    await expect(page.getByText('Total Edges')).toBeVisible();
    await expect(page.getByText('Average Degree')).toBeVisible();
    await expect(page.getByText('Graph Density')).toBeVisible();

    // Verify analytics data
    await expect(page.getByText('3')).toBeVisible(); // Total nodes
    await expect(page.getByText('3')).toBeVisible(); // Total edges
  });

  test('should search for entities', async ({ page }) => {
    await page.goto('/knowledge-graph');

    // Wait for graph to load
    await page.locator('[role="img"]').waitFor();

    // Enter search query
    await page.getByPlaceholder('Search entities...').fill('John');
    await page.getByRole('button', { name: /search/i }).click();

    // Verify search results are displayed
    await expect(page.getByText('John Doe')).toBeVisible();

    // Click on search result to focus entity
    await page.getByText('John Doe').click();

    // Verify entity is focused in graph
    await expect(page.locator('.entity-details-panel')).toBeVisible();
    await expect(page.getByText('John Doe')).toBeVisible();
  });

  test('should handle real-time updates via WebSocket', async ({ page }) => {
    await page.goto('/knowledge-graph');

    // Wait for initial load
    await page.locator('[role="img"]').waitFor();

    // Check WebSocket status indicator
    await expect(page.getByText('Connected')).toBeVisible();

    // Simulate WebSocket update (this would need to be done via page.addInitScript or similar)
    // For now, just verify the connection status is displayed
    const wsIndicator = page.locator('.websocket-status-indicator');
    await expect(wsIndicator).toBeVisible();
  });

  test('should be accessible via keyboard navigation', async ({ page }) => {
    await page.goto('/knowledge-graph');

    // Wait for graph to load
    await page.locator('[role="img"]').waitFor();

    // Tab to graph container
    await page.keyboard.press('Tab');

    // Verify graph container is focused
    await expect(page.locator('[role="img"]')).toBeFocused();

    // Navigate with arrow keys
    await page.keyboard.press('ArrowRight');

    // Verify focus changes (this would depend on implementation)
    // For now, just ensure no JavaScript errors occur
    await expect(page.locator('.knowledge-graph-viewer')).toBeVisible();
  });

  test('should export graph data', async ({ page }) => {
    await page.goto('/knowledge-graph');

    // Wait for graph to load
    await page.locator('[role="img"]').waitFor();

    // Click export button
    await page.getByRole('button', { name: /export/i }).click();

    // Select export format
    await page.getByLabel('Format').selectOption('json');

    // Confirm export
    await page.getByRole('button', { name: /download/i }).click();

    // Verify download started (this would need to verify download event)
    // For now, just ensure the export dialog appears
    await expect(page.getByText('Export Graph')).toBeVisible();
  });

  test('should handle responsive design on mobile', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    await page.goto('/knowledge-graph');

    // Wait for graph to load
    await page.locator('[role="img"]').waitFor();

    // Verify mobile layout
    await expect(page.locator('.responsive-graph-layout')).toBeVisible();

    // Controls should be at bottom on mobile
    const controls = page.locator('.responsive-graph-controls');
    await expect(controls).toBeVisible();

    // Filter panel should be full screen on mobile
    await page.getByRole('button', { name: /filters/i }).click();
    await expect(page.locator('.responsive-filter-panel')).toBeVisible();
  });

  test('should handle performance with large graphs', async ({ page }) => {
    // Mock large graph data
    const largeGraphData = {
      ...mockGraphData,
      nodes: Array.from({ length: 500 }, (_, i) => ({
        ...mockGraphData.nodes[0],
        id: `node-${i}`,
        label: `Node ${i}`,
        position: { x: Math.random() * 800, y: Math.random() * 600 }
      })),
      edges: Array.from({ length: 1000 }, (_, i) => ({
        ...mockGraphData.edges[0],
        id: `edge-${i}`,
        source: `node-${i % 500}`,
        target: `node-${(i + 1) % 500}`
      }))
    };

    await page.route('**/api/v1/layout', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(largeGraphData)
      });
    });

    const startTime = Date.now();
    await page.goto('/knowledge-graph');

    // Wait for graph to load
    await page.locator('[role="img"]').waitFor();

    const loadTime = Date.now() - startTime;

    // Should load within reasonable time (less than 5 seconds)
    expect(loadTime).toBeLessThan(5000);

    // Verify graph is still interactive
    await page.locator('canvas').click({ position: { x: 400, y: 300 } });
    await expect(page.locator('.knowledge-graph-viewer')).toBeVisible();
  });

  test('should handle error states gracefully', async ({ page }) => {
    // Mock API error
    await page.route('**/api/v1/layout', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal Server Error' })
      });
    });

    await page.goto('/knowledge-graph');

    // Should display error state
    await expect(page.getByText('Failed to load graph data')).toBeVisible();
    await expect(page.getByRole('button', { name: /retry/i })).toBeVisible();

    // Click retry button
    await page.getByRole('button', { name: /retry/i }).click();

    // Should still show error state (since we're still mocking the error)
    await expect(page.getByText('Failed to load graph data')).toBeVisible();
  });

  test('should support accessibility features', async ({ page }) => {
    await page.goto('/knowledge-graph');

    // Wait for graph to load
    await page.locator('[role="img"]').waitFor();

    // Open accessibility controls
    await page.getByRole('button', { name: /accessibility/i }).click();

    // Enable high contrast mode
    await page.getByLabel('High Contrast').click();

    // Verify high contrast is applied
    await expect(page.locator('.high-contrast')).toBeVisible();

    // Change font size
    await page.getByLabel('Font Size').selectOption('large');

    // Verify font size change
    await expect(page.locator('.font-large')).toBeVisible();

    // Enable reduced motion
    await page.getByLabel('Reduced Motion').click();

    // Verify reduced motion is applied
    await expect(page.locator('.reduced-motion')).toBeVisible();

    // Test screen reader support
    await expect(page.locator('[role="status"]')).toBeVisible();
  });
});

test.describe('Graph Performance Tests', () => {
  test('should maintain performance with real-time updates', async ({ page }) => {
    await page.goto('/knowledge-graph');

    // Wait for initial load
    await page.locator('[role="img"]').waitFor();

    // Simulate multiple rapid WebSocket updates
    const updateCount = 10;
    const startTime = Date.now();

    for (let i = 0; i < updateCount; i++) {
      // Simulate node addition
      await page.evaluate(() => {
        window.postMessage({
          type: 'node_added',
          timestamp: new Date().toISOString(),
          data: {
            node: {
              id: `dynamic-node-${i}`,
              label: `Dynamic Node ${i}`,
              type: 'person',
              confidence: 0.9,
              position: { x: Math.random() * 800, y: Math.random() * 600 }
            }
          }
        }, '*');
      });

      // Small delay between updates
      await page.waitForTimeout(100);
    }

    const totalTime = Date.now() - startTime;

    // Should handle updates efficiently
    expect(totalTime).toBeLessThan(3000); // 3 seconds for 10 updates

    // Graph should still be responsive
    await expect(page.locator('[role="img"]')).toBeVisible();
  });

  test('should handle memory usage with large datasets', async ({ page }) => {
    // Enable memory monitoring
    await page.goto('/knowledge-graph');

    // Get initial memory usage
    const initialMemory = await page.evaluate(() => {
      return (performance as any).memory?.usedJSHeapSize || 0;
    });

    // Load large graph
    const largeGraphData = {
      ...mockGraphData,
      nodes: Array.from({ length: 1000 }, (_, i) => ({
        ...mockGraphData.nodes[0],
        id: `node-${i}`,
        label: `Node ${i}`,
        position: { x: Math.random() * 800, y: Math.random() * 600 }
      }))
    };

    await page.route('**/api/v1/layout', (route) => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(largeGraphData)
      });
    });

    await page.reload();
    await page.locator('[role="img"]').waitFor();

    // Get memory usage after loading
    const finalMemory = await page.evaluate(() => {
      return (performance as any).memory?.usedJSHeapSize || 0;
    });

    const memoryIncrease = finalMemory - initialMemory;

    // Memory increase should be reasonable (less than 50MB)
    expect(memoryIncrease).toBeLessThan(50 * 1024 * 1024);
  });
});