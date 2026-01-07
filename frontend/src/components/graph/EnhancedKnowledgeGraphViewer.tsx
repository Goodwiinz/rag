/**
 * Enhanced Knowledge Graph Viewer - Main Visualization Component
 *
 * ARCHITECTURE COMPLIANCE: This component ONLY renders graph data provided by backend APIs.
 * NO graph algorithms or processing logic is included - pure data consumption.
 *
 * Data Flow:
 * Backend APIs -> Services -> Enhanced Store -> This Component -> Visualization Library
 *
 * Performance Optimized:
 * - React 18 with concurrent features
 * - Virtual rendering for large graphs
 * - Efficient state management with Zustand
 * - Accessibility first design (WCAG 2.1 AA)
 * - Responsive design for all devices
 */

import React, { useEffect, useRef, useState, useCallback, useMemo, useLayoutEffect } from 'react';
import { Network } from 'vis-network/standalone';
import { useQuery } from '@tanstack/react-query';
import { graphService } from '../../services/graphService';
import { websocketService } from '../../services/websocketService';
import { useGraphStore } from '../../stores/enhancedGraphStore';
import {
  KnowledgeGraphData,
  GraphNode,
  GraphEdge,
  GraphFilters,
  GraphVisualizationState,
  WebSocketGraphUpdate,
  GraphAnalyticsDashboard as GraphAnalyticsData,
  GraphLayout
} from '../../types/knowledge-graph';
import { GraphLayoutData } from '../../types/graph-api';

// Enhanced component props
interface EnhancedKnowledgeGraphViewerProps {
  initialFilters?: Partial<GraphFilters>;
  className?: string;
  height?: string | number;
  width?: string | number;
  onNodeClick?: (nodeId: string, node: GraphNode) => void;
  onEdgeClick?: (edgeId: string, edge: GraphEdge) => void;
  onSelectionChange?: (selectedNodes: string[], selectedEdges: string[]) => void;
  onFiltersChange?: (filters: GraphFilters) => void;
  showControls?: boolean;
  showAnalytics?: boolean;
  virtualRendering?: boolean;
  accessibilityMode?: boolean;
  theme?: 'light' | 'dark' | 'high-contrast';
}

