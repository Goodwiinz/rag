/**
 * Unit tests for EvaluationDashboard component
 */

import React from 'react';
import { fireEvent, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import EvaluationDashboard from '../EvaluationDashboard';
import { render, createMockEvaluationMetric, mockFetchResponse, createMockApiResponse } from '../../__tests__/testUtils';

// Mock the API calls
const mockGetEvaluationMetrics = jest.fn();
const mockGetEvaluationTrends = jest.fn();
const mockGetTestSuites = jest.fn();
const mockRunEvaluation = jest.fn();
const mockExportResults = jest.fn();

jest.mock('../../services/apiService', () => ({
  getEvaluationMetrics: mockGetEvaluationMetrics,
  getEvaluationTrends: mockGetEvaluationTrends,
  getTestSuites: mockGetTestSuites,
  runEvaluation: mockRunEvaluation,
  exportResults: mockExportResults
}));

// Mock recharts
jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div data-testid="line-chart">{children}</div>,
  Line: () => <div data-testid="line" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />,
  BarChart: ({ children }: { children: React.ReactNode }) => <div data-testid="bar-chart">{children}</div>,
  Bar: () => <div data-testid="bar" />,
  PieChart: ({ children }: { children: React.ReactNode }) => <div data-testid="pie-chart">{children}</div>,
  Pie: () => <div data-testid="pie" />,
  Cell: () => <div data-testid="cell" />
}));

// Mock react-hot-toast
jest.mock('react-hot-toast', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
    loading: jest.fn(),
    dismiss: jest.fn()
  },
  Toaster: () => null
}));

