import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { useWebSocket } from '@/hooks/useWebSocket';
import { cn } from '@/lib/utils';
import {
  ArrowTrendingDownIcon,
  ArrowTrendingUpIcon,
  ChartBarIcon,
  ClockIcon,
  DocumentTextIcon,
  MinusIcon,
} from '@heroicons/react/24/outline';
import React, { useEffect, useState } from 'react';

interface QualityMetricsCardProps {
  className?: string;
  query?: string;
  sessionId?: string;
}

interface MetricsData {
  answerRelevancy: number;
  faithfulness: number;
  contextualRelevancy: number;
  hallucinationRisk: number;
  confidence: number;
  latency: number;
  documentsRetrieved: number;
  entities: number;
  timestamp: number;
}

interface WebSocketMetricsUpdate {
  type: 'quality_metrics_update';
  payload: {
    query_id: string;
    metrics: MetricsData;
  };
}

export const QualityMetricsCard: React.FC<QualityMetricsCardProps> = ({
  className,
  query = 'abdel factual',
  sessionId,
}) => {
  const { isConnected, manager } = useWebSocket();
  const [isLive, setIsLive] = useState(true);
  const [metrics, setMetrics] = useState<MetricsData>({
    answerRelevancy: 0,
    faithfulness: 0,
    contextualRelevancy: 0,
    hallucinationRisk: 0,
    confidence: 0,
    latency: 0,
    documentsRetrieved: 0,
    entities: 0,
    timestamp: 0, // Initialize to 0 to prevent hydration mismatch
  });

  // WebSocket subscription for real metrics
  useEffect(() => {
    if (!manager || !isLive) return;

    const handleMetricsUpdate = (data: WebSocketMetricsUpdate) => {
      if (data.payload.query_id === sessionId) {
        setMetrics(data.payload.metrics);
      }
    };

    manager.on('quality_metrics_update', handleMetricsUpdate);

    return () => {
      manager.off('quality_metrics_update', handleMetricsUpdate);
    };
  }, [manager, sessionId, isLive]);

  // Simulate real metrics when WebSocket not available
  useEffect(() => {
    if (isLive && !isConnected) {
      const interval = setInterval(() => {
        // Generate realistic metrics based on query complexity
        const queryComplexity = query.length > 10 ? 1 : 0.8;

        setMetrics({
          answerRelevancy: Math.min(
            95,
            Math.max(45, 65 + Math.random() * 25 * queryComplexity)
          ),
          faithfulness: Math.min(98, Math.max(70, 80 + Math.random() * 15)),
          contextualRelevancy: Math.min(
            92,
            Math.max(50, 70 + Math.random() * 20 * queryComplexity)
          ),
          hallucinationRisk: Math.max(2, 15 - Math.random() * 10),
          confidence: Math.min(
            99,
            Math.max(30, 60 + Math.random() * 35 * queryComplexity)
          ),
          latency: Math.round(300 + Math.random() * 1200 + query.length * 10),
          documentsRetrieved: Math.floor(2 + Math.random() * 8),
          entities: Math.floor(Math.random() * 15),
          timestamp: Date.now(),
        });
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [isLive, isConnected, query]);

  // Quality bands map to neutral foreground + semantic status, never the
  // single Sol accent (reserved for the headline figure). Status is conveyed
  // by label text as well as color, so it is never color-only.
  const getQualityTone = (
    value: number,
    type: 'higher' | 'lower' = 'higher'
  ) => {
    const good = type === 'higher' ? value >= 80 : value <= 5;
    const fair = type === 'higher' ? value >= 70 : value <= 15;
    if (good) return { label: 'Good', dot: 'bg-[var(--nous-terra)]' };
    if (fair) return { label: 'Fair', dot: 'bg-[var(--nous-helios)]' };
    return { label: 'Low', dot: 'bg-[var(--nous-mars)]' };
  };

  const getTrendIcon = (current: number, previous: number) => {
    if (current > previous * 1.05) return ArrowTrendingUpIcon;
    if (current < previous * 0.95) return ArrowTrendingDownIcon;
    return MinusIcon;
  };

  const formatLatency = (ms: number) => {
    if (ms < 1000) return `${Math.round(ms)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const qualityMetrics = [
    {
      key: 'answerRelevancy',
      label: 'Answer relevancy',
      value: metrics.answerRelevancy,
      type: 'higher' as const,
      accent: true,
    },
    {
      key: 'faithfulness',
      label: 'Faithfulness',
      value: metrics.faithfulness,
      type: 'higher' as const,
      accent: false,
    },
    {
      key: 'contextualRelevancy',
      label: 'Context relevancy',
      value: metrics.contextualRelevancy,
      type: 'higher' as const,
      accent: false,
    },
    {
      key: 'hallucinationRisk',
      label: 'Safety score',
      value: 100 - metrics.hallucinationRisk,
      type: 'higher' as const,
      accent: false,
    },
  ];

  return (
    <Card className={cn('overflow-hidden', className)}>
      <CardContent className="p-6">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <ChartBarIcon aria-hidden="true" className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-foreground">
                Retrieval quality
              </h3>
              <p
                role="status"
                className="flex items-center gap-1.5 text-xs text-muted-foreground mt-0.5"
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    'inline-flex h-1.5 w-1.5 rounded-full',
                    isConnected
                      ? 'bg-[var(--nous-terra)]'
                      : 'bg-muted-foreground'
                  )}
                />
                {isConnected ? 'Live connection' : 'Sample values'}
              </p>
            </div>
          </div>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Auto-refresh</span>
            <Switch
              checked={isLive}
              onCheckedChange={setIsLive}
              aria-label="Toggle real-time updates"
            />
          </label>
        </div>

        {/* Query Info */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg border border-border bg-muted/30">
          <span className="text-sm text-foreground truncate max-w-md">
            <span className="text-muted-foreground">Query: </span>
            {query}
          </span>
          <Badge variant="outline" className="tabular-nums">
            {metrics.confidence.toFixed(0)}% confidence
          </Badge>
        </div>

        {/* Main Metrics Grid */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          {qualityMetrics.map((metric) => {
            const tone = getQualityTone(metric.value, metric.type);
            return (
              <div
                key={metric.key}
                className="p-4 rounded-xl border border-border bg-card"
              >
                <div className="flex items-center justify-between gap-2 mb-3">
                  <span className="text-sm font-medium text-foreground">
                    {metric.label}
                  </span>
                  <span className="flex items-center gap-1.5 shrink-0">
                    <span
                      aria-hidden="true"
                      className={cn('h-1.5 w-1.5 rounded-full', tone.dot)}
                    />
                    <span className="text-[11px] text-muted-foreground">
                      {tone.label}
                    </span>
                  </span>
                </div>
                <div
                  className={cn(
                    'text-2xl font-semibold tabular-nums',
                    metric.accent ? 'text-primary' : 'text-foreground'
                  )}
                >
                  {metric.value.toFixed(1)}%
                </div>
              </div>
            );
          })}
        </div>

        {/* Performance Metrics */}
        <div className="border-t border-border pt-4">
          <h4 className="text-sm font-medium text-foreground mb-3">
            Performance
          </h4>
          <div className="grid grid-cols-3 gap-4">
            <div className="flex items-center gap-2">
              <ClockIcon
                aria-hidden="true"
                className="h-4 w-4 text-muted-foreground shrink-0"
              />
              <div>
                <div className="text-lg font-semibold text-foreground tabular-nums">
                  {formatLatency(metrics.latency)}
                </div>
                <div className="text-xs text-muted-foreground">Latency</div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <DocumentTextIcon
                aria-hidden="true"
                className="h-4 w-4 text-muted-foreground shrink-0"
              />
              <div>
                <div className="text-lg font-semibold text-foreground tabular-nums">
                  {metrics.documentsRetrieved}
                </div>
                <div className="text-xs text-muted-foreground">Documents</div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <ChartBarIcon
                aria-hidden="true"
                className="h-4 w-4 text-muted-foreground shrink-0"
              />
              <div>
                <div className="text-lg font-semibold text-foreground tabular-nums">
                  {metrics.entities}
                </div>
                <div className="text-xs text-muted-foreground">Entities</div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer with timestamp */}
        <div className="mt-4 pt-4 border-t border-border">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="tabular-nums">
              Last updated:{' '}
              {metrics.timestamp > 0
                ? new Date(metrics.timestamp).toLocaleTimeString()
                : '—'}
            </span>
            {isConnected && (
              <span className="flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  className="h-1.5 w-1.5 rounded-full bg-[var(--nous-terra)]"
                />
                <span>Connected</span>
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default QualityMetricsCard;
