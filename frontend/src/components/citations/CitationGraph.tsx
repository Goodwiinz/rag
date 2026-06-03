'use client';

/**
 * Citation Graph Component
 *
 * Interactive citation network visualization using Cytoscape.js.
 * Displays papers as nodes and citation relationships as edges.
 *
 * Features:
 * - Force-directed layout with cose-bilkent
 * - Node sizing based on citation count
 * - Color coding for uploaded vs external papers
 * - Click-to-select with details panel
 * - Context menu for actions
 * - Zoom/pan controls
 * - **Graph clustering for 1000+ nodes (performance optimized)**
 * - Expand/collapse cluster nodes
 */

import cytoscape, {
  Core,
  EdgeSingular,
  ElementDefinition,
  NodeSingular,
} from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import popper from 'cytoscape-popper';
import {
  Layers,
  Loader2,
  Maximize,
  Minimize2,
  RotateCcw,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
import { IconButton } from '@/components/ui/icon-button';
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

// Register Cytoscape extensions
if (typeof window !== 'undefined') {
  cytoscape.use(coseBilkent);
  cytoscape.use(popper);
}

// Clustering utilities for large graphs
interface ClusterInfo {
  id: string;
  nodeIds: string[];
  centroid: GraphNode | null;
  size: number;
  avgYear?: number;
  uploadedCount: number;
  externalCount: number;
}

// Types
export interface GraphNode {
  id: string;
  title?: string;
  authors?: string[];
  year?: number;
  venue?: string;
  doi?: string;
  arxiv_id?: string;
  document_id?: string;
  is_uploaded?: boolean;
  citation_count?: number;
  position?: { x: number; y: number } | null;
  influence_score?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
  confidence?: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata?: {
    total_nodes: number;
    total_edges: number;
    depth: number;
    include_external: boolean;
  };
}

export interface CitationGraphProps {
  data: GraphData;
  loading?: boolean;
  onNodeClick?: (node: GraphNode) => void;
  onNodeHover?: (node: GraphNode | null) => void;
  onEdgeClick?: (edge: GraphEdge) => void;
  selectedNodeId?: string;
  height?: string | number;
  className?: string;
  /** Threshold for enabling clustering (default: 1000) */
  clusteringThreshold?: number;
  /** Enable/disable clustering mode */
  enableClustering?: boolean;
}

// Simple community detection using label propagation
function detectCommunities(
  nodes: GraphNode[],
  edges: GraphEdge[],
  targetClusters: number = 20
): Map<string, string> {
  const nodeMap = new Map<string, GraphNode>();
  nodes.forEach((n) => nodeMap.set(n.id, n));

  // Build adjacency list
  const adjacency = new Map<string, Set<string>>();
  nodes.forEach((n) => adjacency.set(n.id, new Set()));
  edges.forEach((e) => {
    adjacency.get(e.source)?.add(e.target);
    adjacency.get(e.target)?.add(e.source);
  });

  // Initialize labels (each node gets its own label)
  const labels = new Map<string, string>();
  nodes.forEach((n) => labels.set(n.id, n.id));

  // Label propagation iterations
  const maxIterations = 10;
  for (let iter = 0; iter < maxIterations; iter++) {
    let changed = false;
    const shuffledNodes = [...nodes].sort(() => Math.random() - 0.5);

    for (const node of shuffledNodes) {
      const neighbors = adjacency.get(node.id);
      if (!neighbors || neighbors.size === 0) continue;

      // Count neighbor labels
      const labelCounts = new Map<string, number>();
      neighbors.forEach((neighborId) => {
        const label = labels.get(neighborId)!;
        labelCounts.set(label, (labelCounts.get(label) || 0) + 1);
      });

      // Find most common label
      let maxCount = 0;
      let bestLabel = labels.get(node.id)!;
      labelCounts.forEach((count, label) => {
        if (count > maxCount) {
          maxCount = count;
          bestLabel = label;
        }
      });

      if (bestLabel !== labels.get(node.id)) {
        labels.set(node.id, bestLabel);
        changed = true;
      }
    }

    if (!changed) break;
  }

  // Merge small clusters to reach target count
  const clusterSizes = new Map<string, number>();
  labels.forEach((label) => {
    clusterSizes.set(label, (clusterSizes.get(label) || 0) + 1);
  });

  // Sort clusters by size
  const sortedClusters = [...clusterSizes.entries()].sort(
    (a, b) => b[1] - a[1]
  );

  // Keep top clusters, merge rest into 'other'
  const topClusters = new Set(
    sortedClusters.slice(0, targetClusters - 1).map((c) => c[0])
  );

  const finalLabels = new Map<string, string>();
  labels.forEach((label, nodeId) => {
    if (topClusters.has(label)) {
      finalLabels.set(nodeId, `cluster_${label}`);
    } else {
      finalLabels.set(nodeId, 'cluster_other');
    }
  });

  return finalLabels;
}

// Build cluster information
function buildClusters(
  nodes: GraphNode[],
  clusterLabels: Map<string, string>
): ClusterInfo[] {
  const clusters = new Map<string, ClusterInfo>();

  nodes.forEach((node) => {
    const clusterId = clusterLabels.get(node.id) || 'cluster_other';

    if (!clusters.has(clusterId)) {
      clusters.set(clusterId, {
        id: clusterId,
        nodeIds: [],
        centroid: null,
        size: 0,
        avgYear: undefined,
        uploadedCount: 0,
        externalCount: 0,
      });
    }

    const cluster = clusters.get(clusterId)!;
    cluster.nodeIds.push(node.id);
    cluster.size++;

    if (node.is_uploaded !== false) {
      cluster.uploadedCount++;
    } else {
      cluster.externalCount++;
    }

    // Track most-cited node as centroid
    if (
      !cluster.centroid ||
      (node.citation_count || 0) > (cluster.centroid.citation_count || 0)
    ) {
      cluster.centroid = node;
    }
  });

  return [...clusters.values()];
}

// Theme colors matching Terminal Observatory
const THEME = {
  phosphorGreen: '#D4A039',
  amber: '#ffb700',
  cyan: '#00d4ff',
  background: '#0a0a0a',
  nodeBorder: '#1a1a1a',
  edgeColor: '#333333',
  textColor: '#e0e0e0',
  uploadedNode: '#D4A039',
  externalNode: '#ffb700',
  selectedBorder: '#00d4ff',
};

export const CitationGraph: React.FC<CitationGraphProps> = ({
  data,
  loading = false,
  onNodeClick,
  onNodeHover,
  onEdgeClick,
  selectedNodeId,
  height = 600,
  className = '',
  clusteringThreshold = 1000,
  enableClustering = true,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const [isClusteredView, setIsClusteredView] = useState(false);
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(
    new Set()
  );
  const [clusters, setClusters] = useState<ClusterInfo[]>([]);

  // Determine if clustering should be active
  const shouldCluster = useMemo(() => {
    return enableClustering && data.nodes.length >= clusteringThreshold;
  }, [enableClustering, data.nodes.length, clusteringThreshold]);

  // Compute clusters when data changes
  const clusterData = useMemo(() => {
    if (!shouldCluster) return null;

    const clusterLabels = detectCommunities(data.nodes, data.edges);
    const clusterInfos = buildClusters(data.nodes, clusterLabels);
    return { labels: clusterLabels, infos: clusterInfos };
  }, [shouldCluster, data.nodes, data.edges]);

  // Update clusters state
  useEffect(() => {
    if (clusterData) {
      setClusters(clusterData.infos);
      setIsClusteredView(true);
    } else {
      setClusters([]);
      setIsClusteredView(false);
    }
  }, [clusterData]);

  // Convert data to Cytoscape elements format
  const convertToElements = useCallback(
    (graphData: GraphData): ElementDefinition[] => {
      // Standard non-clustered view
      if (!isClusteredView || !clusterData) {
        const nodes = graphData.nodes.map((node) => {
          const { id, ...rest } = node;
          return {
            data: {
              id,
              label: node.title || 'Untitled',
              ...rest,
            },
            position: node.position || undefined,
          } as ElementDefinition;
        });

        const edges: ElementDefinition[] = graphData.edges.map((edge) => ({
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            type: edge.type || 'CITES',
            confidence: edge.confidence || 1.0,
          },
        }));

        return [...nodes, ...edges];
      }

      // Clustered view - show cluster nodes + expanded cluster contents
      const elements: ElementDefinition[] = [];
      const visibleNodeIds = new Set<string>();

      // Add cluster nodes
      clusterData.infos.forEach((cluster) => {
        const isExpanded = expandedClusters.has(cluster.id);

        if (!isExpanded) {
          // Show cluster as a single compound node
          elements.push({
            data: {
              id: cluster.id,
              label: `${cluster.size} papers`,
              isCluster: true,
              clusterSize: cluster.size,
              uploadedCount: cluster.uploadedCount,
              externalCount: cluster.externalCount,
              centroidTitle: cluster.centroid?.title || 'Cluster',
            },
          });
          // Track all nodes in this cluster as "visible" via cluster
          cluster.nodeIds.forEach((id) => visibleNodeIds.add(id));
        } else {
          // Show individual nodes for expanded cluster
          cluster.nodeIds.forEach((nodeId) => {
            const node = graphData.nodes.find((n) => n.id === nodeId);
            if (node) {
              const { id, ...rest } = node;
              elements.push({
                data: {
                  id,
                  label: node.title || 'Untitled',
                  parent: cluster.id, // Compound node parent
                  ...rest,
                },
                position: node.position || undefined,
              } as ElementDefinition);
              visibleNodeIds.add(nodeId);
            }
          });

          // Add parent compound node for expanded cluster
          elements.push({
            data: {
              id: cluster.id,
              label: `${cluster.size} papers`,
              isCluster: true,
              isExpanded: true,
              clusterSize: cluster.size,
              uploadedCount: cluster.uploadedCount,
              externalCount: cluster.externalCount,
            },
          });
        }
      });

      // Add edges between visible elements
      graphData.edges.forEach((edge) => {
        const sourceCluster = clusterData.labels.get(edge.source);
        const targetCluster = clusterData.labels.get(edge.target);

        // Determine actual source/target (node or cluster)
        const sourceVisible = expandedClusters.has(sourceCluster || '');
        const targetVisible = expandedClusters.has(targetCluster || '');

        const actualSource = sourceVisible ? edge.source : sourceCluster;
        const actualTarget = targetVisible ? edge.target : targetCluster;

        if (actualSource && actualTarget && actualSource !== actualTarget) {
          const edgeId = `${actualSource}-${actualTarget}`;
          // Avoid duplicate edges
          if (!elements.some((e) => e.data?.id === edgeId)) {
            elements.push({
              data: {
                id: edgeId,
                source: actualSource,
                target: actualTarget,
                type: edge.type || 'CITES',
                confidence: edge.confidence || 1.0,
              },
            });
          }
        }
      });

      return elements;
    },
    [isClusteredView, clusterData, expandedClusters]
  );

  // Toggle cluster expansion
  const toggleCluster = useCallback((clusterId: string) => {
    setExpandedClusters((prev) => {
      const next = new Set(prev);
      if (next.has(clusterId)) {
        next.delete(clusterId);
      } else {
        next.add(clusterId);
      }
      return next;
    });
  }, []);

  // Expand all clusters
  const expandAllClusters = useCallback(() => {
    if (clusterData) {
      setExpandedClusters(new Set(clusterData.infos.map((c) => c.id)));
    }
  }, [clusterData]);

  // Collapse all clusters
  const collapseAllClusters = useCallback(() => {
    setExpandedClusters(new Set());
  }, []);

  // Calculate node size based on citation count
  const getNodeSize = (citationCount: number = 0): number => {
    const minSize = 30;
    const maxSize = 80;
    const scaleFactor = Math.log10(citationCount + 1) / 3;
    return Math.min(maxSize, minSize + scaleFactor * (maxSize - minSize));
  };

  // Initialize Cytoscape
  useEffect(() => {
    if (!containerRef.current || loading) return;

    // Clean up existing instance
    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const elements = convertToElements(data);

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        // Regular node styles
        {
          selector: 'node[!isCluster]',
          style: {
            'background-color': (ele: NodeSingular) =>
              ele.data('is_uploaded') !== false
                ? THEME.uploadedNode
                : THEME.externalNode,
            'border-color': THEME.nodeBorder,
            'border-width': 2,
            width: (ele: NodeSingular) =>
              getNodeSize(ele.data('citation_count') || 0),
            height: (ele: NodeSingular) =>
              getNodeSize(ele.data('citation_count') || 0),
            label: 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 8,
            'font-size': 10,
            'font-family': 'JetBrains Mono, monospace',
            color: THEME.textColor,
            'text-outline-color': THEME.background,
            'text-outline-width': 2,
            'text-max-width': 120 as any,
            'text-wrap': 'ellipsis',
            opacity: 0.9,
          },
        },
        // Cluster node styles (collapsed)
        {
          selector: 'node[isCluster][!isExpanded]',
          style: {
            'background-color': THEME.cyan,
            'background-opacity': 0.3,
            'border-color': THEME.cyan,
            'border-width': 3,
            'border-style': 'dashed',
            width: (ele: NodeSingular) =>
              50 + Math.sqrt(ele.data('clusterSize') || 1) * 8,
            height: (ele: NodeSingular) =>
              50 + Math.sqrt(ele.data('clusterSize') || 1) * 8,
            shape: 'round-rectangle',
            label: 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': 12,
            'font-weight': 'bold',
            'font-family': 'JetBrains Mono, monospace',
            color: THEME.textColor,
            'text-outline-color': THEME.background,
            'text-outline-width': 2,
          },
        },
        // Cluster node styles (expanded - compound parent)
        {
          selector: 'node[isCluster][isExpanded]',
          style: {
            'background-color': THEME.cyan,
            'background-opacity': 0.1,
            'border-color': THEME.cyan,
            'border-width': 2,
            'border-style': 'solid',
            shape: 'round-rectangle',
            padding: 20 as any,
            label: 'data(label)',
            'text-valign': 'top',
            'text-halign': 'center',
            'font-size': 10,
            'font-family': 'JetBrains Mono, monospace',
            color: THEME.cyan,
            'text-margin-y': -10,
          },
        },
        // Selected node style
        {
          selector: 'node:selected',
          style: {
            'border-color': THEME.selectedBorder,
            'border-width': 4,
            opacity: 1,
          },
        },
        // Hovered node style
        {
          selector: 'node:active',
          style: {
            'overlay-opacity': 0.1,
            'overlay-color': THEME.cyan,
          },
        },
        // Edge styles
        {
          selector: 'edge',
          style: {
            width: (ele: EdgeSingular) => 1 + (ele.data('confidence') || 1) * 2,
            'line-color': THEME.edgeColor,
            'target-arrow-color': THEME.edgeColor,
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            opacity: 0.6,
          },
        },
        // Selected edge style
        {
          selector: 'edge:selected',
          style: {
            'line-color': THEME.cyan,
            'target-arrow-color': THEME.cyan,
            opacity: 1,
          },
        },
        // Highlighted path (connected to selected)
        {
          selector: '.highlighted',
          style: {
            opacity: 1,
          },
        },
        {
          selector: '.faded',
          style: {
            opacity: 0.2,
          },
        },
      ],
      layout: {
        name: 'cose-bilkent',
        // @ts-expect-error - cose-bilkent options
        quality: 'default',
        randomize: !data.nodes.some((n) => n.position),
        animate: false,
        nodeDimensionsIncludeLabels: true,
        idealEdgeLength: 100,
        nodeRepulsion: 8000,
        edgeElasticity: 0.45,
        nestingFactor: 0.1,
        gravity: 0.25,
        numIter: 2500,
        tile: true,
        tilingPaddingVertical: 10,
        tilingPaddingHorizontal: 10,
      },
      minZoom: 0.1,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    });

    // Event handlers
    cyRef.current.on('tap', 'node', (evt) => {
      const node = evt.target;
      const nodeData = node.data();

      // Handle cluster node click - toggle expansion
      if (nodeData.isCluster) {
        toggleCluster(nodeData.id);
        return;
      }

      // Regular node click
      // Highlight connected elements
      cyRef.current?.elements().removeClass('highlighted faded');
      node.addClass('highlighted');
      node.connectedEdges().addClass('highlighted');
      node.neighborhood('node').addClass('highlighted');
      cyRef.current?.elements().not('.highlighted').addClass('faded');

      onNodeClick?.(nodeData as GraphNode);
    });

    cyRef.current.on('tap', 'edge', (evt) => {
      const edge = evt.target;
      const edgeData = edge.data() as GraphEdge;
      onEdgeClick?.(edgeData);
    });

    cyRef.current.on('tap', (evt) => {
      if (evt.target === cyRef.current) {
        // Clicked on background - clear selection
        cyRef.current?.elements().removeClass('highlighted faded');
      }
    });

    cyRef.current.on('mouseover', 'node', (evt) => {
      const nodeData = evt.target.data() as GraphNode;
      onNodeHover?.(nodeData);
      containerRef.current!.style.cursor = 'pointer';
    });

    cyRef.current.on('mouseout', 'node', () => {
      onNodeHover?.(null);
      containerRef.current!.style.cursor = 'default';
    });

    setIsInitialized(true);

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, [
    data,
    loading,
    convertToElements,
    onNodeClick,
    onEdgeClick,
    onNodeHover,
    toggleCluster,
    expandedClusters,
  ]);

  // Handle external node selection
  useEffect(() => {
    if (!cyRef.current || !selectedNodeId) return;

    const node = cyRef.current.getElementById(selectedNodeId);
    if (node.length > 0) {
      cyRef.current.elements().removeClass('highlighted faded');
      node.addClass('highlighted');
      node.connectedEdges().addClass('highlighted');
      node.neighborhood('node').addClass('highlighted');
      cyRef.current.elements().not('.highlighted').addClass('faded');

      // Center on selected node
      cyRef.current.animate(
        {
          center: { eles: node },
          zoom: 1.5,
        },
        {
          duration: 300,
        }
      );
    }
  }, [selectedNodeId]);

  // Utility functions exposed to parent
  const fitGraph = useCallback(() => {
    cyRef.current?.fit(undefined, 50);
  }, []);

  const zoomIn = useCallback(() => {
    const currentZoom = cyRef.current?.zoom() || 1;
    cyRef.current?.zoom(currentZoom * 1.2);
  }, []);

  const zoomOut = useCallback(() => {
    const currentZoom = cyRef.current?.zoom() || 1;
    cyRef.current?.zoom(currentZoom / 1.2);
  }, []);

  const resetView = useCallback(() => {
    cyRef.current?.elements().removeClass('highlighted faded');
    cyRef.current?.fit(undefined, 50);
  }, []);

  if (loading) {
    return (
      <div
        className={`flex items-center justify-center bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg ${className}`}
        style={{ height }}
      >
        <div className="flex flex-col items-center gap-2">
          <Loader2 className="h-8 w-8 animate-spin text-sol" />
          <span className="text-sm text-muted-foreground font-mono">
            Loading citation graph...
          </span>
        </div>
      </div>
    );
  }

  if (!data.nodes.length) {
    return (
      <div
        className={`flex items-center justify-center bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg ${className}`}
        style={{ height }}
      >
        <div className="text-center">
          <p className="text-muted-foreground font-mono">
            No citations to display
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            Extract citations from documents to build the graph
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`relative ${className}`}>
      {/* Graph container */}
      <div
        ref={containerRef}
        className="w-full bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg"
        style={{ height }}
      />

      {/* Controls overlay */}
      <div className="absolute top-4 right-4 flex flex-col gap-2">
        <IconButton
          onClick={zoomIn}
          className="p-2 bg-[#1a1a1a] border border-[#333] rounded hover:bg-[#252525] text-sol"
          icon={<ZoomIn className="w-4 h-4" />}
          label="Zoom In"
        />
        <IconButton
          onClick={zoomOut}
          className="p-2 bg-[#1a1a1a] border border-[#333] rounded hover:bg-[#252525] text-sol"
          icon={<ZoomOut className="w-4 h-4" />}
          label="Zoom Out"
        />
        <IconButton
          onClick={fitGraph}
          className="p-2 bg-[#1a1a1a] border border-[#333] rounded hover:bg-[#252525] text-sol"
          icon={<Maximize className="w-4 h-4" />}
          label="Fit to View"
        />
        <IconButton
          onClick={resetView}
          className="p-2 bg-[#1a1a1a] border border-[#333] rounded hover:bg-[#252525] text-sol"
          icon={<RotateCcw className="w-4 h-4" />}
          label="Reset View"
        />

        {/* Clustering controls */}
        {isClusteredView && (
          <>
            <div className="h-px bg-[#333] my-1" />
            <IconButton
              onClick={expandAllClusters}
              className="p-2 bg-[#1a1a1a] border border-[#333] rounded hover:bg-[#252525] text-brand-cyan"
              icon={<Layers className="w-4 h-4" />}
              label="Expand All Clusters"
            />
            <IconButton
              onClick={collapseAllClusters}
              className="p-2 bg-[#1a1a1a] border border-[#333] rounded hover:bg-[#252525] text-brand-cyan"
              icon={<Minimize2 className="w-4 h-4" />}
              label="Collapse All Clusters"
            />
          </>
        )}
      </div>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-[#1a1a1a]/90 border border-[#333] rounded p-3">
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-sol" />
            <span className="text-muted-foreground">Uploaded</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-helios" />
            <span className="text-muted-foreground">External</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-[#333]" />
            <span className="text-muted-foreground">Cites</span>
          </div>
          {isClusteredView && (
            <div className="flex items-center gap-1.5">
              <div className="w-4 h-3 rounded border-2 border-dashed border-brand-cyan bg-brand-cyan/20" />
              <span className="text-muted-foreground">Cluster</span>
            </div>
          )}
        </div>
      </div>

      {/* Stats */}
      {data.metadata && (
        <div className="absolute top-4 left-4 bg-[#1a1a1a]/90 border border-[#333] rounded px-3 py-2">
          <div className="text-xs font-mono text-muted-foreground">
            <span className="text-sol">
              {data.metadata.total_nodes.toLocaleString()}
            </span>{' '}
            nodes
            <span className="mx-2">|</span>
            <span className="text-sol">
              {data.metadata.total_edges.toLocaleString()}
            </span>{' '}
            edges
            <span className="mx-2">|</span>
            depth: <span className="text-sol">{data.metadata.depth}</span>
            {isClusteredView && (
              <>
                <span className="mx-2">|</span>
                <span className="text-brand-cyan">{clusters.length}</span>{' '}
                clusters
                {expandedClusters.size > 0 && (
                  <span className="text-muted-foreground">
                    {' '}
                    ({expandedClusters.size} expanded)
                  </span>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default CitationGraph;
