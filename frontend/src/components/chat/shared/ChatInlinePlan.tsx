'use client';

import React, { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, ListChecks } from 'lucide-react';
import Plan, { type Task } from '@/components/ui/agent-plan';
import { mapPlanToTasks } from '@/components/agent-chat/planMapping';
import type { PlanStep, ToolExecution } from '@/types/agent-chat';
import type { ActivityStep } from '@/components/chat/shared/cloudMessageView';
import {
  formatTurnDuration,
  formatTurnSplit,
} from '@/components/chat/shared/formatStreamingElapsed';

/**
 * Adapt the chat page's ActivityStep records onto the agent-chat
 * ToolExecution shape that planMapping.deriveStepStatus expects, so plan
 * items reflect what the tools actually did this turn.
 */
function toToolExecutions(steps: ActivityStep[]): ToolExecution[] {
  return steps.map((s, i) => ({
    id: `step-${i}`,
    toolName: s.tool,
    toolDisplayName: s.label,
    args: {},
    status:
      s.status === 'error'
        ? 'failed'
        : s.status === 'done'
          ? 'completed'
          : 'running',
  }));
}

/**
 * Collapsible execution plan for a /chat message. Renders the SAME component
 * for the live in-flight turn and the committed one — `streaming` picks the
 * only two things that differ: the disclosure's default open state (a live
 * turn mounts open so steps stream in visibly) and whether the header shows
 * a "took …" duration (only meaningful once the turn has actually finished).
 */
export const ChatInlinePlan = React.memo(function ChatInlinePlan({
  plan,
  reasoning,
  toolExecutions,
  streaming = false,
  elapsedMs,
  ttftMs,
}: {
  plan: PlanStep[];
  /** Planner's top-level rationale for `plan`, shown when expanded. */
  reasoning?: string;
  toolExecutions?: ActivityStep[];
  /** True for the live in-flight instance — mounts expanded instead of the
   * committed default (collapsed), so streamed-in steps are visible. */
  streaming?: boolean;
  /** Committed turn's total elapsed time (message.metadata.responseTimeMs).
   * Ignored while streaming — the turn hasn't finished yet. */
  elapsedMs?: number;
  /** Committed turn's time to first token (message.metadata.ttftMs). Splits
   * the header clock into the wait this plan accounts for and the time spent
   * writing the answer. Ignored while streaming, like `elapsedMs`. */
  ttftMs?: number;
}): React.JSX.Element {
  const [isExpanded, setIsExpanded] = useState(streaming);

  const tasks = useMemo<Task[]>(
    () => mapPlanToTasks(plan, toToolExecutions(toolExecutions ?? [])),
    [plan, toolExecutions]
  );
  const doneCount = tasks.filter((t) => t.status === 'completed').length;
  const elapsed = streaming
    ? null
    : formatTurnDuration(elapsedMs ?? null);
  // Whole seconds, matching `elapsed` above.
  const split = streaming
    ? { suffix: null, title: undefined }
    : formatTurnSplit(elapsedMs, ttftMs, (ms) => formatTurnDuration(ms));

  return (
    <div className="border border-[var(--nous-border-1)] rounded-[var(--nous-radius-md)] bg-[var(--nous-bg-2)] my-2 overflow-hidden">
      <button
        type="button"
        onClick={() => setIsExpanded((v) => !v)}
        aria-label="Toggle execution plan"
        aria-expanded={isExpanded}
        className="flex items-center gap-2 w-full px-3 py-2 text-left transition-colors hover:bg-[var(--nous-bg-3)]"
      >
        <ListChecks className="h-3.5 w-3.5 shrink-0 text-[var(--nous-sol)]" />
        <span className="text-xs font-medium text-[var(--nous-fg-1)] font-nous-ui">
          Execution plan
        </span>
        <span className="ml-auto flex items-center gap-2 shrink-0">
          {elapsed && (
            <span
              className="tabular-nums text-[10px] text-[var(--nous-fg-3)] font-nous-ui"
              title={split.title}
            >
              took {elapsed}
              {split.suffix ? ` · ${split.suffix}` : ''}
            </span>
          )}
          <span className="tabular-nums text-[10px] text-[var(--nous-fg-3)] font-nous-ui">
            {doneCount}/{tasks.length}
          </span>
          {isExpanded ? (
            <ChevronDown className="h-3 w-3 text-[var(--nous-fg-3)]" />
          ) : (
            <ChevronRight className="h-3 w-3 text-[var(--nous-fg-3)]" />
          )}
        </span>
      </button>
      {isExpanded && (
        <div className="border-t border-[var(--nous-border-1)] max-h-[320px] overflow-y-auto">
          {reasoning && (
            <p className="px-3 py-2 text-xs text-[var(--nous-fg-3)] font-nous-ui border-b border-[var(--nous-border-1)]">
              {reasoning}
            </p>
          )}
          <Plan tasks={tasks} readOnly />
        </div>
      )}
    </div>
  );
});

export default ChatInlinePlan;
