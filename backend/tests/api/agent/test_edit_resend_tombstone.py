"""Durable edit-and-resend: tombstone semantics against a real Postgres.

PR #1313 shipped edit-and-resend as a frontend truncation only — the old answer
and every later turn stayed in ``chat_messages`` and in the LangGraph
checkpoint, so a reload showed a contradictory transcript and the model could
still see the prompt the user had replaced.

Here the server does it durably: editing U1 in a U1/A1/U2/A2 thread tombstones
all four rows by pointing ``superseded_by_message_id`` at the NEW user row, in
the same transaction that persists it. Every display / model-context / export
read then excludes them; by-id and analytics reads deliberately do not.

Postgres-only: the ON CONFLICT insert infers a partial unique index, and the
tombstone UPDATE uses ``(created_at, id)`` tuple ordering.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.api.agent.execute import AgentExecuteRequest, AgentMessage
from src.models.chat_message import ChatMessage, MessageRole
from src.services.agent.agent_execution_service import (
    TombstoneReport,
    _persist_assistant_message,
    _persist_user_message,
    build_thread_seed_messages,
    resync_thread_checkpoint,
)

pytestmark = pytest.mark.integration

SERVICE_LOGGER = "src.services.agent.agent_execution_service"


def _req(
    thread_id: Any, content: str, cmid: Any, *, supersedes: Any = None
) -> AgentExecuteRequest:
    kwargs: dict[str, Any] = {}
    if supersedes is not None:
        kwargs["supersedes_client_message_id"] = str(supersedes)
    return AgentExecuteRequest(
        messages=[
            AgentMessage(role="user", content=content, client_message_id=str(cmid))
        ],
        thread_id=str(thread_id),
        **kwargs,
    )


async def _track(db_session: Any, thread_id: Any) -> None:
    ids = (
        (
            await db_session.execute(
                select(ChatMessage.id).where(ChatMessage.thread_id == thread_id)
            )
        )
        .scalars()
        .all()
    )
    db_session.info["_created"]["chat_messages"].extend(ids)


async def _build_thread(
    db_session: Any, user_factory: Any, thread_factory: Any
) -> tuple:
    """U1, A1, U2, A2 — the shape an edit of U1 has to sweep."""
    user = await user_factory()
    thread = await thread_factory(user=user)
    u1_cmid, u2_cmid = uuid4(), uuid4()

    await _persist_user_message(db_session, user, _req(thread.id, "first q", u1_cmid))
    await _persist_assistant_message(
        db_session,
        thread_id=str(thread.id),
        content="first a",
        model_name="gpt-5-mini",
        tool_executions_out=None,
    )
    await _persist_user_message(db_session, user, _req(thread.id, "second q", u2_cmid))
    await _persist_assistant_message(
        db_session,
        thread_id=str(thread.id),
        content="second a",
        model_name="gpt-5-mini",
        tool_executions_out=None,
    )
    return user, thread, u1_cmid, u2_cmid


async def _rows(db_session: Any, thread_id: Any) -> list[Any]:
    """Raw column tuples, deliberately not ORM entities.

    The app's sessions use ``expire_on_commit=False``, so an entity this
    session hydrated BEFORE the tombstone UPDATE comes back from the identity
    map with a stale ``superseded_by_message_id``. Real readers run in a fresh
    session; column tuples bypass the identity map entirely and always show
    what is actually on disk.
    """
    result = await db_session.execute(
        select(
            ChatMessage.id,
            ChatMessage.role,
            ChatMessage.content,
            ChatMessage.client_message_id,
            ChatMessage.superseded_by_message_id,
        )
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    return list(result.all())


# --------------------------------------------------------------------------- #
# 1. Core semantics
# --------------------------------------------------------------------------- #


async def test_editing_the_first_turn_tombstones_the_whole_tail(
    db_session: Any, thread_factory: Any, user_factory: Any
) -> None:
    user, thread, u1_cmid, _u2 = await _build_thread(
        db_session, user_factory, thread_factory
    )

    tombstoned = TombstoneReport()
    new_cmid = uuid4()  # FRESH: reusing u1_cmid would be dropped by ON CONFLICT
    inserted = await _persist_user_message(
        db_session,
        user,
        _req(thread.id, "first q, edited", new_cmid, supersedes=u1_cmid),
        tombstoned_out=tombstoned,
    )
    await _track(db_session, thread.id)

    assert inserted is True
    rows = await _rows(db_session, thread.id)
    assert len(rows) == 5

    replacement = next(r for r in rows if r.client_message_id == new_cmid)
    superseded = [r for r in rows if r.id != replacement.id]
    assert len(superseded) == 4  # U1, A1, U2, A2
    assert {r.superseded_by_message_id for r in superseded} == {replacement.id}
    # The replacement itself is NOT tombstoned by its own sweep.
    assert replacement.superseded_by_message_id is None

    # Count contract, not ids: checkpoint convergence rewrites the whole head
    # from the DB (``resync_thread_checkpoint``), so no per-row id mapping is
    # produced or needed.
    assert tombstoned.count == 4
    assert tombstoned.any is True


async def test_superseded_turns_vanish_from_every_reader(
    db_session: Any, thread_factory: Any, user_factory: Any
) -> None:
    from src.api.agent.execute import get_thread_messages
    from src.services.threads import message_service, workspace_access

    user, thread, u1_cmid, _u2 = await _build_thread(
        db_session, user_factory, thread_factory
    )
    before = await _rows(db_session, thread.id)

    new_cmid = uuid4()
    await _persist_user_message(
        db_session,
        user,
        _req(thread.id, "edited", new_cmid, supersedes=u1_cmid),
    )
    await _track(db_session, thread.id)

    # /agent/threads/{id}/messages — full history AND the windowed page, whose
    # count must agree with the page (a drifted count invents has_more pages).
    full = await get_thread_messages(
        thread_id=thread.id, limit=None, before=None, current_user=user, db=db_session
    )
    assert [m.content for m in full.messages] == ["edited"]
    assert full.total == 1

    window = await get_thread_messages(
        thread_id=thread.id, limit=50, before=None, current_user=user, db=db_session
    )
    assert len(window.messages) == 1
    assert window.total == len(window.messages)  # no drift
    assert window.has_more is False

    # message_service.list_messages (page + total share base_conditions)
    listed = await message_service.list_messages(db_session, thread.id, user.id)
    assert listed is not None
    messages, total, has_more = listed
    assert [m.content for m in messages] == ["edited"]
    assert total == len(messages)
    assert has_more is False

    # Model-visible reseed
    seed = await build_thread_seed_messages(db_session, str(thread.id))
    assert [m.content for m in seed] == ["edited"]

    # by-id fetch STILL resolves a tombstoned row (feedback / re-edit).
    old_user_row_id = next(r.id for r in before if r.client_message_id == u1_cmid)
    fetched = await workspace_access.get_message(db_session, old_user_row_id, user.id)
    assert fetched is not None
    assert fetched.id == old_user_row_id
    # ...and it really is tombstoned (read off disk, not off the identity map).
    assert (
        await db_session.scalar(
            select(ChatMessage.superseded_by_message_id).where(
                ChatMessage.id == old_user_row_id
            )
        )
    ) is not None


async def test_workspace_stats_still_counts_superseded_turns(
    db_session: Any, thread_factory: Any, user_factory: Any
) -> None:
    """Analytics keeps them: an edit hides a turn, it does not un-send it."""
    from src.services.threads.chat_service import ChatService

    user, thread, u1_cmid, _u2 = await _build_thread(
        db_session, user_factory, thread_factory
    )
    conversation_id = thread.conversation_id

    await _persist_user_message(
        db_session, user, _req(thread.id, "edited", uuid4(), supersedes=u1_cmid)
    )
    await _track(db_session, thread.id)

    total_rows = await db_session.scalar(
        select(func.count(ChatMessage.id)).where(ChatMessage.thread_id == thread.id)
    )
    assert total_rows == 5  # nothing deleted

    from src.models.conversation import Conversation

    conversation = await db_session.get(Conversation, conversation_id)
    stats = await ChatService(db_session).get_workspace_stats(
        conversation.workspace_id, user.id
    )
    assert stats is not None
    assert stats["message_count"] == 5


async def test_export_excludes_superseded_turns(
    db_session: Any, thread_factory: Any, user_factory: Any
) -> None:
    from src.services.research.export_service import ExportOptions, ExportService

    user, thread, u1_cmid, _u2 = await _build_thread(
        db_session, user_factory, thread_factory
    )
    await _persist_user_message(
        db_session, user, _req(thread.id, "edited", uuid4(), supersedes=u1_cmid)
    )
    await _track(db_session, thread.id)

    thread_id, user_id = str(thread.id), str(user.id)
    # Detach everything first: ``_load_thread`` selectinloads Thread.messages,
    # but a Thread already in this session's identity map keeps its unloaded
    # relationship and lazy-loads it instead (MissingGreenlet under asyncio).
    # A real export request runs in a fresh session; this reproduces that.
    db_session.expunge_all()

    exported = await ExportService(db_session)._load_thread(
        thread_id,
        user_id,
        # include_attachments=False sidesteps a PRE-EXISTING latent bug in
        # _load_thread: it selectinloads messages->citations but not
        # ->attachments, so `msg.has_attachments` lazy-loads and raises
        # MissingGreenlet under the async session. Out of scope here; noted so
        # it is not mistaken for tombstone fallout.
        ExportOptions(include_attachments=False),
    )
    assert exported is not None
    assert [m.content for m in exported.messages] == ["edited"]


# --------------------------------------------------------------------------- #
# 2. Not-found cmid (the fast-path persist race)
# --------------------------------------------------------------------------- #


async def test_unknown_supersedes_cmid_warns_and_still_persists_the_turn(
    db_session: Any,
    thread_factory: Any,
    user_factory: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The original turn's persist may still be in flight (fast_path.py runs it
    as a background task), so the target row can legitimately be missing. The
    turn must proceed; only the tombstone is lost."""
    user, thread, _u1, _u2 = await _build_thread(
        db_session, user_factory, thread_factory
    )
    caplog.set_level(logging.WARNING, logger=SERVICE_LOGGER)

    tombstoned = TombstoneReport()
    stale = uuid4()  # never persisted in this thread
    inserted = await _persist_user_message(
        db_session,
        user,
        _req(thread.id, "edited", uuid4(), supersedes=stale),
        tombstoned_out=tombstoned,
    )
    await _track(db_session, thread.id)

    assert inserted is True  # turn NOT failed
    assert tombstoned.count == 0
    assert tombstoned.any is False
    rows = await _rows(db_session, thread.id)
    assert len(rows) == 5
    assert all(r.superseded_by_message_id is None for r in rows)

    warns = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and "edit_resend_supersede_target_not_found" in r.getMessage()
    ]
    assert len(warns) == 1
    assert warns[0].supersedes_client_message_id == str(stale)


