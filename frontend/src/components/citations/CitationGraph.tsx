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
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape, { Core, NodeSingular, EdgeSingular } from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import popper from 'cytoscape-popper';
import { Loader2 } from 'lucide-react';

// Register Cytoscape extensions
if (typeof window !== 'undefined') {
  cytoscape.use(coseBilkent);
  cytoscape.use(popper);
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
}

// Theme colors matching Terminal Observatory
const THEME = {
  phosphorGreen: '#00ff9f',
  amber: '#ffb700',
  cyan: '#00d4ff',
  background: '#0a0a0a',
  nodeBorder: '#1a1a1a',
  edgeColor: '#333333',
  textColor: '#e0e0e0',
  uploadedNode: '#00ff9f',
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
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // Convert data to Cytoscape elements format
  const convertToElements = useCallback((graphData: GraphData) => {
    const nodes = graphData.nodes.map((node) => ({
      data: {
        id: node.id,
        label: node.title || 'Untitled',
        ...node,
      },
      position: node.position || undefined,
    }));

    const edges = graphData.edges.map((edge) => ({
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: edge.type || 'CITES',
        confidence: edge.confidence || 1.0,
      },
    }));

    return [...nodes, ...edges];
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
        // Node styles
        {
          selector: 'node',
          style: {
            'background-color': (ele: NodeSingular) =>
              ele.data('is_uploaded') !== false ? THEME.uploadedNode : THEME.externalNode,
            'border-color': THEME.nodeBorder,
            'border-width': 2,
            'width': (ele: NodeSingular) => getNodeSize(ele.data('citation_count') || 0),
            'height': (ele: NodeSingular) => getNodeSize(ele.data('citation_count') || 0),
            'label': 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 8,
            'font-size': 10,
            'font-family': 'JetBrains Mono, monospace',
            'color': THEME.textColor,
            'text-outline-color': THEME.background,
            'text-outline-width': 2,
            'text-max-width': 120,
            'text-wrap': 'ellipsis',
            'opacity': 0.9,
          },
        },
        // Selected node style
        {
          selector: 'node:selected',
          style: {
            'border-color': THEME.selectedBorder,
            'border-width': 4,
            'opacity': 1,
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
            'width': (ele: EdgeSingular) => 1 + (ele.data('confidence') || 1) * 2,
            'line-color': THEME.edgeColor,
            'target-arrow-color': THEME.edgeColor,
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'opacity': 0.6,
          },
        },
        // Selected edge style
        {
          selector: 'edge:selected',
          style: {
            'line-color': THEME.cyan,
            'target-arrow-color': THEME.cyan,
            'opacity': 1,
          },
        },
        // Highlighted path (connected to selected)
        {
          selector: '.highlighted',
          style: {
            'opacity': 1,
          },
        },
        {
          selector: '.faded',
          style: {
            'opacity': 0.2,
          },
        },
      ],
      layout: {
        name: 'cose-bilkent',
        // @ts-ignore - cose-bilkent options
        quality: 'default',
        randomize: !data.nodes.some(n => n.position),
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
      const nodeData = node.data() as GraphNode;

      // Highlight connected elements
      cyRef.current?.elements().removeClass('highlighted faded');
      node.addClass('highlighted');
      node.connectedEdges().addClass('highlighted');
      node.neighborhood('node').addClass('highlighted');
      cyRef.current?.elements().not('.highlighted').addClass('faded');

      onNodeClick?.(nodeData);
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
  }, [data, loading, convertToElements, onNodeClick, onEdgeClick, onNodeHover]);

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
      cyRef.current.animate({
        center: { eles: node },
        zoom: 1.5,
      }, {
        duration: 300,
      });
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
          <Loader2 className="h-8 w-8 animate-spin text-[#00ff9f]" />
          <span className="text-sm text-gray-400 font-mono">Loading citation graph...</span>
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
          <p className="text-gray-400 font-mono">No citations to display</p>
          <p className="text-sm text-gray-500 mt-1">
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
        <button
          onClick={zoomIn}
          className="p-2 bg-[#1a1a1a] border border-[#333] rounded hover:bg-[#252525] text-[#00ff9f] font-mono text-sm"
          title="Zoom In"
        >
          +
        </button>
        <button
          onClick={zoomOut}
          className="p-2 bg-[#1a1a1a] border border-[#333] rounded hover:bg-[#252525] text-[#00ff9f] font-mono text-sm"
          title="Zoom Out"
        >
          -
        </button>
        <button
          onClick={fitGraph}
          className="p-2 bg-[#1a1a1a] border border-[#333] rounded hover:bg-[#252525] text-[#00ff9f] font-mono text-sm"
          title="Fit to View"
        >
          []
        </button>
        <button
          onClick={resetView}
          className="p-2 bg-[#1a1a1a] border border-[#333] rounded hover:bg-[#252525] text-[#00ff9f] font-mono text-sm"
          title="Reset View"
        >
          R
        </button>
      </div>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 bg-[#1a1a1a]/90 border border-[#333] rounded p-3">
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-[#00ff9f]" />
            <span className="text-gray-400">Uploaded</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-[#ffb700]" />
            <span className="text-gray-400">External</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-6 h-0.5 bg-[#333]" />
            <span className="text-gray-400">Cites</span>
          </div>
        </div>
      </div>

      {/* Stats */}
      {data.metadata && (
        <div className="absolute top-4 left-4 bg-[#1a1a1a]/90 border border-[#333] rounded px-3 py-2">
          <div className="text-xs font-mono text-gray-400">
            <span className="text-[#00ff9f]">{data.metadata.total_nodes}</span> nodes
            <span className="mx-2">|</span>
            <span className="text-[#00ff9f]">{data.metadata.total_edges}</span> edges
            <span className="mx-2">|</span>
            depth: <span className="text-[#00ff9f]">{data.metadata.depth}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default CitationGraph;
