'use client';

import React, { useMemo } from 'react';
import { ListChecks } from 'lucide-react';
import Plan, { type Task } from '@/components/ui/agent-plan';
import { useAgentChatStore } from '@/store/agentChatStore';
import type { PlanStep, ToolExecution } from '@/types/agent-chat';

/**
 * Maps a planner step's `tool` against the current turn's tool executions to a
 * display status. Mirrors PlanCard.deriveStepStatus, extended with 'failed' and
 * mapped onto the agent-plan component's status vocabulary.
 */
function deriveStepStatus(
  step: PlanStep,
  toolExecutions: ToolExecution[]
): string {
  const matching = toolExecutions.filter((te) => te.toolName === step.tool);
  if (matching.length === 0) return 'pending';
  if (matching.some((te) => te.status === 'failed')) return 'failed';
  if (matching.some((te) => te.status === 'running')) return 'in-progress';
  if (matching.some((te) => te.status === 'completed')) return 'completed';
  return 'pending';
}

/** Renders the planner's `args_hint` as a compact single-line summary. */
function formatArgsHint(argsHint: Record<string, unknown>): string {
  if (!argsHint || typeof argsHint !== 'object') return '';
  const entries = Object.entries(argsHint);
  if (entries.length === 0) return '';
  return entries
    .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(' · ');
}

/** Flat 1:1 map: each planner step → one top-level task (no subtasks). */
function mapPlanToTasks(
  steps: PlanStep[],
  toolExecutions: ToolExecution[]
): Task[] {
  return steps.map((step) => ({
    id: String(step.step),
    title: step.description,
    description: formatArgsHint(step.args_hint),
    status: deriveStepStatus(step, toolExecutions),
    priority: '',
    level: 0,
    dependencies: (step.depends_on ?? []).map(String),
    subtasks: [],
    tools: step.tool ? [step.tool] : [],
  }));
}

/**
 * Live execution-plan side panel for the agent sidebar. Reads the current
 * plan + the latest assistant turn's tool executions from the store and renders
 * a read-only, auto-updating agent-plan. Collapses entirely when no plan is in
 * flight.
 */
export function AgentPlanPanel(): React.JSX.Element | null {
  const currentPlan = useAgentChatStore((s) => s.currentPlan);
  const messages = useAgentChatStore((s) => s.messages);

  const toolExecutions = useMemo<ToolExecution[]>(
    () => messages[messages.length - 1]?.toolExecutions ?? [],
    [messages]
  );

  const tasks = useMemo<Task[]>(
    () => (currentPlan ? mapPlanToTasks(currentPlan, toolExecutions) : []),
    [currentPlan, toolExecutions]
  );

  if (!currentPlan || currentPlan.length === 0) return null;

  const doneCount = tasks.filter((t) => t.status === 'completed').length;

  return (
    <aside className="w-[300px] shrink-0 border-l border-border flex flex-col overflow-hidden max-lg:hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border shrink-0">
        <ListChecks className="h-3.5 w-3.5 text-sol" />
        <span className="text-sm font-medium text-foreground">
          Execution plan
        </span>
        <span className="ml-auto text-[10px] tabular-nums text-muted-foreground/70">
          {doneCount}/{tasks.length}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto">
        <Plan tasks={tasks} readOnly />
      </div>
    </aside>
  );
}
