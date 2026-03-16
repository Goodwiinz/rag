'use client';

import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Loader2,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import type { ToolExecution } from '@/types/agent-chat';

interface ToolExecutionCardProps {
  execution: ToolExecution;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function ResultSummary({
  result,
}: {
  result: unknown;
}): React.ReactElement | null {
  if (result == null) return null;

  if (typeof result === 'string') {
    return <span>{result}</span>;
  }

  if (typeof result === 'object' && !Array.isArray(result)) {
    const obj = result as Record<string, unknown>;

    if (typeof obj.message === 'string') {
      return <span>{obj.message}</span>;
    }

    if (typeof obj.status === 'string') {
      const count =
        obj.count ?? obj.ingested_count ?? obj.total ?? obj.results_count;
      return (
        <span>
          {obj.status}
          {count != null ? ` · ${String(count)} items` : ''}
        </span>
      );
    }
  }

  return null;
}

export function ToolExecutionCard({ execution }: ToolExecutionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  let statusIcon: React.ReactNode = null;
  if (execution.status === 'running') {
    statusIcon = <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />;
  } else if (execution.status === 'completed') {
    statusIcon = <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />;
  } else if (execution.status === 'failed') {
    statusIcon = <XCircle className="h-3.5 w-3.5 text-destructive" />;
  }

  const hasDetails = execution.result != null || execution.error != null;

  return (
    <div className="border border-border/50 rounded-lg bg-muted/20 text-xs my-2 overflow-hidden">
      {/* Header row */}
      <button
        onClick={() => hasDetails && setIsExpanded(!isExpanded)}
        className={`flex items-center gap-2 w-full px-3 py-2 text-left ${
          hasDetails ? 'hover:bg-muted/40 cursor-pointer' : 'cursor-default'
        } transition-colors`}
        aria-label={`${isExpanded ? 'Collapse' : 'Expand'} tool execution: ${execution.toolDisplayName}`}
      >
        {statusIcon}
        <span className="text-foreground font-medium">
          {execution.toolDisplayName}
        </span>
        <span className="ml-auto flex items-center gap-2 shrink-0">
          {execution.durationMs != null && (
            <span className="text-muted-foreground/70 tabular-nums text-[10px]">
              {formatDuration(execution.durationMs)}
            </span>
          )}
          {hasDetails &&
            (isExpanded ? (
              <ChevronDown className="h-3 w-3 text-muted-foreground/60" />
            ) : (
              <ChevronRight className="h-3 w-3 text-muted-foreground/60" />
            ))}
        </span>
      </button>

      {/* Result summary (always visible when completed) */}
      {!isExpanded &&
        execution.status === 'completed' &&
        execution.result != null && (
          <div className="px-3 pb-2 -mt-0.5 text-muted-foreground leading-relaxed">
            <ResultSummary result={execution.result} />
          </div>
        )}

      {/* Error summary (always visible when failed) */}
      {!isExpanded && execution.status === 'failed' && execution.error && (
        <div className="px-3 pb-2 -mt-0.5 text-destructive leading-relaxed">
          {execution.error}
        </div>
      )}

      {/* Expanded details */}
      {isExpanded && execution.result != null && (
        <div className="border-t border-border/30 px-3 py-2 max-h-[200px] overflow-y-auto bg-muted/10">
          <pre className="whitespace-pre-wrap break-words text-[11px] text-muted-foreground leading-relaxed">
            {typeof execution.result === 'string'
              ? execution.result
              : JSON.stringify(
                  execution.result as Record<string, unknown>,
                  null,
                  2
                )}
          </pre>
        </div>
      )}
      {isExpanded && execution.error && (
        <div className="border-t border-border/30 px-3 py-2 text-destructive">
          {execution.error}
        </div>
      )}
    </div>
  );
}
