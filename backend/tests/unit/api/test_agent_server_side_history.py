"""Option B server-side history rebuild (AGENT_SERVER_SIDE_HISTORY) — unit tests
for the message-assembly helpers in ``src.services.agent.agent_execution_service``.

Pure Python: the graph is a stub whose ``aget_state`` returns a canned snapshot,
and the DB is a fake whose ``execute`` returns canned ChatMessage rows. No real
DB or LangGraph runtime. These pin the two invariants the design rests on:
seed only into an EMPTY checkpoint, and always carry the newest turn.
"""

from __future__ import annotations

import uuid as _uuid
from types import SimpleNamespace
from typing import Annotated

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.models.chat_message import MessageRole
from src.services.agent.agent_execution_service import (
    _newest_user_message,
    _seed_message_id,
    build_graph_input_messages,
    build_thread_seed_messages,
)

THREAD = "11111111-1111-1111-1111-111111111111"


class _GraphState(TypedDict):
    # Module-level so LangGraph's get_type_hints resolves Annotated/add_messages
    # against module globals (the file uses `from __future__ import annotations`,
    # which stringifies annotations).
    messages: Annotated[list, add_messages]


def _row(role, content, *, rid, cmid=None):
    return SimpleNamespace(role=role, content=content, id=rid, client_message_id=cmid)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    """Returns preset rows for any execute(); records nothing else."""

    def __init__(self, rows):
        self._rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _FakeResult(self._rows)


class _FakeGraph:
    def __init__(self, values):
        self._values = values

    async def aget_state(self, _config):
        return SimpleNamespace(values=self._values)


class _RaisingGraph:
    async def aget_state(self, _config):
        raise RuntimeError("checkpoint read failed")


def _req(content, cmid=None):
    return [SimpleNamespace(role="user", content=content, client_message_id=cmid)]


# --- id determinism ---------------------------------------------------------


def test_seed_id_prefers_client_message_id():
    row = _row(MessageRole.USER, "hi", rid=_uuid.uuid4(), cmid="cmid-1")
    assert _seed_message_id(THREAD, row) == "cmid-1"


def test_seed_id_falls_back_to_pk_and_is_stable():
    rid = _uuid.uuid4()
    row = _row(MessageRole.USER, "hi", rid=rid)
    a = _seed_message_id(THREAD, row)
    b = _seed_message_id(THREAD, row)
    assert a == b == str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"{THREAD}:{rid}"))


# --- seed builder -----------------------------------------------------------


async def test_seed_maps_roles_in_order():
    rows = [
        _row(MessageRole.USER, "q1", rid=_uuid.uuid4(), cmid="u1"),
        _row(MessageRole.ASSISTANT, "a1", rid=_uuid.uuid4()),
        _row(MessageRole.USER, "q2", rid=_uuid.uuid4(), cmid="u2"),
    ]
    seed = await build_thread_seed_messages(_FakeDB(rows), THREAD)
    assert [type(m) for m in seed] == [HumanMessage, AIMessage, HumanMessage]
    assert [m.content for m in seed] == ["q1", "a1", "q2"]
    assert seed[0].id == "u1" and seed[2].id == "u2"


async def test_seed_is_idempotent():
    rows = [_row(MessageRole.USER, "q1", rid=_uuid.uuid4())]
    a = await build_thread_seed_messages(_FakeDB(rows), THREAD)
    b = await build_thread_seed_messages(_FakeDB(rows), THREAD)
    assert [m.id for m in a] == [m.id for m in b]


async def test_seed_query_is_bounded_to_the_latest_40_rows():
    db = _FakeDB([])
    await build_thread_seed_messages(db, THREAD)

    sql = str(db.statement.compile(compile_kwargs={"literal_binds": True}))
    assert "LIMIT 40" in sql


async def test_seed_bad_thread_id_returns_empty():
    assert await build_thread_seed_messages(_FakeDB([]), "not-a-uuid") == []


# --- newest turn ------------------------------------------------------------


