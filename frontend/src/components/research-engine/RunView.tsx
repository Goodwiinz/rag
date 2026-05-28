'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Loader2,
  Pause,
  Play,
  AlertCircle,
  Coins,
} from 'lucide-react';
import { getRun, pauseRun, resumeRun } from '@/services/researchEngineService';
import {
  useResearchEngineStore,
  type ResearchRun,
  type RunStepEvent,
} from '@/store/research-engine-store';
import { StepProgress, type StepData } from './StepProgress';

interface RunViewProps {
  runId: string;
}

const STATUS_BADGE: Record<
  string,
  { bg: string; text: string; border: string; label: string }
> = {
  pending: {
    bg: 'bg-gray-500/10',
    text: 'text-muted-foreground',
    border: 'border-border/30',
    label: 'Pending',
  },
  running: {
    bg: 'bg-brand-cyan/10',
    text: 'text-brand-cyan',
    border: 'border-brand-cyan/30',
    label: 'Running',
  },
  paused: {
    bg: 'bg-helios/10',
    text: 'text-helios',
    border: 'border-helios/30',
    label: 'Paused',
  },
  completed: {
    bg: 'bg-sol/10',
    text: 'text-sol',
    border: 'border-sol/30',
    label: 'Completed',
  },
  failed: {
    bg: 'bg-red-500/10',
    text: 'text-red-400',
    border: 'border-red-500/30',
    label: 'Failed',
  },
};

async function getAuthToken(): Promise<string | null> {
  try {
    const { createClient } = await import('@/lib/supabase/client');
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    return session?.access_token ?? null;
  } catch {
    return null;
  }
}

