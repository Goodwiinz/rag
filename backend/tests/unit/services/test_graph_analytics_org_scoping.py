"""Behavioral org-scoping + injection-safety tests for ``GraphAnalyticsService``.

These replace the previous SOURCE-TEXT assertions (which read the service's
``.read_text()`` and therefore passed even if the security code were dead). The
analytics package is now importable in-process (duplicate ``AnalyticsEvent`` ORM
removed; ``src.auth.dependencies`` repointed to ``src.core.dependencies``), so we
exercise the real code: import the service, mock ONLY the neo4j boundary
(``driver -> session -> run/single``), capture every ``run()`` call, drive the
public read paths and the pure Cypher builders, and assert the security contract
on the *generated* query strings and the *captured* ``run()`` params.

Implementation note on how the org predicate is bound
-----------------------------------------------------
The task framing speaks of a "bound ``$organization_id`` parameter". The actual
service does something deliberately different but equally injection-safe: it
scopes every query by interpolating the organization id as a Cypher *string
literal* (``n.organization_id = '<uuid>'``) rather than a bound parameter. That
is intentional -- these queries feed ``apoc`` procedures, ``collect(n)`` node
projections, and mid-pattern ``WHERE`` clauses that cannot accept bound
identifiers and, in several cases, cannot accept bound values either. The
injection defense is therefore *validate-then-interpolate*:

* the org must match a strict anchored UUID regex (``_ORG_ID_RE``) or the call
  fails closed *before any Cypher executes*; a validated UUID cannot carry a
  Cypher metacharacter, so its interpolation is safe; and
* filter labels / property keys / values are allowlisted
  (``_validate_identifier`` / ``_cypher_literal``) or rejected outright.

The tests below pin exactly that behavior: (a) every generated query carries the
org predicate set to the *validated* UUID we passed and nothing attacker-derived
is interpolated (genuinely safe scalars like ``top_k``/node ids DO travel as
bound params, which we also assert); (b) a missing/invalid org raises before any
``run()``; (c) a hostile filter label/value is rejected and never reaches a query
string.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager

import pytest

from src.models.analytics.graph_analytics import (
    GraphAlgorithmType,
    GraphAnalysisRequest,
    PathAnalysisRequest,
)
from src.services.analytics import graph_analytics_service as gas
from src.services.analytics.graph_analytics_service import GraphAnalyticsService

pytestmark = pytest.mark.unit

# A valid v4-shaped UUID that satisfies the service's anchored ``_ORG_ID_RE``.
ORG = "123e4567-e89b-12d3-a456-426614174000"
ORG_PREDICATE = f"organization_id = '{ORG}'"


# --------------------------------------------------------------------------- #
# Fake neo4j boundary -- the ONLY thing mocked. No service method is patched,
# so every assertion runs against the real query-building code.
# --------------------------------------------------------------------------- #


class _ZeroRecord:
    """A neo4j record stand-in whose every column reads as ``0``.

    Enough for the read paths to complete without bespoke per-query data:
    counts come back as ``0`` and the async-iterated result sets are empty.
    """

    def __getitem__(self, key):  # noqa: D401 - mapping access used by service
        return 0


class _FakeResult:
    """Async neo4j result: ``single()`` yields a zero record, iteration empty."""

    def __init__(self):
        self._records = ()
        self._idx = 0

    async def single(self):
        return _ZeroRecord()

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._records):
            raise StopAsyncIteration
        rec = self._records[self._idx]
        self._idx += 1
        return rec


class _FakeSession:
    """Captures every ``run(query, params)`` into a shared list."""

    def __init__(self, calls):
        self._calls = calls

    async def run(self, query, parameters=None):
        self._calls.append((query, parameters))
        return _FakeResult()

    async def close(self):
        return None


class _FakeDriver:
    def __init__(self, calls):
        self._calls = calls

    def session(self, database="neo4j"):
        return _FakeSession(self._calls)

    async def close(self):
        return None


@pytest.fixture(autouse=True)
def _reset_org_context():
    """Force a clean ``None`` org baseline around every test so the fail-closed
    assertions can't be masked by a value leaked from another test."""
    token = gas._current_org.set(None)
    try:
        yield
    finally:
        gas._current_org.reset(token)


