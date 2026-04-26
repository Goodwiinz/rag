import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import { metricsApi } from '@/services/analytics';
import { useAnalyticsStore, useRealtimeStore } from '@/store/analytics';
import { AnalyticsMetric, TimeSeriesData } from '@/store/analytics';

// Hook for fetching metrics
export const useMetrics = (timeRange?: { start: string; end: string }) => {
  const { setLoading, setError, updateMetrics } = useAnalyticsStore();

  return useQuery({
    queryKey: ['metrics', timeRange],
    queryFn: () => metricsApi.getMetrics(timeRange),
    staleTime: 30000, // 30 seconds
    refetchInterval: 60000, // 1 minute
    onSuccess: (data) => {
      const metricsMap = data.reduce((acc, metric) => {
        acc[metric.id] = metric;
        return acc;
      }, {} as Record<string, AnalyticsMetric>);

      updateMetrics(metricsMap);
      setError(null);
    },
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for fetching a single metric
export const useMetric = (metricId: string) => {
  const { setLoading, setError, updateMetric } = useAnalyticsStore();

  return useQuery({
    queryKey: ['metric', metricId],
    queryFn: () => metricsApi.getMetric(metricId),
    enabled: !!metricId,
    staleTime: 30000,
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for fetching time series data
export const useTimeSeriesData = (
  metricId: string,
  timeRange?: { start: string; end: string },
  granularity?: 'minute' | 'hour' | 'day'
) => {
  const { setLoading, setError, addTimeSeriesData, clearTimeSeriesData } = useRealtimeStore();

  return useQuery({
    queryKey: ['timeseries', metricId, timeRange, granularity],
    queryFn: () => metricsApi.getTimeSeriesData(metricId, timeRange, granularity),
    enabled: !!metricId,
    staleTime: 30000,
    refetchInterval: 30000, // 30 seconds for time series data
    onSuccess: (data) => {
      clearTimeSeriesData(metricId);
      addTimeSeriesData(metricId, data);
      setError(null);
    },
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for creating metrics
export const useCreateMetric = () => {
  const queryClient = useQueryClient();
  const { setError } = useAnalyticsStore();

  return useMutation({
    mutationFn: (metric: Omit<AnalyticsMetric, 'id'>) => metricsApi.createMetric(metric),
  });
};

// Hook for updating metrics
export const useUpdateMetric = () => {
  const queryClient = useQueryClient();
  const { setError } = useAnalyticsStore();

  return useMutation({
    mutationFn: ({ metricId, updates }: { metricId: string; updates: Partial<AnalyticsMetric> }) =>
      metricsApi.updateMetric(metricId, updates),
  });
};

// Hook for deleting metrics
export const useDeleteMetric = () => {
  const queryClient = useQueryClient();
  const { setError } = useAnalyticsStore();

  return useMutation({
    mutationFn: (metricId: string) => metricsApi.deleteMetric(metricId),
  });
};

// Hook for aggregated metrics
export const useAggregatedMetrics = (
  metricIds: string[],
  aggregation: 'sum' | 'average' | 'min' | 'max',
  timeRange?: { start: string; end: string }
) => {
  const { setLoading, setError } = useAnalyticsStore();

  return useQuery({
    queryKey: ['aggregated-metrics', metricIds, aggregation, timeRange],
    queryFn: () => metricsApi.getAggregatedMetrics(metricIds, aggregation, timeRange),
    enabled: metricIds.length > 0,
    staleTime: 30000,
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for real-time metric updates
export const useRealtimeMetric = (metricId: string) => {
  const { liveMetrics } = useRealtimeStore();
  const { ws } = useAnalytics();
  const [isSubscribed, setIsSubscribed] = useState(false);

  useEffect(() => {
    if (metricId && !isSubscribed) {
      ws.subscribe([metricId]);
      setIsSubscribed(true);
    }

    return () => {
      if (metricId && isSubscribed) {
        ws.unsubscribe([metricId]);
        setIsSubscribed(false);
      }
    };
  }, [metricId, isSubscribed, ws]);

  return {
    metric: liveMetrics[metricId],
    isSubscribed,
    isConnected: ws.isConnected,
  };
};

// Hook for multiple real-time metrics
export const useRealtimeMetrics = (metricIds: string[]) => {
  const { liveMetrics } = useRealtimeStore();
  const { ws } = useAnalytics();
  const [subscribedMetrics, setSubscribedMetrics] = useState<Set<string>>(new Set());

  useEffect(() => {
    const toSubscribe = metricIds.filter(id => !subscribedMetrics.has(id));
    const toUnsubscribe = Array.from(subscribedMetrics).filter(id => !metricIds.includes(id));

    if (toSubscribe.length > 0) {
      ws.subscribe(toSubscribe);
      setSubscribedMetrics(prev => new Set([...prev, ...toSubscribe]));
    }

    if (toUnsubscribe.length > 0) {
      ws.unsubscribe(toUnsubscribe);
      setSubscribedMetrics(prev => {
        const newSet = new Set(prev);
        toUnsubscribe.forEach(id => newSet.delete(id));
        return newSet;
      });
    }
  }, [metricIds, subscribedMetrics, ws]);

  const metrics = metricIds.reduce((acc, id) => {
    if (liveMetrics[id]) {
      acc[id] = liveMetrics[id];
    }
    return acc;
  }, {} as Record<string, AnalyticsMetric>);

  return {
    metrics,
    subscribedMetrics: Array.from(subscribedMetrics),
    isConnected: ws.isConnected,
  };
};

// Hook for metric trends
export const useMetricTrends = (metricId: string, period: 'hour' | 'day' | 'week' | 'month' = 'day') => {
  const { liveTimeSeries } = useRealtimeStore();
  const timeSeriesData = liveTimeSeries[metricId] || [];

  const calculateTrend = () => {
    if (timeSeriesData.length < 2) {
      return { direction: 'stable' as const, percentage: 0 };
    }

    const recent = timeSeriesData.slice(-10); // Last 10 data points
    const older = timeSeriesData.slice(-20, -10); // Previous 10 data points

    if (older.length === 0) {
      return { direction: 'stable' as const, percentage: 0 };
    }

    const recentAvg = recent.reduce((sum, d) => sum + d.value, 0) / recent.length;
    const olderAvg = older.reduce((sum, d) => sum + d.value, 0) / older.length;

    const percentage = ((recentAvg - olderAvg) / olderAvg) * 100;

    let direction: 'up' | 'down' | 'stable';
    if (Math.abs(percentage) < 1) {
      direction = 'stable';
    } else if (percentage > 0) {
      direction = 'up';
    } else {
      direction = 'down';
    }

    return { direction, percentage: Math.abs(percentage) };
  };

  return {
    data: timeSeriesData,
    trend: calculateTrend(),
    isLoading: timeSeriesData.length === 0,
  };
};

// Hook for metric alerts
export const useMetricAlerts = (metricId: string) => {
  const { alertRules, activeAlerts } = useAnalyticsStore();

  const relevantRules = alertRules.filter(rule => rule.metric === metricId);
  const relevantAlerts = activeAlerts.filter(alert => alert.metric === metricId);

  return {
    rules: relevantRules,
    alerts: relevantAlerts,
    hasActiveAlerts: relevantAlerts.length > 0,
    hasRules: relevantRules.length > 0,
  };
};