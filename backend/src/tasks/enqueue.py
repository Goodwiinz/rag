"""Post-commit Celery enqueue for async SQLAlchemy sessions.

``enqueue_after_commit`` defers a task enqueue until the owning session commits,
closing the worker-reads-before-commit race without reintroducing the orphan-row
problem the raw ``flush -> .delay -> commit`` ordering was built to avoid: the
enqueue fires *after* the row is durable, and is dropped entirely if the session
rolls back.

Mechanics: pending enqueues accumulate on the session (``sync_session.info``),
and a single pair of listeners per session drains them on ``after_commit`` and
discards them on ``after_rollback``. Draining before firing means a raising
``delay`` can't block its siblings and a second commit can't re-fire an
already-fired registration.
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)

# Key under which the per-session list of pending (task, args, kwargs) lives.
_PENDING_KEY = "_enqueue_after_commit_pending"

# Per-session queue of deferred enqueues: (task, positional args, keyword args).
_Pending = list[tuple[Any, tuple[Any, ...], dict[str, Any]]]


def enqueue_after_commit(
    db: AsyncSession, task: Any, *args: Any, **kwargs: Any
) -> None:
    """Register ``task.delay(*args, **kwargs)`` to fire after ``db`` commits.

    Dropped (never fired) if the session rolls back instead. Registrations fire
    in order on the next successful commit; a raising ``delay`` is logged, not
    propagated.
    """
    sync_session = db.sync_session
    pending: _Pending | None = sync_session.info.get(_PENDING_KEY)
    if pending is None:
        pending = []
        sync_session.info[_PENDING_KEY] = pending
        _install_listeners(sync_session)
    pending.append((task, args, kwargs))


def _install_listeners(sync_session: Session) -> None:
    @event.listens_for(sync_session, "after_commit")
    def _fire(session: Session) -> None:
        pending: _Pending | None = session.info.get(_PENDING_KEY)
        if not pending:
            return
        # Drain first: a raising delay must not block siblings, and a later
        # commit must not re-fire these.
        session.info[_PENDING_KEY] = []
        for task, args, kwargs in pending:
            try:
                task.delay(*args, **kwargs)
            except Exception:
                logger.exception("enqueue_after_commit_failed", task=task.name)

    @event.listens_for(sync_session, "after_rollback")
    def _discard(session: Session) -> None:
        session.info[_PENDING_KEY] = []
