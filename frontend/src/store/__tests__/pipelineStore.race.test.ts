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
}));

import { usePipelineStore } from '@/store/pipelineStore';
import * as scispaceService from '@/services/scispaceService';
import type { PipelineState } from '@/types/scispace';

const getPipelineMock = scispaceService.getPipeline as ReturnType<typeof vi.fn>;

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

    const err = vi.spyOn(console, 'error').mockImplementation(() => {});
    a.reject(new Error('network down'));
    await act(async () => {
      await fetchA;
    });
    err.mockRestore();

    expect(usePipelineStore.getState().error).toBeNull();
    expect(usePipelineStore.getState().pipeline?.project_id).toBe('proj-b');
  });
});
