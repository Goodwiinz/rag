/**
 * EntityGraph Component
 * Terminal Observatory themed entity relationship graph
 */

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Entity, GraphEdge } from '@/types/entity';
import { cn } from '@/lib/utils';
import {
  Activity,
  Download,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Network,
} from 'lucide-react';
import { EmptyState } from '@/components/ui/EmptyState';
import React, { useEffect, useRef, useState } from 'react';

interface EntityGraphProps {
  entities: Entity[];
  relationships?: GraphEdge[];
  onEntityClick?: (entity: Entity) => void;
  height?: number;
}

// Terminal Theme Colors
const TERMINAL_COLORS = {
  text: 'var(--nous-fg-1)',
  textDim: 'var(--nous-fg-3)',
  background: 'var(--nous-bg-1)',
  border: 'var(--nous-border-1)',
  primary: 'var(--nous-sol)',
  secondary: 'var(--nous-helios)',
  accent: 'var(--nous-helios)',
  error: '#ff4757',
};

const typeColors: Record<string, string> = {
  PERSON: '#60a5fa', // Blue-400
  ORGANIZATION: '#34d399', // Emerald-400
  LOCATION: '#fbbf24', // Amber-400
  CONCEPT: '#a78bfa', // Purple-400
  EVENT: '#fb7185', // Rose-400
  PRODUCT: '#818cf8', // Indigo-400
  DATE: '#94a3b8', // Slate-400
  TECHNOLOGY: '#22d3ee', // Cyan-400
  DOCUMENT: '#fb923c', // Orange-400
  OTHER: '#9ca3af', // Gray-400
  UNKNOWN: '#6b7280', // Gray-500
};

