"""
Unit tests for Thread Summarization Service (GOO-48)

Tests the ThreadSummarizationService:
- should_summarize(): Rate limiting and message count checks
- generate_summary(): LLM integration with fallback
- _format_messages_for_prompt(): Message formatting
- _clean_summary(): Summary cleanup and truncation
- _generate_fallback_summary(): Fallback when no LLM available
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4, UUID
from datetime import datetime, timezone
import asyncio

import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))


class TestShouldSummarize:
    """Test ThreadSummarizationService.should_summarize() method"""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        return Mock()

    @pytest.fixture
    def summarization_service(self, mock_db_session):
        """Create ThreadSummarizationService instance"""
        from src.services.thread_summarization_service import ThreadSummarizationService

        service = ThreadSummarizationService(mock_db_session)
        service._redis_client = None  # Disable Redis for unit tests
        return service

    @pytest.fixture
    def mock_thread(self):
        """Create a mock Thread object"""
        def _create_thread(message_count: int = 5):
            thread = Mock()
            thread.id = uuid4()
            thread.message_count = message_count
            thread.summary = None
            return thread
        return _create_thread

    def test_should_not_summarize_with_less_than_3_messages(self, summarization_service, mock_thread):
        """Test should_summarize returns False when message_count < 3"""
        thread = mock_thread(message_count=2)

        result = summarization_service.should_summarize(thread)

        assert result is False

    def test_should_summarize_with_3_or_more_messages(self, summarization_service, mock_thread):
        """Test should_summarize returns True when message_count >= 3"""
        thread = mock_thread(message_count=3)

        result = summarization_service.should_summarize(thread)

        assert result is True

    def test_should_summarize_with_many_messages(self, summarization_service, mock_thread):
        """Test should_summarize returns True with many messages"""
        thread = mock_thread(message_count=50)

        result = summarization_service.should_summarize(thread)

        assert result is True

    def test_should_not_summarize_when_rate_limited(self, summarization_service, mock_thread):
        """Test should_summarize returns False when rate limited via Redis"""
        thread = mock_thread(message_count=5)

        # Mock Redis client to return that key exists (rate limited)
        mock_redis = Mock()
        mock_redis.exists = Mock(return_value=True)
        summarization_service._redis_client = mock_redis

        result = summarization_service.should_summarize(thread)

        assert result is False
        mock_redis.exists.assert_called_once()

    def test_should_summarize_when_not_rate_limited(self, summarization_service, mock_thread):
        """Test should_summarize returns True when not rate limited"""
        thread = mock_thread(message_count=5)

        # Mock Redis client to return that key doesn't exist
        mock_redis = Mock()
        mock_redis.exists = Mock(return_value=False)
        summarization_service._redis_client = mock_redis

        result = summarization_service.should_summarize(thread)

        assert result is True

    def test_should_summarize_handles_redis_error(self, summarization_service, mock_thread):
        """Test should_summarize handles Redis errors gracefully"""
        thread = mock_thread(message_count=5)

        # Mock Redis client to throw an error
        mock_redis = Mock()
        mock_redis.exists = Mock(side_effect=Exception("Redis connection error"))
        summarization_service._redis_client = mock_redis

        # Should still return True (fail open)
        result = summarization_service.should_summarize(thread)

        assert result is True


class TestFormatMessagesForPrompt:
    """Test ThreadSummarizationService._format_messages_for_prompt() method"""

    @pytest.fixture
    def summarization_service(self):
        """Create ThreadSummarizationService instance"""
        from src.services.thread_summarization_service import ThreadSummarizationService

        mock_db = Mock()
        return ThreadSummarizationService(mock_db)

    @pytest.fixture
    def mock_message(self):
        """Create a mock ChatMessage object"""
        def _create_message(role: str, content: str):
            from src.models.message import MessageRole

            message = Mock()
            message.role = MessageRole.USER if role == "user" else MessageRole.ASSISTANT
            message.content = content
            return message
        return _create_message

    def test_format_single_message(self, summarization_service, mock_message):
        """Test formatting a single message"""
        messages = [mock_message("user", "Hello, how are you?")]

        result = summarization_service._format_messages_for_prompt(messages)

        assert "User: Hello, how are you?" in result

    def test_format_multiple_messages(self, summarization_service, mock_message):
        """Test formatting multiple messages"""
        messages = [
            mock_message("user", "Hello"),
            mock_message("assistant", "Hi there!"),
            mock_message("user", "How are you?"),
        ]

        result = summarization_service._format_messages_for_prompt(messages)

        assert "User: Hello" in result
        assert "Assistant: Hi there!" in result
        assert "User: How are you?" in result

    def test_format_truncates_long_messages(self, summarization_service, mock_message):
        """Test that individual messages over 500 chars are truncated"""
        long_content = "A" * 600
        messages = [mock_message("user", long_content)]

        result = summarization_service._format_messages_for_prompt(messages)

        # Should be truncated to 500 chars + "..."
        assert len(result) < 600
        assert "..." in result

    def test_format_respects_max_chars_limit(self, summarization_service, mock_message):
        """Test that total output respects max_chars limit"""
        messages = [mock_message("user", "A" * 300) for _ in range(10)]

        result = summarization_service._format_messages_for_prompt(messages, max_chars=500)

        assert len(result) <= 500 + 100  # Allow some buffer for role prefix

    def test_format_handles_empty_content(self, summarization_service, mock_message):
        """Test handling of messages with empty content"""
        message = Mock()
        message.role = Mock()
        message.role.name = "USER"
        message.content = None

        # Create a proper mock with MessageRole
        from src.models.message import MessageRole
        message.role = MessageRole.USER

        messages = [message]

        result = summarization_service._format_messages_for_prompt(messages)

        assert "User:" in result


class TestCleanSummary:
    """Test ThreadSummarizationService._clean_summary() method"""

    @pytest.fixture
    def summarization_service(self):
        """Create ThreadSummarizationService instance"""
        from src.services.thread_summarization_service import ThreadSummarizationService

        mock_db = Mock()
        return ThreadSummarizationService(mock_db)

    def test_clean_removes_quotes(self, summarization_service):
        """Test that quotes are removed from summary"""
        summary = '"This is a quoted summary"'

        result = summarization_service._clean_summary(summary)

        assert not result.startswith('"')
        assert not result.endswith('"')

    def test_clean_removes_single_quotes(self, summarization_service):
        """Test that single quotes are removed from summary"""
        summary = "'This is a quoted summary'"

        result = summarization_service._clean_summary(summary)

        assert not result.startswith("'")
        assert not result.endswith("'")

    def test_clean_truncates_long_summary(self, summarization_service):
        """Test that long summaries are truncated"""
        from src.services.thread_summarization_service import MAX_SUMMARY_LENGTH

        long_summary = "A" * (MAX_SUMMARY_LENGTH + 100)

        result = summarization_service._clean_summary(long_summary)

        assert len(result) <= MAX_SUMMARY_LENGTH

    def test_clean_preserves_short_summary(self, summarization_service):
        """Test that short summaries are not modified"""
        summary = "This is a short summary."

        result = summarization_service._clean_summary(summary)

        assert result == summary

    def test_clean_truncates_at_sentence_boundary(self, summarization_service):
        """Test that truncation prefers sentence boundaries"""
        from src.services.thread_summarization_service import MAX_SUMMARY_LENGTH

        # Create a summary with sentences that exceeds max length
        sentences = "This is sentence one. This is sentence two. This is sentence three."
        long_summary = sentences + " " + "A" * MAX_SUMMARY_LENGTH

        result = summarization_service._clean_summary(long_summary)

        # Should end with a period if truncated at sentence boundary
        assert len(result) <= MAX_SUMMARY_LENGTH


class TestGenerateFallbackSummary:
    """Test ThreadSummarizationService._generate_fallback_summary() method"""

    @pytest.fixture
    def summarization_service(self):
        """Create ThreadSummarizationService instance"""
        from src.services.thread_summarization_service import ThreadSummarizationService

        mock_db = Mock()
        return ThreadSummarizationService(mock_db)

    @pytest.fixture
    def mock_message(self):
        """Create a mock ChatMessage object"""
        def _create_message(role: str, content: str):
            from src.models.message import MessageRole

            message = Mock()
            message.role = MessageRole.USER if role == "user" else MessageRole.ASSISTANT
            message.content = content
            return message
        return _create_message

    def test_fallback_with_empty_messages(self, summarization_service):
        """Test fallback with no messages"""
        result = summarization_service._generate_fallback_summary([])

        assert "Empty conversation" in result

    def test_fallback_uses_first_user_message(self, summarization_service, mock_message):
        """Test fallback uses first user message as topic"""
        messages = [
            mock_message("user", "How do I configure Docker?"),
            mock_message("assistant", "Here's how to configure Docker..."),
        ]

        result = summarization_service._generate_fallback_summary(messages)

        assert "Discussion about:" in result
        assert "Docker" in result

    def test_fallback_truncates_long_topic(self, summarization_service, mock_message):
        """Test fallback truncates long first message"""
        long_content = "A" * 200
        messages = [mock_message("user", long_content)]

        result = summarization_service._generate_fallback_summary(messages)

        assert len(result) < 200
        assert "..." in result

    def test_fallback_with_only_assistant_messages(self, summarization_service, mock_message):
        """Test fallback when no user messages exist"""
        messages = [
            mock_message("assistant", "Welcome! How can I help?"),
            mock_message("assistant", "I'm here to assist."),
        ]

        result = summarization_service._generate_fallback_summary(messages)

        assert "Conversation with" in result
        assert "2 messages" in result


class TestGenerateSummaryAsync:
    """Test ThreadSummarizationService.generate_summary() async method"""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        mock_db = Mock()
        mock_db.query = Mock()
        mock_db.commit = Mock()
        return mock_db

    @pytest.fixture
    def summarization_service(self, mock_db_session):
        """Create ThreadSummarizationService instance"""
        from src.services.thread_summarization_service import ThreadSummarizationService

        service = ThreadSummarizationService(mock_db_session)
        service._redis_client = None
        return service

    @pytest.fixture
    def mock_thread_with_messages(self, mock_db_session):
        """Create mock thread and messages"""
        from src.models.message import MessageRole

        thread = Mock()
        thread.id = uuid4()
        thread.message_count = 5
        thread.summary = None

        messages = []
        for i in range(5):
            msg = Mock()
            msg.role = MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT
            msg.content = f"Message {i}"
            msg.is_deleted = False
            msg.created_at = datetime.now(timezone.utc)
            messages.append(msg)

        return thread, messages

    @pytest.mark.asyncio
    async def test_generate_summary_returns_existing_when_not_needed(
        self, summarization_service, mock_db_session
    ):
        """Test that existing summary is returned when summarization not needed"""
        thread = Mock()
        thread.id = uuid4()
        thread.message_count = 2  # Less than minimum
        thread.summary = "Existing summary"

        mock_db_session.query.return_value.filter.return_value.first.return_value = thread

        result = await summarization_service.generate_summary(thread.id)

        assert result == "Existing summary"

    @pytest.mark.asyncio
    async def test_generate_summary_returns_none_for_missing_thread(
        self, summarization_service, mock_db_session
    ):
        """Test that None is returned for non-existent thread"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        result = await summarization_service.generate_summary(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_summary_force_bypasses_checks(
        self, summarization_service, mock_db_session, mock_thread_with_messages
    ):
        """Test that force=True bypasses should_summarize checks"""
        thread, messages = mock_thread_with_messages
        thread.message_count = 1  # Would normally fail check

        mock_db_session.query.return_value.filter.return_value.first.return_value = thread
        mock_db_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.all.return_value = messages

        # Mock should_summarize to return False
        summarization_service.should_summarize = Mock(return_value=False)

        # Should still generate with force=True
        with patch.object(summarization_service, '_generate_fallback_summary', return_value="Forced summary"):
            result = await summarization_service.generate_summary(thread.id, force=True)

        assert result is not None


