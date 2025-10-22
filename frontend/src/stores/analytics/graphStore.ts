import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { GraphNode, GraphEdge } from './analyticsStore';

interface GraphVisualizationState {
  // Graph Layout
  layout: 'force' | 'hierarchical' | 'circular' | 'grid';
  layoutConfig: Record<string, any>;

  // Visualization Settings
  nodeSize: 'uniform' | 'degree' | 'property';
  edgeWidth: 'uniform' | 'weight';
  colorScheme: 'type' | 'property' | 'community';

  // Interaction State
  hoveredNode: string | null;
  hoveredEdge: string | null;
  draggedNode: string | null;

  // Viewport State
  zoom: number;
  pan: { x: number; y: number };

  // Clustering
  clusters: Record<string, string[]>;
  showClusters: boolean;

  // Filters
  nodeTypeFilter: string[];
  minDegreeFilter: number;
  maxDegreeFilter: number;
  timeFilter: { start: string; end: string } | null;

  // Search
  searchQuery: string;
  searchResults: string[];

  // History
  history: {
    nodes: GraphNode[];
    edges: GraphEdge[];
    timestamp: string;
  }[];
  historyIndex: number;

  // Performance
  renderThreshold: number;
  simplifyLargeGraphs: boolean;
}

interface GraphVisualizationActions {
  // Layout Management
  setLayout: (layout: GraphVisualizationState['layout']) => void;
  updateLayoutConfig: (config: Partial<GraphVisualizationState['layoutConfig']>) => void;

  // Visualization Settings
  setNodeSize: (size: GraphVisualizationState['nodeSize']) => void;
  setEdgeWidth: (width: GraphVisualizationState['edgeWidth']) => void;
  setColorScheme: (scheme: GraphVisualizationState['colorScheme']) => void;

  // Interaction Management
  setHoveredNode: (nodeId: string | null) => void;
  setHoveredEdge: (edgeId: string | null) => void;
  setDraggedNode: (nodeId: string | null) => void;

  // Viewport Management
  setZoom: (zoom: number) => void;
  setPan: (pan: { x: number; y: number }) => void;
  resetViewport: () => void;
  fitToView: () => void;

  // Clustering
  generateClusters: (algorithm: 'louvain' | 'label-propagation' | 'walktrap') => void;
  setClusters: (clusters: Record<string, string[]>) => void;
  toggleClusters: () => void;

  // Filtering
  setNodeTypeFilter: (types: string[]) => void;
  setDegreeFilter: (min: number, max: number) => void;
  setTimeFilter: (filter: { start: string; end: string } | null) => void;
  clearAllFilters: () => void;

  // Search
  setSearchQuery: (query: string) => void;
  setSearchResults: (results: string[]) => void;
  clearSearch: () => void;

  // History Management
  saveToHistory: (nodes: GraphNode[], edges: GraphEdge[]) => void;
  undo: () => void;
  redo: () => void;
  clearHistory: () => void;

  // Performance
  setRenderThreshold: (threshold: number) => void;
  toggleSimplification: () => void;

  // Graph Analysis
  calculateNodeDegrees: () => Record<string, number>;
  calculateBetweenness: () => Record<string, number>;
  calculatePageRank: () => Record<string, number>;
  detectCommunities: () => Record<string, string[]>;
  findShortestPath: (source: string, target: string) => string[] | null;
}

