"""Re-adding a previously removed workspace member must restore the soft-deleted
row, not insert a new one.

Regression guard for the Hunt-5 finding: remove_workspace_member soft-deletes
(is_deleted=True) but the uq_workspace_member (workspace_id, user_id) constraint
is not partial, so a fresh INSERT for a removed user hit the constraint -> 500.
A removed user could never be re-added. Mocked DB, no real Postgres.

Task 4.3 moved this persistence into
``src/services/threads/workspace_service.add_member``, which fetches the
workspace via the shared ``workspace_access.get_workspace`` funnel — these
tests patch that one seam instead of the pre-4.3 router-inline
``_get_workspace_or_404``.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from src.models.workspace import WorkspaceMember
from src.schemas.chat import WorkspaceMemberCreate, WorkspaceRole

GET_WORKSPACE = "src.services.threads.workspace_access.get_workspace"


def _execute_returning(value: object) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.first.return_value = value
    return result


def _admin_workspace() -> MagicMock:
    ws = MagicMock()
    ws.can_user_admin.return_value = True
    return ws


@pytest.mark.unit
@pytest.mark.asyncio
async def test_readd_restores_soft_deleted_member() -> None:
    from src.api.threads.workspaces import add_workspace_member

    workspace_id, target_id, admin_id = uuid4(), uuid4(), uuid4()
    existing = MagicMock(spec=WorkspaceMember)
    existing.is_deleted = True

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_execute_returning(existing))
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with (
        patch(GET_WORKSPACE, new=AsyncMock(return_value=_admin_workspace())),
        patch(
            "src.api.threads.workspace_routes.members._member_to_response",
            return_value="OK",
        ),
    ):
        result = await add_workspace_member(
            workspace_id=workspace_id,
            request=WorkspaceMemberCreate(user_id=target_id, role=WorkspaceRole.EDITOR),
            db=db,
            current_user=SimpleNamespace(id=admin_id),
        )

    assert result == "OK"
    existing.restore.assert_called_once()  # restored, not re-inserted
    assert existing.role == WorkspaceRole.EDITOR
    assert existing.invited_by_id == admin_id
    assert isinstance(existing.joined_at, datetime)  # re-add = joined now
    db.add.assert_not_called()
    db.commit.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_readd_live_member_still_409s_as_400() -> None:
    from src.api.threads.workspaces import add_workspace_member

    existing = MagicMock(spec=WorkspaceMember)
    existing.is_deleted = False  # active membership

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_execute_returning(existing))
    db.add = MagicMock()
    db.commit = AsyncMock()

    with patch(GET_WORKSPACE, new=AsyncMock(return_value=_admin_workspace())):
        with pytest.raises(HTTPException) as exc_info:
            await add_workspace_member(
                workspace_id=uuid4(),
                request=WorkspaceMemberCreate(
                    user_id=uuid4(), role=WorkspaceRole.VIEWER
                ),
                db=db,
                current_user=SimpleNamespace(id=uuid4()),
            )

    assert exc_info.value.status_code == 400
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_add_brand_new_member_inserts_row() -> None:
    from src.api.threads.workspaces import add_workspace_member

    # workspace_service.add_member issues three SELECTs for a brand-new
    # member: (0) R5-L9 target-user existence check, (1) the existing-row
    # lookup (none found), (2) a re-fetch with `.user` eager-loaded after
    # insert+commit.
    new_member = MagicMock(spec=WorkspaceMember)
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _execute_returning(uuid4()),  # user exists
            _execute_returning(None),
            _execute_returning(new_member),
        ]
    )
    db.add = MagicMock()
    db.commit = AsyncMock()

    with (
        patch(GET_WORKSPACE, new=AsyncMock(return_value=_admin_workspace())),
        patch(
            "src.api.threads.workspace_routes.members._member_to_response",
            return_value="OK",
        ),
    ):
        result = await add_workspace_member(
            workspace_id=uuid4(),
            request=WorkspaceMemberCreate(user_id=uuid4(), role=WorkspaceRole.VIEWER),
            db=db,
            current_user=SimpleNamespace(id=uuid4()),
        )

    assert result == "OK"
    db.add.assert_called_once()
    db.commit.assert_awaited_once()
