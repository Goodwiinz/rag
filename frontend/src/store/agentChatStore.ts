import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type {
  AgentChatState,
  AgentChatActions,
  AgentMessage,
  AgentThread,
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
      const { inputValue, isStreaming, pageContext, activeThreadId, uiMode } =
        get();
      const trimmed = inputValue.trim();
      if (!trimmed || isStreaming) return;

      // Create user message and update state
      const userMessage: AgentMessage = {
        id: `msg-${Date.now()}`,
        role: 'user',
        content: trimmed,
        timestamp: new Date(),
      };

      set((state) => {
        state.messages.push(userMessage);
        state.inputValue = '';
        state.isStreaming = true;
      });

      try {
        const { agentChatService } =
          await import('@/services/agentChatService');

        // Build messages array for the API (only user/assistant roles)
        const apiMessages = get()
          .messages.filter((m) => m.role === 'user' || m.role === 'assistant')
          .map((m) => ({ role: m.role, content: m.content }));

        // Step 1: Start the async job
        const { job_id } = await agentChatService.startJob({
          messages: apiMessages,
          page_context: {
            type: pageContext.type,
            project_id: pageContext.projectId,
          },
          thread_id: activeThreadId ?? undefined,
        });

        // Step 2: Add a streaming placeholder message
        const placeholderId = `msg-${Date.now()}-assistant`;
        set((state) => {
          state.messages.push({
            id: placeholderId,
            role: 'assistant',
            content: '',
            timestamp: new Date(),
            isStreaming: true,
          });
        });

        // Step 3: Poll until completed or failed (max 120 polls = 3 min)
        const MAX_POLLS = 120;
        const POLL_INTERVAL_MS = 1500;

        for (let i = 0; i < MAX_POLLS; i++) {
          await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));

          const job = await agentChatService.pollJob(job_id);

          // Update placeholder with intermediate tool executions
          if (job.tool_executions && job.tool_executions.length > 0) {
            set((state) => {
              const idx = state.messages.findIndex(
                (m) => m.id === placeholderId
              );
              if (idx !== -1) {
                state.messages[idx].toolExecutions = job.tool_executions!.map(
                  (te) => ({
                    id: te.id,
                    toolName: te.tool_name,
                    toolDisplayName: te.tool_display_name,
                    args: te.args,
                    status: te.status as 'running' | 'completed' | 'failed',
                    result: te.result,
                    error: te.error,
                    durationMs: te.duration_ms,
                  })
                );
              }
            });
          }

          if (job.status === 'completed' && job.result) {
            const response = job.result;

            // Replace placeholder with final assistant message
            set((state) => {
              const idx = state.messages.findIndex(
                (m) => m.id === placeholderId
              );
              if (idx !== -1) {
                state.messages[idx] = {
                  id: placeholderId,
                  role: 'assistant',
                  content: response.message.content,
                  timestamp: new Date(response.timestamp),
                  isStreaming: false,
                  citations: response.retrieved_contexts?.map((ctx) => ({
                    documentId: ctx.document_id ?? '',
                    documentTitle: ctx.title,
                    snippet: ctx.content,
                    score: ctx.score,
                  })),
                  toolExecutions: response.tool_executions?.map((te) => ({
                    id: te.id,
                    toolName: te.tool_name,
                    toolDisplayName: te.tool_display_name,
                    args: te.args,
                    status: te.status as 'running' | 'completed' | 'failed',
                    result: te.result,
                    error: te.error,
                    durationMs: te.duration_ms,
                  })),
                };
              }
              state.isStreaming = false;
              state.activeThreadId = response.thread_id || state.activeThreadId;
            });

            // Mark unread if chat is closed
            if (uiMode === 'closed') {
              set((state) => {
                state.hasUnread = true;
              });
            }
            return;
          }

          if (job.status === 'failed') {
            set((state) => {
              const idx = state.messages.findIndex(
                (m) => m.id === placeholderId
              );
              if (idx !== -1) {
                state.messages[idx] = {
                  id: placeholderId,
                  role: 'assistant',
                  content:
                    job.error ||
                    'Sorry, something went wrong. Please try again.',
                  timestamp: new Date(),
                  isStreaming: false,
                };
              }
              state.isStreaming = false;
            });
            return;
          }
        }

        // Timeout: max polls exhausted
        set((state) => {
          const idx = state.messages.findIndex((m) => m.id === placeholderId);
          if (idx !== -1) {
            state.messages[idx] = {
              id: placeholderId,
              role: 'assistant',
              content:
                'The request timed out. The agent may still be processing — please try again shortly.',
              timestamp: new Date(),
              isStreaming: false,
            };
          }
          state.isStreaming = false;
        });
      } catch (error) {
        const errorMessage: AgentMessage = {
          id: `msg-${Date.now()}-error`,
          role: 'assistant',
          content: 'Sorry, something went wrong. Please try again.',
          timestamp: new Date(),
        };

        set((state) => {
          state.messages.push(errorMessage);
          state.isStreaming = false;
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
      set((state) => {
        state.isLoadingThreads = true;
      });

      try {
        const { agentChatService } =
          await import('@/services/agentChatService');
        const response = await agentChatService.listThreads();

        const threads: AgentThread[] = response.threads.map((t) => ({
          id: t.id,
          title: t.title ?? 'Untitled',
          createdAt: new Date(t.created_at),
          updatedAt: new Date(t.updated_at),
          messageCount: t.message_count,
          projectId: t.source_project_id ?? undefined,
        }));

        set((state) => {
          state.threads = threads;
          state.isLoadingThreads = false;
        });
      } catch (error) {
        console.error('Failed to load threads:', error);
        set((state) => {
          state.isLoadingThreads = false;
        });
      }
    },

    loadThreadMessages: async (threadId: string) => {
      set((state) => {
        state.isLoadingMessages = true;
      });

      try {
        const { agentChatService } =
          await import('@/services/agentChatService');
        const response = await agentChatService.getThreadMessages(threadId);

        const messages: AgentMessage[] = response.messages.map((m) => ({
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
          toolExecutions: m.tool_executions?.map((te) => ({
            id: te.id,
            toolName: te.tool_name,
            toolDisplayName: te.tool_display_name,
            args: te.args,
            status: te.status as 'running' | 'completed' | 'failed',
            result: te.result,
            error: te.error,
            durationMs: te.duration_ms,
          })),
          backendMessageId: m.id,
        }));

        set((state) => {
          state.messages = messages;
          state.activeThreadId = threadId;
          state.isLoadingMessages = false;
        });
      } catch (error) {
        console.error('Failed to load thread messages:', error);
        set((state) => {
          state.isLoadingMessages = false;
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
