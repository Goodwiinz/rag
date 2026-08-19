/**
 * Round-3 L4: a stream that outlives its thread's deletion runs terminal
 * reconciliation (refreshMessages) when it commits, which used to re-create
 * the deleted thread's message cache, pagination, freshness and reverse-index
 * entries.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    deleteThread: vi.fn().mockResolvedValue(undefined),
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

const makeMessage = (id: string, threadId: string): ChatMessage => ({
  id,
  thread_id: threadId,
  content: `message ${id}`,
  role: MessageRole.USER,
  token_count: 0,
  citations: [],
  attachments: [],
  client_message_id: null,
  created_at: '2026-08-18T00:00:01Z',
  updated_at: '2026-08-18T00:00:01Z',
});

const response = (messages: ChatMessage[]): ChatMessageListResponse => ({
  messages,
  total: messages.length,
  page: 1,
  limit: 50,
  has_more: false,
});

describe('deleted-thread request guard', () => {
  beforeEach(() => {
    useChatStore.getState().reset();
    vi.clearAllMocks();
    vi.mocked(workspaceService.listMessages).mockResolvedValue(
      response([makeMessage('m1', 'thread-A')])
    );
  });

  it('refuses to reconcile into a deleted thread (L4)', async () => {
    await useChatStore.getState().deleteThread('thread-A');

    const committed = await useChatStore.getState().refreshMessages('thread-A');

    expect(committed).toBe(false);
    expect(vi.mocked(workspaceService.listMessages)).not.toHaveBeenCalled();
    expect(useChatStore.getState().messages['thread-A']).toBeUndefined();
    expect(
      useChatStore.getState().messageFreshness['thread-A']
    ).toBeUndefined();
  });

  it('still reconciles a live thread', async () => {
    const committed = await useChatStore.getState().refreshMessages('thread-A');

    expect(committed).toBe(true);
    expect(useChatStore.getState().messages['thread-A']).toHaveLength(1);
  });
});
