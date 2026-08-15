"""Project-scoped graph reads must honor private project ownership."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.search import knowledge_graph as kg
from src.models.collection import Collection, CollectionDocument
from src.models.document import Document, DocumentType
from src.models.workspace import Workspace

pytestmark = pytest.mark.unit


def test_project_scope_rejects_another_users_project():
    import src.models  # noqa: F401 - register all foreign-key targets
    from src.models.base import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    owner_id, other_user_id, org_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with Session() as db:
        owned_workspace = Workspace(name="Owned", owner_id=owner_id)
        other_workspace = Workspace(name="Other", owner_id=other_user_id)
        db.add_all([owned_workspace, other_workspace])
        db.flush()

        owned_project = Collection(name="Owned", workspace_id=owned_workspace.id)
        other_project = Collection(name="Other", workspace_id=other_workspace.id)
        db.add_all([owned_project, other_project])
        db.flush()

        owned_doc = Document(
            title="Owned",
            filename="owned.txt",
            file_path="local:///owned.txt",
            file_size_bytes=1,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=org_id,
        )
        other_doc = Document(
            title="Other",
            filename="other.txt",
            file_path="local:///other.txt",
            file_size_bytes=1,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=org_id,
        )
        removed_doc = Document(
            title="Removed",
            filename="removed.txt",
            file_path="local:///removed.txt",
            file_size_bytes=1,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=org_id,
        )
        db.add_all([owned_doc, other_doc, removed_doc])
        db.flush()
        db.add_all(
            [
                CollectionDocument(
                    collection_id=owned_project.id, document_id=owned_doc.id
                ),
                CollectionDocument(
                    collection_id=other_project.id, document_id=other_doc.id
                ),
                CollectionDocument(
                    collection_id=owned_project.id,
                    document_id=removed_doc.id,
                    is_deleted=True,
                ),
            ]
        )
        db.commit()

        caller = SimpleNamespace(id=owner_id, organization_id=org_id)
        assert kg._scope_doc_ids(db, caller, owned_project.id) == [str(owned_doc.id)]
        assert kg._scope_doc_ids(db, caller, other_project.id) == []

    engine.dispose()
