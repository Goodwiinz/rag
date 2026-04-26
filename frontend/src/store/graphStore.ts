/**
 * Enhanced Graph Store - State Management for Knowledge Graph Data
 *
 * ARCHITECTURE COMPLIANCE: This store ONLY manages state.
 * NO graph processing or algorithm logic is included - only state management.
 * All computation is delegated to backend services.
 */

import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import {
  KnowledgeGraphData,
  GraphNode,
  GraphEdge,
  GraphFilters,
  EntityDetails,
  GraphAnalyticsDashboard,
  WebSocketGraphUpdate,
  GraphVisualizationState,
  PerformanceMetrics,
  GraphAnalyticsData
} from '../types/knowledge-graph';

// Enhanced State interface for graph data
interface GraphState {
  // Current graph data from backend
  graphData: KnowledgeGraphData | null;
  filters: GraphFilters;
  visualizationState: GraphVisualizationState;

  // Selected entities and relationships
  selectedNodes: Set<string>;
  selectedEdges: Set<string>;
  focusedEntity: string | null;
  highlightedNodes: Set<string>;
  highlightedEdges: Set<string>;

  // Entity details cache
  entityDetailsCache: Map<string, EntityDetails>;

  // Analytics data cache
  analyticsCache: Map<string, GraphAnalyticsDashboard>;

  // Search state
  searchQuery: string;
  searchResults: GraphNode[];
  searchLoading: boolean;

  // Layout state
  layoutAlgorithm: string;
  layoutLoading: boolean;

  // UI state
  isLoading: boolean;
  error: string | null;
  lastUpdated: string | null;

  // WebSocket connection status
  wsConnected: boolean;
  wsStatus: 'connecting' | 'connected' | 'disconnected' | 'error';

  // Performance metrics from backend
  performanceMetrics: PerformanceMetrics | null;

  // Batch operations state
  batchOperation: {
    inProgress: boolean;
    operationId?: string;
    progress: number;
    total: number;
  };
}

// Enhanced Actions interface for graph store
interface GraphActions {
  // Data loading actions
  setGraphData: (data: KnowledgeGraphData) => void;
  updateGraphData: (update: Partial<KnowledgeGraphData>) => void;
  clearGraphData: () => void;

  // Filter actions
  setFilters: (filters: Partial<GraphFilters>) => void;
  resetFilters: () => void;

  // Visualization state actions
  setVisualizationState: (state: Partial<GraphVisualizationState>) => void;
  updateViewport: (viewport: Partial<GraphVisualizationState['viewport']>) => void;
  setZoom: (zoom: number) => void;
  setPan: (x: number, y: number) => void;

  // Selection actions
  selectNode: (nodeId: string, multiSelect?: boolean) => void;
  deselectNode: (nodeId: string) => void;
  selectEdge: (edgeId: string, multiSelect?: boolean) => void;
  deselectEdge: (edgeId: string) => void;
  clearSelection: () => void;
  selectMultipleNodes: (nodeIds: string[]) => void;
  selectMultipleEdges: (edgeIds: string[]) => void;

  // Highlight actions
  highlightNode: (nodeId: string) => void;
  highlightEdge: (edgeId: string) => void;
  clearHighlights: () => void;
  highlightPath: (nodeIds: string[]) => void;

  // Focus actions
  focusEntity: (entityId: string) => void;
  clearFocus: () => void;

  // Entity cache actions
  cacheEntityDetails: (entityId: string, details: EntityDetails) => void;
  getCachedEntityDetails: (entityId: string) => EntityDetails | undefined;
  clearEntityCache: () => void;

  // Analytics cache actions
  cacheAnalytics: (key: string, data: GraphAnalyticsDashboard) => void;
  getCachedAnalytics: (key: string) => GraphAnalyticsDashboard | undefined;
  clearAnalyticsCache: () => void;

  // Search actions
  setSearchQuery: (query: string) => void;
  setSearchResults: (results: GraphNode[]) => void;
  clearSearch: () => void;
  setSearchLoading: (loading: boolean) => void;

