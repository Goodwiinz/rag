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

// Single warm-gold accent family + neutral foreground tones. Node type is
// also conveyed by radius and by the text labels in the legend, so meaning
// is never carried by color alone.
const NODE_COLORS: Record<EvidenceNode['type'], string> = {
  research_question: 'var(--nous-sol)',
  sub_question: 'var(--nous-helios)',
  evidence: 'hsl(var(--muted-foreground))',
  source: 'var(--nous-parchment)',
};

const NODE_RADII: Record<EvidenceNode['type'], number> = {
  research_question: 32,
  sub_question: 20,
  evidence: 14,
  source: 14,
};

const NODE_LABELS: Record<EvidenceNode['type'], string> = {
  research_question: 'Research question',
  sub_question: 'Sub-question',
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
      <div aria-busy="true" aria-live="polite">
        <span className="sr-only">Loading evidence map</span>
        {/* Header skeleton */}
        <div className="flex items-center gap-4 mb-6">
          <div className="h-8 w-8 rounded-lg bg-muted animate-pulse" />
          <div className="flex-1 space-y-2">
            <div className="h-5 w-40 rounded bg-muted animate-pulse" />
            <div className="h-3 w-28 rounded bg-muted animate-pulse" />
          </div>
          <div className="hidden md:flex items-center gap-4">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-3 w-20 rounded bg-muted animate-pulse"
              />
            ))}
          </div>
        </div>
        {/* Canvas skeleton */}
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="h-[60vh] bg-muted/40 animate-pulse" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="flex flex-col items-start gap-3 rounded-xl border border-border bg-card p-5 shadow-sm"
      >
        <div className="flex items-center gap-2">
          <AlertCircle
            aria-hidden="true"
            className="h-4 w-4 text-[var(--nous-mars)] shrink-0"
          />
          <span className="text-sm font-medium text-foreground">{error}</span>
        </div>
        <button
          type="button"
          onClick={() => fetchGraph()}
          className="text-sm font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded"
        >
          Retry
        </button>
      </div>
    );
  }

  const hasData = positioned.length > 0;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <button
          type="button"
          onClick={() => router.back()}
          className="p-1.5 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          aria-label="Go back"
        >
          <ArrowLeft aria-hidden="true" className="h-5 w-5" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-semibold text-foreground">
            Evidence map
          </h1>
          {projectName && (
            <p className="text-xs text-muted-foreground mt-0.5 truncate">
              {projectName}
            </p>
          )}
        </div>

        {/* Legend */}
        <div className="hidden md:flex items-center gap-4">
          {(
            Object.entries(NODE_LABELS) as [EvidenceNode['type'], string][]
          ).map(([type, label]) => (
            <div key={type} className="flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className="inline-block rounded-full"
                style={{
                  width: Math.max(NODE_RADII[type] * 0.5, 8),
                  height: Math.max(NODE_RADII[type] * 0.5, 8),
                  backgroundColor: NODE_COLORS[type],
                  opacity: 0.85,
                }}
              />
              <span className="text-xs text-muted-foreground">{label}</span>
            </div>
          ))}
        </div>
      </div>

      {!hasData ? (
        <div className="flex flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-border bg-card py-20 text-center shadow-sm">
          <p className="text-sm font-medium text-foreground">No evidence yet</p>
          <p className="text-xs text-muted-foreground">
            Run a research blueprint to start building the evidence graph.
          </p>
        </div>
      ) : (
        <div className="relative flex flex-col lg:flex-row gap-4">
          {/* SVG graph */}
          <div className="flex-1 rounded-xl border border-border bg-card overflow-hidden shadow-sm">
            <svg
              viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
              className="w-full h-auto"
              style={{ maxHeight: '70vh' }}
              role="img"
              aria-label="Evidence graph showing research questions, sub-questions, evidence and sources"
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
                    stroke="hsl(var(--border))"
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
                      fillOpacity={isSelected ? 0.45 : 0.18}
                      stroke={color}
                      strokeWidth={isSelected ? 2 : 1}
                      strokeOpacity={isSelected ? 1 : 0.6}
                    />
                    <text
                      x={node.x}
                      y={node.y + r + 14}
                      textAnchor="middle"
                      fontSize={10}
                      fill="hsl(var(--muted-foreground))"
                    >
                      {node.label.length > 24
                        ? node.label.slice(0, 22) + '…'
                        : node.label}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Detail panel */}
          {selectedNode && (
            <div className="w-full lg:w-80 lg:shrink-0 rounded-xl border border-border bg-card p-4 shadow-sm">
              <div className="flex items-start justify-between mb-3">
                <span className="px-2 py-0.5 text-xs font-medium rounded-md border bg-muted text-foreground border-border">
                  {NODE_LABELS[selectedNode.type]}
                </span>
                <button
                  type="button"
                  onClick={() => setSelectedNode(null)}
                  className="p-1 rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  aria-label="Close detail panel"
                >
                  <X aria-hidden="true" className="h-4 w-4" />
                </button>
              </div>

              <h3 className="text-sm font-semibold text-foreground mb-2">
                {selectedNode.label}
              </h3>

              {selectedNode.description && (
                <p
                  className="text-sm text-muted-foreground mb-3 leading-relaxed"
                  style={{ fontFamily: 'var(--nous-font-body)' }}
                >
                  {selectedNode.description}
                </p>
              )}

              {selectedNode.metadata &&
                Object.keys(selectedNode.metadata).length > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-muted-foreground mb-1.5">
                      Metadata
                    </h4>
                    <div className="space-y-1">
                      {Object.entries(selectedNode.metadata).map(
                        ([key, value]) => (
                          <div
                            key={key}
                            className="flex justify-between gap-2 text-xs"
                          >
                            <span className="text-muted-foreground">{key}</span>
                            <span className="text-foreground truncate max-w-[160px]">
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
