import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import type {
  AgentChatState,
  AgentChatActions,
  AgentMessage,
  AgentThread,
  PageContext,
  PlanStep,
} from '@/types/agent-chat';

const DEFAULT_PAGE_CONTEXT: PageContext = {
  type: 'unknown',
  label: 'Dashboard',
};

/** Tools that mutate project data — triggers a refetch on the project page */
const PROJECT_MUTATING_TOOLS = new Set([
  'add_document_to_project',
  'ingest_arxiv_papers',
  'create_draft',
  'create_project_note',
]);

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
  projectDataVersion: 0,
  currentPlan: null,
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
        let didMutateProjectData = false;

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
                if (PROJECT_MUTATING_TOOLS.has(tool)) {
                  didMutateProjectData = true;
                }
              },
              onPlan: (steps: Array<Record<string, unknown>>) => {
                set((state) => {
                  state.currentPlan = steps.map((s) => ({
                    step: (s.step as number) ?? 0,
                    description: (s.description as string) ?? '',
                    tool: (s.tool as string) ?? '',
                    args_hint: (s.args_hint as Record<string, unknown>) ?? {},
                    depends_on: (s.depends_on as number[]) ?? [],
                  }));
                });
              },
              onReflection: () => {
                // Reflection events are informational; no store mutation needed
                // beyond what onDone handles.
              },
              onConfirmation: (
                threadId: string,
                confirmation: Record<string, unknown>
              ) => {
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === placeholderId
                  );
                  if (idx !== -1) {
                    state.messages[idx].isStreaming = false;
                    state.messages[idx].content =
                      'Waiting for your confirmation...';
                  }
                  state.pendingConfirmation = {
                    jobId: threadId, // thread_id used as job identifier for SSE
                    tools:
                      (confirmation.tools as Array<{
                        name: string;
                        args: Record<string, unknown>;
                      }>) || [],
                    message:
                      (confirmation.message as string) ||
                      'The agent wants to perform an action. Please confirm.',
                  };
                  state.isStreaming = false;
                  (state as unknown as AgentChatStore)._abortController = null;
                });
              },
              onDone: () => {
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === placeholderId
                  );
                  if (idx !== -1) {
                    state.messages[idx].isStreaming = false;
                    if (didMutateProjectData) {
                      state.projectDataVersion += 1;
                    }
                  }
                  state.isStreaming = false;
                  state.currentPlan = null;
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
                  if (didMutateProjectData) {
                    state.projectDataVersion += 1;
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

              // Bump projectDataVersion if any mutating tools ran
              const hasMutation = response.tool_executions?.some((te) =>
                PROJECT_MUTATING_TOOLS.has(te.tool_name)
              );
              if (hasMutation) {
                state.projectDataVersion += 1;
              }
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
        // Update the waiting message to show streaming
        const lastAsst = [...state.messages]
          .reverse()
          .find((m) => m.role === 'assistant');
        if (lastAsst) {
          const idx = state.messages.findIndex((m) => m.id === lastAsst.id);
          if (idx !== -1) {
            state.messages[idx].isStreaming = true;
            state.messages[idx].content = '';
          }
        }
        state.pendingConfirmation = null;
      });

      try {
        const { agentChatService } =
          await import('@/services/agentChatService');

        // Try SSE streaming confirm first
        let streamedContent = '';
        let didMutateProjectData = false;

        try {
          await agentChatService.streamConfirm(
            { thread_id: jobId, confirmed },
            {
              onToken: (content: string) => {
                streamedContent += content;
                set((state) => {
                  const lastAsst = [...state.messages]
                    .reverse()
                    .find((m) => m.role === 'assistant');
                  if (lastAsst) {
                    const idx = state.messages.findIndex(
                      (m) => m.id === lastAsst.id
                    );
                    if (idx !== -1) {
                      state.messages[idx].content = streamedContent;
                    }
                  }
                });
              },
              onToolStart: (tool: string) => {
                set((state) => {
                  const lastAsst = [...state.messages]
                    .reverse()
                    .find((m) => m.role === 'assistant');
                  if (lastAsst) {
                    const idx = state.messages.findIndex(
                      (m) => m.id === lastAsst.id
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
                  }
                });
              },
              onToolEnd: (tool: string, result: string) => {
                set((state) => {
                  const lastAsst = [...state.messages]
                    .reverse()
                    .find((m) => m.role === 'assistant');
                  if (lastAsst) {
                    const idx = state.messages.findIndex(
                      (m) => m.id === lastAsst.id
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
                  }
                  if (PROJECT_MUTATING_TOOLS.has(tool)) {
                    didMutateProjectData = true;
                  }
                });
              },
              onConfirmation: (
                threadId: string,
                confirmation: Record<string, unknown>
              ) => {
                // Nested confirmation (e.g. ingest confirmed → add needs confirm)
                set((state) => {
                  const lastAsst = [...state.messages]
                    .reverse()
                    .find((m) => m.role === 'assistant');
                  if (lastAsst) {
                    const idx = state.messages.findIndex(
                      (m) => m.id === lastAsst.id
                    );
                    if (idx !== -1) {
                      state.messages[idx].isStreaming = false;
                      state.messages[idx].content =
                        'Waiting for your confirmation...';
                    }
                  }
                  state.pendingConfirmation = {
                    jobId: threadId,
                    tools:
                      (confirmation.tools as Array<{
                        name: string;
                        args: Record<string, unknown>;
                      }>) || [],
                    message:
                      (confirmation.message as string) ||
                      'The agent wants to perform an action. Please confirm.',
                  };
                  state.isStreaming = false;
                  state.isConfirming = false;
                });
              },
              onDone: () => {
                set((state) => {
                  const lastAsst = [...state.messages]
                    .reverse()
                    .find((m) => m.role === 'assistant');
                  if (lastAsst) {
                    const idx = state.messages.findIndex(
                      (m) => m.id === lastAsst.id
                    );
                    if (idx !== -1) {
                      state.messages[idx].isStreaming = false;
                    }
                  }
                  state.isStreaming = false;
                  state.isConfirming = false;
                  state.currentPlan = null;
                  if (didMutateProjectData) {
                    state.projectDataVersion += 1;
                  }
                });
              },
              onError: (error: string) => {
                set((state) => {
                  const lastAsst = [...state.messages]
                    .reverse()
                    .find((m) => m.role === 'assistant');
                  if (lastAsst) {
                    const idx = state.messages.findIndex(
                      (m) => m.id === lastAsst.id
                    );
                    if (idx !== -1) {
                      state.messages[idx].content =
                        streamedContent || error || 'Action failed.';
                      state.messages[idx].isStreaming = false;
                    }
                  }
                  state.isStreaming = false;
                  state.isConfirming = false;
                });
              },
            }
          );
          return; // SSE confirm succeeded
        } catch {
          // SSE confirm failed — fall back to polling
        }

        // Polling fallback
        await agentChatService.confirmAction(jobId, confirmed);

        const MAX_POLLS = 120;
        const POLL_INTERVAL_MS = 1500;
        for (let i = 0; i < MAX_POLLS; i++) {
          await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
          const job = await agentChatService.pollJob(jobId);

          if (job.status === 'completed' && job.result) {
            set((state) => {
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

              const hasMutation = job.result!.tool_executions?.some((te) =>
                PROJECT_MUTATING_TOOLS.has(te.tool_name)
              );
              if (hasMutation) {
                state.projectDataVersion += 1;
              }
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
        state.currentPlan = null;
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
