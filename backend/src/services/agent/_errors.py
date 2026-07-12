"""Client-safe error helpers for the agent execution paths.

Provides utilities that log the full internal exception server-side while
returning a generic, non-leaking message to the caller.  Callers should
replace bare ``str(e)`` in client-facing payloads with ``client_safe_error``.

Lives in the service layer (moved from ``src.api.agent._errors``, audit
B5/C4-fold) because the graph runner in ``agent_execution_service`` needs it
and services must never import ``src.api``.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


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
