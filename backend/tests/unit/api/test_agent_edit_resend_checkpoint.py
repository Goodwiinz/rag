"""Checkpoint half of durable edit-and-resend: whole-head resync.

``resync_thread_checkpoint`` converges the LangGraph HEAD checkpoint on the DB's
post-edit view. It does NOT map tombstoned rows to checkpoint ids — that was the
original design and it was broken by construction: an assistant message in the
checkpoint carries an id the MODEL generated (``run-…``), which no row-derived
mapping can predict, so the superseded ANSWER survived while its question was
removed. Instead the head state is read, EVERYTHING present is removed, and the
DB seed (already superseded-filtered) is re-added in one update.

Properties asserted here:

1. Removals cover every id actually present, including model-generated ones.
2. The result is exactly the seed — one ``aupdate_state``, against HEAD, as
   ``memory_save_node``.
3. ``add_messages`` raises on an unknown RemoveMessage id (pinned upstream
   behaviour) — that is the concurrent-writer race, so a ValueError retries
   ONCE from a fresh read and then gives up with a WARN.
4. No failure mode fails the turn.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Optional, Sequence
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage

from src.services.agent import agent_execution_service as aes

pytestmark = pytest.mark.asyncio

SERVICE_LOGGER = aes.logger.name


def _user() -> Any:  # SimpleNamespace stand-in for models.user.User
    return SimpleNamespace(id=uuid4(), organization_id=uuid4())


class _FakeGraph:
    """Minimal graph seam: a head state + a recording/failing aupdate_state."""

    def __init__(
        self,
        messages: Sequence[Any],
        *,
        get_raises: bool = False,
        update_raises: Optional[BaseException] = None,
        raise_times: int = 0,
    ) -> None:
        self._messages = list(messages)
        self.get_raises = get_raises
        self.update_raises = update_raises
        self.raise_times = raise_times
        self.updates: list = []
        self.reads = 0

    async def aget_state(self, config: Any) -> Any:
        self.reads += 1
        if self.get_raises:
            raise RuntimeError("checkpointer down")
        return SimpleNamespace(values={"messages": list(self._messages)})

    async def aupdate_state(
        self, config: Any, values: Any, as_node: Any = None
    ) -> None:
        if self.update_raises is not None and self.raise_times > 0:
            self.raise_times -= 1
            raise self.update_raises
        self.updates.append((config, values, as_node))


def _patch_seed(monkeypatch: pytest.MonkeyPatch, seed: Sequence[Any]) -> None:
    async def _seed(db: Any, thread_id: Any) -> list:
        return list(seed)

    monkeypatch.setattr(aes, "build_thread_seed_messages", _seed)

    class _Session:
        async def __aenter__(self) -> Any:
            return object()

        async def __aexit__(self, *a: Any) -> bool:
            return False

    monkeypatch.setattr(aes, "AsyncSessionLocal", lambda: _Session())


async def test_removes_every_present_id_including_model_generated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bug this design kills: an AI id we could never have derived."""
    head = [
        HumanMessage(content="q1", id="cmid-1"),
        AIMessage(content="a1", id="run-model-generated-123"),
        HumanMessage(content="q2-old", id="cmid-2"),
        AIMessage(content="a2", id="run-model-generated-456"),
    ]
    seed = [
        HumanMessage(content="q1", id="cmid-1"),
        AIMessage(content="a1", id="seed-a1"),
        HumanMessage(content="q2-edited", id="cmid-3"),
    ]
    _patch_seed(monkeypatch, seed)
    graph = _FakeGraph(head)

    assert await aes.resync_thread_checkpoint(graph, thread_id="t-1", user=_user())

    assert len(graph.updates) == 1
    config, values, as_node = graph.updates[0]
    assert as_node == "memory_save_node"
    assert config["configurable"]["thread_id"] == "t-1"
    # No checkpoint_id -> writes against HEAD, never forks the thread.
    assert "checkpoint_id" not in config["configurable"]

    payload = values["messages"]
    removes = [m for m in payload if isinstance(m, RemoveMessage)]
    adds = [m for m in payload if not isinstance(m, RemoveMessage)]
    assert [m.id for m in removes] == [
        "cmid-1",
        "run-model-generated-123",
        "cmid-2",
        "run-model-generated-456",
    ]
    assert adds == seed
    # Removes precede adds: add_messages applies the list in order.
    assert all(isinstance(m, RemoveMessage) for m in payload[: len(removes)])


async def test_result_through_the_real_reducer_is_exactly_the_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end through langgraph's own reducer, not just the payload shape."""
    from langgraph.graph.message import add_messages

    head = [
        HumanMessage(content="q1", id="cmid-1"),
        AIMessage(content="a1", id="run-abc"),
        HumanMessage(content="q2-old", id="cmid-2"),
        AIMessage(content="a2", id="run-def"),
    ]
    seed = [
        HumanMessage(content="q1", id="cmid-1"),
        AIMessage(content="a1", id="seed-a1"),
        HumanMessage(content="q2-edited", id="cmid-3"),
    ]
    _patch_seed(monkeypatch, seed)
    graph = _FakeGraph(head)

    await aes.resync_thread_checkpoint(graph, thread_id="t-2", user=_user())

    merged = add_messages(head, graph.updates[0][1]["messages"])
    assert [(m.content, m.id) for m in merged] == [
        ("q1", "cmid-1"),
        ("a1", "seed-a1"),
        ("q2-edited", "cmid-3"),
    ]