async def test_supersede_target_in_another_thread_is_not_tombstoned(
    db_session: Any, thread_factory: Any, user_factory: Any
) -> None:
    """The lookup is thread-scoped: a cmid from a different thread is a miss,
    never a cross-thread tombstone."""
    user_a, thread_a, a_cmid, _ = await _build_thread(
        db_session, user_factory, thread_factory
    )
    user_b, thread_b, _b_cmid, _ = await _build_thread(
        db_session, user_factory, thread_factory
    )

    tombstoned = TombstoneReport()
    await _persist_user_message(
        db_session,
        user_b,
        _req(thread_b.id, "edited", uuid4(), supersedes=a_cmid),
        tombstoned_out=tombstoned,
    )
    await _track(db_session, thread_a.id)
    await _track(db_session, thread_b.id)

    assert tombstoned.any is False
    assert all(
        r.superseded_by_message_id is None for r in await _rows(db_session, thread_a.id)
    )


# --------------------------------------------------------------------------- #
# 3. Idempotency
# --------------------------------------------------------------------------- #


async def test_resending_the_same_edit_is_idempotent(
    db_session: Any, thread_factory: Any, user_factory: Any
) -> None:
    user, thread, u1_cmid, _u2 = await _build_thread(
        db_session, user_factory, thread_factory
    )
    new_cmid = uuid4()
    request = _req(thread.id, "edited", new_cmid, supersedes=u1_cmid)

    first = TombstoneReport()
    second = TombstoneReport()
    assert (
        await _persist_user_message(db_session, user, request, tombstoned_out=first)
        is True
    )
    assert (
        await _persist_user_message(db_session, user, request, tombstoned_out=second)
        is False
    )  # ON CONFLICT dedup
    await _track(db_session, thread.id)

    rows = await _rows(db_session, thread.id)
    assert len(rows) == 5  # no duplicate user row
    assert first.count == 4
    assert first.any is True
    # Already tombstoned on the first pass, so the UPDATE finds nothing...
    assert second.count == 0
    # ...but ``any`` must still be True: this is the ambiguous-commit shape (a
    # first attempt that committed and lost its response), and the retry has to
    # re-run the checkpoint resync or the model keeps the edited-away turn.
    assert second.any is True


