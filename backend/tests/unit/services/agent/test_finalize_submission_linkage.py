"""finalize_submission must project payload['assistant_message_id'] onto the
AgentRun row — the column exists, is FK'd, and was never written by any code
path (audit 2026-08-07, gap 3)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import DBAPIError

from src.services.agent.agent_submission_service import finalize_submission
from src.services.agent.run_event_types import RunEventType
from src.shared.enums import JobStatus


def _spy_db() -> SimpleNamespace:
    db = SimpleNamespace(
        execute=AsyncMock(),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    return db


def _update_values(db: SimpleNamespace) -> dict[str, object]:
    stmt = db.execute.await_args_list[0].args[0]
    # stmt._values holds unresolved BindParameter objects on this SQLAlchemy
    # version (not literal values) — compile to get the resolved params.
    return dict(stmt.compile().params)


async def test_finalize_writes_assistant_message_id_from_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.services.agent.agent_submission_service as svc

    monkeypatch.setattr(svc, "append_event", AsyncMock())
    db = _spy_db()
    message_id = str(uuid.uuid4())

    await finalize_submission(
        db,
        run_id=str(uuid.uuid4()),
        status=JobStatus.CANCELLED,
        organization_id=str(uuid.uuid4()),
        event_type=RunEventType.RUN_CANCELLED,
        payload={"reason": "client_disconnected", "assistant_message_id": message_id},
    )

    values = _update_values(db)
    assert str(values.get("assistant_message_id")) == message_id


async def test_finalize_skips_non_uuid_assistant_message_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.services.agent.agent_submission_service as svc

    monkeypatch.setattr(svc, "append_event", AsyncMock())
    db = _spy_db()

    await finalize_submission(
        db,
        run_id=str(uuid.uuid4()),
        status=JobStatus.CANCELLED,
        organization_id=str(uuid.uuid4()),
        event_type=RunEventType.RUN_CANCELLED,
        payload={"reason": "x", "assistant_message_id": "not-a-uuid"},
    )

    assert "assistant_message_id" not in _update_values(db)


async def test_finalize_without_payload_leaves_column_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.services.agent.agent_submission_service as svc

    monkeypatch.setattr(svc, "append_event", AsyncMock())
    db = _spy_db()

    await finalize_submission(
        db,
        run_id=str(uuid.uuid4()),
        status=JobStatus.COMPLETED,
        organization_id=str(uuid.uuid4()),
        event_type=RunEventType.RUN_COMPLETED,
        payload={},
    )

    assert "assistant_message_id" not in _update_values(db)


async def test_terminal_finalize_failure_propagates_after_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.services.agent.agent_submission_service as svc

    monkeypatch.setattr(svc, "append_event", AsyncMock())
    db = _spy_db()
    db.commit.side_effect = RuntimeError("db unavailable")

    with pytest.raises(RuntimeError, match="db unavailable"):
        await finalize_submission(
            db,
            run_id=str(uuid.uuid4()),
            status=JobStatus.COMPLETED,
            organization_id=str(uuid.uuid4()),
            event_type=RunEventType.RUN_COMPLETED,
            payload={},
        )

    db.rollback.assert_awaited_once()


# ---------------------------------------------------------------------------
# lost-connection retry — Sentry JAVASCRIPT-NEXTJS-4W
# ---------------------------------------------------------------------------


def _lost_connection_error() -> DBAPIError:
    """A DBAPIError shaped like a pooler-dropped connection."""
    exc = DBAPIError("UPDATE agent_runs", {}, Exception("connection was closed"))
    exc.connection_invalidated = True
    return exc


async def test_finalize_retries_once_when_the_connection_is_lost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dropped connection must not fail a turn that already produced its answer.

    finalize_submission runs after the last token is streamed but before the
    ``done`` frame. If it raises, the run never reaches a terminal status and
    ``uq_agent_runs_active_thread`` rejects the user's *next* turn until the
    sweeper marks this successful turn failed.
    """
    import src.services.agent.agent_submission_service as svc

    monkeypatch.setattr(svc, "append_event", AsyncMock())
    db = _spy_db()
    db.execute = AsyncMock(side_effect=[_lost_connection_error(), None])

    await finalize_submission(
        db,
        run_id=str(uuid.uuid4()),
        status=JobStatus.COMPLETED,
        organization_id=str(uuid.uuid4()),
        event_type=RunEventType.RUN_COMPLETED,
    )

    assert db.execute.await_count == 2, "expected exactly one retry"
    db.rollback.assert_awaited_once()  # dead connection released before retry
    db.commit.assert_awaited_once()  # the run still reached terminal status


async def test_finalize_raises_when_the_retry_also_loses_the_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two consecutive disconnects mean the database is genuinely unreachable.

    The terminal failure must still propagate: emitting ``done`` while the run
    row is non-terminal would tell the client the turn succeeded and then
    reject its next one.
    """
    import src.services.agent.agent_submission_service as svc

    monkeypatch.setattr(svc, "append_event", AsyncMock())
    db = _spy_db()
    db.execute = AsyncMock(
        side_effect=[_lost_connection_error(), _lost_connection_error()]
    )

    with pytest.raises(DBAPIError):
        await finalize_submission(
            db,
            run_id=str(uuid.uuid4()),
            status=JobStatus.COMPLETED,
            organization_id=str(uuid.uuid4()),
            event_type=RunEventType.RUN_COMPLETED,
        )

    assert db.execute.await_count == 2, "must not retry past the attempt budget"


async def test_finalize_does_not_retry_a_non_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only lost connections are idempotent-safe to replay; real errors are not."""
    import src.services.agent.agent_submission_service as svc

    monkeypatch.setattr(svc, "append_event", AsyncMock())
    db = _spy_db()
    db.execute = AsyncMock(side_effect=ValueError("bad SQL"))

    with pytest.raises(ValueError):
        await finalize_submission(
            db,
            run_id=str(uuid.uuid4()),
            status=JobStatus.COMPLETED,
            organization_id=str(uuid.uuid4()),
            event_type=RunEventType.RUN_COMPLETED,
        )

    assert db.execute.await_count == 1
