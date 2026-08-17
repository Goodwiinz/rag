'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  entityService,
  type ProcessingJobStatus,
} from '@/services/entityService';

/** Statuses that mean the job is still doing something. */
const ACTIVE_STATUSES = new Set(['pending', 'queued', 'running', 'processing']);

export function isJobActive(job: ProcessingJobStatus): boolean {
  return ACTIVE_STATUSES.has(job.status.toLowerCase());
}

export function isJobFailed(job: ProcessingJobStatus): boolean {
  return job.status.toLowerCase() === 'failed';
}

/** Poll while work is in flight; fall back to a slow heartbeat when idle. */
const ACTIVE_INTERVAL_MS = 4000;
const IDLE_INTERVAL_MS = 30000;

export interface UseProcessingJobsResult {
  jobs: ProcessingJobStatus[];
  activeCount: number;
  /** True only for the first load, so the panel can tell empty from unknown. */
  isInitialLoading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Background processing jobs — uploads, ingests, entity extraction — polled
 * from `/processing/jobs`.
 *
 * The interval is state-dependent rather than fixed: work in flight is worth
 * four seconds, an idle queue is not, and the page already polls enough
 * elsewhere. Nothing here pushes, so this is the only way to notice a job that
 * finished while the user was reading.
 *
 * ponytail: polling, not a socket. The WS channel is push-only for other
 * traffic and adding a job topic to it costs more than this does; revisit if
 * job volume makes 4s feel slow.
 */
export function useProcessingJobs(limit = 20): UseProcessingJobsResult {
  const [jobs, setJobs] = useState<ProcessingJobStatus[]>([]);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Read by the scheduler without making it a dependency — otherwise every
  // poll would tear down and rebuild the timer.
  const hasActiveRef = useRef(false);
  const cancelledRef = useRef(false);

  const load = useCallback(async () => {
    try {
      const response = await entityService.listProcessingJobs({ limit });
      if (cancelledRef.current) return;
      const next = response.jobs ?? [];
      setJobs(next);
      hasActiveRef.current = next.some(isJobActive);
      setError(null);
    } catch (err) {
      if (cancelledRef.current) return;
      // A failed poll is not a failed job — keep the last known list on screen
      // and say the freshness is in doubt, rather than blanking the panel.
      setError(err instanceof Error ? err.message : 'Could not reach jobs');
    } finally {
      if (!cancelledRef.current) setIsInitialLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    cancelledRef.current = false;
    let timer: ReturnType<typeof setTimeout>;

    const tick = async (): Promise<void> => {
      await load();
      if (cancelledRef.current) return;
      timer = setTimeout(
        tick,
        hasActiveRef.current ? ACTIVE_INTERVAL_MS : IDLE_INTERVAL_MS
      );
    };

    void tick();
    return () => {
      cancelledRef.current = true;
      clearTimeout(timer);
    };
  }, [load]);

  return {
    jobs,
    activeCount: jobs.filter(isJobActive).length,
    isInitialLoading,
    error,
    refresh: () => void load(),
  };
}
