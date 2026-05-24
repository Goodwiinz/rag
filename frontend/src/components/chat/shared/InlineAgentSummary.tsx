'use client';

import { useAgentActivityStore } from '@/stores/agentActivityStore';
import { cn } from '@/lib/utils';
import { ChevronRight, Wrench } from 'lucide-react';
import { useState } from 'react';

interface InlineAgentSummaryProps {
  threadId: string | null;
  /** Only show when the bubble is the latest assistant message (optional gating). */
  show?: boolean;
}

/**
 * A collapsed, Cowork-style inline summary of agent steps, shown directly
 * above an assistant message bubble. Expands to reveal the tool list.
 *
 * Reads from the same `agentActivityStore` that powers the side-rail
 * `AgentActivityPanel`, so the two stay in sync.
 */
export function InlineAgentSummary({
  threadId,
  show = true,
}: InlineAgentSummaryProps) {
  const run = useAgentActivityStore((s) =>
    threadId ? s.runs[threadId] : undefined
  );
  const [open, setOpen] = useState(false);

  if (!show || !run || run.steps.length === 0) return null;

  const active = run.steps.filter((s) => s.status === 'active').length;
  const done = run.steps.filter((s) => s.status === 'done').length;
  const errored = run.steps.filter((s) => s.status === 'error').length;
  const total = run.steps.length;

  const summary =
    run.state === 'done'
      ? `Ran ${total} ${total === 1 ? 'tool' : 'tools'}`
      : run.state === 'error'
        ? `Ran ${total} ${total === 1 ? 'tool' : 'tools'} · ${errored} failed`
        : `${done}/${total} complete${active > 0 ? ` · ${active} active` : ''}`;

  return (
    <div className="ml-4 mb-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'group inline-flex items-center gap-2 rounded-lg border px-2.5 py-1 text-[11px] transition-colors',
          'border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]/60',
          'text-[var(--nous-fg-3)] hover:text-[var(--nous-fg-1)]',
          'hover:border-[var(--nous-sol)]/30'
        )}
        style={{ fontFamily: 'var(--nous-font-mono)' }}
        aria-expanded={open}
        aria-label={
          open ? 'Hide agent steps' : `Show agent steps: ${summary}`
        }
      >
        <Wrench
          className={cn(
            'h-3 w-3 shrink-0',
            run.state === 'running' && active > 0
              ? 'animate-pulse text-[var(--nous-sol)]'
              : run.state === 'error'
                ? 'text-[var(--nous-mars)]'
                : 'text-[var(--nous-fg-3)]'
          )}
        />
        <span>{summary}</span>
        <ChevronRight
          className={cn(
            'h-3 w-3 shrink-0 transition-transform',
            open && 'rotate-90'
          )}
        />
      </button>

      {open && (
        <ul
          className="mt-2 ml-1 space-y-1"
          style={{ fontFamily: 'var(--nous-font-mono)' }}
        >
          {run.steps.map((step) => (
            <li
              key={step.id}
              className="flex items-center gap-2 text-[11px]"
            >
              <span
                className={cn(
                  'h-1.5 w-1.5 shrink-0 rounded-full',
                  step.status === 'active' &&
                    'animate-pulse bg-[var(--nous-sol)]',
                  step.status === 'done' && 'bg-[var(--nous-sol)]/60',
                  step.status === 'error' && 'bg-[var(--nous-mars)]'
                )}
              />
              <span className="text-[var(--nous-fg-3)]">
                {step.label}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
