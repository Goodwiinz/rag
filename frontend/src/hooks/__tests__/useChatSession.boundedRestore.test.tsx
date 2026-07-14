import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ChatMessage, Thread } from '@/types/workspace';

const navigationMocks = vi.hoisted(() => ({
  push: vi.fn(),
  threadId: null as string | null,
  isNew: false,
}));

const workspaceMocks = vi.hoisted(() => ({
  getOrCreateDefaultWorkspace: vi.fn(),
  getOrCreateDefaultConversation: vi.fn(),
  createConversation: vi.fn(),
  listThreads: vi.fn(),
  listConversations: vi.fn(),
  getThread: vi.fn(),
}));

const chatStoreMocks = vi.hoisted(() => {
  const state = {
    currentThreadId: null as string | null,
    messages: {} as Record<string, ChatMessage[]>,
    addMessageToStore: vi.fn(),
    loadMessages: vi.fn(),
    loadOlderMessages: vi.fn(),
    loadingThreadId: null as string | null,
    error: null as string | null,
    messagePagination: {} as Record<
      string,
      { hasMore: boolean; loadingOlder: boolean; loadedCount: number }
    >,
    setCurrentThread: vi.fn(),
  };
  state.setCurrentThread.mockImplementation((threadId: string | null) => {
    state.currentThreadId = threadId;
  });
  const useStore = Object.assign(
    <T,>(selector: (store: typeof state) => T) => selector(state),
    {
      getState: () => state,
      setState: (partial: Partial<typeof state>) =>
        Object.assign(state, partial),
    }
  );
  return { state, useStore };
});

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: navigationMocks.push }),
  useSearchParams: () => ({
    get: (key: string) => {
      if (key === 'thread') return navigationMocks.threadId;
      if (key === 'new') return navigationMocks.isNew ? '1' : null;
      return null;
    },
  }),
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: workspaceMocks,
}));

vi.mock('@/store/chat-store', () => ({
  useChatStore: chatStoreMocks.useStore,
}));

vi.mock('@/stores/authStore', () => ({
  useAuthStore: () => ({ isAuthenticated: true }),
}));

vi.mock('react-hot-toast', () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));

import { useChatSession } from '@/hooks/chat/useChatSession';

function makeThread(id: string, overrides: Partial<Thread> = {}): Thread {
  return {
    id,
    conversation_id: 'conv-1',
    title: id,
    status: 'active',
    last_message_at: '2026-07-14T12:00:00Z',
    message_count: 0,
    token_count: 0,
    created_at: '2026-07-14T12:00:00Z',
    updated_at: '2026-07-14T12:00:00Z',
    ...overrides,
  };
}

function makeMessage(index: number, threadId = 'thread-old'): ChatMessage {
  return {
    id: `message-${index}`,
    thread_id: threadId,
    content: `message ${index}`,
    role: index % 2 === 0 ? 'assistant' : 'user',
    token_count: 1,
    citations: [],
    attachments: [],
    created_at: new Date(Date.UTC(2026, 6, 14, 12, index)).toISOString(),
    updated_at: new Date(Date.UTC(2026, 6, 14, 12, index)).toISOString(),
  };
}

