'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Loader2, AlertCircle, X } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { getProject } from '@/services/researchEngineService';
import { api } from '@/services/api-client';

// --------------------------------------------------------------------------
// Types
// --------------------------------------------------------------------------

interface EvidenceNode {
  id: string;
  type: 'research_question' | 'sub_question' | 'evidence' | 'source';
  label: string;
  description?: string;
  metadata?: Record<string, unknown>;
}

interface EvidenceEdge {
  source: string;
  target: string;
  label?: string;
}

interface EvidenceGraphData {
  nodes: EvidenceNode[];
  edges: EvidenceEdge[];
}

interface EvidenceMapProps {
  projectId: string;
}

// --------------------------------------------------------------------------
// Constants
// --------------------------------------------------------------------------

const NODE_COLORS: Record<EvidenceNode['type'], string> = {
  research_question: 'var(--nous-helios)',
  sub_question: 'var(--nous-helios)',
  evidence: 'var(--nous-sol)',
  source: 'var(--nous-helios)',
};

const NODE_RADII: Record<EvidenceNode['type'], number> = {
  research_question: 32,
  sub_question: 20,
  evidence: 14,
  source: 14,
};

const NODE_LABELS: Record<EvidenceNode['type'], string> = {
  research_question: 'Research Question',
  sub_question: 'Sub-Question',
  evidence: 'Evidence',
  source: 'Source',
};

// --------------------------------------------------------------------------
// Simple force-layout positioning
// --------------------------------------------------------------------------

interface PositionedNode extends EvidenceNode {
  x: number;
  y: number;
}

function layoutNodes(
  nodes: EvidenceNode[],
  edges: EvidenceEdge[],
  width: number,
  height: number
): PositionedNode[] {
  if (nodes.length === 0) return [];

  const cx = width / 2;
  const cy = height / 2;

  // Group by type for layered layout
  const byType: Record<string, EvidenceNode[]> = {
    research_question: [],
    sub_question: [],
    evidence: [],
    source: [],
  };

  for (const n of nodes) {
    (byType[n.type] ?? byType.evidence).push(n);
  }

  const positioned: PositionedNode[] = [];

  // Research questions at center
  const rqs = byType.research_question;
  rqs.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(rqs.length, 1);
    const r = rqs.length === 1 ? 0 : 40;
    positioned.push({
      ...n,
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    });
  });

  // Sub-questions in inner ring
  const sqs = byType.sub_question;
  sqs.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(sqs.length, 1) - Math.PI / 4;
    const r = 120;
    positioned.push({
      ...n,
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    });
  });

  // Evidence in middle ring
  const evs = byType.evidence;
  evs.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(evs.length, 1);
    const r = 220;
    positioned.push({
      ...n,
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    });
  });

  // Sources in outer ring
  const srcs = byType.source;
  srcs.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(srcs.length, 1) + Math.PI / 6;
    const r = 310;
    positioned.push({
      ...n,
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    });
  });

  return positioned;
}

// --------------------------------------------------------------------------
// Component
// --------------------------------------------------------------------------

