"""AI-Powered Thread Title Generator.

Uses LLM to generate concise, meaningful titles for chat threads
based on the initial conversation content.
"""

import logging
from typing import Optional
import asyncio

from ..core.config import settings

logger = logging.getLogger(__name__)


# Prompt for title generation
TITLE_GENERATION_PROMPT = """Generate a concise, descriptive title for this chat thread based on the user's question/request.

Requirements:
- Maximum 50 characters
- No quotes or special characters
- Capture the main topic or intent
- Use title case

User message:
{message}

Respond with ONLY the title, nothing else."""


async def generate_ai_title(message_content: str, timeout: float = 5.0) -> Optional[str]:
    """
    Generate an AI-powered title for a thread based on message content.

    Args:
        message_content: The user's first message content
        timeout: Maximum time to wait for AI response (default 5 seconds)

    Returns:
        Generated title or None if generation fails/times out
    """
    if not message_content or len(message_content.strip()) < 5:
        return "New Thread"  # Consistent with generate_title_sync

    # Truncate very long messages to avoid token limits
    truncated = message_content[:500] if len(message_content) > 500 else message_content

    try:
        # Try to use OpenAI if available
        if settings.OPENAI_API_KEY:
            return await _generate_with_openai(truncated, timeout)

        # Fallback to Anthropic if available
        if settings.ANTHROPIC_API_KEY:
            return await _generate_with_anthropic(truncated, timeout)

        # No API keys configured, use smart fallback
        return _generate_smart_fallback(truncated)

    except asyncio.TimeoutError:
        logger.warning("AI title generation timed out, using fallback")
        return _generate_smart_fallback(truncated)
    except Exception as e:
        logger.warning(f"AI title generation failed: {e}, using fallback")
        return _generate_smart_fallback(truncated)


async def _generate_with_openai(content: str, timeout: float) -> Optional[str]:
    """Generate title using OpenAI API."""
    try:
        import openai

        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "user",
                        "content": TITLE_GENERATION_PROMPT.format(message=content)
                    }
                ],
                max_tokens=50,
                temperature=0.3,
            ),
            timeout=timeout
        )

        if not response.choices or not response.choices[0].message.content:
            logger.warning("OpenAI returned empty response")
            return None
        title = response.choices[0].message.content.strip()
        # Clean up the title
        title = title.strip('"\'')
        # Ensure max length
        if len(title) > 50:
            title = title[:47] + "..."
        return title

    except ImportError:
        logger.debug("OpenAI package not installed")
        return None


async def _generate_with_anthropic(content: str, timeout: float) -> Optional[str]:
    """Generate title using Anthropic API."""
    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        response = await asyncio.wait_for(
            client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=50,
                messages=[
                    {
                        "role": "user",
                        "content": TITLE_GENERATION_PROMPT.format(message=content)
                    }
                ],
            ),
            timeout=timeout
        )

        if not response.content or not response.content[0].text:
            logger.warning("Anthropic returned empty response")
            return None
        title = response.content[0].text.strip()
        # Clean up the title
        title = title.strip('"\'')
        # Ensure max length
        if len(title) > 50:
            title = title[:47] + "..."
        return title

    except ImportError:
        logger.debug("Anthropic package not installed")
        return None


def _generate_smart_fallback(content: str) -> str:
    """
    Generate a smarter title without AI by extracting key information.

    Uses heuristics to create more meaningful titles than simple truncation:
    - Removes filler words
    - Extracts question topics
    - Handles common patterns
    """
    import re

    # Clean up the content
    text = content.strip()

    # Remove common greeting patterns
    text = re.sub(r'^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening))[,!.\s]*', '', text, flags=re.IGNORECASE)
    text = text.strip()

    # If it's a question, try to extract the core question
    question_patterns = [
        (r'^(can you|could you|would you|will you)\s+(.+?)(\?|$)', r'\2'),
        (r'^(how (do|can|should) I|how to)\s+(.+?)(\?|$)', r'How to \3'),
        (r'^(what is|what are|what\'s)\s+(.+?)(\?|$)', r'\2'),
        (r'^(why (is|are|does|do))\s+(.+?)(\?|$)', r'Why \3'),
        (r'^(explain|describe|tell me about)\s+(.+?)(\?|$)', r'\2'),
    ]

    for pattern, replacement in question_patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            break

    # Remove trailing punctuation except for meaningful ones
    text = text.rstrip('?.!,;:')

    # Title case
    text = text.strip().title()

    # Truncate to 50 chars
    if len(text) > 50:
        # Try to cut at word boundary
        truncated = text[:47]
        last_space = truncated.rfind(' ')
        if last_space > 30:
            truncated = truncated[:last_space]
        text = truncated + "..."

    return text if text else "New Thread"


def generate_title_sync(message_content: str) -> str:
    """
    Synchronous wrapper for title generation.
    Uses smart fallback only (no AI) for synchronous contexts.

    Args:
        message_content: The user's first message content

    Returns:
        Generated title
    """
    if not message_content or len(message_content.strip()) < 5:
        return "New Thread"

    return _generate_smart_fallback(message_content[:500])