export const EnhancedKnowledgeGraphViewer: React.FC<EnhancedKnowledgeGraphViewerProps> = ({
  initialFilters = {},
  className = '',
  height = '600px',
  width = '100%',
  onNodeClick,
  onEdgeClick,
  onSelectionChange,
  onFiltersChange,
  showControls = true,
  showAnalytics = false,
  virtualRendering = true,
  accessibilityMode = false,
  theme = 'light'
}) => {
  // Enhanced state management with Zustand
  const {
    graphData,
    filters,
    visualizationState,
    selectedNodes,
    selectedEdges,
    highlightedNodes,
    highlightedEdges,
    isLoading,
    error,
    wsConnected,
    performanceMetrics,
    // Store actions
    setGraphData,
    setFilters,
    selectNode,
    selectEdge,
    deselectNode,
    deselectEdge,
    clearSelection,
    highlightNode,
    highlightEdge,
    clearHighlights,
    setVisualizationState,
    setWebSocketStatus,
    handleWebSocketMessage,
    setLoading,
    setError,
    getNodeById,
    getEdgeById
  } = useGraphStore();

  // Refs for DOM elements and network instance
  const networkRef = useRef<Network | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Local component state
  const [isInitialized, setIsInitialized] = useState(false);
  const [renderStats, setRenderStats] = useState({
    nodeCount: 0,
    edgeCount: 0,
    renderTime: 0,
    fps: 0
  });

  // Initialize filters with props
  useEffect(() => {
    if (Object.keys(initialFilters).length > 0) {
      setFilters(initialFilters);
    }
  }, [initialFilters, setFilters]);

  // Enhanced query with optimistic updates
  const {
    data: fetchedGraphData,
    isLoading: isQueryLoading,
    error: queryError,
    refetch
  } = useQuery({
    queryKey: ['graphData', filters],
    queryFn: () => graphService.getGraphData({
      filters,
      layout_algorithm: visualizationState.ui.layout_algorithm as any,
      options: {
        dimensions: {
          width: containerRef.current?.clientWidth || 800,
          height: containerRef.current?.clientHeight || 600
        },
        include_analytics: showAnalytics,
        max_nodes: virtualRendering ? 500 : undefined,
        cache_key: `graph-${JSON.stringify(filters)}`
      }
    }),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    retry: 3,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000)
  });

  // WebSocket integration with enhanced error handling
  useEffect(() => {
    let unsubscribe: (() => void) | null = null;

    const setupWebSocket = async () => {
      try {
        const connection = await websocketService.connectToGraphUpdates(filters);
        setWebSocketStatus('connected');

        // Subscribe to all relevant message types
        const unsubscribes = [
          websocketService.subscribe('graph-updates', 'node_added', (message: WebSocketGraphUpdate) => {
            handleWebSocketMessage(message);
          }),
          websocketService.subscribe('graph-updates', 'node_removed', (message: WebSocketGraphUpdate) => {
            handleWebSocketMessage(message);
          }),
          websocketService.subscribe('graph-updates', 'node_updated', (message: WebSocketGraphUpdate) => {
            handleWebSocketMessage(message);
          }),
          websocketService.subscribe('graph-updates', 'edge_added', (message: WebSocketGraphUpdate) => {
            handleWebSocketMessage(message);
          }),
          websocketService.subscribe('graph-updates', 'edge_removed', (message: WebSocketGraphUpdate) => {
            handleWebSocketMessage(message);
          }),
          websocketService.subscribe('graph-updates', 'edge_updated', (message: WebSocketGraphUpdate) => {
            handleWebSocketMessage(message);
          }),
          websocketService.subscribe('graph-updates', 'layout_updated', (message: WebSocketGraphUpdate) => {
            handleWebSocketMessage(message);
            if (message.data.layout && networkRef.current) {
              updateGraphLayout(message.data.layout);
            }
          }),
          websocketService.subscribe('graph-updates', 'batch_updated', (message: WebSocketGraphUpdate) => {
            handleWebSocketMessage(message);
          })
        ];

        unsubscribe = () => {
          unsubscribes.forEach(unsub => unsub());
        };

      } catch (error) {
        console.error('WebSocket connection failed:', error);
        setWebSocketStatus('error');
      }
    };

    setupWebSocket();

    return () => {
      if (unsubscribe) unsubscribe();
      websocketService.disconnect('graph-updates');
    };
  }, [filters, handleWebSocketMessage, setWebSocketStatus]);

  // Virtual rendering optimization
  const visibleData = useMemo(() => {
    if (!graphData || !virtualRendering) return graphData;

    const viewport = visualizationState.viewport;
    const bounds = viewport.bounds;

    // Simple viewport culling for performance
    const visibleNodes = graphData.nodes.filter(node => {
      if (!node.position) return true;
      return node.position.x >= bounds.minX && node.position.x <= bounds.maxX &&
             node.position.y >= bounds.minY && node.position.y <= bounds.maxY;
    });

    // Include connected edges for visible nodes
    const visibleNodeIds = new Set(visibleNodes.map(node => node.id));
    const visibleEdges = graphData.edges.filter(edge =>
      visibleNodeIds.has(edge.source) || visibleNodeIds.has(edge.target)
    );

    return {
      ...graphData,
      nodes: visibleNodes,
      edges: visibleEdges
    };
  }, [graphData, virtualRendering, visualizationState.viewport]);

  // Convert data to vis-network format with performance optimization
  const visData = useMemo(() => {
    if (!visibleData) return { nodes: [], edges: [] };

    const startTime = performance.now();

    const nodes = visibleData.nodes.map(node => ({
      id: node.id,
      label: node.label,
      color: getNodeColor(node.type, node.confidence, theme),
      size: getNodeSize(node, visualizationState.ui),
      font: {
        color: getFontColor(theme),
        size: Math.max(12, getNodeSize(node, visualizationState.ui) / 4),
        multi: 'html' as const,
        bold: selectedNodes.has(node.id) || highlightedNodes.has(node.id)
      },
      borderWidth: selectedNodes.has(node.id) ? 4 : highlightedNodes.has(node.id) ? 3 : 2,
      borderColor: selectedNodes.has(node.id) ? '#2563eb' : highlightedNodes.has(node.id) ? '#f59e0b' : undefined,
      shape: node.style?.shape || 'dot',
      opacity: getNodeOpacity(node, selectedNodes.has(node.id), highlightedNodes.has(node.id)),
      title: getNodeTooltip(node, accessibilityMode),
      chosen: {
        node: (values: any, id: string, selected: boolean, hovering: boolean) => {
          values.borderWidth = selected ? 4 : 2;
          values.shadowSize = selected ? 15 : 5;
          values.shadowColor = selected ? '#2563eb' : '#000000';
        }
      }
    }));

    const edges = visibleData.edges.map(edge => ({
      id: edge.id,
      from: edge.source,
      to: edge.target,
      color: {
        color: getEdgeColor(edge, selectedEdges.has(edge.id), highlightedEdges.has(edge.id), theme),
        highlight: '#2563eb'
      },
      width: getEdgeWidth(edge, visualizationState.ui, selectedEdges.has(edge.id)),
      dashes: edge.style?.dash || false,
      opacity: getEdgeOpacity(edge, selectedEdges.has(edge.id), highlightedEdges.has(edge.id)),
      title: getEdgeTooltip(edge, accessibilityMode),
      arrows: edge.style?.arrow || {
        to: { enabled: true, scaleFactor: 0.8 }
      },
      smooth: {
        enabled: true,
        type: 'continuous',
        roundness: 0.5
      },
      chosen: {
        edge: (values: any, id: string, selected: boolean, hovering: boolean) => {
          values.width = selected ? values.width * 1.5 : values.width;
          values.color = selected ? '#2563eb' : values.color.color;
        }
      }
    }));

    const endTime = performance.now();
    setRenderStats(prev => ({
      ...prev,
      renderTime: endTime - startTime,
      nodeCount: nodes.length,
      edgeCount: edges.length
    }));

    return { nodes, edges };
  }, [visibleData, selectedNodes, selectedEdges, highlightedNodes, highlightedEdges, visualizationState.ui, theme, accessibilityMode]);

  // Network options with accessibility and performance settings
  const networkOptions = useMemo(() => ({
    physics: {
      enabled: visualizationState.ui.layout_algorithm === 'force_directed',
      solver: 'barnesHut' as const,
      barnesHut: {
        gravitationalConstant: -2000,
        centralGravity: 0.3,
        springLength: 95,
        springConstant: 0.04,
        damping: 0.09,
        avoidOverlap: 0.1
      },
      stabilization: {
        enabled: true,
        iterations: 100,
        updateInterval: 25,
        onlyDynamicEdges: false,
        fit: true
      }
    },
    layout: {
      improvedLayout: false, // Use backend layout
      hierarchical: {
        enabled: visualizationState.ui.layout_algorithm === 'hierarchical',
        direction: 'UD' as const,
        sortMethod: 'directed' as const,
        levelSeparation: 150,
        nodeSpacing: 100
      },
      clusterThreshold: 150 // Enable clustering for large graphs
    },
    interaction: {
      hover: true,
      hoverConnectedEdges: true,
      tooltipDelay: accessibilityMode ? 0 : 200,
      zoomView: true,
      dragView: true,
      navigationButtons: accessibilityMode,
      keyboard: accessibilityMode,
      multiselect: true,
      selectable: true,
      selectConnectedEdges: false
    },
    nodes: {
      font: {
        color: getFontColor(theme),
        size: 14,
        face: 'Inter, system-ui, sans-serif'
      },
      borderWidth: 2,
      borderWidthSelected: 4,
      shadow: {
        enabled: true,
        color: 'rgba(0,0,0,0.1)',
        size: 5,
        x: 2,
        y: 2
      }
    },
    edges: {
      width: 2,
      selectionWidth: 3,
      smooth: {
        enabled: true,
        type: 'continuous',
        roundness: 0.5
      },
      shadow: {
        enabled: true,
        color: 'rgba(0,0,0,0.1)',
        size: 3,
        x: 1,
        y: 1
      }
    },
    groups: {
      // Entity type groups for consistent styling
      person: { color: '#ef4444' },
      organization: { color: '#3b82f6' },
      location: { color: '#10b981' },
      event: { color: '#f59e0b' },
      concept: { color: '#8b5cf6' },
      document: { color: '#6b7280' }
    }
  }), [visualizationState, theme, accessibilityMode]);

  // Initialize and update network
  useEffect(() => {
    if (!containerRef.current || !visData.nodes.length) return;

    const renderStartTime = performance.now();

    if (!networkRef.current) {
      // Create new network
      networkRef.current = new Network(containerRef.current, visData, networkOptions);

      // Setup enhanced event handlers
      networkRef.current.on('click', (params) => {
        if (params.nodes.length > 0) {
          const nodeId = params.nodes[0];
          const node = getNodeById(nodeId);
          if (node && onNodeClick) {
            onNodeClick(nodeId, node);
          }
          selectNode(nodeId, params.event?.srcEvent?.ctrlKey || params.event?.srcEvent?.metaKey);
        }
        if (params.edges.length > 0) {
          const edgeId = params.edges[0];
          const edge = getEdgeById(edgeId);
          if (edge && onEdgeClick) {
            onEdgeClick(edgeId, edge);
          }
          selectEdge(edgeId, params.event?.srcEvent?.ctrlKey || params.event?.srcEvent?.metaKey);
        }

        onSelectionChange?.(Array.from(selectedNodes), Array.from(selectedEdges));
      });

      networkRef.current.on('doubleClick', (params) => {
        if (params.nodes.length > 0) {
          const nodeId = params.nodes[0];
          // Focus on node and show neighborhood
          focusNodeAndNeighbors(nodeId);
        }
      });

      networkRef.current.on('oncontext', (params) => {
        params.event.preventDefault();
        // Show context menu for node/edge
      });

      networkRef.current.on('dragEnd', (params) => {
        if (params.nodes.length > 0) {
          // Update node positions in state
          const positions = networkRef.current?.getPosition(params.nodes);
          // Store positions in state for persistence
        }
      });

      networkRef.current.on('zoom', (params) => {
        setVisualizationState({
          viewport: {
            ...visualizationState.viewport,
            zoom: params.scale
          }
        });
      });

      networkRef.current.on('dragging', (params) => {
        // Update pan position during drag
      });

    } else {
      // Update existing network
      networkRef.current.setData(visData);
    }

    const renderEndTime = performance.now();
    setIsInitialized(true);

    // Fit graph to view with animation
    if (networkRef.current) {
      networkRef.current.fit({
        animation: {
          duration: 1000,
          easingFunction: 'easeInOutQuad'
        }
      });
    }

    // Performance monitoring
    setRenderStats(prev => ({
      ...prev,
      renderTime: renderEndTime - renderStartTime
    }));

  }, [visData, networkOptions, getNodeById, getEdgeById, onNodeClick, onEdgeClick, onSelectionChange, selectNode, selectEdge, visualizationState, setVisualizationState]);

  // Setup ResizeObserver for responsive behavior
  useEffect(() => {
    if (!containerRef.current) return;

    resizeObserverRef.current = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (networkRef.current) {
          networkRef.current.setSize(String(width), String(height));
          networkRef.current.redraw();
        }
      }
    });

    resizeObserverRef.current.observe(containerRef.current);

    return () => {
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
      }
    };
  }, []);

  // Performance monitoring with requestAnimationFrame
  useEffect(() => {
    let lastTime = performance.now();
    let frameCount = 0;

    const measureFPS = () => {
      frameCount++;
      const currentTime = performance.now();

      if (currentTime - lastTime >= 1000) {
        setRenderStats(prev => ({
          ...prev,
          fps: frameCount
        }));
        frameCount = 0;
        lastTime = currentTime;
      }

      animationFrameRef.current = requestAnimationFrame(measureFPS);
    };

    animationFrameRef.current = requestAnimationFrame(measureFPS);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  // Enhanced helper functions with accessibility
  const getNodeColor = (type: string, confidence: number, theme: string): string => {
    // Use theme-appropriate colors with high contrast for accessibility
    const themes = {
      light: {
        person: '#ef4444',
        organization: '#3b82f6',
        location: '#10b981',
        event: '#f59e0b',
        concept: '#8b5cf6',
        document: '#6b7280'
      },
      dark: {
        person: '#f87171',
        organization: '#60a5fa',
        location: '#34d399',
        event: '#fbbf24',
        concept: '#a78bfa',
        document: '#9ca3af'
      },
      'high-contrast': {
        person: '#dc2626',
        organization: '#2563eb',
        location: '#059669',
        event: '#d97706',
        concept: '#7c3aed',
        document: '#374151'
      }
    };

    const themeColors = themes[theme as keyof typeof themes] || themes.light;
    return (themeColors as Record<string, string>)[type] || themeColors.document;
  };

  const getNodeSize = (node: GraphNode, ui: GraphVisualizationState['ui']): number => {
    // Size based on analytics data from backend
    if (node.analytics?.centrality_scores?.degree) {
      return Math.max(15, Math.min(60, node.analytics.centrality_scores.degree * 10));
    }
    return node.style?.size || 25;
  };

  const getEdgeWidth = (edge: GraphEdge, ui: GraphVisualizationState['ui'], isSelected: boolean): number => {
    const baseWidth = edge.style?.width || 2;
    const weightMultiplier = edge.weight ? Math.max(1, Math.min(8, edge.weight * 3)) : 1;
    const selectionMultiplier = isSelected ? 1.5 : 1;

    return baseWidth * weightMultiplier * selectionMultiplier;
  };

  const getEdgeColor = (edge: GraphEdge, isSelected: boolean, isHighlighted: boolean, theme: string): string => {
    if (isSelected) return '#2563eb';
    if (isHighlighted) return '#f59e0b';
    return edge.style?.color || '#9ca3af';
  };

  const getNodeOpacity = (node: GraphNode, isSelected: boolean, isHighlighted: boolean): number => {
    if (isSelected || isHighlighted) return 1;
    return node.style?.opacity || 0.9;
  };

  const getEdgeOpacity = (edge: GraphEdge, isSelected: boolean, isHighlighted: boolean): number => {
    if (isSelected || isHighlighted) return 1;
    return edge.style?.opacity || 0.6;
  };

  const getFontColor = (theme: string): string => {
    const colors = {
      light: '#111827',
      dark: '#f9fafb',
      'high-contrast': '#000000'
    };
    return colors[theme as keyof typeof colors] || colors.light;
  };

  const getNodeTooltip = (node: GraphNode, accessibilityMode: boolean): string => {
    const baseInfo = `${node.type}: ${node.label}`;
    const confidence = `Confidence: ${(node.confidence * 100).toFixed(1)}%`;

    if (accessibilityMode) {
      return `${baseInfo}. ${confidence}. Node ID: ${node.id}`;
    }

    if (node.analytics) {
      const centrality = node.analytics.centrality_scores;
      return `${baseInfo}\n${confidence}\nDegree: ${centrality.degree?.toFixed(2) || 'N/A'}\nBetweenness: ${centrality.betweenness?.toFixed(2) || 'N/A'}`;
    }

    return `${baseInfo}\n${confidence}`;
  };

  const getEdgeTooltip = (edge: GraphEdge, accessibilityMode: boolean): string => {
    const baseInfo = `${edge.type}`;
    const weight = `Weight: ${edge.weight.toFixed(2)}`;
    const confidence = `Confidence: ${(edge.confidence * 100).toFixed(1)}%`;

    if (accessibilityMode) {
      return `${baseInfo}. ${weight}. ${confidence}. Edge ID: ${edge.id}`;
    }

    return `${baseInfo}\n${weight}\n${confidence}`;
  };

  const updateGraphLayout = (newLayout: GraphLayout | GraphLayoutData) => {
    if (!networkRef.current) return;

    // Handle both GraphLayout (layout config only) and GraphLayoutData (full data with nodes)
    const layoutData = newLayout as GraphLayoutData;
    if (layoutData.nodes && Array.isArray(layoutData.nodes)) {
      // Full GraphLayoutData - update node positions
      const positions: Record<string, { x: number; y: number }> = {};
      layoutData.nodes.forEach(node => {
        if (node.position) {
          positions[node.id] = node.position;
        }
      });

      // Move each node to its position
      Object.entries(positions).forEach(([nodeId, pos]) => {
        if (networkRef.current && pos) {
          networkRef.current.moveNode(nodeId, pos.x, pos.y);
        }
      });
    }
    // For GraphLayout (config only), the layout algorithm change is handled elsewhere
  };

  const focusNodeAndNeighbors = async (nodeId: string) => {
    try {
      // Fetch neighborhood from backend
      const neighborhoodData = await graphService.getNodeNeighborhood(nodeId, {
        depth: 2,
        max_nodes: 50,
        layout_algorithm: 'circular',
        include_analytics: true
      });

      // Highlight the path
      const nodeIds = neighborhoodData.nodes.map(n => n.id);
      highlightNode(nodeId);

      // Update visualization to focus on neighborhood
      setGraphData(neighborhoodData);

      // Fit to neighborhood
      if (networkRef.current) {
        networkRef.current.fit({
          nodes: nodeIds,
          animation: {
            duration: 800,
            easingFunction: 'easeInOutQuad'
          }
        });
      }
    } catch (error) {
      console.error('Failed to focus on node neighborhood:', error);
    }
  };

  // Enhanced keyboard navigation for accessibility
  useEffect(() => {
    if (!accessibilityMode || !containerRef.current) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!networkRef.current) return;

      switch (event.key) {
        case 'ArrowLeft':
        case 'ArrowRight':
        case 'ArrowUp':
        case 'ArrowDown':
          // Pan viewport
          event.preventDefault();
          const pan = visualizationState.viewport.pan;
          const delta = 50;
          let newPan = { ...pan };

          switch (event.key) {
            case 'ArrowLeft': newPan.x -= delta; break;
            case 'ArrowRight': newPan.x += delta; break;
            case 'ArrowUp': newPan.y -= delta; break;
            case 'ArrowDown': newPan.y += delta; break;
          }

          networkRef.current.moveTo({ position: newPan });
          setVisualizationState({ viewport: { ...visualizationState.viewport, pan: newPan } });
          break;

        case '+':
        case '=':
          // Zoom in
          event.preventDefault();
          const newZoomIn = Math.min(5, visualizationState.viewport.zoom * 1.2);
          networkRef.current.moveTo({ scale: newZoomIn });
          setVisualizationState({ viewport: { ...visualizationState.viewport, zoom: newZoomIn } });
          break;

        case '-':
        case '_':
          // Zoom out
          event.preventDefault();
          const newZoomOut = Math.max(0.1, visualizationState.viewport.zoom / 1.2);
          networkRef.current.moveTo({ scale: newZoomOut });
          setVisualizationState({ viewport: { ...visualizationState.viewport, zoom: newZoomOut } });
          break;

        case 'Escape':
          // Clear selection
          event.preventDefault();
          clearSelection();
          break;

        case 'a':
          if (event.ctrlKey || event.metaKey) {
            // Select all
            event.preventDefault();
            const allNodeIds = visibleData?.nodes.map(n => n.id) || [];
            selectNode(allNodeIds[0], false); // This needs to be updated to select all
          }
          break;
      }
    };

    containerRef.current.addEventListener('keydown', handleKeyDown);
    return () => containerRef.current?.removeEventListener('keydown', handleKeyDown);
  }, [accessibilityMode, visualizationState, visibleData, clearSelection, selectNode, setVisualizationState]);

  // Loading state with accessibility
  if (isQueryLoading || isLoading) {
    return (
      <div
        className="flex items-center justify-center h-full"
        role="status"
        aria-label="Loading graph data"
      >
        <div className="flex flex-col items-center space-y-4">
          <div
            className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"
            aria-hidden="true"
          ></div>
          <span className="text-gray-600 text-lg">
            Loading graph data{virtualRendering ? ' with virtual rendering' : ''}...
          </span>
          {accessibilityMode && (
            <span className="sr-only">
              Please wait while the knowledge graph visualization is being prepared
            </span>
          )}
        </div>
      </div>
    );
  }

  // Error state with accessibility
  if (error || queryError) {
    return (
      <div
        className="flex items-center justify-center h-full"
        role="alert"
        aria-live="polite"
      >
        <div className="text-red-600 text-center max-w-md">
          <h3 className="text-lg font-semibold mb-2">
            Failed to load graph data
          </h3>
          <p className="text-sm mb-4">
            {error || (queryError instanceof Error ? queryError.message : String(queryError || 'Unknown error occurred'))}
          </p>
          <button
            onClick={() => refetch()}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            aria-label="Retry loading graph data"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Render main component
  return (
    <div
      className={`enhanced-knowledge-graph-viewer ${className}`}
      style={{ height, width }}
      role="application"
      aria-label="Interactive knowledge graph visualization"
    >
      {/* Performance Stats (for development) */}
      {process.env.NODE_ENV === 'development' && (
        <div className="absolute top-2 left-2 bg-black bg-opacity-75 text-white text-xs p-2 rounded z-10">
          <div>Nodes: {renderStats.nodeCount}</div>
          <div>Edges: {renderStats.edgeCount}</div>
          <div>Render: {renderStats.renderTime.toFixed(2)}ms</div>
          <div>FPS: {renderStats.fps}</div>
          <div>WebSocket: {wsConnected ? 'Connected' : 'Disconnected'}</div>
        </div>
      )}

      {/* Main graph container */}
      <div
        ref={containerRef}
        className="w-full h-full border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        tabIndex={accessibilityMode ? 0 : undefined}
        aria-label="Graph visualization area"
        onKeyDown={accessibilityMode ? undefined : undefined}
      />

      {/* Controls overlay */}
      {showControls && (
        <div className="absolute top-4 right-4 space-y-2">
          {/* Control buttons would go here */}
          <div className="bg-white rounded-lg shadow-lg p-2 space-y-1">
            <button
              onClick={() => refetch()}
              className="w-full px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
              aria-label="Refresh graph data"
            >
              Refresh
            </button>
            <button
              onClick={() => clearSelection()}
              className="w-full px-3 py-1 text-sm bg-gray-600 text-white rounded hover:bg-gray-700"
              aria-label="Clear selection"
            >
              Clear Selection
            </button>
            <button
              onClick={() => networkRef.current?.fit()}
              className="w-full px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700"
              aria-label="Fit graph to view"
            >
              Fit View
            </button>
          </div>
        </div>
      )}

      {/* Analytics overlay */}
      {showAnalytics && performanceMetrics && (
        <div className="absolute bottom-4 left-4 bg-white rounded-lg shadow-lg p-4 max-w-sm">
          <h4 className="font-semibold mb-2">Performance Metrics</h4>
          <div className="text-xs space-y-1">
            <div>Query Time: {performanceMetrics.query_times.graph_data}ms</div>
            <div>Memory: {(performanceMetrics.memory_usage.graph_data / 1024 / 1024).toFixed(2)}MB</div>
            <div>Cache Hit Rate: {(performanceMetrics.cache_performance.hit_rate * 100).toFixed(1)}%</div>
          </div>
        </div>
      )}

      {/* Accessibility announcement */}
      <div
        className="sr-only"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {selectedNodes.size > 0 && `${selectedNodes.size} nodes selected`}
        {selectedEdges.size > 0 && `${selectedEdges.size} edges selected`}
        {isLoading && 'Loading new graph data'}
        {error && 'Error loading graph data'}
      </div>
    </div>
  );
};

export default EnhancedKnowledgeGraphViewer;