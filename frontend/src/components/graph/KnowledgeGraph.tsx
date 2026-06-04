import React, {
  useState,
  useCallback,
  useEffect,
  useRef,
  useMemo,
} from 'react';
import {
  ShareIcon,
  ArrowDownTrayIcon,
  MagnifyingGlassIcon,
  AdjustmentsHorizontalIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  PlayIcon,
  PauseIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { Entity, Relationship, GraphData, GraphFilters } from '@/types/search';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { IconButton } from '@/components/ui/icon-button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  createLayout,
  LayoutBounds,
  GraphNode,
  GraphEdge,
} from './GraphLayout';

interface KnowledgeGraphProps {
  queryId?: string;
  documentIds?: string[];
  initialFilters?: Partial<GraphFilters>;
  onEntityClick?: (entity: Entity) => void;
  onRelationshipClick?: (relationship: Relationship) => void;
  onGraphChange?: (data: GraphData) => void;
  className?: string;
}

interface GraphNodeComponentProps {
  node: GraphNode;
  isHovered: boolean;
  isSelected: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onClick: () => void;
}

interface GraphEdgeComponentProps {
  edge: GraphEdge;
  isHighlighted: boolean;
  onClick: () => void;
}

const ENTITY_TYPE_COLORS = {
  person: '#4F46E5',
  organization: '#059669',
  location: '#DC2626',
  concept: '#7C3AED',
  date: '#EA580C',
  product: '#0891B2',
};

const ENTITY_TYPE_ICONS = {
  person: '👤',
  organization: '🏢',
  location: '📍',
  concept: '💡',
  date: '📅',
  product: '📦',
};

const GraphNodeComponent: React.FC<GraphNodeComponentProps> = ({
  node,
  isHovered,
  isSelected,
  onMouseEnter,
  onMouseLeave,
  onClick,
}) => {
  const getNodeSize = useCallback(() => {
    const baseSize = 8;
    const confidenceFactor = 0.5 + node.confidence * 0.5;
    const mentionsFactor = Math.log(1 + node.mentions) / Math.log(10);
    return baseSize * confidenceFactor * mentionsFactor;
  }, [node.confidence, node.mentions]);

  const getNodeColor = useCallback(() => {
    return ENTITY_TYPE_COLORS[node.type] || '#6B7280';
  }, [node.type]);

  const size = getNodeSize();
  const color = getNodeColor();

  return (
    <g
      className={cn(
        'cursor-pointer transition-all duration-200',
        isHovered && 'opacity-100',
        !isHovered && 'opacity-80',
        isSelected && 'opacity-100'
      )}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onClick}
    >
      {/* Node shadow */}
      <circle
        cx={node.x}
        cy={node.y}
        r={size + 2}
        fill="black"
        fillOpacity={0.1}
        className={cn(
          isHovered && 'fill-opacity-0.2',
          isSelected && 'fill-opacity-0.3'
        )}
      />

      {/* Node circle */}
      <circle
        cx={node.x}
        cy={node.y}
        r={size}
        fill={color}
        stroke="white"
        strokeWidth={2}
        className={cn(
          isHovered && 'stroke-width-3',
          isSelected && 'stroke-width-4'
        )}
      />

      {/* Node icon/label */}
      <text
        x={node.x}
        y={node.y}
        textAnchor="middle"
        dominantBaseline="middle"
        fill="white"
        fontSize={Math.max(10, size * 0.8)}
        fontWeight="bold"
        pointerEvents="none"
      >
        {ENTITY_TYPE_ICONS[node.type] || node.name.charAt(0).toUpperCase()}
      </text>

      {/* Node label on hover */}
      {isHovered && (
        <g>
          <rect
            x={node.x - 40}
            y={node.y + size + 5}
            width={80}
            height={20}
            fill="white"
            stroke={color}
            strokeWidth={1}
            rx={4}
          />
          <text
            x={node.x}
            y={node.y + size + 18}
            textAnchor="middle"
            dominantBaseline="middle"
            fill={color}
            fontSize={10}
            fontWeight="medium"
            pointerEvents="none"
          >
            {node.name.length > 12
              ? node.name.substring(0, 12) + '...'
              : node.name}
          </text>
        </g>
      )}
    </g>
  );
};

