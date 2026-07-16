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
});

describe('loadMessages (newest-first initial load)', () => {
  beforeEach(() => {
    act(() => {
      useChatStore.getState().reset();
    });
    listMessagesMock.mockReset();
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
      limit: 100,
      order: 'desc',
    });

    const ids = useChatStore.getState().messages[THREAD].map((m) => m.id);
    expect(ids).toEqual(['m3', 'm4', 'm5']);
    // has_more from a desc query means older messages remain.
    expect(useChatStore.getState().messagePagination[THREAD].hasMore).toBe(
      true
    );
  });
});
