"""
Integration test for the full SSE streaming pipeline.

Tests the StreamService round-trip by mocking external dependencies
(ChatService, AzureOpenAIService, RAG retrieval) and verifying that
SSEEvent objects are yielded in the correct order with expected data.

Event ordering contract:
    message_start -> [rag_context] -> token* -> message_done
    On error: error event (with partial content persistence if applicable)
"""

import json
import pytest
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from src.services.threads.stream_service import SSEEvent, StreamService

# Mark all async tests in this module for pytest-asyncio (strict mode compatible)
pytestmark = pytest.mark.asyncio


# ============================================================================
# Helpers
# ============================================================================


def _make_user_message(thread_id: UUID, message_id: Optional[UUID] = None) -> MagicMock:
    """Create a mock user ChatMessage returned by chat_service.create_message."""
    msg = MagicMock()
    msg.id = message_id or uuid4()
    msg.thread_id = thread_id
    msg.role = "user"
    msg.content = "test message"
    return msg


def _make_assistant_message(
    thread_id: UUID, message_id: Optional[UUID] = None
) -> MagicMock:
    """Create a mock assistant ChatMessage returned by chat_service.create_assistant_message."""
    msg = MagicMock()
    msg.id = message_id or uuid4()
    msg.thread_id = thread_id
    msg.role = "assistant"
    return msg


def _make_rag_context(
    document_id: Optional[str] = None,
    title: str = "Test Doc",
    content: str = "Some snippet",
    score: float = 0.92,
) -> MagicMock:
    """Create a mock RAG context result object."""
    ctx = MagicMock()
    ctx.document_id = document_id or str(uuid4())
    ctx.title = title
    ctx.content = content
    ctx.score = score
    return ctx


async def _collect_events(
    gen: AsyncGenerator[SSEEvent, None],
) -> List[SSEEvent]:
    """Drain an async generator of SSEEvents into a list."""
    events: List[SSEEvent] = []
    async for event in gen:
        events.append(event)
    return events


def _build_stream_service(
    *,
    chat_service: Optional[MagicMock] = None,
    openai_service: Optional[MagicMock] = None,
    retrieve_context_fn: Optional[AsyncMock] = None,
    build_context_prompt_fn: Optional[MagicMock] = None,
    rag_system_prompt: Optional[str] = None,
    thread_id: Optional[UUID] = None,
    tokens: Optional[List[str]] = None,
) -> tuple:
    """
    Build a StreamService with sensible defaults for all mocks.

    Returns (service, thread_id, user_id, chat_service, openai_service).
    """
    tid = thread_id or uuid4()
    uid = uuid4()

    # --- ChatService mock ---
    cs = chat_service or MagicMock()
    if chat_service is None:
        user_msg = _make_user_message(tid)
        assistant_msg = _make_assistant_message(tid)
        cs.create_message = AsyncMock(return_value=user_msg)
        cs.create_assistant_message = AsyncMock(return_value=assistant_msg)
        cs.get_thread_context = AsyncMock(
            return_value={
                "messages": [
                    {"role": "user", "content": "test message"},
                ],
            }
        )

    # --- OpenAI mock ---
    oa = openai_service or MagicMock()
    if openai_service is None:
        token_list = tokens if tokens is not None else ["Hello", " world", "!"]

        async def _stream_tokens(**kwargs: Any) -> AsyncGenerator[str, None]:
            for t in token_list:
                yield t

        oa.stream_chat_completion = MagicMock(side_effect=_stream_tokens)

    service = StreamService(
        chat_service=cs,
        openai_service=oa,
        retrieve_context_fn=retrieve_context_fn,
        build_context_prompt_fn=build_context_prompt_fn,
        rag_system_prompt=rag_system_prompt,
    )
    return service, tid, uid, cs, oa


# ============================================================================
# Event Ordering Tests
# ============================================================================


