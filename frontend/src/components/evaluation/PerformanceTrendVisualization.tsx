import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  ComposedChart,
  Scatter,
  ScatterChart,
} from 'recharts';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Clock,
  AlertTriangle,
  CheckCircle,
  BarChart3,
  Download,
  RefreshCw,
  Calendar,
  Target,
  Zap,
  Brain,
  Eye,
  MousePointer,
} from 'lucide-react';

// Types
interface DataPoint {
  timestamp: string;
  date: string;
  value: number;
  target?: number;
  category?: string;
  queryCount?: number;
  latency?: number;
  satisfaction?: number;
}

interface TrendData {
  [key: string]: DataPoint[];
}

interface MetricConfig {
  id: string;
  name: string;
  description: string;
  unit: string;
  target: number;
  color: string;
  areaColor?: string;
  icon: React.ReactNode;
  threshold?: {
    warning: number;
    critical: number;
  };
}

interface Anomaly {
  id: string;
  timestamp: string;
  metric: string;
  value: number;
  expected: number;
  deviation: number;
  severity: 'low' | 'medium' | 'high';
  description: string;
  impact: string;
}

interface Forecast {
  metric: string;
  predictions: DataPoint[];
  confidence: number;
  accuracy: number;
  trend: 'improving' | 'stable' | 'declining';
  nextMilestone: {
    date: string;
    expectedValue: number;
    probability: number;
  };
}

// Mock data generation
const generateMockData = (days: number = 30): TrendData => {
  const data: TrendData = {};
  const metrics = [
    'answerRelevancy',
    'faithfulness',
    'contextualRelevancy',
    'latency',
    'throughput',
    'successRate',
    'userSatisfaction',
    'hallucinationRate',
  ];

  const now = new Date();

  metrics.forEach(metric => {
    const metricData: DataPoint[] = [];
    const baseValue = metric === 'latency' ? 1200 :
                   metric === 'throughput' ? 45 :
                   metric === 'successRate' ? 85 :
                   metric === 'hallucinationRate' ? 15 :
                   metric === 'userSatisfaction' ? 75 : 70;

    for (let i = days; i >= 0; i--) {
      const date = new Date(now);
      date.setDate(date.getDate() - i);

      // Add realistic variations and trends
      const trendFactor = (days - i) / days * 5; // Slight improvement trend
      const randomVariation = (Math.random() - 0.5) * 10;
      const weeklyPattern = Math.sin((days - i) / 7 * Math.PI * 2) * 3;

      let value = baseValue + trendFactor + randomVariation + weeklyPattern;

      // Add some anomalies
      if (Math.random() < 0.05) {
        value += (Math.random() - 0.5) * 30;
      }

      // Clamp values to realistic ranges
      if (metric.includes('Relevancy') || metric === 'faithfulness') {
        value = Math.max(0, Math.min(100, value));
      } else if (metric === 'latency') {
        value = Math.max(100, Math.min(5000, value));
      } else if (metric === 'throughput') {
        value = Math.max(0, Math.min(200, value));
      } else if (metric === 'successRate' || metric === 'userSatisfaction') {
        value = Math.max(0, Math.min(100, value));
      } else if (metric === 'hallucinationRate') {
        value = Math.max(0, Math.min(50, value));
      }

      metricData.push({
        timestamp: date.toISOString(),
        date: date.toLocaleDateString(),
        value: Math.round(value * 100) / 100,
        target: getTargetForMetric(metric),
        category: metric,
        queryCount: Math.floor(Math.random() * 1000) + 100,
        latency: metric === 'latency' ? value : Math.random() * 2000 + 500,
        satisfaction: Math.random() * 30 + 70,
      });
    }

    data[metric] = metricData;
  });

  return data;
};

const getTargetForMetric = (metric: string): number => {
  const targets: { [key: string]: number } = {
    answerRelevancy: 70,
    faithfulness: 90,
    contextualRelevancy: 70,
    latency: 2000,
    throughput: 50,
    successRate: 90,
    userSatisfaction: 80,
    hallucinationRate: 10,
  };
  return targets[metric] || 80;
};

