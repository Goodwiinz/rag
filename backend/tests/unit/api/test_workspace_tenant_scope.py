from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, MagicMock

from src.models.workspace import Workspace


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class _ExecuteResult:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return _ScalarResult(self.value)


def _db_that_refetches_created_workspace():
    captured = {}
    db = AsyncMock()
    now = datetime.now(timezone.utc)

    def add(entity):
        if isinstance(entity, Workspace):
            if entity.id is None:
                entity.id = uuid4()
            entity.is_archived = False
            entity.created_at = now
            entity.updated_at = now
            entity.members = []
            entity.conversations = []
            entity.collections = []
            captured["workspace"] = entity

    async def execute(_stmt):
        return _ExecuteResult(captured["workspace"])

    db.add = MagicMock(side_effect=add)
    db.execute = AsyncMock(side_effect=execute)
    db.commit = AsyncMock()
    return db, captured


@pytest.mark.asyncio
async def test_create_workspace_uses_current_user_organization_when_omitted():
    from src.api.threads.workspaces import create_workspace
    from src.schemas.chat import WorkspaceCreate

    org_id = uuid4()
    db, captured = _db_that_refetches_created_workspace()
    current_user = SimpleNamespace(id=uuid4(), organization_id=org_id)

    response = await create_workspace(
        WorkspaceCreate(name="Scoped", is_public=False),
        db=db,
        current_user=current_user,
    )

    assert captured["workspace"].organization_id == org_id
    assert response.organization_id == org_id


@pytest.mark.asyncio
async def test_create_workspace_rejects_mismatched_organization_id():
    from src.api.threads.workspaces import create_workspace
    from src.schemas.chat import WorkspaceCreate

    current_user = SimpleNamespace(id=uuid4(), organization_id=uuid4())
    db, _captured = _db_that_refetches_created_workspace()

    with pytest.raises(HTTPException) as exc_info:
        await create_workspace(
            WorkspaceCreate(
                name="Cross Tenant",
                is_public=False,
                organization_id=uuid4(),
            ),
            db=db,
            current_user=current_user,
        )

    assert exc_info.value.status_code == 403
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_workspace_allows_personal_workspace_without_user_org():
    from src.api.threads.workspaces import create_workspace
    from src.schemas.chat import WorkspaceCreate

    db, captured = _db_that_refetches_created_workspace()
    current_user = SimpleNamespace(id=uuid4(), organization_id=None)

    response = await create_workspace(
        WorkspaceCreate(name="Personal", is_public=False),
        db=db,
        current_user=current_user,
    )

    assert captured["workspace"].organization_id is None
    assert response.organization_id is None
