# Chat Page Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Break the 1704-line `chat/page.tsx` into focused modules — custom hooks for business logic, memoized components for rendering — to eliminate unnecessary re-renders and make the code maintainable.

**Architecture:** Extract three custom hooks (`useChatSession`, `useChatStreaming`, `useChatThreadActions`) that encapsulate all state and effects. Extract two presentational components (`ChatMessageList`, `ChatDialogs`). The page becomes a thin orchestrator (~150 lines) that wires hooks to components. Each extraction is a standalone commit that keeps the app working.

**Tech Stack:** Next.js 15, React 18, Zustand, framer-motion, TanStack Query v5

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/app/(dashboard)/chat/page.tsx` | Modify | Slim orchestrator — wires hooks to components |
| `frontend/src/hooks/chat/useChatSession.ts` | Create | Workspace init, thread loading, conversation state, message loading |
| `frontend/src/hooks/chat/useChatStreaming.ts` | Create | handleSubmit (useCallback), handleStop, handleConfirmation, streaming state |
| `frontend/src/hooks/chat/useChatThreadActions.ts` | Create | Rename/delete/bulk-delete handlers + dialog state |
| `frontend/src/hooks/chat/chatTypes.ts` | Create | Shared types (Conversation) + generateConversationTitle helper |
| `frontend/src/components/chat/ChatMessageList.tsx` | Create | Memoized message list rendering (replaces inline AnimatePresence block) |
| `frontend/src/components/chat/ChatDialogs.tsx` | Create | Rename/delete/bulk-delete AlertDialog components |

---

### Task 1: Extract shared types and helper to `chatTypes.ts`

**Files:**
- Create: `frontend/src/hooks/chat/chatTypes.ts`
- Modify: `frontend/app/(dashboard)/chat/page.tsx`

The chat page defines a local `Message` interface (lines 99-106) that is identical to `ChatPageMessage` already exported from `cloudMessageView.ts`. It also defines a `Conversation` interface (lines 109-120) and a `generateConversationTitle` helper (lines 57-93) that will be needed by multiple hooks. Extract the `Conversation` type and helper to a shared file; replace `Message` with `ChatPageMessage` throughout.

- [ ] **Step 1: Create `chatTypes.ts`**

Create `frontend/src/hooks/chat/chatTypes.ts`:

```ts
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';

export interface ChatConversation {
  id: string;
  title: string;
  messages: ChatPageMessage[];
  modelId?: string;
  createdAt: number;
  updatedAt: number;
  threadId: string;
  conversationId: string;
  previewText?: string;
  messageCount?: number;
}

