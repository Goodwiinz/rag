import { create } from 'zustand';
import { toolLabel } from '@/components/context-rail/toolLabels';

export type StepStatus = 'active' | 'done' | 'error';

export interface Step {
  id: string;
  tool: string;
  label: string;
  status: StepStatus;
  at: number;
}

/**
 * High-level task item from the LangGraph planner_node. Rendered Cowork-style
 * in the Progress card (check-circle + strikethrough when done). Derived from
 * the `plan` SSE event emitted by the backend.
 */
export interface PlanItem {
  id: string;
  text: string;
  done: boolean;
}

export interface Run {
  threadId: string;
  name: string;
  task: string;
  steps: Step[];
  plan: PlanItem[];
  state: 'running' | 'done' | 'error';
  startedAt: number;
}

interface AgentActivityState {
  runs: Record<string, Run>;
  currentThreadId: string | null;
  startRun: (threadId: string, name: string, task: string) => void;
  pushToolStart: (threadId: string, tool: string) => void;
  pushToolEnd: (threadId: string, tool: string, ok: boolean) => void;
  setPlan: (threadId: string, items: string[]) => void;
  finishRun: (threadId: string, state: 'done' | 'error') => void;
}

// Eviction constants — cap unbounded growth of runs and steps
const MAX_RUNS = 20;
const MAX_STEPS_PER_RUN = 50;

let seq = 0;
const nextId = () => `step-${Date.now()}-${++seq}`;

export const useAgentActivityStore = create<AgentActivityState>((set) => ({
  runs: {},
  currentThreadId: null,

  startRun: (threadId, name, task) =>
    set((s) => {
      const newRuns = {
        ...s.runs,
        [threadId]: {
          threadId,
          name,
          task,
          steps: [],
          plan: [],
          state: 'running' as const,
          startedAt: Date.now(),
        },
      };

      // Evict oldest runs when exceeding the cap
      const keys = Object.keys(newRuns);
      if (keys.length > MAX_RUNS) {
        const sorted = keys.sort(
          (a, b) => (newRuns[a].startedAt ?? 0) - (newRuns[b].startedAt ?? 0)
        );
        const toEvict = sorted.slice(0, keys.length - MAX_RUNS);
        for (const key of toEvict) {
          delete newRuns[key];
        }
      }

      return { currentThreadId: threadId, runs: newRuns };
    }),

  pushToolStart: (threadId, tool) =>
    set((s) => {
      const run = s.runs[threadId];
      // Return the existing state reference so Zustand's Object.is check
      // short-circuits and no subscribers are notified for this no-op.
      if (!run) return s;
      const existing = run.steps.find(
        (st) => st.tool === tool && st.status === 'active'
      );
      if (existing) return s;
      const step: Step = {
        id: nextId(),
        tool,
        label: toolLabel(tool),
        status: 'active',
        at: Date.now(),
      };
      // Cap steps per run — keep the newest steps
      let steps = [...run.steps, step];
      if (steps.length > MAX_STEPS_PER_RUN) {
        steps = steps.slice(steps.length - MAX_STEPS_PER_RUN);
      }
      return {
        runs: {
          ...s.runs,
          [threadId]: { ...run, steps },
        },
      };
    }),

  pushToolEnd: (threadId, tool, ok) =>
    set((s) => {
      const run = s.runs[threadId];
      if (!run) return s;
      const idx = run.steps.findIndex(
        (st) => st.tool === tool && st.status === 'active'
      );
      if (idx < 0) return s;
      const next = [...run.steps];
      next[idx] = { ...next[idx], status: ok ? 'done' : 'error' };
      return {
        runs: { ...s.runs, [threadId]: { ...run, steps: next } },
      };
    }),

  setPlan: (threadId, items) =>
    set((s) => {
      const run = s.runs[threadId];
      if (!run) return s;
      // Only set once — avoid clobbering existing plan with later re-emits.
      if (run.plan.length > 0) return s;
      const plan: PlanItem[] = items.map((text, i) => ({
        id: `plan-${Date.now()}-${i}`,
        text,
        done: false,
      }));
      return { runs: { ...s.runs, [threadId]: { ...run, plan } } };
    }),

  finishRun: (threadId, state) =>
    set((s) => {
      const run = s.runs[threadId];
      if (!run) return s;
      // On successful completion, mark every plan item as done — matches
      // Cowork's "all checked" end state (we don't have fine-grained plan
      // step tracking yet, so this binary mapping is the honest default).
      const plan =
        state === 'done' && run.plan.length > 0
          ? run.plan.map((p) => ({ ...p, done: true }))
          : run.plan;
      return {
        currentThreadId:
          s.currentThreadId === threadId ? null : s.currentThreadId,
        runs: { ...s.runs, [threadId]: { ...run, state, plan } },
      };
    }),
}));
