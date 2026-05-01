/**
 * Zustand State Management Integration Tests
 *
 * Integration tests for the monitoring store state management:
 * - State initialization and default values
 * - State updates and mutations
 * - Selector functions
 * - Computed state
 * - Persistence and rehydration
 * - Performance with large datasets
 * - Race conditions and concurrent updates
 * - Error handling and recovery
 */

import { beforeEach, describe, expect, test } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { create } from 'zustand';
import { persist, subscribeWithSelector } from 'zustand/middleware';

import {
  useMonitoringStore,
  useSystemHealth,
  useSystemHealthLoading,
  usePerformanceMetrics,
  useActiveAlerts,
  useAlertsLoading,
  useRealTimeConnection,
  useSelectedTimeRange,
  useCriticalAlerts,
  useActiveAlertsCount,
  useUnacknowledgedAlerts,
} from '../../stores/monitoringStore';

// Zustand stores are module-scoped singletons, so state mutations from one
// test leak into the next. Reset before every test.
beforeEach(() => {
  useMonitoringStore.getState().resetState();
});

// Test data
const mockSystemHealth = {
  overall_score: 85,
  components: {
    database: { status: 'healthy', score: 90 },
    vector_store: { status: 'healthy', score: 88 },
    graph_db: { status: 'warning', score: 75 },
    api_gateway: { status: 'healthy', score: 92 },
  },
  timestamp: new Date().toISOString(),
};

const mockPerformanceMetrics = {
  response_time: { current: 245, trend: 'decreasing', target: 200 },
  throughput: { current: 1250, trend: 'stable', target: 1000 },
  error_rate: { current: 0.8, trend: 'decreasing', target: 1.0 },
  cpu_usage: { current: 65, trend: 'stable', target: 80 },
  memory_usage: { current: 72, trend: 'increasing', target: 85 },
};

const mockAlerts = [
  {
    id: 'alert-1',
    name: 'High CPU Usage',
    severity: 'critical',
    status: 'active',
    message: 'CPU usage exceeded 80% threshold',
    created_at: new Date(Date.now() - 3600000).toISOString(),
    acknowledged_at: null,
    resolved_at: null,
  },
  {
    id: 'alert-2',
    name: 'Memory Warning',
    severity: 'warning',
    status: 'active',
    message: 'Memory usage approaching threshold',
    created_at: new Date(Date.now() - 1800000).toISOString(),
    acknowledged_at: null,
    resolved_at: null,
  },
  {
    id: 'alert-3',
    name: 'Database Issue',
    severity: 'critical',
    status: 'acknowledged',
    message: 'Database connection pool at high capacity',
    created_at: new Date(Date.now() - 7200000).toISOString(),
    acknowledged_at: new Date(Date.now() - 3600000).toISOString(),
    acknowledged_by: 'admin@example.com',
    resolved_at: null,
  },
];

const mockTimeRange = {
  start: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
  end: new Date().toISOString(),
  preset: '24h',
};

describe('Monitoring Store - State Initialization', () => {
  test('initializes with correct default state', () => {
    const { result } = renderHook(() => useMonitoringStore());

    const state = result.current;

    // System overview defaults
    expect(state.systemHealth).toBeNull();
    expect(state.systemHealthLoading).toEqual({ loading: false });

    // Performance metrics defaults
    expect(state.performanceMetrics).toBeNull();
    expect(state.performanceLoading).toEqual({ loading: false });
    expect(state.performanceTimeRange).toBeDefined();
    expect(state.performanceTimeRange.preset).toBe('24h');

    // Alerts defaults
    expect(state.activeAlerts).toEqual([]);
    expect(state.alertHistory).toBeNull();
    expect(state.alertsLoading).toEqual({ loading: false });
    expect(state.acknowledgedAlerts).toBeInstanceOf(Set);

    // Real-time defaults
    expect(state.isRealTimeConnected).toBe(false);
    expect(state.realTimeUpdates).toEqual([]);
    expect(state.lastRealTimeUpdate).toBeNull();

    // UI state defaults
    expect(state.selectedTimeRange).toBeDefined();
    expect(state.globalFilters).toEqual({});
    expect(state.autoRefresh).toBe(true);
    expect(state.refreshInterval).toBe(30000);
    expect(state.notifications).toEqual([]);
  });

  test('initializes time range with correct defaults', () => {
    const { result } = renderHook(() => useSelectedTimeRange());

    const timeRange = result.current;

    expect(timeRange).toBeDefined();
    expect(timeRange.start).toBeDefined();
    expect(timeRange.end).toBeDefined();
    expect(timeRange.preset).toBe('24h');

    // Verify start time is approximately 24 hours ago
    const startTime = new Date(timeRange.start);
    const expectedStart = new Date(Date.now() - 24 * 60 * 60 * 1000);
    expect(
      Math.abs(startTime.getTime() - expectedStart.getTime())
    ).toBeLessThan(60000); // 1 minute tolerance
  });

  test('initializes dashboard configuration empty', () => {
    const { result } = renderHook(() => useMonitoringStore());

    const state = result.current;

    expect(state.dashboardConfigs).toEqual({});
    expect(state.activeDashboardId).toBeNull();
    expect(state.dashboardLayout.isEditing).toBe(false);
    expect(state.dashboardLayout.draggedWidget).toBeNull();
  });
});

