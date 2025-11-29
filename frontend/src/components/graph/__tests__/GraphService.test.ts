/**
 * Graph Service Tests - API Consumption Testing
 *
 * Tests verify that frontend correctly consumes backend graph APIs.
 * NO algorithm testing - only API integration and data handling.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { graphService } from '../../../services/graphService';
import { GraphFilters, WebSocketGraphUpdate } from '../../../types/graph-api';

// Mock API client
vi.mock('../../../services/apiClient', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('GraphService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getGraphData', () => {
    it('should fetch graph layout data from backend API', async () => {
      const mockFilters: GraphFilters = {
        entity_types: ['person', 'organization'],
        min_confidence: 0.5,
        limit: 100
      };

      const mockResponse = {
        data: {
          nodes: [
            {
              id: 'node1',
              label: 'Person 1',
              type: 'person',
              confidence: 0.9,
              position: { x: 100, y: 100 },
              metadata: {},
              created_at: '2024-01-01T00:00:00Z',
              updated_at: '2024-01-01T00:00:00Z',
              document_ids: ['doc1'],
              entity_count: 5
            }
          ],
          edges: [
            {
              id: 'edge1',
              source: 'node1',
              target: 'node2',
              type: 'knows',
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
            total_nodes: 1,
            total_edges: 1,
            rendering_time_ms: 50,
            layout_algorithm: 'force_directed',
            generated_at: '2024-01-01T00:00:00Z'
          }
        }
      };

      const { apiClient } = await import('../../../services/apiClient');
      vi.mocked(apiClient.post).mockResolvedValue(mockResponse);

      const result = await graphService.getGraphData(mockFilters);

      expect(apiClient.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/layout'),
        expect.objectContaining({
          filters: mockFilters,
          layout_algorithm: 'force_directed',
          options: expect.objectContaining({
            dimensions: { width: 800, height: 600 },
            physics: { enabled: true },
            clustering: { enabled: true }
          })
        })
      );

      expect(result).toEqual(mockResponse.data);
    });

    it('should handle API errors gracefully', async () => {
      const { apiClient } = await import('../../../services/apiClient');
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Network error'));

      await expect(graphService.getGraphData({})).rejects.toThrow('Network error');
    });
  });

  describe('getEntityDetails', () => {
    it('should fetch entity details from backend', async () => {
      const entityId = 'test-entity';
      const mockResponse = {
        data: {
          entity: {
            id: entityId,
            label: 'Test Entity',
            type: 'person',
            confidence: 0.95
          },
          relationships: [],
          documents: [],
          related_entities: [],
          mention_contexts: []
        }
      };

      const { apiClient } = await import('../../../services/apiClient');
      vi.mocked(apiClient.get).mockResolvedValue(mockResponse);

      const result = await graphService.getEntityDetails(entityId);

      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining(`/api/v1/entities/${entityId}`),
        expect.objectContaining({
          params: expect.objectContaining({
            include_relationships: true,
            include_documents: true,
            include_related_entities: true,
            max_related_entities: 20,
            relationship_strength_threshold: 0.3
          })
        })
      );

      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('searchEntities', () => {
    it('should search entities using backend API', async () => {
      const query = 'test query';
      const mockResponse = {
        data: {
          entities: [
            {
              id: 'entity1',
              label: 'Test Entity 1',
              type: 'person',
              confidence: 0.9
            }
          ]
        }
      };

      const { apiClient } = await import('../../../services/apiClient');
      vi.mocked(apiClient.get).mockResolvedValue(mockResponse);

      const result = await graphService.searchEntities(query);

      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/entities/search'),
        expect.objectContaining({
          params: expect.objectContaining({
            query,
            limit: 50,
            ranking: 'semantic',
            include_metadata: true
          })
        })
      );

      expect(result).toEqual(mockResponse.data.entities);
    });
  });

  describe('getGraphAnalytics', () => {
    it('should fetch analytics data from backend', async () => {
      const mockResponse = {
        data: {
          centralities: [
            {
              nodeId: 'node1',
              degree: 5,
              betweenness: 0.3,
              closeness: 0.7,
              eigenvector: 0.8
            }
          ],
          communities: [
            {
              id: 'community1',
              nodes: ['node1'],
              modularity: 0.5
            }
          ],
          statistics: {
            total_nodes: 10,
            total_edges: 15,
            average_degree: 3.0,
            density: 0.3
          }
        }
      };

      const { apiClient } = await import('../../../services/apiClient');
      vi.mocked(apiClient.post).mockResolvedValue(mockResponse);

      const result = await graphService.getGraphAnalytics();

      expect(apiClient.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/analytics'),
        expect.objectContaining({
          metrics: ['centrality', 'community_detection', 'pathfinding', 'graph_statistics'],
          algorithms: expect.objectContaining({
            centrality: ['degree', 'betweenness', 'closeness', 'eigenvector'],
            community_detection: 'louvain',
            pathfinding: 'dijkstra'
          })
        })
      );

      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('exportGraph', () => {
    it('should export graph data in specified format', async () => {
      const format = 'json';
      const filters: GraphFilters = { limit: 100 };
      const mockBlob = new Blob(['test data'], { type: 'application/json' });

      const { apiClient } = await import('../../../services/apiClient');
      vi.mocked(apiClient.post).mockResolvedValue({ data: mockBlob });

      const result = await graphService.exportGraph(format, filters);

      expect(apiClient.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/export'),
        expect.objectContaining({
          format,
          filters,
          include_metadata: true,
          include_layout: true
        }),
        expect.objectContaining({
          responseType: 'blob'
        })
      );

      expect(result).toEqual(mockBlob);
    });
  });
});