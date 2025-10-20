/**
 * Graph Store Tests - State Management Testing
 *
 * Tests verify state management works correctly with API data.
 * Focus on state updates, caching, and data flow - no algorithm testing.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useGraphStore } from '../../../stores/graphStore';
import { GraphLayoutData, GraphNode, GraphEdge } from '../../../types/graph-api';

describe('Graph Store', () => {
  let mockGraphData: GraphLayoutData;
  let mockNode: GraphNode;
  let mockEdge: GraphEdge;

  beforeEach(() => {
    // Reset store before each test
    useGraphStore.getState().clearGraphData();
    useGraphStore.getState().clearEntityCache();
    useGraphStore.getState().clearAnalyticsCache();

    mockNode = {
      id: 'test-node-1',
      label: 'Test Node',
      type: 'person',
      confidence: 0.9,
      metadata: { source: 'test' },
      position: { x: 100, y: 100 },
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      document_ids: ['doc1'],
      entity_count: 5
    };

    mockEdge = {
      id: 'test-edge-1',
      source: 'test-node-1',
      target: 'test-node-2',
      type: 'knows',
      weight: 0.8,
      confidence: 0.9,
      metadata: { strength: 'strong' },
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      document_ids: ['doc1']
    };

    mockGraphData = {
      nodes: [mockNode],
      edges: [mockEdge],
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
    };
  });

  describe('Graph Data Management', () => {
    it('should set graph data correctly', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.setGraphData(mockGraphData);
      });

      expect(result.current.graphData).toEqual(mockGraphData);
      expect(result.current.lastUpdated).toBeTruthy();
      expect(result.current.error).toBeNull();
    });

    it('should update graph data partially', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.setGraphData(mockGraphData);
      });

      const update = {
        layout: {
          ...mockGraphData.layout,
          algorithm: 'circular'
        }
      };

      act(() => {
        result.current.updateGraphData(update);
      });

      expect(result.current.graphData?.layout.algorithm).toBe('circular');
      expect(result.current.graphData?.nodes).toEqual(mockGraphData.nodes); // Unchanged
    });

    it('should clear graph data', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.setGraphData(mockGraphData);
        result.current.selectNode('test-node-1');
        result.current.selectEdge('test-edge-1');
      });

      expect(result.current.selectedNodes.has('test-node-1')).toBe(true);
      expect(result.current.selectedEdges.has('test-edge-1')).toBe(true);

      act(() => {
        result.current.clearGraphData();
      });

      expect(result.current.graphData).toBeNull();
      expect(result.current.selectedNodes.size).toBe(0);
      expect(result.current.selectedEdges.size).toBe(0);
      expect(result.current.focusedEntity).toBeNull();
    });
  });

  describe('Filter Management', () => {
    it('should set filters correctly', () => {
      const { result } = renderHook(() => useGraphStore());

      const filters = {
        entity_types: ['person', 'organization'],
        min_confidence: 0.7,
        limit: 100
      };

      act(() => {
        result.current.setFilters(filters);
      });

      expect(result.current.filters).toEqual(expect.objectContaining(filters));
    });

    it('should merge filters with existing ones', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.setFilters({ entity_types: ['person'] });
      });

      act(() => {
        result.current.setFilters({ min_confidence: 0.8 });
      });

      expect(result.current.filters).toEqual({
        entity_types: ['person'],
        min_confidence: 0.8
      });
    });

    it('should reset filters to defaults', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.setFilters({
          entity_types: ['person'],
          min_confidence: 0.9,
          limit: 500
        });
      });

      act(() => {
        result.current.resetFilters();
      });

      expect(result.current.filters).toEqual({
        min_confidence: 0.5,
        min_weight: 0.1,
        limit: 1000
      });
    });
  });

  describe('Selection Management', () => {
    beforeEach(() => {
      const { result } = renderHook(() => useGraphStore());
      act(() => {
        result.current.setGraphData(mockGraphData);
      });
    });

    it('should select single node', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.selectNode('test-node-1');
      });

      expect(result.current.selectedNodes.has('test-node-1')).toBe(true);
      expect(result.current.selectedNodes.size).toBe(1);
      expect(result.current.selectedEdges.size).toBe(0);
    });

    it('should select multiple nodes with multiSelect', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.selectNode('test-node-1', true);
      });

      act(() => {
        result.current.selectNode('test-node-2', true);
      });

      expect(result.current.selectedNodes.has('test-node-1')).toBe(true);
      expect(result.current.selectedNodes.has('test-node-2')).toBe(true);
      expect(result.current.selectedNodes.size).toBe(2);
    });

    it('should deselect nodes', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.selectNode('test-node-1');
      });

      expect(result.current.selectedNodes.has('test-node-1')).toBe(true);

      act(() => {
        result.current.deselectNode('test-node-1');
      });

      expect(result.current.selectedNodes.has('test-node-1')).toBe(false);
    });

    it('should clear all selections', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.selectNode('test-node-1', true);
        result.current.selectNode('test-node-2', true);
        result.current.selectEdge('test-edge-1', true);
      });

      expect(result.current.selectedNodes.size).toBe(2);
      expect(result.current.selectedEdges.size).toBe(1);

      act(() => {
        result.current.clearSelection();
      });

      expect(result.current.selectedNodes.size).toBe(0);
      expect(result.current.selectedEdges.size).toBe(0);
    });
  });

  describe('Focus Management', () => {
    it('should focus on entity', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.focusEntity('test-node-1');
      });

      expect(result.current.focusedEntity).toBe('test-node-1');
      expect(result.current.selectedNodes.has('test-node-1')).toBe(true);
    });

    it('should clear focus', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.focusEntity('test-node-1');
      });

      expect(result.current.focusedEntity).toBe('test-node-1');

      act(() => {
        result.current.clearFocus();
      });

      expect(result.current.focusedEntity).toBeNull();
    });
  });

  describe('Entity Cache Management', () => {
    it('should cache entity details', () => {
      const { result } = renderHook(() => useGraphStore());

      const entityDetails = {
        entity: mockNode,
        relationships: [mockEdge],
        documents: [],
        related_entities: [],
        mention_contexts: [],
        timeline: []
      };

      act(() => {
        result.current.cacheEntityDetails('test-node-1', entityDetails);
      });

      const cached = result.current.getCachedEntityDetails('test-node-1');
      expect(cached).toEqual(entityDetails);
    });

    it('should return undefined for non-cached entity', () => {
      const { result } = renderHook(() => useGraphStore());

      const cached = result.current.getCachedEntityDetails('non-existent');
      expect(cached).toBeUndefined();
    });

    it('should clear entity cache', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.cacheEntityDetails('test-node-1', {} as any);
      });

      expect(result.current.entityDetailsCache.size).toBe(1);

      act(() => {
        result.current.clearEntityCache();
      });

      expect(result.current.entityDetailsCache.size).toBe(0);
    });
  });

  describe('WebSocket Message Handling', () => {
    beforeEach(() => {
      const { result } = renderHook(() => useGraphStore());
      act(() => {
        result.current.setGraphData(mockGraphData);
      });
    });

    it('should handle node added message', () => {
      const { result } = renderHook(() => useGraphStore());

      const newNode: GraphNode = {
        ...mockNode,
        id: 'new-node',
        label: 'New Node'
      };

      const message = {
        type: 'node_added' as const,
        timestamp: '2024-01-01T00:00:00Z',
        data: { node: newNode }
      };

      act(() => {
        result.current.handleWebSocketMessage(message);
      });

      expect(result.current.graphData?.nodes).toHaveLength(2);
      expect(result.current.graphData?.nodes.find(n => n.id === 'new-node')).toEqual(newNode);
    });

    it('should handle node removed message', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.selectNode('test-node-1');
      });

      const message = {
        type: 'node_removed' as const,
        timestamp: '2024-01-01T00:00:00Z',
        data: { nodeId: 'test-node-1' }
      };

      act(() => {
        result.current.handleWebSocketMessage(message);
      });

      expect(result.current.graphData?.nodes).toHaveLength(0);
      expect(result.current.selectedNodes.has('test-node-1')).toBe(false);
    });

    it('should handle edge added message', () => {
      const { result } = renderHook(() => useGraphStore());

      const newEdge: GraphEdge = {
        ...mockEdge,
        id: 'new-edge',
        source: 'test-node-1',
        target: 'test-node-3'
      };

      const message = {
        type: 'edge_added' as const,
        timestamp: '2024-01-01T00:00:00Z',
        data: { edge: newEdge }
      };

      act(() => {
        result.current.handleWebSocketMessage(message);
      });

      expect(result.current.graphData?.edges).toHaveLength(2);
      expect(result.current.graphData?.edges.find(e => e.id === 'new-edge')).toEqual(newEdge);
    });

    it('should handle layout updated message', () => {
      const { result } = renderHook(() => useGraphStore());

      const newLayout: GraphLayoutData = {
        ...mockGraphData,
        layout: {
          ...mockGraphData.layout,
          algorithm: 'circular'
        }
      };

      const message = {
        type: 'layout_updated' as const,
        timestamp: '2024-01-01T00:00:00Z',
        data: { layout: newLayout }
      };

      act(() => {
        result.current.handleWebSocketMessage(message);
      });

      expect(result.current.graphData?.layout.algorithm).toBe('circular');
    });
  });

  describe('Bulk Operations', () => {
    beforeEach(() => {
      const { result } = renderHook(() => useGraphStore());
      act(() => {
        result.current.setGraphData(mockGraphData);
      });
    });

    it('should add node to existing graph', () => {
      const { result } = renderHook(() => useGraphStore());

      const newNode: GraphNode = {
        ...mockNode,
        id: 'additional-node',
        label: 'Additional Node'
      };

      act(() => {
        result.current.addNode(newNode);
      });

      expect(result.current.graphData?.nodes).toHaveLength(2);
      expect(result.current.graphData?.nodes.find(n => n.id === 'additional-node')).toEqual(newNode);
    });

    it('should not add duplicate node', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.addNode(mockNode); // Same ID as existing
      });

      expect(result.current.graphData?.nodes).toHaveLength(1);
    });

    it('should remove node and connected edges', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.selectNode('test-node-1');
      });

      act(() => {
        result.current.removeNode('test-node-1');
      });

      expect(result.current.graphData?.nodes).toHaveLength(0);
      expect(result.current.graphData?.edges).toHaveLength(0);
      expect(result.current.selectedNodes.has('test-node-1')).toBe(false);
    });

    it('should update node properties', () => {
      const { result } = renderHook(() => useGraphStore());

      const updates = {
        label: 'Updated Node',
        confidence: 0.95
      };

      act(() => {
        result.current.updateNode('test-node-1', updates);
      });

      const updatedNode = result.current.graphData?.nodes.find(n => n.id === 'test-node-1');
      expect(updatedNode?.label).toBe('Updated Node');
      expect(updatedNode?.confidence).toBe(0.95);
    });

    it('should add edge to existing graph', () => {
      const { result } = renderHook(() => useGraphStore());

      const newEdge: GraphEdge = {
        ...mockEdge,
        id: 'additional-edge',
        source: 'test-node-1',
        target: 'test-node-2'
      };

      act(() => {
        result.current.addEdge(newEdge);
      });

      expect(result.current.graphData?.edges).toHaveLength(2);
      expect(result.current.graphData?.edges.find(e => e.id === 'additional-edge')).toEqual(newEdge);
    });

    it('should remove edge', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.selectEdge('test-edge-1');
      });

      act(() => {
        result.current.removeEdge('test-edge-1');
      });

      expect(result.current.graphData?.edges).toHaveLength(0);
      expect(result.current.selectedEdges.has('test-edge-1')).toBe(false);
    });
  });

  describe('Utility Functions', () => {
    beforeEach(() => {
      const { result } = renderHook(() => useGraphStore());
      act(() => {
        result.current.setGraphData(mockGraphData);
      });
    });

    it('should get node by ID', () => {
      const { result } = renderHook(() => useGraphStore());

      const node = result.current.getNodeById('test-node-1');
      expect(node).toEqual(mockNode);
    });

    it('should return undefined for non-existent node', () => {
      const { result } = renderHook(() => useGraphStore());

      const node = result.current.getNodeById('non-existent');
      expect(node).toBeUndefined();
    });

    it('should get edge by ID', () => {
      const { result } = renderHook(() => useGraphStore());

      const edge = result.current.getEdgeById('test-edge-1');
      expect(edge).toEqual(mockEdge);
    });

    it('should get selected node data', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.selectNode('test-node-1');
      });

      const selectedNodes = result.current.getSelectedNodes();
      expect(selectedNodes).toHaveLength(1);
      expect(selectedNodes[0]).toEqual(mockNode);
    });

    it('should get selected edge data', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.selectEdge('test-edge-1');
      });

      const selectedEdges = result.current.getSelectedEdges();
      expect(selectedEdges).toHaveLength(1);
      expect(selectedEdges[0]).toEqual(mockEdge);
    });
  });

  describe('Performance Tracking', () => {
    it('should update render performance metrics', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.updateRenderPerformance(100, 200, 50);
      });

      expect(result.current.renderPerformance).toEqual({
        nodeCount: 100,
        edgeCount: 200,
        renderTime: 50,
        lastRendered: expect.any(String)
      });
    });
  });

  describe('Error and Loading States', () => {
    it('should set loading state', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.setLoading(true);
      });

      expect(result.current.isLoading).toBe(true);

      act(() => {
        result.current.setLoading(false);
      });

      expect(result.current.isLoading).toBe(false);
    });

    it('should set error state', () => {
      const { result } = renderHook(() => useGraphStore());

      act(() => {
        result.current.setError('Test error');
      });

      expect(result.current.error).toBe('Test error');

      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });
  });
});