from uuid import uuid4

from src.models.thread import Thread
from src.models.user import User
from src.models.workspace import Workspace, WorkspaceMember, WorkspaceRole


def test_workspace_ignores_soft_deleted_membership_for_access_helpers():
    active_user_id = uuid4()
    deleted_user_id = uuid4()
    workspace = Workspace(
        id=uuid4(),
        name="Scoped Workspace",
        owner_id=uuid4(),
        members=[
            WorkspaceMember(
                user_id=active_user_id,
                role=WorkspaceRole.EDITOR,
                is_deleted=False,
            ),
            WorkspaceMember(
                user_id=deleted_user_id,
                role=WorkspaceRole.ADMIN,
                is_deleted=True,
            ),
        ],
    )

    assert workspace.is_member(str(active_user_id)) is True
    assert workspace.can_user_edit(str(active_user_id)) is True
    assert workspace.is_member(str(deleted_user_id)) is False
    assert workspace.get_member_role(str(deleted_user_id)) is None
    assert workspace.can_user_edit(str(deleted_user_id)) is False
    assert workspace.can_user_admin(str(deleted_user_id)) is False


def test_workspace_owner_fallback_still_allows_access_without_member_row():
    owner_id = uuid4()
    workspace = Workspace(id=uuid4(), name="Owner Workspace", owner_id=owner_id)

    assert workspace.is_member(str(owner_id)) is False
    assert workspace.can_user_edit(str(owner_id)) is True
    assert workspace.can_user_admin(str(owner_id)) is True


def test_workspace_related_schema_contracts_are_explicit():
    assert hasattr(WorkspaceMember, "is_deleted")
    assert User.__table__.c.organization_id.nullable is True
    assert Thread.__table__.c.source_project_id.nullable is True
    assert Thread.__table__.c.rag_document_scope.comment == (
        'Document IDs for RAG filtering. Format: {"document_ids": ["uuid1", "uuid2"]}'
    )
