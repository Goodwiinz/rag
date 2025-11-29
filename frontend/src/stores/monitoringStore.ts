/**
 * Zustand store for monitoring system state management
 * Handles all monitoring-related state including metrics, alerts, and dashboard configuration
 */

import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import {
  SystemHealthScore,
  PerformanceMetrics,
  BusinessMetrics,
  InfrastructureMetrics,
  Alert,
  AlertHistory,
  UserAnalytics,
  DashboardConfig,
  TimeRange,
  TimeRangePreset,
  LoadingState,
  RealTimeUpdate,
  MonitoringIntegration
} from '@/types/monitoring';

// ============================================================================
// STATE INTERFACES
// ============================================================================

interface MonitoringState {
  // System Overview
  systemHealth: SystemHealthScore | null;
  systemHealthLoading: LoadingState;

  // Performance Metrics
  performanceMetrics: PerformanceMetrics | null;
  performanceLoading: LoadingState;
  performanceTimeRange: TimeRange;

  // Business Metrics
  businessMetrics: BusinessMetrics | null;
  businessLoading: LoadingState;
  businessTimeRange: TimeRange;

  // Infrastructure Metrics
  infrastructureMetrics: InfrastructureMetrics | null;
  infrastructureLoading: LoadingState;

  // Alerts
  activeAlerts: Alert[];
  alertHistory: AlertHistory | null;
  alertsLoading: LoadingState;
  acknowledgedAlerts: Set<string>;

  // User Analytics
  userAnalytics: UserAnalytics | null;
  userAnalyticsLoading: LoadingState;
  userAnalyticsTimeRange: TimeRange;

  // Dashboard Configuration
  dashboardConfigs: Record<string, DashboardConfig>;
  activeDashboardId: string | null;
  dashboardLayout: {
    isEditing: boolean;
    draggedWidget: string | null;
  };

  // Real-time Updates
  realTimeUpdates: RealTimeUpdate[];
  isRealTimeConnected: boolean;
  lastRealTimeUpdate: string | null;

  // Integrations
  integrations: MonitoringIntegration[];
  integrationsLoading: LoadingState;

  // UI State
  selectedTimeRange: TimeRange;
  globalFilters: Record<string, any>;
  autoRefresh: boolean;
  refreshInterval: number;
  notifications: {
    show: boolean;
    message: string;
    type: 'success' | 'error' | 'warning' | 'info';
  }[];

  // Actions
  updateSystemHealth: (health: SystemHealthScore) => void;
  updatePerformanceMetrics: (metrics: PerformanceMetrics) => void;
  updateBusinessMetrics: (metrics: BusinessMetrics) => void;
  updateInfrastructureMetrics: (metrics: InfrastructureMetrics) => void;
  updateActiveAlerts: (alerts: Alert[]) => void;
  updateAlertHistory: (history: AlertHistory) => void;
  updateUserAnalytics: (analytics: UserAnalytics) => void;

  // Alert Actions
  acknowledgeAlert: (alertId: string) => void;
  resolveAlert: (alertId: string, resolvedBy?: string) => void;
  suppressAlert: (alertId: string, durationMinutes: number) => void;
  unacknowledgeAlert: (alertId: string) => void;

  // Dashboard Actions
  setActiveDashboard: (dashboardId: string) => void;
  updateDashboardConfig: (dashboardId: string, config: Partial<DashboardConfig>) => void;
  createDashboard: (config: DashboardConfig) => void;
  deleteDashboard: (dashboardId: string) => void;
  toggleEditMode: () => void;
  setDraggedWidget: (widgetId: string | null) => void;

  // Time Range Actions
  setTimeRange: (timeRange: TimeRange, scope?: 'performance' | 'business' | 'userAnalytics' | 'global') => void;
  setPresetTimeRange: (preset: TimeRangePreset) => void;
  setTimeRangeForScope: (scope: string, timeRange: TimeRange) => void;

  // Real-time Actions
  addRealTimeUpdate: (update: RealTimeUpdate) => void;
  clearRealTimeUpdates: () => void;
  setRealTimeConnection: (connected: boolean) => void;