class TestFullStreamPipelineEventOrdering:
    """Verify the canonical event sequence: message_start -> token(s) -> message_done."""

    async def test_basic_event_ordering_without_rag(self) -> None:
        """Without RAG, the event sequence must be message_start -> tokens -> message_done."""
        service, tid, uid, _, _ = _build_stream_service(tokens=["Hi", " there"])

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="hello")
        )

        event_types = [e.event for e in events]
        assert event_types == ["message_start", "token", "token", "message_done"]

    async def test_event_ordering_with_rag(self) -> None:
        """
        With RAG enabled and context available, the sequence must be:
        message_start -> rag_context -> token(s) -> message_done
        """
        ctx = _make_rag_context(title="RAG Doc", score=0.95)
        retrieve_fn = AsyncMock(return_value=[ctx])
        build_fn = MagicMock(return_value="Context: RAG Doc content")

        service, tid, uid, _, _ = _build_stream_service(
            retrieve_context_fn=retrieve_fn,
            build_context_prompt_fn=build_fn,
            rag_system_prompt="You are a helpful assistant with RAG.",
            tokens=["Answer", " here"],
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=tid, user_id=uid, content="What is RAG?", use_rag=True
            )
        )

        event_types = [e.event for e in events]
        assert event_types == [
            "message_start",
            "rag_context",
            "token",
            "token",
            "message_done",
        ]

    async def test_many_tokens_preserve_ordering(self) -> None:
        """Even with many tokens the bookend events are correct."""
        tokens = [f"tok{i}" for i in range(50)]
        service, tid, uid, _, _ = _build_stream_service(tokens=tokens)

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="go")
        )

        assert events[0].event == "message_start"
        assert events[-1].event == "message_done"
        token_events = [e for e in events if e.event == "token"]
        assert len(token_events) == 50


# ============================================================================
# Event Data Verification Tests
# ============================================================================


class TestEventDataContent:
    """Verify the data payload of each event type."""

    async def test_message_start_contains_ids(self) -> None:
        """message_start must carry message_id and thread_id."""
        service, tid, uid, cs, _ = _build_stream_service()

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="hey")
        )

        start = events[0]
        assert start.event == "message_start"
        assert "message_id" in start.data
        assert start.data["thread_id"] == str(tid)

    async def test_token_events_carry_content(self) -> None:
        """Each token event must include the exact token string."""
        service, tid, uid, _, _ = _build_stream_service(tokens=["A", "B", "C"])

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="abc")
        )

        token_events = [e for e in events if e.event == "token"]
        assert [e.data["content"] for e in token_events] == ["A", "B", "C"]

    async def test_message_done_contains_metadata(self) -> None:
        """message_done should contain message_id, token_count, and latency_ms."""
        service, tid, uid, _, _ = _build_stream_service(tokens=["X", "Y"])

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="end")
        )

        done = events[-1]
        assert done.event == "message_done"
        assert "message_id" in done.data
        assert done.data["token_count"] == 2
        assert "latency_ms" in done.data
        assert isinstance(done.data["latency_ms"], int)

    async def test_rag_context_event_data(self) -> None:
        """rag_context event must include citations with document_id, title, score."""
        doc_id = str(uuid4())
        ctx = _make_rag_context(document_id=doc_id, title="My Paper", score=0.88)
        retrieve_fn = AsyncMock(return_value=[ctx])

        service, tid, uid, _, _ = _build_stream_service(
            retrieve_context_fn=retrieve_fn,
            build_context_prompt_fn=MagicMock(return_value="context text"),
            rag_system_prompt="RAG prompt",
            tokens=["ok"],
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=tid, user_id=uid, content="query", use_rag=True
            )
        )

        rag_events = [e for e in events if e.event == "rag_context"]
        assert len(rag_events) == 1
        rag_data = rag_events[0].data
        assert "citations" in rag_data
        assert len(rag_data["citations"]) == 1
        cit = rag_data["citations"][0]
        assert cit["document_id"] == doc_id
        assert cit["title"] == "My Paper"
        assert cit["score"] == pytest.approx(0.88)
        assert rag_data["search_type"] == "hybrid"