export function RunView({ runId }: RunViewProps) {
  const router = useRouter();
  const {
    activeRun,
    setActiveRun,
    runEvents,
    addRunEvent,
    clearRunEvents,
    setLoading,
    isLoading,
    setError,
    error,
  } = useResearchEngineStore();

  const [actionLoading, setActionLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // Fetch run details on mount
  const fetchRun = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = (await getRun(runId)) as ResearchRun;
      setActiveRun(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load run details'
      );
    } finally {
      setLoading(false);
    }
  }, [runId, setActiveRun, setLoading, setError]);

  useEffect(() => {
    clearRunEvents();
    fetchRun();
    return () => {
      setActiveRun(null);
      clearRunEvents();
    };
  }, [fetchRun, clearRunEvents, setActiveRun]);

  // Connect to SSE stream when run is running
  useEffect(() => {
    const runStatus = activeRun?.status;
    if (runStatus !== 'running' && runStatus !== 'pending') return;

    const controller = new AbortController();
    abortRef.current = controller;

    const connectSSE = async () => {
      const token = await getAuthToken();
      const headers: Record<string, string> = {
        Accept: 'text/event-stream',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      try {
        const response = await fetch(
          `/api/v1/research-engine/runs/${runId}/stream`,
          {
            method: 'GET',
            headers,
            signal: controller.signal,
          }
        );

        if (!response.ok || !response.body) return;

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let currentEventType: string | null = null;

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';

            for (const line of lines) {
              const trimmed = line.trim();

              if (trimmed.startsWith('event: ')) {
                currentEventType = trimmed.slice(7).trim();
              } else if (trimmed.startsWith('data: ') && currentEventType) {
                try {
                  const parsed = JSON.parse(trimmed.slice(6)) as RunStepEvent;
                  addRunEvent({
                    ...parsed,
                    event: currentEventType,
                  });

                  // Update run status from terminal events
                  if (
                    currentEventType === 'run_complete' ||
                    currentEventType === 'run_failed'
                  ) {
                    fetchRun();
                  }
                } catch {
                  // skip malformed JSON
                }
                currentEventType = null;
              }
            }
          }
        } finally {
          reader.releaseLock();
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          console.error('SSE stream error:', err);
        }
      }
    };

    connectSSE();

    return () => {
      controller.abort();
      abortRef.current = null;
    };
  }, [runId, activeRun?.status, addRunEvent, fetchRun]);

  // Build step data from events
  const steps: StepData[] = buildStepsFromEvents(runEvents);

  // Total tokens from events or run data
  const totalTokens =
    steps.reduce((sum, s) => sum + s.tokenCount, 0) ||
    activeRun?.total_tokens ||
    0;

  const handlePause = async () => {
    setActionLoading(true);
    try {
      await pauseRun(runId);
      await fetchRun();
    } catch {
      // ignore
    } finally {
      setActionLoading(false);
    }
  };

  const handleResume = async () => {
    setActionLoading(true);
    try {
      await resumeRun(runId);
      await fetchRun();
    } catch {
      // ignore
    } finally {
      setActionLoading(false);
    }
  };

  const badge = STATUS_BADGE[activeRun?.status ?? 'pending'];

  if (isLoading && !activeRun) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-sol" />
        <span className="ml-2 font-mono text-sm text-muted-foreground">
          Loading run...
        </span>
      </div>
    );
  }

  if (error && !activeRun) {
    return (
      <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded">
        <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
        <span className="text-sm text-red-400 font-mono">{error}</span>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-4 mb-6">
        <button
          onClick={() => router.back()}
          className="p-1.5 rounded hover:bg-white/5 text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Go back"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>

        <div className="flex-1">
          <h1 className="text-xl font-mono font-bold text-muted-foreground">
            Run <span className="text-brand-cyan">{runId.slice(0, 8)}</span>
          </h1>
          {activeRun?.started_at && (
            <p className="text-xs font-mono text-muted-foreground mt-0.5">
              Started {new Date(activeRun.started_at).toLocaleString()}
            </p>
          )}
        </div>

        {/* Status badge */}
        <span
          className={`px-3 py-1 text-xs font-mono rounded border ${badge.bg} ${badge.text} ${badge.border}`}
        >
          {badge.label}
        </span>

        {/* Total tokens */}
        <div className="flex items-center gap-1.5 text-xs font-mono text-muted-foreground">
          <Coins className="h-3.5 w-3.5" />
          {totalTokens.toLocaleString()} tokens
        </div>

        {/* Pause/Resume */}
        {activeRun?.status === 'running' && (
          <button
            onClick={handlePause}
            disabled={actionLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono bg-helios/10 text-helios border border-helios/30 rounded hover:bg-helios/20 transition-colors disabled:opacity-50"
          >
            {actionLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Pause className="h-3.5 w-3.5" />
            )}
            Pause
          </button>
        )}
        {activeRun?.status === 'paused' && (
          <button
            onClick={handleResume}
            disabled={actionLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono bg-sol/10 text-sol border border-sol/30 rounded hover:bg-sol/20 transition-colors disabled:opacity-50"
          >
            {actionLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
            Resume
          </button>
        )}
      </div>

      {/* Steps list */}
      {steps.length === 0 && !isLoading ? (
        <div className="text-center py-16">
          <p className="text-muted-foreground font-mono text-sm">
            {activeRun?.status === 'pending'
              ? 'Waiting for run to start...'
              : 'No steps received yet.'}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {steps.map((step) => (
            <StepProgress key={step.stepIndex} step={step} />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Build a list of StepData from the stream of RunStepEvents.
 * Events with the same step_index are merged together, with later events
 * overwriting earlier fields.
 */
function buildStepsFromEvents(events: RunStepEvent[]): StepData[] {
  const stepMap = new Map<number, StepData>();

  for (const evt of events) {
    const idx = evt.step_index;
    if (idx === undefined || idx === null) continue;

    const existing = stepMap.get(idx);

    const stepStatus = (() => {
      switch (evt.event) {
        case 'step_start':
          return 'running' as const;
        case 'step_complete':
          return 'complete' as const;
        case 'step_error':
          return 'error' as const;
        default:
          return existing?.status ?? ('pending' as const);
      }
    })();

    const merged: StepData = {
      stepIndex: idx,
      stepName: evt.step_name ?? existing?.stepName ?? `Step ${idx + 1}`,
      stepType: evt.step_type ?? existing?.stepType ?? 'unknown',
      status: stepStatus,
      mode: (evt.mode as StepData['mode']) ?? existing?.mode,
      tokenCount: evt.token_count ?? existing?.tokenCount ?? 0,
      qualityMarks: evt.quality_marks ?? existing?.qualityMarks ?? [],
      output: evt.output ?? existing?.output,
      sources: evt.sources ?? existing?.sources,
      prompt: evt.prompt ?? existing?.prompt,
      errorMessage: evt.error_message ?? existing?.errorMessage,
    };

    stepMap.set(idx, merged);
  }

  return Array.from(stepMap.values()).sort((a, b) => a.stepIndex - b.stepIndex);
}