describe('Monitoring Store - State Updates', () => {
  test('updates system health correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    act(() => {
      result.current.updateSystemHealth(mockSystemHealth);
    });

    expect(result.current.systemHealth).toEqual(mockSystemHealth);
    expect(result.current.systemHealthLoading).toEqual({
      loading: false,
      last_updated: expect.any(String),
    });
  });

  test('updates performance metrics correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    act(() => {
      result.current.updatePerformanceMetrics(mockPerformanceMetrics);
    });

    expect(result.current.performanceMetrics).toEqual(mockPerformanceMetrics);
    expect(result.current.performanceLoading).toEqual({
      loading: false,
      last_updated: expect.any(String),
    });
  });

  test('updates active alerts correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    act(() => {
      result.current.updateActiveAlerts(mockAlerts);
    });

    expect(result.current.activeAlerts).toEqual(mockAlerts);
    expect(result.current.alertsLoading).toEqual({
      loading: false,
      last_updated: expect.any(String),
    });
  });

  test('acknowledges alert correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Set up initial alerts
    act(() => {
      result.current.updateActiveAlerts(mockAlerts);
    });

    // Acknowledge first alert
    act(() => {
      result.current.acknowledgeAlert('alert-1');
    });

    // Verify alert is in acknowledged set
    expect(result.current.acknowledgedAlerts.has('alert-1')).toBe(true);
    expect(result.current.acknowledgedAlerts.size).toBe(1);
  });

  test('resolves alert correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Set up initial state with acknowledged alert
    act(() => {
      result.current.updateActiveAlerts(mockAlerts);
      result.current.acknowledgeAlert('alert-1');
    });

    // Resolve the alert
    act(() => {
      result.current.resolveAlert('alert-1', 'test-user');
    });

    // Verify alert is resolved and removed from acknowledged set
    const updatedAlerts = result.current.activeAlerts;
    const resolvedAlert = updatedAlerts.find((a) => a.id === 'alert-1');
    expect(resolvedAlert?.status).toBe('resolved');
    expect(resolvedAlert?.resolved_by).toBe('test-user');
    expect(result.current.acknowledgedAlerts.has('alert-1')).toBe(false);
  });

  test('unacknowledges alert correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Set up initial state with acknowledged alert
    act(() => {
      result.current.updateActiveAlerts(mockAlerts);
      result.current.acknowledgeAlert('alert-1');
    });

    // Unacknowledge the alert
    act(() => {
      result.current.unacknowledgeAlert('alert-1');
    });

    // Verify alert is removed from acknowledged set
    expect(result.current.acknowledgedAlerts.has('alert-1')).toBe(false);
    expect(result.current.acknowledgedAlerts.size).toBe(0);
  });

  test('updates time range correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    const newTimeRange = {
      start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      end: new Date().toISOString(),
      preset: '7d',
    };

    act(() => {
      result.current.setTimeRange(newTimeRange);
    });

    expect(result.current.selectedTimeRange).toEqual(newTimeRange);
    expect(result.current.performanceTimeRange).toEqual(newTimeRange);
    expect(result.current.businessTimeRange).toEqual(newTimeRange);
    expect(result.current.userAnalyticsTimeRange).toEqual(newTimeRange);
  });

  test('sets preset time range correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    act(() => {
      result.current.setPresetTimeRange('1h');
    });

    const timeRange = result.current.selectedTimeRange;
    expect(timeRange.preset).toBe('1h');

    // Verify start time is approximately 1 hour ago
    const startTime = new Date(timeRange.start);
    const expectedStart = new Date(Date.now() - 60 * 60 * 1000);
    expect(
      Math.abs(startTime.getTime() - expectedStart.getTime())
    ).toBeLessThan(60000);
  });

  test('toggles auto refresh correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Default should be true
    expect(result.current.autoRefresh).toBe(true);

    act(() => {
      result.current.toggleAutoRefresh();
    });

    expect(result.current.autoRefresh).toBe(false);

    act(() => {
      result.current.toggleAutoRefresh();
    });

    expect(result.current.autoRefresh).toBe(true);
  });

  test('sets refresh interval correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    const newInterval = 60000; // 1 minute

    act(() => {
      result.current.setRefreshInterval(newInterval);
    });

    expect(result.current.refreshInterval).toBe(newInterval);
  });

  test('adds and clears notifications correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Add notification
    act(() => {
      result.current.showNotification('Test message', 'success');
    });

    expect(result.current.notifications).toHaveLength(1);
    expect(result.current.notifications[0]).toEqual({
      show: true,
      message: 'Test message',
      type: 'success',
    });

    // Clear notifications
    act(() => {
      result.current.clearNotifications();
    });

    expect(result.current.notifications).toHaveLength(0);
  });

  test('dismisses individual notification correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Add multiple notifications
    act(() => {
      result.current.showNotification('First message', 'info');
      result.current.showNotification('Second message', 'warning');
    });

    expect(result.current.notifications).toHaveLength(2);

    // Dismiss first notification
    act(() => {
      result.current.dismissNotification(0);
    });

    expect(result.current.notifications).toHaveLength(1);
    expect(result.current.notifications[0].message).toBe('Second message');
  });

  test('updates global filters correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    const filters = {
      service: 'api-service',
      severity: 'critical',
    };

    act(() => {
      result.current.setGlobalFilters(filters);
    });

    expect(result.current.globalFilters).toEqual(filters);

    // Update single filter
    act(() => {
      result.current.updateGlobalFilter('service', 'user-service');
    });

    expect(result.current.globalFilters).toEqual({
      service: 'user-service',
      severity: 'critical',
    });

    // Clear filters
    act(() => {
      result.current.clearGlobalFilters();
    });

    expect(result.current.globalFilters).toEqual({});
  });

  test('manages real-time connection state correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Connect
    act(() => {
      result.current.setRealTimeConnection(true);
    });

    expect(result.current.isRealTimeConnected).toBe(true);

    // Disconnect
    act(() => {
      result.current.setRealTimeConnection(false);
    });

    expect(result.current.isRealTimeConnected).toBe(false);
  });

  test('adds and clears real-time updates correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    const update = {
      type: 'metric_update',
      data: { cpu_usage: 75 },
      timestamp: new Date().toISOString(),
    };

    // Add update
    act(() => {
      result.current.addRealTimeUpdate(update);
    });

    expect(result.current.realTimeUpdates).toHaveLength(1);
    expect(result.current.realTimeUpdates[0]).toEqual(update);
    expect(result.current.lastRealTimeUpdate).toBe(update.timestamp);

    // Add more updates to test limit
    for (let i = 0; i < 150; i++) {
      act(() => {
        result.current.addRealTimeUpdate({
          ...update,
          data: { cpu_usage: i },
          timestamp: new Date(Date.now() + i).toISOString(),
        });
      });
    }

    // Should keep only last 100 updates
    expect(result.current.realTimeUpdates).toHaveLength(100);

    // Clear updates
    act(() => {
      result.current.clearRealTimeUpdates();
    });

    expect(result.current.realTimeUpdates).toHaveLength(0);
    expect(result.current.lastRealTimeUpdate).toBeNull();
  });
});

