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
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

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

const PerformanceDetail: React.FC<PerformanceDetailProps> = ({ metrics, isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'latency' | 'quality' | 'resources' | 'bottlenecks'>('overview');

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-600';
    if (score >= 80) return 'text-yellow-600';
    if (score >= 70) return 'text-orange-600';
    return 'text-red-600';
  };

  const getScoreBackground = (score: number) => {
    if (score >= 90) return 'bg-green-100 text-green-800';
    if (score >= 80) return 'bg-yellow-100 text-yellow-800';
    if (score >= 70) return 'bg-orange-100 text-orange-800';
    return 'bg-red-100 text-red-800';
  };

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case 'low':
        return 'bg-green-100 text-green-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800';
      case 'high':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
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
        <div className="border-b border-gray-200">
          <nav className="flex space-x-8">
            {['overview', 'latency', 'quality', 'resources', 'bottlenecks'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab as any)}
                className={cn(
                  "py-2 px-1 border-b-2 font-medium text-sm capitalize",
                  activeTab === tab
                    ? "border-blue-500 text-blue-600"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                )}
              >
                {tab}
              </button>
            ))}
          </nav>
        </div>

        <div className="mt-6">
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Key Metrics */}
              <div className="grid grid-cols-4 gap-4">
                <div className="p-4 bg-blue-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <ClockIcon className="h-5 w-5 text-blue-600" />
                    <span className={cn("text-sm font-medium", getScoreColor(100 - (metrics.total_latency_ms / 20)))}>
                      {metrics.total_latency_ms < 1000 ? 'Excellent' : metrics.total_latency_ms < 2000 ? 'Good' : 'Needs Improvement'}
                    </span>
                  </div>
                  <div className="text-2xl font-bold text-blue-900">
                    {metrics.total_latency_ms}ms
                  </div>
                  <div className="text-sm text-blue-700">Total Latency</div>
                </div>

                <div className="p-4 bg-green-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <CheckCircleIcon className="h-5 w-5 text-green-600" />
                    <span className={cn("text-sm font-medium", getScoreColor(metrics.quality_metrics.rag_triad_compliance.answer_relevancy))}>
                      {metrics.quality_metrics.rag_triad_compliance.answer_relevancy >= 70 ? 'Pass' : 'Fail'}
                    </span>
                  </div>
                  <div className="text-2xl font-bold text-green-900">
                    {Math.round(metrics.quality_metrics.rag_triad_compliance.answer_relevancy)}%
                  </div>
                  <div className="text-sm text-green-700">Answer Relevancy</div>
                </div>

                <div className="p-4 bg-purple-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <CircleStackIcon className="h-5 w-5 text-purple-600" />
                    <span className="text-sm font-medium text-purple-900">
                      {metrics.cache_performance.cache_hit_rate >= 0.5 ? 'Good' : 'Poor'}
                    </span>
                  </div>
                  <div className="text-2xl font-bold text-purple-900">
                    {Math.round(metrics.cache_performance.cache_hit_rate * 100)}%
                  </div>
                  <div className="text-sm text-purple-700">Cache Hit Rate</div>
                </div>

                <div className="p-4 bg-orange-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <BoltIcon className="h-5 w-5 text-orange-600" />
                    <span className={cn("text-sm font-medium", getScoreColor(100 - metrics.resource_usage.cpu_percent))}>
                      {metrics.resource_usage.cpu_percent < 50 ? 'Good' : 'High'}
                    </span>
                  </div>
                  <div className="text-2xl font-bold text-orange-900">
                    {metrics.resource_usage.cpu_percent}%
                  </div>
                  <div className="text-sm text-orange-700">CPU Usage</div>
                </div>
              </div>

              {/* RAG Triad Compliance */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-3">RAG Triad Compliance</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-4 border border-gray-200 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-gray-700">Answer Relevancy</span>
                      <Badge className={getScoreBackground(metrics.quality_metrics.rag_triad_compliance.answer_relevancy)}>
                        {Math.round(metrics.quality_metrics.rag_triad_compliance.answer_relevancy)}%
                      </Badge>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={cn("h-2 rounded-full",
                          metrics.quality_metrics.rag_triad_compliance.answer_relevancy >= 90 ? "bg-green-600" :
                          metrics.quality_metrics.rag_triad_compliance.answer_relevancy >= 80 ? "bg-yellow-600" : "bg-red-600"
                        )}
                        style={{ width: `${metrics.quality_metrics.rag_triad_compliance.answer_relevancy}%` }}
                      />
                    </div>
                  </div>

                  <div className="p-4 border border-gray-200 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-gray-700">Faithfulness</span>
                      <Badge className={getScoreBackground(metrics.quality_metrics.rag_triad_compliance.faithfulness)}>
                        {Math.round(metrics.quality_metrics.rag_triad_compliance.faithfulness)}%
                      </Badge>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={cn("h-2 rounded-full",
                          metrics.quality_metrics.rag_triad_compliance.faithfulness >= 90 ? "bg-green-600" :
                          metrics.quality_metrics.rag_triad_compliance.faithfulness >= 80 ? "bg-yellow-600" : "bg-red-600"
                        )}
                        style={{ width: `${metrics.quality_metrics.rag_triad_compliance.faithfulness}%` }}
                      />
                    </div>
                  </div>

                  <div className="p-4 border border-gray-200 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-gray-700">Contextual Relevancy</span>
                      <Badge className={getScoreBackground(metrics.quality_metrics.rag_triad_compliance.contextual_relevancy)}>
                        {Math.round(metrics.quality_metrics.rag_triad_compliance.contextual_relevancy)}%
                      </Badge>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={cn("h-2 rounded-full",
                          metrics.quality_metrics.rag_triad_compliance.contextual_relevancy >= 90 ? "bg-green-600" :
                          metrics.quality_metrics.rag_triad_compliance.contextual_relevancy >= 80 ? "bg-yellow-600" : "bg-red-600"
                        )}
                        style={{ width: `${metrics.quality_metrics.rag_triad_compliance.contextual_relevancy}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Additional Metrics */}
              <div className="grid grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">Quality Metrics</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Hallucination Risk:</span>
                      <span className={cn("font-medium", getScoreColor(100 - metrics.quality_metrics.hallucination_risk))}>
                        {Math.round(metrics.quality_metrics.hallucination_risk)}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Confidence Score:</span>
                      <span className={cn("font-medium", getScoreColor(metrics.quality_metrics.confidence_score))}>
                        {Math.round(metrics.quality_metrics.confidence_score)}%
                      </span>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-medium text-gray-900 mb-2">Resource Usage</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Memory:</span>
                      <span className="font-medium">{formatBytes(metrics.resource_usage.memory_mb * 1024 * 1024)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Network Requests:</span>
                      <span className="font-medium">{metrics.resource_usage.network_requests}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Latency Breakdown Tab */}
          {activeTab === 'latency' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900">Stage Latency Breakdown</h3>
              <div className="space-y-4">
                {Object.entries(metrics.stage_latencies).map(([stage, latency]) => (
                  <div key={stage} className="p-4 border border-gray-200 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-medium text-gray-900 capitalize">
                        {stage.replace('_', ' ')}
                      </span>
                      <div className="flex items-center space-x-2">
                        <span className="text-lg font-bold text-gray-900">{latency}ms</span>
                        <Badge className={cn(
                          latency < 100 ? "bg-green-100 text-green-800" :
                          latency < 300 ? "bg-yellow-100 text-yellow-800" :
                          "bg-red-100 text-red-800"
                        )}>
                          {latency < 100 ? 'Fast' : latency < 300 ? 'Normal' : 'Slow'}
                        </Badge>
                      </div>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className={cn("h-2 rounded-full",
                          latency < 100 ? "bg-green-600" :
                          latency < 300 ? "bg-yellow-600" : "bg-red-600"
                        )}
                        style={{ width: `${Math.min((latency / 500) * 100, 100)}%` }}
                      />
                    </div>
                    <div className="mt-2 text-sm text-gray-600">
                      {Math.round((latency / metrics.total_latency_ms) * 100)}% of total time
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Quality Metrics Tab */}
          {activeTab === 'quality' && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-gray-900">Quality Analysis</h3>

              <div className="grid grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium text-gray-900 mb-4">RAG Triad Scores</h4>
                  <div className="space-y-3">
                    {Object.entries(metrics.quality_metrics.rag_triad_compliance).map(([metric, score]) => (
                      <div key={metric} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <span className="font-medium text-gray-900 capitalize">
                          {metric.replace('_', ' ')}
                        </span>
                        <div className="flex items-center space-x-2">
                          <div className="w-24 bg-gray-200 rounded-full h-2">
                            <div
                              className={cn("h-2 rounded-full",
                                score >= 90 ? "bg-green-600" :
                                score >= 80 ? "bg-yellow-600" : "bg-red-600"
                              )}
                              style={{ width: `${score}%` }}
                            />
                          </div>
                          <span className={cn("font-bold text-sm", getScoreColor(score))}>
                            {Math.round(score)}%
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 className="font-medium text-gray-900 mb-4">Additional Quality Metrics</h4>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <span className="font-medium text-gray-900">Hallucination Risk</span>
                      <Badge className={getScoreBackground(100 - metrics.quality_metrics.hallucination_risk)}>
                        {Math.round(metrics.quality_metrics.hallucination_risk)}%
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <span className="font-medium text-gray-900">Confidence Score</span>
                      <Badge className={getScoreBackground(metrics.quality_metrics.confidence_score)}>
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
              <h3 className="text-lg font-semibold text-gray-900">Resource Utilization</h3>

              <div className="grid grid-cols-3 gap-6">
                <div className="p-4 bg-blue-50 rounded-lg">
                  <div className="flex items-center space-x-2 mb-3">
                    <CpuChipIcon className="h-5 w-5 text-blue-600" />
                    <h4 className="font-medium text-blue-900">CPU Usage</h4>
                  </div>
                  <div className="text-2xl font-bold text-blue-900 mb-2">
                    {metrics.resource_usage.cpu_percent}%
                  </div>
                  <div className="w-full bg-blue-200 rounded-full h-2">
                    <div
                      className={cn("h-2 rounded-full",
                        metrics.resource_usage.cpu_percent < 50 ? "bg-green-600" :
                        metrics.resource_usage.cpu_percent < 80 ? "bg-yellow-600" : "bg-red-600"
                      )}
                      style={{ width: `${Math.min(metrics.resource_usage.cpu_percent, 100)}%` }}
                    />
                  </div>
                </div>

                <div className="p-4 bg-green-50 rounded-lg">
                  <div className="flex items-center space-x-2 mb-3">
                    <CircleStackIcon className="h-5 w-5 text-green-600" />
                    <h4 className="font-medium text-green-900">Memory Usage</h4>
                  </div>
                  <div className="text-2xl font-bold text-green-900 mb-2">
                    {formatBytes(metrics.resource_usage.memory_mb * 1024 * 1024)}
                  </div>
                  <div className="text-sm text-green-700">
                    {metrics.resource_usage.memory_mb < 100 ? 'Low' :
                     metrics.resource_usage.memory_mb < 500 ? 'Normal' : 'High'} usage
                  </div>
                </div>

                <div className="p-4 bg-purple-50 rounded-lg">
                  <div className="flex items-center space-x-2 mb-3">
                    <ServerIcon className="h-5 w-5 text-purple-600" />
                    <h4 className="font-medium text-purple-900">Network</h4>
                  </div>
                  <div className="text-2xl font-bold text-purple-900 mb-2">
                    {metrics.resource_usage.network_requests}
                  </div>
                  <div className="text-sm text-purple-700">Requests</div>
                </div>
              </div>

              {/* Cache Performance */}
              <div className="p-4 bg-gray-50 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-3">Cache Performance</h4>
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="text-lg font-bold text-gray-900">
                      {metrics.cache_performance.cache_hit_rate * 100}%
                    </div>
                    <div className="text-sm text-gray-600">Hit Rate</div>
                  </div>
                  <div>
                    <div className="text-lg font-bold text-gray-900">
                      {metrics.cache_performance.cache_hits}
                    </div>
                    <div className="text-sm text-gray-600">Hits</div>
                  </div>
                  <div>
                    <div className="text-lg font-bold text-gray-900">
                      {metrics.cache_performance.cache_misses}
                    </div>
                    <div className="text-sm text-gray-600">Misses</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Bottlenecks Tab */}
          {activeTab === 'bottlenecks' && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900">Performance Bottlenecks</h3>

              {metrics.bottlenecks.length > 0 ? (
                <div className="space-y-3">
                  {metrics.bottlenecks.map((bottleneck, index) => (
                    <div key={index} className="p-4 border border-gray-200 rounded-lg">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-3 mb-2">
                            <ExclamationTriangleIcon className="h-4 w-4 text-yellow-600" />
                            <span className="font-medium text-gray-900">
                              {bottleneck.stage.replace('_', ' ')}
                            </span>
                            <Badge className={getImpactColor(bottleneck.impact)}>
                              {bottleneck.impact} impact
                            </Badge>
                          </div>
                          <p className="text-sm text-gray-700 mb-2">{bottleneck.issue}</p>
                          <p className="text-sm text-blue-700">{bottleneck.suggestion}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <CheckCircleIcon className="h-12 w-12 text-green-500 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    No bottlenecks detected
                  </h3>
                  <p className="text-gray-600">
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

export const QueryPerformanceMonitor: React.FC<QueryPerformanceMonitorProps> = ({
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
          impact: latency > 500 ? 'high' : 'medium' as const,
          suggestion: `Consider optimizing ${stage.replace('_', ' ')} algorithms or increasing resources`
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
      bottlenecks
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
    if (processingState && (processingState.current_stage === 'search_execution' || processingState.current_stage === 'result_aggregation')) {
      startMonitoring();
    } else if (processingState?.current_stage === 'completed' && metrics) {
      // Generate final metrics when processing completes
      const finalMetrics = generateMockMetrics();
      setMetrics(finalMetrics);
      onMetricsUpdate?.(finalMetrics);
    }
  }, [processingState, startMonitoring, metrics, generateMockMetrics, onMetricsUpdate]);

  const getPerformanceStatus = () => {
    if (!metrics) return 'unknown';

    if (metrics.total_latency_ms < 1000 &&
        metrics.quality_metrics.rag_triad_compliance.answer_relevancy > 80 &&
        metrics.resource_usage.cpu_percent < 70) {
      return 'excellent';
    } else if (metrics.total_latency_ms < 2000 &&
               metrics.quality_metrics.rag_triad_compliance.answer_relevancy > 70 &&
               metrics.resource_usage.cpu_percent < 85) {
      return 'good';
    } else {
      return 'needs-improvement';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'excellent':
        return 'text-green-600';
      case 'good':
        return 'text-yellow-600';
      case 'needs-improvement':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const getStatusBackground = (status: string) => {
    switch (status) {
      case 'excellent':
        return 'bg-green-100 text-green-800';
      case 'good':
        return 'bg-yellow-100 text-yellow-800';
      case 'needs-improvement':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (!metrics) {
    return null;
  }

  const performanceStatus = getPerformanceStatus();

  return (
    <div className={cn("space-y-4", className)}>
      {/* Performance Header */}
      <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
        <div className="flex items-center space-x-3">
          {isMonitoring ? (
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
          ) : (
            <ChartBarIcon className="h-5 w-5 text-blue-600" />
          )}
          <div>
            <h3 className="font-medium text-gray-900">Performance Monitor</h3>
            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-600">
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
            <div className="flex items-center space-x-1 text-yellow-600">
              <ExclamationTriangleIcon className="h-4 w-4" />
              <span className="text-sm font-medium">
                {metrics.bottlenecks.length} bottleneck{metrics.bottlenecks.length !== 1 ? 's' : ''}
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
        <div className="flex items-center space-x-2 p-3 bg-blue-50 rounded-lg">
          <ClockIcon className="h-4 w-4 text-blue-600" />
          <div>
            <div className="text-sm font-medium text-blue-900">
              {metrics.total_latency_ms}ms
            </div>
            <div className="text-xs text-blue-700">Latency</div>
          </div>
        </div>

        <div className="flex items-center space-x-2 p-3 bg-green-50 rounded-lg">
          <CheckCircleIcon className="h-4 w-4 text-green-600" />
          <div>
            <div className="text-sm font-medium text-green-900">
              {Math.round(metrics.quality_metrics.rag_triad_compliance.answer_relevancy)}%
            </div>
            <div className="text-xs text-green-700">Answer Quality</div>
          </div>
        </div>

        <div className="flex items-center space-x-2 p-3 bg-purple-50 rounded-lg">
          <CircleStackIcon className="h-4 w-4 text-purple-600" />
          <div>
            <div className="text-sm font-medium text-purple-900">
              {Math.round(metrics.cache_performance.cache_hit_rate * 100)}%
            </div>
            <div className="text-xs text-purple-700">Cache Hit</div>
          </div>
        </div>

        <div className="flex items-center space-x-2 p-3 bg-orange-50 rounded-lg">
          <CpuChipIcon className="h-4 w-4 text-orange-600" />
          <div>
            <div className="text-sm font-medium text-orange-900">
              {metrics.resource_usage.cpu_percent}%
            </div>
            <div className="text-xs text-orange-700">CPU</div>
          </div>
        </div>
      </div>

      {/* Bottleneck Alert */}
      {metrics.bottlenecks.length > 0 && (
        <div className="flex items-center space-x-2 p-3 bg-yellow-50 rounded-lg">
          <ExclamationTriangleIcon className="h-4 w-4 text-yellow-600" />
          <span className="text-sm text-yellow-800">
            Performance bottleneck detected in {metrics.bottlenecks[0]?.stage.replace('_', ' ')}: {metrics.bottlenecks[0]?.issue}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDetailDialog(true)}
            className="h-6 text-xs text-yellow-700 hover:text-yellow-900"
          >
            View Details
          </Button>
        </div>
      )}

      {/* Monitoring Status */}
      {isMonitoring && (
        <div className="flex items-center space-x-2 p-3 bg-blue-50 rounded-lg">
          <div className="h-3 w-3 animate-ping bg-blue-600 rounded-full" />
          <span className="text-sm text-blue-800">Real-time monitoring active</span>
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