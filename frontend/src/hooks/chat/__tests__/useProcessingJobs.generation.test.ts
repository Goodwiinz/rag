/**
 * Generation-gating tests for useProcessingJobs (audit F5)
 *
 * A manual refresh() load and the scheduled tick can be in flight at once;
 * whichever response lands LAST used to win, so a slower stale response
 * could overwrite fresher jobs. And during an API outage with an active
 * queue, the catch branch never backed pollFast off — polling stayed at
 * 4s forever instead of returning to the idle cadence.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';

const listProcessingJobsMock = vi.hoisted(() => vi.fn());
vi.mock('@/services/entityService', () => ({
  entityService: { listProcessingJobs: listProcessingJobsMock },
}));

import { useProcessingJobs } from '@/hooks/chat/useProcessingJobs';
import type { ProcessingJobStatus } from '@/services/entityService';

function job(id: string, status: string): ProcessingJobStatus {
  return {
    id,
    job_type: 'ingest',
    status,
    progress_percentage: status === 'completed' ? 100 : 50,
    created_at: new Date().toISOString(),
  };
}

function defer<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

interface JobsPage {
  jobs: ProcessingJobStatus[];
  total?: number;
}

describe('useProcessingJobs load generation', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    listProcessingJobsMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('a stale overlapping response never overwrites fresher jobs', async () => {
    const first = defer<JobsPage>();
    const second = defer<JobsPage>();
    listProcessingJobsMock
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);

    const { result } = renderHook(() => useProcessingJobs());
    expect(listProcessingJobsMock).toHaveBeenCalledTimes(1);

    // Manual refresh while the scheduled load is still in flight.
    act(() => {
      result.current.refresh();
    });
    expect(listProcessingJobsMock).toHaveBeenCalledTimes(2);

    // The NEWER load resolves first...
    await act(async () => {
      second.resolve({ jobs: [job('fresh', 'completed')], total: 1 });
    });
    expect(result.current.jobs.map((j) => j.id)).toEqual(['fresh']);

    // ...then the OLDER one lands. It must not win.
    await act(async () => {
      first.resolve({ jobs: [job('stale', 'running')], total: 1 });
    });
    expect(result.current.jobs.map((j) => j.id)).toEqual(['fresh']);
  });

  it('backs off to the idle cadence after a failed fast poll', async () => {
    const ok = defer<JobsPage>();
    const down = defer<JobsPage>();
    listProcessingJobsMock
      .mockReturnValueOnce(ok.promise)
      .mockReturnValueOnce(down.promise);

    renderHook(() => useProcessingJobs());

    // First poll succeeds with an active queue → next tick at 4s.
    await act(async () => {
      ok.resolve({ jobs: [job('j1', 'running')], total: 1 });
    });
    await vi.advanceTimersByTimeAsync(4_000);
    expect(listProcessingJobsMock).toHaveBeenCalledTimes(2);

    // Second poll fails mid-outage → next tick must be at 30s, not 4s.
    await act(async () => {
      down.reject(new Error('network down'));
    });
    await vi.advanceTimersByTimeAsync(29_999);
    expect(listProcessingJobsMock).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(listProcessingJobsMock).toHaveBeenCalledTimes(3);
  });
});
