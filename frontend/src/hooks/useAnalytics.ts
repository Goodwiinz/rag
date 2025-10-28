import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAnalyticsStore } from '@/stores/analyticsStore';
import { useTimeRange, useAnalyticsFilters } from '@/stores/analyticsStore';
import {
  RAGTriadMetrics,
  PerformanceAnalytics,
  UsageAnalytics,
  SystemPerformanceMetrics,
  SystemUsageMetrics,
  TimeRange,
  TimeRangePreset,
  CustomTimeRange,
  AnalyticsFilters
} from '@/types';
import analyticsService from '@/services/analyticsService';

// Type guard for CustomTimeRange
const isCustomTimeRange = (timeRange: TimeRange): timeRange is CustomTimeRange => {
  return typeof timeRange === 'object' && 'start' in timeRange && 'end' in timeRange;
};

// Type guard for preset TimeRange
const isPresetTimeRange = (timeRange: TimeRange): timeRange is TimeRangePreset => {
  return typeof timeRange === 'string';
};

// Helper to check if timeRange is valid for queries
const isValidTimeRange = (timeRange: TimeRange): boolean => {
  return isPresetTimeRange(timeRange) || 
         (isCustomTimeRange(timeRange) && !!timeRange.start && !!timeRange.end);
};

// RAG Triad Metrics Hook
export const useRAGTriadMetrics = (timeRange?: TimeRange) => {
  const storeTimeRange = useTimeRange();
  const selectedTimeRange = timeRange || storeTimeRange;

  return useQuery({
    queryKey: ['rag-triad-metrics', selectedTimeRange],
    queryFn: () => analyticsService.getRAGTriadMetrics(selectedTimeRange),
    select: (data) => data.metrics,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
    refetchInterval: 2 * 60 * 1000, // 2 minutes
    enabled: isValidTimeRange(selectedTimeRange),
  });
};

// Performance Analytics Hook
export const usePerformanceAnalytics = (filters?: Partial<AnalyticsFilters>) => {
  const storeFilters = useAnalyticsFilters();
  const timeRange = useTimeRange();
  const selectedFilters = { ...storeFilters, ...filters };

  return useQuery({
    queryKey: ['performance-analytics', selectedFilters, timeRange],
    queryFn: () => analyticsService.getPerformanceAnalytics(selectedFilters, timeRange),
    select: (data) => ({
      ...data,
      chartData: transformDataForCharts(data),
      trendData: calculateTrends(data),
    }),
    staleTime: 5 * 60 * 1000,
    gcTime: 15 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000, // 5 minutes
    enabled: isValidTimeRange(timeRange),
  });
};

// Usage Analytics Hook
export const useUsageAnalytics = (timeRange?: TimeRange) => {
  const storeTimeRange = useTimeRange();
  const selectedTimeRange = timeRange || storeTimeRange;

  return useQuery({
    queryKey: ['usage-analytics', selectedTimeRange],
    queryFn: () => analyticsService.getUsageAnalytics(selectedTimeRange),
    select: (data) => ({
      ...data,
      queryPatterns: analyzeQueryPatterns(data.popular_queries || []),
      usageHeatmap: generateUsageHeatmap(data.user_behavior),
    }),
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000, // 10 minutes
  });
};

// Real-time Metrics Hook
export const useRealTimeMetrics = () => {
  const queryClient = useQueryClient();
  const { setRealTimeMetrics, setRealTimeConnection } = useAnalyticsStore();

  const query = useQuery({
    queryKey: ['real-time-metrics'],
    queryFn: () => analyticsService.getRealTimeMetrics(),
    select: (data) => data.metrics,
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 2 * 60 * 1000, // 2 minutes
    refetchInterval: 30 * 1000, // 30 seconds
  });

  // Handle success/error with useEffect
  React.useEffect(() => {
    if (query.data) {
      setRealTimeMetrics(query.data);
      setRealTimeConnection(true);
    }
    if (query.error) {
      setRealTimeConnection(false);
    }
  }, [query.data, query.error, setRealTimeMetrics, setRealTimeConnection]);

  // WebSocket for real-time updates
  React.useEffect(() => {
    const ws = new WebSocket(`${process.env.REACT_APP_WS_URL}/analytics/metrics`);

    ws.onopen = () => {
      setRealTimeConnection(true);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setRealTimeMetrics(data);
      queryClient.setQueryData(['real-time-metrics'], data);
    };

    ws.onclose = () => {
      setRealTimeConnection(false);
      // Attempt to reconnect after 5 seconds
      setTimeout(() => {
        const newWs = new WebSocket(`${process.env.REACT_APP_WS_URL}/analytics/metrics`);
        ws.onopen = newWs.onopen;
        ws.onmessage = newWs.onmessage;
        ws.onclose = newWs.onclose;
      }, 5000);
    };

    return () => {
      ws.close();
    };
  }, [queryClient, setRealTimeMetrics, setRealTimeConnection]);
};

