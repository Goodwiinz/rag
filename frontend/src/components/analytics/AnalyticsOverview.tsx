'use client';

import { useEffect, useState } from 'react';
import { useReducedMotion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Users,
  FileText,
  Search,
  MessageSquare,
  Clock,
  Activity,
  AlertTriangle,
  BarChart3,
} from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string | number;
  icon: any;
  description?: string;
  loading?: boolean;
  onClick?: () => void;
}

function MetricCard({
  title,
  value,
  icon: Icon,
  description,
  loading = false,
  onClick,
}: MetricCardProps) {
  const reduceMotion = useReducedMotion();
  const targetValue = typeof value === 'number' ? value : 0;
  const [displayValue, setDisplayValue] = useState(() =>
    reduceMotion ? targetValue : 0
  );

  // Count up to the real value. When the user prefers reduced motion we snap
  // straight to the final number instead of animating it.
  useEffect(() => {
    if (loading || typeof value !== 'number') return;

    if (reduceMotion) {
      setDisplayValue(targetValue);
      return;
    }

    const duration = 1200;
    const steps = 40;
    const stepDuration = duration / steps;
    let step = 0;

    const timer = setInterval(() => {
      step++;
      const progress = step / steps;
      const easeOut = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(Math.round(targetValue * easeOut));

      if (step >= steps) {
        setDisplayValue(targetValue);
        clearInterval(timer);
      }
    }, stepDuration);

    return () => clearInterval(timer);
  }, [value, loading, reduceMotion, targetValue]);

  const isInteractive = Boolean(onClick);

  return (
    <Card
      className={cn(
        'transition-colors',
        isInteractive &&
          'cursor-pointer hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
      )}
      onClick={onClick}
      {...(isInteractive
        ? {
            role: 'button',
            tabIndex: 0,
            onKeyDown: (e: React.KeyboardEvent) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick?.();
              }
            },
            'aria-label': `${title} details`,
          }
        : {})}
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted text-primary">
          <Icon aria-hidden="true" className="h-4 w-4" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          <div className="text-2xl font-semibold tabular-nums tracking-tight text-foreground">
            {loading ? (
              <div className="h-8 w-24 animate-pulse rounded bg-muted" />
            ) : typeof value === 'number' ? (
              displayValue.toLocaleString()
            ) : (
              value
            )}
          </div>
          {description && !loading && (
            <p className="text-xs text-muted-foreground">{description}</p>
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
  onMetricClick,
}: AnalyticsOverviewProps) {
  const hasAnyData =
    Boolean(data) &&
    [
      data?.totalUsers,
      data?.activeUsers,
      data?.totalSessions,
      data?.documentsUploaded,
      data?.searchesPerformed,
      data?.chatsInitiated,
    ].some((n) => (n ?? 0) > 0);

  // Real measured values only. We do not invent period-over-period deltas;
  // until a comparison period exists in the data, no trend is shown.
  const overviewMetrics = [
    {
      key: 'totalUsers',
      title: 'Registered users',
      value: data?.totalUsers || 0,
      icon: Users,
      description: 'People with workspace access',
    },
    {
      key: 'activeUsers',
      title: 'Active users',
      value: data?.activeUsers || 0,
      icon: Activity,
      description: 'Active in the last 24 hours',
    },
    {
      key: 'pageViews',
      title: 'Page views',
      value: data?.totalPageViews || 0,
      icon: BarChart3,
      description: 'Views across the workspace',
    },
    {
      key: 'sessions',
      title: 'Sessions',
      value: data?.totalSessions || 0,
      icon: Clock,
      description: 'Recorded user sessions',
    },
    {
      key: 'documents',
      title: 'Documents',
      value: data?.documentsUploaded || 0,
      icon: FileText,
      description: 'Indexed in your knowledge base',
    },
    {
      key: 'searches',
      title: 'Searches',
      value: data?.searchesPerformed || 0,
      icon: Search,
      description: 'Queries run against the corpus',
    },
    {
      key: 'chats',
      title: 'Conversations',
      value: data?.chatsInitiated || 0,
      icon: MessageSquare,
      description: 'Sessions with the agent',
    },
    {
      key: 'errors',
      title: 'Error rate',
      value: `${(data?.errorRate ?? 0).toFixed(1)}%`,
      icon: AlertTriangle,
      description: 'Requests that returned an error',
    },
  ];

  if (!loading && !hasAnyData) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center gap-2 py-12 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
            <BarChart3 aria-hidden="true" className="h-5 w-5" />
          </div>
          <p className="text-sm font-medium text-foreground">No activity yet</p>
          <p className="max-w-xs text-sm text-muted-foreground">
            Upload documents and run searches to start measuring usage across
            your knowledge base.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {overviewMetrics.map((metric) => (
        <MetricCard
          key={metric.key}
          title={metric.title}
          value={metric.value}
          icon={metric.icon}
          description={metric.description}
          loading={loading}
          onClick={onMetricClick ? () => onMetricClick(metric.key) : undefined}
        />
      ))}
    </div>
  );
}

export default AnalyticsOverview;
