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
      const state = get();
      const trimmed = state.inputValue.trim();
      if (!trimmed || state.isStreaming) return;

      const userMessage: AgentMessage = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: trimmed,
        timestamp: new Date(),
      };

      set((s) => {
        s.messages.push(userMessage);
        s.inputValue = '';
        s.isStreaming = true;
      });

      try {
        const { agentChatService } =
          await import('@/services/agentChatService');

        const messagesForApi = get()
          .messages.filter((m) => m.role === 'user' || m.role === 'assistant')
          .map((m) => ({ role: m.role, content: m.content }));

        const response = await agentChatService.execute({
          messages: messagesForApi,
          page_context: {
            type: get().pageContext.type,
            project_id: get().pageContext.projectId,
          },
          thread_id: get().activeThreadId ?? undefined,
        });

        const assistantMessage: AgentMessage = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: response.message.content,
          timestamp: new Date(),
          citations: response.retrieved_contexts?.map((ctx) => ({
            documentId: ctx.document_id || '',
            documentTitle: ctx.title,
            snippet: ctx.content.slice(0, 200),
            score: ctx.score,
          })),
          toolExecutions: response.tool_executions?.map((exec) => ({
            id: exec.id,
            toolName: exec.tool_name,
            toolDisplayName: exec.tool_display_name,
            args: exec.args,
            status: exec.status as 'running' | 'completed' | 'failed',
            result: exec.result,
            error: exec.error,
            durationMs: exec.duration_ms,
          })),
        };

        set((s) => {
          s.messages.push(assistantMessage);
          s.isStreaming = false;
          if (response.thread_id) {
            s.activeThreadId = response.thread_id;
          }
          if (s.uiMode === 'closed') {
            s.hasUnread = true;
          }
        });
      } catch (error) {
        console.error('Agent chat error:', error);
        set((s) => {
          s.messages.push({
            id: `error-${Date.now()}`,
            role: 'assistant',
            content: 'Sorry, something went wrong. Please try again.',
            timestamp: new Date(),
          });
          s.isStreaming = false;
        });
      }
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
      set((s) => {
        s.isLoadingThreads = true;
      });
      try {
        const { agentChatService } =
          await import('@/services/agentChatService');
        const response = await agentChatService.listThreads();
        set((s) => {
          s.threads = response.threads.map((t) => ({
            id: t.id,
            title: t.title || 'Untitled',
            createdAt: new Date(t.created_at),
            updatedAt: new Date(t.updated_at),
            messageCount: t.message_count,
            lastMessage: undefined,
            projectId: t.source_project_id || undefined,
          }));
          s.isLoadingThreads = false;
        });
      } catch (error) {
        console.error('Failed to load threads:', error);
        set((s) => {
          s.isLoadingThreads = false;
        });
      }
    },

    loadThreadMessages: async (threadId: string) => {
      set((s) => {
        s.isLoadingMessages = true;
      });
      try {
        const { agentChatService } =
          await import('@/services/agentChatService');
        const response = await agentChatService.getThreadMessages(threadId);
        set((s) => {
          s.messages = response.messages.map((m) => ({
            id: m.id,
            role: m.role as 'user' | 'assistant' | 'tool',
            content: m.content,
            timestamp: new Date(m.created_at),
            citations: m.citations?.map((c) => ({
              documentId: c.document_id,
              documentTitle: c.document_title,
              snippet: c.snippet,
              page: c.page_number,
              score: c.score,
            })),
            backendMessageId: m.id,
          }));
          s.activeThreadId = threadId;
          s.isLoadingMessages = false;
        });
      } catch (error) {
        console.error('Failed to load thread messages:', error);
        set((s) => {
          s.isLoadingMessages = false;
        });
      }
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
