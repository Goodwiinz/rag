/**
 * Knowledge Graph Viewer Tests - Component Testing
 *
 * Tests verify visualization behavior without algorithm processing.
 * Focus on rendering, user interaction, and API data consumption.
 */

import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GraphWebSocketProvider } from '../GraphWebSocketProvider';
import { GraphAccessibilityProvider } from '../GraphAccessibilityProvider';
import KnowledgeGraphViewer from '../KnowledgeGraphViewer';
import { GraphLayoutData, GraphFilters } from '../../../types/graph-api';

// Mock services
vi.mock('../../../services/graphService');
vi.mock('../../../services/websocketService');

// Mock vis-network
vi.mock('vis-network/standalone', () => ({
  Network: vi.fn().mockImplementation(() => ({
    on: vi.fn(),
    setData: vi.fn(),
    fit: vi.fn(),
    moveNode: vi.fn()
  }))
}));

const mockGraphService = await import('../../../services/graphService');
const mockWebSocketService = await import('../../../services/websocketService');

describe('KnowledgeGraphViewer', () => {
  let queryClient: QueryClient;
  let mockGraphData: GraphLayoutData;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false }
      }
    });

    mockGraphData = {
      nodes: [
        {
          id: 'node1',
          label: 'Person 1',
          type: 'person',
          confidence: 0.9,
          metadata: {},
          position: { x: 100, y: 100 },
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          document_ids: ['doc1'],
          entity_count: 5
        },
        {
          id: 'node2',
          label: 'Organization 1',
          type: 'organization',
          confidence: 0.85,
          metadata: {},
          position: { x: 200, y: 200 },
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          document_ids: ['doc2'],
          entity_count: 3
        }
      ],
      edges: [
        {
          id: 'edge1',
          source: 'node1',
          target: 'node2',
          type: 'works_for',
          weight: 0.8,
          confidence: 0.9,
          metadata: {},
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          document_ids: ['doc1']
        }
      ],
      layout: {
        algorithm: 'force_directed',
        dimensions: { width: 800, height: 600 },
        bounds: { minX: 0, minY: 0, maxX: 800, maxY: 600 },
        parameters: {}
      },
      metadata: {
        total_nodes: 2,
        total_edges: 1,
        rendering_time_ms: 50,
        layout_algorithm: 'force_directed',
        generated_at: '2024-01-01T00:00:00Z'
      }
    };

    // Mock successful API responses
    vi.mocked(mockGraphService.graphService.getGraphData).mockResolvedValue(mockGraphData);
    vi.mocked(mockWebSocketService.websocketService.connectToGraphUpdates).mockResolvedValue({} as any);
    vi.mocked(mockWebSocketService.websocketService.subscribe).mockReturnValue(() => {});
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = (props = {}) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <GraphWebSocketProvider>
          <GraphAccessibilityProvider nodes={mockGraphData.nodes} edges={mockGraphData.edges}>
            <KnowledgeGraphViewer {...props} />
          </GraphAccessibilityProvider>
        </GraphWebSocketProvider>
      </QueryClientProvider>
    );
  };

  describe('Initial Rendering', () => {
    it('should render loading state initially', () => {
      // Mock API to delay response
      vi.mocked(mockGraphService.graphService.getGraphData).mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve(mockGraphData), 100))
      );

      renderComponent();

      expect(screen.getByText(/Loading graph data/i)).toBeInTheDocument();
    });

    it('should render graph when data is loaded', async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getByRole('img', { name: /knowledge graph visualization/i })).toBeInTheDocument();
      });

      // Verify the graph container is rendered
      const graphContainer = screen.getByRole('img');
      expect(graphContainer).toHaveClass('w-full', 'h-full', 'border', 'border-gray-200', 'rounded-lg');
    });

    it('should render error state when API fails', async () => {
      vi.mocked(mockGraphService.graphService.getGraphData).mockRejectedValue(
        new Error('API Error')
      );

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText(/Failed to load graph data/i)).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
    });
  });

  describe('API Integration', () => {
    it('should call graph service with correct filters', async () => {
      const filters: GraphFilters = {
        entity_types: ['person'],
        min_confidence: 0.5,
        limit: 100
      };

      renderComponent({ initialFilters: filters });

      await waitFor(() => {
        expect(mockGraphService.graphService.getGraphData).toHaveBeenCalledWith(filters);
      });
    });

    it('should refetch data when retry button is clicked', async () => {
      vi.mocked(mockGraphService.graphService.getGraphData).mockRejectedValueOnce(
        new Error('API Error')
      ).mockResolvedValueOnce(mockGraphData);

      renderComponent();

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /Retry/i }));

      await waitFor(() => {
        expect(mockGraphService.graphService.getGraphData).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('User Interaction', () => {
    it('should call onNodeClick when node is clicked', async () => {
      const onNodeClick = vi.fn();

      renderComponent({ onNodeClick });

      await waitFor(() => {
        expect(screen.getByRole('img')).toBeInTheDocument();
      });

      // Mock network click event
      const { Network } = await import('vis-network/standalone');
      const mockNetwork = vi.mocked(Network).mock.results[0].value;

      // Get the click handler
      const clickHandler = mockNetwork.on.mock.calls.find(
        call => call[0] === 'click'
      )?.[1];

      if (clickHandler) {
        clickHandler({ nodes: ['node1'], edges: [] });
        expect(onNodeClick).toHaveBeenCalledWith('node1');
      }
    });

    it('should call onEdgeClick when edge is clicked', async () => {
      const onEdgeClick = vi.fn();

      renderComponent({ onEdgeClick });

      await waitFor(() => {
        expect(screen.getByRole('img')).toBeInTheDocument();
      });

      const { Network } = await import('vis-network/standalone');
      const mockNetwork = vi.mocked(Network).mock.results[0].value;

      const clickHandler = mockNetwork.on.mock.calls.find(
        call => call[0] === 'click'
      )?.[1];

      if (clickHandler) {
        clickHandler({ nodes: [], edges: ['edge1'] });
        expect(onEdgeClick).toHaveBeenCalledWith('edge1');
      }
    });

    it('should call onSelectionChange when selection changes', async () => {
      const onSelectionChange = vi.fn();

      renderComponent({ onSelectionChange });

      await waitFor(() => {
        expect(screen.getByRole('img')).toBeInTheDocument();
      });

      const { Network } = await import('vis-network/standalone');
      const mockNetwork = vi.mocked(Network).mock.results[0].value;

      const selectHandler = mockNetwork.on.mock.calls.find(
        call => call[0] === 'selectNode'
      )?.[1];

      if (selectHandler) {
        selectHandler({ nodes: ['node1', 'node2'] });
        expect(onSelectionChange).toHaveBeenCalledWith(['node1', 'node2'], []);
      }
    });
  });

  describe('Configuration', () => {
    it('should apply custom configuration', async () => {
      const config = {
        layout_algorithm: 'circular' as const,
        physics_enabled: false,
        show_labels: false
      };

      renderComponent({ config });

      await waitFor(() => {
        expect(screen.getByRole('img')).toBeInTheDocument();
      });

      // Verify that the network is configured with custom settings
      const { Network } = await import('vis-network/standalone');
      const mockNetwork = vi.mocked(Network).mock.results[0].value;

      expect(mockNetwork).toHaveBeenCalledWith(
        expect.any(HTMLElement),
        expect.any(Object),
        expect.objectContaining({
          physics: { enabled: false },
          layout: { improvedLayout: false }
        })
      );
    });

    it('should use custom dimensions', () => {
      const { container } = renderComponent({
        width: '500px',
        height: '400px'
      });

      const graphContainer = container.querySelector('.knowledge-graph-viewer');
      expect(graphContainer).toHaveStyle({
        width: '500px',
        height: '400px'
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels', async () => {
      renderComponent();

      await waitFor(() => {
        expect(screen.getByRole('img', {
          name: /knowledge graph visualization/i
        })).toBeInTheDocument();
      });
    });

    it('should be keyboard accessible', async () => {
      renderComponent();

      await waitFor(() => {
        const graphContainer = screen.getByRole('img');
        expect(graphContainer).toHaveAttribute('tabIndex', '0');
      });
    });
  });

  describe('Performance', () => {
    it('should handle large graphs without blocking', async () => {
      const largeGraphData: GraphLayoutData = {
        ...mockGraphData,
        nodes: Array.from({ length: 1000 }, (_, i) => ({
          ...mockGraphData.nodes[0],
          id: `node${i}`,
          label: `Node ${i}`
        })),
        edges: Array.from({ length: 2000 }, (_, i) => ({
          ...mockGraphData.edges[0],
          id: `edge${i}`,
          source: `node${i % 1000}`,
          target: `node${(i + 1) % 1000}`
        }))
      };

      vi.mocked(mockGraphService.graphService.getGraphData).mockResolvedValue(largeGraphData);

      const startTime = performance.now();
      renderComponent();

      await waitFor(() => {
        expect(screen.getByRole('img')).toBeInTheDocument();
      });

      const endTime = performance.now();
      expect(endTime - startTime).toBeLessThan(1000); // Should render within 1 second
    });
  });

  describe('Error Handling', () => {
    it('should handle network errors gracefully', async () => {
      vi.mocked(mockGraphService.graphService.getGraphData).mockRejectedValue(
        new Error('Network Error')
      );

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText(/Failed to load graph data/i)).toBeInTheDocument();
        expect(screen.getByText(/Network Error/i)).toBeInTheDocument();
      });
    });

    it('should handle malformed data gracefully', async () => {
      const malformedData = {
        ...mockGraphData,
        nodes: null,
        edges: 'invalid'
      } as any;

      vi.mocked(mockGraphService.graphService.getGraphData).mockResolvedValue(malformedData);

      renderComponent();

      // Component should not crash, even with invalid data
      await waitFor(() => {
        expect(screen.getByRole('img')).toBeInTheDocument();
      });
    });
  });
});