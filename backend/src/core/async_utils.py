"""Small async helpers shared across the backend."""

import asyncio


def reraise_if_cancelled(result) -> None:
    """Re-raise an ``asyncio.CancelledError`` that slipped through a
    ``gather(return_exceptions=True)`` result list.

    ``CancelledError`` is a ``BaseException`` (not ``Exception``) since Python
    3.8, so an ``isinstance(result, Exception)`` branch treats a cancelled task
    as a successful value. Call this *before* that check so cancellation
    propagates instead of being mis-handled as data.
    """
    if isinstance(result, asyncio.CancelledError):
        raise result
