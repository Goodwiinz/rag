"""Unit tests for ProjectService."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.research.project_service import ProjectService
from src.shared.research_schemas import ProjectCreate, ProjectUpdate, ResearchStatus


@pytest.fixture
def mock_db() -> AsyncMock:
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_list_projects_returns_filtered_paginated_result(mock_db: AsyncMock) -> None:
    service = ProjectService(mock_db)
    workspace_id = uuid4()
    user_id = uuid4()

    workspace_result = MagicMock()
    workspace_result.all.return_value = [(workspace_id,)]

    count_result = MagicMock()
    count_result.scalar.return_value = 2

    project_a = MagicMock()
    project_b = MagicMock()
    projects_result = MagicMock()
    projects_result.scalars.return_value.all.return_value = [project_a, project_b]

    mock_db.execute.side_effect = [workspace_result, count_result, projects_result]

    result = await service.list_projects(
        user_id=user_id,
        project_status="active",
        skip=0,
        limit=10,
    )

    assert result["total"] == 2
    assert result["page"] == 1
    assert result["size"] == 10
    assert len(result["projects"]) == 2
    assert result["has_next"] is False
    assert result["has_prev"] is False


@pytest.mark.asyncio
async def test_create_project_enforces_private_true(mock_db: AsyncMock) -> None:
    service = ProjectService(mock_db)
    workspace_id = uuid4()
    user_id = uuid4()

    workspace_result = MagicMock()
    workspace_result.scalar_one_or_none.return_value = object()
    mock_db.execute.return_value = workspace_result

    payload = ProjectCreate(
        workspace_id=workspace_id,
        name="ML Healthcare",
    )

    await service.create_project(user_id=user_id, project_data=payload)

    created_project = mock_db.add.call_args[0][0]
    assert created_project.name == "ML Healthcare"
    assert created_project.workspace_id == workspace_id
    assert created_project.is_private is True
    assert created_project.project_type == "research"
    assert created_project.research_status == "active"
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_project_rejects_invalid_status_transition(
    mock_db: AsyncMock,
) -> None:
    service = ProjectService(mock_db)
    user_id = uuid4()
    project_id = uuid4()

    project = MagicMock()
    project.research_status = "completed"

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project
    mock_db.execute.return_value = project_result

    with pytest.raises(HTTPException) as exc_info:
        await service.update_project(
            user_id=user_id,
            project_id=project_id,
            project_data=ProjectUpdate(research_status=ResearchStatus.ACTIVE),
        )

    assert exc_info.value.status_code == 400
    assert "Invalid status transition" in exc_info.value.detail
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_project_allows_valid_status_transition(mock_db: AsyncMock) -> None:
    service = ProjectService(mock_db)
    user_id = uuid4()
    project_id = uuid4()

    project = MagicMock()
    project.research_status = "active"

    project_result = MagicMock()
    project_result.scalar_one_or_none.return_value = project
    mock_db.execute.return_value = project_result

    updated_project = await service.update_project(
        user_id=user_id,
        project_id=project_id,
        project_data=ProjectUpdate(research_status=ResearchStatus.PAUSED),
    )

    assert updated_project is project
    assert project.research_status == "paused"
    assert project.is_private is True
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once_with(project)
