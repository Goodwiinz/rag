"""Chat dual-store divergence guard — unit tests (audit D3 / P2.6).

Covers the two halves of the guard added to ``src.api.agent.jobs``:

1. ``_persist_user_message_guarded`` — the user-turn INSERT is retried once and,
   if it still fails, emits a structured WARN (thread_id + client_message_id) and
   bumps ``agent_dualstore_user_turn_persist_failures_total`` instead of failing
   silently. It must never raise (the turn continues either way).
2. ``build_graph_input_messages`` / ``_detect_dualstore_divergence`` — at turn
   start, when the checkpoint is populated, the checkpoint HumanMessage count is
   compared against the persisted ``chat_messages`` user-row count; a mismatch is
   logged (detection only) and counted. The empty-checkpoint seed path is skipped
   (it self-heals from the DB). Sampling keeps the extra COUNT off the hot path.

Pure Python: DB/graph/counters are fakes or monkeypatched. No real DB or runtime.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage

import src.api.agent.jobs as jobs
import src.services.agent.observability as obs
from src.models.chat_message import MessageRole

THREAD = "11111111-1111-1111-1111-111111111111"
JOBS_LOGGER = "src.api.agent.jobs"


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class _FakeCounter:
    """Stand-in for a prometheus Counter — records ``.inc()`` calls."""

    def __init__(self) -> None:
        self.count = 0

    def inc(self, amount: float = 1) -> None:
        self.count += amount


class _RollbackDB:
    """Minimal async session exposing only ``rollback()`` (persist-guard tests)."""

    def __init__(self) -> None:
        self.rollbacks = 0

    async def rollback(self) -> None:
        self.rollbacks += 1


class _CountResult:
    def __init__(self, n: int) -> None:
        self._n = n

    def scalar_one(self) -> int:
        return self._n


class _CountDB:
    """Returns a canned COUNT for any execute() (exercises the real query build)."""

    def __init__(self, n: int) -> None:
        self._n = n
        self.executed: list = []

    async def execute(self, stmt):
        self.executed.append(stmt)
        return _CountResult(self._n)


class _SeedResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _SeedDB:
    """Returns preset ChatMessage-like rows for the empty-checkpoint seed path."""

    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _stmt):
        return _SeedResult(self._rows)


class _FakeGraph:
    def __init__(self, values):
        self._values = values

    async def aget_state(self, _config):
        return SimpleNamespace(values=self._values)


def _row(role, content, *, rid=None, cmid=None):
    return SimpleNamespace(
        role=role, content=content, id=rid or _uuid.uuid4(), client_message_id=cmid
    )


def _req(content, cmid=None):
    """A one-turn request-messages list (list of message-like objects)."""
    return [SimpleNamespace(role="user", content=content, client_message_id=cmid)]


def _req_obj(thread_id="t-1", content="hi", cmid="cmid-1"):
    """A request object shaped like AgentExecuteRequest for the persist guard."""
    return SimpleNamespace(
        thread_id=thread_id,
        messages=[
            SimpleNamespace(role="user", content=content, client_message_id=cmid)
        ],
    )


def _user():
    return SimpleNamespace(id=_uuid.uuid4())


# --------------------------------------------------------------------------- #
# 1. _persist_user_message_guarded — retry + observable marker
# --------------------------------------------------------------------------- #


async def test_guarded_success_passes_result_through(monkeypatch):
    calls = []

    async def fake_persist(db, user, req):
        calls.append(req)
        return True

    ctr = _FakeCounter()
    monkeypatch.setattr(jobs, "_persist_user_message", fake_persist)
    monkeypatch.setattr(obs, "agent_dualstore_user_turn_persist_failures_total", ctr)

    db = _RollbackDB()
    result = await jobs._persist_user_message_guarded(db, _user(), _req_obj())

    assert result is True
    assert len(calls) == 1  # no retry on success
    assert db.rollbacks == 0
    assert ctr.count == 0  # no divergence marker on the happy path


async def test_guarded_dedup_false_is_not_a_failure(monkeypatch):
    """A ``False`` from the underlying insert (duplicate / nothing to do) is a
    success, not a failure — no rollback, no marker."""

    async def fake_persist(db, user, req):
        return False

    ctr = _FakeCounter()
    monkeypatch.setattr(jobs, "_persist_user_message", fake_persist)
    monkeypatch.setattr(obs, "agent_dualstore_user_turn_persist_failures_total", ctr)

    db = _RollbackDB()
    result = await jobs._persist_user_message_guarded(db, _user(), _req_obj())

    assert result is False
    assert db.rollbacks == 0
    assert ctr.count == 0


async def test_guarded_retries_once_then_succeeds(monkeypatch, caplog):
    attempts = {"n": 0}

    async def flaky(db, user, req):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("transient blip")
        return True

    ctr = _FakeCounter()
    monkeypatch.setattr(jobs, "_persist_user_message", flaky)
    monkeypatch.setattr(obs, "agent_dualstore_user_turn_persist_failures_total", ctr)

    db = _RollbackDB()
    caplog.set_level(logging.WARNING, logger=JOBS_LOGGER)
    result = await jobs._persist_user_message_guarded(db, _user(), _req_obj())

    assert result is True
    assert attempts["n"] == 2  # first failed, retry succeeded
    assert db.rollbacks == 1  # rolled back the failed transaction before retry
    assert ctr.count == 0  # recovered → no marker
    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []


async def test_guarded_both_fail_marks_and_does_not_raise(monkeypatch, caplog):
    async def always_fail(db, user, req):
        raise RuntimeError("db down")

    ctr = _FakeCounter()
    monkeypatch.setattr(jobs, "_persist_user_message", always_fail)
    monkeypatch.setattr(obs, "agent_dualstore_user_turn_persist_failures_total", ctr)

    db = _RollbackDB()
    caplog.set_level(logging.WARNING, logger=JOBS_LOGGER)

    req = _req_obj(thread_id="t-abc", cmid="cmid-9")
    # Must NOT raise — a durable-persist failure can't abort a streamable turn.
    result = await jobs._persist_user_message_guarded(db, _user(), req)

    assert result is False
    assert db.rollbacks == 2  # both attempts rolled back
    assert ctr.count == 1  # divergence marker stamped

    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warns) == 1
    rec = warns[0]
    assert rec.thread_id == "t-abc"
    assert rec.client_message_id == "cmid-9"


async def test_guarded_marker_survives_missing_metric(monkeypatch):
    """A metrics-layer failure must never mask the persist error / raise."""

    async def always_fail(db, user, req):
        raise RuntimeError("db down")

    class _BoomCounter:
        def inc(self, *a, **k):
            raise RuntimeError("registry gone")

    monkeypatch.setattr(jobs, "_persist_user_message", always_fail)
    monkeypatch.setattr(
        obs, "agent_dualstore_user_turn_persist_failures_total", _BoomCounter()
    )

    result = await jobs._persist_user_message_guarded(
        _RollbackDB(), _user(), _req_obj()
    )
    assert result is False  # swallowed, still returns


# --------------------------------------------------------------------------- #
# 2. _should_check_divergence — sampling gate
# --------------------------------------------------------------------------- #


def test_sampling_always_below_threshold():
    # Always runs for the first couple of populated-checkpoint turns.
    assert jobs._should_check_divergence(0) is True
    assert jobs._should_check_divergence(1) is True
    assert jobs._should_check_divergence(2) is True


def test_sampling_one_in_n_above_threshold(monkeypatch):
    # At/above the threshold it samples 1-in-N via random.randrange.
    monkeypatch.setattr(jobs.random, "randrange", lambda n: 0)
    assert jobs._should_check_divergence(3) is True
    assert jobs._should_check_divergence(500) is True

    monkeypatch.setattr(jobs.random, "randrange", lambda n: 1)
    assert jobs._should_check_divergence(3) is False
    assert jobs._should_check_divergence(500) is False


# --------------------------------------------------------------------------- #
# 3. _chat_user_row_count — tenant-scoped COUNT
# --------------------------------------------------------------------------- #


async def test_count_bad_thread_id_returns_none():
    assert await jobs._chat_user_row_count(_CountDB(0), "not-a-uuid") is None


async def test_count_returns_scalar_one_int():
    db = _CountDB(4)
    assert await jobs._chat_user_row_count(db, THREAD) == 4
    assert len(db.executed) == 1


async def test_count_owner_scoped_builds_joined_statement():
    # The owner_id branch adds the workspace-owner JOIN; assert it builds and
    # runs without error (defense-in-depth on top of the verified thread id).
    db = _CountDB(7)
    n = await jobs._chat_user_row_count(db, THREAD, owner_id=_uuid.uuid4())
    assert n == 7


# --------------------------------------------------------------------------- #
# 4. _detect_dualstore_divergence — detection only
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("user_rows,ckpt", [(2, 2), (3, 2)])  # delta 0, delta 1
async def test_detect_silent_on_healthy_delta(monkeypatch, caplog, user_rows, ckpt):
    async def fake_count(db, tid, *, owner_id=None):
        return user_rows

    ctr = _FakeCounter()
    monkeypatch.setattr(jobs, "_chat_user_row_count", fake_count)
    monkeypatch.setattr(obs, "agent_dualstore_divergence_detected_total", ctr)
    caplog.set_level(logging.WARNING, logger=JOBS_LOGGER)

    await jobs._detect_dualstore_divergence(
        object(), THREAD, checkpoint_human_count=ckpt
    )

    assert ctr.count == 0
    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []


async def test_detect_warns_when_checkpoint_ahead(monkeypatch, caplog):
    # Checkpoint remembers 5 human turns, DB only persisted 2 → the agent knows
    # turns the user can't see (delta = 2 - 5 = -3).
    async def fake_count(db, tid, *, owner_id=None):
        return 2

    ctr = _FakeCounter()
    monkeypatch.setattr(jobs, "_chat_user_row_count", fake_count)
    monkeypatch.setattr(obs, "agent_dualstore_divergence_detected_total", ctr)
    caplog.set_level(logging.WARNING, logger=JOBS_LOGGER)

    await jobs._detect_dualstore_divergence(object(), THREAD, checkpoint_human_count=5)

    assert ctr.count == 1
    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warns) == 1
    rec = warns[0]
    assert rec.thread_id == THREAD
    assert rec.checkpoint_human_count == 5
    assert rec.chat_user_rows == 2
    assert rec.delta == -3


async def test_detect_warns_when_db_far_ahead(monkeypatch, caplog):
    # DB has 6 user rows but the checkpoint only 2 humans → the checkpoint
    # dropped persisted turns without reseeding (delta = 4, beyond the +1 offset).
    async def fake_count(db, tid, *, owner_id=None):
        return 6

    ctr = _FakeCounter()
    monkeypatch.setattr(jobs, "_chat_user_row_count", fake_count)
    monkeypatch.setattr(obs, "agent_dualstore_divergence_detected_total", ctr)
    caplog.set_level(logging.WARNING, logger=JOBS_LOGGER)

    await jobs._detect_dualstore_divergence(object(), THREAD, checkpoint_human_count=2)

    assert ctr.count == 1
    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warns) == 1 and warns[0].delta == 4


async def test_detect_silent_when_count_unavailable(monkeypatch, caplog):
    async def none_count(db, tid, *, owner_id=None):
        return None

    ctr = _FakeCounter()
    monkeypatch.setattr(jobs, "_chat_user_row_count", none_count)
    monkeypatch.setattr(obs, "agent_dualstore_divergence_detected_total", ctr)
    caplog.set_level(logging.WARNING, logger=JOBS_LOGGER)

    await jobs._detect_dualstore_divergence(object(), THREAD, checkpoint_human_count=3)

    assert ctr.count == 0
    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []


async def test_detect_swallows_count_error(monkeypatch):
    async def boom(db, tid, *, owner_id=None):
        raise RuntimeError("db read failed")

    monkeypatch.setattr(jobs, "_chat_user_row_count", boom)
    # Must not raise — detection is fully best-effort.
    await jobs._detect_dualstore_divergence(object(), THREAD, checkpoint_human_count=3)


# --------------------------------------------------------------------------- #
# 5. build_graph_input_messages — integration of the guard at turn start
# --------------------------------------------------------------------------- #


async def test_build_input_fires_divergence_on_mismatch(monkeypatch, caplog):
    # Populated checkpoint (2 humans), DB empty (0 user rows) → delta -2.
    graph = _FakeGraph(
        {
            "messages": [
                HumanMessage(content="a", id="a"),
                HumanMessage(content="b", id="b"),
            ]
        }
    )

    async def fake_count(db, tid, *, owner_id=None):
        return 0

    ctr = _FakeCounter()
    monkeypatch.setattr(jobs, "_chat_user_row_count", fake_count)
    monkeypatch.setattr(obs, "agent_dualstore_divergence_detected_total", ctr)
    caplog.set_level(logging.WARNING, logger=JOBS_LOGGER)

    out = await jobs.build_graph_input_messages(
        object(), graph, THREAD, _req("new", cmid="c1")
    )

    # Detection never changes behaviour: the newest turn is still appended.
    assert [m.content for m in out] == ["new"]
    assert ctr.count == 1
    assert any(
        r.levelno == logging.WARNING and getattr(r, "delta", None) == -2
        for r in caplog.records
    )


async def test_build_input_silent_when_stores_agree(monkeypatch, caplog):
    # Populated checkpoint (2 humans), DB has 3 user rows (the pending newest
    # turn) → delta 1, the healthy steady state.
    graph = _FakeGraph(
        {
            "messages": [
                HumanMessage(content="a", id="a"),
                HumanMessage(content="b", id="b"),
            ]
        }
    )

    async def fake_count(db, tid, *, owner_id=None):
        return 3

    ctr = _FakeCounter()
    monkeypatch.setattr(jobs, "_chat_user_row_count", fake_count)
    monkeypatch.setattr(obs, "agent_dualstore_divergence_detected_total", ctr)
    caplog.set_level(logging.WARNING, logger=JOBS_LOGGER)

    out = await jobs.build_graph_input_messages(
        object(), graph, THREAD, _req("new", cmid="c1")
    )

    assert [m.content for m in out] == ["new"]
    assert ctr.count == 0
    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []


async def test_build_input_empty_checkpoint_skips_divergence(monkeypatch):
    """The empty-checkpoint seed path self-heals from the DB, so it must NOT run
    the divergence check (else every reseed would false-positive)."""
    graph = _FakeGraph({"messages": []})  # count == 0 → seed path

    called = {"n": 0}

    async def spy_detect(*a, **k):
        called["n"] += 1

    monkeypatch.setattr(jobs, "_detect_dualstore_divergence", spy_detect)

    rows = [_row(MessageRole.USER, "q1", cmid="u1")]
    out = await jobs.build_graph_input_messages(
        _SeedDB(rows), graph, THREAD, _req("new", cmid="u2")
    )

    assert [m.content for m in out] == ["q1", "new"]  # seeded from DB + newest
    assert called["n"] == 0  # divergence check skipped on the seed path


async def test_build_input_read_failure_skips_divergence(monkeypatch):
    """A failed checkpoint read (count is None) must not run the check either —
    there's no reliable checkpoint count to compare against."""

    class _RaisingGraph:
        async def aget_state(self, _config):
            raise RuntimeError("checkpoint read failed")

    called = {"n": 0}

    async def spy_detect(*a, **k):
        called["n"] += 1

    monkeypatch.setattr(jobs, "_detect_dualstore_divergence", spy_detect)

    out = await jobs.build_graph_input_messages(
        object(), _RaisingGraph(), THREAD, _req("new", cmid="c1")
    )

    assert [m.content for m in out] == ["new"]  # append-only on a failed read
    assert called["n"] == 0
