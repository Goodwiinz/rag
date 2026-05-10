"""Unit tests for ThreadSummarizationService.

Covers should_summarize, _format_messages_for_prompt, _clean_summary,
_generate_fallback_summary, and the async generate_summary orchestrator.
"""

import asyncio
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.chat_message import ChatMessage, MessageRole
from src.models.thread import Thread
from src.services.threads.thread_summarization_service import (
    MAX_SUMMARY_LENGTH,
    ThreadSummarizationService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_sync_db() -> MagicMock:
    """Sync SQLAlchemy Session mock — service uses sync Session, not Async."""
    db = MagicMock()
    return db


def _install_query_chain(db, thread=None, messages=None):
    """Wire db.query(Model) to return chain mocks for Thread.first and ChatMessage.all."""

    def query_factory(model):
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.order_by.return_value = chain
        if model is Thread:
            chain.first.return_value = thread
        elif model is ChatMessage:
            chain.all.return_value = messages or []
        return chain

    db.query.side_effect = query_factory


@pytest.fixture
def thread_factory():
    def _make(thread_id=None, message_count=5, summary=None):
        t = MagicMock(spec=Thread)
        t.id = thread_id or uuid4()
        t.message_count = message_count
        t.summary = summary
        return t

    return _make


@pytest.fixture
def msg_factory():
    def _make(role=MessageRole.USER, content="hello"):
        m = MagicMock(spec=ChatMessage)
        m.role = role
        m.content = content
        return m

    return _make


@pytest.fixture
def service(mock_sync_db, monkeypatch):
    """Service with both API keys cleared and redis pre-installed as a benign MagicMock."""
    monkeypatch.setattr(
        "src.services.threads.thread_summarization_service.settings.OPENAI_API_KEY",
        "",
    )
    monkeypatch.setattr(
        "src.services.threads.thread_summarization_service.settings.ANTHROPIC_API_KEY",
        "",
    )
    svc = ThreadSummarizationService(mock_sync_db)
    redis_mock = MagicMock()
    redis_mock.exists.return_value = 0
    redis_mock.setex.return_value = True
    svc._redis_client = redis_mock
    return svc


def _make_openai_module(content="Test summary."):
    """Build a fake openai module suitable for sys.modules injection."""
    fake = types.ModuleType("openai")

    response = MagicMock()
    if content is None:
        response.choices = []
    else:
        choice = MagicMock()
        choice.message.content = content
        response.choices = [choice]

    client = MagicMock()
    client.chat.completions.create = AsyncMock(return_value=response)

    fake.AsyncOpenAI = MagicMock(return_value=client)
    return fake, client


def _make_anthropic_module(text="Test anthropic summary."):
    fake = types.ModuleType("anthropic")

    response = MagicMock()
    if text is None:
        response.content = []
    else:
        block = MagicMock()
        block.text = text
        response.content = [block]

    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)

    fake.AsyncAnthropic = MagicMock(return_value=client)
    return fake, client


# ---------------------------------------------------------------------------
# TestShouldSummarize
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestShouldSummarize:
    def test_below_min_messages(self, service, thread_factory):
        """Threads with fewer than 3 messages are skipped."""
        thread = thread_factory(message_count=2)
        assert service.should_summarize(thread) is False

    def test_at_min_messages_no_rate_limit(self, service, thread_factory):
        """A thread with >=3 messages and no rate-limit key gets summarized."""
        thread = thread_factory(message_count=3)
        service._redis_client.exists.return_value = 0
        assert service.should_summarize(thread) is True

    def test_rate_limited(self, service, thread_factory):
        """If Redis rate-limit key exists, summarization is skipped."""
        thread = thread_factory(message_count=10)
        service._redis_client.exists.return_value = 1
        assert service.should_summarize(thread) is False

    def test_redis_unavailable_falls_open(self, service, thread_factory):
        """When redis_client returns None, the rate-limit check is bypassed."""
        thread = thread_factory(message_count=5)
        service._redis_client = None
        with patch(
            "src.services.threads.thread_summarization_service.redis",
            create=True,
        ) as redis_mod:
            redis_mod.Redis.from_url.side_effect = ConnectionError("nope")
            # property swallows the error and returns None
            assert service.should_summarize(thread) is True

    def test_redis_exists_raises_falls_open(self, service, thread_factory):
        """If redis.exists raises, the rate-limit check is treated as a miss."""
        thread = thread_factory(message_count=5)
        service._redis_client.exists.side_effect = RuntimeError("oops")
        assert service.should_summarize(thread) is True