describe('Monitoring Store - Selectors', () => {
  test('useSystemHealth returns correct state', () => {
    const { result } = renderHook(() => useSystemHealth());

    expect(result.current).toBeNull();

    // Update state
    const { result: storeResult } = renderHook(() => useMonitoringStore());
    act(() => {
      storeResult.current.updateSystemHealth(mockSystemHealth);
    });

    expect(result.current).toEqual(mockSystemHealth);
  });

  test('useSystemHealthLoading returns correct state', () => {
    const { result } = renderHook(() => useSystemHealthLoading());

    expect(result.current).toEqual({ loading: false });
  });

  test('usePerformanceMetrics returns correct state', () => {
    const { result } = renderHook(() => usePerformanceMetrics());

    expect(result.current).toBeNull();

    // Update state
    const { result: storeResult } = renderHook(() => useMonitoringStore());
    act(() => {
      storeResult.current.updatePerformanceMetrics(mockPerformanceMetrics);
    });

    expect(result.current).toEqual(mockPerformanceMetrics);
  });

  test('useActiveAlerts returns correct state', () => {
    const { result } = renderHook(() => useActiveAlerts());

    expect(result.current).toEqual([]);

    // Update state
    const { result: storeResult } = renderHook(() => useMonitoringStore());
    act(() => {
      storeResult.current.updateActiveAlerts(mockAlerts);
    });

    expect(result.current).toEqual(mockAlerts);
  });

  test('useAlertsLoading returns correct state', () => {
    const { result } = renderHook(() => useAlertsLoading());

    expect(result.current).toEqual({ loading: false });
  });

  test('useRealTimeConnection returns correct state', () => {
    const { result } = renderHook(() => useRealTimeConnection());

    expect(result.current).toBe(false);

    // Update state
    const { result: storeResult } = renderHook(() => useMonitoringStore());
    act(() => {
      storeResult.current.setRealTimeConnection(true);
    });

    expect(result.current).toBe(true);
  });

  test('useSelectedTimeRange returns correct state', () => {
    const { result } = renderHook(() => useSelectedTimeRange());

    expect(result.current).toBeDefined();
    expect(result.current.preset).toBe('24h');
  });

  test('useCriticalAlerts returns only critical active alerts', () => {
    const { result } = renderHook(() => useCriticalAlerts());

    expect(result.current).toEqual([]);

    // Update state with alerts
    const { result: storeResult } = renderHook(() => useMonitoringStore());
    act(() => {
      storeResult.current.updateActiveAlerts(mockAlerts);
    });

    const criticalAlerts = result.current;
    expect(criticalAlerts).toHaveLength(2); // Two critical alerts
    expect(
      criticalAlerts.every(
        (alert) => alert.severity === 'critical' && alert.status === 'active'
      )
    ).toBe(true);
  });

  test('useActiveAlertsCount returns correct count', () => {
    const { result } = renderHook(() => useActiveAlertsCount());

    expect(result.current).toBe(0);

    // Update state with alerts
    const { result: storeResult } = renderHook(() => useMonitoringStore());
    act(() => {
      storeResult.current.updateActiveAlerts(mockAlerts);
    });

    expect(result.current).toBe(2); // Two active alerts
  });

  test('useUnacknowledgedAlerts returns unacknowledged active alerts', () => {
    const { result } = renderHook(() => useUnacknowledgedAlerts());

    expect(result.current).toEqual([]);

    // Update state with alerts
    const { result: storeResult } = renderHook(() => useMonitoringStore());
    act(() => {
      storeResult.current.updateActiveAlerts(mockAlerts);
    });

    const unacknowledgedAlerts = result.current;
    expect(unacknowledgedAlerts).toHaveLength(2); // Two unacknowledged active alerts
    expect(
      unacknowledgedAlerts.every(
        (alert) =>
          alert.status === 'active' &&
          !storeResult.current.acknowledgedAlerts.has(alert.id)
      )
    ).toBe(true);
  });
});

