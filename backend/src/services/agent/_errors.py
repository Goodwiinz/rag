"""Client-safe error helpers for the agent execution paths.

Provides utilities that log the full internal exception server-side while
returning a generic, non-leaking message to the caller.  Callers should
replace bare ``str(e)`` in client-facing payloads with ``client_safe_error``.

Lives in the service layer (moved from ``src.api.agent._errors``, audit
B5/C4-fold) because the graph runner in ``agent_execution_service`` needs it
and services must never import ``src.api``.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple, Type, Union

from src.shared.enums import AgentErrorCategory

logger = logging.getLogger(__name__)


def _openai_error_types() -> Tuple[
    Tuple[Type[BaseException], ...],
    Tuple[Type[BaseException], ...],
    Tuple[Type[BaseException], ...],
]:
    """Resolve the openai SDK exception families, guardedly.

    The deployed LLM client is the ``openai`` package's ``AzureOpenAI`` /
    ``OpenAI`` (see ``src/services/infrastructure/azure_openai_service.py``),
    whose failures are ``openai.APIError`` subclasses — ``RateLimitError`` for
    429s, ``APITimeoutError`` for deadline overruns, and the rest of the
    ``APIStatusError`` / ``APIConnectionError`` families for everything else.
    The import is guarded so this module (and therefore the whole streaming
    route) never hard-depends on the SDK being installed.

    Returns ``(rate_limited, timeout, model_error)`` tuples, each empty when
    the SDK is unavailable.
    """
    try:
        from openai import (  # type: ignore[import-not-found]
            APIError,
            APITimeoutError,
            RateLimitError,
        )
    except Exception:  # pragma: no cover - SDK always present in this repo
        return ((), (), ())
    return ((RateLimitError,), (APITimeoutError,), (APIError,))


def classify_agent_error(exc: BaseException) -> AgentErrorCategory:
    """Map an exception to the server-authored SSE ``category`` label.

    Order matters: ``CancelledError`` is checked first, the timeout families
    before the generic ``APIError`` family (``APITimeoutError`` *is* an
    ``APIError``), and rate limiting before the rest of the status errors.

    ``asyncio.CancelledError`` is **never** swallowed by this function — it
    only maps a value. Cancellation semantics (re-raise, shield the partial
    persist) stay entirely with the callers, which catch ``CancelledError``
    ahead of ``Exception`` and re-raise. This branch exists only so a caller
    that deliberately reports a cancelled run gets the right label.
    """
    rate_limit_types, timeout_types, model_error_types = _openai_error_types()

    if isinstance(exc, asyncio.CancelledError):
        return AgentErrorCategory.CANCELLED
    # asyncio.TimeoutError is an alias of the builtin TimeoutError on 3.11+.
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return AgentErrorCategory.UPSTREAM_TIMEOUT
    if timeout_types and isinstance(exc, timeout_types):
        return AgentErrorCategory.UPSTREAM_TIMEOUT
    if rate_limit_types and isinstance(exc, rate_limit_types):
        return AgentErrorCategory.RATE_LIMITED
    if model_error_types and isinstance(exc, model_error_types):
        return AgentErrorCategory.MODEL_ERROR
    return AgentErrorCategory.INTERNAL


def error_frame_payload(
    exc_or_message: Union[BaseException, str],
    category: Optional[AgentErrorCategory] = None,
) -> Dict[str, Any]:
    """Build the payload for an ``AgentStreamEvent.ERROR`` frame.

    The single constructor for error frames, so no emit site can drift the key
    names or forget ``category``. ``error`` stays a plain string (the wire
    contract); ``category`` is a flat sibling key.

    Args:
        exc_or_message: An exception (routed through ``client_safe_error`` so
            nothing internal leaks) or an already-safe literal message.
        category: Explicit category. When omitted and an exception was passed,
            it is derived via :func:`classify_agent_error`; when omitted for a
            literal message it falls back to ``internal``.
    """
    if isinstance(exc_or_message, BaseException):
        message = client_safe_error(exc_or_message)
        resolved = category or classify_agent_error(exc_or_message)
    else:
        message = exc_or_message
        resolved = category or AgentErrorCategory.INTERNAL
    return {"error": message, "category": resolved.value}


def extract_interrupt_confirmation(exc: BaseException) -> Dict[str, Any]:
    """Pull the HITL confirmation payload out of a langgraph ``GraphInterrupt``.

    ``GraphInterrupt.__init__(interrupts)`` calls ``super().__init__(interrupts)``,
    so the ``Sequence[Interrupt]`` lands in ``exc.args[0]`` — there is **no**
    ``.interrupts`` attribute. The previous ``getattr(exc, "interrupts", [])``
    therefore always returned ``[]`` and every confirmation surfaced empty
    (the SSE ``confirmation`` event and the job ``confirmation`` field both
    shipped ``{}``, so clients had no tool details to confirm). Read
    ``args[0]`` and return the first interrupt's ``value``.
    """
    args = getattr(exc, "args", ())
    interrupts = args[0] if args else []
    if interrupts:
        return getattr(interrupts[0], "value", {}) or {}
    return {}


def client_safe_error(
    exc: BaseException,
    *,
    fallback: str = "The request could not be completed. Please retry.",
) -> str:
    """Log *exc* server-side and return a generic message safe for clients.

    The full exception detail is written to the server log so operators can
    diagnose failures.  Only the generic *fallback* string is returned to
    the caller, preventing internal implementation details (stack traces,
    database connection strings, model names, etc.) from leaking into API
    responses or SSE payloads.

    Args:
        exc:      The exception to log.
        fallback: The safe string to return to the client.  Defaults to a
                  neutral retry prompt.

    Returns:
        *fallback* — always the generic message, never ``str(exc)``.
    """
    logger.error("agent_request_error", exc_info=exc)
    return fallback