describe('EvaluationDashboard', () => {
  const defaultProps = {
    title: 'RAG Evaluation Dashboard',
    showTrends: true,
    showTestSuites: true,
    autoRefresh: false,
    refreshInterval: 30000
  };

  const mockMetrics = [
    createMockEvaluationMetric({ name: 'answer_relevancy', value: 0.85 }),
    createMockEvaluationMetric({ name: 'faithfulness', value: 0.92 }),
    createMockEvaluationMetric({ name: 'contextual_relevancy', value: 0.78 })
  ];

  const mockTrends = {
    answer_relevancy: [
      { timestamp: '2025-01-15T00:00:00Z', value: 0.82 },
      { timestamp: '2025-01-16T00:00:00Z', value: 0.84 },
      { timestamp: '2025-01-17T00:00:00Z', value: 0.85 }
    ],
    faithfulness: [
      { timestamp: '2025-01-15T00:00:00Z', value: 0.90 },
      { timestamp: '2025-01-16T00:00:00Z', value: 0.91 },
      { timestamp: '2025-01-17T00:00:00Z', value: 0.92 }
    ]
  };

  const mockTestSuites = [
    {
      id: 'suite-1',
      name: 'Core RAG Tests',
      description: 'Basic RAG functionality tests',
      lastRun: '2025-01-18T10:30:00Z',
      status: 'passed',
      score: 0.88,
      tests: [
        { id: 'test-1', name: 'Answer Relevancy Test', status: 'passed', score: 0.85 },
        { id: 'test-2', name: 'Faithfulness Test', status: 'passed', score: 0.92 }
      ]
    }
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    // Setup default successful API responses
    mockGetEvaluationMetrics.mockResolvedValue(createMockApiResponse(mockMetrics));
    mockGetEvaluationTrends.mockResolvedValue(createMockApiResponse(mockTrends));
    mockGetTestSuites.mockResolvedValue(createMockApiResponse(mockTestSuites));
    mockRunEvaluation.mockResolvedValue(createMockApiResponse({ status: 'completed', results: [] }));
    mockExportResults.mockResolvedValue(createMockApiResponse({ downloadUrl: '/downloads/results.csv' }));
  });

  it('renders without crashing', () => {
    render(<EvaluationDashboard {...defaultProps} />);

    expect(screen.getByText('RAG Evaluation Dashboard')).toBeInTheDocument();
    expect(screen.getByText(/answer relevancy/i)).toBeInTheDocument();
    expect(screen.getByText(/faithfulness/i)).toBeInTheDocument();
    expect(screen.getByText(/contextual relevancy/i)).toBeInTheDocument();
  });

  it('displays metric cards with correct values', () => {
    render(<EvaluationDashboard {...defaultProps} />);

    expect(screen.getByText('85%')).toBeInTheDocument(); // answer_relevancy
    expect(screen.getByText('92%')).toBeInTheDocument(); // faithfulness
    expect(screen.getByText('78%')).toBeInTheDocument(); // contextual_relevancy
  });

  it('shows metric status indicators', () => {
    render(<EvaluationDashboard {...defaultProps} />);

    // Good metrics should have green indicators
    expect(screen.getByTestId('metric-answer_relevancy')).toHaveClass('text-green-600');
    expect(screen.getByTestId('metric-faithfulness')).toHaveClass('text-green-600');

    // Warning metrics should have yellow indicators
    expect(screen.getByTestId('metric-contextual_relevancy')).toHaveClass('text-yellow-600');
  });

  it('displays trend charts', () => {
    render(<EvaluationDashboard {...defaultProps} showTrends={true} />);

    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
    expect(screen.getByText(/trends/i)).toBeInTheDocument();
  });

  it('shows test suites section', () => {
    render(<EvaluationDashboard {...defaultProps} showTestSuites={true} />);

    expect(screen.getByText('Core RAG Tests')).toBeInTheDocument();
    expect(screen.getByText('88%')).toBeInTheDocument();
    expect(screen.getByText('passed')).toBeInTheDocument();
  });

  it('runs evaluation suite', async () => {
    const user = userEvent.setup();
    render(<EvaluationDashboard {...defaultProps} />);

    const runButton = screen.getByRole('button', { name: /run evaluation/i });

    await act(async () => {
      await user.click(runButton);
    });

    await waitFor(() => {
      expect(mockRunEvaluation).toHaveBeenCalled();
    });
  });

  it('shows loading state during evaluation', async () => {
    mockRunEvaluation.mockImplementation(() => new Promise(resolve =>
      setTimeout(() => resolve(createMockApiResponse({ status: 'completed', results: [] })), 2000)
    ));

    const user = userEvent.setup();
    render(<EvaluationDashboard {...defaultProps} />);

    const runButton = screen.getByRole('button', { name: /run evaluation/i });

    await act(async () => {
      await user.click(runButton);
    });

    expect(screen.getByText(/running evaluation/i)).toBeInTheDocument();
    expect(runButton).toBeDisabled();
  });

  it('shows evaluation results', async () => {
    mockRunEvaluation.mockResolvedValue(createMockApiResponse({
      status: 'completed',
      results: {
        overallScore: 0.87,
        metrics: [
          { name: 'answer_relevancy', score: 0.85, improvement: 0.03 },
          { name: 'faithfulness', score: 0.92, improvement: 0.02 }
        ],
        recommendations: [
          'Improve contextual relevancy by enhancing entity extraction',
          'Consider adding more diverse test cases'
        ]
      }
    }));

    const user = userEvent.setup();
    render(<EvaluationDashboard {...defaultProps} />);

    const runButton = screen.getByRole('button', { name: /run evaluation/i });

    await act(async () => {
      await user.click(runButton);
    });

    await waitFor(() => {
      expect(screen.getByText('87%')).toBeInTheDocument(); // overall score
      expect(screen.getByText(/improve contextual relevancy/i)).toBeInTheDocument();
    });
  });

  it('exports evaluation results', async () => {
    const user = userEvent.setup();
    render(<EvaluationDashboard {...defaultProps} />);

    const exportButton = screen.getByRole('button', { name: /export results/i });

    await act(async () => {
      await user.click(exportButton);
    });

    await waitFor(() => {
      expect(mockExportResults).toHaveBeenCalled();
    });
  });

  it('handles evaluation failure', async () => {
    mockRunEvaluation.mockRejectedValue(new Error('Evaluation failed'));

    const user = userEvent.setup();
    render(<EvaluationDashboard {...defaultProps} />);

    const runButton = screen.getByRole('button', { name: /run evaluation/i });

    await act(async () => {
      await user.click(runButton);
    });

    await waitFor(() => {
      expect(screen.getByText(/evaluation failed/i)).toBeInTheDocument();
    });
  });

  it('switches between different metric views', async () => {
    const user = userEvent.setup();
    render(<EvaluationDashboard {...defaultProps} />);

    // Click on detailed view
    await act(async () => {
      await user.click(screen.getByRole('button', { name: /detailed view/i }));
    });

    expect(screen.getByText(/detailed metrics/i)).toBeInTheDocument();

    // Click on summary view
    await act(async () => {
      await user.click(screen.getByRole('button', { name: /summary view/i }));
    });

    expect(screen.getByText(/summary/i)).toBeInTheDocument();
  });

  it('filters metrics by category', async () => {
    const user = userEvent.setup();
    render(<EvaluationDashboard {...defaultProps} />);

    const categoryFilter = screen.getByLabelText(/category filter/i);

    await act(async () => {
      await user.selectOptions(categoryFilter, 'quality');
    });

    // Should show only quality metrics
    expect(screen.getByText('Answer Relevancy')).toBeInTheDocument();
  });

  it('shows metric history', async () => {
    render(<EvaluationDashboard {...defaultProps} />);

    const metricCard = screen.getByTestId('metric-answer_relevancy');

    await act(async () => {
      fireEvent.click(metricCard);
    });

    await waitFor(() => {
      expect(screen.getByText(/metric history/i)).toBeInTheDocument();
      expect(screen.getByText(/last 30 days/i)).toBeInTheDocument();
    });
  });

  it('updates metrics in real-time', async () => {
    const { rerender } = render(<EvaluationDashboard {...defaultProps} autoRefresh={true} />);

    // Mock updated metrics
    const updatedMetrics = [
      createMockEvaluationMetric({ name: 'answer_relevancy', value: 0.87 }),
      createMockEvaluationMetric({ name: 'faithfulness', value: 0.93 })
    ];

    mockGetEvaluationMetrics.mockResolvedValue(createMockApiResponse(updatedMetrics));

    // Trigger refresh
    act(() => {
      rerender(<EvaluationDashboard {...defaultProps} autoRefresh={true} />);
    });

    await waitFor(() => {
      expect(screen.getByText('87%')).toBeInTheDocument(); // updated answer_relevancy
      expect(screen.getByText('93%')).toBeInTheDocument(); // updated faithfulness
    });
  });

  it('displays benchmark comparisons', async () => {
    const user = userEvent.setup();
    render(<EvaluationDashboard {...defaultProps} />);

    await act(async () => {
      await user.click(screen.getByRole('button', { name: /benchmarks/i }));
    });

    await waitFor(() => {
      expect(screen.getByText(/benchmark comparison/i)).toBeInTheDocument();
      expect(screen.getByText(/industry average/i)).toBeInTheDocument();
    });
  });

  it('allows custom date range selection', async () => {
    const user = userEvent.setup();
    render(<EvaluationDashboard {...defaultProps} />);

    const dateRangeButton = screen.getByRole('button', { name: /date range/i });

    await act(async () => {
      await user.click(dateRangeButton);
    });

    await waitFor(() => {
      expect(screen.getByLabelText(/start date/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/end date/i)).toBeInTheDocument();
    });
  });

  it('shows test suite details', async () => {
    const user = userEvent.setup();
    render(<EvaluationDashboard {...defaultProps} showTestSuites={true} />);

    const testSuite = screen.getByText('Core RAG Tests');

    await act(async () => {
      await user.click(testSuite);
    });

    await waitFor(() => {
      expect(screen.getByText('Answer Relevancy Test')).toBeInTheDocument();
      expect(screen.getByText('Faithfulness Test')).toBeInTheDocument();
    });
  });

  it('handles empty metric state', async () => {
    mockGetEvaluationMetrics.mockResolvedValue(createMockApiResponse([]));

    render(<EvaluationDashboard {...defaultProps} />);

    expect(screen.getByText(/no metrics available/i)).toBeInTheDocument();
  });

  it('displays performance alerts', async () => {
    // Mock metrics with poor performance
    const poorMetrics = [
      createMockEvaluationMetric({ name: 'answer_relevancy', value: 0.45, status: 'critical' })
    ];

    mockGetEvaluationMetrics.mockResolvedValue(createMockApiResponse(poorMetrics));

    render(<EvaluationDashboard {...defaultProps} />);

    expect(screen.getByText(/performance alert/i)).toBeInTheDocument();
    expect(screen.getByText(/critical metrics detected/i)).toBeInTheDocument();
  });

  it('provides improvement recommendations', async () => {
    mockGetEvaluationMetrics.mockResolvedValue(createMockApiResponse([
      createMockEvaluationMetric({ name: 'answer_relevancy', value: 0.65, recommendations: [
        'Improve query understanding',
        'Enhance context retrieval',
        'Optimize ranking algorithm'
      ]})
    ]));

    const user = userEvent.setup();
    render(<EvaluationDashboard {...defaultProps} />);

    const metricCard = screen.getByTestId('metric-answer_relevancy');

    await act(async () => {
      await user.click(metricCard);
    });

    await waitFor(() => {
      expect(screen.getByText('Improve query understanding')).toBeInTheDocument();
      expect(screen.getByText('Enhance context retrieval')).toBeInTheDocument();
    });
  });

  it('supports metric thresholds configuration', async () => {
    const customThresholds = {
      answer_relevancy: { warning: 0.7, critical: 0.5 },
      faithfulness: { warning: 0.85, critical: 0.7 }
    };

    render(<EvaluationDashboard {...defaultProps} thresholds={customThresholds} />);

    // Should use custom thresholds for status determination
    expect(screen.getByTestId('metric-answer_relevancy')).toHaveClass('text-yellow-600'); // warning
    expect(screen.getByTestId('metric-faithfulness')).toHaveClass('text-green-600'); // good
  });

  it('handles responsive layout', async () => {
    // Mock mobile viewport
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: 375
    });

    Object.defineProperty(window, 'innerHeight', {
      writable: true,
      configurable: true,
      value: 667
    });

    render(<EvaluationDashboard {...defaultProps} />);

    // Should adapt layout for mobile
    expect(screen.getByTestId('metric-cards')).toHaveClass('grid-cols-1');
  });
});