def test_newest_uses_cmid():
    m = _newest_user_message(_req("hello", cmid="c9"))
    assert isinstance(m, HumanMessage) and m.content == "hello" and m.id == "c9"


def test_newest_without_cmid_returns_none():
    # No client_message_id -> no safe idempotency id -> signal legacy fallback.
    assert _newest_user_message(_req("hello")) is None


# --- the core gate: seed only when checkpoint is empty ----------------------


async def test_caught_up_checkpoint_appends_only_newest():
    """Non-empty checkpoint → return only the newest turn (no reseed, no dup)."""
    graph = _FakeGraph({"messages": [HumanMessage(content="old", id="old")]})
    db = _FakeDB([_row(MessageRole.USER, "should-not-be-read", rid=_uuid.uuid4())])
    out = await build_graph_input_messages(db, graph, THREAD, _req("new", cmid="c1"))
    assert [m.content for m in out] == ["new"]


async def test_empty_checkpoint_seeds_from_db():
    """Empty checkpoint → rebuild the whole conversation from the DB."""
    graph = _FakeGraph({"messages": []})
    rows = [
        _row(MessageRole.USER, "q1", rid=_uuid.uuid4(), cmid="u1"),
        _row(MessageRole.ASSISTANT, "a1", rid=_uuid.uuid4()),
        _row(MessageRole.USER, "new", rid=_uuid.uuid4(), cmid="u2"),
    ]
    out = await build_graph_input_messages(
        db := _FakeDB(rows), graph, THREAD, _req("new", cmid="u2")
    )
    assert [m.content for m in out] == [
        "q1",
        "a1",
        "new",
    ]  # newest already in seed, not duplicated


async def test_empty_checkpoint_missing_db_row_still_carries_newest():
    """Swallowed persist: DB lacks the newest turn → append it, don't drop it."""
    graph = _FakeGraph({"messages": []})
    rows = [_row(MessageRole.USER, "q1", rid=_uuid.uuid4(), cmid="u1")]  # newest absent
    out = await build_graph_input_messages(
        _FakeDB(rows), graph, THREAD, _req("new", cmid="u2")
    )
    assert [m.content for m in out] == ["q1", "new"]


async def test_empty_checkpoint_and_empty_db_uses_request():
    """Brand-new / unresolved thread → the request's newest turn."""
    graph = _FakeGraph({"messages": []})
    out = await build_graph_input_messages(
        _FakeDB([]), graph, THREAD, _req("first", cmid="c1")
    )
    assert [m.content for m in out] == ["first"]


async def test_none_snapshot_treated_as_empty():
    """aget_state returning no values → seed path (never silently drop)."""
    graph = _FakeGraph(None)
    rows = [_row(MessageRole.USER, "first", rid=_uuid.uuid4(), cmid="c1")]
    out = await build_graph_input_messages(
        _FakeDB(rows), graph, THREAD, _req("first", cmid="c1")
    )
    assert [m.content for m in out] == ["first"]


async def test_checkpoint_read_failure_appends_not_seeds():
    """A failed checkpoint read must NOT seed (could dup a live checkpoint) —
    append only the newest turn, even though the DB has rows."""
    graph = _RaisingGraph()
    rows = [
        _row(MessageRole.USER, "q1", rid=_uuid.uuid4(), cmid="u1"),
        _row(MessageRole.ASSISTANT, "a1", rid=_uuid.uuid4()),
    ]
    out = await build_graph_input_messages(
        _FakeDB(rows), graph, THREAD, _req("new", cmid="u2")
    )
    assert [m.content for m in out] == ["new"]  # newest only, DB not seeded


async def test_no_cmid_signals_legacy_fallback():
    """Newest turn without a client_message_id → None (caller uses legacy path)."""
    graph = _FakeGraph({"messages": []})
    rows = [_row(MessageRole.USER, "q1", rid=_uuid.uuid4())]
    out = await build_graph_input_messages(_FakeDB(rows), graph, THREAD, _req("q1"))
    assert out is None


