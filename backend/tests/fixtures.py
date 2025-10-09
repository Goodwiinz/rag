"""
Test fixtures for file processing tests
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.main import app
from src.core.database import get_db, Base
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.entity import Entity, EntityType, ExtractionMethod
from src.models.processing import ProcessingJob, JobType, JobStatus, JobPriority

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
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


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database dependency override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_organization(db_session):
    """Create a test organization"""
    org = Organization(
        name="Test Organization",
        plan_tier="free",
        max_users=10,
        storage_quota_gb=5.0,
        is_active=True
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def test_admin_user(db_session, test_organization):
    """Create a test admin user"""
    user = User(
        email="admin@test.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
        organization_id=test_organization.id,
        is_active=True,
        email_verified=True
    )
    user.set_password("testpassword123")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_regular_user(db_session, test_organization):
    """Create a test regular user"""
    user = User(
        email="user@test.com",
        first_name="Regular",
        last_name="User",
        role=UserRole.USER,
        organization_id=test_organization.id,
        is_active=True,
        email_verified=True
    )
    user.set_password("testpassword123")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers_admin(test_admin_user):
    """Get authentication headers for admin user"""
    from src.core.security import create_access_token
    token = create_access_token(data={"sub": str(test_admin_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user(test_regular_user):
    """Get authentication headers for regular user"""
    from src.core.security import create_access_token
    token = create_access_token(data={"sub": str(test_regular_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def temp_upload_dir():
    """Create a temporary upload directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_text_file(temp_upload_dir):
    """Create a sample text file for testing"""
    file_path = os.path.join(temp_upload_dir, "sample.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("""This is a sample text document for testing purposes.

It contains multiple paragraphs and various content types including:
- Regular text
- Some numbers like 123 and 4567
- Email addresses: test@example.com
- URLs: https://www.example.com
- Company names: Acme Corporation, Global Tech Inc

This document should be suitable for testing text extraction,
entity extraction, and content analysis features.

The quick brown fox jumps over the lazy dog. This pangram helps
test OCR and text processing capabilities.
""")
    return file_path


@pytest.fixture
def sample_json_file(temp_upload_dir):
    """Create a sample JSON file for testing"""
    file_path = os.path.join(temp_upload_dir, "sample.json")
    data = {
        "title": "Test Document",
        "author": "Test Author",
        "content": "This is test content for JSON processing",
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
            "tags": ["test", "sample", "json"]
        },
        "entities": [
            {"name": "Test Author", "type": "person", "confidence": 0.95},
            {"name": "JSON", "type": "technology", "confidence": 0.88}
        ]
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return file_path


@pytest.fixture
def sample_small_binary_file(temp_upload_dir):
    """Create a small binary file for testing"""
    file_path = os.path.join(temp_upload_dir, "sample.bin")
    with open(file_path, "wb") as f:
        f.write(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F")
    return file_path


@pytest.fixture
def sample_large_text_file(temp_upload_dir):
    """Create a larger text file for performance testing"""
    file_path = os.path.join(temp_upload_dir, "large_sample.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        # Write about 1MB of text
        base_text = "This is a test paragraph with various entities. Contact John Doe at john.doe@acme.com or visit https://acme.com. "
        for i in range(5000):  # Approximately 1MB
            f.write(f"{base_text} Paragraph {i+1}. ")
            if i % 100 == 0:
                f.write("\n")
    return file_path


@pytest.fixture
def corrupted_file(temp_upload_dir):
    """Create a corrupted file for error testing"""
    file_path = os.path.join(temp_upload_dir, "corrupted.txt")
    with open(file_path, "wb") as f:
        f.write(b"\xFF\xFE\x00\x00Invalid content that should cause processing errors")
    return file_path


@pytest.fixture
def sample_document_data():
    """Sample document metadata for testing"""
    return {
        "title": "Test Document",
        "filename": "test.txt",
        "document_type": DocumentType.TEXT,
        "file_size_bytes": 1024,
        "mime_type": "text/plain",
        "processing_status": ProcessingStatus.PENDING,
        "tags": ["test", "sample"],
        "is_public": False,
        "metadata": {
            "test_key": "test_value",
            "created_for": "unit_testing"
        }
    }


@pytest.fixture
def sample_entity_data():
    """Sample entity data for testing"""
    return {
        "name": "Test Entity",
        "entity_type": EntityType.PERSON,
        "confidence_score": 0.95,
        "extraction_method": ExtractionMethod.SPACY_NER,
        "metadata": {
            "source": "unit_test",
            "context": "Test Entity was mentioned here"
        }
    }


@pytest.fixture
def sample_processing_job_data():
    """Sample processing job data for testing"""
    return {
        "job_type": JobType.DOCUMENT_INGESTION,
        "status": JobStatus.PENDING,
        "priority": JobPriority.NORMAL,
        "parameters": {
            "document_id": "test-doc-id",
            "processing_options": {
                "extract_entities": True,
                "generate_summary": True
            }
        },
        "config": {
            "max_retries": 3,
            "timeout_seconds": 300
        },
        "total_steps": 5
    }


@pytest.fixture
def mock_image_file(temp_upload_dir):
    """Create a mock image file for testing"""
    # Create a simple 1x1 pixel PNG file
    import base64

    # Base64 encoded 1x1 transparent PNG
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
        "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    )

    file_path = os.path.join(temp_upload_dir, "test_image.png")
    with open(file_path, "wb") as f:
        f.write(png_data)
    return file_path


@pytest.fixture
def mock_audio_file(temp_upload_dir):
    """Create a mock audio file for testing"""
    # Create a minimal WAV file header
    file_path = os.path.join(temp_upload_dir, "test_audio.wav")
    with open(file_path, "wb") as f:
        # WAV header (44 bytes) + minimal audio data
        wav_header = b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1F\x00\x00\x80\x3E\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00"
        f.write(wav_header)
        # Add some dummy audio data
        f.write(b"\x00\x00\x00\x00\x00\x00\x00\x00")
    return file_path


@pytest.fixture
def mock_video_file(temp_upload_dir):
    """Create a mock video file for testing"""
    # Create a minimal MP4 file header (simplified)
    file_path = os.path.join(temp_upload_dir, "test_video.mp4")
    with open(file_path, "wb") as f:
        # Minimal MP4 header
        mp4_header = b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom"
        f.write(mp4_header)
        # Add some dummy data
        f.write(b"\x00" * 1000)  # 1KB of dummy data
    return file_path


@pytest.fixture
def test_documents_with_different_types(db_session, test_organization, test_admin_user):
    """Create test documents of different types"""
    documents = []

    # Text document
    text_doc = Document(
        title="Test Text Document",
        filename="test.txt",
        document_type=DocumentType.TEXT,
        file_size_bytes=1024,
        mime_type="text/plain",
        processing_status=ProcessingStatus.COMPLETED,
        content_text="This is a test text document with entities like John Doe and Acme Corporation.",
        tags=["text", "test"],
        organization_id=test_organization.id,
        uploaded_by_user_id=test_admin_user.id
    )
    documents.append(text_doc)

    # PDF document
    pdf_doc = Document(
        title="Test PDF Document",
        filename="test.pdf",
        document_type=DocumentType.PDF,
        file_size_bytes=2048,
        mime_type="application/pdf",
        processing_status=ProcessingStatus.COMPLETED,
        content_text="This is a test PDF document.",
        tags=["pdf", "test"],
        organization_id=test_organization.id,
        uploaded_by_user_id=test_admin_user.id
    )
    documents.append(pdf_doc)

    # Image document
    image_doc = Document(
        title="Test Image",
        filename="test.jpg",
        document_type=DocumentType.IMAGE,
        file_size_bytes=4096,
        mime_type="image/jpeg",
        processing_status=ProcessingStatus.COMPLETED,
        tags=["image", "test"],
        organization_id=test_organization.id,
        uploaded_by_user_id=test_admin_user.id
    )
    documents.append(image_doc)

    # Save all documents
    for doc in documents:
        db_session.add(doc)

    db_session.commit()

    # Refresh to get IDs
    for doc in documents:
        db_session.refresh(doc)

    return documents


@pytest.fixture
def test_entities(db_session, test_admin_user, test_documents_with_different_types):
    """Create test entities for documents"""
    entities = []

    # Add entities to the first document
    test_doc = test_documents_with_different_types[0]

    entity1 = Entity(
        name="John Doe",
        entity_type=EntityType.PERSON,
        confidence_score=0.95,
        extraction_method=ExtractionMethod.SPACY_NER,
        document_id=test_doc.id,
        organization_id=test_admin_user.organization_id,
        metadata={"source": "test", "position": [0, 8]}
    )
    entities.append(entity1)

    entity2 = Entity(
        name="Acme Corporation",
        entity_type=EntityType.ORGANIZATION,
        confidence_score=0.88,
        extraction_method=ExtractionMethod.SPACY_NER,
        document_id=test_doc.id,
        organization_id=test_admin_user.organization_id,
        metadata={"source": "test", "position": [50, 66]}
    )
    entities.append(entity2)

    # Save all entities
    for entity in entities:
        db_session.add(entity)

    db_session.commit()

    # Refresh to get IDs
    for entity in entities:
        db_session.refresh(entity)

    return entities


@pytest.fixture
def mock_processing_services():
    """Mock processing services for testing"""
    from unittest.mock import MagicMock

    # Mock services
    mock_file_service = MagicMock()
    mock_entity_extractor = MagicMock()
    mock_image_processor = MagicMock()
    mock_audio_processor = MagicMock()
    mock_video_processor = MagicMock()

    return {
        "file_service": mock_file_service,
        "entity_extractor": mock_entity_extractor,
        "image_processor": mock_image_processor,
        "audio_processor": mock_audio_processor,
        "video_processor": mock_video_processor
    }