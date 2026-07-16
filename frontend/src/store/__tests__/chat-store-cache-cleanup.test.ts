/**
 * Chat Store cache-lifecycle tests.
 *
 * Pins the fixes for four pre-existing monolith bugs preserved verbatim by
 * the behavior-freeze store split (PR #1205 CodeRabbit triage, 2026-07-16).
 * Each test FAILS against the old behavior — these are deliberate behavior
 * changes:
 * - deleteConversation cascades cleanup to cached threads/messages/
 *   reverse-indexes/pagination/freshness and aborts descendant requests
 * - loadConversations purges stale conversationToWorkspace entries for
 *   conversations no longer returned for that workspace
 * - bulkDeleteThreads clears currentThreadId from SUCCESSFUL results, not
 *   requested ids
 * - loadThreads ignores a late 404 for a conversation the user has already
 *   navigated away from (no stale-data recovery nuking valid state)
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, waitFor } from '@testing-library/react';
import { enableMapSet } from 'immer';

enableMapSet();

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    listWorkspaces: vi.fn(),
    createWorkspace: vi.fn(),
    updateWorkspace: vi.fn(),
    deleteWorkspace: vi.fn(),
    getOrCreateDefaultWorkspace: vi.fn(),
    listConversations: vi.fn(),
    createConversation: vi.fn(),
    updateConversation: vi.fn(),
    deleteConversation: vi.fn(),
    listThreads: vi.fn(),
    createThread: vi.fn(),
    updateThread: vi.fn(),
    deleteThread: vi.fn(),
    bulkResolveThreads: vi.fn(),
    bulkArchiveThreads: vi.fn(),
    bulkSummarizeThreads: vi.fn(),
    bulkDeleteThreads: vi.fn(),
    listMessages: vi.fn(),
    createMessage: vi.fn(),
    updateMessage: vi.fn(),
    deleteMessage: vi.fn(),
  },
}));

import { workspaceService } from '@/services/workspaceService';
import { useChatStore } from '@/store/chat-store';
import { newestPageRequests } from '@/store/chat/requestCoordinator';
import {
  ChatMessage,
  Conversation,
  MessageRole,
  Thread,
  ThreadStatus,
  Workspace,
} from '@/types/workspace';

const iso = new Date().toISOString();

const makeWorkspace = (id: string): Workspace => ({
  id,
  name: id,
  owner_id: 'user-1',
  is_archived: false,
  is_public: false,
  created_at: iso,
  updated_at: iso,
});

const makeConversation = (id: string, workspaceId: string): Conversation => ({
  id,
  workspace_id: workspaceId,
  title: id,
  created_by_id: 'user-1',
  is_archived: false,
  is_pinned: false,
  last_activity_at: iso,
  created_at: iso,
  updated_at: iso,
});

const makeThread = (id: string, conversationId: string): Thread => ({
  id,
  conversation_id: conversationId,
  title: id,
  status: ThreadStatus.ACTIVE,
  last_message_at: iso,
  message_count: 0,
  token_count: 0,
  created_at: iso,
  updated_at: iso,
});

const makeMessage = (id: string, threadId: string): ChatMessage => ({
  id,
  thread_id: threadId,
  content: `message ${id}`,
  role: MessageRole.USER,
  token_count: 0,
  citations: [],
  attachments: [],
  created_at: iso,
  updated_at: iso,
});

const pagination = () => ({
  hasMore: false,
  loadingOlder: false,
  loadedCount: 1,
});

describe('deleteConversation cascade cleanup', () => {
  beforeEach(() => {
    act(() => {
      useChatStore.getState().reset();
    });
    vi.clearAllMocks();
    newestPageRequests.clear();
  });

  it('cascades cleanup to cached threads, messages, reverse indexes, pagination and freshness, and aborts descendant requests', async () => {
    const m1 = makeMessage('m1', 't1');
    const m2 = makeMessage('m2', 't2');
    const m3 = makeMessage('m3', 't3');
    useChatStore.setState({
      currentConversationId: 'conv-a',
      currentThreadId: 't1',
      conversations: {
        'ws-1': [
          makeConversation('conv-a', 'ws-1'),
          makeConversation('conv-b', 'ws-1'),
        ],
      },
      conversationToWorkspace: { 'conv-a': 'ws-1', 'conv-b': 'ws-1' },
      threads: {
        'conv-a': [makeThread('t1', 'conv-a'), makeThread('t2', 'conv-a')],
        'conv-b': [makeThread('t3', 'conv-b')],
      },
      threadToConversation: { t1: 'conv-a', t2: 'conv-a', t3: 'conv-b' },
      messages: { t1: [m1], t2: [m2], t3: [m3] },
      messageToThread: { m1: 't1', m2: 't2', m3: 't3' },
      messagePagination: { t1: pagination(), t2: pagination(), t3: pagination() },
      messageFreshness: { t1: 'fresh', t2: 'fresh', t3: 'fresh' },
    });
    const inFlight = new AbortController();
    newestPageRequests.set('t1', { generation: 1, controller: inFlight });
    (
      workspaceService.deleteConversation as ReturnType<typeof vi.fn>
    ).mockResolvedValue(undefined);

    await act(async () => {
      await useChatStore.getState().deleteConversation('conv-a');
    });

    const state = useChatStore.getState();
    // Conversation row + reverse index (previous behavior already had this)
    expect(state.conversations['ws-1'].map((c) => c.id)).toEqual(['conv-b']);
    expect(state.conversationToWorkspace['conv-a']).toBeUndefined();
    // Descendant thread cache — the old code left ALL of this orphaned
    expect(state.threads['conv-a']).toBeUndefined();
    expect(state.threadToConversation.t1).toBeUndefined();
    expect(state.threadToConversation.t2).toBeUndefined();
    expect(state.messages.t1).toBeUndefined();
    expect(state.messages.t2).toBeUndefined();
    expect(state.messagePagination.t1).toBeUndefined();
    expect(state.messagePagination.t2).toBeUndefined();
    expect(state.messageFreshness.t1).toBeUndefined();
    expect(state.messageFreshness.t2).toBeUndefined();
    expect(state.messageToThread.m1).toBeUndefined();
    expect(state.messageToThread.m2).toBeUndefined();
    // In-flight newest-page request for a descendant thread is aborted
    expect(inFlight.signal.aborted).toBe(true);
    expect(newestPageRequests.has('t1')).toBe(false);
    // Selection cleared
    expect(state.currentConversationId).toBeNull();
    expect(state.currentThreadId).toBeNull();
    // Sibling conversation untouched
    expect(state.threads['conv-b']).toHaveLength(1);
    expect(state.threadToConversation.t3).toBe('conv-b');
    expect(state.messages.t3).toHaveLength(1);
    expect(state.messageToThread.m3).toBe('t3');
  });
});

describe('loadConversations reverse-index purge', () => {
  beforeEach(() => {
    act(() => {
      useChatStore.getState().reset();
    });
    vi.clearAllMocks();
  });

  it('purges stale conversationToWorkspace entries for conversations absent from the response, leaving other workspaces alone', async () => {
    useChatStore.setState({
      conversationToWorkspace: {
        'conv-live': 'ws-1',
        'conv-gone': 'ws-1',
        'conv-other': 'ws-2',
      },
    });
    (
      workspaceService.listConversations as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      conversations: [makeConversation('conv-live', 'ws-1')],
      total: 1,
      page: 1,
      limit: 50,
      has_more: false,
    });

    await act(async () => {
      await useChatStore.getState().loadConversations('ws-1');
    });

    expect(useChatStore.getState().conversationToWorkspace).toEqual({
      'conv-live': 'ws-1',
      'conv-other': 'ws-2',
    });
  });
});

describe('bulkDeleteThreads success-based currentThreadId clearing', () => {
  beforeEach(() => {
    act(() => {
      useChatStore.getState().reset();
    });
    vi.clearAllMocks();
  });

  const seed = () => {
    useChatStore.setState({
      currentConversationId: 'conv-a',
      currentThreadId: 't1',
      threads: {
        'conv-a': [makeThread('t1', 'conv-a'), makeThread('t2', 'conv-a')],
      },
      threadToConversation: { t1: 'conv-a', t2: 'conv-a' },
      selectedThreadIds: new Set(['t1', 't2']),
      isSelectMode: true,
    });
  };

  it('keeps currentThreadId when its delete FAILED, even though it was requested', async () => {
    seed();
    (
      workspaceService.bulkDeleteThreads as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      total: 2,
      succeeded: 1,
      failed: 1,
      results: [
        { thread_id: 't1', success: false, error: 'delete failed' },
        { thread_id: 't2', success: true },
      ],
    });

    await act(async () => {
      await useChatStore.getState().bulkDeleteThreads();
    });

    const state = useChatStore.getState();
    // Old behavior cleared this from the REQUESTED ids; t1 is still alive
    expect(state.currentThreadId).toBe('t1');
    expect(state.threads['conv-a'].map((t) => t.id)).toEqual(['t1']);
  });

  it('still clears currentThreadId when its delete succeeded', async () => {
    seed();
    (
      workspaceService.bulkDeleteThreads as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      total: 2,
      succeeded: 2,
      failed: 0,
      results: [
        { thread_id: 't1', success: true },
        { thread_id: 't2', success: true },
      ],
    });

    await act(async () => {
      await useChatStore.getState().bulkDeleteThreads();
    });

    expect(useChatStore.getState().currentThreadId).toBeNull();
  });
});

describe('loadThreads stale-404 recovery guard', () => {
  beforeEach(() => {
    act(() => {
      useChatStore.getState().reset();
    });
    vi.clearAllMocks();
  });

  const notFound = () =>
    Object.assign(new Error('Not Found'), { response: { status: 404 } });

  it('ignores a late 404 for a conversation the user has already navigated away from', async () => {
    useChatStore.setState({
      currentWorkspaceId: 'ws-1',
      currentConversationId: 'conv-b',
      currentThreadId: 't3',
      workspaces: [makeWorkspace('ws-1')],
    });
    (
      workspaceService.listThreads as ReturnType<typeof vi.fn>
    ).mockRejectedValue(notFound());

    await act(async () => {
      await useChatStore.getState().loadThreads('conv-a');
    });

    const state = useChatStore.getState();
    // Old behavior nuked the valid current selection + workspaces and
    // triggered a full reinit
    expect(state.currentConversationId).toBe('conv-b');
    expect(state.currentThreadId).toBe('t3');
    expect(state.currentWorkspaceId).toBe('ws-1');
    expect(state.workspaces).toHaveLength(1);
    expect(state.isLoadingThreads).toBe(false);
    expect(workspaceService.getOrCreateDefaultWorkspace).not.toHaveBeenCalled();
  });

  it('still runs stale-data recovery when the 404 is for the CURRENT conversation', async () => {
    useChatStore.setState({
      currentWorkspaceId: 'ws-1',
      currentConversationId: 'conv-a',
    });
    (
      workspaceService.listThreads as ReturnType<typeof vi.fn>
    ).mockRejectedValue(notFound());
    (
      workspaceService.getOrCreateDefaultWorkspace as ReturnType<typeof vi.fn>
    ).mockResolvedValue({ id: 'ws-1', name: 'W' });
    (
      workspaceService.listConversations as ReturnType<typeof vi.fn>
    ).mockResolvedValue({
      conversations: [],
      total: 0,
      page: 1,
      limit: 50,
      has_more: false,
    });

    await act(async () => {
      await useChatStore.getState().loadThreads('conv-a');
    });

    expect(useChatStore.getState().currentConversationId).toBeNull();
    await waitFor(() => {
      expect(workspaceService.getOrCreateDefaultWorkspace).toHaveBeenCalled();
    });
  });
});