export const EntityGraph: React.FC<EntityGraphProps> = ({
  entities,
  relationships = [],
  onEntityClick,
  height = 600,
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [d3Loaded, setD3Loaded] = useState(false);

  const prepareGraphData = () => {
    // Create nodes
    const nodes = entities.map((entity) => ({
      id: entity.id,
      name: entity.name,
      type: entity.type || 'UNKNOWN',
      color: typeColors[entity.type] || typeColors.UNKNOWN,
      radius: 20 + (entity.confidence || 0.8) * 10,
    }));

    // Create links from relationships
    const links = relationships
      .filter(
        (rel) =>
          entities.find((e) => e.id === rel.source) &&
          entities.find((e) => e.id === rel.target)
      )
      .map((rel) => ({
        source: rel.source,
        target: rel.target,
        type: rel.type,
        strength: rel.weight || rel.strength || 0.5,
        confidence: rel.confidence || 0.8,
      }));

    return { nodes, links };
  };

  const renderGraph = () => {
    if (!svgRef.current || !window.d3 || entities.length === 0) return;

    const d3 = window.d3;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth;
    const { nodes, links } = prepareGraphData();

    // Create simulation
    const simulation = d3
      .forceSimulation(nodes as any)
      .force(
        'link',
        d3
          .forceLink(links)
          .id((d: any) => d.id)
          .strength((d: any) => d.strength || 0.5)
      )
      .force('charge', d3.forceManyBody().strength(-800))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force(
        'collision',
        d3.forceCollide().radius((d: any) => d.radius + 10)
      );

    // Create container
    const g = svg.append('g');

    // Add zoom behavior
    const zoom = d3
      .zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event: any) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom as any);

    // Create arrow markers
    svg
      .append('defs')
      .selectAll('marker')
      .data(['arrow'])
      .enter()
      .append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 28) // Adjusted for node radius
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', TERMINAL_COLORS.border);

    // Create links
    const link = g
      .append('g')
      .selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('stroke', TERMINAL_COLORS.border)
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', (d: any) =>
        Math.max(1, Math.sqrt(d.strength || 0.5) * 3)
      );

    // Create node groups
    const node = g
      .append('g')
      .selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .call(
        (d3.drag() as any)
          .on('start', (event: any, d: any) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event: any, d: any) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event: any, d: any) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }) as any
      );

    // Add circles to nodes
    node
      .append('circle')
      .attr('r', (d: any) => d.radius)
      .attr('fill', TERMINAL_COLORS.background) // Dark center
      .attr('stroke', (d: any) => d.color)
      .attr('stroke-width', 2)
      .attr('fill-opacity', 0.8)
      .style('cursor', 'pointer')
      .on('click', (event: any, d: any) => {
        const entity = entities.find((e) => e.id === d.id);
        if (entity) {
          setSelectedEntity(entity);
          onEntityClick?.(entity);
        }
      })
      .on('mouseover', function (this: SVGCircleElement, event: any, d: any) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('r', d.radius * 1.1)
          .attr('stroke-width', 3)
          .attr('stroke-opacity', 1);
      })
      .on('mouseout', function (this: SVGCircleElement, event: any, d: any) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('r', d.radius)
          .attr('stroke-width', 2)
          .attr('stroke-opacity', 1);
      });

    // Add labels
    node
      .append('text')
      .text((d: any) => d.name)
      .attr('x', 0)
      .attr('y', (d: any) => d.radius + 15)
      .attr('text-anchor', 'middle')
      .style('font-size', '10px')
      .style('font-family', "'JetBrains Mono', monospace")
      .style('font-weight', 'bold')
      .style('fill', TERMINAL_COLORS.text)
      .style('pointer-events', 'none')
      .style('text-shadow', '0px 0px 4px #000');

    // Add type labels
    node
      .append('text')
      .text((d: any) => d.type)
      .attr('x', 0)
      .attr('y', (d: any) => d.radius + 28)
      .attr('text-anchor', 'middle')
      .style('font-size', '8px')
      .style('font-family', "'JetBrains Mono', monospace")
      .style('fill', TERMINAL_COLORS.textDim)
      .style('pointer-events', 'none')
      .style('letter-spacing', '1px');

    // Update positions on tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });
  };

  const handleZoomIn = () => {
    if (!window.d3 || !svgRef.current) return;
    const d3 = window.d3;
    const svg = d3.select(svgRef.current);
    const zoom = d3.zoom();
    svg
      .transition()
      .duration(300)
      .call(zoom.scaleBy as any, 1.3);
  };

  const handleZoomOut = () => {
    if (!window.d3 || !svgRef.current) return;
    const d3 = window.d3;
    const svg = d3.select(svgRef.current);
    const zoom = d3.zoom();
    svg
      .transition()
      .duration(300)
      .call(zoom.scaleBy as any, 0.7);
  };

  const handleReset = () => {
    if (!window.d3 || !svgRef.current) return;
    const d3 = window.d3;
    const svg = d3.select(svgRef.current);
    const zoom = d3.zoom();
    svg
      .transition()
      .duration(300)
      .call(zoom.transform as any, d3.zoomIdentity);
  };

  const exportGraph = () => {
    if (!svgRef.current) return;

    const svgData = new XMLSerializer().serializeToString(svgRef.current);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();

    canvas.width = svgRef.current.clientWidth;
    canvas.height = height;

    // Fill background for export
    if (ctx) {
      ctx.fillStyle = TERMINAL_COLORS.background;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
    }

    img.onload = () => {
      ctx?.drawImage(img, 0, 0);
      const png = canvas.toDataURL('image/png');
      const downloadLink = document.createElement('a');
      downloadLink.download = 'entity-graph.png';
      downloadLink.href = png;
      downloadLink.click();
    };

    img.src =
      'data:image/svg+xml;base64,' +
      btoa(unescape(encodeURIComponent(svgData)));
  };

  useEffect(() => {
    // Load D3 library if not already loaded
    if (window.d3) {
      setD3Loaded(true);
      renderGraph();
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://d3js.org/d3.v7.min.js';
    script.async = true;
    script.onload = () => {
      setD3Loaded(true);
      renderGraph();
    };
    document.body.appendChild(script);

    return () => {
      document.body.removeChild(script);
    };
  }, []);

  useEffect(() => {
    if (window.d3 && d3Loaded) {
      renderGraph();
    }
  }, [entities, relationships, d3Loaded]);

  return (
    <Card className="w-full bg-[var(--nous-bg-2)] border-[var(--nous-border-1)] shadow-lg">
      <CardHeader className="border-b border-[var(--nous-border-1)] py-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-xs font-mono font-bold uppercase tracking-widest text-[var(--nous-fg-3)] flex items-center gap-2">
            <Network className="w-4 h-4" />
            Entity_Graph_Viz
          </CardTitle>
          <div className="flex items-center space-x-2">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Zoom in"
              onClick={handleZoomIn}
              className="h-7 w-7 text-[var(--nous-fg-3)] hover:text-[var(--nous-sol)] hover:bg-[var(--nous-sol)]/10"
            >
              <ZoomIn className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Zoom out"
              onClick={handleZoomOut}
              className="h-7 w-7 text-[var(--nous-fg-3)] hover:text-[var(--nous-sol)] hover:bg-[var(--nous-sol)]/10"
            >
              <ZoomOut className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Reset zoom"
              onClick={handleReset}
              className="h-7 w-7 text-[var(--nous-fg-3)] hover:text-[var(--nous-sol)] hover:bg-[var(--nous-sol)]/10"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={exportGraph}
              className="h-7 text-[10px] font-mono text-[var(--nous-fg-3)] hover:text-[var(--nous-helios)] hover:bg-[var(--nous-helios)]/10"
            >
              <Download className="h-3.5 w-3.5 mr-1.5" />
              EXPORT_IMG
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0 bg-background">
        {entities.length === 0 ? (
          <EmptyState
            icon={Activity}
            title="NO_DATA_STREAM"
            description="No entity graph data available. Extract entities from documents to populate the knowledge graph."
            className="py-12"
          />
        ) : (
          <div className="relative">
            {/* Legend Overlay */}
            <div className="absolute top-4 left-4 p-3 bg-[var(--nous-bg-2)]/90 backdrop-blur-sm border border-[var(--nous-border-1)] rounded-lg max-w-[200px] z-10">
              <h4 className="text-[10px] font-mono font-bold text-[var(--nous-fg-3)] uppercase mb-2">
                Node_Types
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(typeColors).map(([type, color]) => (
                  <Badge
                    key={type}
                    variant="outline"
                    className="text-[9px] font-mono border bg-transparent"
                    style={{ borderColor: color, color: color }}
                  >
                    {type}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="overflow-hidden bg-[var(--nous-bg-1)] relative">
              {/* Grid Background Effect */}
              <div
                className="absolute inset-0 pointer-events-none opacity-[0.03]"
                style={{
                  backgroundImage: `linear-gradient(${TERMINAL_COLORS.primary} 1px, transparent 1px), linear-gradient(90deg, ${TERMINAL_COLORS.primary} 1px, transparent 1px)`,
                  backgroundSize: '40px 40px',
                }}
              />

              <svg
                ref={svgRef}
                width="100%"
                height={height}
                style={{ cursor: 'grab' }}
                className="block"
              />
            </div>

            {/* Selected Entity Details Overlay */}
            {selectedEntity && (
              <div className="absolute bottom-4 right-4 p-4 bg-[var(--nous-bg-2)]/95 backdrop-blur-md border border-[var(--nous-border-1)] rounded-lg w-64 shadow-xl z-10 animate-in fade-in slide-in-from-bottom-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-mono text-xs font-bold text-[var(--nous-fg-1)] uppercase tracking-wide">
                    Node_Inspector
                  </h3>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Close entity details"
                    className="h-5 w-5 -mr-2"
                    onClick={() => setSelectedEntity(null)}
                  >
                    <span className="sr-only">Close</span>
                    <svg
                      width="10"
                      height="10"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="text-[var(--nous-fg-3)]"
                    >
                      <line x1="18" y1="6" x2="6" y2="18"></line>
                      <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                  </Button>
                </div>
                <div className="space-y-2 font-mono text-xs">
                  <div className="grid grid-cols-3 gap-1">
                    <span className="text-[var(--nous-fg-3)]">ID:</span>
                    <span className="col-span-2 text-[var(--nous-fg-1)] truncate">
                      {selectedEntity.name}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-1">
                    <span className="text-[var(--nous-fg-3)]">
                      TYPE:
                    </span>
                    <span
                      className="col-span-2"
                      style={{
                        color: typeColors[selectedEntity.type] || '#fff',
                      }}
                    >
                      {selectedEntity.type}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-1">
                    <span className="text-[var(--nous-fg-3)]">
                      CONF:
                    </span>
                    <span className="col-span-2 text-[var(--nous-sol)]">
                      {((selectedEntity.confidence || 0) * 100).toFixed(1)}%
                    </span>
                  </div>
                  {selectedEntity.metadata?.description && (
                    <div className="pt-2 border-t border-[var(--nous-border-1)] mt-2">
                      <p className="text-[var(--nous-fg-3)] line-clamp-3 leading-relaxed">
                        {selectedEntity.metadata.description}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

declare global {
  interface Window {
    d3: any;
  }
}