# ---------------------------------------------------------------------------
# TestFormatMessages
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFormatMessages:
    def test_user_assistant_prefix(self, service, msg_factory):
        """User and assistant messages get the right line prefix."""
        msgs = [
            msg_factory(role=MessageRole.USER, content="hi"),
            msg_factory(role=MessageRole.ASSISTANT, content="hello"),
        ]
        out = service._format_messages_for_prompt(msgs)
        assert out == "User: hi\nAssistant: hello"

    def test_individual_msg_truncated_at_500(self, service, msg_factory):
        """Content longer than 500 chars is cut to first 497 chars plus '...'."""
        long_content = "x" * 600
        msgs = [msg_factory(content=long_content)]
        out = service._format_messages_for_prompt(msgs, max_chars=5000)
        body = out.split(": ", 1)[1]
        assert len(body) == 500
        assert body.endswith("...")
        assert body[:497] == "x" * 497

    def test_total_capped_at_2000(self, service, msg_factory):
        """The cumulative output is bounded by max_chars; later messages drop."""
        # 10 messages of 300 chars each → would be ~3000 chars; cap at 2000
        msgs = [msg_factory(content="a" * 300) for _ in range(10)]
        out = service._format_messages_for_prompt(msgs, max_chars=2000)
        assert len(out) <= 2000
        # At least one message was dropped
        assert out.count("User:") < 10

    def test_handles_empty_content(self, service, msg_factory):
        """A message with None content produces an empty body, not a TypeError."""
        msgs = [
            msg_factory(role=MessageRole.USER, content=None),
            msg_factory(role=MessageRole.ASSISTANT, content="ok"),
        ]
        out = service._format_messages_for_prompt(msgs)
        assert out == "User: \nAssistant: ok"


# ---------------------------------------------------------------------------
# TestCleanSummary
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCleanSummary:
    def test_strips_surrounding_quotes(self, service):
        """Leading/trailing quotes are removed."""
        assert service._clean_summary('"hello"') == "hello"
        assert service._clean_summary("'world'") == "world"

    def test_under_max_unchanged(self, service):
        """Input shorter than MAX_SUMMARY_LENGTH is returned (minus quotes)."""
        text = "Short summary"
        assert service._clean_summary(text) == text

    def test_sentence_boundary_truncation(self, service):
        """A period past the midpoint of the truncated window cuts cleanly with no ellipsis."""
        # Build a 200-char string with a period at position 100 (well past MAX//2=75)
        prefix = "a" * 100 + "."
        suffix = "b" * 100
        out = service._clean_summary(prefix + suffix)
        assert out.endswith(".")
        assert "..." not in out
        assert len(out) <= MAX_SUMMARY_LENGTH

    def test_word_boundary_truncation(self, service):
        """With no sentence terminator, truncation happens at the last space past midpoint."""
        # 200 chars with a space at position 100 and no period
        prefix = "a" * 100 + " "
        suffix = "b" * 100
        out = service._clean_summary(prefix + suffix)
        assert out.endswith("...")
        assert " ..." not in out  # the space is consumed, then "..." appended
        assert len(out) <= MAX_SUMMARY_LENGTH

    def test_hard_cut_no_boundary(self, service):
        """Continuous text with no space or period gets a hard cut at MAX-3 + '...'."""
        text = "x" * 200
        out = service._clean_summary(text)
        assert out == "x" * (MAX_SUMMARY_LENGTH - 3) + "..."
        assert len(out) == MAX_SUMMARY_LENGTH


# ---------------------------------------------------------------------------
# TestFallbackSummary
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFallbackSummary:
    def test_empty_messages(self, service):
        """An empty list yields the 'Empty conversation' marker."""
        assert service._generate_fallback_summary([]) == "Empty conversation"

    def test_no_user_messages(self, service, msg_factory):
        """If there's no user message, fall back to a count-based summary."""
        msgs = [
            msg_factory(role=MessageRole.ASSISTANT, content="hi"),
            msg_factory(role=MessageRole.ASSISTANT, content="hello"),
        ]
        out = service._generate_fallback_summary(msgs)
        assert out == "Conversation with 2 messages"

    def test_first_user_truncated_at_word(self, service, msg_factory):
        """A long first user message gets word-truncated and prefixed with 'Discussion about:'."""
        long_msg = ("word " * 50).strip()  # 249 chars with spaces
        msgs = [msg_factory(role=MessageRole.USER, content=long_msg)]
        out = service._generate_fallback_summary(msgs)
        assert out.startswith("Discussion about: ")
        assert out.endswith("...")


