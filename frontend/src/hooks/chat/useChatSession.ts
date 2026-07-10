'use client';

import {
  mapDbMessageToChatPageMessage,
  mapStoreMessagesToChatMessages,
  selectDisplayedMessages,
  syncConversationMessagesWithStore,
} from '@/components/chat/shared/cloudMessageView';
import toast from 'react-hot-toast';

import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { ChatConversation } from '@/hooks/chat/chatTypes';
import { upsertConversationFromThreadDetail } from '@/components/chat/shared/threadConversationState';
import { workspaceService } from '@/services/workspaceService';
import { useChatStore } from '@/store/chat-store';
import { useAuthStore } from '@/stores/authStore';
import {
  ChatMessage as DBChatMessage,
  Conversation as DBConversation,
  Thread,
  Workspace,
} from '@/types/workspace';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

const THREADS_PAGE_SIZE = 50;

// Shared by every listThreads call site (cold load, warm start, "show older")
// so the sidebar's ChatConversation shape can't drift between them.
function threadToConversation(
  thread: Thread,
  conversationId: string,
  messages: ChatPageMessage[] = []
): ChatConversation {
  return {
    id: thread.id,
    title: thread.title || 'New Chat',
    messages,
    createdAt: new Date(thread.created_at).getTime(),
    updatedAt: new Date(thread.updated_at).getTime(),
    threadId: thread.id,
    conversationId,
    previewText: thread.summary || undefined,
    messageCount: thread.message_count,
  };
}

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
  storeMessages: import('@/types/workspace').ChatMessage[] | null;
  addMessageToStore: (
    threadId: string,
    message: import('@/types/workspace').ChatMessage
  ) => void;
  isAuthenticated: boolean;

  // Derived
  activeThreadId: string | null;
  displayedMessages: ChatPageMessage[];

  // Pagination
  loadOlderMessages: (threadId: string) => Promise<void>;
  messagePagination: Record<
    string,
    { hasMore: boolean; loadingOlder: boolean; loadedCount: number }
  > | null;

  // Sidebar thread pagination (CX8) — the thread list is capped at
  // THREADS_PAGE_SIZE per fetch; loadMoreThreads fetches+appends the next page.
  hasMoreThreads: boolean;
  loadMoreThreads: () => Promise<void>;

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

  // Sidebar thread pagination (CX8): which conversation + page the currently
  // loaded thread list reflects, so loadMoreThreads knows what to fetch next.
  const [hasMoreThreads, setHasMoreThreads] = useState(false);
  const threadsListConvIdRef = useRef<string | null>(null);
  const threadsPageRef = useRef(1);

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
  // `activeThreadId` MUST be declared before the selector below. zustand runs
  // the selector synchronously during render, so referencing activeThreadId
  // while it was still declared further down read it in its temporal dead zone
  // -> "Cannot access 'activeThreadId' before initialization", which crashed
  // /chat on mount in the production bundle.
  const activeThreadId = currentThreadIdFromStore || activeConversationId;
  // Select only the active thread's messages to avoid re-renders when
  // background threads change (streaming elsewhere, FIFO eviction, etc.).
  const activeThreadMessages = useChatStore((state) =>
    activeThreadId ? (state.messages[activeThreadId] ?? null) : null
  );
  const addMessageToStore = useChatStore((state) => state.addMessageToStore);
  const storeLoadOlderMessages = useChatStore(
    (state) => state.loadOlderMessages
  );
  const messagePagination = useChatStore((state) => state.messagePagination);

  // ---- Derived values ----
  const displayedMessages = useMemo(
    () =>
      selectDisplayedMessages({
        localMessages: messages,
        storeMessages: activeThreadMessages ?? [],
      }),
    [messages, activeThreadMessages]
  );

  // ---- Callbacks ----

  // Map a DB/server message to the UI shape. Thin wrapper over the canonical
  // mapper so the lazy-load path (here) and the store path can't drift — a
  // prior second copy silently dropped plan + token_usage on thread reload.
  const mapDbMessageToUiMessage = useCallback(
    (dbMsg: DBChatMessage): ChatPageMessage =>
      mapDbMessageToChatPageMessage(dbMsg),
    []
  );

  // Pagination: load older messages for a thread (prepends to the store list).
  const loadOlderMessages = useCallback(
    async (threadId: string) => {
      await storeLoadOlderMessages(threadId);
    },
    [storeLoadOlderMessages]
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

    const activeStoreMessages = activeThreadMessages || [];

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
  }, [activeThreadId, activeThreadMessages]);

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
          // Set the store id directly (mirror the warm-start path) instead of
          // setCurrentThread, whose loadMessages side-effect would re-fetch the
          // transcript we just got from getThread. The conversation cache is
          // already seeded above (upsertConversationFromThreadDetail), so the
          // lazy-load effect cache-hits.
          useChatStore.setState({ currentThreadId: threadDetail.id });
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
          { page: 1, limit: THREADS_PAGE_SIZE }
        );

        // CX8: record what this list reflects so "show older threads" knows
        // which conversation + page to fetch next.
        threadsListConvIdRef.current = conversationId;
        threadsPageRef.current = 1;
        setHasMoreThreads(threadResponse.has_more);

        // Map threads without loading messages (lazy-loaded on selection)
        const uiConversations: ChatConversation[] = threadResponse.threads.map(
          (thread) => threadToConversation(thread, conversationId)
        );

        setConversations(uiConversations);
        console.log(
          '[Chat] Loaded',
          uiConversations.length,
          'threads from database'
        );

        // Restore active thread from URL param or default to first — UNLESS the
        // user explicitly started a new chat (?new=1), in which case load the
        // sidebar list but leave the composer blank (no auto-open).
        const threadFromUrl = searchParamsRef.current.get('thread');
        const isNewChat = searchParamsRef.current.get('new') === '1';

        if (isNewChat && !threadFromUrl) {
          setActiveConversationId(null);
          activeConversationIdRef.current = null;
          setMessages([]);
          setCurrentThread(null);
          console.log('[Chat] New chat requested; not auto-selecting a thread');
        } else if (uiConversations.length > 0) {
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

  // CX8: fetch the next page of threads for whichever conversation the
  // sidebar list currently reflects, and append (never replace) — a stable
  // callback so it can be passed straight into ChatSidebar (React.memo, #1083).
  const loadMoreThreads = useCallback(async () => {
    const conversationId = threadsListConvIdRef.current;
    if (!conversationId) return;

    const nextPage = threadsPageRef.current + 1;
    try {
      const response = await workspaceService.listThreads(conversationId, {
        page: nextPage,
        limit: THREADS_PAGE_SIZE,
      });

      setConversations((prev) => {
        const existingIds = new Set(prev.map((c) => c.id));
        const appended = response.threads
          .filter((thread) => !existingIds.has(thread.id))
          .map((thread) => threadToConversation(thread, conversationId));
        return [...prev, ...appended];
      });

      threadsPageRef.current = nextPage;
      setHasMoreThreads(response.has_more);
    } catch (error) {
      console.error('[Chat] Failed to load more threads:', error);
      toast.error('Could not load more threads. Please try again.');
    }
  }, []);

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
      // The watchdog (above) may set a provisional "taking too long" error at
      // 15s while init is still running. If init then SUCCEEDS past that point,
      // `finally` must clear it — otherwise a slow-but-successful load is stuck
      // on the error screen forever. Only a genuine failure keeps the error.
      let didFail = false;
      console.log('[Chat] Initializing from database...');

      // Warm-start: read IDs cached on prior visits and fire sidebar + message
      // fetches in parallel with workspace validation. On repeat page loads this
      // collapses 4 sequential calls into 2 parallel ones.
      // Explicit "new chat" intent (?new=1) suppresses warm-start restore so
      // the page lands on a blank composer instead of the last thread.
      const isNewChat = searchParamsRef.current.get('new') === '1';
      const persistedConvId =
        typeof window !== 'undefined'
          ? localStorage.getItem('default-conversation-id')
          : null;
      const persistedThreadId = isNewChat
        ? null
        : useChatStore.getState().currentThreadId;

      const wsPromise = workspaceService.getOrCreateDefaultWorkspace();

      try {
        let ws: Workspace;

        if (persistedConvId && persistedThreadId) {
          const warmDataPromise = Promise.all([
            workspaceService.listThreads(persistedConvId, {
              page: 1,
              limit: THREADS_PAGE_SIZE,
            }),
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
            // Map the warm-fetched transcript ONCE and seed it into the active
            // thread's conversation cache. Without this the lazy-load effect
            // (conv.messages.length > 0 guard) misses, clears `messages` to a
            // skeleton, and re-fetches getThread — a redundant round-trip of the
            // heaviest payload plus a transcript→skeleton→transcript flicker on
            // the most common load path.
            const persistedUiMessages = threadDetail.messages.map(
              mapDbMessageToUiMessage
            );
            const uiConversations: ChatConversation[] =
              threadListResponse.threads.map((thread) =>
                threadToConversation(
                  thread,
                  persistedConvId,
                  thread.id === persistedThreadId ? persistedUiMessages : []
                )
              );
            // CX8: warm-start also seeds the first page of the thread list.
            threadsListConvIdRef.current = persistedConvId;
            threadsPageRef.current = 1;
            setHasMoreThreads(threadListResponse.has_more);
            setConversations(uiConversations);
            setMessages(persistedUiMessages);
            setActiveConversationId(persistedThreadId);
            activeConversationIdRef.current = persistedThreadId;
            // Set store ID directly to avoid the loadMessages side-effect in
            // setCurrentThread — we already have messages from getThread above.
            useChatStore.setState({ currentThreadId: persistedThreadId });
            isHydratedRef.current = true;

            // dbConversation is only needed for NEW-thread creation (post user
            // action), so fetch it OFF the paint path — awaiting it here blocked
            // first paint / isInitializing on an extra HTTP round-trip. The
            // .catch is required: the call re-throws on 404.
            void workspaceService
              .getOrCreateDefaultConversation(ws.id)
              .then(setDbConversation)
              .catch((e) =>
                console.warn('[Chat] default conversation fetch failed', e)
              );
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
            didFail = true;
            setInitError(
              'Failed to create new chat session. Please refresh the page.'
            );
            setIsInitializing(false);
            return;
          }
        }

        didFail = true;
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
        // Clear the provisional watchdog error if init ultimately succeeded —
        // the 15s timeout may have fired before a slow load completed.
        if (!didFail) {
          setInitError(null);
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

    // The store is the per-thread source of truth. When it already holds THIS
    // thread's messages, adopt them into local state — do NOT early-return
    // leaving the PREVIOUS thread's transcript in `messages` (that stale copy
    // both rendered here via the length-based display merge AND got streamed as
    // the wrong thread's history by handleSubmit — the I1 bleed).
    const store = useChatStore.getState();
    const storeMsgs = store.messages[activeConversationId];
    if (storeMsgs && storeMsgs.length > 0) {
      setMessages(mapStoreMessagesToChatMessages(storeMsgs));
      setIsLoadingMessages(false);
      return;
    }
    // ponytail: the fuller fix is to feed displayedMessages solely from the
    // store and delete the local conversations[].messages cache. Until then we
    // fall through to the getThread fetch below (which sets `messages`
    // correctly) rather than skipping on the GLOBAL store.isLoadingMessages
    // flag — that skip left local stale and is what caused the bleed; the rare
    // redundant fetch it avoided is not worth the correctness bug.

    // Neither the conversation cache nor the store has this thread: clear the
    // PREVIOUS thread's transcript NOW, before the async fetch below. Leaving
    // it in `messages` during the fetch window rendered thread A under thread
    // B (length-based display merge) and let a send stream A's history as B's
    // context — the remaining I1 bleed vector.
    setMessages([]);

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
          // Without a signal the thread renders as the empty "start a
          // conversation" welcome state — indistinguishable from a genuinely
          // empty thread — so a transient 500 / expired session looks like
          // data loss. Tell the user it failed so they can retry.
          toast.error('Could not load this conversation. Please try again.');
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
    storeMessages: activeThreadMessages,
    addMessageToStore,
    isAuthenticated,

    // Derived
    activeThreadId,
    displayedMessages,

    // Pagination
    loadOlderMessages,
    messagePagination,
    hasMoreThreads,
    loadMoreThreads,

    // Helpers
    mapDbMessageToUiMessage,
    loadThreadsFromDb,
  };
}
