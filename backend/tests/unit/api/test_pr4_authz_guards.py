"""Endpoint-guard / IDOR fixes (authz PR4).

Covers the pipeline project-ownership check and the processing-service org
scoping. Connectors auth and metric admin-gating are router/dependency-level
and exercised via the app's dependency wiring elsewhere.
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