export function generateConversationTitle(message: string): string {
  let title = message.trim();

  const prefixesToRemove = [
    /^(hi|hello|hey|good morning|good afternoon|good evening)[,!\s]*/i,
    /^(can you|could you|would you|please|i need|i want|i'd like)[,\s]*/i,
    /^(help me|assist me|tell me|show me|explain)[,\s]*/i,
  ];

  for (const prefix of prefixesToRemove) {
    title = title.replace(prefix, '');
  }

  title = title.charAt(0).toUpperCase() + title.slice(1);

  if (title.length > 40) {
    const truncated = title.substring(0, 40);
    const lastSpace = truncated.lastIndexOf(' ');
    if (lastSpace > 20) {
      title = truncated.substring(0, lastSpace) + '...';
    } else {
      title = truncated + '...';
    }
  }

  if (title.length < 3) {
    title = message.trim().substring(0, 40);
    if (message.length > 40) title += '...';
  }

  return title;
}
```

- [ ] **Step 2: Update page.tsx to import from chatTypes**

In `frontend/app/(dashboard)/chat/page.tsx`:

1. Add import at the top:
```ts
import { ChatConversation, generateConversationTitle } from '@/hooks/chat/chatTypes';
import { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
```

2. Remove the local `Message` interface (lines 99-106) and the local `Conversation` interface (lines 109-120).

3. Remove the `generateConversationTitle` function (lines 57-93).

4. Replace all occurrences of `Message` (the local type) with `ChatPageMessage` and all occurrences of `Conversation` (the local type) with `ChatConversation`. Be careful NOT to replace `DBConversation` (the import from `@/types/workspace`).

The specific replacements in state declarations:
```ts
// Before:
const [conversations, setConversations] = useState<Conversation[]>([]);
const [messages, setMessages] = useState<Message[]>([]);
// After:
const [conversations, setConversations] = useState<ChatConversation[]>([]);
const [messages, setMessages] = useState<ChatPageMessage[]>([]);
```

And in function signatures — the `mapDbMessageToUiMessage` callback return type:
```ts
// Before:
const mapDbMessageToUiMessage = useCallback((dbMsg: DBChatMessage): Message => {
// After:
const mapDbMessageToUiMessage = useCallback((dbMsg: DBChatMessage): ChatPageMessage => {
```

And `userMessage` / `finalAssistantMessage` / `errorMessage` / `emptyResponseMessage` / other inline message objects:
```ts
// Before:
const userMessage: Message = { ... };
// After:
const userMessage: ChatPageMessage = { ... };
```

And the `uiConversations` array types:
```ts
// Before:
const uiConversations: Conversation[] = threadResponse.threads.map(...)
// After:
const uiConversations: ChatConversation[] = threadResponse.threads.map(...)
```

And the `newConv` object in handleSubmit:
```ts
// Before:
const newConv: Conversation = { ... };
// After:
const newConv: ChatConversation = { ... };
```

- [ ] **Step 3: Verify and commit**

```bash
cd /home/clawdbot/rag-clean/frontend && npx tsc --noEmit 2>&1 | head -30
```

```bash
cd /home/clawdbot/rag-clean && git add frontend/src/hooks/chat/chatTypes.ts "frontend/app/(dashboard)/chat/page.tsx"
git commit -m "refactor(chat): extract shared types and title helper to chatTypes.ts"
```

---

### Task 2: Extract `useChatSession` hook

**Files:**
- Create: `frontend/src/hooks/chat/useChatSession.ts`
- Modify: `frontend/app/(dashboard)/chat/page.tsx`

This hook encapsulates: workspace/conversation initialization from the database, thread loading, message loading on thread switch, the `mapDbMessageToUiMessage` callback, URL-based thread switching, and auth redirect. It returns the state and setters that the page and other hooks need.

- [ ] **Step 1: Create `useChatSession.ts`**

Create `frontend/src/hooks/chat/useChatSession.ts`:

```ts
import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useChatStore } from '@/store/chat-store';
import { useAuthStore } from '@/stores/authStore';
import { workspaceService } from '@/services/workspaceService';
import {
  ChatMessage as DBChatMessage,
  Conversation as DBConversation,
  MessageRole,
  Workspace,
} from '@/types/workspace';
import {
  ChatPageMessage,
  selectDisplayedMessages,
  syncConversationMessagesWithStore,
} from '@/components/chat/shared/cloudMessageView';
import { upsertConversationFromThreadDetail } from '@/components/chat/shared/threadConversationState';
import { normalizeCitation } from '@/utils/citationNormalizer';
import type { ChatConversation } from './chatTypes';

export interface UseChatSessionReturn {
  // State
  conversations: ChatConversation[];
  setConversations: React.Dispatch<React.SetStateAction<ChatConversation[]>>;
  activeConversationId: string | null;
  setActiveConversationId: React.Dispatch<React.SetStateAction<string | null>>;
  activeConversationIdRef: React.MutableRefObject<string | null>;
  messages: ChatPageMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatPageMessage[]>>;
  displayedMessages: ChatPageMessage[];
  workspace: Workspace | null;
  dbConversation: DBConversation | null;
  isInitializing: boolean;
  initError: string | null;
  isLoadingMessages: boolean;
  isAuthenticated: boolean;
  activeThreadId: string | null | undefined;

  // Helpers
  mapDbMessageToUiMessage: (dbMsg: DBChatMessage) => ChatPageMessage;

  // Store bindings
  setCurrentThread: (threadId: string | null) => void;
  addMessageToStore: (threadId: string, message: DBChatMessage) => void;

  // Refs
  isHydratedRef: React.MutableRefObject<boolean>;
}

export function useChatSession(): UseChatSessionReturn {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatPageMessage[]>([]);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [dbConversation, setDbConversation] = useState<DBConversation | null>(null);
  const [isInitializing, setIsInitializing] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

  const activeConversationIdRef = useRef<string | null>(null);
  const isHydratedRef = useRef(false);

  const { isAuthenticated } = useAuthStore();
  const router = useRouter();
  const searchParams = useSearchParams();
  const searchParamsRef = useRef(searchParams);
  searchParamsRef.current = searchParams;

  const currentThreadIdFromStore = useChatStore((state) => state.currentThreadId);
  const setCurrentThread = useChatStore((state) => state.setCurrentThread);
  const storeMessages = useChatStore((state) => state.messages);
  const addMessageToStore = useChatStore((state) => state.addMessageToStore);

  const activeThreadId = currentThreadIdFromStore || activeConversationId;

  const displayedMessages = selectDisplayedMessages({
    localMessages: messages,
    storeMessages: activeThreadId ? storeMessages[activeThreadId] || [] : [],
  });

  const mapDbMessageToUiMessage = useCallback(
    (dbMsg: DBChatMessage): ChatPageMessage => ({
      id: dbMsg.id,
      role: dbMsg.role === MessageRole.USER ? 'user' : 'assistant',
      content: dbMsg.content,
      timestamp: new Date(dbMsg.created_at).getTime(),
      citations: dbMsg.citations?.map(normalizeCitation),
    }),
    []
  );

  // Keep ref in sync
  useEffect(() => {
    activeConversationIdRef.current = activeConversationId;
  }, [activeConversationId]);

  // Reset on logout
  useEffect(() => {
    if (!isAuthenticated) {
      isHydratedRef.current = false;
    }
  }, [isAuthenticated]);

  // Auth redirect
  useEffect(() => {
    if (!isAuthenticated && !isInitializing) {
      const timer = setTimeout(() => {
        router.push('/login');
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, isInitializing, router]);

  // Sync store messages → conversations
  useEffect(() => {
    if (!activeThreadId) return;
    const activeStoreMessages = storeMessages[activeThreadId] || [];
    if (activeStoreMessages.length === 0) return;
    setConversations((prev) =>
      syncConversationMessagesWithStore(prev, activeThreadId, activeStoreMessages)
    );
  }, [activeThreadId, storeMessages]);

  // Load threads from DB
  const loadThreadsFromDb = useCallback(
    async (
      conversationId: string,
      _isRetry = false
    ): Promise<{ ok: boolean; threadCount: number }> => {
      try {
        const threadResponse = await workspaceService.listThreads(conversationId, { limit: 50 });
        const uiConversations: ChatConversation[] = threadResponse.threads.map((thread) => ({
          id: thread.id,
          title: thread.title || 'New Chat',
          messages: [],
          createdAt: new Date(thread.created_at).getTime(),
          updatedAt: new Date(thread.updated_at).getTime(),
          threadId: thread.id,
          conversationId,
          previewText: thread.summary || undefined,
          messageCount: thread.message_count,
        }));
        setConversations(uiConversations);

        if (uiConversations.length > 0) {
          const threadFromUrl = searchParamsRef.current.get('thread');
          let selectedConv = uiConversations[0];
          if (threadFromUrl) {
            const urlConv = uiConversations.find((c) => c.id === threadFromUrl);
            if (urlConv) selectedConv = urlConv;
          }
          setActiveConversationId(selectedConv.id);
          activeConversationIdRef.current = selectedConv.id;
          setMessages(selectedConv.messages);
          setCurrentThread(selectedConv.id);
        }
        return { ok: true, threadCount: uiConversations.length };
      } catch (error: unknown) {
        const err = error as { response?: { status?: number }; status_code?: number };
        if (err?.response?.status === 404 || err?.status_code === 404) {
          if (typeof window !== 'undefined') {
            localStorage.removeItem('default-workspace-id');
            localStorage.removeItem('default-conversation-id');
          }
          return { ok: false, threadCount: 0 };
        }
        throw error;
      }
    },
    [mapDbMessageToUiMessage, setCurrentThread]
  );

  // URL-based thread switching
  useEffect(() => {
    if (conversations.length === 0 || isInitializing) return;
    const threadFromUrl = searchParams.get('thread');
    if (!threadFromUrl) return;

    const targetConv = conversations.find((c) => c.id === threadFromUrl);
    if (targetConv) {
      if (targetConv.id !== activeConversationId) {
        setActiveConversationId(targetConv.id);
        activeConversationIdRef.current = targetConv.id;
        setMessages(targetConv.messages);
        setCurrentThread(targetConv.id);
      }
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const threadDetail = await workspaceService.getThread(threadFromUrl);
        if (cancelled) return;
        const uiMessages = threadDetail.messages.map(mapDbMessageToUiMessage);
        setConversations((prev) =>
          upsertConversationFromThreadDetail(prev, threadDetail, mapDbMessageToUiMessage)
        );
        setActiveConversationId(threadDetail.id);
        activeConversationIdRef.current = threadDetail.id;
        setMessages(uiMessages);
        setCurrentThread(threadDetail.id);
      } catch (error: unknown) {
        if (!cancelled) console.error('[Chat] Failed to fetch requested thread:', error);
      }
    })();
    return () => { cancelled = true; };
  }, [searchParams, conversations, isInitializing, activeConversationId, mapDbMessageToUiMessage, setCurrentThread]);

  // Initialize workspace and conversation
  useEffect(() => {
    const initializeFromDb = async () => {
      if (!isAuthenticated) {
        setIsInitializing(false);
        return;
      }
      setIsInitializing(true);
      setInitError(null);

      const persistedConvId =
        typeof window !== 'undefined' ? localStorage.getItem('default-conversation-id') : null;
      const persistedThreadId = useChatStore.getState().currentThreadId;
      const wsPromise = workspaceService.getOrCreateDefaultWorkspace();

      try {
        let ws: Workspace;
        if (persistedConvId && persistedThreadId) {
          const warmDataPromise = Promise.all([
            workspaceService.listThreads(persistedConvId, { limit: 50 }),
            workspaceService.getThread(persistedThreadId),
          ]).catch(() => null);

          const [resolvedWs, warmData] = await Promise.all([wsPromise, warmDataPromise]);
          ws = resolvedWs;
          setWorkspace(ws);

          if (warmData) {
            const [threadListResponse, threadDetail] = warmData;
            const uiConversations: ChatConversation[] = threadListResponse.threads.map((thread) => ({
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
            useChatStore.setState({ currentThreadId: persistedThreadId });

            const conv = await workspaceService.getOrCreateDefaultConversation(ws.id);
            setDbConversation(conv);
            isHydratedRef.current = true;
            return;
          }
        } else {
          ws = await wsPromise;
          setWorkspace(ws);
        }

        const conv = await workspaceService.getOrCreateDefaultConversation(ws.id);
        setDbConversation(conv);

        const loadResult = await loadThreadsFromDb(conv.id);
        if (!loadResult.ok) {
          const freshConv = await workspaceService.createConversation({
            workspace_id: ws.id,
            title: 'New Chat',
            description: 'A new conversation',
          });
          setDbConversation(freshConv);
          await loadThreadsFromDb(freshConv.id);
        } else if (loadResult.threadCount === 0) {
          try {
            const allConversations = await workspaceService.listConversations(ws.id, { limit: 50 });
            const candidate = allConversations.conversations.find(
              (c) => c.id !== conv.id && (c.thread_count ?? 0) > 0
            );
            if (candidate) {
              setDbConversation(candidate);
              if (typeof window !== 'undefined') {
                localStorage.setItem('default-conversation-id', candidate.id);
              }
              await loadThreadsFromDb(candidate.id);
            }
          } catch (fallbackError) {
            console.warn('[Chat] Empty-default fallback failed:', fallbackError);
          }
        }
        isHydratedRef.current = true;
      } catch (error: unknown) {
        const err = error as { response?: { status?: number } };
        if (err?.response?.status === 404) {
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
            isHydratedRef.current = true;
            setIsInitializing(false);
            return;
          } catch (retryError) {
            setInitError('Failed to create new chat session. Please refresh the page.');
            setIsInitializing(false);
            return;
          }
        }
        setInitError(error instanceof Error ? error.message : 'Failed to load chat data');
      } finally {
        setIsInitializing(false);
      }
    };
    initializeFromDb();
  }, [isAuthenticated, loadThreadsFromDb, mapDbMessageToUiMessage]);

  // Lazy-load messages when active conversation changes
  useEffect(() => {
    if (!activeConversationId) { setIsLoadingMessages(false); return; }
    const conv = conversations.find((c) => c.id === activeConversationId);
    if (!conv) { setIsLoadingMessages(false); return; }
    if (conv.messages.length > 0) { setMessages(conv.messages); setIsLoadingMessages(false); return; }

    let cancelled = false;
    setIsLoadingMessages(true);
    (async () => {
      try {
        const threadDetail = await workspaceService.getThread(activeConversationId);
        if (cancelled) return;
        const uiMessages = threadDetail.messages.map(mapDbMessageToUiMessage);
        setConversations((prev) =>
          prev.map((c) => (c.id === activeConversationId ? { ...c, messages: uiMessages } : c))
        );
        setMessages(uiMessages);
      } catch (err) {
        if (!cancelled) console.error('[Chat] Failed to load messages:', err);
      } finally {
        if (!cancelled) setIsLoadingMessages(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeConversationId, mapDbMessageToUiMessage]);

  return {
    conversations,
    setConversations,
    activeConversationId,
    setActiveConversationId,
    activeConversationIdRef,
    messages,
    setMessages,
    displayedMessages,
    workspace,
    dbConversation,
    isInitializing,
    initError,
    isLoadingMessages,
    isAuthenticated,
    activeThreadId,
    mapDbMessageToUiMessage,
    setCurrentThread,
    addMessageToStore,
    isHydratedRef,
  };
}
```

- [ ] **Step 2: Update page.tsx to use `useChatSession`**

In `frontend/app/(dashboard)/chat/page.tsx`:

1. Add import:
```ts
import { useChatSession } from '@/hooks/chat/useChatSession';
```

2. Remove the following imports that are now inside the hook (they may still be needed elsewhere in the file — only remove if no longer referenced):
   - `selectDisplayedMessages`, `syncConversationMessagesWithStore` from `cloudMessageView`
   - `upsertConversationFromThreadDetail` from `threadConversationState`
   - `useAuthStore` from `@/stores/authStore`
   - `workspaceService` from `@/services/workspaceService`
   - `Workspace` from `@/types/workspace` (keep `ChatMessage as DBChatMessage`, `Conversation as DBConversation`, `MessageRole` if still used)
   - `normalizeCitation` from `@/utils/citationNormalizer`

3. At the top of `ChatPageContent`, replace ALL state declarations, store selectors, and effects that are now in `useChatSession` with a single destructured call:

```ts
const {
  conversations,
  setConversations,
  activeConversationId,
  setActiveConversationId,
  activeConversationIdRef,
  messages,
  setMessages,
  displayedMessages,
  workspace,
  dbConversation,
  isInitializing,
  initError,
  isLoadingMessages,
  isAuthenticated,
  activeThreadId,
  mapDbMessageToUiMessage,
  setCurrentThread,
  addMessageToStore,
  isHydratedRef,
} = useChatSession();
```

4. Remove from `ChatPageContent`:
   - The `conversations` / `activeConversationId` / `messages` / `workspace` / `dbConversation` / `isInitializing` / `initError` / `isLoadingMessages` useState calls
   - The `activeConversationIdRef` / `isHydratedRef` useRef calls
   - The `isAuthenticated` from `useAuthStore()`
   - The `currentThreadIdFromStore` / `setCurrentThread` / `storeMessages` / `addMessageToStore` store selectors
   - The `activeThreadId` derived value
   - The `displayedMessages` derived value
   - The `mapDbMessageToUiMessage` useCallback
   - The `searchParams` / `searchParamsRef` / `router` declarations (keep `router` if still used by remaining code — it will be used by handlers and JSX)
   - The `activeConversationIdRef` sync useEffect
   - The `isAuthenticated` reset useEffect
   - The auth redirect useEffect
   - The store messages sync useEffect
   - The URL thread switching useEffect
   - The `loadThreadsFromDb` useCallback
   - The workspace initialization useEffect
   - The message lazy-loading useEffect

Keep: `useSearchParams` import (still needed for the Suspense boundary), `useRouter` import (still used by remaining handlers/JSX), and the `router` declaration in the component.

- [ ] **Step 3: Verify and commit**

```bash
cd /home/clawdbot/rag-clean/frontend && npx tsc --noEmit 2>&1 | head -30
```

```bash
cd /home/clawdbot/rag-clean && git add frontend/src/hooks/chat/useChatSession.ts "frontend/app/(dashboard)/chat/page.tsx"
git commit -m "refactor(chat): extract useChatSession hook for workspace/thread management"
```

---

### Task 3: Extract `useChatStreaming` hook

**Files:**
- Create: `frontend/src/hooks/chat/useChatStreaming.ts`
- Modify: `frontend/app/(dashboard)/chat/page.tsx`

This hook encapsulates `handleSubmit` (wrapped in `useCallback`), `handleStop`, `handleConfirmation`, and all streaming-related state/refs. It receives session state as parameters.

- [ ] **Step 1: Create `useChatStreaming.ts`**

Create `frontend/src/hooks/chat/useChatStreaming.ts`:

```ts
import { useCallback, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useChatStore } from '@/store/chat-store';
import { useAgentActivityStore } from '@/stores/agentActivityStore';
import { agentChatService } from '@/services/agentChatService';
import { workspaceService } from '@/services/workspaceService';
import { MessageRole } from '@/types/workspace';
import { deriveAgentName, deriveTask } from '@/components/context-rail';
import { getSelectedThreadUrl } from '@/components/chat/shared/chatNavigation';
import { buildThreadCreateRequest } from '@/components/chat/shared/threadCreation';
import { generateConversationTitle } from './chatTypes';
import type { ChatConversation } from './chatTypes';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import type { Conversation as DBConversation } from '@/types/workspace';

interface UseChatStreamingParams {
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
  addMessageToStore: (threadId: string, msg: import('@/types/workspace').ChatMessage) => void;
  enableRAG: boolean;
}

export interface PendingConfirmation {
  threadId: string;
  workspaceThreadId: string;
  confirmation: Record<string, unknown>;
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
  chatInputRef: React.RefObject<HTMLTextAreaElement | null>;
  storeIsStreaming: boolean;
  storeStreamingContent: string;
  streamingTimestampRef: React.MutableRefObject<number>;
  selectedModel: string;
  setSelectedModel: (model: string) => void;
}

export function useChatStreaming({
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
}: UseChatStreamingParams): UseChatStreamingReturn {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [pendingConfirmation, setPendingConfirmation] = useState<PendingConfirmation | null>(null);
  const [isConfirming, setIsConfirming] = useState(false);

  const agentThreadMapRef = useRef<Record<string, string>>({});
  const lastStreamedContentRef = useRef<string>('');
  const abortControllerRef = useRef<AbortController | null>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);
  const streamingTimestampRef = useRef(Date.now());

  const router = useRouter();
  const storeStopStreaming = useChatStore((state) => state.stopStreaming);
  const storeIsStreaming = useChatStore((state) => state.isStreaming);
  const storeStreamingContent = useChatStore((state) => state.streamingContent);
  const selectedModel = useChatStore((state) => state.selectedModel);
  const setSelectedModel = useChatStore((state) => state.setSelectedModel);

  const handleSubmit = useCallback(
    async (contentOverride?: string) => {
      const rawContent = typeof contentOverride === 'string' ? contentOverride : input;
      const content = rawContent.trim();
      if (!content || isLoading || storeIsStreaming) return;

      const userMessage: ChatPageMessage = {
        role: 'user',
        content,
        timestamp: Date.now(),
      };

      const newMessages = [...messages, userMessage];
      setMessages(newMessages);
      setInput('');
      setIsLoading(true);

      let currentConversationId =
        activeConversationIdRef.current || activeConversationId || useChatStore.getState().currentThreadId;
      let currentThreadId = currentConversationId;

      if (!currentConversationId && dbConversation) {
        try {
          const dynamicTitle = generateConversationTitle(content);
          const newThread = await workspaceService.createThread(
            buildThreadCreateRequest({ conversationId: dbConversation.id, title: dynamicTitle })
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
          queueMicrotask(() => router.replace(getSelectedThreadUrl(newThread.id)));
        } catch (error) {
          console.error('[Chat] Failed to create thread:', error);
          setIsLoading(false);
          return;
        }
      }

      try {
        const existingAgentThreadId = currentThreadId
          ? agentThreadMapRef.current[currentThreadId]
          : undefined;

        let assistantContent = '';
        lastStreamedContentRef.current = '';
        let streamHadError = false;
        let streamHadConfirmation = false;

        useChatStore.setState({ isStreaming: true, streamingContent: '' });

        if (currentThreadId) {
          useAgentActivityStore.getState().startRun(currentThreadId, deriveAgentName(), deriveTask(content));
        }

        const streamAbort = new AbortController();
        abortControllerRef.current = streamAbort;

        await agentChatService.streamMessage(
          {
            messages: newMessages.map((m) => ({ role: m.role, content: m.content })),
            page_context: { type: 'chat' },
            use_rag: enableRAG,
            thread_id: existingAgentThreadId,
            model: selectedModel,
          },
          {
            onToken: (token) => {
              assistantContent += token;
              lastStreamedContentRef.current = assistantContent;
              useChatStore.setState({ streamingContent: assistantContent });
            },
            onToolStart: (tool, args) => {
              console.log('[Agent] Tool start:', tool, args);
              if (currentThreadId) {
                useAgentActivityStore.getState().pushToolStart(currentThreadId, tool);
              }
            },
            onToolEnd: (tool, result, isError) => {
              console.log('[Agent] Tool end:', tool, result, { isError });
              if (currentThreadId) {
                useAgentActivityStore.getState().pushToolEnd(currentThreadId, tool, !isError);
              }
            },
            onRagContext: (contexts) => {
              useChatStore.setState({ streamingCitations: contexts });
            },
            onPlan: (steps) => {
              if (!currentThreadId) return;
              const items = (steps ?? [])
                .map((step) => {
                  if (typeof step === 'string') return step;
                  if (step && typeof step === 'object') {
                    const s = step as Record<string, unknown>;
                    return String(s.description ?? s.text ?? s.title ?? s.step ?? '');
                  }
                  return '';
                })
                .filter((s) => s.length > 0);
              if (items.length > 0) {
                useAgentActivityStore.getState().setPlan(currentThreadId, items);
              }
            },
            onTrace: (threadId) => {
              if (currentThreadId) {
                agentThreadMapRef.current[currentThreadId] = threadId;
              }
            },
            onConfirmation: (threadId, confirmation) => {
              streamHadConfirmation = true;
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
              if (currentThreadId) {
                useAgentActivityStore.getState().finishRun(currentThreadId, 'done');
              }
            },
            onError: (error) => {
              console.error('[Agent] Stream error:', error);
              streamHadError = true;
              if (currentThreadId) {
                useAgentActivityStore.getState().finishRun(currentThreadId, 'error');
              }
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

        if (streamHadError || streamHadConfirmation) {
          useChatStore.setState({ isStreaming: false, streamingContent: '', streamingCitations: [] });
          setIsLoading(false);
          return;
        }

        const finalContent = assistantContent || lastStreamedContentRef.current;
        if (!finalContent.trim()) {
          const emptyResponseMessage: ChatPageMessage = {
            role: 'assistant',
            content: '⚠ No response received from the agent. The stream completed without any tokens — check backend logs.',
            timestamp: Date.now(),
          };
          setMessages([...newMessages, emptyResponseMessage]);
          useChatStore.setState({ isStreaming: false, streamingContent: '', streamingCitations: [] });
          setIsLoading(false);
          return;
        }

        const finalAssistantMessage: ChatPageMessage = {
          role: 'assistant',
          content: finalContent,
          timestamp: Date.now(),
        };

        useChatStore.setState({ isStreaming: false, streamingContent: '', streamingCitations: [] });
        lastStreamedContentRef.current = '';

        const finalMessages = [...newMessages, finalAssistantMessage];
        setMessages(finalMessages);

        if (currentThreadId && isAuthenticated) {
          try {
            const savedUserMessage = await workspaceService.createMessage({
              thread_id: currentThreadId,
              content,
              role: MessageRole.USER,
            });
            addMessageToStore(currentThreadId, savedUserMessage);
            const savedAssistantMessage = await workspaceService.createMessage({
              thread_id: currentThreadId,
              content: finalAssistantMessage.content,
              role: MessageRole.ASSISTANT,
            });
            addMessageToStore(currentThreadId, savedAssistantMessage);
          } catch (error) {
            console.error('[Chat] Failed to save messages:', error);
          }
        }

        setConversations((prev) =>
          prev.map((conv) =>
            conv.id === currentConversationId
              ? { ...conv, messages: finalMessages, updatedAt: Date.now() }
              : conv
          )
        );
      } catch (err) {
        console.error('Failed to send message:', err);
        const errorMessage = 'Error: ' + (err instanceof Error ? err.message : 'Failed to get response');
        setMessages([...newMessages, { role: 'assistant', content: errorMessage, timestamp: Date.now() }]);
      } finally {
        setIsLoading(false);
        useChatStore.setState({ isStreaming: false, streamingContent: '', streamingCitations: [] });
        lastStreamedContentRef.current = '';
      }
    },
    [
      input,
      isLoading,
      storeIsStreaming,
      messages,
      setMessages,
      activeConversationId,
      activeConversationIdRef,
      dbConversation,
      setConversations,
      setActiveConversationId,
      setCurrentThread,
      enableRAG,
      selectedModel,
      isAuthenticated,
      addMessageToStore,
      router,
    ]
  );

  const handleStop = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setIsLoading(false);
    if (storeIsStreaming) {
      storeStopStreaming();
    }
    useChatStore.setState({ isStreaming: false, streamingContent: '', streamingCitations: [] });
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
            onToken: (token) => {
              confirmContent += token;
              useChatStore.setState({ streamingContent: confirmContent });
            },
            onToolStart: (tool) => {
              useAgentActivityStore.getState().pushToolStart(pendingConfirmation.workspaceThreadId, tool);
            },
            onToolEnd: (tool, _result, isError) => {
              useAgentActivityStore.getState().pushToolEnd(pendingConfirmation.workspaceThreadId, tool, !isError);
            },
            onDone: () => {
              if (confirmContent.trim()) {
                const msg: ChatPageMessage = { role: 'assistant', content: confirmContent, timestamp: Date.now() };
                setMessages([...confirmMessages, msg]);
              }
            },
            onError: (error) => {
              const msg: ChatPageMessage = { role: 'assistant', content: `Confirmation error: ${error}`, timestamp: Date.now() };
              setMessages([...confirmMessages, msg]);
            },
          },
          confirmAbort.signal
        );
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Network error during confirmation';
        const msg: ChatPageMessage = { role: 'assistant', content: `Confirmation failed: ${errorMessage}`, timestamp: Date.now() };
        setMessages([...confirmMessages, msg]);
      } finally {
        setPendingConfirmation(null);
        setIsConfirming(false);
        useChatStore.setState({ isStreaming: false, streamingContent: '' });
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
    streamingTimestampRef,
    selectedModel,
    setSelectedModel,
  };
}
```

- [ ] **Step 2: Update page.tsx to use `useChatStreaming`**

In `frontend/app/(dashboard)/chat/page.tsx`:

1. Add import:
```ts
import { useChatStreaming } from '@/hooks/chat/useChatStreaming';
```

2. After the `useChatSession()` call, add:
```ts
const [enableRAG, setEnableRAG] = useState(true);

const {
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
  streamingTimestampRef,
  selectedModel,
  setSelectedModel,
} = useChatStreaming({
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
});
```

3. Remove from `ChatPageContent`:
   - The `input` / `isLoading` / `enableRAG` / `pendingConfirmation` / `isConfirming` useState calls
   - The `agentThreadMapRef` / `lastStreamedContentRef` / `abortControllerRef` / `chatInputRef` useRef calls
   - The `storeStopStreaming` / `storeIsStreaming` / `storeStreamingContent` / `selectedModel` / `setSelectedModel` store selectors
   - The `streamingTimestampRef` and its sync useEffect
   - The entire `handleSubmit` function
   - The `handleStop` function
   - The `handleConfirmation` function
   - Remove now-unused imports: `agentChatService`, `buildThreadCreateRequest`, `getSelectedThreadUrl` (if only used in handleSubmit), `deriveAgentName`, `deriveTask`, `useAgentActivityStore`, `MessageRole` (if only used in streaming)

4. Keep: `enableRAG` and `setEnableRAG` (they stay in page.tsx as they're passed to both the hook and the `ChatInput` component). Actually, looking at the code, `enableRAG` is only used in `handleSubmit` and `ChatInput`. Move the `useState` to `page.tsx` as shown above.

- [ ] **Step 3: Verify and commit**

```bash
cd /home/clawdbot/rag-clean/frontend && npx tsc --noEmit 2>&1 | head -30
```

```bash
cd /home/clawdbot/rag-clean && git add frontend/src/hooks/chat/useChatStreaming.ts "frontend/app/(dashboard)/chat/page.tsx"
git commit -m "refactor(chat): extract useChatStreaming hook with useCallback-wrapped handleSubmit"
```

---

### Task 4: Extract `useChatThreadActions` hook

**Files:**
- Create: `frontend/src/hooks/chat/useChatThreadActions.ts`
- Modify: `frontend/app/(dashboard)/chat/page.tsx`

This hook encapsulates rename/delete/bulk-delete handlers and their dialog state.

- [ ] **Step 1: Create `useChatThreadActions.ts`**

Create `frontend/src/hooks/chat/useChatThreadActions.ts`:

```ts
import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { workspaceService } from '@/services/workspaceService';
import { getNewChatUrl } from '@/components/chat/shared/chatNavigation';
import type { ChatConversation } from './chatTypes';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';

interface UseChatThreadActionsParams {
  conversations: ChatConversation[];
  setConversations: React.Dispatch<React.SetStateAction<ChatConversation[]>>;
  activeConversationId: string | null;
  setActiveConversationId: React.Dispatch<React.SetStateAction<string | null>>;
  activeConversationIdRef: React.MutableRefObject<string | null>;
  setMessages: React.Dispatch<React.SetStateAction<ChatPageMessage[]>>;
  setCurrentThread: (threadId: string | null) => void;
}

export interface RenameDialogState {
  open: boolean;
  threadId: string;
  currentTitle: string;
  value: string;
}

export interface DeleteDialogState {
  open: boolean;
  threadId: string;
}

export interface BulkDeleteDialogState {
  open: boolean;
  ids: string[];
}

export interface UseChatThreadActionsReturn {
  renameDialog: RenameDialogState;
  setRenameDialog: React.Dispatch<React.SetStateAction<RenameDialogState>>;
  deleteDialog: DeleteDialogState;
  setDeleteDialog: React.Dispatch<React.SetStateAction<DeleteDialogState>>;
  bulkDeleteDialog: BulkDeleteDialogState;
  setBulkDeleteDialog: React.Dispatch<React.SetStateAction<BulkDeleteDialogState>>;
  handleRenameThread: (threadId: string) => void;
  commitRename: () => Promise<void>;
  handleDeleteThread: (threadId: string) => void;
  commitDeleteThread: () => Promise<void>;
  handleBulkDeleteThreads: (ids: string[]) => void;
  commitBulkDelete: () => Promise<void>;
}

export function useChatThreadActions({
  conversations,
  setConversations,
  activeConversationId,
  setActiveConversationId,
  activeConversationIdRef,
  setMessages,
  setCurrentThread,
}: UseChatThreadActionsParams): UseChatThreadActionsReturn {
  const router = useRouter();

  const [renameDialog, setRenameDialog] = useState<RenameDialogState>({
    open: false,
    threadId: '',
    currentTitle: '',
    value: '',
  });
  const [deleteDialog, setDeleteDialog] = useState<DeleteDialogState>({
    open: false,
    threadId: '',
  });
  const [bulkDeleteDialog, setBulkDeleteDialog] = useState<BulkDeleteDialogState>({
    open: false,
    ids: [],
  });

  const handleRenameThread = useCallback(
    (threadId: string) => {
      const target = conversations.find((c) => c.id === threadId);
      setRenameDialog({
        open: true,
        threadId,
        currentTitle: target?.title ?? '',
        value: target?.title ?? '',
      });
    },
    [conversations]
  );

  const commitRename = useCallback(async () => {
    const { threadId, value, currentTitle } = renameDialog;
    const trimmed = value.trim();
    setRenameDialog((d) => ({ ...d, open: false }));
    if (!trimmed || trimmed === currentTitle) return;
    try {
      const updated = await workspaceService.updateThread(threadId, { title: trimmed });
      const nextTitleValue = updated.title ?? trimmed;
      setConversations((prev) =>
        prev.map((c) => (c.id === threadId ? { ...c, title: nextTitleValue } : c))
      );
    } catch (err) {
      console.error('[Chat] Rename failed', err);
    }
  }, [renameDialog, setConversations]);

  const handleDeleteThread = useCallback((threadId: string) => {
    setDeleteDialog({ open: true, threadId });
  }, []);

  const commitDeleteThread = useCallback(async () => {
    const { threadId } = deleteDialog;
    setDeleteDialog({ open: false, threadId: '' });
    try {
      await workspaceService.deleteThread(threadId);
      setConversations((prev) => prev.filter((c) => c.id !== threadId));
      if (activeConversationId === threadId) {
        setActiveConversationId(null);
        activeConversationIdRef.current = null;
        setMessages([]);
        setCurrentThread(null);
        router.push(getNewChatUrl());
      }
    } catch (err) {
      console.error('[Chat] Delete failed', err);
    }
  }, [deleteDialog, activeConversationId, setConversations, setActiveConversationId, activeConversationIdRef, setMessages, setCurrentThread, router]);

  const handleBulkDeleteThreads = useCallback((ids: string[]) => {
    setBulkDeleteDialog({ open: true, ids });
  }, []);

  const commitBulkDelete = useCallback(async () => {
    const { ids } = bulkDeleteDialog;
    setBulkDeleteDialog({ open: false, ids: [] });
    try {
      await workspaceService.bulkDeleteThreads(ids);
      setConversations((prev) => prev.filter((c) => !ids.includes(c.id)));
      if (activeConversationId && ids.includes(activeConversationId)) {
        setActiveConversationId(null);
        activeConversationIdRef.current = null;
        setMessages([]);
        setCurrentThread(null);
        router.push(getNewChatUrl());
      }
    } catch (err) {
      console.error('[Chat] Bulk delete failed', err);
    }
  }, [bulkDeleteDialog, activeConversationId, setConversations, setActiveConversationId, activeConversationIdRef, setMessages, setCurrentThread, router]);

  return {
    renameDialog,
    setRenameDialog,
    deleteDialog,
    setDeleteDialog,
    bulkDeleteDialog,
    setBulkDeleteDialog,
    handleRenameThread,
    commitRename,
    handleDeleteThread,
    commitDeleteThread,
    handleBulkDeleteThreads,
    commitBulkDelete,
  };
}
```

- [ ] **Step 2: Update page.tsx to use `useChatThreadActions`**

In `frontend/app/(dashboard)/chat/page.tsx`:

1. Add import:
```ts
import { useChatThreadActions } from '@/hooks/chat/useChatThreadActions';
```

2. After the `useChatStreaming()` call, add:
```ts
const {
  renameDialog,
  setRenameDialog,
  deleteDialog,
  setDeleteDialog,
  bulkDeleteDialog,
  setBulkDeleteDialog,
  handleRenameThread,
  commitRename,
  handleDeleteThread,
  commitDeleteThread,
  handleBulkDeleteThreads,
  commitBulkDelete,
} = useChatThreadActions({
  conversations,
  setConversations,
  activeConversationId,
  setActiveConversationId,
  activeConversationIdRef,
  setMessages,
  setCurrentThread,
});
```

3. Remove from `ChatPageContent`:
   - The `renameDialog` / `deleteDialog` / `bulkDeleteDialog` useState calls
   - The `handleRenameThread` / `commitRename` / `handleDeleteThread` / `commitDeleteThread` / `handleBulkDeleteThreads` / `commitBulkDelete` useCallback calls

- [ ] **Step 3: Verify and commit**

```bash
cd /home/clawdbot/rag-clean/frontend && npx tsc --noEmit 2>&1 | head -30
```

```bash
cd /home/clawdbot/rag-clean && git add frontend/src/hooks/chat/useChatThreadActions.ts "frontend/app/(dashboard)/chat/page.tsx"
git commit -m "refactor(chat): extract useChatThreadActions hook for rename/delete dialogs"
```

---

### Task 5: Extract `ChatDialogs` component

**Files:**
- Create: `frontend/src/components/chat/ChatDialogs.tsx`
- Modify: `frontend/app/(dashboard)/chat/page.tsx`

The three `AlertDialog` blocks at the bottom of the JSX (~90 lines) are pure UI driven by the dialog state from `useChatThreadActions`. Extract them to a dedicated component.

- [ ] **Step 1: Create `ChatDialogs.tsx`**

Create `frontend/src/components/chat/ChatDialogs.tsx`:

```tsx
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Input } from '@/components/ui/input';
import type {
  RenameDialogState,
  DeleteDialogState,
  BulkDeleteDialogState,
} from '@/hooks/chat/useChatThreadActions';

interface ChatDialogsProps {
  renameDialog: RenameDialogState;
  setRenameDialog: React.Dispatch<React.SetStateAction<RenameDialogState>>;
  commitRename: () => void;
  deleteDialog: DeleteDialogState;
  setDeleteDialog: React.Dispatch<React.SetStateAction<DeleteDialogState>>;
  commitDeleteThread: () => void;
  bulkDeleteDialog: BulkDeleteDialogState;
  setBulkDeleteDialog: React.Dispatch<React.SetStateAction<BulkDeleteDialogState>>;
  commitBulkDelete: () => void;
}

export function ChatDialogs({
  renameDialog,
  setRenameDialog,
  commitRename,
  deleteDialog,
  setDeleteDialog,
  commitDeleteThread,
  bulkDeleteDialog,
  setBulkDeleteDialog,
  commitBulkDelete,
}: ChatDialogsProps) {
  return (
    <>
      {/* Rename dialog */}
      <AlertDialog
        open={renameDialog.open}
        onOpenChange={(open) => setRenameDialog((d) => ({ ...d, open }))}
      >
        <AlertDialogContent className="terminal-window border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-[var(--terminal-text)] font-mono tracking-tight">
              Rename thread
            </AlertDialogTitle>
          </AlertDialogHeader>
          <Input
            className="font-mono text-sm bg-[var(--terminal-surface)] border-[var(--terminal-border)] text-[var(--terminal-text)]"
            value={renameDialog.value}
            onChange={(e) => setRenameDialog((d) => ({ ...d, value: e.target.value }))}
            onKeyDown={(e) => e.key === 'Enter' && commitRename()}
            autoFocus
          />
          <AlertDialogFooter>
            <AlertDialogCancel className="font-mono text-xs uppercase tracking-wider">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={commitRename}
              className="font-mono text-xs uppercase tracking-wider"
            >
              Rename
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete single thread dialog */}
      <AlertDialog
        open={deleteDialog.open}
        onOpenChange={(open) => setDeleteDialog((d) => ({ ...d, open }))}
      >
        <AlertDialogContent className="terminal-window border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-[var(--terminal-text)] font-mono tracking-tight">
              Delete thread?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-[var(--terminal-text-muted)] font-mono text-xs">
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="font-mono text-xs uppercase tracking-wider">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={commitDeleteThread}
              className="bg-red-500/10 border border-red-500/50 text-red-400 hover:bg-red-500/20 font-mono text-xs uppercase tracking-wider"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Bulk delete dialog */}
      <AlertDialog
        open={bulkDeleteDialog.open}
        onOpenChange={(open) => setBulkDeleteDialog((d) => ({ ...d, open }))}
      >
        <AlertDialogContent className="terminal-window border-[var(--terminal-border)] bg-[var(--terminal-bg)]">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-[var(--terminal-text)] font-mono tracking-tight">
              Delete {bulkDeleteDialog.ids.length} threads?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-[var(--terminal-text-muted)] font-mono text-xs">
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="font-mono text-xs uppercase tracking-wider">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={commitBulkDelete}
              className="bg-red-500/10 border border-red-500/50 text-red-400 hover:bg-red-500/20 font-mono text-xs uppercase tracking-wider"
            >
              Delete all
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
```

- [ ] **Step 2: Update page.tsx to use `ChatDialogs`**

In `frontend/app/(dashboard)/chat/page.tsx`:

1. Add import:
```ts
import { ChatDialogs } from '@/components/chat/ChatDialogs';
```

2. Replace the three `<AlertDialog>` blocks at the bottom of the return JSX (lines ~1594-1681 after prior tasks) with:
```tsx
<ChatDialogs
  renameDialog={renameDialog}
  setRenameDialog={setRenameDialog}
  commitRename={commitRename}
  deleteDialog={deleteDialog}
  setDeleteDialog={setDeleteDialog}
  commitDeleteThread={commitDeleteThread}
  bulkDeleteDialog={bulkDeleteDialog}
  setBulkDeleteDialog={setBulkDeleteDialog}
  commitBulkDelete={commitBulkDelete}
/>
```

3. Remove now-unused imports from page.tsx: `AlertDialog`, `AlertDialogAction`, `AlertDialogCancel`, `AlertDialogContent`, `AlertDialogDescription`, `AlertDialogFooter`, `AlertDialogHeader`, `AlertDialogTitle`, `Input`.

- [ ] **Step 3: Verify and commit**

```bash
cd /home/clawdbot/rag-clean/frontend && npx tsc --noEmit 2>&1 | head -30
```

```bash
cd /home/clawdbot/rag-clean && git add frontend/src/components/chat/ChatDialogs.tsx "frontend/app/(dashboard)/chat/page.tsx"
git commit -m "refactor(chat): extract ChatDialogs component for rename/delete dialogs"
```

---

### Task 6: Extract `ChatMessageList` component

**Files:**
- Create: `frontend/src/components/chat/ChatMessageList.tsx`
- Modify: `frontend/app/(dashboard)/chat/page.tsx`

The message rendering block (~150 lines of JSX with AnimatePresence, message mapping, streaming bubble, and scroll button) is the most render-sensitive section. Extract it into a `React.memo` component to prevent re-renders when parent state unrelated to messages changes. Also remove the staggered animation delay on messages (`delay: Math.min(index * 0.03, 0.3)`) which causes layout thrashing with long conversations.

- [ ] **Step 1: Create `ChatMessageList.tsx`**

Create `frontend/src/components/chat/ChatMessageList.tsx`:

```tsx
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ArrowDown } from 'lucide-react';
import { TerminalChatBubble } from '@/components/chat/shared/TerminalChatBubble';
import { InlineAgentSummary } from '@/components/chat/shared/InlineAgentSummary';
import type { ChatPageMessage } from '@/components/chat/shared/cloudMessageView';
import type { Citation } from '@/utils/citationParser';

interface ChatMessageListProps {
  messages: ChatPageMessage[];
  activeThreadId: string | null | undefined;
  isLoading: boolean;
  storeIsStreaming: boolean;
  storeStreamingContent: string;
  streamingTimestamp: number;
  onRegenerate: (index: number) => void;
  onCitationClick: (citations: Citation[], clickedCitation: Citation) => void;
}

export const ChatMessageList = React.memo(function ChatMessageList({
  messages,
  activeThreadId,
  isLoading,
  storeIsStreaming,
  storeStreamingContent,
  streamingTimestamp,
  onRegenerate,
  onCitationClick,
}: ChatMessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);

  useEffect(() => {
    if (!showScrollButton) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, storeStreamingContent, showScrollButton]);

  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const { scrollTop, scrollHeight, clientHeight } = container;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    setShowScrollButton(!isNearBottom && messages.length > 0);
  }, [messages.length]);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    setShowScrollButton(false);
  }, []);

  return (
    <div className="flex-1 relative min-h-0">
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="h-full overflow-y-auto overflow-x-hidden terminal-scrollbar"
      >
        <div className="max-w-4xl mx-auto pt-4 px-4 pb-6">
          <AnimatePresence>
            {messages.map((message, index) => (
              <motion.div
                key={message.id || `msg-${index}`}
                initial={{ opacity: 0, y: 20, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, transition: { duration: 0.2 } }}
                transition={{
                  duration: 0.4,
                  ease: [0.25, 0.46, 0.45, 0.94],
                }}
              >
                {message.role === 'assistant' &&
                  index === messages.length - 1 &&
                  !storeIsStreaming && (
                    <InlineAgentSummary threadId={activeThreadId} />
                  )}
                <TerminalChatBubble
                  message={message}
                  index={index}
                  modelName={message.role === 'assistant' ? 'NOUS AGENT' : undefined}
                  isTyping={
                    index === messages.length - 1 &&
                    isLoading &&
                    !storeIsStreaming &&
                    message.role === 'assistant'
                  }
                  onRetry={
                    message.role === 'assistant' ? () => onRegenerate(index) : undefined
                  }
                  onCitationClick={onCitationClick}
                />
              </motion.div>
            ))}

            {storeIsStreaming && (
              <motion.div
                key="streaming-message"
                initial={{ opacity: 0, y: 20, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10, transition: { duration: 0.2 } }}
                transition={{ duration: 0.3 }}
              >
                <InlineAgentSummary threadId={activeThreadId} />
                <TerminalChatBubble
                  message={{
                    role: 'assistant',
                    content: '',
                    timestamp: streamingTimestamp,
                  }}
                  index={messages.length}
                  modelName="NOUS AGENT"
                  isStreaming={true}
                  streamingContent={storeStreamingContent}
                  onCitationClick={onCitationClick}
                />
              </motion.div>
            )}
          </AnimatePresence>
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Scroll to bottom button */}
      <AnimatePresence>
        {showScrollButton && (
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
            <motion.button
              initial={{ opacity: 0, y: 10, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.9 }}
              onClick={scrollToBottom}
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--phosphor-green)] text-[var(--terminal-bg)] text-xs font-bold shadow-[0_0_20px_var(--phosphor-green-glow)] hover:shadow-[0_0_30px_var(--phosphor-green-glow)] transition-all pointer-events-auto border border-[var(--terminal-bg)]"
              style={{ fontFamily: "'JetBrains Mono', monospace" }}
            >
              <ArrowDown className="w-4 h-4" />
              <span className="hidden sm:inline tracking-wider">NEW MESSAGES</span>
            </motion.button>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
});
```

Key changes from the original:
- Removed `delay: Math.min(index * 0.03, 0.3)` from message animation transitions (performance anti-pattern with long conversations)
- Wrapped in `React.memo` to skip re-renders when parent state changes but messages haven't
- Self-contained scroll state (refs, handlers, scroll button) — no longer leaks scroll concerns into the page

- [ ] **Step 2: Update page.tsx to use `ChatMessageList`**

In `frontend/app/(dashboard)/chat/page.tsx`:

1. Add import:
```ts
import { ChatMessageList } from '@/components/chat/ChatMessageList';
```

2. The `handleRegenerate` callback should remain in page.tsx (it calls `handleSubmit`). Keep it, but wrap it in `useCallback` properly:
```ts
const handleRegenerate = useCallback(
  (assistantMessageIndex: number) => {
    if (isLoading || storeIsStreaming) return;
    const priorUser = [...displayedMessages]
      .slice(0, assistantMessageIndex)
      .reverse()
      .find((m) => m.role === 'user');
    if (!priorUser) return;
    setMessages((prev) => prev.slice(0, assistantMessageIndex));
    setInput(priorUser.content);
    const contentToSend = priorUser.content;
    setTimeout(() => handleSubmit(contentToSend), 0);
  },
  [displayedMessages, handleSubmit, isLoading, storeIsStreaming, setMessages, setInput]
);
```

3. Add a stable citation click handler:
```ts
const handleCitationClick = useCallback(
  (citations: Citation[], clickedCitation: Citation) => {
    setCitationPanelCitations(citations);
    setActiveCitationId(clickedCitation.documentId);
    setIsCitationPanelOpen(true);
  },
  []
);
```

4. Replace the `{/* Messages Area Wrapper */}` div (the entire `<div className="flex-1 relative min-h-0">` block through its closing `</div>`) with:
```tsx
<ChatMessageList
  messages={displayedMessages}
  activeThreadId={activeThreadId}
  isLoading={isLoading}
  storeIsStreaming={storeIsStreaming}
  storeStreamingContent={storeStreamingContent}
  streamingTimestamp={streamingTimestampRef.current}
  onRegenerate={handleRegenerate}
  onCitationClick={handleCitationClick}
/>
```

Note: The loading/error/initializing/empty states that appear BEFORE the message list (authentication required, initializing, error, loading messages, welcome state) should remain in page.tsx — they are conditional renders that replace the entire area, not part of the message list. Wrap the `ChatMessageList` usage within the existing conditional chain:

```tsx
{!isAuthenticated ? (
  /* auth redirect state — keep as-is */
) : isInitializing ? (
  /* initializing state — keep as-is */
) : initError ? (
  /* error state — keep as-is */
) : isLoadingMessages ? (
  /* loading messages state — keep as-is */
) : displayedMessages.length === 0 && !storeIsStreaming ? (
  <WelcomeState onPromptSelect={handlePromptSelect} selectedModel="nous-agent" />
) : (
  <ChatMessageList
    messages={displayedMessages}
    activeThreadId={activeThreadId}
    isLoading={isLoading}
    storeIsStreaming={storeIsStreaming}
    storeStreamingContent={storeStreamingContent}
    streamingTimestamp={streamingTimestampRef.current}
    onRegenerate={handleRegenerate}
    onCitationClick={handleCitationClick}
  />
)}
```

The loading/error/welcome states still need the scroll container wrapper around them. Keep the outer `<div className="flex-1 relative min-h-0"><div ref={scrollContainerRef} ...>` wrapper around the conditional chain, but move the scroll refs and handler OUT of page.tsx (they're now in `ChatMessageList`). The non-message states don't need scroll handling, so the outer wrapper simplifies to:
```tsx
<div className="flex-1 relative min-h-0">
  <div className="h-full overflow-y-auto overflow-x-hidden terminal-scrollbar">
    {/* conditional chain here */}
  </div>
</div>
```

5. Remove from page.tsx:
   - The `messagesEndRef` / `scrollContainerRef` useRef calls
   - The `showScrollButton` useState
   - The auto-scroll useEffect
   - The `handleScroll` / `scrollToBottom` useCallbacks
   - The `ArrowDown` import from lucide-react (if only used for scroll button)
   - The `AnimatePresence` import from framer-motion (if only used for message list) — keep `motion` if still used for loading/error states

- [ ] **Step 3: Verify and commit**

```bash
cd /home/clawdbot/rag-clean/frontend && npx tsc --noEmit 2>&1 | head -30
```

```bash
cd /home/clawdbot/rag-clean && git add frontend/src/components/chat/ChatMessageList.tsx "frontend/app/(dashboard)/chat/page.tsx"
git commit -m "refactor(chat): extract memoized ChatMessageList, remove stagger animation"
```

---

### Task 7: Clean up page.tsx and add barrel export

**Files:**
- Modify: `frontend/app/(dashboard)/chat/page.tsx`
- Modify: `frontend/src/components/chat/index.ts`

Final cleanup: remove orphaned imports, verify the page is the thin orchestrator it should be (~200 lines), and export the new components from the chat barrel.

- [ ] **Step 1: Audit and clean page.tsx imports**

Read the current `frontend/app/(dashboard)/chat/page.tsx`. Remove any imports that are no longer used after Tasks 1-6. The page should only import:

```ts
'use client';

import { ChatInput, CitationPanel, WelcomeState } from '@/components/chat';
import { ChatHeader } from '@/components/chat/ChatHeader';
import { ChatSidebar } from '@/components/chat/ChatSidebar';
import { ChatDialogs } from '@/components/chat/ChatDialogs';
import { ChatMessageList } from '@/components/chat/ChatMessageList';
import { getNewChatUrl, getSelectedThreadUrl } from '@/components/chat/shared/chatNavigation';
import { useChatSession } from '@/hooks/chat/useChatSession';
import { useChatStreaming } from '@/hooks/chat/useChatStreaming';
import { useChatThreadActions } from '@/hooks/chat/useChatThreadActions';
import { enhancedDocumentService } from '@/services/enhancedDocumentService';
import { Activity, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Suspense, useCallback, useState } from 'react';
import { motion } from 'framer-motion';
import type { Citation } from '@/utils/citationParser';
```

Remove any import not in this list. If `motion` is only used by loading/error states and those are simple enough to not need animation, replace with plain divs — but this is optional; keeping `motion` for those 3 states is fine.

- [ ] **Step 2: Verify the populate-chat-input listener is intact**

The `useEffect` that listens for the `populate-chat-input` custom event (lines ~289-308 in the original) must still be present in `ChatPageContent`. It uses `setInput` and `chatInputRef` — both come from `useChatStreaming`. Verify this effect is still there. If it was accidentally removed in a prior task, re-add it:

```ts
useEffect(() => {
  const handlePopulateChatInput = (event: CustomEvent<string>) => {
    if (event.detail) {
      setInput(event.detail);
      chatInputRef.current?.focus();
    }
  };
  window.addEventListener('populate-chat-input', handlePopulateChatInput as EventListener);
  return () => {
    window.removeEventListener('populate-chat-input', handlePopulateChatInput as EventListener);
  };
}, [setInput, chatInputRef]);
```

- [ ] **Step 3: Add exports to chat barrel**

In `frontend/src/components/chat/index.ts`, add at the end of the named exports section:

```ts
export { ChatDialogs } from './ChatDialogs';
export { ChatMessageList } from './ChatMessageList';
```

And add type exports:

```ts
export type { ChatDialogsProps } from './ChatDialogs';
```

Wait — `ChatDialogsProps` is not exported from `ChatDialogs.tsx` (the interface is not exported). That's fine; skip the type export.

- [ ] **Step 4: Verify final line count and commit**

```bash
wc -l "/home/clawdbot/rag-clean/frontend/app/(dashboard)/chat/page.tsx"
```

Expected: ~200-250 lines (down from 1704).

```bash
cd /home/clawdbot/rag-clean/frontend && npx tsc --noEmit 2>&1 | head -30
```

```bash
cd /home/clawdbot/rag-clean && git add frontend/src/components/chat/index.ts "frontend/app/(dashboard)/chat/page.tsx"
git commit -m "refactor(chat): finalize page.tsx cleanup — 1704→~200 lines"
```

---

### Task 8: Type-check, test, and push

- [ ] **Step 1: Full type-check**

```bash
cd /home/clawdbot/rag-clean/frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 2: Run tests**

```bash
cd /home/clawdbot/rag-clean/frontend && npx vitest run --passWithNoTests 2>&1 | tail -20
```

Expected: all existing tests pass. The existing chat tests (`ChatHeader.test.tsx`, `ChatInput-*.test.tsx`, `ChatSidebar.test.tsx`, `TerminalChatBubble.test.tsx`) should not be affected since we only moved code around, not changed behavior.

- [ ] **Step 3: Push**

```bash
cd /home/clawdbot/rag-clean && git push origin develop
```

---

## Summary

| Task | What | Lines moved |
|------|------|-------------|
| 1 | Types + helper → `chatTypes.ts` | ~65 |
| 2 | Session logic → `useChatSession.ts` | ~350 |
| 3 | Streaming logic → `useChatStreaming.ts` | ~350 |
| 4 | Thread actions → `useChatThreadActions.ts` | ~130 |
| 5 | Dialog JSX → `ChatDialogs.tsx` | ~90 |
| 6 | Message list → `ChatMessageList.tsx` | ~150 |
| 7 | Final cleanup + barrel | ~20 |
| 8 | Verify + push | — |

**Net result:** `page.tsx` drops from 1704 lines to ~200 lines. `handleSubmit` is now `useCallback`-wrapped. Message list is `React.memo`-wrapped. Staggered animation delay removed.
