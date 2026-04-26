import { create } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';

// Types
export interface AnalyticsMetric {
  id: string;
  name: string;
  value: number | string;
  unit?: string;
  trend?: {
    direction: 'up' | 'down' | 'stable';
    percentage: number;
    period: string;
  };
  metadata?: Record<string, any>;
}

export interface TimeSeriesData {
  timestamp: string;
  value: number;
  metadata?: Record<string, any>;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
  position?: { x: number; y: number };
  color?: string;
  size?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, any>;
  weight?: number;
  color?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata: {
    totalNodes: number;
    totalEdges: number;
    lastUpdated: string;
  };
}

export interface Widget {
  id: string;
  type: 'metric' | 'chart' | 'graph' | 'table' | 'text';
  title: string;
  position: { x: number; y: number; width: number; height: number };
  config: Record<string, any>;
  data: any;
  lastUpdated: string;
  isRefreshing: boolean;
}

export interface Dashboard {
  id: string;
  name: string;
  description?: string;
  widgets: Widget[];
  layout: 'grid' | 'free';
  createdAt: string;
  updatedAt: string;
  isPublic: boolean;
  tags: string[];
}

export interface Report {
  id: string;
  name: string;
  type: 'summary' | 'detailed' | 'custom';
  schedule?: {
    frequency: 'daily' | 'weekly' | 'monthly';
    time: string;
    enabled: boolean;
  };
  format: 'pdf' | 'csv' | 'json';
  recipients: string[];
  lastGenerated?: string;
  nextRun?: string;
  template: string;
  config: Record<string, any>;
}

export interface AlertRule {
  id: string;
  name: string;
  metric: string;
  condition: 'greater_than' | 'less_than' | 'equals' | 'not_equals';
  threshold: number;
  enabled: boolean;
  channels: ('email' | 'webhook' | 'slack')[];
  lastTriggered?: string;
}

// Store State
interface AnalyticsState {
  // Loading and Error States
  isLoading: boolean;
  error: string | null;

  // Real-time Metrics
  metrics: Record<string, AnalyticsMetric>;
  timeSeriesData: Record<string, TimeSeriesData[]>;

  // Graph Data
  graphData: GraphData | null;
  selectedNodes: string[];
  selectedEdges: string[];
  graphFilters: {
    nodeTypes: string[];
    edgeTypes: string[];
    timeRange: { start: string; end: string };
    searchQuery: string;
  };

  // Dashboards
  dashboards: Dashboard[];
  activeDashboard: string | null;
  activeWidgets: Record<string, Widget>;

  // Reports
  reports: Report[];
  isGeneratingReport: boolean;

  // Alerts
  alertRules: AlertRule[];
  activeAlerts: any[];

  // UI State
  sidebarCollapsed: boolean;
  theme: 'light' | 'dark' | 'system';
  refreshInterval: number;
  autoRefresh: boolean;

  // WebSocket Connection
  isConnected: boolean;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
}

// Store Actions
interface AnalyticsActions {
  // Loading and Error Management
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;

  // Metrics Management
  updateMetric: (metricId: string, metric: AnalyticsMetric) => void;
  updateMetrics: (metrics: Record<string, AnalyticsMetric>) => void;
  addTimeSeriesData: (metricId: string, data: TimeSeriesData[]) => void;
  clearTimeSeriesData: (metricId: string) => void;

  // Graph Management
  setGraphData: (data: GraphData) => void;
  updateGraphNode: (nodeId: string, updates: Partial<GraphNode>) => void;
  updateGraphEdge: (edgeId: string, updates: Partial<GraphEdge>) => void;
  selectNodes: (nodeIds: string[]) => void;
  selectEdges: (edgeIds: string[]) => void;
  clearSelection: () => void;
  updateGraphFilters: (filters: Partial<AnalyticsState['graphFilters']>) => void;
  resetGraphFilters: () => void;

  // Dashboard Management
  setDashboards: (dashboards: Dashboard[]) => void;
  createDashboard: (dashboard: Omit<Dashboard, 'id' | 'createdAt' | 'updatedAt'>) => void;
  updateDashboard: (dashboardId: string, updates: Partial<Dashboard>) => void;
  deleteDashboard: (dashboardId: string) => void;
  setActiveDashboard: (dashboardId: string | null) => void;
  duplicateDashboard: (dashboardId: string, newName: string) => void;

  // Widget Management
  addWidget: (dashboardId: string, widget: Omit<Widget, 'id' | 'lastUpdated' | 'isRefreshing'>) => void;
  updateWidget: (widgetId: string, updates: Partial<Widget>) => void;
  removeWidget: (widgetId: string) => void;
  moveWidget: (widgetId: string, position: { x: number; y: number; width: number; height: number }) => void;
  refreshWidget: (widgetId: string) => void;
  setWidgetData: (widgetId: string, data: any) => void;

