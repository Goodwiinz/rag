'use client';

import { cn } from '@/lib/utils';
import type { ActivityStep } from '@/components/chat/shared/cloudMessageView';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, ChevronRight, Loader2, XCircle } from 'lucide-react';
import { useReducedMotion } from 'framer-motion';
import React, { useState } from 'react';

// ─── helpers ──────────────────────────────────────────────────────────────────

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Produce a terse joined summary of done/error steps (max 3 verbs). */
function buildSummary(steps: ActivityStep[]): string {
  const settled = steps.filter((s) => s.status !== 'running');
  if (settled.length === 0) return '';
  const labels = settled.slice(0, 3).map((s) => s.label);
  return labels.join(' · ');
}

// ─── status dot / icon ────────────────────────────────────────────────────────

interface StatusIconProps {
  live: boolean;
  hasRunning: boolean;
  hasError: boolean;
  reduced: boolean;
}

function StatusIcon({ live, hasRunning, hasError, reduced }: StatusIconProps) {
  if (live && hasRunning) {
    return reduced ? (
      <span
        className="inline-block w-2 h-2 rounded-full bg-[var(--nous-sol)] dark:bg-[var(--nous-helios)]"
        aria-hidden="true"
      />
    ) : (
      <Loader2
        className="w-3 h-3 shrink-0 text-[var(--nous-sol)] dark:text-[var(--nous-helios)] animate-spin"
        aria-hidden="true"
      />
    );
  }
  if (hasError) {
    return (
      <XCircle
        className="w-3 h-3 shrink-0 text-[var(--nous-mars)]"
        aria-hidden="true"
      />
    );
  }
  return (
    <CheckCircle2
      className="w-3 h-3 shrink-0 text-[var(--nous-terra)]"
      aria-hidden="true"
    />
  );
}

// ─── step row ─────────────────────────────────────────────────────────────────

function StepRow({
  step,
  reduced,
  index,
}: {
  step: ActivityStep;
  reduced: boolean;
  index: number;
}) {
  return (
    <div
      className="flex items-center gap-2 min-w-0"
      style={
        reduced
          ? undefined
          : {
              animationDelay: `${index * 40}ms`,
              animationFillMode: 'both',
            }
      }
    >
      {/* status icon */}
      {step.status === 'running' ? (
        reduced ? (
          <span className="inline-block w-3.5 h-3.5 shrink-0 rounded-full border border-[var(--nous-sol)]/60 dark:border-[var(--nous-helios)]/60" />
        ) : (
          <Loader2
            className="w-3.5 h-3.5 shrink-0 text-[var(--nous-sol)] dark:text-[var(--nous-helios)] animate-spin"
            aria-hidden="true"
          />
        )
      ) : step.status === 'done' ? (
        <CheckCircle2
          className="w-3.5 h-3.5 shrink-0 text-[var(--nous-terra)]"
          aria-hidden="true"
        />
      ) : (
        <XCircle
          className="w-3.5 h-3.5 shrink-0 text-[var(--nous-mars)]"
          aria-hidden="true"
        />
      )}

      {/* label */}
      <span className="truncate text-[12px] text-[var(--nous-fg-1)] font-nous-ui">
        {step.label}
      </span>

      {/* tool name (mono, subdued) */}
      <span className="hidden sm:inline truncate text-[10px] text-[var(--nous-fg-3)] font-nous-mono">
        {step.tool}
      </span>

      {/* duration — right-aligned tabular */}
      {step.durationMs !== undefined && (
        <span className="ml-auto shrink-0 tabular-nums text-[10px] text-[var(--nous-fg-3)] font-nous-ui">
          {formatDuration(step.durationMs)}
        </span>
      )}
    </div>
  );
}

// ─── main component ───────────────────────────────────────────────────────────

export interface ChatActivityStripProps {
  steps: ActivityStep[];
  /** True while the parent message is actively streaming. */
  live?: boolean;
}

export function ChatActivityStrip({
  steps,
  live = false,
}: ChatActivityStripProps) {
  const [expanded, setExpanded] = useState(false);
  const reduced = useReducedMotion() ?? false;

  if (steps.length === 0) return null;

  const hasRunning = steps.some((s) => s.status === 'running');
  const hasError = steps.some((s) => s.status === 'error');

  // Collapsed summary text
  const currentRunning = steps.find((s) => s.status === 'running');
  const summaryText =
    live && hasRunning
      ? `${currentRunning?.label ?? 'Working'}…`
      : buildSummary(steps) ||
        `${steps.length} step${steps.length !== 1 ? 's' : ''}`;

  // Human-readable trigger label for screen readers
  const statusWord =
    live && hasRunning ? 'running' : hasError ? 'error' : 'done';
  const triggerLabel = `Agent activity — ${steps.length} step${steps.length !== 1 ? 's' : ''} ${statusWord}. ${expanded ? 'Collapse' : 'Expand'} details.`;

  return (
    <Collapsible
      open={expanded}
      onOpenChange={setExpanded}
      className={cn(
        'mb-3 rounded-[var(--nous-radius-md)] border border-[var(--nous-border-1)]',
        'bg-[var(--nous-bg-2)] overflow-hidden'
      )}
      style={{
        transition: reduced
          ? 'none'
          : 'border-color 150ms var(--nous-ease-out)',
      }}
    >
      {/* Trigger row — Radix wires aria-expanded + aria-controls automatically */}
      <CollapsibleTrigger
        aria-label={triggerLabel}
        className={cn(
          'flex w-full items-center gap-2 px-3 py-2 text-left',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nous-sol)]/40',
          'rounded-[var(--nous-radius-md)]',
          'transition-colors hover:bg-[var(--nous-bg-3)]'
        )}
      >
        {/* leading status icon */}
        <StatusIcon
          live={live}
          hasRunning={hasRunning}
          hasError={hasError}
          reduced={reduced}
        />

        {/* summary text */}
        <span className="min-w-0 flex-1 truncate text-[12px] text-[var(--nous-fg-2)] font-nous-ui">
          {summaryText}
        </span>

        {/* step count chip — Badge variant="info" is subdued (muted text/bg) */}
        <Badge
          variant="info"
          className="shrink-0 px-1.5 py-0.5 text-[10px] font-nous-ui tabular-nums leading-none rounded-full"
        >
          {steps.length}
        </Badge>

        {/* single rotating chevron — CSS transform avoids icon swap jank */}
        <ChevronRight
          className={cn(
            'w-3.5 h-3.5 shrink-0 text-[var(--nous-fg-3)]',
            reduced
              ? expanded
                ? 'rotate-90'
                : 'rotate-0'
              : 'transition-transform duration-200 ease-out',
            !reduced && expanded && 'rotate-90'
          )}
          aria-hidden="true"
        />
      </CollapsibleTrigger>

      {/* Expanded step list — Radix animates height via --radix-collapsible-content-height */}
      <CollapsibleContent
        className={cn(
          'overflow-hidden',
          !reduced &&
            'data-[state=open]:animate-collapsible-down data-[state=closed]:animate-collapsible-up'
        )}
      >
        <div className="flex flex-col gap-1.5 px-3 pb-3 pt-1 max-h-64 overflow-y-auto">
          <div
            className="h-px w-full bg-[var(--nous-border-1)] mb-1"
            aria-hidden="true"
          />
          {steps.map((step, i) => (
            <StepRow
              key={`${step.tool}-${i}`}
              step={step}
              reduced={reduced}
              index={i}
            />
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

export default ChatActivityStrip;
