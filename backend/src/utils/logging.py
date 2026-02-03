"""Logging utilities for safe content handling.

Provides functions to truncate and sanitize content before logging
to prevent sensitive data exposure in log files.
"""

import re
from typing import List, Optional

# Default PII patterns for sanitization
# These patterns detect common sensitive data formats
DEFAULT_PII_PATTERNS: List[str] = [
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email addresses
    r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Phone numbers (US format)
    r"\b\d{3}[-]?\d{2}[-]?\d{4}\b",  # Social Security Numbers
    r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b",  # Credit card numbers
    r"\b[A-Za-z0-9]{20,}\b(?=.*key|.*token|.*secret)",  # API keys/tokens (heuristic)
]


def truncate_for_logging(content: str, max_length: int = 100) -> str:
    """
    Truncate content for safe logging with ellipsis indicator.

    Args:
        content: Content to truncate
        max_length: Maximum length before truncation (default 100)

    Returns:
        Truncated string with '...' suffix if truncated
    """
    if not content:
        return ""

    if len(content) <= max_length:
        return content

    return content[:max_length] + "..."


def sanitize_for_logging(
    content: str, max_length: int = 100, mask_patterns: Optional[List[str]] = None
) -> str:
    """
    Sanitize and truncate content for logging, masking sensitive patterns.

    Args:
        content: Content to sanitize
        max_length: Maximum length before truncation
        mask_patterns: List of regex patterns to mask (emails, phone numbers, etc.)

    Returns:
        Sanitized and truncated string
    """
    if not content:
        return ""

    sanitized = content

    # Use default PII patterns if none provided
    patterns_to_use = (
        mask_patterns if mask_patterns is not None else DEFAULT_PII_PATTERNS
    )

    # Mask sensitive patterns
    for pattern in patterns_to_use:
        sanitized = re.sub(pattern, "[REDACTED]", sanitized)

    # Truncate
    return truncate_for_logging(sanitized, max_length)
