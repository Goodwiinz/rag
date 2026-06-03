'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { Activity } from 'lucide-react';
import { EmptyState } from '@/components/ui/EmptyState';
import {
  AggregateStats,
  BottleneckReport,
  diagnosticsService,
  Finding,
  RetrievalTrace,
  TraceSummary,
  WeightConfig,
  WeightExperimentResult,
} from '@/services/diagnosticsService';

// --- Health badge ---
function HealthBadge({ health }: { health: string }) {
  const variant =
    health === 'green'
      ? 'default'
      : health === 'yellow'
        ? 'secondary'
        : 'destructive';
  const label =
    health === 'green'
      ? 'Healthy'
      : health === 'yellow'
        ? 'Warning'
        : 'Critical';
  return <Badge variant={variant}>{label}</Badge>;
}

// --- Stage health indicator ---
function StageHealth({ stage, health }: { stage: string; health: string }) {
  const color =
    health === 'green'
      ? 'bg-primary'
      : health === 'yellow'
        ? 'bg-[var(--nous-helios)]'
        : 'bg-red-500';
  return (
    <div className="flex items-center gap-2">
      <div className={cn('h-3 w-3 rounded-full', color)} />
      <span className="text-sm capitalize">{stage}</span>
    </div>
  );
}

// --- Tab 1: Query Explorer ---
function QueryExplorer() {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<RetrievalTrace | null>(
    null
  );
  const [report, setReport] = useState<BottleneckReport | null>(null);
  const [loading, setLoading] = useState(false);

  const loadTraces = useCallback(async () => {
    setLoading(true);
    try {
      const data = await diagnosticsService.getRecentTraces(50);
      setTraces(data.traces);
    } catch (err) {
      console.error('Failed to load traces:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTraces();
  }, [loadTraces]);

  const selectTrace = useCallback(async (traceId: string) => {
    try {
      const data = await diagnosticsService.getTrace(traceId);
      setSelectedTrace(data.trace);
      setReport(data.bottleneck_report);
    } catch (err) {
      console.error('Failed to load trace:', err);
    }
  }, []);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {/* Trace list */}
      <Card className="lg:col-span-1">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium">Recent Queries</CardTitle>
          <Button
            variant="ghost"
            size="sm"
            onClick={loadTraces}
            disabled={loading}
          >
            {loading ? 'Loading...' : 'Refresh'}
          </Button>
        </CardHeader>
        <CardContent className="max-h-[600px] space-y-1 overflow-y-auto">
          {traces.length === 0 && (
            <EmptyState
              icon={Activity}
              title="NO_TRACES_CAPTURED"
              description="Send a RAG query to start recording pipeline diagnostics and performance traces."
              action={{ label: 'OPEN_SEARCH', href: '/search' }}
            />
          )}
          {traces.map((t) => (
            <button
              key={t.trace_id}
              className={cn(
                'w-full rounded-md border p-2 text-left text-sm transition-colors',
                selectedTrace?.trace_id === t.trace_id
                  ? 'border-primary/50 bg-primary/10'
                  : 'hover:bg-muted/50'
              )}
              onClick={() => selectTrace(t.trace_id)}
            >
              <div className="truncate font-medium">
                {t.query || '(empty query)'}
              </div>
              <div className="text-muted-foreground mt-1 flex gap-3 text-xs">
                <span>{t.total_time_ms.toFixed(0)}ms</span>
                <span>{t.final_result_count} results</span>
                <span>{t.source_count} sources</span>
              </div>
            </button>
          ))}
        </CardContent>
      </Card>

      {/* Trace detail */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="text-sm font-medium">Pipeline Detail</CardTitle>
        </CardHeader>
        <CardContent>
          {!selectedTrace ? (
            <p className="text-muted-foreground text-sm">
              Select a query to view its pipeline stages.
            </p>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">Overall:</span>
                {report && <HealthBadge health={report.overall_health} />}
                <span className="text-muted-foreground text-xs">
                  {selectedTrace.total_time_ms.toFixed(0)}ms total
                </span>
              </div>

              {/* Sources */}
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider">
                  Sources
                </h4>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  {selectedTrace.sources.map((src) => (
                    <div
                      key={src.source_type}
                      className={cn(
                        'rounded-md border p-3',
                        src.success ? 'border-border' : 'border-red-500/50'
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium capitalize">
                          {src.source_type}
                        </span>
                        <Badge
                          variant={src.success ? 'default' : 'destructive'}
                          className="text-xs"
                        >
                          {src.success
                            ? `${src.result_count} results`
                            : 'Failed'}
                        </Badge>
                      </div>
                      <div className="text-muted-foreground mt-1 text-xs">
                        {src.search_time_ms.toFixed(0)}ms | avg score:{' '}
                        {src.avg_score.toFixed(3)}
                      </div>
                      {src.error && (
                        <div className="mt-1 text-xs text-red-400">
                          {src.error}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Fusion */}
              {selectedTrace.fusion && (
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider">
                    Fusion
                  </h4>
                  <div className="rounded-md border p-3 text-sm">
                    <div className="flex flex-wrap gap-4">
                      <span>
                        {selectedTrace.fusion.input_count} raw &rarr;{' '}
                        {selectedTrace.fusion.output_count} unique
                      </span>
                      <span>
                        {selectedTrace.fusion.multi_source_count} multi-source
                      </span>
                      <span>
                        {selectedTrace.fusion.fusion_time_ms.toFixed(0)}ms
                      </span>
                    </div>
                    <div className="text-muted-foreground mt-1 text-xs">
                      Weights:{' '}
                      {Object.entries(selectedTrace.fusion.weights_used)
                        .map(([k, v]) => `${k}: ${(v * 100).toFixed(0)}%`)
                        .join(', ')}
                    </div>
                  </div>
                </div>
              )}

              {/* Reranking */}
              {selectedTrace.rerank?.enabled && (
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider">
                    Reranking
                  </h4>
                  <div className="rounded-md border p-3 text-sm">
                    <div className="flex flex-wrap gap-4">
                      <span>
                        {selectedTrace.rerank.input_count} &rarr;{' '}
                        {selectedTrace.rerank.output_count} results
                      </span>
                      <span>
                        {selectedTrace.rerank.rerank_time_ms.toFixed(0)}ms
                      </span>
                      {selectedTrace.rerank.fallback_used && (
                        <Badge variant="destructive">Fallback</Badge>
                      )}
                    </div>
                    {selectedTrace.rerank.score_deltas.length > 0 && (
                      <div className="mt-2 max-h-32 overflow-y-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="text-muted-foreground">
                              <th className="text-left">Doc</th>
                              <th className="text-right">Before</th>
                              <th className="text-right">After</th>
                              <th className="text-right">Delta</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedTrace.rerank.score_deltas
                              .slice(0, 10)
                              .map((d) => (
                                <tr key={d.doc_id}>
                                  <td className="truncate pr-2">
                                    {d.doc_id.slice(0, 8)}...
                                  </td>
                                  <td className="text-right">
                                    {d.before.toFixed(3)}
                                  </td>
                                  <td className="text-right">
                                    {d.after.toFixed(3)}
                                  </td>
                                  <td
                                    className={cn(
                                      'text-right',
                                      d.delta > 0
                                        ? 'text-primary'
                                        : 'text-red-400'
                                    )}
                                  >
                                    {d.delta > 0 ? '+' : ''}
                                    {d.delta.toFixed(3)}
                                  </td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Context truncation */}
              {selectedTrace.context && (
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider">
                    Context Assembly
                  </h4>
                  <div className="rounded-md border p-3 text-sm">
                    <div className="flex flex-wrap gap-4">
                      <span>
                        {selectedTrace.context.docs_with_content}/
                        {selectedTrace.context.docs_retrieved} docs with content
                      </span>
                      <span>
                        {selectedTrace.context.total_chars_before_truncation.toLocaleString()}{' '}
                        &rarr;{' '}
                        {selectedTrace.context.total_chars_after_truncation.toLocaleString()}{' '}
                        chars
                      </span>
                      {selectedTrace.context.truncation_ratio > 0 && (
                        <Badge
                          variant={
                            selectedTrace.context.truncation_ratio > 0.3
                              ? 'destructive'
                              : 'secondary'
                          }
                        >
                          {(
                            selectedTrace.context.truncation_ratio * 100
                          ).toFixed(0)}
                          % truncated
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Findings */}
              {report && report.findings.length > 0 && (
                <div>
                  <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider">
                    Issues Found
                  </h4>
                  <div className="space-y-2">
                    {report.findings.map((f, i) => (
                      <FindingCard key={i} finding={f} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function FindingCard({ finding }: { finding: Finding }) {
  const severityColor =
    finding.severity === 'high'
      ? 'border-red-500/50'
      : finding.severity === 'medium'
        ? 'border-[var(--nous-helios)]/50'
        : 'border-border';

  return (
    <div className={cn('rounded-md border p-3', severityColor)}>
      <div className="flex items-center gap-2">
        <Badge
          variant={
            finding.severity === 'high'
              ? 'destructive'
              : finding.severity === 'medium'
                ? 'secondary'
                : 'default'
          }
          className="text-xs"
        >
          {finding.severity}
        </Badge>
        <span className="text-sm font-medium">{finding.title}</span>
      </div>
      <p className="text-muted-foreground mt-1 text-xs">{finding.detail}</p>
      <p className="mt-1 text-xs text-brand-cyan">{finding.recommendation}</p>
    </div>
  );
}

// --- Tab 2: Quality Overview ---
function QualityOverview() {
  const [stats, setStats] = useState<AggregateStats | null>(null);
  const [hours, setHours] = useState(24);
  const [loading, setLoading] = useState(false);

  const loadStats = useCallback(async () => {
    setLoading(true);
    try {
      const data = await diagnosticsService.getAggregateStats(hours);
      setStats(data);
    } catch (err) {
      console.error('Failed to load aggregate stats:', err);
    } finally {
      setLoading(false);
    }
  }, [hours]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  if (!stats) {
    return (
      <div className="text-muted-foreground text-sm">
        {loading ? 'Loading statistics...' : 'No data available.'}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <select
          className="bg-background rounded border px-2 py-1 text-sm"
          value={hours}
          onChange={(e) => setHours(Number(e.target.value))}
        >
          <option value={1}>Last 1 hour</option>
          <option value={6}>Last 6 hours</option>
          <option value={24}>Last 24 hours</option>
          <option value={72}>Last 3 days</option>
          <option value={168}>Last 7 days</option>
        </select>
        <Button
          variant="ghost"
          size="sm"
          onClick={loadStats}
          disabled={loading}
        >
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <StatCard
          label="Total Queries"
          value={(stats.total_traces ?? 0).toString()}
        />
        <StatCard
          label="Avg Response Time"
          value={`${(stats.avg_time_ms ?? 0).toFixed(0)}ms`}
        />
        <StatCard
          label="Avg Results"
          value={(stats.avg_result_count ?? 0).toFixed(1)}
        />
        <StatCard
          label="Source Failures"
          value={(stats.source_failure_count ?? 0).toString()}
          alert={(stats.source_failure_count ?? 0) > 0}
        />
      </div>

      {/* Source stats */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            Source Performance
          </CardTitle>
        </CardHeader>
        <CardContent>
          {Object.keys(stats.source_stats ?? {}).length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No source data available.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {Object.entries(stats.source_stats ?? {}).map(
                ([source, data]) => (
                  <div key={source} className="rounded-md border p-3">
                    <div className="text-sm font-medium capitalize">
                      {source}
                    </div>
                    <div className="text-muted-foreground mt-1 text-xs">
                      Avg: {data.avg_time_ms.toFixed(0)}ms | Max:{' '}
                      {data.max_time_ms.toFixed(0)}ms | Queries:{' '}
                      {data.query_count}
                    </div>
                  </div>
                )
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Truncation stats */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            Context Truncation
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StatCard
              label="Avg Truncation"
              value={`${((stats.truncation_stats?.avg_ratio ?? 0) * 100).toFixed(1)}%`}
              alert={(stats.truncation_stats?.avg_ratio ?? 0) > 0.3}
            />
            <StatCard
              label="Max Truncation"
              value={`${((stats.truncation_stats?.max_ratio ?? 0) * 100).toFixed(1)}%`}
              alert={(stats.truncation_stats?.max_ratio ?? 0) > 0.3}
            />
            <StatCard
              label="Queries with Truncation"
              value={(
                stats.truncation_stats?.traces_with_truncation ?? 0
              ).toString()}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  label,
  value,
  alert = false,
}: {
  label: string;
  value: string;
  alert?: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-muted-foreground text-xs">{label}</div>
        <div
          className={cn(
            'mt-1 text-2xl font-bold',
            alert ? 'text-red-400' : 'text-foreground'
          )}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

// --- Tab 3: Weight Tuner ---
function WeightTuner() {
  const [query, setQuery] = useState('');
  const [fulltext, setFulltext] = useState(0.4);
  const [vector, setVector] = useState(0.4);
  const [kg, setKg] = useState(0.2);
  const [results, setResults] = useState<WeightExperimentResult[]>([]);
  const [loading, setLoading] = useState(false);

  const normalizeWeights = useCallback(
    (changed: 'fulltext' | 'vector' | 'kg', newValue: number) => {
      const remaining = 1.0 - newValue;
      if (changed === 'fulltext') {
        const otherTotal = vector + kg || 1;
        setFulltext(newValue);
        setVector(Math.round(remaining * (vector / otherTotal) * 100) / 100);
        setKg(Math.round(remaining * (kg / otherTotal) * 100) / 100);
      } else if (changed === 'vector') {
        const otherTotal = fulltext + kg || 1;
        setVector(newValue);
        setFulltext(
          Math.round(remaining * (fulltext / otherTotal) * 100) / 100
        );
        setKg(Math.round(remaining * (kg / otherTotal) * 100) / 100);
      } else {
        const otherTotal = fulltext + vector || 1;
        setKg(newValue);
        setFulltext(
          Math.round(remaining * (fulltext / otherTotal) * 100) / 100
        );
        setVector(Math.round(remaining * (vector / otherTotal) * 100) / 100);
      }
    },
    [fulltext, vector, kg]
  );

  const runExperiment = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const configs: WeightConfig[] = [
        { fulltext: 0.4, vector: 0.4, knowledge_graph: 0.2 }, // Default
        { fulltext, vector, knowledge_graph: kg }, // Custom
      ];
      const data = await diagnosticsService.experimentWeights(query, configs);
      setResults(data.results);
    } catch (err) {
      console.error('Weight experiment failed:', err);
    } finally {
      setLoading(false);
    }
  }, [query, fulltext, vector, kg]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            Weight Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="mb-1 block text-xs">
              Fulltext: {(fulltext * 100).toFixed(0)}%
            </label>
            <Slider
              value={[fulltext]}
              min={0}
              max={1}
              step={0.05}
              onValueChange={([v]) => normalizeWeights('fulltext', v)}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs">
              Vector: {(vector * 100).toFixed(0)}%
            </label>
            <Slider
              value={[vector]}
              min={0}
              max={1}
              step={0.05}
              onValueChange={([v]) => normalizeWeights('vector', v)}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs">
              Knowledge Graph: {(kg * 100).toFixed(0)}%
            </label>
            <Slider
              value={[kg]}
              min={0}
              max={1}
              step={0.05}
              onValueChange={([v]) => normalizeWeights('kg', v)}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-2">
        <Input
          placeholder="Enter a test query..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && runExperiment()}
        />
        <Button onClick={runExperiment} disabled={loading || !query.trim()}>
          {loading ? 'Running...' : 'Compare'}
        </Button>
      </div>

      {/* Results comparison */}
      {results.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {results.map((r, i) => (
            <Card key={i}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">
                  {i === 0 ? 'Default Weights' : 'Custom Weights'}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm">
                <div className="text-muted-foreground text-xs">
                  {Object.entries(r.weights)
                    .map(([k, v]) => `${k}: ${(v * 100).toFixed(0)}%`)
                    .join(' | ')}
                </div>
                <div className="mt-2 flex flex-wrap gap-3">
                  <span>{r.result_count} results</span>
                  <span>{r.total_time_ms.toFixed(0)}ms</span>
                </div>
                {r.top_scores.length > 0 && (
                  <div className="mt-2">
                    <span className="text-muted-foreground text-xs">
                      Top scores:{' '}
                      {r.top_scores.map((s) => s.toFixed(3)).join(', ')}
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Tab 4: Bottleneck Analysis ---
function BottleneckAnalysis() {
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [reports, setReports] = useState<
    Array<{ trace: RetrievalTrace; report: BottleneckReport }>
  >([]);
  const [loading, setLoading] = useState(false);

  const loadAnalysis = useCallback(async () => {
    setLoading(true);
    try {
      const data = await diagnosticsService.getRecentTraces(10);
      setTraces(data.traces);

      // Load bottleneck reports for recent traces
      const loaded = await Promise.all(
        data.traces.slice(0, 10).map(async (t) => {
          try {
            const detail = await diagnosticsService.getTrace(t.trace_id);
            return { trace: detail.trace, report: detail.bottleneck_report };
          } catch {
            return null;
          }
        })
      );
      setReports(loaded.filter(Boolean) as typeof reports);
    } catch (err) {
      console.error('Failed to load analysis:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAnalysis();
  }, [loadAnalysis]);

  // Aggregate stage health across recent traces
  const stageHealthSummary = useMemo(() => {
    const stages = ['source', 'fusion', 'rerank', 'context'];
    return stages.map((stage) => {
      const healths = reports
        .map((r) => r.report.stage_health[stage])
        .filter(Boolean);
      const reds = healths.filter((h) => h === 'red').length;
      const yellows = healths.filter((h) => h === 'yellow').length;
      const overall =
        reds > 0 ? 'red' : yellows > healths.length * 0.3 ? 'yellow' : 'green';
      return { stage, health: overall, total: healths.length, reds, yellows };
    });
  }, [reports]);

  // Aggregate all findings
  const allFindings = useMemo(() => {
    const findingCounts = new Map<
      string,
      { finding: Finding; count: number }
    >();
    for (const r of reports) {
      for (const f of r.report.findings) {
        const key = f.title;
        const existing = findingCounts.get(key);
        if (existing) {
          existing.count++;
        } else {
          findingCounts.set(key, { finding: f, count: 1 });
        }
      }
    }
    return Array.from(findingCounts.values()).sort((a, b) => {
      const sevOrder = { high: 0, medium: 1, low: 2 };
      const aSev = sevOrder[a.finding.severity as keyof typeof sevOrder] ?? 3;
      const bSev = sevOrder[b.finding.severity as keyof typeof sevOrder] ?? 3;
      return aSev - bSev || b.count - a.count;
    });
  }, [reports]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <span className="text-muted-foreground text-sm">
          Analyzing last {traces.length} queries
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={loadAnalysis}
          disabled={loading}
        >
          {loading ? 'Analyzing...' : 'Refresh'}
        </Button>
      </div>

      {/* Pipeline health overview */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Pipeline Health</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-6">
            {stageHealthSummary.map((s) => (
              <StageHealth key={s.stage} stage={s.stage} health={s.health} />
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Top issues */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            Top Issues ({allFindings.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {allFindings.length === 0 && (
            <p className="text-muted-foreground text-sm">
              No issues detected across recent queries.
            </p>
          )}
          {allFindings.map(({ finding, count }, i) => (
            <div
              key={i}
              className="flex items-start gap-3 rounded-md border p-3"
            >
              <Badge
                variant={
                  finding.severity === 'high'
                    ? 'destructive'
                    : finding.severity === 'medium'
                      ? 'secondary'
                      : 'default'
                }
                className="mt-0.5 shrink-0 text-xs"
              >
                {finding.severity}
              </Badge>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{finding.title}</span>
                  {count > 1 && (
                    <span className="text-muted-foreground text-xs">
                      ({count}x)
                    </span>
                  )}
                </div>
                <p className="text-muted-foreground text-xs">
                  {finding.detail}
                </p>
                <p className="mt-1 text-xs text-brand-cyan">
                  {finding.recommendation}
                </p>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

// --- Main Dashboard ---

interface RetrievalDiagnosticsDashboardProps {
  className?: string;
}

export function RetrievalDiagnosticsDashboard({
  className,
}: RetrievalDiagnosticsDashboardProps) {
  return (
    <div className={cn('space-y-6', className)}>
      <div>
        <h1 className="text-2xl font-mono font-bold text-[var(--nous-fg-1)] tracking-wider">
          RETRIEVAL_DIAGNOSTICS
        </h1>
        <p className="text-xs font-mono text-muted-foreground mt-0.5 uppercase tracking-widest">
          Inspect the RAG retrieval pipeline, identify bottlenecks, and tune
          search weights.
        </p>
      </div>

      <Tabs defaultValue="explorer" className="w-full">
        <TabsList>
          <TabsTrigger value="explorer">Query Explorer</TabsTrigger>
          <TabsTrigger value="quality">Quality Overview</TabsTrigger>
          <TabsTrigger value="weights">Weight Tuner</TabsTrigger>
          <TabsTrigger value="bottleneck">Bottleneck Analysis</TabsTrigger>
        </TabsList>

        <TabsContent value="explorer" className="mt-4">
          <QueryExplorer />
        </TabsContent>
        <TabsContent value="quality" className="mt-4">
          <QualityOverview />
        </TabsContent>
        <TabsContent value="weights" className="mt-4">
          <WeightTuner />
        </TabsContent>
        <TabsContent value="bottleneck" className="mt-4">
          <BottleneckAnalysis />
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default RetrievalDiagnosticsDashboard;