// Historical Trends Hook
export const useHistoricalTrends = (metric: string, timeRange: TimeRange) => {
  return useQuery({
    queryKey: ['historical-trends', metric, timeRange],
    queryFn: () => analyticsService.getHistoricalTrends(metric, timeRange),
    select: (data) => ({
      ...data,
      chartData: formatTrendData(data),
      summary: calculateTrendSummary(data),
    }),
    staleTime: 30 * 60 * 1000, // 30 minutes
    gcTime: 60 * 60 * 1000, // 1 hour
    enabled: !!metric && isValidTimeRange(timeRange),
  });
};

// Comparison Hook
export const useComparisonData = (timeRanges: TimeRange[]) => {
  return useQuery({
    queryKey: ['comparison-data', timeRanges],
    queryFn: () => analyticsService.getComparisonData(timeRanges),
    select: (data) => ({
      ...data,
      comparisonChart: formatComparisonData(data),
      insights: generateComparisonInsights(data),
    }),
    staleTime: 15 * 60 * 1000,
    gcTime: 45 * 60 * 1000,
    enabled: timeRanges.length >= 2,
  });
};

// Export Data Hook
export const useExportAnalytics = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ format, filters, timeRange }: {
      format: 'csv' | 'json' | 'pdf';
      filters: AnalyticsFilters;
      timeRange: TimeRange;
    }) => analyticsService.exportAnalytics(format, filters, timeRange),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usage-analytics'] });
    },
  });
};

// Custom Analytics Actions Hook
export const useAnalyticsActions = () => {
  const queryClient = useQueryClient();
  const { setTimeRange, setFilters } = useAnalyticsStore();

  const updateTimeRange = React.useCallback((newTimeRange: TimeRange) => {
    setTimeRange(newTimeRange);
    // Invalidate relevant queries when time range changes
    queryClient.invalidateQueries({ queryKey: ['rag-triad-metrics'] });
    queryClient.invalidateQueries({ queryKey: ['performance-analytics'] });
    queryClient.invalidateQueries({ queryKey: ['usage-analytics'] });
  }, [setTimeRange, queryClient]);

  const updateFilters = React.useCallback((newFilters: Partial<AnalyticsFilters>) => {
    setFilters(newFilters);
    // Invalidate relevant queries when filters change
    queryClient.invalidateQueries({ queryKey: ['performance-analytics'] });
  }, [setFilters, queryClient]);

  const refreshAllAnalytics = React.useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['rag-triad-metrics'] });
    queryClient.invalidateQueries({ queryKey: ['performance-analytics'] });
    queryClient.invalidateQueries({ queryKey: ['usage-analytics'] });
    queryClient.invalidateQueries({ queryKey: ['real-time-metrics'] });
  }, [queryClient]);

  return {
    updateTimeRange,
    updateFilters,
    refreshAllAnalytics,
  };
};

// Utility functions for data transformation
const transformDataForCharts = (data: any) => {
  // Transform raw data into chart-friendly format
  return {
    lineChartData: {
      labels: data.timestamps,
      datasets: [
        {
          label: 'Answer Relevancy',
          data: data.answer_relevancy_history,
          borderColor: 'rgb(75, 192, 192)',
          backgroundColor: 'rgba(75, 192, 192, 0.2)',
        },
        {
          label: 'Faithfulness',
          data: data.faithfulness_history,
          borderColor: 'rgb(255, 99, 132)',
          backgroundColor: 'rgba(255, 99, 132, 0.2)',
        },
        {
          label: 'Contextual Relevancy',
          data: data.contextual_relevancy_history,
          borderColor: 'rgb(54, 162, 235)',
          backgroundColor: 'rgba(54, 162, 235, 0.2)',
        },
      ],
    },
    barChartData: {
      labels: data.modalities,
      datasets: [{
        label: 'Queries by Modality',
        data: data.modality_counts,
        backgroundColor: [
          'rgba(255, 99, 132, 0.8)',
          'rgba(54, 162, 235, 0.8)',
          'rgba(255, 205, 86, 0.8)',
          'rgba(75, 192, 192, 0.8)',
        ],
      }],
    },
  };
};

const calculateTrends = (data: any) => {
  // Calculate trend indicators
  return {
    answer_relevancy_trend: calculateTrend(data.answer_relevancy_history),
    faithfulness_trend: calculateTrend(data.faithfulness_history),
    contextual_relevancy_trend: calculateTrend(data.contextual_relevancy_history),
  };
};

const calculateTrend = (values: number[]): { direction: 'up' | 'down' | 'stable'; value: number } => {
  if (values.length < 2) return { direction: 'stable', value: 0 };

  const recent = values.slice(-7); // Last 7 data points
  const previous = values.slice(-14, -7); // Previous 7 data points

  if (previous.length === 0) return { direction: 'stable', value: 0 };

  const recentAvg = recent.reduce((a, b) => a + b, 0) / recent.length;
  const previousAvg = previous.reduce((a, b) => a + b, 0) / previous.length;
  const change = ((recentAvg - previousAvg) / previousAvg) * 100;

  let direction: 'up' | 'down' | 'stable';
  if (Math.abs(change) < 2) {
    direction = 'stable';
  } else if (change > 0) {
    direction = 'up';
  } else {
    direction = 'down';
  }

  return { direction, value: Math.abs(change) };
};

