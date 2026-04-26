/**
 * Frontend Dashboard Integration Tests
 *
 * Integration tests for all 6 monitoring dashboard components:
 * 1. System Overview Component
 * 2. Performance Metrics Component
 * 3. Business Metrics Component
 * 4. Infrastructure Metrics Component
 * 5. Alerts Management Component
 * 6. User Analytics Component
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { Provider } from 'jotai';

// Components to test
import SystemOverview from '../../components/monitoring/SystemOverview';
import PerformanceMetrics from '../../components/monitoring/PerformanceMetrics';
import BusinessMetrics from '../../components/monitoring/BusinessMetrics';
import InfrastructureMetrics from '../../components/monitoring/InfrastructureMetrics';
import AlertsManagement from '../../components/monitoring/AlertsManagement';
import UserAnalytics from '../../components/monitoring/UserAnalytics';

// Monitoring store and services
import { useMonitoringStore } from '../../store/monitoringStore';
import monitoringWebSocketService from '../../services/monitoringWebsocketService';

// Mocks
import { server } from '../mocks/server';
import { rest } from 'msw';

// Test data
const mockSystemHealth = {
  overall_score: 85,
  components: {
    database: { status: 'healthy', score: 90 },
    vector_store: { status: 'healthy', score: 88 },
    graph_db: { status: 'warning', score: 75 },
    api_gateway: { status: 'healthy', score: 92 }
  },
  timestamp: new Date().toISOString()
};

const mockPerformanceMetrics = {
  response_time: { current: 245, trend: 'decreasing', target: 200 },
  throughput: { current: 1250, trend: 'stable', target: 1000 },
  error_rate: { current: 0.8, trend: 'decreasing', target: 1.0 },
  cpu_usage: { current: 65, trend: 'stable', target: 80 },
  memory_usage: { current: 72, trend: 'increasing', target: 85 }
};

const mockBusinessMetrics = {
  total_queries: 15420,
  successful_queries: 14890,
  user_satisfaction: 4.6,
  avg_response_quality: 8.2,
  daily_active_users: 342,
  documents_processed: 1284
};

const mockInfrastructureMetrics = {
  cpu_usage: { current: 65, cores: 8, load_average: [1.2, 1.5, 1.8] },
  memory_usage: { current: 72, total: 16384, available: 4592 },
  disk_usage: { current: 45, total: 500, free: 275 },
  network_io: { bytes_in: 1024000, bytes_out: 512000 },
  database_connections: { active: 15, idle: 25, max: 100 }
};

const mockAlerts = [
  {
    id: 'alert-1',
    name: 'High CPU Usage',
    severity: 'warning',
    status: 'active',
    message: 'CPU usage exceeded 80% threshold',
    created_at: new Date(Date.now() - 3600000).toISOString(),
    acknowledged_at: null,
    resolved_at: null
  },
  {
    id: 'alert-2',
    name: 'Database Connection Pool Exhausted',
    severity: 'critical',
    status: 'acknowledged',
    message: 'Database connection pool at 95% capacity',
    created_at: new Date(Date.now() - 7200000).toISOString(),
    acknowledged_at: new Date(Date.now() - 1800000).toISOString(),
    acknowledged_by: 'admin@example.com',
    resolved_at: null
  },
  {
    id: 'alert-3',
    name: 'Slow Query Response',
    severity: 'medium',
    status: 'resolved',
    message: 'Query response time exceeded 5 seconds',
    created_at: new Date(Date.now() - 10800000).toISOString(),
    acknowledged_at: new Date(Date.now() - 5400000).toISOString(),
    resolved_at: new Date(Date.now() - 1200000).toISOString(),
    resolved_by: 'system@example.com'
  }
];

const mockUserAnalytics = {
  total_users: 1250,
  active_sessions: 89,
  avg_session_duration: 1240, // seconds
  user_retention: { daily: 0.85, weekly: 0.72, monthly: 0.68 },
  top_features: [
    { name: 'Document Search', usage_count: 3420, users: 567 },
    { name: 'Knowledge Graph', usage_count: 2180, users: 423 },
    { name: 'Multimodal Query', usage_count: 1890, users: 389 }
  ],
  user_satisfaction_trend: [
    { date: '2024-01-01', score: 4.4 },
    { date: '2024-01-02', score: 4.5 },
    { date: '2024-01-03', score: 4.6 }
  ]
};

// Test wrapper component
const TestWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  return (
    <Provider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          {children}
        </BrowserRouter>
      </QueryClientProvider>
    </Provider>
  );
};

// Mock WebSocket service
jest.mock('../../services/monitoringWebsocketService', () => ({
  __esModule: true,
  default: {
    connect: jest.fn(),
    disconnect: jest.fn(),
    subscribe: jest.fn(),
    unsubscribe: jest.fn(),
    isConnected: jest.fn(() => true),
    on: jest.fn(),
    off: jest.fn()
  }
}));

// Establish API mocking before all tests
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('System Overview Component Integration', () => {
  beforeEach(() => {
    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        return res(ctx.json(mockSystemHealth));
      }),
      rest.get('/api/monitoring/dashboard', (req, res, ctx) => {
        return res(ctx.json({
          health: mockSystemHealth,
          metrics_summary: { total_metrics: 156 },
          recent_alerts: mockAlerts.filter(a => a.status === 'active'),
          service_health: mockSystemHealth.components
        }));
      })
    );
  });

  test('renders system overview with health data', async () => {
    render(
      <TestWrapper>
        <SystemOverview />
      </TestWrapper>
    );

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('System Health')).toBeInTheDocument();
    });

    // Verify overall health score
    expect(screen.getByText('85%')).toBeInTheDocument();

    // Verify component status indicators
    expect(screen.getByText('Database')).toBeInTheDocument();
    expect(screen.getByText('Vector Store')).toBeInTheDocument();
    expect(screen.getByText('Graph DB')).toBeInTheDocument();
    expect(screen.getByText('API Gateway')).toBeInTheDocument();
  });

  test('displays component health status correctly', async () => {
    render(
      <TestWrapper>
        <SystemOverview />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Database')).toBeInTheDocument();
    });

    // Verify healthy components show green status
    const databaseStatus = screen.getByTestId('component-database');
    expect(databaseStatus).toHaveClass('status-healthy');

    // Verify warning component shows yellow status
    const graphDbStatus = screen.getByTestId('component-graph_db');
    expect(graphDbStatus).toHaveClass('status-warning');
  });

  test('refreshes system health data', async () => {
    render(
      <TestWrapper>
        <SystemOverview />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('85%')).toBeInTheDocument();
    });

    // Click refresh button
    const refreshButton = screen.getByTestId('refresh-health-button');
    fireEvent.click(refreshButton);

    // Verify loading state
    expect(screen.getByTestId('health-loading')).toBeInTheDocument();

    // Verify data refreshes
    await waitFor(() => {
      expect(screen.getByTestId('health-loading')).not.toBeInTheDocument();
    });
  });

  test('shows error state on API failure', async () => {
    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Internal server error' }));
      })
    );

    render(
      <TestWrapper>
        <SystemOverview />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Unable to load system health')).toBeInTheDocument();
    });

    // Verify retry button is shown
    expect(screen.getByTestId('retry-health-button')).toBeInTheDocument();
  });
});

describe('Performance Metrics Component Integration', () => {
  beforeEach(() => {
    server.use(
      rest.get('/api/monitoring/metrics', (req, res, ctx) => {
        return res(ctx.json({
          metrics: {
            performance: mockPerformanceMetrics
          }
        }));
      }),
      rest.post('/api/monitoring/metrics', (req, res, ctx) => {
        return res(ctx.json({
          metrics: {
            performance: mockPerformanceMetrics
          }
        }));
      })
    );
  });

  test('renders performance metrics with data', async () => {
    render(
      <TestWrapper>
        <PerformanceMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Performance Metrics')).toBeInTheDocument();
    });

    // Verify key performance indicators
    expect(screen.getByText('Response Time')).toBeInTheDocument();
    expect(screen.getByText('Throughput')).toBeInTheDocument();
    expect(screen.getByText('Error Rate')).toBeInTheDocument();

    // Verify metric values
    expect(screen.getByText('245ms')).toBeInTheDocument();
    expect(screen.getByText('1,250')).toBeInTheDocument();
    expect(screen.getByText('0.8%')).toBeInTheDocument();
  });

  test('displays trend indicators correctly', async () => {
    render(
      <TestWrapper>
        <PerformanceMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByTestId('trend-response_time')).toBeInTheDocument();
    });

    // Verify decreasing trend shows down arrow
    const responseTimeTrend = screen.getByTestId('trend-response_time');
    expect(responseTimeTrend).toHaveClass('trend-decreasing');

    // Verify stable trend shows neutral indicator
    const throughputTrend = screen.getByTestId('trend-throughput');
    expect(throughputTrend).toHaveClass('trend-stable');
  });

  test('allows time range selection', async () => {
    render(
      <TestWrapper>
        <PerformanceMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Performance Metrics')).toBeInTheDocument();
    });

    // Click time range selector
    const timeRangeSelector = screen.getByTestId('time-range-selector');
    fireEvent.click(timeRangeSelector);

    // Select 24h time range
    const timeRange24h = screen.getByTestId('time-range-24h');
    fireEvent.click(timeRange24h);

    // Verify API is called with new time range
    await waitFor(() => {
      expect(screen.getByText('Last 24 hours')).toBeInTheDocument();
    });
  });

  test('displays performance charts', async () => {
    render(
      <TestWrapper>
        <PerformanceMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByTestId('performance-chart')).toBeInTheDocument();
    });

    // Verify chart elements are rendered
    expect(screen.getByTestId('chart-canvas')).toBeInTheDocument();
    expect(screen.getByTestId('chart-legend')).toBeInTheDocument();
  });

  test('shows detailed metric modal on click', async () => {
    render(
      <TestWrapper>
        <PerformanceMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Response Time')).toBeInTheDocument();
    });

    // Click on response time metric
    const responseTimeMetric = screen.getByTestId('metric-response_time');
    fireEvent.click(responseTimeMetric);

    // Verify modal opens
    await waitFor(() => {
      expect(screen.getByTestId('metric-detail-modal')).toBeInTheDocument();
    });

    // Verify modal content
    expect(screen.getByText('Response Time Details')).toBeInTheDocument();
    expect(screen.getByText('245ms')).toBeInTheDocument();
    expect(screen.getByText('Target: 200ms')).toBeInTheDocument();
  });
});

describe('Business Metrics Component Integration', () => {
  beforeEach(() => {
    server.use(
      rest.get('/api/monitoring/metrics', (req, res, ctx) => {
        return res(ctx.json({
          metrics: {
            business: mockBusinessMetrics
          }
        }));
      })
    );
  });

  test('renders business metrics with data', async () => {
    render(
      <TestWrapper>
        <BusinessMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Business Metrics')).toBeInTheDocument();
    });

    // Verify key business indicators
    expect(screen.getByText('Total Queries')).toBeInTheDocument();
    expect(screen.getByText('User Satisfaction')).toBeInTheDocument();
    expect(screen.getByText('Daily Active Users')).toBeInTheDocument();

    // Verify metric values
    expect(screen.getByText('15,420')).toBeInTheDocument();
    expect(screen.getByText('4.6')).toBeInTheDocument();
    expect(screen.getByText('342')).toBeInTheDocument();
  });

  test('displays query success rate', async () => {
    render(
      <TestWrapper>
        <BusinessMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Query Success Rate')).toBeInTheDocument();
    });

    // Calculate expected success rate
    const successRate = (mockBusinessMetrics.successful_queries / mockBusinessMetrics.total_queries * 100).toFixed(1);
    expect(screen.getByText(`${successRate}%`)).toBeInTheDocument();
  });

  test('shows user satisfaction visualization', async () => {
    render(
      <TestWrapper>
        <BusinessMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByTestId('satisfaction-chart')).toBeInTheDocument();
    });

    // Verify satisfaction score display
    expect(screen.getByText('4.6')).toBeInTheDocument();
    expect(screen.getByText('out of 5')).toBeInTheDocument();

    // Verify star rating display
    const starRating = screen.getByTestId('star-rating');
    expect(starRating).toBeInTheDocument();
  });

  test('displays document processing metrics', async () => {
    render(
      <TestWrapper>
        <BusinessMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Documents Processed')).toBeInTheDocument();
    });

    expect(screen.getByText('1,284')).toBeInTheDocument();
  });

  test('exports business metrics report', async () => {
    render(
      <TestWrapper>
        <BusinessMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Business Metrics')).toBeInTheDocument();
    });

    // Click export button
    const exportButton = screen.getByTestId('export-business-metrics');
    fireEvent.click(exportButton);

    // Verify export modal opens
    await waitFor(() => {
      expect(screen.getByTestId('export-modal')).toBeInTheDocument();
    });

    // Select CSV format
    const csvFormat = screen.getByTestId('export-format-csv');
    fireEvent.click(csvFormat);

    // Click generate export
    const generateButton = screen.getByTestId('generate-export');
    fireEvent.click(generateButton);

    // Verify success message
    await waitFor(() => {
      expect(screen.getByText('Report exported successfully')).toBeInTheDocument();
    });
  });
});

describe('Infrastructure Metrics Component Integration', () => {
  beforeEach(() => {
    server.use(
      rest.get('/api/monitoring/metrics', (req, res, ctx) => {
        return res(ctx.json({
          metrics: {
            infrastructure: mockInfrastructureMetrics
          }
        }));
      })
    );
  });

  test('renders infrastructure metrics with data', async () => {
    render(
      <TestWrapper>
        <InfrastructureMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Infrastructure Metrics')).toBeInTheDocument();
    });

    // Verify key infrastructure indicators
    expect(screen.getByText('CPU Usage')).toBeInTheDocument();
    expect(screen.getByText('Memory Usage')).toBeInTheDocument();
    expect(screen.getByText('Disk Usage')).toBeInTheDocument();

    // Verify metric values
    expect(screen.getByText('65%')).toBeInTheDocument();
    expect(screen.getByText('72%')).toBeInTheDocument();
    expect(screen.getByText('45%')).toBeInTheDocument();
  });

  test('displays CPU details', async () => {
    render(
      <TestWrapper>
        <InfrastructureMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('CPU Usage')).toBeInTheDocument();
    });

    // Verify CPU cores info
    expect(screen.getByText('8 cores')).toBeInTheDocument();

    // Verify load average
    const loadAverage = screen.getByTestId('load-average');
    expect(loadAverage).toBeInTheDocument();
  });

  test('shows memory breakdown', async () => {
    render(
      <TestWrapper>
        <InfrastructureMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Memory Usage')).toBeInTheDocument();
    });

    // Verify memory details
    expect(screen.getByText('16 GB')).toBeInTheDocument(); // Total memory
    expect(screen.getByText('4.5 GB')).toBeInTheDocument(); // Available memory

    // Verify memory visualization
    const memoryChart = screen.getByTestId('memory-chart');
    expect(memoryChart).toBeInTheDocument();
  });

  test('displays network I/O metrics', async () => {
    render(
      <TestWrapper>
        <InfrastructureMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByTestId('network-io')).toBeInTheDocument();
    });

    // Verify network metrics
    expect(screen.getByText('1.0 MB/s')).toBeInTheDocument(); // Bytes in
    expect(screen.getByText('512 KB/s')).toBeInTheDocument(); // Bytes out
  });

  test('shows database connection pool status', async () => {
    render(
      <TestWrapper>
        <InfrastructureMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Database Connections')).toBeInTheDocument();
    });

    // Verify connection counts
    expect(screen.getByText('15 active')).toBeInTheDocument();
    expect(screen.getByText('25 idle')).toBeInTheDocument();
    expect(screen.getByText('100 max')).toBeInTheDocument();

    // Verify connection pool visualization
    const connectionPoolChart = screen.getByTestId('connection-pool-chart');
    expect(connectionPoolChart).toBeInTheDocument();
  });

  test('allows infrastructure metric filtering', async () => {
    render(
      <TestWrapper>
        <InfrastructureMetrics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Infrastructure Metrics')).toBeInTheDocument();
    });

    // Click filter button
    const filterButton = screen.getByTestId('filter-metrics');
    fireEvent.click(filterButton);

    // Toggle network metrics
    const networkToggle = screen.getByTestId('toggle-network');
    fireEvent.click(networkToggle);

    // Verify network metrics are hidden
    await waitFor(() => {
      expect(screen.queryByTestId('network-io')).not.toBeInTheDocument();
    });
  });
});

describe('Alerts Management Component Integration', () => {
  beforeEach(() => {
    server.use(
      rest.get('/api/monitoring/alerts', (req, res, ctx) => {
        return res(ctx.json({
          alerts: mockAlerts
        }));
      }),
      rest.post('/api/monitoring/alerts/:alertId/acknowledge', (req, res, ctx) => {
        const { alertId } = req.params;
        return res(ctx.json({
          message: `Alert ${alertId} acknowledged successfully`
        }));
      }),
      rest.post('/api/monitoring/alerts/:alertId/resolve', (req, res, ctx) => {
        const { alertId } = req.params;
        return res(ctx.json({
          message: `Alert ${alertId} resolved successfully`
        }));
      })
    );
  });

  test('renders alerts list with data', async () => {
    render(
      <TestWrapper>
        <AlertsManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Alerts Management')).toBeInTheDocument();
    });

    // Verify alert items
    expect(screen.getByText('High CPU Usage')).toBeInTheDocument();
    expect(screen.getByText('Database Connection Pool Exhausted')).toBeInTheDocument();
    expect(screen.getByText('Slow Query Response')).toBeInTheDocument();
  });

  test('displays alert severity indicators', async () => {
    render(
      <TestWrapper>
        <AlertsManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByTestId('alert-alert-1')).toBeInTheDocument();
    });

    // Verify severity badges
    const warningBadge = screen.getByTestId('severity-warning');
    expect(warningBadge).toBeInTheDocument();
    expect(warningBadge).toHaveClass('severity-warning');

    const criticalBadge = screen.getByTestId('severity-critical');
    expect(criticalBadge).toBeInTheDocument();
    expect(criticalBadge).toHaveClass('severity-critical');
  });

  test('displays alert status indicators', async () => {
    render(
      <TestWrapper>
        <AlertsManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByTestId('alert-alert-1')).toBeInTheDocument();
    });

    // Verify status indicators
    const activeStatus = screen.getByTestId('status-active');
    expect(activeStatus).toBeInTheDocument();
    expect(activeStatus).toHaveClass('status-active');

    const acknowledgedStatus = screen.getByTestId('status-acknowledged');
    expect(acknowledgedStatus).toBeInTheDocument();
    expect(acknowledgedStatus).toHaveClass('status-acknowledged');

    const resolvedStatus = screen.getByTestId('status-resolved');
    expect(resolvedStatus).toBeInTheDocument();
    expect(resolvedStatus).toHaveClass('status-resolved');
  });

  test('allows acknowledging alerts', async () => {
    render(
      <TestWrapper>
        <AlertsManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('High CPU Usage')).toBeInTheDocument();
    });

    // Click acknowledge button for active alert
    const acknowledgeButton = screen.getByTestId('acknowledge-alert-1');
    fireEvent.click(acknowledgeButton);

    // Verify acknowledgment modal
    await waitFor(() => {
      expect(screen.getByTestId('acknowledge-modal')).toBeInTheDocument();
    });

    // Enter acknowledgment message
    const messageInput = screen.getByTestId('acknowledgment-message');
    fireEvent.change(messageInput, { target: { value: 'Acknowledging CPU alert' } });

    // Confirm acknowledgment
    const confirmButton = screen.getByTestId('confirm-acknowledge');
    fireEvent.click(confirmButton);

    // Verify success message
    await waitFor(() => {
      expect(screen.getByText('Alert acknowledged successfully')).toBeInTheDocument();
    });
  });

  test('allows resolving alerts', async () => {
    render(
      <TestWrapper>
        <AlertsManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Database Connection Pool Exhausted')).toBeInTheDocument();
    });

    // Click resolve button for acknowledged alert
    const resolveButton = screen.getByTestId('resolve-alert-2');
    fireEvent.click(resolveButton);

    // Verify resolution modal
    await waitFor(() => {
      expect(screen.getByTestId('resolve-modal')).toBeInTheDocument();
    });

    // Enter resolution message
    const messageInput = screen.getByTestId('resolution-message');
    fireEvent.change(messageInput, { target: { value: 'Database connections optimized' } });

    // Confirm resolution
    const confirmButton = screen.getByTestId('confirm-resolve');
    fireEvent.click(confirmButton);

    // Verify success message
    await waitFor(() => {
      expect(screen.getByText('Alert resolved successfully')).toBeInTheDocument();
    });
  });

  test('filters alerts by severity', async () => {
    render(
      <TestWrapper>
        <AlertsManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Alerts Management')).toBeInTheDocument();
    });

    // Click severity filter
    const severityFilter = screen.getByTestId('severity-filter');
    fireEvent.click(severityFilter);

    // Select critical severity only
    const criticalOption = screen.getByTestId('severity-critical');
    fireEvent.click(criticalOption);

    // Verify only critical alerts are shown
    await waitFor(() => {
      expect(screen.getByText('Database Connection Pool Exhausted')).toBeInTheDocument();
      expect(screen.queryByText('High CPU Usage')).not.toBeInTheDocument();
    });
  });

  test('filters alerts by status', async () => {
    render(
      <TestWrapper>
        <AlertsManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Alerts Management')).toBeInTheDocument();
    });

    // Click status filter
    const statusFilter = screen.getByTestId('status-filter');
    fireEvent.click(statusFilter);

    // Select active status only
    const activeOption = screen.getByTestId('status-active');
    fireEvent.click(activeOption);

    // Verify only active alerts are shown
    await waitFor(() => {
      expect(screen.getByText('High CPU Usage')).toBeInTheDocument();
      expect(screen.queryByText('Database Connection Pool Exhausted')).not.toBeInTheDocument();
      expect(screen.queryByText('Slow Query Response')).not.toBeInTheDocument();
    });
  });

  test('searches alerts by name', async () => {
    render(
      <TestWrapper>
        <AlertsManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Alerts Management')).toBeInTheDocument();
    });

    // Enter search term
    const searchInput = screen.getByTestId('alert-search');
    fireEvent.change(searchInput, { target: { value: 'CPU' } });

    // Verify search results
    await waitFor(() => {
      expect(screen.getByText('High CPU Usage')).toBeInTheDocument();
      expect(screen.queryByText('Database Connection Pool Exhausted')).not.toBeInTheDocument();
    });
  });

  test('exports alerts report', async () => {
    render(
      <TestWrapper>
        <AlertsManagement />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Alerts Management')).toBeInTheDocument();
    });

    // Click export button
    const exportButton = screen.getByTestId('export-alerts');
    fireEvent.click(exportButton);

    // Verify export modal opens
    await waitFor(() => {
      expect(screen.getByTestId('export-alerts-modal')).toBeInTheDocument();
    });

    // Select PDF format
    const pdfFormat = screen.getByTestId('export-format-pdf');
    fireEvent.click(pdfFormat);

    // Click generate export
    const generateButton = screen.getByTestId('generate-alerts-export');
    fireEvent.click(generateButton);

    // Verify success message
    await waitFor(() => {
      expect(screen.getByText('Alerts report exported successfully')).toBeInTheDocument();
    });
  });
});

describe('User Analytics Component Integration', () => {
  beforeEach(() => {
    server.use(
      rest.get('/api/monitoring/analytics/users', (req, res, ctx) => {
        return res(ctx.json(mockUserAnalytics));
      })
    );
  });

  test('renders user analytics with data', async () => {
    render(
      <TestWrapper>
        <UserAnalytics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('User Analytics')).toBeInTheDocument();
    });

    // Verify key user metrics
    expect(screen.getByText('Total Users')).toBeInTheDocument();
    expect(screen.getByText('Active Sessions')).toBeInTheDocument();
    expect(screen.getByText('Avg Session Duration')).toBeInTheDocument();

    // Verify metric values
    expect(screen.getByText('1,250')).toBeInTheDocument();
    expect(screen.getByText('89')).toBeInTheDocument();
    expect(screen.getByText('20m 40s')).toBeInTheDocument(); // 1240 seconds formatted
  });

  test('displays user retention metrics', async () => {
    render(
      <TestWrapper>
        <UserAnalytics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('User Retention')).toBeInTheDocument();
    });

    // Verify retention rates
    expect(screen.getByText('85%')).toBeInTheDocument(); // Daily retention
    expect(screen.getByText('72%')).toBeInTheDocument(); // Weekly retention
    expect(screen.getByText('68%')).toBeInTheDocument(); // Monthly retention
  });

  test('shows top features usage', async () => {
    render(
      <TestWrapper>
        <UserAnalytics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Top Features')).toBeInTheDocument();
    });

    // Verify feature list
    expect(screen.getByText('Document Search')).toBeInTheDocument();
    expect(screen.getByText('Knowledge Graph')).toBeInTheDocument();
    expect(screen.getByText('Multimodal Query')).toBeInTheDocument();

    // Verify usage counts
    expect(screen.getByText('3,420 uses')).toBeInTheDocument();
    expect(screen.getByText('2,180 uses')).toBeInTheDocument();
    expect(screen.getByText('1,890 uses')).toBeInTheDocument();
  });

  test('displays user satisfaction trend', async () => {
    render(
      <TestWrapper>
        <UserAnalytics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByTestId('satisfaction-trend-chart')).toBeInTheDocument();
    });

    // Verify trend chart is rendered
    const trendChart = screen.getByTestId('satisfaction-trend-chart');
    expect(trendChart).toBeInTheDocument();

    // Verify trend data points
    expect(screen.getByText('4.4')).toBeInTheDocument();
    expect(screen.getByText('4.5')).toBeInTheDocument();
    expect(screen.getByText('4.6')).toBeInTheDocument();
  });

  test('allows time period selection', async () => {
    render(
      <TestWrapper>
        <UserAnalytics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('User Analytics')).toBeInTheDocument();
    });

    // Click period selector
    const periodSelector = screen.getByTestId('period-selector');
    fireEvent.click(periodSelector);

    // Select weekly period
    const weeklyOption = screen.getByTestId('period-weekly');
    fireEvent.click(weeklyOption);

    // Verify period is updated
    await waitFor(() => {
      expect(screen.getByText('Last 7 days')).toBeInTheDocument();
    });
  });

  test('drills down into feature details', async () => {
    render(
      <TestWrapper>
        <UserAnalytics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('Document Search')).toBeInTheDocument();
    });

    // Click on feature
    const featureItem = screen.getByTestId('feature-document-search');
    fireEvent.click(featureItem);

    // Verify feature detail modal
    await waitFor(() => {
      expect(screen.getByTestId('feature-detail-modal')).toBeInTheDocument();
    });

    // Verify modal content
    expect(screen.getByText('Document Search Details')).toBeInTheDocument();
    expect(screen.getByText('3,420 total uses')).toBeInTheDocument();
    expect(screen.getByText('567 unique users')).toBeInTheDocument();
  });

  test('exports user analytics report', async () => {
    render(
      <TestWrapper>
        <UserAnalytics />
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('User Analytics')).toBeInTheDocument();
    });

    // Click export button
    const exportButton = screen.getByTestId('export-analytics');
    fireEvent.click(exportButton);

    // Verify export modal opens
    await waitFor(() => {
      expect(screen.getByTestId('export-analytics-modal')).toBeInTheDocument();
    });

    // Select Excel format
    const excelFormat = screen.getByTestId('export-format-excel');
    fireEvent.click(excelFormat);

    // Click generate export
    const generateButton = screen.getByTestId('generate-analytics-export');
    fireEvent.click(generateButton);

    // Verify success message
    await waitFor(() => {
      expect(screen.getByText('User analytics exported successfully')).toBeInTheDocument();
    });
  });
});

describe('Dashboard Integration Tests', () => {
  test('all components render together without conflicts', async () => {
    render(
      <TestWrapper>
        <div>
          <SystemOverview />
          <PerformanceMetrics />
          <BusinessMetrics />
          <InfrastructureMetrics />
          <AlertsManagement />
          <UserAnalytics />
        </div>
      </TestWrapper>
    );

    // Wait for all components to load
    await waitFor(() => {
      expect(screen.getByText('System Health')).toBeInTheDocument();
      expect(screen.getByText('Performance Metrics')).toBeInTheDocument();
      expect(screen.getByText('Business Metrics')).toBeInTheDocument();
      expect(screen.getByText('Infrastructure Metrics')).toBeInTheDocument();
      expect(screen.getByText('Alerts Management')).toBeInTheDocument();
      expect(screen.getByText('User Analytics')).toBeInTheDocument();
    });

    // Verify no console errors
    expect(console.error).not.toHaveBeenCalled();
  });

  test('components share real-time updates correctly', async () => {
    const mockWebSocketService = monitoringWebSocketService;

    render(
      <TestWrapper>
        <div>
          <SystemOverview />
          <PerformanceMetrics />
          <AlertsManagement />
        </div>
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('System Health')).toBeInTheDocument();
    });

    // Simulate WebSocket update
    const updateData = {
      type: 'health_update',
      data: {
        ...mockSystemHealth,
        overall_score: 90 // Updated score
      }
    };

    act(() => {
      // Simulate receiving WebSocket message
      mockWebSocketService.on('message', updateData);
    });

    // Verify component updates with new data
    await waitFor(() => {
      expect(screen.getByText('90%')).toBeInTheDocument();
    });
  });

  test('responsive design works across components', async () => {
    // Test desktop view
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 1920 });

    render(
      <TestWrapper>
        <div>
          <SystemOverview />
          <PerformanceMetrics />
          <BusinessMetrics />
          <InfrastructureMetrics />
          <AlertsManagement />
          <UserAnalytics />
        </div>
      </TestWrapper>
    );

    await waitFor(() => {
      expect(screen.getByText('System Health')).toBeInTheDocument();
    });

    // Verify desktop layout
    expect(screen.getByTestId('dashboard-grid')).toHaveClass('grid-desktop');

    // Test tablet view
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 768 });
    fireEvent.resize(window);

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-grid')).toHaveClass('grid-tablet');
    });

    // Test mobile view
    Object.defineProperty(window, 'innerWidth', { writable: true, configurable: true, value: 375 });
    fireEvent.resize(window);

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-grid')).toHaveClass('grid-mobile');
    });
  });

  test('error handling works across all components', async () => {
    // Mock API failures
    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        return res(ctx.status(500));
      }),
      rest.get('/api/monitoring/metrics', (req, res, ctx) => {
        return res(ctx.status(500));
      }),
      rest.get('/api/monitoring/alerts', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(
      <TestWrapper>
        <div>
          <SystemOverview />
          <PerformanceMetrics />
          <AlertsManagement />
        </div>
      </TestWrapper>
    );

    // Verify error states are shown
    await waitFor(() => {
      expect(screen.getByText('Unable to load system health')).toBeInTheDocument();
      expect(screen.getByText('Unable to load performance metrics')).toBeInTheDocument();
      expect(screen.getByText('Unable to load alerts')).toBeInTheDocument();
    });

    // Verify retry buttons are available
    expect(screen.getAllByTestId('retry-button')).toHaveLength(3);
  });
});