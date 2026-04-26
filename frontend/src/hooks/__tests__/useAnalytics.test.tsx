import { renderHook } from '@testing-library/react';
import { useAnalyticsStore, useTimeRange, useAnalyticsFilters } from '@/store/analyticsStore';
import analyticsService from '@/services/analyticsService';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useRAGTriadMetrics, usePerformanceAnalytics, useAnalyticsActions } from '../useAnalytics';

jest.mock('@tanstack/react-query', () => ({
  useQuery: jest.fn(),
  useMutation: jest.fn(),
  useQueryClient: jest.fn(),
}));

jest.mock('@/services/analyticsService', () => ({
  __esModule: true,
  default: {
    getRAGTriadMetrics: jest.fn(),
    getPerformanceAnalytics: jest.fn(),
  },
}));

jest.mock('@/store/analyticsStore', () => ({
  useAnalyticsStore: jest.fn(),
  useTimeRange: jest.fn(),
  useAnalyticsFilters: jest.fn(),
}));

const mockUseQuery = useQuery as jest.Mock;
const mockUseQueryClient = useQueryClient as jest.Mock;
const mockUseAnalyticsStore = useAnalyticsStore as unknown as jest.Mock;
const mockUseTimeRange = useTimeRange as unknown as jest.Mock;
const mockUseAnalyticsFilters = useAnalyticsFilters as unknown as jest.Mock;
const mockAnalyticsService = analyticsService as jest.Mocked<typeof analyticsService>;

const storeActions = {
  setTimeRange: jest.fn(),
  setFilters: jest.fn(),
  setRealTimeMetrics: jest.fn(),
  setRealTimeConnection: jest.fn(),
};

describe('useAnalytics', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    mockUseQuery.mockReturnValue({
      data: undefined,
      isSuccess: false,
      isError: false,
      fetchStatus: 'idle',
    });

    mockUseQueryClient.mockReturnValue({
      invalidateQueries: jest.fn(),
    });

    mockUseTimeRange.mockReturnValue({
      start: '2024-01-01T00:00:00Z',
      end: '2024-01-31T23:59:59Z',
    });

    mockUseAnalyticsFilters.mockReturnValue({
      modalities: [],
      queryTypes: [],
      userSegments: [],
      performanceThresholds: {
        answer_relevancy: 70,
        faithfulness: 90,
        contextual_relevancy: 70,
      },
    });

    mockUseAnalyticsStore.mockReturnValue(storeActions);
  });

  it('configures RAG triad query with valid time range', async () => {
    useRAGTriadMetrics();

    const options = mockUseQuery.mock.calls[0][0];
    expect(options.queryKey).toEqual([
      'rag-triad-metrics',
      { start: '2024-01-01T00:00:00Z', end: '2024-01-31T23:59:59Z' },
    ]);
    expect(options.enabled).toBe(true);

    mockAnalyticsService.getRAGTriadMetrics.mockResolvedValue({ metrics: {} } as any);
    await options.queryFn();
    expect(mockAnalyticsService.getRAGTriadMetrics).toHaveBeenCalledWith({
      start: '2024-01-01T00:00:00Z',
      end: '2024-01-31T23:59:59Z',
    });
  });

  it('disables RAG triad query with invalid time range', () => {
    mockUseTimeRange.mockReturnValue({ start: '', end: '' });

    useRAGTriadMetrics();

    const options = mockUseQuery.mock.calls[0][0];
    expect(options.enabled).toBe(false);
  });

  it('configures performance analytics select transformation', () => {
    usePerformanceAnalytics();

    const options = mockUseQuery.mock.calls[0][0];
    expect(options.queryKey[0]).toBe('performance-analytics');
    expect(options.enabled).toBe(true);

    const transformed = options.select({
      answer_relevancy_history: [80, 82, 85, 87],
      faithfulness_history: [88, 90, 91, 92],
      contextual_relevancy_history: [75, 77, 78, 79],
      timestamps: ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04'],
      modalities: ['text', 'image'],
      modality_counts: [10, 5],
    });

    expect(transformed).toHaveProperty('chartData');
    expect(transformed).toHaveProperty('trendData');
    expect(transformed.chartData.lineChartData.datasets).toHaveLength(3);
  });

  it('updates time range and invalidates related queries', () => {
    const invalidateQueries = jest.fn();
    mockUseQueryClient.mockReturnValue({ invalidateQueries });

    const { result } = renderHook(() => useAnalyticsActions());

    const range = {
      start: '2024-02-01T00:00:00Z',
      end: '2024-02-29T23:59:59Z',
    };

    result.current.updateTimeRange(range as any);

    expect(storeActions.setTimeRange).toHaveBeenCalledWith(range);
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['rag-triad-metrics'] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['performance-analytics'] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['usage-analytics'] });
  });

  it('updates filters and invalidates performance query', () => {
    const invalidateQueries = jest.fn();
    mockUseQueryClient.mockReturnValue({ invalidateQueries });

    const { result } = renderHook(() => useAnalyticsActions());

    const filters = { modalities: ['text'] };
    result.current.updateFilters(filters as any);

    expect(storeActions.setFilters).toHaveBeenCalledWith(filters);
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['performance-analytics'] });
  });
});
