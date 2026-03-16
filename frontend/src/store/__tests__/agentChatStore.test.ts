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

    it('has unknown page context', () => {
      const state = useAgentChatStore.getState();
      expect(state.pageContext.type).toBe('unknown');
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

    it('toggle cycles closed → panel → closed', () => {
      useAgentChatStore.getState().toggle();
      expect(useAgentChatStore.getState().uiMode).toBe('panel');
      useAgentChatStore.getState().toggle();
      expect(useAgentChatStore.getState().uiMode).toBe('closed');
    });

    it('openPanel clears unread', () => {
      useAgentChatStore.setState({ hasUnread: true });
      useAgentChatStore.getState().openPanel();
      expect(useAgentChatStore.getState().hasUnread).toBe(false);
    });
  });

  describe('input management', () => {
    it('setInputValue updates input', () => {
      useAgentChatStore.getState().setInputValue('hello');
      expect(useAgentChatStore.getState().inputValue).toBe('hello');
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
      expect(ctx.projectId).toBe('abc-123');
    });
  });

  describe('thread management', () => {
    it('newThread clears active thread and messages', () => {
      useAgentChatStore.setState({
        activeThreadId: 'thread-1',
        messages: [
          { id: '1', role: 'user', content: 'hi', timestamp: new Date() },
        ],
      });
      useAgentChatStore.getState().newThread();
      expect(useAgentChatStore.getState().activeThreadId).toBeNull();
      expect(useAgentChatStore.getState().messages).toEqual([]);
    });

    it('selectThread sets activeThreadId', () => {
      useAgentChatStore.getState().selectThread('thread-42');
      expect(useAgentChatStore.getState().activeThreadId).toBe('thread-42');
    });
  });
});
