import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';
import { getAppQueryClient } from '@/lib/query-client';
import type { AgentExecuteRequest } from '@/services/agentChatService';
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

/** Tools that mutate project data — triggers a refetch on the project page */
const PROJECT_MUTATING_TOOLS = new Set([
  'add_document_to_project',
  'ingest_arxiv_papers',
  'create_draft',
  'create_project_note',
]);

// Dual-cache reconciliation (docs/engineering/frontend.md, "Legacy
// server-state stores"): project-mutating agent tools bump
// projectDataVersion so the project page refetches its projectStore copy —
// but the context rail's Query copy (['project', id, …], 5-min staleTime)
// also needs invalidating. The /chat SSE path does this in useChatStreaming;
// this covers the global widget's own streaming paths. Same key scoping:
// narrow to the bound project when known, broad ['project'] otherwise.
function invalidateProjectQueries(projectId?: string): void {
  void getAppQueryClient()?.invalidateQueries({
    queryKey: projectId ? ['project', projectId] : ['project'],
  });
}

// Each thread load owns a monotonically increasing token. A late response must
// never replace the transcript selected after it started.
// Monotonic suffix for tool-execution ids: `Date.now()` alone collides for
// tools that start within the same millisecond, which duplicates React keys.
let toolExecutionSeq = 0;

let threadLoadEpoch = 0;

// Identity for the in-flight thread-list fetch. Module scope, unique token
// objects (not a counter) — mirrors pipelineStore.ts's pipelineRequestToken.
// There's only one thread list, so a single global token is enough to let a
// slower, superseded loadThreads() call detect it lost the race and drop its
// response instead of overwriting a newer one.
let loadThreadsToken: object | null = null;

