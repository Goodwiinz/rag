"""
Workspace CRUD endpoints (Task 4.2 split of the former monolithic
``backend/src/api/threads/workspaces.py``).
"""

import logging
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.user import User
from src.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from src.schemas.chat import (
    WorkspaceCreate,
    WorkspaceDetailResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)

from .dependencies import _get_workspace_or_404
from .presenters import _workspace_to_detail_response, _workspace_to_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2/workspaces", tags=["workspaces"])

# ============================================================================
# Workspace Endpoints
# ============================================================================


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new workspace"""
    user_org_id = getattr(current_user, "organization_id", None)
    if request.organization_id is not None and str(request.organization_id) != str(
        user_org_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create workspace for a different organization",
        )

    workspace = Workspace(
        name=request.name,
        description=request.description,
        is_public=request.is_public,
        owner_id=current_user.id,
        organization_id=user_org_id,
    )
    db.add(workspace)

    # Add owner as member with OWNER role
    member = WorkspaceMember(
        workspace=workspace, user_id=current_user.id, role=WorkspaceRole.OWNER
    )
    db.add(member)

    await db.commit()

    # Re-fetch workspace with eager-loaded relationships to avoid greenlet errors
    stmt = (
        select(Workspace)
        .options(
            selectinload(Workspace.members),
            selectinload(Workspace.conversations),
            selectinload(Workspace.collections),
        )
        .where(Workspace.id == workspace.id)
    )
    result = await db.execute(stmt)
    workspace = result.scalars().first()

    logger.info(f"Workspace '{workspace.name}' created by user {current_user.id}")

    return _workspace_to_response(workspace)


@router.get("", response_model=List[WorkspaceResponse])
async def list_workspaces(
    include_archived: bool = Query(False, description="Include archived workspaces"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List workspaces accessible by the current user"""
    stmt = (
        select(Workspace)
        .options(
            selectinload(Workspace.members),
            selectinload(Workspace.conversations),
            selectinload(Workspace.collections),
        )
        .join(WorkspaceMember)
        .where(
            WorkspaceMember.user_id == current_user.id,
            WorkspaceMember.is_deleted == False,
            Workspace.is_deleted == False,
        )
    )

    if not include_archived:
        stmt = stmt.where(Workspace.is_archived == False)

    stmt = stmt.order_by(Workspace.updated_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    workspaces = result.scalars().all()

    return [_workspace_to_response(w) for w in workspaces]


@router.get("/{workspace_id}", response_model=WorkspaceDetailResponse)
async def get_workspace(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get workspace details with members"""
    workspace = await _get_workspace_or_404(db, workspace_id, current_user)

    return _workspace_to_detail_response(workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: UUID,
    request: WorkspaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update workspace details"""
    workspace = await _get_workspace_or_404(db, workspace_id, current_user)

    # Check permission
    if not workspace.can_user_admin(str(current_user.id)):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Update fields
    if request.name is not None:
        workspace.name = request.name
    if request.description is not None:
        workspace.description = request.description
    if request.is_public is not None:
        workspace.is_public = request.is_public
    if request.is_archived is not None:
        workspace.is_archived = request.is_archived

    workspace.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(workspace)

    return _workspace_to_response(workspace)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a workspace"""
    workspace = await _get_workspace_or_404(db, workspace_id, current_user)

    # Only owner can delete
    if str(workspace.owner_id) != str(current_user.id):
        raise HTTPException(
            status_code=403, detail="Only the owner can delete a workspace"
        )

    workspace.is_deleted = True
    workspace.deleted_at = datetime.utcnow()
    await db.commit()

    logger.info(f"Workspace {workspace_id} deleted by user {current_user.id}")
