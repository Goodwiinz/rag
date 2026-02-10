"""Token counting utilities for LLM operations.

Provides functions to estimate token counts for text content,
used for tracking usage and managing context windows.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import tiktoken
except ImportError:  # pragma: no cover - optional dependency
    tiktoken = None

# Average characters per token for estimation (conservative estimate)
# GPT models average ~4 chars/token for English, we use 3.5 for safety margin
CHARS_PER_TOKEN_ESTIMATE = 3.5


def count_tokens(text: str, model: Optional[str] = None) -> int:
    """
    Count tokens in text using tiktoken if available, otherwise estimate.

    Args:
        text: The text to count tokens for
        model: Optional model name for more accurate counting

    Returns:
        Token count (exact if tiktoken available, estimated otherwise)
    """
    if not text:
        return 0

    # Try to use tiktoken for accurate counting
    try:
        if tiktoken is None:
            raise ImportError("tiktoken not available")

        # Map common model names to encoding
        encoding_name = "cl100k_base"  # Default for GPT-4, Claude-compatible

        if model:
            model_lower = model.lower()
            if "gpt-4" in model_lower or "gpt-3.5" in model_lower:
                encoding_name = "cl100k_base"
            elif "davinci" in model_lower or "curie" in model_lower:
                encoding_name = "p50k_base"

        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))

    except ImportError:
        # tiktoken not installed, use estimation
        pass
    except Exception as e:
        logger.debug(f"tiktoken encoding failed, using estimation: {e}")

    # Fallback: estimate based on character count
    return estimate_tokens(text)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count based on character count.

    Uses a conservative estimate of ~3.5 characters per token.
    This is a reasonable approximation for English text.

    Args:
        text: The text to estimate tokens for

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    # Count characters (excluding excessive whitespace)
    normalized = " ".join(text.split())
    char_count = len(normalized)

    # Estimate tokens
    return max(1, int(char_count / CHARS_PER_TOKEN_ESTIMATE))


def count_message_tokens(
    content: str, role: str = "user", estimate_only: bool = False
) -> int:
    """
    Count tokens for a chat message, including role overhead.

    Chat messages have additional tokens for role markers and formatting.

    Args:
        content: Message content
        role: Message role (user, assistant, system)
        estimate_only: If True, use fast estimation instead of tiktoken.
            Use this in request handlers to avoid blocking on large messages.

    Returns:
        Total token count including overhead
    """
    # Use fast estimation for request paths to prevent timeouts on large messages
    if estimate_only:
        content_tokens = estimate_tokens(content)
    else:
        content_tokens = count_tokens(content)

    # Add overhead for role and message structure
    # Typically ~4 tokens per message for role markers
    overhead = 4

    return content_tokens + overhead
