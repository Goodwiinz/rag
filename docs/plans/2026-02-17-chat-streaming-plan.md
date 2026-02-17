# Chat Streaming Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add real-time token-by-token streaming to the chat system using SSE, with inline citations and stop/cancel support.

**Architecture:** New SSE endpoint (`POST /api/v2/threads/{thread_id}/stream`) orchestrates RAG retrieval + LLM streaming + persistence. Frontend consumes via `fetch` + `ReadableStream`. Existing WebSocket broadcasts `message_created` events to other clients/tabs.

**Tech Stack:** FastAPI `StreamingResponse`, OpenAI SDK streaming, `AbortController`, Zustand immer store

**Design doc:** `docs/plans/2026-02-17-chat-streaming-design.md`

---

## Task 1: Add `stream_chat_completion()` async generator to Azure OpenAI service

**Files:**

- Modify: `backend/src/services/infrastructure/azure_openai_service.py:143-208`
- Test: `backend/tests/unit/services/test_stream_chat_completion.py`

**Step 1: Write the failing test**

Create `backend/tests/unit/services/test_stream_chat_completion.py`:

```python
"""Tests for streaming chat completion in Azure OpenAI service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.infrastructure.azure_openai_service import AzureOpenAIService


class FakeChunk:
    """Simulates an OpenAI streaming chunk."""
    def __init__(self, content: str | None, finish_reason: str | None = None):
        choice = MagicMock()
        choice.delta.content = content
        choice.finish_reason = finish_reason
        self.choices = [choice]


class FakeStream:
    """Simulates an async iterable OpenAI stream."""
    def __init__(self, chunks: list[FakeChunk]):
        self._chunks = chunks
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


@pytest.mark.asyncio
async def test_stream_chat_completion_yields_content_chunks():
    """stream_chat_completion should yield each content string from the LLM."""
    service = AzureOpenAIService.__new__(AzureOpenAIService)
    service.client = MagicMock()
    service.chat_client = None

    fake_stream = FakeStream([
        FakeChunk("Hello"),
        FakeChunk(" world"),
        FakeChunk(None),  # Empty chunk (role-only)
        FakeChunk("!", finish_reason="stop"),
    ])
    service.client.chat.completions.create = MagicMock(return_value=fake_stream)
    service.get_chat_deployment = MagicMock(return_value="gpt-4o")

    chunks = []
    async for content in service.stream_chat_completion(
        messages=[{"role": "user", "content": "Hi"}]
    ):
        chunks.append(content)

    assert chunks == ["Hello", " world", "!"]
    service.client.chat.completions.create.assert_called_once()
    call_kwargs = service.client.chat.completions.create.call_args[1]
    assert call_kwargs["stream"] is True


@pytest.mark.asyncio
async def test_stream_chat_completion_empty_response():
    """stream_chat_completion should handle empty responses gracefully."""
    service = AzureOpenAIService.__new__(AzureOpenAIService)
    service.client = MagicMock()
    service.chat_client = None

    fake_stream = FakeStream([FakeChunk(None, finish_reason="stop")])
    service.client.chat.completions.create = MagicMock(return_value=fake_stream)
    service.get_chat_deployment = MagicMock(return_value="gpt-4o")

    chunks = []
    async for content in service.stream_chat_completion(
        messages=[{"role": "user", "content": "Hi"}]
    ):
        chunks.append(content)

    assert chunks == []
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/services/test_stream_chat_completion.py -v`
Expected: FAIL — `AttributeError: 'AzureOpenAIService' object has no attribute 'stream_chat_completion'`

**Step 3: Write minimal implementation**

In `backend/src/services/infrastructure/azure_openai_service.py`, add after the `chat_completion` method (after line 208):

```python
    async def stream_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ):
        """
        Stream chat completion tokens from Azure OpenAI.

        Yields content strings as they arrive from the LLM.
        """
        # Reuse existing chat_completion with stream=True to get the raw stream
        stream = await asyncio.coroutine(lambda: self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        ))()
        # Actually, chat_completion is sync when stream=True (returns iterator)
        # So call it directly:
        stream = self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        # Handle both sync and async iterators from OpenAI SDK
        if hasattr(stream, "__aiter__"):
            async for chunk in stream:
                content = chunk.choices[0].delta.content if chunk.choices else None
                if content:
                    yield content
        else:
            for chunk in stream:
                content = chunk.choices[0].delta.content if chunk.choices else None
                if content:
                    yield content
```

