'use client';

import { useAgentActivityStore } from '@/stores/agentActivityStore';
import { ChevronRight } from 'lucide-react';

interface ProgressPanelProps {
  threadId: string | null;
}

/**
 * Compact progress card — matches Cowork's "Progress · N of M >" header.
 * Rendered above the full `AgentActivityPanel` for a quick scan of status.
 * Hidden when there's no active or recent run for this thread.
 */
export function ProgressPanel({ threadId }: ProgressPanelProps) {
  const run = useAgentActivityStore((s) =>
    threadId ? s.runs[threadId] : undefined
  );

  if (!run || run.steps.length === 0) return null;

  const done = run.steps.filter((s) => s.status === 'done').length;
  const errored = run.steps.filter((s) => s.status === 'error').length;
  const total = run.steps.length;

  const label =
    run.state === 'done'
      ? `${total} of ${total}`
      : run.state === 'error'
        ? `${done}/${total} · ${errored} failed`
        : `${done} of ${total}`;

  const accent =
    run.state === 'error'
      ? 'var(--error-red)'
      : run.state === 'done'
        ? 'var(--nous-terra)'
        : 'var(--nous-sol)';

  return (
    <section aria-label="Agent progress">
      <div
        className="flex items-center justify-between rounded-xl border px-3 py-2.5"
        style={{
          borderColor: 'var(--nous-border-1)',
          background: 'var(--nous-bg-2)',
          fontFamily: 'var(--nous-font-ui)',
        }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="h-1.5 w-1.5 shrink-0 rounded-full"
            style={{
              background: accent,
              animation:
                run.state === 'running' ? 'pulse 1.5s ease-in-out infinite' : undefined,
            }}
          />
          <span
            className="text-[11px] uppercase tracking-wider"
            style={{ color: 'var(--nous-fg-3)' }}
          >
            Progress
          </span>
          <span
            className="text-sm tabular-nums"
            style={{ color: 'var(--nous-fg-1)' }}
          >
            {label}
          </span>
        </div>
        <ChevronRight
          className="h-3.5 w-3.5 shrink-0"
          style={{ color: 'var(--nous-fg-3)' }}
        />
      </div>
    </section>
  );
}
