"""Retrieval traces are tenant data and must be scoped like any other.

A trace holds the user's raw query (``RetrievalTrace.query``), and
``GET /api/v1/diagnostics/traces`` returns ``query[:100]`` for every trace it
finds. The router is gated by ``require_admin``, but that is
``require_role(UserRole.ADMIN)`` — a per-user role, and every user belongs to
an organization. So an admin of org A passed the gate and read org B's
queries: the store keyed traces as ``diag:trace:<id>`` under one global
recency index, with no tenant dimension anywhere.

Traces are written on a live path (``api/research/chat.py`` →
``diagnostics_store.store_trace``), and ``chat_router`` is mounted at
``/api/v1``, so this was reachable rather than theoretical.

Scoping is by **per-tenant index** rather than filtering a shared one after
the fact: post-filtering a global ``zrevrange`` silently returns fewer rows
than the caller's ``limit`` and makes ``offset`` meaningless.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

pytestmark = pytest.mark.unit

_ORG_A = "11111111-1111-1111-1111-111111111111"
_ORG_B = "22222222-2222-2222-2222-222222222222"


class _FakeRedis:
    """Enough of the Redis surface for the store's sync branch."""

    def __init__(self) -> None:
        self.values: Dict[str, str] = {}
        self.zsets: Dict[str, List[tuple]] = {}

    def setex(self, key: str, _ttl: int, value: str) -> None:
        self.values[key] = value

    def set(self, key: str, value: str, **_kw: Any) -> None:
        self.values[key] = value

    def get(self, key: str) -> Optional[str]:
        return self.values.get(key)

    def zadd(self, key: str, mapping: Dict[str, float]) -> None:
        # Real ZADD updates an existing member's score in place; appending
        # would duplicate it, and update_trace_evaluation re-stores traces.
        members = self.zsets.setdefault(key, [])
        for member, score in mapping.items():
            existing = [i for i, (m, _) in enumerate(members) if m == member]
            if existing:
                members[existing[0]] = (member, score)
            else:
                members.append((member, score))

    def zremrangebyrank(self, *_a: Any, **_kw: Any) -> None:
        return None

    def zrevrange(self, key: str, start: int, end: int) -> List[str]:
        members = [m for m, _ in sorted(self.zsets.get(key, []), key=lambda x: -x[1])]
        return members[start : end + 1]

    def zrangebyscore(self, key: str, min_score: Any = "-inf", *_a: Any) -> List[str]:
        # Honour the range: get_aggregate_stats passes a cutoff, and a fake
        # that ignores it cannot show the cutoff working.
        low = float("-inf") if min_score in ("-inf", None) else float(min_score)
        return [m for m, score in self.zsets.get(key, []) if score >= low]


def _store() -> Any:
    from src.services.diagnostics.diagnostics_store import DiagnosticsStore

    return DiagnosticsStore(redis_client=_FakeRedis())


def _trace(query: str, organization_id: Optional[str]) -> Any:
    from src.services.diagnostics.retrieval_diagnostics import RetrievalTrace

    return RetrievalTrace(query=query, organization_id=organization_id)


class TestTraceCarriesItsTenant:
    def test_organization_id_round_trips(self) -> None:
        from src.services.diagnostics.retrieval_diagnostics import RetrievalTrace

        restored = RetrievalTrace.from_dict(_trace("q", _ORG_A).to_dict())

        assert restored.organization_id == _ORG_A


class TestReadsAreScoped:
    async def test_another_tenants_trace_is_not_readable_by_id(self) -> None:
        store = _store()
        trace = _trace("org B's confidential query", _ORG_B)
        await store.store_trace(trace)

        assert await store.get_trace(trace.trace_id, organization_id=_ORG_A) is None
        assert await store.get_trace(trace.trace_id, organization_id=_ORG_B) is not None

    async def test_recent_traces_only_shows_your_own(self) -> None:
        store = _store()
        await store.store_trace(_trace("org A query", _ORG_A))
        await store.store_trace(_trace("org B confidential", _ORG_B))

        summaries = await store.get_recent_traces(organization_id=_ORG_A)

        queries = [s["query"] for s in summaries]
        assert queries == ["org A query"], (
            "the summary includes query text, so a cross-tenant row here is a "
            "disclosure of another tenant's search terms"
        )

    async def test_a_trace_with_no_tenant_is_readable_by_nobody(self) -> None:
        """Fail closed: traces written before the field existed stay hidden."""
        store = _store()
        legacy = _trace("legacy query", None)
        await store.store_trace(legacy)

        assert await store.get_trace(legacy.trace_id, organization_id=_ORG_A) is None
        assert await store.get_recent_traces(organization_id=_ORG_A) == []


class TestPaginationStaysHonest:
    async def test_limit_counts_your_rows_not_everyones(self) -> None:
        """Filtering a shared index after the fact would under-fill the page."""
        store = _store()
        # Order matters: A's traces are stored FIRST so they are the oldest.
        # A shared index would hand zrevrange(0, 2) three of B's rows, and
        # post-filtering would drop all three, returning an empty page. With
        # A newest, both designs pass and the test proves nothing.
        for i in range(3):
            await store.store_trace(_trace(f"a{i}", _ORG_A))
        for i in range(3):
            await store.store_trace(_trace(f"b{i}", _ORG_B))

        page = await store.get_recent_traces(limit=3, organization_id=_ORG_A)

        assert len(page) == 3
        assert all(s["query"].startswith("a") for s in page)


class TestEndpointsPassTheTenant:
    def test_every_read_endpoint_takes_the_acting_user(self) -> None:
        import inspect

        from src.api.diagnostics import retrieval_diagnostics as api

        for name in ("get_trace", "get_recent_traces", "get_aggregate_stats"):
            params = inspect.signature(getattr(api, name)).parameters
            assert (
                "current_user" in params
            ), f"{name} cannot scope to a tenant without knowing who is asking"


class TestAggregateIsScoped:
    async def test_stats_only_cover_your_own_traces(self) -> None:
        store = _store()
        await store.store_trace(_trace("a", _ORG_A))
        await store.store_trace(_trace("b1", _ORG_B))
        await store.store_trace(_trace("b2", _ORG_B))

        stats = await store.get_aggregate_stats(organization_id=_ORG_A)

        assert (
            stats["total_traces"] == 1
        ), "aggregate stats over another tenant's traffic disclose its volume"

    async def test_count_reflects_loaded_traces_not_index_size(self) -> None:
        """Index entries outlive trace bodies (no TTL on the index, 24h on bodies).

        Counting index members would over-report total_traces and dilute
        avg_time_ms toward zero for any window past the body TTL.
        """
        store = _store()
        trace = _trace("a", _ORG_A)
        await store.store_trace(trace)
        # Body expires, index entry remains.
        store.redis.values.pop(f"diag:trace:{trace.trace_id}")

        stats = await store.get_aggregate_stats(organization_id=_ORG_A)

        assert stats["total_traces"] == 0
