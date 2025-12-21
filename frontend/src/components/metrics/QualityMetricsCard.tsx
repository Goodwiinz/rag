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
    MinusIcon
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
  query = "abdel factual",
  sessionId
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
    timestamp: 0 // Initialize to 0 to prevent hydration mismatch
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
          answerRelevancy: Math.min(95, Math.max(45, 65 + Math.random() * 25 * queryComplexity)),
          faithfulness: Math.min(98, Math.max(70, 80 + Math.random() * 15)),
          contextualRelevancy: Math.min(92, Math.max(50, 70 + Math.random() * 20 * queryComplexity)),
          hallucinationRisk: Math.max(2, 15 - Math.random() * 10),
          confidence: Math.min(99, Math.max(30, 60 + Math.random() * 35 * queryComplexity)),
          latency: Math.round(300 + Math.random() * 1200 + (query.length * 10)),
          documentsRetrieved: Math.floor(2 + Math.random() * 8),
          entities: Math.floor(Math.random() * 15),
          timestamp: Date.now()
        });
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [isLive, isConnected, query]);

  const getMetricColor = (value: number, type: 'higher' | 'lower' = 'higher') => {
    if (type === 'higher') {
      if (value >= 90) return 'text-green-600';
      if (value >= 80) return 'text-yellow-600';
      if (value >= 70) return 'text-orange-600';
      return 'text-red-600';
    } else {
      if (value <= 5) return 'text-green-600';
      if (value <= 10) return 'text-yellow-600';
      if (value <= 15) return 'text-orange-600';
      return 'text-red-600';
    }
  };

  const getMetricBackground = (value: number, type: 'higher' | 'lower' = 'higher') => {
    if (type === 'higher') {
      if (value >= 90) return 'bg-green-100 text-green-800';
      if (value >= 80) return 'bg-yellow-100 text-yellow-800';
      if (value >= 70) return 'bg-orange-100 text-orange-800';
      return 'bg-red-100 text-red-800';
    } else {
      if (value <= 5) return 'bg-green-100 text-green-800';
      if (value <= 10) return 'bg-yellow-100 text-yellow-800';
      if (value <= 15) return 'bg-orange-100 text-orange-800';
      return 'bg-red-100 text-red-800';
    }
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

  return (
    <Card className={cn("relative overflow-hidden", className)}>
      <CardContent className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <ChartBarIcon className="h-5 w-5 text-blue-600" />
              <h3 className="text-lg font-semibold text-gray-900">Quality Metrics</h3>
            </div>
            <Badge variant={isConnected ? "default" : "secondary"} className="text-xs">
              {isConnected ? "LIVE" : "SIMULATED"}
            </Badge>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-sm text-gray-500">Real-time</span>
            <Switch checked={isLive} onCheckedChange={setIsLive} />
          </div>
        </div>

        {/* Query Info */}
        <div className="mb-6 p-3 bg-gray-50 rounded-lg">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700 truncate max-w-md">
              Query: {query}
            </span>
            <Badge className={getMetricBackground(metrics.confidence)}>
              {metrics.confidence.toFixed(0)}% confidence
            </Badge>
          </div>
        </div>

        {/* Main Metrics Grid */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          {/* Answer Relevancy */}
          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-blue-900">Answer Relevancy</span>
              <Badge className={getMetricBackground(metrics.answerRelevancy)}>
                {metrics.answerRelevancy.toFixed(0)}%
              </Badge>
            </div>
            <div className="text-2xl font-bold text-blue-600">
              {metrics.answerRelevancy.toFixed(1)}%
            </div>
          </div>

          {/* Faithfulness */}
          <div className="p-4 bg-green-50 rounded-lg border border-green-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-green-900">Faithfulness</span>
              <Badge className={getMetricBackground(metrics.faithfulness)}>
                {metrics.faithfulness.toFixed(0)}%
              </Badge>
            </div>
            <div className="text-2xl font-bold text-green-600">
              {metrics.faithfulness.toFixed(1)}%
            </div>
          </div>

          {/* Contextual Relevancy */}
          <div className="p-4 bg-purple-50 rounded-lg border border-purple-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-purple-900">Context Relevancy</span>
              <Badge className={getMetricBackground(metrics.contextualRelevancy)}>
                {metrics.contextualRelevancy.toFixed(0)}%
              </Badge>
            </div>
            <div className="text-2xl font-bold text-purple-600">
              {metrics.contextualRelevancy.toFixed(1)}%
            </div>
          </div>

          {/* Hallucination Risk */}
          <div className="p-4 bg-red-50 rounded-lg border border-red-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-red-900">Hallucination Risk</span>
              <Badge className={getMetricBackground(metrics.hallucinationRisk, 'lower')}>
                {metrics.hallucinationRisk.toFixed(1)}%
              </Badge>
            </div>
            <div className="text-2xl font-bold text-red-600">
              {(100 - metrics.hallucinationRisk).toFixed(1)}%
            </div>
            <div className="text-xs text-red-500">Safety Score</div>
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="border-t pt-4">
          <h4 className="text-sm font-medium text-gray-700 mb-3">Performance</h4>
          <div className="grid grid-cols-3 gap-4">
            <div className="flex items-center space-x-2">
              <ClockIcon className="h-4 w-4 text-gray-500" />
              <div>
                <div className="text-lg font-semibold text-gray-900">
                  {formatLatency(metrics.latency)}
                </div>
                <div className="text-xs text-gray-500">Latency</div>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <DocumentTextIcon className="h-4 w-4 text-gray-500" />
              <div>
                <div className="text-lg font-semibold text-gray-900">
                  {metrics.documentsRetrieved}
                </div>
                <div className="text-xs text-gray-500">Docs</div>
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <ChartBarIcon className="h-4 w-4 text-gray-500" />
              <div>
                <div className="text-lg font-semibold text-gray-900">
                  {metrics.entities}
                </div>
                <div className="text-xs text-gray-500">Entities</div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer with timestamp */}
        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span>Last updated: {metrics.timestamp > 0 ? new Date(metrics.timestamp).toLocaleTimeString() : '---'}</span>
            {isConnected && (
              <span className="flex items-center space-x-1">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
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