# ============================================================================
# SSEEvent Wire Format Tests
# ============================================================================


class TestSSEEventFormat:
    """Verify the SSEEvent.format() wire-protocol output."""

    async def test_format_produces_valid_sse(self) -> None:
        """format() must produce 'event: <type>\\ndata: <json>\\n\\n'."""
        evt = SSEEvent(event="token", data={"content": "hi"})
        formatted = evt.format()
        assert formatted.startswith("event: token\n")
        assert "data: " in formatted
        assert formatted.endswith("\n\n")

        # The data line should be valid JSON
        data_line = formatted.split("\n")[1]
        json_str = data_line[len("data: "):]
        parsed = json.loads(json_str)
        assert parsed["content"] == "hi"

    async def test_format_empty_data(self) -> None:
        """An event with empty data should still produce valid SSE."""
        evt = SSEEvent(event="ping", data={})
        formatted = evt.format()
        assert "event: ping\n" in formatted
        data_line = formatted.split("\n")[1]
        json_str = data_line[len("data: "):]
        assert json.loads(json_str) == {}


# ============================================================================
# Pipeline Without RAG Tests
# ============================================================================


class TestStreamPipelineWithoutRAG:
    """When use_rag is False (or retrieve_context_fn is None), no rag_context event."""

    async def test_no_rag_context_when_use_rag_false(self) -> None:
        """use_rag=False must suppress rag_context even if retrieve_fn is provided."""
        retrieve_fn = AsyncMock(return_value=[_make_rag_context()])

        service, tid, uid, _, _ = _build_stream_service(
            retrieve_context_fn=retrieve_fn,
            rag_system_prompt="RAG prompt",
            tokens=["no", " rag"],
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=tid, user_id=uid, content="test", use_rag=False
            )
        )

        event_types = [e.event for e in events]
        assert "rag_context" not in event_types
        # retrieve_fn should NOT have been called
        retrieve_fn.assert_not_called()

    async def test_no_rag_context_when_no_retrieve_fn(self) -> None:
        """Without retrieve_context_fn, no rag_context even if use_rag=True."""
        service, tid, uid, _, _ = _build_stream_service(tokens=["data"])

        events = await _collect_events(
            service.stream_response(
                thread_id=tid, user_id=uid, content="test", use_rag=True
            )
        )

        event_types = [e.event for e in events]
        assert "rag_context" not in event_types


# ============================================================================
# Error Recovery Tests
# ============================================================================