  // Layout actions
  setLayoutAlgorithm: (algorithm: string) => void;
  setLayoutLoading: (loading: boolean) => void;

  // WebSocket actions
  setWebSocketStatus: (status: GraphState['wsStatus']) => void;
  setWebSocketConnected: (connected: boolean) => void;

  // WebSocket message handling - NO processing logic, just state updates
  handleWebSocketMessage: (message: WebSocketGraphUpdate) => void;

  // Performance actions
  setPerformanceMetrics: (metrics: PerformanceMetrics) => void;
  updatePerformanceMetric: (key: keyof PerformanceMetrics, value: any) => void;

  // Batch operations
  startBatchOperation: (operationId: string, total: number) => void;
  updateBatchProgress: (progress: number) => void;
  completeBatchOperation: () => void;

  // UI state actions
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;

  // Utility actions
  getNodeById: (nodeId: string) => GraphNode | undefined;
  getEdgeById: (edgeId: string) => GraphEdge | undefined;
  getSelectedNodes: () => GraphNode[];
  getSelectedEdges: () => GraphEdge[];
  getHighlightedNodes: () => GraphNode[];
  getHighlightedEdges: () => GraphEdge[];

  // Bulk operations - simple state updates only
  addNode: (node: GraphNode) => void;
  removeNode: (nodeId: string) => void;
  updateNode: (nodeId: string, updates: Partial<GraphNode>) => void;

  addEdge: (edge: GraphEdge) => void;
  removeEdge: (edgeId: string) => void;
  updateEdge: (edgeId: string, updates: Partial<GraphEdge>) => void;

  // Batch updates from WebSocket
  batchUpdateNodes: (nodes: GraphNode[]) => void;
  batchUpdateEdges: (edges: GraphEdge[]) => void;
}

// Enhanced initial state
const initialState: GraphState = {
  graphData: null,
  filters: {
    entity_types: [],
    relationship_types: [],
    min_confidence: 0.5,
    max_confidence: 1.0,
  },
  visualizationState: {
    viewport: {
      zoom: 1,
      pan: { x: 0, y: 0 },
      bounds: { minX: 0, minY: 0, maxX: 1000, maxY: 1000 }
    },
    selection: {
      nodes: new Set(),
      edges: new Set(),
      highlighted_nodes: new Set(),
      highlighted_edges: new Set()
    },
    rendering: {
      nodes_visible: 0,
      edges_visible: 0,
      fps: 0,
      render_time: 0
    },
    ui: {
      show_labels: true,
      show_analytics_overlay: false,
      color_scheme: 'default',
      layout_algorithm: 'force_directed',
      clustering_enabled: false
    }
  },
  selectedNodes: new Set(),
  selectedEdges: new Set(),
  focusedEntity: null,
  highlightedNodes: new Set(),
  highlightedEdges: new Set(),
  entityDetailsCache: new Map(),
  analyticsCache: new Map(),
  searchQuery: '',
  searchResults: [],
  searchLoading: false,
  layoutAlgorithm: 'force_directed',
  layoutLoading: false,
  isLoading: false,
  error: null,
  lastUpdated: null,
  wsConnected: false,
  wsStatus: 'disconnected',
  performanceMetrics: null,
  batchOperation: {
    inProgress: false,
    progress: 0,
    total: 0
  }
};

// Default filters
const defaultFilters: GraphFilters = {
  entity_types: [],
  relationship_types: [],
  min_confidence: 0.5,
  max_confidence: 1.0,
};

