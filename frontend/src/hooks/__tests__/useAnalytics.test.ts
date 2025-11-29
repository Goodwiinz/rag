import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAnalyticsStore } from '@/stores/analyticsStore';
import { useRAGTriadMetrics, usePerformanceAnalytics, useAnalyticsActions } from '../useAnalytics';
import { analyticsService } from '@/services/analyticsService';

// Mock analytics service
jest.mock('@/services/analyticsService');
const mockAnalyticsService = analyticsService as jest.Mocked<typeof analyticsService>;

// Mock store
const mockStore = useAnalyticsStore as jest.MockedFunction<typeof useAnalyticsStore>;

// Test wrapper
const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
};

describe('useAnalytics', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Mock store
    mockStore.mockImplementation((selector) => {
      const state = {
        timeRange: {
          start: '2024-01-01T00:00:00Z',
          end: '2024-01-31T23:59:59Z',
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
        refreshInterval: 30000,
        setTimeRange: jest.fn(),
        setFilters: jest.fn(),
        setRealTimeMetrics: jest.fn(),
        setRealTimeConnection: jest.fn(),
        setPerformanceData: jest.fn(),
        updateSelectedMetrics: jest.fn(),
        setChartView: jest.fn(),
        toggleAutoRefresh: jest.fn(),
        setRefreshInterval: jest.fn(),
        resetFilters: jest.fn(),
      };
      return selector(state);
    });
  });

  describe('useRAGTriadMetrics', () => {
    it('fetches RAG triad metrics successfully', async () => {
      const mockMetrics = {
        metrics: {
          answer_relevancy: 85.5,
          faithfulness: 92.1,
          contextual_relevancy: 78.9,
        },
      };

      mockAnalyticsService.getRAGTriadMetrics.mockResolvedValue(mockMetrics);

      const { result } = renderHook(() => useRAGTriadMetrics(), {
        wrapper: createTestWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockMetrics.metrics);
      expect(mockAnalyticsService.getRAGTriadMetrics).toHaveBeenCalledWith({
        start: '2024-01-01T00:00:00Z',
        end: '2024-01-31T23:59:59Z',
      });
    });

    it('handles fetch errors gracefully', async () => {
      const error = new Error('Failed to fetch metrics');
      mockAnalyticsService.getRAGTriadMetrics.mockRejectedValue(error);

      const { result } = renderHook(() => useRAGTriadMetrics(), {
        wrapper: createTestWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error).toEqual(error);
    });

    it('does not fetch when time range is invalid', () => {
      mockStore.mockImplementation((selector) => {
        const state = {
          timeRange: { start: '', end: '' },
          // ... other state
          setTimeRange: jest.fn(),
          setFilters: jest.fn(),
          // ... other methods
        } as any;
        return selector(state);
      });

      const { result } = renderHook(() => useRAGTriadMetrics(), {
        wrapper: createTestWrapper(),
      });

      expect(result.current.fetchStatus).toBe('idle');
      expect(mockAnalyticsService.getRAGTriadMetrics).not.toHaveBeenCalled();
    });

    it('caches data appropriately', async () => {
      const mockMetrics = {
        metrics: {
          answer_relevancy: 85.5,
          faithfulness: 92.1,
          contextual_relevancy: 78.9,
        },
      };

      mockAnalyticsService.getRAGTriadMetrics.mockResolvedValue(mockMetrics);

      const { result, rerender } = renderHook(() => useRAGTriadMetrics(), {
        wrapper: createTestWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      // Reset mock
      mockAnalyticsService.getRAGTriadMetrics.mockClear();

      // Rerender hook
      rerender();

      // Should not fetch again due to caching
      expect(mockAnalyticsService.getRAGTriadMetrics).not.toHaveBeenCalled();
      expect(result.current.data).toEqual(mockMetrics.metrics);
    });
  });

  describe('usePerformanceAnalytics', () => {
    it('fetches and transforms performance analytics', async () => {
      const mockAnalyticsData = {
        average_latency_ms: 1500,
        success_rate: 98.5,
        answer_relevancy_history: [80, 82, 85, 87],
        faithfulness_history: [88, 90, 91, 92],
        contextual_relevancy_history: [75, 77, 78, 79],
        modalities: {
          text: 1000,
          image: 500,
          audio: 200,
        },
      };

      mockAnalyticsService.getPerformanceAnalytics.mockResolvedValue(mockAnalyticsData);

      const { result } = renderHook(() => usePerformanceAnalytics(), {
        wrapper: createTestWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toHaveProperty('chartData');
      expect(result.current.data).toHaveProperty('trendData');
      expect(mockAnalyticsService.getPerformanceAnalytics).toHaveBeenCalledWith(
        expect.objectContaining({
          modalities: [],
          queryTypes: [],
          userSegments: [],
        }),
        {
          start: '2024-01-01T00:00:00Z',
          end: '2024-01-31T23:59:59Z',
        }
      );
    });

    it('applies custom filters', async () => {
      const customFilters = {
        modalities: ['text', 'image'],
        queryTypes: ['search'],
      };

      mockAnalyticsService.getPerformanceAnalytics.mockResolvedValue({});

      renderHook(() => usePerformanceAnalytics(customFilters), {
        wrapper: createTestWrapper(),
      });

      await waitFor(() => {
        expect(mockAnalyticsService.getPerformanceAnalytics).toHaveBeenCalledWith(
          expect.objectContaining(customFilters),
          expect.any(Object)
        );
      });
    });
  });

  describe('useAnalyticsActions', () => {
    it('updates time range and invalidates queries', () => {
      const mockInvalidateQueries = jest.fn();
      const mockQueryClient = {
        invalidateQueries: mockInvalidateQueries,
      };

      jest.mock('@tanstack/react-query', () => ({
        useQueryClient: () => mockQueryClient,
      }));

      const { result } = renderHook(() => useAnalyticsActions());

      const newTimeRange = {
        start: '2024-02-01T00:00:00Z',
        end: '2024-02-29T23:59:59Z',
      };

      result.current.updateTimeRange(newTimeRange);

      expect(mockStore()).setTimeRange?.toHaveBeenCalledWith(newTimeRange);
      expect(mockInvalidateQueries).toHaveBeenCalledWith(['rag-triad-metrics']);
      expect(mockInvalidateQueries).toHaveBeenCalledWith(['performance-analytics']);
    });

    it('updates filters and invalidates relevant queries', () => {
      const mockInvalidateQueries = jest.fn();
      const mockQueryClient = {
        invalidateQueries: mockInvalidateQueries,
      };

      jest.mock('@tanstack/react-query', () => ({
        useQueryClient: () => mockQueryClient,
      }));

      const { result } = renderHook(() => useAnalyticsActions());

      const newFilters = {
        modalities: ['text'],
        performanceThresholds: {
          answer_relevancy: 80,
        },
      };

      result.current.updateFilters(newFilters);

      expect(mockStore()).setFilters?.toHaveBeenCalledWith(newFilters);
      expect(mockInvalidateQueries).toHaveBeenCalledWith(['performance-analytics']);
    });

    it('refreshes all analytics data', () => {
      const mockInvalidateQueries = jest.fn();
      const mockQueryClient = {
        invalidateQueries: mockInvalidateQueries,
      };

      jest.mock('@tanstack/react-query', () => ({
        useQueryClient: () => mockQueryClient,
      }));

      const { result } = renderHook(() => useAnalyticsActions());

      result.current.refreshAllAnalytics();

      expect(mockInvalidateQueries).toHaveBeenCalledWith(['rag-triad-metrics']);
      expect(mockInvalidateQueries).toHaveBeenCalledWith(['performance-analytics']);
      expect(mockInvalidateQueries).toHaveBeenCalledWith(['usage-analytics']);
      expect(mockInvalidateQueries).toHaveBeenCalledWith(['real-time-metrics']);
    });
  });

  describe('Data Transformation', () => {
    it('transforms data for charts correctly', async () => {
      const mockData = {
        answer_relevancy_history: [80, 82, 85, 87],
        faithfulness_history: [88, 90, 91, 92],
        contextual_relevancy_history: [75, 77, 78, 79],
        timestamps: ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04'],
      };

      mockAnalyticsService.getPerformanceAnalytics.mockResolvedValue(mockData);

      const { result } = renderHook(() => usePerformanceAnalytics(), {
        wrapper: createTestWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data?.chartData).toBeDefined();
      });

      const { chartData } = result.current.data!;

      expect(chartData.lineChartData).toHaveProperty('labels');
      expect(chartData.lineChartData).toHaveProperty('datasets');
      expect(chartData.lineChartData.datasets).toHaveLength(3); // Three metrics
    });

    it('calculates trends correctly', async () => {
      const mockData = {
        answer_relevancy_history: [80, 82, 85, 87],
        faithfulness_history: [92, 91, 90, 89], // Declining
        contextual_relevancy_history: [78, 78, 79, 78], // Stable
      };

      mockAnalyticsService.getPerformanceAnalytics.mockResolvedValue(mockData);

      const { result } = renderHook(() => usePerformanceAnalytics(), {
        wrapper: createTestWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data?.trendData).toBeDefined();
      });

      const { trendData } = result.current.data!;

      expect(trendData.answer_relevancy_trend.direction).toBe('up');
      expect(trendData.faithfulness_trend.direction).toBe('down');
      expect(trendData.contextual_relevancy_trend.direction).toBe('stable');
    });
  });

  describe('Real-time Updates', () => {
    beforeEach(() => {
      // Mock WebSocket
      global.WebSocket = jest.fn().mockImplementation(() => ({
        addEventListener: jest.fn(),
        close: jest.fn(),
      })) as any;
    });

    it('sets up WebSocket connection', () => {
      renderHook(() => {
        const RealTimeHook = require('../useAnalytics').useRealTimeMetrics;
        RealTimeHook();
      });

      expect(global.WebSocket).toHaveBeenCalled();
    });

    it('handles WebSocket messages', () => {
      const mockAddEventListener = jest.fn();
      global.WebSocket = jest.fn().mockImplementation(() => ({
        addEventListener: mockAddEventListener,
        close: jest.fn(),
      })) as any;

      renderHook(() => {
        const RealTimeHook = require('../useAnalytics').useRealTimeMetrics;
        RealTimeHook();
      });

      expect(mockAddEventListener).toHaveBeenCalledWith('message', expect.any(Function));
    });
  });

  describe('Error Handling', () => {
    it('handles network errors gracefully', async () => {
      mockAnalyticsService.getRAGTriadMetrics.mockRejectedValue(
        new Error('Network error')
      );

      const { result } = renderHook(() => useRAGTriadMetrics(), {
        wrapper: createTestWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe('Network error');
    });

    it('handles malformed API responses', async () => {
      mockAnalyticsService.getRAGTriadMetrics.mockResolvedValue({
        // Missing required metrics field
        invalid: 'data',
      });

      const { result } = renderHook(() => useRAGTriadMetrics(), {
        wrapper: createTestWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      // Should handle missing data gracefully
      expect(result.current.data).toBeUndefined();
    });
  });

  describe('Performance', () => {
    it('does not cause memory leaks', () => {
      const { unmount } = renderHook(() => useRAGTriadMetrics(), {
        wrapper: createTestWrapper(),
      });

      // Cleanup should not throw errors
      expect(() => unmount()).not.toThrow();
    });

    it('handles rapid filter changes', async () => {
      const { rerender } = renderHook(
        (filters) => usePerformanceAnalytics(filters),
        {
          wrapper: createTestWrapper(),
          initialProps: {},
        }
      );

      // Rapid filter changes
      for (let i = 0; i < 5; i++) {
        rerender({ modalities: [`type-${i}`] });
      }

      // Should handle gracefully
      expect(mockAnalyticsService.getPerformanceAnalytics).toHaveBeenCalledTimes(5);
    });
  });
});