export function EvidenceMap({ projectId }: EvidenceMapProps) {
  const router = useRouter();
  const [graphData, setGraphData] = useState<EvidenceGraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<EvidenceNode | null>(null);
  const [projectName, setProjectName] = useState<string>('');

  const SVG_WIDTH = 700;
  const SVG_HEIGHT = 700;

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Try to fetch evidence graph from API
      const data = (await api.get(
        `/api/v1/research-engine/projects/${projectId}/evidence-graph`
      )) as EvidenceGraphData;
      setGraphData(data);
    } catch {
      // API may not exist yet - set empty data as placeholder
      setGraphData({ nodes: [], edges: [] });
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  const fetchProject = useCallback(async () => {
    try {
      const data = (await getProject(projectId)) as { name?: string };
      setProjectName(data.name ?? '');
    } catch {
      // non-critical
    }
  }, [projectId]);

  useEffect(() => {
    fetchGraph();
    fetchProject();
  }, [fetchGraph, fetchProject]);

  const positioned = useMemo(() => {
    if (!graphData) return [];
    return layoutNodes(graphData.nodes, graphData.edges, SVG_WIDTH, SVG_HEIGHT);
  }, [graphData]);

  const nodeById = useMemo(() => {
    const map = new Map<string, PositionedNode>();
    for (const n of positioned) map.set(n.id, n);
    return map;
  }, [positioned]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-sol" />
        <span className="ml-2 font-mono text-sm text-muted-foreground">
          Loading evidence map...
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded">
        <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
        <span className="text-sm text-red-400 font-mono">{error}</span>
      </div>
    );
  }

  const hasData = positioned.length > 0;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={() => router.back()}
          className="p-1.5 rounded hover:bg-white/5 text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Go back"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-mono font-bold text-sol">Evidence Map</h1>
          {projectName && (
            <p className="text-xs font-mono text-muted-foreground mt-0.5">
              {projectName}
            </p>
          )}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4">
          {(
            Object.entries(NODE_LABELS) as [EvidenceNode['type'], string][]
          ).map(([type, label]) => (
            <div key={type} className="flex items-center gap-1.5">
              <span
                className="inline-block rounded-full"
                style={{
                  width: Math.max(NODE_RADII[type] * 0.6, 8),
                  height: Math.max(NODE_RADII[type] * 0.6, 8),
                  backgroundColor: NODE_COLORS[type],
                  opacity: 0.7,
                }}
              />
              <span className="text-xs font-mono text-muted-foreground">
                {label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {!hasData ? (
        <div className="flex flex-col items-center justify-center py-20 border border-dashed border-white/10 rounded">
          <p className="text-muted-foreground font-mono text-sm mb-1">
            No evidence data available yet.
          </p>
          <p className="text-foreground font-mono text-xs">
            Run a research blueprint to start building the evidence graph.
          </p>
        </div>
      ) : (
        <div className="relative flex gap-4">
          {/* SVG graph */}
          <div className="flex-1 border border-white/10 rounded bg-black/30 overflow-hidden">
            <svg
              viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
              className="w-full h-auto"
              style={{ maxHeight: '70vh' }}
            >
              {/* Edges */}
              {graphData?.edges.map((edge, i) => {
                const src = nodeById.get(edge.source);
                const tgt = nodeById.get(edge.target);
                if (!src || !tgt) return null;
                return (
                  <line
                    key={`edge-${i}`}
                    x1={src.x}
                    y1={src.y}
                    x2={tgt.x}
                    y2={tgt.y}
                    stroke="rgba(255,255,255,0.1)"
                    strokeWidth={1}
                  />
                );
              })}

              {/* Nodes */}
              {positioned.map((node) => {
                const r = NODE_RADII[node.type];
                const color = NODE_COLORS[node.type];
                const isSelected = selectedNode?.id === node.id;
                return (
                  <g
                    key={node.id}
                    className="cursor-pointer"
                    onClick={() => setSelectedNode(node)}
                  >
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={r}
                      fill={color}
                      fillOpacity={isSelected ? 0.4 : 0.15}
                      stroke={color}
                      strokeWidth={isSelected ? 2 : 1}
                      strokeOpacity={isSelected ? 1 : 0.5}
                    />
                    <text
                      x={node.x}
                      y={node.y + r + 14}
                      textAnchor="middle"
                      className="font-mono"
                      fontSize={10}
                      fill="rgba(255,255,255,0.6)"
                    >
                      {node.label.length > 24
                        ? node.label.slice(0, 22) + '...'
                        : node.label}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Detail panel */}
          {selectedNode && (
            <div className="w-80 shrink-0 border border-white/10 rounded bg-black/40 p-4">
              <div className="flex items-start justify-between mb-3">
                <span
                  className="px-2 py-0.5 text-xs font-mono rounded border"
                  style={{
                    color: NODE_COLORS[selectedNode.type],
                    borderColor: NODE_COLORS[selectedNode.type] + '40',
                    backgroundColor: NODE_COLORS[selectedNode.type] + '15',
                  }}
                >
                  {NODE_LABELS[selectedNode.type]}
                </span>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="p-1 rounded hover:bg-white/5 text-muted-foreground hover:text-foreground transition-colors"
                  aria-label="Close detail panel"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <h3 className="text-sm font-mono font-semibold text-muted-foreground mb-2">
                {selectedNode.label}
              </h3>

              {selectedNode.description && (
                <p className="text-xs font-mono text-muted-foreground mb-3">
                  {selectedNode.description}
                </p>
              )}

              {selectedNode.metadata &&
                Object.keys(selectedNode.metadata).length > 0 && (
                  <div>
                    <h4 className="text-xs font-mono text-muted-foreground uppercase tracking-wide mb-1">
                      Metadata
                    </h4>
                    <div className="space-y-1">
                      {Object.entries(selectedNode.metadata).map(
                        ([key, value]) => (
                          <div
                            key={key}
                            className="flex justify-between text-xs font-mono"
                          >
                            <span className="text-muted-foreground">{key}</span>
                            <span className="text-muted-foreground truncate ml-2 max-w-[160px]">
                              {String(value)}
                            </span>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
