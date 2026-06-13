"""Client-safe error helpers for the agent API.

Provides utilities that log the full internal exception server-side while
returning a generic, non-leaking message to the caller.  Callers should
replace bare ``str(e)`` in client-facing payloads with ``client_safe_error``.
"""

import logging

logger = logging.getLogger(__name__)


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
