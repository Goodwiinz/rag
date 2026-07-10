import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAgentChatStore } from '@/store/agentChatStore';

const serviceMocks = vi.hoisted(() => ({
  listThreads: vi.fn(async () => ({ threads: [] })),
  getThreadMessages: vi.fn(async () => ({ messages: [] })),
  streamMessage: vi.fn(async () => {}),
  startDurableRun: vi.fn(async () => ({ runId: 'run-stub' })),
}));

// loadThreads/loadThreadMessages dynamically import agentChatService and call
// the backend. In jsdom that request never resolves, so loadThreads otherwise
// hangs to the 15s test timeout. Mock the service to keep these unit tests
// hermetic and fast. (Mirrors the fix in PR #734.)
vi.mock('@/services/agentChatService', () => ({
  agentChatService: {
    listThreads: serviceMocks.listThreads,
    getThreadMessages: serviceMocks.getThreadMessages,
    streamMessage: serviceMocks.streamMessage,
    startDurableRun: serviceMocks.startDurableRun,
  },
}));

describe('agentChatStore', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    useAgentChatStore.getState().reset();
    serviceMocks.getThreadMessages.mockReset();
    serviceMocks.getThreadMessages.mockResolvedValue({ messages: [] });
  });

  describe('initial state', () => {
    it('starts with closed UI mode', () => {
      const state = useAgentChatStore.getState();
      expect(state.uiMode).toBe('closed');
    });

    it('has no active thread', () => {
      const state = useAgentChatStore.getState();
      expect(state.activeThreadId).toBeNull();
    });

    it('has empty messages', () => {
      const state = useAgentChatStore.getState();
      expect(state.messages).toEqual([]);
    });

    it('has empty threads', () => {
      const state = useAgentChatStore.getState();
      expect(state.threads).toEqual([]);
    });

    it('has unknown page context with Dashboard label', () => {
      const state = useAgentChatStore.getState();
      expect(state.pageContext).toEqual({
        type: 'unknown',
        label: 'Dashboard',
      });
    });

    it('is not streaming', () => {
      const state = useAgentChatStore.getState();
      expect(state.isStreaming).toBe(false);
    });

    it('has empty input value', () => {
      const state = useAgentChatStore.getState();
      expect(state.inputValue).toBe('');
    });

    it('has no unread messages', () => {
      const state = useAgentChatStore.getState();
      expect(state.hasUnread).toBe(false);
    });

    it('is not loading threads or messages', () => {
      const state = useAgentChatStore.getState();
      expect(state.isLoadingThreads).toBe(false);
      expect(state.isLoadingMessages).toBe(false);
    });
  });

  describe('UI mode transitions', () => {
    it('openPanel sets mode to panel', () => {
      useAgentChatStore.getState().openPanel();
      expect(useAgentChatStore.getState().uiMode).toBe('panel');
    });

    it('openSidebar sets mode to sidebar', () => {
      useAgentChatStore.getState().openSidebar();
      expect(useAgentChatStore.getState().uiMode).toBe('sidebar');
    });

    it('close sets mode to closed', () => {
      useAgentChatStore.getState().openPanel();
      useAgentChatStore.getState().close();
      expect(useAgentChatStore.getState().uiMode).toBe('closed');
    });

    it('toggle cycles closed -> panel -> closed', () => {
      useAgentChatStore.getState().toggle();
      expect(useAgentChatStore.getState().uiMode).toBe('panel');
      useAgentChatStore.getState().toggle();
      expect(useAgentChatStore.getState().uiMode).toBe('closed');
    });

    it('toggle from sidebar closes', () => {
      useAgentChatStore.getState().openSidebar();
      useAgentChatStore.getState().toggle();
      expect(useAgentChatStore.getState().uiMode).toBe('closed');
    });

    it('openPanel clears unread', () => {
      useAgentChatStore.setState({ hasUnread: true });
      useAgentChatStore.getState().openPanel();
      expect(useAgentChatStore.getState().hasUnread).toBe(false);
    });

    it('openSidebar clears unread', () => {
      useAgentChatStore.setState({ hasUnread: true });
      useAgentChatStore.getState().openSidebar();
      expect(useAgentChatStore.getState().hasUnread).toBe(false);
    });

    it('toggle to open clears unread', () => {
      useAgentChatStore.setState({ hasUnread: true });
      useAgentChatStore.getState().toggle();
      expect(useAgentChatStore.getState().hasUnread).toBe(false);
    });
  });

  describe('input management', () => {
    it('setInputValue updates input', () => {
      useAgentChatStore.getState().setInputValue('hello');
      expect(useAgentChatStore.getState().inputValue).toBe('hello');
    });

    it('setInputValue can set empty string', () => {
      useAgentChatStore.getState().setInputValue('hello');
      useAgentChatStore.getState().setInputValue('');
      expect(useAgentChatStore.getState().inputValue).toBe('');
    });
  });

  describe('page context', () => {
    it('setPageContext updates context', () => {
      useAgentChatStore.getState().setPageContext({
        type: 'project',
        label: 'Test Project',
        projectId: 'abc-123',
        projectName: 'Test Project',
      });
      const ctx = useAgentChatStore.getState().pageContext;
      expect(ctx.type).toBe('project');
      expect(ctx.label).toBe('Test Project');
      expect(ctx.projectId).toBe('abc-123');
      expect(ctx.projectName).toBe('Test Project');
    });

    it('setPageContext skips update when context is identical', () => {
      const context = {
        type: 'documents' as const,
        label: 'Documents',
      };
      useAgentChatStore.getState().setPageContext(context);
      const stateAfterFirst = useAgentChatStore.getState();
      useAgentChatStore.getState().setPageContext(context);
      const stateAfterSecond = useAgentChatStore.getState();
      // pageContext object reference should be the same (no unnecessary update)
      expect(stateAfterFirst.pageContext).toBe(stateAfterSecond.pageContext);
    });
  });

  describe('thread management', () => {
    it('newThread clears active thread, messages, and input', () => {
      useAgentChatStore.setState({
        activeThreadId: 'thread-1',
        messages: [
          { id: '1', role: 'user', content: 'hi', timestamp: new Date() },
        ],
        inputValue: 'draft message',
      });
      useAgentChatStore.getState().newThread();
      expect(useAgentChatStore.getState().activeThreadId).toBeNull();
      expect(useAgentChatStore.getState().messages).toEqual([]);
      expect(useAgentChatStore.getState().inputValue).toBe('');
    });

    it('selectThread sets activeThreadId', () => {
      useAgentChatStore.getState().selectThread('thread-42');
      expect(useAgentChatStore.getState().activeThreadId).toBe('thread-42');
    });

    it('keeps the latest selected thread when an earlier fetch resolves last', async () => {
      let resolveThreadA!: (value: { messages: Array<Record<string, unknown>> }) => void;
      let resolveThreadB!: (value: { messages: Array<Record<string, unknown>> }) => void;
      const threadA = new Promise<{ messages: Array<Record<string, unknown>> }>((resolve) => {
        resolveThreadA = resolve;
      });
      const threadB = new Promise<{ messages: Array<Record<string, unknown>> }>((resolve) => {
        resolveThreadB = resolve;
      });
      vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
        const response = String(input).includes('thread-A') ? threadA : threadB;
        return response.then((body) =>
          Promise.resolve(
            new Response(JSON.stringify(body), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            })
          )
        );
      }));

      useAgentChatStore.setState({
        messages: [
          { id: 'old', role: 'assistant', content: 'old transcript', timestamp: new Date() },
        ],
      });

      useAgentChatStore.getState().selectThread('thread-A');
      const loadA = useAgentChatStore.getState().loadThreadMessages('thread-A');
      useAgentChatStore.getState().selectThread('thread-B');
      const loadB = useAgentChatStore.getState().loadThreadMessages('thread-B');

      expect(useAgentChatStore.getState().messages).toEqual([]);
      expect(useAgentChatStore.getState().isLoadingMessages).toBe(true);

      resolveThreadB({
        messages: [
          { id: 'b1', role: 'assistant', content: 'thread B', created_at: new Date().toISOString() },
        ],
      });
      await loadB;
      resolveThreadA({
        messages: [
          { id: 'a1', role: 'assistant', content: 'thread A', created_at: new Date().toISOString() },
        ],
      });
      await loadA;

      const state = useAgentChatStore.getState();
      expect(state.activeThreadId).toBe('thread-B');
      expect(state.messages.map((message) => message.content)).toEqual(['thread B']);
      expect(state.isLoadingMessages).toBe(false);
    });
  });

  describe('clearMessages', () => {
    it('clears messages, activeThreadId, and isStreaming', () => {
      useAgentChatStore.setState({
        messages: [
          {
            id: '1',
            role: 'assistant',
            content: 'hello',
            timestamp: new Date(),
          },
        ],
        activeThreadId: 'thread-1',
        isStreaming: true,
      });
      useAgentChatStore.getState().clearMessages();
      const state = useAgentChatStore.getState();
      expect(state.messages).toEqual([]);
      expect(state.activeThreadId).toBeNull();
      expect(state.isStreaming).toBe(false);
    });
  });

  describe('async stubs', () => {
    it('sendMessage is callable and returns a promise', async () => {
      await expect(
        useAgentChatStore.getState().sendMessage()
      ).resolves.toBeUndefined();
    });

    it('loadThreads is callable and returns a promise', async () => {
      await expect(
        useAgentChatStore.getState().loadThreads()
      ).resolves.toBeUndefined();
    });

    it('loadThreadMessages is callable and returns a promise', async () => {
      await expect(
        useAgentChatStore.getState().loadThreadMessages('thread-1')
      ).resolves.toBeUndefined();
    });
  });

  describe('reflection revise loop', () => {
    it('replaces first-answer tokens with second when revising=true fires between them', async () => {
      // Arrange: streamMessage calls onToken('A'), then onReflection(revising=true),
      // then onToken('B'), then onDone — the final message content must be 'B'.
      const { agentChatService } = await import('@/services/agentChatService');
      vi.mocked(agentChatService.streamMessage).mockImplementationOnce(
        async (_req, callbacks) => {
          callbacks.onToken?.('A');
          callbacks.onReflection?.(false, [], 1, true);
          callbacks.onToken?.('B');
          callbacks.onDone?.();
        }
      );

      useAgentChatStore.setState({ inputValue: 'test prompt' });
      await useAgentChatStore.getState().sendMessage();

      const messages = useAgentChatStore.getState().messages;
      const assistant = messages.find((m) => m.role === 'assistant');
      expect(assistant?.content).toBe('B');
    });

    it('does NOT reset content when revising=false', async () => {
      // Arrange: onReflection with revising=false (quality passed) should leave
      // accumulated content untouched.
      const { agentChatService } = await import('@/services/agentChatService');
      vi.mocked(agentChatService.streamMessage).mockImplementationOnce(
        async (_req, callbacks) => {
          callbacks.onToken?.('A');
          callbacks.onReflection?.(true, [], 0, false);
          callbacks.onDone?.();
        }
      );

      useAgentChatStore.setState({ inputValue: 'test prompt' });
      await useAgentChatStore.getState().sendMessage();

      const messages = useAgentChatStore.getState().messages;
      const assistant = messages.find((m) => m.role === 'assistant');
      expect(assistant?.content).toBe('A');
    });
  });

  describe('reset', () => {
    it('restores all state to initial values', () => {
      // Mutate state
      useAgentChatStore.setState({
        uiMode: 'panel',
        activeThreadId: 'thread-99',
        messages: [
          { id: '1', role: 'user', content: 'msg', timestamp: new Date() },
        ],
        isStreaming: true,
        inputValue: 'some text',
        hasUnread: true,
        pageContext: { type: 'project', label: 'Proj' },
        isLoadingThreads: true,
        isLoadingMessages: true,
      });

      useAgentChatStore.getState().reset();

      const state = useAgentChatStore.getState();
      expect(state.uiMode).toBe('closed');
      expect(state.activeThreadId).toBeNull();
      expect(state.messages).toEqual([]);
      expect(state.threads).toEqual([]);
      expect(state.isStreaming).toBe(false);
      expect(state.inputValue).toBe('');
      expect(state.hasUnread).toBe(false);
      expect(state.pageContext).toEqual({
        type: 'unknown',
        label: 'Dashboard',
      });
      expect(state.isLoadingThreads).toBe(false);
      expect(state.isLoadingMessages).toBe(false);
    });
  });
});
