"""AI-Powered Thread Summarization Service.

Uses LLM to generate concise summaries for chat threads
based on the conversation content.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.chat_message import ChatMessage, MessageRole
from ..models.thread import Thread

logger = logging.getLogger(__name__)

# Minimum messages required before generating summary
MIN_MESSAGES_FOR_SUMMARY = 3

# Rate limit: minimum time between summary updates (seconds)
SUMMARY_RATE_LIMIT_SECONDS = 300  # 5 minutes

# Maximum summary length
MAX_SUMMARY_LENGTH = 150

# Prompt for summary generation
SUMMARY_GENERATION_PROMPT = """Summarize this conversation in 1-2 sentences (max 150 characters).
Focus on: main topic, key decisions or findings, current status.

Conversation:
{messages}

Respond with ONLY the summary, nothing else."""


class ThreadSummarizationService:
    """Service for generating AI-powered thread summaries."""

    def __init__(self, db: Session):
        self.db = db
        self._redis_client = None

    @property
    def redis_client(self):
        """Lazy load Redis client."""
        if self._redis_client is None:
            try:
                import redis

                self._redis_client = redis.Redis.from_url(
                    settings.REDIS_URL or "redis://localhost:6379/0",
                    decode_responses=True,
                )
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")
        return self._redis_client

    def should_summarize(self, thread: Thread) -> bool:
        """
        Check if a thread should be summarized.

        Args:
            thread: Thread model instance

        Returns:
            True if summary should be generated
        """
        # Must have minimum messages
        if thread.message_count < MIN_MESSAGES_FOR_SUMMARY:
            return False

        # Check rate limit via Redis
        if self.redis_client:
            try:
                rate_key = f"thread_summary:{thread.id}:last_generated"
                if self.redis_client.exists(rate_key):
                    logger.debug(f"Thread {thread.id} summary rate limited")
                    return False
            except Exception as e:
                logger.warning(f"Redis rate limit check failed: {e}")

        return True

    def _set_rate_limit(self, thread_id: UUID) -> None:
        """Set rate limit key in Redis."""
        if self.redis_client:
            try:
                rate_key = f"thread_summary:{thread_id}:last_generated"
                self.redis_client.setex(
                    rate_key, SUMMARY_RATE_LIMIT_SECONDS, datetime.utcnow().isoformat()
                )
            except Exception as e:
                logger.warning(f"Failed to set rate limit: {e}")

    def _format_messages_for_prompt(
        self, messages: list[ChatMessage], max_chars: int = 2000
    ) -> str:
        """
        Format messages for the summary prompt.

        Args:
            messages: List of ChatMessage objects
            max_chars: Maximum characters to include

        Returns:
            Formatted message string
        """
        formatted = []
        total_chars = 0

        for msg in messages:
            role = "User" if msg.role == MessageRole.USER else "Assistant"
            content = msg.content or ""

            # Truncate individual messages if too long
            if len(content) > 500:
                content = content[:497] + "..."

            line = f"{role}: {content}"

            if total_chars + len(line) > max_chars:
                break

            formatted.append(line)
            total_chars += len(line) + 1  # +1 for newline

        return "\n".join(formatted)

    async def generate_summary(
        self, thread_id: UUID, force: bool = False, timeout: float = 10.0
    ) -> Optional[str]:
        """
        Generate a summary for a thread.

        Args:
            thread_id: Thread UUID
            force: Skip rate limit check
            timeout: Maximum time to wait for AI response

        Returns:
            Generated summary or None if generation fails
        """
        # Load thread with messages
        thread = self.db.query(Thread).filter(Thread.id == thread_id).first()

        if not thread:
            logger.warning(f"Thread {thread_id} not found")
            return None

        # Check if we should summarize
        if not force and not self.should_summarize(thread):
            logger.debug(f"Thread {thread_id} does not need summarization")
            return thread.summary

        # Get messages
        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.thread_id == thread_id)
            .filter(ChatMessage.is_deleted == False)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

        if not messages:
            logger.warning(f"No messages found for thread {thread_id}")
            return None

        # Format messages for prompt
        messages_text = self._format_messages_for_prompt(messages)

        try:
            # Try to use OpenAI if available
            if settings.OPENAI_API_KEY:
                summary = await self._generate_with_openai(messages_text, timeout)
                if summary:
                    self._update_thread_summary(thread, summary)
                    self._set_rate_limit(thread_id)
                    return summary

            # Fallback to Anthropic if available
            if settings.ANTHROPIC_API_KEY:
                summary = await self._generate_with_anthropic(messages_text, timeout)
                if summary:
                    self._update_thread_summary(thread, summary)
                    self._set_rate_limit(thread_id)
                    return summary

            # No API keys configured, use fallback
            summary = self._generate_fallback_summary(messages)
            self._update_thread_summary(thread, summary)
            return summary

        except asyncio.TimeoutError:
            logger.warning(f"Summary generation timed out for thread {thread_id}")
            return self._generate_fallback_summary(messages)
        except Exception as e:
            logger.error(f"Summary generation failed for thread {thread_id}: {e}")
            return None

    def _update_thread_summary(self, thread: Thread, summary: str) -> None:
        """Update thread summary in database."""
        thread.summary = summary
        self.db.commit()
        logger.info(f"Updated summary for thread {thread.id}")

    async def _generate_with_openai(
        self, messages_text: str, timeout: float
    ) -> Optional[str]:
        """Generate summary using OpenAI API."""
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that creates concise conversation summaries.",
                        },
                        {
                            "role": "user",
                            "content": SUMMARY_GENERATION_PROMPT.format(
                                messages=messages_text
                            ),
                        },
                    ],
                    max_tokens=100,
                    temperature=0.3,
                ),
                timeout=timeout,
            )

            if not response.choices or not response.choices[0].message.content:
                logger.warning("OpenAI returned empty response")
                return None

            summary = response.choices[0].message.content.strip()
            return self._clean_summary(summary)

        except ImportError:
            logger.debug("OpenAI package not installed")
            return None

    async def _generate_with_anthropic(
        self, messages_text: str, timeout: float
    ) -> Optional[str]:
        """Generate summary using Anthropic API."""
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

            response = await asyncio.wait_for(
                client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=100,
                    messages=[
                        {
                            "role": "user",
                            "content": SUMMARY_GENERATION_PROMPT.format(
                                messages=messages_text
                            ),
                        }
                    ],
                ),
                timeout=timeout,
            )

            if not response.content or not response.content[0].text:
                logger.warning("Anthropic returned empty response")
                return None

            summary = response.content[0].text.strip()
            return self._clean_summary(summary)

        except ImportError:
            logger.debug("Anthropic package not installed")
            return None

    def _clean_summary(self, summary: str) -> str:
        """Clean and truncate summary."""
        # Remove quotes
        summary = summary.strip("\"'")

        # Ensure max length
        if len(summary) > MAX_SUMMARY_LENGTH:
            # Try to cut at sentence boundary
            truncated = summary[: MAX_SUMMARY_LENGTH - 3]
            last_period = truncated.rfind(".")
            if last_period > MAX_SUMMARY_LENGTH // 2:
                summary = truncated[: last_period + 1]
            else:
                # Cut at word boundary
                last_space = truncated.rfind(" ")
                if last_space > MAX_SUMMARY_LENGTH // 2:
                    summary = truncated[:last_space] + "..."
                else:
                    summary = truncated + "..."

        return summary

    def _generate_fallback_summary(self, messages: list[ChatMessage]) -> str:
        """
        Generate a basic summary without AI.

        Uses heuristics to create a simple summary.
        """
        if not messages:
            return "Empty conversation"

        # Get first user message as topic indicator
        first_user_msg = None
        for msg in messages:
            if msg.role == MessageRole.USER and msg.content:
                first_user_msg = msg.content
                break

        if not first_user_msg:
            return f"Conversation with {len(messages)} messages"

        # Truncate and clean
        topic = first_user_msg[:100].strip()
        if len(first_user_msg) > 100:
            last_space = topic.rfind(" ")
            if last_space > 50:
                topic = topic[:last_space]
            topic += "..."

        return f"Discussion about: {topic}"


def get_thread_summarization_service(db: Session) -> ThreadSummarizationService:
    """Factory function to create ThreadSummarizationService."""
    return ThreadSummarizationService(db)
