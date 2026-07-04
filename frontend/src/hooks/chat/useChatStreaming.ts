'use client';

import type {
  ActivityStep,
  ChatPageMessage,
} from '@/components/chat/shared/cloudMessageView';
import {
  summarizeToolArgs,
  summarizeToolResult,
} from '@/components/chat/shared/cloudMessageView';
import { getSelectedThreadUrl } from '@/components/chat/shared/chatNavigation';
import { buildThreadCreateRequest } from '@/components/chat/shared/threadCreation';
import {
  ChatConversation,
  generateConversationTitle,
} from '@/hooks/chat/chatTypes';
import { agentChatService } from '@/services/agentChatService';
import { workspaceService } from '@/services/workspaceService';
import {
  resolveBoundProjectId,
  selectCurrentThreadProjectId,
  useChatStore,
} from '@/store/chat-store';
import { useAgentActivityStore } from '@/stores/agentActivityStore';
import { toolLabel } from '@/components/context-rail/toolLabels';
import { deriveAgentName, deriveTask } from '@/components/context-rail';
import { Conversation as DBConversation, MessageRole } from '@/types/workspace';
import type { CitationCreate } from '@/types/workspace';
import { normalizeCitation } from '@/utils/citationNormalizer';
import { useQueryClient } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useProjectStore } from '@/store/projectStore';
import type { ChatMessage as DBChatMessage } from '@/types/workspace';

// localStorage key for the workspace→agent thread map (see agentThreadMapRef).
const AGENT_THREAD_MAP_KEY = 'nous.agentThreadMap.v1';

// Server-canonical persistence cutover (PR 3/4 of the dual-persistence
// consolidation). When on: the workspace thread id is sent as the agent
// stream's thread_id (one thread, no localStorage mapping), the backend is
// the only message writer (AGENT_CANONICAL_PERSISTENCE must be on
// server-side too), and the frontend reconciles its optimistic bubbles via
// the ids in the `done` event instead of double-saving.
const SERVER_CANONICAL_CHAT =
  process.env.NEXT_PUBLIC_SERVER_CANONICAL_CHAT === 'true';

/**
 * Map a raw rag_context SSE item ({document_id, title, content, score} from
 * the agent's rag_node) onto the workspace CitationCreate schema so the
 * turn's sources persist with the assistant message. Snippet capped at the
 * backend Citation column limit.
 */
export function toCitationCreate(ctx: Record<string, unknown>): CitationCreate {
  const documentId =
    (ctx.document_id as string | undefined) ??
    (ctx.documentId as string | undefined);
  const snippet =
    (ctx.content as string | undefined) ??
    (ctx.snippet as string | undefined) ??
    '';
  return {
    ...(documentId ? { document_id: documentId } : {}),
    ...(ctx.external_reference_id
      ? { external_reference_id: ctx.external_reference_id as string }
      : {}),
    document_title:
      (ctx.title as string | undefined) ??
      (ctx.document_title as string | undefined),
    snippet: snippet.slice(0, 2000),
    ...(typeof ctx.score === 'number' ? { score: ctx.score } : {}),
  };
}

// Agent tools that mutate project content shown in the Working folders rail
// (sources/notes/drafts). A successful run of one of these must invalidate
// the ['project', …] queries — useProjectWorkingFolders caches them for 5
// minutes, so without this the rail misses documents/notes the agent just
// created until a reload.
const PROJECT_MUTATING_TOOLS = new Set([
  'ingest_arxiv',
  'add_document_to_project',
  'create_project',
  'create_project_note',
  'create_draft',
]);
// Warn once per session when the map can't be persisted (quota/private mode).
let warnedAgentMapWriteFailed = false;

// ============================================
// TYPES
// ============================================

export interface PendingConfirmation {
  threadId: string;
  workspaceThreadId: string;
  confirmation: Record<string, unknown>;
}

export interface UseChatStreamingParams {
  messages: ChatPageMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatPageMessage[]>>;
  conversations: ChatConversation[];
  setConversations: React.Dispatch<React.SetStateAction<ChatConversation[]>>;
  activeConversationId: string | null;
  setActiveConversationId: React.Dispatch<React.SetStateAction<string | null>>;
  activeConversationIdRef: React.MutableRefObject<string | null>;
  dbConversation: DBConversation | null;
  isAuthenticated: boolean;
  setCurrentThread: (threadId: string | null) => void;
  addMessageToStore: (threadId: string, msg: DBChatMessage) => void;
  enableRAG: boolean;
}