const analyzeQueryPatterns = (topQueries: Array<{ query: string; frequency: number }>) => {
  // Analyze query patterns for insights
  const avgQueryLength = topQueries.reduce((sum, q) => sum + q.query.length, 0) / topQueries.length;
  const totalFrequency = topQueries.reduce((sum, q) => sum + q.frequency, 0);

  return {
    averageQueryLength: Math.round(avgQueryLength),
    uniqueQueries: topQueries.length,
    totalQueries: totalFrequency,
    topCategories: categorizeQueries(topQueries),
  };
};

const categorizeQueries = (queries: Array<{ query: string; frequency: number }>) => {
  // Simple categorization based on keywords
  const categories: Record<string, Array<{ query: string; frequency: number }>> = {
    'General Inquiry': [],
    'Technical Documentation': [],
    'Code Examples': [],
    'Best Practices': [],
    'Troubleshooting': [],
  };

  queries.forEach(({ query, frequency }) => {
    const lowerQuery = query.toLowerCase();
    if (lowerQuery.includes('how to') || lowerQuery.includes('what is')) {
      categories['General Inquiry']!.push({ query, frequency });
    } else if (lowerQuery.includes('documentation') || lowerQuery.includes('api')) {
      categories['Technical Documentation']!.push({ query, frequency });
    } else if (lowerQuery.includes('code') || lowerQuery.includes('example')) {
      categories['Code Examples']!.push({ query, frequency });
    } else if (lowerQuery.includes('best') || lowerQuery.includes('practice')) {
      categories['Best Practices']!.push({ query, frequency });
    } else if (lowerQuery.includes('error') || lowerQuery.includes('issue') || lowerQuery.includes('problem')) {
      categories['Troubleshooting']!.push({ query, frequency });
    }
  });

  return categories;
};

const generateUsageHeatmap = (searchPatterns: any) => {
  // Generate heatmap data for usage patterns
  const { peak_usage_hours } = searchPatterns;
  const heatmapData = [];

  for (let hour = 0; hour < 24; hour++) {
    const intensity = peak_usage_hours.includes(hour) ?
      Math.random() * 0.5 + 0.5 :
      Math.random() * 0.3 + 0.1;
    heatmapData.push({
      hour,
      intensity,
      label: `${hour}:00`,
    });
  }

  return heatmapData;
};

const formatTrendData = (data: any) => {
  return {
    labels: data.timestamps,
    datasets: [{
      label: data.metric_name,
      data: data.values,
      borderColor: 'rgb(75, 192, 192)',
      backgroundColor: 'rgba(75, 192, 192, 0.2)',
      tension: 0.1,
    }],
  };
};

const calculateTrendSummary = (data: any) => {
  const values = data.values;
  const latest = values[values.length - 1];
  const earliest = values[0];
  const change = ((latest - earliest) / earliest) * 100;
  const average = values.reduce((a: number, b: number) => a + b, 0) / values.length;
  const max = Math.max(...values);
  const min = Math.min(...values);

  return {
    change: Math.round(change * 100) / 100,
    average: Math.round(average * 100) / 100,
    max: Math.round(max * 100) / 100,
    min: Math.round(min * 100) / 100,
    trend: change > 0 ? 'improving' : change < 0 ? 'declining' : 'stable',
  };
};

const formatComparisonData = (data: any) => {
  return {
    labels: data.time_ranges.map((range: any, index: number) => `Period ${index + 1}`),
    datasets: [
      {
        label: 'Answer Relevancy',
        data: data.answer_relevancy_comparison,
        backgroundColor: 'rgba(75, 192, 192, 0.8)',
      },
      {
        label: 'Faithfulness',
        data: data.faithfulness_comparison,
        backgroundColor: 'rgba(255, 99, 132, 0.8)',
      },
      {
        label: 'Contextual Relevancy',
        data: data.contextual_relevancy_comparison,
        backgroundColor: 'rgba(54, 162, 235, 0.8)',
      },
    ],
  };
};

const generateComparisonInsights = (data: any) => {
  // Generate insights from comparison data
  const insights = [];

  // Compare performance across periods
  const bestPerforming = data.time_ranges.reduce((best: any, current: any, index: number) => {
    const currentScore = current.answer_relevancy + current.faithfulness + current.contextual_relevancy;
    const bestScore = best.score || 0;
    return currentScore > bestScore ? { ...current, index, score: currentScore } : best;
  }, {});

  insights.push({
    type: 'performance',
    title: 'Best Performing Period',
    description: `Period ${bestPerforming.index + 1} showed the best overall performance with an average score of ${(bestPerforming.score / 3).toFixed(1)}%`,
  });

  // Identify trends
  const trend = calculateTrend(data.answer_relevancy_comparison);
  if (trend.direction !== 'stable') {
    insights.push({
      type: 'trend',
      title: `${trend.direction === 'up' ? 'Improving' : 'Declining'} Trend`,
      description: `Answer relevancy is ${trend.direction} by ${trend.value.toFixed(1)}% across the compared periods`,
    });
  }

  return insights;
};