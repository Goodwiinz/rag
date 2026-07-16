"""
Workspace member management endpoints (Task 4.2 split of the former
monolithic ``backend/src/api/threads/workspaces.py``).
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.user import User
from src.models.workspace import WorkspaceMember, WorkspaceRole
from src.schemas.chat import (
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdate,
)

from .dependencies import _get_workspace_or_404
from .presenters import _member_to_response

router = APIRouter(prefix="/api/v2/workspaces", tags=["workspaces"])

# ============================================================================
# Workspace Member Endpoints
# ============================================================================


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_workspace_member(
    workspace_id: UUID,
    request: WorkspaceMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a member to a workspace"""
    workspace = await _get_workspace_or_404(db, workspace_id, current_user)

    if not workspace.can_user_admin(str(current_user.id)):
        raise HTTPException(
            status_code=403, detail="Insufficient permissions to add members"
        )

    # Look up any existing membership row, INCLUDING a soft-deleted one. The
    # uq_workspace_member (workspace_id, user_id) constraint is not partial, so
    # it still covers removed members; inserting a fresh row for a previously
    # removed user would hit the constraint and 500. Restore the row instead.
    stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == request.user_id,
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()

    if existing and not existing.is_deleted:
        raise HTTPException(status_code=400, detail="User is already a member")

    if existing:
        # Re-add a previously removed member by restoring the soft-deleted row.
        existing.restore()
        existing.role = request.role
        existing.invited_by_id = current_user.id
        existing.joined_at = datetime.utcnow()
        member = existing
    else:
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=request.user_id,
            role=request.role,
            invited_by_id=current_user.id,
        )
        db.add(member)

    await db.commit()
    await db.refresh(member)

    return _member_to_response(member)


@router.patch(
    "/{workspace_id}/members/{user_id}", response_model=WorkspaceMemberResponse
)
async def update_member_role(
    workspace_id: UUID,
    user_id: UUID,
    request: WorkspaceMemberUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a member's role"""
    workspace = await _get_workspace_or_404(db, workspace_id, current_user)

    if not workspace.can_user_admin(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id,
        WorkspaceMember.is_deleted == False,
    )
    result = await db.execute(stmt)
    member = result.scalars().first()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Prevent changing owner role
    if member.role == WorkspaceRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot change owner role")

    member.role = request.role
    member.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(member)

    return _member_to_response(member)


@router.delete(
    "/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a member from a workspace"""
    workspace = await _get_workspace_or_404(db, workspace_id, current_user)

    # Users can remove themselves, admins can remove others
    if str(user_id) != str(current_user.id) and not workspace.can_user_admin(
        str(current_user.id)
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id,
        WorkspaceMember.is_deleted == False,
    )
    result = await db.execute(stmt)
    member = result.scalars().first()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Prevent removing owner
    if member.role == WorkspaceRole.OWNER:
        raise HTTPException(status_code=400, detail="Cannot remove workspace owner")

    member.is_deleted = True
    member.deleted_at = datetime.utcnow()
    await db.commit()