export interface UseChatStreamingReturn {
  input: string;
  setInput: React.Dispatch<React.SetStateAction<string>>;
  isLoading: boolean;
  handleSubmit: (contentOverride?: string) => Promise<void>;
  handleStop: () => void;
  pendingConfirmation: PendingConfirmation | null;
  isConfirming: boolean;
  handleConfirmation: (confirmed: boolean) => Promise<void>;
  chatInputRef: React.RefObject<HTMLTextAreaElement>;
  storeIsStreaming: boolean;
  storeStreamingContent: string;
  storeIsRetrievingRag: boolean;
  streamingTimestampRef: React.MutableRefObject<number>;
  selectedModel: string;
  setSelectedModel: (model: string) => void;
}

// ============================================
// HOOK
// ============================================

export function useChatStreaming(
  params: UseChatStreamingParams
): UseChatStreamingReturn {
  const {
    messages,
    setMessages,
    conversations,
    setConversations,
    activeConversationId,
    setActiveConversationId,
    activeConversationIdRef,
    dbConversation,
    isAuthenticated,
    setCurrentThread,
    addMessageToStore,
    enableRAG,
  } = params;

  // ---- Project context (for agent page_context) ----
  const searchParams = useSearchParams();
  // Thread row first (source_project_id is the durable binding), URL param
  // only as the initial intent — thread navigation (getSelectedThreadUrl)
  // drops it. Sentinel semantics documented on selectCurrentThreadProjectId.
  const threadProjectId = useChatStore(selectCurrentThreadProjectId);
  const boundProjectId = resolveBoundProjectId(
    threadProjectId,
    searchParams.get('projectId')
  );
  const projectStoreProjects = useProjectStore((s) => s.projects);
  const currentProject = useProjectStore((s) => s.currentProject);
  const resolvedProjectName = boundProjectId
    ? currentProject?.id === boundProjectId
      ? currentProject.name
      : (projectStoreProjects.find((p) => p.id === boundProjectId)?.name ??
        undefined)
    : undefined;

  // ---- State ----
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [pendingConfirmation, setPendingConfirmation] =
    useState<PendingConfirmation | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);

  // ---- Refs ----
  // workspace thread id -> agent thread id. Persisted so a reload reuses the
  // same agent thread (and therefore its project binding) instead of letting
  // the backend mint a fresh unlinked one every session.
  const agentThreadMapRef = useRef<Record<string, string>>({});
  useEffect(() => {
    if (SERVER_CANONICAL_CHAT) {
      // One thread now — the mapping is obsolete. Clear the stale key once
      // so old entries can't be misread if the flag is ever rolled back.
      try {
        window.localStorage.removeItem(AGENT_THREAD_MAP_KEY);
      } catch {
        // Storage unavailable — nothing to clear.
      }
      return;
    }
    try {
      const stored = window.localStorage.getItem(AGENT_THREAD_MAP_KEY);
      if (stored) {
        const parsed: unknown = JSON.parse(stored);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          agentThreadMapRef.current = {
            ...(parsed as Record<string, string>),
            ...agentThreadMapRef.current,
          };
        } else {
          window.localStorage.removeItem(AGENT_THREAD_MAP_KEY);
        }
      }
    } catch (err) {
      // Without the map every reload mints a fresh agent thread, so the
      // agent "forgets" project context — make that diagnosable, and clear
      // a corrupt value so it doesn't re-fail on every mount.
      console.warn(
        '[Chat] agent thread map unreadable; reloads will mint new agent threads',
        err
      );
      try {
        window.localStorage.removeItem(AGENT_THREAD_MAP_KEY);
      } catch {
        // Storage unavailable entirely (private mode/policy) — nothing to clear.
      }
    }
  }, []);
  const rememberAgentThread = useCallback(
    (workspaceThreadId: string, agentThreadId: string) => {
      if (SERVER_CANONICAL_CHAT) return; // one thread — nothing to map
      agentThreadMapRef.current[workspaceThreadId] = agentThreadId;
      try {
        window.localStorage.setItem(
          AGENT_THREAD_MAP_KEY,
          JSON.stringify(agentThreadMapRef.current)
        );
      } catch (err) {
        if (!warnedAgentMapWriteFailed) {
          warnedAgentMapWriteFailed = true;
          console.warn(
            '[Chat] failed to persist agent thread map; agent context will not survive reload',
            err
          );
        }
      }
    },
    []
  );
  const lastStreamedContentRef = useRef<string>('');
  const abortControllerRef = useRef<AbortController | null>(null);
  // Set the instant the user hits Stop, read by the stream-completion path so a
  // user abort finalizes the partial answer (tagged `stopped`) instead of
  // surfacing an error or an empty bubble. Reset once the turn is wrapped up.
  const stoppedByUserRef = useRef(false);
  // Citations snapshot taken by handleStop the instant the user aborts —
  // storeStopStreaming() clears streamingCitations synchronously, but the
  // completion path still needs them to commit + persist the stopped answer's
  // sources. Cleared once the turn is finalized.
  const stopCitationsRef = useRef<Array<Record<string, unknown>>>([]);
  // Workspace thread id of the in-flight run, so Stop can close out the agent
  // activity indicator (the normal onDone never fires on abort).
  const activeRunThreadRef = useRef<string | null>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const submitLockRef = useRef(false);
  const streamingTimestampRef = useRef(Date.now());
  const streamingRafRef = useRef<number | null>(null);
  const pendingStreamContentRef = useRef<string | null>(null);

  // ---- Store bindings ----
  const storeStopStreaming = useChatStore((state) => state.stopStreaming);
  const storeIsStreaming = useChatStore((state) => state.isStreaming);
  const storeStreamingContent = useChatStore((state) => state.streamingContent);
  const storeIsRetrievingRag = useChatStore((state) => state.isRetrievingRag);
  const selectedModel = useChatStore((state) => state.selectedModel);
  const setSelectedModel = useChatStore((state) => state.setSelectedModel);

  const router = useRouter();
  const queryClient = useQueryClient();

  // Refetch the Working-folders queries once a project-mutating tool
  // succeeds, so the rail shows agent-created sources/notes/drafts without
  // waiting out the 5-minute staleTime.
  const invalidateProjectDataForTool = useCallback(
    (tool: string, isError: boolean) => {
      if (isError || !PROJECT_MUTATING_TOOLS.has(tool)) return;
      void queryClient.invalidateQueries({ queryKey: ['project'] });
    },
    [queryClient]
  );

  // ---- Effects ----

  // Capture a stable timestamp when streaming begins
  useEffect(() => {
    if (storeIsStreaming) {
      streamingTimestampRef.current = Date.now();
    }
  }, [storeIsStreaming]);

  // Cleanup RAF on unmount
  useEffect(() => {
    return () => {
      if (streamingRafRef.current !== null) {
        cancelAnimationFrame(streamingRafRef.current);
      }
    };
  }, []);

  // ---- Handlers ----

  const handleSubmit = useCallback(
    async (contentOverride?: string) => {
      if (submitLockRef.current) return;
      const rawContent =
        typeof contentOverride === 'string' ? contentOverride : input;
      const content = rawContent.trim();
      if (!content || isLoading || storeIsStreaming) return;
      submitLockRef.current = true;

      const userMessage: ChatPageMessage = {
        role: 'user',
        content,
        timestamp: Date.now(),
      };

      const newMessages = [...messages, userMessage];
      setMessages(newMessages);
      setInput('');
      setIsLoading(true);

      // Create new thread if needed (when no active conversation).
      // Read from ref first (synchronous, immune to React batching), then
      // state, then Zustand store as final fallback.
      let currentConversationId =
        activeConversationIdRef.current ||
        activeConversationId ||
        useChatStore.getState().currentThreadId;
      let currentThreadId = currentConversationId;

      if (!currentConversationId && dbConversation) {
        try {
          const dynamicTitle = generateConversationTitle(content);
          console.log(
            '[Chat] Creating new thread in database with title:',
            dynamicTitle
          );
          const newThread = await workspaceService.createThread(
            buildThreadCreateRequest({
              conversationId: dbConversation.id,
              title: dynamicTitle,
              projectId: boundProjectId,
            })
          );

          // Register in the chat store: the binding selectors and
          // setThreadProjectBinding read store.threads, and without this the
          // thread is invisible there until the next full loadThreads — a
          // project attached to it would be silently dropped from the UI.
          useChatStore.getState().registerThread(newThread);

          currentConversationId = newThread.id;
          currentThreadId = newThread.id;

          const newConv: ChatConversation = {
            id: newThread.id,
            title: newThread.title || dynamicTitle,
            messages: newMessages,
            createdAt: Date.now(),
            updatedAt: Date.now(),
            threadId: newThread.id,
            conversationId: dbConversation.id,
          };

          setConversations((prev) => [newConv, ...prev]);
          setActiveConversationId(newConv.id);
          activeConversationIdRef.current = newConv.id;
          setCurrentThread(newConv.id);
          queueMicrotask(() =>
            router.replace(getSelectedThreadUrl(newThread.id))
          );
          console.log('[Chat] Created new thread:', newThread.id);
        } catch (error) {
          console.error('[Chat] Failed to create thread:', error);
          submitLockRef.current = false;
          setIsLoading(false);
          return;
        }
      }

      try {
        // Stream via Agent (LangGraph) backend
        // Server-canonical: the workspace thread IS the agent thread — the
        // legacy localStorage mapping only applies with the flag off.
        const existingAgentThreadId = SERVER_CANONICAL_CHAT
          ? currentThreadId || undefined
          : currentThreadId
            ? agentThreadMapRef.current[currentThreadId]
            : undefined;
        // Idempotency key for this user turn; the backend derives the
        // assistant row's key from it (uuid5), so an SSE retry can't
        // duplicate either row.
        const turnClientMessageId = SERVER_CANONICAL_CHAT
          ? crypto.randomUUID()
          : undefined;
        // Persisted ids from the done event (server-canonical only).
        let doneIds: {
          assistant_message_id?: string | null;
        } = {};

        console.log(
          '[Chat] Starting agent stream, workspace thread:',
          currentThreadId,
          'agent thread:',
          existingAgentThreadId
        );

        let assistantContent = '';
        lastStreamedContentRef.current = '';
        let streamHadError = false;
        let streamHadConfirmation = false;
        const responseStart = Date.now();

        // Per-turn step tracking — reset each send
        const turnSteps: ActivityStep[] = [];
        const toolStartTimes = new Map<string, number>();

        // Set streaming state in store for UI
        useChatStore.setState({
          isStreaming: true,
          streamingContent: '',
          streamingSteps: [],
          // Only "retrieving" when RAG is on; cleared on first token / context.
          isRetrievingRag: enableRAG,
        });

        // Fresh turn — clear any stop flag from a previous run and record the
        // thread so Stop can finalize this run's activity indicator.
        stoppedByUserRef.current = false;
        activeRunThreadRef.current = currentThreadId || null;

        if (currentThreadId) {
          useAgentActivityStore
            .getState()
            .startRun(currentThreadId, deriveAgentName(), deriveTask(content));
        }

        const streamAbort = new AbortController();
        abortControllerRef.current = streamAbort;

        await agentChatService.streamMessage(
          {
            messages: newMessages.map((m, i) => ({
              role: m.role,
              content: m.content,
              // Idempotency key rides on the user turn being sent (the last
              // message) — server-canonical only.
              ...(turnClientMessageId &&
              i === newMessages.length - 1 &&
              m.role === 'user'
                ? { client_message_id: turnClientMessageId }
                : {}),
            })),
            page_context: {
              type: boundProjectId ? 'project' : 'chat',
              ...(boundProjectId && {
                project_id: boundProjectId,
                project_name: resolvedProjectName || '',
              }),
              // The project is bound to the WORKSPACE thread, but this stream
              // runs on a separate agent thread. The backend uses this id to
              // resolve (and durably adopt) the bound project when the URL
              // param has been dropped by thread navigation.
              ...(currentThreadId && {
                metadata: { workspace_thread_id: currentThreadId },
              }),
            },
            use_rag: enableRAG,
            thread_id: existingAgentThreadId,
            model: selectedModel,
          },
          {
            onToken: (content) => {
              assistantContent += content;
              lastStreamedContentRef.current = assistantContent;
              pendingStreamContentRef.current = assistantContent;
              if (streamingRafRef.current === null) {
                streamingRafRef.current = requestAnimationFrame(() => {
                  streamingRafRef.current = null;
                  if (pendingStreamContentRef.current !== null) {
                    useChatStore.setState({
                      streamingContent: pendingStreamContentRef.current,
                      isRetrievingRag: false,
                    });
                    pendingStreamContentRef.current = null;
                  }
                });
              }
            },
            onToolStart: (tool, args) => {
              console.log('[Agent] Tool start:', tool, args);
              if (currentThreadId) {
                useAgentActivityStore
                  .getState()
                  .pushToolStart(currentThreadId, tool);
              }
              // Per-turn tracking for inline activity strip
              toolStartTimes.set(tool, Date.now());
              turnSteps.push({
                tool,
                label: toolLabel(tool),
                status: 'running',
                argsSummary: summarizeToolArgs(args),
              });
              useChatStore.setState({ streamingSteps: [...turnSteps] });
            },
            onToolEnd: (tool, result, isError) => {
              console.log('[Agent] Tool end:', tool, result, { isError });
              if (currentThreadId) {
                useAgentActivityStore
                  .getState()
                  .pushToolEnd(currentThreadId, tool, !isError);
              }
              invalidateProjectDataForTool(tool, isError);
              // Update last matching running step for this tool
              const startTime = toolStartTimes.get(tool);
              const durationMs = startTime ? Date.now() - startTime : undefined;
              const idx = [...turnSteps]
                .map((s, i) => ({ s, i }))
                .reverse()
                .find(({ s }) => s.tool === tool && s.status === 'running')?.i;
              if (idx !== undefined) {
                turnSteps[idx] = {
                  ...turnSteps[idx],
                  status: isError ? 'error' : 'done',
                  durationMs,
                  resultSummary: summarizeToolResult(result),
                };
              }
              useChatStore.setState({ streamingSteps: [...turnSteps] });
            },
            onRagContext: (contexts) => {
              console.log('[Agent] RAG contexts:', contexts.length);
              useChatStore.setState({
                streamingCitations: contexts,
                isRetrievingRag: false,
              });
            },
            onPlan: (steps) => {
              if (!currentThreadId) return;
              // Backend emits `{steps: [...], reasoning: ...}` — step items
              // may be plain strings or planner dicts with `description` and
              // a `tool` hint ("N/A" for reasoning/respond steps). Keep the
              // tool hint: the activity store marks a plan item done when its
              // tool actually completes, instead of bulk-completing the whole
              // plan at stream end.
              const items = (steps ?? [])
                .map((step) => {
                  if (typeof step === 'string') return { text: step };
                  if (step && typeof step === 'object') {
                    const s = step as Record<string, unknown>;
                    return {
                      text: String(
                        s.description ?? s.text ?? s.title ?? s.step ?? ''
                      ),
                      tool: typeof s.tool === 'string' ? s.tool : undefined,
                    };
                  }
                  return { text: '' };
                })
                .filter((item) => item.text.length > 0);
              if (items.length > 0) {
                useAgentActivityStore
                  .getState()
                  .setPlan(currentThreadId, items);
              }
            },
            onTrace: (threadId) => {
              // Capture agent thread_id from trace event for subsequent sends
              if (currentThreadId) {
                rememberAgentThread(currentThreadId, threadId);
              }
            },
            onReflection: (_passed, _issues, _round, revising) => {
              if (!revising) return;
              assistantContent = '';
              lastStreamedContentRef.current = '';
              pendingStreamContentRef.current = '';
              useChatStore.setState({ streamingContent: '' });
            },
            onConfirmation: (threadId, confirmation) => {
              console.log('[Agent] HITL confirmation needed:', confirmation);
              streamHadConfirmation = true;
              // Store agent thread ID for confirmation flow
              if (currentThreadId) {
                rememberAgentThread(currentThreadId, threadId);
              }
              setPendingConfirmation({
                threadId,
                workspaceThreadId: currentThreadId || '',
                confirmation,
              });
            },
            onDone: (payload) => {
              console.log('[Agent] Stream complete');
              if (payload) {
                doneIds = payload;
              }
              if (currentThreadId) {
                useAgentActivityStore
                  .getState()
                  .finishRun(currentThreadId, 'done');
              }
            },
            onError: (error) => {
              console.error('[Agent] Stream error:', error);
              streamHadError = true;
              if (currentThreadId) {
                useAgentActivityStore
                  .getState()
                  .finishRun(currentThreadId, 'error');
              }
              // Show error as assistant message instead of blank bubble
              const errorMsg: ChatPageMessage = {
                role: 'assistant',
                content: `Stream error: ${error}`,
                timestamp: Date.now(),
              };
              setMessages([...newMessages, errorMsg]);
            },
          },
          streamAbort.signal
        );

        // Cancel any pending RAF flush — streaming is done
        if (streamingRafRef.current !== null) {
          cancelAnimationFrame(streamingRafRef.current);
          streamingRafRef.current = null;
        }
        pendingStreamContentRef.current = null;

        // Don't append a normal message if stream errored or needs confirmation
        if (streamHadError || streamHadConfirmation) {
          useChatStore.setState({
            isStreaming: false,
            streamingContent: '',
            streamingCitations: [],
            streamingSteps: [],
          });
          setIsLoading(false);
          return;
        }

        // Guard against empty content (no tokens received). Surface the failure
        // to the user instead of leaving an empty bubble — every "agent broke
        // upstream" failure (DNS, auth, model error) used to look identical from
        // the UI side.
        const finalContent = assistantContent || lastStreamedContentRef.current;
        if (!finalContent.trim()) {
          // A user-stop before the first token: just unwind quietly — no error
          // bubble for an answer the user chose not to wait for.
          if (!stoppedByUserRef.current) {
            const emptyResponseMessage: ChatPageMessage = {
              role: 'assistant',
              content:
                '⚠ No response received from the agent. The stream completed without any tokens — check backend logs.',
              timestamp: Date.now(),
            };
            setMessages([...newMessages, emptyResponseMessage]);
          }
          useChatStore.setState({
            isStreaming: false,
            streamingContent: '',
            streamingCitations: [],
            streamingSteps: [],
          });
          setIsLoading(false);
          stoppedByUserRef.current = false;
          activeRunThreadRef.current = null;
          return;
        }

        // After streaming completes, build final message.
        // Clear the streaming state BEFORE appending the final assistant message
        // so the virtual streaming bubble unmounts atomically with the real one
        // mounting. Otherwise the final message and the streaming bubble render
        // together during the (awaited) DB save window below.
        const responseTimeMs = Date.now() - responseStart;
        const wasStopped = stoppedByUserRef.current;
        const finalTurnSteps = [...turnSteps];
        // Capture the turn's RAG citations BEFORE the streaming state is
        // cleared below — they are attached to the committed message (so
        // inline [Doc N] refs keep resolving after the stream ends) and
        // persisted with the assistant row (so they survive reload).
        // On a user Stop, storeStopStreaming() has ALREADY wiped
        // streamingCitations out-of-band — handleStop snapshots them into
        // stopCitationsRef first, so a stopped RAG answer keeps its sources.
        const liveCitations = useChatStore.getState().streamingCitations;
        const turnCitations =
          liveCitations.length > 0
            ? liveCitations
            : wasStopped
              ? stopCitationsRef.current
              : liveCitations;
        stopCitationsRef.current = [];
        const finalAssistantMessage: ChatPageMessage = {
          role: 'assistant',
          content: finalContent,
          timestamp: Date.now(),
          citations:
            turnCitations.length > 0
              ? turnCitations.map(normalizeCitation)
              : undefined,
          toolExecutions:
            finalTurnSteps.length > 0 ? finalTurnSteps : undefined,
          metadata: {
            responseTimeMs,
            ...(wasStopped ? { stopped: true } : {}),
            ...(finalTurnSteps.length > 0
              ? {
                  toolsUsed: finalTurnSteps.map((s) => s.label),
                }
              : {}),
            ...(turnCitations.length > 0
              ? { sourcesCount: turnCitations.length }
              : {}),
          },
        };
        stoppedByUserRef.current = false;
        activeRunThreadRef.current = null;

        useChatStore.setState({
          isStreaming: false,
          streamingContent: '',
          streamingCitations: [],
          streamingSteps: [],
        });
        lastStreamedContentRef.current = '';

        const finalMessages = [...newMessages, finalAssistantMessage];
        setMessages(finalMessages);

        // Save messages to workspace database for persistence.
        // Server-canonical mode: the BACKEND already persisted both rows
        // (user pre-stream, assistant before `done` — full fidelity incl.
        // tool_executions), so the client only reconciles its optimistic
        // bubble with the persisted id instead of double-writing a lower-
        // fidelity copy.
        if (SERVER_CANONICAL_CHAT) {
          if (doneIds.assistant_message_id) {
            finalAssistantMessage.id = doneIds.assistant_message_id;
            setMessages([...newMessages, finalAssistantMessage]);
          }
        } else if (currentThreadId && isAuthenticated) {
          try {
            // Save user message
            const savedUserMessage = await workspaceService.createMessage({
              thread_id: currentThreadId,
              content,
              role: MessageRole.USER,
            });
            addMessageToStore(currentThreadId, savedUserMessage);

            // Save assistant message. Citations ride along so provenance
            // survives thread reload — the backend Citation rows round-trip
            // through GET messages (dbMsg.citations → normalizeCitation).
            const savedAssistantMessage = await workspaceService.createMessage({
              thread_id: currentThreadId,
              content: finalAssistantMessage.content,
              role: MessageRole.ASSISTANT,
              latency_ms: responseTimeMs,
              ...(wasStopped ? { stopped: true } : {}),
              ...(turnCitations.length > 0
                ? { citations: turnCitations.map(toCitationCreate) }
                : {}),
            });
            addMessageToStore(currentThreadId, {
              ...savedAssistantMessage,
              latency_ms: responseTimeMs,
              ...(wasStopped ? { stopped: true } : {}),
            });
            console.log('[Chat] Saved messages to database');
          } catch (error) {
            console.error('[Chat] Failed to save messages:', error);
          }
        }

        // Update conversation
        setConversations((prev) =>
          prev.map((conv) =>
            conv.id === currentConversationId
              ? { ...conv, messages: finalMessages, updatedAt: Date.now() }
              : conv
          )
        );
      } catch (err) {
        // A user stop should never read as a failure. (streamMessage already
        // swallows AbortError, but guard here too in case the abort surfaces.)
        if (!stoppedByUserRef.current) {
          console.error('Failed to send message:', err);
          const errorMessage =
            'Error: ' +
            (err instanceof Error ? err.message : 'Failed to get response');

          setMessages([
            ...newMessages,
            {
              role: 'assistant',
              content: errorMessage,
              timestamp: Date.now(),
            },
          ]);
        }
      } finally {
        submitLockRef.current = false;
        setIsLoading(false);
        useChatStore.setState({
          isStreaming: false,
          streamingContent: '',
          streamingCitations: [],
        });
        lastStreamedContentRef.current = '';
        stoppedByUserRef.current = false;
        activeRunThreadRef.current = null;
      }
    },
    [
      input,
      isLoading,
      storeIsStreaming,
      messages,
      setMessages,
      activeConversationIdRef,
      activeConversationId,
      dbConversation,
      setConversations,
      setActiveConversationId,
      setCurrentThread,
      router,
      enableRAG,
      selectedModel,
      isAuthenticated,
      addMessageToStore,
      boundProjectId,
      resolvedProjectName,
      rememberAgentThread,
      invalidateProjectDataForTool,
    ]
  );

  const handleStop = useCallback(() => {
    // Mark the stop first so the stream-completion path (which runs right after
    // the abort makes streamMessage resolve) keeps the partial answer and tags
    // it `stopped`, rather than wiping it here and racing the commit.
    stoppedByUserRef.current = true;
    // Snapshot the turn's citations BEFORE storeStopStreaming() wipes
    // streamingCitations — the completion path reads the store after the
    // wipe and would otherwise commit + persist a stopped RAG answer with
    // zero sources.
    stopCitationsRef.current = useChatStore.getState().streamingCitations;
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;

    // Close out the agent activity indicator — onDone won't fire on abort.
    // 'stopped', not 'done': a user abort must not strike through the
    // remaining plan items as if they completed.
    const runThread = activeRunThreadRef.current;
    if (runThread) {
      useAgentActivityStore.getState().finishRun(runThread, 'stopped');
    }

    // The store-driven streaming path (used by the non-cloud chat) finalizes
    // through its own action; keep that contract intact.
    if (storeIsStreaming) {
      storeStopStreaming();
    }
  }, [storeIsStreaming, storeStopStreaming]);

  const handleConfirmation = useCallback(
    async (confirmed: boolean) => {
      if (!pendingConfirmation) return;
      setIsConfirming(true);
      useChatStore.setState({ isStreaming: true, streamingContent: '' });

      let confirmContent = '';
      const confirmMessages = [...messages];

      const confirmAbort = new AbortController();
      abortControllerRef.current = confirmAbort;

      try {
        await agentChatService.streamConfirm(
          { thread_id: pendingConfirmation.threadId, confirmed },
          {
            onToken: (content) => {
              confirmContent += content;
              pendingStreamContentRef.current = confirmContent;
              if (streamingRafRef.current === null) {
                streamingRafRef.current = requestAnimationFrame(() => {
                  streamingRafRef.current = null;
                  if (pendingStreamContentRef.current !== null) {
                    useChatStore.setState({
                      streamingContent: pendingStreamContentRef.current,
                      isRetrievingRag: false,
                    });
                    pendingStreamContentRef.current = null;
                  }
                });
              }
            },
            onToolStart: (tool) => {
              useAgentActivityStore
                .getState()
                .pushToolStart(pendingConfirmation.workspaceThreadId, tool);
            },
            onToolEnd: (tool, _result, isError) => {
              useAgentActivityStore
                .getState()
                .pushToolEnd(
                  pendingConfirmation.workspaceThreadId,
                  tool,
                  !isError
                );
              // HITL-confirmed tools are exactly the mutating ones (ingest,
              // create_note, create_draft) — refresh the rail here too.
              invalidateProjectDataForTool(tool, isError);
            },
            onReflection: (_passed, _issues, _round, revising) => {
              if (!revising) return;
              confirmContent = '';
              pendingStreamContentRef.current = '';
              useChatStore.setState({ streamingContent: '' });
            },
            onDone: () => {
              if (confirmContent.trim()) {
                const msg: ChatPageMessage = {
                  role: 'assistant',
                  content: confirmContent,
                  timestamp: Date.now(),
                };
                setMessages([...confirmMessages, msg]);
              }
            },
            onError: (error) => {
              const msg: ChatPageMessage = {
                role: 'assistant',
                content: `Confirmation error: ${error}`,
                timestamp: Date.now(),
              };
              setMessages([...confirmMessages, msg]);
            },
          },
          confirmAbort.signal
        );
      } catch (err) {
        const errorMessage =
          err instanceof Error
            ? err.message
            : 'Network error during confirmation';
        const msg: ChatPageMessage = {
          role: 'assistant',
          content: `Confirmation failed: ${errorMessage}`,
          timestamp: Date.now(),
        };
        setMessages([...confirmMessages, msg]);
      } finally {
        setPendingConfirmation(null);
        setIsConfirming(false);
        // The confirm stream shares streamingRafRef/pendingStreamContentRef
        // with handleSubmit's onToken throttle. A token that lands just
        // before completion schedules a rAF that would otherwise fire AFTER
        // this reset and resurrect stale streamingContent into the store.
        if (streamingRafRef.current !== null) {
          cancelAnimationFrame(streamingRafRef.current);
          streamingRafRef.current = null;
        }
        pendingStreamContentRef.current = null;
        useChatStore.setState({
          isStreaming: false,
          streamingContent: '',
        });
      }
    },
    [pendingConfirmation, messages, setMessages, invalidateProjectDataForTool]
  );

  return {
    input,
    setInput,
    isLoading,
    handleSubmit,
    handleStop,
    pendingConfirmation,
    isConfirming,
    handleConfirmation,
    chatInputRef,
    storeIsStreaming,
    storeStreamingContent,
    storeIsRetrievingRag,
    streamingTimestampRef,
    selectedModel,
    setSelectedModel,
  };
}
