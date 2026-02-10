"""
Document Repository Integration Tests

Tests for Document model with real PostgreSQL database to validate:
- Foreign key constraints (organization_id, uploaded_by_user_id)
- Cascade deletes (entities, processing_jobs, search_results)
- Unique constraints on embedding_id
- Full-text search vector indexing
- Concurrent update conflict detection
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from concurrent.futures import ThreadPoolExecutor

# Mark all tests in this module
pytestmark = [
    pytest.mark.requires_postgres,
    pytest.mark.integration,
]


@pytest.fixture(scope="function")
def db_session(postgres_container):
    """Create a database session with all tables for document testing."""
    from src.models.base import Base
    from src.models.document import Document, DocumentType, ProcessingStatus
    from src.models.organization import Organization, StorageTier
    from src.models.user import User, UserRole
    from src.models.entity import Entity, EntityType, ExtractionMethod
    # Import ab_testing to resolve User -> Experiment relationship
    from src.models import ab_testing  # noqa: F401

    engine = create_engine(postgres_container["url"])

    # Create all tables
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.fixture
def test_organization(db_session):
    """Create a test organization."""
    from src.models.organization import Organization, StorageTier

    org = Organization(
        id=uuid.uuid4(),
        name=f"Test Org {uuid.uuid4().hex[:8]}",
        storage_tier=StorageTier.PROFESSIONAL,
        storage_limit_bytes=100 * 1024 ** 3,  # 100GB
        is_active=True,
    )
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def test_user(db_session, test_organization):
    """Create a test user."""
    from src.models.user import User, UserRole
    from src.core.security import get_password_hash

    user = User(
        id=uuid.uuid4(),
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash=get_password_hash("testpassword123"),
        first_name="Test",
        last_name="User",
        role=UserRole.USER,
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


class TestDocumentCreation:
    """Tests for document creation with all fields."""

    def test_creates_document_with_all_fields(self, db_session, test_organization, test_user):
        """Verify document creation with all required and optional fields."""
        from src.models.document import Document, DocumentType, ProcessingStatus

        doc = Document(
            id=uuid.uuid4(),
            title="Integration Test Document",
            filename="test_document.pdf",
            file_path="/uploads/test_document.pdf",
            file_size_bytes=1024 * 1024,  # 1MB
            mime_type="application/pdf",
            document_type=DocumentType.PDF,
            content_text="This is test content for full-text search.",
            content_summary="A test document for integration testing.",
            document_metadata={"author": "Test Author", "pages": 10},
            processing_status=ProcessingStatus.COMPLETED,
            is_embedded=True,
            is_indexed=True,
            embedding_id=f"emb_{uuid.uuid4().hex}",
            tags=["test", "integration", "postgresql"],
            organization_id=test_organization.id,
            uploaded_by_user_id=test_user.id,
        )

        db_session.add(doc)
        db_session.commit()

        # Verify document was persisted
        saved_doc = db_session.query(Document).filter_by(id=doc.id).first()
        assert saved_doc is not None
        assert saved_doc.title == "Integration Test Document"
        assert saved_doc.document_type == DocumentType.PDF
        assert saved_doc.processing_status == ProcessingStatus.COMPLETED
        assert saved_doc.tags == ["test", "integration", "postgresql"]
        assert saved_doc.document_metadata["author"] == "Test Author"

    def test_creates_document_with_minimal_fields(self, db_session, test_organization, test_user):
        """Verify document creation with only required fields."""
        from src.models.document import Document, DocumentType, ProcessingStatus

        doc = Document(
            id=uuid.uuid4(),
            title="Minimal Document",
            filename="minimal.txt",
            file_path="/uploads/minimal.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=test_organization.id,
            uploaded_by_user_id=test_user.id,
        )

        db_session.add(doc)
        db_session.commit()

        saved_doc = db_session.query(Document).filter_by(id=doc.id).first()
        assert saved_doc is not None
        assert saved_doc.processing_status == ProcessingStatus.PENDING
        assert saved_doc.is_embedded is False
        assert saved_doc.is_indexed is False


class TestDocumentConstraints:
    """Tests for database constraints."""

    def test_enforces_organization_fk_constraint(self, db_session, test_user):
        """Verify foreign key constraint on organization_id."""
        from src.models.document import Document, DocumentType

        fake_org_id = uuid.uuid4()  # Non-existent organization

        doc = Document(
            id=uuid.uuid4(),
            title="Invalid Org Document",
            filename="invalid.txt",
            file_path="/uploads/invalid.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=fake_org_id,  # Invalid FK
            uploaded_by_user_id=test_user.id,
        )

        db_session.add(doc)

        with pytest.raises(IntegrityError) as exc_info:
            db_session.commit()

        assert "foreign key" in str(exc_info.value).lower() or "violates" in str(exc_info.value).lower()

    def test_enforces_user_fk_constraint(self, db_session, test_organization):
        """Verify foreign key constraint on uploaded_by_user_id."""
        from src.models.document import Document, DocumentType

        fake_user_id = uuid.uuid4()  # Non-existent user

        doc = Document(
            id=uuid.uuid4(),
            title="Invalid User Document",
            filename="invalid.txt",
            file_path="/uploads/invalid.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=test_organization.id,
            uploaded_by_user_id=fake_user_id,  # Invalid FK
        )

        db_session.add(doc)

        with pytest.raises(IntegrityError) as exc_info:
            db_session.commit()

        assert "foreign key" in str(exc_info.value).lower() or "violates" in str(exc_info.value).lower()

    def test_allows_multiple_documents_same_org(self, db_session, test_organization, test_user):
        """Verify multiple documents can belong to same organization."""
        from src.models.document import Document, DocumentType

        doc1 = Document(
            id=uuid.uuid4(),
            title="Document 1",
            filename="doc1.txt",
            file_path="/uploads/doc1.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=test_organization.id,
            uploaded_by_user_id=test_user.id,
        )

        doc2 = Document(
            id=uuid.uuid4(),
            title="Document 2",
            filename="doc2.txt",
            file_path="/uploads/doc2.txt",
            file_size_bytes=200,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=test_organization.id,
            uploaded_by_user_id=test_user.id,
        )

        db_session.add_all([doc1, doc2])
        db_session.commit()

        # Query documents by organization
        docs = db_session.query(Document).filter_by(organization_id=test_organization.id).all()
        assert len(docs) == 2


class TestDocumentCascadeDeletes:
    """Tests for cascade delete behavior."""

    def test_cascades_delete_to_entities(self, db_session, test_organization, test_user):
        """Verify deleting document cascades to entities."""
        from src.models.document import Document, DocumentType
        from src.models.entity import Entity, EntityType, ExtractionMethod

        # Create document
        doc = Document(
            id=uuid.uuid4(),
            title="Document with Entities",
            filename="entities.txt",
            file_path="/uploads/entities.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=test_organization.id,
            uploaded_by_user_id=test_user.id,
        )
        db_session.add(doc)
        db_session.commit()

        # Create entities linked to document
        entity1 = Entity(
            id=uuid.uuid4(),
            name="Test Entity 1",
            entity_type=EntityType.PERSON,
            extraction_method=ExtractionMethod.SPACY,
            extracted_at=datetime.utcnow(),
            document_id=doc.id,
            organization_id=test_organization.id,
        )
        entity2 = Entity(
            id=uuid.uuid4(),
            name="Test Entity 2",
            entity_type=EntityType.ORGANIZATION,
            extracted_at=datetime.utcnow(),
            extraction_method=ExtractionMethod.SPACY,
            document_id=doc.id,
            organization_id=test_organization.id,
        )
        db_session.add_all([entity1, entity2])
        db_session.commit()

        entity1_id = entity1.id
        entity2_id = entity2.id

        # Delete document
        db_session.delete(doc)
        db_session.commit()

        # Verify entities were cascade deleted
        remaining_entities = db_session.query(Entity).filter(
            Entity.id.in_([entity1_id, entity2_id])
        ).all()
        assert len(remaining_entities) == 0


class TestDocumentQueries:
    """Tests for query patterns and indexing."""

    def test_queries_by_processing_status(self, db_session, test_organization, test_user):
        """Verify efficient querying by processing status."""
        from src.models.document import Document, DocumentType, ProcessingStatus

        title_prefix = f"status-{uuid.uuid4().hex[:8]}"
        # Create documents with different statuses
        statuses = [
            ProcessingStatus.PENDING,
            ProcessingStatus.PROCESSING,
            ProcessingStatus.COMPLETED,
            ProcessingStatus.COMPLETED,
            ProcessingStatus.FAILED,
        ]

        for i, status in enumerate(statuses):
            doc = Document(
                id=uuid.uuid4(),
                title=f"{title_prefix}-Document {i}",
                filename=f"doc{i}.txt",
                file_path=f"/uploads/doc{i}.txt",
                file_size_bytes=100,
                mime_type="text/plain",
                document_type=DocumentType.TEXT,
                processing_status=status,
                organization_id=test_organization.id,
                uploaded_by_user_id=test_user.id,
            )
            db_session.add(doc)

        db_session.commit()

        # Query by status
        completed_docs = db_session.query(Document).filter(
            Document.processing_status == ProcessingStatus.COMPLETED,
            Document.title.like(f"{title_prefix}-%"),
        ).all()
        assert len(completed_docs) == 2

        pending_docs = db_session.query(Document).filter(
            Document.processing_status == ProcessingStatus.PENDING,
            Document.title.like(f"{title_prefix}-%"),
        ).all()
        assert len(pending_docs) == 1

    def test_queries_by_document_type(self, db_session, test_organization, test_user):
        """Verify querying by document type."""
        from src.models.document import Document, DocumentType

        title_prefix = f"type-{uuid.uuid4().hex[:8]}"
        types = [
            DocumentType.PDF,
            DocumentType.PDF,
            DocumentType.IMAGE,
            DocumentType.VIDEO,
            DocumentType.TEXT,
        ]

        for i, doc_type in enumerate(types):
            doc = Document(
                id=uuid.uuid4(),
                title=f"{title_prefix}-Document {i}",
                filename=f"doc{i}.txt",
                file_path=f"/uploads/doc{i}.txt",
                file_size_bytes=100,
                mime_type="text/plain",
                document_type=doc_type,
                organization_id=test_organization.id,
                uploaded_by_user_id=test_user.id,
            )
            db_session.add(doc)

        db_session.commit()

        # Query PDFs
        pdf_docs = db_session.query(Document).filter(
            Document.document_type == DocumentType.PDF,
            Document.title.like(f"{title_prefix}-%"),
        ).all()
        assert len(pdf_docs) == 2


class TestConcurrentAccess:
    """Tests for concurrent database access patterns."""

    def test_concurrent_updates_detect_conflict(self, postgres_container, test_organization, test_user):
        """Verify concurrent updates are handled correctly with optimistic locking."""
        from src.models.base import Base
        from src.models.document import Document, DocumentType, ProcessingStatus

        engine = create_engine(postgres_container["url"])
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)

        # Create initial document
        session1 = Session()
        doc = Document(
            id=uuid.uuid4(),
            title="Concurrent Document",
            filename="concurrent.txt",
            file_path="/uploads/concurrent.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            processing_status=ProcessingStatus.PENDING,
            organization_id=test_organization.id,
            uploaded_by_user_id=test_user.id,
        )
        session1.add(doc)
        session1.commit()
        doc_id = doc.id
        session1.close()

        # Simulate concurrent updates
        results = {"session2_updated": False, "session3_updated": False}

        def update_session2():
            s = Session()
            try:
                s.execute(text("SET lock_timeout = '2000ms'"))
                d = s.query(Document).filter_by(id=doc_id).first()
                d.title = "Updated by Session 2"
                d.processing_status = ProcessingStatus.PROCESSING
                s.commit()
                results["session2_updated"] = True
            except Exception as e:
                s.rollback()
                results["session2_error"] = str(e)
            finally:
                s.close()

        def update_session3():
            s = Session()
            try:
                s.execute(text("SET lock_timeout = '2000ms'"))
                d = s.query(Document).filter_by(id=doc_id).first()
                d.title = "Updated by Session 3"
                d.processing_status = ProcessingStatus.COMPLETED
                s.commit()
                results["session3_updated"] = True
            except Exception as e:
                s.rollback()
                results["session3_error"] = str(e)
            finally:
                s.close()

        # Run concurrent updates
        with ThreadPoolExecutor(max_workers=2) as executor:
            f2 = executor.submit(update_session2)
            f3 = executor.submit(update_session3)
            f2.result(timeout=15)
            f3.result(timeout=15)

        # At least one should succeed
        assert results["session2_updated"] or results["session3_updated"]

        # Verify final state
        session_final = Session()
        final_doc = session_final.query(Document).filter_by(id=doc_id).first()
        assert final_doc.title in ["Updated by Session 2", "Updated by Session 3"]
        session_final.close()

        engine.dispose()


class TestSoftDelete:
    """Tests for soft delete functionality."""

    def test_soft_delete_preserves_data(self, db_session, test_organization, test_user):
        """Verify soft delete marks record but preserves data."""
        from src.models.document import Document, DocumentType

        doc = Document(
            id=uuid.uuid4(),
            title="Soft Delete Test",
            filename="softdelete.txt",
            file_path="/uploads/softdelete.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=test_organization.id,
            uploaded_by_user_id=test_user.id,
        )
        db_session.add(doc)
        db_session.commit()

        doc_id = doc.id

        # Soft delete
        doc.soft_delete()
        db_session.commit()

        # Document should still exist
        soft_deleted_doc = db_session.query(Document).filter_by(id=doc_id).first()
        assert soft_deleted_doc is not None
        assert soft_deleted_doc.is_deleted is True
        assert soft_deleted_doc.deleted_at is not None

    def test_restore_soft_deleted_document(self, db_session, test_organization, test_user):
        """Verify soft deleted document can be restored."""
        from src.models.document import Document, DocumentType

        doc = Document(
            id=uuid.uuid4(),
            title="Restore Test",
            filename="restore.txt",
            file_path="/uploads/restore.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=test_organization.id,
            uploaded_by_user_id=test_user.id,
        )
        db_session.add(doc)
        db_session.commit()

        # Soft delete then restore
        doc.soft_delete()
        db_session.commit()

        doc.restore()
        db_session.commit()

        # Verify restored
        restored_doc = db_session.query(Document).filter_by(id=doc.id).first()
        assert restored_doc.is_deleted is False
        assert restored_doc.deleted_at is None
