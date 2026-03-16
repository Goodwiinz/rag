'use client';

import React from 'react';
import {
  User,
  Bot,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { ToolExecutionCard } from './ToolExecutionCard';
import type { AgentMessage, ToolExecution } from '@/types/agent-chat';

interface AgentMessageItemProps {
  message: AgentMessage;
}

/**
 * Group consecutive tool executions with the same toolName into batches.
 * E.g., 3x "add_document_to_project" → one group with count badge.
 */
function groupToolExecutions(
  executions: ToolExecution[]
): Array<{ key: string; items: ToolExecution[] }> {
  const groups: Array<{ key: string; items: ToolExecution[] }> = [];
  for (const exec of executions) {
    const last = groups[groups.length - 1];
    if (last && last.items[0].toolName === exec.toolName) {
      last.items.push(exec);
    } else {
      groups.push({ key: exec.id, items: [exec] });
    }
  }
  return groups;
}

export function AgentMessageItem({ message }: AgentMessageItemProps) {
  const isUser = message.role === 'user';

  const toolGroups = message.toolExecutions
    ? groupToolExecutions(message.toolExecutions)
    : [];

  return (
    <div className={`flex gap-3 px-4 py-3 ${isUser ? '' : 'bg-muted/20'}`}>
      <div
        className={`shrink-0 h-6 w-6 rounded-full flex items-center justify-center mt-0.5 ${
          isUser
            ? 'bg-primary/10 text-primary'
            : 'bg-muted text-muted-foreground'
        }`}
      >
        {isUser ? (
          <User className="h-3.5 w-3.5" />
        ) : (
          <Bot className="h-3.5 w-3.5" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        {/* Message content */}
        {message.content && (
          <div className="text-sm text-foreground whitespace-pre-wrap break-words leading-relaxed">
            {message.content}
            {message.isStreaming && (
              <span className="inline-block w-1.5 h-4 bg-primary animate-pulse ml-0.5 align-text-bottom" />
            )}
          </div>
        )}

        {/* Tool executions — grouped */}
        {toolGroups.length > 0 && (
          <div className="mt-2 space-y-1">
            {toolGroups.map((group) =>
              group.items.length === 1 ? (
                <ToolExecutionCard key={group.key} execution={group.items[0]} />
              ) : (
                <ToolExecutionGroupCard
                  key={group.key}
                  executions={group.items}
                />
              )
            )}
          </div>
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.citations.map((cite, i) => (
              <span
                key={`${cite.documentId}-${i}`}
                className="inline-flex items-center text-[10px] bg-primary/10 text-primary rounded-md px-2 py-0.5"
                title={cite.snippet}
              >
                {cite.documentTitle}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Grouped card for multiple identical tool calls (e.g., 3x add_document_to_project).
 * Shows a summary with count, expandable to see individual results.
 */
function ToolExecutionGroupCard({
  executions,
}: {
  executions: ToolExecution[];
}) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const allCompleted = executions.every((e) => e.status === 'completed');
  const anyFailed = executions.some((e) => e.status === 'failed');
  const totalMs = executions.reduce((sum, e) => sum + (e.durationMs ?? 0), 0);

  // Icons imported at top of file

  return (
    <div className="border border-border/50 rounded-lg bg-muted/20 text-xs my-2 overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 w-full px-3 py-2 text-left hover:bg-muted/40 transition-colors"
        aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${executions.length} ${executions[0].toolDisplayName} executions`}
      >
        {anyFailed ? (
          <XCircle className="h-3.5 w-3.5 text-destructive shrink-0" />
        ) : allCompleted ? (
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
        ) : null}
        <span className="text-foreground font-medium">
          {executions[0].toolDisplayName}
        </span>
        <span className="text-muted-foreground bg-muted rounded-full px-1.5 py-0 text-[10px]">
          {executions.length}x
        </span>
        <span className="ml-auto flex items-center gap-2 shrink-0">
          {totalMs > 0 && (
            <span className="text-muted-foreground/70 tabular-nums text-[10px]">
              {totalMs < 1000
                ? `${totalMs}ms`
                : `${(totalMs / 1000).toFixed(1)}s`}
            </span>
          )}
          {isExpanded ? (
            <ChevronDown className="h-3 w-3 text-muted-foreground/60" />
          ) : (
            <ChevronRight className="h-3 w-3 text-muted-foreground/60" />
          )}
        </span>
      </button>

      {/* Collapsed: show summary messages */}
      {!isExpanded && (
        <div className="px-3 pb-2 space-y-0.5 text-muted-foreground">
          {executions.map((exec) => {
            const msg =
              typeof exec.result === 'object' &&
              exec.result &&
              'message' in (exec.result as Record<string, unknown>)
                ? (exec.result as Record<string, unknown>).message
                : null;
            return msg ? (
              <div key={exec.id} className="truncate">
                {String(msg)}
              </div>
            ) : null;
          })}
        </div>
      )}

      {/* Expanded: individual cards */}
      {isExpanded && (
        <div className="border-t border-border/30 px-2 py-2 space-y-1">
          {executions.map((exec) => (
            <ToolExecutionCard key={exec.id} execution={exec} />
          ))}
        </div>
      )}
    </div>
  );
}
