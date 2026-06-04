import { beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { RetrievalDiagnosticsDashboard } from '@/components/diagnostics/RetrievalDiagnosticsDashboard';

const mockGetRecentTraces = vi.fn();
const mockGetTrace = vi.fn();
const mockGetAggregateStats = vi.fn();
const mockExperimentWeights = vi.fn();

vi.mock('@/services/diagnosticsService', () => ({
  diagnosticsService: {
    getRecentTraces: (...args: unknown[]) => mockGetRecentTraces(...args),
    getTrace: (...args: unknown[]) => mockGetTrace(...args),
    getAggregateStats: (...args: unknown[]) => mockGetAggregateStats(...args),
    experimentWeights: (...args: unknown[]) => mockExperimentWeights(...args),
  },
}));

describe('RetrievalDiagnosticsDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetRecentTraces.mockResolvedValue({ traces: [], count: 0 });
    mockGetTrace.mockResolvedValue({
      trace: {
        trace_id: 'trace-1',
        query: 'sample query',
        timestamp: '2026-02-19T00:00:00Z',
        total_time_ms: 95,
        sources: [],
        fusion: null,
        rerank: null,
        context: null,
        final_result_count: 0,
        search_type: 'hybrid',
        evaluation_id: null,
        evaluation_scores: null,
      },
      bottleneck_report: {
        trace_id: 'trace-1',
        findings: [],
        stage_health: {},
        overall_health: 'green',
      },
    });
    mockGetAggregateStats.mockResolvedValue({
      period_hours: 24,
      total_traces: 0,
      avg_time_ms: 0,
      avg_result_count: 0,
      source_stats: {},
      source_failure_count: 0,
      truncation_stats: {
        avg_ratio: 0,
        max_ratio: 0,
        traces_with_truncation: 0,
      },
    });
    mockExperimentWeights.mockResolvedValue({ query: 'test', results: [] });
  });

  const activateTab = (name: string) => {
    const tab = screen.getByRole('tab', { name });
    fireEvent.mouseDown(tab);
    fireEvent.click(tab);
    return tab;
  };

  it('loads recent traces and shows empty diagnostics message', async () => {
    render(<RetrievalDiagnosticsDashboard />);

    await waitFor(() => {
      expect(mockGetRecentTraces).toHaveBeenCalledWith(50);
    });

    expect(screen.getByText('No traces captured yet')).toBeInTheDocument();
  });

  it('refreshes traces when refresh button is clicked', async () => {
    render(<RetrievalDiagnosticsDashboard />);

    await waitFor(() => {
      expect(mockGetRecentTraces).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }));

    await waitFor(() => {
      expect(mockGetRecentTraces).toHaveBeenCalledTimes(2);
    });
  });

  it('loads aggregate stats in quality overview tab', async () => {
    render(<RetrievalDiagnosticsDashboard />);

    const qualityTab = activateTab('Quality overview');

    await waitFor(() => {
      expect(qualityTab).toHaveAttribute('aria-selected', 'true');
      expect(mockGetAggregateStats).toHaveBeenCalledWith(24);
    });

    expect(screen.getByText('Total queries')).toBeInTheDocument();
    expect(screen.getByText('Context truncation')).toBeInTheDocument();
  });

  it('loads bottleneck analysis data in bottleneck tab', async () => {
    mockGetRecentTraces.mockImplementation((limit: number) => {
      if (limit === 10) {
        return Promise.resolve({
          traces: [
            {
              trace_id: 'trace-1',
              query: 'sample query',
              timestamp: '2026-02-19T00:00:00Z',
              total_time_ms: 95,
              final_result_count: 2,
              search_type: 'hybrid',
              source_count: 2,
              has_evaluation: false,
            },
          ],
          count: 1,
        });
      }
      return Promise.resolve({ traces: [], count: 0 });
    });

    render(<RetrievalDiagnosticsDashboard />);

    const bottleneckTab = activateTab('Bottleneck analysis');

    await waitFor(() => {
      expect(bottleneckTab).toHaveAttribute('aria-selected', 'true');
      expect(mockGetRecentTraces).toHaveBeenCalledWith(10);
      expect(mockGetTrace).toHaveBeenCalledWith('trace-1');
    });

    expect(screen.getByText('Pipeline health')).toBeInTheDocument();
    expect(screen.getByText('Top issues (0)')).toBeInTheDocument();
  });
});