@pytest.fixture
def service():
    """A real ``GraphAnalyticsService`` with only its neo4j driver faked."""
    svc = GraphAnalyticsService()
    svc.initialized = True
    calls: list[tuple[str, object]] = []
    svc.driver = _FakeDriver(calls)
    svc.captured_calls = calls  # test handle; not used by the service itself
    return svc


@contextmanager
def _org_scope(org):
    """Reproduce the contract the public entrypoints guarantee: the validated
    org ContextVar is set before any builder/finder runs. Used to exercise the
    builders and the neo4j-only ``_run_*``/``_find_*`` helpers in isolation."""
    token = gas._current_org.set(gas._validate_organization_id(org))
    try:
        yield
    finally:
        gas._current_org.reset(token)


def _queries(service):
    return [q for q, _ in service.captured_calls]


# --------------------------------------------------------------------------- #
# (a) Every generated query carries the validated org predicate
# --------------------------------------------------------------------------- #


async def test_statistics_queries_all_carry_validated_org_predicate(service):
    await service.get_graph_statistics(organization_id=ORG)

    # node count, edge count, node-type dist, edge-type dist
    assert len(service.captured_calls) == 4
    # The interpolated org is exactly the strict UUID we passed -- nothing else
    # is interpolated -- and it carries no bound param (it's a literal).
    assert gas._ORG_ID_RE.match(ORG)
    for query, params in service.captured_calls:
        assert ORG_PREDICATE in query
        assert params is None  # org travels as a validated literal, not a param
    # Both original cross-tenant statistics shapes are gone behaviorally: every
    # `MATCH (n)` is immediately scoped, and edge queries scope both endpoints.
    node_q = next(q for q in _queries(service) if "RETURN count(n)" in q)
    assert f"MATCH (n) WHERE n.{ORG_PREDICATE}" in node_q
    edge_q = next(q for q in _queries(service) if "RETURN count(r)" in q)
    assert f"a.{ORG_PREDICATE}" in edge_q and f"b.{ORG_PREDICATE}" in edge_q


@pytest.mark.parametrize("algorithm", ["pagerank", "betweenness", "degree"])
async def test_centrality_queries_are_org_scoped(service, algorithm):
    await service.get_centrality_analysis(
        algorithm=algorithm, top_k=25, organization_id=ORG
    )

    assert service.captured_calls, "centrality should issue at least one query"
    for query, params in service.captured_calls:
        assert f"n.{ORG_PREDICATE}" in query
        # `top_k` IS a genuinely-bindable scalar, so it travels as a bound param
        # -- proving the service binds what it safely can and only interpolates
        # the (validated) org.
        assert params == {"limit": 25}
        assert ORG not in (params or {}).values()
    if algorithm == "degree":
        # degree scopes the node AND the neighbor hop
        degree_q = _queries(service)[0]
        assert degree_q.count(ORG_PREDICATE) >= 2
        assert f"m.{ORG_PREDICATE}" in degree_q


async def test_path_finder_shortest_scopes_both_endpoints(service):
    req = PathAnalysisRequest(
        analysis_type="shortest",
        source_node_id="11",
        target_node_id="22",
        path_count_limit=5,
        weight_property="weight",
    )
    with _org_scope(ORG):
        await service._find_shortest_paths(req)

    (query, params) = service.captured_calls[0]
    assert f"start.{ORG_PREDICATE}" in query and f"end.{ORG_PREDICATE}" in query
    # Node ids ARE bound params (safe to bind), never interpolated.
    assert params["source_id"] == 11 and params["target_id"] == 22
    assert "11" not in query and "22" not in query


async def test_path_finder_all_scopes_both_endpoints(service):
    req = PathAnalysisRequest(
        analysis_type="all",
        source_node_id="11",
        target_node_id="22",
        max_depth=3,
        path_count_limit=50,
    )
    with _org_scope(ORG):
        await service._find_all_paths(req)

    (query, params) = service.captured_calls[0]
    assert f"start.{ORG_PREDICATE}" in query and f"end.{ORG_PREDICATE}" in query
    assert params["source_id"] == 11 and params["target_id"] == 22


async def test_path_finder_k_shortest_scopes_both_endpoints(service):
    req = PathAnalysisRequest(
        analysis_type="k_shortest",
        source_node_id="11",
        target_node_id="22",
        path_count_limit=4,
        weight_property="weight",
    )
    with _org_scope(ORG):
        await service._find_k_shortest_paths(req)

    (query, params) = service.captured_calls[0]
    assert f"start.{ORG_PREDICATE}" in query and f"end.{ORG_PREDICATE}" in query
    assert params["source_id"] == 11 and params["target_id"] == 22


