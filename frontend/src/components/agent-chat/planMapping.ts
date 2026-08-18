import type { Task } from '@/components/ui/agent-plan';
import type { PlanStep, ToolExecution } from '@/types/agent-chat';

/**
 * Maps a planner step's `tool` against the current turn's tool executions to a
 * display status in the agent-plan component's status vocabulary
 * ('pending' | 'in-progress' | 'completed' | 'failed').
 */
export function deriveStepStatus(
  step: PlanStep,
  toolExecutions: ToolExecution[],
  occurrence = 0,
  occurrencesForTool = 1
): string {
  const matching = toolExecutions.filter((te) => te.toolName === step.tool);
  // A plan can name the same tool in several steps (2x search_documents is
  // common); correlate positionally so one execution can't complete every
  // such step. The last step using a tool absorbs the remaining executions,
  // which keeps retries of a single-step tool aggregating as before.
  const isLastForTool = occurrence === occurrencesForTool - 1;
  const window = isLastForTool
    ? matching.slice(occurrence)
    : matching.slice(occurrence, occurrence + 1);
  if (window.length === 0) return 'pending';
  if (window.some((te) => te.status === 'failed')) return 'failed';
  if (window.some((te) => te.status === 'running')) return 'in-progress';
  if (window.some((te) => te.status === 'completed')) return 'completed';
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
  const totalPerTool = new Map<string, number>();
  for (const step of steps) {
    totalPerTool.set(step.tool, (totalPerTool.get(step.tool) ?? 0) + 1);
  }
  const seenPerTool = new Map<string, number>();
  return steps.map((step) => {
    const occurrence = seenPerTool.get(step.tool) ?? 0;
    seenPerTool.set(step.tool, occurrence + 1);
    return {
      id: String(step.step),
      title: step.description,
      description: formatArgsHint(step.args_hint),
      status: deriveStepStatus(
        step,
        toolExecutions,
        occurrence,
        totalPerTool.get(step.tool) ?? 1
      ),
      priority: '',
      level: 0,
      dependencies: (step.depends_on ?? []).map(String),
      subtasks: [],
      tools: step.tool ? [step.tool] : [],
    };
  });
}