async def test_duplicate_head_ids_are_removed_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two RemoveMessages for one id would be an unknown-id ValueError."""
    head = [HumanMessage(content="q", id="dup"), AIMessage(content="a", id="dup")]
    _patch_seed(monkeypatch, [HumanMessage(content="new", id="fresh")])
    graph = _FakeGraph(head)

    await aes.resync_thread_checkpoint(graph, thread_id="t-3", user=_user())

    removes = [
        m for m in graph.updates[0][1]["messages"] if isinstance(m, RemoveMessage)
    ]
    assert [m.id for m in removes] == ["dup"]


async def test_empty_head_still_seeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Checkpoint lost on restart: converge by seeding, with no removals."""
    _patch_seed(monkeypatch, [HumanMessage(content="new", id="fresh")])
    graph = _FakeGraph([])

    assert await aes.resync_thread_checkpoint(graph, thread_id="t-4", user=_user())
    payload = graph.updates[0][1]["messages"]
    assert not any(isinstance(m, RemoveMessage) for m in payload)
    assert [m.id for m in payload] == ["fresh"]


async def test_nothing_to_do_writes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_seed(monkeypatch, [])
    graph = _FakeGraph([])

    assert (
        await aes.resync_thread_checkpoint(graph, thread_id="t-5", user=_user())
        is False
    )
    assert graph.updates == []


async def test_value_error_retries_once_and_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent writer dropped an id between our read and our write."""
    _patch_seed(monkeypatch, [HumanMessage(content="new", id="fresh")])
    graph = _FakeGraph(
        [HumanMessage(content="q", id="a")],
        update_raises=ValueError("Attempting to delete a message with an ID..."),
        raise_times=1,
    )

    assert await aes.resync_thread_checkpoint(graph, thread_id="t-6", user=_user())
    assert graph.reads == 2  # fresh read on the retry
    assert len(graph.updates) == 1


async def test_value_error_twice_warns_and_gives_up(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _patch_seed(monkeypatch, [HumanMessage(content="new", id="fresh")])
    graph = _FakeGraph(
        [HumanMessage(content="q", id="a")],
        update_raises=ValueError("boom"),
        raise_times=5,
    )
    caplog.set_level(logging.WARNING, logger=SERVICE_LOGGER)

    # The turn is NOT failed.
    assert (
        await aes.resync_thread_checkpoint(graph, thread_id="t-7", user=_user())
        is False
    )
    assert graph.reads == 2
    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warns) == 1
    assert "edit_resend_checkpoint_resync_failed" in warns[0].getMessage()
    assert warns[0].thread_id == "t-7"


async def test_state_read_failure_is_swallowed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _patch_seed(monkeypatch, [HumanMessage(content="new", id="fresh")])
    graph = _FakeGraph([], get_raises=True)
    caplog.set_level(logging.WARNING, logger=SERVICE_LOGGER)

    assert (
        await aes.resync_thread_checkpoint(graph, thread_id="t-8", user=_user())
        is False
    )
    assert graph.updates == []
    assert any(
        "edit_resend_checkpoint_resync_failed" in r.getMessage()
        for r in caplog.records
        if r.levelno == logging.WARNING
    )
    # A non-ValueError is not the concurrent-writer race: no retry.
    assert graph.reads == 1


async def test_langgraph_still_raises_on_unknown_remove_id() -> None:
    """Pin the upstream behaviour the retry-once path exists for.

    If a future langgraph makes RemoveMessage tolerant, this fails loudly and
    the ValueError branch can be simplified — it does not silently rot.
    """
    from langgraph.graph.message import add_messages

    with pytest.raises(ValueError):
        add_messages(
            [HumanMessage(content="a", id="1")],
            [RemoveMessage(id="not-there")],
        )


async def test_langgraph_replaces_a_same_id_message_in_place() -> None:
    """Why the Luna post-answer append is safe to run after a resync.

    ``streaming.py`` always appends the finished answer, including right after
    the resync already seeded HEAD, because that append is the only repair for a
    partial-row dedup (a cancelled attempt's stopped text under the same
    deterministic assistant cmid). It is only safe if a same-id re-add REPLACES
    rather than duplicates. Pin that, so a future langgraph cannot silently turn
    the repair into a doubled message.
    """
    from langgraph.graph.message import add_messages

    left = [
        HumanMessage(content="q", id="u-1"),
        AIMessage(content="partial ans", id="a-1"),
    ]
    merged = add_messages(
        left,
        [
            HumanMessage(content="q", id="u-1"),
            AIMessage(content="full answer", id="a-1"),
        ],
    )
    assert [(m.content, m.id) for m in merged] == [
        ("q", "u-1"),
        ("full answer", "a-1"),
    ]


async def test_langgraph_applies_remove_then_add_in_one_batch() -> None:
    """The single-update design depends on this; pin it too."""
    from langgraph.graph.message import add_messages

    left = [HumanMessage(content="q", id="a"), AIMessage(content="ans", id="run-x")]
    merged = add_messages(
        left,
        [RemoveMessage(id="a"), RemoveMessage(id="run-x")]
        + [HumanMessage(content="edited", id="b")],
    )
    assert [(m.content, m.id) for m in merged] == [("edited", "b")]