const GraphEdgeComponent: React.FC<GraphEdgeComponentProps> = ({
  edge,
  isHighlighted,
  onClick,
}) => {
  const getEdgeWidth = useCallback(() => {
    const baseWidth = 1;
    return baseWidth + edge.confidence * edge.weight * 2;
  }, [edge.confidence, edge.weight]);

  const getEdgeColor = useCallback(() => {
    return isHighlighted ? '#4F46E5' : '#9CA3AF';
  }, [isHighlighted]);

  const width = getEdgeWidth();
  const color = getEdgeColor();

  // Calculate midpoint for label
  const midX = (edge.source.x + edge.target.x) / 2;
  const midY = (edge.source.y + edge.target.y) / 2;

  return (
    <g
      className={cn(
        'cursor-pointer transition-all duration-200',
        isHighlighted ? 'opacity-100' : 'opacity-60'
      )}
      onClick={onClick}
    >
      {/* Edge line */}
      <line
        x1={edge.source.x}
        y1={edge.source.y}
        x2={edge.target.x}
        y2={edge.target.y}
        stroke={color}
        strokeWidth={width}
        className={cn(isHighlighted && 'stroke-2')}
      />

      {/* Relationship label on hover/highlight */}
      {isHighlighted && (
        <g>
          <rect
            x={midX - 30}
            y={midY - 10}
            width={60}
            height={20}
            fill="white"
            stroke={color}
            strokeWidth={1}
            rx={4}
          />
          <text
            x={midX}
            y={midY}
            textAnchor="middle"
            dominantBaseline="middle"
            fill={color}
            fontSize={9}
            fontWeight="medium"
            pointerEvents="none"
          >
            {edge.relationship_type.length > 10
              ? edge.relationship_type.substring(0, 10) + '...'
              : edge.relationship_type}
          </text>
        </g>
      )}
    </g>
  );
};

