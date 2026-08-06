"""CLI-token revocation via a per-user "revoked before" timestamp.

CLI tokens are long-lived (CLI_TOKEN_EXPIRE_DAYS, default 30) and otherwise
only signature+exp validated, so a leaked token of an *active* user could not
be invalidated without deactivating the user. This module records, per user, a
Redis timestamp before which all CLI tokens are considered revoked; the auth
chokepoint (get_current_user) rejects a CLI token whose issued-at predates it.

Design (approved): revoke-all-for-user (no per-jti tracking) + FAIL-OPEN — if
Redis is unavailable the check passes (the token stays signature/exp valid), so
a Redis outage never breaks CLI auth platform-wide; revocation is best-effort
and effective as soon as Redis is reachable again.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as redis

from src.core.config import settings

logger = logging.getLogger(__name__)

_KEY = "cli_revoked_before:{user_id}"
# Keep the marker at least as long as a CLI token can live, so a revoked-before
# cutoff outlives every token it must reject.
_TTL_SECONDS = settings.CLI_TOKEN_EXPIRE_DAYS * 24 * 3600

_client: Optional["redis.Redis"] = None


async def _get_redis() -> Optional["redis.Redis"]:
    global _client
    if _client is not None:
        return _client
    url = getattr(settings, "REDIS_URL", None)
    if not url:
        return None
    try:
        # Socket timeouts (repo's 5s standard) so a degraded/hung Redis fails
        # fast and the auth path fails OPEN instead of stalling get_current_user.
        _client = redis.from_url(
            url,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
        )
        return _client
    except Exception as e:  # noqa: BLE001 - fail open
        logger.warning("CLI revocation: Redis unavailable (%s)", e)
        return None


def _reset_client() -> None:
    """Drop the cached client so the next call reconnects. Prevents a client
    bound to a now-dead event loop from failing every subsequent call (which
    would silently defeat revocation forever — fail-open with no recovery)."""
    global _client
    _client = None


async def revoke_user_cli_tokens(user_id: str) -> None:
    """Revoke every CLI token issued to ``user_id`` up to now (best-effort)."""
    client = await _get_redis()
    if client is None:
        logger.warning("CLI revocation skipped (no Redis) for user %s", user_id)
        return
    try:
        # Store cutoff = next whole second so a token minted in the SAME second
        # as the revoke (iat is whole-second from create_cli_token) is still
        # caught by the `iat < cutoff` check ("revoke up to now" inclusive).
        cutoff = int(datetime.now(timezone.utc).timestamp()) + 1
        await client.set(_KEY.format(user_id=user_id), cutoff, ex=_TTL_SECONDS)
    except Exception as e:  # noqa: BLE001 - never raise into the caller
        logger.warning("CLI revocation write failed for user %s: %s", user_id, e)
        _reset_client()


async def is_cli_token_revoked(
    user_id: str, issued_at: Optional[datetime]
) -> bool:
    """True iff the CLI token (minted at ``issued_at``) has been revoked.

    Fail-open: any Redis error / missing key / missing issued_at -> not revoked.
    """
    if issued_at is None:
        return False
    client = await _get_redis()
    if client is None:
        return False
    try:
        raw = await client.get(_KEY.format(user_id=user_id))
        if raw is None:
            return False
        cutoff = int(raw)
        iat = int(issued_at.replace(tzinfo=issued_at.tzinfo or timezone.utc).timestamp())
        return iat < cutoff
    except Exception as e:  # noqa: BLE001 - fail open
        logger.warning("CLI revocation check failed for user %s: %s", user_id, e)
        _reset_client()
        return False
