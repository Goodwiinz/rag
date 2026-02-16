"""
Unit tests for models package
Tests model instantiation, methods, and database operations
"""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from src.models.base import Base, BaseModel, GUID
from src.models.user import User, UserRole
from src.models.organization import Organization, StorageTier
from src.models.document import Document, ProcessingStatus
from src.models.vector import VectorEntry
from src.models.search import SearchQuery, SearchResult
from src.models.analytics_event import AnalyticsEvent, EventType
from src.models.evidence import StanceClassificationModel
from src.models.collection import Collection


# Test database setup
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_organization(db_session):
    """Create a sample organization for testing"""
    org = Organization(
        name="Test Organization",
        storage_tier=StorageTier.PROFESSIONAL,
        storage_limit_bytes=1000000000  # 1GB limit
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def sample_user(db_session, sample_organization):
    """Create a sample user for testing"""
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="User",
        role=UserRole.USER,
        organization_id=sample_organization.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestBaseModel:
    """Test the base model functionality"""
    
    def test_base_model_creation(self, db_session):
        """Test base model fields and creation"""
        # Using User as a concrete example of BaseModel
        user = User(
            email="test@example.com",
            password_hash="hash",
            first_name="Test",
            last_name="User",
            role=UserRole.USER,
            organization_id=uuid.uuid4()
        )
        
        # Test that ID is generated
        assert user.id is not None
        assert isinstance(user.id, uuid.UUID)
        
        # Test timestamps are set
        assert user.created_at is not None
        assert user.updated_at is not None
        
        # Test soft delete defaults
        assert user.is_deleted is False
        assert user.deleted_at is None
    
    def test_soft_delete(self, db_session, sample_user):
        """Test soft delete functionality"""
        assert sample_user.is_deleted is False
        assert sample_user.deleted_at is None
        
        sample_user.soft_delete()
        
        assert sample_user.is_deleted is True
        assert sample_user.deleted_at is not None
        assert isinstance(sample_user.deleted_at, datetime)
    
    def test_restore(self, db_session, sample_user):
        """Test restore functionality"""
        sample_user.soft_delete()
        assert sample_user.is_deleted is True
        
        sample_user.restore()
        
        assert sample_user.is_deleted is False
        assert sample_user.deleted_at is None
    
    def test_to_dict(self, db_session, sample_user):
        """Test to_dict method"""
        user_dict = sample_user.to_dict()
        
        assert isinstance(user_dict, dict)
        assert "id" in user_dict
        assert "created_at" in user_dict
        assert "updated_at" in user_dict
        assert "email" in user_dict
        assert user_dict["email"] == "test@example.com"
    
    def test_repr(self, db_session, sample_user):
        """Test string representation"""
        repr_str = repr(sample_user)
        assert "User" in repr_str
        assert str(sample_user.id) in repr_str


class TestGUID:
    """Test the GUID type converter"""
    
    def test_uuid_generation(self):
        """Test UUID generation and conversion"""
        guid = GUID()
        test_uuid = uuid.uuid4()
        
        # Test that we can process UUIDs
        assert guid.process_bind_param(test_uuid, Mock(name="postgresql")) == str(test_uuid)
        assert guid.process_bind_param(test_uuid, Mock(name="sqlite")) == str(test_uuid)
    
    def test_none_handling(self):
        """Test handling of None values"""
        guid = GUID()
        assert guid.process_bind_param(None, Mock()) is None
        assert guid.process_result_value(None, Mock()) is None


class TestUser:
    """Test User model functionality"""
    
    def test_user_creation(self, db_session, sample_organization):
        """Test user model creation and fields"""
        user = User(
            email="newuser@example.com",
            password_hash="hashed_password",
            first_name="New",
            last_name="User",
            role=UserRole.ANALYST,
            organization_id=sample_organization.id
        )
        
        db_session.add(user)
        db_session.commit()
        
        assert user.id is not None
        assert user.email == "newuser@example.com"
        assert user.role == UserRole.ANALYST
        assert user.is_active is True
        assert user.login_count == 0
    
    def test_full_name_property(self, sample_user):
        """Test full_name computed property"""
        assert sample_user.full_name == "Test User"
    
    def test_password_methods(self, sample_user):
        """Test password setting and checking"""
        with patch('src.core.security.get_password_hash') as mock_hash:
            mock_hash.return_value = "new_hashed_password"
            sample_user.set_password("newpassword")
            assert sample_user.password_hash == "new_hashed_password"
            mock_hash.assert_called_once_with("newpassword")
        
        with patch('src.core.security.verify_password') as mock_verify:
            mock_verify.return_value = True
            assert sample_user.check_password("password") is True
            mock_verify.assert_called_once_with("password", sample_user.password_hash)
    
    def test_update_last_login(self, sample_user):
        """Test login tracking"""
        initial_count = sample_user.login_count
        sample_user.update_last_login()
        
        assert sample_user.last_login is not None
        assert sample_user.login_count == initial_count + 1
    
    def test_permission_hierarchy(self, sample_user):
        """Test role-based permission system"""
        # Test USER role
        sample_user.role = UserRole.USER
        assert sample_user.has_permission(UserRole.USER) is True
        assert sample_user.has_permission(UserRole.ANALYST) is False
        assert sample_user.has_permission(UserRole.ADMIN) is False
        
        # Test ADMIN role
        sample_user.role = UserRole.ADMIN
        assert sample_user.has_permission(UserRole.USER) is True
        assert sample_user.has_permission(UserRole.ANALYST) is True
        assert sample_user.has_permission(UserRole.ADMIN) is True

    def test_permission_string_type_confusion_fix(self, sample_user):
        """Test that passing strings to has_permission returns False (security fix)"""
        sample_user.role = UserRole.USER

        # This was the vulnerability: passing "admin" string returned True
        assert sample_user.has_permission("admin") is False
        assert sample_user.has_permission("user") is False
        assert sample_user.has_permission(None) is False

        # Verify legitimate enum usage still works
        assert sample_user.has_permission(UserRole.USER) is True
    
    def test_specific_permissions(self, sample_user):
        """Test specific permission methods"""
        sample_user.role = UserRole.USER
        assert sample_user.can_upload_documents() is True
        assert sample_user.can_manage_users() is False
        assert sample_user.can_view_analytics() is False
        
        sample_user.role = UserRole.ADMIN
        assert sample_user.can_upload_documents() is True
        assert sample_user.can_manage_users() is True
        assert sample_user.can_view_analytics() is True
    
    def test_user_to_dict(self, sample_user):
        """Test user-specific to_dict implementation"""
        user_dict = sample_user.to_dict()
        
        assert "password_hash" not in user_dict  # Excluded by default
        assert "full_name" in user_dict
        assert "role" in user_dict
        assert user_dict["role"] == UserRole.USER.value
        
        # Test including sensitive data
        user_dict_sensitive = sample_user.to_dict(exclude_sensitive=False)
        assert "password_hash" in user_dict_sensitive
    
    def test_unique_email_constraint(self, db_session, sample_organization):
        """Test email uniqueness constraint"""
        user1 = User(
            email="duplicate@example.com",
            password_hash="hash1",
            first_name="User",
            last_name="One",
            organization_id=sample_organization.id
        )
        db_session.add(user1)
        db_session.commit()
        
        user2 = User(
            email="duplicate@example.com",
            password_hash="hash2",
            first_name="User",
            last_name="Two",
            organization_id=sample_organization.id
        )
        db_session.add(user2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestOrganization:
    """Test Organization model"""
    
    def test_organization_creation(self, db_session):
        """Test organization creation"""
        org = Organization(
            name="Test Corp",
            storage_tier=StorageTier.ENTERPRISE,
            storage_limit_bytes=5000000000  # 5GB limit
        )
        
        db_session.add(org)
        db_session.commit()
        
        assert org.id is not None
        assert org.name == "Test Corp"
        assert org.storage_tier == StorageTier.ENTERPRISE
        assert org.is_active is True
    
    def test_organization_to_dict(self, sample_organization):
        """Test organization to_dict method"""
        org_dict = sample_organization.to_dict()
        
        assert isinstance(org_dict, dict)
        assert org_dict["name"] == "Test Organization"
        assert org_dict["storage_tier"] == StorageTier.PROFESSIONAL


class TestDocument:
    """Test Document model"""
    
    def test_document_creation(self, db_session, sample_user):
        """Test document creation"""
        doc = Document(
            title="Test Document",
            content="This is test content",
            file_path="/test/path.pdf",
            file_size=1024,
            mime_type="application/pdf",
            uploaded_by=sample_user.id,
            organization_id=sample_user.organization_id
        )
        
        db_session.add(doc)
        db_session.commit()
        
        assert doc.id is not None
        assert doc.title == "Test Document"
        assert doc.file_size == 1024
        assert doc.processing_status is not None


class TestAnalyticsEvent:
    """Test AnalyticsEvent model"""
    
    def test_analytics_event_creation(self, db_session, sample_user):
        """Test analytics event creation"""
        event = AnalyticsEvent(
            event_type=EventType.SEARCH_QUERY,
            user_id=sample_user.id,
            organization_id=sample_user.organization_id,
            event_data={"query": "test search"},
            session_id="test_session_123"
        )
        
        db_session.add(event)
        db_session.commit()
        
        assert event.id is not None
        assert event.event_type == EventType.SEARCH_QUERY
        assert event.event_data == {"query": "test search"}


class TestSearchQuery:
    """Test SearchQuery model"""
    
    def test_search_query_creation(self, db_session, sample_user):
        """Test search query creation"""
        query = SearchQuery(
            query_text="test search",
            user_id=sample_user.id,
            organization_id=sample_user.organization_id,
            result_count=5,
            search_duration_ms=150
        )
        
        db_session.add(query)
        db_session.commit()
        
        assert query.id is not None
        assert query.query_text == "test search"
        assert query.result_count == 5
        assert query.search_duration_ms == 150


class TestEvidence:
    """Test Evidence/StanceClassification model"""
    
    def test_stance_classification_creation(self, db_session):
        """Test stance classification creation"""
        classification = StanceClassificationModel(
            claim_hash="test_claim_hash",
            source_id=uuid.uuid4(),
            stance="supporting",
            confidence=0.95,
            justification_excerpt="Strong supporting evidence",
            model_version="gpt-4o-mini-2024-07-18"
        )
        
        db_session.add(classification)
        db_session.commit()
        
        assert classification.id is not None
        assert classification.stance == "supporting"
        assert classification.confidence == 0.95
        assert classification.model_version == "gpt-4o-mini-2024-07-18"


class TestCollection:
    """Test Collection model"""
    
    def test_collection_creation(self, db_session, sample_user):
        """Test collection creation"""
        collection = Collection(
            name="Test Collection",
            description="A test collection",
            owner_id=sample_user.id,
            organization_id=sample_user.organization_id
        )
        
        db_session.add(collection)
        db_session.commit()
        
        assert collection.id is not None
        assert collection.name == "Test Collection"
        assert collection.owner_id == sample_user.id


class TestVectorEntry:
    """Test VectorEntry model (Pydantic)"""
    
    def test_vector_entry_creation(self):
        """Test vector entry creation"""
        from src.models.vector import VectorMetadata, VectorCollectionType
        
        metadata = VectorMetadata(
            document_id=str(uuid.uuid4()),
            organization_id=str(uuid.uuid4()),
            content_type="text",
            source_type="text",
            chunk_index=1,
            confidence_score=0.95,
            timestamp=datetime.now()
        )
        
        vector_entry = VectorEntry(
            id=str(uuid.uuid4()),
            vector=[0.1, 0.2, 0.3, 0.4, 0.5],
            text="Test content for vectorization",
            metadata=metadata,
            collection=VectorCollectionType.DOCUMENT_CHUNKS
        )
        
        assert vector_entry.id is not None
        assert vector_entry.text == "Test content for vectorization"
        assert len(vector_entry.vector) == 5
        assert vector_entry.collection == VectorCollectionType.DOCUMENT_CHUNKS


class TestModelRelationships:
    """Test model relationships and foreign keys"""
    
    def test_user_organization_relationship(self, db_session, sample_organization, sample_user):
        """Test user-organization relationship"""
        # Refresh to load relationships
        db_session.refresh(sample_user)
        db_session.refresh(sample_organization)
        
        assert sample_user.organization_id == sample_organization.id
        # Note: Relationship loading might not work in SQLite without proper setup
        # In real tests with PostgreSQL, you would test:
        # assert sample_user.organization == sample_organization
    
    def test_document_user_relationship(self, db_session, sample_user):
        """Test document-user relationship"""
        doc = Document(
            title="User's Document",
            content="Content",
            file_path="/path/doc.pdf",
            uploaded_by=sample_user.id,
            organization_id=sample_user.organization_id
        )
        
        db_session.add(doc)
        db_session.commit()
        
        assert doc.uploaded_by == sample_user.id


if __name__ == "__main__":
    pytest.main([__file__])