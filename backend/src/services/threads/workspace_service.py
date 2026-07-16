"""
Workspace and workspace-member persistence (Task 4.3 consolidation).

Canonical owner for workspace CRUD and member management — the router-inline
copy in ``backend/src/api/threads/workspace_routes/{workspaces,members}.py``
and ``ChatService``'s workspace methods both called into this module's
predecessor logic independently; this is now the one implementation.

Divergence flags (see docs/plans/2026-07-15-maintainability-foundation.md
Task 4.3 + its 2026-07-16 amendment A2): the router and ``ChatService`` diverged
on two workspace concerns. Router semantics are canonical for the endpoints the
router serves; ``ChatService``'s own (pre-4.3) callers keep their observed
behavior via an explicit flag defaulting to the old value:

- ``enforce_org_match`` (create): router raises on a cross-org create
  request; old ``ChatService.create_workspace`` trusted the caller's
  ``organization_id`` verbatim. Default ``False`` (old).
- ``filter_deleted_memberships`` (list): router excludes a workspace the
  caller was removed from (soft-deleted ``WorkspaceMember`` row); old
  ``ChatService.list_workspaces`` did not filter it, so a removed member
  still saw the workspace. Default ``False`` (old).

Workspace member management (add/update/remove) has no ``ChatService``
duplicate to reconcile — it was router-only before this split — so those
three functions are a straight move, no flag.
"""

from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from src.schemas.chat import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberUpdate,
    WorkspaceUpdate,
)
from src.services.threads import workspace_access

# =============================================================================
# Workspace CRUD
# =============================================================================


async def create_workspace(
    db: AsyncSession,
    data: WorkspaceCreate,
    owner_id: UUID,
    user_organization_id: Optional[UUID],
    *,
    enforce_org_match: bool = False,
) -> Workspace:
    """Create a workspace + its owner membership row.

    Raises ``PermissionError`` when ``enforce_org_match=True`` and the
    request's ``organization_id`` doesn't match the caller's own org (the
    router turns this into a 403). With ``enforce_org_match=False`` (the old
    ``ChatService`` default), ``data.organization_id`` is trusted verbatim.
    """
    if enforce_org_match:
        if data.organization_id is not None and str(data.organization_id) != str(
            user_organization_id
        ):
            raise PermissionError(
                "Cannot create workspace for a different organization"
            )
        organization_id = user_organization_id
    else:
        organization_id = data.organization_id

    workspace = Workspace(
        name=data.name,
        description=data.description,
        is_public=data.is_public,
        owner_id=owner_id,
        organization_id=organization_id,
    )
    db.add(workspace)
    db.add(
        WorkspaceMember(workspace=workspace, user_id=owner_id, role=WorkspaceRole.OWNER)
    )
    await db.commit()

    # Re-fetch with full eager load — the response/presenter reads
    # member/conversation/collection counts immediately after create.
    created = await workspace_access.get_workspace(db, workspace.id, owner_id)
    if created is None:
        raise RuntimeError(
            "Workspace lookup failed immediately after creation"
        )  # pragma: no cover
    return created


async def list_workspaces(
    db: AsyncSession,
    user_id: UUID,
    *,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
    filter_deleted_memberships: bool = False,
) -> Tuple[List[Workspace], int]:
    """List workspaces the caller is a member of.

    Always eager-loads members/conversations/collections — the count fields
    every ``WorkspaceResponse`` renders.
    """
    base_conditions = [
        WorkspaceMember.user_id == user_id,
        Workspace.is_deleted == False,  # noqa: E712
    ]
    if filter_deleted_memberships:
        base_conditions.append(WorkspaceMember.is_deleted == False)  # noqa: E712
    if not include_archived:
        base_conditions.append(Workspace.is_archived == False)  # noqa: E712

    count_stmt = (
        select(func.count(Workspace.id)).join(WorkspaceMember).where(*base_conditions)
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Workspace)
        .options(
            selectinload(Workspace.members),
            selectinload(Workspace.conversations),
            selectinload(Workspace.collections),
        )
        .join(WorkspaceMember)
        .where(*base_conditions)
        .order_by(desc(Workspace.updated_at))
        .offset(offset)
        .limit(limit)
    )
    workspaces = (await db.execute(stmt)).scalars().all()
    return list(workspaces), total


async def update_workspace(
    db: AsyncSession, workspace_id: UUID, data: WorkspaceUpdate, user_id: UUID
) -> Optional[Workspace]:
    """Update a workspace. ``None`` if not found/accessible; raises
    ``PermissionError`` if found but the caller lacks admin rights."""
    workspace = await workspace_access.get_workspace(db, workspace_id, user_id)
    if not workspace:
        return None
    if not workspace.can_user_admin(str(user_id)):
        raise PermissionError("Insufficient permissions")

    if data.name is not None:
        workspace.name = data.name
    if data.description is not None:
        workspace.description = data.description
    if data.is_public is not None:
        workspace.is_public = data.is_public
    if data.is_archived is not None:
        workspace.is_archived = data.is_archived

    workspace.updated_at = datetime.utcnow()
    await db.commit()
    # No db.refresh(): every mutated field is a Python-side assignment
    # already reflecting final state, and a bare refresh() would expire the
    # members/conversations/collections eager-loaded above (untouched by
    # this mutation) — the presenter reads all three right after, and an
    # expired-then-accessed relationship MissingGreenlets under the async
    # session.
    return workspace


