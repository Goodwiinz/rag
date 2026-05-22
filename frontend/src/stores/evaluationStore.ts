import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import {
  Evaluation,
  EvaluationConfig,
  EvaluationResults,
  ComparisonData,
} from '@/types';
import { api } from '@/services/api-client';

interface EvaluationState {
  // Current evaluation
  currentEvaluation: Evaluation | null;
  evaluationConfig: EvaluationConfig | null;
  evaluationResults: EvaluationResults | null;

  // Evaluation list
  evaluations: Evaluation[];
  evaluationsLoading: boolean;
  evaluationsError: string | null;
  evaluationsPagination: {
    page: number;
    pageSize: number;
    total: number;
    hasNext: boolean;
    hasPrev: boolean;
  };

  // Comparison state
  selectedEvaluations: string[];
  comparisonData: ComparisonData | null;
  comparisonLoading: boolean;

  // Creation state
  isCreatingEvaluation: boolean;
  creationStep: number;
  creationErrors: Record<string, string>;

  // UI state
  activeTab: 'overview' | 'results' | 'comparison' | 'history';
  viewMode: 'grid' | 'table';
  sortBy: 'created_at' | 'name' | 'status' | 'score';
  sortOrder: 'asc' | 'desc';

  // Actions
  setCurrentEvaluation: (evaluation: Evaluation | null) => void;
  setEvaluationConfig: (config: EvaluationConfig | null) => void;
  setEvaluationResults: (results: EvaluationResults | null) => void;

  setEvaluations: (evaluations: Evaluation[]) => void;
  addEvaluation: (evaluation: Evaluation) => void;
  updateEvaluation: (id: string, updates: Partial<Evaluation>) => void;
  removeEvaluation: (id: string) => void;
  setEvaluationsLoading: (loading: boolean) => void;
  setEvaluationsError: (error: string | null) => void;
  setEvaluationsPagination: (
    pagination: Partial<EvaluationState['evaluationsPagination']>
  ) => void;

  setSelectedEvaluations: (ids: string[]) => void;
  toggleEvaluationSelection: (id: string) => void;
  setComparisonData: (data: ComparisonData | null) => void;
  setComparisonLoading: (loading: boolean) => void;

  setIsCreatingEvaluation: (creating: boolean) => void;
  setCreationStep: (step: number) => void;
  setCreationErrors: (errors: Record<string, string>) => void;
  clearCreationErrors: () => void;

  setActiveTab: (tab: EvaluationState['activeTab']) => void;
  setViewMode: (mode: EvaluationState['viewMode']) => void;
  setSortBy: (sortBy: EvaluationState['sortBy']) => void;
  setSortOrder: (order: EvaluationState['sortOrder']) => void;

  // Complex actions
  createEvaluation: (config: EvaluationConfig) => Promise<void>;
  runEvaluation: (id: string) => Promise<void>;
  compareEvaluations: (evaluationIds: string[]) => Promise<void>;
  exportResults: (format: 'json' | 'csv' | 'pdf') => Promise<void>;
}

