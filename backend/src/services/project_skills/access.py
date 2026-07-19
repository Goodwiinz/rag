"""Workspace-scoped authorization for project skills."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import Collection, Workspace


class ProjectSkillAccessDenied(PermissionError):
    """The current user is not allowed to perform the requested workspace action."""


class ProjectSkillNotFound(LookupError):
    """The project is absent or deliberately hidden from an unauthorized caller."""


def assert_workspace_access(
    workspace: Workspace, user_id: UUID, capability: str
) -> None:
    """Enforce the project workspace's roles without substituting org membership."""
    workspace_user_id = str(user_id)
    if capability == "read":
        allowed = workspace.is_member(workspace_user_id) or str(
            workspace.owner_id
        ) == str(user_id)
    elif capability == "edit":
        allowed = workspace.can_user_edit(workspace_user_id)
    elif capability == "admin":
        allowed = workspace.can_user_admin(workspace_user_id)
    else:
        raise ValueError(f"unknown project-skill capability: {capability}")
    if not allowed:
        raise ProjectSkillAccessDenied("workspace role does not permit this action")


async def get_authorized_project(
    session: AsyncSession, *, project_id: UUID, user_id: UUID, capability: str
) -> Collection:
    """Load a project plus workspace membership, returning not-found before access leaks."""
    project = cast(
        Collection | None,
        await session.scalar(
            select(Collection)
            .where(Collection.id == project_id, Collection.is_deleted.is_(False))
            .options(selectinload(Collection.workspace).selectinload(Workspace.members))
        ),
    )
    if project is None or project.workspace is None:
        raise ProjectSkillNotFound("project not found")
    try:
        assert_workspace_access(project.workspace, user_id, capability)
    except ProjectSkillAccessDenied as error:
        raise ProjectSkillNotFound("project not found") from error
    return project
