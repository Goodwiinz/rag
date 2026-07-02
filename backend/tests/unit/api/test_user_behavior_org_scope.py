"""get_user_behavior_analytics must bind the target user to the caller's org
for EVERY role, including ADMIN.

UserRole.ADMIN is a per-organization role (role and organization_id are
independent columns; no global superuser). The old guard skipped the org check
entirely for ADMIN, and analyze_user_behavior filters only by user_id — so an
org-A admin could read an org-B user's behavior once the endpoint stopped
500ing on the get_db() bug. These tests drive the endpoint coroutine directly
with a mocked db + service.
"""

from __future__ import annotations

import asyncio
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
    target = SimpleNamespace(id="target", organization_id=org_id)
    db.query.return_value.filter.return_value.first.return_value = target
    return db


def _call(user, db):
    return asyncio.get_event_loop().run_until_complete(
        ub.get_user_behavior_analytics(
            user_id="target-user", days_back=30, current_user=user, db=db
        )
    )


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.USER])
def test_cross_org_forbidden_for_every_role(role, monkeypatch):
    called = AsyncMock()
    monkeypatch.setattr(ub.user_behavior_service, "analyze_user_behavior", called)
    caller = SimpleNamespace(id="admin-A", role=role, organization_id="org-A")
    db = _db_returning_target("org-B")  # different org
    with pytest.raises(HTTPException) as ei:
        _call(caller, db)
    assert ei.value.status_code == 403
    called.assert_not_awaited()  # never reaches the service on a cross-org request


def test_missing_target_user_forbidden(monkeypatch):
    monkeypatch.setattr(ub.user_behavior_service, "analyze_user_behavior", AsyncMock())
    caller = SimpleNamespace(id="admin-A", role=UserRole.ADMIN, organization_id="org-A")
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as ei:
        _call(caller, db)
    assert ei.value.status_code == 403


def test_same_org_admin_allowed(monkeypatch):
    metrics = SimpleNamespace(
        user_id="target",
        session_count=1,
        total_searches=2,
        avg_session_duration=1.0,
        avg_response_time=0.5,
        preferred_search_types=[],
        top_queries=[],
        last_active=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        ub.user_behavior_service,
        "analyze_user_behavior",
        AsyncMock(return_value=metrics),
    )
    caller = SimpleNamespace(id="admin-A", role=UserRole.ADMIN, organization_id="org-A")
    db = _db_returning_target("org-A")  # same org
    result = _call(caller, db)
    assert result.user_id == "target"
    assert result.total_searches == 2
