/**
 * Unit tests for useDocuments' deleteDocuments (batch delete).
 *
 * R4-M22: batch delete used to call deleteDocument() per id, each of which
 * awaits a full fetchDocuments() — N deletes meant N refetches, and a
 * mid-loop refetch racing the final delete's commit could repaint deleted
 * docs. deleteDocuments() must delete all ids first, then refetch exactly
 * once.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDocuments } from '../useDocuments';
import { APIErrorClass } from '@/types';

const mockGet = vi.fn();
const mockDelete = vi.fn();
const mockPost = vi.fn();

vi.mock('@/services/api-client', () => ({
  api: {
    get: (...args: unknown[]) => mockGet(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
}));

const mockHandleAuthError = vi.fn();

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    isLoading: false,
    handleAuthError: mockHandleAuthError,
  }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(console, 'log').mockImplementation();
  vi.spyOn(console, 'warn').mockImplementation();
  vi.spyOn(console, 'error').mockImplementation();
  mockGet.mockResolvedValue({
    documents: [],
    pagination: {
      page: 1,
      page_size: 20,
      total: 0,
      total_pages: 0,
      has_next: false,
      has_prev: false,
    },
  });
  mockDelete.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useDocuments.deleteDocuments', () => {
  it('deletes every id and refetches the list exactly once', async () => {
    const { result } = renderHook(() => useDocuments({ autoFetch: false }));

    mockGet.mockClear();

    await act(async () => {
      await result.current.deleteDocuments(['a', 'b', 'c']);
    });

    expect(mockDelete).toHaveBeenCalledTimes(3);
    expect(mockDelete).toHaveBeenCalledWith('/documents/a');
    expect(mockDelete).toHaveBeenCalledWith('/documents/b');
    expect(mockDelete).toHaveBeenCalledWith('/documents/c');
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it('reports progress as each id completes', async () => {
    const { result } = renderHook(() => useDocuments({ autoFetch: false }));
    const onProgress = vi.fn();

    await act(async () => {
      await result.current.deleteDocuments(['a', 'b'], onProgress);
    });

    expect(onProgress).toHaveBeenNthCalledWith(1, 1, 2);
    expect(onProgress).toHaveBeenNthCalledWith(2, 2, 2);
  });

  it('prunes all deleted ids from selection in one update', async () => {
    const { result } = renderHook(() => useDocuments({ autoFetch: false }));

    act(() => {
      result.current.selectDocument('a');
      result.current.selectDocument('b');
      result.current.selectDocument('c');
    });
    expect(result.current.selectedCount).toBe(3);

    await act(async () => {
      await result.current.deleteDocuments(['a', 'b']);
    });

    expect(result.current.selectedDocuments.has('a')).toBe(false);
    expect(result.current.selectedDocuments.has('b')).toBe(false);
    expect(result.current.selectedDocuments.has('c')).toBe(true);
  });

  it('continues past a failing delete, still refetches once, and reports the failure reason per title', async () => {
    mockDelete.mockImplementation((path: string) => {
      if (path === '/documents/b') {
        return Promise.reject(new Error('boom'));
      }
      return Promise.resolve(undefined);
    });

    const { result } = renderHook(() => useDocuments({ autoFetch: false }));
    mockGet.mockClear();

    let caught: unknown;
    await act(async () => {
      try {
        await result.current.deleteDocuments(['a', 'b', 'c']);
      } catch (error) {
        caught = error;
      }
    });

    expect(caught).toBeInstanceOf(Error);
    // The message names which id failed AND why (not just the id).
    expect((caught as Error).message).toMatch(/b: boom/);
    expect(mockDelete).toHaveBeenCalledTimes(3);
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it('stops the loop on a mid-batch auth failure, skips the rest, and calls handleAuthError once', async () => {
    mockDelete.mockImplementation((path: string) => {
      if (path === '/documents/b') {
        return Promise.reject(
          new APIErrorClass({
            message: 'Session expired',
            status_code: 401,
            type: 'auth_error',
          })
        );
      }
      return Promise.resolve(undefined);
    });

    const { result } = renderHook(() => useDocuments({ autoFetch: false }));
    mockGet.mockClear();

    let caught: unknown;
    await act(async () => {
      try {
        await result.current.deleteDocuments(['a', 'b', 'c']);
      } catch (error) {
        caught = error;
      }
    });

    // 'c' is never attempted once the auth failure on 'b' breaks the loop.
    expect(mockDelete).toHaveBeenCalledTimes(2);
    expect(mockDelete).toHaveBeenCalledWith('/documents/a');
    expect(mockDelete).toHaveBeenCalledWith('/documents/b');
    expect(mockHandleAuthError).toHaveBeenCalledTimes(1);

    // Still one refetch and one selection prune, covering the whole batch.
    expect(mockGet).toHaveBeenCalledTimes(1);

    expect(caught).toBeInstanceOf(Error);
    expect((caught as Error).message).toMatch(/c: skipped: session expired/);
  });
});
