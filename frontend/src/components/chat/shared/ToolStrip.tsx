'use client';

import React from 'react';
import { Clock, Coins, Search, Square } from 'lucide-react';

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
  // The execution plan's header shows its own "took …" duration (Chat
  // InlinePlan) — when a plan is present, the clock moved there. Showing it
  // twice is worse than moving it, so the strip omits it in that case.
  const hasPlan = !!message.plan && message.plan.length > 0;
  return {
    toolsUsed:
      message.metadata?.toolsUsed ??
      (message.toolExecutions && message.toolExecutions.length > 0
        ? message.toolExecutions.map((s) => s.label)
        : undefined),
    sourcesCount: message.metadata?.sourcesCount ?? visibleCitationsCount,
    responseTimeMs: hasPlan ? undefined : message.metadata?.responseTimeMs,
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
  stopped,
  tokenUsage,
}: ToolStripProps): React.JSX.Element | null {
  const hasTokens =
    !!tokenUsage && (tokenUsage.input > 0 || tokenUsage.output > 0);
  const hasAny =
    (toolsUsed && toolsUsed.length > 0) ||
    (sourcesCount && sourcesCount > 0) ||
    (responseTimeMs && responseTimeMs > 0) ||
    hasTokens ||
    stopped;
  if (!hasAny) return null;

  // Only claim "Searched" when the agent actually retrieved/used tools; a
  // response can carry just a timing with no sources (e.g. RAG off).
  const didSearch =
    (toolsUsed && toolsUsed.length > 0) || (sourcesCount && sourcesCount > 0);

  return (
    <div className="nous-tool-strip">
      {didSearch && (
        <>
          <div className="nous-tool-strip-icon">
            <Search className="w-2.5 h-2.5" strokeWidth={2} />
          </div>
          <span className="nous-tool-strip-label">Searched</span>
          {toolsUsed?.slice(0, 3).map((tool) => (
            <React.Fragment key={tool}>
              <span className="nous-tool-strip-sep" />
              <span className="nous-tool-strip-chip">{tool}</span>
            </React.Fragment>
          ))}
          {sourcesCount && sourcesCount > 0 && (
            <>
              <span className="nous-tool-strip-sep" />
              <span className="nous-tool-strip-chip">
                {sourcesCount} {sourcesCount === 1 ? 'source' : 'sources'}
              </span>
            </>
          )}
        </>
      )}
      {responseTimeMs && responseTimeMs > 0 && (
        <span className="nous-tool-strip-time inline-flex items-center gap-1">
          <Clock className="w-2.5 h-2.5" strokeWidth={2} />
          {(responseTimeMs / 1000).toFixed(1)}s
        </span>
      )}
      {hasTokens && tokenUsage && (
        <span
          className="nous-tool-strip-tokens inline-flex items-center gap-1"
          title={`${tokenUsage.input.toLocaleString()} input tokens · ${tokenUsage.output.toLocaleString()} output tokens (this turn)`}
        >
          <Coins className="w-2.5 h-2.5" strokeWidth={2} />
          {formatTokenCount(tokenUsage.input)} in ·{' '}
          {formatTokenCount(tokenUsage.output)} out
        </span>
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