class TestStreamPipelineErrorRecovery:
    """Verify error handling and partial content persistence."""

    async def test_llm_error_emits_error_event(self) -> None:
        """An exception during LLM streaming should yield an error event."""
        oa = MagicMock()

        async def _failing_stream(**kwargs: Any) -> AsyncGenerator[str, None]:
            yield "partial"
            raise RuntimeError("LLM connection lost")

        oa.stream_chat_completion = MagicMock(side_effect=_failing_stream)

        service, tid, uid, cs, _ = _build_stream_service(openai_service=oa)

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="boom")
        )

        event_types = [e.event for e in events]
        assert "message_start" in event_types
        assert "token" in event_types  # the partial token before failure
        assert "error" in event_types
        assert "message_done" not in event_types

        # Verify error event data
        error_event = [e for e in events if e.event == "error"][0]
        assert error_event.data["code"] == "llm_error"
        assert "LLM connection lost" in error_event.data["message"]

    async def test_llm_error_persists_partial_content(self) -> None:
        """On LLM error with partial tokens, partial content must be persisted."""
        oa = MagicMock()

        async def _partial_then_fail(**kwargs: Any) -> AsyncGenerator[str, None]:
            yield "Hello"
            yield " world"
            raise RuntimeError("stream interrupted")

        oa.stream_chat_completion = MagicMock(side_effect=_partial_then_fail)

        service, tid, uid, cs, _ = _build_stream_service(openai_service=oa)

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="test")
        )

        # Verify partial content was persisted
        cs.create_assistant_message.assert_called_once()
        call_kwargs = cs.create_assistant_message.call_args
        assert call_kwargs.kwargs["content"] == "Hello world"
        assert call_kwargs.kwargs["thread_id"] == tid

    async def test_llm_error_no_partial_if_no_tokens(self) -> None:
        """If LLM fails before any tokens, no partial message should be persisted."""
        oa = MagicMock()

        async def _immediate_fail(**kwargs: Any) -> AsyncGenerator[str, None]:
            raise RuntimeError("immediate failure")
            yield  # pragma: no cover - makes this an async generator

        oa.stream_chat_completion = MagicMock(side_effect=_immediate_fail)

        service, tid, uid, cs, _ = _build_stream_service(openai_service=oa)

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="fail")
        )

        assert events[-1].event == "error"
        # create_assistant_message should NOT have been called
        cs.create_assistant_message.assert_not_called()

    async def test_user_message_creation_failure(self) -> None:
        """If user message creation returns None, emit error and stop."""
        cs = MagicMock()
        cs.create_message = AsyncMock(return_value=None)

        service, tid, uid, _, _ = _build_stream_service(chat_service=cs)

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="nope")
        )

        assert len(events) == 1
        assert events[0].event == "error"
        assert events[0].data["code"] == "message_create_failed"

    async def test_user_message_creation_exception(self) -> None:
        """If user message creation raises, emit error and stop."""
        cs = MagicMock()
        cs.create_message = AsyncMock(side_effect=Exception("db down"))

        service, tid, uid, _, _ = _build_stream_service(chat_service=cs)

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="crash")
        )

        assert len(events) == 1
        assert events[0].event == "error"
        assert events[0].data["code"] == "message_create_failed"
        assert "db down" in events[0].data["message"]

    async def test_context_build_failure(self) -> None:
        """If get_thread_context raises, emit error and stop after message_start."""
        cs = MagicMock()
        user_msg = _make_user_message(uuid4())
        cs.create_message = AsyncMock(return_value=user_msg)
        cs.get_thread_context = AsyncMock(
            side_effect=Exception("context retrieval failed")
        )

        service, tid, uid, _, _ = _build_stream_service(chat_service=cs)

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="ctx fail")
        )

        event_types = [e.event for e in events]
        assert event_types == ["message_start", "error"]
        assert events[1].data["code"] == "context_build_failed"

    async def test_rag_retrieval_failure_continues_without_rag(self) -> None:
        """If RAG retrieval raises, the pipeline should continue without RAG context."""
        retrieve_fn = AsyncMock(side_effect=Exception("vector DB timeout"))

        service, tid, uid, _, _ = _build_stream_service(
            retrieve_context_fn=retrieve_fn,
            rag_system_prompt="RAG prompt",
            tokens=["still", " works"],
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=tid, user_id=uid, content="test", use_rag=True
            )
        )

        event_types = [e.event for e in events]
        # RAG failure is non-fatal: should not have rag_context, but pipeline continues
        assert "rag_context" not in event_types
        assert "error" not in event_types
        assert event_types == ["message_start", "token", "token", "message_done"]


# ============================================================================
# Persistence Verification Tests
# ============================================================================


