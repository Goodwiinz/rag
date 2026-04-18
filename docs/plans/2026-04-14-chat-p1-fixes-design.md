# Chat P1 Fixes — Design Document

**Date:** 2026-04-14  
**Goal:** Fix 3 P1 bugs in the chat page: missing thread_id, dead-end HITL confirmation, silent stream errors.

## Architecture

All 3 bugs live in `handleSubmit()` (lines 600-792) of `chat/page.tsx` and the callbacks passed to `agentChatService.streamMessage()`. Fixes are surgical — no new components, no new endpoints. The HITL confirmation renders as a special chat bubble with action buttons.

## Fix 1: Capture thread_id from trace event

Add `onTrace` to the callbacks block. The backend emits a `trace` SSE event with `thread_id` before any tokens. This is the only reliable way to capture the agent thread for non-HITL flows.

```typescript
onTrace: (threadId) => {
  if (currentThreadId) {
    agentThreadMapRef.current[currentThreadId] = threadId;
  }
  setAgentThreadId(threadId);
},
```

## Fix 2: HITL confirmation as chat bubble

**Flow:**

1. `onConfirmation` fires → set `streamHadConfirmation = true`, populate `pendingConfirmation` state, append a confirmation-type message to the chat
2. Post-stream guard skips normal message append
3. User sees a special assistant bubble with tool name + APPROVE/DENY buttons
4. On click → `handleConfirmation(bool)` calls `agentChatService.streamConfirm()`, streams remaining tokens, appends final assistant message
5. Chat input disabled while `pendingConfirmation` is set

**Confirmation bubble:** Rendered inline via a conditional in the message list. When `msg.type === 'confirmation'`, render the tool name from `pendingConfirmation.confirmation` and two buttons styled in the terminal theme (green for approve, red for deny).

## Fix 3: Guard against blank/error messages

Add `streamHadError` and `streamHadConfirmation` flags before `streamMessage`. Set them in the respective callbacks. After stream resolves:

- If either flag is set, return early (don't append)
- If `assistantContent` is empty after a normal stream, don't append either
- On error, append a message with the error text prefixed

## Files to modify

| File                                         | Changes                                                                                                                                                                                                |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `frontend/app/(dashboard)/chat/page.tsx`     | Add `onTrace` callback, populate `pendingConfirmation` in `onConfirmation`, add `handleConfirmation()`, add post-stream guards, render confirmation bubble in message list, disable input when pending |
| `frontend/src/components/chat/ChatInput.tsx` | Accept `disabled` override prop from parent (currently only checks `isLoading`)                                                                                                                        |
