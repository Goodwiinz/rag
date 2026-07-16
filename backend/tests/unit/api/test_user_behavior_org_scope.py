"""Tenant-scope guards on the /api/v1/analytics/behavior endpoints.

Fixing the get_db() 500 in user_behavior_service un-masked several endpoints
whose service queries did not filter organization_id. These tests pin that the
endpoints now bind every client-supplied id (user_id, event_id, session_id) to
the CALLER'S OWN organization:

- get_user_behavior_analytics: target user must share the caller's org (for
  every role incl. ADMIN, and rejecting the null-org == null-org conflation).
- track_user_interaction: passes the caller's org into the event lookup.
- get_session_analysis: passes the caller's org; a foreign/missing session is
  404, not a cross-tenant read.

asyncio_mode=AUTO, so plain ``async def`` tests run natively.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit

from src.api.quality import user_behavior as ub
from src.models.user import UserRole


def _db_returning_target(org_id):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id="target", organization_id=org_id
    )
    return db


def _metrics():
    return SimpleNamespace(
        user_id="target",
        session_count=1,
        total_searches=2,
        avg_session_duration=1.0,
        avg_response_time=0.5,
        preferred_search_types=[],
        top_queries=[],
        last_active=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )


# ---- get_user_behavior_analytics: org binding for every role ---------------


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.USER])
async def test_cross_org_forbidden_for_every_role(role, monkeypatch):
    svc = AsyncMock()
    monkeypatch.setattr(ub.user_behavior_service, "analyze_user_behavior", svc)
    caller = SimpleNamespace(id="a", role=role, organization_id="org-A")
    with pytest.raises(HTTPException) as ei:
        await ub.get_user_behavior_analytics(
            user_id="t",
            days_back=30,
            current_user=caller,
            db=_db_returning_target("org-B"),
        )
    assert ei.value.status_code == 403
    svc.assert_not_awaited()


async def test_missing_target_user_forbidden(monkeypatch):
    monkeypatch.setattr(ub.user_behavior_service, "analyze_user_behavior", AsyncMock())
    caller = SimpleNamespace(id="a", role=UserRole.ADMIN, organization_id="org-A")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as ei:
        await ub.get_user_behavior_analytics(
            user_id="t", days_back=30, current_user=caller, db=db
        )
    assert ei.value.status_code == 403


async def test_null_org_caller_forbidden(monkeypatch):
    # null-org caller must NOT read another null-org user (str(None)==str(None)).
    monkeypatch.setattr(ub.user_behavior_service, "analyze_user_behavior", AsyncMock())
    caller = SimpleNamespace(id="a", role=UserRole.ADMIN, organization_id=None)
    with pytest.raises(HTTPException) as ei:
        await ub.get_user_behavior_analytics(
            user_id="t",
            days_back=30,
            current_user=caller,
            db=_db_returning_target(None),
        )
    assert ei.value.status_code == 403


async def test_same_org_admin_allowed(monkeypatch):
    monkeypatch.setattr(
        ub.user_behavior_service,
        "analyze_user_behavior",
        AsyncMock(return_value=_metrics()),
    )
    caller = SimpleNamespace(id="a", role=UserRole.ADMIN, organization_id="org-A")
    result = await ub.get_user_behavior_analytics(
        user_id="t", days_back=30, current_user=caller, db=_db_returning_target("org-A")
    )
    assert result.user_id == "target"
    assert result.total_searches == 2


async def test_same_org_non_admin_peer_forbidden(monkeypatch):
    # Intra-tenant horizontal authz: a same-org, non-admin caller must NOT read
    # a *different* user's behavior analytics (top_queries etc). The org check
    # alone is insufficient — this pins the role/self gate.
    svc = AsyncMock(return_value=_metrics())
    monkeypatch.setattr(ub.user_behavior_service, "analyze_user_behavior", svc)
    caller = SimpleNamespace(id="a", role=UserRole.USER, organization_id="org-A")
    with pytest.raises(HTTPException) as ei:
        await ub.get_user_behavior_analytics(
            user_id="t",  # a different user in the same org
            days_back=30,
            current_user=caller,
            db=_db_returning_target("org-A"),
        )
    assert ei.value.status_code == 403
    svc.assert_not_awaited()


async def test_same_org_non_admin_reads_self_allowed(monkeypatch):
    # A non-admin may read their OWN behavior analytics.
    monkeypatch.setattr(
        ub.user_behavior_service,
        "analyze_user_behavior",
        AsyncMock(return_value=_metrics()),
    )
    caller = SimpleNamespace(id="target", role=UserRole.USER, organization_id="org-A")
    result = await ub.get_user_behavior_analytics(
        user_id="target",  # own id
        days_back=30,
        current_user=caller,
        db=_db_returning_target("org-A"),
    )
    assert result.user_id == "target"


# ---- track_user_interaction: caller org passed into the lookup -------------


async def test_track_interaction_scopes_to_caller_org(monkeypatch):
    svc = AsyncMock(return_value=True)
    monkeypatch.setattr(ub.user_behavior_service, "track_user_interaction", svc)
    caller = SimpleNamespace(id="a", role=UserRole.USER, organization_id="org-A")
    await ub.track_user_interaction(
        interaction_data={
            "session_id": "s",
            "event_id": "e",
            "interaction_type": "click",
        },
        current_user=caller,
    )
    assert svc.await_args.kwargs["organization_id"] == "org-A"


# ---- get_session_analysis: foreign session -> 404, not a cross-tenant read -


async def test_session_analysis_foreign_session_404(monkeypatch):
    # service raises ValueError (session not in caller's org) -> endpoint 404
    monkeypatch.setattr(
        ub.user_behavior_service,
        "analyze_session",
        AsyncMock(side_effect=ValueError("Session not found")),
    )
    caller = SimpleNamespace(
        id="a", role=SimpleNamespace(value="admin"), organization_id="org-A"
    )
    with pytest.raises(HTTPException) as ei:
        await ub.get_session_analysis(session_id="foreign", current_user=caller)
    assert ei.value.status_code == 404


async def test_session_analysis_passes_caller_org(monkeypatch):
    analysis = SimpleNamespace(
        session_id="s",
        user_id="a",
        duration=1.0,
        search_count=1,
        avg_response_time=0.1,
        clicked_results=0,
        total_results_viewed=0,
        queries=[],
        search_types=[],
        bounce_rate=0.0,
        task_completion_rate=0.0,
        satisfaction_indicators={},
    )
    svc = AsyncMock(return_value=analysis)
    monkeypatch.setattr(ub.user_behavior_service, "analyze_session", svc)
    caller = SimpleNamespace(
        id="a", role=SimpleNamespace(value="user"), organization_id="org-A"
    )
    await ub.get_session_analysis(session_id="s", current_user=caller)
    assert svc.await_args.kwargs["organization_id"] == "org-A"