async def test_triangle_count_scopes_primary_alias_and_neighbors(service):
    # The primary node is bound as `a` (the alias fix), and b/c are scoped too,
    # so a triangle reaching into another tenant's nodes is excluded.
    req = GraphAnalysisRequest(
        algorithm=GraphAlgorithmType.TRIANGLE_COUNT, name="t", node_filters=None
    )
    with _org_scope(ORG):
        await service._run_triangle_count(uuid.uuid4(), req)

    query = service.captured_calls[0][0]
    assert f"a.{ORG_PREDICATE}" in query  # primary bound as `a`, not `n`
    assert f"b.{ORG_PREDICATE}" in query and f"c.{ORG_PREDICATE}" in query


async def test_connected_components_query_is_org_scoped_with_benign_filter(service):
    # A real query that *uses* node_filters: org predicate present and the
    # benign label/value are interpolated as safe literals.
    req = GraphAnalysisRequest(
        algorithm=GraphAlgorithmType.CONNECTED_COMPONENTS,
        name="t",
        node_filters={"labels": ["Document"], "properties": {"status": "indexed"}},
    )
    with _org_scope(ORG):
        await service._run_connected_components(uuid.uuid4(), req)

    query = service.captured_calls[0][0]
    assert f"n.{ORG_PREDICATE}" in query
    assert "'Document' in labels(n)" in query
    assert "n.status = 'indexed'" in query


# --------------------------------------------------------------------------- #
# (b) Missing / invalid org fails closed BEFORE any Cypher runs
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bad_org",
    [
        None,
        "",
        "not-a-uuid",
        "' OR '1'='1",  # classic injection attempt -- rejected as non-UUID
        "123",
        "123e4567e89b12d3a456426614174000",  # UUID digits but unhyphenated
        "123e4567-e89b-12d3-a456-426614174000' OR '1'='1",  # UUID + suffix
    ],
)
async def test_statistics_rejects_invalid_org_before_any_cypher(service, bad_org):
    with pytest.raises(ValueError):
        await service.get_graph_statistics(organization_id=bad_org)
    assert service.captured_calls == [], "no Cypher may run on an invalid org"


@pytest.mark.parametrize("bad_org", [None, "", "DROP DATABASE neo4j"])
async def test_centrality_rejects_invalid_org_before_any_cypher(service, bad_org):
    with pytest.raises(ValueError):
        await service.get_centrality_analysis(
            algorithm="pagerank", organization_id=bad_org
        )
    assert service.captured_calls == []


async def test_unsupported_centrality_algorithm_raises_without_query(service):
    with pytest.raises(ValueError):
        await service.get_centrality_analysis(
            algorithm="definitely-not-real", organization_id=ORG
        )
    assert service.captured_calls == []


def test_node_filter_builder_fails_closed_without_org(service):
    # The builder must refuse to emit an unscoped clause when no org is set --
    # this is the belt-and-suspenders guard against a missing entrypoint scope.
    assert gas._current_org.get() is None
    with pytest.raises(ValueError):
        service._build_node_filter(None)


# --------------------------------------------------------------------------- #
# (a/builder) Builders always emit the org predicate
# --------------------------------------------------------------------------- #


def test_node_filter_builder_always_emits_org_predicate(service):
    with _org_scope(ORG):
        # No filters -> still scoped (previously this returned "" => cross-tenant)
        assert service._build_node_filter(None) == f"WHERE n.{ORG_PREDICATE}"
        # Alias override (the triangle-count `a` fix) scopes the right variable
        assert service._build_node_filter(None, alias="a") == f"WHERE a.{ORG_PREDICATE}"
        # Benign filters keep the org predicate and add allowlisted clauses
        clause = service._build_node_filter(
            {"labels": ["Document"], "properties": {"status": "indexed"}}
        )
        assert clause.startswith(f"WHERE n.{ORG_PREDICATE}")
        assert "'Document' in labels(n)" in clause
        assert "n.status = 'indexed'" in clause