  // Integration Actions
  updateIntegrations: (integrations: MonitoringIntegration[]) => void;
  toggleIntegration: (integrationId: string) => void;
  updateIntegrationConfig: (integrationId: string, config: any) => void;

  // UI Actions
  setGlobalFilters: (filters: Record<string, any>) => void;
  updateGlobalFilter: (key: string, value: any) => void;
  clearGlobalFilters: () => void;
  toggleAutoRefresh: () => void;
  setRefreshInterval: (interval: number) => void;

  // Notification Actions
  showNotification: (message: string, type?: 'success' | 'error' | 'warning' | 'info') => void;
  clearNotifications: () => void;
  dismissNotification: (index: number) => void;

  // Loading Actions
  setLoading: (key: string, loading: boolean, error?: string) => void;
  clearAllLoading: () => void;

  // Reset Actions
  resetState: () => void;
}

// ============================================================================
// INITIAL STATE
// ============================================================================

const getInitialTimeRange = (): TimeRange => ({
  start: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
  end: new Date().toISOString(),
  preset: '24h'
});

const initialState: Omit<MonitoringState, 'updateSystemHealth' | 'updatePerformanceMetrics' | 'updateBusinessMetrics' | 'updateInfrastructureMetrics' | 'updateActiveAlerts' | 'updateAlertHistory' | 'updateUserAnalytics' | 'acknowledgeAlert' | 'resolveAlert' | 'suppressAlert' | 'unacknowledgeAlert' | 'setActiveDashboard' | 'updateDashboardConfig' | 'createDashboard' | 'deleteDashboard' | 'toggleEditMode' | 'setDraggedWidget' | 'setTimeRange' | 'setPresetTimeRange' | 'setTimeRangeForScope' | 'addRealTimeUpdate' | 'clearRealTimeUpdates' | 'setRealTimeConnection' | 'updateIntegrations' | 'toggleIntegration' | 'updateIntegrationConfig' | 'setGlobalFilters' | 'updateGlobalFilter' | 'clearGlobalFilters' | 'toggleAutoRefresh' | 'setRefreshInterval' | 'showNotification' | 'clearNotifications' | 'dismissNotification' | 'setLoading' | 'clearAllLoading' | 'resetState'> = {
  // System Overview
  systemHealth: null,
  systemHealthLoading: { loading: false },

  // Performance Metrics
  performanceMetrics: null,
  performanceLoading: { loading: false },
  performanceTimeRange: getInitialTimeRange(),

  // Business Metrics
  businessMetrics: null,
  businessLoading: { loading: false },
  businessTimeRange: getInitialTimeRange(),

  // Infrastructure Metrics
  infrastructureMetrics: null,
  infrastructureLoading: { loading: false },

  // Alerts
  activeAlerts: [],
  alertHistory: null,
  alertsLoading: { loading: false },
  acknowledgedAlerts: new Set(),

  // User Analytics
  userAnalytics: null,
  userAnalyticsLoading: { loading: false },
  userAnalyticsTimeRange: getInitialTimeRange(),

  // Dashboard Configuration
  dashboardConfigs: {},
  activeDashboardId: null,
  dashboardLayout: {
    isEditing: false,
    draggedWidget: null,
  },

  // Real-time Updates
  realTimeUpdates: [],
  isRealTimeConnected: false,
  lastRealTimeUpdate: null,

  // Integrations
  integrations: [],
  integrationsLoading: { loading: false },

  // UI State
  selectedTimeRange: getInitialTimeRange(),
  globalFilters: {},
  autoRefresh: true,
  refreshInterval: 30000, // 30 seconds
  notifications: [],
};

// ============================================================================
// STORE CREATION
// ============================================================================

