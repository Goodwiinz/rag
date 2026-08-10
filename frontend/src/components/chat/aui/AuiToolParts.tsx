'use client';

import {
  memo,
  useId,
  useState,
  type ReactElement,
  type ReactNode,
} from 'react';
import type { ToolCallMessagePartStatus } from '@assistant-ui/react';
import { ChevronDown, Clock, Coins, Square, Wrench } from 'lucide-react';
import { ToolFallback } from '@/components/assistant-ui/tool-fallback';
import type { ActivityStep } from '@/components/chat/shared/cloudMessageView';
import {
  formatTokenCount,
  type ToolStripProps,
} from '@/components/chat/shared/ToolStrip';
import { toToolCallParts } from './convertMessage';

interface AuiToolPartsProps {
  messageId: string;
  steps: ActivityStep[];
  isStreaming: boolean;
  summary?: ToolStripProps;
}

interface ToolActivityDisclosureProps {
  count: number;
  isStreaming: boolean;
  summary?: ToolStripProps;
  children: ReactNode;
}

/**
 * A 'running' step on a message that is no longer streaming never settled —
 * the turn was stopped or the stream dropped — so it reads as cancelled.
 */
function toPartStatus(
  status: ActivityStep['status'],
  isStreaming: boolean
): ToolCallMessagePartStatus {
  if (status === 'error') return { type: 'incomplete', reason: 'error' };
  if (status === 'running') {
    return isStreaming
      ? { type: 'running' }
      : { type: 'incomplete', reason: 'cancelled' };
  }
  return { type: 'complete' };
}

// HITL approvals stay on the existing interrupt/confirm flow in stage 1; we
// never emit a 'requires-action' status, so the approval bar (the only
// consumer of these callbacks) cannot render.
const noopHandlers = {
  addResult: () => undefined,
  resume: () => undefined,
  respondToApproval: () => undefined,
};

/** One transcript-level disclosure for a consecutive tool run. Individual
 * ToolFallback disclosures stay nested inside for optional raw payloads. */
export function ToolActivityDisclosure({
  count,
  isStreaming,
  summary,
  children,
}: ToolActivityDisclosureProps): ReactElement {
  const [expanded, setExpanded] = useState(isStreaming);
  const contentId = useId();
  const isExpanded = isStreaming || expanded;

  const countLabel = `${count} ${count === 1 ? 'tool' : 'tools'}`;
  const actionLabel = isStreaming ? 'Using' : 'Used';
  const hasTokens =
    summary?.tokenUsage &&
    (summary.tokenUsage.input > 0 || summary.tokenUsage.output > 0);

  return (
    <div
      data-slot="aui-tool-parts"
      className="mb-3 max-w-full rounded-lg border border-(--nous-border-1) bg-(--nous-bg-2)/70"
    >
      <button
        type="button"
        aria-expanded={isExpanded}
        aria-controls={contentId}
        onClick={() => setExpanded((current) => !current)}
        className="flex w-full min-w-0 items-center gap-2 rounded-lg px-3 py-2 text-left font-nous-mono text-[10px] tracking-[0.04em] text-(--nous-fg-3) transition-colors hover:bg-(--nous-bg-2) focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--nous-sol)"
      >
        <Wrench className="h-3.5 w-3.5 shrink-0 text-(--nous-sol)" />
        <span className="shrink-0 font-semibold text-(--nous-fg-2)">
          {actionLabel} {countLabel}
        </span>
        {summary?.sourcesCount ? (
          <span className="hidden shrink-0 sm:inline">
            · {summary.sourcesCount}{' '}
            {summary.sourcesCount === 1 ? 'source' : 'sources'}
          </span>
        ) : null}
        {summary?.responseTimeMs ? (
          <span className="ml-auto inline-flex shrink-0 items-center gap-1">
            <Clock className="h-3 w-3" />
            {(summary.responseTimeMs / 1000).toFixed(1)}s
          </span>
        ) : null}
        {hasTokens && summary?.tokenUsage ? (
          <span className="hidden shrink-0 items-center gap-1 sm:inline-flex">
            <Coins className="h-3 w-3" />
            {formatTokenCount(summary.tokenUsage.input)} in ·{' '}
            {formatTokenCount(summary.tokenUsage.output)} out
          </span>
        ) : null}
        {summary?.stopped ? (
          <span className="inline-flex shrink-0 items-center gap-1">
            <Square className="h-2.5 w-2.5" /> Stopped
          </span>
        ) : null}
        <ChevronDown
          aria-hidden="true"
          className={`h-3.5 w-3.5 shrink-0 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
        />
      </button>
      {isExpanded ? (
        <div
          id={contentId}
          role="region"
          aria-label="Tool activity details"
          className="flex flex-col gap-1 border-t border-(--nous-border-1) px-3 py-2"
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}

export const AuiToolParts = memo(function AuiToolParts({
  messageId,
  steps,
  isStreaming,
  summary,
}: AuiToolPartsProps): ReactElement | null {
  if (steps.length === 0) return null;
  const parts = toToolCallParts(messageId, steps);

  return (
    <ToolActivityDisclosure
      count={steps.length}
      isStreaming={isStreaming}
      summary={summary}
    >
      {parts.map((part, i) => (
        <ToolFallback
          key={part.toolCallId}
          type="tool-call"
          toolCallId={part.toolCallId}
          toolName={part.toolName}
          args={part.args}
          argsText={part.argsText}
          result={part.result}
          status={toPartStatus(steps[i].status, isStreaming)}
          {...noopHandlers}
        />
      ))}
    </ToolActivityDisclosure>
  );
});
