"""An admin must not be able to mint a second OWNER member (R5-H4).

remove_member and update_member_role both refuse rows whose role is OWNER,
so a member created or promoted with role=owner would hold admin rights
forever with no API path to demote or remove them — only DB surgery.
add_member/update_member_role must therefore reject role=owner up front.

Mocked DB, no real Postgres (same harness as test_workspace_member_readd).
"""

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.models.user import User
from src.schemas.chat import WorkspaceMemberCreate, WorkspaceMemberUpdate, WorkspaceRole

GET_WORKSPACE = "src.services.threads.workspace_access.get_workspace"


def _admin_workspace() -> MagicMock:
    ws = MagicMock()
    ws.can_user_admin.return_value = True
    return ws


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_member_rejects_owner_role() -> None:
    from src.api.threads.workspaces import add_workspace_member

    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    with patch(GET_WORKSPACE, new=AsyncMock(return_value=_admin_workspace())):
        with pytest.raises(HTTPException) as exc_info:
            await add_workspace_member(
                workspace_id=uuid4(),
                request=WorkspaceMemberCreate(
                    user_id=uuid4(), role=WorkspaceRole.OWNER
                ),
                db=db,
                current_user=cast(User, SimpleNamespace(id=uuid4())),
            )

    assert exc_info.value.status_code == 400
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_member_role_rejects_owner_role() -> None:
    from src.api.threads.workspace_routes.members import update_member_role

    db = AsyncMock()
    db.commit = AsyncMock()

    with patch(GET_WORKSPACE, new=AsyncMock(return_value=_admin_workspace())):
        with pytest.raises(HTTPException) as exc_info:
            await update_member_role(
                workspace_id=uuid4(),
                user_id=uuid4(),
                request=WorkspaceMemberUpdate(role=WorkspaceRole.OWNER),
                db=db,
                current_user=cast(User, SimpleNamespace(id=uuid4())),
            )

    assert exc_info.value.status_code == 400
    db.commit.assert_not_called()