class TestStreamPipelinePersistence:
    """Verify that ChatService is called correctly for message persistence."""

    async def test_user_message_persisted_first(self) -> None:
        """create_message should be called with user content before streaming starts."""
        service, tid, uid, cs, _ = _build_stream_service(tokens=["ok"])

        await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="persist me")
        )

        cs.create_message.assert_called_once()
        call_args = cs.create_message.call_args
        msg_data = call_args.args[0]
        assert msg_data.content == "persist me"
        assert msg_data.thread_id == tid
        assert msg_data.role.value == "user"
        assert call_args.args[1] == uid

    async def test_assistant_message_persisted_with_full_content(self) -> None:
        """create_assistant_message should be called with all collected tokens joined."""
        service, tid, uid, cs, _ = _build_stream_service(
            tokens=["The", " answer", " is", " 42"]
        )

        await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="question")
        )

        cs.create_assistant_message.assert_called_once()
        call_kwargs = cs.create_assistant_message.call_args.kwargs
        assert call_kwargs["content"] == "The answer is 42"
        assert call_kwargs["thread_id"] == tid
        assert "latency_ms" in call_kwargs
        assert isinstance(call_kwargs["latency_ms"], int)

    async def test_assistant_message_includes_citations_from_rag(self) -> None:
        """When RAG is used, citations should be passed to create_assistant_message."""
        doc_id = str(uuid4())
        ctx = _make_rag_context(
            document_id=doc_id, title="Paper X", content="snippet", score=0.91
        )
        retrieve_fn = AsyncMock(return_value=[ctx])

        service, tid, uid, cs, _ = _build_stream_service(
            retrieve_context_fn=retrieve_fn,
            build_context_prompt_fn=MagicMock(return_value="ctx text"),
            rag_system_prompt="Use these sources.",
            tokens=["cited"],
        )

        await _collect_events(
            service.stream_response(
                thread_id=tid, user_id=uid, content="rag query", use_rag=True
            )
        )

        cs.create_assistant_message.assert_called_once()
        call_kwargs = cs.create_assistant_message.call_args.kwargs
        citations = call_kwargs["citations"]
        assert citations is not None
        assert len(citations) == 1
        assert citations[0]["document_id"] == doc_id
        assert citations[0]["document_title"] == "Paper X"
        assert citations[0]["snippet"] == "snippet"
        assert citations[0]["score"] == pytest.approx(0.91)

    async def test_no_citations_when_rag_not_used(self) -> None:
        """Without RAG, citations should be None in create_assistant_message."""
        service, tid, uid, cs, _ = _build_stream_service(tokens=["no", " rag"])

        await _collect_events(
            service.stream_response(
                thread_id=tid, user_id=uid, content="plain", use_rag=False
            )
        )

        cs.create_assistant_message.assert_called_once()
        call_kwargs = cs.create_assistant_message.call_args.kwargs
        assert call_kwargs["citations"] is None


# ============================================================================
# LLM Message Construction Tests
# ============================================================================


class TestLLMMessageConstruction:
    """Verify that the messages sent to the LLM are built correctly."""

    async def test_default_system_prompt_without_rag(self) -> None:
        """Without RAG, a default system prompt should be used."""
        service, tid, uid, _, oa = _build_stream_service(tokens=["ok"])

        await _collect_events(
            service.stream_response(
                thread_id=tid, user_id=uid, content="test", use_rag=False
            )
        )

        call_kwargs = oa.stream_chat_completion.call_args.kwargs
        messages = call_kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert "AI assistant" in messages[0]["content"]

    async def test_rag_system_prompt_with_context(self) -> None:
        """With RAG enabled and context, the RAG system prompt + context should be used."""
        ctx = _make_rag_context()
        retrieve_fn = AsyncMock(return_value=[ctx])
        build_fn = MagicMock(return_value="Document context goes here")

        service, tid, uid, _, oa = _build_stream_service(
            retrieve_context_fn=retrieve_fn,
            build_context_prompt_fn=build_fn,
            rag_system_prompt="You are a research assistant.",
            tokens=["answer"],
        )

        await _collect_events(
            service.stream_response(
                thread_id=tid, user_id=uid, content="query", use_rag=True
            )
        )

        call_kwargs = oa.stream_chat_completion.call_args.kwargs
        messages = call_kwargs["messages"]
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        assert "research assistant" in system_msg["content"]
        assert "Document context goes here" in system_msg["content"]

    async def test_thread_history_included_in_messages(self) -> None:
        """Thread context messages should be appended after the system prompt."""
        cs = MagicMock()
        user_msg = _make_user_message(uuid4())
        assistant_msg = _make_assistant_message(uuid4())
        cs.create_message = AsyncMock(return_value=user_msg)
        cs.create_assistant_message = AsyncMock(return_value=assistant_msg)
        cs.get_thread_context = AsyncMock(
            return_value={
                "messages": [
                    {"role": "user", "content": "first question"},
                    {"role": "assistant", "content": "first answer"},
                    {"role": "user", "content": "follow up"},
                ],
            }
        )

        oa = MagicMock()

        async def _stream(**kwargs: Any) -> AsyncGenerator[str, None]:
            yield "reply"

        oa.stream_chat_completion = MagicMock(side_effect=_stream)

        service = StreamService(chat_service=cs, openai_service=oa)
        tid, uid = uuid4(), uuid4()

        await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="follow up")
        )

        call_kwargs = oa.stream_chat_completion.call_args.kwargs
        messages = call_kwargs["messages"]
        # system + 3 history messages
        assert len(messages) == 4
        assert messages[1]["content"] == "first question"
        assert messages[2]["content"] == "first answer"
        assert messages[3]["content"] == "follow up"

    async def test_temperature_and_max_tokens_forwarded(self) -> None:
        """temperature and max_tokens must be forwarded to stream_chat_completion."""
        service, tid, uid, _, oa = _build_stream_service(tokens=["ok"])

        await _collect_events(
            service.stream_response(
                thread_id=tid,
                user_id=uid,
                content="test",
                temperature=0.3,
                max_tokens=512,
            )
        )

        call_kwargs = oa.stream_chat_completion.call_args.kwargs
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["max_tokens"] == 512


