"""KG maintenance/reset endpoints must be tenant-scoped.

`POST /knowledge-graph/schema/reset` previously ran `MATCH (n) DETACH DELETE n`
— an unscoped wipe of EVERY tenant's graph — gated only on the per-user
UserRole.ADMIN (no platform-vs-tenant distinction), so any one org's admin could
destroy all other orgs' graphs. `fix-null-types` similarly SET over all tenants'
nodes. Both are now scoped to the caller's organization; a caller with no org is
rejected rather than running unscoped.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit

from src.api.search import knowledge_graph as kg
from src.models.user import UserRole


def _admin(org_id: str | None = "org-1") -> MagicMock:
    user = MagicMock()
    user.role = UserRole.ADMIN
    user.organization_id = org_id
    return user


def _session_mock(deleted: int = 0, count: int = 0) -> MagicMock:
    session = MagicMock()
    calls: list = []

    def run(query: str, params: dict | None = None) -> MagicMock:
        res = MagicMock()
        res.single.return_value = {"deleted": deleted, "count": count, "updated": count}
        calls.append((query, params))
        return res

    session.run = run
    session.run_calls = calls
    return session


@contextmanager
def _session_cm(session: MagicMock) -> Iterator[MagicMock]:
    yield session


def test_require_org_id_rejects_missing_org() -> None:
    user = MagicMock()
    user.organization_id = None
    with pytest.raises(HTTPException) as exc:
        kg._require_org_id(user)
    assert exc.value.status_code == 403


def test_schema_reset_is_org_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session_mock(deleted=7)
    monkeypatch.setattr(
        kg.knowledge_graph_service, "get_session", lambda: _session_cm(session)
    )
    monkeypatch.setattr(kg.knowledge_graph_service, "_ensure_schema", lambda: None)

    result = kg.reset_graph_schema(confirm=True, current_user=_admin("org-1"))

    assert result["deleted_entities"] == 7
    # The destructive query must be org-scoped, never the global wipe.
    joined = " ".join(q for q, _ in session.run_calls)
    assert "MATCH (n) DETACH DELETE n" not in joined
    assert "e.organization_id = $org_id" in joined
    assert all(p == {"org_id": "org-1"} for _, p in session.run_calls if p is not None)


def test_schema_reset_rejects_org_less_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    # Must 403 before touching the graph — never run unscoped.
    called = {"got_session": False}

    def _no_session() -> None:
        called["got_session"] = True
        raise AssertionError("must not open a session for an org-less caller")

    monkeypatch.setattr(kg.knowledge_graph_service, "get_session", _no_session)

    user = _admin(org_id=None)
    with pytest.raises(HTTPException) as exc:
        kg.reset_graph_schema(confirm=True, current_user=user)
    assert exc.value.status_code == 403
    assert called["got_session"] is False


def test_fix_null_types_is_org_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session_mock(count=3)
    monkeypatch.setattr(
        kg.knowledge_graph_service, "get_session", lambda: _session_cm(session)
    )

    result = kg.fix_null_entity_types(current_user=_admin("org-9"))

    assert result["updated"] == 3
    joined = " ".join(q for q, _ in session.run_calls)
    assert "e.organization_id = $org_id" in joined
    assert all(p == {"org_id": "org-9"} for _, p in session.run_calls if p is not None)