// Create the store
export const useGraphStore = create<GraphState & GraphActions>()(
  devtools(
    subscribeWithSelector(
      immer((set, get) => ({
        ...initialState,

        // Data loading actions
        setGraphData: (data) =>
          set((state) => {
            state.graphData = data;
            state.lastUpdated = new Date().toISOString();
            state.error = null;
          }),

        updateGraphData: (update) =>
          set((state) => {
            if (state.graphData) {
              Object.assign(state.graphData, update);
              state.lastUpdated = new Date().toISOString();
            }
          }),

        clearGraphData: () =>
          set((state) => {
            state.graphData = null;
            state.selectedNodes.clear();
            state.selectedEdges.clear();
            state.focusedEntity = null;
          }),

        // Filter actions
        setFilters: (filters) =>
          set((state) => {
            state.filters = { ...state.filters, ...filters };
          }),

        resetFilters: () =>
          set((state) => {
            state.filters = { ...defaultFilters };
          }),

        // Visualization state actions
        setVisualizationState: (stateUpdate) =>
          set((state) => {
            Object.assign(state.visualizationState, stateUpdate);
          }),

        updateViewport: (viewport) =>
          set((state) => {
            Object.assign(state.visualizationState.viewport, viewport);
          }),

        setZoom: (zoom) =>
          set((state) => {
            state.visualizationState.viewport.zoom = zoom;
          }),

        setPan: (x, y) =>
          set((state) => {
            state.visualizationState.viewport.pan.x = x;
            state.visualizationState.viewport.pan.y = y;
          }),

        // Highlight actions
        highlightNode: (nodeId) =>
          set((state) => {
            state.highlightedNodes.add(nodeId);
          }),

        highlightEdge: (edgeId) =>
          set((state) => {
            state.highlightedEdges.add(edgeId);
          }),

        clearHighlights: () =>
          set((state) => {
            state.highlightedNodes.clear();
            state.highlightedEdges.clear();
          }),

        highlightPath: (nodeIds) =>
          set((state) => {
            state.highlightedNodes.clear();
            nodeIds.forEach(id => state.highlightedNodes.add(id));
          }),

        // Search actions
        setSearchQuery: (query) =>
          set((state) => {
            state.searchQuery = query;
          }),

        setSearchResults: (results) =>
          set((state) => {
            state.searchResults = results;
          }),

        clearSearch: () =>
          set((state) => {
            state.searchQuery = '';
            state.searchResults = [];
          }),

        setSearchLoading: (loading) =>
          set((state) => {
            state.searchLoading = loading;
          }),

        // Layout actions
        setLayoutAlgorithm: (algorithm) =>
          set((state) => {
            state.layoutAlgorithm = algorithm;
            state.visualizationState.ui.layout_algorithm = algorithm;
          }),

        setLayoutLoading: (loading) =>
          set((state) => {
            state.layoutLoading = loading;
          }),

        // Performance actions
        setPerformanceMetrics: (metrics) =>
          set((state) => {
            state.performanceMetrics = metrics;
          }),

        updatePerformanceMetric: (key, value) =>
          set((state) => {
            if (state.performanceMetrics) {
              (state.performanceMetrics as any)[key] = value;
            }
          }),

        // Batch operations
        startBatchOperation: (operationId, total) =>
          set((state) => {
            state.batchOperation = {
              inProgress: true,
              operationId,
              progress: 0,
              total
            };
          }),

        updateBatchProgress: (progress) =>
          set((state) => {
            state.batchOperation.progress = progress;
          }),

        completeBatchOperation: () =>
          set((state) => {
            state.batchOperation = {
              inProgress: false,
              progress: 0,
              total: 0
            };
          }),

        // Utility actions
        getNodeById: (nodeId) => {
          const { graphData } = get();
          return graphData?.nodes.find(node => node.id === nodeId);
        },

        getEdgeById: (edgeId) => {
          const { graphData } = get();
          return graphData?.edges.find(edge => edge.id === edgeId);
        },

        getSelectedNodes: () => {
          const { graphData, selectedNodes } = get();
          if (!graphData) return [];
          return graphData.nodes.filter(node => selectedNodes.has(node.id));
        },

        getSelectedEdges: () => {
          const { graphData, selectedEdges } = get();
          if (!graphData) return [];
          return graphData.edges.filter(edge => selectedEdges.has(edge.id));
        },

        getHighlightedNodes: () => {
          const { graphData, highlightedNodes } = get();
          if (!graphData) return [];
          return graphData.nodes.filter(node => highlightedNodes.has(node.id));
        },

        getHighlightedEdges: () => {
          const { graphData, highlightedEdges } = get();
          if (!graphData) return [];
          return graphData.edges.filter(edge => highlightedEdges.has(edge.id));
        },

        // Batch updates from WebSocket
        batchUpdateNodes: (nodes) =>
          set((state) => {
            if (state.graphData) {
              nodes.forEach(node => {
                const existingIndex = state.graphData!.nodes.findIndex(n => n.id === node.id);
                if (existingIndex >= 0) {
                  state.graphData!.nodes[existingIndex] = node;
                } else {
                  state.graphData!.nodes.push(node);
                }
              });
            }
          }),

        batchUpdateEdges: (edges) =>
          set((state) => {
            if (state.graphData) {
              edges.forEach(edge => {
                const existingIndex = state.graphData!.edges.findIndex(e => e.id === edge.id);
                if (existingIndex >= 0) {
                  state.graphData!.edges[existingIndex] = edge;
                } else {
                  state.graphData!.edges.push(edge);
                }
              });
            }
          }),

        // Selection actions
        selectNode: (nodeId, multiSelect = false) =>
          set((state) => {
            if (!multiSelect) {
              state.selectedNodes.clear();
              state.selectedEdges.clear();
            }
            state.selectedNodes.add(nodeId);
          }),

        deselectNode: (nodeId) =>
          set((state) => {
            state.selectedNodes.delete(nodeId);
          }),

        selectEdge: (edgeId, multiSelect = false) =>
          set((state) => {
            if (!multiSelect) {
              state.selectedEdges.clear();
              state.selectedNodes.clear();
            }
            state.selectedEdges.add(edgeId);
          }),

        deselectEdge: (edgeId) =>
          set((state) => {
            state.selectedEdges.delete(edgeId);
          }),

        clearSelection: () =>
          set((state) => {
            state.selectedNodes.clear();
            state.selectedEdges.clear();
          }),

        selectMultipleNodes: (nodeIds) =>
          set((state) => {
            state.selectedNodes.clear();
            state.selectedEdges.clear();
            nodeIds.forEach(id => state.selectedNodes.add(id));
          }),

        selectMultipleEdges: (edgeIds) =>
          set((state) => {
            state.selectedEdges.clear();
            state.selectedNodes.clear();
            edgeIds.forEach(id => state.selectedEdges.add(id));
          }),

        // Focus actions
        focusEntity: (entityId) =>
          set((state) => {
            state.focusedEntity = entityId;
            state.selectedNodes.clear();
            state.selectedEdges.clear();
            state.selectedNodes.add(entityId);
          }),

        clearFocus: () =>
          set((state) => {
            state.focusedEntity = null;
          }),

        // Entity cache actions
        cacheEntityDetails: (entityId, details) =>
          set((state) => {
            state.entityDetailsCache.set(entityId, details);
          }),

        getCachedEntityDetails: (entityId) => {
          return get().entityDetailsCache.get(entityId);
        },

        clearEntityCache: () =>
          set((state) => {
            state.entityDetailsCache.clear();
          }),

        // Analytics cache actions
        cacheAnalytics: (key, data) =>
          set((state) => {
            state.analyticsCache.set(key, data);
          }),

        getCachedAnalytics: (key) => {
          return get().analyticsCache.get(key);
        },

        clearAnalyticsCache: () =>
          set((state) => {
            state.analyticsCache.clear();
          }),

        // WebSocket actions
        setWebSocketStatus: (status) =>
          set((state) => {
            state.wsStatus = status;
            state.wsConnected = status === 'connected';
          }),

        setWebSocketConnected: (connected) =>
          set((state) => {
            state.wsConnected = connected;
          }),

        // WebSocket message handling - NO processing logic, just state updates
        handleWebSocketMessage: (message) =>
          set((state) => {
            const { type, data } = message;

            switch (type) {
              case 'node_added':
                if (data.node && state.graphData) {
                  const existingNode = state.graphData.nodes.find(n => n.id === data.node.id);
                  if (!existingNode) {
                    state.graphData.nodes.push(data.node);
                  }
                }
                break;

              case 'node_removed':
                if (data.nodeId && state.graphData) {
                  state.graphData.nodes = state.graphData.nodes.filter(n => n.id !== data.nodeId);
                  state.graphData.edges = state.graphData.edges.filter(e =>
                    e.source !== data.nodeId && e.target !== data.nodeId
                  );
                  state.selectedNodes.delete(data.nodeId);
                }
                break;

              case 'edge_added':
                if (data.edge && state.graphData) {
                  const existingEdge = state.graphData.edges.find(e => e.id === data.edge.id);
                  if (!existingEdge) {
                    state.graphData.edges.push(data.edge);
                  }
                }
                break;

              case 'edge_removed':
                if (data.edgeId && state.graphData) {
                  state.graphData.edges = state.graphData.edges.filter(e => e.id !== data.edgeId);
                  state.selectedEdges.delete(data.edgeId);
                }
                break;

              case 'layout_updated':
                if (data.layout) {
                  state.graphData = data.layout;
                }
                break;

              case 'analytics_updated':
                if (data.analytics) {
                  // Update analytics cache with new data
                  const cacheKey = JSON.stringify(state.filters);
                  state.analyticsCache.set(cacheKey, data.analytics as GraphAnalyticsData);
                }
                break;
            }
          }),

        // UI state actions
        setLoading: (loading) =>
          set((state) => {
            state.isLoading = loading;
          }),

        setError: (error) =>
          set((state) => {
            state.error = error;
          }),

        clearError: () =>
          set((state) => {
            state.error = null;
          }),

        // Performance tracking
        updateRenderPerformance: (nodeCount, edgeCount, renderTime) =>
          set((state) => {
            state.renderPerformance = {
              nodeCount,
              edgeCount,
              renderTime,
              lastRendered: new Date().toISOString()
            };
          }),

        // Utility actions
        getNodeById: (nodeId) => {
          const { graphData } = get();
          return graphData?.nodes.find(node => node.id === nodeId);
        },

        getEdgeById: (edgeId) => {
          const { graphData } = get();
          return graphData?.edges.find(edge => edge.id === edgeId);
        },

        getSelectedNodes: () => {
          const { graphData, selectedNodes } = get();
          if (!graphData) return [];
          return graphData.nodes.filter(node => selectedNodes.has(node.id));
        },

        getSelectedEdges: () => {
          const { graphData, selectedEdges } = get();
          if (!graphData) return [];
          return graphData.edges.filter(edge => selectedEdges.has(edge.id));
        },

        // Bulk operations
        addNode: (node) =>
          set((state) => {
            if (state.graphData) {
              const existingNode = state.graphData.nodes.find(n => n.id === node.id);
              if (!existingNode) {
                state.graphData.nodes.push(node);
              }
            }
          }),

        removeNode: (nodeId) =>
          set((state) => {
            if (state.graphData) {
              state.graphData.nodes = state.graphData.nodes.filter(n => n.id !== nodeId);
              state.graphData.edges = state.graphData.edges.filter(e =>
                e.source !== nodeId && e.target !== nodeId
              );
              state.selectedNodes.delete(nodeId);
              if (state.focusedEntity === nodeId) {
                state.focusedEntity = null;
              }
            }
          }),

        updateNode: (nodeId, updates) =>
          set((state) => {
            if (state.graphData) {
              const node = state.graphData.nodes.find(n => n.id === nodeId);
              if (node) {
                Object.assign(node, updates);
              }
            }
          }),

        addEdge: (edge) =>
          set((state) => {
            if (state.graphData) {
              const existingEdge = state.graphData.edges.find(e => e.id === edge.id);
              if (!existingEdge) {
                state.graphData.edges.push(edge);
              }
            }
          }),

        removeEdge: (edgeId) =>
          set((state) => {
            if (state.graphData) {
              state.graphData.edges = state.graphData.edges.filter(e => e.id !== edgeId);
              state.selectedEdges.delete(edgeId);
            }
          }),

        updateEdge: (edgeId, updates) =>
          set((state) => {
            if (state.graphData) {
              const edge = state.graphData.edges.find(e => e.id === edgeId);
              if (edge) {
                Object.assign(edge, updates);
              }
            }
          })
      }))
    ),
    {
      name: 'graph-store'
    }
  )
);