# ============================================================================
# Edge Cases
# ============================================================================


class TestStreamEdgeCases:
    """Edge cases and boundary conditions."""

    async def test_empty_token_stream(self) -> None:
        """If LLM returns zero tokens, message_done should still be emitted."""
        service, tid, uid, cs, _ = _build_stream_service(tokens=[])

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="empty")
        )

        event_types = [e.event for e in events]
        assert event_types == ["message_start", "message_done"]
        # Should persist empty content
        cs.create_assistant_message.assert_called_once()
        assert cs.create_assistant_message.call_args.kwargs["content"] == ""

    async def test_single_token_stream(self) -> None:
        """A single-token response should produce exactly one token event."""
        service, tid, uid, _, _ = _build_stream_service(tokens=["only"])

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="one")
        )

        event_types = [e.event for e in events]
        assert event_types == ["message_start", "token", "message_done"]

    async def test_multiple_rag_contexts(self) -> None:
        """Multiple RAG context items should appear in a single rag_context event."""
        contexts = [
            _make_rag_context(title=f"Doc {i}", score=0.9 - i * 0.1)
            for i in range(3)
        ]
        retrieve_fn = AsyncMock(return_value=contexts)

        service, tid, uid, _, _ = _build_stream_service(
            retrieve_context_fn=retrieve_fn,
            build_context_prompt_fn=MagicMock(return_value="ctx"),
            rag_system_prompt="system",
            tokens=["done"],
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=tid, user_id=uid, content="multi", use_rag=True
            )
        )

        rag_events = [e for e in events if e.event == "rag_context"]
        assert len(rag_events) == 1
        assert len(rag_events[0].data["citations"]) == 3

    async def test_persist_failure_after_successful_stream(self) -> None:
        """If assistant message persistence fails after streaming, emit error (not message_done)."""
        cs = MagicMock()
        user_msg = _make_user_message(uuid4())
        cs.create_message = AsyncMock(return_value=user_msg)
        cs.create_assistant_message = AsyncMock(
            side_effect=Exception("DB write failed")
        )
        cs.get_thread_context = AsyncMock(return_value={"messages": []})

        service, tid, uid, _, _ = _build_stream_service(
            chat_service=cs, tokens=["good", " content"]
        )

        events = await _collect_events(
            service.stream_response(thread_id=tid, user_id=uid, content="persist fail")
        )

        event_types = [e.event for e in events]
        assert "token" in event_types
        assert events[-1].event == "error"
        assert events[-1].data["code"] == "persist_failed"
        assert "message_done" not in event_types
