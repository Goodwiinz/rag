"""
Unit tests for the Research Engine SSE streaming endpoint.

Tests cover:
- POST /runs/{run_id}/stream returns 200 with SSE content-type
- 404 returned for non-existent run
- 409 returned for run not in PENDING or PAUSED status
- Proper SSE headers (Cache-Control, X-Accel-Buffering)
- SSE events are yielded in correct event:/data: format
"""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.research_engine.runs import router
from src.core.database import get_db
from src.core.dependencies import get_current_user


# ============================================================================
# Helpers
# ============================================================================


def _make_run(**overrides):
    """Create a mock ResearchRun ORM object."""
    now = datetime.now(timezone.utc)
    run = Mock()
    run.id = overrides.get("id", uuid.uuid4())
    run.blueprint_id = overrides.get("blueprint_id", uuid.uuid4())
    run.blueprint_version = overrides.get("blueprint_version", 1)
    run.status = overrides.get("status", "pending")
    run.started_at = overrides.get("started_at", None)
    run.completed_at = overrides.get("completed_at", None)
    run.total_tokens = overrides.get("total_tokens", 0)
    run.created_at = overrides.get("created_at", now)
    run.updated_at = overrides.get("updated_at", now)
    return run


def _make_blueprint(**overrides):
    """Create a mock ResearchBlueprint ORM object."""
    bp = Mock()
    bp.id = overrides.get("id", uuid.uuid4())
    bp.project_id = overrides.get("project_id", uuid.uuid4())
    bp.name = overrides.get("name", "Test Blueprint")
    bp.version = overrides.get("version", 1)
    bp.steps = overrides.get("steps", [{"type": "search", "query": "test"}])
    bp.parameters = overrides.get("parameters", {})
    bp.is_immutable = True
    return bp


