import { beforeEach, describe, expect, it, vi } from 'vitest';
import React from 'react';
import { render } from '@/test/test-utils';
import { ResearchPipeline } from '../ResearchPipeline';
import { usePipelineStore } from '@/store/pipelineStore';

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

const fetchPipeline = vi.fn();

beforeEach(() => {
  vi.clearAllMocks();
  (usePipelineStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
    pipeline: null,
    loading: true,
    error: null,
    fetchPipeline,
    advanceStep: vi.fn(),
    skipStep: vi.fn(),
    goToStep: vi.fn(),
    resetPipeline: vi.fn(),
    clearError: vi.fn(),
  });
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
