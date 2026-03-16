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

export function ToolExecutionCard({ execution }: ToolExecutionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const statusIcon = {
    running: <Loader2 className="h-3 w-3 animate-spin text-primary" />,
    completed: <CheckCircle2 className="h-3 w-3 text-green-500" />,
    failed: <XCircle className="h-3 w-3 text-destructive" />,
  }[execution.status];

  return (
    <div className="border border-border rounded-md bg-muted/20 text-xs my-1">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 w-full px-3 py-2 hover:bg-muted/40 transition-colors text-left"
        aria-label={`${isExpanded ? 'Collapse' : 'Expand'} tool execution: ${execution.toolDisplayName}`}
      >
        {isExpanded ? (
          <ChevronDown className="h-3 w-3 shrink-0" />
        ) : (
          <ChevronRight className="h-3 w-3 shrink-0" />
        )}
        {statusIcon}
        <span className="text-foreground font-medium truncate">
          {execution.toolDisplayName}
        </span>
        {execution.durationMs != null && (
          <span className="ml-auto text-muted-foreground">
            {execution.durationMs}ms
          </span>
        )}
      </button>
      {isExpanded && execution.result && (
        <div className="px-3 pb-2 text-muted-foreground border-t border-border pt-2">
          <pre className="whitespace-pre-wrap break-words text-[11px]">
            {typeof execution.result === 'string'
              ? execution.result
              : JSON.stringify(execution.result, null, 2)}
          </pre>
        </div>
      )}
      {isExpanded && execution.error && (
        <div className="px-3 pb-2 text-destructive border-t border-border pt-2">
          {execution.error}
        </div>
      )}
    </div>
  );
}