export const useMonitoringStore = create<MonitoringState>()(
  subscribeWithSelector((set, get) => ({
    ...initialState,

    // System Health Actions
    updateSystemHealth: (health) => {
      set((state) => ({
        systemHealth: health,
        systemHealthLoading: {
          loading: false,
          last_updated: new Date().toISOString()
        }
      }));
    },

    // Performance Metrics Actions
    updatePerformanceMetrics: (metrics) => {
      set((state) => ({
        performanceMetrics: metrics,
        performanceLoading: {
          loading: false,
          last_updated: new Date().toISOString()
        }
      }));
    },

    // Business Metrics Actions
    updateBusinessMetrics: (metrics) => {
      set((state) => ({
        businessMetrics: metrics,
        businessLoading: {
          loading: false,
          last_updated: new Date().toISOString()
        }
      }));
    },

    // Infrastructure Metrics Actions
    updateInfrastructureMetrics: (metrics) => {
      set((state) => ({
        infrastructureMetrics: metrics,
        infrastructureLoading: {
          loading: false,
          last_updated: new Date().toISOString()
        }
      }));
    },

    // Alert Actions
    updateActiveAlerts: (alerts) => {
      set((state) => {
        // Filter out acknowledged alerts that are no longer active
        const filteredAlerts = alerts.filter(alert =>
          !state.acknowledgedAlerts.has(alert.id) || alert.status === 'active'
        );
        return {
          activeAlerts: filteredAlerts,
          alertsLoading: {
            loading: false,
            last_updated: new Date().toISOString()
          }
        };
      });
    },

    updateAlertHistory: (history) => {
      set((state) => ({
        alertHistory: history,
        alertsLoading: {
          loading: false,
          last_updated: new Date().toISOString()
        }
      }));
    },

    acknowledgeAlert: (alertId) => {
      set((state) => ({
        acknowledgedAlerts: new Set([...state.acknowledgedAlerts, alertId])
      }));
    },

    resolveAlert: (alertId, resolvedBy) => {
      set((state) => ({
        activeAlerts: state.activeAlerts.map(alert =>
          alert.id === alertId
            ? { ...alert, status: 'resolved', resolved_at: new Date().toISOString(), resolved_by: resolvedBy }
            : alert
        ),
        acknowledgedAlerts: new Set([...state.acknowledgedAlerts].filter(id => id !== alertId))
      }));
    },

    suppressAlert: (alertId, durationMinutes) => {
      set((state) => ({
        activeAlerts: state.activeAlerts.map(alert =>
          alert.id === alertId
            ? { ...alert, status: 'suppressed' as const }
            : alert
        )
      }));
    },

    unacknowledgeAlert: (alertId) => {
      set((state) => {
        const newAcknowledged = new Set(state.acknowledgedAlerts);
        newAcknowledged.delete(alertId);
        return { acknowledgedAlerts: newAcknowledged };
      });
    },

    updateUserAnalytics: (analytics) => {
      set((state) => ({
        userAnalytics: analytics,
        userAnalyticsLoading: {
          loading: false,
          last_updated: new Date().toISOString()
        }
      }));
    },

    // Dashboard Actions
    setActiveDashboard: (dashboardId) => {
      set({ activeDashboardId: dashboardId });
    },

    updateDashboardConfig: (dashboardId, config) => {
      set((state) => ({
        dashboardConfigs: {
          ...state.dashboardConfigs,
          [dashboardId]: {
            ...state.dashboardConfigs[dashboardId],
            ...config
          }
        }
      }));
    },

    createDashboard: (config) => {
      set((state) => ({
        dashboardConfigs: {
          ...state.dashboardConfigs,
          [config.id]: config
        }
      }));
    },

    deleteDashboard: (dashboardId) => {
      set((state) => {
        const newConfigs = { ...state.dashboardConfigs };
        delete newConfigs[dashboardId];
        return {
          dashboardConfigs: newConfigs,
          activeDashboardId: state.activeDashboardId === dashboardId ? null : state.activeDashboardId
        };
      });
    },

    toggleEditMode: () => {
      set((state) => ({
        dashboardLayout: {
          ...state.dashboardLayout,
          isEditing: !state.dashboardLayout.isEditing
        }
      }));
    },

    setDraggedWidget: (widgetId) => {
      set((state) => ({
        dashboardLayout: {
          ...state.dashboardLayout,
          draggedWidget: widgetId
        }
      }));
    },

    // Time Range Actions
    setTimeRange: (timeRange, scope = 'global') => {
      set((state) => {
        const updates: Partial<MonitoringState> = {};

        switch (scope) {
          case 'performance':
            updates.performanceTimeRange = timeRange;
            break;
          case 'business':
            updates.businessTimeRange = timeRange;
            break;
          case 'userAnalytics':
            updates.userAnalyticsTimeRange = timeRange;
            break;
          case 'global':
          default:
            updates.selectedTimeRange = timeRange;
            updates.performanceTimeRange = timeRange;
            updates.businessTimeRange = timeRange;
            updates.userAnalyticsTimeRange = timeRange;
            break;
        }

        return updates;
      });
    },

    setPresetTimeRange: (preset) => {
      const now = new Date();
      let start: Date;

      switch (preset) {
        case '1h':
          start = new Date(now.getTime() - 60 * 60 * 1000);
          break;
        case '6h':
          start = new Date(now.getTime() - 6 * 60 * 60 * 1000);
          break;
        case '24h':
          start = new Date(now.getTime() - 24 * 60 * 60 * 1000);
          break;
        case '7d':
          start = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
          break;
        case '30d':
          start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
          break;
        case '90d':
          start = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
          break;
        default:
          start = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      }

      const timeRange: TimeRange = {
        start: start.toISOString(),
        end: now.toISOString(),
        preset
      };

      get().setTimeRange(timeRange, 'global');
    },

    setTimeRangeForScope: (scope, timeRange) => {
      get().setTimeRange(timeRange, scope);
    },

    // Real-time Actions
    addRealTimeUpdate: (update) => {
      set((state) => ({
        realTimeUpdates: [...state.realTimeUpdates.slice(-99), update], // Keep last 100 updates
        lastRealTimeUpdate: update.timestamp
      }));
    },

    clearRealTimeUpdates: () => {
      set({
        realTimeUpdates: [],
        lastRealTimeUpdate: null
      });
    },

    setRealTimeConnection: (connected) => {
      set({ isRealTimeConnected: connected });
    },

    // Integration Actions
    updateIntegrations: (integrations) => {
      set({
        integrations,
        integrationsLoading: {
          loading: false,
          last_updated: new Date().toISOString()
        }
      });
    },

    toggleIntegration: (integrationId) => {
      set((state) => ({
        integrations: state.integrations.map(integration =>
          integration.id === integrationId
            ? { ...integration, enabled: !integration.enabled }
            : integration
        )
      }));
    },

    updateIntegrationConfig: (integrationId, config) => {
      set((state) => ({
        integrations: state.integrations.map(integration =>
          integration.id === integrationId
            ? { ...integration, config: { ...integration.config, ...config } }
            : integration
        )
      }));
    },

    // UI Actions
    setGlobalFilters: (filters) => {
      set({ globalFilters: filters });
    },

    updateGlobalFilter: (key, value) => {
      set((state) => ({
        globalFilters: {
          ...state.globalFilters,
          [key]: value
        }
      }));
    },

    clearGlobalFilters: () => {
      set({ globalFilters: {} });
    },

    toggleAutoRefresh: () => {
      set((state) => ({ autoRefresh: !state.autoRefresh }));
    },

    setRefreshInterval: (interval) => {
      set({ refreshInterval: interval });
    },

    // Notification Actions
    showNotification: (message, type = 'info') => {
      set((state) => ({
        notifications: [...state.notifications, { show: true, message, type }]
      }));
    },

    clearNotifications: () => {
      set({ notifications: [] });
    },

    dismissNotification: (index) => {
      set((state) => ({
        notifications: state.notifications.filter((_, i) => i !== index)
      }));
    },

    // Loading Actions
    setLoading: (key, loading, error) => {
      set((state) => ({
        [`${key}Loading`]: {
          loading,
          error: error || undefined,
          last_updated: loading ? undefined : new Date().toISOString()
        }
      }));
    },

    clearAllLoading: () => {
      set({
        systemHealthLoading: { loading: false },
        performanceLoading: { loading: false },
        businessLoading: { loading: false },
        infrastructureLoading: { loading: false },
        alertsLoading: { loading: false },
        userAnalyticsLoading: { loading: false },
        integrationsLoading: { loading: false },
      });
    },

    // Reset Actions
    resetState: () => {
      set(initialState);
    }
  }))
);

