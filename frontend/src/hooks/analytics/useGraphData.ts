import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect, useCallback } from 'react';
import { graphApi } from '@/services/analytics';
import { useAnalyticsStore, useGraphVisualizationStore } from '@/store/analytics';
import { GraphData, GraphNode, GraphEdge } from '@/store/analytics';

// Hook for fetching graph data
export const useGraphData = (filters?: {
  nodeTypes?: string[];
  edgeTypes?: string[];
  timeRange?: { start: string; end: string };
  searchQuery?: string;
  limit?: number;
}) => {
  const { setLoading, setError, setGraphData } = useAnalyticsStore();

  return useQuery({
    queryKey: ['graph', filters],
    queryFn: () => graphApi.getGraphData(filters),
    staleTime: 60000, // 1 minute
    refetchInterval: 300000, // 5 minutes
    onSuccess: (data) => {
      setGraphData(data);
      setError(null);
    },
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for fetching graph statistics
export const useGraphStatistics = () => {
  const { setLoading, setError } = useAnalyticsStore();

  return useQuery({
    queryKey: ['graph-statistics'],
    queryFn: () => graphApi.getGraphStatistics(),
    staleTime: 300000, // 5 minutes
    refetchInterval: 600000, // 10 minutes
    onSuccess: () => {
      setError(null);
    },
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for searching nodes
export const useNodeSearch = (query: string, limit: number = 10) => {
  const { setLoading, setError } = useAnalyticsStore();

  return useQuery({
    queryKey: ['node-search', query, limit],
    queryFn: () => graphApi.searchNodes(query, limit),
    enabled: query.length > 0,
    staleTime: 30000,
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for fetching node neighbors
export const useNodeNeighbors = (nodeId: string, depth: number = 1) => {
  const { setLoading, setError } = useAnalyticsStore();

  return useQuery({
    queryKey: ['node-neighbors', nodeId, depth],
    queryFn: () => graphApi.getNodeNeighbors(nodeId, depth),
    enabled: !!nodeId,
    staleTime: 60000,
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for graph layout
export const useGraphLayout = (layoutType: 'force' | 'hierarchical' | 'circular' = 'force') => {
  const { setLoading, setError } = useGraphVisualizationStore();

  return useQuery({
    queryKey: ['graph-layout', layoutType],
    queryFn: () => graphApi.getGraphLayout(layoutType),
    staleTime: 300000,
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for community detection
export const useCommunityDetection = (algorithm?: 'louvain' | 'label-propagation' | 'walktrap') => {
  const { setLoading, setError, setClusters } = useGraphVisualizationStore();

  return useQuery({
    queryKey: ['communities', algorithm],
    queryFn: () => graphApi.detectCommunities(algorithm),
    staleTime: 300000,
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for centrality calculations
export const useCentrality = (type: 'degree' | 'betweenness' | 'closeness' | 'eigenvector' | 'pagerank') => {
  const { setLoading, setError } = useAnalyticsStore();

  return useQuery({
    queryKey: ['centrality', type],
    queryFn: () => graphApi.calculateCentrality(type),
    staleTime: 300000,
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for shortest path
export const useShortestPath = (sourceId: string, targetId: string) => {
  const { setLoading, setError } = useAnalyticsStore();

  return useQuery({
    queryKey: ['shortest-path', sourceId, targetId],
    queryFn: () => graphApi.findShortestPath(sourceId, targetId),
    enabled: !!sourceId && !!targetId && sourceId !== targetId,
    staleTime: 300000,
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for graph interaction
export const useGraphInteraction = () => {
  const {
    selectedNodes,
    selectedEdges,
    selectNodes,
    selectEdges,
    clearSelection,
    hoveredNode,
    hoveredEdge,
    setHoveredNode,
    setHoveredEdge,
  } = useAnalyticsStore();

  const {
    zoom,
    pan,
    setZoom,
    setPan,
    resetViewport,
    fitToView,
  } = useGraphVisualizationStore();

  const handleNodeClick = useCallback((nodeId: string, multiSelect: boolean = false) => {
    if (multiSelect) {
      const newSelection = selectedNodes.includes(nodeId)
        ? selectedNodes.filter(id => id !== nodeId)
        : [...selectedNodes, nodeId];
      selectNodes(newSelection);
    } else {
      selectNodes([nodeId]);
      selectEdges([]);
    }
  }, [selectedNodes, selectNodes, selectEdges]);

  const handleEdgeClick = useCallback((edgeId: string, multiSelect: boolean = false) => {
    if (multiSelect) {
      const newSelection = selectedEdges.includes(edgeId)
        ? selectedEdges.filter(id => id !== edgeId)
        : [...selectedEdges, edgeId];
      selectEdges(newSelection);
    } else {
      selectEdges([edgeId]);
      selectNodes([]);
    }
  }, [selectedEdges, selectEdges, selectNodes]);

  const handleNodeHover = useCallback((nodeId: string | null) => {
    setHoveredNode(nodeId);
  }, [setHoveredNode]);

  const handleEdgeHover = useCallback((edgeId: string | null) => {
    setHoveredEdge(edgeId);
  }, [setHoveredEdge]);

  const handleZoomChange = useCallback((newZoom: number) => {
    setZoom(Math.max(0.1, Math.min(5, newZoom)));
  }, [setZoom]);

  const handlePanChange = useCallback((newPan: { x: number; y: number }) => {
    setPan(newPan);
  }, [setPan]);

  return {
    // Selection
    selectedNodes,
    selectedEdges,
    handleNodeClick,
    handleEdgeClick,
    clearSelection,

    // Hover
    hoveredNode,
    hoveredEdge,
    handleNodeHover,
    handleEdgeHover,

    // Viewport
    zoom,
    pan,
    handleZoomChange,
    handlePanChange,
    resetViewport,
    fitToView,

    // Selection state
    hasSelection: selectedNodes.length > 0 || selectedEdges.length > 0,
    selectionCount: selectedNodes.length + selectedEdges.length,
  };
};

// Hook for graph filtering
export const useGraphFilters = () => {
  const { graphFilters, updateGraphFilters, resetGraphFilters } = useAnalyticsStore();
  const [localFilters, setLocalFilters] = useState(graphFilters);

  const updateFilter = useCallback((key: keyof typeof graphFilters, value: any) => {
    const newFilters = { ...localFilters, [key]: value };
    setLocalFilters(newFilters);
    updateGraphFilters({ [key]: value });
  }, [localFilters, updateGraphFilters]);

  const applyFilters = useCallback(() => {
    updateGraphFilters(localFilters);
  }, [localFilters, updateGraphFilters]);

  const resetFilters = useCallback(() => {
    const defaultFilters = {
      nodeTypes: [],
      edgeTypes: [],
      timeRange: {
        start: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
        end: new Date().toISOString(),
      },
      searchQuery: '',
    };
    setLocalFilters(defaultFilters);
    resetGraphFilters();
  }, [resetGraphFilters]);

  return {
    filters: localFilters,
    updateFilter,
    applyFilters,
    resetFilters,
    hasActiveFilters: (
      localFilters.nodeTypes.length > 0 ||
      localFilters.edgeTypes.length > 0 ||
      localFilters.searchQuery.length > 0
    ),
  };
};

// Hook for graph analysis
export const useGraphAnalysis = () => {
  const queryClient = useQueryClient();

  const calculateNodeDegrees = useCallback(() => {
    // This would typically call an API endpoint
    console.log('Calculating node degrees');
    return {};
  }, []);

  const calculateBetweenness = useCallback(() => {
    // This would typically call an API endpoint
    console.log('Calculating betweenness centrality');
    return {};
  }, []);

  const calculatePageRank = useCallback(() => {
    // This would typically call an API endpoint
    console.log('Calculating PageRank');
    return {};
  }, []);

  const detectCommunities = useCallback((algorithm?: 'louvain' | 'label-propagation' | 'walktrap') => {
    queryClient.invalidateQueries({ queryKey: ['communities', algorithm] });
  }, [queryClient]);

  const findShortestPath = useCallback((sourceId: string, targetId: string) => {
    queryClient.invalidateQueries({ queryKey: ['shortest-path', sourceId, targetId] });
  }, [queryClient]);

  return {
    calculateNodeDegrees,
    calculateBetweenness,
    calculatePageRank,
    detectCommunities,
    findShortestPath,
  };
};

// Hook for graph export
export const useGraphExport = () => {
  const { setLoading, setError } = useAnalyticsStore();
  const queryClient = useQueryClient();

  const exportGraph = useCallback(async (
    format: 'json' | 'csv' | 'graphml' | 'gexf',
    filters?: Record<string, any>
  ) => {
    setLoading(true);
    try {
      // This would call the export API
      console.log(`Exporting graph in ${format} format`, filters);
      setError(null);
    } catch (error: any) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  }, [setLoading, setError]);

  return {
    exportGraph,
  };
};