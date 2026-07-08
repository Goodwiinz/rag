"""Option B server-side history rebuild (AGENT_SERVER_SIDE_HISTORY) — unit tests
for the message-assembly helpers in ``src.api.agent.jobs``.

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

from src.api.agent.jobs import (
    _newest_user_message,
    _seed_message_id,
    build_graph_input_messages,
    build_thread_seed_messages,
)
from src.models.chat_message import MessageRole

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

    async def execute(self, _stmt):
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