describe('useChatSession bounded restoration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    navigationMocks.threadId = null;
    navigationMocks.isNew = false;
    chatStoreMocks.state.currentThreadId = null;
    chatStoreMocks.state.messages = {};
    chatStoreMocks.state.messagePagination = {};
    chatStoreMocks.state.loadingThreadId = null;
    chatStoreMocks.state.error = null;
    workspaceMocks.getOrCreateDefaultWorkspace.mockResolvedValue({
      id: 'workspace-1',
      name: 'Workspace',
    });
    workspaceMocks.getOrCreateDefaultConversation.mockResolvedValue({
      id: 'conv-1',
      title: 'New Chat',
    });
    workspaceMocks.listThreads.mockResolvedValue({
      threads: [],
      total: 0,
      page: 1,
      limit: 50,
      has_more: false,
    });
    workspaceMocks.listConversations.mockResolvedValue({ conversations: [] });
    chatStoreMocks.state.loadMessages.mockResolvedValue(undefined);
  });

  it('does not select the newest sidebar thread before an uncached URL target', async () => {
    navigationMocks.threadId = 'thread-old';
    workspaceMocks.listThreads.mockResolvedValue({
      threads: [makeThread('thread-newest')],
      total: 1,
      page: 1,
      limit: 50,
      has_more: false,
    });
    workspaceMocks.getThread.mockResolvedValue({
      ...makeThread('thread-old'),
      messages: [],
    });

    renderHook(() => useChatSession());

    await waitFor(() =>
      expect(workspaceMocks.getThread).toHaveBeenCalledWith('thread-old', {
        includeMessages: false,
      })
    );
    expect(chatStoreMocks.state.setCurrentThread).not.toHaveBeenCalledWith(
      'thread-newest'
    );
  });

  it('restores an uncached URL target when the sidebar page is empty', async () => {
    navigationMocks.threadId = 'thread-old';
    workspaceMocks.getThread.mockResolvedValue({
      ...makeThread('thread-old'),
      messages: [],
    });

    renderHook(() => useChatSession());

    await waitFor(() =>
      expect(workspaceMocks.getThread).toHaveBeenCalledWith('thread-old', {
        includeMessages: false,
      })
    );
  });

  it('lets the URL target override a different persisted warm thread', async () => {
    localStorage.setItem('default-conversation-id', 'conv-1');
    navigationMocks.threadId = 'thread-deep-link';
    chatStoreMocks.state.currentThreadId = 'thread-persisted';
    workspaceMocks.listThreads.mockResolvedValue({
      threads: [makeThread('thread-persisted')],
      total: 1,
      page: 1,
      limit: 50,
      has_more: false,
    });
    workspaceMocks.getThread.mockResolvedValue({
      ...makeThread('thread-deep-link'),
      messages: [],
    });

    renderHook(() => useChatSession());

    await waitFor(() =>
      expect(workspaceMocks.getThread).toHaveBeenCalledWith(
        'thread-deep-link',
        { includeMessages: false }
      )
    );
    expect(workspaceMocks.getThread).not.toHaveBeenCalledWith(
      'thread-persisted',
      expect.anything()
    );
  });

  it('restores only the bounded store page for a warm thread', async () => {
    localStorage.setItem('default-conversation-id', 'conv-1');
    chatStoreMocks.state.currentThreadId = 'thread-old';
    workspaceMocks.listThreads.mockResolvedValue({
      threads: [makeThread('thread-old', { message_count: 1000 })],
      total: 1,
      page: 1,
      limit: 50,
      has_more: false,
    });
    chatStoreMocks.state.loadMessages.mockImplementation(async () => {
      chatStoreMocks.state.messages['thread-old'] = Array.from(
        { length: 50 },
        (_, index) => makeMessage(index)
      );
      chatStoreMocks.state.messagePagination['thread-old'] = {
        hasMore: true,
        loadingOlder: false,
        loadedCount: 50,
      };
    });
    workspaceMocks.getThread.mockResolvedValue({
      ...makeThread('thread-old', { message_count: 1000 }),
      messages: Array.from({ length: 1000 }, (_, index) => makeMessage(index)),
    });

    const { result } = renderHook(() => useChatSession());

    await waitFor(() => expect(result.current.isInitializing).toBe(false));
    expect(workspaceMocks.getThread).not.toHaveBeenCalled();
    expect(chatStoreMocks.state.loadMessages).toHaveBeenCalledWith(
      'thread-old'
    );
    expect(result.current.displayedMessages).toHaveLength(50);
    expect(result.current.messagePagination?.['thread-old']).toMatchObject({
      hasMore: true,
      loadedCount: 50,
    });
  });
});