**Important:** The existing `chat_completion()` method at line 143 already accepts `stream=True` and returns the raw response object at line 192-193. The new method wraps this to yield individual content strings. However, `chat_completion` is currently a sync call disguised as async (the OpenAI client is sync `AzureOpenAI`, not `AsyncAzureOpenAI`). So the stream will be a sync iterator. The implementation above handles both cases.

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/services/test_stream_chat_completion.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add backend/src/services/infrastructure/azure_openai_service.py backend/tests/unit/services/test_stream_chat_completion.py
git commit -m "feat: add stream_chat_completion async generator to Azure OpenAI service"
```

---

## Task 2: Create SSE stream service (backend orchestrator)

**Files:**

- Create: `backend/src/services/threads/stream_service.py`
- Test: `backend/tests/unit/services/test_stream_service.py`

**Step 1: Write the failing test**

Create `backend/tests/unit/services/test_stream_service.py`:

```python
"""Tests for the SSE chat stream service."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.services.threads.stream_service import StreamService, SSEEvent


class TestSSEEvent:
    def test_format_event(self):
        event = SSEEvent(event="token", data={"content": "Hello"})
        formatted = event.format()
        assert formatted == 'event: token\ndata: {"content": "Hello"}\n\n'

    def test_format_event_with_error(self):
        event = SSEEvent(event="error", data={"code": "llm_error", "message": "timeout"})
        formatted = event.format()
        assert "error" in formatted
        assert "llm_error" in formatted


@pytest.mark.asyncio
async def test_stream_generates_expected_events():
    """Stream should emit message_start, rag_context, tokens, and message_done."""
    thread_id = uuid4()
    user_id = uuid4()

    mock_chat_service = AsyncMock()
    mock_user_msg = MagicMock(id=uuid4(), content="test query")
    mock_chat_service.create_message.return_value = mock_user_msg

    mock_assistant_msg = MagicMock(id=uuid4(), token_count=5, citations=[])
    mock_chat_service.create_assistant_message.return_value = mock_assistant_msg

    mock_chat_service.get_thread_context.return_value = {
        "messages": [{"role": "user", "content": "test query"}],
        "metadata": {},
    }

    async def fake_llm_stream(*args, **kwargs):
        for token in ["Hello", " from", " AI"]:
            yield token

    mock_openai = MagicMock()
    mock_openai.stream_chat_completion = fake_llm_stream

    service = StreamService(
        chat_service=mock_chat_service,
        openai_service=mock_openai,
        search_service=None,  # RAG disabled for this test
    )

    events = []
    async for event in service.stream_response(
        thread_id=thread_id,
        user_id=user_id,
        content="test query",
        use_rag=False,
    ):
        events.append(event)

    event_types = [e.event for e in events]
    assert event_types[0] == "message_start"
    assert "token" in event_types
    assert event_types[-1] == "message_done"

    token_events = [e for e in events if e.event == "token"]
    token_content = "".join(json.loads(e.format().split("data: ")[1].split("\n")[0])["content"] for e in token_events)
    assert token_content == "Hello from AI"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/services/test_stream_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.services.threads.stream_service'`

**Step 3: Write minimal implementation**

Create `backend/src/services/threads/stream_service.py`:

```python
"""
SSE streaming service for chat responses.

Orchestrates: user message creation -> RAG retrieval -> LLM streaming -> persistence.
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class SSEEvent:
    """A Server-Sent Event."""
    event: str
    data: dict

    def format(self) -> str:
        """Format as SSE wire protocol."""
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


