"""Characterize collection_service.py (Task 4.3 consolidation).

Unlike the other resource services in this task, ``ChatService``'s five
collection methods have zero production callers and two carry real bugs (see
the module docstring) — these tests prove the bugs are fixed unconditionally
(no compatibility flag): per-document organization ownership on attach, and
soft- (not hard-) delete on remove.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from src.schemas.chat import CollectionCreate, CollectionUpdate
from src.services.threads import collection_service

pytestmark = pytest.mark.integration


async def _make_workspace(db_session, owner):
    ws = Workspace(name="ws", owner_id=owner.id, organization_id=owner.organization_id)
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)
    db_session.info["_created"]["workspaces"].append(ws.id)
    return ws


async def _make_document(db_session, organization_id, user, *, title="doc"):
    from src.models.document import Document, DocumentType

    doc = Document(
        title=title,
        filename="f.pdf",
        file_path="x/f.pdf",
        file_size_bytes=1,
        mime_type="application/pdf",
        document_type=DocumentType.PDF,
        organization_id=organization_id,
        uploaded_by_user_id=user.id,
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


async def test_create_collection_only_attaches_owned_documents(
    db_session, user_factory, organization_factory
):
    owner = await user_factory()
    other_org = await organization_factory()
    other_user = await user_factory(organization=other_org)
    ws = await _make_workspace(db_session, owner)

    owned_doc = await _make_document(db_session, owner.organization_id, owner)
    foreign_doc = await _make_document(db_session, other_org.id, other_user)

    collection = await collection_service.create_collection(
        db_session,
        CollectionCreate(
            workspace_id=ws.id, name="c", document_ids=[owned_doc.id, foreign_doc.id]
        ),
        owner.id,
    )

    attached_ids = {cd.document_id for cd in collection.documents}
    assert attached_ids == {owned_doc.id}


async def test_add_documents_to_collection_rejects_foreign_org_document(
    db_session, user_factory, organization_factory
):
    owner = await user_factory()
    other_org = await organization_factory()
    other_user = await user_factory(organization=other_org)
    ws = await _make_workspace(db_session, owner)
    collection = await collection_service.create_collection(
        db_session, CollectionCreate(workspace_id=ws.id, name="c"), owner.id
    )
    foreign_doc = await _make_document(db_session, other_org.id, other_user)

    updated = await collection_service.add_documents_to_collection(
        db_session, collection.id, [foreign_doc.id], owner.id
    )
    assert updated.documents == []


async def test_remove_documents_soft_deletes_not_hard_deletes(db_session, user_factory):
    owner = await user_factory()
    ws = await _make_workspace(db_session, owner)
    doc = await _make_document(db_session, owner.organization_id, owner)
    collection = await collection_service.create_collection(
        db_session,
        CollectionCreate(workspace_id=ws.id, name="c", document_ids=[doc.id]),
        owner.id,
    )
    collection_doc_id = collection.documents[0].id

    await collection_service.remove_documents_from_collection(
        db_session, collection.id, [doc.id], owner.id
    )

    from sqlalchemy import select

    from src.models.collection import CollectionDocument

    row = (
        await db_session.execute(
            select(CollectionDocument).where(CollectionDocument.id == collection_doc_id)
        )
    ).scalar_one_or_none()
    assert row is not None  # still exists (soft-deleted), not hard-deleted
    assert row.is_deleted is True
    assert row.deleted_at is not None


async def test_update_collection_rejects_mismatched_workspace_id(
    db_session, user_factory
):
    owner = await user_factory()
    ws_a = await _make_workspace(db_session, owner)
    ws_b = await _make_workspace(db_session, owner)
    collection = await collection_service.create_collection(
        db_session, CollectionCreate(workspace_id=ws_b.id, name="c"), owner.id
    )

    assert (
        await collection_service.update_collection(
            db_session,
            collection.id,
            CollectionUpdate(name="new"),
            owner.id,
            workspace_id=ws_a.id,
        )
    ) is None

    updated = await collection_service.update_collection(
        db_session,
        collection.id,
        CollectionUpdate(name="new"),
        owner.id,
        workspace_id=ws_b.id,
    )
    assert updated.name == "new"


async def test_delete_collection_not_found_vs_forbidden(db_session, user_factory):
    owner = await user_factory()
    viewer = await user_factory()
    ws = await _make_workspace(db_session, owner)
    db_session.add(
        WorkspaceMember(
            workspace_id=ws.id, user_id=viewer.id, role=WorkspaceRole.VIEWER
        )
    )
    await db_session.commit()
    collection = await collection_service.create_collection(
        db_session, CollectionCreate(workspace_id=ws.id, name="c"), owner.id
    )

    assert (
        await collection_service.delete_collection(db_session, uuid4(), owner.id)
    ) is None

    with pytest.raises(PermissionError):
        await collection_service.delete_collection(db_session, collection.id, viewer.id)
