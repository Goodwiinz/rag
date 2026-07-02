"""track_search_session / record_search_event must scope by the caller's org.

session_id is globally unique (SearchSession.session_id String unique=True), so
looking it up by session_id alone let a caller mutate another tenant's session
(bump updated_at / search_count / response-time counters). Both lookups are now
org-scoped; track_search_session additionally rejects a session_id owned by a
different org rather than colliding on the unique insert.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

from src.services.quality import quality_metrics_service as qms_mod

svc = qms_mod.quality_metrics_service


class _Query:
    """Minimal chainable stub: records the filter clause count, returns preset."""

    def __init__(self, result):
        self._result = result
        self.filters = None

    def filter(self, *clauses):
        self.filters = clauses
        return self

    def first(self):
        return self._result


def _db(query_results):
    """db.query(...) returns successive _Query stubs from query_results."""
    db = MagicMock()
    db.query.side_effect = [_Query(r) for r in query_results]
    return db


async def test_track_updates_only_own_org_session(monkeypatch):
    own = MagicMock()  # org-scoped lookup finds the caller's own session
    db = _db([own])
    monkeypatch.setattr(qms_mod, "get_db_sync", lambda: iter([db]))
    await svc.track_search_session(
        session_id="s1", user_id="u", organization_id="org-A"
    )
    assert own.updated_at is not None
    db.commit.assert_called_once()


async def test_track_rejects_session_owned_by_other_org(monkeypatch):
    # org-scoped lookup -> None; unscoped conflict check -> a row exists (other org)
    db = _db([None, object()])
    monkeypatch.setattr(qms_mod, "get_db_sync", lambda: iter([db]))
    with pytest.raises(ValueError):
        await svc.track_search_session(
            session_id="foreign", user_id="u", organization_id="org-A"
        )
    db.add.assert_not_called()
    db.commit.assert_not_called()


async def test_track_creates_when_truly_new(monkeypatch):
    # org-scoped lookup -> None; conflict check -> None -> create
    db = _db([None, None])
    monkeypatch.setattr(qms_mod, "get_db_sync", lambda: iter([db]))
    await svc.track_search_session(
        session_id="brand-new", user_id="u", organization_id="org-A"
    )
    db.add.assert_called_once()
    db.commit.assert_called_once()


async def test_record_event_skips_foreign_session_counters(monkeypatch):
    # event insert always happens; the counter-update lookup is org-scoped ->
    # a foreign session_id yields None -> no counter mutation.
    db = _db([None])  # org-scoped session lookup returns None
    monkeypatch.setattr(qms_mod, "get_db_sync", lambda: iter([db]))
    await svc.record_search_event(
        session_id="foreign",
        query="q",
        search_type="hybrid",
        results_count=1,
        response_time=1.0,
        user_id="u",
        organization_id="org-A",
    )
    # exactly one add (the SearchEvent); no session counter object mutated
    db.add.assert_called_once()
    db.commit.assert_called_once()