// ============================================================================
// SELECTOR HOOKS
// ============================================================================

// System Overview Selectors
export const useSystemHealth = () => useMonitoringStore((state) => state.systemHealth);
export const useSystemHealthLoading = () => useMonitoringStore((state) => state.systemHealthLoading);

// Performance Selectors
export const usePerformanceMetrics = () => useMonitoringStore((state) => state.performanceMetrics);
export const usePerformanceLoading = () => useMonitoringStore((state) => state.performanceLoading);
export const usePerformanceTimeRange = () => useMonitoringStore((state) => state.performanceTimeRange);

// Business Selectors
export const useBusinessMetrics = () => useMonitoringStore((state) => state.businessMetrics);
export const useBusinessLoading = () => useMonitoringStore((state) => state.businessLoading);
export const useBusinessTimeRange = () => useMonitoringStore((state) => state.businessTimeRange);

// Infrastructure Selectors
export const useInfrastructureMetrics = () => useMonitoringStore((state) => state.infrastructureMetrics);
export const useInfrastructureLoading = () => useMonitoringStore((state) => state.infrastructureLoading);

// Alert Selectors
export const useActiveAlerts = () => useMonitoringStore((state) => state.activeAlerts);
export const useAlertHistory = () => useMonitoringStore((state) => state.alertHistory);
export const useAlertsLoading = () => useMonitoringStore((state) => state.alertsLoading);
export const useAcknowledgedAlerts = () => useMonitoringStore((state) => state.acknowledgedAlerts);

