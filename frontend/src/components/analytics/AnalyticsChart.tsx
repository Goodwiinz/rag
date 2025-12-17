'use client';

import { useState, useMemo } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  BarChart3,
  LineChart as LineChartIcon,
  PieChart as PieChartIcon,
  Activity,
  TrendingUp,
  TrendingDown,
  Calendar,
  Download,
  Settings,
} from 'lucide-react';
import { cn } from '@/lib/utils';

type ChartType = 'line' | 'bar' | 'area' | 'pie';

interface ChartDataPoint {
  name: string;
  value: number;
  value2?: number;
  date?: string;
  change?: number;
}

interface AnalyticsChartProps {
  title: string;
  description?: string;
  data: ChartDataPoint[];
  type?: ChartType;
  height?: number;
  showLegend?: boolean;
  showGrid?: boolean;
  showTooltip?: boolean;
  colors?: string[];
  dataKeys?: string[];
  labels?: Record<string, string>;
  format?: {
    xAxis?: (value: string) => string;
    yAxis?: (value: number) => string;
    tooltip?: (value: number) => string;
  };
  actions?: {
    onExport?: () => void;
    onSettings?: () => void;
  };
  className?: string;
}

const CHART_COLORS = [
  'var(--chart-1)', // Amber
  'var(--chart-2)', // Blue
  'var(--chart-3)', // Green
  'var(--chart-4)', // Purple
  'var(--chart-5)', // Orange
  'var(--chart-6)', // Pink
];

const DEFAULT_COLORS = [
  '#f59e0b', // Amber-500
  '#3b82f6', // Blue-500
  '#10b981', // Green-500
  '#8b5cf6', // Purple-500
  '#f97316', // Orange-500
  '#ec4899', // Pink-500
];