async def delete_workspace(
    db: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    *,
    stamp_deleted_at: bool = False,
) -> Optional[bool]:
    """Soft-delete a workspace. ``None`` if not found; raises
    ``PermissionError`` if found but the caller isn't the owner.

    ``stamp_deleted_at=True`` (router-canonical) also sets ``deleted_at``.
    ``False`` (old ``ChatService`` default) leaves it ``NULL``, matching the
    pre-4.3 divergence recorded for existing ``ChatService`` callers.
    """
    workspace = await workspace_access.get_workspace(db, workspace_id, user_id)
    if not workspace:
        return None
    if str(workspace.owner_id) != str(user_id):
        raise PermissionError("Only the owner can delete a workspace")

    workspace.is_deleted = True
    if stamp_deleted_at:
        workspace.deleted_at = datetime.utcnow()
    workspace.updated_at = datetime.utcnow()
    await db.commit()
    return True


# =============================================================================
# Workspace member management (router-only before this split; no flag needed)
# =============================================================================


async def add_member(
    db: AsyncSession,
    workspace_id: UUID,
    data: WorkspaceMemberCreate,
    current_user_id: UUID,
) -> Optional[WorkspaceMember]:
    """Add (or restore) a workspace member.

    ``None`` if the workspace isn't found/accessible. Raises
    ``PermissionError`` if the caller can't admin the workspace, or
    ``ValueError`` if the target user is already an active member — both
    ports of the router's exact checks.
    """
    workspace = await workspace_access.get_workspace(db, workspace_id, current_user_id)
    if not workspace:
        return None
    if not workspace.can_user_admin(str(current_user_id)):
        raise PermissionError("Insufficient permissions to add members")

    stmt = (
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.user))
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == data.user_id,
        )
    )
    existing = (await db.execute(stmt)).scalars().first()

    if existing and not existing.is_deleted:
        raise ValueError("User is already a member")

    if existing:
        # Restore a previously removed member. uq_workspace_member is not a
        # partial index, so inserting a fresh row for a re-added user would
        # hit the unique constraint and 500 — restore the soft-deleted row.
        existing.restore()
        existing.role = data.role
        existing.invited_by_id = current_user_id
        existing.joined_at = datetime.utcnow()
        member = existing
        await db.commit()
    else:
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=data.user_id,
            role=data.role,
            invited_by_id=current_user_id,
        )
        db.add(member)
        await db.commit()
        # A freshly-constructed member's `.user` was never loaded (it's a
        # many-to-one that would otherwise lazy-load on first access, which
        # MissingGreenlets under the async session) — re-fetch it eager-loaded
        # rather than db.refresh(), which would only re-expire it again.
        member = (await db.execute(stmt)).scalars().first()
    return member


async def update_member_role(
    db: AsyncSession,
    workspace_id: UUID,
    target_user_id: UUID,
    data: WorkspaceMemberUpdate,
    current_user_id: UUID,
) -> Optional[WorkspaceMember]:
    """Update a member's role. ``None`` if workspace/member not found.
    Raises ``PermissionError``/``ValueError`` matching the router's checks."""
    workspace = await workspace_access.get_workspace(db, workspace_id, current_user_id)
    if not workspace:
        return None
    if not workspace.can_user_admin(str(current_user_id)):
        raise PermissionError("Insufficient permissions")

    stmt = (
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.user))
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == target_user_id,
            WorkspaceMember.is_deleted == False,  # noqa: E712
        )
    )
    member = (await db.execute(stmt)).scalars().first()
    if not member:
        return None
    if member.role == WorkspaceRole.OWNER:
        raise ValueError("Cannot change owner role")

    member.role = data.role
    member.updated_at = datetime.utcnow()
    await db.commit()
    # No db.refresh(): `.user` is eager-loaded above and untouched by this
    # mutation; refresh() would only expire it again (MissingGreenlet on the
    # presenter's next access under the async session).
    return member


async def remove_member(
    db: AsyncSession,
    workspace_id: UUID,
    target_user_id: UUID,
    current_user_id: UUID,
) -> Optional[bool]:
    """Remove (soft-delete) a workspace member. ``None`` if workspace/member
    not found. Raises ``PermissionError``/``ValueError`` matching the
    router's checks (self-removal always allowed; owner can't be removed)."""
    workspace = await workspace_access.get_workspace(db, workspace_id, current_user_id)
    if not workspace:
        return None
    if str(target_user_id) != str(current_user_id) and not workspace.can_user_admin(
        str(current_user_id)
    ):
        raise PermissionError("Insufficient permissions")

    stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == target_user_id,
        WorkspaceMember.is_deleted == False,  # noqa: E712
    )
    member = (await db.execute(stmt)).scalars().first()
    if not member:
        return None
    if member.role == WorkspaceRole.OWNER:
        raise ValueError("Cannot remove workspace owner")

    member.is_deleted = True
    member.deleted_at = datetime.utcnow()
    await db.commit()
    return True