// Selectors for common state combinations
export const useGraphData = () => useGraphStore((state) => state.graphData);
export const useGraphFilters = () => useGraphStore((state) => state.filters);
export const useVisualizationState = () => useGraphStore((state) => state.visualizationState);
export const useSelectedNodes = () => useGraphStore((state) => state.selectedNodes);
export const useSelectedEdges = () => useGraphStore((state) => state.selectedEdges);
export const useFocusedEntity = () => useGraphStore((state) => state.focusedEntity);
export const useHighlightedNodes = () => useGraphStore((state) => state.highlightedNodes);
export const useHighlightedEdges = () => useGraphStore((state) => state.highlightedEdges);
export const useGraphLoading = () => useGraphStore((state) => state.isLoading);
export const useGraphError = () => useGraphStore((state) => state.error);
export const useSearchState = () => useGraphStore((state) => ({
  query: state.searchQuery,
  results: state.searchResults,
  loading: state.searchLoading
}));
export const useLayoutState = () => useGraphStore((state) => ({
  algorithm: state.layoutAlgorithm,
  loading: state.layoutLoading
}));
export const useWebSocketStatus = () => useGraphStore((state) => ({
  connected: state.wsConnected,
  status: state.wsStatus
}));
export const usePerformanceMetrics = () => useGraphStore((state) => state.performanceMetrics);
export const useBatchOperation = () => useGraphStore((state) => state.batchOperation);

