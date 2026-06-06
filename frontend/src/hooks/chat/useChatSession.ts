'use client';

import {
  selectDisplayedMessages,
  syncConversationMessagesWithStore,
} from '@/components/chat/shared/cloudMessageView';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { ChatConversation } from '@/hooks/chat/chatTypes';
import { upsertConversationFromThreadDetail } from '@/components/chat/shared/threadConversationState';
import { workspaceService } from '@/services/workspaceService';
import { useChatStore } from '@/store/chat-store';
import { useAuthStore } from '@/stores/authStore';
import {
  ChatMessage as DBChatMessage,
  Conversation as DBConversation,
  MessageRole,
  Workspace,
} from '@/types/workspace';
import { normalizeCitation } from '@/utils/citationNormalizer';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

export interface UseChatSessionReturn {
  // State
  conversations: ChatConversation[];
  setConversations: React.Dispatch<React.SetStateAction<ChatConversation[]>>;
  activeConversationId: string | null;
  setActiveConversationId: React.Dispatch<React.SetStateAction<string | null>>;
  messages: ChatPageMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatPageMessage[]>>;
  workspace: Workspace | null;
  dbConversation: DBConversation | null;
  isInitializing: boolean;
  initError: string | null;
  isLoadingMessages: boolean;

  // Refs
  activeConversationIdRef: React.MutableRefObject<string | null>;
  isHydratedRef: React.MutableRefObject<boolean>;

  // Store bindings
  currentThreadIdFromStore: string | null;
  setCurrentThread: (threadId: string | null) => void;
  storeMessages: Record<string, import('@/types/workspace').ChatMessage[]>;
  addMessageToStore: (
    threadId: string,
    message: import('@/types/workspace').ChatMessage
  ) => void;
  isAuthenticated: boolean;

  // Derived
  activeThreadId: string | null;
  displayedMessages: ChatPageMessage[];

  // Helpers
  mapDbMessageToUiMessage: (dbMsg: DBChatMessage) => ChatPageMessage;
  loadThreadsFromDb: (
    conversationId: string,
    isRetry?: boolean
  ) => Promise<{ ok: boolean; threadCount: number }>;
}

/**
 * Custom hook encapsulating session/workspace initialization logic for the chat page.
 *
 * Manages: conversations, active thread, messages, workspace, DB conversation,
 * initialization lifecycle, and lazy message loading.
 *
 * Must be called inside a component wrapped in <Suspense> (uses useSearchParams).
 */
