import React, { useState, useCallback, useMemo } from 'react';
import {
  ChartBarIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  ArrowTrendingUpIcon as TrendingUpIcon,
  ArrowTrendingDownIcon as TrendingDownIcon,
  DocumentTextIcon,
  EyeIcon,
  ArrowPathIcon,
  FunnelIcon,
  CalendarIcon,
  InformationCircleIcon,
  StarIcon,
  AcademicCapIcon,
  BeakerIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';

interface EvaluationDashboardProps {
  timeRange?: '1h' | '24h' | '7d' | '30d' | '90d';
  refreshInterval?: number;
  className?: string;
  onMetricClick?: (metric: string, details: any) => void;
}

interface RAGTriadMetrics {
  answerRelevancy: {
    current: number;
    target: number;
    trend: 'up' | 'down' | 'stable';
    history: Array<{ timestamp: number; value: number }>;
    distribution: Array<{ range: string; count: number; percentage: number }>;
  };
  faithfulness: {
    current: number;
    target: number;
    trend: 'up' | 'down' | 'stable';
    history: Array<{ timestamp: number; value: number }>;
    distribution: Array<{ range: string; count: number; percentage: number }>;
  };
  contextualRelevancy: {
    current: number;
    target: number;
    trend: 'up' | 'down' | 'stable';
    history: Array<{ timestamp: number; value: number }>;
    distribution: Array<{ range: string; count: number; percentage: number }>;
  };
}

interface PerformanceMetrics {
  latency: {
    current: number;
    target: number;
    p50: number;
    p95: number;
    p99: number;
    trend: 'improving' | 'degrading' | 'stable';
  };
  throughput: {
    current: number;
    target: number;
    peak: number;
    average: number;
  };
  errorRate: {
    current: number;
    target: number;
    errors: Array<{ type: string; count: number; percentage: number }>;
  };
  resourceUsage: {
    cpu: number;
    memory: number;
    gpu: number;
  };
}

interface QualityMetrics {
  hallucinationScore: {
    current: number;
    target: number;
    trend: 'improving' | 'degrading' | 'stable';
  };
  factualAccuracy: {
    current: number;
    target: number;
    trend: 'improving' | 'degrading' | 'stable';
  };
  coherenceScore: {
    current: number;
    target: number;
    trend: 'improving' | 'degrading' | 'stable';
  };
}

interface BenchmarkData {
  name: string;
  score: number;
  rank: number;
  total: number;
  percentile: number;
  category: 'rag_triad' | 'performance' | 'quality' | 'overall';
}

interface Alert {
  id: string;
  type: 'warning' | 'error' | 'info';
  title: string;
  message: string;
  metric: string;
  currentValue: number;
  targetValue: number;
  timestamp: number;
  acknowledged: boolean;
}

export const EvaluationDashboard: React.FC<EvaluationDashboardProps> = ({
  timeRange = '24h',
  refreshInterval = 30000,
  className,
  onMetricClick,
}) => {
  const [currentTimeRange, setCurrentTimeRange] = useState(timeRange);
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [showFilters, setShowFilters] = useState(false);

  // Mock data generation (in real implementation, this would come from API)
  const ragTriadMetrics = useMemo(
    (): RAGTriadMetrics => ({
      answerRelevancy: {
        current: 78.5,
        target: 70,
        trend: 'up',
        history: Array.from({ length: 24 }, (_, i) => ({
          timestamp: Date.now() - (23 - i) * 60 * 60 * 1000,
          value: 70 + Math.random() * 15 + i * 0.3,
        })),
        distribution: [
          { range: '90-100', count: 15, percentage: 12.5 },
          { range: '80-90', count: 35, percentage: 29.2 },
          { range: '70-80', count: 40, percentage: 33.3 },
          { range: '60-70', count: 20, percentage: 16.7 },
          { range: '0-60', count: 10, percentage: 8.3 },
        ],
      },
      faithfulness: {
        current: 92.3,
        target: 90,
        trend: 'stable',
        history: Array.from({ length: 24 }, (_, i) => ({
          timestamp: Date.now() - (23 - i) * 60 * 60 * 1000,
          value: 88 + Math.random() * 8 + Math.sin(i * 0.5) * 2,
        })),
        distribution: [
          { range: '95-100', count: 25, percentage: 20.8 },
          { range: '90-95', count: 45, percentage: 37.5 },
          { range: '85-90', count: 30, percentage: 25.0 },
          { range: '80-85', count: 15, percentage: 12.5 },
          { range: '0-80', count: 5, percentage: 4.2 },
        ],
      },
      contextualRelevancy: {
        current: 85.2,
        target: 70,
        trend: 'up',
        history: Array.from({ length: 24 }, (_, i) => ({
          timestamp: Date.now() - (23 - i) * 60 * 60 * 1000,
          value: 75 + Math.random() * 20 + i * 0.4,
        })),
        distribution: [
          { range: '90-100', count: 30, percentage: 25.0 },
          { range: '80-90', count: 40, percentage: 33.3 },
          { range: '70-80', count: 25, percentage: 20.8 },
          { range: '60-70', count: 20, percentage: 16.7 },
          { range: '0-60', count: 5, percentage: 4.2 },
        ],
      },
    }),
    []
  );

  const performanceMetrics = useMemo(
    (): PerformanceMetrics => ({
      latency: {
        current: 1250,
        target: 2000,
        p50: 980,
        p95: 2100,
        p99: 3500,
        trend: 'improving',
      },
      throughput: {
        current: 45,
        target: 30,
        peak: 78,
        average: 42,
      },
      errorRate: {
        current: 2.3,
        target: 5,
        errors: [
          { type: 'Timeout', count: 15, percentage: 35.7 },
          { type: 'Validation', count: 12, percentage: 28.6 },
          { type: 'Processing', count: 10, percentage: 23.8 },
          { type: 'Network', count: 5, percentage: 11.9 },
        ],
      },
      resourceUsage: {
        cpu: 65,
        memory: 78,
        gpu: 45,
      },
    }),
    []
  );

  const qualityMetrics = useMemo(
    (): QualityMetrics => ({
      hallucinationScore: {
        current: 8.2,
        target: 10,
        trend: 'improving',
      },
      factualAccuracy: {
        current: 91.5,
        target: 85,
        trend: 'stable',
      },
      coherenceScore: {
        current: 88.7,
        target: 80,
        trend: 'improving',
      },
    }),
    []
  );

  const benchmarks = useMemo(
    (): BenchmarkData[] => [
      {
        name: 'Answer Relevancy',
        score: 78.5,
        rank: 15,
        total: 100,
        percentile: 85,
        category: 'rag_triad',
      },
      {
        name: 'Faithfulness',
        score: 92.3,
        rank: 8,
        total: 100,
        percentile: 92,
        category: 'rag_triad',
      },
      {
        name: 'Contextual Relevancy',
        score: 85.2,
        rank: 12,
        total: 100,
        percentile: 88,
        category: 'rag_triad',
      },
      {
        name: 'Latency',
        score: 88.0,
        rank: 20,
        total: 100,
        percentile: 80,
        category: 'performance',
      },
      {
        name: 'Throughput',
        score: 92.5,
        rank: 10,
        total: 100,
        percentile: 90,
        category: 'performance',
      },
      {
        name: 'Overall Quality',
        score: 87.1,
        rank: 18,
        total: 100,
        percentile: 82,
        category: 'overall',
      },
    ],
    []
  );

  // Generate alerts based on metrics
  React.useEffect(() => {
    const newAlerts: Alert[] = [];

    // Check RAG Triad metrics
    if (
      ragTriadMetrics.answerRelevancy.current <
      ragTriadMetrics.answerRelevancy.target
    ) {
      newAlerts.push({
        id: 'answer-relevancy-low',
        type: 'warning',
        title: 'Answer Relevancy Below Target',
        message: `Current score (${ragTriadMetrics.answerRelevancy.current}%) is below target (${ragTriadMetrics.answerRelevancy.target}%)`,
        metric: 'answerRelevancy',
        currentValue: ragTriadMetrics.answerRelevancy.current,
        targetValue: ragTriadMetrics.answerRelevancy.target,
        timestamp: Date.now(),
        acknowledged: false,
      });
    }

    if (
      performanceMetrics.latency.current > performanceMetrics.latency.target
    ) {
      newAlerts.push({
        id: 'latency-high',
        type: 'error',
        title: 'High Latency Detected',
        message: `Current latency (${performanceMetrics.latency.current}ms) exceeds target (${performanceMetrics.latency.target}ms)`,
        metric: 'latency',
        currentValue: performanceMetrics.latency.current,
        targetValue: performanceMetrics.latency.target,
        timestamp: Date.now(),
        acknowledged: false,
      });
    }

    if (
      qualityMetrics.hallucinationScore.current >
      qualityMetrics.hallucinationScore.target
    ) {
      newAlerts.push({
        id: 'hallucination-high',
        type: 'warning',
        title: 'Elevated Hallucination Score',
        message: `Hallucination score (${qualityMetrics.hallucinationScore.current}%) above acceptable threshold (${qualityMetrics.hallucinationScore.target}%)`,
        metric: 'hallucinationScore',
        currentValue: qualityMetrics.hallucinationScore.current,
        targetValue: qualityMetrics.hallucinationScore.target,
        timestamp: Date.now(),
        acknowledged: false,
      });
    }

    setAlerts(newAlerts);
  }, [ragTriadMetrics, performanceMetrics, qualityMetrics]);

  // Refresh data
  const refreshData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      // In real implementation, this would fetch fresh data from API
      await new Promise((resolve) => setTimeout(resolve, 1000));
    } catch (error) {
      console.error('Error refreshing dashboard data:', error);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  // Auto-refresh
  React.useEffect(() => {
    const interval = setInterval(refreshData, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshData, refreshInterval]);

  // Get metric status color
  const getMetricStatus = (current: number, target: number) => {
    if (current >= target) return 'text-green-600 bg-green-50';
    if (current >= target * 0.9) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  // Get trend icon
  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'up':
      case 'improving':
        return TrendingUpIcon;
      case 'down':
      case 'degrading':
        return TrendingDownIcon;
      default:
        return ChartBarIcon;
    }
  };

  // Get trend color
  const getTrendColor = (trend: string) => {
    switch (trend) {
      case 'up':
      case 'improving':
        return 'text-green-600';
      case 'down':
      case 'degrading':
        return 'text-red-600';
      default:
        return 'text-foreground';
    }
  };

  // Get alert icon
  const getAlertIcon = (type: Alert['type']) => {
    switch (type) {
      case 'error':
        return ExclamationTriangleIcon;
      case 'warning':
        return ExclamationTriangleIcon;
      default:
        return InformationCircleIcon;
    }
  };

  const getAlertColor = (type: Alert['type']) => {
    switch (type) {
      case 'error':
        return 'border-red-200 bg-red-50';
      case 'warning':
        return 'border-yellow-200 bg-yellow-50';
      default:
        return 'border-blue-200 bg-blue-50';
    }
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center">
              <BeakerIcon className="h-5 w-5 mr-2" />
              Query Performance Evaluation Dashboard
            </div>
            <div className="flex items-center space-x-2">
              <Select
                value={currentTimeRange}
                onValueChange={(value) =>
                  setCurrentTimeRange(value as typeof currentTimeRange)
                }
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1h">Last hour</SelectItem>
                  <SelectItem value="24h">Last 24h</SelectItem>
                  <SelectItem value="7d">Last 7 days</SelectItem>
                  <SelectItem value="30d">Last 30 days</SelectItem>
                  <SelectItem value="90d">Last 90 days</SelectItem>
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="sm"
                onClick={refreshData}
                disabled={isRefreshing}
              >
                <ArrowPathIcon
                  className={cn('h-4 w-4', isRefreshing && 'animate-spin')}
                />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowFilters(!showFilters)}
              >
                <FunnelIcon className="h-4 w-4" />
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
      </Card>

      {/* Alerts */}
      {alerts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <ExclamationTriangleIcon className="h-5 w-5 mr-2 text-yellow-600" />
              Active Alerts ({alerts.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {alerts.slice(0, 3).map((alert) => {
                const AlertIcon = getAlertIcon(alert.type);
                return (
                  <div
                    key={alert.id}
                    className={cn(
                      'flex items-start space-x-3 p-3 rounded-lg border',
                      getAlertColor(alert.type)
                    )}
                  >
                    <AlertIcon className="h-5 w-5 mt-0.5" />
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <h4 className="font-medium text-foreground">
                          {alert.title}
                        </h4>
                        <span className="text-xs text-muted-foreground">
                          {new Date(alert.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-sm text-foreground">{alert.message}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        setAlerts((prev) =>
                          prev.map((a) =>
                            a.id === alert.id ? { ...a, acknowledged: true } : a
                          )
                        )
                      }
                    >
                      Dismiss
                    </Button>
                  </div>
                );
              })}
            </div>
            {alerts.length > 3 && (
              <div className="text-center pt-2">
                <Button variant="outline" size="sm">
                  View all {alerts.length} alerts
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* RAG Triad Metrics Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center">
                <StarIcon className="h-4 w-4 mr-2" />
                Answer Relevancy
              </div>
              <div className="flex items-center space-x-1">
                {React.createElement(
                  getTrendIcon(ragTriadMetrics.answerRelevancy.trend),
                  {
                    className: cn(
                      'h-4 w-4',
                      getTrendColor(ragTriadMetrics.answerRelevancy.trend)
                    ),
                  }
                )}
                <span
                  className={cn(
                    'text-sm font-medium',
                    getMetricStatus(
                      ragTriadMetrics.answerRelevancy.current,
                      ragTriadMetrics.answerRelevancy.target
                    )
                  )}
                >
                  {ragTriadMetrics.answerRelevancy.current}%
                </span>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-foreground">
                  Target: {ragTriadMetrics.answerRelevancy.target}%
                </span>
                <span className="text-sm text-foreground">
                  Current: {ragTriadMetrics.answerRelevancy.current}%
                </span>
              </div>
              <Progress
                value={ragTriadMetrics.answerRelevancy.current}
                className="h-2"
              />
              <div className="space-y-1">
                {ragTriadMetrics.answerRelevancy.distribution
                  .slice(0, 3)
                  .map((item, index) => (
                    <div key={index} className="flex justify-between text-sm">
                      <span className="text-foreground">{item.range}%</span>
                      <span className="font-medium">{item.count} queries</span>
                    </div>
                  ))}
              </div>
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() =>
                  onMetricClick?.(
                    'answerRelevancy',
                    ragTriadMetrics.answerRelevancy
                  )
                }
              >
                View Details
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center">
                <CheckCircleIcon className="h-4 w-4 mr-2" />
                Faithfulness
              </div>
              <div className="flex items-center space-x-1">
                {React.createElement(
                  getTrendIcon(ragTriadMetrics.faithfulness.trend),
                  {
                    className: cn(
                      'h-4 w-4',
                      getTrendColor(ragTriadMetrics.faithfulness.trend)
                    ),
                  }
                )}
                <span
                  className={cn(
                    'text-sm font-medium',
                    getMetricStatus(
                      ragTriadMetrics.faithfulness.current,
                      ragTriadMetrics.faithfulness.target
                    )
                  )}
                >
                  {ragTriadMetrics.faithfulness.current}%
                </span>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-foreground">
                  Target: {ragTriadMetrics.faithfulness.target}%
                </span>
                <span className="text-sm text-foreground">
                  Current: {ragTriadMetrics.faithfulness.current}%
                </span>
              </div>
              <Progress
                value={ragTriadMetrics.faithfulness.current}
                className="h-2"
              />
              <div className="space-y-1">
                {ragTriadMetrics.faithfulness.distribution
                  .slice(0, 3)
                  .map((item, index) => (
                    <div key={index} className="flex justify-between text-sm">
                      <span className="text-foreground">{item.range}%</span>
                      <span className="font-medium">{item.count} queries</span>
                    </div>
                  ))}
              </div>
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() =>
                  onMetricClick?.('faithfulness', ragTriadMetrics.faithfulness)
                }
              >
                View Details
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center">
                <DocumentTextIcon className="h-4 w-4 mr-2" />
                Contextual Relevancy
              </div>
              <div className="flex items-center space-x-1">
                {React.createElement(
                  getTrendIcon(ragTriadMetrics.contextualRelevancy.trend),
                  {
                    className: cn(
                      'h-4 w-4',
                      getTrendColor(ragTriadMetrics.contextualRelevancy.trend)
                    ),
                  }
                )}
                <span
                  className={cn(
                    'text-sm font-medium',
                    getMetricStatus(
                      ragTriadMetrics.contextualRelevancy.current,
                      ragTriadMetrics.contextualRelevancy.target
                    )
                  )}
                >
                  {ragTriadMetrics.contextualRelevancy.current}%
                </span>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-foreground">
                  Target: {ragTriadMetrics.contextualRelevancy.target}%
                </span>
                <span className="text-sm text-foreground">
                  Current: {ragTriadMetrics.contextualRelevancy.current}%
                </span>
              </div>
              <Progress
                value={ragTriadMetrics.contextualRelevancy.current}
                className="h-2"
              />
              <div className="space-y-1">
                {ragTriadMetrics.contextualRelevancy.distribution
                  .slice(0, 3)
                  .map((item, index) => (
                    <div key={index} className="flex justify-between text-sm">
                      <span className="text-foreground">{item.range}%</span>
                      <span className="font-medium">{item.count} queries</span>
                    </div>
                  ))}
              </div>
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() =>
                  onMetricClick?.(
                    'contextualRelevancy',
                    ragTriadMetrics.contextualRelevancy
                  )
                }
              >
                View Details
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Performance Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <ClockIcon className="h-4 w-4 mr-2" />
              Latency Performance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-center">
                <div>
                  <div className="text-lg font-bold">
                    {performanceMetrics.latency.current}ms
                  </div>
                  <div className="text-sm text-muted-foreground">Current</div>
                </div>
                <div>
                  <div
                    className={cn(
                      'text-lg font-bold',
                      getMetricStatus(
                        performanceMetrics.latency.target,
                        performanceMetrics.latency.current
                      )
                    )}
                  >
                    {performanceMetrics.latency.target}ms
                  </div>
                  <div className="text-sm text-muted-foreground">Target</div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>P50:</span>
                  <span className="font-medium">
                    {performanceMetrics.latency.p50}ms
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>P95:</span>
                  <span className="font-medium">
                    {performanceMetrics.latency.p95}ms
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span>P99:</span>
                  <span className="font-medium">
                    {performanceMetrics.latency.p99}ms
                  </span>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                {React.createElement(
                  getTrendIcon(performanceMetrics.latency.trend),
                  {
                    className: cn(
                      'h-4 w-4',
                      getTrendColor(performanceMetrics.latency.trend)
                    ),
                  }
                )}
                <span className="text-sm text-foreground capitalize">
                  {performanceMetrics.latency.trend}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <TrendingUpIcon className="h-4 w-4 mr-2" />
              Throughput & Errors
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-center">
                <div>
                  <div className="text-lg font-bold">
                    {performanceMetrics.throughput.current}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Queries/min
                  </div>
                </div>
                <div>
                  <div
                    className={cn(
                      'text-lg font-bold',
                      getMetricStatus(
                        performanceMetrics.errorRate.target,
                        performanceMetrics.errorRate.current
                      )
                    )}
                  >
                    {performanceMetrics.errorRate.current}%
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Error Rate
                  </div>
                </div>
              </div>

              <div>
                <div className="text-sm font-medium text-foreground mb-2">
                  Peak Throughput: {performanceMetrics.throughput.peak}{' '}
                  queries/min
                </div>
                <div className="text-sm text-foreground mb-3">
                  Average: {performanceMetrics.throughput.average} queries/min
                </div>
              </div>

              <div>
                <h4 className="text-sm font-medium text-foreground mb-2">
                  Error Breakdown
                </h4>
                <div className="space-y-1">
                  {performanceMetrics.errorRate.errors.map((error, index) => (
                    <div key={index} className="flex justify-between text-sm">
                      <span>{error.type}</span>
                      <span className="font-medium">
                        {error.count} ({error.percentage}%)
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quality Metrics */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <AcademicCapIcon className="h-4 w-4 mr-2" />
            Quality Assessment
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="text-lg font-bold text-red-600">
                {qualityMetrics.hallucinationScore.current}%
              </div>
              <div className="text-sm text-muted-foreground">
                Hallucination Score
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Target: ≤{qualityMetrics.hallucinationScore.target}%
              </div>
              <div className="flex items-center justify-center mt-2 space-x-1">
                {React.createElement(
                  getTrendIcon(qualityMetrics.hallucinationScore.trend),
                  {
                    className: cn(
                      'h-3 w-3',
                      getTrendColor(qualityMetrics.hallucinationScore.trend)
                    ),
                  }
                )}
              </div>
            </div>

            <div className="text-center">
              <div className="text-lg font-bold text-green-600">
                {qualityMetrics.factualAccuracy.current}%
              </div>
              <div className="text-sm text-muted-foreground">
                Factual Accuracy
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Target: ≥{qualityMetrics.factualAccuracy.target}%
              </div>
              <div className="flex items-center justify-center mt-2 space-x-1">
                {React.createElement(
                  getTrendIcon(qualityMetrics.factualAccuracy.trend),
                  {
                    className: cn(
                      'h-3 w-3',
                      getTrendColor(qualityMetrics.factualAccuracy.trend)
                    ),
                  }
                )}
              </div>
            </div>

            <div className="text-center">
              <div className="text-lg font-bold text-blue-600">
                {qualityMetrics.coherenceScore.current}%
              </div>
              <div className="text-sm text-muted-foreground">
                Coherence Score
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Target: ≥{qualityMetrics.coherenceScore.target}%
              </div>
              <div className="flex items-center justify-center mt-2 space-x-1">
                {React.createElement(
                  getTrendIcon(qualityMetrics.coherenceScore.trend),
                  {
                    className: cn(
                      'h-3 w-3',
                      getTrendColor(qualityMetrics.coherenceScore.trend)
                    ),
                  }
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Benchmarks */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <ChartBarIcon className="h-4 w-4 mr-2" />
            Performance Benchmarks
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {benchmarks.map((benchmark) => (
              <div
                key={benchmark.name}
                className="flex items-center justify-between p-3 border rounded-lg"
              >
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-medium">{benchmark.name}</span>
                    <Badge variant="outline" className="capitalize">
                      {benchmark.category}
                    </Badge>
                  </div>
                  <div className="text-sm text-muted-foreground mt-1">
                    Rank #{benchmark.rank} of {benchmark.total} (Percentile:{' '}
                    {benchmark.percentile}%)
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold">{benchmark.score}%</div>
                  <Progress value={benchmark.score} className="w-24 h-2 mt-1" />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Resource Usage */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <EyeIcon className="h-4 w-4 mr-2" />
            Resource Usage
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium text-foreground">
                  CPU Usage
                </span>
                <span className="text-sm font-bold">
                  {performanceMetrics.resourceUsage.cpu}%
                </span>
              </div>
              <Progress
                value={performanceMetrics.resourceUsage.cpu}
                className="h-2"
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium text-foreground">
                  Memory Usage
                </span>
                <span className="text-sm font-bold">
                  {performanceMetrics.resourceUsage.memory}%
                </span>
              </div>
              <Progress
                value={performanceMetrics.resourceUsage.memory}
                className="h-2"
              />
            </div>

            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm font-medium text-foreground">
                  GPU Usage
                </span>
                <span className="text-sm font-bold">
                  {performanceMetrics.resourceUsage.gpu}%
                </span>
              </div>
              <Progress
                value={performanceMetrics.resourceUsage.gpu}
                className="h-2"
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default EvaluationDashboard;
