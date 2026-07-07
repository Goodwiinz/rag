'use client';

import type {
  ActivityStep,
  ChatPageMessage,
} from '@/components/chat/shared/cloudMessageView';
import {
  mapDbToolExecutions,
  summarizeToolArgs,
  summarizeToolResult,
} from '@/components/chat/shared/cloudMessageView';
import toast from 'react-hot-toast';

import { getSelectedThreadUrl } from '@/components/chat/shared/chatNavigation';
import { buildThreadCreateRequest } from '@/components/chat/shared/threadCreation';
import {
  ChatConversation,
  generateConversationTitle,
} from '@/hooks/chat/chatTypes';
import { agentChatService } from '@/services/agentChatService';
import type { AgentStreamCallbacks } from '@/services/agentChatService';
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
import type { CitationCreate, DbToolExecution } from '@/types/workspace';
import type { PlanStep } from '@/types/agent-chat';
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
  /** Settled tool steps recorded before the interrupt, carried into the
   * resumed turn so the confirmed answer keeps its full provenance. */
  steps?: ActivityStep[];
  /** Structured plan emitted before the interrupt — carried so the
   * confirmed turn commits with its inline plan. */
  plan?: PlanStep[];
  /** RAG citations retrieved before the interrupt — the interrupt exit
   * clears streamingCitations, so they must ride the confirmation. */
  citations?: Array<Record<string, unknown>>;
}

/** Map raw planner SSE steps onto the structured inline-plan shape. */
function toTurnPlan(steps: Array<Record<string, unknown>> | undefined): PlanStep[] {
  return (steps ?? [])
    .filter(
      (st): st is Record<string, unknown> => !!st && typeof st === 'object'
    )
    .map((st, i) => ({
      step: typeof st.step === 'number' ? st.step : i + 1,
      description: String(st.description ?? st.text ?? st.title ?? ''),
      tool: typeof st.tool === 'string' ? st.tool : '',
      args_hint:
        st.args_hint && typeof st.args_hint === 'object'
          ? (st.args_hint as Record<string, unknown>)
          : {},
      depends_on: Array.isArray(st.depends_on)
        ? (st.depends_on as number[])
        : [],
    }))
    .filter((p) => p.description.length > 0);
}

/** Map raw planner SSE steps onto activity-rail plan items (text + tool
 * hint, so the rail marks items done when their tool completes). Step items
 * may be plain strings or planner dicts. */
function toActivityPlanItems(
  steps: Array<Record<string, unknown> | string> | undefined
): Array<{ text: string; tool?: string }> {
  return (steps ?? [])
    .map((step) => {
      if (typeof step === 'string') return { text: step };
      if (step && typeof step === 'object') {
        const s = step as Record<string, unknown>;
        return {
          text: String(s.description ?? s.text ?? s.title ?? s.step ?? ''),
          tool: typeof s.tool === 'string' ? s.tool : undefined,
        };
      }
      return { text: '' };
    })
    .filter((item) => item.text.length > 0);
}

/**
 * A pending HITL confirmation may only be rendered/actioned on the thread it
 * belongs to — actioning it elsewhere injects the resumed turn's messages
 * into whatever thread happens to be displayed. workspaceThreadId is '' when
 * the turn started before any thread existed (new chat), which matches a
 * null displayed-thread id.
 */
