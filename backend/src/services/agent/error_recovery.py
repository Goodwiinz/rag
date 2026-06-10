"""Structured error recovery for agent tool execution."""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

logger = logging.getLogger(__name__)

ErrorCategory = Literal["transient", "recoverable", "user_fixable", "fatal"]

# Maps (tool_name, error_keyword) -> (category, suggestion)
TOOL_ERROR_HINTS: dict[tuple[str, str], tuple[ErrorCategory, str]] = {
    ("add_document_to_project", "not found"): (
        "recoverable",
        "The document must be ingested first. Use ingest_arxiv_papers with the arXiv paper IDs.",
    ),
    ("add_document_to_project", "not a valid uuid"): (
        "recoverable",
        "Use document UUIDs from ingest_arxiv_papers, not arXiv paper IDs.",
    ),
    ("ingest_arxiv_papers", "timed out"): (
        "transient",
        "ArXiv ingestion timed out. Try fewer papers (max 3 at a time).",
    ),
    ("search_arxiv", "no results"): (
        "recoverable",
        "No results found. Try broader search terms or different keywords.",
    ),
    ("search_documents", "no results"): (
        "recoverable",
        "No matching documents found. Try different search terms or ingest new papers first.",
    ),
}

# Exception types that are always transient (CancelledError is intentionally excluded —
# it means the caller aborted the request and must propagate immediately, not be retried)
_TRANSIENT_EXCEPTIONS = (asyncio.TimeoutError, ConnectionError, OSError)
_USER_FIXABLE_EXCEPTIONS = (PermissionError,)


@dataclass(frozen=True)
class ToolError:
    """Structured tool error with category and actionable suggestion."""
    category: ErrorCategory
    message: str
    suggestion: str = ""

    def to_tool_message_content(self) -> str:
        payload: dict[str, Any] = {
            "error": self.message,
            "error_type": self.category,
        }
        if self.suggestion:
            payload["suggestion"] = self.suggestion
        return json.dumps(payload)

    def to_state_info(self) -> dict:
        return {
            "category": self.category,
            "message": self.message,
            "suggestion": self.suggestion,
        }


def classify_error(tool_name: str, exc: Exception) -> ToolError:
    """Classify a thrown exception into a ToolError."""
    msg = str(exc)

    # Check user_fixable before transient (PermissionError is a subclass of OSError)
    if isinstance(exc, _USER_FIXABLE_EXCEPTIONS):
        return ToolError(category="user_fixable", message=msg, suggestion="Check your permissions or ask the user for help.")

    if isinstance(exc, _TRANSIENT_EXCEPTIONS):
        return ToolError(category="transient", message=msg, suggestion="Retrying automatically...")

    # Check hints by keyword
    msg_lower = msg.lower()
    for (tn, keyword), (cat, suggestion) in TOOL_ERROR_HINTS.items():
        if tn == tool_name and keyword in msg_lower:
            return ToolError(category=cat, message=msg, suggestion=suggestion)

    return ToolError(category="fatal", message=msg)


def classify_error_from_payload(tool_name: str, payload: dict) -> ToolError:
    """Classify an error from a returned payload dict.

    Keyword check ordering matters: more-specific categories must run
    before more-general ones. Otherwise:
    - "permission timeout" gets caught by ``timeout`` and misclassified
      as transient (the underlying cause is access, not flakiness).
    - "invalid api key" / "invalid credentials" get caught by
      ``invalid`` and misclassified as recoverable input errors.
    """
    error_msg = payload.get("error", "")
    msg_lower = error_msg.lower()

    # 1. Per-tool hints (most specific).
    for (tn, keyword), (cat, suggestion) in TOOL_ERROR_HINTS.items():
        if tn == tool_name and keyword in msg_lower:
            return ToolError(category=cat, message=error_msg, suggestion=suggestion)

    # 2. Credential-style "invalid" errors are NOT recoverable by the LLM
    # — the user has to fix them. Match these BEFORE the generic
    # "invalid" fallthrough below.
    if any(
        kw in msg_lower
        for kw in (
            "invalid api key",
            "invalid credentials",
            "invalid token",
            "invalid signature",
            "expired token",
        )
    ):
        return ToolError(
            category="user_fixable",
            message=error_msg,
            suggestion="Authentication failed — check API credentials.",
        )

    # 3. Permission / authorization errors take precedence over transient
    # ones so phrases like "permission timeout" are not swallowed by the
    # transient-keyword check.
    if any(kw in msg_lower for kw in ("permission", "unauthorized", "forbidden")):
        return ToolError(
            category="user_fixable",
            message=error_msg,
            suggestion="You may need different permissions.",
        )

    # 4. Transient infrastructure errors. Connection keywords are scoped —
    # a bare "connection" also matches benign payload text like "no
    # connection found between entities" and would retry a fatal error.
    if any(
        kw in msg_lower
        for kw in (
            "timeout",
            "timed out",
            "connection refused",
            "connection reset",
            "connection error",
            "connection closed",
            "connection failed",
            # Canonical requests/urllib3 failure string:
            # ('Connection aborted.', RemoteDisconnected(...))
            "connection aborted",
            "econnrefused",
            "econnreset",
        )
    ):
        return ToolError(category="transient", message=error_msg)

    # 5. Recoverable input-shape errors (LLM can usually retry differently).
    if any(
        kw in msg_lower
        for kw in ("not found", "does not exist", "no results", "invalid")
    ):
        return ToolError(
            category="recoverable",
            message=error_msg,
            suggestion="Check the input and try again.",
        )

    return ToolError(category="fatal", message=error_msg)


async def retry_transient(
    fn: Callable[[], Awaitable[Any]],
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> Any:
    """Retry a coroutine on transient errors with exponential backoff.

    Raises ``ValueError`` for non-positive ``max_attempts`` rather than
    falling through the empty range and re-raising ``None`` (which would
    surface as a confusing ``TypeError: exceptions must derive from
    BaseException``).
    """
    if max_attempts < 1:
        raise ValueError(
            f"retry_transient requires max_attempts >= 1, got {max_attempts}"
        )

    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await fn()
        except asyncio.CancelledError:
            raise
        except _TRANSIENT_EXCEPTIONS as e:
            last_exc = e
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)
                logger.info(
                    "Transient error (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    max_attempts,
                    delay,
                    e,
                )
                await asyncio.sleep(delay)
    # ``last_exc`` is non-None here because the only way to exit the loop
    # without ``return`` is by hitting a transient exception that
    # populated it.
    assert last_exc is not None
    raise last_exc
