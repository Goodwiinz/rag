import React from 'react';
import { render, screen } from '@testing-library/react';
import QualityMetricsDashboardMUI from '../QualityMetricsDashboardMUI';

jest.mock('../../../services/analyticsService', () => ({
  __esModule: true,
  default: {
    getQualityMetrics: jest.fn().mockResolvedValue({
      metrics: [
        {
          id: 'answer_relevancy',
          name: 'Answer Relevancy',
          current_value: 90,
          target_value: 95,
          threshold: 70,
          unit: '%',
          trend: 'improving',
          status: 'good',
          last_updated: new Date().toISOString(),
          description: 'Measures relevance.'
        }
      ],
      alerts: []
    })
  }
}));

describe('QualityMetricsDashboardMUI', () => {
  it('renders Quality Metrics heading', async () => {
    render(<QualityMetricsDashboardMUI />);
    const heading = await screen.findByRole('heading', { name: /Quality Metrics/i });
    expect(heading).toBeInTheDocument();
  });
});