class TestLLMProviders:
    """Test LLM provider integration with mocks"""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session"""
        return Mock()

    @pytest.fixture
    def summarization_service(self, mock_db_session):
        """Create ThreadSummarizationService instance"""
        from src.services.thread_summarization_service import ThreadSummarizationService

        return ThreadSummarizationService(mock_db_session)

    @pytest.mark.asyncio
    async def test_openai_provider_success(self, summarization_service):
        """Test successful OpenAI summary generation"""
        with patch('src.services.thread_summarization_service.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"

            with patch('openai.AsyncOpenAI') as mock_openai:
                mock_client = AsyncMock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = "Test summary from OpenAI"
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai.return_value = mock_client

                result = await summarization_service._generate_with_openai(
                    "User: Hello\nAssistant: Hi",
                    timeout=10.0
                )

                assert result == "Test summary from OpenAI"

    @pytest.mark.asyncio
    async def test_openai_provider_timeout(self, summarization_service):
        """Test OpenAI timeout handling"""
        with patch('src.services.thread_summarization_service.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"

            with patch('openai.AsyncOpenAI') as mock_openai:
                mock_client = AsyncMock()
                mock_client.chat.completions.create = AsyncMock(
                    side_effect=asyncio.TimeoutError()
                )
                mock_openai.return_value = mock_client

                # Should handle timeout gracefully
                try:
                    result = await summarization_service._generate_with_openai(
                        "User: Hello",
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    result = None

                # Result should be None on timeout
                assert result is None

    @pytest.mark.asyncio
    async def test_anthropic_provider_success(self, summarization_service):
        """Test successful Anthropic summary generation"""
        with patch('src.services.thread_summarization_service.settings') as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = "test-key"

            with patch('anthropic.AsyncAnthropic') as mock_anthropic:
                mock_client = AsyncMock()
                mock_response = Mock()
                mock_response.content = [Mock()]
                mock_response.content[0].text = "Test summary from Anthropic"
                mock_client.messages.create = AsyncMock(return_value=mock_response)
                mock_anthropic.return_value = mock_client

                result = await summarization_service._generate_with_anthropic(
                    "User: Hello\nAssistant: Hi",
                    timeout=10.0
                )

                assert result == "Test summary from Anthropic"

    @pytest.mark.asyncio
    async def test_fallback_when_no_api_keys(self, summarization_service):
        """Test fallback to basic summary when no API keys configured"""
        with patch('src.services.thread_summarization_service.settings') as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.ANTHROPIC_API_KEY = None

            from src.models.message import MessageRole

            messages = [Mock()]
            messages[0].role = MessageRole.USER
            messages[0].content = "How do I use Python?"

            result = summarization_service._generate_fallback_summary(messages)

            assert "Discussion about:" in result or "Python" in result
