"""``accepted`` on ``/stream`` must imply committed state (P0-C).

Before this change the SSE generator emitted ``status/accepted`` as its very
first line, before a single row existed. A crash anywhere after it left the
client holding an acknowledgment for a run the system had no record of — the
repo's dominant "fake-success" shape, at the protocol level.

These tests drive the REAL ``stream_event_generator`` against a SQLite database
carrying the real tables, and fault-inject at every statement boundary inside
the accept transaction. The contract asserted in all cases: no ``accepted``
frame, an ``error`` frame instead, and not one surviving row.

Note on libpq: the generator lazily imports ``psycopg``; this host may have no
libpq, so a stub is installed the same way ``test_agent_stream_accepted_latency``
does (see nous-libpq-test-env).
"""

from __future__ import annotations

import sys
import types
import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models.agent_outbox import AgentOutbox
from src.models.agent_run import AgentRun
from src.models.agent_run_event import AgentRunEvent
from src.models.chat_message import ChatMessage
from src.models.thread import Thread
from src.services.agent.agent_submission_service import AcceptedSubmission
from src.services.agent.stream_buffer import BufferedFrame
from src.shared.enums import AgentOutboxStatus, JobStatus
from tests.utils.agent_stream import frames_of_type, make_stream_request, sse_data


def _install_psycopg_stub() -> None:
    if "psycopg" in sys.modules:
        return
    stub = types.ModuleType("psycopg")
    stub.OperationalError = OSError  # type: ignore[attr-defined]
    sys.modules["psycopg"] = stub


_install_psycopg_stub()

ORG_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
THREAD_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
CONVERSATION_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")

# Every statement boundary inside the accept transaction, plus the commit
# itself. The parametrization is the point: "accepted implies committed" has to
# hold no matter where the transaction dies, not just at a convenient spot.
_BOUNDARIES = ["user_message", "run", "event", "outbox", "commit"]