// Metric configurations
const metricConfigs: MetricConfig[] = [
  {
    id: 'answerRelevancy',
    name: 'Answer Relevancy',
    description: 'Relevance of generated answers to user queries',
    unit: '%',
    target: 70,
    color: '#3b82f6',
    areaColor: '#3b82f620',
    icon: <Brain className="h-4 w-4" />,
    threshold: { warning: 60, critical: 50 },
  },
  {
    id: 'faithfulness',
    name: 'Faithfulness',
    description: 'Factual accuracy of generated responses',
    unit: '%',
    target: 90,
    color: '#10b981',
    areaColor: '#10b98120',
    icon: <CheckCircle className="h-4 w-4" />,
    threshold: { warning: 85, critical: 75 },
  },
  {
    id: 'contextualRelevancy',
    name: 'Contextual Relevancy',
    description: 'Relevance of retrieved context',
    unit: '%',
    target: 70,
    color: '#f59e0b',
    areaColor: '#f59e0b20',
    icon: <Eye className="h-4 w-4" />,
    threshold: { warning: 60, critical: 50 },
  },
  {
    id: 'latency',
    name: 'Response Latency',
    description: 'Average response time',
    unit: 'ms',
    target: 2000,
    color: '#ef4444',
    areaColor: '#ef444420',
    icon: <Clock className="h-4 w-4" />,
    threshold: { warning: 3000, critical: 5000 },
  },
  {
    id: 'throughput',
    name: 'Query Throughput',
    description: 'Queries processed per minute',
    unit: 'qpm',
    target: 50,
    color: '#8b5cf6',
    areaColor: '#8b5cf620',
    icon: <Activity className="h-4 w-4" />,
    threshold: { warning: 30, critical: 20 },
  },
  {
    id: 'userSatisfaction',
    name: 'User Satisfaction',
    description: 'User satisfaction scores',
    unit: '%',
    target: 80,
    color: '#ec4899',
    areaColor: '#ec489920',
    icon: <Zap className="h-4 w-4" />,
    threshold: { warning: 70, critical: 60 },
  },
];

