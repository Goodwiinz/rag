import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { fireEvent, render, screen } from '@/test/test-utils';
import { ResearchPipeline } from '../ResearchPipeline';
import { usePipelineStore } from '@/store/pipelineStore';
import type { PipelineState } from '@/types/scispace';

vi.mock('@/store/pipelineStore', () => ({
  usePipelineStore: vi.fn(),
}));

vi.mock('@/store/projectStore', () => ({
  useProjectStore: vi.fn((selector) =>
    selector({
      projectDocuments: [],
      documentsLoading: false,
      removeDocument: vi.fn(),
    })
  ),
}));

vi.mock('../PipelineStepper', () => ({
  PipelineStepper: ({ onStepClick }: { onStepClick: (s: number) => void }) => (
    <button onClick={() => onStepClick(2)}>stepper</button>
  ),
}));
vi.mock('../steps/CollectStep', () => ({
  CollectStep: ({ onContinue }: { onContinue: () => void }) => (
    <button onClick={onContinue}>collect-step</button>
  ),
}));
vi.mock('../steps/ExtractStep', () => ({
  ExtractStep: () => <div>extract-step</div>,
}));
vi.mock('../steps/CiteStep', () => ({ CiteStep: () => <div>cite-step</div> }));
vi.mock('../steps/DraftStep', () => ({
  DraftStep: () => <div>draft-step</div>,
}));
vi.mock('../steps/ExportStep', () => ({
  ExportStep: () => <div>export-step</div>,
}));

const fetchPipeline = vi.fn();
const advanceStep = vi.fn();
const goToStep = vi.fn();
const resetPipeline = vi.fn();
const clearError = vi.fn();

function mockPipelineStore(
  overrides: Partial<{
    pipeline: Partial<PipelineState> | null;
    loading: boolean;
    error: string | null;
  }> = {}
): void {
  (usePipelineStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
    pipeline: null,
    loading: true,
    error: null,
    fetchPipeline,
    advanceStep,
    skipStep: vi.fn(),
    goToStep,
    resetPipeline,
    clearError,
    ...overrides,
  });
}

const basePipeline = {
  current_step: 0,
  completed_steps: [] as number[],
  skipped_steps: [] as number[],
  invalidated_steps: [] as number[],
};

beforeEach(() => {
  vi.clearAllMocks();
  mockPipelineStore();
});

describe('ResearchPipeline fetch-on-projectId-change', () => {
  it('fetches once on mount and dedupes re-renders for the same project', () => {
    const { rerender } = render(<ResearchPipeline projectId="proj-a" />);
    rerender(<ResearchPipeline projectId="proj-a" />);

    expect(fetchPipeline).toHaveBeenCalledTimes(1);
    expect(fetchPipeline).toHaveBeenCalledWith('proj-a');
  });

  it('refetches when the projectId prop changes on a reused instance', () => {
    const { rerender } = render(<ResearchPipeline projectId="proj-a" />);
    expect(fetchPipeline).toHaveBeenCalledWith('proj-a');

    rerender(<ResearchPipeline projectId="proj-b" />);

    expect(fetchPipeline).toHaveBeenCalledWith('proj-b');
    expect(fetchPipeline).toHaveBeenCalledTimes(2);
  });
});

describe('ResearchPipeline rendering', () => {
  it('shows error banner, reset button, and the active step; wires actions', () => {
    mockPipelineStore({
      pipeline: { ...basePipeline, completed_steps: [0] },
      loading: false,
      error: 'Pipeline fetch failed',
    });
    render(<ResearchPipeline projectId="proj-a" />);

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Pipeline fetch failed'
    );
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(clearError).toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'collect-step' }));
    expect(advanceStep).toHaveBeenCalledWith('proj-a');

    fireEvent.click(screen.getByRole('button', { name: 'stepper' }));
    expect(goToStep).toHaveBeenCalledWith('proj-a', 2);

    fireEvent.click(screen.getByRole('button', { name: /reset pipeline/i }));
    expect(resetPipeline).toHaveBeenCalledWith('proj-a');
  });

  it('renders a later step without error banner or reset button', () => {
    mockPipelineStore({
      pipeline: { ...basePipeline, current_step: 2 },
      loading: false,
    });
    render(<ResearchPipeline projectId="proj-a" />);

    expect(screen.getByText('cite-step')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /reset pipeline/i })
    ).not.toBeInTheDocument();
    expect(screen.queryByText('collect-step')).not.toBeInTheDocument();
  });
});