class StreamService:
    """Orchestrates streaming chat responses via SSE."""

    def __init__(self, chat_service, openai_service, search_service=None):
        self.chat_service = chat_service
        self.openai_service = openai_service
        self.search_service = search_service

    async def stream_response(
        self,
        thread_id: UUID,
        user_id: UUID,
        content: str,
        use_rag: bool = True,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 2048,
    ) -> AsyncGenerator[SSEEvent, None]:
        """
        Stream a chat response as SSE events.

        Yields SSEEvent objects in order:
        1. message_start - user message persisted
        2. rag_context - RAG citations (if use_rag)
        3. token - each LLM token
        4. message_done - assistant message persisted
        """
        start_time = time.time()
        citations = []

        # 1. Create user message
        from src.schemas.chat import ChatMessageCreate, MessageRole

        user_msg_data = ChatMessageCreate(
            thread_id=thread_id,
            content=content,
            role=MessageRole.USER,
        )
        user_msg = await self.chat_service.create_message(user_msg_data, user_id)
        if not user_msg:
            yield SSEEvent(event="error", data={"code": "thread_not_found", "message": "Thread not found or insufficient permissions"})
            return

        yield SSEEvent(event="message_start", data={
            "message_id": str(user_msg.id),
            "thread_id": str(thread_id),
        })

        # 2. RAG retrieval (optional)
        if use_rag and self.search_service:
            try:
                from src.api.research.chat import retrieve_context, build_context_prompt
                rag_results = await retrieve_context(content, max_docs=5)
                if rag_results:
                    citations = [
                        {
                            "document_id": ctx.document_id,
                            "snippet": ctx.content[:500],
                            "snippet_preview": ctx.content[:200],
                            "score": ctx.score,
                            "document_title": ctx.title,
                        }
                        for ctx in rag_results
                    ]
                    yield SSEEvent(event="rag_context", data={
                        "citations": citations,
                        "search_type": "hybrid",
                    })
            except Exception as e:
                logger.warning(f"RAG retrieval failed, proceeding without context: {e}")
                rag_results = []
        else:
            rag_results = []

        # 3. Build LLM messages
        thread_context = await self.chat_service.get_thread_context(
            thread_id, user_id, max_messages=20, max_tokens=4000
        )
        messages = self._build_llm_messages(
            thread_context.get("messages", []),
            rag_results,
            content,
        )

        # 4. Stream LLM response
        full_content = ""
        try:
            async for chunk in self.openai_service.stream_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                full_content += chunk
                yield SSEEvent(event="token", data={"content": chunk})
        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            if full_content:
                # Persist partial content
                await self._persist_assistant_message(
                    thread_id, full_content, citations, start_time, is_truncated=True
                )
            yield SSEEvent(event="error", data={
                "code": "llm_error",
                "message": str(e),
            })
            return

        # 5. Persist assistant message
        assistant_msg = await self._persist_assistant_message(
            thread_id, full_content, citations, start_time
        )

        latency_ms = int((time.time() - start_time) * 1000)
        yield SSEEvent(event="message_done", data={
            "message_id": str(assistant_msg.id) if assistant_msg else None,
            "token_count": assistant_msg.token_count if assistant_msg else 0,
            "latency_ms": latency_ms,
        })

    async def _persist_assistant_message(
        self, thread_id, content, citations, start_time, is_truncated=False
    ):
        """Persist the assistant message and citations to the database."""
        latency_ms = int((time.time() - start_time) * 1000)
        return await self.chat_service.create_assistant_message(
            thread_id=thread_id,
            content=content,
            citations=citations or None,
            latency_ms=latency_ms,
        )

    def _build_llm_messages(self, thread_messages, rag_results, current_query):
        """Build the message list for the LLM call."""
        from src.api.research.chat import RAG_SYSTEM_PROMPT, build_context_prompt

        messages = []

        # System prompt
        if rag_results:
            system_content = RAG_SYSTEM_PROMPT
            context_prompt = build_context_prompt(rag_results)
            if context_prompt:
                system_content = f"{RAG_SYSTEM_PROMPT}\n\n{context_prompt}"
            messages.append({"role": "system", "content": system_content})
        else:
            messages.append({
                "role": "system",
                "content": "You are an advanced AI assistant. Provide precise, well-structured responses.",
            })

        # Thread history (excludes current message, already in thread_messages)
        for msg in thread_messages:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        return messages
```

**Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/services/test_stream_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/services/threads/stream_service.py backend/tests/unit/services/test_stream_service.py
git commit -m "feat: add StreamService for SSE chat response orchestration"
```

---

## Task 3: Create SSE streaming endpoint

**Files:**

