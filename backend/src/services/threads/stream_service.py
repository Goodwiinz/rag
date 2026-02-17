"""
SSE Stream Service for Terminal Observatory thread-centric chat.

Orchestrates user message persistence, optional RAG retrieval, LLM streaming,
and assistant message persistence. Yields SSEEvent objects for each step of
the pipeline so the caller (an SSE endpoint) can forward them to the client.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Coroutine, Dict, List, Optional
from uuid import UUID

from src.schemas.chat import ChatMessageCreate, MessageRole
from src.services.infrastructure.azure_openai_service import AzureOpenAIService
from src.services.threads.chat_service import ChatService

logger = logging.getLogger(__name__)


@dataclass
class SSEEvent:
    """
    Represents a single Server-Sent Event.

    Attributes:
        event: The SSE event type (e.g. 'token', 'message_start', 'error').
        data: A dictionary that will be serialized to JSON for the data field.
    """

    event: str
    data: Dict[str, Any] = field(default_factory=dict)

    def format(self) -> str:
        """
        Format this event as an SSE wire-protocol string.

        Returns a string like:
            event: token
            data: {"content": "Hello"}

        (with a trailing blank line to delimit the event)
        """
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"


class StreamService:
    """
    Orchestrates the full streaming chat flow:

    1. Persist user message via ChatService
    2. (Optional) Perform RAG retrieval via retrieve_context_fn
    3. Stream LLM tokens via AzureOpenAIService.stream_chat_completion()
    4. Persist assistant message with citations via ChatService
    5. Yield SSEEvent objects for each step

    Event ordering:
        message_start -> [rag_context] -> token* -> message_done
        On error: error event (with partial content persistence if applicable)
    """

    def __init__(
        self,
        chat_service: ChatService,
        openai_service: AzureOpenAIService,
        retrieve_context_fn: Optional[
            Callable[..., Coroutine[Any, Any, list]]
        ] = None,
        build_context_prompt_fn: Optional[Callable[..., str]] = None,
        rag_system_prompt: Optional[str] = None,
    ):
        self.chat_service = chat_service
        self.openai_service = openai_service
        self.retrieve_context_fn = retrieve_context_fn
        self.build_context_prompt_fn = build_context_prompt_fn
        self.rag_system_prompt = rag_system_prompt

    async def stream_response(
        self,
        thread_id: UUID,
        user_id: UUID,
        content: str,
        use_rag: bool = False,
        max_context_docs: int = 5,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[SSEEvent, None]:
        """
        Async generator that yields SSEEvent objects for the full chat pipeline.

        Args:
            thread_id: The thread to post the message in.
            user_id: The authenticated user's ID.
            content: The user's message text.
            use_rag: Whether to perform RAG retrieval before LLM call.
            max_context_docs: Maximum documents to retrieve for RAG context.
            temperature: LLM sampling temperature.
            max_tokens: Maximum tokens for LLM response.

        Yields:
            SSEEvent objects in this order:
            - message_start (after user message persisted)
            - rag_context (if use_rag=True, after search completes)
            - token (for each LLM token)
            - message_done (after assistant message persisted)
            - error (if something goes wrong)
        """
        start_time = time.monotonic()
        collected_content: List[str] = []
        citations: Optional[List[Dict[str, Any]]] = None
        contexts = []

        # -----------------------------------------------------------------
        # Step 1: Persist user message
        # -----------------------------------------------------------------
        try:
            msg_data = ChatMessageCreate(
                thread_id=thread_id,
                content=content,
                role=MessageRole.USER,
            )
            user_message = await self.chat_service.create_message(msg_data, user_id)

            if user_message is None:
                yield SSEEvent(
                    event="error",
                    data={
                        "code": "message_create_failed",
                        "message": "Failed to create user message. Check thread access permissions.",
                    },
                )
                return

            yield SSEEvent(
                event="message_start",
                data={
                    "message_id": str(user_message.id),
                    "thread_id": str(thread_id),
                },
            )
        except Exception as exc:
            logger.error(f"Failed to create user message: {exc}", exc_info=True)
            yield SSEEvent(
                event="error",
                data={
                    "code": "message_create_failed",
                    "message": str(exc),
                },
            )
            return

        # -----------------------------------------------------------------
        # Step 2: Optional RAG retrieval
        # -----------------------------------------------------------------
        if use_rag and self.retrieve_context_fn is not None:
            try:
                contexts = await self.retrieve_context_fn(content, max_context_docs)

                # Build citation dicts for persistence
                citations = [
                    {
                        "document_id": getattr(ctx, "document_id", None),
                        "document_title": getattr(ctx, "title", None),
                        "snippet": getattr(ctx, "content", None),
                        "score": getattr(ctx, "score", None),
                    }
                    for ctx in contexts
                ]

                yield SSEEvent(
                    event="rag_context",
                    data={
                        "citations": [
                            {
                                "document_id": str(
                                    getattr(ctx, "document_id", "unknown")
                                ),
                                "title": getattr(ctx, "title", "Untitled"),
                                "score": float(getattr(ctx, "score", 0.0)),
                            }
                            for ctx in contexts
                        ],
                        "search_type": "hybrid",
                    },
                )
            except Exception as exc:
                logger.warning(f"RAG retrieval failed, continuing without: {exc}")
                contexts = []
                citations = None

        # -----------------------------------------------------------------
        # Step 3: Build LLM messages
        # -----------------------------------------------------------------
        try:
            thread_context = await self.chat_service.get_thread_context(
                thread_id=thread_id,
                user_id=user_id,
            )
            llm_messages: List[Dict[str, str]] = []

            # Add system prompt
            if use_rag and contexts and self.rag_system_prompt:
                system_content = self.rag_system_prompt
                if self.build_context_prompt_fn:
                    context_prompt = self.build_context_prompt_fn(contexts)
                    system_content = f"{self.rag_system_prompt}\n\n{context_prompt}"
                llm_messages.append({"role": "system", "content": system_content})
            else:
                llm_messages.append(
                    {
                        "role": "system",
                        "content": "You are an advanced AI assistant. Provide precise, well-structured responses.",
                    }
                )

            # Add thread history
            for msg in thread_context.get("messages", []):
                llm_messages.append(
                    {"role": msg["role"], "content": msg["content"]}
                )

        except Exception as exc:
            logger.error(f"Failed to build LLM context: {exc}", exc_info=True)
            yield SSEEvent(
                event="error",
                data={
                    "code": "context_build_failed",
                    "message": str(exc),
                },
            )
            return

        # -----------------------------------------------------------------
        # Step 4: Stream LLM tokens
        # -----------------------------------------------------------------
        try:
            async for token in self.openai_service.stream_chat_completion(
                messages=llm_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                collected_content.append(token)
                yield SSEEvent(
                    event="token",
                    data={"content": token},
                )
        except Exception as exc:
            logger.error(f"LLM streaming error: {exc}", exc_info=True)

            # Persist partial content if we got any tokens
            full_content = "".join(collected_content)
            if full_content:
                try:
                    await self.chat_service.create_assistant_message(
                        thread_id=thread_id,
                        content=full_content,
                        citations=citations,
                        latency_ms=int(
                            (time.monotonic() - start_time) * 1000
                        ),
                    )
                except Exception as persist_exc:
                    logger.error(
                        f"Failed to persist partial content: {persist_exc}",
                        exc_info=True,
                    )

            yield SSEEvent(
                event="error",
                data={
                    "code": "llm_error",
                    "message": str(exc),
                },
            )
            return

        # -----------------------------------------------------------------
        # Step 5: Persist assistant message
        # -----------------------------------------------------------------
        full_content = "".join(collected_content)
        latency_ms = int((time.monotonic() - start_time) * 1000)

        try:
            assistant_message = await self.chat_service.create_assistant_message(
                thread_id=thread_id,
                content=full_content,
                citations=citations,
                latency_ms=latency_ms,
            )

            yield SSEEvent(
                event="message_done",
                data={
                    "message_id": str(
                        assistant_message.id if assistant_message else ""
                    ),
                    "token_count": len(collected_content),
                    "latency_ms": latency_ms,
                },
            )
        except Exception as exc:
            logger.error(
                f"Failed to persist assistant message: {exc}", exc_info=True
            )
            yield SSEEvent(
                event="error",
                data={
                    "code": "persist_failed",
                    "message": str(exc),
                },
            )
