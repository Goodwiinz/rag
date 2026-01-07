/**
 * EntityGraph Component
 * Interactive visualization of entities and their relationships
 */

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { THEME } from '@/theme/constants';
import { Entity, GraphEdge } from '@/types/entity';
import { Download, RefreshCw, ZoomIn, ZoomOut } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';

interface EntityGraphProps {
  entities: Entity[];
  relationships?: GraphEdge[];
  onEntityClick?: (entity: Entity) => void;
  height?: number;
}

export const EntityGraph: React.FC<EntityGraphProps> = ({
  entities,
  relationships = [],
  onEntityClick,
  height = 600
}) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const [selectedEntity, setSelectedEntity] = useState<Entity | null>(null);
  const [loading, setLoading] = useState(false);
  const [d3Loaded, setD3Loaded] = useState(false);

  const typeColors: Record<string, string> = {
    PERSON: '#3B82F6',
    ORGANIZATION: '#10B981',
    LOCATION: THEME.colors.warning, // Amber
    CONCEPT: '#8B5CF6',
    EVENT: THEME.colors.error,
    PRODUCT: '#6366F1',
    DATE: '#6B7280',
    TECHNOLOGY: '#EC4899',
    DOCUMENT: '#F97316'
  };

  const prepareGraphData = () => {
    // Create nodes
    const nodes = entities.map(entity => ({
      id: entity.id,
      name: entity.name,
      type: entity.type || 'UNKNOWN',
      color: typeColors[entity.type] || '#9CA3AF',
      radius: 20 + (entity.confidence || 0.8) * 10
    }));

    // Create links from relationships
    const links = relationships
      .filter(rel =>
        entities.find(e => e.id === rel.source) &&
        entities.find(e => e.id === rel.target)
      )
      .map(rel => ({
        source: rel.source,
        target: rel.target,
        type: rel.type,
        strength: rel.weight || rel.strength || 0.5,
        confidence: rel.confidence || 0.8
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
    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(links)
        .id((d: any) => d.id)
        .strength((d: any) => d.strength || 0.5)
      )
      .force('charge', d3.forceManyBody().strength(-1000))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius((d: any) => d.radius + 5));

    // Create container
    const g = svg.append('g');

    // Add zoom behavior
    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event: any) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom as any);

    // Create arrow markers
    svg.append('defs').selectAll('marker')
      .data(['arrow'])
      .enter().append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#999');

    // Create links
    const link = g.append('g')
      .selectAll('line')
      .data(links)
      .enter().append('line')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', (d: any) => Math.sqrt(d.strength || 0.5) * 3)
      .attr('marker-end', 'url(#arrow)');

    // Create node groups
    const node = g.append('g')
      .selectAll('g')
      .data(nodes)
      .enter().append('g')
      .call((d3.drag() as d3.DragBehavior<SVGGElement, any, any>)
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
    node.append('circle')
      .attr('r', (d: any) => d.radius)
      .attr('fill', (d: any) => d.color)
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .on('click', (event: any, d: any) => {
        const entity = entities.find(e => e.id === d.id);
        if (entity) {
          setSelectedEntity(entity);
          onEntityClick?.(entity);
        }
      })
      .on('mouseover', function(this: SVGCircleElement, event: any, d: any) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('r', d.radius * 1.2);
      })
      .on('mouseout', function(this: SVGCircleElement, event: any, d: any) {
        d3.select(this)
          .transition()
          .duration(200)
          .attr('r', d.radius);
      });

    // Add labels
    node.append('text')
      .text((d: any) => d.name)
      .attr('x', 0)
      .attr('y', (d: any) => d.radius + 15)
      .attr('text-anchor', 'middle')
      .style('font-size', '12px')
      .style('font-weight', 'bold')
      .style('fill', THEME.colors.textSubtle)
      .style('pointer-events', 'none');

    // Add type labels
    node.append('text')
      .text((d: any) => d.type)
      .attr('x', 0)
      .attr('y', (d: any) => d.radius + 30)
      .attr('text-anchor', 'middle')
      .style('font-size', '10px')
      .style('fill', '#6B7280')
      .style('pointer-events', 'none');

    // Update positions on tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);

      node
        .attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });
  };

  const handleZoomIn = () => {
    if (!window.d3 || !svgRef.current) return;
    const d3 = window.d3;
    const svg = d3.select(svgRef.current);
    const zoom = d3.zoom();
    svg.transition().duration(300).call(zoom.scaleBy as any, 1.3);
  };

  const handleZoomOut = () => {
    if (!window.d3 || !svgRef.current) return;
    const d3 = window.d3;
    const svg = d3.select(svgRef.current);
    const zoom = d3.zoom();
    svg.transition().duration(300).call(zoom.scaleBy as any, 0.7);
  };

  const handleReset = () => {
    if (!window.d3 || !svgRef.current) return;
    const d3 = window.d3;
    const svg = d3.select(svgRef.current);
    const zoom = d3.zoom();
    svg.transition().duration(300).call(zoom.transform as any, d3.zoomIdentity);
  };

  const exportGraph = () => {
    if (!svgRef.current) return;

    const svgData = new XMLSerializer().serializeToString(svgRef.current);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const img = new Image();

    canvas.width = svgRef.current.clientWidth;
    canvas.height = height;

    img.onload = () => {
      ctx?.drawImage(img, 0, 0);
      const png = canvas.toDataURL('image/png');
      const downloadLink = document.createElement('a');
      downloadLink.download = 'entity-graph.png';
      downloadLink.href = png;
      downloadLink.click();
    };

    img.src = 'data:image/svg+xml;base64,' + btoa(svgData);
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
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Entity Relationship Graph</CardTitle>
          <div className="flex items-center space-x-2">
            <Button variant="outline" size="sm" onClick={handleZoomIn}>
              <ZoomIn className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={handleZoomOut}>
              <ZoomOut className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={handleReset}>
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={exportGraph}>
              <Download className="h-4 w-4 mr-2" />
              Export
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {entities.length === 0 ? (
          <div className="flex items-center justify-center h-[400px] text-gray-500">
            No entities to display
          </div>
        ) : (
          <>
            <div className="mb-4 flex flex-wrap gap-2">
              <span className="text-sm text-gray-600">Entity Types:</span>
              {Object.entries(typeColors).map(([type, color]) => (
                <Badge
                  key={type}
                  variant="outline"
                  style={{ borderColor: color, color }}
                  className="text-xs"
                >
                  {type}
                </Badge>
              ))}
            </div>
            <div className="border rounded-lg overflow-hidden">
              <svg
                ref={svgRef}
                width="100%"
                height={height}
                style={{ cursor: 'grab' }}
              />
            </div>
            {selectedEntity && (
              <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                <h3 className="font-semibold mb-2">Selected Entity</h3>
                <p><strong>Name:</strong> {selectedEntity.name}</p>
                <p><strong>Type:</strong> {selectedEntity.type}</p>
                <p><strong>Confidence:</strong> {((selectedEntity.confidence || 0) * 100).toFixed(1)}%</p>
                {selectedEntity.metadata?.description && (
                  <p><strong>Description:</strong> {selectedEntity.metadata.description}</p>
                )}
              </div>
            )}
          </>
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