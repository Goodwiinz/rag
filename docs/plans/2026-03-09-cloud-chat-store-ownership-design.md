# Cloud Chat Store Ownership Design

**Date:** 2026-03-09

## Goal

Refactor the cloud-model chat path so the Zustand chat store is the single owner
of cloud message lifecycle state after streaming begins, while keeping the
existing page-owned thread creation, model selection, and local-model flow.

## Current Problem

The current cloud chat path splits ownership across two frontend layers:

- `frontend/app/(dashboard)/chat/page.tsx`
- `frontend/src/store/chat-store.ts`

The page owns optimistic/local message state and then rehydrates itself from the
store after the SSE stream completes. The store independently owns streaming
state and final message reloads. This creates duplicated control flow and extra
sync points:

1. The page appends an optimistic user message.
2. The page starts `storeStreamMessage(...)`.
3. The store owns SSE token state and reloads messages on `message_done`.
4. The page then reads store messages and copies them back into page-local
   state.

This arrangement increases the chance of:

- duplicate message rendering
- flicker between virtual and persisted messages
- stale local state after streaming
- bugs caused by local and store state drifting apart

## Approved Scope

Conservative refactor, cloud path only.

Keep page-owned:

- thread creation/bootstrap
- selected model and model loading
- input state
- scroll and citation panel state
- local-model/WebLLM path

Move to store ownership for cloud path:

- streaming lifecycle state
- authoritative thread messages after cloud stream start
- final persisted message refresh after `message_done`

## Target Ownership Model

### Before stream

The page may still create a temporary optimistic user message for immediate UI
feedback.

### After stream starts

Once `storeStreamMessage(...)` is called for a cloud-model request, the page no
longer treats its own `messages` state as authoritative for that thread.
Instead:

- the store owns virtual streaming state
- the store owns final persisted messages
- the page renders a store-backed message view for the active thread

### After stream completes

The store handles `message_done` by loading messages for the thread. The page
renders the updated store-backed messages directly instead of remapping them
back into local page state.

## Proposed Data Flow

1. User submits message from `ChatInput`.
2. `page.tsx` validates state and ensures the thread exists.
3. `page.tsx` calls `storeStreamMessage(content, threadId, useRag)`.
4. `chat-store.ts` sets streaming flags and opens the SSE client.
5. `streamingService.ts` posts to `/api/v2/threads/{threadId}/stream`.
6. Backend `StreamService`:
   - persists user message
   - performs optional RAG retrieval
   - streams tokens
   - persists assistant message
7. `chat-store.ts` consumes SSE events:
   - `message_start`
   - `rag_context`
   - `token`
   - `message_done`
8. On `message_done`, `chat-store.ts` calls `loadMessages(threadId)`.
9. `page.tsx` renders:
   - store-backed persisted messages
   - virtual streaming assistant message while `isStreaming` is true

## Implementation Direction

### 1. Add a store-backed cloud message selector

Create a small shared helper or selector that maps store `ChatMessage[]` into
the UI message shape already used by the page.

This mapping should reuse existing citation normalization logic rather than
adding yet another custom mapper.

### 2. Gate page rendering by active mode

For cloud-model streams, the page should render the active thread’s messages
from the store-backed selector instead of from local `messages` after the
stream begins.

For local models, keep the existing local `messages` path untouched.

### 3. Remove post-stream page rehydration logic

Shrink or remove the block in `page.tsx` that:

- reads `useChatStore.getState().messages[currentThreadId]`
- maps DB messages into UI messages
- writes them back into local page state

The store should already be authoritative at that point.

### 4. Keep the virtual streaming bubble

The current virtual assistant bubble is useful and should remain. It should sit
on top of store-backed persisted messages and disappear only after the store has
loaded final thread messages.

## Non-Goals

- No local-model/WebLLM refactor
- No removal of page-local UI state unrelated to cloud streaming
- No broad rewrite of `useChatPersistence`
- No backend API changes

## Risks

### Mixed ownership still exists overall

The page will still own local-model message state while the store owns cloud
message state. This is acceptable for the conservative refactor, but it leaves
some structural duplication in place.

### Thread switching during stream

Because the page can switch active threads independently of the store, care is
needed to ensure that rendering uses the correct thread’s store messages and
does not leak a previous thread’s virtual bubble.

### Optimistic user message duplication

The page’s temporary optimistic user message must not double-render alongside
the persisted user message after store reload. The handoff from local optimistic
message to store-backed persisted list needs explicit tests.

## Verification Strategy

Frontend regression coverage should prove:

1. first cloud message in a new thread appears once
2. store-backed persisted messages replace virtual streaming output cleanly
3. virtual streaming bubble disappears only after final messages are available
4. switching threads does not leak old streaming state into the new thread view

## Recommended Next Step

Write a step-by-step implementation plan that:

- extracts the store-backed cloud message selector
- updates `page.tsx` rendering and handoff logic
- adds regression tests before changing behavior