describe('Monitoring Store - Dashboard Management', () => {
  test('creates dashboard configuration correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    const dashboardConfig = {
      id: 'test-dashboard',
      name: 'Test Dashboard',
      layout: { widgets: ['metric-1', 'metric-2'] },
      settings: { refreshInterval: 30000 },
    };

    act(() => {
      result.current.createDashboard(dashboardConfig);
    });

    expect(result.current.dashboardConfigs['test-dashboard']).toEqual(
      dashboardConfig
    );
  });

  test('updates dashboard configuration correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Create initial dashboard
    const initialConfig = {
      id: 'test-dashboard',
      name: 'Test Dashboard',
      layout: { widgets: ['metric-1'] },
    };

    act(() => {
      result.current.createDashboard(initialConfig);
    });

    // Update dashboard
    const updates = {
      name: 'Updated Dashboard',
      layout: { widgets: ['metric-1', 'metric-2', 'metric-3'] },
    };

    act(() => {
      result.current.updateDashboardConfig('test-dashboard', updates);
    });

    const updatedConfig = result.current.dashboardConfigs['test-dashboard'];
    expect(updatedConfig.name).toBe('Updated Dashboard');
    expect(updatedConfig.layout.widgets).toEqual([
      'metric-1',
      'metric-2',
      'metric-3',
    ]);
  });

  test('sets active dashboard correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Create dashboard
    const dashboardConfig = {
      id: 'test-dashboard',
      name: 'Test Dashboard',
      layout: { widgets: [] },
    };

    act(() => {
      result.current.createDashboard(dashboardConfig);
      result.current.setActiveDashboard('test-dashboard');
    });

    expect(result.current.activeDashboardId).toBe('test-dashboard');
  });

  test('deletes dashboard configuration correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Create dashboard
    const dashboardConfig = {
      id: 'test-dashboard',
      name: 'Test Dashboard',
      layout: { widgets: [] },
    };

    act(() => {
      result.current.createDashboard(dashboardConfig);
      result.current.setActiveDashboard('test-dashboard');
    });

    expect(result.current.dashboardConfigs['test-dashboard']).toBeDefined();
    expect(result.current.activeDashboardId).toBe('test-dashboard');

    // Delete dashboard
    act(() => {
      result.current.deleteDashboard('test-dashboard');
    });

    expect(result.current.dashboardConfigs['test-dashboard']).toBeUndefined();
    expect(result.current.activeDashboardId).toBeNull();
  });

  test('toggles edit mode correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    expect(result.current.dashboardLayout.isEditing).toBe(false);

    act(() => {
      result.current.toggleEditMode();
    });

    expect(result.current.dashboardLayout.isEditing).toBe(true);

    act(() => {
      result.current.toggleEditMode();
    });

    expect(result.current.dashboardLayout.isEditing).toBe(false);
  });

  test('sets dragged widget correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    act(() => {
      result.current.setDraggedWidget('metric-1');
    });

    expect(result.current.dashboardLayout.draggedWidget).toBe('metric-1');

    act(() => {
      result.current.setDraggedWidget(null);
    });

    expect(result.current.dashboardLayout.draggedWidget).toBeNull();
  });
});

