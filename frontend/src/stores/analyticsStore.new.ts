/**
 * Analytics Store - State Management for Knowledge Graph Analytics Dashboard
 *
 * This store manages the global state for the analytics dashboard, including:
 * - Dashboard configurations and widget layouts
 * - Real-time data from WebSocket connections
 * - Filter states and time ranges
 * - Loading and error states
 */

import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import {
  TimeRange,
  AnalyticsFilters,
  MetricCardProps,
  ChartData,
  ActivityItem,
  PerformanceMetrics,
} from '../types/analytics';
import {
  KnowledgeGraphData,
  GraphFilters,
  EntityDetails,
  GraphAnalyticsDashboard,
  WebSocketGraphUpdate,
  GraphVisualizationState,
} from '../types/knowledge-graph';

// Dashboard Configuration Types
export interface DashboardConfig {
  id: string;
  name: string;
  description: string;
  layout: WidgetLayout[];
  timeRange: TimeRange;
  filters: AnalyticsFilters;
  refreshInterval: number;
  isPublic: boolean;
  owner: string;
  createdAt: string;
  updatedAt: string;
}

export interface WidgetLayout {
  id: string;
  type: 'metric' | 'chart' | 'table' | 'graph' | 'heatmap';
  title: string;
  position: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
  config: Record<string, any>;
  dataSource: string;
  refreshInterval?: number;
}

export interface WidgetConfig {
  id: string;
  type: string;
  title: string;
  config: Record<string, any>;
  dataSource: string;
}

export interface MetricsData {
  kpiMetrics: MetricCardProps[];
  chartData: Record<string, ChartData[]>;
  activityData: ActivityItem[];
  performanceData: PerformanceMetrics;
  lastUpdated: string;
}

// State Interface
interface AnalyticsState {
  // Dashboard Configuration
  dashboards: Record<string, DashboardConfig>;
  activeDashboard: string | null;
  widgetRegistry: Record<string, WidgetConfig>;

  // Data State
  metricsData: Record<string, MetricsData>;
  graphsData: KnowledgeGraphData | null;
  realTimeData: Record<string, any>;

  // UI State
  timeRange: TimeRange;
  filters: AnalyticsFilters;
  graphFilters: GraphFilters;
  viewMode: 'desktop' | 'tablet' | 'mobile';

  // Loading and Error States
  loading: Record<string, boolean>;
  errors: Record<string, string | null>;

  // Real-time State
  wsConnected: boolean;
  wsStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
  subscriptions: Set<string>;

  // Visualization State
  visualizationState: GraphVisualizationState;
  selectedWidgets: Set<string>;
  widgetPositions: Record<string, { x: number; y: number; w: number; h: number }>;

  // Export and Sharing State
  exportProgress: {
    inProgress: boolean;
    progress: number;
    format?: string;
  };
}

// Actions Interface
interface AnalyticsActions {
  // Dashboard Management
  createDashboard: (config: Omit<DashboardConfig, 'id' | 'createdAt' | 'updatedAt'>) => void;
  updateDashboard: (id: string, config: Partial<DashboardConfig>) => void;
  deleteDashboard: (id: string) => void;
  setActiveDashboard: (id: string) => void;
  duplicateDashboard: (id: string, newName: string) => void;

  // Widget Management
  addWidget: (dashboardId: string, widget: WidgetLayout) => void;
  updateWidget: (dashboardId: string, widgetId: string, config: Partial<WidgetLayout>) => void;
  removeWidget: (dashboardId: string, widgetId: string) => void;
  moveWidget: (dashboardId: string, widgetId: string, position: { x: number; y: number; w: number; h: number }) => void;

  // Data Management
  setMetricsData: (key: string, data: MetricsData) => void;
  setGraphsData: (data: KnowledgeGraphData) => void;
  updateRealTimeData: (key: string, data: any) => void;
  clearData: () => void;

