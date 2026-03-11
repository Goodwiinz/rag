/**
 * Pipeline Store - Zustand state management for Research Pipeline wizard
 */

import { create } from 'zustand';
import type { PipelineState } from '@/types/scispace';
import { PIPELINE_STEPS } from '@/types/scispace';
import * as scispaceService from '@/services/scispaceService';

interface PipelineStore {
  pipeline: PipelineState | null;
  loading: boolean;
  error: string | null;

  fetchPipeline: (projectId: string) => Promise<void>;
  advanceStep: (projectId: string) => Promise<void>;
  skipStep: (projectId: string) => Promise<void>;
  goToStep: (projectId: string, step: number) => Promise<void>;
  updateStepData: (
    projectId: string,
    step: number,
    data: Record<string, unknown>
  ) => Promise<void>;
  resetPipeline: (projectId: string) => Promise<void>;
  clearError: () => void;
}

export const usePipelineStore = create<PipelineStore>((set, get) => ({
  pipeline: null,
  loading: false,
  error: null,

  fetchPipeline: async (projectId: string) => {
    set({ loading: true, error: null });
    try {
      const pipeline = await scispaceService.getPipeline(projectId);
      set({ pipeline, loading: false });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to load pipeline';
      set({ error: message, loading: false });
    }
  },

  advanceStep: async (projectId: string) => {
    const { pipeline } = get();
    if (!pipeline) return;

    const currentStep = pipeline.current_step;
    const nextStep = Math.min(currentStep + 1, PIPELINE_STEPS.length - 1);
    const completedSteps = [
      ...new Set([...pipeline.completed_steps, currentStep]),
    ];
    // Remove from invalidated if re-completing
    const invalidatedSteps = pipeline.invalidated_steps.filter(
      (s) => s !== currentStep
    );

    try {
      const updated = await scispaceService.updatePipeline(projectId, {
        current_step: nextStep,
        completed_steps: completedSteps,
        invalidated_steps: invalidatedSteps,
      });
      set({ pipeline: updated });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to advance step';
      set({ error: message });
    }
  },

  skipStep: async (projectId: string) => {
    const { pipeline } = get();
    if (!pipeline) return;

    const currentStep = pipeline.current_step;
    const stepDef = PIPELINE_STEPS[currentStep];
    if (!stepDef?.skippable) return;

    const nextStep = Math.min(currentStep + 1, PIPELINE_STEPS.length - 1);
    const skippedSteps = [...new Set([...pipeline.skipped_steps, currentStep])];

    try {
      const updated = await scispaceService.updatePipeline(projectId, {
        current_step: nextStep,
        skipped_steps: skippedSteps,
      });
      set({ pipeline: updated });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to skip step';
      set({ error: message });
    }
  },

  goToStep: async (projectId: string, step: number) => {
    const { pipeline } = get();
    if (!pipeline) return;

    try {
      const updated = await scispaceService.updatePipeline(projectId, {
        current_step: step,
      });
      set({ pipeline: updated });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to navigate to step';
      set({ error: message });
    }
  },

  updateStepData: async (
    projectId: string,
    step: number,
    data: Record<string, unknown>
  ) => {
    try {
      const updated = await scispaceService.updatePipeline(projectId, {
        step_data: { [String(step)]: data },
      });
      set({ pipeline: updated });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to update step data';
      set({ error: message });
    }
  },

  resetPipeline: async (projectId: string) => {
    set({ loading: true, error: null });
    try {
      const pipeline = await scispaceService.resetPipeline(projectId);
      set({ pipeline, loading: false });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Failed to reset pipeline';
      set({ error: message, loading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
