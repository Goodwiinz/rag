/**
 * Chat Store Project Binding Tests
 *
 * Pins the thread→project binding contract introduced for the context rail
 * and agent page_context:
 * - resolveBoundProjectId truth table (null sentinel ignores stale URL param)
 * - selectCurrentThreadProjectId three-state output from the real store
 * - setThreadProjectBinding write/unbind semantics and safe no-op
 * - registerThread makes composer-created threads bindable immediately
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from '@testing-library/react';
import { enableMapSet } from 'immer';

// Enable Immer MapSet plugin before store import
enableMapSet();

// Mock workspace service (required by store module)
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

// Must import after mocks are set up
import {
  resolveBoundProjectId,
  selectCurrentThreadProjectId,
  useChatStore,
} from '@/store/chat-store';
import type { Thread } from '@/types/workspace';
import { ThreadStatus } from '@/types/workspace';

const iso = new Date().toISOString();

const makeThread = (
  id: string,
  conversationId: string,
  extra: Partial<Thread> = {}
): Thread => ({
  id,
  conversation_id: conversationId,
  title: id,
  status: ThreadStatus.ACTIVE,
  last_message_at: iso,
  message_count: 0,
  token_count: 0,
  created_at: iso,
  updated_at: iso,
  ...extra,
});

describe('resolveBoundProjectId', () => {
  it('ignores a stale URL param when the thread is loaded and unbound', () => {
    expect(resolveBoundProjectId(null, 'stale-proj')).toBeUndefined();
  });

  it('prefers the thread binding over the URL param', () => {
    expect(resolveBoundProjectId('proj-b', 'proj-a')).toBe('proj-b');
  });

  it('falls back to the URL param while the thread is not in the store yet', () => {
    expect(resolveBoundProjectId(undefined, 'proj-a')).toBe('proj-a');
  });

  it('returns undefined with no binding and no param', () => {
    expect(resolveBoundProjectId(undefined, null)).toBeUndefined();
    expect(resolveBoundProjectId(null, null)).toBeUndefined();
  });
});

describe('selectCurrentThreadProjectId', () => {
  beforeEach(() => {
    act(() => {
      useChatStore.getState().reset();
    });
  });

  it('returns the bound project id for the current thread', () => {
    useChatStore.setState({
      currentThreadId: 't1',
      threads: {
        'conv-a': [makeThread('t1', 'conv-a', { source_project_id: 'p1' })],
      },
    });
    expect(selectCurrentThreadProjectId(useChatStore.getState())).toBe('p1');
  });

  it('treats a thread without source_project_id as loaded-and-unbound (null)', () => {
    useChatStore.setState({
      currentThreadId: 't2',
      // t2 lives in the SECOND list — the scan must cross conversations.
      threads: {
        'conv-a': [makeThread('t1', 'conv-a')],
        'conv-b': [makeThread('t2', 'conv-b')],
      },
    });
    expect(selectCurrentThreadProjectId(useChatStore.getState())).toBeNull();
  });

  it('returns undefined while the thread has not loaded into the store', () => {
    useChatStore.setState({
      currentThreadId: 'ghost',
      threads: { 'conv-a': [makeThread('t1', 'conv-a')] },
    });
    expect(
      selectCurrentThreadProjectId(useChatStore.getState())
    ).toBeUndefined();
  });

  it('returns undefined when no thread is selected', () => {
    useChatStore.setState({ currentThreadId: null, threads: {} });
    expect(
      selectCurrentThreadProjectId(useChatStore.getState())
    ).toBeUndefined();
  });
});

describe('setThreadProjectBinding', () => {
  beforeEach(() => {
    act(() => {
      useChatStore.getState().reset();
    });
  });

  it('binds the matching thread across conversation lists and only that thread', () => {
    useChatStore.setState({
      threads: {
        'conv-a': [makeThread('t1', 'conv-a')],
        'conv-b': [makeThread('t2', 'conv-b')],
      },
    });
    let result: boolean | undefined;
    act(() => {
      result = useChatStore.getState().setThreadProjectBinding('t2', 'proj-9');
    });
    const { threads } = useChatStore.getState();
    expect(result).toBe(true);
    expect(threads['conv-b'][0].source_project_id).toBe('proj-9');
    expect(threads['conv-a'][0].source_project_id).toBeUndefined();
  });

  it('uses the reverse index when populated', () => {
    useChatStore.setState({
      threads: { 'conv-a': [makeThread('t1', 'conv-a')] },
      threadToConversation: { t1: 'conv-a' },
    });
    act(() => {
      useChatStore.getState().setThreadProjectBinding('t1', 'proj-1');
    });
    expect(useChatStore.getState().threads['conv-a'][0].source_project_id).toBe(
      'proj-1'
    );
  });

  it('unbinds with null', () => {
    useChatStore.setState({
      threads: {
        'conv-a': [makeThread('t1', 'conv-a', { source_project_id: 'p1' })],
      },
    });
    act(() => {
      useChatStore.getState().setThreadProjectBinding('t1', null);
    });
    expect(
      useChatStore.getState().threads['conv-a'][0].source_project_id
    ).toBeNull();
    // Selector then reports loaded-and-unbound, which masks stale URL params.
    useChatStore.setState({ currentThreadId: 't1' });
    expect(selectCurrentThreadProjectId(useChatStore.getState())).toBeNull();
  });

  it('is a safe no-op returning false for a thread not yet loaded', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    useChatStore.setState({
      threads: { 'conv-a': [makeThread('t1', 'conv-a')] },
    });
    let result: boolean | undefined;
    expect(() => {
      act(() => {
        result = useChatStore.getState().setThreadProjectBinding('ghost', 'p');
      });
    }).not.toThrow();
    expect(result).toBe(false);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });
});

describe('registerThread', () => {
  beforeEach(() => {
    act(() => {
      useChatStore.getState().reset();
    });
  });

  it('makes a composer-created thread visible to binding immediately', () => {
    const t = makeThread('t-new', 'conv-a');
    act(() => {
      useChatStore.getState().registerThread(t);
    });
    let bound: boolean | undefined;
    act(() => {
      bound = useChatStore.getState().setThreadProjectBinding('t-new', 'p1');
    });
    expect(bound).toBe(true);
    useChatStore.setState({ currentThreadId: 't-new' });
    expect(selectCurrentThreadProjectId(useChatStore.getState())).toBe('p1');
    expect(useChatStore.getState().threadToConversation['t-new']).toBe(
      'conv-a'
    );
  });

  it('does not duplicate an already-registered thread', () => {
    const t = makeThread('t1', 'conv-a');
    act(() => {
      useChatStore.getState().registerThread(t);
      useChatStore.getState().registerThread(t);
    });
    expect(useChatStore.getState().threads['conv-a']).toHaveLength(1);
  });
});
