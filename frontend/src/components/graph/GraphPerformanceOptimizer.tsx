/**
 * Graph Performance Optimizer - Performance Enhancement Utilities
 *
 * Provides performance optimization strategies for large graph visualization.
 * Includes virtual rendering, lazy loading, and memory management.
 */

import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import { GraphEdge, GraphNode } from '../../types/graph-api';

// Extend Performance interface for Chrome's memory API
interface PerformanceMemory {
  usedJSHeapSize: number;
  totalJSHeapSize: number;
  jsHeapSizeLimit: number;
}

declare global {
  interface Performance {
    memory?: PerformanceMemory;
  }
}

interface PerformanceConfig {
  maxVisibleNodes: number;
  maxVisibleEdges: number;
  chunkSize: number;
  renderThreshold: number;
  enableVirtualization: boolean;
  enableLazyLoading: boolean;
  memoryThreshold: number;
}

interface GraphPerformanceOptimizerProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  config?: Partial<PerformanceConfig>;
  onNodeClick?: (nodeId: string) => void;
  onEdgeClick?: (edgeId: string) => void;
  children: (
    visibleNodes: GraphNode[],
    visibleEdges: GraphEdge[]
  ) => React.ReactNode;
}

export const GraphPerformanceOptimizer: React.FC<
  GraphPerformanceOptimizerProps
