/**
 * Comprehensive Frontend Dashboard Integration Tests
 *
 * This module provides integration tests for all 6 monitoring dashboard components:
 * 1. SystemOverviewDashboard
 * 2. PerformanceMetricsDashboard
 * 3. MetricCard
 * 4. StatusGrid
 * 5. AlertList
 * 6. SystemMonitoringPage
 *
 * Tests cover:
 * - Component integration and data flow
 * - WebSocket integration with real-time updates
 * - State management (Zustand) integration
 * - React Query caching and background updates
 * - Error handling and recovery scenarios
 * - Accessibility testing (WCAG 2.1 AA compliance)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import { axe, toHaveNoViolations } from 'jest-axe';

// Monitoring components
import SystemOverviewDashboard from '../SystemOverviewDashboard';
import PerformanceMetricsDashboard from '../PerformanceMetricsDashboard';
import MetricCard from '../MetricCard';
import StatusGrid from '../StatusGrid';
import AlertList from '../AlertList';
import SystemMonitoringPage from '../../page-components/monitoring/SystemMonitoringPage';

// State management
import { useMonitoringStore } from '../../../stores/monitoringStore';

// Utils
import { createTestQueryClient } from '../../../utils/test-utils';

// Extend Jest matchers
expect.extend(toHaveNoViolations);

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  readyState: number = WebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  sentMessages: any[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);

    // Simulate connection opening
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 10);
  }

  send(data: string) {
    this.sentMessages.push(JSON.parse(data));
  }

  close() {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  static reset() {
    MockWebSocket.instances = [];
  }
}

// Mock global WebSocket
Object.defineProperty(global, 'WebSocket', {
  writable: true,
  value: MockWebSocket,
});

// Test data
const mockMetrics = {
  system: {
    cpu_usage: 45.2,
    memory_usage: 68.5,
    disk_usage: 32.1,
    network_io: 125000,
  },
  application: {
    active_connections: 156,
    request_rate: 42.5,
    error_rate: 0.02,
    response_time: 125.5,
  },
  database: {
    connections: 25,
    query_time: 45.2,
    index_usage: 92.5,
    cache_hit_rate: 88.3,
  },
};

const mockAlerts = [
  {
    id: '1',
    title: 'High CPU Usage',
    description: 'CPU usage exceeded 80% threshold',
    severity: 'warning',
    status: 'active',
    timestamp: '2024-01-15T10:30:00Z',
    source: 'system_monitor',
  },
  {
    id: '2',
    title: 'Database Connection Pool Exhaustion',
    description: 'All database connections are in use',
    severity: 'error',
    status: 'active',
    timestamp: '2024-01-15T10:25:00Z',
    source: 'database_monitor',
  },
  {
    id: '3',
    title: 'Service Unavailable',
    description: 'Vector store service is not responding',
    severity: 'critical',
    status: 'active',
    timestamp: '2024-01-15T10:20:00Z',
    source: 'health_checker',
  },
];

const mockHealthStatus = {
  overall: 'healthy',
  components: {
    database: { status: 'healthy', uptime: '99.9%', last_check: '2024-01-15T10:30:00Z' },
    vector_store: { status: 'healthy', uptime: '99.5%', last_check: '2024-01-15T10:30:00Z' },
    graph_db: { status: 'warning', uptime: '98.2%', last_check: '2024-01-15T10:30:00Z' },
    monitoring: { status: 'healthy', uptime: '100%', last_check: '2024-01-15T10:30:00Z' },
  },
};

// MSW Server setup
const server = setupServer(
  // Metrics endpoints
  rest.get('/api/monitoring/metrics', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        metrics: mockMetrics,
        timestamp: new Date().toISOString(),
      })
    );
  }),

  rest.post('/api/monitoring/metrics', (req, res, ctx) => {
    return res(ctx.status(201));
  }),

  // Alerts endpoints
  rest.get('/api/monitoring/alerts', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        alerts: mockAlerts,
        total: mockAlerts.length,
      })
    );
  }),

  rest.get('/api/monitoring/alerts/:id', (req, res, ctx) => {
    const { id } = req.params;
    const alert = mockAlerts.find(a => a.id === id);
    if (alert) {
      return res(ctx.status(200), ctx.json(alert));
    }
    return res(ctx.status(404));
  }),

  rest.patch('/api/monitoring/alerts/:id', (req, res, ctx) => {
    const { id } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        id,
        status: 'resolved',
        resolved_at: new Date().toISOString(),
      })
    );
  }),

  // Health endpoints
  rest.get('/api/monitoring/health', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        components: mockHealthStatus.components,
      })
    );
  }),

  // Performance endpoints
  rest.get('/api/monitoring/analytics/performance', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        analysis: {
          cpu_trend: 'stable',
          memory_trend: 'increasing',
          performance_score: 85.5,
        },
        recommendations: [
          'Consider optimizing database queries',
          'Monitor memory usage trends',
        ],
      })
    );
  }),

  // WebSocket endpoint for testing
  rest.get('/ws/monitoring/metrics', (req, res, ctx) => {
    return res(ctx.status(101));
  }),
);

// Test utilities
const createTestWrapper = (queryClient: QueryClient) => {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

const renderWithQueryClient = (
  component: React.ReactElement,
  options: { queryClient?: QueryClient } = {}
) => {
  const queryClient = options.queryClient || createTestQueryClient();
  return render(component, {
    wrapper: createTestWrapper(queryClient),
    ...options,
  });
};

describe('SystemOverviewDashboard Integration', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
    server.listen();
    MockWebSocket.reset();
  });

  afterEach(() => {
    server.resetHandlers();
    server.close();
  });

  it('renders system overview with real-time data', async () => {
    renderWithQueryClient(<SystemOverviewDashboard />);

    // Check loading state
    expect(screen.getByText('Loading system overview...')).toBeInTheDocument();

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('System Overview')).toBeInTheDocument();
    });

    // Verify metrics are displayed
    expect(screen.getByText('CPU Usage')).toBeInTheDocument();
    expect(screen.getByText('45.2%')).toBeInTheDocument();
    expect(screen.getByText('Memory Usage')).toBeInTheDocument();
    expect(screen.getByText('68.5%')).toBeInTheDocument();
  });

  it('updates data in real-time via WebSocket', async () => {
    renderWithQueryClient(<SystemOverviewDashboard />);

    await waitFor(() => {
      expect(screen.getByText('CPU Usage')).toBeInTheDocument();
    });

    // Simulate WebSocket update
    act(() => {
      const mockWS = MockWebSocket.instances[0];
      if (mockWS && mockWS.onmessage) {
        mockWS.onmessage({
          data: JSON.stringify({
            type: 'metric_update',
            data: {
              name: 'cpu_usage',
              value: 78.5,
              timestamp: new Date().toISOString(),
            },
          }),
        } as MessageEvent);
      }
    });

    // Verify UI updates
    await waitFor(() => {
      expect(screen.getByText('78.5%')).toBeInTheDocument();
    });
  });

  it('handles WebSocket reconnection', async () => {
    renderWithQueryClient(<SystemOverviewDashboard />);

    await waitFor(() => {
      expect(screen.getByText('CPU Usage')).toBeInTheDocument();
    });

    // Simulate WebSocket disconnection and reconnection
    act(() => {
      const mockWS = MockWebSocket.instances[0];
      if (mockWS) {
        mockWS.readyState = WebSocket.CLOSED;
        if (mockWS.onclose) {
          mockWS.onclose(new CloseEvent('close'));
        }
      }
    });

    // Should attempt reconnection
    await waitFor(() => {
      expect(MockWebSocket.instances.length > 1).toBeTruthy();
    }, { timeout: 5000 });
  });

  it('passes accessibility tests', async () => {
    const { container } = renderWithQueryClient(<SystemOverviewDashboard />);

    await waitFor(() => {
      expect(screen.getByText('System Overview')).toBeInTheDocument();
    });

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

describe('PerformanceMetricsDashboard Integration', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
    server.listen();
  });

  afterEach(() => {
    server.resetHandlers();
    server.close();
  });

  it('renders performance metrics with charts', async () => {
    renderWithQueryClient(<PerformanceMetricsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Performance Metrics')).toBeInTheDocument();
    });

    // Verify performance metrics are displayed
    expect(screen.getByText('Response Time')).toBeInTheDocument();
    expect(screen.getByText('125.5ms')).toBeInTheDocument();
    expect(screen.getByText('Error Rate')).toBeInTheDocument();
    expect(screen.getByText('2%')).toBeInTheDocument();

    // Verify charts are rendered
    expect(screen.getByRole('img', { name: /performance chart/i })).toBeInTheDocument();
  });

  it('handles metric filtering and time range selection', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<PerformanceMetricsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Performance Metrics')).toBeInTheDocument();
    });

    // Test time range selection
    const timeRangeSelect = screen.getByLabelText(/time range/i);
    await user.selectOptions(timeRangeSelect, '1h');

    // Test metric filtering
    const cpuCheckbox = screen.getByLabelText(/cpu usage/i);
    await user.click(cpuCheckbox);

    // Verify filtering is applied
    await waitFor(() => {
      expect(screen.queryByText('CPU Usage')).not.toBeInTheDocument();
    });
  });

  it('displays performance recommendations', async () => {
    renderWithQueryClient(<PerformanceMetricsDashboard />);

    await waitFor(() => {
      expect(screen.getByText('Performance Metrics')).toBeInTheDocument();
    });

    // Verify recommendations are displayed
    expect(screen.getByText('Recommendations')).toBeInTheDocument();
    expect(screen.getByText('Consider optimizing database queries')).toBeInTheDocument();
  });

  it('handles chart interactions', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<PerformanceMetricsDashboard />);

    await waitFor(() => {
      expect(screen.getByRole('img', { name: /performance chart/i })).toBeInTheDocument();
    });

    // Test chart hover interactions
    const chart = screen.getByRole('img', { name: /performance chart/i });
    await user.hover(chart);

    // Should show tooltip with detailed information
    await waitFor(() => {
      expect(screen.getByText(/details/i)).toBeInTheDocument();
    });
  });
});

describe('MetricCard Integration', () => {
  const defaultProps = {
    title: 'Test Metric',
    value: 42.5,
    unit: '%',
    trend: 'up' as const,
    trendValue: 5.2,
    status: 'normal' as const,
    icon: 'cpu',
  };

  it('renders metric card with all props', () => {
    render(<MetricCard {...defaultProps} />);

    expect(screen.getByText('Test Metric')).toBeInTheDocument();
    expect(screen.getByText('42.5%')).toBeInTheDocument();
    expect(screen.getByText('+5.2%')).toBeInTheDocument();
  });

  it('displays appropriate colors based on status', () => {
    const { rerender } = render(<MetricCard {...defaultProps} status="normal" />);
    expect(screen.getByTestId('metric-card')).toHaveClass('border-green-500');

    rerender(<MetricCard {...defaultProps} status="warning" />);
    expect(screen.getByTestId('metric-card')).toHaveClass('border-yellow-500');

    rerender(<MetricCard {...defaultProps} status="error" />);
    expect(screen.getByTestId('metric-card')).toHaveClass('border-red-500');
  });

  it('handles click interactions', async () => {
    const handleClick = jest.fn();
    const user = userEvent.setup();

    render(<MetricCard {...defaultProps} onClick={handleClick} />);

    await user.click(screen.getByTestId('metric-card'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('passes accessibility tests', async () => {
    const { container } = render(<MetricCard {...defaultProps} />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

describe('StatusGrid Integration', () => {
  it('renders system status grid', async () => {
    renderWithQueryClient(<StatusGrid />);

    await waitFor(() => {
      expect(screen.getByText('System Status')).toBeInTheDocument();
    });

    // Verify component status cards
    expect(screen.getByText('Database')).toBeInTheDocument();
    expect(screen.getByText('Vector Store')).toBeInTheDocument();
    expect(screen.getByText('Graph DB')).toBeInTheDocument();
    expect(screen.getByText('Monitoring')).toBeInTheDocument();
  });

  it('displays real-time status updates', async () => {
    renderWithQueryClient(<StatusGrid />);

    await waitFor(() => {
      expect(screen.getByText('Database')).toBeInTheDocument();
    });

    // Simulate status update via WebSocket
    act(() => {
      const mockWS = MockWebSocket.instances.find(ws =>
        ws.url.includes('/ws/monitoring/health')
      );
      if (mockWS && mockWS.onmessage) {
        mockWS.onmessage({
          data: JSON.stringify({
            type: 'component_health_update',
            data: {
              component: 'database',
              status: 'degraded',
              timestamp: new Date().toISOString(),
            },
          }),
        } as MessageEvent);
      }
    });

    // Verify status update
    await waitFor(() => {
      expect(screen.getByText('Degraded')).toBeInTheDocument();
    });
  });

  it('handles status refresh on demand', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<StatusGrid />);

    await waitFor(() => {
      expect(screen.getByText('System Status')).toBeInTheDocument();
    });

    // Click refresh button
    const refreshButton = screen.getByLabelText(/refresh status/i);
    await user.click(refreshButton);

    // Should show loading state
    expect(screen.getByText('Refreshing...')).toBeInTheDocument();

    // Should complete refresh
    await waitFor(() => {
      expect(screen.queryByText('Refreshing...')).not.toBeInTheDocument();
    });
  });
});

describe('AlertList Integration', () => {
  beforeEach(() => {
    server.listen();
  });

  afterEach(() => {
    server.resetHandlers();
    server.close();
  });

  it('renders list of active alerts', async () => {
    renderWithQueryClient(<AlertList />);

    await waitFor(() => {
      expect(screen.getByText('High CPU Usage')).toBeInTheDocument();
      expect(screen.getByText('Database Connection Pool Exhaustion')).toBeInTheDocument();
      expect(screen.getByText('Service Unavailable')).toBeInTheDocument();
    });

    // Verify alert details
    expect(screen.getByText('CPU usage exceeded 80% threshold')).toBeInTheDocument();
    expect(screen.getByText('Vector store service is not responding')).toBeInTheDocument();
  });

  it('filters alerts by severity', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<AlertList />);

    await waitFor(() => {
      expect(screen.getByText('High CPU Usage')).toBeInTheDocument();
    });

    // Filter by critical severity
    const severityFilter = screen.getByLabelText(/severity/i);
    await user.selectOptions(severityFilter, 'critical');

    // Should only show critical alerts
    await waitFor(() => {
      expect(screen.getByText('Service Unavailable')).toBeInTheDocument();
      expect(screen.queryByText('High CPU Usage')).not.toBeInTheDocument();
    });
  });

  it('handles alert acknowledgment', async () => {
    const user = userEvent.setup();

    // Mock acknowledgment endpoint
    server.use(
      rest.patch('/api/monitoring/alerts/:id/acknowledge', (req, res, ctx) => {
        return res(ctx.status(200));
      })
    );

    renderWithQueryClient(<AlertList />);

    await waitFor(() => {
      expect(screen.getByText('High CPU Usage')).toBeInTheDocument();
    });

    // Find and click acknowledge button
    const acknowledgeButton = screen.getByLabelText(/acknowledge alert/i);
    await user.click(acknowledgeButton);

    // Should show acknowledgment confirmation
    await waitFor(() => {
      expect(screen.getByText('Alert acknowledged')).toBeInTheDocument();
    });
  });

  it('handles alert resolution', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<AlertList />);

    await waitFor(() => {
      expect(screen.getByText('High CPU Usage')).toBeInTheDocument();
    });

    // Find and click resolve button
    const resolveButton = screen.getByLabelText(/resolve alert/i);
    await user.click(resolveButton);

    // Should show resolution dialog
    expect(screen.getByText(/resolve alert/i)).toBeInTheDocument();

    // Add resolution note and confirm
    const noteInput = screen.getByLabelText(/resolution note/i);
    await user.type(noteInput, 'Issue has been resolved');

    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    await user.click(confirmButton);

    // Should show success message
    await waitFor(() => {
      expect(screen.getByText('Alert resolved successfully')).toBeInTheDocument();
    });
  });

  it('passes accessibility tests', async () => {
    const { container } = renderWithQueryClient(<AlertList />);

    await waitFor(() => {
      expect(screen.getByText('High CPU Usage')).toBeInTheDocument();
    });

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

describe('SystemMonitoringPage Integration', () => {
  beforeEach(() => {
    server.listen();
  });

  afterEach(() => {
    server.resetHandlers();
    server.close();
  });

  it('renders complete monitoring dashboard', async () => {
    renderWithQueryClient(<SystemMonitoringPage />);

    await waitFor(() => {
      expect(screen.getByText('System Monitoring')).toBeInTheDocument();
    });

    // Verify all major components are present
    expect(screen.getByText('System Overview')).toBeInTheDocument();
    expect(screen.getByText('Performance Metrics')).toBeInTheDocument();
    expect(screen.getByText('System Status')).toBeInTheDocument();
    expect(screen.getByText('Active Alerts')).toBeInTheDocument();
  });

  it('handles navigation between different views', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<SystemMonitoringPage />);

    await waitFor(() => {
      expect(screen.getByText('System Monitoring')).toBeInTheDocument();
    });

    // Navigate to performance view
    const performanceTab = screen.getByRole('tab', { name: /performance/i });
    await user.click(performanceTab);

    // Should show performance-focused view
    await waitFor(() => {
      expect(screen.getByText('Performance Analytics')).toBeInTheDocument();
    });

    // Navigate to alerts view
    const alertsTab = screen.getByRole('tab', { name: /alerts/i });
    await user.click(alertsTab);

    // Should show alerts-focused view
    await waitFor(() => {
      expect(screen.getByText('Alert Management')).toBeInTheDocument();
    });
  });

  it('handles error states gracefully', async () => {
    // Mock API error
    server.use(
      rest.get('/api/monitoring/metrics', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Internal server error' }));
      })
    );

    renderWithQueryClient(<SystemMonitoringPage />);

    // Should show error state
    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });

    // Should provide retry option
    const retryButton = screen.getByRole('button', { name: /retry/i });
    expect(retryButton).toBeInTheDocument();
  });

  it('maintains state across page refreshes', async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<SystemMonitoringPage />);

    await waitFor(() => {
      expect(screen.getByText('System Monitoring')).toBeInTheDocument();
    });

    // Change some settings
    const timeRangeSelect = screen.getByLabelText(/time range/i);
    await user.selectOptions(timeRangeSelect, '24h');

    // Simulate page refresh by re-rendering
    renderWithQueryClient(<SystemMonitoringPage />);

    // Should restore previous settings
    await waitFor(() => {
      expect(screen.getByDisplayValue('24h')).toBeInTheDocument();
    });
  });
});

describe('Zustand State Management Integration', () => {
  beforeEach(() => {
    // Reset store state
    useMonitoringStore.getState().reset();
  });

  it('updates monitoring store with new metrics', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Update metrics
    act(() => {
      result.current.updateMetrics(mockMetrics);
    });

    expect(result.current.metrics).toEqual(mockMetrics);
    expect(result.current.lastUpdated).toBeDefined();
  });

  it('manages WebSocket connection state', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Connect WebSocket
    act(() => {
      result.current.connectWebSocket();
    });

    expect(result.current.isConnected).toBe(true);

    // Disconnect WebSocket
    act(() => {
      result.current.disconnectWebSocket();
    });

    expect(result.current.isConnected).toBe(false);
  });

  it('handles alert updates', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Add alert
    act(() => {
      result.current.addAlert(mockAlerts[0]);
    });

    expect(result.current.alerts).toHaveLength(1);
    expect(result.current.alerts[0].id).toBe(mockAlerts[0].id);

    // Update alert status
    act(() => {
      result.current.updateAlertStatus(mockAlerts[0].id, 'resolved');
    });

    expect(result.current.alerts[0].status).toBe('resolved');
  });

  it('persists state to localStorage', () => {
    const { result } = renderHook(() => useMonitoringStore());

    // Update settings
    const settings = {
      refreshInterval: 5000,
      enableNotifications: true,
      theme: 'dark',
    };

    act(() => {
      result.current.updateSettings(settings);
    });

    expect(result.current.settings).toEqual(settings);

    // Verify localStorage was called
    expect(localStorage.setItem).toHaveBeenCalledWith(
      'monitoring-store',
      expect.stringContaining('"refreshInterval":5000')
    );
  });
});

describe('React Query Integration', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
    server.listen();
  });

  afterEach(() => {
    server.resetHandlers();
    server.close();
  });

  it('caches metrics data', async () => {
    renderWithQueryClient(<SystemOverviewDashboard />, { queryClient });

    // First load - should fetch from API
    await waitFor(() => {
      expect(screen.getByText('CPU Usage')).toBeInTheDocument();
    });

    // Verify data is cached
    const cacheData = queryClient.getQueryData(['metrics']);
    expect(cacheData).toEqual(mockMetrics);

    // Second load - should use cache
    queryClient.clear();
    renderWithQueryClient(<SystemOverviewDashboard />, { queryClient });

    await waitFor(() => {
      expect(screen.getByText('CPU Usage')).toBeInTheDocument();
    });
  });

  it('invalidates cache on WebSocket updates', async () => {
    renderWithQueryClient(<SystemOverviewDashboard />, { queryClient });

    await waitFor(() => {
      expect(screen.getByText('CPU Usage')).toBeInTheDocument();
    });

    // Simulate WebSocket update
    act(() => {
      const mockWS = MockWebSocket.instances[0];
      if (mockWS && mockWS.onmessage) {
        mockWS.onmessage({
          data: JSON.stringify({
            type: 'metric_update',
            data: {
              name: 'cpu_usage',
              value: 85.5,
              timestamp: new Date().toISOString(),
            },
          }),
        } as MessageEvent);
      }
    });

    // Cache should be invalidated and refetched
    await waitFor(() => {
      expect(screen.getByText('85.5%')).toBeInTheDocument();
    });
  });

  it('handles background refetching', async () => {
    jest.useFakeTimers();

    renderWithQueryClient(<SystemOverviewDashboard />, { queryClient });

    await waitFor(() => {
      expect(screen.getByText('CPU Usage')).toBeInTheDocument();
    });

    // Fast-forward time to trigger background refetch
    act(() => {
      jest.advanceTimersByTime(30000); // 30 seconds
    });

    // Should show refetching indicator
    await waitFor(() => {
      expect(screen.getByText('Updating...')).toBeInTheDocument();
    });

    // Should complete refetch
    await waitFor(() => {
      expect(screen.queryByText('Updating...')).not.toBeInTheDocument();
    });

    jest.useRealTimers();
  });

  it('handles query errors with retry', async () => {
    let attemptCount = 0;

    server.use(
      rest.get('/api/monitoring/metrics', (req, res, ctx) => {
        attemptCount++;
        if (attemptCount < 3) {
          return res(ctx.status(500));
        }
        return res(
          ctx.status(200),
          ctx.json({ metrics: mockMetrics })
        );
      })
    );

    renderWithQueryClient(<SystemOverviewDashboard />, { queryClient });

    // Should show retry attempts
    await waitFor(() => {
      expect(screen.getByText('CPU Usage')).toBeInTheDocument();
    }, { timeout: 10000 });

    expect(attemptCount).toBe(3);
  });
});

describe('Error Handling and Recovery', () => {
  it('handles network connectivity issues', async () => {
    // Mock network error
    server.use(
      rest.get('*', (req, res, ctx) => {
        return res.networkError('Network error');
      })
    );

    renderWithQueryClient(<SystemMonitoringPage />);

    await waitFor(() => {
      expect(screen.getByText(/network error/i)).toBeInTheDocument();
    });

    // Should provide offline mode indication
    expect(screen.getByText(/offline mode/i)).toBeInTheDocument();
  });

  it('handles WebSocket connection failures', async () => {
    // Mock WebSocket failure
    Object.defineProperty(global, 'WebSocket', {
      writable: true,
      value: class {
        constructor() {
          setTimeout(() => {
            if (this.onerror) {
              this.onerror(new Event('error'));
            }
          }, 10);
        }
      },
    });

    renderWithQueryClient(<SystemOverviewDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/real-time updates unavailable/i)).toBeInTheDocument();
    });
  });

  it('provides fallback data when API fails', async () => {
    server.use(
      rest.get('/api/monitoring/metrics', (req, res, ctx) => {
        return res(ctx.status(500));
      }),
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    renderWithQueryClient(<SystemMonitoringPage />);

    await waitFor(() => {
      expect(screen.getByText(/some features may be unavailable/i)).toBeInTheDocument();
    });

    // Should still render basic UI with cached/fallback data
    expect(screen.getByText('System Monitoring')).toBeInTheDocument();
  });
});

describe('Performance Testing', () => {
  it('renders dashboard within performance thresholds', async () => {
    const startTime = performance.now();

    renderWithQueryClient(<SystemMonitoringPage />);

    await waitFor(() => {
      expect(screen.getByText('System Monitoring')).toBeInTheDocument();
    });

    const renderTime = performance.now() - startTime;
    expect(renderTime).toBeLessThan(2000); // Should render within 2 seconds
  });

  it('handles large datasets efficiently', async () => {
    // Mock large dataset
    const largeAlerts = Array.from({ length: 1000 }, (_, i) => ({
      id: `alert-${i}`,
      title: `Alert ${i}`,
      description: `Description for alert ${i}`,
      severity: i % 3 === 0 ? 'warning' : i % 3 === 1 ? 'error' : 'critical',
      status: 'active',
      timestamp: new Date().toISOString(),
      source: 'test',
    }));

    server.use(
      rest.get('/api/monitoring/alerts', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({ alerts: largeAlerts, total: largeAlerts.length })
        );
      })
    );

    const startTime = performance.now();
    renderWithQueryClient(<AlertList />);

    await waitFor(() => {
      expect(screen.getByText('Alert 0')).toBeInTheDocument();
    });

    const renderTime = performance.now() - startTime;
    expect(renderTime).toBeLessThan(3000); // Should handle large datasets within 3 seconds
  });
});

// Integration test helper
export const renderMonitoringDashboard = () => {
  const queryClient = createTestQueryClient();
  return renderWithQueryClient(<SystemMonitoringPage />, { queryClient });
};

export const mockWebSocketUpdate = (type: string, data: any) => {
  act(() => {
    const mockWS = MockWebSocket.instances[0];
    if (mockWS && mockWS.onmessage) {
      mockWS.onmessage({
        data: JSON.stringify({ type, data }),
      } as MessageEvent);
    }
  });
};