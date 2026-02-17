# Chat Streaming Design — Hybrid SSE + WebSocket

**Date:** 2026-02-17
**Status:** Approved
**Scope:** Add real-time token streaming to the chat system with inline citations and stop/cancel support.

## Problem

The chat system currently uses a blocking request/response pattern. Users send a message and see no feedback until the full AI response arrives. This creates a poor experience, especially for longer responses that take several seconds to generate.

## Solution: Hybrid SSE + WebSocket

- **SSE** for streaming LLM tokens to the requesting client
- **WebSocket** (existing infrastructure) for notifying other clients/tabs when a message is complete

## SSE Streaming Protocol

**Endpoint:** `POST /api/v2/threads/{thread_id}/stream`

**Request body:**

```json
{ "content": "user message text" }
```

**Response:** `text/event-stream` with typed events:

| Event             | Data                                    | When                                     |
| ----------------- | --------------------------------------- | ---------------------------------------- |
| `message_start`   | `{message_id, thread_id}`               | User message persisted, stream begins    |
| `rag_context`     | `{citations: [...], search_type}`       | RAG search complete, citations available |
| `token`           | `{content: "..."}`                      | Each LLM token as it arrives             |
| `citation_inline` | `{index, position, citation_id}`        | Inline citation marker position          |
| `message_done`    | `{message_id, token_count, latency_ms}` | Full response persisted                  |
| `error`           | `{code, message}`                       | Error during generation                  |

## Backend Architecture

### New Files

| File                                             | Purpose                                        |
| ------------------------------------------------ | ---------------------------------------------- |
| `backend/src/api/threads/stream.py`              | SSE streaming endpoint                         |
| `backend/src/services/threads/stream_service.py` | Orchestrates RAG + LLM streaming + persistence |

### Modified Files

| File                                                          | Change                                         |
| ------------------------------------------------------------- | ---------------------------------------------- |
| `backend/src/services/infrastructure/azure_openai_service.py` | Add `stream_chat_completion()` async generator |
| `backend/src/api/threads/threads.py`                          | Include stream router                          |

### Stream Service Flow

```
POST /api/v2/threads/{thread_id}/stream
  1. Authenticate user, validate thread access
  2. Create user message in DB
  3. yield message_start event
  4. Run RAG hybrid search (vector + graph + keyword)
  5. yield rag_context event with citations
  6. Build LLM message list (system prompt + thread context + RAG context + user message)
  7. Call LLM with stream=True
  8. For each token chunk:
     - Accumulate full_content
     - yield token event
  9. Persist assistant message with citations
  10. yield message_done event
  11. Broadcast message_created via existing WebSocket
```

### LLM Streaming Addition

Add `stream_chat_completion()` to `azure_openai_service.py`:

- Async generator that yields content strings
- Calls OpenAI/Anthropic SDK with `stream=True`
- Handles both providers transparently

### Disconnect Handling

FastAPI `StreamingResponse` detects client disconnect. On disconnect:

- Persist whatever content was generated so far
- Mark message with `is_truncated=True`
- Clean up LLM connection

## Frontend Architecture

### New Files

| File                                        | Purpose                             |
| ------------------------------------------- | ----------------------------------- |
| `frontend/src/services/streamingService.ts` | SSE client consuming the stream     |
| `frontend/src/hooks/useStreamingChat.ts`    | React hook managing streaming state |

### Modified Files

| File                                           | Change                                   |
| ---------------------------------------------- | ---------------------------------------- |
| `frontend/src/store/chat-store.ts`             | Add streaming state + actions            |
| `frontend/src/components/chat/ChatMessage.tsx` | Render streaming text + typing indicator |
| `frontend/src/components/chat/ChatInput.tsx`   | Add stop button during streaming         |

### Chat Store Additions

New state:

```typescript
streamingMessageId: string | null;
streamingContent: string;
isStreaming: boolean;
abortController: AbortController | null;
```

New actions:

```typescript
streamMessage: (content: string, threadId?: string) => Promise<void>;
stopStreaming: () => void;
```

### Streaming Flow (Frontend)

1. User submits message
2. `streamMessage()` called — creates AbortController, sets `isStreaming=true`
3. Empty assistant message bubble appears with pulsing cursor
4. As `token` events arrive, `streamingContent` grows, triggering re-renders
5. On `message_done`, replace streaming state with persisted message from store
6. Stop button calls `abortController.abort()` to cancel mid-stream

### Citation Rendering

- `rag_context` event delivers citations before text streaming begins
- Inline `[1]` markers in streamed text link to citation data
- Citations panel populates progressively

## Error Handling

| Scenario                | Handling                                                              |
| ----------------------- | --------------------------------------------------------------------- |
| LLM provider timeout    | `error` SSE event, persist user message only, show retry button       |
| Network disconnect      | Frontend detects fetch failure, shows "Connection lost" with retry    |
| Client stops mid-stream | Backend persists partial content with `is_truncated=True`             |
| RAG search fails        | Fall back to LLM-only (no citations), send warning event              |
| Concurrent streams      | One active stream per thread; second request returns 409              |
| Token limit hit         | `message_done` with truncation note                                   |
| Cache hit               | Skip streaming, send full response as single `token` + `message_done` |

## Testing Strategy

| Layer                | Test                                                         |
| -------------------- | ------------------------------------------------------------ |
| Backend unit         | `stream_service` with mocked LLM returning async generator   |
| Backend integration  | SSE endpoint returning proper event format                   |
| Frontend unit        | `useStreamingChat` hook with mocked SSE events               |
| Frontend integration | Chat component rendering streaming text                      |
| E2E                  | Playwright: send message, verify progressive text appearance |

## Files Reference (Current System)

### Backend

- `backend/src/api/threads/threads.py:706-754` — Current message creation endpoint
- `backend/src/services/threads/chat_service.py:856-920` — create_assistant_message()
- `backend/src/api/research/chat.py:212-401` — Existing chat completion (non-thread)
- `backend/src/services/infrastructure/azure_openai_service.py:143-200` — LLM wrapper
- `backend/src/services/threads/thread_event_service.py:182-214` — WebSocket broadcasting

### Frontend

- `frontend/src/store/chat-store.ts:894-933` — Current sendMessage action
- `frontend/src/services/realtime-websocket-service.ts` — Existing WebSocket client
- `frontend/src/services/workspaceService.ts` — API wrapper