  // Report Management
  setReports: (reports: Report[]) => void;
  createReport: (report: Omit<Report, 'id'>) => void;
  updateReport: (reportId: string, updates: Partial<Report>) => void;
  deleteReport: (reportId: string) => void;
  generateReport: (reportId: string) => Promise<void>;
  setGeneratingReport: (generating: boolean) => void;

  // Alert Management
  setAlertRules: (rules: AlertRule[]) => void;
  createAlertRule: (rule: Omit<AlertRule, 'id'>) => void;
  updateAlertRule: (ruleId: string, updates: Partial<AlertRule>) => void;
  deleteAlertRule: (ruleId: string) => void;
  toggleAlertRule: (ruleId: string) => void;
  setActiveAlerts: (alerts: any[]) => void;

  // UI Management
  toggleSidebar: () => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
  setRefreshInterval: (interval: number) => void;
  toggleAutoRefresh: () => void;

  // WebSocket Management
  setConnected: (connected: boolean) => void;
  setConnectionStatus: (status: AnalyticsState['connectionStatus']) => void;

  // Data Refresh
  refreshAllData: () => Promise<void>;
  resetStore: () => void;
}

// Initial State
const initialState: AnalyticsState = {
  isLoading: false,
  error: null,
  metrics: {},
  timeSeriesData: {},
  graphData: null,
  selectedNodes: [],
  selectedEdges: [],
  graphFilters: {
    nodeTypes: [],
    edgeTypes: [],
    timeRange: {
      start: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
      end: new Date().toISOString(),
    },
    searchQuery: '',
  },
  dashboards: [],
  activeDashboard: null,
  activeWidgets: {},
  reports: [],
  isGeneratingReport: false,
  alertRules: [],
  activeAlerts: [],
  sidebarCollapsed: false,
  theme: 'system',
  refreshInterval: 30000, // 30 seconds
  autoRefresh: true,
  isConnected: false,
  connectionStatus: 'disconnected',
};