async def test_same_content_distinct_turns_do_not_collide():
    """Two distinct same-content turns keep distinct ids via cmid (no overwrite)."""
    graph = _FakeGraph({"messages": [HumanMessage(content="hi", id="c1")]})
    a = await build_graph_input_messages(
        _FakeDB([]), graph, THREAD, _req("hi", cmid="c1")
    )
    b = await build_graph_input_messages(
        _FakeDB([]), graph, THREAD, _req("hi", cmid="c2")
    )
    assert a[0].id == "c1" and b[0].id == "c2"  # distinct ids despite equal content


# --- integration: against a REAL MemorySaver checkpoint + add_messages -------
#
# Proves the core hypothesis end to end with genuine LangGraph reducer/checkpoint
# semantics (not a stub): appending onto a populated checkpoint adds only the
# newest turn, and seeding into an EMPTY checkpoint rebuilds the whole thread
# WITHOUT duplicating any turn (the id-keyed upsert converges).


def _real_graph():
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(_GraphState)
    g.add_node("noop", lambda state: {})
    g.add_edge(START, "noop")
    g.add_edge("noop", END)
    return g.compile(checkpointer=MemorySaver())


async def test_real_checkpoint_populated_appends_only_newest():
    graph = _real_graph()
    config = {"configurable": {"thread_id": THREAD}}
    # Turn 1 lands q1 + a1 in the checkpoint.
    await graph.ainvoke(
        {
            "messages": [
                HumanMessage(content="q1", id="u1"),
                AIMessage(content="a1", id="a1"),
            ]
        },
        config,
    )
    rows = [
        _row(MessageRole.USER, "q1", rid=_uuid.uuid4(), cmid="u1"),
        _row(MessageRole.ASSISTANT, "a1", rid=_uuid.uuid4(), cmid="a1"),
        _row(MessageRole.USER, "q2", rid=_uuid.uuid4(), cmid="u2"),
    ]
    out = await build_graph_input_messages(
        _FakeDB(rows), graph, THREAD, _req("q2", cmid="u2")
    )
    assert [m.content for m in out] == ["q2"]  # checkpoint holds q1/a1; add only q2

    # Feed it back through the real reducer: history accumulates, no duplicates.
    await graph.ainvoke({"messages": out}, config)
    final = (await graph.aget_state(config)).values["messages"]
    assert [m.content for m in final] == ["q1", "a1", "q2"]


async def test_real_checkpoint_empty_seeds_without_duplication():
    graph = _real_graph()  # fresh MemorySaver — simulates checkpoint loss/legacy
    config = {"configurable": {"thread_id": THREAD}}
    rows = [
        _row(MessageRole.USER, "q1", rid=_uuid.uuid4(), cmid="u1"),
        _row(MessageRole.ASSISTANT, "a1", rid=_uuid.uuid4(), cmid="a1"),
        _row(MessageRole.USER, "q2", rid=_uuid.uuid4(), cmid="u2"),
    ]
    out = await build_graph_input_messages(
        _FakeDB(rows), graph, THREAD, _req("q2", cmid="u2")
    )
    assert [m.content for m in out] == ["q1", "a1", "q2"]  # seeded whole thread

    await graph.ainvoke({"messages": out}, config)
    final = (await graph.aget_state(config)).values["messages"]
    # id-keyed upsert: exactly the three seeded turns, none doubled.
    assert [m.content for m in final] == ["q1", "a1", "q2"]


