import React, { useState, useCallback, useEffect } from 'react';
import {
  ChartBarIcon,
  ClockIcon,
  CpuChipIcon,
  ServerIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  InformationCircleIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  LightBulbIcon,
  CircleStackIcon,
  BoltIcon,
} from '@heroicons/react/24/outline';
import { QueryPerformanceMetrics, QueryProcessingState } from '@/types/search';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

interface QueryPerformanceMonitorProps {
  processingState?: QueryProcessingState;
  onMetricsUpdate?: (metrics: QueryPerformanceMetrics) => void;
  showRealTime?: boolean;
  showDetails?: boolean;
  refreshInterval?: number;
  className?: string;
}

interface PerformanceDetailProps {
  metrics: QueryPerformanceMetrics;
  isOpen: boolean;
  onClose: () => void;
}

const PerformanceDetail: React.FC<PerformanceDetailProps> = ({
  metrics,
  isOpen,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<
    'overview' | 'latency' | 'quality' | 'resources' | 'bottlenecks'
  >('overview');

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-[var(--nous-terra)]';
    if (score >= 80) return 'text-[var(--nous-corona)]';
    if (score >= 70) return 'text-[var(--nous-corona)]';
    return 'text-[var(--nous-mars)]';
  };

  const getScoreBackground = (score: number) => {
    if (score >= 90)
      return 'bg-[var(--nous-terra)]/15 text-[var(--nous-terra)]';
    if (score >= 80)
      return 'bg-[var(--nous-corona)]/15 text-[var(--nous-corona)]';
    if (score >= 70)
      return 'bg-[var(--nous-corona)]/15 text-[var(--nous-corona)]';
    return 'bg-[var(--nous-mars)]/15 text-[var(--nous-mars)]';
  };

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case 'low':
        return 'bg-[var(--nous-terra)]/15 text-[var(--nous-terra)]';
      case 'medium':
        return 'bg-[var(--nous-corona)]/15 text-[var(--nous-corona)]';
      case 'high':
        return 'bg-[var(--nous-mars)]/15 text-[var(--nous-mars)]';
      default:
        return 'bg-[var(--nous-bg-3)] text-[var(--nous-fg-1)]';
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 MB';
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-5xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Performance Analysis</DialogTitle>
        </DialogHeader>

        {/* Tabs */}
        <div className="border-b border-border">
          <nav role="tablist" className="flex space-x-8">
            {['overview', 'latency', 'quality', 'resources', 'bottlenecks'].map(
              (tab) => (
                <button
                  key={tab}
                  role="tab"
                  aria-selected={activeTab === tab}
                  onClick={() => setActiveTab(tab as any)}
                  className={cn(
                    'py-2 px-1 border-b-2 font-medium text-sm capitalize',
                    activeTab === tab
                      ? 'border-[var(--nous-sol)] text-[var(--nous-fg-accent-safe)]'
                      : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border'
                  )}
                >
                  {tab}
                </button>
              )
            )}
          </nav>
        </div>

        <div className="mt-6">
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Key Metrics */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-4 bg-[var(--nous-sol)]/10 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <ClockIcon className="h-5 w-5 text-[var(--nous-fg-accent-safe)]" />
                    <span
                      className={cn(
                        'text-sm font-medium',
                        getScoreColor(100 - metrics.total_latency_ms / 20)
                      )}
                    >
                      {metrics.total_latency_ms < 1000
                        ? 'Excellent'
                        : metrics.total_latency_ms < 2000
                          ? 'Good'
                          : 'Needs Improvement'}
                    </span>
                  </div>
                  <div className="text-2xl font-bold text-[var(--nous-fg-accent-safe)]">
                    {metrics.total_latency_ms}ms
                  </div>
                  <div className="text-sm text-[var(--nous-fg-accent-safe)]">
                    Total Latency
                  </div>
                </div>

                <div className="p-4 bg-[var(--nous-terra)]/10 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <CheckCircleIcon className="h-5 w-5 text-[var(--nous-terra)]" />
                    <span
                      className={cn(
                        'text-sm font-medium',
                        getScoreColor(
                          metrics.quality_metrics.rag_triad_compliance
                            .answer_relevancy
                        )
                      )}
                    >
                      {metrics.quality_metrics.rag_triad_compliance
                        .answer_relevancy >= 70
                        ? 'Pass'
                        : 'Fail'}
                    </span>
                  </div>
                  <div className="text-2xl font-bold text-[var(--nous-terra)]">
                    {Math.round(
                      metrics.quality_metrics.rag_triad_compliance
                        .answer_relevancy
                    )}
                    %
                  </div>
                  <div className="text-sm text-[var(--nous-terra)]">
                    Answer Relevancy
                  </div>
                </div>

                <div className="p-4 bg-[var(--nous-sol)]/10 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <CircleStackIcon className="h-5 w-5 text-[var(--nous-fg-accent-safe)]" />
                    <span className="text-sm font-medium text-[var(--nous-fg-accent-safe)]">
                      {metrics.cache_performance.cache_hit_rate >= 0.5
                        ? 'Good'
                        : 'Poor'}
                    </span>
                  </div>
                  <div className="text-2xl font-bold text-[var(--nous-fg-accent-safe)]">
                    {Math.round(metrics.cache_performance.cache_hit_rate * 100)}
                    %
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Cache Hit Rate
                  </div>
                </div>

                <div className="p-4 bg-[var(--nous-corona)]/10 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <BoltIcon className="h-5 w-5 text-[var(--nous-corona)]" />
                    <span
                      className={cn(
                        'text-sm font-medium',
                        getScoreColor(100 - metrics.resource_usage.cpu_percent)
                      )}
                    >
                      {metrics.resource_usage.cpu_percent < 50
                        ? 'Good'
                        : 'High'}
                    </span>
                  </div>
                  <div className="text-2xl font-bold text-[var(--nous-corona)]">
                    {metrics.resource_usage.cpu_percent}%
                  </div>
                  <div className="text-sm text-[var(--nous-corona)]">
                    CPU Usage
                  </div>
                </div>
              </div>

              {/* RAG Triad Compliance */}
              <div>
                <h3 className="text-lg font-semibold text-foreground mb-3">
                  RAG Triad Compliance
                </h3>
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-4 border border-border rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-foreground">Answer Relevancy</span>
                      <Badge
                        className={getScoreBackground(
                          metrics.quality_metrics.rag_triad_compliance
                            .answer_relevancy
                        )}
                      >
                        {Math.round(
                          metrics.quality_metrics.rag_triad_compliance
                            .answer_relevancy
                        )}
                        %
                      </Badge>
                    </div>
                    <div className="w-full bg-[var(--nous-bg-3)] rounded-full h-2">
                      <div
                        className={cn(
                          'h-2 rounded-full',
                          metrics.quality_metrics.rag_triad_compliance
                            .answer_relevancy >= 90
                            ? 'bg-[var(--nous-terra)]'
                            : metrics.quality_metrics.rag_triad_compliance
                                  .answer_relevancy >= 80
                              ? 'bg-[var(--nous-corona)]'
                              : 'bg-[var(--nous-mars)]'
                        )}
                        style={{
                          width: `${metrics.quality_metrics.rag_triad_compliance.answer_relevancy}%`,
                        }}
                      />
                    </div>
                  </div>

                  <div className="p-4 border border-border rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-foreground">Faithfulness</span>
                      <Badge
                        className={getScoreBackground(
                          metrics.quality_metrics.rag_triad_compliance
                            .faithfulness
                        )}
                      >
                        {Math.round(
                          metrics.quality_metrics.rag_triad_compliance
                            .faithfulness
                        )}
                        %
                      </Badge>
                    </div>
                    <div className="w-full bg-[var(--nous-bg-3)] rounded-full h-2">
                      <div
                        className={cn(
                          'h-2 rounded-full',
                          metrics.quality_metrics.rag_triad_compliance
                            .faithfulness >= 90
                            ? 'bg-[var(--nous-terra)]'
                            : metrics.quality_metrics.rag_triad_compliance
                                  .faithfulness >= 80
                              ? 'bg-[var(--nous-corona)]'
                              : 'bg-[var(--nous-mars)]'
                        )}
                        style={{
                          width: `${metrics.quality_metrics.rag_triad_compliance.faithfulness}%`,
                        }}
                      />
                    </div>
                  </div>

                  <div className="p-4 border border-border rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-foreground">
                        Contextual Relevancy
                      </span>
                      <Badge
                        className={getScoreBackground(
                          metrics.quality_metrics.rag_triad_compliance
                            .contextual_relevancy
                        )}
                      >
                        {Math.round(
                          metrics.quality_metrics.rag_triad_compliance
                            .contextual_relevancy
                        )}
                        %
                      </Badge>
                    </div>
                    <div className="w-full bg-[var(--nous-bg-3)] rounded-full h-2">
                      <div
                        className={cn(
                          'h-2 rounded-full',
                          metrics.quality_metrics.rag_triad_compliance
                            .contextual_relevancy >= 90
                            ? 'bg-[var(--nous-terra)]'
                            : metrics.quality_metrics.rag_triad_compliance
                                  .contextual_relevancy >= 80
                              ? 'bg-[var(--nous-corona)]'
                              : 'bg-[var(--nous-mars)]'
                        )}
                        style={{
                          width: `${metrics.quality_metrics.rag_triad_compliance.contextual_relevancy}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Additional Metrics */}
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium text-foreground mb-2">
                    Quality Metrics
                  </h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-foreground">
                        Hallucination Risk:
                      </span>
                      <span
                        className={cn(
                          'font-medium',
                          getScoreColor(
                            100 - metrics.quality_metrics.hallucination_risk
                          )
                        )}
                      >
                        {Math.round(metrics.quality_metrics.hallucination_risk)}
                        %
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-foreground">Confidence Score:</span>
                      <span
                        className={cn(
                          'font-medium',
                          getScoreColor(
                            metrics.quality_metrics.confidence_score
                          )
                        )}
                      >
                        {Math.round(metrics.quality_metrics.confidence_score)}%
                      </span>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-medium text-foreground mb-2">
                    Resource Usage
                  </h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-foreground">Memory:</span>
                      <span className="font-medium">
                        {formatBytes(
                          metrics.resource_usage.memory_mb * 1024 * 1024
                        )}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-foreground">Network Requests:</span>
                      <span className="font-medium">
                        {metrics.resource_usage.network_requests}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Latency Breakdown Tab */}
          {activeTab === 'latency' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-foreground">
                Stage Latency Breakdown
              </h3>
              <div className="space-y-4">
                {Object.entries(metrics.stage_latencies).map(
                  ([stage, latency]) => (
                    <div
                      key={stage}
                      className="p-4 border border-border rounded-lg"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-foreground capitalize">
                          {stage.replace('_', ' ')}
                        </span>
                        <div className="flex items-center space-x-2">
                          <span className="text-lg font-bold text-foreground">
                            {latency}ms
                          </span>
                          <Badge
                            className={cn(
                              latency < 100
                                ? 'bg-[var(--nous-terra)]/15 text-[var(--nous-terra)]'
                                : latency < 300
                                  ? 'bg-[var(--nous-corona)]/15 text-[var(--nous-corona)]'
                                  : 'bg-[var(--nous-mars)]/15 text-[var(--nous-mars)]'
                            )}
                          >
                            {latency < 100
                              ? 'Fast'
                              : latency < 300
                                ? 'Normal'
                                : 'Slow'}
                          </Badge>
                        </div>
                      </div>
                      <div className="w-full bg-[var(--nous-bg-3)] rounded-full h-2">
                        <div
                          className={cn(
                            'h-2 rounded-full',
                            latency < 100
                              ? 'bg-[var(--nous-terra)]'
                              : latency < 300
                                ? 'bg-[var(--nous-corona)]'
                                : 'bg-[var(--nous-mars)]'
                          )}
                          style={{
                            width: `${Math.min((latency / 500) * 100, 100)}%`,
                          }}
                        />
                      </div>
                      <div className="mt-2 text-sm text-foreground">
                        {Math.round((latency / metrics.total_latency_ms) * 100)}
                        % of total time
                      </div>
                    </div>
                  )
                )}
              </div>
            </div>
          )}

          {/* Quality Metrics Tab */}
          {activeTab === 'quality' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-foreground">
                Quality Analysis
              </h3>

              <div className="grid grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium text-foreground mb-4">
                    RAG Triad Scores
                  </h4>
                  <div className="space-y-3">
                    {Object.entries(
                      metrics.quality_metrics.rag_triad_compliance
                    ).map(([metric, score]) => (
                      <div
                        key={metric}
                        className="flex items-center justify-between p-3 bg-[var(--nous-bg-2)] rounded-lg"
                      >
                        <span className="font-medium text-foreground capitalize">
                          {metric.replace('_', ' ')}
                        </span>
                        <div className="flex items-center space-x-2">
                          <div className="w-24 bg-[var(--nous-bg-3)] rounded-full h-2">
                            <div
                              className={cn(
                                'h-2 rounded-full',
                                score >= 90
                                  ? 'bg-[var(--nous-terra)]'
                                  : score >= 80
                                    ? 'bg-[var(--nous-corona)]'
                                    : 'bg-[var(--nous-mars)]'
                              )}
                              style={{ width: `${score}%` }}
                            />
                          </div>
                          <span
                            className={cn(
                              'font-bold text-sm',
                              getScoreColor(score)
                            )}
                          >
                            {Math.round(score)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="font-medium text-foreground mb-4">
                    Additional Quality Metrics
                  </h4>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 bg-[var(--nous-bg-2)] rounded-lg">
                      <span className="font-medium text-foreground">
                        Hallucination Risk
                      </span>
                      <Badge
                        className={getScoreBackground(
                          100 - metrics.quality_metrics.hallucination_risk
                        )}
                      >
                        {Math.round(metrics.quality_metrics.hallucination_risk)}
                        %
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-[var(--nous-bg-2)] rounded-lg">
                      <span className="font-medium text-foreground">
                        Confidence Score
                      </span>
                      <Badge
                        className={getScoreBackground(
                          metrics.quality_metrics.confidence_score
                        )}
                      >
                        {Math.round(metrics.quality_metrics.confidence_score)}%
                      </Badge>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Resources Tab */}
          {activeTab === 'resources' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-foreground">
                Resource Utilization
              </h3>

              <div className="grid grid-cols-3 gap-6">
                <div className="p-4 bg-[var(--nous-sol)]/10 rounded-lg">
                  <div className="flex items-center space-x-2 mb-3">
                    <CpuChipIcon className="h-5 w-5 text-[var(--nous-fg-accent-safe)]" />
                    <h4 className="font-medium text-[var(--nous-fg-accent-safe)]">
                      CPU Usage
                    </h4>
                  </div>
                  <div className="text-2xl font-bold text-[var(--nous-fg-accent-safe)] mb-2">
                    {metrics.resource_usage.cpu_percent}%
                  </div>
                  <div className="w-full bg-[var(--nous-bg-3)] rounded-full h-2">
                    <div
                      className={cn(
                        'h-2 rounded-full',
                        metrics.resource_usage.cpu_percent < 50
                          ? 'bg-[var(--nous-terra)]'
                          : metrics.resource_usage.cpu_percent < 80
                            ? 'bg-[var(--nous-corona)]'
                            : 'bg-[var(--nous-mars)]'
                      )}
                      style={{
                        width: `${Math.min(metrics.resource_usage.cpu_percent, 100)}%`,
                      }}
                    />
                  </div>
                </div>

                <div className="p-4 bg-[var(--nous-terra)]/10 rounded-lg">
                  <div className="flex items-center space-x-2 mb-3">
                    <CircleStackIcon className="h-5 w-5 text-[var(--nous-terra)]" />
                    <h4 className="font-medium text-[var(--nous-terra)]">
                      Memory Usage
                    </h4>
                  </div>
                  <div className="text-2xl font-bold text-[var(--nous-terra)] mb-2">
                    {formatBytes(
                      metrics.resource_usage.memory_mb * 1024 * 1024
                    )}
                  </div>
                  <div className="text-sm text-[var(--nous-terra)]">
                    {metrics.resource_usage.memory_mb < 100
                      ? 'Low'
                      : metrics.resource_usage.memory_mb < 500
                        ? 'Normal'
                        : 'High'}{' '}
                    usage
                  </div>
                </div>

                <div className="p-4 bg-[var(--nous-sol)]/10 rounded-lg">
                  <div className="flex items-center space-x-2 mb-3">
                    <ServerIcon className="h-5 w-5 text-[var(--nous-fg-accent-safe)]" />
                    <h4 className="font-medium text-[var(--nous-fg-accent-safe)]">
                      Network
                    </h4>
                  </div>
                  <div className="text-2xl font-bold text-[var(--nous-fg-accent-safe)] mb-2">
                    {metrics.resource_usage.network_requests}
                  </div>
                  <div className="text-sm text-muted-foreground">Requests</div>
                </div>
              </div>

              {/* Cache Performance */}
              <div className="p-4 bg-[var(--nous-bg-2)] rounded-lg">
                <h4 className="font-medium text-foreground mb-3">
                  Cache Performance
                </h4>
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="text-lg font-bold text-foreground">
                      {metrics.cache_performance.cache_hit_rate * 100}%
                    </div>
                    <div className="text-sm text-foreground">Hit Rate</div>
                  </div>
                  <div>
                    <div className="text-lg font-bold text-foreground">
                      {metrics.cache_performance.cache_hits}
                    </div>
                    <div className="text-sm text-foreground">Hits</div>
                  </div>
                  <div>
                    <div className="text-lg font-bold text-foreground">
                      {metrics.cache_performance.cache_misses}
                    </div>
                    <div className="text-sm text-foreground">Misses</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Bottlenecks Tab */}
          {activeTab === 'bottlenecks' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-foreground">
                Performance Bottlenecks
              </h3>

              {metrics.bottlenecks.length > 0 ? (
                <div className="space-y-3">
                  {metrics.bottlenecks.map((bottleneck, index) => (
                    <div
                      key={index}
                      className="p-4 border border-border rounded-lg"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-3 mb-2">
                            <ExclamationTriangleIcon className="h-4 w-4 text-[var(--nous-corona)]" />
                            <span className="font-medium text-foreground">
                              {bottleneck.stage.replace('_', ' ')}
                            </span>
                            <Badge
                              className={getImpactColor(bottleneck.impact)}
                            >
                              {bottleneck.impact} impact
                            </Badge>
                          </div>
                          <p className="text-sm text-foreground mb-2">
                            {bottleneck.issue}
                          </p>
                          <p className="text-sm text-[var(--nous-fg-accent-safe)]">
                            {bottleneck.suggestion}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <CheckCircleIcon className="h-12 w-12 text-[var(--nous-terra)] mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-foreground mb-2">
                    No bottlenecks detected
                  </h3>
                  <p className="text-foreground">
                    Performance is optimal across all stages
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export const QueryPerformanceMonitor: React.FC<
  QueryPerformanceMonitorProps
> = ({
  processingState,
  onMetricsUpdate,
  showRealTime = true,
  showDetails = false,
  refreshInterval = 1000,
  className,
}) => {
  const [metrics, setMetrics] = useState<QueryPerformanceMetrics | null>(null);
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [showDetailDialog, setShowDetailDialog] = useState(false);

  const generateMockMetrics = useCallback((): QueryPerformanceMetrics => {
    const totalLatency = 300 + Math.random() * 1500; // 300-1800ms

    const stageLatencies = {
      intent_detection: 50 + Math.random() * 100,
      query_rewriting: 100 + Math.random() * 200,
      vector_search: 150 + Math.random() * 300,
      graph_search: 100 + Math.random() * 250,
      keyword_search: 50 + Math.random() * 150,
      result_aggregation: 80 + Math.random() * 200,
    };

    const bottlenecks: QueryPerformanceMetrics['bottlenecks'] = [];

    // Add bottlenecks based on latency
    Object.entries(stageLatencies).forEach(([stage, latency]) => {
      if (latency > 300) {
        bottlenecks.push({
          stage,
          issue: `High latency detected in ${stage.replace('_', ' ')} stage`,
          impact: latency > 500 ? 'high' : ('medium' as const),
          suggestion: `Consider optimizing ${stage.replace('_', ' ')} algorithms or increasing resources`,
        });
      }
    });

    return {
      total_latency_ms: Math.round(totalLatency),
      stage_latencies: Object.fromEntries(
        Object.entries(stageLatencies).map(([k, v]) => [k, Math.round(v)])
      ) as QueryPerformanceMetrics['stage_latencies'],
      resource_usage: {
        memory_mb: Math.round(100 + Math.random() * 400),
        cpu_percent: Math.round(20 + Math.random() * 60),
        network_requests: Math.round(5 + Math.random() * 15),
      },
      quality_metrics: {
        rag_triad_compliance: {
          answer_relevancy: Math.round(70 + Math.random() * 30),
          faithfulness: Math.round(80 + Math.random() * 20),
          contextual_relevancy: Math.round(75 + Math.random() * 25),
        },
        hallucination_risk: Math.round(5 + Math.random() * 15),
        confidence_score: Math.round(70 + Math.random() * 30),
      },
      cache_performance: {
        cache_hit_rate: Math.random() * 0.8,
        cache_hits: Math.round(Math.random() * 10),
        cache_misses: Math.round(Math.random() * 5),
      },
      bottlenecks,
    };
  }, []);

  const startMonitoring = useCallback(() => {
    setIsMonitoring(true);

    if (showRealTime) {
      const interval = setInterval(() => {
        const newMetrics = generateMockMetrics();
        setMetrics(newMetrics);
        onMetricsUpdate?.(newMetrics);
      }, refreshInterval);

      return () => clearInterval(interval);
    }

    return undefined;
  }, [showRealTime, refreshInterval, generateMockMetrics, onMetricsUpdate]);

  useEffect(() => {
    if (
      processingState &&
      (processingState.current_stage === 'search_execution' ||
        processingState.current_stage === 'result_aggregation')
    ) {
      startMonitoring();
    } else if (processingState?.current_stage === 'completed' && metrics) {
      // Generate final metrics when processing completes
      const finalMetrics = generateMockMetrics();
      setMetrics(finalMetrics);
      onMetricsUpdate?.(finalMetrics);
    }
  }, [
    processingState,
    startMonitoring,
    metrics,
    generateMockMetrics,
    onMetricsUpdate,
  ]);

  const getPerformanceStatus = () => {
    if (!metrics) return 'unknown';

    if (
      metrics.total_latency_ms < 1000 &&
      metrics.quality_metrics.rag_triad_compliance.answer_relevancy > 80 &&
      metrics.resource_usage.cpu_percent < 70
    ) {
      return 'excellent';
    } else if (
      metrics.total_latency_ms < 2000 &&
      metrics.quality_metrics.rag_triad_compliance.answer_relevancy > 70 &&
      metrics.resource_usage.cpu_percent < 85
    ) {
      return 'good';
    } else {
      return 'needs-improvement';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'excellent':
        return 'text-[var(--nous-terra)]';
      case 'good':
        return 'text-[var(--nous-corona)]';
      case 'needs-improvement':
        return 'text-[var(--nous-mars)]';
      default:
        return 'text-foreground';
    }
  };

  const getStatusBackground = (status: string) => {
    switch (status) {
      case 'excellent':
        return 'bg-[var(--nous-terra)]/15 text-[var(--nous-terra)]';
      case 'good':
        return 'bg-[var(--nous-corona)]/15 text-[var(--nous-corona)]';
      case 'needs-improvement':
        return 'bg-[var(--nous-mars)]/15 text-[var(--nous-mars)]';
      default:
        return 'bg-[var(--nous-bg-3)] text-[var(--nous-fg-1)]';
    }
  };

  if (!metrics) {
    return null;
  }

  const performanceStatus = getPerformanceStatus();

  return (
    <div className={cn('space-y-4', className)}>
      {/* Performance Header */}
      <div className="flex items-center justify-between p-4 bg-[var(--nous-bg-2)] rounded-lg">
        <div className="flex items-center space-x-3">
          {isMonitoring ? (
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--nous-sol)] border-t-transparent" />
          ) : (
            <ChartBarIcon className="h-5 w-5 text-[var(--nous-fg-accent-safe)]" />
          )}
          <div>
            <h3 className="font-medium text-foreground">Performance Monitor</h3>
            <div className="flex items-center space-x-2">
              <span className="text-sm text-foreground">
                {metrics.total_latency_ms}ms total latency
              </span>
              <Badge className={getStatusBackground(performanceStatus)}>
                {performanceStatus.replace('-', ' ')}
              </Badge>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {metrics.bottlenecks.length > 0 && (
            <div className="flex items-center space-x-1 text-[var(--nous-corona)]">
              <ExclamationTriangleIcon className="h-4 w-4" />
              <span className="text-sm font-medium">
                {metrics.bottlenecks.length} bottleneck
                {metrics.bottlenecks.length !== 1 ? 's' : ''}
              </span>
            </div>
          )}

          {showDetails && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowDetailDialog(true)}
              className="h-8 w-8 p-0"
            >
              <InformationCircleIcon className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Quick Metrics */}
      <div className="grid grid-cols-4 gap-3">
        <div className="flex items-center space-x-2 p-3 bg-[var(--nous-sol)]/10 rounded-lg">
          <ClockIcon className="h-4 w-4 text-[var(--nous-fg-accent-safe)]" />
          <div>
            <div className="text-sm font-medium text-[var(--nous-fg-accent-safe)]">
              {metrics.total_latency_ms}ms
            </div>
            <div className="text-xs text-[var(--nous-fg-accent-safe)]">Latency</div>
          </div>
        </div>

        <div className="flex items-center space-x-2 p-3 bg-[var(--nous-terra)]/10 rounded-lg">
          <CheckCircleIcon className="h-4 w-4 text-[var(--nous-terra)]" />
          <div>
            <div className="text-sm font-medium text-[var(--nous-terra)]">
              {Math.round(
                metrics.quality_metrics.rag_triad_compliance.answer_relevancy
              )}
              %
            </div>
            <div className="text-xs text-[var(--nous-terra)]">
              Answer Quality
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 p-3 bg-[var(--nous-sol)]/10 rounded-lg">
          <CircleStackIcon className="h-4 w-4 text-[var(--nous-fg-accent-safe)]" />
          <div>
            <div className="text-sm font-medium text-[var(--nous-fg-accent-safe)]">
              {Math.round(metrics.cache_performance.cache_hit_rate * 100)}%
            </div>
            <div className="text-xs text-muted-foreground">Cache Hit</div>
          </div>
        </div>

        <div className="flex items-center space-x-2 p-3 bg-[var(--nous-corona)]/10 rounded-lg">
          <CpuChipIcon className="h-4 w-4 text-[var(--nous-corona)]" />
          <div>
            <div className="text-sm font-medium text-[var(--nous-corona)]">
              {metrics.resource_usage.cpu_percent}%
            </div>
            <div className="text-xs text-[var(--nous-corona)]">CPU</div>
          </div>
        </div>
      </div>

      {/* Bottleneck Alert */}
      {metrics.bottlenecks.length > 0 && (
        <div className="flex items-center space-x-2 p-3 bg-[var(--nous-corona)]/10 rounded-lg">
          <ExclamationTriangleIcon className="h-4 w-4 text-[var(--nous-corona)]" />
          <span className="text-sm text-[var(--nous-corona)]">
            Performance bottleneck detected in{' '}
            {metrics.bottlenecks[0]?.stage.replace('_', ' ')}:{' '}
            {metrics.bottlenecks[0]?.issue}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDetailDialog(true)}
            className="h-6 text-xs text-[var(--nous-corona)] hover:text-[var(--nous-fg-1)]"
          >
            View Details
          </Button>
        </div>
      )}

      {/* Monitoring Status */}
      {isMonitoring && (
        <div className="flex items-center space-x-2 p-3 bg-[var(--nous-sol)]/10 rounded-lg">
          <div className="h-3 w-3 animate-ping bg-[var(--nous-sol)] rounded-full" />
          <span className="text-sm text-[var(--nous-fg-accent-safe)]">
            Real-time monitoring active
          </span>
        </div>
      )}

      {/* Detail Dialog */}
      <PerformanceDetail
        metrics={metrics}
        isOpen={showDetailDialog}
        onClose={() => setShowDetailDialog(false)}
      />
    </div>
  );
};

export default QueryPerformanceMonitor;
