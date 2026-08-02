"""Contract tests for atomic submission acceptance (P0-C).

The guarantee under test: an ``accepted`` acknowledgment is a claim about
durable state, so the user message, the run row, the run's ``run.created``
event and the outbox dispatch record either all exist or none do, and a
resubmitted idempotency key attaches to the run it already created rather than
producing a second one.

Everything runs against SQLite, which carries the same partial unique indexes
the accept path depends on (``uq_agent_runs_user_idempotency_key``,
``uq_agent_runs_active_thread``, ``uq_agent_outbox_run``) because the models
declare ``sqlite_where`` alongside ``postgresql_where``. True cross-connection
contention needs PostgreSQL; the race is therefore driven deterministically by
suppressing the pre-insert lookup, which is exactly the state a losing racer
sees — its snapshot predates the winner's commit — and lets the real
``IntegrityError`` recovery run.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.agent_outbox import AgentOutbox
from src.models.agent_run import AgentRun
from src.models.agent_run_event import AgentRunEvent
from src.models.chat_message import ChatMessage, MessageRole
from src.models.thread import Thread
from src.services.agent import agent_submission_service as submission_mod
from src.services.agent.agent_submission_service import (
    accept_submission,
    stream_idempotency_key,
)
from src.services.agent.run_event_types import RunEventType
from src.shared.enums import AgentOutboxStatus, JobStatus

pytestmark = pytest.mark.unit

ORG_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
ORG_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
USER_A = uuid.UUID("33333333-3333-3333-3333-333333333333")
USER_B = uuid.UUID("44444444-4444-4444-4444-444444444444")
THREAD_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
CONVERSATION_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # pysqlite/aiosqlite emit an implicit COMMIT before SAVEPOINT unless driver
    # transaction handling is disabled and BEGIN is emitted by hand (SQLAlchemy's
    # documented sqlite caveat). Without this the savepoint-scoped inserts would
    # silently commit the accept transaction and the rollback assertions below
    # would test nothing.
    @event.listens_for(engine.sync_engine, "connect")
    def _disable_driver_transactions(dbapi_connection: Any, _record: Any) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(engine.sync_engine, "begin")
    def _emit_begin(connection: Any) -> None:
        connection.exec_driver_sql("BEGIN")

    async with engine.begin() as conn:
        await conn.run_sync(Thread.__table__.create)
        await conn.run_sync(ChatMessage.__table__.create)
        await conn.run_sync(AgentRun.__table__.create)
        await conn.run_sync(AgentRunEvent.__table__.create)
        await conn.run_sync(AgentOutbox.__table__.create)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def db(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        session.add(
            Thread(
                id=THREAD_ID,
                conversation_id=CONVERSATION_ID,
                title="t",
                created_by_id=USER_A,
                message_count=0,
            )
        )
        await session.commit()
        yield session


def _user(user_id: uuid.UUID = USER_A, org: uuid.UUID | None = ORG_A) -> Any:
    return SimpleNamespace(id=user_id, organization_id=org)


def _request(cmid: uuid.UUID | None, content: str = "hello") -> Any:
    return SimpleNamespace(
        messages=[
            SimpleNamespace(role="user", content=content, client_message_id=cmid)
        ],
        model="",
        use_rag=True,
        thread_id=str(THREAD_ID),
    )


def _thread() -> Any:
    return SimpleNamespace(id=THREAD_ID, conversation_id=CONVERSATION_ID)


async def _count(db: AsyncSession, model: Any) -> int:
    return int((await db.execute(select(func.count()).select_from(model))).scalar_one())


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


async def test_idempotent_retry_returns_existing_run(db: AsyncSession) -> None:
    """Same key + same user twice: one run, one user row, one outbox row."""
    cmid = uuid.uuid4()
    user = _user()

    first = await accept_submission(
        db, current_user=user, request=_request(cmid), thread=_thread()
    )
    second = await accept_submission(
        db, current_user=user, request=_request(cmid), thread=_thread()
    )

    assert second.run_id == first.run_id, (
        "a resubmitted idempotency key must attach to the run it already "
        "created, not start a second one"
    )
    assert second.replayed is True
    assert first.replayed is False
    assert second.outbox_id == first.outbox_id
    assert await _count(db, AgentRun) == 1
    assert await _count(db, ChatMessage) == 1
    assert await _count(db, AgentOutbox) == 1


async def test_idempotency_race_attaches_to_the_winner(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The IntegrityError path: the loser re-reads the winner, never duplicates.

    A racing submission's pre-insert lookup runs against a snapshot that does
    not yet contain the winner's row, so it proceeds to INSERT and loses on
    ``uq_agent_runs_user_idempotency_key``. Suppressing the lookup reproduces
    exactly that state deterministically.
    """
    cmid = uuid.uuid4()
    user = _user()
    winner = await accept_submission(
        db, current_user=user, request=_request(cmid), thread=_thread()
    )

    calls = {"n": 0}
    real_lookup = submission_mod._find_by_idempotency_key

    async def blind_first_lookup(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:  # the pre-insert probe: winner not yet visible
            return None
        return await real_lookup(*args, **kwargs)

    monkeypatch.setattr(submission_mod, "_find_by_idempotency_key", blind_first_lookup)

    loser = await accept_submission(
        db, current_user=user, request=_request(cmid), thread=_thread()
    )

    assert calls["n"] == 2, "the recovery must re-read after the IntegrityError"
    assert loser.run_id == winner.run_id
    assert loser.replayed is True
    assert await _count(db, AgentRun) == 1
    assert await _count(db, ChatMessage) == 1
    assert await _count(db, AgentOutbox) == 1


async def test_idempotency_key_is_scoped_per_user(db: AsyncSession) -> None:
    """Two users sending the same client id get two runs, never one shared."""
    cmid = uuid.uuid4()
    key_a = stream_idempotency_key(_request(cmid), _user(USER_A))
    key_b = stream_idempotency_key(_request(cmid), _user(USER_B, ORG_B))
    assert key_a is not None and key_b is not None and key_a != key_b


def test_no_client_message_id_means_no_idempotency_key() -> None:
    """Legacy clients dispatch unconditionally, exactly as before."""
    assert stream_idempotency_key(_request(None), _user()) is None


# ---------------------------------------------------------------------------
# What the transaction actually writes
# ---------------------------------------------------------------------------


async def test_accept_writes_all_four_rows_atomically(db: AsyncSession) -> None:
    cmid = uuid.uuid4()
    accepted = await accept_submission(
        db, current_user=_user(), request=_request(cmid), thread=_thread()
    )

    run = await db.get(AgentRun, accepted.run_id)
    assert run is not None
    assert run.status == JobStatus.QUEUED.value
    assert run.thread_id == THREAD_ID
    assert run.organization_id == ORG_A
    assert run.user_id == USER_A
    assert str(run.user_message_id) == accepted.user_message_id

    message = await db.get(ChatMessage, uuid.UUID(str(accepted.user_message_id)))
    assert message is not None
    assert message.role == MessageRole.USER
    assert message.content == "hello"

    events = (
        (
            await db.execute(
                select(AgentRunEvent).where(AgentRunEvent.run_id == accepted.run_id)
            )
        )
        .scalars()
        .all()
    )
    assert [(e.seq, e.event_type) for e in events] == [
        (1, RunEventType.RUN_CREATED.value)
    ], "run.created is seq 1 of a new run's ledger"
    assert events[0].organization_id == ORG_A

    outbox = await db.get(AgentOutbox, uuid.UUID(str(accepted.outbox_id)))
    assert outbox is not None
    assert outbox.run_id == accepted.run_id
    assert outbox.status == AgentOutboxStatus.PENDING.value
    assert outbox.organization_id == ORG_A
    assert outbox.dispatched_at is None

    thread = await db.get(Thread, THREAD_ID)
    assert thread is not None and thread.message_count == 1


async def test_org_less_user_is_not_stringified(db: AsyncSession) -> None:
    """``str(None) == "None"`` has merged tenants here before — never again."""
    accepted = await accept_submission(
        db,
        current_user=_user(org=None),
        request=_request(uuid.uuid4()),
        thread=_thread(),
    )
    run = await db.get(AgentRun, accepted.run_id)
    outbox = await db.get(AgentOutbox, uuid.UUID(str(accepted.outbox_id)))
    event_row = (
        await db.execute(
            select(AgentRunEvent).where(AgentRunEvent.run_id == accepted.run_id)
        )
    ).scalar_one()
    assert run is not None and run.organization_id is None
    assert outbox is not None and outbox.organization_id is None
    assert event_row.organization_id is None


async def test_second_turn_supersedes_the_threads_active_run(
    db: AsyncSession,
) -> None:
    """``uq_agent_runs_active_thread`` permits one live run per thread.

    Without superseding, the second turn of every conversation would be
    rejected by the index and the client would get an error instead of an
    acknowledgment.
    """
    first = await accept_submission(
        db, current_user=_user(), request=_request(uuid.uuid4()), thread=_thread()
    )
    second = await accept_submission(
        db, current_user=_user(), request=_request(uuid.uuid4()), thread=_thread()
    )

    assert second.run_id != first.run_id
    old = await db.get(AgentRun, first.run_id)
    assert old is not None
    assert old.status == JobStatus.CANCELLED.value
    assert old.error_code == "superseded"

    closing = (
        (
            await db.execute(
                select(AgentRunEvent)
                .where(AgentRunEvent.run_id == first.run_id)
                .order_by(AgentRunEvent.seq)
            )
        )
        .scalars()
        .all()
    )
    assert [e.event_type for e in closing] == [
        RunEventType.RUN_CREATED.value,
        RunEventType.RUN_CANCELLED.value,
    ]


async def test_a_failed_write_leaves_nothing_behind(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Service-level mirror of the stream fault-injection suite."""

    async def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("outbox write failed")

    monkeypatch.setattr(submission_mod, "_insert_outbox", boom)

    with pytest.raises(RuntimeError):
        await accept_submission(
            db, current_user=_user(), request=_request(uuid.uuid4()), thread=_thread()
        )

    assert await _count(db, AgentRun) == 0
    assert await _count(db, ChatMessage) == 0
    assert await _count(db, AgentRunEvent) == 0
    assert await _count(db, AgentOutbox) == 0