def _mock_db_returning(run_result=None, blueprint_result=None, project_result=None):
    """Build an AsyncMock DB that returns expected query results.

    For the stream endpoint flow:
    - Query 1: get run
    - Query 2: get blueprint (ownership check)
    - Query 3: get project (ownership check)
    - Query 4: get blueprint (for streaming)
    - Query 5: get last completed step (for paused runs)
    """
    db = AsyncMock()
    results = []

    run_mock = Mock()
    run_mock.scalars.return_value.first.return_value = run_result
    results.append(run_mock)

    if run_result is not None:
        # Ownership check: blueprint lookup
        bp_own_mock = Mock()
        bp_own_mock.scalars.return_value.first.return_value = blueprint_result
        results.append(bp_own_mock)

        if blueprint_result is not None:
            # Ownership check: project lookup
            proj_mock = Mock()
            proj_result_obj = project_result if project_result is not None else Mock()
            proj_mock.scalars.return_value.first.return_value = proj_result_obj
            results.append(proj_mock)

            # Only add more results for streamable statuses
            streamable = {"pending", "paused"}
            if run_result.status in streamable:
                # Blueprint lookup for streaming
                bp_stream_mock = Mock()
                bp_stream_mock.scalars.return_value.first.return_value = blueprint_result
                results.append(bp_stream_mock)

                # Step query for paused runs
                if run_result.status == "paused":
                    step_mock = Mock()
                    step_mock.scalars.return_value.first.return_value = None
                    results.append(step_mock)

    db.execute = AsyncMock(side_effect=results)
    return db


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def stream_app():
    """Minimal FastAPI app with just the runs router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def mock_current_user():
    user = Mock()
    user.id = uuid.uuid4()
    user.email = "researcher@example.com"
    user.is_active = True
    return user


@pytest.fixture
def stream_client(stream_app, mock_current_user):
    """TestClient with auth override on the minimal app."""
    stream_app.dependency_overrides[get_current_user] = lambda: mock_current_user
    with TestClient(stream_app) as c:
        yield c
    stream_app.dependency_overrides.clear()


# ============================================================================
# Success Cases
# ============================================================================


class TestStreamEndpointSuccess:
    """Test successful SSE streaming responses."""

    def _patch_engine_and_get(self, stream_app, stream_client, run_id, mock_engine_run):
        """Helper to patch WorkflowEngine + StepExecutor and make GET request."""
        with patch(
            "src.api.research_engine.runs.WorkflowEngine"
        ) as mock_engine_cls, patch(
            "src.api.research_engine.runs.StepExecutor"
        ), patch(
            "src.api.research_engine.runs.ArxivConnector"
        ), patch(
            "src.api.research_engine.runs.SemanticScholarConnector"
        ):
            engine = Mock()
            engine.run = mock_engine_run
            mock_engine_cls.return_value = engine

            response = stream_client.get(
                f"/api/v1/research-engine/runs/{run_id}/stream"
            )
        return response

    def test_stream_returns_200_with_sse_content_type(
        self, stream_app, stream_client
    ):
        run_id = uuid.uuid4()
        bp_id = uuid.uuid4()
        mock_run = _make_run(id=run_id, blueprint_id=bp_id, status="pending")
        mock_bp = _make_blueprint(id=bp_id)
        db = _mock_db_returning(run_result=mock_run, blueprint_result=mock_bp)

        stream_app.dependency_overrides[get_db] = lambda: db

        async def mock_engine_run(blueprint, run_id, start_from_step=0):
            yield {"event": "run_start", "run_id": str(run_id), "total_steps": 1}
            yield {"event": "run_complete", "run_id": str(run_id), "context": {}}

        response = self._patch_engine_and_get(
            stream_app, stream_client, run_id, mock_engine_run
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        stream_app.dependency_overrides.pop(get_db, None)

    def test_stream_returns_correct_sse_headers(
        self, stream_app, stream_client
    ):
        run_id = uuid.uuid4()
        bp_id = uuid.uuid4()
        mock_run = _make_run(id=run_id, blueprint_id=bp_id, status="pending")
        mock_bp = _make_blueprint(id=bp_id)
        db = _mock_db_returning(run_result=mock_run, blueprint_result=mock_bp)

        stream_app.dependency_overrides[get_db] = lambda: db

        async def mock_engine_run(blueprint, run_id, start_from_step=0):
            yield {"event": "run_complete", "run_id": str(run_id), "context": {}}

        response = self._patch_engine_and_get(
            stream_app, stream_client, run_id, mock_engine_run
        )

        assert response.headers.get("cache-control") == "no-cache"
        assert response.headers.get("x-accel-buffering") == "no"
        stream_app.dependency_overrides.pop(get_db, None)

    def test_stream_yields_sse_events(self, stream_app, stream_client):
        run_id = uuid.uuid4()
        bp_id = uuid.uuid4()
        mock_run = _make_run(id=run_id, blueprint_id=bp_id, status="pending")
        mock_bp = _make_blueprint(id=bp_id)
        db = _mock_db_returning(run_result=mock_run, blueprint_result=mock_bp)

        stream_app.dependency_overrides[get_db] = lambda: db

        async def mock_engine_run(blueprint, run_id, start_from_step=0):
            yield {"event": "run_start", "run_id": str(run_id), "total_steps": 2}
            yield {
                "event": "step_complete",
                "run_id": str(run_id),
                "step_index": 0,
                "step_type": "search",
            }
            yield {"event": "run_complete", "run_id": str(run_id), "context": {}}

        response = self._patch_engine_and_get(
            stream_app, stream_client, run_id, mock_engine_run
        )

        body = response.text
        assert "event: run_start" in body
        assert "event: step_complete" in body
        assert "event: run_complete" in body
        assert "data:" in body
        stream_app.dependency_overrides.pop(get_db, None)

    def test_stream_works_with_paused_run(self, stream_app, stream_client):
        run_id = uuid.uuid4()
        bp_id = uuid.uuid4()
        mock_run = _make_run(id=run_id, blueprint_id=bp_id, status="paused")
        mock_bp = _make_blueprint(id=bp_id)
        db = _mock_db_returning(run_result=mock_run, blueprint_result=mock_bp)

        stream_app.dependency_overrides[get_db] = lambda: db

        async def mock_engine_run(blueprint, run_id, start_from_step=0):
            yield {"event": "run_complete", "run_id": str(run_id), "context": {}}

        response = self._patch_engine_and_get(
            stream_app, stream_client, run_id, mock_engine_run
        )

        assert response.status_code == 200
        stream_app.dependency_overrides.pop(get_db, None)


# ============================================================================
# Error Cases
# ============================================================================


class TestStreamEndpointErrors:
    """Test error cases for the streaming endpoint."""

    def test_stream_returns_404_for_nonexistent_run(
        self, stream_app, stream_client
    ):
        run_id = uuid.uuid4()
        db = _mock_db_returning(run_result=None)

        stream_app.dependency_overrides[get_db] = lambda: db

        response = stream_client.get(
            f"/api/v1/research-engine/runs/{run_id}/stream"
        )
        assert response.status_code == 404
        stream_app.dependency_overrides.pop(get_db, None)

    def test_stream_returns_409_for_completed_run(
        self, stream_app, stream_client
    ):
        run_id = uuid.uuid4()
        bp_id = uuid.uuid4()
        mock_run = _make_run(id=run_id, blueprint_id=bp_id, status="completed")
        mock_bp = _make_blueprint(id=bp_id)
        db = _mock_db_returning(run_result=mock_run, blueprint_result=mock_bp)

        stream_app.dependency_overrides[get_db] = lambda: db

        response = stream_client.get(
            f"/api/v1/research-engine/runs/{run_id}/stream"
        )
        assert response.status_code == 409
        stream_app.dependency_overrides.pop(get_db, None)

    def test_stream_returns_409_for_failed_run(
        self, stream_app, stream_client
    ):
        run_id = uuid.uuid4()
        bp_id = uuid.uuid4()
        mock_run = _make_run(id=run_id, blueprint_id=bp_id, status="failed")
        mock_bp = _make_blueprint(id=bp_id)
        db = _mock_db_returning(run_result=mock_run, blueprint_result=mock_bp)

        stream_app.dependency_overrides[get_db] = lambda: db

        response = stream_client.get(
            f"/api/v1/research-engine/runs/{run_id}/stream"
        )
        assert response.status_code == 409
        stream_app.dependency_overrides.pop(get_db, None)

    def test_stream_returns_409_for_running_run(
        self, stream_app, stream_client
    ):
        run_id = uuid.uuid4()
        bp_id = uuid.uuid4()
        mock_run = _make_run(id=run_id, blueprint_id=bp_id, status="running")
        mock_bp = _make_blueprint(id=bp_id)
        db = _mock_db_returning(run_result=mock_run, blueprint_result=mock_bp)

        stream_app.dependency_overrides[get_db] = lambda: db

        response = stream_client.get(
            f"/api/v1/research-engine/runs/{run_id}/stream"
        )
        assert response.status_code == 409
        stream_app.dependency_overrides.pop(get_db, None)