async def test_dedup_onto_the_supersede_target_is_refused(
    db_session: Any,
    thread_factory: Any,
    user_factory: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The replacement cmid IS the superseded turn's cmid.

    The schema validator rejects this at the edge (422), so reaching the
    persist means something bypassed it. If we let the dedup path proceed, the
    "replacement" resolves to the very row being edited and the sweep marks its
    own replacement superseded — the turn disappears from every reader. Refuse,
    warn, and leave the thread untouched.
    """
    user, thread, u1_cmid, _u2 = await _build_thread(
        db_session, user_factory, thread_factory
    )
    caplog.set_level(logging.WARNING, logger=SERVICE_LOGGER)

    report = TombstoneReport()
    # Same cmid on both sides. Built with a fresh key and then mutated, because
    # constructing it directly is exactly what the schema validator refuses
    # (see test_agent_request_schema.py) — this asserts the SECOND line of
    # defence, for a request that reached the persist another way.
    request = _req(thread.id, "edited", uuid4(), supersedes=u1_cmid)
    request.messages[0].client_message_id = u1_cmid

    inserted = await _persist_user_message(
        db_session, user, request, tombstoned_out=report
    )
    await _track(db_session, thread.id)

    assert inserted is False  # ON CONFLICT dedup onto the existing U1 row
    assert report.count == 0
    assert report.any is False
    rows = await _rows(db_session, thread.id)
    assert len(rows) == 4  # nothing added
    assert all(r.superseded_by_message_id is None for r in rows)  # nothing swept

    warns = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and "edit_resend_dedup_target_conflict" in r.getMessage()
    ]
    assert len(warns) == 1


async def test_dedup_onto_an_already_superseded_row_is_refused(
    db_session: Any,
    thread_factory: Any,
    user_factory: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A LATER edit already tombstoned the row we would reuse.

    Reusing it as the replacement would rewrite history backwards: rows the
    later edit superseded would be re-pointed at a row that is itself dead.
    """
    user, thread, u1_cmid, u2_cmid = await _build_thread(
        db_session, user_factory, thread_factory
    )

    # Edit U2 -> replacement R1. Then edit U1 with R1's cmid reused.
    r1_cmid = uuid4()
    await _persist_user_message(
        db_session, user, _req(thread.id, "u2 edited", r1_cmid, supersedes=u2_cmid)
    )
    # Now supersede R1 itself with a third turn.
    r2_cmid = uuid4()
    await _persist_user_message(
        db_session,
        user,
        _req(thread.id, "u2 edited again", r2_cmid, supersedes=r1_cmid),
    )
    await _track(db_session, thread.id)
    caplog.set_level(logging.WARNING, logger=SERVICE_LOGGER)

    before = await _rows(db_session, thread.id)
    report = TombstoneReport()
    # Replay the FIRST edit: its cmid (r1_cmid) now names a superseded row.
    inserted = await _persist_user_message(
        db_session,
        user,
        _req(thread.id, "u2 edited", r1_cmid, supersedes=u2_cmid),
        tombstoned_out=report,
    )

    assert inserted is False
    assert report.any is False
    after = await _rows(db_session, thread.id)
    assert len(after) == len(before)
    assert {(r.id, r.superseded_by_message_id) for r in after} == {
        (r.id, r.superseded_by_message_id) for r in before
    }

    warns = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and "edit_resend_dedup_target_conflict" in r.getMessage()
    ]
    assert len(warns) == 1


