"""get_health_status must scope node/relationship counts per tenant.

Regression guard for KG-L1 (tenancy-kg-auth-2026-07-09 audit): the /health
endpoint feeds a user-facing panel (GraphHealthMonitor) but ran a global
``MATCH (n)`` / ``MATCH ()-[r]->()``, leaking the whole multi-tenant graph's
size — and displaying another tenant's totals as the caller's own.

Pure unit test — patches the (sync) Neo4j session, no external services.
"""

from contextlib import contextmanager
from unittest.mock import patch

from src.services.knowledge_graph.knowledge_graph_service import (
    knowledge_graph_service,
)


class _Single:
    def __init__(self, value):
        self._value = value

    def single(self):
        return self._value


class _FakeSession:
    """Records every Cypher run(); returns canned .single() rows by query shape."""

    def __init__(self, count):
        self.calls = []  # list[(normalized_query, params)]
        self._count = count

    def run(self, query, **params):
        q = " ".join(query.split())
        self.calls.append((q, params))
        if "count(e)" in q or "count(n)" in q or "count(r)" in q:
            return _Single({"count": self._count})
        if "versions[0]" in q:
            return _Single({"version": "5.0.0"})
        if "SHOW INDEXES" in q or "SHOW CONSTRAINTS" in q:
            return _Single({"count": 0})
        return _Single(None)


def _patch_session(session):
    @contextmanager
    def _cm(*_args, **_kwargs):
        yield session

    return patch.object(knowledge_graph_service, "get_session", _cm)


def test_health_counts_are_org_scoped_and_hide_db_size():
    session = _FakeSession(count=42)
    with _patch_session(session):
        health = knowledge_graph_service.get_health_status(organization_id="org-a")

    scoped = [(q, p) for q, p in session.calls if "organization_id: $org" in q]
    assert scoped, "node/relationship counts must carry the tenant predicate"
    assert all(p.get("org") == "org-a" for _, p in scoped)

    # A tenant call must NOT run the unscoped global counts.
    assert not any(
        q in ("MATCH (n) RETURN count(n) as count",
              "MATCH ()-[r]->() RETURN count(r) as count")
        for q, _ in session.calls
    ), "must not run an unscoped global count for a tenant"

    assert health.node_count == 42
    # whole-DB store size is cross-tenant → withheld on the per-tenant panel
    assert health.database_size is None


def test_health_without_org_keeps_global_counts():
    """Ops/standalone path (no tenant) is unchanged — back-compat."""
    session = _FakeSession(count=999)
    with _patch_session(session):
        knowledge_graph_service.get_health_status()

    assert "MATCH (n) RETURN count(n) as count" in [q for q, _ in session.calls]
    assert not any("organization_id: $org" in q for q, _ in session.calls)
