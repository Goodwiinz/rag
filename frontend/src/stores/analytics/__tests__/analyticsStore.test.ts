import { beforeEach, describe, expect, it, vi } from 'vitest';

const analyticsApiMock = vi.hoisted(() => ({
  generateReport: vi.fn(),
}));

vi.mock('@/services/analytics/analyticsApi', () => ({
  reportApi: analyticsApiMock,
}));

import { useAnalyticsStore, type Report } from '../analyticsStore';

const report: Report = {
  id: 'report-1',
  name: 'Weekly report',
  type: 'summary',
  format: 'pdf',
  recipients: [],
  template: 'default',
  config: {},
};

describe('analytics report actions', () => {
  beforeEach(() => {
    analyticsApiMock.generateReport.mockReset();
    useAnalyticsStore.getState().resetStore();
    useAnalyticsStore.setState({ reports: [report], error: null });
  });

  it('generates through the report API and records the generation time', async () => {
    analyticsApiMock.generateReport.mockResolvedValue({
      downloadUrl: '',
      expiresAt: '2026-08-25T00:00:00Z',
    });

    await useAnalyticsStore.getState().generateReport(report.id);

    expect(analyticsApiMock.generateReport).toHaveBeenCalledWith(
      report.id,
      report.format
    );
    expect(useAnalyticsStore.getState().reports[0].lastGenerated).toEqual(
      expect.any(String)
    );
    expect(useAnalyticsStore.getState().isGeneratingReport).toBe(false);
  });

  it('surfaces API failures and always clears the generating state', async () => {
    analyticsApiMock.generateReport.mockRejectedValue(new Error('API offline'));

    await expect(
      useAnalyticsStore.getState().generateReport(report.id)
    ).rejects.toThrow('API offline');

    expect(useAnalyticsStore.getState().error).toBe('API offline');
    expect(useAnalyticsStore.getState().isGeneratingReport).toBe(false);
  });
});
