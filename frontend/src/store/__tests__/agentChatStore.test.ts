import { beforeEach, describe, expect, it } from 'vitest';
import { useAgentChatStore } from '@/store/agentChatStore';

describe('agentChatStore', () => {
  beforeEach(() => {
    useAgentChatStore.getState().reset();
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
