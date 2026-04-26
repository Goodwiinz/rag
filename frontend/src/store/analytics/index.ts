// Main Analytics Store
export { useAnalyticsStore } from './analyticsStore';
export type {
  AnalyticsMetric,
  TimeSeriesData,
  GraphNode,
  GraphEdge,
  GraphData,
  Widget,
  Dashboard,
  Report,
  AlertRule,
} from './analyticsStore';

// Graph Visualization Store
export { useGraphVisualizationStore } from './graphStore';
// Note: GraphVisualizationState and GraphVisualizationActions are internal types

// Real-time Store
export { useRealtimeStore } from './realtimeStore';
// Note: RealtimeState and RealtimeActions are internal types

// Utility hooks for store combinations
export const useAnalyticsState = () => {
  const analyticsStore = useAnalyticsStore();
  const graphStore = useGraphVisualizationStore();
  const realtimeStore = useRealtimeStore();

  return {
    analytics: analyticsStore,
    graph: graphStore,
    realtime: realtimeStore,
  };
};

// Combined selectors for common use cases
export const useDashboardData = () => {
  const { dashboards, activeDashboard, activeWidgets } = useAnalyticsStore();
  const currentDashboard = dashboards.find(d => d.id === activeDashboard);

  return {
    dashboards,
    activeDashboard,
    currentDashboard,
    activeWidgets,
    widgets: currentDashboard?.widgets || [],
  };
};

export const useGraphData = () => {
  const { graphData, selectedNodes, selectedEdges, graphFilters } = useAnalyticsStore();
  const {
    layout,
    nodeSize,
    edgeWidth,
    colorScheme,
    hoveredNode,
    hoveredEdge,
    zoom,
    pan,
  } = useGraphVisualizationStore();

  return {
    graphData,
    selectedNodes,
    selectedEdges,
    graphFilters,
    visualization: {
      layout,
      nodeSize,
      edgeWidth,
      colorScheme,
      hoveredNode,
      hoveredEdge,
      zoom,
      pan,
    },
  };
};

export const useRealtimeMetrics = () => {
  const {
    isConnected,
    connectionStatus,
    liveMetrics,
    liveTimeSeries,
    subscriptions,
  } = useRealtimeStore();

  return {
    connection: {
      isConnected,
      status: connectionStatus,
    },
    data: {
      metrics: liveMetrics,
      timeSeries: liveTimeSeries,
    },
    subscriptions,
  };
};

export const useAnalyticsReports = () => {
  const { reports, isGeneratingReport } = useAnalyticsStore();

  return {
    reports,
    isGeneratingReport,
  };
};

export const useAnalyticsAlerts = () => {
  const { alertRules, activeAlerts } = useAnalyticsStore();

  return {
    rules: alertRules,
    active: activeAlerts,
  };
};