// Computed selectors
export const useSelectedNodeData = () => useGraphStore((state) => {
  if (!state.graphData) return [];
  return state.graphData.nodes.filter(node => state.selectedNodes.has(node.id));
});

export const useSelectedEdgeData = () => useGraphStore((state) => {
  if (!state.graphData) return [];
  return state.graphData.edges.filter(edge => state.selectedEdges.has(edge.id));
});

export const useHighlightedNodeData = () => useGraphStore((state) => {
  if (!state.graphData) return [];
  return state.graphData.nodes.filter(node => state.highlightedNodes.has(node.id));
});

export const useHighlightedEdgeData = () => useGraphStore((state) => {
  if (!state.graphData) return [];
  return state.graphData.edges.filter(edge => state.highlightedEdges.has(edge.id));
});

export const useGraphStats = () => useGraphStore((state) => {
  if (!state.graphData) {
    return {
      nodeCount: 0,
      edgeCount: 0,
      selectedNodeCount: state.selectedNodes.size,
      selectedEdgeCount: state.selectedEdges.size,
      highlightedNodeCount: state.highlightedNodes.size,
      highlightedEdgeCount: state.highlightedEdges.size
    };
  }

  return {
    nodeCount: state.graphData.nodes.length,
    edgeCount: state.graphData.edges.length,
    selectedNodeCount: state.selectedNodes.size,
    selectedEdgeCount: state.selectedEdges.size,
    highlightedNodeCount: state.highlightedNodes.size,
    highlightedEdgeCount: state.highlightedEdges.size
  };
});

export const useCachedEntityDetails = (entityId: string) =>
  useGraphStore((state) => state.entityDetailsCache.get(entityId));

export const useCachedAnalytics = (key: string) =>
  useGraphStore((state) => state.analyticsCache.get(key));