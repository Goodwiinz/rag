/**
 * PerformanceMetricsDashboard - Comprehensive performance monitoring dashboard
 * Displays latency, throughput, error rates, and resource utilization metrics
 */

import React, { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { useMonitoringStore } from '@/stores/monitoringStore';
import MetricCard from './MetricCard';
import {
  PerformanceMetrics,
  LatencyMetrics,
  ThroughputMetrics,
  ErrorRateMetrics,
  ResourceMetrics,
  TimeRangePreset,
} from '@/types/monitoring';
import {
  ClockIcon,
  ChartBarIcon,
  ServerIcon,
  ExclamationTriangleIcon,
  CpuChipIcon,
  CircleStackIcon,
  SignalIcon,
  ArrowPathIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
} from '@heroicons/react/24/outline';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

interface PerformanceMetricsDashboardProps {
  className?: string;
  timeRange?: TimeRangePreset;
  showDetails?: boolean;
  refreshInterval?: number;
  onTimeRangeChange?: (range: TimeRangePreset) => void;
}

const PerformanceMetricsDashboard: React.FC<
  PerformanceMetricsDashboardProps
> = ({
  className,
  timeRange = '24h',
  showDetails = true,
  refreshInterval = 30000,
  onTimeRangeChange,
}) => {
  // Store hooks
  const performanceMetrics = useMonitoringStore(
    (state) => state.performanceMetrics
  );
  const performanceLoading = useMonitoringStore(
    (state) => state.performanceLoading
  );
  const performanceTimeRange = useMonitoringStore(
    (state) => state.performanceTimeRange
  );
  const setTimeRange = useMonitoringStore((state) => state.setTimeRange);

  // Local state
  const [selectedTimeRange, setSelectedTimeRange] =
    useState<TimeRangePreset>(timeRange);
  const [selectedMetric, setSelectedMetric] = useState('latency');

  // Mock performance data
  const mockPerformanceData: PerformanceMetrics = useMemo(
    () => ({
      latency: {
        average_ms: 245,
        p50_ms: 180,
        p90_ms: 420,
        p95_ms: 680,
        p99_ms: 1200,
        max_ms: 2500,
        trend: {
          direction: 'stable',
          percentage: 2.5,
          period: '24h',
          is_significant: false,
        },
      },
      throughput: {
        requests_per_second: 1250,
        queries_per_minute: 45000,
        peak_throughput: 2100,
        trend: {
          direction: 'up',
          percentage: 8.3,
          period: '24h',
          is_significant: true,
        },
      },
      error_rates: {
        total_errors: 47,
        error_rate: 0.38,
        errors_by_type: {
          timeout: 15,
          connection_failed: 12,
          rate_limit: 8,
          server_error: 7,
          validation_error: 5,
        },
        errors_by_service: {
          api_gateway: 18,
          search_engine: 12,
          document_processor: 10,
          vector_database: 7,
        },
        critical_errors: 3,
        trend: {
          direction: 'down',
          percentage: -15.2,
          period: '24h',
          is_significant: true,
        },
      },
      resource_utilization: {
        cpu: {
          usage_percentage: 68,
          cores_available: 16,
          load_average: [2.1, 2.3, 2.0],
        },
        memory: {
          used_percentage: 72,
          used_gb: 11.5,
          total_gb: 16,
          available_gb: 4.5,
        },
        disk: {
          used_percentage: 45,
          used_gb: 225,
          total_gb: 500,
          read_iops: 1250,
          write_iops: 890,
        },
        network: {
          incoming_mbps: 45,
          outgoing_mbps: 32,
        },
      },
      cache_performance: {
        hit_rate_percentage: 84,
        miss_rate_percentage: 16,
        eviction_rate: 2.1,
        size_mb: 1024,
        max_size_mb: 2048,
      },
      database_performance: {
        connection_pool: {
          active_connections: 24,
          idle_connections: 56,
          max_connections: 100,
        },
        query_performance: {
          average_query_time_ms: 125,
          slow_queries_count: 8,
          total_queries_count: 12500,
        },
        replication_lag_ms: 45,
      },
      timestamp: new Date().toISOString(),
    }),
    []
  );

  // Mock time series data
  const mockTimeSeriesData = useMemo(() => {
    return Array.from({ length: 24 }, (_, i) => ({
      time: new Date(Date.now() - (23 - i) * 60 * 60 * 1000).toLocaleTimeString(
        [],
        { hour: '2-digit', minute: '2-digit' }
      ),
      latency_p95: 600 + Math.random() * 200,
      latency_p99: 1000 + Math.random() * 400,
      throughput_rps: 1000 + Math.random() * 500,
      error_rate: Math.random() * 2,
      cpu_usage: 50 + Math.random() * 30,
      memory_usage: 60 + Math.random() * 20,
    }));
  }, []);

  // Mock latency distribution data
  const latencyDistribution = useMemo(
    () => [
      { range: '0-100ms', count: 1250, percentage: 35.2 },
      { range: '100-250ms', count: 980, percentage: 27.6 },
      { range: '250-500ms', count: 765, percentage: 21.5 },
      { range: '500ms-1s', count: 420, percentage: 11.8 },
      { range: '1s-2s', count: 95, percentage: 2.7 },
      { range: '2s+', count: 40, percentage: 1.2 },
    ],
    []
  );

  // Error type distribution for pie chart
  const errorTypeData = useMemo(() => {
    const errors = mockPerformanceData.error_rates.errors_by_type;
    return Object.entries(errors).map(([type, count]) => ({
      name: type.replace(/_/g, ' '),
      value: count,
    }));
  }, [mockPerformanceData]);

  const COLORS = ['#ef4444', '#f59e0b', '#eab308', '#84cc16', '#06b6d4'];

  // Use mock data if store data is not available
  const metrics = performanceMetrics || mockPerformanceData;

  // Handle time range change
  useEffect(() => {
    setSelectedTimeRange(timeRange);
  }, [timeRange]);

  const handleTimeRangeChange = (newRange: TimeRangePreset) => {
    setSelectedTimeRange(newRange);
    setTimeRange({ start: '', end: '', preset: newRange });
    onTimeRangeChange?.(newRange);
  };

  // Format time duration
  const formatDuration = (ms: number): string => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  // Get status based on thresholds
  const getLatencyStatus = (
    latency: number
  ): 'success' | 'warning' | 'error' => {
    if (latency < 500) return 'success';
    if (latency < 1000) return 'warning';
    return 'error';
  };

  const getErrorRateStatus = (
    rate: number
  ): 'success' | 'warning' | 'error' => {
    if (rate < 1) return 'success';
    if (rate < 5) return 'warning';
    return 'error';
  };

  const getResourceStatus = (
    usage: number
  ): 'success' | 'warning' | 'error' => {
    if (usage < 70) return 'success';
    if (usage < 90) return 'warning';
    return 'error';
  };

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground">
            Performance Metrics
          </h2>
          <p className="text-foreground mt-1">
            System performance and resource utilization monitoring
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <Select
            value={selectedTimeRange}
            onValueChange={handleTimeRangeChange}
          >
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1h">Last Hour</SelectItem>
              <SelectItem value="6h">Last 6 Hours</SelectItem>
              <SelectItem value="24h">Last 24 Hours</SelectItem>
              <SelectItem value="7d">Last 7 Days</SelectItem>
              <SelectItem value="30d">Last 30 Days</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm">
            <ArrowPathIcon className="h-4 w-4 mr-1" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Key Performance Indicators */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="P95 Latency"
          value={metrics.latency.p95_ms}
          unit="ms"
          status={getLatencyStatus(metrics.latency.p95_ms)}
          description="95th percentile response time"
          icon={<ClockIcon className="h-6 w-6" />}
          format="duration"
          threshold={{ value: 1000, type: 'lte' }}
          trend={metrics.latency.trend}
        />
        <MetricCard
          title="Throughput"
          value={metrics.throughput.requests_per_second}
          unit="req/s"
          status="success"
          description="Requests per second"
          icon={<ChartBarIcon className="h-6 w-6" />}
          trend={metrics.throughput.trend}
        />
        <MetricCard
          title="Error Rate"
          value={metrics.error_rates.error_rate}
          unit="%"
          status={getErrorRateStatus(metrics.error_rates.error_rate)}
          description="Percentage of failed requests"
          icon={<ExclamationTriangleIcon className="h-6 w-6" />}
          format="percentage"
          threshold={{ value: 5, type: 'lte' }}
          trend={metrics.error_rates.trend}
        />
        <MetricCard
          title="CPU Usage"
          value={metrics.resource_utilization.cpu.usage_percentage}
          unit="%"
          status={getResourceStatus(
            metrics.resource_utilization.cpu.usage_percentage
          )}
          description="Current CPU utilization"
          icon={<CpuChipIcon className="h-6 w-6" />}
          threshold={{ value: 80, type: 'lte' }}
        />
      </div>

      {/* Detailed Metrics Tabs */}
      <Tabs defaultValue="latency" className="space-y-6">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="latency">Latency</TabsTrigger>
          <TabsTrigger value="throughput">Throughput</TabsTrigger>
          <TabsTrigger value="errors">Errors</TabsTrigger>
          <TabsTrigger value="resources">Resources</TabsTrigger>
          <TabsTrigger value="database">Database</TabsTrigger>
        </TabsList>

        {/* Latency Tab */}
        <TabsContent value="latency" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Latency Time Series */}
            <Card>
              <CardHeader>
                <CardTitle>Latency Trends</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={mockTimeSeriesData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" />
                      <YAxis />
                      <Tooltip />
                      <Line
                        type="monotone"
                        dataKey="latency_p95"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        name="P95 Latency"
                      />
                      <Line
                        type="monotone"
                        dataKey="latency_p99"
                        stroke="#ef4444"
                        strokeWidth={2}
                        name="P99 Latency"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Latency Distribution */}
            <Card>
              <CardHeader>
                <CardTitle>Latency Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={latencyDistribution} layout="horizontal">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis dataKey="range" type="category" />
                      <Tooltip />
                      <Bar dataKey="count" fill="#3b82f6" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Latency Percentiles */}
          <Card>
            <CardHeader>
              <CardTitle>Latency Percentiles</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <MetricCard
                  title="Average"
                  value={metrics.latency.average_ms}
                  unit="ms"
                  format="duration"
                  size="sm"
                  variant="compact"
                />
                <MetricCard
                  title="P50"
                  value={metrics.latency.p50_ms}
                  unit="ms"
                  format="duration"
                  size="sm"
                  variant="compact"
                />
                <MetricCard
                  title="P90"
                  value={metrics.latency.p90_ms}
                  unit="ms"
                  format="duration"
                  size="sm"
                  variant="compact"
                />
                <MetricCard
                  title="P95"
                  value={metrics.latency.p95_ms}
                  unit="ms"
                  format="duration"
                  size="sm"
                  variant="compact"
                />
                <MetricCard
                  title="P99"
                  value={metrics.latency.p99_ms}
                  unit="ms"
                  format="duration"
                  size="sm"
                  variant="compact"
                />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Throughput Tab */}
        <TabsContent value="throughput" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Throughput Trends</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={mockTimeSeriesData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" />
                      <YAxis />
                      <Tooltip />
                      <Area
                        type="monotone"
                        dataKey="throughput_rps"
                        stroke="#10b981"
                        fill="#10b981"
                        fillOpacity={0.3}
                        name="Requests/sec"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Throughput Metrics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 gap-4">
                  <MetricCard
                    title="Requests/Second"
                    value={metrics.throughput.requests_per_second}
                    unit="req/s"
                    icon={<ChartBarIcon className="h-5 w-5" />}
                    size="sm"
                    variant="compact"
                  />
                  <MetricCard
                    title="Queries/Minute"
                    value={metrics.throughput.queries_per_minute}
                    unit="qpm"
                    icon={<ChartBarIcon className="h-5 w-5" />}
                    size="sm"
                    variant="compact"
                  />
                  <MetricCard
                    title="Peak Throughput"
                    value={metrics.throughput.peak_throughput}
                    unit="req/s"
                    icon={<ArrowTrendingUpIcon className="h-5 w-5" />}
                    size="sm"
                    variant="compact"
                  />
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Errors Tab */}
        <TabsContent value="errors" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Error Rate Trends</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={mockTimeSeriesData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" />
                      <YAxis />
                      <Tooltip />
                      <Line
                        type="monotone"
                        dataKey="error_rate"
                        stroke="#ef4444"
                        strokeWidth={2}
                        name="Error Rate (%)"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Error Types</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={errorTypeData}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={({ name, percent }) =>
                          `${name} ${(percent * 100).toFixed(0)}%`
                        }
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                      >
                        {errorTypeData.map((entry, index) => (
                          <Cell
                            key={`cell-${index}`}
                            fill={COLORS[index % COLORS.length]}
                          />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Error Breakdown */}
          <Card>
            <CardHeader>
              <CardTitle>Error Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-semibold mb-3">By Type</h4>
                  <div className="space-y-2">
                    {Object.entries(metrics.error_rates.errors_by_type).map(
                      ([type, count]) => (
                        <div key={type} className="flex justify-between">
                          <span className="capitalize">
                            {type.replace(/_/g, ' ')}
                          </span>
                          <span className="font-medium">{count}</span>
                        </div>
                      )
                    )}
                  </div>
                </div>
                <div>
                  <h4 className="font-semibold mb-3">By Service</h4>
                  <div className="space-y-2">
                    {Object.entries(metrics.error_rates.errors_by_service).map(
                      ([service, count]) => (
                        <div key={service} className="flex justify-between">
                          <span className="capitalize">
                            {service.replace(/_/g, ' ')}
                          </span>
                          <span className="font-medium">{count}</span>
                        </div>
                      )
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Resources Tab */}
        <TabsContent value="resources" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard
              title="CPU Usage"
              value={metrics.resource_utilization.cpu.usage_percentage}
              unit="%"
              status={getResourceStatus(
                metrics.resource_utilization.cpu.usage_percentage
              )}
              icon={<CpuChipIcon className="h-6 w-6" />}
              threshold={{ value: 80, type: 'lte' }}
            />
            <MetricCard
              title="Memory Usage"
              value={metrics.resource_utilization.memory.used_percentage}
              unit="%"
              status={getResourceStatus(
                metrics.resource_utilization.memory.used_percentage
              )}
              icon={<CircleStackIcon className="h-6 w-6" />}
              threshold={{ value: 85, type: 'lte' }}
            />
            <MetricCard
              title="Disk Usage"
              value={metrics.resource_utilization.disk.used_percentage}
              unit="%"
              status={getResourceStatus(
                metrics.resource_utilization.disk.used_percentage
              )}
              icon={<ServerIcon className="h-6 w-6" />}
            />
            <MetricCard
              title="Network In"
              value={metrics.resource_utilization.network.incoming_mbps}
              unit="Mbps"
              icon={<SignalIcon className="h-6 w-6" />}
            />
          </div>

          {/* Resource Trends */}
          <Card>
            <CardHeader>
              <CardTitle>Resource Utilization Trends</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={mockTimeSeriesData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" />
                    <YAxis />
                    <Tooltip />
                    <Area
                      type="monotone"
                      dataKey="cpu_usage"
                      stackId="1"
                      stroke="#3b82f6"
                      fill="#3b82f6"
                      fillOpacity={0.6}
                      name="CPU %"
                    />
                    <Area
                      type="monotone"
                      dataKey="memory_usage"
                      stackId="2"
                      stroke="#10b981"
                      fill="#10b981"
                      fillOpacity={0.6}
                      name="Memory %"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Database Tab */}
        <TabsContent value="database" className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Connection Pool</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex justify-between items-center">
                  <span>Active Connections</span>
                  <span className="font-semibold">
                    {
                      metrics.database_performance.connection_pool
                        .active_connections
                    }
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Idle Connections</span>
                  <span className="font-semibold">
                    {
                      metrics.database_performance.connection_pool
                        .idle_connections
                    }
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Max Connections</span>
                  <span className="font-semibold">
                    {
                      metrics.database_performance.connection_pool
                        .max_connections
                    }
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{
                      width: `${(metrics.database_performance.connection_pool.active_connections / metrics.database_performance.connection_pool.max_connections) * 100}%`,
                    }}
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Query Performance</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <MetricCard
                  title="Avg Query Time"
                  value={
                    metrics.database_performance.query_performance
                      .average_query_time_ms
                  }
                  unit="ms"
                  icon={<ClockIcon className="h-5 w-5" />}
                  size="sm"
                  variant="compact"
                />
                <MetricCard
                  title="Slow Queries"
                  value={
                    metrics.database_performance.query_performance
                      .slow_queries_count
                  }
                  icon={<ExclamationTriangleIcon className="h-5 w-5" />}
                  size="sm"
                  variant="compact"
                />
                <MetricCard
                  title="Total Queries"
                  value={
                    metrics.database_performance.query_performance
                      .total_queries_count
                  }
                  icon={<ChartBarIcon className="h-5 w-5" />}
                  size="sm"
                  variant="compact"
                />
              </CardContent>
            </Card>
          </div>

          {metrics.database_performance.replication_lag_ms && (
            <Card>
              <CardHeader>
                <CardTitle>Replication Lag</CardTitle>
              </CardHeader>
              <CardContent>
                <MetricCard
                  title="Current Lag"
                  value={metrics.database_performance.replication_lag_ms}
                  unit="ms"
                  icon={<ClockIcon className="h-6 w-6" />}
                  threshold={{ value: 1000, type: 'lte' }}
                />
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default PerformanceMetricsDashboard;