export function confirmationBelongsToThread(
  pending: PendingConfirmation | null,
  displayedThreadId: string | null
): boolean {
  if (!pending) return false;
  return pending.workspaceThreadId === (displayedThreadId ?? '');
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
  // rAF-batched SSE seq cursor (same pattern as streamingRafRef for tokens):
  // onSeq fires per frame, but the activity store only needs the latest value
  // once per paint.
  const seqRafRef = useRef<number | null>(null);
  const pendingSeqRef = useRef<{ threadId: string; seq: number } | null>(null);
  // Threads a resume was already attempted for this mount — guards against
  // double-resume from effect re-runs (StrictMode, dep changes).
  const resumeTriedRef = useRef<Set<string>>(new Set());

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
      // Scope to the bound project so we don't invalidate every
      // ['project', …] query (project list, unrelated project details,
      // metadata). Fall back to broad invalidation when no project is
      // bound (global chat has no narrower key to target).
      void queryClient.invalidateQueries({
        queryKey: boundProjectId ? ['project', boundProjectId] : ['project'],
      });
    },
    [queryClient, boundProjectId]
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
      if (seqRafRef.current !== null) {
        cancelAnimationFrame(seqRafRef.current);
      }
    };
  }, []);

  // ---- Handlers ----

  /**
   * Run one agent turn end-to-end — streaming state setup, the single shared
   * set of SSE callbacks, and the commit/persist/cleanup path. Used by both
   * handleSubmit (POST /agent/stream) and the mount-time resume effect
   * (GET /agent/stream/resume) so a resumed stream renders through EXACTLY
   * the same path as a live one (isStreaming cleared BEFORE setMessages).
   */
  const runStreamTurn = useCallback(
    async (opts: {
      currentThreadId: string | null;
      currentConversationId: string | null;
      newMessages: ChatPageMessage[];
      /** Legacy (non-server-canonical) mode: persist this user turn after
       * the stream. Omitted on resume — the original submit wrote it. */
      persistUserContent?: string;
      /** Resume: a replay that yields no tokens (nothing buffered / 204)
       * must unwind quietly instead of rendering a "no response" bubble. */
      quietWhenEmpty?: boolean;
      start: (
        callbacks: AgentStreamCallbacks,
        signal: AbortSignal
      ) => Promise<void>;
    }): Promise<void> => {
      const {
        currentThreadId,
        currentConversationId,
        newMessages,
        persistUserContent,
        quietWhenEmpty,
        start,
      } = opts;

      // The thread this turn belongs to, snapshotted after thread creation.
      // Every local setMessages below must be gated on the user still viewing
      // this thread: setMessages writes to whatever thread is CURRENTLY
      // displayed, and the sidebar switches threads without aborting the
      // stream. Store/back-end persistence is thread-scoped already, so a
      // skipped local write is not lost — it reappears when the user returns.
      // ponytail: the global streaming bubble/flags still render on whatever
      // thread is displayed while a background turn streams — per-thread
      // streaming state is the upgrade path if that becomes noticeable.
      const turnThreadId = activeConversationIdRef.current;
      const isTurnDisplayed = () =>
        activeConversationIdRef.current === turnThreadId;

      try {
        // Persisted ids from the done event (server-canonical only).
        let doneIds: {
          assistant_message_id?: string | null;
        } = {};

        let assistantContent = '';
        lastStreamedContentRef.current = '';
        let streamHadError = false;
        let streamHadConfirmation = false;
        const responseStart = Date.now();

        // Per-turn step tracking — reset each send
        const turnSteps: ActivityStep[] = [];
        // Structured plan snapshot for the committed message (the activity
        // store only keeps flattened strings for the ContextRail).
        let turnPlan: PlanStep[] = [];
        const toolStartTimes = new Map<string, number>();
        // Per-turn LLM token usage, captured from the `usage` SSE event that
        // fires just before `done`. Null until (and unless) it arrives.
        let turnTokenUsage: { input: number; output: number } | null = null;

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

        const streamAbort = new AbortController();
        abortControllerRef.current = streamAbort;

        await start(
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
            onSeq: (seq) => {
              if (!currentThreadId) return;
              pendingSeqRef.current = { threadId: currentThreadId, seq };
              if (seqRafRef.current === null) {
                seqRafRef.current = requestAnimationFrame(() => {
                  seqRafRef.current = null;
                  const p = pendingSeqRef.current;
                  pendingSeqRef.current = null;
                  if (p) {
                    useAgentActivityStore
                      .getState()
                      .setStreamSeq(p.threadId, p.seq);
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
              // Structured copy for the inline transcript plan — keeps
              // tool/depends_on so status derivation works after commit.
              turnPlan = toTurnPlan(steps);
              if (!currentThreadId) return;
              const items = toActivityPlanItems(steps);
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
            onUsage: (inputTokens, outputTokens) => {
              turnTokenUsage = { input: inputTokens, output: outputTokens };
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
                // Only settled steps: the interrupted tool re-emits its own
                // tool_start on resume, so a carried 'running' step would
                // duplicate it.
                steps: turnSteps.filter((s) => s.status !== 'running'),
                plan: [...turnPlan],
                // Snapshot NOW — the streamHadConfirmation exit below clears
                // streamingCitations before the confirm stream starts.
                citations: useChatStore.getState().streamingCitations,
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
              if (isTurnDisplayed()) setMessages([...newMessages, errorMsg]);
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
          if (!stoppedByUserRef.current && !quietWhenEmpty) {
            const emptyResponseMessage: ChatPageMessage = {
              role: 'assistant',
              content:
                '⚠ No response received from the agent. The stream completed without any tokens — check backend logs.',
              timestamp: Date.now(),
            };
            if (isTurnDisplayed())
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
          plan: turnPlan.length > 0 ? turnPlan : undefined,
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
            ...(turnTokenUsage ? { tokenUsage: turnTokenUsage } : {}),
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
        if (isTurnDisplayed()) setMessages(finalMessages);

        // Save messages to workspace database for persistence.
        // Server-canonical mode: the BACKEND already persisted both rows
        // (user pre-stream, assistant before `done` — full fidelity incl.
        // tool_executions), so the client only reconciles its optimistic
        // bubble with the persisted id instead of double-writing a lower-
        // fidelity copy.
        if (SERVER_CANONICAL_CHAT) {
          if (doneIds.assistant_message_id) {
            finalAssistantMessage.id = doneIds.assistant_message_id;
            if (isTurnDisplayed())
              setMessages([...newMessages, finalAssistantMessage]);
          }
        } else if (currentThreadId && isAuthenticated && persistUserContent) {
          try {
            // Save user message
            const savedUserMessage = await workspaceService.createMessage({
              thread_id: currentThreadId,
              content: persistUserContent,
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

          if (isTurnDisplayed())
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
      activeConversationIdRef,
      setMessages,
      setConversations,
      enableRAG,
      isAuthenticated,
      addMessageToStore,
      rememberAgentThread,
      invalidateProjectDataForTool,
    ]
  );

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
          // Roll back the optimistic turn: the user message was appended and
          // the composer cleared before this call. Without this the bubble
          // ghosts (never sent, gone on reload) and the typed text is lost.
          // Restore both and tell the user, so they can retry.
          setMessages(messages);
          setInput(content);
          toast.error('Could not start the conversation. Please try again.');
          submitLockRef.current = false;
          setIsLoading(false);
          return;
        }
      }

      // Stream via Agent (LangGraph) backend.
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

      console.log(
        '[Chat] Starting agent stream, workspace thread:',
        currentThreadId,
        'agent thread:',
        existingAgentThreadId
      );

      if (currentThreadId) {
        useAgentActivityStore
          .getState()
          .startRun(currentThreadId, deriveAgentName(), deriveTask(content));
      }

      try {
        await runStreamTurn({
          currentThreadId,
          currentConversationId,
          newMessages,
          persistUserContent: content,
          start: (streamCallbacks, signal) =>
            agentChatService.streamMessage(
              {
                messages: newMessages.map((m, i) => ({
                  role: m.role,
                  content: m.content,
                  // Idempotency key rides on the user turn being sent (the
                  // last message) — server-canonical only.
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
                  // The project is bound to the WORKSPACE thread, but this
                  // stream runs on a separate agent thread. The backend uses
                  // this id to resolve (and durably adopt) the bound project
                  // when the URL param has been dropped by thread navigation.
                  ...(currentThreadId && {
                    metadata: { workspace_thread_id: currentThreadId },
                  }),
                },
                use_rag: enableRAG,
                thread_id: existingAgentThreadId,
                model: selectedModel,
              },
              streamCallbacks,
              signal
            ),
        });
      } finally {
        submitLockRef.current = false;
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
      boundProjectId,
      resolvedProjectName,
      runStreamTurn,
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

  // ---- Resume an in-flight stream on mount / thread switch ----
  // If the activity store still records a running run for the displayed
  // thread (e.g. the page remounted mid-stream), reattach to the backend's
  // buffered stream and replay from the last seen seq through the exact
  // same callbacks/commit path as a live submit.
  useEffect(() => {
    const threadId = activeConversationId;
    if (!threadId || isLoading) return;
    if (useChatStore.getState().isStreaming) return;
    const run = useAgentActivityStore.getState().runs[threadId];
    if (!run || run.state !== 'running') return;
    if (resumeTriedRef.current.has(threadId)) return;
    resumeTriedRef.current.add(threadId);
    console.log('[Chat] Resuming in-flight agent stream:', threadId);
    // ponytail: messages is the snapshot at effect time — if thread history
    // is still loading, the resumed commit appends to a stale list; a
    // reload reconciles from the server-persisted rows.
    void runStreamTurn({
      currentThreadId: threadId,
      currentConversationId: threadId,
      newMessages: messages,
      quietWhenEmpty: true,
      start: async (streamCallbacks, signal) => {
        const res = await agentChatService.resumeStream(
          threadId,
          run.streamSeq ?? 0,
          streamCallbacks,
          signal
        );
        if (!res.resumed) {
          // Nothing active server-side — clear the stale run record.
          useAgentActivityStore.getState().finishRun(threadId, 'done');
        }
      },
    });
  }, [activeConversationId, isLoading, messages, runStreamTurn]);

  const handleConfirmation = useCallback(
    async (confirmed: boolean) => {
      if (!pendingConfirmation) return;
      // Defense in depth — the page hides the banner on foreign threads, but
      // a stale click must never resume a confirmation against the wrong
      // thread's transcript.
      if (
        !confirmationBelongsToThread(
          pendingConfirmation,
          activeConversationIdRef.current
        )
      )
        return;
      // The confirm resume is async; the user can still switch threads while it
      // streams. Gate every local setMessages below on the confirmation's
      // thread still being displayed — the resumed answer is persisted
      // server-side regardless, so a skipped local write is not lost (mirrors
      // handleSubmit's isTurnDisplayed guard).
      const isConfirmDisplayed = () =>
        confirmationBelongsToThread(
          pendingConfirmation,
          activeConversationIdRef.current
        );
      setIsConfirming(true);
      const confirmStart = Date.now();
      // Track tool steps for the resumed turn exactly like handleSubmit —
      // seed with the pre-interrupt steps so the live bubble and the
      // committed message both show the whole turn's tools, not just the
      // post-confirm ones (previously none rendered until a page reload).
      const confirmSteps: ActivityStep[] = [
        ...(pendingConfirmation.steps ?? []),
      ];
      const confirmToolStartTimes = new Map<string, number>();
      // Pre-interrupt provenance carried on the confirmation — the interrupt
      // exit cleared the live streaming state, so restore it here.
      const carriedCitations = pendingConfirmation.citations ?? [];
      let confirmPlan: PlanStep[] = [...(pendingConfirmation.plan ?? [])];
      useChatStore.setState({
        isStreaming: true,
        streamingContent: '',
        streamingSteps: [...confirmSteps],
        streamingCitations: carriedCitations,
      });

      let confirmContent = '';
      // Post-confirm retrieval contexts (the resumed turn can run RAG); the
      // confirm parser previously dropped rag_context entirely, so a
      // confirmed action's sources never reached the UI (sync-audit gap 2).
      // Committed alongside the carried pre-interrupt citations.
      let resumeCitations: Array<Record<string, unknown>> = [];
      // Token usage emitted by the confirm path (backend fires event: usage
      // before done). Without capturing this, confirmed turns showed no token
      // cost — inconsistent with the main stream.
      let confirmTokenUsage: { input: number; output: number } | null = null;
      // A resumed turn can hit ANOTHER destructive tool (nested interrupt):
      // the backend emits a fresh `confirmation` and ends the stream without
      // `done`. Captured here so `finally` re-arms the banner instead of
      // clearing it — previously the event was dropped and the graph was
      // left interrupted with no way to resume from the UI.
      let nestedConfirmation: PendingConfirmation | null = null;
      // Set when onDone/onError committed a bubble — the post-stream abort
      // path below must not double-commit.
      let confirmCommitted = false;
      const confirmMessages = [...messages];

      const buildConfirmMessage = (
        content: string,
        stopped: boolean
      ): ChatPageMessage => {
        const allCitations = [...carriedCitations, ...resumeCitations];
        return {
          role: 'assistant',
          content,
          timestamp: Date.now(),
          ...(allCitations.length > 0
            ? { citations: allCitations.map(normalizeCitation) }
            : {}),
          ...(confirmSteps.length > 0
            ? { toolExecutions: [...confirmSteps] }
            : {}),
          ...(confirmPlan.length > 0 ? { plan: [...confirmPlan] } : {}),
          metadata: {
            responseTimeMs: Date.now() - confirmStart,
            ...(stopped ? { stopped: true } : {}),
            ...(confirmTokenUsage ? { tokenUsage: confirmTokenUsage } : {}),
            ...(confirmSteps.length > 0
              ? { toolsUsed: confirmSteps.map((s) => s.label) }
              : {}),
          },
        };
      };

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
            onToolStart: (tool, args) => {
              useAgentActivityStore
                .getState()
                .pushToolStart(pendingConfirmation.workspaceThreadId, tool);
              confirmToolStartTimes.set(tool, Date.now());
              confirmSteps.push({
                tool,
                label: toolLabel(tool),
                status: 'running',
                argsSummary: summarizeToolArgs(args),
              });
              useChatStore.setState({ streamingSteps: [...confirmSteps] });
            },
            onToolEnd: (tool, result, isError) => {
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
              const startTime = confirmToolStartTimes.get(tool);
              const durationMs = startTime ? Date.now() - startTime : undefined;
              const idx = [...confirmSteps]
                .map((s, i) => ({ s, i }))
                .reverse()
                .find(({ s }) => s.tool === tool && s.status === 'running')?.i;
              if (idx !== undefined) {
                confirmSteps[idx] = {
                  ...confirmSteps[idx],
                  status: isError ? 'error' : 'done',
                  durationMs,
                  resultSummary: summarizeToolResult(result),
                };
              }
              useChatStore.setState({ streamingSteps: [...confirmSteps] });
            },
            onRagContext: (contexts) => {
              resumeCitations = contexts;
              useChatStore.setState({
                streamingCitations: [...carriedCitations, ...contexts],
                isRetrievingRag: false,
              });
            },
            onPlan: (steps) => {
              confirmPlan = toTurnPlan(steps);
              const items = toActivityPlanItems(steps);
              if (pendingConfirmation.workspaceThreadId && items.length > 0) {
                useAgentActivityStore
                  .getState()
                  .setPlan(pendingConfirmation.workspaceThreadId, items);
              }
            },
            onConfirmation: (threadId, confirmation) => {
              nestedConfirmation = {
                threadId,
                workspaceThreadId: pendingConfirmation.workspaceThreadId,
                confirmation,
                steps: confirmSteps.filter((s) => s.status !== 'running'),
                plan: [...confirmPlan],
                citations: [...carriedCitations, ...resumeCitations],
              };
            },
            onUsage: (inputTokens, outputTokens) => {
              confirmTokenUsage = { input: inputTokens, output: outputTokens };
            },
            onReflection: (_passed, _issues, _round, revising) => {
              if (!revising) return;
              confirmContent = '';
              pendingStreamContentRef.current = '';
              useChatStore.setState({ streamingContent: '' });
            },
            onDone: (payload) => {
              if (confirmContent.trim()) {
                const msg = buildConfirmMessage(confirmContent, false);
                // Server-canonical: stamp the persisted id onto the
                // optimistic bubble so a reload reconciles with the row
                // instead of re-fetching a duplicate. Mirrors handleSubmit.
                if (payload?.assistant_message_id) {
                  msg.id = payload.assistant_message_id;
                }
                // The done payload carries the graph state's tool executions
                // (parsed results, real durations) for the WHOLE turn —
                // richer than the live SSE summaries, and identical to what
                // a reload would show. Prefer them when present.
                const serverSteps = mapDbToolExecutions(
                  payload?.tool_executions as DbToolExecution[] | undefined
                );
                if (serverSteps && serverSteps.length > 0) {
                  msg.toolExecutions = serverSteps;
                  msg.metadata = {
                    ...msg.metadata,
                    toolsUsed: serverSteps.map((s) => s.label),
                  };
                }
                confirmCommitted = true;
                if (isConfirmDisplayed()) setMessages([...confirmMessages, msg]);
              }
            },
            onError: (error) => {
              const msg: ChatPageMessage = {
                role: 'assistant',
                content: `Confirmation error: ${error}`,
                timestamp: Date.now(),
              };
              confirmCommitted = true;
              if (isConfirmDisplayed()) setMessages([...confirmMessages, msg]);
            },
          },
          confirmAbort.signal
        );

        // User hit Stop mid-resume: the abort swallows the stream so onDone
        // never fires — commit the partial answer tagged `stopped`, like
        // handleSubmit does. The backend's disconnect branch persists the
        // same partial server-side, so reload reconciles.
        if (
          !confirmCommitted &&
          stoppedByUserRef.current &&
          confirmContent.trim()
        ) {
          confirmCommitted = true;
          if (isConfirmDisplayed())
            setMessages([
              ...confirmMessages,
              buildConfirmMessage(confirmContent, true),
            ]);
        }
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
        if (isConfirmDisplayed()) setMessages([...confirmMessages, msg]);
      } finally {
        // A nested interrupt re-arms the banner with the new confirmation
        // (carrying the turn's accumulated provenance); otherwise clear it.
        setPendingConfirmation(nestedConfirmation);
        setIsConfirming(false);
        stoppedByUserRef.current = false;
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
          streamingSteps: [],
          streamingCitations: [],
        });
      }
    },
    [
      pendingConfirmation,
      messages,
      setMessages,
      invalidateProjectDataForTool,
      activeConversationIdRef,
    ]
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
