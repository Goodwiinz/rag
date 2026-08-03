'use client';

import {
  isThreadSwitchPending,
  mapDbMessageToChatPageMessage,
  selectDisplayedMessages,
} from '@/components/chat/shared/cloudMessageView';
import toast from 'react-hot-toast';

import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import { getSelectedThreadUrl } from '@/components/chat/shared/chatNavigation';
import { ChatConversation } from '@/hooks/chat/chatTypes';
import { upsertConversationFromThread } from '@/components/chat/shared/threadConversationState';
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
  conversationId: string
): ChatConversation {
  return {
    id: thread.id,
    title: thread.title || 'New Chat',
    messages: [],
    createdAt: new Date(thread.created_at).getTime(),
    updatedAt: new Date(thread.updated_at).getTime(),
    threadId: thread.id,
    conversationId,
    previewText: thread.last_message_preview || thread.summary || undefined,
    messageCount: thread.message_count,
  };
}

export interface UseChatSessionReturn {
  // State
  conversations: ChatConversation[];
  setConversations: React.Dispatch<React.SetStateAction<ChatConversation[]>>;
  messages: ChatPageMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatPageMessage[]>>;
  workspace: Workspace | null;
  dbConversation: DBConversation | null;
  isInitializing: boolean;
  initError: string | null;
  isLoadingMessages: boolean;

  // Refs
  isHydratedRef: React.MutableRefObject<boolean>;

  // Store bindings
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

  // ---- Refs ----
  // URL synchronization reads the latest list without subscribing its effect
  // to conversation-cache writes, which are common during a thread handoff.
  const conversationsRef = useRef(conversations);
  conversationsRef.current = conversations;
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const localMessagesThreadIdRef = useRef<string | null>(null);
  const isHydratedRef = useRef(false);

  // ---- Auth ----
  const { isAuthenticated } = useAuthStore();

  // ---- Store bindings ----
  const activeThreadId = useChatStore((state) => state.currentThreadId);
  const setCurrentThread = useChatStore((state) => state.setCurrentThread);
  // Select only the active thread's messages to avoid re-renders when
  // background threads change (streaming elsewhere, FIFO eviction, etc.).
  const activeThreadMessages = useChatStore((state) =>
    activeThreadId ? (state.messages[activeThreadId] ?? null) : null
  );
  const activeMessageFreshness = useChatStore((state) =>
    activeThreadId ? state.messageFreshness?.[activeThreadId] : undefined
  );
  const addMessageToStore = useChatStore((state) => state.addMessageToStore);
  const storeLoadOlderMessages = useChatStore(
    (state) => state.loadOlderMessages
  );
  const storeLoadingThreadId = useChatStore((state) => state.loadingThreadId);
  const messagePagination = useChatStore((state) => state.messagePagination);

  // ---- Derived values ----
  const displayedMessages = useMemo(
    () =>
      selectDisplayedMessages({
        localMessages: messages,
        storeMessages: activeThreadMessages ?? [],
        messageFreshness: activeMessageFreshness,
      }),
    [messages, activeThreadMessages, activeMessageFreshness]
  );

  // Skeleton gate: only an uncached switch into the active thread counts as
  // "loading" — a send-path fetch of a just-created thread (local turn
  // present) or a background refresh of a cached thread must keep rendering
  // the transcript (#1121 regressions).
  const isThreadLoadPending = isThreadSwitchPending({
    activeThreadId,
    loadingThreadId: storeLoadingThreadId,
    localMessageCount: messages.length,
    storeMessageCount: activeThreadMessages?.length ?? 0,
  });

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
  // Depend on the primitive value, not the search-params object: local state
  // renders may change object identity before router.push updates ?thread=.
  const threadFromUrl = searchParams.get('thread');
  const router = useRouter();
  // Read the router through a ref in callbacks/effects: depending on the
  // router object itself re-runs the init chain whenever its identity
  // changes, which can loop initialization.
  const routerRef = useRef(router);
  routerRef.current = router;

  // ---- Effects ----

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

  // Thread-scoped load-failure signal. The toast fires only when the failed
  // thread is the one on screen, and — unlike the old loading-flag transition
  // watcher — also for background stale-cache refreshes, which have no
  // loading flags. A failed thread the user has already navigated away from
  // never toasts on the wrong conversation. The nonce dedupes re-renders
  // while letting a genuinely new failure re-fire.
  const messageLoadError = useChatStore((state) => state.messageLoadError);
  const lastMessageLoadErrorNonceRef = useRef<number | null>(null);
  useEffect(() => {
    if (!messageLoadError) return;
    if (messageLoadError.threadId !== activeThreadId) return;
    if (lastMessageLoadErrorNonceRef.current === messageLoadError.nonce) return;
    lastMessageLoadErrorNonceRef.current = messageLoadError.nonce;
    toast.error('Could not load this conversation. Please try again.');
  }, [activeThreadId, messageLoadError]);

