"""Per-tool-call database session + acting-user resolution (audit B8).

The LangGraph ``configurable`` dict must carry **scalar identifiers only**
(``user_id`` / ``organization_id`` / ``thread_id`` / ``page_context``) —
never a live ``AsyncSession`` or ORM ``User``. Smuggling the request/job
session through config meant every parallel tool shared one session (unsafe
concurrent use), the ORM user could detach from its closed session
(``MissingGreenlet``), and ~a dozen tools grew ad-hoc ``AsyncSessionLocal()``
blocks purely to dodge the shared session.

Instead, consumers that need database access open a short-lived session via
:func:`tool_session` (the fresh-session pattern DraftGenerationService
already uses) and re-load the acting user with :func:`resolve_tool_user`
(org-scoped, mirroring ``get_current_user``'s ``is_active`` / ``is_deleted``
filters). One session per tool call — parallel tools never share.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.user import User

logger = logging.getLogger(__name__)


@asynccontextmanager
async def tool_session() -> AsyncIterator[AsyncSession]:
    """Yield a fresh, tool-call-scoped ``AsyncSession``.

    Semantics:
    - fresh ``AsyncSessionLocal()`` per call — never the request session, so
      parallel tool calls each own their session (AsyncSession is not safe
      for concurrent use);
    - on exception the open transaction is rolled back before the session is
      returned to the pool (a session mid-aborted-transaction must never be
      pooled);
    - the session is always closed on exit (the ``async with`` of the
      sessionmaker), whether the body committed, raised, or was cancelled.

    Commits are the caller's responsibility — read-only tools simply never
    commit and the close discards the implicit transaction.
    """
    # Lazy import so importing this module never requires a configured
    # database (unit tests patch ``src.core.database.AsyncSessionLocal``).
    from src.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except BaseException:
            # Roll back on error *and* cancellation (tool timeouts cancel the
            # executing coroutine) so the pool never receives a session with
            # an aborted transaction still open.
            try:
                await session.rollback()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                logger.debug("tool_session rollback failed", exc_info=True)
            raise


def _coerce_uuid(value) -> Optional[_uuid.UUID]:
    """Parse *value* into a UUID, or ``None`` when empty/invalid."""
    if value is None:
        return None
    if isinstance(value, _uuid.UUID):
        return value
    try:
        return _uuid.UUID(str(value).strip())
    except (ValueError, TypeError, AttributeError):
        return None


async def resolve_tool_user(
    session: AsyncSession,
    user_id: str,
    organization_id: Optional[str] = None,
) -> Optional[User]:
    """Load the acting :class:`User` for a tool call, org-scoped.

    Mirrors the ``get_current_user`` dependency: only active, non-deleted
    users resolve, and the organization relationship is eager-loaded so the
    returned instance is safe to use after the session ends
    (``expire_on_commit=False``).

    Tenancy guard: when *organization_id* is provided the user row must
    belong to that organization — a mismatch returns ``None`` (fail closed)
    rather than acting across tenants. Invalid/empty ids return ``None``.
    """
    uid = _coerce_uuid(user_id)
    if uid is None:
        return None

    stmt = (
        select(User)
        .options(selectinload(User.organization))
        .where(
            User.id == uid,
            User.is_active == True,  # noqa: E712 - SQLAlchemy comparator
            User.is_deleted == False,  # noqa: E712 - SQLAlchemy comparator
        )
    )
    if organization_id:
        org_uuid = _coerce_uuid(organization_id)
        if org_uuid is None:
            # An org id was asserted but is unparseable — fail closed rather
            # than silently widening the query to all tenants.
            return None
        stmt = stmt.where(User.organization_id == org_uuid)

    result = await session.execute(stmt)
    return result.scalars().first()


__all__ = ["tool_session", "resolve_tool_user"]
