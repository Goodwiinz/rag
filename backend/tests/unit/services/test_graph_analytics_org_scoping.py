"""Graph analytics must be org-scoped and injection-safe.

The service ran unscoped ``MATCH (n)`` Cypher over the whole cross-tenant
graph and f-stringed user-supplied node/edge filter values straight into
queries (Cypher injection). These tests pin the validated-org requirement,
the always-present org predicate, and the allowlisting of labels / property
keys / values.

NB: ``src.services.analytics.__init__`` has a pre-existing broken import
(``WidgetCreate``); stub the sibling so this module imports in isolation.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest

# src.services.analytics.__init__ has pre-existing broken imports
# (dashboard_service: WidgetCreate, metrics_service: missing uuid). Load the
# target module by file path so the package __init__ never executes.
_ANALYTICS_DIR = pathlib.Path(__file__).parents[3] / "src/services/analytics"
if "src.services.analytics" not in sys.modules:
    _pkg = types.ModuleType("src.services.analytics")
    _pkg.__path__ = [str(_ANALYTICS_DIR)]
    sys.modules["src.services.analytics"] = _pkg

_spec = importlib.util.spec_from_file_location(
    "src.services.analytics.graph_analytics_service",
    str(_ANALYTICS_DIR / "graph_analytics_service.py"),
)
svc = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = svc
_spec.loader.exec_module(svc)

pytestmark = pytest.mark.unit

_ORG = "123e4567-e89b-12d3-a456-426614174000"


@pytest.fixture
def scoped():
    token = svc._current_org.set(_ORG)
    yield svc.GraphAnalyticsService()
    svc._current_org.reset(token)


# --- org validation ----------------------------------------------------------


def test_validate_org_accepts_uuid():
    assert svc._validate_organization_id(_ORG) == _ORG


@pytest.mark.parametrize("bad", [None, "", "not-a-uuid", "12345", "x" * 36])
def test_validate_org_rejects_bad(bad):
    with pytest.raises(ValueError):
        svc._validate_organization_id(bad)


# --- node filter: always org-scoped -----------------------------------------


def test_node_filter_always_includes_org(scoped):
    clause = scoped._build_node_filter(None)
    assert f"n.organization_id = '{_ORG}'" in clause
    assert clause.startswith("WHERE ")


def test_node_filter_requires_org_context():
    # No org set in the contextvar → must raise, never build an unscoped clause.
    token = svc._current_org.set(None)
    try:
        with pytest.raises(ValueError):
            svc.GraphAnalyticsService()._build_node_filter(None)
    finally:
        svc._current_org.reset(token)


def test_node_filter_allows_valid_label_and_prop(scoped):
    clause = scoped._build_node_filter(
        {"labels": ["Entity"], "properties": {"name": "Acme", "count": 3}}
    )
    assert "'Entity' in labels(n)" in clause
    assert "n.name = 'Acme'" in clause
    assert "n.count = 3" in clause
    assert f"n.organization_id = '{_ORG}'" in clause


@pytest.mark.parametrize(
    "node_filters",
    [
        {"labels": ["Entity') DETACH DELETE n //"]},  # label injection
        {"properties": {"name": "x' OR '1'='1"}},  # value injection
        {"properties": {"bad-key": "v"}},  # non-identifier key
    ],
)
def test_node_filter_rejects_injection(scoped, node_filters):
    with pytest.raises(ValueError):
        scoped._build_node_filter(node_filters)


# --- edge filter: injection-safe --------------------------------------------


def test_edge_filter_allows_valid(scoped):
    clause = scoped._build_edge_filter({"types": ["RELATED_TO"], "properties": {"w": 2}})
    assert "type(r) = 'RELATED_TO'" in clause
    assert "r.w = 2" in clause


@pytest.mark.parametrize(
    "edge_filters",
    [
        {"types": ["RELATED_TO']->() DELETE r //"]},
        {"properties": {"w": "1' OR '1'='1"}},
        {"properties": {"bad key": 1}},
    ],
)
def test_edge_filter_rejects_injection(scoped, edge_filters):
    with pytest.raises(ValueError):
        scoped._build_edge_filter(edge_filters)


# --- literal renderer --------------------------------------------------------


def test_cypher_literal_safe_values():
    assert svc._cypher_literal(True) == "true"
    assert svc._cypher_literal(3) == "3"
    assert svc._cypher_literal("ok") == "'ok'"


@pytest.mark.parametrize("bad", ["a'b", 'a"b', "a\\b", "a\nb", "a$b", "a;b", "a{b}"])
def test_cypher_literal_rejects_metachars(bad):
    with pytest.raises(ValueError):
        svc._cypher_literal(bad)


# --- shortest-path analysis is org-scoped (reachable-leak regression) --------


@pytest.mark.asyncio
async def test_run_shortest_path_analysis_scopes_endpoints(scoped):
    """The SHORTEST_PATH algorithm path matched nodes by raw internal id with
    no org predicate — a caller could path across another tenant's graph."""
    import contextlib
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    captured = {}

    session = MagicMock()

    async def _run(query, params=None):
        captured["query"] = query
        result = MagicMock()
        result.single = AsyncMock(return_value=None)

        async def _aiter():
            return
            yield  # pragma: no cover

        result.__aiter__ = lambda self_: _aiter()
        return result

    session.run = AsyncMock(side_effect=_run)

    @contextlib.asynccontextmanager
    async def _get_session():
        yield session

    scoped.get_session = _get_session
    request = SimpleNamespace(
        parameters={"source_node_id": 1, "target_node_id": 2}
    )

    with contextlib.suppress(Exception):
        await scoped._run_shortest_path_analysis(None, request)

    assert f"start.organization_id = '{_ORG}'" in captured["query"]
    assert f"end.organization_id = '{_ORG}'" in captured["query"]