// User Analytics Selectors
export const useUserAnalytics = () => useMonitoringStore((state) => state.userAnalytics);
export const useUserAnalyticsLoading = () => useMonitoringStore((state) => state.userAnalyticsLoading);
export const useUserAnalyticsTimeRange = () => useMonitoringStore((state) => state.userAnalyticsTimeRange);

// Dashboard Selectors
export const useDashboardConfigs = () => useMonitoringStore((state) => state.dashboardConfigs);
export const useActiveDashboardId = () => useMonitoringStore((state) => state.activeDashboardId);
export const useActiveDashboard = () => useMonitoringStore((state) =>
  state.activeDashboardId ? state.dashboardConfigs[state.activeDashboardId] : null
);
export const useDashboardLayout = () => useMonitoringStore((state) => state.dashboardLayout);

// Real-time Selectors
export const useRealTimeUpdates = () => useMonitoringStore((state) => state.realTimeUpdates);
export const useRealTimeConnection = () => useMonitoringStore((state) => state.isRealTimeConnected);
export const useLastRealTimeUpdate = () => useMonitoringStore((state) => state.lastRealTimeUpdate);

// Integration Selectors
export const useIntegrations = () => useMonitoringStore((state) => state.integrations);
export const useIntegrationsLoading = () => useMonitoringStore((state) => state.integrationsLoading);

// UI Selectors
export const useSelectedTimeRange = () => useMonitoringStore((state) => state.selectedTimeRange);
export const useGlobalFilters = () => useMonitoringStore((state) => state.globalFilters);
export const useAutoRefresh = () => useMonitoringStore((state) => state.autoRefresh);
export const useRefreshInterval = () => useMonitoringStore((state) => state.refreshInterval);
export const useNotifications = () => useMonitoringStore((state) => state.notifications);

// Computed Selectors
export const useCriticalAlerts = () => useMonitoringStore((state) =>
  state.activeAlerts.filter(alert => alert.severity === 'critical' && alert.status === 'active')
);
export const useWarningAlerts = () => useMonitoringStore((state) =>
  state.activeAlerts.filter(alert => alert.severity === 'warning' && alert.status === 'active')
);
export const useActiveAlertsCount = () => useMonitoringStore((state) =>
  state.activeAlerts.filter(alert => alert.status === 'active').length
);
export const useUnacknowledgedAlerts = () => useMonitoringStore((state) =>
  state.activeAlerts.filter(alert =>
    alert.status === 'active' && !state.acknowledgedAlerts.has(alert.id)
  )
);

// Export default store
export default useMonitoringStore;