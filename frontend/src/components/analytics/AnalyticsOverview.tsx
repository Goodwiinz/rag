'use client';

import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Users,
  FileText,
  Search,
  MessageSquare,
  Clock,
  Activity,
  Zap,
  BarChart3,
  PieChart,
  Download,
  Calendar,
  Filter,
  RefreshCw
} from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  previousValue?: string | number;
  change?: number;
  changeType?: 'increase' | 'decrease' | 'neutral';
  icon: any;
  iconColor?: string;
  description?: string;
  loading?: boolean;
  onClick?: () => void;
}

function MetricCard({
  title,
  value,
  previousValue,
  change,
  changeType = 'neutral',
  icon: Icon,
  iconColor = 'text-amber-500',
  description,
  loading = false,
  onClick
}: MetricCardProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    if (loading) return;

    const targetValue = typeof value === 'number' ? value : 0;
    const duration = 1200;
    const steps = 40;
    const stepDuration = duration / steps;
    const increment = targetValue / steps;
    let current = 0;
    let step = 0;

    setIsAnimating(true);
    const timer = setInterval(() => {
      step++;
      const progress = step / steps;
      const easeOut = 1 - Math.pow(1 - progress, 3);
      current = Math.round(targetValue * easeOut);
      setDisplayValue(current);

      if (step >= steps) {
        setDisplayValue(targetValue);
        setIsAnimating(false);
        clearInterval(timer);
      }
    }, stepDuration);

    return () => clearInterval(timer);
  }, [value, loading]);

  const TrendIcon = changeType === 'increase' ? TrendingUp : changeType === 'decrease' ? TrendingDown : Minus;
  const trendColors = {
    increase: 'text-emerald-500 bg-emerald-500/10',
    decrease: 'text-rose-500 bg-rose-500/10',
    neutral: 'text-muted-foreground bg-muted'
  };

  return (
    <Card
      className={cn(
        'group relative overflow-hidden transition-all duration-300',
        'hover:border-amber-500/30 hover:shadow-lg hover:shadow-amber-500/5',
        'hover:-translate-y-0.5',
        onClick && 'cursor-pointer'
      )}
      onClick={onClick}
    >
      {/* Gradient overlay on hover */}
      <div className="absolute inset-0 bg-gradient-to-br from-amber-500/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <div className={cn(
          'flex h-8 w-8 items-center justify-center rounded-lg',
          'bg-gradient-to-br from-amber-500/10 to-orange-500/10',
          'group-hover:from-amber-500/20 group-hover:to-orange-500/20',
          'transition-all duration-300'
        )}>
          <Icon className={cn('h-4 w-4', iconColor)} />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div className="text-2xl font-bold tracking-tight">
            {loading ? (
              <div className="h-8 w-24 bg-muted rounded animate-pulse" />
            ) : (
              typeof value === 'number' ? displayValue.toLocaleString() : value
            )}
          </div>

          {(change !== undefined || previousValue !== undefined) && !loading && (
            <div className="flex items-center gap-2">
              <Badge
                variant="secondary"
                className={cn(
                  'font-medium',
                  trendColors[changeType]
                )}
              >
                <TrendIcon className="h-3 w-3 mr-1" />
                {change !== undefined ? `${change > 0 ? '+' : ''}${change}%` : ''}
              </Badge>
              <span className="text-xs text-muted-foreground">
                vs last period
              </span>
            </div>
          )}

          {description && (
            <p className="text-xs text-muted-foreground mt-1">
              {description}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

interface AnalyticsOverviewProps {
  data?: {
    totalUsers: number;
    activeUsers: number;
    totalSessions: number;
    totalPageViews: number;
    averageSessionDuration: number;
    bounceRate: number;
    documentsUploaded: number;
    searchesPerformed: number;
    chatsInitiated: number;
    errorRate: number;
  };
  loading?: boolean;
  onRefresh?: () => void;
  onExport?: () => void;
  onMetricClick?: (metric: string) => void;
}

export function AnalyticsOverview({
  data,
  loading = false,
  onRefresh,
  onExport,
  onMetricClick
}: AnalyticsOverviewProps) {
  const [selectedTimeRange, setSelectedTimeRange] = useState('7d');
  const [lastUpdated, setLastUpdated] = useState(new Date());

  const handleRefresh = () => {
    setLastUpdated(new Date());
    onRefresh?.();
  };

  const overviewMetrics = [
    {
      title: 'Total Users',
      value: data?.totalUsers || 0,
      change: 12.5,
      changeType: 'increase' as const,
      icon: Users,
      iconColor: 'text-blue-500',
      description: 'Registered users',
      onClick: () => onMetricClick?.('totalUsers')
    },
    {
      title: 'Active Users',
      value: data?.activeUsers || 0,
      change: 8.2,
      changeType: 'increase' as const,
      icon: Activity,
      iconColor: 'text-emerald-500',
      description: 'Users in last 24h',
      onClick: () => onMetricClick?.('activeUsers')
    },
    {
      title: 'Page Views',
      value: data?.totalPageViews || 0,
      change: -2.4,
      changeType: 'decrease' as const,
      icon: BarChart3,
      iconColor: 'text-purple-500',
      description: 'Total page views',
      onClick: () => onMetricClick?.('pageViews')
    },
    {
      title: 'Sessions',
      value: data?.totalSessions || 0,
      change: 5.7,
      changeType: 'increase' as const,
      icon: Clock,
      iconColor: 'text-orange-500',
      description: 'User sessions',
      onClick: () => onMetricClick?.('sessions')
    },
    {
      title: 'Documents',
      value: data?.documentsUploaded || 0,
      change: 18.3,
      changeType: 'increase' as const,
      icon: FileText,
      iconColor: 'text-cyan-500',
      description: 'Documents uploaded',
      onClick: () => onMetricClick?.('documents')
    },
    {
      title: 'Searches',
      value: data?.searchesPerformed || 0,
      change: 9.1,
      changeType: 'increase' as const,
      icon: Search,
      iconColor: 'text-indigo-500',
      description: 'Searches performed',
      onClick: () => onMetricClick?.('searches')
    },
    {
      title: 'AI Chats',
      value: data?.chatsInitiated || 0,
      change: 15.6,
      changeType: 'increase' as const,
      icon: MessageSquare,
      iconColor: 'text-pink-500',
      description: 'Chat sessions',
      onClick: () => onMetricClick?.('chats')
    },
    {
      title: 'Error Rate',
      value: `${data?.errorRate.toFixed(1) || 0}%`,
      change: -0.3,
      changeType: 'increase' as const, // Decrease in error rate is positive
      icon: Zap,
      iconColor: 'text-rose-500',
      description: 'System errors',
      onClick: () => onMetricClick?.('errors')
    }
  ];

  const timeRanges = [
    { value: '24h', label: 'Last 24h' },
    { value: '7d', label: 'Last 7 days' },
    { value: '30d', label: 'Last 30 days' },
    { value: '90d', label: 'Last 90 days' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Analytics Overview</h2>
          <p className="text-muted-foreground">
            Monitor your RAG system performance and user engagement
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Time Range Selector */}
          <div className="flex items-center rounded-lg border border-border bg-background p-1">
            {timeRanges.map((range) => (
              <Button
                key={range.value}
                variant={selectedTimeRange === range.value ? 'default' : 'ghost'}
                size="sm"
                onClick={() => setSelectedTimeRange(range.value)}
                className="h-7 px-3 text-xs"
              >
                {range.label}
              </Button>
            ))}
          </div>

          <Separator orientation="vertical" className="h-6" />

          {/* Action Buttons */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={loading}
          >
            <RefreshCw className={cn(
              'h-4 w-4 mr-2',
              loading && 'animate-spin'
            )} />
            Refresh
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={onExport}
          >
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Last Updated */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Clock className="h-3 w-3" />
        Last updated: {lastUpdated.toLocaleTimeString()}
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {overviewMetrics.map((metric, index) => (
          <div
            key={metric.title}
            className="animate-fade-in"
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <MetricCard {...metric} loading={loading} />
          </div>
        ))}
      </div>

      {/* Key Insights */}
      <Card className="bg-gradient-to-br from-amber-500/5 to-orange-500/5 border-amber-500/20">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <PieChart className="h-5 w-5 text-amber-500" />
            Key Insights
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex items-start gap-3">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500/10">
                <TrendingUp className="h-3 w-3 text-emerald-500" />
              </div>
              <div>
                <p className="text-sm font-medium">Strong User Growth</p>
                <p className="text-xs text-muted-foreground">
                  Active users increased by 8.2% this period
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-500/10">
                <FileText className="h-3 w-3 text-blue-500" />
              </div>
              <div>
                <p className="text-sm font-medium">High Engagement</p>
                <p className="text-xs text-muted-foreground">
                  Document uploads up 18.3% showing strong adoption
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-rose-500/10">
                <Zap className="h-3 w-3 text-rose-500" />
              </div>
              <div>
                <p className="text-sm font-medium">System Health</p>
                <p className="text-xs text-muted-foreground">
                  Error rate decreased by 0.3% - stable performance
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default AnalyticsOverview;