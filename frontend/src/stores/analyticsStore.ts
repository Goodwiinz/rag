import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import {
  RAGTriadMetrics,
  PerformanceAnalytics,
  TimeRange,
  AnalyticsFilters
} from '@/types';

interface AnalyticsState {
  // Time range and filters
  timeRange: TimeRange;
  filters: AnalyticsFilters;

  // Real-time data
  realTimeMetrics: RAGTriadMetrics | null;
  isRealTimeConnected: boolean;

  // Performance data
  performanceData: PerformanceAnalytics | null;

  // UI state
  selectedMetrics: string[];
  chartView: 'overview' | 'detailed' | 'comparison';
  autoRefresh: boolean;
  refreshInterval: number;

  // Actions
  setTimeRange: (timeRange: TimeRange) => void;
  setFilters: (filters: Partial<AnalyticsFilters>) => void;
  setRealTimeMetrics: (metrics: RAGTriadMetrics) => void;
  setRealTimeConnection: (connected: boolean) => void;
  setPerformanceData: (data: PerformanceAnalytics) => void;
  updateSelectedMetrics: (metric: string, selected: boolean) => void;
  setChartView: (view: 'overview' | 'detailed' | 'comparison') => void;
  toggleAutoRefresh: () => void;
  setRefreshInterval: (interval: number) => void;
  resetFilters: () => void;
}

export const useAnalyticsStore = create<AnalyticsState>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    timeRange: {
      start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(), // 7 days ago
      end: new Date().toISOString(),
    },
    filters: {
      modalities: [],
      queryTypes: [],
      userSegments: [],
      performanceThresholds: {
        answer_relevancy: 70,
        faithfulness: 90,
        contextual_relevancy: 70,
      },
    },
    realTimeMetrics: null,
    isRealTimeConnected: false,
    performanceData: null,
    selectedMetrics: ['answer_relevancy', 'faithfulness', 'contextual_relevancy'],
    chartView: 'overview',
    autoRefresh: true,
    refreshInterval: 30000, // 30 seconds

    // Actions
    setTimeRange: (timeRange) => set({ timeRange }),

    setFilters: (newFilters) => {
      const currentFilters = get().filters;
      set({ filters: { ...currentFilters, ...newFilters } });
    },

    setRealTimeMetrics: (metrics) => set({ realTimeMetrics: metrics }),

    setRealTimeConnection: (connected) => set({ isRealTimeConnected: connected }),

    setPerformanceData: (data) => set({ performanceData: data }),

    updateSelectedMetrics: (metric, selected) => {
      const { selectedMetrics } = get();
      if (selected && !selectedMetrics.includes(metric)) {
        set({ selectedMetrics: [...selectedMetrics, metric] });
      } else if (!selected && selectedMetrics.includes(metric)) {
        set({ selectedMetrics: selectedMetrics.filter(m => m !== metric) });
      }
    },

    setChartView: (view) => set({ chartView: view }),

    toggleAutoRefresh: () => set((state) => ({ autoRefresh: !state.autoRefresh })),

    setRefreshInterval: (interval) => set({ refreshInterval: interval }),

    resetFilters: () => set({
      filters: {
        modalities: [],
        queryTypes: [],
        userSegments: [],
        performanceThresholds: {
          answer_relevancy: 70,
          faithfulness: 90,
          contextual_relevancy: 70,
        },
      },
    }),
  }))
);

// Selector hooks for specific data
export const useTimeRange = () => useAnalyticsStore((state) => state.timeRange);
export const useAnalyticsFilters = () => useAnalyticsStore((state) => state.filters);
export const useRealTimeMetrics = () => useAnalyticsStore((state) => state.realTimeMetrics);
export const usePerformanceData = () => useAnalyticsStore((state) => state.performanceData);
export const useSelectedMetrics = () => useAnalyticsStore((state) => state.selectedMetrics);
export const useChartView = () => useAnalyticsStore((state) => state.chartView);
export const useAutoRefresh = () => useAnalyticsStore((state) => state.autoRefresh);
export const useRefreshInterval = () => useAnalyticsStore((state) => state.refreshInterval);