# ---------------------------------------------------------------------------
# TestGenerateSummary
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGenerateSummary:
    @pytest.mark.asyncio
    async def test_openai_success(
        self, service, mock_sync_db, thread_factory, msg_factory, monkeypatch
    ):
        """OpenAI returns a summary string → thread.summary updated, rate-limit set, summary returned."""
        thread = thread_factory(message_count=5)
        messages = [msg_factory(content="hi") for _ in range(3)]
        _install_query_chain(mock_sync_db, thread=thread, messages=messages)

        monkeypatch.setattr(
            "src.services.threads.thread_summarization_service.settings.OPENAI_API_KEY",
            "sk-test",
        )
        fake_openai, _ = _make_openai_module(content="Great chat about widgets.")
        monkeypatch.setitem(sys.modules, "openai", fake_openai)

        result = await service.generate_summary(thread.id)

        assert result == "Great chat about widgets."
        assert thread.summary == "Great chat about widgets."
        mock_sync_db.commit.assert_called_once()
        service._redis_client.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_openai_timeout_returns_fallback(
        self, service, mock_sync_db, thread_factory, msg_factory, monkeypatch
    ):
        """asyncio.TimeoutError from the OpenAI call surfaces to the outer handler → fallback summary."""
        thread = thread_factory(message_count=5)
        messages = [msg_factory(content="topic of discussion")]
        _install_query_chain(mock_sync_db, thread=thread, messages=messages)

        monkeypatch.setattr(
            "src.services.threads.thread_summarization_service.settings.OPENAI_API_KEY",
            "sk-test",
        )
        fake_openai, client = _make_openai_module(content="ignored")
        client.chat.completions.create = AsyncMock(side_effect=asyncio.TimeoutError())
        monkeypatch.setitem(sys.modules, "openai", fake_openai)

        result = await service.generate_summary(thread.id)

        # Outer handler returns fallback summary (line 197-199 in source)
        assert result is not None
        assert result.startswith("Discussion about:") or result.startswith(
            "Conversation with"
        )
        # Outer handler does NOT call _update_thread_summary on timeout
        mock_sync_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_openai_none_falls_through_to_anthropic(
        self, service, mock_sync_db, thread_factory, msg_factory, monkeypatch
    ):
        """If OpenAI returns no content, Anthropic is tried next and its summary is committed."""
        thread = thread_factory(message_count=5)
        messages = [msg_factory(content="hi")]
        _install_query_chain(mock_sync_db, thread=thread, messages=messages)

        monkeypatch.setattr(
            "src.services.threads.thread_summarization_service.settings.OPENAI_API_KEY",
            "sk-test",
        )
        monkeypatch.setattr(
            "src.services.threads.thread_summarization_service.settings.ANTHROPIC_API_KEY",
            "anthropic-test",
        )
        fake_openai, _ = _make_openai_module(content=None)  # empty choices → None
        fake_anthropic, _ = _make_anthropic_module(text="Anthropic summary.")
        monkeypatch.setitem(sys.modules, "openai", fake_openai)
        monkeypatch.setitem(sys.modules, "anthropic", fake_anthropic)

        result = await service.generate_summary(thread.id)

        assert result == "Anthropic summary."
        assert thread.summary == "Anthropic summary."
        mock_sync_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_keys_uses_fallback(
        self, service, mock_sync_db, thread_factory, msg_factory
    ):
        """With both API keys empty, the heuristic fallback summary is used and committed."""
        thread = thread_factory(message_count=5)
        messages = [
            msg_factory(role=MessageRole.USER, content="What's the deal with X?")
        ]
        _install_query_chain(mock_sync_db, thread=thread, messages=messages)

        result = await service.generate_summary(thread.id)

        assert result is not None
        assert result.startswith("Discussion about:")
        assert thread.summary == result
        mock_sync_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_thread_not_found_returns_none(self, service, mock_sync_db):
        """If the thread doesn't exist, generate_summary returns None without touching the DB."""
        _install_query_chain(mock_sync_db, thread=None)

        result = await service.generate_summary(uuid4())

        assert result is None
        mock_sync_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_messages_returns_none(
        self, service, mock_sync_db, thread_factory
    ):
        """A thread with zero messages short-circuits to None."""
        thread = thread_factory(message_count=5)
        _install_query_chain(mock_sync_db, thread=thread, messages=[])

        result = await service.generate_summary(thread.id, force=True)

        assert result is None
        mock_sync_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_when_should_not_summarize_no_force(
        self, service, mock_sync_db, thread_factory
    ):
        """When should_summarize is False and force=False, the existing summary is returned untouched."""
        thread = thread_factory(message_count=1, summary="existing")
        _install_query_chain(mock_sync_db, thread=thread)

        result = await service.generate_summary(thread.id, force=False)

        assert result == "existing"
        mock_sync_db.commit.assert_not_called()