class _FakeGraph:
    """Minimal graph: one user-visible token, then a clean finish."""

    async def astream_events(
        self, *_args: Any, **_kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        yield {
            "event": "on_chat_model_stream",
            "name": "llm",
            "metadata": {"langgraph_node": "llm_node"},
            "data": {"chunk": SimpleNamespace(content="hi")},
        }

    async def aget_state(self, _config: Any) -> Any:
        return SimpleNamespace(
            values={"messages": [SimpleNamespace(type="ai", content="hi")]},
            tasks=(),
        )

    async def aupdate_state(self, *_args: Any, **_kwargs: Any) -> None:
        return None


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # SQLAlchemy's documented sqlite caveat: without this, SAVEPOINT usage
    # inside the accept transaction implicitly COMMITs it, and the rollback
    # assertions below would pass vacuously.
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

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as setup:
        setup.add(
            Thread(
                id=THREAD_ID,
                conversation_id=CONVERSATION_ID,
                title="t",
                created_by_id=USER_ID,
                message_count=0,
            )
        )
        await setup.commit()
    yield factory
    await engine.dispose()


def _thread_row() -> Any:
    """What ``_resolve_thread`` hands back: an ownership-verified thread."""
    return SimpleNamespace(id=THREAD_ID, conversation_id=CONVERSATION_ID)


async def _drive_stream(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    extra_patches: tuple[Any, ...] = (),
) -> list[str]:
    from src.api.agent import streaming as streaming_mod

    body = make_stream_request(
        messages=[
            {"role": "user", "content": "hello", "client_message_id": str(uuid.uuid4())}
        ],
        thread_id=str(THREAD_ID),
    )
    request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
    current_user = SimpleNamespace(id=USER_ID, organization_id=ORG_ID)

    with (
        patch.object(streaming_mod, "AsyncSessionLocal", session_factory),
        patch.object(
            streaming_mod,
            "_resolve_thread",
            new=AsyncMock(return_value=(_thread_row(), str(CONVERSATION_ID))),
        ),
        patch.object(
            streaming_mod, "_resolve_and_bind_project", new=AsyncMock(return_value=None)
        ),
        patch(
            "src.services.agent.observability.configure_langsmith", return_value=None
        ),
        patch(
            "src.services.agent.checkpointer.get_checkpointer",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.memory.get_memory_store",
            new=AsyncMock(return_value=object()),
        ),
        patch(
            "src.services.agent.graph.compile_agent_graph",
            new=lambda **_kwargs: _FakeGraph(),
        ),
        patch(
            "src.services.agent.agent_execution_service._persist_assistant_message_safe",
            new=AsyncMock(return_value=str(uuid.uuid4())),
        ),
    ):
        with _nested(extra_patches):
            return [
                frame
                async for frame in streaming_mod.stream_event_generator(
                    body,
                    request,
                    current_user,  # type: ignore[arg-type]  # duck-typed User
                )
            ]


class _nested:
    """Apply a tuple of already-built patchers as one context."""

    def __init__(self, patchers: tuple[Any, ...]) -> None:
        self._patchers = patchers

    def __enter__(self) -> None:
        for patcher in self._patchers:
            patcher.start()

    def __exit__(self, *_exc: Any) -> None:
        for patcher in reversed(self._patchers):
            patcher.stop()


def _accepted_frames(frames: list[str]) -> list[dict[str, Any]]:
    return [
        data
        for data in (sse_data(frame) for frame in frames_of_type(frames, "status"))
        if data.get("phase") == "accepted"
    ]


async def _count(db: AsyncSession, model: Any) -> int:
    return int((await db.execute(select(func.count()).select_from(model))).scalar_one())


def _boundary_patcher(boundary: str) -> Any:
    """A patcher that breaks exactly one statement of the accept transaction."""
    from sqlalchemy.ext.asyncio import AsyncSession as _AsyncSession

    async def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError(f"injected failure at {boundary}")

    if boundary == "commit":
        return patch.object(_AsyncSession, "commit", new=boom)
    target = {
        "user_message": "_insert_user_message",
        "run": "_insert_run",
        "event": "append_event",
        "outbox": "_insert_outbox",
    }[boundary]
    return patch(
        f"src.services.agent.agent_submission_service.{target}",
        new=boom,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", _BOUNDARIES)
async def test_stream_accepted_implies_committed(
    session_factory: async_sessionmaker[AsyncSession], boundary: str
) -> None:
    """Break the accept transaction anywhere: no acknowledgment, no rows."""
    frames = await _drive_stream(
        session_factory, extra_patches=(_boundary_patcher(boundary),)
    )

    assert not _accepted_frames(frames), (
        f"an `accepted` frame was emitted although the accept transaction "
        f"failed at the {boundary} boundary — the client would be holding an "
        f"acknowledgment for a run that does not exist"
    )
    assert frames_of_type(
        frames, "error"
    ), f"a failed accept ({boundary}) must surface as an error frame: {frames}"

    async with session_factory() as verify:
        assert await _count(verify, ChatMessage) == 0
        assert await _count(verify, AgentRun) == 0
        assert await _count(verify, AgentRunEvent) == 0
        assert await _count(verify, AgentOutbox) == 0
        thread = await verify.get(Thread, THREAD_ID)
        assert thread is not None and thread.message_count == 0


@pytest.mark.asyncio
async def test_accepted_carries_committed_run_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The run id on the accepted frame must already exist in ``agent_runs``."""
    frames = await _drive_stream(session_factory)

    accepted = _accepted_frames(frames)
    assert len(accepted) == 1, f"expected exactly one accepted frame: {frames}"
    run_id = accepted[0]["run_id"]
    assert run_id, "the accepted frame must carry the committed run id"

    async with session_factory() as verify:
        run = await verify.get(AgentRun, run_id)
        assert run is not None, "accepted named a run that is not in agent_runs"
        assert run.thread_id == THREAD_ID
        assert run.organization_id == ORG_ID

        # The rest of the accept transaction landed with it.
        assert await _count(verify, ChatMessage) == 1
        assert await _count(verify, AgentOutbox) == 1
        outbox = (await verify.execute(select(AgentOutbox))).scalar_one()
        assert outbox.run_id == run_id
        # Dispatch happened in-process right after the commit, so the record is
        # closed out rather than left for a relay that does not exist yet.
        assert outbox.status == AgentOutboxStatus.DISPATCHED.value

        seqs = (
            await verify.execute(
                select(AgentRunEvent.seq, AgentRunEvent.event_type)
                .where(AgentRunEvent.run_id == run_id)
                .order_by(AgentRunEvent.seq)
            )
        ).all()
        assert seqs[0] == (1, "run.created"), "run.created is seq 1"
        assert run.status == JobStatus.COMPLETED.value
        assert [row[1] for row in seqs][-1] == "run.completed"


@pytest.mark.asyncio
async def test_accepted_frame_precedes_every_other_frame(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Moving accept before the acknowledgment must not reorder the stream."""
    frames = await _drive_stream(session_factory)
    first = sse_data(frames[0])
    assert first.get("phase") == "accepted"
    assert first["schema_version"] == "1.0"
    assert first["sequence"] == 1
    assert frames[0].startswith("id: 1\n"), "the resume cursor line must survive"


@pytest.mark.asyncio
async def test_replayed_submission_does_not_dispatch_again(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An idempotent retry attaches to the existing run and stops there."""
    from src.api.agent import streaming as streaming_mod

    replayed = AcceptedSubmission(
        run_id=str(uuid.uuid4()),
        thread_id=str(THREAD_ID),
        user_message_id=str(uuid.uuid4()),
        outbox_id=str(uuid.uuid4()),
        idempotency_key="agent-stream:retry",
        replayed=True,
    )
    classify = Mock(side_effect=AssertionError("replay reached route selection"))
    compile_graph = Mock(side_effect=AssertionError("replay reached LangGraph"))
    buffered = [
        BufferedFrame(
            seq=2,
            frame='id: 2\nevent: token\ndata: {"content": "original"}\n\n',
        ),
        BufferedFrame(
            seq=3,
            frame='id: 3\nevent: done\ndata: {"status": "complete"}\n\n',
        ),
    ]

    frames = await _drive_stream(
        session_factory,
        extra_patches=(
            patch.object(
                streaming_mod,
                "accept_submission",
                new=AsyncMock(return_value=replayed),
            ),
            patch(
                "src.services.agent.fast_path.classify_fast_path_turn",
                new=classify,
            ),
            patch(
                "src.services.agent.graph.compile_agent_graph",
                new=compile_graph,
            ),
            patch.object(
                streaming_mod._stream_buffer,
                "stream_id_for_run",
                new=AsyncMock(return_value="existing-stream"),
                create=True,
            ),
            patch.object(
                streaming_mod._stream_buffer,
                "read_after",
                new=AsyncMock(return_value=buffered),
            ),
        ),
    )

    accepted = _accepted_frames(frames)
    assert len(accepted) == 1
    assert accepted[0]["run_id"] == replayed.run_id
    assert accepted[0]["replayed"] is True
    assert not frames_of_type(frames, "error")
    assert sse_data(frames_of_type(frames, "token")[0])["content"] == "original"
    assert frames_of_type(frames, "done")
    classify.assert_not_called()
    compile_graph.assert_not_called()