const PerformanceTrendVisualization: React.FC<PerformanceTrendVisualizationProps> = ({
  timeRange = '30d',
  data,
  onTimeRangeChange,
  onMetricClick,
  onAnomalyClick,
  className,
}) => {
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>(['answerRelevancy', 'faithfulness', 'contextualRelevancy']);
  const [chartType, setChartType] = useState<'line' | 'area' | 'bar'>('line');
  const [showTargets, setShowTargets] = useState(true);
  const [showForecast, setShowForecast] = useState(false);
  const [comparisonMode, setComparisonMode] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Generate mock data if not provided
  const trendData = useMemo(() => {
    return data || generateMockData(parseInt(timeRange));
  }, [data, timeRange]);

  // Generate anomalies
  const anomalies = useMemo((): Anomaly[] => {
    const anomalies: Anomaly[] = [];
    const now = new Date();

    Object.entries(trendData).forEach(([metric, dataPoints]) => {
      const config = metricConfigs.find(c => c.id === metric);
      if (!config) return;

      dataPoints.forEach((point, index) => {
        if (index === 0) return; // Skip first point

        const prevPoint = dataPoints[index - 1];
        if (!prevPoint) return; // Skip if prevPoint is undefined

        const change = Math.abs(point.value - prevPoint.value);
        const changePercent = (change / prevPoint.value) * 100;

        // Detect significant changes
        if (changePercent > 15 || (config.threshold && point.value > config.threshold.critical)) {
          anomalies.push({
            id: `${metric}-${point.timestamp}`,
            timestamp: point.timestamp,
            metric: config.name,
            value: point.value,
            expected: prevPoint.value,
            deviation: changePercent,
            severity: changePercent > 30 ? 'high' : changePercent > 20 ? 'medium' : 'low',
            description: `${metric === 'latency' ? 'Increased' : 'Changed'} ${config.name} from ${prevPoint.value.toFixed(1)} to ${point.value.toFixed(1)}${config.unit}`,
            impact: changePercent > 25 ? 'High impact on user experience' : 'Moderate impact on performance',
          });
        }
      });
    });

    return anomalies.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }, [trendData]);

  // Generate forecasts
  const forecasts = useMemo((): Forecast[] => {
    if (!showForecast) return [];

    return selectedMetrics.map(metric => {
      const dataPoints = trendData[metric] || [];
      const config = metricConfigs.find(c => c.id === metric);
      if (!config || dataPoints.length < 7) return null;

      // Simple linear regression for forecasting
      const n = Math.min(dataPoints.length, 14);
      const recentData = dataPoints.slice(-n);
      if (recentData.length < 2) return null;
      const avgValue = recentData.reduce((sum, p) => sum + p.value, 0) / n;
      const trend = ((recentData[recentData.length - 1]?.value || 0) - (recentData[0]?.value || 0)) / n;

      const predictions: DataPoint[] = [];
      let lastValue = recentData[recentData.length - 1]?.value || 0;

      for (let i = 1; i <= 7; i++) {
        const futureDate = new Date();
        futureDate.setDate(futureDate.getDate() + i);

        lastValue = lastValue + trend + (Math.random() - 0.5) * 2;

        predictions.push({
          timestamp: futureDate.toISOString(),
          date: futureDate.toLocaleDateString(),
          value: Math.round(lastValue * 100) / 100,
          target: config.target,
          category: metric,
        });
      }

      const trendDirection = trend > 0.5 ? 'improving' : trend < -0.5 ? 'declining' : 'stable';

      return {
        metric,
        predictions,
        confidence: 75 + Math.random() * 15,
        accuracy: 80 + Math.random() * 10,
        trend: trendDirection,
        nextMilestone: {
          date: predictions[predictions.length - 1]?.date || '',
          expectedValue: predictions[predictions.length - 1]?.value || 0,
          probability: 0.7 + Math.random() * 0.2,
        },
      };
    }).filter(Boolean) as Forecast[];
  }, [selectedMetrics, showForecast, trendData]);

  // Prepare chart data
  const chartData = useMemo(() => {
    const allTimestamps = new Set<string>();
    selectedMetrics.forEach(metric => {
      const metricData = trendData[metric];
      if (metricData) {
        metricData.forEach(point => allTimestamps.add(point.date));
      }
    });

    const sortedDates = Array.from(allTimestamps).sort((a, b) =>
      new Date(a).getTime() - new Date(b).getTime()
    );

    return sortedDates.map(date => {
      const point: any = { date };

      selectedMetrics.forEach(metric => {
        const dataPoint = trendData[metric]?.find(p => p.date === date);
        if (dataPoint) {
          point[metric] = dataPoint.value;
          point[`${metric}_target`] = dataPoint.target;
        }
      });

      // Add forecast data if enabled
      if (showForecast) {
        forecasts.forEach(forecast => {
          const forecastPoint = forecast.predictions.find(p => p.date === date);
          if (forecastPoint) {
            point[`${forecast.metric}_forecast`] = forecastPoint.value;
          }
        });
      }

      return point;
    });
  }, [selectedMetrics, trendData, showForecast, forecasts]);

  // Calculate statistics
  const statistics = useMemo(() => {
    const stats: any = {};

    selectedMetrics.forEach(metric => {
      const dataPoints = trendData[metric] || [];
      if (dataPoints.length === 0) return;

      const values = dataPoints.map(p => p.value);
      const latest = values[values.length - 1] || 0;
      const previous = values[values.length - 2] || latest;
      const change = latest - previous;
      const changePercent = previous !== 0 ? (change / previous) * 100 : 0;

      const avg = values.reduce((sum, v) => sum + v, 0) / values.length;
      const max = Math.max(...values);
      const min = Math.min(...values);

      stats[metric] = {
        current: latest,
        previous,
        change,
        changePercent,
        average: avg,
        max,
        min,
        trend: changePercent > 1 ? 'up' : changePercent < -1 ? 'down' : 'stable',
      };
    });

    return stats;
  }, [selectedMetrics, trendData]);

  // Toggle metric selection
  const toggleMetric = useCallback((metricId: string) => {
    setSelectedMetrics(prev => {
      if (prev.includes(metricId)) {
        return prev.filter(id => id !== metricId);
      } else {
        return [...prev, metricId];
      }
    });
  }, []);

  // Export data
  const exportData = useCallback(() => {
    const exportObj = {
      timeRange,
      selectedMetrics,
      data: trendData,
      anomalies,
      statistics,
      forecasts,
      exportedAt: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(exportObj, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `performance-trends-${timeRange}-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [timeRange, selectedMetrics, trendData, anomalies, statistics, forecasts]);

  // Refresh data
  const refreshData = useCallback(() => {
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
    }, 2000);
  }, []);

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Performance Trends</h2>
          <p className="text-gray-600 dark:text-gray-400">Historical performance analysis and forecasting</p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={refreshData}
            disabled={isLoading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={exportData}
          >
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Controls */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <BarChart3 className="h-5 w-5 mr-2" />
            Chart Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <Label>Time Range</Label>
              <Select value={timeRange} onValueChange={onTimeRangeChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="7d">Last 7 days</SelectItem>
                  <SelectItem value="30d">Last 30 days</SelectItem>
                  <SelectItem value="90d">Last 90 days</SelectItem>
                  <SelectItem value="1y">Last year</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Chart Type</Label>
              <Select value={chartType} onValueChange={(value: any) => setChartType(value)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="line">Line Chart</SelectItem>
                  <SelectItem value="area">Area Chart</SelectItem>
                  <SelectItem value="bar">Bar Chart</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="show-targets"
                checked={showTargets}
                onCheckedChange={setShowTargets}
              />
              <Label htmlFor="show-targets">Show Targets</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Switch
                id="show-forecast"
                checked={showForecast}
                onCheckedChange={setShowForecast}
              />
              <Label htmlFor="show-forecast">Show Forecast</Label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Metric Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Select Metrics</CardTitle>
          <CardDescription>Choose which metrics to display in the chart</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {metricConfigs.map(config => (
              <Button
                key={config.id}
                variant={selectedMetrics.includes(config.id) ? "default" : "outline"}
                size="sm"
                onClick={() => toggleMetric(config.id)}
                className="h-auto p-3 flex flex-col items-center space-y-1"
                style={selectedMetrics.includes(config.id) ? {
                  backgroundColor: config.color + '20',
                  borderColor: config.color,
                  color: config.color
                } : {}}
              >
                {config.icon}
                <span className="text-xs font-medium">{config.name}</span>
                <span className="text-xs opacity-70">{config.unit}</span>
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Main Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Performance Trends</span>
            <div className="flex items-center space-x-2">
              {comparisonMode && (
                <Badge variant="outline">Comparison Mode</Badge>
              )}
              {showForecast && (
                <Badge variant="outline">
                  <Target className="h-3 w-3 mr-1" />
                  Forecast Enabled
                </Badge>
              )}
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-96">
            <ResponsiveContainer width="100%" height="100%">
              {chartType === 'line' ? (
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 12 }}
                    interval="preserveStartEnd"
                  />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(255, 255, 255, 0.95)',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                    }}
                  />
                  <Legend />
                  {selectedMetrics.map(metric => {
                    const config = metricConfigs.find(c => c.id === metric);
                    if (!config) return null;

                    return (
                      <React.Fragment key={metric}>
                        <Line
                          type="monotone"
                          dataKey={metric}
                          stroke={config.color}
                          strokeWidth={2}
                          dot={false}
                          name={config.name}
                          connectNulls={false}
                        />
                        {showTargets && (
                          <Line
                            type="monotone"
                            dataKey={`${metric}_target`}
                            stroke={config.color}
                            strokeWidth={1}
                            strokeDasharray="5 5"
                            dot={false}
                            opacity={0.5}
                            name={`${config.name} Target`}
                          />
                        )}
                        {showForecast && forecasts.map(forecast =>
                          forecast.metric === metric ? (
                            <Line
                              key="forecast"
                              type="monotone"
                              dataKey={`${metric}_forecast`}
                              stroke={config.color}
                              strokeWidth={2}
                              strokeDasharray="3 3"
                              dot={false}
                              opacity={0.7}
                              name={`${config.name} Forecast`}
                            />
                          ) : null
                        )}
                      </React.Fragment>
                    );
                  })}
                </LineChart>
              ) : chartType === 'area' ? (
                <AreaChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 12 }}
                    interval="preserveStartEnd"
                  />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(255, 255, 255, 0.95)',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                    }}
                  />
                  <Legend />
                  {selectedMetrics.map(metric => {
                    const config = metricConfigs.find(c => c.id === metric);
                    if (!config) return null;

                    return (
                      <Area
                        key={metric}
                        type="monotone"
                        dataKey={metric}
                        stroke={config.color}
                        fill={config.areaColor || config.color + '20'}
                        strokeWidth={2}
                        fillOpacity={0.3}
                        name={config.name}
                      />
                    );
                  })}
                </AreaChart>
              ) : (
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 12 }}
                    interval="preserveStartEnd"
                  />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(255, 255, 255, 0.95)',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                    }}
                  />
                  <Legend />
                  {selectedMetrics.map(metric => {
                    const config = metricConfigs.find(c => c.id === metric);
                    if (!config) return null;

                    return (
                      <Bar
                        key={metric}
                        dataKey={metric}
                        fill={config.color}
                        name={config.name}
                        fillOpacity={0.8}
                      />
                    );
                  })}
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Statistics Summary */}
      <Card>
        <CardHeader>
          <CardTitle>Performance Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {selectedMetrics.map(metric => {
              const config = metricConfigs.find(c => c.id === metric);
              const stats = statistics[metric];
              if (!config || !stats) return null;

              return (
                <div key={metric} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                      {config.icon}
                      <span className="font-medium">{config.name}</span>
                    </div>
                    <Badge
                      variant={stats.trend === 'up' ? 'default' : stats.trend === 'down' ? 'destructive' : 'secondary'}
                      className="flex items-center space-x-1"
                    >
                      {stats.trend === 'up' ? <TrendingUp className="h-3 w-3" /> :
                       stats.trend === 'down' ? <TrendingDown className="h-3 w-3" /> : null}
                      <span>{stats.changePercent > 0 ? '+' : ''}{stats.changePercent.toFixed(1)}%</span>
                    </Badge>
                  </div>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600 dark:text-gray-400">Current:</span>
                      <span className="font-medium">{stats.current.toFixed(1)}{config.unit}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600 dark:text-gray-400">Target:</span>
                      <span>{config.target}{config.unit}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600 dark:text-gray-400">Average:</span>
                      <span>{stats.average.toFixed(1)}{config.unit}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600 dark:text-gray-400">Range:</span>
                      <span>{stats.min.toFixed(1)} - {stats.max.toFixed(1)}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Anomalies */}
      {anomalies.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <AlertTriangle className="h-5 w-5 mr-2" />
              Detected Anomalies ({anomalies.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {anomalies.slice(0, 5).map(anomaly => (
                <div key={anomaly.id} className="border rounded-lg p-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-1">
                        <Badge
                          variant={anomaly.severity === 'high' ? 'destructive' :
                                  anomaly.severity === 'medium' ? 'default' : 'secondary'}
                        >
                          {anomaly.severity}
                        </Badge>
                        <span className="font-medium text-sm">{anomaly.metric}</span>
                        <span className="text-xs text-gray-500">
                          {new Date(anomaly.timestamp).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
                        {anomaly.description}
                      </p>
                      <p className="text-xs text-gray-500">
                        Impact: {anomaly.impact}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onAnomalyClick?.(anomaly)}
                    >
                      <MousePointer className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
              {anomalies.length > 5 && (
                <div className="text-center">
                  <Button variant="outline" size="sm">
                    View all {anomalies.length} anomalies
                  </Button>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Forecast Insights */}
      {showForecast && forecasts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Forecast Insights</CardTitle>
            <CardDescription>Predictive analysis based on historical trends</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {forecasts.map(forecast => {
                const config = metricConfigs.find(c => c.id === forecast.metric);
                if (!config) return null;

                return (
                  <div key={forecast.metric} className="border rounded-lg p-4">
                    <div className="flex items-center space-x-2 mb-3">
                      {config.icon}
                      <span className="font-medium">{config.name}</span>
                      <Badge
                        variant={forecast.trend === 'improving' ? 'default' :
                                forecast.trend === 'declining' ? 'destructive' : 'secondary'}
                      >
                        {forecast.trend}
                      </Badge>
                    </div>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600 dark:text-gray-400">Confidence:</span>
                        <span>{forecast.confidence.toFixed(0)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600 dark:text-gray-400">Accuracy:</span>
                        <span>{forecast.accuracy.toFixed(0)}%</span>
                      </div>
                      <Separator />
                      <div>
                        <div className="text-xs text-gray-600 dark:text-gray-400 mb-1">Next milestone:</div>
                        <div className="font-medium">{forecast.nextMilestone.date}</div>
                        <div className="text-lg">
                          {forecast.nextMilestone.expectedValue.toFixed(1)}{config.unit}
                        </div>
                        <div className="text-xs text-gray-500">
                          {forecast.nextMilestone.probability.toFixed(0)}% probability
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default PerformanceTrendVisualization;

interface PerformanceTrendVisualizationProps {
  timeRange?: string;
  data?: TrendData;
  onTimeRangeChange?: (range: string) => void;
  onMetricClick?: (metric: string) => void;
  onAnomalyClick?: (anomaly: Anomaly) => void;
  className?: string;
}