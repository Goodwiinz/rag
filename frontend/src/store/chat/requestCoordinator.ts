/**
 * Per-thread newest-page request coordination + the (deprecated) single
 * active streaming AbortController.
 *
 * Deliberately module-scope, outside Immer/Zustand state: AbortController is
 * mutable and must never be proxied or persisted (see chat-store-streaming
 * test: `expect('abortController' in useChatStore.getState()).toBe(false)`).
 *
 * Split out of chat-store.ts (Task 5.4) with no behavior change. Owned here
 * (not per-slice) because both the message slice (refreshMessages/
 * loadOlderMessages/clearThread) and the thread slice (deleteThread,
 * bulkDeleteThreads) must abort a thread's in-flight newest-page request.
 */

export interface NewestPageRequest {
  generation: number;
  controller: AbortController;
}

// Request coordination stays outside Immer state because AbortController is
// mutable and must never be proxied or persisted.
export const newestPageRequests = new Map<string, NewestPageRequest>();

export function abortNewestPageRequest(threadId: string): void {
  const request = newestPageRequests.get(threadId);
  if (!request) return;
  request.controller.abort();
  newestPageRequests.delete(threadId);
}

export function abortAllNewestPageRequests(): void {
  for (const request of newestPageRequests.values()) {
    request.controller.abort();
  }
  newestPageRequests.clear();
}

// Module-level abort controller for the deprecated `streamMessage` v2 path
// (outside Immer state to avoid proxy issues).
export let activeAbortController: AbortController | null = null;

export function setActiveAbortController(
  controller: AbortController | null
): void {
  activeAbortController = controller;
}
