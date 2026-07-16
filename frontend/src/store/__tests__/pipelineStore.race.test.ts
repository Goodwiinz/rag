/**
 * Pipeline Store race-guard tests (RS-B1)
 *
 * `fetchPipeline` writes into a SINGLE `pipeline` slot with zero request
 * identity. Switching project A -> B while A's fetch is still in flight lets
 * A's payload land last and show A's pipeline under B. A superseded
 * request's failure must also not clobber the store-global `error`.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from '@testing-library/react';

vi.mock('@/services/scispaceService', () => ({
  getPipeline: vi.fn(),
  updatePipeline: vi.fn(),
  resetPipeline: vi.fn(),
}));

import { usePipelineStore } from '@/store/pipelineStore';
import * as scispaceService from '@/services/scispaceService';
import type { PipelineState } from '@/types/scispace';

const getPipelineMock = scispaceService.getPipeline as ReturnType<typeof vi.fn>;
const updatePipelineMock = scispaceService.updatePipeline as ReturnType<
  typeof vi.fn
>;
const resetPipelineMock = scispaceService.resetPipeline as ReturnType<
  typeof vi.fn
>;

const makePipeline = (projectId: string): PipelineState => ({
  id: `pipeline-${projectId}`,
  project_id: projectId,
  current_step: 0,
  completed_steps: [],
  skipped_steps: [],
  step_data: {},
  invalidated_steps: [],
  created_at: null,
  updated_at: null,
});

const deferred = <T,>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
} => {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

describe('pipelineStore fetchPipeline race guard', () => {
  beforeEach(() => {
    act(() => {
      usePipelineStore.setState({ pipeline: null, loading: false, error: null });
    });
    getPipelineMock.mockReset();
  });

  it('drops a superseded fetch for a different project', async () => {
    const a = deferred<PipelineState>();
    const b = deferred<PipelineState>();
    getPipelineMock.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);

    const fetchA = usePipelineStore.getState().fetchPipeline('proj-a');
    const fetchB = usePipelineStore.getState().fetchPipeline('proj-b');

    b.resolve(makePipeline('proj-b'));
    await act(async () => {
      await fetchB;
    });

    a.resolve(makePipeline('proj-a'));
    await act(async () => {
      await fetchA;
    });

    expect(usePipelineStore.getState().pipeline?.project_id).toBe('proj-b');
    expect(usePipelineStore.getState().loading).toBe(false);
  });

  it('a superseded failure does not set the global error', async () => {
    const a = deferred<PipelineState>();
    const b = deferred<PipelineState>();
    getPipelineMock.mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);

    const fetchA = usePipelineStore.getState().fetchPipeline('proj-a');
    const fetchB = usePipelineStore.getState().fetchPipeline('proj-b');

    b.resolve(makePipeline('proj-b'));
    await act(async () => {
      await fetchB;
    });

    a.reject(new Error('network down'));
    await act(async () => {
      await fetchA;
    });

    expect(usePipelineStore.getState().error).toBeNull();
    expect(usePipelineStore.getState().pipeline?.project_id).toBe('proj-b');
  });
});

describe('pipelineStore mutation race guards', () => {
  beforeEach(() => {
    act(() => {
      usePipelineStore.setState({ pipeline: null, loading: false, error: null });
    });
    getPipelineMock.mockReset();
    updatePipelineMock.mockReset();
    resetPipelineMock.mockReset();
  });

  it('a mutation settling after a cross-project fetch does not overwrite the newer pipeline', async () => {
    // Seed the store with proj-a's pipeline via a resolved fetch.
    getPipelineMock.mockResolvedValueOnce(makePipeline('proj-a'));
    await act(async () => {
      await usePipelineStore.getState().fetchPipeline('proj-a');
    });

    // Start a mutation for proj-a that stays in flight.
    const mutation = deferred<PipelineState>();
    updatePipelineMock.mockReturnValueOnce(mutation.promise);
    const advancePromise = usePipelineStore.getState().advanceStep('proj-a');

    // A newer fetch for proj-b lands and resolves before the mutation does.
    const fetchB = deferred<PipelineState>();
    getPipelineMock.mockReturnValueOnce(fetchB.promise);
    const fetchBPromise = usePipelineStore.getState().fetchPipeline('proj-b');
    fetchB.resolve(makePipeline('proj-b'));
    await act(async () => {
      await fetchBPromise;
    });

    // The stale proj-a mutation resolves after proj-b is already current.
    mutation.resolve(makePipeline('proj-a'));
    await act(async () => {
      await advancePromise;
    });

    expect(usePipelineStore.getState().pipeline?.project_id).toBe('proj-b');
    expect(usePipelineStore.getState().error).toBeNull();
  });

  it('resetPipeline participates in the token scheme', async () => {
    getPipelineMock.mockResolvedValueOnce(makePipeline('proj-a'));
    await act(async () => {
      await usePipelineStore.getState().fetchPipeline('proj-a');
    });

    // Start a reset for proj-a that stays in flight.
    const reset = deferred<PipelineState>();
    resetPipelineMock.mockReturnValueOnce(reset.promise);
    const resetPromise = usePipelineStore.getState().resetPipeline('proj-a');

    // A newer fetch for proj-b lands and resolves before the reset does.
    const fetchB = deferred<PipelineState>();
    getPipelineMock.mockReturnValueOnce(fetchB.promise);
    const fetchBPromise = usePipelineStore.getState().fetchPipeline('proj-b');
    fetchB.resolve(makePipeline('proj-b'));
    await act(async () => {
      await fetchBPromise;
    });

    // The stale proj-a reset resolves after proj-b is already current.
    reset.resolve(makePipeline('proj-a'));
    await act(async () => {
      await resetPromise;
    });

    expect(usePipelineStore.getState().pipeline?.project_id).toBe('proj-b');
    expect(usePipelineStore.getState().loading).toBe(false);
  });
});