async def test_dedup_onto_a_replacement_bound_to_another_target_is_refused(
    db_session: Any,
    thread_factory: Any,
    user_factory: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The replacement cmid exists, but it replaced a DIFFERENT turn.

    U2 was edited into R. A later request reuses R's cmid while claiming to
    supersede U1. The insert dedups onto R (still active, so neither existing
    refusal branch fires), and without binding R to the target it replaced the
    guard would wave it through: U1 and A1 get tombstoned on the strength of a
    recycled id, and R's content — which belongs to the U2 edit — is silently
    kept as the "new" question.

    A replacement cmid names exactly one edit. Accept the dedup only when the
    claimed target is already superseded BY this very row.
    """
    user, thread, u1_cmid, u2_cmid = await _build_thread(
        db_session, user_factory, thread_factory
    )

    r_cmid = uuid4()
    first = TombstoneReport()
    assert (
        await _persist_user_message(
            db_session,
            user,
            _req(thread.id, "u2 edited", r_cmid, supersedes=u2_cmid),
            tombstoned_out=first,
        )
        is True
    )
    await _track(db_session, thread.id)
    assert first.count == 2  # U2 + A2
    caplog.set_level(logging.WARNING, logger=SERVICE_LOGGER)

    before = await _rows(db_session, thread.id)
    report = TombstoneReport()
    inserted = await _persist_user_message(
        db_session,
        user,
        # Same replacement cmid, different claimed target.
        _req(thread.id, "u2 edited", r_cmid, supersedes=u1_cmid),
        tombstoned_out=report,
    )

    assert inserted is False  # ON CONFLICT dedup onto R
    assert report.count == 0
    assert report.any is False
    after = await _rows(db_session, thread.id)
    assert {(r.id, r.superseded_by_message_id) for r in after} == {
        (r.id, r.superseded_by_message_id) for r in before
    }
    # U1 (the falsely-claimed target) is still a live turn.
    u1 = next(r for r in after if str(r.client_message_id) == str(u1_cmid))
    assert u1.superseded_by_message_id is None

    warns = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and "edit_resend_dedup_target_mismatch" in r.getMessage()
    ]
    assert len(warns) == 1


async def test_dedup_reporting_a_genuine_prior_edit_still_marks(
    db_session: Any,
    thread_factory: Any,
    user_factory: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The idempotent case the mismatch guard must not break.

    Same replacement cmid AND the same target it actually replaced: this is the
    ambiguous-commit resend, so the report still has to say "tombstones exist"
    or the retry skips the checkpoint resync.
    """
    user, thread, u1_cmid, _u2 = await _build_thread(
        db_session, user_factory, thread_factory
    )
    r_cmid = uuid4()
    request = _req(thread.id, "edited", r_cmid, supersedes=u1_cmid)

    first = TombstoneReport()
    await _persist_user_message(db_session, user, request, tombstoned_out=first)
    await _track(db_session, thread.id)
    caplog.set_level(logging.WARNING, logger=SERVICE_LOGGER)

    second = TombstoneReport()
    assert (
        await _persist_user_message(db_session, user, request, tombstoned_out=second)
        is False
    )

    assert first.count == 4
    assert second.count == 0
    assert second.any is True
    assert not [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and "edit_resend_dedup_target_mismatch" in r.getMessage()
    ]


async def test_message_count_is_decremented_by_the_tombstoned_rows(
    db_session: Any, thread_factory: Any, user_factory: Any
) -> None:
    """Net delta: +1 for the replacement, -N for what it superseded."""
    from src.models.thread import Thread as ThreadModel

    user, thread, u1_cmid, _u2 = await _build_thread(
        db_session, user_factory, thread_factory
    )
    before = await db_session.scalar(
        select(ThreadModel.message_count).where(ThreadModel.id == thread.id)
    )
    assert before == 4  # U1, A1, U2, A2

    report = TombstoneReport()
    await _persist_user_message(
        db_session,
        user,
        _req(thread.id, "edited", uuid4(), supersedes=u1_cmid),
        tombstoned_out=report,
    )
    await _track(db_session, thread.id)

    after = await db_session.scalar(
        select(ThreadModel.message_count).where(ThreadModel.id == thread.id)
    )
    assert report.count == 4
    assert after == before + 1 - report.count == 1
    # ...and it matches what the readers actually render.
    visible = await db_session.scalar(
        select(func.count(ChatMessage.id)).where(
            ChatMessage.thread_id == thread.id,
            ChatMessage.superseded_by_message_id.is_(None),
        )
    )
    assert after == visible


async def test_message_count_never_goes_negative(
    db_session: Any, thread_factory: Any, user_factory: Any
) -> None:
    """message_count is a denormalised counter that historically drifts."""
    from src.models.thread import Thread as ThreadModel

    user, thread, u1_cmid, _u2 = await _build_thread(
        db_session, user_factory, thread_factory
    )
    # Drift the counter through the ORM, not a bulk UPDATE: sessions here use
    # ``expire_on_commit=False``, so a bulk UPDATE would leave the identity-map
    # copy _persist_user_message reads at its old value and the test would
    # assert nothing.
    drifted = await db_session.get(ThreadModel, thread.id)
    drifted.message_count = 0
    await db_session.commit()

    await _persist_user_message(
        db_session, user, _req(thread.id, "edited", uuid4(), supersedes=u1_cmid)
    )
    await _track(db_session, thread.id)

    after = await db_session.scalar(
        select(ThreadModel.message_count).where(ThreadModel.id == thread.id)
    )
    assert after == 0  # floored, not -3


# --------------------------------------------------------------------------- #
# 4. Checkpoint convergence against the real seed builder
# --------------------------------------------------------------------------- #


class _RecordingGraph:
    """Head state seeded with MODEL-generated assistant ids."""

    def __init__(self, messages: Sequence[Any]) -> None:
        self._messages = list(messages)
        self.updates: list = []

    async def aget_state(self, config: Any) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(values={"messages": list(self._messages)})

    async def aupdate_state(
        self, config: Any, values: Any, as_node: Any = None
    ) -> None:
        from langgraph.graph.message import add_messages

        self._messages = add_messages(self._messages, values["messages"])
        self.updates.append((config, values, as_node))


async def test_resync_converges_head_on_the_post_edit_db(
    db_session: Any,
    thread_factory: Any,
    user_factory: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The P0 this design exists for: assistant ids the model invented.

    A per-id RemoveMessage mapping could never name ``run-…``, so the
    superseded ANSWER survived. Removing what IS present does.
    """
    from langchain_core.messages import AIMessage, HumanMessage

    from src.services.agent import agent_execution_service as aes_module

    user, thread, u1_cmid, u2_cmid = await _build_thread(
        db_session, user_factory, thread_factory
    )

    # Checkpoint as LangGraph would really have it: human ids are the client
    # keys, assistant ids are model-generated and unrelated to any row.
    head = [
        HumanMessage(content="first q", id=str(u1_cmid)),
        AIMessage(content="first a", id="model-gen-123"),
        HumanMessage(content="second q", id=str(u2_cmid)),
        AIMessage(content="second a", id="model-gen-456"),
    ]
    graph = _RecordingGraph(head)

    # ``resync_thread_checkpoint`` opens its OWN session (it runs after the
    # request's transaction has committed). Point that factory at this test's
    # engine; the default one targets the app DSN, which is not this DB.
    class _TestSession:
        async def __aenter__(self) -> Any:
            return db_session

        async def __aexit__(self, *a: Any) -> bool:
            return False

    monkeypatch.setattr(aes_module, "AsyncSessionLocal", lambda: _TestSession())

    new_cmid = uuid4()
    report = TombstoneReport()
    await _persist_user_message(
        db_session,
        user,
        _req(thread.id, "first q, edited", new_cmid, supersedes=u1_cmid),
        tombstoned_out=report,
    )
    await _track(db_session, thread.id)
    assert report.any is True

    assert await resync_thread_checkpoint(graph, thread_id=str(thread.id), user=user)

    # Exactly the non-superseded seed set, nothing else.
    expected = await build_thread_seed_messages(db_session, str(thread.id))
    assert [(m.content, m.id) for m in expected] == [("first q, edited", str(new_cmid))]
    assert [(type(m).__name__, m.content, m.id) for m in graph._messages] == [
        ("HumanMessage", "first q, edited", str(new_cmid))
    ]
    # The model-generated assistant id is GONE — the whole point.
    assert not any(m.id.startswith("model-gen") for m in graph._messages)
    assert len(graph.updates) == 1
    assert graph.updates[0][2] == "memory_save_node"
