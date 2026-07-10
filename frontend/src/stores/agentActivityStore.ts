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
 *
 * `tool` carries the planner's tool hint for the step (absent for pure
 * reasoning/respond steps). Tool-bearing items are only marked done when the
 * matching tool actually completes successfully — never in bulk at stream
 * end — so the Progress card reflects what really ran, not just that the
 * stream closed.
 */
export interface PlanItem {
  id: string;
  text: string;
  tool?: string;
  done: boolean;
}

/** Input accepted by setPlan: plain text or text + planner tool hint. */
export type PlanItemInput = string | { text: string; tool?: string | null };

export interface Run {
  threadId: string;
  name: string;
  task: string;
  steps: Step[];
  plan: PlanItem[];
  state: 'running' | 'done' | 'error' | 'stopped';
  startedAt: number;
  /** Last SSE frame seq seen for this run — the resume cursor. */
  streamSeq?: number;
}

interface AgentActivityState {
  runs: Record<string, Run>;
  currentThreadId: string | null;
  startRun: (threadId: string, name: string, task: string) => void;
  pushToolStart: (threadId: string, tool: string) => void;
  pushToolEnd: (threadId: string, tool: string, ok: boolean) => void;
  setPlan: (threadId: string, items: PlanItemInput[]) => void;
  setStreamSeq: (threadId: string, seq: number) => void;
  finishRun: (threadId: string, state: 'done' | 'error' | 'stopped') => void;
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
      let steps = run.steps;
      if (idx >= 0) {
        steps = [...run.steps];
        steps[idx] = { ...steps[idx], status: ok ? 'done' : 'error' };
      }

      // A successful tool completion also completes the first pending plan
      // item that hints at this tool — this is the only path that marks
      // tool-bearing plan items done.
      let plan = run.plan;
      if (ok) {
        const planIdx = run.plan.findIndex((p) => !p.done && p.tool === tool);
        if (planIdx >= 0) {
          plan = [...run.plan];
          plan[planIdx] = { ...plan[planIdx], done: true };
        }
      }

      if (steps === run.steps && plan === run.plan) return s;
      return {
        runs: { ...s.runs, [threadId]: { ...run, steps, plan } },
      };
    }),

  setPlan: (threadId, items) =>
    set((s) => {
      const run = s.runs[threadId];
      if (!run) return s;
      // Only set once — avoid clobbering existing plan with later re-emits.
      if (run.plan.length > 0) return s;
      const plan: PlanItem[] = items.map((item, i) => {
        const text = typeof item === 'string' ? item : item.text;
        const rawTool = typeof item === 'string' ? undefined : item.tool;
        // Planner emits "N/A" for reasoning/respond steps with no tool.
        const tool =
          rawTool && rawTool.trim().toUpperCase() !== 'N/A'
            ? rawTool.trim()
            : undefined;
        return { id: `plan-${Date.now()}-${i}`, text, tool, done: false };
      });
      return { runs: { ...s.runs, [threadId]: { ...run, plan } } };
    }),

  setStreamSeq: (threadId, seq) =>
    set((s) => {
      const run = s.runs[threadId];
      if (!run || run.streamSeq === seq) return s;
      return { runs: { ...s.runs, [threadId]: { ...run, streamSeq: seq } } };
    }),

  finishRun: (threadId, state) =>
    set((s) => {
      const run = s.runs[threadId];
      if (!run) return s;
      // On successful completion, close out only the tool-less plan items
      // (reasoning/respond steps) — tool-bearing items are completed by
      // pushToolEnd when their tool actually succeeds. A run that never
      // executed its planned tools must not render as fully complete
      // (7-of-7 struck through while the answer says the extraction
      // failed). 'stopped' (user abort) and 'error' leave the plan as-is.
      const plan =
        state === 'done' && run.plan.length > 0
          ? run.plan.map((p) => (p.tool ? p : { ...p, done: true }))
          : run.plan;
      return {
        currentThreadId:
          s.currentThreadId === threadId ? null : s.currentThreadId,
        runs: { ...s.runs, [threadId]: { ...run, state, plan } },
      };
    }),
}));