export function useChatSession(): UseChatSessionReturn {
  // ---- State ----
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<
    string | null
  >(null);
  const [messages, setMessages] = useState<ChatPageMessage[]>([]);

  // Database state
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [dbConversation, setDbConversation] = useState<DBConversation | null>(
    null
  );
  const [isInitializing, setIsInitializing] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);

  // Loading states
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

  // ---- Refs ----
  const activeConversationIdRef = useRef<string | null>(null);
  const isHydratedRef = useRef(false);

  // ---- Auth ----
  const { isAuthenticated } = useAuthStore();

  // ---- Store bindings ----
  const currentThreadIdFromStore = useChatStore(
    (state) => state.currentThreadId
  );
  const setCurrentThread = useChatStore((state) => state.setCurrentThread);
  const storeMessages = useChatStore((state) => state.messages);
  const addMessageToStore = useChatStore((state) => state.addMessageToStore);

  // ---- Derived values ----
  const activeThreadId = currentThreadIdFromStore || activeConversationId;
  const displayedMessages = selectDisplayedMessages({
    localMessages: messages,
    storeMessages: activeThreadId ? storeMessages[activeThreadId] || [] : [],
  });

  // ---- Callbacks ----

  // Map DB messages to UI messages
  const mapDbMessageToUiMessage = useCallback(
    (dbMsg: DBChatMessage): ChatPageMessage => {
      // Rebuild display metadata from the persisted row so a reloaded thread
      // keeps the response time and the "Stopped" marker (both were otherwise
      // session-only).
      const metadata: ChatPageMessage['metadata'] = {};
      if (dbMsg.latency_ms) metadata.responseTimeMs = dbMsg.latency_ms;
      if (dbMsg.stopped) metadata.stopped = true;

      return {
        id: dbMsg.id,
        role: dbMsg.role === MessageRole.USER ? 'user' : 'assistant',
        content: dbMsg.content,
        timestamp: new Date(dbMsg.created_at).getTime(),
        citations: dbMsg.citations?.map(normalizeCitation),
        metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
      };
    },
    []
  );

  // ---- Router / Search params ----
  const searchParams = useSearchParams();
  const searchParamsRef = useRef(searchParams);
  searchParamsRef.current = searchParams;
  const router = useRouter();

  // ---- Effects ----

  // Keep activeConversationIdRef in sync so handleSubmit can read it
  // synchronously (immune to React batching delays).
  useEffect(() => {
    activeConversationIdRef.current = activeConversationId;
  }, [activeConversationId]);

  // Reset refs when user changes (logout/login)
  useEffect(() => {
    if (!isAuthenticated) {
      isHydratedRef.current = false;
    }
  }, [isAuthenticated]);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!isAuthenticated && !isInitializing) {
      const timer = setTimeout(() => {
        router.push('/login');
      }, 1500); // Short delay to show the "Redirecting..." state
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, isInitializing, router]);

  // Store messages -> conversations sync
  useEffect(() => {
    if (!activeThreadId) {
      return;
    }

    const activeStoreMessages = storeMessages[activeThreadId] || [];

    if (activeStoreMessages.length === 0) {
      return;
    }

    setConversations((prev) =>
      syncConversationMessagesWithStore(
        prev,
        activeThreadId,
        activeStoreMessages
      )
    );
  }, [activeThreadId, storeMessages]);

  // Handle thread switching from URL query param (single source of truth)
  useEffect(() => {
    if (conversations.length === 0 || isInitializing) {
      return;
    }

    const threadFromUrl = searchParams.get('thread');

    if (threadFromUrl) {
      console.log('[Chat] Thread switch requested:', threadFromUrl);
      const targetConv = conversations.find((c) => c.id === threadFromUrl);

      if (targetConv) {
        if (targetConv.id !== activeConversationId) {
          setActiveConversationId(targetConv.id);
          activeConversationIdRef.current = targetConv.id;
          setMessages(targetConv.messages);
          // Also update the Zustand store so sidebar highlights correctly
          setCurrentThread(targetConv.id);
          console.log('[Chat] Switched to thread:', targetConv.title);
        }
        return;
      }

      console.log(
        '[Chat] Thread not found in conversations, fetching detail:',
        threadFromUrl
      );

      let cancelled = false;

      (async () => {
        try {
          const threadDetail = await workspaceService.getThread(threadFromUrl);
          if (cancelled) return;

          const uiMessages = threadDetail.messages.map(mapDbMessageToUiMessage);
          setConversations((prev) =>
            upsertConversationFromThreadDetail(
              prev,
              threadDetail,
              mapDbMessageToUiMessage
            )
          );
          setActiveConversationId(threadDetail.id);
          activeConversationIdRef.current = threadDetail.id;
          setMessages(uiMessages);
          setCurrentThread(threadDetail.id);
        } catch (error: unknown) {
          if (!cancelled) {
            console.error('[Chat] Failed to fetch requested thread:', error);
          }
        }
      })();

      return () => {
        cancelled = true;
      };
    }
  }, [
    searchParams,
    conversations,
    isInitializing,
    activeConversationId,
    mapDbMessageToUiMessage,
    setCurrentThread,
  ]);

  // Load threads and messages from database
  const loadThreadsFromDb = useCallback(
    async (
      conversationId: string,
      _isRetry = false
    ): Promise<{ ok: boolean; threadCount: number }> => {
      try {
        console.log(
          '[Chat] Loading threads from database for conversation:',
          conversationId
        );
        const threadResponse = await workspaceService.listThreads(
          conversationId,
          { limit: 50 }
        );

        // Map threads without loading messages (lazy-loaded on selection)
        const uiConversations: ChatConversation[] = threadResponse.threads.map(
          (thread) => ({
            id: thread.id,
            title: thread.title || 'New Chat',
            messages: [],
            createdAt: new Date(thread.created_at).getTime(),
            updatedAt: new Date(thread.updated_at).getTime(),
            threadId: thread.id,
            conversationId: conversationId,
            previewText: thread.summary || undefined,
            messageCount: thread.message_count,
          })
        );

        setConversations(uiConversations);
        console.log(
          '[Chat] Loaded',
          uiConversations.length,
          'threads from database'
        );

        // Restore active thread from URL param or default to first
        if (uiConversations.length > 0) {
          const threadFromUrl = searchParamsRef.current.get('thread');
          let selectedConv = uiConversations[0];

          if (threadFromUrl) {
            const urlConv = uiConversations.find((c) => c.id === threadFromUrl);
            if (urlConv) {
              selectedConv = urlConv;
              console.log(
                '[Chat] Restored thread from URL param:',
                urlConv.title
              );
            }
          }

          setActiveConversationId(selectedConv.id);
          activeConversationIdRef.current = selectedConv.id;
          setMessages(selectedConv.messages);
          // Sync with Zustand store for sidebar highlighting
          setCurrentThread(selectedConv.id);
          console.log('[Chat] Active thread:', selectedConv.title);
        }
        return { ok: true, threadCount: uiConversations.length };
      } catch (error: unknown) {
        console.error('[Chat] Failed to load threads from database:', error);

        // Handle 404 - conversation not found (stale data)
        const err = error as {
          response?: { status?: number };
          status_code?: number;
        };
        if (err?.response?.status === 404 || err?.status_code === 404) {
          console.warn(
            '[Chat] Conversation not found (404) - clearing stale data'
          );
          // Clear stale localStorage data
          if (typeof window !== 'undefined') {
            localStorage.removeItem('default-workspace-id');
            localStorage.removeItem('default-conversation-id');
          }
          return { ok: false, threadCount: 0 }; // Signal to caller to retry with fresh data
        }

        throw error;
      }
    },
    [mapDbMessageToUiMessage, setCurrentThread]
  );

  // Initialize workspace and conversation from database
  useEffect(() => {
    // Watchdog: a hung request (socket open, no response) leaves init awaiting
    // forever and the UI stuck on "Initializing…". Surface a recoverable error
    // if init has not settled in time. Cleared once init resolves or unmounts.
    let settled = false;
    const watchdog = setTimeout(() => {
      if (settled) return;
      setInitError(
        'Connecting is taking longer than expected. Check your connection, then retry.'
      );
      setIsInitializing(false);
    }, 15000);

    const initializeFromDb = async () => {
      if (!isAuthenticated) {
        console.log(
          '[Chat] Not authenticated, skipping database initialization'
        );
        settled = true;
        clearTimeout(watchdog);
        setIsInitializing(false);
        return;
      }

      setIsInitializing(true);
      setInitError(null);
      console.log('[Chat] Initializing from database...');

      // Warm-start: read IDs cached on prior visits and fire sidebar + message
      // fetches in parallel with workspace validation. On repeat page loads this
      // collapses 4 sequential calls into 2 parallel ones.
      const persistedConvId =
        typeof window !== 'undefined'
          ? localStorage.getItem('default-conversation-id')
          : null;
      const persistedThreadId = useChatStore.getState().currentThreadId;

      const wsPromise = workspaceService.getOrCreateDefaultWorkspace();

      try {
        let ws: Workspace;

        if (persistedConvId && persistedThreadId) {
          const warmDataPromise = Promise.all([
            workspaceService.listThreads(persistedConvId, { limit: 50 }),
            workspaceService.getThread(persistedThreadId),
          ]).catch(() => null);

          const [resolvedWs, warmData] = await Promise.all([
            wsPromise,
            warmDataPromise,
          ]);
          ws = resolvedWs;
          setWorkspace(ws);

          if (warmData) {
            const [threadListResponse, threadDetail] = warmData;
            const uiConversations: ChatConversation[] =
              threadListResponse.threads.map((thread) => ({
                id: thread.id,
                title: thread.title || 'New Chat',
                messages: [],
                createdAt: new Date(thread.created_at).getTime(),
                updatedAt: new Date(thread.updated_at).getTime(),
                threadId: thread.id,
                conversationId: persistedConvId,
                previewText: thread.summary || undefined,
                messageCount: thread.message_count,
              }));
            setConversations(uiConversations);
            setMessages(threadDetail.messages.map(mapDbMessageToUiMessage));
            setActiveConversationId(persistedThreadId);
            activeConversationIdRef.current = persistedThreadId;
            // Set store ID directly to avoid the loadMessages side-effect in
            // setCurrentThread — we already have messages from getThread above.
            useChatStore.setState({ currentThreadId: persistedThreadId });

            // Still need dbConversation so new-thread creation works
            const conv = await workspaceService.getOrCreateDefaultConversation(
              ws.id
            );
            setDbConversation(conv);
            isHydratedRef.current = true;
            console.log('[Chat] Warm-start initialization complete');
            return;
          }
          // Warm data fetch failed (stale IDs) — fall through to cold init
        } else {
          ws = await wsPromise;
          setWorkspace(ws);
        }

        console.log('[Chat] Workspace:', ws.name);

        // Cold init: full sequential chain
        const conv = await workspaceService.getOrCreateDefaultConversation(
          ws.id
        );
        setDbConversation(conv);
        console.log('[Chat] DB Conversation:', conv.title);

        const loadResult = await loadThreadsFromDb(conv.id);

        if (!loadResult.ok) {
          console.log('[Chat] Retrying with fresh conversation...');
          const freshConv = await workspaceService.createConversation({
            workspace_id: ws.id,
            title: 'New Chat',
            description: 'A new conversation',
          });
          setDbConversation(freshConv);
          console.log('[Chat] Created fresh conversation:', freshConv.title);
          await loadThreadsFromDb(freshConv.id);
        } else if (loadResult.threadCount === 0) {
          // The most-recently-active conversation has no threads. Older
          // conversations in this workspace may still hold the user's threads.
          try {
            const allConversations = await workspaceService.listConversations(
              ws.id,
              { limit: 50 }
            );
            const candidate = allConversations.conversations.find(
              (c) => c.id !== conv.id && (c.thread_count ?? 0) > 0
            );
            if (candidate) {
              console.log(
                '[Chat] Default conversation empty; switching to:',
                candidate.title,
                `(${candidate.thread_count} threads)`
              );
              setDbConversation(candidate);
              if (typeof window !== 'undefined') {
                localStorage.setItem('default-conversation-id', candidate.id);
              }
              await loadThreadsFromDb(candidate.id);
            }
          } catch (fallbackError) {
            console.warn(
              '[Chat] Empty-default fallback failed:',
              fallbackError
            );
          }
        }

        isHydratedRef.current = true;
        console.log('[Chat] Database initialization complete');
      } catch (error: unknown) {
        console.error('[Chat] Failed to initialize from database:', error);

        const err = error as { response?: { status?: number } };
        if (err?.response?.status === 404) {
          console.warn('[Chat] Stale data detected, clearing and retrying...');
          if (typeof window !== 'undefined') {
            localStorage.removeItem('default-workspace-id');
            localStorage.removeItem('default-conversation-id');
          }
          try {
            const ws = await workspaceService.getOrCreateDefaultWorkspace();
            setWorkspace(ws);
            const freshConv = await workspaceService.createConversation({
              workspace_id: ws.id,
              title: 'New Chat',
              description: 'A new conversation',
            });
            setDbConversation(freshConv);
            setConversations([]);
            setMessages([]);
            console.log('[Chat] Created fresh workspace and conversation');
            isHydratedRef.current = true;
            setIsInitializing(false);
            return;
          } catch (retryError) {
            console.error('[Chat] Retry failed:', retryError);
            setInitError(
              'Failed to create new chat session. Please refresh the page.'
            );
            setIsInitializing(false);
            return;
          }
        }

        setInitError(
          error instanceof Error ? error.message : 'Failed to load chat data'
        );
      } finally {
        // Init settled (success or handled error): stand down the watchdog so a
        // slow-but-successful load doesn't flip to the timeout error.
        if (!settled) {
          settled = true;
          clearTimeout(watchdog);
          setIsInitializing(false);
        }
      }
    };

    initializeFromDb();

    return () => {
      settled = true;
      clearTimeout(watchdog);
    };
  }, [isAuthenticated, loadThreadsFromDb, mapDbMessageToUiMessage]);

  // Load messages when active conversation changes (lazy-load from API)
  useEffect(() => {
    if (!activeConversationId) {
      setIsLoadingMessages(false);
      return;
    }
    const conv = conversations.find((c) => c.id === activeConversationId);
    if (!conv) {
      setIsLoadingMessages(false);
      return;
    }

    // If messages already loaded (cached), use them directly
    if (conv.messages.length > 0) {
      setMessages(conv.messages);
      setIsLoadingMessages(false);
      return;
    }

    // Lazy-load messages for this thread using the thread detail endpoint
    let cancelled = false;
    setIsLoadingMessages(true);
    (async () => {
      try {
        const threadDetail =
          await workspaceService.getThread(activeConversationId);
        if (cancelled) return;
        const uiMessages = threadDetail.messages.map(mapDbMessageToUiMessage);
        // Update conversation cache so subsequent switches are instant
        setConversations((prev) =>
          prev.map((c) =>
            c.id === activeConversationId ? { ...c, messages: uiMessages } : c
          )
        );
        setMessages(uiMessages);
      } catch (err) {
        if (!cancelled) {
          console.error('[Chat] Failed to load messages:', err);
        }
      } finally {
        if (!cancelled) {
          setIsLoadingMessages(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only trigger on thread selection, not conversation updates
  }, [activeConversationId, mapDbMessageToUiMessage]);

  return {
    // State
    conversations,
    setConversations,
    activeConversationId,
    setActiveConversationId,
    messages,
    setMessages,
    workspace,
    dbConversation,
    isInitializing,
    initError,
    isLoadingMessages,

    // Refs
    activeConversationIdRef,
    isHydratedRef,

    // Store bindings
    currentThreadIdFromStore,
    setCurrentThread,
    storeMessages,
    addMessageToStore,
    isAuthenticated,

    // Derived
    activeThreadId,
    displayedMessages,

    // Helpers
    mapDbMessageToUiMessage,
    loadThreadsFromDb,
  };
}
