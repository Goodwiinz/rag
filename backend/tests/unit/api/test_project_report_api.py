"""Unit tests for the project-report endpoint authorization.

Guards the fix for the ``Collection.owner_id`` bug: the report endpoint now
scopes the project lookup to the caller's workspaces (ownership lives on
Workspace, not Collection) and returns a single 404 for both missing and
inaccessible projects (no existence disclosure). Mocked DB, no real Postgres.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Collection, User, UserRole


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.email = "owner@example.com"
    user.role = UserRole.USER
    user.is_active = True
    return user


@pytest.fixture
def mock_project():
    project = MagicMock(spec=Collection)
    project.id = uuid4()
    project.name = "Test Research Project"
    project.description = "A test project"
    project.workspace_id = uuid4()
    project.created_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    return project


@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    return db


def _scalar_one_or_none(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _scalars_all(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_report_renders_for_owner(mock_user, mock_project, mock_db):
    """Owner gets a rendered HTML report (200)."""
    from src.api.research.project_report import render_project_report

    # 1) owner-scoped project lookup, 2) docs query, 3) notes query
    mock_db.execute.side_effect = [
        _scalar_one_or_none(mock_project),
        _scalars_all([]),
        _scalars_all([]),
    ]

    with patch(
        "src.api.research.project_report._scan_recent_threads", return_value=[]
    ):
        response = await render_project_report(
            mock_project.id, current_user=mock_user, db=mock_db
        )

    assert isinstance(response, HTMLResponse)
    assert response.status_code == 200
    assert b"Test Research Project" in response.body


@pytest.mark.unit
@pytest.mark.asyncio
async def test_report_404_when_not_owned_or_missing(mock_user, mock_db):
    """A project in another user's workspace (or absent) yields 404 — the
    scoped query returns nothing, so missing and forbidden are indistinguishable.
    """
    from src.api.research.project_report import render_project_report

    mock_db.execute.side_effect = [_scalar_one_or_none(None)]

    with pytest.raises(HTTPException) as exc_info:
        await render_project_report(
            uuid4(), current_user=mock_user, db=mock_db
        )

    assert exc_info.value.status_code == 404
    assert "not found or access denied" in exc_info.value.detail
    # Lookup must short-circuit: no docs/notes queries after a denied project.
    assert mock_db.execute.await_count == 1
