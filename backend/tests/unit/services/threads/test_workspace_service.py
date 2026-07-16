"""Characterize workspace_service.py (Task 4.3 consolidation).

Covers the two measured divergences between the pre-4.3 router-inline
workspace endpoints and ``ChatService`` (see the module's docstring):
``enforce_org_match`` (create) and ``filter_deleted_memberships`` (list).
Also proves the ``stamp_deleted_at`` delete flag and the permission-vs-not-
found ``PermissionError``/``None`` split every write method uses.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.models.workspace import WorkspaceMember, WorkspaceRole
from src.schemas.chat import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberUpdate,
    WorkspaceUpdate,
)
from src.services.threads import workspace_service

pytestmark = pytest.mark.integration


async def test_create_workspace_enforce_org_match_rejects_mismatch(
    db_session, user_factory
):
    owner = await user_factory()
    with pytest.raises(PermissionError):
        await workspace_service.create_workspace(
            db_session,
            WorkspaceCreate(name="x", is_public=False, organization_id=uuid4()),
            owner.id,
            owner.organization_id,
            enforce_org_match=True,
        )


async def test_create_workspace_old_default_trusts_requested_org(
    db_session, user_factory, organization_factory
):
    """``enforce_org_match=False`` (ChatService's pre-4.3 default) creates
    the workspace under the REQUESTED org even when it differs from the
    caller's own — the pre-existing (unenforced) behavior preserved for
    ChatService's own callers."""
    owner = await user_factory()
    foreign_org = await organization_factory()

    workspace = await workspace_service.create_workspace(
        db_session,
        WorkspaceCreate(name="x", is_public=False, organization_id=foreign_org.id),
        owner.id,
        owner.organization_id,
        enforce_org_match=False,
    )
    assert workspace.organization_id == foreign_org.id


async def test_create_workspace_enforce_org_match_allows_matching_org(
    db_session, user_factory
):
    owner = await user_factory()
    workspace = await workspace_service.create_workspace(
        db_session,
        WorkspaceCreate(
            name="x", is_public=False, organization_id=owner.organization_id
        ),
        owner.id,
        owner.organization_id,
        enforce_org_match=True,
    )
    assert workspace.organization_id == owner.organization_id
    assert any(str(m.user_id) == str(owner.id) for m in workspace.members)


async def test_list_workspaces_filter_deleted_memberships_flag(
    db_session, user_factory
):
    owner = await user_factory()
    workspace = await workspace_service.create_workspace(
        db_session,
        WorkspaceCreate(name="x", is_public=False),
        owner.id,
        owner.organization_id,
        enforce_org_match=True,
    )
    db_session.info["_created"]["workspaces"].append(workspace.id)

    # Soft-delete the owner's own membership row (simulating a removed member
    # whose row wasn't hard-deleted).
    membership = next(m for m in workspace.members if str(m.user_id) == str(owner.id))
    membership.is_deleted = True
    await db_session.commit()

    filtered, _total = await workspace_service.list_workspaces(
        db_session, owner.id, filter_deleted_memberships=True
    )
    assert workspace.id not in [w.id for w in filtered]

    unfiltered, _total = await workspace_service.list_workspaces(
        db_session, owner.id, filter_deleted_memberships=False
    )
    assert workspace.id in [w.id for w in unfiltered]


async def test_update_workspace_not_found_vs_forbidden(db_session, user_factory):
    owner = await user_factory()
    editor = await user_factory()  # a member, but not admin/owner
    workspace = await workspace_service.create_workspace(
        db_session,
        WorkspaceCreate(name="x", is_public=False),
        owner.id,
        owner.organization_id,
        enforce_org_match=True,
    )
    db_session.info["_created"]["workspaces"].append(workspace.id)
    db_session.add(
        WorkspaceMember(
            workspace_id=workspace.id, user_id=editor.id, role=WorkspaceRole.EDITOR
        )
    )
    await db_session.commit()
    db_session.expire(workspace, ["members"])

    assert (
        await workspace_service.update_workspace(
            db_session, uuid4(), WorkspaceUpdate(name="y"), owner.id
        )
    ) is None  # not found

    # editor can see the workspace (member) but can't admin it -> 403, not 404.
    with pytest.raises(PermissionError):
        await workspace_service.update_workspace(
            db_session, workspace.id, WorkspaceUpdate(name="y"), editor.id
        )


async def test_delete_workspace_stamp_deleted_at_flag(db_session, user_factory):
    owner = await user_factory()
    ws_stamped = await workspace_service.create_workspace(
        db_session,
        WorkspaceCreate(name="a", is_public=False),
        owner.id,
        owner.organization_id,
        enforce_org_match=True,
    )
    ws_unstamped = await workspace_service.create_workspace(
        db_session,
        WorkspaceCreate(name="b", is_public=False),
        owner.id,
        owner.organization_id,
        enforce_org_match=True,
    )
    db_session.info["_created"]["workspaces"].extend([ws_stamped.id, ws_unstamped.id])

    assert await workspace_service.delete_workspace(
        db_session, ws_stamped.id, owner.id, stamp_deleted_at=True
    )
    assert ws_stamped.deleted_at is not None

    assert await workspace_service.delete_workspace(
        db_session, ws_unstamped.id, owner.id, stamp_deleted_at=False
    )
    assert ws_unstamped.deleted_at is None


async def test_delete_workspace_only_owner(db_session, user_factory):
    owner = await user_factory()
    other_admin = await user_factory()
    workspace = await workspace_service.create_workspace(
        db_session,
        WorkspaceCreate(name="x", is_public=False),
        owner.id,
        owner.organization_id,
        enforce_org_match=True,
    )
    db_session.info["_created"]["workspaces"].append(workspace.id)
    db_session.add(
        WorkspaceMember(
            workspace_id=workspace.id, user_id=other_admin.id, role=WorkspaceRole.ADMIN
        )
    )
    await db_session.commit()
    db_session.expire(workspace, ["members"])

    with pytest.raises(PermissionError):
        await workspace_service.delete_workspace(
            db_session, workspace.id, other_admin.id
        )


async def test_add_member_restores_soft_deleted_row(db_session, user_factory):
    owner = await user_factory()
    target = await user_factory()
    workspace = await workspace_service.create_workspace(
        db_session,
        WorkspaceCreate(name="x", is_public=False),
        owner.id,
        owner.organization_id,
        enforce_org_match=True,
    )
    db_session.info["_created"]["workspaces"].append(workspace.id)

    member = await workspace_service.add_member(
        db_session,
        workspace.id,
        WorkspaceMemberCreate(user_id=target.id, role=WorkspaceRole.VIEWER),
        owner.id,
    )
    original_member_id = member.id

    await workspace_service.remove_member(db_session, workspace.id, target.id, owner.id)

    restored = await workspace_service.add_member(
        db_session,
        workspace.id,
        WorkspaceMemberCreate(user_id=target.id, role=WorkspaceRole.EDITOR),
        owner.id,
    )
    assert restored.id == original_member_id  # same row, restored not re-inserted
    assert restored.is_deleted is False
    # Compare by value: WorkspaceMemberCreate.role is schemas.chat.WorkspaceRole
    # (str, Enum); the ORM column is src.models.workspace.WorkspaceRole (a plain
    # PyEnum) — same string values, different classes, so `==` across them is
    # always False even when logically equal.
    assert restored.role.value == "editor"


async def test_update_member_role_rejects_owner_change(db_session, user_factory):
    owner = await user_factory()
    workspace = await workspace_service.create_workspace(
        db_session,
        WorkspaceCreate(name="x", is_public=False),
        owner.id,
        owner.organization_id,
        enforce_org_match=True,
    )
    db_session.info["_created"]["workspaces"].append(workspace.id)

    with pytest.raises(ValueError):
        await workspace_service.update_member_role(
            db_session,
            workspace.id,
            owner.id,
            WorkspaceMemberUpdate(role=WorkspaceRole.VIEWER),
            owner.id,
        )