export function AnalyticsChart({
  title,
  description,
  data,
  type = 'area',
  height = 300,
  showLegend = true,
  showGrid = true,
  showTooltip = true,
  colors = CHART_COLORS,
  dataKeys = ['value'],
  labels = {},
  format,
  actions,
  className,
}: AnalyticsChartProps) {
  const [chartType, setChartType] = useState<ChartType>(type);
  const [timeRange, setTimeRange] = useState('7d');

  // Process data based on time range
  const processedData = useMemo(() => {
    if (timeRange === 'all') return data;

    const now = new Date();
    const daysMap: Record<string, number> = {
      '7d': 7,
      '30d': 30,
      '90d': 90,
    };

    const days = daysMap[timeRange] || 7;
    const cutoffDate = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);

    return data.filter(item => {
      if (!item.date) return true;
      return new Date(item.date) >= cutoffDate;
    });
  }, [data, timeRange]);

  // Calculate trend
  const trend = useMemo(() => {
    if (processedData.length < 2) return null;

    const recent = processedData.slice(-7);
    const previous = processedData.slice(-14, -7);

    if (previous.length === 0) return null;

    const recentAvg = recent.reduce((sum, item) => sum + item.value, 0) / recent.length;
    const previousAvg = previous.reduce((sum, item) => sum + item.value, 0) / previous.length;

    const change = ((recentAvg - previousAvg) / previousAvg) * 100;

    return {
      value: Math.abs(change),
      direction: change > 0 ? 'up' : 'down',
    };
  }, [processedData]);

  const renderChart = () => {
    const commonProps = {
      data: processedData,
      margin: { top: 5, right: 30, left: 20, bottom: 5 },
    };

    switch (chartType) {
      case 'line':
        return (
          <LineChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />}
            <XAxis
              dataKey="name"
              tickLine={false}
              tickFormatter={format?.xAxis}
              className="text-xs"
            />
            <YAxis
              tickLine={false}
              tickFormatter={format?.yAxis}
              className="text-xs"
            />
            {showTooltip && (
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
                formatter={format?.tooltip}
              />
            )}
            {showLegend && <Legend />}
            {dataKeys.map((key, index) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[index] || DEFAULT_COLORS[index]}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6 }}
                name={labels[key] || key}
              />
            ))}
          </LineChart>
        );

      case 'bar':
        return (
          <BarChart {...commonProps}>
            {showGrid && <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />}
            <XAxis
              dataKey="name"
              tickLine={false}
              tickFormatter={format?.xAxis}
              className="text-xs"
            />
            <YAxis
              tickLine={false}
              tickFormatter={format?.yAxis}
              className="text-xs"
            />
            {showTooltip && (
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
                formatter={format?.tooltip}
              />
            )}
            {showLegend && <Legend />}
            {dataKeys.map((key, index) => (
              <Bar
                key={key}
                dataKey={key}
                fill={colors[index] || DEFAULT_COLORS[index]}
                radius={[4, 4, 0, 0]}
                name={labels[key] || key}
              />
            ))}
          </BarChart>
        );

      case 'area':
        return (
          <AreaChart {...commonProps}>
            <defs>
              {dataKeys.map((key, index) => (
                <linearGradient
                  key={key}
                  id={`gradient-${key}`}
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop
                    offset="5%"
                    stopColor={colors[index] || DEFAULT_COLORS[index]}
                    stopOpacity={0.8}
                  />
                  <stop
                    offset="95%"
                    stopColor={colors[index] || DEFAULT_COLORS[index]}
                    stopOpacity={0.1}
                  />
                </linearGradient>
              ))}
            </defs>
            {showGrid && <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />}
            <XAxis
              dataKey="name"
              tickLine={false}
              tickFormatter={format?.xAxis}
              className="text-xs"
            />
            <YAxis
              tickLine={false}
              tickFormatter={format?.yAxis}
              className="text-xs"
            />
            {showTooltip && (
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
                formatter={format?.tooltip}
              />
            )}
            {showLegend && <Legend />}
            {dataKeys.map((key, index) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[index] || DEFAULT_COLORS[index]}
                fillOpacity={1}
                fill={`url(#gradient-${key})`}
                strokeWidth={2}
                name={labels[key] || key}
              />
            ))}
          </AreaChart>
        );

      case 'pie':
        return (
          <PieChart>
            <Pie
              data={processedData}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              outerRadius={100}
              fill="#8884d8"
              dataKey="value"
            >
              {processedData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={colors[index] || DEFAULT_COLORS[index]}
                />
              ))}
            </Pie>
            {showTooltip && (
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--card))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
                formatter={format?.tooltip}
              />
            )}
            {showLegend && <Legend />}
          </PieChart>
        );

      default:
        return null;
    }
  };

  return (
    <Card className={cn('overflow-hidden', className)}>
      {/* Header */}
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              {title}
              {trend && (
                <Badge
                  variant={trend.direction === 'up' ? 'default' : 'secondary'}
                  className={cn(
                    'text-xs',
                    trend.direction === 'up'
                      ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20'
                      : 'bg-rose-500/10 text-rose-600 border-rose-500/20'
                  )}
                >
                  {trend.direction === 'up' ? (
                    <TrendingUp className="h-3 w-3 mr-1" />
                  ) : (
                    <TrendingDown className="h-3 w-3 mr-1" />
                  )}
                  {trend.value.toFixed(1)}%
                </Badge>
              )}
            </CardTitle>
            {description && (
              <p className="text-sm text-muted-foreground">{description}</p>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Chart Type Selector */}
            <div className="flex items-center rounded-lg border border-border bg-background p-1">
              <Button
                variant={chartType === 'line' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setChartType('line')}
                className="h-7 w-7 p-0"
              >
                <LineChartIcon className="h-3 w-3" />
              </Button>
              <Button
                variant={chartType === 'bar' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setChartType('bar')}
                className="h-7 w-7 p-0"
              >
                <BarChart3 className="h-3 w-3" />
              </Button>
              <Button
                variant={chartType === 'area' ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setChartType('area')}
                className="h-7 w-7 p-0"
              >
                <Activity className="h-3 w-3" />
              </Button>
              {data.length <= 10 && (
                <Button
                  variant={chartType === 'pie' ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setChartType('pie')}
                  className="h-7 w-7 p-0"
                >
                  <PieChartIcon className="h-3 w-3" />
                </Button>
              )}
            </div>

            <Separator orientation="vertical" className="h-6" />

            {/* Time Range Selector */}
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="h-7 w-[80px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7d">7d</SelectItem>
                <SelectItem value="30d">30d</SelectItem>
                <SelectItem value="90d">90d</SelectItem>
                <SelectItem value="all">All</SelectItem>
              </SelectContent>
            </Select>

            {/* Actions */}
            {actions && (
              <>
                <Separator orientation="vertical" className="h-6" />
                {actions.onExport && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={actions.onExport}
                    className="h-7 w-7 p-0"
                  >
                    <Download className="h-3 w-3" />
                  </Button>
                )}
                {actions.onSettings && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={actions.onSettings}
                    className="h-7 w-7 p-0"
                  >
                    <Settings className="h-3 w-3" />
                  </Button>
                )}
              </>
            )}
          </div>
        </div>
      </CardHeader>

      {/* Chart */}
      <CardContent className="p-0">
        <div style={{ height: `${height}px` }} className="w-full px-6 pb-6">
          <ResponsiveContainer width="100%" height="100%">
            {renderChart()}
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

export default AnalyticsChart;