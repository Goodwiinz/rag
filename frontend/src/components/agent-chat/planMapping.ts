import type { Task } from '@/components/ui/agent-plan';
import type { PlanStep, ToolExecution } from '@/types/agent-chat';

/**
 * Maps a planner step's `tool` against the current turn's tool executions to a
 * display status in the agent-plan component's status vocabulary
 * ('pending' | 'in-progress' | 'completed' | 'failed').
 */
export function deriveStepStatus(
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
export function formatArgsHint(argsHint: Record<string, unknown>): string {
  if (!argsHint || typeof argsHint !== 'object') return '';
  const entries = Object.entries(argsHint);
  if (entries.length === 0) return '';
  return entries
    .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(' · ');
}

/** Flat 1:1 map: each planner step → one top-level task (no subtasks). */
export function mapPlanToTasks(
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
