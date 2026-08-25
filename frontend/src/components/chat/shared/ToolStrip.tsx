'use client';

import React from 'react';
import { Search, Square, Wrench } from 'lucide-react';

import {
  MessageTiming,
  type TimingStat,
} from '@/components/elements/message-timing';
import type { ChatPageMessage } from './cloudMessageView';

/** Compact token count: 1234 → "1.2k", 2_500_000 → "2.5M", <1000 verbatim. */
export function formatTokenCount(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(n < 10000 ? 1 : 0)}k`;
  return `${(n / 1_000_000).toFixed(1)}M`;
}

export interface ToolStripProps {
  toolsUsed?: string[];
  sourcesCount?: number;
  responseTimeMs?: number;
  /** Time to first token, same origin as `responseTimeMs`. Splits the clock
   * into the wait before the answer started and the time spent writing it. */
  ttftMs?: number;
  stopped?: boolean;
  tokenUsage?: { input: number; output: number };
}

/**
 * Derive the strip props from a committed message. Prefers explicit
 * metadata; falls back to toolExecutions labels / citation count so the
 * strip never under-reports when metadata wasn't set.
 */
export function getToolStripProps(
  message: ChatPageMessage,
  visibleCitationsCount: number
): ToolStripProps {
  return {
    toolsUsed:
      message.metadata?.toolsUsed ??
      (message.toolExecutions && message.toolExecutions.length > 0
        ? message.toolExecutions.map((s) => s.label)
        : undefined),
    sourcesCount: message.metadata?.sourcesCount ?? visibleCitationsCount,
    responseTimeMs: message.metadata?.responseTimeMs,
    ttftMs: message.metadata?.ttftMs,
    stopped: message.metadata?.stopped,
    tokenUsage: message.metadata?.tokenUsage,
  };
}

/**
 * Footer strip on committed assistant messages: tools used, source count,
 * response time, per-turn token usage, stopped indicator. Shared by the
 * legacy ChatBubble and the assistant-ui message renderer.
 */
export function ToolStrip({
  toolsUsed,
  sourcesCount,
  responseTimeMs,
  ttftMs,
  stopped,
  tokenUsage,
}: ToolStripProps): React.JSX.Element | null {
  const hasTokens =
    !!tokenUsage && (tokenUsage.input > 0 || tokenUsage.output > 0);
  const timingStats: TimingStat[] = [];
  if (ttftMs && ttftMs > 0) {
    timingStats.push({
      label: 'first word',
      value: `${(ttftMs / 1000).toFixed(1)}s`,
    });
  }
  if (responseTimeMs && responseTimeMs > 0) {
    timingStats.push({
      label: 'total',
      value: `${(responseTimeMs / 1000).toFixed(1)}s`,
    });
  }
  if (hasTokens && tokenUsage) {
    timingStats.push({
      label: 'tokens',
      value: `${formatTokenCount(tokenUsage.input)} in · ${formatTokenCount(tokenUsage.output)} out`,
    });
  }
  const hasAny =
    (toolsUsed && toolsUsed.length > 0) ||
    (sourcesCount && sourcesCount > 0) ||
    (responseTimeMs && responseTimeMs > 0) ||
    hasTokens ||
    stopped;
  if (!hasAny) return null;

  // Tool-only turns may mutate data, so reserve "Searched" for turns that
  // actually produced sources and use the neutral "Used" otherwise.
  const hasTools = Boolean(toolsUsed?.length);
  const hasSources = (sourcesCount ?? 0) > 0;
  const hasActivity = hasTools || hasSources;
  const activityLabel = hasSources ? 'Searched' : 'Used';
  const ActivityIcon = hasSources ? Search : Wrench;

  return (
    <div className="nous-tool-strip">
      {hasActivity && (
        <>
          <div className="nous-tool-strip-icon">
            <ActivityIcon className="w-2.5 h-2.5" strokeWidth={2} />
          </div>
          <span className="nous-tool-strip-label">{activityLabel}</span>
          {toolsUsed?.slice(0, 3).map((tool, index) => (
            <React.Fragment key={`${tool}-${index}`}>
              <span className="nous-tool-strip-sep" />
              <span className="nous-tool-strip-chip">{tool}</span>
            </React.Fragment>
          ))}
          {hasSources && (
            <>
              <span className="nous-tool-strip-sep" />
              <span className="nous-tool-strip-chip">
                {sourcesCount} {sourcesCount === 1 ? 'source' : 'sources'}
              </span>
            </>
          )}
        </>
      )}
      {timingStats.length > 0 && (
        <MessageTiming
          stats={timingStats}
          className="w-auto max-w-none gap-x-3 [&>span>span:first-child]:text-(--nous-fg-3) [&>span>span:last-child]:text-(--nous-fg-2)"
        />
      )}
      {stopped && (
        <span
          className="inline-flex items-center gap-1 text-[10px] font-medium text-(--nous-fg-3)"
          title="You stopped this response; the text above is partial."
        >
          <Square className="w-2 h-2" strokeWidth={2.4} />
          Stopped
        </span>
      )}
    </div>
  );
}
