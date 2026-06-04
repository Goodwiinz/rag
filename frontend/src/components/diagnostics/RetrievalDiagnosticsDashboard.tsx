'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Slider } from '@/components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import {
  AlertTriangle,
  CheckCircle2,
  RotateCw,
  Search,
  XCircle,
} from 'lucide-react';
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

// --- Health labels (never color-only: each carries text + icon) ---
const HEALTH_LABEL: Record<string, string> = {
  green: 'Healthy',
  yellow: 'Warning',
  red: 'Critical',
};

function healthIcon(health: string) {
  if (health === 'green')
    return (
      <CheckCircle2
        className="h-4 w-4 text-[var(--nous-terra)]"
        aria-hidden="true"
      />
    );
  if (health === 'yellow')
    return (
      <AlertTriangle
        className="h-4 w-4 text-[var(--nous-corona)]"
        aria-hidden="true"
      />
    );
  return <XCircle className="h-4 w-4 text-destructive" aria-hidden="true" />;
}

// --- Health badge ---
function HealthBadge({ health }: { health: string }) {
  const variant =
    health === 'green'
      ? 'default'
      : health === 'yellow'
        ? 'secondary'
        : 'destructive';
  return <Badge variant={variant}>{HEALTH_LABEL[health] ?? 'Unknown'}</Badge>;
}

// --- Stage health indicator (text label + icon, not color alone) ---
function StageHealth({ stage, health }: { stage: string; health: string }) {
  return (
    <div className="flex items-center gap-2">
      {healthIcon(health)}
      <span className="text-sm">
        <span className="capitalize">{stage}</span>
        <span className="text-muted-foreground">
          {' '}
          — {HEALTH_LABEL[health] ?? 'Unknown'}
        </span>
      </span>
    </div>
  );
}

// --- Shared inline error state with retry ---
function LoadError({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle
          className="mt-0.5 h-4 w-4 shrink-0 text-destructive"
          aria-hidden="true"
        />
        <span className="text-foreground">{message}</span>
      </div>
      <Button variant="outline" size="sm" onClick={onRetry}>
        <RotateCw className="mr-2 h-4 w-4" aria-hidden="true" />
        Retry
      </Button>
    </div>
  );
}