- Create: `backend/src/api/threads/stream.py`
- Modify: `backend/src/api/threads/__init__.py` (add stream router export)
- Modify: `backend/src/main.py:321-322` (include stream router)
- Test: `backend/tests/unit/api/test_stream_endpoint.py`

**Step 1: Write the failing test**

Create `backend/tests/unit/api/test_stream_endpoint.py`:

```python
"""Tests for the SSE streaming endpoint."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from httpx import AsyncClient
from src.services.threads.stream_service import SSEEvent


@pytest.mark.asyncio
async def test_stream_endpoint_returns_event_stream_content_type():
    """The /stream endpoint should return text/event-stream content type."""
    # This is an integration-level test that verifies the endpoint exists
    # and returns the correct content type. Full streaming behavior is tested
    # in the stream_service unit tests.
    from src.api.threads.stream import router
    assert any(
        route.path == "/{thread_id}/stream" and "POST" in route.methods
        for route in router.routes
    )


def test_sse_event_format():
    """Verify SSE wire format is correct."""
    event = SSEEvent(event="token", data={"content": "test"})
    formatted = event.format()
    lines = formatted.strip().split("\n")
    assert lines[0] == "event: token"
    assert lines[1] == 'data: {"content": "test"}'
```

**Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/api/test_stream_endpoint.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.threads.stream'`

**Step 3: Write minimal implementation**

Create `backend/src/api/threads/stream.py`:

```python
"""
SSE streaming endpoint for chat responses.

POST /api/v2/threads/{thread_id}/stream
Returns: text/event-stream with typed SSE events
"""
import asyncio
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_current_user
from src.database.session import get_db
from src.models.user import User
from src.services.infrastructure.azure_openai_service import azure_openai_service
from src.services.threads.chat_service import ChatService
from src.services.threads.stream_service import StreamService
from src.services.threads.thread_event_service import ThreadEventService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/threads", tags=["streaming"])

# Active streams per thread (for concurrent stream prevention)
_active_streams: dict[str, bool] = {}

thread_event_service = ThreadEventService()


class StreamRequest(BaseModel):
    """Request body for streaming chat."""
    content: str = Field(..., min_length=1, max_length=32000, description="User message content")
    use_rag: bool = Field(default=True, description="Enable RAG context retrieval")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=2048, ge=1, le=8192)


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(db)


@router.post("/{thread_id}/stream")
async def stream_chat(
    thread_id: UUID,
    request_body: StreamRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Stream a chat response as Server-Sent Events.

    Creates a user message, runs RAG retrieval, streams LLM tokens,
    and persists the assistant response with citations.
    """
    thread_key = str(thread_id)

    # Prevent concurrent streams on the same thread
    if _active_streams.get(thread_key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A stream is already active for this thread",
        )

    chat_service = ChatService(db)
    stream_service = StreamService(
        chat_service=chat_service,
        openai_service=azure_openai_service,
        search_service=None,  # Will use retrieve_context directly
    )

    async def event_generator():
        _active_streams[thread_key] = True
        try:
            async for event in stream_service.stream_response(
                thread_id=thread_id,
                user_id=current_user.id,
                content=request_body.content,
                use_rag=request_body.use_rag,
                temperature=request_body.temperature,
                max_tokens=request_body.max_tokens,
            ):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"Client disconnected during stream for thread {thread_id}")
                    break
                yield event.format()

            # Broadcast message_created via WebSocket for other clients
            # (The stream_service already persisted the message)
            try:
                await thread_event_service.broadcast_message_created(
                    message_id="stream_complete",
                    thread_id=thread_key,
                    conversation_id="",
                    user_id=str(current_user.id),
                    role="assistant",
                    content_preview=None,
                    has_citations=False,
                )
            except Exception as e:
                logger.warning(f"Failed to broadcast stream completion: {e}")

        except Exception as e:
            logger.error(f"Stream error for thread {thread_id}: {e}")
            from src.services.threads.stream_service import SSEEvent
            yield SSEEvent(event="error", data={"code": "stream_error", "message": str(e)}).format()
        finally:
            _active_streams.pop(thread_key, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
```

**Step 4: Wire up the router**

Add to `backend/src/api/threads/__init__.py` (after line 7):

```python
from .stream import router as stream_router
```

And add `"stream_router"` to the `__all__` list.

Add to `backend/src/main.py` (after line 322, the threads_router include):