interface AgentChatStore extends AgentChatState, AgentChatActions {
  /**
   * Internal: single ownership slot shared by sendMessage AND confirmAction —
   * whoever holds the live generation's controller owns the streaming state.
   * Invariant: every callback that writes shared state re-checks ownership
   * via a captured-identity closure (isCurrentGeneration) before writing;
   * every supersession path (stopGeneration/selectThread/newThread/confirm
   * takeover) aborts the old controller BEFORE reassigning this slot.
   */
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
  pendingConfirmations: {},
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
        const apiMessages: AgentExecuteRequest['messages'] =
          get().messages.flatMap((message) =>
            message.role === 'user' || message.role === 'assistant'
              ? [{ role: message.role, content: message.content }]
              : []
          );

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
            // Ownership check for EVERY stream callback: a superseded or
            // already-completed generation (stopGeneration, thread switch,
            // its own onDone releasing the slot) must not have late events
            // mutate state a newer generation now owns. Identity subsumes
            // the old signal.aborted check — a normally-completed stream
            // never aborts its own signal, so a trailing token frame after
            // onDone slipped past the abort flag.
            const isCurrentGeneration = (): boolean =>
              (get() as unknown as AgentChatStore)._abortController ===
              abortController;
            await agentChatService.streamMessage(
              requestPayload,
              {
                onTrace: (threadId: string) => {
                  if (!isCurrentGeneration()) return;
                  set((state) => {
                    if (!state.activeThreadId) state.activeThreadId = threadId;
                  });
                },
                onToken: (content: string) => {
                  if (!isCurrentGeneration()) return;
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
                  if (!isCurrentGeneration()) return;
                  set((state) => {
                    const idx = state.messages.findIndex(
                      (m) => m.id === placeholderId
                    );
                    if (idx !== -1) {
                      const existing = state.messages[idx].toolExecutions || [];
                      existing.push({
                        id: `te-${Date.now()}-${(toolExecutionSeq += 1)}`,
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
                onToolEnd: (tool: string, result: string, isError = false) => {
                  if (!isCurrentGeneration()) return;
                  set((state) => {
                    const idx = state.messages.findIndex(
                      (m) => m.id === placeholderId
                    );
                    if (idx !== -1) {
                      const execs = state.messages[idx].toolExecutions || [];
                      // Settle the newest still-running execution of this tool;
                      // falling back to the newest one at all keeps parallel
                      // same-tool calls from being dropped entirely.
                      const runningIdx = [...execs]
                        .reverse()
                        .findIndex(
                          (te) => te.toolName === tool && te.status === 'running'
                        );
                      const teIdx =
                        runningIdx !== -1
                          ? runningIdx
                          : [...execs]
                              .reverse()
                              .findIndex((te) => te.toolName === tool);
                      if (teIdx !== -1) {
                        const actualIdx = execs.length - 1 - teIdx;
                        // The service forwards the frame's is_error flag; a failed
                        // tool must not render as a completed one.
                        execs[actualIdx].status = isError ? 'failed' : 'completed';
                        if (isError) execs[actualIdx].error = result;
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
                // The event's second argument (the planner's rationale) is
                // deliberately ignored: the global sidebar renders plans as a
                // compact progress tracker, and this store doesn't rehydrate
                // plan provenance on reload (loadThreadMessages drops `plan`
                // too), so live-only reasoning would vanish on thread switch.
                // /chat is the surface that shows it. Thread it through
                // (AgentMessage field + both renderers) if this surface
                // should ever match.
                onPlan: (steps: Array<Record<string, unknown>>) => {
                  if (!isCurrentGeneration()) return;
                  set((state) => {
                    const plan = steps.map((s) => ({
                      step: (s.step as number) ?? 0,
                      description: (s.description as string) ?? '',
                      tool: (s.tool as string) ?? '',
                      args_hint: (s.args_hint as Record<string, unknown>) ?? {},
                      depends_on: (s.depends_on as number[]) ?? [],
                    }));
                    state.currentPlan = plan;
                    const idx = state.messages.findIndex(
                      (m) => m.id === placeholderId
                    );
                    if (idx !== -1) {
                      state.messages[idx].plan = plan;
                    }
                  });
                },
                onRagContext: (contexts: Array<Record<string, unknown>>) => {
                  if (!isCurrentGeneration()) return;
                  set((state) => {
                    const idx = state.messages.findIndex(
                      (m) => m.id === placeholderId
                    );
                    if (idx !== -1) {
                      state.messages[idx].citations = contexts.map((ctx) => ({
                        documentId:
                          (ctx.document_id as string | undefined) ?? '',
                        documentTitle:
                          (ctx.title as string | undefined) ?? 'Source',
                        snippet: ctx.content as string | undefined,
                        score: ctx.score as number | undefined,
                      }));
                    }
                  });
                },
                onReflection: (_passed, _issues, _round, revising) => {
                  if (!isCurrentGeneration()) return;
                  if (!revising) return;
                  streamedContent = '';
                  set((state) => {
                    const idx = state.messages.findIndex(
                      (m) => m.id === placeholderId
                    );
                    if (idx !== -1) {
                      state.messages[idx].content = '';
                    }
                  });
                },
                onConfirmation: (
                  threadId: string,
                  confirmation: Record<string, unknown>
                ) => {
                  if (!isCurrentGeneration()) {
                    // A parked HITL confirmation from a superseded generation
                    // is silently unrecoverable — the card never renders and
                    // the next turn wipes it. Log so the drop is observable
                    // (audit finding A, trace 019ff314-c29c) while keeping
                    // the guard, which prevents cross-thread corruption
                    // (PR #1223).
                    console.warn(
                      '[agentChatStore] dropped SSE confirmation: generation superseded',
                      { threadId }
                    );
                    return;
                  }
                  set((state) => {
                    const idx = state.messages.findIndex(
                      (m) => m.id === placeholderId
                    );
                    if (idx !== -1) {
                      state.messages[idx].isStreaming = false;
                      state.messages[idx].content =
                        'Waiting for your confirmation...';
                    }
                    state.pendingConfirmations[threadId] = {
                      threadId,
                      assistantMessageId: placeholderId,
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
                    (state as unknown as AgentChatStore)._abortController =
                      null;
                  });
                },
                onDone: () => {
                  if (!isCurrentGeneration()) return;
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
                    (state as unknown as AgentChatStore)._abortController =
                      null;
                  });
                  if (didMutateProjectData) {
                    invalidateProjectQueries(pageContext.projectId);
                  }
                  if (uiMode === 'closed') {
                    set((state) => {
                      state.hasUnread = true;
                    });
                  }
                },
                onError: (error: string) => {
                  if (!isCurrentGeneration()) return;
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
                  if (didMutateProjectData) {
                    invalidateProjectQueries(pageContext.projectId);
                  }
                },
              },
              abortController.signal
            );
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

        // Durable Trigger.dev fallback
        const { runId } =
          await agentChatService.startDurableRun(requestPayload);
        set((state) => {
          state.messages.push({
            id: placeholderId,
            role: 'assistant',
            content: '',
            timestamp: new Date(),
            isStreaming: true,
          });
        });

        const MAX_POLLS = 200;
        const POLL_INTERVAL_MS = 3000;

        // src/trigger/agent/execute-agent.ts (repo root — the Trigger.dev
        // task this poll actually observes) publishes metadata.status =
        // 'awaiting_confirmation' synchronously and only sets waitTokenId
        // after awaiting wait.createToken() — a real, short async race
        // window where this poll can land on a tokenless snapshot. Every
        // run reaching this task DOES eventually get a token (deterministic
        // in that file), so surfacing the tokenless snapshot as-is would be
        // permanent and unresumable: confirmAction has no token to complete
        // and this loop never re-polls once it returns. Tolerate a couple
        // of extra ticks for the token to land; only surface tokenless as a
        // fail-safe if it still hasn't shown up after that (never silently
        // drop a parked confirmation — the original bug, audit finding A,
        // trace 019ff314-c29c).
        const MAX_TOKENLESS_TICKS = 2;
        let tokenlessTicks = 0;

        for (let i = 0; i < MAX_POLLS; i++) {
          if (abortController.signal.aborted) return;
          await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
          if (abortController.signal.aborted) return;

          const run = await agentChatService.getDurableRunStatus(runId);
          const meta = run.metadata ?? {};

          if (meta.status === 'awaiting_confirmation') {
            const hasToken = typeof meta.waitTokenId === 'string';
            if (!hasToken && tokenlessTicks < MAX_TOKENLESS_TICKS) {
              tokenlessTicks += 1;
              continue;
            }
            const ownerThreadId =
              requestPayload.thread_id ??
              (typeof meta.threadId === 'string' ? meta.threadId : undefined);
            if (!ownerThreadId) {
              throw new Error('Durable confirmation is missing its thread id');
            }
            set((state) => {
              state.activeThreadId ??= ownerThreadId;
              state.pendingConfirmations[ownerThreadId] = {
                threadId: ownerThreadId,
                assistantMessageId: placeholderId,
                jobId: runId,
                tools:
                  ((meta.confirmation as Record<string, unknown>)?.tools as
                    | Array<{ name: string; args: Record<string, unknown> }>
                    | undefined) ?? [],
                message:
                  ((meta.confirmation as Record<string, unknown>)
                    ?.message as string) ||
                  'The agent wants to perform an action. Please confirm.',
                ...(hasToken
                  ? { waitTokenId: meta.waitTokenId as string }
                  : {}),
              };
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

          if (run.status === 'COMPLETED' && run.output) {
            const result = run.output as Record<string, unknown>;
            const content =
              (result.result as Record<string, unknown>)?.message ??
              result.status ??
              'Done';
            set((state) => {
              const idx = state.messages.findIndex(
                (m) => m.id === placeholderId
              );
              if (idx !== -1) {
                state.messages[idx].content = String(content);
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
            return;
          }

          if (run.status === 'FAILED' || run.status === 'CRASHED') {
            set((state) => {
              const idx = state.messages.findIndex(
                (m) => m.id === placeholderId
              );
              if (idx !== -1) {
                state.messages[idx] = {
                  id: placeholderId,
                  role: 'assistant',
                  content:
                    run.error ||
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

        // Timeout
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

    confirmAction: async (threadId: string, confirmed: boolean) => {
      const pendingConfirmation = get().pendingConfirmations[threadId];
      if (!pendingConfirmation) return;
      if (get().activeThreadId !== threadId) return;

      const jobId = pendingConfirmation.jobId;
      // Capture the durable wait token NOW: the set() below removes this
      // thread's pending confirmation, so re-reading it in the fallback
      // branch (after streamConfirm fails) would always be undefined —
      // silently skipping completeDurableConfirmation and mis-routing a
      // durable-run approval to the legacy /confirm endpoint, which fails and
      // leaves the run waiting on its token forever.
      const waitTokenId = pendingConfirmation.waitTokenId;

      // Single-ownership: confirmAction now shares the _abortController slot
      // with sendMessage. If one is somehow already in flight, supersede it
      // the same way stopGeneration would, then take ownership.
      const previousController = (get() as unknown as AgentChatStore)
        ._abortController;
      if (previousController) previousController.abort();
      const abortController = new AbortController();

      // Capture identity ONCE, before any await: which thread and message
      // this confirmation belongs to. Every later callback must resolve
      // state via these captured values, never via "current last assistant
      // message" — the user can switch threads mid-confirm, and the newly
      // visible thread's last assistant message would then belong to a
      // different conversation entirely (cross-thread corruption).
      const confirmThreadId = pendingConfirmation.threadId;
      const targetMessageId = pendingConfirmation.assistantMessageId;
      // The thread-id clause is defense-in-depth: today every thread switch
      // also nulls _abortController synchronously, so the identity check
      // alone would catch it — kept in case controller-nulling and
      // thread-switch ever decouple.
      const isCurrentGeneration = (): boolean =>
        (get() as unknown as AgentChatStore)._abortController ===
          abortController && get().activeThreadId === confirmThreadId;

      set((state) => {
        state.isConfirming = true;
        state.isStreaming = true;
        (state as unknown as AgentChatStore)._abortController = abortController;
        // Update the waiting message to show streaming
        let idx = state.messages.findIndex((m) => m.id === targetMessageId);
        if (idx === -1) {
          state.messages.push({
            id: targetMessageId,
            role: 'assistant',
            content: '',
            timestamp: new Date(),
            isStreaming: true,
          });
          idx = state.messages.length - 1;
        }
        if (idx !== -1) {
          state.messages[idx].isStreaming = true;
          state.messages[idx].content = '';
        }
        delete state.pendingConfirmations[threadId];
      });

      try {
        const { agentChatService, isTerminalJobStatus } =
          await import('@/services/agentChatService');

        // Try SSE streaming confirm first
        let streamedContent = '';
        let didMutateProjectData = false;

        try {
          await agentChatService.streamConfirm(
            { thread_id: jobId, confirmed },
            {
              onToken: (content: string) => {
                if (!isCurrentGeneration()) return;
                streamedContent += content;
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === targetMessageId
                  );
                  if (idx !== -1) {
                    state.messages[idx].content = streamedContent;
                  }
                });
              },
              onToolStart: (tool: string) => {
                if (!isCurrentGeneration()) return;
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === targetMessageId
                  );
                  if (idx !== -1) {
                    const existing = state.messages[idx].toolExecutions || [];
                    existing.push({
                      id: `te-${Date.now()}-${(toolExecutionSeq += 1)}`,
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
              onToolEnd: (tool: string, result: string, isError = false) => {
                if (!isCurrentGeneration()) return;
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === targetMessageId
                  );
                  if (idx !== -1) {
                    const execs = state.messages[idx].toolExecutions || [];
                    // Settle the newest still-running execution of this tool;
                    // falling back to the newest one at all keeps parallel
                    // same-tool calls from being dropped entirely.
                    const runningIdx = [...execs]
                      .reverse()
                      .findIndex(
                        (te) => te.toolName === tool && te.status === 'running'
                      );
                    const teIdx =
                      runningIdx !== -1
                        ? runningIdx
                        : [...execs]
                            .reverse()
                            .findIndex((te) => te.toolName === tool);
                    if (teIdx !== -1) {
                      const actualIdx = execs.length - 1 - teIdx;
                      // The service forwards the frame's is_error flag; a failed
                      // tool must not render as a completed one.
                      execs[actualIdx].status = isError ? 'failed' : 'completed';
                      if (isError) execs[actualIdx].error = result;
                      try {
                        execs[actualIdx].result = JSON.parse(result);
                      } catch {
                        execs[actualIdx].result = result;
                      }
                    }
                  }
                  if (PROJECT_MUTATING_TOOLS.has(tool)) {
                    didMutateProjectData = true;
                  }
                });
              },
              // Second argument (planner rationale) deliberately ignored —
              // same reasoning as the onPlan above.
              onPlan: (steps: Array<Record<string, unknown>>) => {
                if (!isCurrentGeneration()) return;
                set((state) => {
                  const plan = steps.map((s) => ({
                    step: (s.step as number) ?? 0,
                    description: (s.description as string) ?? '',
                    tool: (s.tool as string) ?? '',
                    args_hint: (s.args_hint as Record<string, unknown>) ?? {},
                    depends_on: (s.depends_on as number[]) ?? [],
                  }));
                  state.currentPlan = plan;
                  const idx = state.messages.findIndex(
                    (m) => m.id === targetMessageId
                  );
                  if (idx !== -1) {
                    state.messages[idx].plan = plan;
                  }
                });
              },
              onRagContext: (contexts: Array<Record<string, unknown>>) => {
                if (!isCurrentGeneration()) return;
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === targetMessageId
                  );
                  if (idx !== -1) {
                    state.messages[idx].citations = contexts.map((ctx) => ({
                      documentId: (ctx.document_id as string | undefined) ?? '',
                      documentTitle:
                        (ctx.title as string | undefined) ?? 'Source',
                      snippet: ctx.content as string | undefined,
                      score: ctx.score as number | undefined,
                    }));
                  }
                });
              },
              onReflection: (_passed, _issues, _round, revising) => {
                if (!isCurrentGeneration()) return;
                if (!revising) return;
                streamedContent = '';
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === targetMessageId
                  );
                  if (idx !== -1) {
                    state.messages[idx].content = '';
                  }
                });
              },
              onConfirmation: (
                threadId: string,
                confirmation: Record<string, unknown>
              ) => {
                // Nested confirmation (e.g. ingest confirmed → add needs confirm)
                if (!isCurrentGeneration()) {
                  console.warn(
                    '[agentChatStore] dropped nested SSE confirmation: generation superseded',
                    { threadId }
                  );
                  return;
                }
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === targetMessageId
                  );
                  if (idx !== -1) {
                    state.messages[idx].isStreaming = false;
                    state.messages[idx].content =
                      'Waiting for your confirmation...';
                  }
                  state.pendingConfirmations[threadId] = {
                    threadId,
                    assistantMessageId: targetMessageId,
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
                  (state as unknown as AgentChatStore)._abortController = null;
                });
              },
              onDone: () => {
                if (!isCurrentGeneration()) return;
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === targetMessageId
                  );
                  if (idx !== -1) {
                    state.messages[idx].isStreaming = false;
                  }
                  state.isStreaming = false;
                  state.isConfirming = false;
                  state.currentPlan = null;
                  if (didMutateProjectData) {
                    state.projectDataVersion += 1;
                  }
                  (state as unknown as AgentChatStore)._abortController = null;
                });
                if (didMutateProjectData) {
                  invalidateProjectQueries(get().pageContext.projectId);
                }
              },
              onError: (error: string) => {
                if (!isCurrentGeneration()) return;
                set((state) => {
                  const idx = state.messages.findIndex(
                    (m) => m.id === targetMessageId
                  );
                  if (idx !== -1) {
                    state.messages[idx].content =
                      streamedContent || error || 'Action failed.';
                    state.messages[idx].isStreaming = false;
                  }
                  state.isStreaming = false;
                  state.isConfirming = false;
                  state.pendingConfirmations[threadId] = pendingConfirmation;
                  (state as unknown as AgentChatStore)._abortController = null;
                });
              },
            },
            abortController.signal
          );
          if (abortController.signal.aborted) {
            set((state) => {
              state.pendingConfirmations[threadId] ??= pendingConfirmation;
              const store = state as unknown as AgentChatStore;
              if (store._abortController !== abortController) return;
              state.isStreaming = false;
              state.isConfirming = false;
              store._abortController = null;
            });
          }
          return; // SSE confirm succeeded
        } catch {
          // SSE confirm failed — fall back to polling
        }

        // Durable run or legacy polling fallback. waitTokenId was captured
        // up-front (before pendingConfirmation was nulled) so this branch is
        // actually reachable for durable runs.
        if (waitTokenId) {
          await agentChatService.completeDurableConfirmation(
            jobId,
            waitTokenId,
            confirmed
          );

          const MAX_POLLS = 200;
          const POLL_INTERVAL_MS = 3000;
          for (let i = 0; i < MAX_POLLS; i++) {
            if (abortController.signal.aborted) return;
            await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
            if (abortController.signal.aborted) return;
            const run = await agentChatService.getDurableRunStatus(jobId);
            // Re-check AFTER the network await: selectThread/newThread can
            // abort + swap the transcript while the poll was in flight, and
            // the branches below resolve "last assistant message" from
            // CURRENT state — without this, thread A's result writes into
            // thread B's message. (Unlike the SSE branch, the poll branches
            // deliberately do NOT anchor to the captured targetMessageId: a
            // same-thread reload can replace message ids, so once thread
            // identity is confirmed, "current last assistant" is the only
            // stable anchor.)
            if (!isCurrentGeneration()) return;

            if (run.status === 'COMPLETED' && run.output) {
              const result = run.output as Record<string, unknown>;
              const content =
                (result.result as Record<string, unknown>)?.message ??
                result.status ??
                'Done';
              set((state) => {
                const lastAsst = [...state.messages]
                  .reverse()
                  .find((m) => m.role === 'assistant');
                if (lastAsst) {
                  const idx = state.messages.findIndex(
                    (m) => m.id === lastAsst.id
                  );
                  if (idx !== -1) {
                    state.messages[idx].content = String(content);
                    state.messages[idx].isStreaming = false;
                  }
                }
                state.isStreaming = false;
                delete state.pendingConfirmations[threadId];
                state.isConfirming = false;
              });
              return;
            }
            if (run.status === 'FAILED' || run.status === 'CRASHED') {
              set((state) => {
                const lastAsst = [...state.messages]
                  .reverse()
                  .find((m) => m.role === 'assistant');
                if (lastAsst) {
                  const idx = state.messages.findIndex(
                    (m) => m.id === lastAsst.id
                  );
                  if (idx !== -1) {
                    state.messages[idx].content = run.error || 'Action failed.';
                    state.messages[idx].isStreaming = false;
                  }
                }
                state.isStreaming = false;
                delete state.pendingConfirmations[threadId];
                state.isConfirming = false;
              });
              return;
            }
          }
        } else {
          // Legacy polling fallback for SSE-originated confirmations
          await agentChatService.confirmAction(jobId, confirmed);

          const MAX_POLLS = 120;
          const POLL_INTERVAL_MS = 1500;
          for (let i = 0; i < MAX_POLLS; i++) {
            if (abortController.signal.aborted) return;
            await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
            if (abortController.signal.aborted) return;
            const job = await agentChatService.pollJob(jobId);
            // Same post-await re-check as the durable loop above.
            if (!isCurrentGeneration()) return;

            if (job.status === 'completed' && job.result) {
              const hasMutation =
                job.result.tool_executions?.some((te) =>
                  PROJECT_MUTATING_TOOLS.has(te.tool_name)
                ) ?? false;
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
                delete state.pendingConfirmations[threadId];
                state.isConfirming = false;

                if (hasMutation) {
                  state.projectDataVersion += 1;
                }
              });
              if (hasMutation) {
                invalidateProjectQueries(get().pageContext.projectId);
              }
              return;
            }
            // Any other terminal state (failed / error / cancelled / a
            // completed job whose result payload is missing) — stop polling
            // and surface the failure. The old hand-listed check only knew
            // 'failed', so 'error' and 'cancelled' jobs spun for the full
            // poll budget with a stuck spinner (audit C7).
            if (isTerminalJobStatus(job.status)) {
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
                delete state.pendingConfirmations[threadId];
                state.isConfirming = false;
              });
              return;
            }
          }
        }
      } catch {
        // If superseded (stopGeneration / thread switch already aborted this
        // generation), its own reset already ran — don't clobber whatever
        // owns the slot now. Mirrors sendMessage's outer catch guard.
        if (abortController.signal.aborted) {
          set((state) => {
            state.pendingConfirmations[threadId] ??= pendingConfirmation;
          });
          return;
        }
        set((state) => {
          state.isStreaming = false;
          state.isConfirming = false;
          state.pendingConfirmations[threadId] = pendingConfirmation;
          const idx = state.messages.findIndex(
            (message) => message.id === targetMessageId
          );
          if (idx !== -1) {
            state.messages[idx].isStreaming = false;
            state.messages[idx].content = 'Waiting for your confirmation...';
          }
          (state as unknown as AgentChatStore)._abortController = null;
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
        state.pendingConfirmations = {};
        state.currentPlan = null;
        (state as unknown as AgentChatStore)._abortController = null;
      }),

    // Threads
    newThread: () =>
      set((state) => {
        threadLoadEpoch += 1;
        // A sendMessage/confirmAction generation left running against the
        // thread we're navigating away from must not keep streaming into
        // (or clobbering state for) the blank thread we're about to show.
        // Mirrors stopGeneration's abort + reset.
        const store = state as unknown as AgentChatStore;
        if (store._abortController) {
          store._abortController.abort();
          store._abortController = null;
        }
        state.activeThreadId = null;
        state.messages = [];
        state.inputValue = '';
        state.isLoadingMessages = false;
        state.isStreaming = false;
        state.isConfirming = false;
      }),

    selectThread: (threadId: string) =>
      set((state) => {
        threadLoadEpoch += 1;
        // See newThread — abort whatever generation is in flight before
        // switching the visible thread out from under it.
        const store = state as unknown as AgentChatStore;
        if (store._abortController) {
          store._abortController.abort();
          store._abortController = null;
        }
        state.activeThreadId = threadId;
        state.messages = [];
        state.isLoadingMessages = true;
        state.isStreaming = false;
        state.isConfirming = false;
      }),

    loadThreads: async () => {
      // Unique token identity (not a counter) — a slower, superseded call
      // must detect it lost the race and drop its response. See
      // loadThreadsToken above / pipelineStore.ts's pipelineRequestToken.
      const requestToken = {};
      loadThreadsToken = requestToken;

      set((state) => {
        state.isLoadingThreads = true;
      });

      try {
        const { agentChatService } =
          await import('@/services/agentChatService');
        const response = await agentChatService.listThreads();
        if (loadThreadsToken !== requestToken) return; // superseded

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
        if (loadThreadsToken !== requestToken) return; // superseded
        console.error('Failed to load threads:', error);
        set((state) => {
          state.isLoadingThreads = false;
        });
      }
    },

    loadThreadMessages: async (threadId: string) => {
      const loadEpoch = ++threadLoadEpoch;
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

        if (
          loadEpoch !== threadLoadEpoch ||
          get().activeThreadId !== threadId
        ) {
          return;
        }

        set((state) => {
          state.messages = messages;
          state.activeThreadId = threadId;
          state.isLoadingMessages = false;
        });
      } catch (error) {
        console.error('Failed to load thread messages:', error);
        if (
          loadEpoch !== threadLoadEpoch ||
          get().activeThreadId !== threadId
        ) {
          return;
        }
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
