'use client';

import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { getSelectedThreadUrl } from '@/components/chat/shared/chatNavigation';
import { buildThreadCreateRequest } from '@/components/chat/shared/threadCreation';
import {
  ChatConversation,
  generateConversationTitle,
} from '@/hooks/chat/chatTypes';
import { agentChatService } from '@/services/agentChatService';
import { workspaceService } from '@/services/workspaceService';
import { useChatStore } from '@/store/chat-store';
import { useAgentActivityStore } from '@/stores/agentActivityStore';
import { deriveAgentName, deriveTask } from '@/components/context-rail';
import { Conversation as DBConversation, MessageRole } from '@/types/workspace';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useProjectStore } from '@/store/projectStore';
import type { ChatMessage as DBChatMessage } from '@/types/workspace';

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
  const boundProjectId = searchParams.get('projectId') ?? undefined;
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
  const agentThreadMapRef = useRef<Record<string, string>>({});
  const lastStreamedContentRef = useRef<string>('');
  const abortControllerRef = useRef<AbortController | null>(null);
  // Set the instant the user hits Stop, read by the stream-completion path so a
  // user abort finalizes the partial answer (tagged `stopped`) instead of
  // surfacing an error or an empty bubble. Reset once the turn is wrapped up.
  const stoppedByUserRef = useRef(false);
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
        const existingAgentThreadId = currentThreadId
          ? agentThreadMapRef.current[currentThreadId]
          : undefined;

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

        // Set streaming state in store for UI
        useChatStore.setState({
          isStreaming: true,
          streamingContent: '',
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
            messages: newMessages.map((m) => ({
              role: m.role,
              content: m.content,
            })),
            page_context: {
              type: boundProjectId ? 'project' : 'chat',
              ...(boundProjectId && {
                project_id: boundProjectId,
                project_name: resolvedProjectName || '',
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
            },
            onToolEnd: (tool, result, isError) => {
              console.log('[Agent] Tool end:', tool, result, { isError });
              if (currentThreadId) {
                useAgentActivityStore
                  .getState()
                  .pushToolEnd(currentThreadId, tool, !isError);
              }
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
              // Coerce each plan step into a single human-readable string.
              // Backend emits `{steps: [...], reasoning: ...}` — step items may
              // be plain strings or objects with `description`/`text`/`title`.
              const items = (steps ?? [])
                .map((step) => {
                  if (typeof step === 'string') return step;
                  if (step && typeof step === 'object') {
                    const s = step as Record<string, unknown>;
                    return String(
                      s.description ?? s.text ?? s.title ?? s.step ?? ''
                    );
                  }
                  return '';
                })
                .filter((s) => s.length > 0);
              if (items.length > 0) {
                useAgentActivityStore
                  .getState()
                  .setPlan(currentThreadId, items);
              }
            },
            onTrace: (threadId) => {
              // Capture agent thread_id from trace event for subsequent sends
              if (currentThreadId) {
                agentThreadMapRef.current[currentThreadId] = threadId;
              }
            },
            onConfirmation: (threadId, confirmation) => {
              console.log('[Agent] HITL confirmation needed:', confirmation);
              streamHadConfirmation = true;
              // Store agent thread ID for confirmation flow
              if (currentThreadId) {
                agentThreadMapRef.current[currentThreadId] = threadId;
              }
              setPendingConfirmation({
                threadId,
                workspaceThreadId: currentThreadId || '',
                confirmation,
              });
            },
            onDone: () => {
              console.log('[Agent] Stream complete');
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
        const finalAssistantMessage: ChatPageMessage = {
          role: 'assistant',
          content: finalContent,
          timestamp: Date.now(),
          metadata: { responseTimeMs, ...(wasStopped ? { stopped: true } : {}) },
        };
        stoppedByUserRef.current = false;
        activeRunThreadRef.current = null;

        useChatStore.setState({
          isStreaming: false,
          streamingContent: '',
          streamingCitations: [],
        });
        lastStreamedContentRef.current = '';

        const finalMessages = [...newMessages, finalAssistantMessage];
        setMessages(finalMessages);

        // Save messages to workspace database for persistence
        if (currentThreadId && isAuthenticated) {
          try {
            // Save user message
            const savedUserMessage = await workspaceService.createMessage({
              thread_id: currentThreadId,
              content,
              role: MessageRole.USER,
            });
            addMessageToStore(currentThreadId, savedUserMessage);

            // Save assistant message
            const savedAssistantMessage = await workspaceService.createMessage({
              thread_id: currentThreadId,
              content: finalAssistantMessage.content,
              role: MessageRole.ASSISTANT,
              latency_ms: responseTimeMs,
            });
            addMessageToStore(currentThreadId, {
              ...savedAssistantMessage,
              latency_ms: responseTimeMs,
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
    ]
  );

  const handleStop = useCallback(() => {
    // Mark the stop first so the stream-completion path (which runs right after
    // the abort makes streamMessage resolve) keeps the partial answer and tags
    // it `stopped`, rather than wiping it here and racing the commit.
    stoppedByUserRef.current = true;
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;

    // Close out the agent activity indicator — onDone won't fire on abort.
    const runThread = activeRunThreadRef.current;
    if (runThread) {
      useAgentActivityStore.getState().finishRun(runThread, 'done');
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
        useChatStore.setState({
          isStreaming: false,
          streamingContent: '',
        });
      }
    },
    [pendingConfirmation, messages, setMessages]
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
