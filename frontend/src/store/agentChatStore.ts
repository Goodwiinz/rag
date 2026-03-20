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
  /** Internal: AbortController for current polling loop */
  _abortController: AbortController | null;
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
  pendingConfirmation: null,
  isConfirming: false,
};

export const useAgentChatStore = create<AgentChatStore>()(
  immer((set, get) => ({
    ...initialState,
    _abortController: null,

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

      // Create AbortController for this generation
      const abortController = new AbortController();

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
        (state as unknown as AgentChatStore)._abortController = abortController;
      });

      try {
        const { agentChatService } =
          await import('@/services/agentChatService');

        // Build messages array for the API (only user/assistant roles)
        const apiMessages = get()
          .messages.filter((m) => m.role === 'user' || m.role === 'assistant')
          .map((m) => ({ role: m.role, content: m.content }));

        const requestPayload = {
          messages: apiMessages,
          page_context: {
            type: pageContext.type,
            project_id: pageContext.projectId,
            project_name: pageContext.projectName,
            label: pageContext.label,
            metadata: pageContext.metadata,
          },
          thread_id: activeThreadId ?? undefined,
        };

        // Step 2: Add a streaming placeholder message
        const placeholderId = `msg-${Date.now()}-assistant`;

        // Try SSE streaming first, fall back to polling
        let useStreaming = true;
        if (useStreaming) {
          set((state) => {
            state.messages.push({
              id: placeholderId,
              role: 'assistant',
              content: '',
              timestamp: new Date(),
              isStreaming: true,
            });
          });

          try {
            let streamedContent = '';
            await agentChatService.streamMessage(requestPayload, {
              onToken: (content: string) => {
                if (abortController.signal.aborted) return;
                streamedContent += content;
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === placeholderId
                  );
                  if (idx !== -1) {
                    state.messages[idx].content = streamedContent;
                  }
                });
              },
              onToolStart: (tool: string) => {
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === placeholderId
                  );
                  if (idx !== -1) {
                    const existing = state.messages[idx].toolExecutions || [];
                    existing.push({
                      id: `te-${Date.now()}`,
                      toolName: tool,
                      toolDisplayName: tool
                        .replace(/_/g, ' ')
                        .replace(/\b\w/g, (c) => c.toUpperCase()),
                      args: {},
                      status: 'running',
                    });
                    state.messages[idx].toolExecutions = existing;
                  }
                });
              },
              onToolEnd: (tool: string, result: string) => {
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === placeholderId
                  );
                  if (idx !== -1) {
                    const execs = state.messages[idx].toolExecutions || [];
                    const teIdx = [...execs]
                      .reverse()
                      .findIndex((te) => te.toolName === tool);
                    if (teIdx !== -1) {
                      const actualIdx = execs.length - 1 - teIdx;
                      execs[actualIdx].status = 'completed';
                      try {
                        execs[actualIdx].result = JSON.parse(result);
                      } catch {
                        execs[actualIdx].result = result;
                      }
                    }
                  }
                });
              },
              onDone: () => {
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === placeholderId
                  );
                  if (idx !== -1) {
                    state.messages[idx].isStreaming = false;
                  }
                  state.isStreaming = false;
                  (state as unknown as AgentChatStore)._abortController = null;
                });
                if (uiMode === 'closed') {
                  set((state) => {
                    state.hasUnread = true;
                  });
                }
              },
              onError: (error: string) => {
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === placeholderId
                  );
                  if (idx !== -1) {
                    state.messages[idx].content =
                      streamedContent || error || 'An error occurred.';
                    state.messages[idx].isStreaming = false;
                    state.messages[idx].isError = !streamedContent;
                  }
                  state.isStreaming = false;
                });
              },
            });
            return; // SSE streaming succeeded
          } catch {
            // SSE failed — fall back to polling below
            // Remove the placeholder if it's still empty
            const msgs = get().messages;
            const placeholder = msgs.find((m) => m.id === placeholderId);
            if (placeholder && !placeholder.content) {
              set((state) => {
                state.messages = state.messages.filter(
                  (m) => m.id !== placeholderId
                );
              });
            }
            useStreaming = false;
          }
        }

        // Polling fallback
        // Step 1: Start the async job
        const { job_id } = await agentChatService.startJob(requestPayload);
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
          // Check if generation was stopped
          if (abortController.signal.aborted) return;

          await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));

          // Check again after sleep
          if (abortController.signal.aborted) return;

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

          if (job.status === 'awaiting_confirmation' && job.confirmation) {
            set((state) => {
              state.pendingConfirmation = {
                jobId: job_id,
                tools: job.confirmation!.tools || [],
                message:
                  job.confirmation!.message ||
                  'The agent wants to perform an action. Please confirm.',
              };
              // Keep streaming indicator but stop the poll loop
              const idx = state.messages.findIndex(
                (m) => m.id === placeholderId
              );
              if (idx !== -1) {
                state.messages[idx].isStreaming = false;
                state.messages[idx].content =
                  'Waiting for your confirmation...';
              }
              state.isStreaming = false;
            });
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
                  isError: true,
                };
              }
              state.isStreaming = false;
              (state as unknown as AgentChatStore)._abortController = null;
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
              isError: true,
            };
          }
          state.isStreaming = false;
          (state as unknown as AgentChatStore)._abortController = null;
        });
      } catch (error) {
        // If aborted, don't add an error message
        if (abortController.signal.aborted) return;

        const errorMessage: AgentMessage = {
          id: `msg-${Date.now()}-error`,
          role: 'assistant',
          content: 'Sorry, something went wrong. Please try again.',
          timestamp: new Date(),
          isError: true,
        };

        set((state) => {
          state.messages.push(errorMessage);
          state.isStreaming = false;
          (state as unknown as AgentChatStore)._abortController = null;
        });
      }
    },

    confirmAction: async (confirmed: boolean) => {
      const { pendingConfirmation } = get();
      if (!pendingConfirmation) return;

      const jobId = pendingConfirmation.jobId;

      set((state) => {
        state.isConfirming = true;
        state.isStreaming = true;
      });

      try {
        const { agentChatService } =
          await import('@/services/agentChatService');
        await agentChatService.confirmAction(jobId, confirmed);

        // Resume polling for the confirmed job
        const MAX_POLLS = 120;
        const POLL_INTERVAL_MS = 1500;
        for (let i = 0; i < MAX_POLLS; i++) {
          await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
          const job = await agentChatService.pollJob(jobId);

          if (job.status === 'completed' && job.result) {
            set((state) => {
              // Find the last assistant message and update it
              const lastAsst = [...state.messages]
                .reverse()
                .find((m) => m.role === 'assistant');
              if (lastAsst) {
                const idx = state.messages.findIndex(
                  (m) => m.id === lastAsst.id
                );
                if (idx !== -1) {
                  state.messages[idx].content = job.result!.message.content;
                  state.messages[idx].isStreaming = false;
                  state.messages[idx].toolExecutions =
                    job.result!.tool_executions?.map((te) => ({
                      id: te.id,
                      toolName: te.tool_name,
                      toolDisplayName: te.tool_display_name,
                      args: te.args,
                      status: te.status as 'running' | 'completed' | 'failed',
                      result: te.result,
                      error: te.error,
                      durationMs: te.duration_ms,
                    }));
                }
              }
              state.isStreaming = false;
              state.pendingConfirmation = null;
              state.isConfirming = false;
            });
            return;
          }
          if (job.status === 'failed') {
            set((state) => {
              const lastAsst = [...state.messages]
                .reverse()
                .find((m) => m.role === 'assistant');
              if (lastAsst) {
                const idx = state.messages.findIndex(
                  (m) => m.id === lastAsst.id
                );
                if (idx !== -1) {
                  state.messages[idx].content = job.error || 'Action failed.';
                  state.messages[idx].isStreaming = false;
                }
              }
              state.isStreaming = false;
              state.pendingConfirmation = null;
              state.isConfirming = false;
            });
            return;
          }
        }
      } catch {
        set((state) => {
          state.isStreaming = false;
          state.isConfirming = false;
          state.pendingConfirmation = null;
        });
      }
    },

    stopGeneration: () => {
      const ctrl = (get() as unknown as AgentChatStore)._abortController;
      if (ctrl) ctrl.abort();

      set((state) => {
        // Mark the last assistant message as stopped
        const lastAsst = [...state.messages]
          .reverse()
          .find((m) => m.role === 'assistant');
        if (lastAsst) {
          const idx = state.messages.findIndex((m) => m.id === lastAsst.id);
          if (idx !== -1) {
            state.messages[idx].isStreaming = false;
            if (!state.messages[idx].content) {
              state.messages[idx].content = 'Generation stopped.';
            }
          }
        }
        state.isStreaming = false;
        (state as unknown as AgentChatStore)._abortController = null;
      });
    },

    retryLastMessage: () => {
      const { messages, isStreaming } = get();
      if (isStreaming) return;

      // Find the last user message
      const lastUserIdx = [...messages]
        .map((m, i) => ({ m, i }))
        .reverse()
        .find(({ m }) => m.role === 'user');
      if (!lastUserIdx) return;

      const lastUserContent = lastUserIdx.m.content;

      // Remove all messages after the last user message (failed assistant response)
      set((state) => {
        state.messages = state.messages.slice(0, lastUserIdx.i);
        state.inputValue = lastUserContent;
      });

      // Re-send
      void get().sendMessage();
    },

    clearMessages: () =>
      set((state) => {
        state.messages = [];
        state.activeThreadId = null;
        state.isStreaming = false;
        state.pendingConfirmation = null;
        (state as unknown as AgentChatStore)._abortController = null;
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
