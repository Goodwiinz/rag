/**
 * React Query Integration Tests for Monitoring
 *
 * Tests for React Query caching, background updates, and data synchronization:
 * - Query caching and stale-while-revalidate strategies
 * - Background refetching and data synchronization
 * - Optimistic updates and rollback
 * - Query invalidation and cache management
 * - Error handling and retry mechanisms
 * - Pagination and infinite queries
 * - WebSocket integration with React Query
 * - Performance under concurrent queries
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';

// React Query hooks for monitoring data
import { useSystemHealthQuery } from '../../hooks/queries/useSystemHealthQuery';
import { useMetricsQuery } from '../../hooks/queries/useMetricsQuery';
import { useAlertsQuery } from '../../hooks/queries/useAlertsQuery';
import { useAlertManagement } from '../../hooks/mutations/useAlertManagement';
import { useRealTimeSubscription } from '../../hooks/subscriptions/useRealTimeSubscription';

// Monitoring components that use React Query
import SystemHealth from '../../components/monitoring/SystemHealth';
import MetricsDashboard from '../../components/monitoring/MetricsDashboard';
import AlertsPanel from '../../components/monitoring/AlertsPanel';

// Mocks
import { server } from '../mocks/server';
import { rest } from 'msw';
import { mockWebSocketService } from '../mocks/websocket';

// Test data
const mockSystemHealth = {
  overall_score: 85,
  components: {
    database: { status: 'healthy', score: 90 },
    vector_store: { status: 'healthy', score: 88 },
    graph_db: { status: 'warning', score: 75 }
  },
  timestamp: new Date().toISOString()
};

const mockMetrics = {
  performance: {
    response_time: { current: 245, trend: 'decreasing' },
    throughput: { current: 1250, trend: 'stable' },
    error_rate: { current: 0.8, trend: 'decreasing' }
  },
  business: {
    total_queries: 15420,
    user_satisfaction: 4.6,
    daily_active_users: 342
  }
};

const mockAlerts = [
  {
    id: 'alert-1',
    name: 'High CPU Usage',
    severity: 'warning',
    status: 'active',
    message: 'CPU usage exceeded threshold',
    created_at: new Date().toISOString()
  },
  {
    id: 'alert-2',
    name: 'Memory Warning',
    severity: 'critical',
    status: 'active',
    message: 'Memory usage approaching limit',
    created_at: new Date().toISOString()
  }
];

// Test wrapper with QueryClient
const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      gcTime: 1000, // 1 second for testing
      staleTime: 5000, // 5 seconds
    },
    mutations: {
      retry: false,
    }
  }
});

const TestWrapper: React.FC<{ children: React.ReactNode; client?: QueryClient }> = ({
  children,
  client = createTestQueryClient()
}) => (
  <QueryClientProvider client={client}>
    <BrowserRouter>
      {children}
    </BrowserRouter>
  </QueryClientProvider>
);

// Mock WebSocket service
jest.mock('../../services/monitoringWebsocketService', () => ({
  default: mockWebSocketService
}));

// Establish API mocking
beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  // Clear query cache between tests
  localStorage.clear();
});
afterAll(() => server.close());

describe('React Query - Basic Query Functionality', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  test('fetches and caches system health data', async () => {
    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        return res(ctx.json(mockSystemHealth));
      })
    );

    function TestComponent() {
      const { data, isLoading, error, isFetching } = useSystemHealthQuery();

      return (
        <div>
          {isLoading && <div data-testid="loading">Loading...</div>}
          {error && <div data-testid="error">Error: {error.message}</div>}
          {data && <div data-testid="health-score">{data.overall_score}</div>}
          {isFetching && <div data-testid="fetching">Fetching...</div>}
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Initial loading state
    expect(screen.getByTestId('loading')).toBeInTheDocument();

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toBeInTheDocument();
    });

    // Verify data is displayed
    expect(screen.getByTestId('health-score')).toHaveTextContent('85');
    expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
    expect(screen.queryByTestId('fetching')).not.toBeInTheDocument();
  });

  test('caches query results and serves from cache', async () => {
    let requestCount = 0;

    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        requestCount++;
        return res(ctx.json(mockSystemHealth));
      })
    );

    function TestComponent() {
      const { data } = useSystemHealthQuery();
      return data ? <div data-testid="health-score">{data.overall_score}</div> : null;
    }

    function TestApp() {
      const [showComponent, setShowComponent] = React.useState(true);

      return (
        <div>
          <button
            data-testid="toggle-button"
            onClick={() => setShowComponent(!showComponent)}
          >
            Toggle
          </button>
          {showComponent && <TestComponent />}
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestApp />
      </TestWrapper>
    );

    // Wait for initial data load
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toBeInTheDocument();
    });

    expect(requestCount).toBe(1);

    // Unmount and remount component
    fireEvent.click(screen.getByTestId('toggle-button'));
    expect(screen.queryByTestId('health-score')).not.toBeInTheDocument();

    // Remount component
    fireEvent.click(screen.getByTestId('toggle-button'));

    // Should serve from cache (no additional request)
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toBeInTheDocument();
    });

    expect(requestCount).toBe(1); // Still only one request
  });

  test('handles query errors and retry logic', async () => {
    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Server error' }));
      })
    );

    function TestComponent() {
      const { data, isLoading, error, refetch } = useSystemHealthQuery();

      return (
        <div>
          {isLoading && <div data-testid="loading">Loading...</div>}
          {error && (
            <div>
              <div data-testid="error">Error: {error.message}</div>
              <button data-testid="retry-button" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          )}
          {data && <div data-testid="health-score">{data.overall_score}</div>}
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Should show error state
    await waitFor(() => {
      expect(screen.getByTestId('error')).toBeInTheDocument();
    });

    // Retry functionality
    server.resetHandlers(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        return res(ctx.json(mockSystemHealth));
      })
    );

    fireEvent.click(screen.getByTestId('retry-button'));

    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toBeInTheDocument();
    });

    expect(screen.getByTestId('health-score')).toHaveTextContent('85');
  });
});

describe('React Query - Background Refetching', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  test('automatically refetches stale data', async () => {
    let requestCount = 0;

    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        requestCount++;
        return res(ctx.json({
          ...mockSystemHealth,
          overall_score: 85 + requestCount // Increment score each request
        }));
      })
    );

    function TestComponent() {
      const { data, isFetching } = useSystemHealthQuery({
        staleTime: 1000, // 1 second stale time
        refetchInterval: 2000 // Refetch every 2 seconds
      });

      return (
        <div>
          {data && <div data-testid="health-score">{data.overall_score}</div>}
          {isFetching && <div data-testid="fetching">Fetching...</div>}
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Initial load
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toHaveTextContent('86');
    });
    expect(requestCount).toBe(1);

    // Wait for automatic refetch
    await waitFor(
      () => {
        expect(screen.getByTestId('health-score')).toHaveTextContent('87');
      },
      { timeout: 3000 }
    );

    expect(requestCount).toBe(2);
    expect(screen.getByTestId('fetching')).toBeInTheDocument();
  });

  test('handles window focus refetching', async () => {
    let requestCount = 0;

    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        requestCount++;
        return res(ctx.json({
          ...mockSystemHealth,
          overall_score: 85 + requestCount
        }));
      })
    );

    function TestComponent() {
      const { data } = useSystemHealthQuery({
        refetchOnWindowFocus: true
      });

      return data ? <div data-testid="health-score">{data.overall_score}</div> : null;
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Initial load
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toHaveTextContent('86');
    });
    expect(requestCount).toBe(1);

    // Simulate window focus
    act(() => {
      window.dispatchEvent(new Event('focus'));
    });

    // Should trigger refetch
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toHaveTextContent('87');
    });

    expect(requestCount).toBe(2);
  });

  test('handles network reconnect refetching', async () => {
    let requestCount = 0;

    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        requestCount++;
        return res(ctx.json({
          ...mockSystemHealth,
          overall_score: 85 + requestCount
        }));
      })
    );

    function TestComponent() {
      const { data } = useSystemHealthQuery({
        refetchOnReconnect: true
      });

      return data ? <div data-testid="health-score">{data.overall_score}</div> : null;
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Initial load
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toHaveTextContent('86');
    });
    expect(requestCount).toBe(1);

    // Simulate network reconnect
    act(() => {
      window.dispatchEvent(new Event('online'));
    });

    // Should trigger refetch
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toHaveTextContent('87');
    });

    expect(requestCount).toBe(2);
  });
});

describe('React Query - Mutations and Optimistic Updates', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  test('performs alert acknowledgment with optimistic update', async () => {
    let mutationCount = 0;

    server.use(
      rest.get('/api/monitoring/alerts', (req, res, ctx) => {
        return res(ctx.json({ alerts: mockAlerts }));
      }),
      rest.post('/api/monitoring/alerts/:alertId/acknowledge', (req, res, ctx) => {
        mutationCount++;
        const { alertId } = req.params;

        // Simulate server delay
        return res(
          ctx.delay(100),
          ctx.json({
            message: `Alert ${alertId} acknowledged`,
            acknowledged_at: new Date().toISOString()
          })
        );
      })
    );

    function TestComponent() {
      const { data: alerts } = useAlertsQuery();
      const acknowledgeAlert = useAlertManagement();

      const handleAcknowledge = (alertId: string) => {
        acknowledgeAlert.mutate({
          alertId,
          action: 'acknowledge',
          message: 'Test acknowledgment'
        });
      };

      return (
        <div>
          <div data-testid="alert-count">{alerts?.alerts.length || 0}</div>
          {alerts?.alerts.map(alert => (
            <div key={alert.id} data-testid={`alert-${alert.id}`}>
              <span data-testid={`status-${alert.id}`}>{alert.status}</span>
              <button
                data-testid={`acknowledge-${alert.id}`}
                onClick={() => handleAcknowledge(alert.id)}
                disabled={acknowledgeAlert.isPending}
              >
                Acknowledge
              </button>
            </div>
          ))}
          {acknowledgeAlert.isPending && <div data-testid="pending">Pending...</div>}
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Wait for initial data
    await waitFor(() => {
      expect(screen.getByTestId('alert-count')).toHaveTextContent('2');
    });

    // Verify initial alert status
    expect(screen.getByTestId('status-alert-1')).toHaveTextContent('active');

    // Click acknowledge button
    fireEvent.click(screen.getByTestId('acknowledge-alert-1'));

    // Should show optimistic update immediately (status changes to acknowledged)
    await waitFor(() => {
      expect(screen.getByTestId('status-alert-1')).toHaveTextContent('acknowledged');
    });

    // Should show pending state
    expect(screen.getByTestId('pending')).toBeInTheDocument();

    // Wait for mutation to complete
    await waitFor(() => {
      expect(screen.queryByTestId('pending')).not.toBeInTheDocument();
    });

    // Verify mutation was called
    expect(mutationCount).toBe(1);
  });

  test('handles mutation errors and rollback', async () => {
    server.use(
      rest.get('/api/monitoring/alerts', (req, res, ctx) => {
        return res(ctx.json({ alerts: mockAlerts }));
      }),
      rest.post('/api/monitoring/alerts/:alertId/acknowledge', (req, res, ctx) => {
        return res(
          ctx.status(500),
          ctx.json({ error: 'Failed to acknowledge alert' })
        );
      })
    );

    function TestComponent() {
      const { data: alerts } = useAlertsQuery();
      const acknowledgeAlert = useAlertManagement();

      const handleAcknowledge = (alertId: string) => {
        acknowledgeAlert.mutate({
          alertId,
          action: 'acknowledge',
          message: 'Test acknowledgment'
        });
      };

      return (
        <div>
          {alerts?.alerts.map(alert => (
            <div key={alert.id} data-testid={`alert-${alert.id}`}>
              <span data-testid={`status-${alert.id}`}>{alert.status}</span>
              <button
                data-testid={`acknowledge-${alert.id}`}
                onClick={() => handleAcknowledge(alert.id)}
              >
                Acknowledge
              </button>
            </div>
          ))}
          {acknowledgeAlert.isError && (
            <div data-testid="error">Mutation failed</div>
          )}
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Wait for initial data
    await waitFor(() => {
      expect(screen.getByTestId('status-alert-1')).toBeInTheDocument();
    });

    const initialStatus = screen.getByTestId('status-alert-1').textContent;

    // Click acknowledge button
    fireEvent.click(screen.getByTestId('acknowledge-alert-1'));

    // Should show optimistic update
    await waitFor(() => {
      expect(screen.getByTestId('status-alert-1')).toHaveTextContent('acknowledged');
    });

    // Wait for error and rollback
    await waitFor(() => {
      expect(screen.getByTestId('status-alert-1')).toHaveTextContent(initialStatus);
    });

    // Should show error state
    expect(screen.getByTestId('error')).toBeInTheDocument();
  });
});

describe('React Query - Query Invalidation and Cache Management', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  test('invalidates related queries after mutation', async () => {
    let alertsRequestCount = 0;
    let metricsRequestCount = 0;

    server.use(
      rest.get('/api/monitoring/alerts', (req, res, ctx) => {
        alertsRequestCount++;
        return res(ctx.json({ alerts: mockAlerts }));
      }),
      rest.get('/api/monitoring/metrics', (req, res, ctx) => {
        metricsRequestCount++;
        return res(ctx.json({ metrics: mockMetrics }));
      }),
      rest.post('/api/monitoring/alerts/:alertId/resolve', (req, res, ctx) => {
        return res(ctx.json({ message: 'Alert resolved' }));
      })
    );

    function TestComponent() {
      const { data: alerts } = useAlertsQuery();
      const { data: metrics } = useMetricsQuery();
      const resolveAlert = useAlertManagement();

      const handleResolve = (alertId: string) => {
        resolveAlert.mutate({
          alertId,
          action: 'resolve',
          message: 'Test resolution'
        });
      };

      return (
        <div>
          <div data-testid="alerts-request-count">{alertsRequestCount}</div>
          <div data-testid="metrics-request-count">{metricsRequestCount}</div>
          <button
            data-testid="resolve-alert-1"
            onClick={() => handleResolve('alert-1')}
          >
            Resolve Alert
          </button>
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Wait for initial queries
    await waitFor(() => {
      expect(screen.getByTestId('alerts-request-count')).toHaveTextContent('1');
      expect(screen.getByTestId('metrics-request-count')).toHaveTextContent('1');
    });

    // Resolve alert (should invalidate related queries)
    fireEvent.click(screen.getByTestId('resolve-alert-1'));

    // Wait for refetch of invalidated queries
    await waitFor(() => {
      expect(screen.getByTestId('alerts-request-count')).toHaveTextContent('2');
      expect(screen.getByTestId('metrics-request-count')).toHaveTextContent('2');
    });
  });

  test('manually invalidates queries', async () => {
    let requestCount = 0;

    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        requestCount++;
        return res(ctx.json({
          ...mockSystemHealth,
          overall_score: 85 + requestCount
        }));
      })
    );

    function TestComponent() {
      const { data } = useSystemHealthQuery();
      const queryClient = useQueryClient();

      const handleInvalidate = () => {
        queryClient.invalidateQueries({ queryKey: ['systemHealth'] });
      };

      return (
        <div>
          <div data-testid="health-score">{data?.overall_score}</div>
          <div data-testid="request-count">{requestCount}</div>
          <button data-testid="invalidate-button" onClick={handleInvalidate}>
            Invalidate
          </button>
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Initial load
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toHaveTextContent('86');
    });

    // Manually invalidate
    fireEvent.click(screen.getByTestId('invalidate-button'));

    // Should trigger refetch
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toHaveTextContent('87');
    });

    expect(screen.getByTestId('request-count')).toHaveTextContent('2');
  });

  test('removes specific queries from cache', async () => {
    let requestCount = 0;

    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        requestCount++;
        return res(ctx.json(mockSystemHealth));
      })
    );

    function TestComponent() {
      const { data } = useSystemHealthQuery();
      const queryClient = useQueryClient();

      const handleRemove = () => {
        queryClient.removeQueries({ queryKey: ['systemHealth'] });
      };

      return (
        <div>
          <div data-testid="has-data">{data ? 'yes' : 'no'}</div>
          <div data-testid="request-count">{requestCount}</div>
          <button data-testid="remove-button" onClick={handleRemove}>
            Remove from Cache
          </button>
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Initial load
    await waitFor(() => {
      expect(screen.getByTestId('has-data')).toHaveTextContent('yes');
    });

    // Remove from cache
    fireEvent.click(screen.getByTestId('remove-button'));

    // Data should be gone from cache
    expect(screen.getByTestId('has-data')).toHaveTextContent('no');

    // Next access should trigger new request
    await waitFor(() => {
      expect(screen.getByTestId('has-data')).toHaveTextContent('yes');
    });

    expect(screen.getByTestId('request-count')).toHaveTextContent('2');
  });
});

describe('React Query - Pagination and Infinite Queries', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  test('handles paginated alerts correctly', async () => {
    server.use(
      rest.get('/api/monitoring/alerts', (req, res, ctx) => {
        const page = Number(req.url.searchParams.get('page')) || 1;
        const pageSize = 10;

        const allAlerts = Array.from({ length: 25 }, (_, i) => ({
          id: `alert-${i}`,
          name: `Alert ${i}`,
          severity: i % 3 === 0 ? 'critical' : 'warning',
          status: 'active'
        }));

        const startIndex = (page - 1) * pageSize;
        const endIndex = startIndex + pageSize;
        const pageAlerts = allAlerts.slice(startIndex, endIndex);

        return res(ctx.json({
          alerts: pageAlerts,
          pagination: {
            page,
            pageSize,
            total: allAlerts.length,
            totalPages: Math.ceil(allAlerts.length / pageSize)
          }
        }));
      })
    );

    function TestComponent() {
      const [page, setPage] = React.useState(1);
      const { data, isLoading, isFetching } = useAlertsQuery({ page });

      return (
        <div>
          {isLoading && <div data-testid="loading">Loading...</div>}
          {isFetching && <div data-testid="fetching">Fetching...</div>}
          <div data-testid="current-page">{page}</div>
          <div data-testid="total-alerts">{data?.pagination.total || 0}</div>
          <div data-testid="page-alerts">{data?.alerts.length || 0}</div>
          <button
            data-testid="next-page"
            onClick={() => setPage(p => p + 1)}
            disabled={page >= (data?.pagination.totalPages || 1)}
          >
            Next Page
          </button>
          <button
            data-testid="prev-page"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
          >
            Previous Page
          </button>
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // First page
    await waitFor(() => {
      expect(screen.getByTestId('current-page')).toHaveTextContent('1');
      expect(screen.getByTestId('total-alerts')).toHaveTextContent('25');
      expect(screen.getByTestId('page-alerts')).toHaveTextContent('10');
    });

    // Next page
    fireEvent.click(screen.getByTestId('next-page'));

    await waitFor(() => {
      expect(screen.getByTestId('current-page')).toHaveTextContent('2');
      expect(screen.getByTestId('page-alerts')).toHaveTextContent('10');
    });

    // Next page again
    fireEvent.click(screen.getByTestId('next-page'));

    await waitFor(() => {
      expect(screen.getByTestId('current-page')).toHaveTextContent('3');
      expect(screen.getByTestId('page-alerts')).toHaveTextContent('5'); // Last page with fewer items
    });

    // Should be disabled on last page
    expect(screen.getByTestId('next-page')).toBeDisabled();

    // Previous page
    fireEvent.click(screen.getByTestId('prev-page'));

    await waitFor(() => {
      expect(screen.getByTestId('current-page')).toHaveTextContent('2');
    });
  });

  test('handles infinite scroll for logs', async () => {
    let requestCount = 0;

    server.use(
      rest.get('/api/monitoring/logs', (req, res, ctx) => {
        requestCount++;
        const pageParam = Number(req.url.searchParams.get('page')) || 1;
        const pageSize = 20;

        const logs = Array.from({ length: 100 }, (_, i) => ({
          id: `log-${i}`,
          level: ['INFO', 'WARNING', 'ERROR'][i % 3],
          message: `Log message ${i}`,
          timestamp: new Date(Date.now() - i * 60000).toISOString()
        }));

        const startIndex = (pageParam - 1) * pageSize;
        const endIndex = startIndex + pageSize;
        const pageLogs = logs.slice(startIndex, endIndex);

        const hasNextPage = endIndex < logs.length;

        return res(ctx.json({
          logs: pageLogs,
          nextPage: hasNextPage ? pageParam + 1 : null
        }));
      })
    );

    function TestComponent() {
      const {
        data,
        fetchNextPage,
        hasNextPage,
        isFetchingNextPage,
        isFetching
      } = useInfiniteLogsQuery();

      return (
        <div>
          <div data-testid="request-count">{requestCount}</div>
          <div data-testid="total-logs">{data?.pages.flat().length || 0}</div>
          <button
            data-testid="load-more"
            onClick={() => fetchNextPage()}
            disabled={!hasNextPage || isFetchingNextPage}
          >
            Load More
          </button>
          {isFetching && <div data-testid="fetching">Fetching...</div>}
          {isFetchingNextPage && <div data-testid="fetching-next">Fetching next...</div>}
        </div>
      );
    }

    // Mock infinite query hook
    const useInfiniteLogsQuery = () => {
      return useInfiniteQuery({
        queryKey: ['logs'],
        queryFn: ({ pageParam = 1 }) =>
          fetch(`/api/monitoring/logs?page=${pageParam}`).then(res => res.json()),
        getNextPageParam: (lastPage) => lastPage.nextPage,
        initialPageParam: 1
      });
    };

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Initial load
    await waitFor(() => {
      expect(screen.getByTestId('total-logs')).toHaveTextContent('20');
    });

    expect(screen.getByTestId('request-count')).toBe(1);

    // Load more
    fireEvent.click(screen.getByTestId('load-more'));

    await waitFor(() => {
      expect(screen.getByTestId('total-logs')).toHaveTextContent('40');
    });

    expect(screen.getByTestId('request-count')).toBe(2);

    // Continue loading until no more pages
    let loadCount = 2;
    while (screen.getByTestId('load-more')).isEnabled && loadCount < 6) {
      fireEvent.click(screen.getByTestId('load-more'));
      loadCount++;

      await waitFor(() => {
        const currentLogs = parseInt(screen.getByTestId('total-logs').textContent || '0');
        expect(currentLogs).toBeGreaterThan(0);
      });
    }

    // Should have loaded all logs
    await waitFor(() => {
      expect(screen.getByTestId('total-logs')).toHaveTextContent('100');
    });
  });
});

describe('React Query - WebSocket Integration', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  test('updates queries based on WebSocket messages', async () => {
    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        return res(ctx.json(mockSystemHealth));
      })
    );

    function TestComponent() {
      const { data } = useSystemHealthQuery();
      useRealTimeSubscription(['health_update']);

      return (
        <div>
          {data && (
            <div data-testid="health-score">{data.overall_score}</div>
          )}
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Initial load
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toHaveTextContent('85');
    });

    // Simulate WebSocket message
    act(() => {
      mockWebSocketService.simulateMessage({
        type: 'health_update',
        data: {
          ...mockSystemHealth,
          overall_score: 92
        }
      });
    });

    // Should update React Query cache
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toHaveTextContent('92');
    });
  });

  test('handles WebSocket reconnection', async () => {
    let connectionCount = 0;

    const mockWebSocketServiceWithReconnect = {
      ...mockWebSocketService,
      connect: jest.fn(() => {
        connectionCount++;
        return Promise.resolve();
      }),
      disconnect: jest.fn(() => Promise.resolve()),
      on: jest.fn(),
      off: jest.fn()
    };

    jest.mock('../../services/monitoringWebsocketService', () => ({
      default: mockWebSocketServiceWithReconnect
    }));

    function TestComponent() {
      useRealTimeSubscription(['metrics_update', 'alerts_update']);
      return <div data-testid="subscription-active">Active</div>;
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    expect(screen.getByTestId('subscription-active')).toBeInTheDocument();
    expect(mockWebSocketServiceWithReconnect.connect).toHaveBeenCalled();
  });
});

describe('React Query - Performance and Concurrent Queries', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  test('handles multiple concurrent queries efficiently', async () => {
    let healthRequestCount = 0;
    let metricsRequestCount = 0;
    let alertsRequestCount = 0;

    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        healthRequestCount++;
        return res(ctx.json(mockSystemHealth));
      }),
      rest.get('/api/monitoring/metrics', (req, res, ctx) => {
        metricsRequestCount++;
        return res(ctx.json({ metrics: mockMetrics }));
      }),
      rest.get('/api/monitoring/alerts', (req, res, ctx) => {
        alertsRequestCount++;
        return res(ctx.json({ alerts: mockAlerts }));
      })
    );

    function TestComponent() {
      const { data: health } = useSystemHealthQuery();
      const { data: metrics } = useMetricsQuery();
      const { data: alerts } = useAlertsQuery();

      return (
        <div>
          <div data-testid="health-loaded">{health ? 'yes' : 'no'}</div>
          <div data-testid="metrics-loaded">{metrics ? 'yes' : 'no'}</div>
          <div data-testid="alerts-loaded">{alerts ? 'yes' : 'no'}</div>
          <div data-testid="total-requests">
            {healthRequestCount + metricsRequestCount + alertsRequestCount}
          </div>
        </div>
      );
    }

    const startTime = performance.now();

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Wait for all queries to complete
    await waitFor(() => {
      expect(screen.getByTestId('health-loaded')).toHaveTextContent('yes');
      expect(screen.getByTestId('metrics-loaded')).toHaveTextContent('yes');
      expect(screen.getByTestId('alerts-loaded')).toHaveTextContent('yes');
    });

    const loadTime = performance.now() - startTime;

    // Should complete quickly
    expect(loadTime).toBeLessThan(1000); // Less than 1 second

    // Should make exactly one request per query
    expect(screen.getByTestId('total-requests')).toHaveTextContent('3');
  });

  test('handles query deduplication', async () => {
    let requestCount = 0;

    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        requestCount++;
        return res(ctx.json(mockSystemHealth));
      })
    );

    function TestComponent() {
      const { data: data1 } = useSystemHealthQuery();
      const { data: data2 } = useSystemHealthQuery();
      const { data: data3 } = useSystemHealthQuery();

      return (
        <div>
          <div data-testid="data1">{data1?.overall_score}</div>
          <div data-testid="data2">{data2?.overall_score}</div>
          <div data-testid="data3">{data3?.overall_score}</div>
          <div data-testid="request-count">{requestCount}</div>
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // All three hooks should get the same data
    await waitFor(() => {
      expect(screen.getByTestId('data1')).toHaveTextContent('85');
      expect(screen.getByTestId('data2')).toHaveTextContent('85');
      expect(screen.getByTestId('data3')).toHaveTextContent('85');
    });

    // Should only make one request due to deduplication
    expect(screen.getByTestId('request-count')).toHaveTextContent('1');
  });

  test('handles background refetching under load', async () => {
    let requestCount = 0;

    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        requestCount++;
        // Simulate variable response times
        const delay = Math.random() * 100; // 0-100ms
        return res(
          ctx.delay(delay),
          ctx.json({
            ...mockSystemHealth,
            overall_score: 85 + requestCount
          })
        );
      })
    );

    function TestComponent() {
      const { data, isFetching } = useSystemHealthQuery({
        refetchInterval: 100, // Very frequent refetch for testing
        staleTime: 0
      });

      return (
        <div>
          <div data-testid="health-score">{data?.overall_score}</div>
          <div data-testid="request-count">{requestCount}</div>
          <div data-testid="is-fetching">{isFetching ? 'yes' : 'no'}</div>
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Initial load
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toHaveTextContent('86');
    });

    // Let it run for a bit to test background refetching
    await new Promise(resolve => setTimeout(resolve, 500));

    // Should have made multiple requests
    const finalRequestCount = parseInt(screen.getByTestId('request-count').textContent);
    expect(finalRequestCount).toBeGreaterThan(3);

    // Should handle concurrent requests gracefully
    expect(screen.getByTestId('health-score')).toBeInTheDocument();
  });
});

describe('React Query - Error Recovery and Retry Logic', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = createTestQueryClient();
  });

  test('implements exponential backoff retry', async () => {
    let attemptCount = 0;

    server.use(
      rest.get('/api/monitoring/health', (req, res, ctx) => {
        attemptCount++;
        if (attemptCount < 3) {
          return res(ctx.status(500), ctx.json({ error: 'Server error' }));
        }
        return res(ctx.json(mockSystemHealth));
      })
    );

    function TestComponent() {
      const { data, isLoading, error, failureCount } = useSystemHealthQuery({
        retry: 3,
        retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000)
      });

      return (
        <div>
          {isLoading && <div data-testid="loading">Loading...</div>}
          {error && <div data-testid="error">Error: {error.message}</div>}
          {data && <div data-testid="health-score">{data.overall_score}</div>}
          <div data-testid="attempt-count">{attemptCount}</div>
          <div data-testid="failure-count">{failureCount || 0}</div>
        </div>
      );
    });

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Should retry and eventually succeed
    await waitFor(() => {
      expect(screen.getByTestId('health-score')).toHaveTextContent('85');
    }, { timeout: 5000 });

    // Should have made 3 attempts
    expect(screen.getByTestId('attempt-count')).toHaveTextContent('3');
  });

  test('handles offline mode gracefully', async () => {
    // Simulate offline state
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: false
    });

    function TestComponent() {
      const { data, isLoading, error, isPaused } = useSystemHealthQuery({
        retry: false,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false
      });

      return (
        <div>
          {isLoading && <div data-testid="loading">Loading...</div>}
          {isPaused && <div data-testid="paused">Paused (offline)</div>}
          {error && <div data-testid="error">Error: {error.message}</div>}
          {data && <div data-testid="health-score">{data.overall_score}</div>}
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Should be paused when offline
    expect(screen.getByTestId('paused')).toBeInTheDocument();

    // Go back online
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: true
    });

    act(() => {
      window.dispatchEvent(new Event('online'));
    });

    // Should attempt to refetch when coming back online
    // (This depends on the specific implementation)
  });
});

describe('React Query - Cache Persistence', () => {
  test('persists and restores cache across page reloads', async () => {
    // This would test integration with React Query's persistence
    // For now, we'll simulate the behavior

    const persistedState = {
      queries: [
        {
          queryKey: ['systemHealth'],
          state: {
            data: mockSystemHealth,
            status: 'success',
            lastUpdated: Date.now()
          }
        }
      ]
    };

    // In a real implementation, this would use React Query persistor
    localStorage.setItem('react-query-cache', JSON.stringify(persistedState));

    const queryClient = createTestQueryClient();

    function TestComponent() {
      const { data, isLoading } = useSystemHealthQuery({
        staleTime: Infinity, // Always use cached data
        gcTime: Infinity
      });

      return (
        <div>
          {isLoading && <div data-testid="loading">Loading...</div>}
          {data && <div data-testid="health-score">{data.overall_score}</div>}
        </div>
      );
    }

    render(
      <TestWrapper client={queryClient}>
        <TestComponent />
      </TestWrapper>
    );

    // Should load from persisted cache immediately
    expect(screen.getByTestId('health-score')).toHaveTextContent('85');
    expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
  });
});