// --- Labelled key/value metric (replaces pipe-delimited runs) ---
function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium tabular-nums">{value}</dd>
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
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const loadTraces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await diagnosticsService.getRecentTraces(50);
      setTraces(data.traces);
    } catch (err) {
      console.error('Failed to load traces:', err);
      setError(
        'Could not load recent queries. Check the diagnostics service and try again.'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTraces();
  }, [loadTraces]);

  const selectTrace = useCallback(async (traceId: string) => {
    setDetailError(null);
    try {
      const data = await diagnosticsService.getTrace(traceId);
      setSelectedTrace(data.trace);
      setReport(data.bottleneck_report);
    } catch (err) {
      console.error('Failed to load trace:', err);
      setSelectedTrace(null);
      setReport(null);
      setDetailError(
        'Could not load this trace. It may have expired, or the service is unavailable.'
      );
    }
  }, []);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {/* Trace list */}
      <Card className="lg:col-span-1">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-sm font-medium">Recent queries</CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={loadTraces}
            disabled={loading}
          >
            <RotateCw
              className={cn('mr-2 h-4 w-4', loading && 'animate-spin')}
              aria-hidden="true"
            />
            {loading ? 'Loading' : 'Refresh'}
          </Button>
        </CardHeader>
        <CardContent
          className="max-h-[600px] space-y-1 overflow-y-auto"
          aria-busy={loading}
        >
          {error && <LoadError message={error} onRetry={loadTraces} />}
          {!error && loading && traces.length === 0 && (
            <div className="space-y-2" aria-hidden="true">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          )}
          {!error && !loading && traces.length === 0 && (
            <EmptyState
              icon={Search}
              title="No traces captured yet"
              description="Run a search to start recording pipeline diagnostics and performance traces."
              action={{ label: 'Open search', href: '/search' }}
            />
          )}
          {traces.map((t) => {
            const isSelected = selectedTrace?.trace_id === t.trace_id;
            return (
              <button
                key={t.trace_id}
                aria-pressed={isSelected}
                className={cn(
                  'w-full rounded-md border p-2 text-left text-sm transition-colors',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40',
                  isSelected
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:bg-muted/50'
                )}
                onClick={() => selectTrace(t.trace_id)}
              >
                <div className="truncate font-medium">
                  {t.query || '(empty query)'}
                </div>
                <div className="mt-1 flex gap-3 text-xs text-muted-foreground tabular-nums">
                  <span>{t.total_time_ms.toFixed(0)} ms</span>
                  <span>{t.final_result_count} results</span>
                  <span>{t.source_count} sources</span>
                </div>
              </button>
            );
          })}
        </CardContent>
      </Card>

      {/* Trace detail */}
      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="text-sm font-medium">Pipeline detail</CardTitle>
        </CardHeader>
        <CardContent>
          {detailError ? (
            <LoadError
              message={detailError}
              onRetry={() =>
                selectedTrace && selectTrace(selectedTrace.trace_id)
              }
            />
          ) : !selectedTrace ? (
            <p className="text-sm text-muted-foreground">
              Select a query to view its pipeline stages.
            </p>
          ) : (
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">Overall</span>
                {report && <HealthBadge health={report.overall_health} />}
                <span className="text-xs text-muted-foreground tabular-nums">
                  {selectedTrace.total_time_ms.toFixed(0)} ms total
                </span>
              </div>

              {/* Sources */}
              <section>
                <h4 className="mb-2 text-sm font-medium text-foreground">
                  Sources
                </h4>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  {selectedTrace.sources.map((src) => (
                    <div
                      key={src.source_type}
                      className={cn(
                        'rounded-md border p-3',
                        src.success ? 'border-border' : 'border-destructive/40'
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="min-w-0 truncate text-sm font-medium capitalize">
                          {src.source_type}
                        </span>
                        <Badge
                          variant={src.success ? 'default' : 'destructive'}
                          className="shrink-0 text-xs"
                        >
                          {src.success
                            ? `${src.result_count} results`
                            : 'Failed'}
                        </Badge>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground tabular-nums">
                        {src.search_time_ms.toFixed(0)} ms · avg score{' '}
                        {src.avg_score.toFixed(3)}
                      </div>
                      {src.error && (
                        <div className="mt-1 break-words text-xs text-destructive">
                          {src.error}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </section>

              {/* Fusion */}
              {selectedTrace.fusion && (
                <section>
                  <h4 className="mb-2 text-sm font-medium text-foreground">
                    Fusion
                  </h4>
                  <div className="rounded-md border p-3 text-sm">
                    <dl className="flex flex-wrap gap-x-8 gap-y-2">
                      <Metric
                        label="Deduplicated"
                        value={`${selectedTrace.fusion.input_count} raw → ${selectedTrace.fusion.output_count} unique`}
                      />
                      <Metric
                        label="Multi-source"
                        value={`${selectedTrace.fusion.multi_source_count}`}
                      />
                      <Metric
                        label="Fusion time"
                        value={`${selectedTrace.fusion.fusion_time_ms.toFixed(0)} ms`}
                      />
                    </dl>
                    <div className="mt-2 text-xs text-muted-foreground">
                      Weights used:{' '}
                      {Object.entries(selectedTrace.fusion.weights_used)
                        .map(([k, v]) => `${k} ${(v * 100).toFixed(0)}%`)
                        .join(', ')}
                    </div>
                  </div>
                </section>
              )}

              {/* Reranking */}
              {selectedTrace.rerank?.enabled && (
                <section>
                  <h4 className="mb-2 text-sm font-medium text-foreground">
                    Reranking
                  </h4>
                  <div className="rounded-md border p-3 text-sm">
                    <dl className="flex flex-wrap items-center gap-x-8 gap-y-2">
                      <Metric
                        label="Candidates"
                        value={`${selectedTrace.rerank.input_count} → ${selectedTrace.rerank.output_count} results`}
                      />
                      <Metric
                        label="Rerank time"
                        value={`${selectedTrace.rerank.rerank_time_ms.toFixed(0)} ms`}
                      />
                      {selectedTrace.rerank.fallback_used && (
                        <Badge variant="destructive">Fallback used</Badge>
                      )}
                    </dl>
                    {selectedTrace.rerank.score_deltas.length > 0 && (
                      <div className="mt-3 max-h-32 overflow-x-auto overflow-y-auto">
                        <table className="w-full min-w-[18rem] text-xs tabular-nums">
                          <thead>
                            <tr className="text-muted-foreground">
                              <th className="text-left font-medium">Doc</th>
                              <th className="text-right font-medium">Before</th>
                              <th className="text-right font-medium">After</th>
                              <th className="text-right font-medium">Delta</th>
                            </tr>
                          </thead>
                          <tbody>
                            {selectedTrace.rerank.score_deltas
                              .slice(0, 10)
                              .map((d) => (
                                <tr key={d.doc_id}>
                                  <td className="truncate pr-2">
                                    {d.doc_id.slice(0, 8)}…
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
                                        ? 'text-[var(--nous-terra)]'
                                        : d.delta < 0
                                          ? 'text-destructive'
                                          : 'text-muted-foreground'
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
                </section>
              )}

              {/* Context truncation */}
              {selectedTrace.context && (
                <section>
                  <h4 className="mb-2 text-sm font-medium text-foreground">
                    Context assembly
                  </h4>
                  <div className="rounded-md border p-3 text-sm">
                    <dl className="flex flex-wrap items-center gap-x-8 gap-y-2">
                      <Metric
                        label="Docs with content"
                        value={`${selectedTrace.context.docs_with_content}/${selectedTrace.context.docs_retrieved}`}
                      />
                      <Metric
                        label="Characters"
                        value={`${selectedTrace.context.total_chars_before_truncation.toLocaleString()} → ${selectedTrace.context.total_chars_after_truncation.toLocaleString()}`}
                      />
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
                    </dl>
                  </div>
                </section>
              )}

              {/* Findings */}
              {report && report.findings.length > 0 && (
                <section>
                  <h4 className="mb-2 text-sm font-medium text-foreground">
                    Issues found
                  </h4>
                  <div className="space-y-2">
                    {report.findings.map((f, i) => (
                      <FindingCard key={i} finding={f} />
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function FindingCard({ finding }: { finding: Finding }) {
  const severityBorder =
    finding.severity === 'high'
      ? 'border-destructive/40'
      : finding.severity === 'medium'
        ? 'border-[var(--nous-corona)]/40'
        : 'border-border';

  const severityLabel =
    finding.severity === 'high'
      ? 'High'
      : finding.severity === 'medium'
        ? 'Medium'
        : 'Low';

  return (
    <div className={cn('rounded-md border p-3', severityBorder)}>
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
          {severityLabel}
        </Badge>
        <span className="text-sm font-medium">{finding.title}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{finding.detail}</p>
      <p className="mt-1 text-xs font-medium text-foreground">
        {finding.recommendation}
      </p>
    </div>
  );
}

// --- Tab 2: Quality Overview ---
function QualityOverview() {
  const [stats, setStats] = useState<AggregateStats | null>(null);
  const [hours, setHours] = useState(24);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await diagnosticsService.getAggregateStats(hours);
      setStats(data);
    } catch (err) {
      console.error('Failed to load aggregate stats:', err);
      setError(
        'Could not load aggregate statistics. Check the diagnostics service and try again.'
      );
    } finally {
      setLoading(false);
    }
  }, [hours]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const controls = (
    <div className="flex flex-wrap items-center gap-3 sm:gap-4">
      <label className="sr-only" htmlFor="quality-window">
        Time window
      </label>
      <select
        id="quality-window"
        className="min-h-[44px] rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40 sm:min-h-0 sm:px-2 sm:py-1"
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
        variant="outline"
        size="sm"
        onClick={loadStats}
        disabled={loading}
      >
        <RotateCw
          className={cn('mr-2 h-4 w-4', loading && 'animate-spin')}
          aria-hidden="true"
        />
        Refresh
      </Button>
    </div>
  );

  if (error) {
    return (
      <div className="space-y-4">
        {controls}
        <LoadError message={error} onRetry={loadStats} />
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="space-y-4" aria-busy="true">
        {controls}
        <div className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border bg-border md:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="bg-card p-4">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="mt-2 h-7 w-16" />
            </div>
          ))}
        </div>
        <span className="sr-only" role="status">
          Loading statistics
        </span>
      </div>
    );
  }

  const failures = stats.source_failure_count ?? 0;

  return (
    <div className="space-y-4" aria-busy={loading}>
      {controls}

      {/* Aggregate metrics as bordered cells in a single surface (no nested cards) */}
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border bg-border md:grid-cols-4">
        <StatCell
          label="Total queries"
          value={(stats.total_traces ?? 0).toString()}
        />
        <StatCell
          label="Avg response time"
          value={`${(stats.avg_time_ms ?? 0).toFixed(0)} ms`}
        />
        <StatCell
          label="Avg results"
          value={(stats.avg_result_count ?? 0).toFixed(1)}
        />
        <StatCell
          label="Source failures"
          value={failures.toString()}
          alert={failures > 0}
          emphasis
        />
      </dl>

      {/* Source stats */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            Source performance
          </CardTitle>
        </CardHeader>
        <CardContent>
          {Object.keys(stats.source_stats ?? {}).length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No source data yet for this time window.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {Object.entries(stats.source_stats ?? {}).map(
                ([source, data]) => (
                  <div key={source} className="rounded-md border p-3">
                    <div className="text-sm font-medium capitalize">
                      {source}
                    </div>
                    <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1">
                      <Metric
                        label="Avg time"
                        value={`${data.avg_time_ms.toFixed(0)} ms`}
                      />
                      <Metric
                        label="Max time"
                        value={`${data.max_time_ms.toFixed(0)} ms`}
                      />
                      <Metric label="Queries" value={`${data.query_count}`} />
                    </dl>
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
            Context truncation
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-3">
            <StatCell
              label="Avg truncation"
              value={`${((stats.truncation_stats?.avg_ratio ?? 0) * 100).toFixed(1)}%`}
              alert={(stats.truncation_stats?.avg_ratio ?? 0) > 0.3}
            />
            <StatCell
              label="Max truncation"
              value={`${((stats.truncation_stats?.max_ratio ?? 0) * 100).toFixed(1)}%`}
              alert={(stats.truncation_stats?.max_ratio ?? 0) > 0.3}
            />
            <StatCell
              label="Queries with truncation"
              value={(
                stats.truncation_stats?.traces_with_truncation ?? 0
              ).toString()}
            />
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}

function StatCell({
  label,
  value,
  alert = false,
  emphasis = false,
}: {
  label: string;
  value: string;
  alert?: boolean;
  emphasis?: boolean;
}) {
  return (
    <div className="bg-card p-4">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          'mt-1 font-bold tabular-nums',
          emphasis ? 'text-3xl' : 'text-2xl',
          alert ? 'text-destructive' : 'text-foreground'
        )}
      >
        <span className="inline-flex items-center gap-1.5">
          {alert && (
            <AlertTriangle
              className="h-4 w-4 text-destructive"
              aria-hidden="true"
            />
          )}
          {value}
        </span>
      </dd>
    </div>
  );
}

// --- Tab 3: Weight Tuner ---
const DEFAULT_WEIGHTS = { fulltext: 0.4, vector: 0.4, kg: 0.2 };

function WeightTuner() {
  const [query, setQuery] = useState('');
  const [fulltext, setFulltext] = useState(DEFAULT_WEIGHTS.fulltext);
  const [vector, setVector] = useState(DEFAULT_WEIGHTS.vector);
  const [kg, setKg] = useState(DEFAULT_WEIGHTS.kg);
  const [results, setResults] = useState<WeightExperimentResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    setError(null);
    try {
      const configs: WeightConfig[] = [
        { fulltext: 0.4, vector: 0.4, knowledge_graph: 0.2 }, // Default
        { fulltext, vector, knowledge_graph: kg }, // Custom
      ];
      const data = await diagnosticsService.experimentWeights(query, configs);
      setResults(data.results);
    } catch (err) {
      console.error('Weight experiment failed:', err);
      setError(
        'The weight experiment could not run. Check the diagnostics service and try again.'
      );
    } finally {
      setLoading(false);
    }
  }, [query, fulltext, vector, kg]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            Weight configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <WeightSlider
            id="weight-fulltext"
            label="Full text"
            value={fulltext}
            onChange={(v) => normalizeWeights('fulltext', v)}
          />
          <WeightSlider
            id="weight-vector"
            label="Vector"
            value={vector}
            onChange={(v) => normalizeWeights('vector', v)}
          />
          <WeightSlider
            id="weight-kg"
            label="Knowledge graph"
            value={kg}
            onChange={(v) => normalizeWeights('kg', v)}
          />
        </CardContent>
      </Card>

      <div className="flex gap-2">
        <label className="sr-only" htmlFor="weight-query">
          Test query
        </label>
        <Input
          id="weight-query"
          placeholder="Enter a test query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && runExperiment()}
          className="min-w-0 flex-1"
        />
        <Button
          onClick={runExperiment}
          disabled={loading || !query.trim()}
          className="shrink-0"
        >
          {loading ? 'Running' : 'Compare'}
        </Button>
      </div>

      {error && <LoadError message={error} onRetry={runExperiment} />}

      {/* Results comparison */}
      <div role="status" aria-live="polite">
        {!error && results.length > 0 && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {results.map((r, i) => (
              <Card key={i}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium">
                    {i === 0 ? 'Default weights' : 'Custom weights'}
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-sm">
                  <div className="text-xs text-muted-foreground">
                    {Object.entries(r.weights)
                      .map(([k, v]) => `${k} ${(v * 100).toFixed(0)}%`)
                      .join(', ')}
                  </div>
                  <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
                    <Metric label="Results" value={`${r.result_count}`} />
                    <Metric
                      label="Time"
                      value={`${r.total_time_ms.toFixed(0)} ms`}
                    />
                  </dl>
                  {r.top_scores.length > 0 && (
                    <div className="mt-2 text-xs text-muted-foreground tabular-nums">
                      Top scores:{' '}
                      {r.top_scores.map((s) => s.toFixed(3)).join(', ')}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function WeightSlider({
  id,
  label,
  value,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  const pct = (value * 100).toFixed(0);
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm">
        {label}: <span className="tabular-nums">{pct}%</span>
      </label>
      <Slider
        id={id}
        value={[value]}
        min={0}
        max={1}
        step={0.05}
        aria-label={`${label} weight`}
        aria-valuetext={`${pct} percent`}
        onValueChange={([v]) => onChange(v)}
      />
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
  const [error, setError] = useState<string | null>(null);

  const loadAnalysis = useCallback(async () => {
    setLoading(true);
    setError(null);
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
      setError(
        'Could not load bottleneck analysis. Check the diagnostics service and try again.'
      );
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

  const severityLabel = (severity: string) =>
    severity === 'high' ? 'High' : severity === 'medium' ? 'Medium' : 'Low';

  return (
    <div className="space-y-4" aria-busy={loading}>
      <div className="flex flex-wrap items-center gap-3 sm:gap-4">
        <span className="text-sm text-muted-foreground">
          Analyzing last {traces.length} queries
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={loadAnalysis}
          disabled={loading}
        >
          <RotateCw
            className={cn('mr-2 h-4 w-4', loading && 'animate-spin')}
            aria-hidden="true"
          />
          {loading ? 'Analyzing' : 'Refresh'}
        </Button>
      </div>

      {error && <LoadError message={error} onRetry={loadAnalysis} />}

      {!error && (
        <>
          {/* Pipeline health overview */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">
                Pipeline health
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-x-8 gap-y-3">
                {stageHealthSummary.map((s) => (
                  <StageHealth
                    key={s.stage}
                    stage={s.stage}
                    health={s.health}
                  />
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Top issues */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">
                Top issues ({allFindings.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {allFindings.length === 0 && (
                <p className="text-sm text-muted-foreground">
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
                    {severityLabel(finding.severity)}
                  </Badge>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">
                        {finding.title}
                      </span>
                      {count > 1 && (
                        <span className="text-xs text-muted-foreground">
                          ({count}×)
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {finding.detail}
                    </p>
                    <p className="mt-1 text-xs font-medium text-foreground">
                      {finding.recommendation}
                    </p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </>
      )}
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
        <h1 className="nous-h2 text-foreground">Retrieval diagnostics</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Inspect the retrieval pipeline, find bottlenecks, and tune search
          weights.
        </p>
      </div>

      <Tabs defaultValue="explorer" className="w-full">
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:overflow-visible sm:px-0">
          <TabsList className="h-auto w-max min-w-full flex-nowrap justify-start sm:w-auto sm:min-w-0">
            <TabsTrigger value="explorer" className="min-h-[40px] shrink-0">
              Query explorer
            </TabsTrigger>
            <TabsTrigger value="quality" className="min-h-[40px] shrink-0">
              Quality overview
            </TabsTrigger>
            <TabsTrigger value="weights" className="min-h-[40px] shrink-0">
              Weight tuner
            </TabsTrigger>
            <TabsTrigger value="bottleneck" className="min-h-[40px] shrink-0">
              Bottleneck analysis
            </TabsTrigger>
          </TabsList>
        </div>

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