export const useGraphVisualizationStore = create<GraphVisualizationState & GraphVisualizationActions>()(
  devtools(
    (set, get) => ({
      // Initial State
      layout: 'force',
      layoutConfig: {
        force: {
          strength: -300,
          linkDistance: 100,
          chargeStrength: -300,
          collideRadius: 30,
        },
        hierarchical: {
          direction: 'TB',
          nodeSpacing: 100,
          levelSpacing: 150,
        },
      },
      nodeSize: 'degree',
      edgeWidth: 'uniform',
      colorScheme: 'type',
      hoveredNode: null,
      hoveredEdge: null,
      draggedNode: null,
      zoom: 1,
      pan: { x: 0, y: 0 },
      clusters: {},
      showClusters: false,
      nodeTypeFilter: [],
      minDegreeFilter: 0,
      maxDegreeFilter: Infinity,
      timeFilter: null,
      searchQuery: '',
      searchResults: [],
      history: [],
      historyIndex: -1,
      renderThreshold: 1000,
      simplifyLargeGraphs: true,

      // Layout Management
      setLayout: (layout) => set({ layout }, false, 'setLayout'),
      updateLayoutConfig: (config) =>
        set(
          (state) => ({
            layoutConfig: { ...state.layoutConfig, [state.layout]: { ...state.layoutConfig[state.layout], ...config } },
          }),
          false,
          'updateLayoutConfig'
        ),

      // Visualization Settings
      setNodeSize: (nodeSize) => set({ nodeSize }, false, 'setNodeSize'),
      setEdgeWidth: (edgeWidth) => set({ edgeWidth }, false, 'setEdgeWidth'),
      setColorScheme: (colorScheme) => set({ colorScheme }, false, 'setColorScheme'),

      // Interaction Management
      setHoveredNode: (hoveredNode) => set({ hoveredNode }, false, 'setHoveredNode'),
      setHoveredEdge: (hoveredEdge) => set({ hoveredEdge }, false, 'setHoveredEdge'),
      setDraggedNode: (draggedNode) => set({ draggedNode }, false, 'setDraggedNode'),

      // Viewport Management
      setZoom: (zoom) => set({ zoom }, false, 'setZoom'),
      setPan: (pan) => set({ pan }, false, 'setPan'),
      resetViewport: () => set({ zoom: 1, pan: { x: 0, y: 0 } }, false, 'resetViewport'),
      fitToView: () => {
        // Implementation would calculate bounds and adjust viewport
        console.log('Fitting graph to view');
      },

      // Clustering
      generateClusters: (algorithm) => {
        // Implementation would call clustering algorithm
        console.log('Generating clusters with algorithm:', algorithm);
        set({ clusters: {} }, false, 'generateClusters');
      },
      setClusters: (clusters) => set({ clusters }, false, 'setClusters'),
      toggleClusters: () =>
        set(
          (state) => ({ showClusters: !state.showClusters }),
          false,
          'toggleClusters'
        ),

      // Filtering
      setNodeTypeFilter: (nodeTypeFilter) => set({ nodeTypeFilter }, false, 'setNodeTypeFilter'),
      setDegreeFilter: (minDegreeFilter, maxDegreeFilter) =>
        set({ minDegreeFilter, maxDegreeFilter }, false, 'setDegreeFilter'),
      setTimeFilter: (timeFilter) => set({ timeFilter }, false, 'setTimeFilter'),
      clearAllFilters: () =>
        set(
          {
            nodeTypeFilter: [],
            minDegreeFilter: 0,
            maxDegreeFilter: Infinity,
            timeFilter: null,
          },
          false,
          'clearAllFilters'
        ),

      // Search
      setSearchQuery: (searchQuery) => set({ searchQuery }, false, 'setSearchQuery'),
      setSearchResults: (searchResults) => set({ searchResults }, false, 'setSearchResults'),
      clearSearch: () => set({ searchQuery: '', searchResults: [] }, false, 'clearSearch'),

      // History Management
      saveToHistory: (nodes, edges) =>
        set(
          (state) => {
            const newHistory = state.history.slice(0, state.historyIndex + 1);
            newHistory.push({
              nodes: [...nodes],
              edges: [...edges],
              timestamp: new Date().toISOString(),
            });

            // Keep only last 50 states
            if (newHistory.length > 50) {
              newHistory.shift();
            }

            return {
              history: newHistory,
              historyIndex: newHistory.length - 1,
            };
          },
          false,
          'saveToHistory'
        ),
      undo: () =>
        set(
          (state) => ({
            historyIndex: Math.max(0, state.historyIndex - 1),
          }),
          false,
          'undo'
        ),
      redo: () =>
        set(
          (state) => ({
            historyIndex: Math.min(state.history.length - 1, state.historyIndex + 1),
          }),
          false,
          'redo'
        ),
      clearHistory: () => set({ history: [], historyIndex: -1 }, false, 'clearHistory'),

      // Performance
      setRenderThreshold: (renderThreshold) => set({ renderThreshold }, false, 'setRenderThreshold'),
      toggleSimplification: () =>
        set(
          (state) => ({ simplifyLargeGraphs: !state.simplifyLargeGraphs }),
          false,
          'toggleSimplification'
        ),

      // Graph Analysis (placeholder implementations)
      calculateNodeDegrees: () => {
        console.log('Calculating node degrees');
        return {};
      },
      calculateBetweenness: () => {
        console.log('Calculating betweenness centrality');
        return {};
      },
      calculatePageRank: () => {
        console.log('Calculating PageRank');
        return {};
      },
      detectCommunities: () => {
        console.log('Detecting communities');
        return {};
      },
      findShortestPath: (source, target) => {
        console.log('Finding shortest path from', source, 'to', target);
        return null;
      },
    }),
    {
      name: 'graph-visualization-store',
    }
  )
);