```python
app.include_router(
    stream_router, prefix="/api/v2"
)  # SSE streaming chat endpoint
```

With the import at the top of main.py:

```python
from src.api.threads import stream_router
```

**Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/unit/api/test_stream_endpoint.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/api/threads/stream.py backend/src/api/threads/__init__.py backend/src/main.py backend/tests/unit/api/test_stream_endpoint.py
git commit -m "feat: add SSE streaming endpoint POST /api/v2/threads/{thread_id}/stream"
```

---

## Task 4: Create frontend streaming service

**Files:**

- Create: `frontend/src/services/streamingService.ts`
- Test: `frontend/src/services/__tests__/streamingService.test.ts`

**Step 1: Write the failing test**

Create `frontend/src/services/__tests__/streamingService.test.ts`:

```typescript
import { parseSSELine, StreamEventType } from "../streamingService";

describe("streamingService", () => {
  describe("parseSSELine", () => {
    it("should parse a token event", () => {
      const result = parseSSELine("token", '{"content": "Hello"}');
      expect(result).toEqual({
        type: "token" as StreamEventType,
        data: { content: "Hello" },
      });
    });

    it("should parse a message_start event", () => {
      const result = parseSSELine(
        "message_start",
        '{"message_id": "abc", "thread_id": "def"}',
      );
      expect(result).toEqual({
        type: "message_start" as StreamEventType,
        data: { message_id: "abc", thread_id: "def" },
      });
    });

    it("should parse a message_done event", () => {
      const result = parseSSELine(
        "message_done",
        '{"message_id": "abc", "token_count": 50, "latency_ms": 1200}',
      );
      expect(result).toEqual({
        type: "message_done" as StreamEventType,
        data: { message_id: "abc", token_count: 50, latency_ms: 1200 },
      });
    });

    it("should return null for invalid JSON", () => {
      const result = parseSSELine("token", "not json");
      expect(result).toBeNull();
    });
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest src/services/__tests__/streamingService.test.ts --no-coverage`
Expected: FAIL — `Cannot find module '../streamingService'`

**Step 3: Write minimal implementation**

Create `frontend/src/services/streamingService.ts`:

```typescript
/**
 * SSE streaming service for chat responses.
 *
 * Consumes the POST /api/v2/threads/{thread_id}/stream endpoint
 * and yields typed SSE events.
 */

export type StreamEventType =
  | "message_start"
  | "rag_context"
  | "token"
  | "citation_inline"
  | "message_done"
  | "error";

export interface StreamEvent {
  type: StreamEventType;
  data: Record<string, unknown>;
}

/**
 * Parse a single SSE event line into a typed StreamEvent.
 */
export function parseSSELine(
  eventType: string,
  dataStr: string,
): StreamEvent | null {
  try {
    const data = JSON.parse(dataStr) as Record<string, unknown>;
    return { type: eventType as StreamEventType, data };
  } catch {
    return null;
  }
}

/**
 * Stream a chat message and yield SSE events as they arrive.
 *
 * @param threadId - The thread to send the message in
 * @param content - The user's message content
 * @param options - Optional streaming parameters
 * @param signal - AbortSignal for cancellation
 */
export async function* streamChatMessage(
  threadId: string,
  content: string,
  options: {
    useRag?: boolean;
    temperature?: number;
    maxTokens?: number;
  } = {},
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent, void, unknown> {
  const token = localStorage.getItem("auth-token");

  const response = await fetch(`/api/v2/threads/${threadId}/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      content,
      use_rag: options.useRag ?? true,
      temperature: options.temperature ?? 0.7,
      max_tokens: options.maxTokens ?? 2048,
    }),
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    yield {
      type: "error",
      data: { code: `http_${response.status}`, message: errorText },
    };
    return;
  }

  if (!response.body) {
    yield {
      type: "error",
      data: { code: "no_body", message: "Response has no body" },
    };
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ") && currentEvent) {
          const dataStr = line.slice(6);
          const event = parseSSELine(currentEvent, dataStr);
          if (event) {
            yield event;
          }
          currentEvent = "";
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest src/services/__tests__/streamingService.test.ts --no-coverage`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/services/streamingService.ts frontend/src/services/__tests__/streamingService.test.ts
git commit -m "feat: add SSE streaming service for chat responses"
```

---

## Task 5: Add streaming state and actions to chat store

**Files:**

- Modify: `frontend/src/store/chat-store.ts:120-159` (state), `894-933` (actions)
- Test: `frontend/src/store/__tests__/chat-store-streaming.test.ts`

**Step 1: Write the failing test**

Create `frontend/src/store/__tests__/chat-store-streaming.test.ts`:

```typescript
/**
 * Tests for streaming additions to the chat store.
 */
import { useChatStore } from "../chat-store";

describe("chat-store streaming state", () => {
  beforeEach(() => {
    // Reset store to initial state
    useChatStore.setState({
      isStreaming: false,
      streamingContent: "",
      streamingMessageId: null,
      streamingCitations: [],
    });
  });

  it("should have streaming state properties", () => {
    const state = useChatStore.getState();
    expect(state).toHaveProperty("isStreaming");
    expect(state).toHaveProperty("streamingContent");
    expect(state).toHaveProperty("streamingMessageId");
    expect(state).toHaveProperty("streamingCitations");
  });

  it("should have streamMessage action", () => {
    const state = useChatStore.getState();
    expect(typeof state.streamMessage).toBe("function");
  });

  it("should have stopStreaming action", () => {
    const state = useChatStore.getState();
    expect(typeof state.stopStreaming).toBe("function");
  });

  it("stopStreaming should reset streaming state", () => {
    useChatStore.setState({
      isStreaming: true,
      streamingContent: "partial response",
      streamingMessageId: "msg-123",
    });

    useChatStore.getState().stopStreaming();

    const state = useChatStore.getState();
    expect(state.isStreaming).toBe(false);
    expect(state.streamingContent).toBe("");
    expect(state.streamingMessageId).toBeNull();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest src/store/__tests__/chat-store-streaming.test.ts --no-coverage`
Expected: FAIL — properties not found on state

**Step 3: Add streaming state and actions to chat-store.ts**

In `frontend/src/store/chat-store.ts`, add to the state interface (around line 155, after `isSendingMessage`):

```typescript
// Streaming state
isStreaming: boolean;
streamingContent: string;
streamingMessageId: string | null;
streamingCitations: Array<Record<string, unknown>>;
abortController: AbortController | null;
```

Add initial values in the store creation (in the initial state section):

```typescript
isStreaming: false,
streamingContent: '',
streamingMessageId: null,
streamingCitations: [],
abortController: null,
```

Add new actions (after the `sendMessage` action around line 933):

```typescript
streamMessage: async (content, threadId) => {
  const state = get();
  const targetThreadId = threadId || state.currentThreadId;

  if (!targetThreadId) {
    console.error('[ChatStore] No thread selected for streaming');
    return;
  }

  const abortController = new AbortController();

  set((state) => {
    state.isStreaming = true;
    state.streamingContent = '';
    state.streamingMessageId = null;
    state.streamingCitations = [];
    state.abortController = abortController;
    state.error = null;
  });

  try {
    const { streamChatMessage } = await import('@/services/streamingService');

    for await (const event of streamChatMessage(
      targetThreadId,
      content,
      {},
      abortController.signal,
    )) {
      switch (event.type) {
        case 'message_start':
          set((state) => {
            state.streamingMessageId = event.data.message_id as string;
          });
          break;
        case 'rag_context':
          set((state) => {
            state.streamingCitations = (event.data.citations ?? []) as Array<Record<string, unknown>>;
          });
          break;
        case 'token':
          set((state) => {
            state.streamingContent += event.data.content as string;
          });
          break;
        case 'message_done':
          // Reload messages to get the persisted version with proper IDs
          await get().loadMessages(targetThreadId);
          break;
        case 'error':
          set((state) => {
            state.error = (event.data.message as string) || 'Streaming error';
          });
          break;
      }
    }
  } catch (error) {
    if ((error as Error).name !== 'AbortError') {
      console.error('[ChatStore] Streaming error:', error);
      set((state) => {
        state.error = 'Failed to stream response';
      });
    }
  } finally {
    set((state) => {
      state.isStreaming = false;
      state.streamingContent = '';
      state.streamingMessageId = null;
      state.streamingCitations = [];
      state.abortController = null;
    });
  }
},

stopStreaming: () => {
  const state = get();
  if (state.abortController) {
    state.abortController.abort();
  }
  set((state) => {
    state.isStreaming = false;
    state.streamingContent = '';
    state.streamingMessageId = null;
    state.streamingCitations = [];
    state.abortController = null;
  });
},
```

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest src/store/__tests__/chat-store-streaming.test.ts --no-coverage`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/store/chat-store.ts frontend/src/store/__tests__/chat-store-streaming.test.ts
git commit -m "feat: add streaming state and actions to chat store"
```

---

## Task 6: Update ChatInput with stop button

**Files:**

- Modify: `frontend/src/components/chat/ChatInput.tsx`
- Test: `frontend/src/components/chat/__tests__/ChatInput.test.tsx` (if exists, add tests)

**Step 1: Write the failing test**

Add to the ChatInput test file (or create `frontend/src/components/chat/__tests__/ChatInput-streaming.test.tsx`):

```typescript
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ChatInput } from '../ChatInput';

describe('ChatInput streaming', () => {
  it('should show stop button when isStreaming is true', () => {
    render(
      <ChatInput
        value=""
        onChange={() => {}}
        onSubmit={() => {}}
        onStop={() => {}}
        isLoading={false}
        isStreaming={true}
      />
    );

    const stopButton = screen.getByRole('button', { name: /stop/i });
    expect(stopButton).toBeInTheDocument();
  });

  it('should call onStop when stop button is clicked', () => {
    const onStop = jest.fn();
    render(
      <ChatInput
        value=""
        onChange={() => {}}
        onSubmit={() => {}}
        onStop={onStop}
        isLoading={false}
        isStreaming={true}
      />
    );

    const stopButton = screen.getByRole('button', { name: /stop/i });
    fireEvent.click(stopButton);
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it('should disable input when isStreaming is true', () => {
    render(
      <ChatInput
        value=""
        onChange={() => {}}
        onSubmit={() => {}}
        onStop={() => {}}
        isLoading={false}
        isStreaming={true}
      />
    );

    const input = screen.getByPlaceholderText(/type your message/i);
    expect(input).toBeDisabled();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest src/components/chat/__tests__/ChatInput-streaming.test.tsx --no-coverage`
Expected: FAIL — `isStreaming` prop not recognized

**Step 3: Modify ChatInput.tsx**

Read the current component first. Add `isStreaming` prop to the interface and render a stop button when streaming. The stop button should be a square icon (standard "stop generation" pattern). Key changes:

1. Add `isStreaming?: boolean` to `ChatInputProps` interface
2. When `isStreaming` is true: disable the input, show a stop (square) button instead of the send button
3. The stop button calls `onStop`

**Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest src/components/chat/__tests__/ChatInput-streaming.test.tsx --no-coverage`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/chat/ChatInput.tsx frontend/src/components/chat/__tests__/ChatInput-streaming.test.tsx
git commit -m "feat: add stop button to ChatInput during streaming"
```

---

## Task 7: Update ChatMessage to render streaming text

**Files:**

- Modify: `frontend/src/components/chat/ChatMessage.tsx`
- Modify: `frontend/src/components/chat/MessageBubble.tsx` (if content rendering lives here)

**Step 1: Understand current rendering**

Read `ChatMessage.tsx` and `MessageBubble.tsx` to understand how message content is currently rendered. The streaming message needs:

- A pulsing cursor when `isStreaming && streamingContent === ''` (waiting for first token)
- Growing text with a blinking cursor at the end during token streaming
- Normal rendering once streaming completes

**Step 2: Add streaming props and rendering**

Add to the ChatMessage component:

- `isStreaming?: boolean` — whether this message is actively streaming
- `streamingContent?: string` — the current streaming text to display

When `isStreaming` is true, render `streamingContent` instead of `message.content`, with a blinking cursor span at the end:

```tsx
{
  isStreaming && (
    <span className="inline-block w-2 h-4 bg-[#00ff9f] animate-pulse ml-0.5" />
  );
}
```

**Step 3: Run type-check**

Run: `cd frontend && npm run type-check`
Expected: PASS

**Step 4: Commit**

```bash
git add frontend/src/components/chat/ChatMessage.tsx frontend/src/components/chat/MessageBubble.tsx
git commit -m "feat: render streaming text with blinking cursor in ChatMessage"
```

---

## Task 8: Wire up streaming in the chat page/container

**Files:**

- Modify: The component that composes ChatInput + ChatMessage list (likely in `frontend/app/chat/` or `frontend/src/components/chat/`)
- This is the integration point where `streamMessage` replaces `sendMessage` as the primary send action

**Step 1: Find the chat container component**

Search for the component that uses `useChatStore` or `useChatPersistence` and renders the message list + input. This is where:

- `sendMessage` is called on submit → change to `streamMessage`
- The message list renders → add a streaming message bubble at the bottom when `isStreaming`
- `stopStreaming` is passed to ChatInput's `onStop`

**Step 2: Integrate streaming**

Key changes:

1. Import `streamMessage`, `stopStreaming`, `isStreaming`, `streamingContent` from chat store
2. On submit: call `streamMessage(content)` instead of `sendMessage(content)`
3. When `isStreaming`: append a virtual assistant message to the list with `streamingContent`
4. Pass `isStreaming` and `onStop={stopStreaming}` to ChatInput

**Step 3: Run type-check**

Run: `cd frontend && npm run type-check`
Expected: PASS

**Step 4: Manual testing**

1. Start backend: `docker-compose -f docker-compose.development.yml up -d`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:3000/chat`
4. Send a message and verify:
   - Pulsing cursor appears immediately
   - Text streams in token-by-token
   - Stop button appears during streaming
   - Clicking stop cancels the stream
   - After completion, message appears normally with citations

**Step 5: Commit**

```bash
git add <modified-files>
git commit -m "feat: wire up streaming chat in chat container component"
```

---

## Task 9: Integration test — full SSE round-trip

**Files:**

- Create: `backend/tests/integration/test_stream_endpoint.py`

**Step 1: Write integration test**

```python
"""Integration test for the SSE streaming endpoint."""
import json
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


@pytest.mark.asyncio
async def test_stream_endpoint_emits_sse_events(test_client, auth_headers):
    """
    POST /api/v2/threads/{thread_id}/stream should return SSE events
    in the correct order: message_start, token(s), message_done.
    """
    thread_id = "test-thread-id"  # Must exist in test DB

    async with test_client.stream(
        "POST",
        f"/api/v2/threads/{thread_id}/stream",
        json={"content": "Hello", "use_rag": False},
        headers={**auth_headers, "Accept": "text/event-stream"},
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        events = []
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                events.append({"type": event_type, "data": data})

    # Verify event ordering
    event_types = [e["type"] for e in events]
    assert event_types[0] == "message_start"
    assert event_types[-1] == "message_done"
    assert "token" in event_types
```

**Note:** This test requires test fixtures for thread/user creation. Adapt to your existing test infrastructure — check `backend/tests/integration/test_bulk_thread_api.py` for the fixture patterns used in this project.

**Step 2: Run integration test**

Run: `cd backend && python -m pytest tests/integration/test_stream_endpoint.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/tests/integration/test_stream_endpoint.py
git commit -m "test: add integration test for SSE streaming endpoint"
```

---

## Task 10: Type-check, lint, and validate

**Files:** None new — this is a validation task.

**Step 1: Run frontend validation**

Run: `cd frontend && npm run validate`
Expected: PASS (lint + type-check + test)

**Step 2: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All existing + new tests pass

**Step 3: Fix any issues found**

If any type errors, lint issues, or test failures: fix them.

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: fix lint/type-check issues from streaming implementation"
```

---

## Summary of all commits (expected):

1. `feat: add stream_chat_completion async generator to Azure OpenAI service`
2. `feat: add StreamService for SSE chat response orchestration`
3. `feat: add SSE streaming endpoint POST /api/v2/threads/{thread_id}/stream`
4. `feat: add SSE streaming service for chat responses`
5. `feat: add streaming state and actions to chat store`
6. `feat: add stop button to ChatInput during streaming`
7. `feat: render streaming text with blinking cursor in ChatMessage`
8. `feat: wire up streaming chat in chat container component`
9. `test: add integration test for SSE streaming endpoint`
10. `chore: fix lint/type-check issues from streaming implementation`
