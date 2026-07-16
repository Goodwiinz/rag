/**
 * Chat Store Pagination Tests (loadOlderMessages)
 *
 * Pins the newest-first older-message pagination contract:
 * - older messages are PREPENDED to the existing list (display order kept)
 * - overlapping ids are de-duplicated before prepend
 * - the hasMore guard short-circuits without an API call on the final page
 * - the loadingOlder flag always returns to false (success, guard, and error)
 * - a transport error surfaces state.error and clears loadingOlder
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from '@testing-library/react';
import { enableMapSet } from 'immer';

enableMapSet();

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    listMessages: vi.fn(),
  },
}));

import { useChatStore } from '@/store/chat-store';
import { workspaceService } from '@/services/workspaceService';
import {
  ChatMessage,
  ChatMessageListResponse,
  MessageRole,
} from '@/types/workspace';

const iso = new Date().toISOString();

const makeMessage = (id: string): ChatMessage => ({
  id,
  thread_id: 't1',
  content: `message ${id}`,
  role: MessageRole.USER,
  token_count: 0,
  citations: [],
  attachments: [],
  created_at: iso,
  updated_at: iso,
});

const makeResponse = (
  messages: ChatMessage[],
  has_more: boolean
): ChatMessageListResponse => ({
  messages,
  total: messages.length,
  page: 1,
  limit: 100,
  has_more,
});

const listMessagesMock = workspaceService.listMessages as ReturnType<
  typeof vi.fn
>;

const THREAD = 't1';

const seedThread = (
  ids: string[],
  pagination: { hasMore?: boolean; loadingOlder?: boolean } = {}
) => {
  const existing = ids.map(makeMessage);
  useChatStore.setState({
    messages: { [THREAD]: existing },
    messageToThread: Object.fromEntries(ids.map((id) => [id, THREAD])),
    messagePagination: {
      [THREAD]: {
        hasMore: pagination.hasMore ?? true,
        loadingOlder: pagination.loadingOlder ?? false,
        loadedCount: existing.length,
      },
    },
    error: null,
  });
};

describe('loadOlderMessages', () => {
  beforeEach(() => {
    act(() => {
      useChatStore.getState().reset();
    });
    listMessagesMock.mockReset();
  });

  it('requests strictly-older messages via before_id (newest-first) and prepends them', async () => {
    seedThread(['m3', 'm4', 'm5']);
    // order=desc → the server returns the older batch newest-first ([m2, m1]);
    // the store reverses it to ascending before prepending.
    listMessagesMock.mockResolvedValue(
      makeResponse([makeMessage('m2'), makeMessage('m1')], true)
    );

    await act(async () => {
      await useChatStore.getState().loadOlderMessages(THREAD);
    });

    // Cursor must be the OLDEST currently-loaded message (display index 0 = m3),
    // not an offset — offset against an asc list walks toward newer messages.
    expect(listMessagesMock).toHaveBeenCalledWith(THREAD, {
      limit: 100,
      order: 'desc',
      before_id: 'm3',
    });

    const ids = useChatStore.getState().messages[THREAD].map((m) => m.id);
    expect(ids).toEqual(['m1', 'm2', 'm3', 'm4', 'm5']);
    expect(useChatStore.getState().messagePagination[THREAD].loadingOlder).toBe(
      false
    );
    expect(useChatStore.getState().messagePagination[THREAD].loadedCount).toBe(
      5
    );
  });

  it('de-duplicates overlapping ids before prepending', async () => {
    seedThread(['m1', 'm2', 'm3']);
    // Server page (desc/newest-first) overlaps (m3, m2) and adds one genuinely
    // older message (m0): [m3, m2, m0] → reversed to [m0, m2, m3].
    listMessagesMock.mockResolvedValue(
      makeResponse(
        [makeMessage('m3'), makeMessage('m2'), makeMessage('m0')],
        false
      )
    );

    await act(async () => {
      await useChatStore.getState().loadOlderMessages(THREAD);
    });

    const ids = useChatStore.getState().messages[THREAD].map((m) => m.id);
    // No duplicates; only the genuinely-new m0 is prepended.
    expect(ids).toEqual(['m0', 'm1', 'm2', 'm3']);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('short-circuits with no API call when hasMore is false', async () => {
    seedThread(['m1'], { hasMore: false });

    await act(async () => {
      await useChatStore.getState().loadOlderMessages(THREAD);
    });

    expect(listMessagesMock).not.toHaveBeenCalled();
    expect(useChatStore.getState().messagePagination[THREAD].loadingOlder).toBe(
      false
    );
  });

  it('short-circuits when a load is already in flight', async () => {
    seedThread(['m1'], { loadingOlder: true });

    await act(async () => {
      await useChatStore.getState().loadOlderMessages(THREAD);
    });

    expect(listMessagesMock).not.toHaveBeenCalled();
  });

  it('sets error and clears loadingOlder when the request fails', async () => {
    seedThread(['m1', 'm2']);
    listMessagesMock.mockRejectedValue(new Error('network down'));
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});

    await act(async () => {
      await useChatStore.getState().loadOlderMessages(THREAD);
    });

    expect(useChatStore.getState().error).toBe('Failed to load older messages');
    expect(useChatStore.getState().messagePagination[THREAD].loadingOlder).toBe(
      false
    );
    err.mockRestore();
  });

  it('ignores a malformed payload without corrupting the list', async () => {
    seedThread(['m1', 'm2']);
    // Missing/invalid messages array.
    listMessagesMock.mockResolvedValue({
      total: 0,
      page: 1,
      limit: 100,
      has_more: true,
    } as unknown as ChatMessageListResponse);
    const err = vi.spyOn(console, 'error').mockImplementation(() => {});

    await act(async () => {
      await useChatStore.getState().loadOlderMessages(THREAD);
    });

    const ids = useChatStore.getState().messages[THREAD].map((m) => m.id);
    expect(ids).toEqual(['m1', 'm2']);
    expect(useChatStore.getState().messagePagination[THREAD].loadingOlder).toBe(
      false
    );
    err.mockRestore();
  });

  // Pins the commit-phase guard (PR #1205 triage, pre-existing bug): the old
  // code applied the older page unconditionally, resurrecting a cache that
  // was invalidated mid-flight or splicing a stale page into a rebuilt one.
  // These tests FAIL against the old behavior.
  describe('commit-phase guard against mid-flight invalidation', () => {
    it('drops the older page when the thread cache was invalidated while the request was in flight', async () => {
      seedThread(['m3']);
      let resolveOlder!: (response: ChatMessageListResponse) => void;
      listMessagesMock.mockReturnValueOnce(
        new Promise<ChatMessageListResponse>((resolve) => {
          resolveOlder = resolve;
        })
      );

      const load = useChatStore.getState().loadOlderMessages(THREAD);
      // Thread cache invalidated mid-flight (e.g. thread deleted / evicted)
      act(() => {
        useChatStore.getState().clearThread(THREAD);
      });
      resolveOlder(makeResponse([makeMessage('m2'), makeMessage('m1')], true));
      await act(async () => {
        await load;
      });

      // Old behavior resurrected the deleted cache as [m1, m2]
      expect(useChatStore.getState().messages[THREAD]).toBeUndefined();
      expect(useChatStore.getState().messagePagination[THREAD]).toBeUndefined();
      expect(useChatStore.getState().messageToThread.m1).toBeUndefined();
      expect(useChatStore.getState().messageToThread.m2).toBeUndefined();
    });

    it('drops a stale older page when the cache was rebuilt (fresh newest page) mid-flight', async () => {
      seedThread(['m3']);
      let resolveOlder!: (response: ChatMessageListResponse) => void;
      listMessagesMock.mockReturnValueOnce(
        new Promise<ChatMessageListResponse>((resolve) => {
          resolveOlder = resolve;
        })
      );

      const load = useChatStore.getState().loadOlderMessages(THREAD);
      // Invalidate + rebuild with a fresh newest page (loadingOlder resets
      // to false on a rebuilt cache) while the older-page request is in
      // flight — its cursor no longer matches this cache.
      act(() => {
        useChatStore.getState().clearThread(THREAD);
        seedThread(['m9']);
      });
      resolveOlder(makeResponse([makeMessage('m2'), makeMessage('m1')], true));
      await act(async () => {
        await load;
      });

      // Old behavior spliced the stale page in: ['m1', 'm2', 'm9']
      const ids = useChatStore.getState().messages[THREAD].map((m) => m.id);
      expect(ids).toEqual(['m9']);
      expect(
        useChatStore.getState().messagePagination[THREAD].loadingOlder
      ).toBe(false);
      expect(
        useChatStore.getState().messagePagination[THREAD].loadedCount
      ).toBe(1);
    });

    it('a superseded request that FAILS after the cache was rebuilt does not set the global error', async () => {
      seedThread(['m3']);
      let rejectOlder!: (reason: unknown) => void;
      listMessagesMock.mockReturnValueOnce(
        new Promise<ChatMessageListResponse>((_, reject) => {
          rejectOlder = reject;
        })
      );

      const load = useChatStore.getState().loadOlderMessages(THREAD);
      act(() => {
        useChatStore.getState().clearThread(THREAD);
        seedThread(['m9']);
      });
      const err = vi.spyOn(console, 'error').mockImplementation(() => {});
      rejectOlder(new Error('network down'));
      await act(async () => {
        await load;
      });
      err.mockRestore();

      // Old behavior surfaced a global error banner for a request the
      // current view no longer owns
      expect(useChatStore.getState().error).toBeNull();
      expect(
        useChatStore.getState().messages[THREAD].map((m) => m.id)
      ).toEqual(['m9']);
    });

    it('a superseded request neither commits nor clears the flag owned by the newer request', async () => {
      seedThread(['m3']);
      let resolveFirst!: (response: ChatMessageListResponse) => void;
      let resolveSecond!: (response: ChatMessageListResponse) => void;
      listMessagesMock
        .mockReturnValueOnce(
          new Promise<ChatMessageListResponse>((resolve) => {
            resolveFirst = resolve;
          })
        )
        .mockReturnValueOnce(
          new Promise<ChatMessageListResponse>((resolve) => {
            resolveSecond = resolve;
          })
        );

      const first = useChatStore.getState().loadOlderMessages(THREAD);
      // Invalidate + rebuild, then a NEWER older-page request starts against
      // the rebuilt cache while the first is still in flight.
      act(() => {
        useChatStore.getState().clearThread(THREAD);
        seedThread(['m9']);
      });
      const second = useChatStore.getState().loadOlderMessages(THREAD);

      resolveFirst(makeResponse([makeMessage('m2'), makeMessage('m1')], true));
      await act(async () => {
        await first;
      });

      // The stale page is dropped even though loadingOlder is true (it
      // belongs to the second request), and the first request's finally must
      // not clear the second request's flag.
      expect(
        useChatStore.getState().messages[THREAD].map((m) => m.id)
      ).toEqual(['m9']);
      expect(
        useChatStore.getState().messagePagination[THREAD].loadingOlder
      ).toBe(true);

      resolveSecond(makeResponse([makeMessage('m8')], false));
      await act(async () => {
        await second;
      });

      expect(
        useChatStore.getState().messages[THREAD].map((m) => m.id)
      ).toEqual(['m8', 'm9']);
      expect(
        useChatStore.getState().messagePagination[THREAD].loadingOlder
      ).toBe(false);
    });
  });
});

describe('loadMessages (newest-first initial load)', () => {
  beforeEach(() => {
    act(() => {
      useChatStore.getState().reset();
    });
    listMessagesMock.mockReset();
  });

  it('reuses a valid cached page when selecting a thread', () => {
    seedThread(['m1', 'm2', 'm3'], { hasMore: true });

    act(() => {
      useChatStore.getState().setCurrentThread(THREAD);
    });

    expect(useChatStore.getState().currentThreadId).toBe(THREAD);
    expect(listMessagesMock).not.toHaveBeenCalled();
    expect(useChatStore.getState().messagePagination[THREAD]).toEqual({
      hasMore: true,
      loadingOlder: false,
      loadedCount: 3,
    });
  });

  it('requests the newest page (order=desc) and stores it in ascending display order', async () => {
    // Server returns newest-first ([m5, m4, m3]); the store reverses to
    // ascending so the newest message renders at the bottom.
    listMessagesMock.mockResolvedValue(
      makeResponse(
        [makeMessage('m5'), makeMessage('m4'), makeMessage('m3')],
        true
      )
    );

    await act(async () => {
      await useChatStore.getState().loadMessages(THREAD);
    });

    expect(listMessagesMock).toHaveBeenCalledWith(THREAD, {
      limit: 50,
      order: 'desc',
      signal: expect.any(AbortSignal),
    });

    const ids = useChatStore.getState().messages[THREAD].map((m) => m.id);
    expect(ids).toEqual(['m3', 'm4', 'm5']);
    // has_more from a desc query means older messages remain.
    expect(useChatStore.getState().messagePagination[THREAD].hasMore).toBe(
      true
    );
  });

  it('allows independent thread loads to complete in either order', async () => {
    let resolveA!: (response: ChatMessageListResponse) => void;
    let resolveB!: (response: ChatMessageListResponse) => void;
    const responseA = new Promise<ChatMessageListResponse>((resolve) => {
      resolveA = resolve;
    });
    const responseB = new Promise<ChatMessageListResponse>((resolve) => {
      resolveB = resolve;
    });
    listMessagesMock
      .mockReturnValueOnce(responseA)
      .mockReturnValueOnce(responseB);

    const loadA = useChatStore.getState().loadMessages('thread-A');
    const loadB = useChatStore.getState().loadMessages('thread-B');

    resolveB(makeResponse([makeMessage('b1')], false));
    await loadB;
    resolveA(makeResponse([makeMessage('a1')], false));
    await loadA;

    expect(useChatStore.getState().messages['thread-B']).toHaveLength(1);
    expect(useChatStore.getState().messages['thread-A']).toHaveLength(1);
    expect(useChatStore.getState().isLoadingMessages).toBe(false);
  });

  it('tracks which thread the pending initial load belongs to', async () => {
    let resolveA!: (response: ChatMessageListResponse) => void;
    const responseA = new Promise<ChatMessageListResponse>((resolve) => {
      resolveA = resolve;
    });
    listMessagesMock.mockReturnValueOnce(responseA);

    const loadA = useChatStore.getState().loadMessages('thread-A');
    expect(useChatStore.getState().loadingThreadId).toBe('thread-A');
    expect(useChatStore.getState().isLoadingMessages).toBe(true);

    resolveA(makeResponse([makeMessage('a1')], false));
    await loadA;

    expect(useChatStore.getState().loadingThreadId).toBeNull();
    expect(useChatStore.getState().isLoadingMessages).toBe(false);
  });

  it('clears the loading state when the user opens a new chat mid-load (no stranded flag)', async () => {
    let resolveA!: (response: ChatMessageListResponse) => void;
    const responseA = new Promise<ChatMessageListResponse>((resolve) => {
      resolveA = resolve;
    });
    listMessagesMock.mockReturnValueOnce(responseA);

    const loadA = useChatStore.getState().loadMessages('thread-A');
    // "New chat" while thread-A's page is still in flight: the epoch bump
    // makes the in-flight response stale, so nothing else will ever clear
    // the loading flags — setCurrentThread(null) must clear them itself.
    useChatStore.getState().setCurrentThread(null);

    resolveA(makeResponse([makeMessage('a1')], false));
    await loadA;

    expect(useChatStore.getState().isLoadingMessages).toBe(false);
    expect(useChatStore.getState().loadingThreadId).toBeNull();
  });
});
