'use client';

import { useEffect, useRef, useState } from 'react';
import {
  entityService,
  type ProcessingJobStatus,
} from '@/services/entityService';

/**
 * Mirrors `ProcessingJob.is_active` in backend/src/models/processing.py
 * (queued, running, retrying) — a retried job is still working, and treating
 * it as finished showed a success tick and dropped polling to the idle rate
 * mid-run.
 *
 * `pending` is included here but not in the backend property: for the reader,
 * a job that has not started yet is unfinished work, and the alternative is
 * telling them it completed.
 */
const ACTIVE_STATUSES = new Set(['pending', 'queued', 'running', 'retrying']);

export function isJobActive(job: ProcessingJobStatus): boolean {
  return ACTIVE_STATUSES.has(job.status.toLowerCase());
}

export function isJobFailed(job: ProcessingJobStatus): boolean {
  return job.status.toLowerCase() === 'failed';
}

export function isJobCancelled(job: ProcessingJobStatus): boolean {
  return job.status.toLowerCase() === 'cancelled';
}

/** Terminal, and neither a success nor a failure the user should act on. */
export function jobStatusLabel(job: ProcessingJobStatus): string {
  if (isJobFailed(job)) return 'Failed';
  if (isJobCancelled(job)) return 'Cancelled';
  if (isJobActive(job)) return 'Running';
  return 'Completed';
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
export function useProcessingJobs(limit = 50): UseProcessingJobsResult {
  const [jobs, setJobs] = useState<ProcessingJobStatus[]>([]);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Read by the scheduler without making it a dependency — otherwise every
  // poll would tear down and rebuild the timer.
  const pollFastRef = useRef(false);
  // Monotonic token for in-flight loads: a manual refresh() and the scheduled
  // tick can overlap, and whichever response landed last used to win — a slow
  // stale payload could overwrite fresher jobs. Only the newest load may
  // commit state.
  const loadGenerationRef = useRef(0);
  const refresh = useRef<() => void>(() => undefined);

  useEffect(() => {
    // Per-effect cancellation. A shared ref breaks under Strict Mode: the
    // first invocation is cleaned up while its load() is still in flight, the
    // second resets the shared flag, and the first then schedules a timer its
    // own cleanup can no longer clear — two pollers for the page's lifetime.
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const load = async (): Promise<void> => {
      const gen = ++loadGenerationRef.current;
      try {
        const response = await entityService.listProcessingJobs({ limit });
        if (cancelled || gen !== loadGenerationRef.current) return;
        const next = response.jobs ?? [];
        setJobs(next);
        // The list is newest-first and only the first page is fetched, so an
        // older job could still be running past the page edge. When the page
        // is full, hold the fast cadence rather than assuming an idle queue.
        //
        // ponytail: the count itself can still undercount past `limit`. The
        // fix is a server-side is_active filter, not N calls (the endpoint
        // takes one status per request); revisit if queues run deeper than 50.
        const truncated = (response.total ?? next.length) > next.length;
        pollFastRef.current = next.some(isJobActive) || truncated;
        setError(null);
      } catch (err) {
        if (cancelled || gen !== loadGenerationRef.current) return;
        // A failed poll is not a failed job — keep the last known list on
        // screen and say freshness is in doubt, rather than blanking. Also
        // back off: with an active queue upstream of an outage, leaving this
        // true would keep hammering at 4s forever; the next successful poll
        // turns it back on if work really is in flight.
        pollFastRef.current = false;
        setError(err instanceof Error ? err.message : 'Could not reach jobs');
      } finally {
        if (!cancelled) setIsInitialLoading(false);
      }
    };

    refresh.current = () => void load();

    const tick = async (): Promise<void> => {
      await load();
      if (cancelled) return;
      timer = setTimeout(
        tick,
        pollFastRef.current ? ACTIVE_INTERVAL_MS : IDLE_INTERVAL_MS
      );
    };

    void tick();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [limit]);

  return {
    jobs,
    activeCount: jobs.filter(isJobActive).length,
    isInitialLoading,
    error,
    refresh: () => refresh.current(),
  };
}