async def test_windowed_reopen_appends_newest_never_replaces_old_turns():
    """Audit review, PR #1395 (Codex): the /chat client resends only a
    WINDOWED page (e.g. the initial 50 messages) when reopening a long
    thread, not the full conversation from turn 1. A positional id scheme
    (thread_id, index-within-request) breaks here: turns 11-60's window
    replays indices 0-49, the SAME indices turns 1-50 used earlier, so a
    naive positional rebuild would silently REPLACE old checkpoint content
    in place (add_messages is an id-keyed upsert). build_graph_input_messages
    (Option B) never has this problem because it ignores the resent window's
    positions entirely once the checkpoint is populated: it appends only the
    newest turn, keyed on its own client_message_id.

    Simulates a 60-turn thread already in a real checkpoint, then a resend
    of only the last 50 user turns (a window, NOT the full history) plus one
    new turn — pins that only the new turn is added and every earlier turn's
    content survives unchanged.
    """
    graph = _real_graph()
    config = {"configurable": {"thread_id": THREAD}}

    # Seed 60 turns directly into a real checkpoint.
    for i in range(1, 61):
        await graph.ainvoke(
            {
                "messages": [
                    HumanMessage(content=f"q{i}", id=f"u{i}"),
                    AIMessage(content=f"a{i}", id=f"a{i}"),
                ]
            },
            config,
        )
    before = (await graph.aget_state(config)).values["messages"]
    assert len(before) == 120  # 60 human + 60 assistant, sanity check

    # Client reopens the thread and only has the last 50 messages loaded
    # (turns 11-60) plus the brand-new turn 61 — NOT turns 1-10.
    windowed_request = _req("q61", cmid="u61")  # newest turn only matters here
    out = await build_graph_input_messages(_FakeDB([]), graph, THREAD, windowed_request)

    # Checkpoint is populated -> only the newest turn is ever returned,
    # regardless of what window the client resent.
    assert [m.content for m in out] == ["q61"]

    await graph.ainvoke({"messages": out}, config)
    final = (await graph.aget_state(config)).values["messages"]
    assert len(final) == 121  # exactly one turn appended
    # Every earlier turn's content is untouched — none were replaced in place.
    assert [m.content for m in final[:120]] == [m.content for m in before]
    assert final[-1].content == "q61"


# --- concurrent seeding (codex audit CX2/CX4) --------------------------------


class _MutableCountGraph:
    """count starts empty; flips to populated when the test says so."""

    def __init__(self):
        self.values = {"messages": []}

    async def aget_state(self, _config):
        return SimpleNamespace(values=self.values)


async def test_seed_lock_loser_waits_and_appends_only_newest(monkeypatch):
    """Second concurrent first-turn must NOT double-seed: it waits on the seed
    lock, re-reads a now-populated checkpoint, and appends only its turn."""
    import asyncio

    from src.services.agent import agent_execution_service as svc

    graph = _MutableCountGraph()
    rows = [_row(MessageRole.USER, "new", rid=_uuid.uuid4(), cmid="u1")]

    lock_holder = {"held": True}

    async def fake_acquire(_thread_id):
        return not lock_holder["held"]

    monkeypatch.setattr(svc, "_acquire_seed_lock", fake_acquire)
    monkeypatch.setattr(svc, "_release_seed_lock", _async_noop)

    async def winner_finishes():
        await asyncio.sleep(0.15)
        graph.values = {"messages": [HumanMessage(content="q1", id="s1")]}
        lock_holder["held"] = False

    task = asyncio.create_task(winner_finishes())
    out = await build_graph_input_messages(
        _FakeDB(rows), graph, THREAD, _req("new", cmid="u1")
    )
    await task

    # The loser saw the populated checkpoint and appended ONLY its newest turn.
    assert [m.content for m in out] == ["new"]


async def _async_noop(_thread_id):
    return None


async def test_seed_lock_unavailable_still_seeds(monkeypatch):
    """Lock never freeing (winner crashed) degrades to the pre-lock seed —
    a turn is never lost to the lock."""
    from src.services.agent import agent_execution_service as svc

    monkeypatch.setattr(svc, "_acquire_seed_lock", _return_false)
    monkeypatch.setattr(svc, "_release_seed_lock", _async_noop)
    # Collapse the loser's wait loop so the test stays fast.
    monkeypatch.setattr(svc.asyncio, "sleep", _async_noop)

    graph = _FakeGraph({"messages": []})
    rows = [_row(MessageRole.USER, "new", rid=_uuid.uuid4(), cmid="u1")]
    out = await build_graph_input_messages(
        _FakeDB(rows), graph, THREAD, _req("new", cmid="u1")
    )
    assert [m.content for m in out] == ["new"]


async def _return_false(_thread_id):
    return False
