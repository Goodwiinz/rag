"""finalize_submission must project payload['assistant_message_id'] onto the
AgentRun row — the column exists, is FK'd, and was never written by any code
path (audit 2026-08-07, gap 3)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.agent.agent_submission_service import finalize_submission
from src.services.agent.run_event_types import RunEventType
from src.shared.enums import JobStatus


def _spy_db():
    db = SimpleNamespace(
        execute=AsyncMock(),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    return db


def _update_values(db) -> dict:
    stmt = db.execute.await_args_list[0].args[0]
    # stmt._values holds unresolved BindParameter objects on this SQLAlchemy
    # version (not literal values) — compile to get the resolved params.
    return dict(stmt.compile().params)


async def test_finalize_writes_assistant_message_id_from_payload(monkeypatch):
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


async def test_finalize_skips_non_uuid_assistant_message_id(monkeypatch):
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


async def test_finalize_without_payload_leaves_column_untouched(monkeypatch):
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