// Create Store
export const useAnalyticsStore = create<AnalyticsState & AnalyticsActions>()(
  devtools(
    subscribeWithSelector((set, get) => ({
      ...initialState,

      // Loading and Error Management
      setLoading: (loading) => set({ isLoading: loading }, false, 'setLoading'),
      setError: (error) => set({ error }, false, 'setError'),
      clearError: () => set({ error: null }, false, 'clearError'),

      // Metrics Management
      updateMetric: (metricId, metric) =>
        set(
          (state) => ({
            metrics: { ...state.metrics, [metricId]: metric },
          }),
          false,
          'updateMetric'
        ),
      updateMetrics: (metrics) =>
        set(
          (state) => ({
            metrics: { ...state.metrics, ...metrics },
          }),
          false,
          'updateMetrics'
        ),
      addTimeSeriesData: (metricId, data) =>
        set(
          (state) => ({
            timeSeriesData: {
              ...state.timeSeriesData,
              [metricId]: [...(state.timeSeriesData[metricId] || []), ...data],
            },
          }),
          false,
          'addTimeSeriesData'
        ),
      clearTimeSeriesData: (metricId) =>
        set(
          (state) => {
            const newTimeSeriesData = { ...state.timeSeriesData };
            delete newTimeSeriesData[metricId];
            return { timeSeriesData: newTimeSeriesData };
          },
          false,
          'clearTimeSeriesData'
        ),

      // Graph Management
      setGraphData: (data) => set({ graphData: data }, false, 'setGraphData'),
      updateGraphNode: (nodeId, updates) =>
        set(
          (state) => {
            if (!state.graphData) return state;
            return {
              graphData: {
                ...state.graphData,
                nodes: state.graphData.nodes.map((node) =>
                  node.id === nodeId ? { ...node, ...updates } : node
                ),
              },
            };
          },
          false,
          'updateGraphNode'
        ),
      updateGraphEdge: (edgeId, updates) =>
        set(
          (state) => {
            if (!state.graphData) return state;
            return {
              graphData: {
                ...state.graphData,
                edges: state.graphData.edges.map((edge) =>
                  edge.id === edgeId ? { ...edge, ...updates } : edge
                ),
              },
            };
          },
          false,
          'updateGraphEdge'
        ),
      selectNodes: (nodeIds) => set({ selectedNodes: nodeIds }, false, 'selectNodes'),
      selectEdges: (edgeIds) => set({ selectedEdges: edgeIds }, false, 'selectEdges'),
      clearSelection: () =>
        set({ selectedNodes: [], selectedEdges: [] }, false, 'clearSelection'),
      updateGraphFilters: (filters) =>
        set(
          (state) => ({
            graphFilters: { ...state.graphFilters, ...filters },
          }),
          false,
          'updateGraphFilters'
        ),
      resetGraphFilters: () =>
        set({ graphFilters: initialState.graphFilters }, false, 'resetGraphFilters'),

      // Dashboard Management
      setDashboards: (dashboards) => set({ dashboards }, false, 'setDashboards'),
      createDashboard: (dashboard) =>
        set(
          (state) => {
            const newDashboard: Dashboard = {
              ...dashboard,
              id: `dashboard_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            };
            return {
              dashboards: [...state.dashboards, newDashboard],
            };
          },
          false,
          'createDashboard'
        ),
      updateDashboard: (dashboardId, updates) =>
        set(
          (state) => ({
            dashboards: state.dashboards.map((dashboard) =>
              dashboard.id === dashboardId
                ? { ...dashboard, ...updates, updatedAt: new Date().toISOString() }
                : dashboard
            ),
          }),
          false,
          'updateDashboard'
        ),
      deleteDashboard: (dashboardId) =>
        set(
          (state) => ({
            dashboards: state.dashboards.filter((dashboard) => dashboard.id !== dashboardId),
            activeDashboard: state.activeDashboard === dashboardId ? null : state.activeDashboard,
          }),
          false,
          'deleteDashboard'
        ),
      setActiveDashboard: (dashboardId) => set({ activeDashboard: dashboardId }, false, 'setActiveDashboard'),
      duplicateDashboard: (dashboardId, newName) =>
        set(
          (state) => {
            const originalDashboard = state.dashboards.find((d) => d.id === dashboardId);
            if (!originalDashboard) return state;

            const duplicatedDashboard: Dashboard = {
              ...originalDashboard,
              id: `dashboard_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              name: newName,
              widgets: originalDashboard.widgets.map((widget) => ({
                ...widget,
                id: `widget_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              })),
              createdAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            };

            return {
              dashboards: [...state.dashboards, duplicatedDashboard],
            };
          },
          false,
          'duplicateDashboard'
        ),

      // Widget Management
      addWidget: (dashboardId, widget) =>
        set(
          (state) => {
            const newWidget: Widget = {
              ...widget,
              id: `widget_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
              lastUpdated: new Date().toISOString(),
              isRefreshing: false,
            };

            const updatedDashboards = state.dashboards.map((dashboard) =>
              dashboard.id === dashboardId
                ? { ...dashboard, widgets: [...dashboard.widgets, newWidget], updatedAt: new Date().toISOString() }
                : dashboard
            );

            const updatedActiveWidgets = { ...state.activeWidgets, [newWidget.id]: newWidget };

            return {
              dashboards: updatedDashboards,
              activeWidgets: updatedActiveWidgets,
            };
          },
          false,
          'addWidget'
        ),
      updateWidget: (widgetId, updates) =>
        set(
          (state) => {
            const updatedActiveWidgets = {
              ...state.activeWidgets,
              [widgetId]: { ...state.activeWidgets[widgetId], ...updates },
            };

            const updatedDashboards = state.dashboards.map((dashboard) => ({
              ...dashboard,
              widgets: dashboard.widgets.map((widget) =>
                widget.id === widgetId
                  ? { ...widget, ...updates, lastUpdated: new Date().toISOString() }
                  : widget
              ),
            }));

            return {
              activeWidgets: updatedActiveWidgets,
              dashboards: updatedDashboards,
            };
          },
          false,
          'updateWidget'
        ),
      removeWidget: (widgetId) =>
        set(
          (state) => {
            const updatedActiveWidgets = { ...state.activeWidgets };
            delete updatedActiveWidgets[widgetId];

            const updatedDashboards = state.dashboards.map((dashboard) => ({
              ...dashboard,
              widgets: dashboard.widgets.filter((widget) => widget.id !== widgetId),
            }));

            return {
              activeWidgets: updatedActiveWidgets,
              dashboards: updatedDashboards,
            };
          },
          false,
          'removeWidget'
        ),
      moveWidget: (widgetId, position) =>
        set(
          (state) => {
            const updatedActiveWidgets = {
              ...state.activeWidgets,
              [widgetId]: { ...state.activeWidgets[widgetId], position },
            };

            const updatedDashboards = state.dashboards.map((dashboard) => ({
              ...dashboard,
              widgets: dashboard.widgets.map((widget) =>
                widget.id === widgetId ? { ...widget, position } : widget
              ),
            }));

            return {
              activeWidgets: updatedActiveWidgets,
              dashboards: updatedDashboards,
            };
          },
          false,
          'moveWidget'
        ),
      refreshWidget: (widgetId) =>
        set(
          (state) => {
            const updatedActiveWidgets = {
              ...state.activeWidgets,
              [widgetId]: { ...state.activeWidgets[widgetId], isRefreshing: true },
            };

            return { activeWidgets: updatedActiveWidgets };
          },
          false,
          'refreshWidget'
        ),
      setWidgetData: (widgetId, data) =>
        set(
          (state) => {
            const updatedActiveWidgets = {
              ...state.activeWidgets,
              [widgetId]: {
                ...state.activeWidgets[widgetId],
                data,
                isRefreshing: false,
                lastUpdated: new Date().toISOString(),
              },
            };

            return { activeWidgets: updatedActiveWidgets };
          },
          false,
          'setWidgetData'
        ),

      // Report Management
      setReports: (reports) => set({ reports }, false, 'setReports'),
      createReport: (report) =>
        set(
          (state) => ({
            reports: [
              ...state.reports,
              { ...report, id: `report_${Date.now()}_${Math.random().toString(36).substr(2, 9)}` },
            ],
          }),
          false,
          'createReport'
        ),
      updateReport: (reportId, updates) =>
        set(
          (state) => ({
            reports: state.reports.map((report) =>
              report.id === reportId ? { ...report, ...updates } : report
            ),
          }),
          false,
          'updateReport'
        ),
      deleteReport: (reportId) =>
        set(
          (state) => ({
            reports: state.reports.filter((report) => report.id !== reportId),
          }),
          false,
          'deleteReport'
        ),
      generateReport: async (reportId) => {
        const { setGeneratingReport } = get();
        setGeneratingReport(true);
        try {
          // Implementation would call API service
          console.log('Generating report:', reportId);
        } finally {
          setGeneratingReport(false);
        }
      },
      setGeneratingReport: (generating) => set({ isGeneratingReport: generating }, false, 'setGeneratingReport'),

      // Alert Management
      setAlertRules: (rules) => set({ alertRules: rules }, false, 'setAlertRules'),
      createAlertRule: (rule) =>
        set(
          (state) => ({
            alertRules: [
              ...state.alertRules,
              { ...rule, id: `alert_${Date.now()}_${Math.random().toString(36).substr(2, 9)}` },
            ],
          }),
          false,
          'createAlertRule'
        ),
      updateAlertRule: (ruleId, updates) =>
        set(
          (state) => ({
            alertRules: state.alertRules.map((rule) =>
              rule.id === ruleId ? { ...rule, ...updates } : rule
            ),
          }),
          false,
          'updateAlertRule'
        ),
      deleteAlertRule: (ruleId) =>
        set(
          (state) => ({
            alertRules: state.alertRules.filter((rule) => rule.id !== ruleId),
          }),
          false,
          'deleteAlertRule'
        ),
      toggleAlertRule: (ruleId) =>
        set(
          (state) => ({
            alertRules: state.alertRules.map((rule) =>
              rule.id === ruleId ? { ...rule, enabled: !rule.enabled } : rule
            ),
          }),
          false,
          'toggleAlertRule'
        ),
      setActiveAlerts: (alerts) => set({ activeAlerts: alerts }, false, 'setActiveAlerts'),

      // UI Management
      toggleSidebar: () =>
        set(
          (state) => ({ sidebarCollapsed: !state.sidebarCollapsed }),
          false,
          'toggleSidebar'
        ),
      setTheme: (theme) => set({ theme }, false, 'setTheme'),
      setRefreshInterval: (interval) => set({ refreshInterval: interval }, false, 'setRefreshInterval'),
      toggleAutoRefresh: () =>
        set(
          (state) => ({ autoRefresh: !state.autoRefresh }),
          false,
          'toggleAutoRefresh'
        ),

      // WebSocket Management
      setConnected: (connected) => set({ isConnected: connected }, false, 'setConnected'),
      setConnectionStatus: (status) => set({ connectionStatus: status }, false, 'setConnectionStatus'),

      // Data Refresh
      refreshAllData: async () => {
        const { setLoading } = get();
        setLoading(true);
        try {
          // Implementation would call various API services
          console.log('Refreshing all analytics data');
        } finally {
          setLoading(false);
        }
      },

      // Reset Store
      resetStore: () => set(initialState, false, 'resetStore'),
    })),
    {
      name: 'analytics-store',
    }
  )
);