> = ({ nodes, edges, config = {}, onNodeClick, onEdgeClick, children }) => {
  const defaultConfig: PerformanceConfig = {
    maxVisibleNodes: 1000,
    maxVisibleEdges: 2000,
    chunkSize: 100,
    renderThreshold: 500,
    enableVirtualization: true,
    enableLazyLoading: true,
    memoryThreshold: 100 * 1024 * 1024, // 100MB
  };

  const performanceConfig = useMemo(
    () => ({ ...defaultConfig, ...config }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      config.maxVisibleNodes,
      config.maxVisibleEdges,
      config.chunkSize,
      config.renderThreshold,
      config.enableVirtualization,
      config.enableLazyLoading,
      config.memoryThreshold,
    ]
  );
  const visibleRangeRef = useRef({
    minX: -Infinity,
    maxX: Infinity,
    minY: -Infinity,
    maxY: Infinity,
  });
  const loadedNodesRef = useRef(new Set<string>());
  const loadedEdgesRef = useRef(new Set<string>());
  const renderQueueRef = useRef<Array<() => void>>([]);
  const animationFrameRef = useRef<number>();

  // Memory monitoring
  const memoryMonitor = useRef({
    checkInterval: 5000, // 5 seconds
    lastCheck: 0,
    threshold: performanceConfig.memoryThreshold,
  });

  // Virtualization bounds
  const updateVisibleRange = useCallback(
    (bounds: typeof visibleRangeRef.current) => {
      visibleRangeRef.current = bounds;
    },
    []
  );

  // Spatial indexing for efficient queries
  const spatialIndex = useMemo(() => {
    if (!performanceConfig.enableVirtualization) return null;

    const index = new Map<string, GraphNode>();
    nodes.forEach((node) => {
      if (node.position) {
        const key = getSpatialKey(node.position.x, node.position.y, 50); // 50px grid
        if (!index.has(key)) {
          index.set(key, node);
        }
      }
    });
    return index;
  }, [nodes, performanceConfig.enableVirtualization]);

  // Get spatial key for indexing
  function getSpatialKey(x: number, y: number, gridSize: number): string {
    const gridX = Math.floor(x / gridSize);
    const gridY = Math.floor(y / gridSize);
    return `${gridX},${gridY}`;
  }

  // Check if node is in visible range
  const isNodeVisible = useCallback(
    (node: GraphNode): boolean => {
      if (!performanceConfig.enableVirtualization) return true;
      if (!node.position) return true;

      const { minX, maxX, minY, maxY } = visibleRangeRef.current;
      return (
        node.position.x >= minX &&
        node.position.x <= maxX &&
        node.position.y >= minY &&
        node.position.y <= maxY
      );
    },
    [performanceConfig.enableVirtualization]
  );

  // Priority-based node selection
  const getNodePriority = useCallback((node: GraphNode): number => {
    let priority = 0;

    // Higher priority for nodes with more connections
    priority += (node.entity_count || 0) * 10;

    // Higher priority for higher confidence
    priority += node.confidence * 5;

    // Higher priority for certain entity types
    const highPriorityTypes = ['person', 'organization', 'location'];
    if (highPriorityTypes.includes(node.type)) {
      priority += 20;
    }

    // Higher priority for recently updated nodes
    if (node.updated_at) {
      const updateTime = new Date(node.updated_at).getTime();
      const now = Date.now();
      const daysSinceUpdate = (now - updateTime) / (1000 * 60 * 60 * 24);
      priority += Math.max(0, 10 - daysSinceUpdate);
    }

    return priority;
  }, []);

  // Filter and paginate nodes
  const { visibleNodes, hasMoreNodes } = useMemo(() => {
    if (
      !performanceConfig.enableVirtualization &&
      !performanceConfig.enableLazyLoading
    ) {
      return {
        visibleNodes: nodes.slice(0, performanceConfig.maxVisibleNodes),
        hasMoreNodes: nodes.length > performanceConfig.maxVisibleNodes,
      };
    }

    // Filter by visibility and sort by priority
    const filteredNodes = nodes.filter(isNodeVisible);
    const sortedNodes = filteredNodes.sort(
      (a, b) => getNodePriority(b) - getNodePriority(a)
    );

    // Apply pagination
    const maxNodes = performanceConfig.maxVisibleNodes;
    const visible = sortedNodes.slice(0, maxNodes);

    return {
      visibleNodes: visible,
      hasMoreNodes: sortedNodes.length > maxNodes,
    };
  }, [nodes, isNodeVisible, getNodePriority, performanceConfig]);

  // Filter edges based on visible nodes
  const visibleEdges = useMemo(() => {
    if (!performanceConfig.enableVirtualization) {
      return edges.slice(0, performanceConfig.maxVisibleEdges);
    }

    const visibleNodeIds = new Set(visibleNodes.map((node) => node.id));
    const filteredEdges = edges.filter(
      (edge) =>
        visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
    );

    // Sort by weight and limit
    return filteredEdges
      .sort((a, b) => b.weight - a.weight)
      .slice(0, performanceConfig.maxVisibleEdges);
  }, [edges, visibleNodes, performanceConfig]);

  // Chunked rendering for large datasets
  const scheduleRender = useCallback(() => {
    if (renderQueueRef.current.length === 0) return;

    const renderChunk = () => {
      const startTime = performance.now();
      let processed = 0;

      while (
        renderQueueRef.current.length > 0 &&
        processed < performanceConfig.chunkSize
      ) {
        const renderFn = renderQueueRef.current.shift();
        if (renderFn) {
          renderFn();
          processed++;
        }

        // Check if we've exceeded render time budget (16ms for 60fps)
        if (performance.now() - startTime > 16) {
          break;
        }
      }

      if (renderQueueRef.current.length > 0) {
        animationFrameRef.current = requestAnimationFrame(renderChunk);
      }
    };

    animationFrameRef.current = requestAnimationFrame(renderChunk);
  }, [performanceConfig.chunkSize]);

  // Memory cleanup
  const performMemoryCleanup = useCallback(() => {
    // Clear caches if memory threshold exceeded
    if ('memory' in performance && performance.memory) {
      const memoryUsage = performance.memory.usedJSHeapSize;
      if (memoryUsage > memoryMonitor.current.threshold) {
        console.warn('Memory threshold exceeded, performing cleanup');

        // Clear spatial index
        // (Note: actual cache clearing would be handled by the parent component)

        // Force garbage collection if available
        if ('gc' in window) {
          (window as any).gc();
        }
      }
    }
    memoryMonitor.current.lastCheck = Date.now();
  }, []);

  // Performance monitoring
  useEffect(() => {
    const monitor = setInterval(() => {
      const now = Date.now();
      if (
        now - memoryMonitor.current.lastCheck >
        memoryMonitor.current.checkInterval
      ) {
        performMemoryCleanup();
      }
    }, memoryMonitor.current.checkInterval);

    return () => clearInterval(monitor);
  }, [performMemoryCleanup]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  // Render performance metrics
  const renderMetrics = useMemo(
    () => ({
      totalNodes: nodes.length,
      visibleNodes: visibleNodes.length,
      totalEdges: edges.length,
      visibleEdges: visibleEdges.length,
      memoryUsage:
        'memory' in performance ? performance.memory?.usedJSHeapSize : 0,
      hasMoreNodes,
      hasMoreEdges: edges.length > visibleEdges.length,
    }),
    [nodes, visibleNodes, edges, visibleEdges, hasMoreNodes]
  );

  return (
    <div className="graph-performance-optimizer">
      {children(visibleNodes, visibleEdges)}

      {/* Performance metrics for debugging */}
      {process.env.NODE_ENV === 'development' && (
        <div className="absolute top-2 right-2 bg-[var(--nous-bg-2)] bg-opacity-75 text-[var(--nous-fg-1)] text-xs p-2 rounded">
          <div>
            Nodes: {renderMetrics.visibleNodes}/{renderMetrics.totalNodes}
          </div>
          <div>
            Edges: {renderMetrics.visibleEdges}/{renderMetrics.totalEdges}
          </div>
          {renderMetrics.memoryUsage !== undefined && (
            <div>
              Memory: {(renderMetrics.memoryUsage / 1024 / 1024).toFixed(1)}MB
            </div>
          )}
          {renderMetrics.hasMoreNodes && (
            <div className="text-[var(--nous-corona)]">
              More nodes available
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// Performance hooks for components
export const useGraphPerformance = () => {
  const metricsRef = useRef({
    renderStartTime: 0,
    renderCount: 0,
    averageRenderTime: 0,
  });

  const startRender = useCallback(() => {
    metricsRef.current.renderStartTime = performance.now();
  }, []);

  const endRender = useCallback(() => {
    const renderTime = performance.now() - metricsRef.current.renderStartTime;
    metricsRef.current.renderCount++;
    metricsRef.current.averageRenderTime =
      (metricsRef.current.averageRenderTime *
        (metricsRef.current.renderCount - 1) +
        renderTime) /
      metricsRef.current.renderCount;

    return {
      renderTime,
      averageRenderTime: metricsRef.current.averageRenderTime,
      renderCount: metricsRef.current.renderCount,
    };
  }, []);

  return {
    startRender,
    endRender,
    metrics: metricsRef.current,
  };
};

// Performance optimization utilities
export const graphPerformanceUtils = {
  // Debounce function for filter changes
  debounce: <T extends (...args: any[]) => any = (...args: any[]) => any>(
    func: T,
    wait: number
  ): ((...args: Parameters<T>) => void) => {
    let timeout: NodeJS.Timeout;
    return (...args: Parameters<T>) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => func(...args), wait);
    };
  },

  // Throttle function for scroll events
  throttle: <T extends (...args: any[]) => any = (...args: any[]) => any>(
    func: T,
    limit: number
  ): ((...args: Parameters<T>) => void) => {
    let inThrottle: boolean;
    return (...args: Parameters<T>) => {
      if (!inThrottle) {
        func(...args);
        inThrottle = true;
        setTimeout(() => (inThrottle = false), limit);
      }
    };
  },

  // Lazy loading utility
  createLazyLoader: <T = any,>(items: T[], batchSize: number = 50) => {
    let currentIndex = 0;

    return {
      loadNext: (): T[] => {
        const next = items.slice(currentIndex, currentIndex + batchSize);
        currentIndex += batchSize;
        return next;
      },
      hasMore: () => currentIndex < items.length,
      reset: () => {
        currentIndex = 0;
      },
      getProgress: () => ({
        loaded: currentIndex,
        total: items.length,
        percentage: (currentIndex / items.length) * 100,
      }),
    };
  },

  // Memory efficient data structure for large graphs
  createCompactGraph: (nodes: GraphNode[], edges: GraphEdge[]) => {
    const nodeMap = new Map<string, GraphNode>();
    const adjacencyList = new Map<string, Set<string>>();

    nodes.forEach((node) => {
      nodeMap.set(node.id, node);
      adjacencyList.set(node.id, new Set());
    });

    edges.forEach((edge) => {
      adjacencyList.get(edge.source)?.add(edge.target);
      adjacencyList.get(edge.target)?.add(edge.source);
    });

    return {
      getNode: (id: string) => nodeMap.get(id),
      getNeighbors: (id: string) => Array.from(adjacencyList.get(id) || []),
      getAllNodes: () => Array.from(nodeMap.values()),
      size: nodeMap.size,
    };
  },
};

export default GraphPerformanceOptimizer;