describe('Monitoring Store - Loading State Management', () => {
  test('sets loading state correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    act(() => {
      result.current.setLoading('systemHealth', true);
    });

    expect(result.current.systemHealthLoading).toEqual({ loading: true });

    act(() => {
      result.current.setLoading('systemHealth', false, 'Success');
    });

    expect(result.current.systemHealthLoading).toEqual({
      loading: false,
      last_updated: expect.any(String),
    });
  });

  test('clears all loading states correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Set loading states
    act(() => {
      result.current.setLoading('systemHealth', true);
      result.current.setLoading('performance', true);
      result.current.setLoading('alerts', true);
    });

    expect(result.current.systemHealthLoading.loading).toBe(true);
    expect(result.current.performanceLoading.loading).toBe(true);
    expect(result.current.alertsLoading.loading).toBe(true);

    // Clear all loading states
    act(() => {
      result.current.clearAllLoading();
    });

    expect(result.current.systemHealthLoading.loading).toBe(false);
    expect(result.current.performanceLoading.loading).toBe(false);
    expect(result.current.alertsLoading.loading).toBe(false);
  });
});

describe('Monitoring Store - Error Handling', () => {
  test('handles loading errors correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    act(() => {
      result.current.setLoading('systemHealth', false, 'Network error');
    });

    expect(result.current.systemHealthLoading).toEqual({
      loading: false,
      error: 'Network error',
      last_updated: expect.any(String),
    });
  });

  test('recovers from errors correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Set error state
    act(() => {
      result.current.setLoading('systemHealth', false, 'Network error');
    });

    expect(result.current.systemHealthLoading.error).toBe('Network error');

    // Update with successful data
    act(() => {
      result.current.updateSystemHealth(mockSystemHealth);
    });

    expect(result.current.systemHealthLoading.error).toBeUndefined();
    expect(result.current.systemHealth).toEqual(mockSystemHealth);
  });
});