export const useEvaluationStore = create<EvaluationState>()(
  devtools(
    (set, get) => ({
      // Initial state
      currentEvaluation: null,
      evaluationConfig: null,
      evaluationResults: null,

      evaluations: [],
      evaluationsLoading: false,
      evaluationsError: null,
      evaluationsPagination: {
        page: 1,
        pageSize: 20,
        total: 0,
        hasNext: false,
        hasPrev: false,
      },

      selectedEvaluations: [],
      comparisonData: null,
      comparisonLoading: false,

      isCreatingEvaluation: false,
      creationStep: 1,
      creationErrors: {},

      activeTab: 'overview',
      viewMode: 'grid',
      sortBy: 'created_at',
      sortOrder: 'desc',

      // Actions
      setCurrentEvaluation: (evaluation) =>
        set({ currentEvaluation: evaluation }),

      setEvaluationConfig: (config) => set({ evaluationConfig: config }),

      setEvaluationResults: (results) => set({ evaluationResults: results }),

      setEvaluations: (evaluations) => set({ evaluations }),

      addEvaluation: (evaluation) => {
        const { evaluations } = get();
        set({ evaluations: [evaluation, ...evaluations] });
      },

      updateEvaluation: (id, updates) => {
        const { evaluations } = get();
        set({
          evaluations: evaluations.map((evaluation) =>
            evaluation.id === id ? { ...evaluation, ...updates } : evaluation
          ),
        });
      },

      removeEvaluation: (id) => {
        const { evaluations } = get();
        set({
          evaluations: evaluations.filter((evaluation) => evaluation.id !== id),
        });
      },

      setEvaluationsLoading: (loading) => set({ evaluationsLoading: loading }),

      setEvaluationsError: (error) => set({ evaluationsError: error }),

      setEvaluationsPagination: (pagination) => {
        const currentPagination = get().evaluationsPagination;
        set({
          evaluationsPagination: { ...currentPagination, ...pagination },
        });
      },

      setSelectedEvaluations: (ids) => set({ selectedEvaluations: ids }),

      toggleEvaluationSelection: (id) => {
        const { selectedEvaluations } = get();
        if (selectedEvaluations.includes(id)) {
          set({
            selectedEvaluations: selectedEvaluations.filter(
              (eid) => eid !== id
            ),
          });
        } else {
          set({ selectedEvaluations: [...selectedEvaluations, id] });
        }
      },

      setComparisonData: (data) => set({ comparisonData: data }),

      setComparisonLoading: (loading) => set({ comparisonLoading: loading }),

      setIsCreatingEvaluation: (creating) =>
        set({ isCreatingEvaluation: creating }),

      setCreationStep: (step) => set({ creationStep: step }),

      setCreationErrors: (errors) => set({ creationErrors: errors }),

      clearCreationErrors: () => set({ creationErrors: {} }),

      setActiveTab: (tab) => set({ activeTab: tab }),

      setViewMode: (mode) => set({ viewMode: mode }),

      setSortBy: (sortBy) => set({ sortBy }),

      setSortOrder: (order) => set({ sortOrder: order }),

      // Complex actions
      createEvaluation: async (config) => {
        set({ isCreatingEvaluation: true, creationErrors: {} });

        try {
          const evaluation = await api.post<Evaluation>('/evaluations', config);
          get().addEvaluation(evaluation);
          set({ currentEvaluation: evaluation, isCreatingEvaluation: false });
        } catch (error) {
          set({
            creationErrors: {
              general:
                error instanceof Error
                  ? error.message
                  : 'Failed to create evaluation',
            },
            isCreatingEvaluation: false,
          });
        }
      },

      runEvaluation: async (id) => {
        try {
          await api.post(`/evaluations/${id}/run`);
          get().updateEvaluation(id, { status: 'running' });
        } catch (error) {
          console.error('Failed to run evaluation:', error);
        }
      },

      compareEvaluations: async (evaluationIds) => {
        set({ comparisonLoading: true });

        try {
          const comparisonData = await api.post<ComparisonData>(
            '/evaluations/compare',
            { evaluationIds }
          );
          set({ comparisonData, comparisonLoading: false });
        } catch (error) {
          set({
            comparisonLoading: false,
            comparisonData: null,
          });
          console.error('Failed to compare evaluations:', error);
        }
      },

      exportResults: async (format) => {
        const { currentEvaluation } = get();
        if (!currentEvaluation) return;

        try {
          const blob = await api.request<Blob>(
            `/evaluations/${currentEvaluation.id}/export?format=${format}`,
            { method: 'GET' }
          );
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `evaluation-${currentEvaluation.id}.${format}`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          document.body.removeChild(a);
        } catch (error) {
          console.error('Failed to export results:', error);
        }
      },
    }),
    {
      name: 'evaluation-store',
    }
  )
);

// Selector hooks
export const useCurrentEvaluation = () =>
  useEvaluationStore((state) => state.currentEvaluation);
export const useEvaluationConfig = () =>
  useEvaluationStore((state) => state.evaluationConfig);
export const useEvaluationResults = () =>
  useEvaluationStore((state) => state.evaluationResults);
export const useEvaluationsList = () =>
  useEvaluationStore((state) => state.evaluations);
export const useSelectedEvaluations = () =>
  useEvaluationStore((state) => state.selectedEvaluations);
export const useComparisonData = () =>
  useEvaluationStore((state) => state.comparisonData);
export const useCreationState = () =>
  useEvaluationStore((state) => ({
    isCreating: state.isCreatingEvaluation,
    step: state.creationStep,
    errors: state.creationErrors,
  }));
