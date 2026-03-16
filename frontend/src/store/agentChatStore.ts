import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type {
  AgentChatState,
  AgentChatActions,
  AgentMessage,
  AgentThread,
  AgentUIMode,
  PageContext,
} from '@/types/agent-chat';

const DEFAULT_PAGE_CONTEXT: PageContext = {
  type: 'unknown',
  label: 'Dashboard',
};

interface AgentChatStore extends AgentChatState, AgentChatActions {
  reset: () => void;
}

const initialState: AgentChatState = {
  uiMode: 'closed',
  activeThreadId: null,
  threads: [],
  messages: [],
  isStreaming: false,
  inputValue: '',
  hasUnread: false,
  pageContext: DEFAULT_PAGE_CONTEXT,
  isLoadingThreads: false,
  isLoadingMessages: false,
};

export const useAgentChatStore = create<AgentChatStore>()(
  immer((set, get) => ({
    ...initialState,

    // UI
    openPanel: () =>
      set((state) => {
        state.uiMode = 'panel';
        state.hasUnread = false;
      }),

    openSidebar: () =>
      set((state) => {
        state.uiMode = 'sidebar';
        state.hasUnread = false;
      }),

    close: () =>
      set((state) => {
        state.uiMode = 'closed';
      }),

    toggle: () =>
      set((state) => {
        if (state.uiMode === 'closed') {
          state.uiMode = 'panel';
          state.hasUnread = false;
        } else {
          state.uiMode = 'closed';
        }
      }),

    // Input
    setInputValue: (value: string) =>
      set((state) => {
        state.inputValue = value;
      }),

    // Messages
    sendMessage: async () => {
      // Implemented in Task 5 (agent service integration)
    },

    clearMessages: () =>
      set((state) => {
        state.messages = [];
        state.activeThreadId = null;
        state.isStreaming = false;
      }),

    // Threads
    newThread: () =>
      set((state) => {
        state.activeThreadId = null;
        state.messages = [];
        state.inputValue = '';
      }),

    selectThread: (threadId: string) =>
      set((state) => {
        state.activeThreadId = threadId;
      }),

    loadThreads: async () => {
      // Implemented in Task 5
    },

    loadThreadMessages: async (threadId: string) => {
      // Implemented in Task 5
    },

    // Context
    setPageContext: (context: PageContext) => {
      const current = get().pageContext;
      if (
        current.type === context.type &&
        current.label === context.label &&
        current.projectId === context.projectId &&
        current.projectName === context.projectName
      ) {
        return;
      }
      set((state) => {
        state.pageContext = context;
      });
    },

    // Reset
    reset: () => set(() => ({ ...initialState })),
  }))
);
