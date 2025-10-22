// Context and Provider
export {
  AnalyticsProvider,
  useAnalytics,
  useAnalyticsState,
  useGraphState,
  useRealtimeState,
  useAnalyticsWebSocket,
} from './useAnalyticsContext';

// Metrics Hooks
export {
  useMetrics,
  useMetric,
  useTimeSeriesData,
  useCreateMetric,
  useUpdateMetric,
  useDeleteMetric,
  useAggregatedMetrics,
  useRealtimeMetric,
  useRealtimeMetrics,
  useMetricTrends,
  useMetricAlerts,
} from './useMetrics';

// Graph Data Hooks
export {
  useGraphData,
  useGraphStatistics,
  useNodeSearch,
  useNodeNeighbors,
  useGraphLayout,
  useCommunityDetection,
  useCentrality,
  useShortestPath,
  useGraphInteraction,
  useGraphFilters,
  useGraphAnalysis,
  useGraphExport,
} from './useGraphData';

// Dashboard Hooks
export {
  useDashboards,
  useDashboard,
  useCreateDashboard,
  useUpdateDashboard,
  useDeleteDashboard,
  useDuplicateDashboard,
  useDashboardManager,
  useWidgetData,
  useDashboardTemplates,
  useDashboardSharing,
} from './useDashboards';

// Report Hooks
export {
  useReports,
  useReport,
  useCreateReport,
  useUpdateReport,
  useDeleteReport,
  useGenerateReport,
  useReportTemplates,
  useScheduleReport,
  useReportHistory,
  useReportManager,
  useReportBuilder,
  useReportExport,
} from './useReports';

import { useState, useEffect } from 'react';

// Utility Hooks
export const useAnalyticsLoading = () => {
  const { isLoading } = useAnalyticsState();
  return isLoading;
};

export const useAnalyticsError = () => {
  const { error, clearError } = useAnalyticsState();
  return { error, clearError };
};

export const useConnectionStatus = () => {
  const { isConnected, connectionStatus } = useRealtimeState();
  return { isConnected, connectionStatus };
};

export const useRefreshInterval = () => {
  const { refreshInterval, autoRefresh, setRefreshInterval, toggleAutoRefresh } = useAnalyticsState();
  return {
    refreshInterval,
    autoRefresh,
    setRefreshInterval,
    toggleAutoRefresh,
  };
};

// Combined Hooks for Common Use Cases
export const useDashboardOverview = (dashboardId?: string) => {
  const { currentDashboard, widgets } = useDashboardManager(dashboardId);
  const { isLoading, error } = useAnalyticsState();
  const { isConnected } = useConnectionStatus();

  return {
    dashboard: currentDashboard,
    widgets,
    isLoading,
    error,
    isConnected,
    hasData: !!(currentDashboard && widgets.length > 0),
  };
};

export const useGraphOverview = () => {
  const { graphData, selectedNodes, selectedEdges } = useAnalyticsState();
  const { zoom, layout, showClusters } = useGraphState();
  const { isLoading, error } = useAnalyticsState();

  return {
    graphData,
    selectedNodes,
    selectedEdges,
    zoom,
    layout,
    showClusters,
    isLoading,
    error,
    hasData: !!(graphData && graphData.nodes.length > 0),
    nodeCount: graphData?.nodes.length || 0,
    edgeCount: graphData?.edges.length || 0,
  };
};

export const useRealtimeOverview = () => {
  const { liveMetrics, liveTimeSeries, subscriptions } = useRealtimeState();
  const { isConnected, connectionStatus } = useConnectionStatus();

  return {
    liveMetrics,
    liveTimeSeries,
    subscriptions,
    isConnected,
    connectionStatus,
    metricCount: Object.keys(liveMetrics).length,
    subscriptionCount: Object.keys(subscriptions).length,
    hasRealtimeData: Object.keys(liveMetrics).length > 0,
  };
};

// Performance monitoring hook
export const useAnalyticsPerformance = () => {
  const { updateCount, errorCount } = useRealtimeState();
  const [renderTime, setRenderTime] = useState(0);
  const [memoryUsage, setMemoryUsage] = useState(0);

  useEffect(() => {
    const startTime = performance.now();

    // Simulate render time measurement
    const measureRender = () => {
      const endTime = performance.now();
      setRenderTime(endTime - startTime);
    };

    const timer = setTimeout(measureRender, 0);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    // Simulate memory usage measurement
    if ('memory' in performance) {
      const memory = (performance as any).memory;
      setMemoryUsage(memory.usedJSHeapSize / 1024 / 1024); // Convert to MB
    }
  }, []);

  return {
    renderTime,
    memoryUsage,
    updateCount,
    errorCount,
    errorRate: updateCount > 0 ? (errorCount / updateCount) * 100 : 0,
  };
};

// Hook for accessibility features
export const useAnalyticsAccessibility = () => {
  const [highContrast, setHighContrast] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [screenReader, setScreenReader] = useState(false);

  useEffect(() => {
    // Detect user preferences
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mediaQuery.matches);

    const handleChange = (e: MediaQueryListEvent) => {
      setReducedMotion(e.matches);
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  useEffect(() => {
    // Detect screen reader
    const handleKeyDown = (e: KeyboardEvent) => {
      // Common screen reader shortcuts
      if (e.altKey && (e.key === 'A' || e.key === 'a')) {
        setScreenReader(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return {
    highContrast,
    setHighContrast,
    reducedMotion,
    setReducedMotion,
    screenReader,
    setScreenReader,
  };
};

// Hook for theme management
export const useAnalyticsTheme = () => {
  const { theme, setTheme } = useAnalyticsState();
  const [systemTheme, setSystemTheme] = useState<'light' | 'dark'>('light');

  useEffect(() => {
    // Detect system theme preference
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    setSystemTheme(mediaQuery.matches ? 'dark' : 'light');

    const handleChange = (e: MediaQueryListEvent) => {
      setSystemTheme(e.matches ? 'dark' : 'light');
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  const effectiveTheme = theme === 'system' ? systemTheme : theme;

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : theme === 'dark' ? 'system' : 'light';
    setTheme(newTheme);
  };

  return {
    theme,
    systemTheme,
    effectiveTheme,
    setTheme,
    toggleTheme,
    isDark: effectiveTheme === 'dark',
  };
};