export const KnowledgeGraph: React.FC<KnowledgeGraphProps> = ({
  queryId,
  documentIds,
  initialFilters,
  onEntityClick,
  onRelationshipClick,
  onGraphChange,
  className,
}) => {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<string | null>(null);
  const [highlightedEdges, setHighlightedEdges] = useState<Set<string>>(
    new Set()
  );
  const [layout, setLayout] = useState<'force' | 'hierarchical' | 'circular'>(
    'force'
  );
  const [isAnimating, setIsAnimating] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Calculate bounds for layout
  const bounds: LayoutBounds = useMemo(
    () => ({
      width: 800,
      height: 600,
      padding: 50,
    }),
    []
  );

  // Load graph data
  const loadGraphData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Simulate API call - in real implementation, use the actual API
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // Mock data for demonstration
      const mockEntities: Entity[] = [
        {
          id: '1',
          name: 'Machine Learning',
          type: 'concept',
          confidence: 0.95,
          description: 'AI and machine learning technologies',
          aliases: ['ML', 'Artificial Intelligence'],
          mentions: 45,
          first_seen: '2024-01-01T00:00:00Z',
          last_seen: '2024-10-14T00:00:00Z',
          document_ids: ['doc1', 'doc2'],
          metadata: {},
        },
        {
          id: '2',
          name: 'Natural Language Processing',
          type: 'concept',
          confidence: 0.88,
          description: 'Processing and understanding human language',
          aliases: ['NLP'],
          mentions: 32,
          first_seen: '2024-01-01T00:00:00Z',
          last_seen: '2024-10-14T00:00:00Z',
          document_ids: ['doc1', 'doc3'],
          metadata: {},
        },
        {
          id: '3',
          name: 'Deep Learning',
          type: 'concept',
          confidence: 0.92,
          description: 'Neural network-based learning approaches',
          aliases: ['DL', 'Neural Networks'],
          mentions: 28,
          first_seen: '2024-01-01T00:00:00Z',
          last_seen: '2024-10-14T00:00:00Z',
          document_ids: ['doc2', 'doc4'],
          metadata: {},
        },
        {
          id: '4',
          name: 'Transformer Architecture',
          type: 'concept',
          confidence: 0.85,
          description: 'Attention-based neural architecture',
          aliases: ['Transformer'],
          mentions: 22,
          first_seen: '2024-01-01T00:00:00Z',
          last_seen: '2024-10-14T00:00:00Z',
          document_ids: ['doc3', 'doc4'],
          metadata: {},
        },
        {
          id: '5',
          name: 'OpenAI',
          type: 'organization',
          confidence: 0.9,
          description: 'AI research company',
          aliases: [],
          mentions: 18,
          first_seen: '2024-01-01T00:00:00Z',
          last_seen: '2024-10-14T00:00:00Z',
          document_ids: ['doc1', 'doc5'],
          metadata: {},
        },
      ];

      const mockRelationships: Relationship[] = [
        {
          id: 'r1',
          source_entity_id: '1',
          target_entity_id: '2',
          relationship_type: 'includes',
          confidence: 0.85,
          context: 'Machine learning includes natural language processing',
          document_ids: ['doc1'],
          first_seen: '2024-01-01T00:00:00Z',
          last_seen: '2024-10-14T00:00:00Z',
          weight: 0.8,
          metadata: {},
        },
        {
          id: 'r2',
          source_entity_id: '1',
          target_entity_id: '3',
          relationship_type: 'includes',
          confidence: 0.9,
          context: 'Machine learning includes deep learning',
          document_ids: ['doc2'],
          first_seen: '2024-01-01T00:00:00Z',
          last_seen: '2024-10-14T00:00:00Z',
          weight: 0.9,
          metadata: {},
        },
        {
          id: 'r3',
          source_entity_id: '3',
          target_entity_id: '4',
          relationship_type: 'enables',
          confidence: 0.88,
          context: 'Deep learning enables transformer architecture',
          document_ids: ['doc4'],
          first_seen: '2024-01-01T00:00:00Z',
          last_seen: '2024-10-14T00:00:00Z',
          weight: 0.85,
          metadata: {},
        },
        {
          id: 'r4',
          source_entity_id: '2',
          target_entity_id: '4',
          relationship_type: 'uses',
          confidence: 0.82,
          context: 'NLP uses transformer architecture',
          document_ids: ['doc3'],
          first_seen: '2024-01-01T00:00:00Z',
          last_seen: '2024-10-14T00:00:00Z',
          weight: 0.75,
          metadata: {},
        },
        {
          id: 'r5',
          source_entity_id: '5',
          target_entity_id: '4',
          relationship_type: 'developed',
          confidence: 0.95,
          context: 'OpenAI developed transformer architecture',
          document_ids: ['doc5'],
          first_seen: '2024-01-01T00:00:00Z',
          last_seen: '2024-10-14T00:00:00Z',
          weight: 0.95,
          metadata: {},
        },
      ];

      const newGraphData: GraphData = {
        nodes: mockEntities,
        edges: mockRelationships,
        layout: layout,
        filters: {
          entity_types: initialFilters?.entity_types || [],
          min_confidence: initialFilters?.min_confidence || 0.5,
          date_range: initialFilters?.date_range,
        },
      };

      setGraphData(newGraphData);
      onGraphChange?.(newGraphData);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load graph data'
      );
    } finally {
      setIsLoading(false);
    }
  }, [queryId, documentIds, initialFilters, layout, onGraphChange]);

  // Apply layout to graph data
  const layoutData = useMemo(() => {
    if (!graphData) return null;

    try {
      const layoutAlgorithm = createLayout(
        layout,
        graphData.nodes,
        graphData.edges,
        {
          bounds,
          iterations: layout === 'force' ? 300 : 0,
        }
      );

      return layoutAlgorithm.layout();
    } catch (err) {
      console.error('Layout error:', err);
      return null;
    }
  }, [graphData, layout, bounds]);

  // Calculate highlighted edges based on selected node
  useEffect(() => {
    if (!selectedNode || !layoutData) {
      setHighlightedEdges(new Set());
      return;
    }

    const highlighted = new Set<string>();
    layoutData.edges.forEach((edge) => {
      if (edge.source.id === selectedNode || edge.target.id === selectedNode) {
        highlighted.add(edge.id);
      }
    });
    setHighlightedEdges(highlighted);
  }, [selectedNode, layoutData]);

  // Handle node interactions
  const handleNodeClick = useCallback(
    (node: GraphNode) => {
      setSelectedNode(node.id === selectedNode ? null : node.id);
      const entity = graphData?.nodes.find((n) => n.id === node.id);
      if (entity) {
        onEntityClick?.(entity);
      }
    },
    [selectedNode, graphData, onEntityClick]
  );

  // Handle edge interactions
  const handleEdgeClick = useCallback(
    (edge: GraphEdge) => {
      setSelectedEdge(edge.id === selectedEdge ? null : edge.id);
      onRelationshipClick?.(edge);
    },
    [selectedEdge, onRelationshipClick]
  );

  // Handle zoom
  const handleZoomIn = useCallback(() => {
    setZoom((prev) => Math.min(prev * 1.2, 3));
  }, []);

  const handleZoomOut = useCallback(() => {
    setZoom((prev) => Math.max(prev / 1.2, 0.3));
  }, []);

  const handleResetZoom = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  // Handle pan
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      setIsDragging(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    },
    [pan]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDragging) return;
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    },
    [isDragging, dragStart]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Export graph
  const exportGraph = useCallback(
    (format: 'png' | 'svg' | 'json') => {
      if (!svgRef.current) return;

      switch (format) {
        case 'svg':
          const svgData = new XMLSerializer().serializeToString(svgRef.current);
          const blob = new Blob([svgData], { type: 'image/svg+xml' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'knowledge-graph.svg';
          a.click();
          URL.revokeObjectURL(url);
          break;

        case 'json':
          if (graphData) {
            const jsonData = JSON.stringify(graphData, null, 2);
            const jsonBlob = new Blob([jsonData], { type: 'application/json' });
            const jsonUrl = URL.createObjectURL(jsonBlob);
            const jsonA = document.createElement('a');
            jsonA.href = jsonUrl;
            jsonA.download = 'knowledge-graph.json';
            jsonA.click();
            URL.revokeObjectURL(jsonUrl);
          }
          break;

        case 'png':
          // Canvas-based PNG export would require additional implementation
          console.log('PNG export not implemented');
          break;
      }
    },
    [graphData]
  );

  // Load data on mount
  useEffect(() => {
    loadGraphData();
  }, [loadGraphData]);

  if (isLoading) {
    return (
      <div className={cn('flex items-center justify-center h-96', className)}>
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--nous-sol)] border-t-transparent mx-auto mb-4" />
          <p className="text-foreground">Loading knowledge graph...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('flex items-center justify-center h-96', className)}>
        <div className="text-center">
          <div className="text-[var(--nous-mars)] mb-4">
            <InformationCircleIcon className="h-12 w-12 mx-auto" />
          </div>
          <p className="text-foreground">Failed to load knowledge graph</p>
          <p className="text-sm text-muted-foreground mt-2">{error}</p>
          <Button onClick={loadGraphData} className="mt-4">
            Try Again
          </Button>
        </div>
      </div>
    );
  }

  if (!layoutData) {
    return (
      <div className={cn('flex items-center justify-center h-96', className)}>
        <div className="text-center">
          <p className="text-foreground">No graph data available</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('space-y-4', className)}>
      {/* Controls */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Knowledge Graph</CardTitle>
            <div className="flex items-center space-x-2">
              <Badge variant="outline">{layoutData.nodes.length} nodes</Badge>
              <Badge variant="outline">{layoutData.edges.length} edges</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {/* Layout selector */}
            <div className="flex items-center space-x-2">
              <AdjustmentsHorizontalIcon className="h-4 w-4 text-muted-foreground" />
              <select
                value={layout}
                onChange={(e) => setLayout(e.target.value as any)}
                className="text-sm border border-border rounded px-2 py-1"
              >
                <option value="force">Force Layout</option>
                <option value="hierarchical">Hierarchical</option>
                <option value="circular">Circular</option>
              </select>
            </div>

            {/* Zoom controls */}
            <div className="flex items-center space-x-1">
              <IconButton
                variant="outline"
                size="sm"
                onClick={handleZoomIn}
                icon={<ArrowsPointingOutIcon className="h-4 w-4" />}
                label="Zoom In"
              />
              <IconButton
                variant="outline"
                size="sm"
                onClick={handleZoomOut}
                icon={<ArrowsPointingInIcon className="h-4 w-4" />}
                label="Zoom Out"
              />
              <Button variant="outline" size="sm" onClick={handleResetZoom}>
                Reset
              </Button>
            </div>

            {/* Export controls */}
            <div className="flex items-center space-x-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => exportGraph('svg')}
              >
                <ArrowDownTrayIcon className="h-4 w-4 mr-1" />
                SVG
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => exportGraph('json')}
              >
                <ArrowDownTrayIcon className="h-4 w-4 mr-1" />
                JSON
              </Button>
            </div>

            {/* Refresh */}
            <Button variant="outline" size="sm" onClick={loadGraphData}>
              Refresh
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Graph visualization */}
      <Card ref={containerRef}>
        <CardContent className="p-0">
          <svg
            ref={svgRef}
            width="100%"
            height="600"
            className="cursor-move"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
              {/* Edges */}
              {layoutData.edges.map((edge) => (
                <GraphEdgeComponent
                  key={edge.id}
                  edge={edge}
                  isHighlighted={highlightedEdges.has(edge.id)}
                  onClick={() => handleEdgeClick(edge)}
                />
              ))}

              {/* Nodes */}
              {layoutData.nodes.map((node) => (
                <GraphNodeComponent
                  key={node.id}
                  node={node}
                  isHovered={hoveredNode === node.id}
                  isSelected={selectedNode === node.id}
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                  onClick={() => handleNodeClick(node)}
                />
              ))}
            </g>
          </svg>
        </CardContent>
      </Card>

      {/* Legend */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Legend</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {Object.entries(ENTITY_TYPE_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center space-x-2">
                <div
                  className="w-4 h-4 rounded-full"
                  style={{ backgroundColor: color }}
                />
                <span className="text-xs capitalize">{type}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Selected entity details */}
      {selectedNode && (
        <Dialog open={showDetails} onOpenChange={setShowDetails}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Entity Details</DialogTitle>
            </DialogHeader>
            {(() => {
              const entity = graphData?.nodes.find(
                (n) => n.id === selectedNode
              );
              return entity ? (
                <div className="space-y-4">
                  <div>
                    <h3 className="font-semibold text-lg">{entity.name}</h3>
                    <Badge className="mt-1 capitalize">{entity.type}</Badge>
                  </div>

                  {entity.description && (
                    <p className="text-sm text-foreground">
                      {entity.description}
                    </p>
                  )}

                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="font-medium">Confidence:</span>
                      <div className="flex items-center mt-1">
                        <div className="w-full bg-muted rounded-full h-2">
                          <div
                            className="bg-[var(--nous-sol)] h-2 rounded-full"
                            style={{ width: `${entity.confidence * 100}%` }}
                          />
                        </div>
                        <span className="ml-2">
                          {Math.round(entity.confidence * 100)}%
                        </span>
                      </div>
                    </div>

                    <div>
                      <span className="font-medium">Mentions:</span>
                      <p className="mt-1">{entity.mentions}</p>
                    </div>
                  </div>

                  {entity.aliases.length > 0 && (
                    <div>
                      <span className="font-medium text-sm">Aliases:</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {entity.aliases.map((alias, index) => (
                          <Badge
                            key={index}
                            variant="outline"
                            className="text-xs"
                          >
                            {alias}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  <div>
                    <span className="font-medium text-sm">Documents:</span>
                    <p className="text-sm text-foreground mt-1">
                      Found in {entity.document_ids.length} document
                      {entity.document_ids.length !== 1 ? 's' : ''}
                    </p>
                  </div>
                </div>
              ) : null;
            })()}
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

export default KnowledgeGraph;