  // Keep sidebar metadata current without copying the transcript into a
  // second cache. Zustand is the sole canonical transcript owner.
  useEffect(() => {
    if (!activeThreadId || !activeThreadMessages?.length) return;
    const latest = activeThreadMessages[activeThreadMessages.length - 1];
    setConversations((prev) =>
      prev.map((conversation) =>
        conversation.id === activeThreadId
          ? {
              ...conversation,
              messages: [],
              previewText: latest.content,
              messageCount: Math.max(
                conversation.messageCount ?? 0,
                activeThreadMessages.length
              ),
              updatedAt: new Date(latest.created_at).getTime(),
            }
          : conversation
      )
    );
  }, [activeThreadId, activeThreadMessages]);

  // Handle thread switching from URL query param (single source of truth)
  useEffect(() => {
    if (isInitializing || !isAuthenticated) {
      return;
    }

    if (threadFromUrl) {
      console.log('[Chat] Thread switch requested:', threadFromUrl);
      const targetConv = conversationsRef.current.find(
        (c) => c.id === threadFromUrl
      );

      if (targetConv) {
        if (targetConv.id !== useChatStore.getState().currentThreadId) {
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
      const activeThreadAtRequestStart =
        useChatStore.getState().currentThreadId;

      (async () => {
        try {
          const thread = await workspaceService.getThread(threadFromUrl, {
            includeMessages: false,
          });
          // A sidebar selection can happen before router.push replaces the old
          // URL. Do not let this stale detail response overwrite that newer
          // local selection while the query string is catching up.
          if (
            cancelled ||
            useChatStore.getState().currentThreadId !==
              activeThreadAtRequestStart
          ) {
            return;
          }

          setConversations((prev) =>
            upsertConversationFromThread(prev, thread, [])
          );
          setCurrentThread(thread.id);
        } catch (error: unknown) {
          if (!cancelled) {
            console.error('[Chat] Failed to fetch requested thread:', error);
            // Deleted thread, revoked access, or a transient failure: leaving
            // ?thread=<dead-id> in the URL would re-trigger this effect on
            // every render and show whatever thread was previously active
            // with no explanation. Say what happened and drop the dead param.
            toast.error('Could not open that conversation. Please try again.');
            routerRef.current.replace('/chat');
          }
        }
      })();

      return () => {
        cancelled = true;
      };
    }
  }, [threadFromUrl, isInitializing, isAuthenticated, setCurrentThread]);

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
          setCurrentThread(null);
          console.log('[Chat] New chat requested; not auto-selecting a thread');
        } else if (threadFromUrl) {
          const urlConversation = uiConversations.find(
            (conversation) => conversation.id === threadFromUrl
          );
          if (urlConversation) {
            setCurrentThread(urlConversation.id);
            console.log(
              '[Chat] Restored thread from URL param:',
              urlConversation.title
            );
          } else {
            // The URL effect owns uncached deep links, including when the
            // requested thread falls outside the first sidebar page.
            setCurrentThread(null);
          }
        } else if (uiConversations.length > 0) {
          const selectedConversation = uiConversations[0];
          setCurrentThread(selectedConversation.id);
          // Keep the URL in sync with the auto-selection: a bare /chat URL
          // breaks Back-button restoration and loses the thread on share.
          routerRef.current.replace(
            getSelectedThreadUrl(selectedConversation.id)
          );
          console.log('[Chat] Active thread:', selectedConversation.title);
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
    [setCurrentThread]
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
      // Initialization may overlap a first send or sidebar selection. Only the
      // selection that existed when this run began may be restored from warm
      // data; a newer synchronous store selection owns the UI.
      const selectionAtInitializationStart =
        useChatStore.getState().currentThreadId;

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
      const requestedThreadId = searchParamsRef.current.get('thread');
      const restoreThreadId = isNewChat
        ? null
        : (requestedThreadId ?? useChatStore.getState().currentThreadId);

      const wsPromise = workspaceService.getOrCreateDefaultWorkspace();

      try {
        let ws: Workspace;

        if (persistedConvId && restoreThreadId) {
          const warmDataPromise = Promise.all([
            workspaceService.listThreads(persistedConvId, {
              page: 1,
              limit: THREADS_PAGE_SIZE,
            }),
            useChatStore.getState().loadMessages(restoreThreadId),
          ]).catch(() => null);

          const [resolvedWs, warmData] = await Promise.all([
            wsPromise,
            warmDataPromise,
          ]);
          ws = resolvedWs;
          setWorkspace(ws);

          if (warmData) {
            // dbConversation is only needed for NEW-thread creation (post user
            // action), so fetch it OFF the paint path. Start this regardless of
            // whether warm transcript data still owns selection.
            void workspaceService
              .getOrCreateDefaultConversation(ws.id)
              .then(setDbConversation)
              .catch((e) =>
                console.warn('[Chat] default conversation fetch failed', e)
              );

            if (
              useChatStore.getState().currentThreadId !==
              selectionAtInitializationStart
            ) {
              isHydratedRef.current = true;
              setInitError(null);
              console.log(
                '[Chat] Warm-start data ignored after newer thread selection'
              );
              return;
            }

            const [threadListResponse] = warmData;
            let restoreThread = threadListResponse.threads.find(
              (thread) => thread.id === restoreThreadId
            );
            if (!restoreThread) {
              restoreThread = await workspaceService.getThread(
                restoreThreadId,
                { includeMessages: false }
              );
            }

            // A deep-link metadata lookup can overlap a first send or sidebar
            // selection just like the parallel list/page requests above.
            if (
              useChatStore.getState().currentThreadId !==
              selectionAtInitializationStart
            ) {
              isHydratedRef.current = true;
              setInitError(null);
              console.log(
                '[Chat] Warm-start metadata ignored after newer thread selection'
              );
              return;
            }

            let uiConversations: ChatConversation[] =
              threadListResponse.threads.map((thread) =>
                threadToConversation(thread, persistedConvId)
              );
            if (
              !threadListResponse.threads.some(
                (thread) => thread.id === restoreThreadId
              )
            ) {
              uiConversations = upsertConversationFromThread(
                uiConversations,
                restoreThread,
                []
              );
            }
            // CX8: warm-start also seeds the first page of the thread list.
            threadsListConvIdRef.current = persistedConvId;
            threadsPageRef.current = 1;
            setHasMoreThreads(threadListResponse.has_more);
            setConversations(uiConversations);
            setMessages([]);
            // The bounded page and pagination record are already cached, so
            // this selection does not issue another message request.
            setCurrentThread(restoreThreadId);
            // The restore target came from persisted store state, not the
            // URL — sync the address bar so Back/share behave (cold-start
            // auto-select does the same in loadThreadsFromDb).
            if (!requestedThreadId) {
              routerRef.current.replace(getSelectedThreadUrl(restoreThreadId));
            }
            isHydratedRef.current = true;
            setInitError(null);

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
        setInitError(null);
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
            setInitError(null);
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
  }, [isAuthenticated, loadThreadsFromDb, setCurrentThread]);

  // React-local messages are an overlay only. Bind a just-created thread's
  // optimistic turn to its new id, and clear the overlay on every real thread
  // switch. Canonical rows render directly from Zustand.
  //
  // Exception: switching away from a thread MID-TURN parks its overlay
  // (optimistic user message + in-flight assistant state) instead of dropping
  // it — the stream deliberately keeps running across switches, and the store
  // page does not contain the just-sent user row yet. Returning to that thread
  // restores the park so the sent message never vanishes; once the turn
  // commits and the page refreshes to 'fresh', selectDisplayedMessages filters
  // the optimistic copy in favor of the canonical rows.
  const parkedMessagesRef = useRef(new Map<string, ChatPageMessage[]>());
  useEffect(() => {
    const outgoingThreadId = localMessagesThreadIdRef.current;

    if (!activeThreadId) {
      // "New chat" mid-turn: park the outgoing thread's overlay too, so
      // returning to it restores the in-flight turn like any other switch.
      if (
        outgoingThreadId &&
        messagesRef.current.length > 0 &&
        useChatStore.getState().streamingThreadId === outgoingThreadId
      ) {
        parkedMessagesRef.current.set(outgoingThreadId, messagesRef.current);
      }
      localMessagesThreadIdRef.current = null;
      setMessages([]);
      return;
    }

    if (outgoingThreadId === activeThreadId) {
      return;
    }

    if (
      outgoingThreadId &&
      messagesRef.current.length > 0 &&
      useChatStore.getState().streamingThreadId === outgoingThreadId
    ) {
      parkedMessagesRef.current.set(outgoingThreadId, messagesRef.current);
    }

    const isNewThreadHandoff =
      outgoingThreadId === null &&
      messagesRef.current.some((message) => message.source === 'optimistic');
    localMessagesThreadIdRef.current = activeThreadId;
    if (isNewThreadHandoff) {
      return;
    }
    const parked = parkedMessagesRef.current.get(activeThreadId);
    if (parked) {
      parkedMessagesRef.current.delete(activeThreadId);
      setMessages(parked);
      return;
    }
    setMessages([]);
  }, [activeThreadId]);

  return {
    // State
    conversations,
    setConversations,
    messages,
    setMessages,
    workspace,
    dbConversation,
    isInitializing,
    initError,
    isLoadingMessages: isThreadLoadPending,

    // Refs
    isHydratedRef,

    // Store bindings
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
