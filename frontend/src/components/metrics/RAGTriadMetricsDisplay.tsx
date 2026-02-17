import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { THEME } from '@/theme/constants';
import {
    ArrowTrendingDownIcon,
    ArrowTrendingUpIcon,
    ChartBarIcon,
    MinusIcon
} from '@heroicons/react/24/outline';
import React from 'react';
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Legend,
    Line,
    LineChart,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis
} from 'recharts';

interface RAGTriadMetricsDisplayProps {
  metrics: {
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
  };
  timeRange?: string;
  className?: string;
}

const COLORS = [
  THEME.colors.primary,
  THEME.colors.secondary,
  THEME.colors.accent,
  THEME.colors.info,
  THEME.colors.success
];

export const RAGTriadMetricsDisplay: React.FC<RAGTriadMetricsDisplayProps> = ({
  metrics,
  timeRange = '24h',
  className
}) => {
  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'up':
        return ArrowTrendingUpIcon;
      case 'down':
        return ArrowTrendingDownIcon;
      default:
        return MinusIcon;
    }
  };

  const getTrendColor = (trend: string) => {
    switch (trend) {
      case 'up':
        return 'text-green-600';
      case 'down':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const getMetricStatus = (current: number, target: number) => {
    if (current >= target) return 'text-green-600 bg-green-50';
    if (current >= target * 0.9) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  const formatHistoryData = (history: Array<{ timestamp: number; value: number }>) => {
    return history.map(item => ({
      time: new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      value: Math.round(item.value * 100) / 100
    }));
  };

  const allHistoryData = React.useMemo(() => {
    const maxLength = Math.max(
      metrics.answerRelevancy.history.length,
      metrics.faithfulness.history.length,
      metrics.contextualRelevancy.history.length
    );

    return Array.from({ length: maxLength }, (_, i) => {
      const answerRelevancy = metrics.answerRelevancy.history[i];
      const faithfulness = metrics.faithfulness.history[i];
      const contextualRelevancy = metrics.contextualRelevancy.history[i];

      return {
        time: answerRelevancy ? new Date(answerRelevancy.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) :
              faithfulness ? new Date(faithfulness.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) :
              contextualRelevancy ? new Date(contextualRelevancy.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
        answerRelevancy: answerRelevancy ? Math.round(answerRelevancy.value * 100) / 100 : null,
        faithfulness: faithfulness ? Math.round(faithfulness.value * 100) / 100 : null,
        contextualRelevancy: contextualRelevancy ? Math.round(contextualRelevancy.value * 100) / 100 : null,
      };
    }).filter(item => item.time);
  }, [metrics]);

  return (
    <div className={cn("space-y-6", className)}>
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Answer Relevancy */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="text-sm font-medium">Answer Relevancy</span>
              <div className="flex items-center space-x-1">
                {React.createElement(getTrendIcon(metrics.answerRelevancy.trend), {
                  className: cn("h-4 w-4", getTrendColor(metrics.answerRelevancy.trend))
                })}
                <Badge className={getMetricStatus(metrics.answerRelevancy.current, metrics.answerRelevancy.target)}>
                  {metrics.answerRelevancy.current}%
                </Badge>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-600">Target: {metrics.answerRelevancy.target}%</span>
                <span className="text-gray-600">Current: {metrics.answerRelevancy.current}%</span>
              </div>
              <Progress value={metrics.answerRelevancy.current} className="h-2" />

              {/* Distribution Chart */}
              <div className="h-32">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={metrics.answerRelevancy.distribution}
                      dataKey="count"
                      nameKey="range"
                      cx="50%"
                      cy="50%"
                      outerRadius={40}
                      label={({ payload, percent }) => {
                        const range = (payload as { range?: string } | undefined)?.range || 'N/A';
                        const percentage =
                          (payload as { percentage?: number } | undefined)?.percentage ??
                          ((percent ?? 0) * 100).toFixed(0);
                        return `${range}: ${percentage}%`;
                      }}
                    >
                      {metrics.answerRelevancy.distribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Faithfulness */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="text-sm font-medium">Faithfulness</span>
              <div className="flex items-center space-x-1">
                {React.createElement(getTrendIcon(metrics.faithfulness.trend), {
                  className: cn("h-4 w-4", getTrendColor(metrics.faithfulness.trend))
                })}
                <Badge className={getMetricStatus(metrics.faithfulness.current, metrics.faithfulness.target)}>
                  {metrics.faithfulness.current}%
                </Badge>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-600">Target: {metrics.faithfulness.target}%</span>
                <span className="text-gray-600">Current: {metrics.faithfulness.current}%</span>
              </div>
              <Progress value={metrics.faithfulness.current} className="h-2" />

              {/* Distribution Chart */}
              <div className="h-32">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={metrics.faithfulness.distribution}
                      dataKey="count"
                      nameKey="range"
                      cx="50%"
                      cy="50%"
                      outerRadius={40}
                      label={({ payload, percent }) => {
                        const range = (payload as { range?: string } | undefined)?.range || 'N/A';
                        const percentage =
                          (payload as { percentage?: number } | undefined)?.percentage ??
                          ((percent ?? 0) * 100).toFixed(0);
                        return `${range}: ${percentage}%`;
                      }}
                    >
                      {metrics.faithfulness.distribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Contextual Relevancy */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span className="text-sm font-medium">Contextual Relevancy</span>
              <div className="flex items-center space-x-1">
                {React.createElement(getTrendIcon(metrics.contextualRelevancy.trend), {
                  className: cn("h-4 w-4", getTrendColor(metrics.contextualRelevancy.trend))
                })}
                <Badge className={getMetricStatus(metrics.contextualRelevancy.current, metrics.contextualRelevancy.target)}>
                  {metrics.contextualRelevancy.current}%
                </Badge>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-600">Target: {metrics.contextualRelevancy.target}%</span>
                <span className="text-gray-600">Current: {metrics.contextualRelevancy.current}%</span>
              </div>
              <Progress value={metrics.contextualRelevancy.current} className="h-2" />

              {/* Distribution Chart */}
              <div className="h-32">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={metrics.contextualRelevancy.distribution}
                      dataKey="count"
                      nameKey="range"
                      cx="50%"
                      cy="50%"
                      outerRadius={40}
                      label={({ payload, percent }) => {
                        const range = (payload as { range?: string } | undefined)?.range || 'N/A';
                        const percentage =
                          (payload as { percentage?: number } | undefined)?.percentage ??
                          ((percent ?? 0) * 100).toFixed(0);
                        return `${range}: ${percentage}%`;
                      }}
                    >
                      {metrics.contextualRelevancy.distribution.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Historical Trends */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <ChartBarIcon className="h-4 w-4 mr-2" />
            RAG Triad Metrics - Historical Trends ({timeRange})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={allHistoryData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="time"
                  tick={{ fontSize: 12 }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fontSize: 12 }}
                  domain={[0, 100]}
                />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="answerRelevancy"
                  stroke={THEME.colors.primary}
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  name="Answer Relevancy"
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="faithfulness"
                  stroke={THEME.colors.secondary}
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  name="Faithfulness"
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="contextualRelevancy"
                  stroke={THEME.colors.accent}
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  name="Contextual Relevancy"
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      {/* Detailed Distribution */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Answer Relevancy Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={metrics.answerRelevancy.distribution}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="range"
                    tick={{ fontSize: 10 }}
                    angle={-45}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill={THEME.colors.primary} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Faithfulness Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={metrics.faithfulness.distribution}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="range"
                    tick={{ fontSize: 10 }}
                    angle={-45}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill={THEME.colors.secondary} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Contextual Relevancy Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={metrics.contextualRelevancy.distribution}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="range"
                    tick={{ fontSize: 10 }}
                    angle={-45}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill={THEME.colors.accent} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default RAGTriadMetricsDisplay;