def test_edge_filter_builder_allowlists_and_emits_safe_literals(service):
    # Edges carry no org of their own (scoped via endpoints); keys/values/types
    # are allowlisted. No org needed for this builder.
    assert service._build_edge_filter(None) == ""
    clause = service._build_edge_filter(
        {"types": ["MENTIONS", "CITES"], "properties": {"weight": 3}}
    )
    assert "type(r) = 'MENTIONS'" in clause and "type(r) = 'CITES'" in clause
    assert "r.weight = 3" in clause


# --------------------------------------------------------------------------- #
# (c) Hostile filter labels/values are rejected and never reach a query string
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "node_filters, hostile",
    [
        # label injection -- breaks out of the pattern
        ({"labels": ["User) MATCH (x"]}, "User) MATCH (x"),
        # property-key injection
        ({"properties": {"x) RETURN n //": 1}}, "x) RETURN n //"),
        # property-value injection -- carries Cypher metacharacters
        ({"properties": {"name": "' OR 1=1"}}, "' OR 1=1"),
        ({"properties": {"name": "'; DROP DATABASE neo4j; //"}}, "DROP DATABASE"),
    ],
)
async def test_hostile_node_filter_is_rejected_not_interpolated(
    service, node_filters, hostile
):
    req = GraphAnalysisRequest(
        algorithm=GraphAlgorithmType.CONNECTED_COMPONENTS,
        name="t",
        node_filters=node_filters,
    )
    with _org_scope(ORG):
        with pytest.raises(ValueError):
            # Raises in _build_node_filter, before get_session/run.
            await service._run_connected_components(uuid.uuid4(), req)
    # The hostile value never reached a query string because no query ran.
    assert service.captured_calls == []
    assert all(hostile not in q for q in _queries(service))


def test_hostile_node_filter_rejected_at_builder(service):
    with _org_scope(ORG):
        with pytest.raises(ValueError):
            service._build_node_filter({"labels": ["User) MATCH (x"]})
        with pytest.raises(ValueError):
            service._build_node_filter({"properties": {"name": "' OR 1=1"}})


@pytest.mark.parametrize(
    "edge_filters",
    [
        {"types": ["MENTIONS) DELETE n //"]},  # bad relationship-type identifier
        {"properties": {"weight": "' OR 1=1"}},  # value carries a Cypher quote
        {"properties": {"w) RETURN r //": 1}},  # bad property key
    ],
)
def test_hostile_edge_filter_is_rejected(service, edge_filters):
    with pytest.raises(ValueError):
        service._build_edge_filter(edge_filters)


# --------------------------------------------------------------------------- #
# API layer: a missing/invalid org surfaces as 400 (not 500), org forwarded.
# Behavioral: real router + TestClient, neo4j-free (service method monkeypatched
# at the I/O boundary only, to raise the same ValueError the validator raises).
# --------------------------------------------------------------------------- #


def test_statistics_endpoint_forwards_org_and_maps_value_error_to_400(monkeypatch):
    # Sync test: starlette's TestClient drives its own event loop, so it must
    # not run inside an already-running asyncio test loop.
    import types as _types

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.api.analytics import graph_analytics as api_mod
    from src.core.dependencies import get_current_user

    user_org = uuid.uuid4()
    seen = {}

    async def _fake_statistics(*, organization_id):
        seen["organization_id"] = organization_id
        raise ValueError("organization_id is required for graph analytics")

    monkeypatch.setattr(
        api_mod.graph_analytics_service, "get_graph_statistics", _fake_statistics
    )

    app = FastAPI()
    app.include_router(api_mod.router)
    app.dependency_overrides[get_current_user] = lambda: _types.SimpleNamespace(
        id=uuid.uuid4(), organization_id=user_org
    )

    client = TestClient(app)
    resp = client.get("/graph-analytics/statistics")

    assert resp.status_code == 400  # ValueError -> 400, not an opaque 500
    assert seen["organization_id"] == str(user_org)  # org forwarded from the user


# --------------------------------------------------------------------------- #
# Source-text guard (the single allowed non-behavioral test).
# The behavioral tests above prove every query they reach is org-scoped, but a
# few `_run_*` paths also touch Postgres and aren't exercised here without a
# live DB. This guard is the cheap regression net that the two ORIGINAL
# cross-tenant query shapes never reappear anywhere in the module.
# --------------------------------------------------------------------------- #


def test_no_original_unscoped_query_shapes_remain_source_guard():
    import inspect

    source = inspect.getsource(gas)
    assert "MATCH (n) RETURN count(n)" not in source
    assert "MATCH ()-[r]->()" not in source
