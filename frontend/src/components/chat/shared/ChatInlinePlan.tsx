'use client';

import React, { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, ListChecks } from 'lucide-react';
import Plan, { type Task } from '@/components/ui/agent-plan';
import { mapPlanToTasks } from '@/components/agent-chat/planMapping';
import type { PlanStep, ToolExecution } from '@/types/agent-chat';
import type { ActivityStep } from '@/components/chat/shared/cloudMessageView';

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
 * Collapsible, read-only execution plan for a committed /chat message.
 * Mirrors agent-chat's InlinePlan: collapsed by default in the transcript
 * (the ContextRail shows the live plan while streaming), expandable for
 * provenance after the fact.
 */
export function ChatInlinePlan({
  plan,
  toolExecutions,
}: {
  plan: PlanStep[];
  toolExecutions?: ActivityStep[];
}): React.JSX.Element {
  const [isExpanded, setIsExpanded] = useState(false);

  const tasks = useMemo<Task[]>(
    () => mapPlanToTasks(plan, toToolExecutions(toolExecutions ?? [])),
    [plan, toolExecutions]
  );
  const doneCount = tasks.filter((t) => t.status === 'completed').length;

  return (
    <div className="border border-[var(--nous-border-1)] rounded-[var(--nous-radius-md)] bg-[var(--nous-bg-2)] my-2 overflow-hidden">
      <button
        type="button"
        onClick={() => setIsExpanded((v) => !v)}
        aria-label={`${isExpanded ? 'Collapse' : 'Expand'} execution plan`}
        className="flex items-center gap-2 w-full px-3 py-2 text-left transition-colors hover:bg-[var(--nous-bg-3)]"
      >
        <ListChecks className="h-3.5 w-3.5 shrink-0 text-[var(--nous-sol)]" />
        <span className="text-xs font-medium text-[var(--nous-fg-1)] font-nous-ui">
          Execution plan
        </span>
        <span className="ml-auto flex items-center gap-2 shrink-0">
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
          <Plan tasks={tasks} readOnly />
        </div>
      )}
    </div>
  );
}

export default ChatInlinePlan;
