"""
SSE streaming endpoint for Terminal Observatory thread-centric chat.

POST /api/v2/threads/{thread_id}/stream

Authenticates the user, validates the request, prevents concurrent streams
on the same thread, and returns an SSE StreamingResponse backed by
StreamService.stream_response().
"""

import logging
from typing import Optional, Set
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.research.chat import RAG_SYSTEM_PROMPT, build_context_prompt, retrieve_context
from src.core.database import AsyncSessionLocal, get_db
from src.core.dependencies import get_current_user
from src.models.user import User
from src.services.infrastructure.azure_openai_service import azure_openai_service
from src.services.threads.chat_service import ChatService
from src.services.threads.stream_service import SSEEvent, StreamService
from src.services.threads.thread_event_service import thread_event_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/threads", tags=["Streaming"])

# Tracks thread IDs that currently have an active stream in progress.
# Used to prevent concurrent streams on the same thread (returns 409).
_active_streams: Set[UUID] = set()


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------


class StreamRequest(BaseModel):
    """Request body for the SSE streaming chat endpoint."""

    content: str = Field(..., min_length=1, max_length=32000)
    use_rag: bool = Field(default=True)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=2048, ge=1, le=8192)


# ---------------------------------------------------------------------------
# SSE response headers
# ---------------------------------------------------------------------------

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # Disable nginx buffering
}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/{thread_id}/stream")
async def stream_thread_chat(
    thread_id: UUID,
    body: StreamRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Stream an LLM response for a thread message via Server-Sent Events.

    1. Persists the user message
    2. Optionally performs RAG retrieval
    3. Streams LLM tokens as SSE events
    4. Persists the assistant response
    5. Broadcasts ``message_created`` via WebSocket

    NOTE: The database session is created inside the async generator rather than
    via Depends(get_db). FastAPI's dependency cleanup can close the session while
    the streaming generator is still running, causing MissingGreenlet errors.
    """

    # ---- Concurrent-stream guard ----
    if thread_id in _active_streams:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A stream is already active on this thread.",
        )

    # ---- Inner async generator ----
    # The DB session is created here (not via Depends) so its lifecycle is
    # fully controlled within the generator, preventing MissingGreenlet errors.
    async def _event_generator():
        _active_streams.add(thread_id)
        async with AsyncSessionLocal() as db:
            chat_service = ChatService(db)
            stream_service = StreamService(
                chat_service=chat_service,
                openai_service=azure_openai_service,
                retrieve_context_fn=retrieve_context,
                build_context_prompt_fn=build_context_prompt,
                rag_system_prompt=RAG_SYSTEM_PROMPT,
            )

            try:
                async for sse_event in stream_service.stream_response(
                    thread_id=thread_id,
                    user_id=current_user.id,
                    content=body.content,
                    use_rag=body.use_rag,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                ):
                    # Check for client disconnect
                    if await request.is_disconnected():
                        logger.info(
                            f"Client disconnected from stream on thread {thread_id}"
                        )
                        break

                    yield sse_event.format()

                    # After the final message_done event, broadcast via WebSocket
                    if sse_event.event == "message_done":
                        try:
                            thread = await chat_service.get_thread(
                                thread_id, current_user.id
                            )
                            if thread:
                                await thread_event_service.broadcast_message_created(
                                    message_id=sse_event.data.get("message_id", ""),
                                    thread_id=str(thread_id),
                                    conversation_id=str(thread.conversation_id),
                                    user_id=str(current_user.id),
                                    role="assistant",
                                    content_preview=None,
                                    has_citations=False,
                                )
                        except Exception as exc:
                            logger.error(
                                f"Failed to broadcast message_created event: {exc}"
                            )

            except Exception as exc:
                logger.error(
                    f"Unexpected error during stream on thread {thread_id}: {exc}",
                    exc_info=True,
                )
                error_event = SSEEvent(
                    event="error",
                    data={"code": "stream_error", "message": str(exc)},
                )
                yield error_event.format()
            finally:
                _active_streams.discard(thread_id)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
