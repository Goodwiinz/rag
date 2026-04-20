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

export interface Run {
  threadId: string;
  name: string;
  task: string;
  steps: Step[];
  state: 'running' | 'done' | 'error';
  startedAt: number;
}

interface AgentActivityState {
  runs: Record<string, Run>;
  currentThreadId: string | null;
  startRun: (threadId: string, name: string, task: string) => void;
  pushToolStart: (threadId: string, tool: string) => void;
  pushToolEnd: (threadId: string, tool: string, ok: boolean) => void;
  finishRun: (threadId: string, state: 'done' | 'error') => void;
}

let seq = 0;
const nextId = () => `step-${Date.now()}-${++seq}`;

export const useAgentActivityStore = create<AgentActivityState>((set) => ({
  runs: {},
  currentThreadId: null,

  startRun: (threadId, name, task) =>
    set((s) => ({
      currentThreadId: threadId,
      runs: {
        ...s.runs,
        [threadId]: {
          threadId,
          name,
          task,
          steps: [],
          state: 'running',
          startedAt: Date.now(),
        },
      },
    })),

  pushToolStart: (threadId, tool) =>
    set((s) => {
      const run = s.runs[threadId];
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
      return {
        runs: {
          ...s.runs,
          [threadId]: { ...run, steps: [...run.steps, step] },
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

  finishRun: (threadId, state) =>
    set((s) => {
      const run = s.runs[threadId];
      if (!run) return s;
      return {
        runs: { ...s.runs, [threadId]: { ...run, state } },
      };
    }),
}));
