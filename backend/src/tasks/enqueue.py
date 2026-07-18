"""Post-commit Celery enqueue for async SQLAlchemy sessions.

``enqueue_after_commit`` (``.delay``) and ``enqueue_after_commit_apply_async``
(``.apply_async``, for callers that need a queue/options override) defer a task
enqueue until the owning session commits, closing the worker-reads-before-commit
race without reintroducing the orphan-row problem the raw ``flush -> enqueue ->
commit`` ordering was built to avoid: the enqueue fires *after* the row is
durable, and is dropped entirely if the session rolls back.

Mechanics: pending enqueues accumulate on the session (``sync_session.info``) as
zero-arg thunks, and a single pair of listeners per session drains them on
``after_commit`` and discards them on ``after_rollback``. Draining before firing
means a raising enqueue can't block its siblings and a second commit can't
re-fire an already-fired registration.
"""

from __future__ import annotations

from typing import Any, Callable

import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)

# Key under which the per-session list of pending enqueues lives.
_PENDING_KEY = "_enqueue_after_commit_pending"

# Per-session queue of deferred enqueues: (task, thunk). ``task`` is retained
# only so a raising thunk can be logged with the task name.
_Pending = list[tuple[Any, Callable[[], Any]]]


def enqueue_after_commit(
    db: AsyncSession, task: Any, *args: Any, **kwargs: Any
) -> None:
    """Register ``task.delay(*args, **kwargs)`` to fire after ``db`` commits.

    Dropped (never fired) if the session rolls back instead. Registrations fire
    in order on the next successful commit; a raising ``delay`` is logged, not
    propagated.
    """
    _register(db, task, lambda: task.delay(*args, **kwargs))


def enqueue_after_commit_apply_async(
    db: AsyncSession,
    task: Any,
    *,
    args: list[Any] | tuple[Any, ...] | None = None,
    kwargs: dict[str, Any] | None = None,
    **options: Any,
) -> None:
    """Register ``task.apply_async(args, kwargs, **options)`` for after commit.

    The ``.apply_async`` sibling of ``enqueue_after_commit``, for callers that
    need a ``queue=`` (or other apply_async option) override. Same post-commit /
    drop-on-rollback semantics.
    """
    _register(db, task, lambda: task.apply_async(args=args, kwargs=kwargs, **options))


def _register(db: AsyncSession, task: Any, thunk: Callable[[], Any]) -> None:
    sync_session = db.sync_session
    pending: _Pending | None = sync_session.info.get(_PENDING_KEY)
    if pending is None:
        pending = []
        sync_session.info[_PENDING_KEY] = pending
        _install_listeners(sync_session)
    pending.append((task, thunk))


def _install_listeners(sync_session: Session) -> None:
    @event.listens_for(sync_session, "after_commit")
    def _fire(session: Session) -> None:
        pending: _Pending | None = session.info.get(_PENDING_KEY)
        if not pending:
            return
        # Drain first: a raising enqueue must not block siblings, and a later
        # commit must not re-fire these.
        session.info[_PENDING_KEY] = []
        for task, thunk in pending:
            try:
                thunk()
            except Exception:
                logger.exception("enqueue_after_commit_failed", task=task.name)

    @event.listens_for(sync_session, "after_rollback")
    def _discard(session: Session) -> None:
        session.info[_PENDING_KEY] = []
