import React, { useState, useEffect, useRef } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';
import {
  PlayIcon,
  PauseIcon,
  ArrowPathIcon,
  SignalSlashIcon,
  WifiIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { useWebSocket } from '@/hooks/useWebSocket';

interface RealTimeMetricsProps {
  className?: string;
  maxDataPoints?: number;
  updateInterval?: number;
}

interface MetricData {
  timestamp: number;
  answerRelevancy: number;
  faithfulness: number;
  contextualRelevancy: number;
  latency: number;
  throughput: number;
  errorRate: number;
  activeUsers: number;
  cpuUsage: number;
  memoryUsage: number;
}

interface WebSocketMetricsUpdate {
  type: 'metrics_update';
  payload: {
    timestamp: number;
    metrics: {
      rag_triad: {
        answer_relevancy: number;
        faithfulness: number;
        contextual_relevancy: number;
      };
      performance: {
        latency_ms: number;
        throughput_qpm: number;
        error_rate: number;
        cpu_usage: number;
        memory_usage: number;
      };
      system: {
        active_users: number;
      };
    };
  };
}

export const RealTimeMetrics: React.FC<RealTimeMetricsProps> = ({
  className,
  maxDataPoints = 50,
  updateInterval = 5000,
}) => {
  const { isConnected, manager } = useWebSocket();
  const [isLive, setIsLive] = useState(true);
  const [metrics, setMetrics] = useState<MetricData[]>([]);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [connectionErrors, setConnectionErrors] = useState<string[]>([]);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize with some mock data
  useEffect(() => {
    const initialData: MetricData[] = Array.from({ length: 20 }, (_, i) => ({
      timestamp: Date.now() - (19 - i) * updateInterval,
      answerRelevancy: 70 + Math.random() * 20 + Math.sin(i * 0.2) * 5,
      faithfulness: 85 + Math.random() * 10 + Math.cos(i * 0.3) * 3,
      contextualRelevancy: 75 + Math.random() * 15 + Math.sin(i * 0.25) * 4,
      latency: 800 + Math.random() * 400 + Math.sin(i * 0.4) * 100,
      throughput: 30 + Math.random() * 20 + Math.cos(i * 0.2) * 5,
      errorRate: 1 + Math.random() * 3,
      activeUsers: 50 + Math.floor(Math.random() * 30),
      cpuUsage: 40 + Math.random() * 30,
      memoryUsage: 60 + Math.random() * 25,
    }));
    setMetrics(initialData);
    setLastUpdate(new Date());
  }, [updateInterval]);

  // WebSocket subscription
  useEffect(() => {
    if (!manager) return;

    const handleMetricsUpdate = (data: WebSocketMetricsUpdate) => {
      const newMetric: MetricData = {
        timestamp: data.payload.timestamp,
        answerRelevancy: data.payload.metrics.rag_triad.answer_relevancy,
        faithfulness: data.payload.metrics.rag_triad.faithfulness,
        contextualRelevancy:
          data.payload.metrics.rag_triad.contextual_relevancy,
        latency: data.payload.metrics.performance.latency_ms,
        throughput: data.payload.metrics.performance.throughput_qpm,
        errorRate: data.payload.metrics.performance.error_rate,
        activeUsers: data.payload.metrics.system.active_users,
        cpuUsage: data.payload.metrics.performance.cpu_usage,
        memoryUsage: data.payload.metrics.performance.memory_usage,
      };

      setMetrics((prev) => {
        const updated = [...prev, newMetric];
        return updated.slice(-maxDataPoints);
      });
      setLastUpdate(new Date());
    };

    const handleError = (error: any) => {
      const errorMessage = error?.message || 'Connection error';
      setConnectionErrors((prev) => [...prev.slice(-4), errorMessage]);
    };

    manager.on('metrics_update', handleMetricsUpdate);
    manager.on('error', handleError);

    return () => {
      manager.off('metrics_update', handleMetricsUpdate);
      manager.off('error', handleError);
    };
  }, [manager, maxDataPoints]);

  // Simulate real-time updates when WebSocket is not available
  useEffect(() => {
    if (!isLive || isConnected) return;

    intervalRef.current = setInterval(() => {
      const newMetric: MetricData = {
        timestamp: Date.now(),
        answerRelevancy:
          70 + Math.random() * 20 + Math.sin(Date.now() * 0.0001) * 5,
        faithfulness:
          85 + Math.random() * 10 + Math.cos(Date.now() * 0.00015) * 3,
        contextualRelevancy:
          75 + Math.random() * 15 + Math.sin(Date.now() * 0.00012) * 4,
        latency:
          800 + Math.random() * 400 + Math.sin(Date.now() * 0.0002) * 100,
        throughput: 30 + Math.random() * 20 + Math.cos(Date.now() * 0.0001) * 5,
        errorRate: 1 + Math.random() * 3,
        activeUsers: 50 + Math.floor(Math.random() * 30),
        cpuUsage: 40 + Math.random() * 30,
        memoryUsage: 60 + Math.random() * 25,
      };

      setMetrics((prev) => {
        const updated = [...prev, newMetric];
        return updated.slice(-maxDataPoints);
      });
      setLastUpdate(new Date());
    }, updateInterval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isLive, isConnected, updateInterval, maxDataPoints]);

  const toggleLive = () => {
    setIsLive(!isLive);
  };

  const clearErrors = () => {
    setConnectionErrors([]);
  };

  const getCurrentValues = () => {
    if (metrics.length === 0) return null;
    return metrics[metrics.length - 1];
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const formatChartData = (data: MetricData[]) => {
    return data.map((item) => ({
      time: formatTime(item.timestamp),
      answerRelevancy: Math.round(item.answerRelevancy * 10) / 10,
      faithfulness: Math.round(item.faithfulness * 10) / 10,
      contextualRelevancy: Math.round(item.contextualRelevancy * 10) / 10,
      latency: Math.round(item.latency),
      throughput: Math.round(item.throughput * 10) / 10,
      errorRate: Math.round(item.errorRate * 10) / 10,
      activeUsers: item.activeUsers,
      cpuUsage: Math.round(item.cpuUsage),
      memoryUsage: Math.round(item.memoryUsage),
    }));
  };

  const currentValues = getCurrentValues();

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="flex items-center">
                {isConnected ? (
                  <WifiIcon className="h-5 w-5 text-green-500 mr-2" />
                ) : (
                  <SignalSlashIcon className="h-5 w-5 text-red-500 mr-2" />
                )}
                <span>Real-time Metrics</span>
              </div>
              <Badge variant={isLive ? 'default' : 'secondary'}>
                {isLive ? 'LIVE' : 'PAUSED'}
              </Badge>
              {lastUpdate && (
                <span className="text-sm text-muted-foreground">
                  Last update: {lastUpdate.toLocaleTimeString()}
                </span>
              )}
            </div>
            <div className="flex items-center space-x-2">
              <div className="flex items-center space-x-2">
                <Switch
                  checked={isLive}
                  onCheckedChange={toggleLive}
                  disabled={!isConnected && !isLive}
                />
                <span className="text-sm">Live Updates</span>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setMetrics([])}>
                <ArrowPathIcon className="h-4 w-4" />
              </Button>
            </div>
          </CardTitle>
        </CardHeader>
      </Card>

      {/* Connection Errors */}
      {connectionErrors.length > 0 && (
        <Card className="border-red-200 bg-red-50">
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-red-700">
              <div className="flex items-center">
                <ExclamationTriangleIcon className="h-5 w-5 mr-2" />
                Connection Issues
              </div>
              <Button variant="ghost" size="sm" onClick={clearErrors}>
                Clear
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {connectionErrors.map((error, index) => (
                <div key={index} className="text-sm text-red-600">
                  {error}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Current Values */}
      {currentValues && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="text-2xl font-bold text-blue-600">
                {currentValues.answerRelevancy.toFixed(1)}%
              </div>
              <div className="text-sm text-foreground">Answer Relevancy</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-2xl font-bold text-green-600">
                {currentValues.faithfulness.toFixed(1)}%
              </div>
              <div className="text-sm text-foreground">Faithfulness</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-2xl font-bold text-[var(--nous-fg-accent)]">
                {currentValues.contextualRelevancy.toFixed(1)}%
              </div>
              <div className="text-sm text-foreground">
                Contextual Relevancy
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-2xl font-bold text-orange-600">
                {currentValues.latency.toFixed(0)}ms
              </div>
              <div className="text-sm text-foreground">Latency</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-2xl font-bold text-cyan-600">
                {currentValues.throughput.toFixed(1)}
              </div>
              <div className="text-sm text-foreground">QPM</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-2xl font-bold text-red-600">
                {currentValues.errorRate.toFixed(1)}%
              </div>
              <div className="text-sm text-foreground">Error Rate</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* RAG Triad Metrics Chart */}
      <Card>
        <CardHeader>
          <CardTitle>RAG Triad Metrics - Real-time</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={formatChartData(metrics)}
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="time"
                  tick={{ fontSize: 12 }}
                  interval="preserveStartEnd"
                />
                <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="answerRelevancy"
                  stroke="#8884d8"
                  strokeWidth={2}
                  dot={false}
                  name="Answer Relevancy"
                />
                <Line
                  type="monotone"
                  dataKey="faithfulness"
                  stroke="#82ca9d"
                  strokeWidth={2}
                  dot={false}
                  name="Faithfulness"
                />
                <Line
                  type="monotone"
                  dataKey="contextualRelevancy"
                  stroke="#ffc658"
                  strokeWidth={2}
                  dot={false}
                  name="Contextual Relevancy"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Performance Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Latency & Throughput</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={formatChartData(metrics)}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 12 }}
                    interval="preserveStartEnd"
                  />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="latency"
                    stackId="1"
                    stroke="#ff7300"
                    fill="#ff7300"
                    fillOpacity={0.3}
                    name="Latency (ms)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>System Resources</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={formatChartData(metrics)}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 12 }}
                    interval="preserveStartEnd"
                  />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="cpuUsage"
                    stackId="1"
                    stroke="#8884d8"
                    fill="#8884d8"
                    fillOpacity={0.3}
                    name="CPU (%)"
                  />
                  <Area
                    type="monotone"
                    dataKey="memoryUsage"
                    stackId="1"
                    stroke="#82ca9d"
                    fill="#82ca9d"
                    fillOpacity={0.3}
                    name="Memory (%)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* System Status */}
      <Card>
        <CardHeader>
          <CardTitle>System Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {currentValues && (
              <>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600">
                    {currentValues.activeUsers}
                  </div>
                  <div className="text-sm text-foreground">Active Users</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {isConnected ? 'Connected' : 'Disconnected'}
                  </div>
                  <div className="text-sm text-foreground">
                    WebSocket Status
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-[var(--nous-fg-accent)]">
                    {metrics.length}
                  </div>
                  <div className="text-sm text-foreground">Data Points</div>
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default RealTimeMetrics;
