import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

const listProcessingJobs = vi.fn();
vi.mock('@/services/entityService', () => ({
  entityService: {
    listProcessingJobs: (...args: unknown[]) => listProcessingJobs(...args),
  },
}));

import { JobsIndicator } from '../JobsIndicator';

function job(overrides: Record<string, unknown> = {}) {
  return {
    id: 'job-1',
    job_type: 'arxiv_ingest',
    status: 'running',
    progress_percentage: 40,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe('JobsIndicator', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders nothing when no job has ever run', async () => {
    listProcessingJobs.mockResolvedValue({ jobs: [] });
    const { container } = render(<JobsIndicator />);

    // A control that opens an empty panel is worse than no control.
    await waitFor(() => expect(listProcessingJobs).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('counts only jobs that are still working', async () => {
    listProcessingJobs.mockResolvedValue({
      jobs: [
        job({ id: 'a', status: 'running' }),
        job({ id: 'b', status: 'queued' }),
        job({ id: 'c', status: 'completed' }),
        job({ id: 'd', status: 'failed' }),
      ],
    });
    render(<JobsIndicator />);

    expect(
      await screen.findByRole('button', { name: /2 running/i })
    ).toBeInTheDocument();
  });

  it('keeps the last known jobs when a poll fails', async () => {
    listProcessingJobs
      .mockResolvedValueOnce({ jobs: [job()] })
      .mockRejectedValue(new Error('network down'));

    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<JobsIndicator />);

    const trigger = await screen.findByRole('button', { name: /1 running/i });

    // Second poll rejects; the panel must not blank out — a failed poll is not
    // a finished job.
    await vi.advanceTimersByTimeAsync(5000);
    await waitFor(() => expect(listProcessingJobs).toHaveBeenCalledTimes(2));
    expect(trigger).toBeInTheDocument();
  });

  it('polls faster while work is in flight than when idle', async () => {
    listProcessingJobs.mockResolvedValue({
      jobs: [job({ status: 'completed' })],
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<JobsIndicator />);

    await waitFor(() => expect(listProcessingJobs).toHaveBeenCalledTimes(1));
    // Idle: the 4s active interval must not fire.
    await vi.advanceTimersByTimeAsync(5000);
    expect(listProcessingJobs).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(26000);
    await waitFor(() => expect(listProcessingJobs).toHaveBeenCalledTimes(2));
  });
});
