"""Graph analytics must be org-scoped and injection-safe.

The service ran unscoped ``MATCH (n)`` Cypher over the whole cross-tenant
graph and f-stringed user-supplied filter values into queries. These tests
pin the security-relevant patterns.

NB: this is SOURCE-TEXT verification, not behavioral. Importing
``graph_analytics_service`` is impossible to do in-process without side
effects: the analytics package __init__ is broken (WidgetCreate) AND pulls
``analytics_models`` which defines a SECOND ``analytics_events`` table that
collides (duplicate indexes via extend_existing) with the standalone
``src/models/analytics_event.py`` other tests load — poisoning every later
test's create_all with "index ... already exists". So we assert against the
source instead. Behavioral coverage waits on a fix to those two pre-existing
model/package defects (tracked separately).
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = pytest.mark.unit

_BACKEND = pathlib.Path(__file__).parents[3]
_SVC = (_BACKEND / "src/services/analytics/graph_analytics_service.py").read_text()
_API = (_BACKEND / "src/api/analytics/graph_analytics.py").read_text()


# --- validation + injection-safe helpers -------------------------------------


def test_org_is_validated_as_uuid_and_required():
    assert "def _validate_organization_id" in _SVC
    assert "organization_id is required" in _SVC
    assert "_ORG_ID_RE" in _SVC  # anchored UUID regex


def test_identifier_and_literal_allowlisting_present():
    assert "def _validate_identifier" in _SVC
    assert "def _cypher_literal" in _SVC
    # literal renderer rejects (not escapes) Cypher metacharacters
    assert "Invalid filter value" in _SVC
    assert "_IDENT_RE" in _SVC


# --- node/edge filters always org-scoped -------------------------------------


def test_node_filter_always_emits_org_predicate():
    # _build_node_filter seeds conditions with the org clause unconditionally,
    # and takes an alias param (the triangle-count `a` fix).
    assert "def _build_node_filter(" in _SVC
    assert "alias: str = " in _SVC
    assert "self._org_node_clause(alias)" in _SVC
    assert "def _org_node_clause" in _SVC
    assert "organization_id = '{_require_current_org()}'" in _SVC


def test_edge_filter_is_injection_safe():
    assert "def _build_edge_filter" in _SVC
    assert '_validate_identifier(edge_type, "edge type")' in _SVC


# --- every node/path query carries an org predicate --------------------------


def test_statistics_queries_are_org_scoped():
    # all four statistics queries filter by org; the cross-tenant
    # connectedComponents() count is dropped (None).
    assert _SVC.count("WHERE n.organization_id = '{org}'") >= 1
    assert "a.organization_id = '{org}'" in _SVC  # edge-count both endpoints
    assert "connected_components = None" in _SVC


def test_centrality_rankings_are_org_scoped():
    # pagerank/betweenness/degree projections all scope the node; degree also
    # scopes the neighbor.
    assert _SVC.count("MATCH (n) WHERE n.organization_id = '{org}'") >= 2
    assert "OPTIONAL MATCH (n)-[r]-(m) WHERE m.organization_id = '{org}'" in _SVC


def test_path_finders_scope_both_endpoints():
    # shortest-path twin + the three path finders constrain start AND end.
    assert (
        _SVC.count("start.organization_id = '{org}' AND end.organization_id = '{org}'")
        >= 3
    )


def test_triangle_and_clustering_scope_neighbors():
    # triangle binds primary as `a`; b and c scoped. clustering scopes a, b.
    assert 'alias="a"' in _SVC
    assert "b.organization_id = '{org}' AND c.organization_id = '{org}'" in _SVC
    assert "OPTIONAL MATCH (n)-[r1]-(a) WHERE a.organization_id = '{org}'" in _SVC
    # the broken in-pattern {edge_filter} splice is gone from the queries
    # (community now uses a real WHERE on the neighbor).
    assert "OPTIONAL MATCH (n)-[r]-(m) WHERE m.organization_id = '{org}'" in _SVC


def test_no_unscoped_match_n_remains():
    # No bare `MATCH (n) RETURN`/`MATCH ()-[r]->()` (the original cross-tenant
    # statistics queries).
    assert "MATCH (n) RETURN count(n)" not in _SVC
    assert "MATCH ()-[r]->()" not in _SVC


# --- ContextVar lifecycle + entrypoints --------------------------------------


def test_entrypoints_set_and_reset_context_var():
    # set() outside try, reset() in finally, in every entry method.
    assert _SVC.count("_current_org.set(_validate_organization_id(") >= 4
    assert _SVC.count("_current_org.reset(org_token)") >= 4
    assert "db_result = None" in _SVC  # NameError guard


def test_api_passes_org_and_maps_value_error_to_400():
    assert _API.count("organization_id=str(current_user.organization_id)") >= 4
    # /statistics maps a missing/invalid-org ValueError to 400, not 500.
    assert _API.count("except ValueError") >= 3
