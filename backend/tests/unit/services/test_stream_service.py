"""Unit tests for StreamService and SSEEvent."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.services.threads.stream_service import SSEEvent, StreamService


# ============================================================================
# SSEEvent Tests
# ============================================================================


class TestSSEEvent:
    """Tests for SSEEvent dataclass and wire format."""

    def test_format_basic_event(self) -> None:
        """SSEEvent.format() should produce correct SSE wire format."""
        event = SSEEvent(event="token", data={"content": "Hello"})
        formatted = event.format()

        assert formatted == 'event: token\ndata: {"content": "Hello"}\n\n'

    def test_format_message_start_event(self) -> None:
        """message_start event should include message_id and thread_id."""
        msg_id = str(uuid4())
        thread_id = str(uuid4())
        event = SSEEvent(
            event="message_start",
            data={"message_id": msg_id, "thread_id": thread_id},
        )
        formatted = event.format()

        assert formatted.startswith("event: message_start\n")
        assert f'"message_id": "{msg_id}"' in formatted
        assert f'"thread_id": "{thread_id}"' in formatted
        assert formatted.endswith("\n\n")

    def test_format_error_event(self) -> None:
        """error event should include code and message."""
        event = SSEEvent(
            event="error",
            data={"code": "llm_error", "message": "Model timed out"},
        )
        formatted = event.format()

        assert "event: error\n" in formatted
        parsed_data = json.loads(formatted.split("data: ")[1].strip())
        assert parsed_data["code"] == "llm_error"
        assert parsed_data["message"] == "Model timed out"

    def test_format_data_is_json(self) -> None:
        """The data field should be valid JSON."""
        event = SSEEvent(event="token", data={"content": 'He said "hi"'})
        formatted = event.format()
        data_line = formatted.split("data: ")[1].strip()
        parsed = json.loads(data_line)
        assert parsed["content"] == 'He said "hi"'

    def test_format_empty_data(self) -> None:
        """SSEEvent with empty dict data should still produce valid format."""
        event = SSEEvent(event="message_done", data={})
        formatted = event.format()
        assert formatted == "event: message_done\ndata: {}\n\n"


# ============================================================================
# StreamService Tests — Helpers
# ============================================================================


def _make_mock_chat_service():
    """Create a mock ChatService with common methods."""
    chat_service = AsyncMock()

    # create_message returns a mock message with an id
    mock_user_msg = MagicMock()
    mock_user_msg.id = uuid4()
    chat_service.create_message.return_value = mock_user_msg

    # create_assistant_message returns a mock assistant message
    mock_asst_msg = MagicMock()
    mock_asst_msg.id = uuid4()
    chat_service.create_assistant_message.return_value = mock_asst_msg

    # get_thread_context returns messages formatted for LLM
    chat_service.get_thread_context.return_value = {
        "messages": [
            {"role": "user", "content": "What is RAG?"},
        ],
        "metadata": {
            "truncated": False,
            "total_tokens": 10,
            "max_tokens": 4000,
            "message_count": 1,
            "total_messages": 1,
            "usage_ratio": 0.0025,
            "approaching_limit": False,
        },
    }

    return chat_service


def _make_mock_openai_service(tokens: list[str]):
    """Create a mock AzureOpenAIService whose stream yields the given tokens."""
    openai_service = AsyncMock()

    async def mock_stream(*args, **kwargs):
        for token in tokens:
            yield token

    openai_service.stream_chat_completion = MagicMock(side_effect=mock_stream)
    return openai_service


def _make_mock_retrieve_context(contexts=None):
    """Create a mock retrieve_context coroutine."""
    if contexts is None:
        contexts = []
    mock_fn = AsyncMock(return_value=contexts)
    return mock_fn


async def _collect_events(async_gen) -> list[SSEEvent]:
    """Collect all SSEEvent objects from an async generator."""
    events = []
    async for event in async_gen:
        events.append(event)
    return events


# ============================================================================
# StreamService Tests — Event Ordering
# ============================================================================


class TestStreamServiceEventOrdering:
    """Tests for the correct ordering of SSE events."""

    @pytest.mark.asyncio
    async def test_basic_flow_without_rag(self) -> None:
        """Without RAG: message_start -> tokens -> message_done."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()
        openai_service = _make_mock_openai_service(["Hello", " world"])

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="What is RAG?",
                use_rag=False,
            )
        )

        event_types = [e.event for e in events]
        assert event_types[0] == "message_start"
        assert event_types[-1] == "message_done"
        # All middle events should be tokens
        for et in event_types[1:-1]:
            assert et == "token"

    @pytest.mark.asyncio
    async def test_basic_flow_event_data(self) -> None:
        """message_start should contain message_id and thread_id."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()
        openai_service = _make_mock_openai_service(["Hi"])

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="Hello",
                use_rag=False,
            )
        )

        start_event = events[0]
        assert start_event.event == "message_start"
        assert "message_id" in start_event.data
        assert "thread_id" in start_event.data

    @pytest.mark.asyncio
    async def test_token_events_contain_content(self) -> None:
        """Token events should contain the content field."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()
        openai_service = _make_mock_openai_service(["Hello", " world"])

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="Hi",
                use_rag=False,
            )
        )

        token_events = [e for e in events if e.event == "token"]
        assert len(token_events) == 2
        assert token_events[0].data["content"] == "Hello"
        assert token_events[1].data["content"] == " world"

    @pytest.mark.asyncio
    async def test_message_done_contains_metadata(self) -> None:
        """message_done should have message_id, token_count, and latency_ms."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()
        openai_service = _make_mock_openai_service(["ok"])

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="Hi",
                use_rag=False,
            )
        )

        done_event = events[-1]
        assert done_event.event == "message_done"
        assert "message_id" in done_event.data
        assert "token_count" in done_event.data
        assert "latency_ms" in done_event.data

    @pytest.mark.asyncio
    async def test_user_message_created(self) -> None:
        """StreamService should call chat_service.create_message with the user content."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()
        openai_service = _make_mock_openai_service(["ok"])

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
        )

        await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="What is RAG?",
                use_rag=False,
            )
        )

        chat_service.create_message.assert_called_once()
        call_args = chat_service.create_message.call_args
        msg_data = call_args[0][0] if call_args[0] else call_args[1]["data"]
        assert msg_data.content == "What is RAG?"
        assert msg_data.thread_id == thread_id

    @pytest.mark.asyncio
    async def test_assistant_message_persisted(self) -> None:
        """StreamService should persist the full assistant message after streaming."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()
        openai_service = _make_mock_openai_service(["Hello", " world"])

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
        )

        await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="Hi",
                use_rag=False,
            )
        )

        chat_service.create_assistant_message.assert_called_once()
        call_kwargs = chat_service.create_assistant_message.call_args[1]
        assert call_kwargs["thread_id"] == thread_id
        assert call_kwargs["content"] == "Hello world"


# ============================================================================
# StreamService Tests — RAG Flow
# ============================================================================


class TestStreamServiceRAGFlow:
    """Tests for RAG-enabled streaming."""

    @pytest.mark.asyncio
    async def test_rag_flow_event_ordering(self) -> None:
        """With RAG: message_start -> rag_context -> tokens -> message_done."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()
        openai_service = _make_mock_openai_service(["Answer"])

        mock_contexts = [
            MagicMock(
                document_id="doc-1",
                title="Test Doc",
                content="Some content",
                score=0.95,
                source="vector",
            )
        ]
        mock_retrieve = _make_mock_retrieve_context(mock_contexts)

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
            retrieve_context_fn=mock_retrieve,
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="What is ML?",
                use_rag=True,
            )
        )

        event_types = [e.event for e in events]
        assert event_types[0] == "message_start"
        assert event_types[1] == "rag_context"
        assert event_types[-1] == "message_done"
        # Tokens in between
        token_events = [e for e in events if e.event == "token"]
        assert len(token_events) >= 1

    @pytest.mark.asyncio
    async def test_rag_context_event_data(self) -> None:
        """rag_context event should contain citations and search_type."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()
        openai_service = _make_mock_openai_service(["Answer"])

        mock_contexts = [
            MagicMock(
                document_id="doc-1",
                title="Test Doc",
                content="Some content",
                score=0.95,
                source="vector",
            )
        ]
        mock_retrieve = _make_mock_retrieve_context(mock_contexts)

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
            retrieve_context_fn=mock_retrieve,
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="What is ML?",
                use_rag=True,
            )
        )

        rag_event = [e for e in events if e.event == "rag_context"][0]
        assert "citations" in rag_event.data
        assert "search_type" in rag_event.data
        assert len(rag_event.data["citations"]) == 1

    @pytest.mark.asyncio
    async def test_persists_only_inline_referenced_citations(self) -> None:
        """Assistant persistence should drop retrieved citations not cited in the response."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()
        openai_service = _make_mock_openai_service(["Answer [2] only."])

        mock_contexts = [
            MagicMock(
                document_id="doc-1",
                title="Doc One",
                content="First context",
                score=0.91,
            ),
            MagicMock(
                document_id="doc-2",
                title="Doc Two",
                content="Second context",
                score=0.87,
            ),
        ]
        mock_retrieve = _make_mock_retrieve_context(mock_contexts)

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
            retrieve_context_fn=mock_retrieve,
        )

        await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="What is ML?",
                use_rag=True,
            )
        )

        persisted_citations = chat_service.create_assistant_message.call_args[1][
            "citations"
        ]
        assert persisted_citations == [
            {
                "document_id": "doc-2",
                "document_title": "Doc Two",
                "snippet": "Second context",
                "score": 0.87,
            }
        ]

    @pytest.mark.asyncio
    async def test_rag_retrieve_called_with_query(self) -> None:
        """retrieve_context_fn should be called with the user's message content."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()
        openai_service = _make_mock_openai_service(["ok"])

        mock_retrieve = _make_mock_retrieve_context([])

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
            retrieve_context_fn=mock_retrieve,
        )

        await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="What is ML?",
                use_rag=True,
                max_context_docs=3,
            )
        )

        mock_retrieve.assert_called_once_with("What is ML?", 3)

    @pytest.mark.asyncio
    async def test_no_rag_context_when_disabled(self) -> None:
        """When use_rag=False, no rag_context event should appear."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()
        openai_service = _make_mock_openai_service(["ok"])

        mock_retrieve = _make_mock_retrieve_context()

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
            retrieve_context_fn=mock_retrieve,
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="Hi",
                use_rag=False,
            )
        )

        event_types = [e.event for e in events]
        assert "rag_context" not in event_types
        mock_retrieve.assert_not_called()

    @pytest.mark.asyncio
    async def test_citations_passed_to_assistant_message(self) -> None:
        """When RAG finds contexts, citations should be passed to create_assistant_message."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()
        openai_service = _make_mock_openai_service(["Answer"])

        mock_contexts = [
            MagicMock(
                document_id="doc-1",
                title="Test Doc",
                content="Some content",
                score=0.95,
                source="vector",
            )
        ]
        mock_retrieve = _make_mock_retrieve_context(mock_contexts)

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
            retrieve_context_fn=mock_retrieve,
        )

        await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="What is ML?",
                use_rag=True,
            )
        )

        call_kwargs = chat_service.create_assistant_message.call_args[1]
        assert call_kwargs["citations"] is not None
        assert len(call_kwargs["citations"]) == 1


# ============================================================================
# StreamService Tests — Error Handling
# ============================================================================


class TestStreamServiceErrorHandling:
    """Tests for error handling in stream_response."""

    @pytest.mark.asyncio
    async def test_llm_error_yields_error_event(self) -> None:
        """If LLM streaming fails, an error event should be yielded."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()

        # Make the OpenAI service raise during streaming
        openai_service = AsyncMock()

        async def failing_stream(*args, **kwargs):
            raise RuntimeError("LLM timeout")
            yield  # noqa: unreachable — makes this an async generator

        openai_service.stream_chat_completion = MagicMock(side_effect=failing_stream)

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="Hi",
                use_rag=False,
            )
        )

        event_types = [e.event for e in events]
        assert "error" in event_types
        error_event = [e for e in events if e.event == "error"][0]
        assert "code" in error_event.data
        assert "message" in error_event.data

    @pytest.mark.asyncio
    async def test_partial_content_persisted_on_llm_error(self) -> None:
        """If LLM errors after some tokens, partial content should be persisted."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()

        openai_service = AsyncMock()

        async def partial_then_fail(*args, **kwargs):
            yield "Partial"
            yield " content"
            raise RuntimeError("Connection lost")

        openai_service.stream_chat_completion = MagicMock(
            side_effect=partial_then_fail
        )

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="Hi",
                use_rag=False,
            )
        )

        # Should have persisted partial content
        chat_service.create_assistant_message.assert_called_once()
        call_kwargs = chat_service.create_assistant_message.call_args[1]
        assert call_kwargs["content"] == "Partial content"

        # Should have error event
        event_types = [e.event for e in events]
        assert "error" in event_types

    @pytest.mark.asyncio
    async def test_no_persist_on_llm_error_without_content(self) -> None:
        """If LLM errors before any tokens, no assistant message should be persisted."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()

        openai_service = AsyncMock()

        async def immediate_fail(*args, **kwargs):
            raise RuntimeError("Connection refused")
            yield  # noqa: unreachable

        openai_service.stream_chat_completion = MagicMock(
            side_effect=immediate_fail
        )

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="Hi",
                use_rag=False,
            )
        )

        # Should NOT have persisted any assistant message
        chat_service.create_assistant_message.assert_not_called()

        # Should have error event
        error_events = [e for e in events if e.event == "error"]
        assert len(error_events) == 1

    @pytest.mark.asyncio
    async def test_user_message_creation_error(self) -> None:
        """If user message creation fails, an error event should be yielded."""
        thread_id = uuid4()
        user_id = uuid4()
        chat_service = _make_mock_chat_service()
        chat_service.create_message.return_value = None  # Simulates auth/access failure

        openai_service = _make_mock_openai_service(["ok"])

        service = StreamService(
            chat_service=chat_service,
            openai_service=openai_service,
        )

        events = await _collect_events(
            service.stream_response(
                thread_id=thread_id,
                user_id=user_id,
                content="Hi",
                use_rag=False,
            )
        )

        event_types = [e.event for e in events]
        assert "error" in event_types
        # Should not proceed to LLM
        assert "token" not in event_types