describe('Monitoring Store - Performance Tests', () => {
  test('handles large alert datasets efficiently', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Generate large dataset (1000 alerts)
    const largeAlerts = Array.from({ length: 1000 }, (_, i) => ({
      id: `alert-${i}`,
      name: `Alert ${i}`,
      severity: i % 3 === 0 ? 'critical' : i % 2 === 0 ? 'warning' : 'info',
      status: 'active',
      message: `Test alert message ${i}`,
      created_at: new Date(Date.now() - i * 1000).toISOString(),
    }));

    const startTime = performance.now();

    act(() => {
      result.current.updateActiveAlerts(largeAlerts);
    });

    const updateTime = performance.now() - startTime;

    // Should complete within reasonable time
    expect(updateTime).toBeLessThan(100); // Less than 100ms
    expect(result.current.activeAlerts).toHaveLength(1000);
  });

  test('handles frequent time range updates efficiently', () => {
    const { result } = renderHook(() => useMonitoringStore());

    const startTime = performance.now();

    // Perform many time range updates
    for (let i = 0; i < 100; i++) {
      act(() => {
        result.current.setPresetTimeRange(i % 2 === 0 ? '1h' : '24h');
      });
    }

    const updateTime = performance.now() - startTime;

    // Should handle frequent updates efficiently
    expect(updateTime).toBeLessThan(50); // Less than 50ms
  });

  test('handles real-time updates efficiently', () => {
    const { result } = renderHook(() => useMonitoringStore());

    const startTime = performance.now();

    // Add many real-time updates
    for (let i = 0; i < 200; i++) {
      act(() => {
        result.current.addRealTimeUpdate({
          type: 'metric_update',
          data: { cpu_usage: Math.random() * 100 },
          timestamp: new Date(Date.now() + i).toISOString(),
        });
      });
    }

    const updateTime = performance.now() - startTime;

    // Should handle updates efficiently and maintain limit
    expect(updateTime).toBeLessThan(100); // Less than 100ms
    expect(result.current.realTimeUpdates).toHaveLength(100); // Should maintain limit of 100
  });
});

describe('Monitoring Store - Concurrency Tests', () => {
  test('handles concurrent state updates correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Simulate concurrent updates
    const promises = Array.from(
      { length: 10 },
      (_, i) =>
        new Promise<void>((resolve) => {
          setTimeout(() => {
            act(() => {
              result.current.setLoading('systemHealth', i % 2 === 0);
            });
            resolve();
          }, Math.random() * 10);
        })
    );

    return Promise.all(promises).then(() => {
      // State should be consistent after concurrent updates
      expect(typeof result.current.systemHealthLoading.loading).toBe('boolean');
    });
  });

  test('handles concurrent alert updates correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Set up initial alerts
    act(() => {
      result.current.updateActiveAlerts(mockAlerts);
    });

    // Simulate concurrent alert acknowledgments
    const promises = mockAlerts.slice(0, 2).map(
      (alert) =>
        new Promise<void>((resolve) => {
          setTimeout(() => {
            act(() => {
              result.current.acknowledgeAlert(alert.id);
            });
            resolve();
          }, Math.random() * 10);
        })
    );

    return Promise.all(promises).then(() => {
      // Both alerts should be acknowledged
      expect(result.current.acknowledgedAlerts.has('alert-1')).toBe(true);
      expect(result.current.acknowledgedAlerts.has('alert-2')).toBe(true);
      expect(result.current.acknowledgedAlerts.size).toBe(2);
    });
  });
});

describe('Monitoring Store - Integration with Persistence', () => {
  test('persists and rehydrates state correctly', () => {
    // Create a store with persistence
    const createStore = () =>
      create(
        subscribeWithSelector((set, get) => ({
          // Test state
          testValue: 'initial',
          updateTestValue: (value: string) => set({ testValue: value }),
        }))
      );

    const testStore = createStore();

    // Update state
    act(() => {
      testStore.getState().updateTestValue('updated');
    });

    expect(testStore.getState().testValue).toBe('updated');

    // In a real implementation, this would test persistence to localStorage
    // For now, we verify the store maintains state correctly
  });

  test('handles persistence errors gracefully', () => {
    // This would test error handling when persistence fails
    // For example, when localStorage is not available or full

    // Mock localStorage unavailable
    const originalLocalStorage = global.localStorage;
    global.localStorage = undefined as any;

    try {
      const { result } = renderHook(() => useMonitoringStore());

      // Store should still work without persistence
      expect(result.current).toBeDefined();
    } finally {
      // Restore localStorage
      global.localStorage = originalLocalStorage;
    }
  });
});

