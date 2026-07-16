/**
 * Chat store selectors.
 *
 * Split out of chat-store.ts (Task 5.4) with no behavior change. Re-exported
 * from `@/store/chat-store` so existing callers are unaffected.
 */
import type {
  ChatMessage,
  Conversation,
  Thread,
  Workspace,
} from '@/types/workspace';
import type { ChatStore } from './types';

export const selectCurrentWorkspace = (state: ChatStore): Workspace | null =>
  state.workspaces.find((w) => w.id === state.currentWorkspaceId) || null;

export const selectCurrentConversation = (
  state: ChatStore
): Conversation | null => {
  if (!state.currentWorkspaceId || !state.currentConversationId) return null;
  const conversations = state.conversations[state.currentWorkspaceId] || [];
  return (
    conversations.find((c) => c.id === state.currentConversationId) || null
  );
};

export const selectCurrentThread = (state: ChatStore): Thread | null => {
  if (!state.currentConversationId || !state.currentThreadId) return null;
  const threads = state.threads[state.currentConversationId] || [];
  return threads.find((t) => t.id === state.currentThreadId) || null;
};

/**
 * Project binding of the current thread, with three states:
 * - `string`  — bound to that project
 * - `null`    — thread is loaded and unbound (a stale ?projectId= URL param
 *               must be ignored)
 * - `undefined` — no thread selected, or thread not in the store yet (the
 *               URL param is the caller's intent)
 */
export const selectCurrentThreadProjectId = (
  state: ChatStore
): string | null | undefined => {
  if (!state.currentThreadId) return undefined;
  const conversationId = state.threadToConversation[state.currentThreadId];
  const indexed = conversationId
    ? state.threads[conversationId]?.find((t) => t.id === state.currentThreadId)
    : undefined;
  if (indexed) return indexed.source_project_id ?? null;
  for (const list of Object.values(state.threads)) {
    const t = list.find((x) => x.id === state.currentThreadId);
    if (t) return t.source_project_id ?? null;
  }
  return undefined;
};

/**
 * Collapse the three-state thread binding with the URL param fallback.
 * The thread row wins; the param only stands in while the thread has not
 * loaded (e.g. arriving from a project page before threads fetch).
 */
export const resolveBoundProjectId = (
  threadProjectId: string | null | undefined,
  urlProjectId: string | null
): string | undefined =>
  threadProjectId === null
    ? undefined
    : (threadProjectId ?? urlProjectId ?? undefined);

export const selectCurrentMessages = (state: ChatStore): ChatMessage[] => {
  if (!state.currentThreadId) return [];
  return state.messages[state.currentThreadId] || [];
};

export const selectConversationsForCurrentWorkspace = (
  state: ChatStore
): Conversation[] => {
  if (!state.currentWorkspaceId) return [];
  return state.conversations[state.currentWorkspaceId] || [];
};

export const selectThreadsForCurrentConversation = (
  state: ChatStore
): Thread[] => {
  if (!state.currentConversationId) return [];
  return state.threads[state.currentConversationId] || [];
};
