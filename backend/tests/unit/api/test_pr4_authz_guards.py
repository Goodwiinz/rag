"""Endpoint-guard / IDOR fixes (authz PR4).

Covers the pipeline project-ownership check, the processing-service org
scoping, the query-history producer→filter contract, plus router/dependency
introspection for the connectors auth and the metric admin-gating (so a guard
removed from one route is caught).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


def _user():
    u = Mock()
    u.id = uuid4()
    u.organization_id = uuid4()
    return u


def _db_scalar(value):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = Mock(return_value=value)
    db.execute = AsyncMock(return_value=result)
    return db


async def test_pipeline_access_404_for_non_owner():
    from src.api.research.pipeline import _ensure_project_access

    db = _db_scalar(None)  # no project owned by caller
    with pytest.raises(HTTPException) as exc:
        await _ensure_project_access(uuid4(), _user(), db)
    assert exc.value.status_code == 404


async def test_pipeline_access_passes_for_owner():
    from src.api.research.pipeline import _ensure_project_access

    db = _db_scalar(uuid4())  # owned project row returned
    await _ensure_project_access(uuid4(), _user(), db)  # no raise


async def test_get_pipeline_enforces_access_before_service():
    """The endpoint must call the access check before touching PipelineService."""
    from unittest.mock import patch

    from src.api.research import pipeline as mod

    db = _db_scalar(None)
    with patch.object(mod.PipelineService, "get_or_create", AsyncMock()) as svc:
        with pytest.raises(HTTPException) as exc:
            await mod.get_pipeline(uuid4(), current_user=_user(), db=db)
    assert exc.value.status_code == 404
    svc.assert_not_called()


async def test_process_document_scopes_by_org():
    """process_document must include organization_id in the lookup so a caller
    cannot start processing on another org's document by id."""
    from src.services.processing import processing_service as mod

    svc = mod.ProcessingPipeline.__new__(mod.ProcessingPipeline)
    captured = {}

    class _Result:
        def scalar_one_or_none(self):
            return None  # not found in caller's org → ValueError

    def _execute(stmt):
        # Render the compiled WHERE to confirm organization_id is constrained.
        captured["sql"] = str(stmt)
        return _Result()

    svc.db = MagicMock()
    svc.db.execute = _execute

    org = str(uuid4())
    with pytest.raises(ValueError):
        await svc.process_document("doc-1", user_id="u-1", organization_id=org)

    assert "organization_id" in captured["sql"]


async def test_query_history_filters_to_caller():
    """The /query-history filter only works if the producer stamps user_id —
    pin the producer→filter contract so the endpoint isn't silently empty."""
    import src.services.search.multi_agent_search_service_v2 as mod

    svc = mod.MultiAgentSearchServiceV2.__new__(mod.MultiAgentSearchServiceV2)
    svc.query_history = []

    await svc._update_learning(
        "my query", {"workflow_type": None}, [], 1.0, user_id="user-A"
    )

    assert svc.query_history, "producer must append an entry"
    entry = svc.query_history[-1]
    assert entry["user_id"] == "user-A"
    # The endpoint filter keeps it for user-A, drops it for user-B.
    assert [e for e in svc.query_history if str(e.get("user_id", "")) == "user-A"]
    assert not [e for e in svc.query_history if str(e.get("user_id", "")) == "user-B"]


# --- comprehensive-review additions -----------------------------------------


async def test_pipeline_update_and_reset_enforce_access_before_service():
    """update/reset got the same _ensure_project_access line as get — pin that
    each call site enforces before touching PipelineService."""
    from unittest.mock import patch

    from src.api.research import pipeline as mod

    db = _db_scalar(None)  # caller owns no matching project
    body = mod.UpdatePipelineRequest()
    with patch.object(mod.PipelineService, "update_pipeline", AsyncMock()) as up, patch.object(
        mod.PipelineService, "reset_pipeline", AsyncMock()
    ) as rp:
        with pytest.raises(HTTPException) as e1:
            await mod.update_pipeline(uuid4(), body=body, current_user=_user(), db=db)
        with pytest.raises(HTTPException) as e2:
            await mod.reset_pipeline(uuid4(), current_user=_user(), db=db)
    assert e1.value.status_code == 404 and e2.value.status_code == 404
    up.assert_not_called()
    rp.assert_not_called()


def test_all_connector_routes_require_auth():
    """Router-level dependency must attach get_current_user to every route —
    survives someone adding a 4th connector route without re-guarding."""
    from fastapi.routing import APIRoute

    from src.api.connectors.router import router
    from src.core.dependencies import get_current_user

    assert any(d.dependency is get_current_user for d in router.dependencies)
    routes = [r for r in router.routes if isinstance(r, APIRoute)]
    assert routes
    for route in routes:
        calls = [d.call for d in route.dependant.dependencies]
        assert get_current_user in calls, f"{route.path} not auth-guarded"


def test_metrics_source_gates_mutations_with_require_admin():
    """src.api.analytics.metrics imports a pre-existing-broken
    `src.auth.dependencies`, so the router can't be introspected here — assert
    on the source instead: the 4 mutations depend on require_admin, not
    get_current_user."""
    import pathlib

    backend = pathlib.Path(__file__).parents[3]
    src = (backend / "src/api/analytics/metrics.py").read_text()
    # 4 mutation endpoints carry require_admin.
    assert src.count("Depends(require_admin)") >= 4
    assert "from src.core.dependencies import require_admin" in src


def test_require_admin_rejects_non_admin():
    from src.core.dependencies import require_role
    from src.models.user import UserRole

    checker = require_role(UserRole.ADMIN)
    non_admin = Mock()
    non_admin.has_permission = Mock(return_value=False)
    with pytest.raises(HTTPException) as exc:
        checker(current_user=non_admin)
    assert exc.value.status_code == 403


def test_get_extracted_features_query_is_org_scoped():
    """The arxiv extracted-features query must constrain organization_id +
    is_deleted (was unscoped, returning every org's features). Source-text
    assertion: the underlying query references Document.external_id, a column
    that doesn't exist on that model (pre-existing bug), so the query can't be
    executed in a behavioral test — pin the scoping clauses in the source."""
    import pathlib

    backend = pathlib.Path(__file__).parents[3]
    src = (backend / "src/api/arxiv/arxiv_extraction.py").read_text()
    assert "Document.organization_id == current_user.organization_id" in src
    assert "Document.is_deleted == False" in src