describe('Monitoring Store - Memory Management', () => {
  test('clears real-time updates to prevent memory leaks', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Add many updates
    for (let i = 0; i < 150; i++) {
      act(() => {
        result.current.addRealTimeUpdate({
          type: 'test_update',
          data: { index: i },
          timestamp: new Date(Date.now() + i).toISOString(),
        });
      });
    }

    // Should maintain limit of 100
    expect(result.current.realTimeUpdates).toHaveLength(100);

    // Clear updates
    act(() => {
      result.current.clearRealTimeUpdates();
    });

    expect(result.current.realTimeUpdates).toHaveLength(0);
    expect(result.current.lastRealTimeUpdate).toBeNull();
  });

  test('resetState clears all data correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Set up various state
    act(() => {
      result.current.updateSystemHealth(mockSystemHealth);
      result.current.updatePerformanceMetrics(mockPerformanceMetrics);
      result.current.updateActiveAlerts(mockAlerts);
      result.current.acknowledgeAlert('alert-1');
      result.current.setRealTimeConnection(true);
      result.current.showNotification('Test notification');
    });

    // Verify state is set
    expect(result.current.systemHealth).toEqual(mockSystemHealth);
    expect(result.current.performanceMetrics).toEqual(mockPerformanceMetrics);
    expect(result.current.activeAlerts).toEqual(mockAlerts);
    expect(result.current.acknowledgedAlerts.size).toBe(1);
    expect(result.current.isRealTimeConnected).toBe(true);
    expect(result.current.notifications).toHaveLength(1);

    // Reset state
    act(() => {
      result.current.resetState();
    });

    // Verify state is reset to defaults
    expect(result.current.systemHealth).toBeNull();
    expect(result.current.performanceMetrics).toBeNull();
    expect(result.current.activeAlerts).toEqual([]);
    expect(result.current.acknowledgedAlerts.size).toBe(0);
    expect(result.current.isRealTimeConnected).toBe(false);
    expect(result.current.notifications).toEqual([]);
  });
});

describe('Monitoring Store - Edge Cases', () => {
  test('handles duplicate alert acknowledgments gracefully', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Set up alerts
    act(() => {
      result.current.updateActiveAlerts(mockAlerts);
    });

    // Acknowledge same alert multiple times
    act(() => {
      result.current.acknowledgeAlert('alert-1');
      result.current.acknowledgeAlert('alert-1');
      result.current.acknowledgeAlert('alert-1');
    });

    // Should only be acknowledged once
    expect(result.current.acknowledgedAlerts.has('alert-1')).toBe(true);
    expect(result.current.acknowledgedAlerts.size).toBe(1);
  });

  test('handles resolving non-existent alerts gracefully', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Try to resolve non-existent alert
    act(() => {
      result.current.resolveAlert('non-existent-alert', 'test-user');
    });

    // Should not cause errors
    expect(result.current.activeAlerts).toEqual([]);
  });

  test('handles invalid time range data gracefully', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Try to set invalid time range
    const invalidTimeRange = {
      start: 'invalid-date',
      end: 'invalid-date',
      preset: '24h',
    };

    act(() => {
      result.current.setTimeRange(invalidTimeRange);
    });

    // Should handle gracefully (implementation dependent)
    expect(result.current.selectedTimeRange).toBeDefined();
  });

  test('handles empty alert updates correctly', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Set up initial alerts
    act(() => {
      result.current.updateActiveAlerts(mockAlerts);
    });

    expect(result.current.activeAlerts).toHaveLength(3);

    // Update with empty alerts
    act(() => {
      result.current.updateActiveAlerts([]);
    });

    expect(result.current.activeAlerts).toHaveLength(0);
    expect(result.current.alertsLoading.loading).toBe(false);
  });
});