  // Filter and Time Management
  setTimeRange: (range: TimeRange) => void;
  setFilters: (filters: Partial<AnalyticsFilters>) => void;
  setGraphFilters: (filters: Partial<GraphFilters>) => void;
  clearFilters: () => void;

  // Loading and Error Management
  setLoading: (key: string, loading: boolean) => void;
  setError: (key: string, error: string | null) => void;
  clearErrors: () => void;

  // Real-time Management
  connectWebSocket: () => void;
  disconnectWebSocket: () => void;
  setWsStatus: (status: 'connecting' | 'connected' | 'disconnected' | 'error') => void;
  subscribe: (channel: string) => void;
  unsubscribe: (channel: string) => void;
  handleWebSocketUpdate: (update: WebSocketGraphUpdate) => void;

  // Visualization Management
  setVisualizationState: (state: Partial<GraphVisualizationState>) => void;
  selectWidget: (widgetId: string) => void;
  deselectWidget: (widgetId: string) => void;
  clearWidgetSelection: () => void;

  // Export Management
  startExport: (format: string) => void;
  updateExportProgress: (progress: number) => void;
  completeExport: () => void;

  // Utility Actions
  refreshDashboard: () => void;
  resetStore: () => void;
}

// Store Creation
export const useAnalyticsStore = create<AnalyticsState & AnalyticsActions>()(
  devtools(
    subscribeWithSelector(
      immer((set, get) => ({
        // Initial State
        dashboards: {},
        activeDashboard: null,
        widgetRegistry: {},

        metricsData: {},
        graphsData: null,
        realTimeData: {},

        timeRange: '7d',
        filters: {},
        graphFilters: {
          entity_types: [],
          relationship_types: [],
          min_confidence: 0.5,
        },
        viewMode: 'desktop',

        loading: {},
        errors: {},

        wsConnected: false,
        wsStatus: 'disconnected',
        subscriptions: new Set(),

        visualizationState: {
          viewport: {
            zoom: 1,
            pan: { x: 0, y: 0 },
            bounds: { minX: 0, minY: 0, maxX: 1000, maxY: 1000 },
          },
          selection: {
            nodes: new Set(),
            edges: new Set(),
          },
          rendering: {
            nodes_visible: 0,
            edges_visible: 0,
            fps: 60,
            render_time: 0,
          },
          ui: {
            show_labels: true,
            show_analytics_overlay: false,
            color_scheme: 'default',
            layout_algorithm: 'force_directed',
            clustering_enabled: false,
          },
        },
        selectedWidgets: new Set(),
        widgetPositions: {},

        exportProgress: {
          inProgress: false,
          progress: 0,
        },

        // Dashboard Management Actions
        createDashboard: (config) => {
          set((state) => {
            const id = `dashboard_${Date.now()}`;
            const newDashboard: DashboardConfig = {
              ...config,
              id,
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            };
            state.dashboards[id] = newDashboard;
            if (!state.activeDashboard) {
              state.activeDashboard = id;
            }
          });
        },

        updateDashboard: (id, config) => {
          set((state) => {
            if (state.dashboards[id]) {
              state.dashboards[id] = {
                ...state.dashboards[id],
                ...config,
                updatedAt: new Date().toISOString(),
              };
            }
          });
        },

        deleteDashboard: (id) => {
          set((state) => {
            delete state.dashboards[id];
            if (state.activeDashboard === id) {
              state.activeDashboard = Object.keys(state.dashboards)[0] || null;
            }
          });
        },

        setActiveDashboard: (id) => {
          set((state) => {
            state.activeDashboard = id;
          });
        },

        duplicateDashboard: (id, newName) => {
          set((state) => {
            const original = state.dashboards[id];
            if (original) {
              const newId = `dashboard_${Date.now()}`;
              state.dashboards[newId] = {
                ...original,
                id: newId,
                name: newName,
                createdAt: new Date().toISOString(),
                updatedAt: new Date().toISOString(),
              };
            }
          });
        },

        // Widget Management Actions
        addWidget: (dashboardId, widget) => {
          set((state) => {
            if (state.dashboards[dashboardId]) {
              state.dashboards[dashboardId].layout.push(widget);
            }
          });
        },

        updateWidget: (dashboardId, widgetId, config) => {
          set((state) => {
            const dashboard = state.dashboards[dashboardId];
            if (dashboard) {
              const widgetIndex = dashboard.layout.findIndex(w => w.id === widgetId);
              if (widgetIndex !== -1) {
                dashboard.layout[widgetIndex] = {
                  ...dashboard.layout[widgetIndex],
                  ...config,
                };
              }
            }
          });
        },

        removeWidget: (dashboardId, widgetId) => {
          set((state) => {
            const dashboard = state.dashboards[dashboardId];
            if (dashboard) {
              dashboard.layout = dashboard.layout.filter(w => w.id !== widgetId);
            }
          });
        },

        moveWidget: (dashboardId, widgetId, position) => {
          set((state) => {
            const dashboard = state.dashboards[dashboardId];
            if (dashboard) {
              const widget = dashboard.layout.find(w => w.id === widgetId);
              if (widget) {
                widget.position = position;
              }
            }
          });
        },

        // Data Management Actions
        setMetricsData: (key, data) => {
          set((state) => {
            state.metricsData[key] = data;
          });
        },

        setGraphsData: (data) => {
          set((state) => {
            state.graphsData = data;
          });
        },

        updateRealTimeData: (key, data) => {
          set((state) => {
            state.realTimeData[key] = data;
          });
        },

        clearData: () => {
          set((state) => {
            state.metricsData = {};
            state.realTimeData = {};
            state.errors = {};
          });
        },

        // Filter and Time Management
        setTimeRange: (range) => {
          set((state) => {
            state.timeRange = range;
            // Clear cached data when time range changes
            state.metricsData = {};
          });
        },

        setFilters: (filters) => {
          set((state) => {
            state.filters = { ...state.filters, ...filters };
          });
        },

        setGraphFilters: (filters) => {
          set((state) => {
            state.graphFilters = { ...state.graphFilters, ...filters };
          });
        },

        clearFilters: () => {
          set((state) => {
            state.filters = {};
            state.graphFilters = {
              entity_types: [],
              relationship_types: [],
              min_confidence: 0.5,
            };
          });
        },

        // Loading and Error Management
        setLoading: (key, loading) => {
          set((state) => {
            state.loading[key] = loading;
          });
        },

        setError: (key, error) => {
          set((state) => {
            state.errors[key] = error;
          });
        },

        clearErrors: () => {
          set((state) => {
            state.errors = {};
          });
        },

        // Real-time Management
        connectWebSocket: () => {
          set((state) => {
            state.wsStatus = 'connecting';
          });
        },

        disconnectWebSocket: () => {
          set((state) => {
            state.wsStatus = 'disconnected';
            state.wsConnected = false;
            state.subscriptions.clear();
          });
        },

        setWsStatus: (status) => {
          set((state) => {
            state.wsStatus = status;
            state.wsConnected = status === 'connected';
          });
        },

        subscribe: (channel) => {
          set((state) => {
            state.subscriptions.add(channel);
          });
        },

        unsubscribe: (channel) => {
          set((state) => {
            state.subscriptions.delete(channel);
          });
        },

        handleWebSocketUpdate: (update) => {
          set((state) => {
            // Handle different types of updates
            switch (update.type) {
              case 'analytics_updated':
                // Update real-time analytics data
                if (update.data) {
                  state.realTimeData = {
                    ...state.realTimeData,
                    ...update.data,
                  };
                }
                break;
              case 'node_added':
              case 'node_removed':
              case 'node_updated':
                // Update graph data if we have it
                if (state.graphsData && update.data.node) {
                  // Update nodes in graph data
                  const nodeIndex = state.graphsData.nodes.findIndex(
                    n => n.id === update.data.node!.id
                  );
                  if (nodeIndex !== -1) {
                    if (update.type === 'node_removed') {
                      state.graphsData.nodes.splice(nodeIndex, 1);
                    } else {
                      state.graphsData.nodes[nodeIndex] = update.data.node!;
                    }
                  } else if (update.type === 'node_added') {
                    state.graphsData.nodes.push(update.data.node!);
                  }
                }
                break;
              case 'edge_added':
              case 'edge_removed':
              case 'edge_updated':
                // Update edges in graph data
                if (state.graphsData && update.data.edge) {
                  const edgeIndex = state.graphsData.edges.findIndex(
                    e => e.id === update.data.edge!.id
                  );
                  if (edgeIndex !== -1) {
                    if (update.type === 'edge_removed') {
                      state.graphsData.edges.splice(edgeIndex, 1);
                    } else {
                      state.graphsData.edges[edgeIndex] = update.data.edge!;
                    }
                  } else if (update.type === 'edge_added') {
                    state.graphsData.edges.push(update.data.edge!);
                  }
                }
                break;
            }
          });
        },

        // Visualization Management
        setVisualizationState: (newState) => {
          set((state) => {
            state.visualizationState = {
              ...state.visualizationState,
              ...newState,
            };
          });
        },

        selectWidget: (widgetId) => {
          set((state) => {
            state.selectedWidgets.add(widgetId);
          });
        },

        deselectWidget: (widgetId) => {
          set((state) => {
            state.selectedWidgets.delete(widgetId);
          });
        },

        clearWidgetSelection: () => {
          set((state) => {
            state.selectedWidgets.clear();
          });
        },

        // Export Management
        startExport: (format) => {
          set((state) => {
            state.exportProgress = {
              inProgress: true,
              progress: 0,
              format,
            };
          });
        },

        updateExportProgress: (progress) => {
          set((state) => {
            state.exportProgress.progress = progress;
          });
        },

        completeExport: () => {
          set((state) => {
            state.exportProgress = {
              inProgress: false,
              progress: 100,
            };
          });
        },

        // Utility Actions
        refreshDashboard: () => {
          set((state) => {
            // Clear cached data to trigger refresh
            state.metricsData = {};
            state.loading = {};
          });
        },

        resetStore: () => {
          set((state) => {
            // Reset all state to initial values
            state.activeDashboard = null;
            state.metricsData = {};
            state.graphsData = null;
            state.realTimeData = {};
            state.loading = {};
            state.errors = {};
            state.wsConnected = false;
            state.wsStatus = 'disconnected';
            state.subscriptions.clear();
            state.selectedWidgets.clear();
            state.exportProgress = {
              inProgress: false,
              progress: 0,
            };
          });
        },
      }))
    ),
    {
      name: 'analytics-store',
    }
  )
);

// Selectors for common use cases
export const useActiveDashboard = () => {
  return useAnalyticsStore((state) => {
    const dashboardId = state.activeDashboard;
    return dashboardId ? state.dashboards[dashboardId] : null;
  });
};

export const useDashboardWidgets = (dashboardId: string) => {
  return useAnalyticsStore((state) => {
    const dashboard = state.dashboards[dashboardId];
    return dashboard?.layout || [];
  });
};

export const useRealTimeConnection = () => {
  return useAnalyticsStore((state) => ({
    connected: state.wsConnected,
    status: state.wsStatus,
    subscriptions: Array.from(state.subscriptions),
  }));
};

export const useAnalyticsFilters = () => {
  return useAnalyticsStore((state) => ({
    timeRange: state.timeRange,
    filters: state.filters,
    graphFilters: state.graphFilters,
    setTimeRange: state.setTimeRange,
    setFilters: state.setFilters,
    setGraphFilters: state.setGraphFilters,
    clearFilters: state.clearFilters,
  }));
};