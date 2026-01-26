"""
Tests for file upload and management functionality
"""

import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from io import BytesIO

from src.main import app
from src.core.database import get_db, Base
from src.models import User, Organization, UserRole, StorageTier
from tests.test_auth import TestingSessionLocal, get_auth_headers, engine

# Override database dependency for testing
app.dependency_overrides[get_db] = lambda: TestingSessionLocal()

@pytest.fixture(scope="function")
def client():
    """Create test client"""
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def test_organization():
    """Create test organization"""
    db = TestingSessionLocal()
    organization = Organization(
        name="Test Organization",
        storage_tier=StorageTier.FREE,
        storage_limit_bytes=Organization.get_default_storage_limit(StorageTier.FREE),
        is_active=True
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)
    db.close()
    return organization

@pytest.fixture(scope="function")
def test_user(test_organization):
    """Create test user"""
    db = TestingSessionLocal()
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        role=UserRole.USER,
        organization_id=test_organization.id,
        is_active=True
    )
    user.set_password("testpassword123")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user

def create_test_file(content: str = "Test file content", filename: str = "test.txt"):
    """Create a test file for upload"""
    file_content = content.encode('utf-8')
    return BytesIO(file_content), filename

def test_upload_text_file_success(client, test_user):
    """Test successful text file upload"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")
    file_content, filename = create_test_file("This is a test file", "test.txt")

    response = client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": (filename, file_content, "text/plain")},
        data={"title": "Test Document", "tags": "test,demo"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Document"
    assert data["filename"] == "test.txt"
    assert data["document_type"] == "text"

def test_upload_file_unauthorized(client):
    """Test file upload without authentication"""
    file_content, filename = create_test_file("Test content", "test.txt")

    response = client.post(
        "/api/v1/files/upload",
        files={"file": (filename, file_content, "text/plain")},
        data={"title": "Test Document"}
    )

    assert response.status_code == 401

def test_upload_file_too_large(client, test_user):
    """Test upload of file that's too large"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")

    # Create a large file content (larger than typical limits)
    large_content = "x" * (100 * 1024 * 1024)  # 100MB
    file_content = BytesIO(large_content.encode('utf-8'))

    response = client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": ("large.txt", file_content, "text/plain")},
        data={"title": "Large File"}
    )

    assert response.status_code == 400
    assert "exceeds maximum allowed size" in response.json()["detail"]

def test_list_files_empty(client, test_user):
    """Test listing files when no files exist"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")

    response = client.get("/api/v1/files/", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["files"] == []
    assert data["total"] == 0

def test_list_files_with_files(client, test_user):
    """Test listing files when files exist"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")

    # Upload a file first
    file_content, filename = create_test_file("Test content", "test.txt")
    upload_response = client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": (filename, file_content, "text/plain")},
        data={"title": "Test Document"}
    )
    assert upload_response.status_code == 200

    # List files
    response = client.get("/api/v1/files/", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 1
    assert data["total"] == 1
    assert data["files"][0]["title"] == "Test Document"

def test_get_file_info(client, test_user):
    """Test getting detailed file information"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")

    # Upload a file first
    file_content, filename = create_test_file("Test content", "test.txt")
    upload_response = client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": (filename, file_content, "text/plain")},
        data={"title": "Test Document"}
    )
    file_id = upload_response.json()["id"]

    # Get file info
    response = client.get(f"/api/v1/files/{file_id}", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["file"]["id"] == file_id
    assert data["file"]["title"] == "Test Document"

def test_get_file_info_not_found(client, test_user):
    """Test getting info for non-existent file"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")
    fake_id = "00000000-0000-0000-0000-000000000000"

    response = client.get(f"/api/v1/files/{fake_id}", headers=headers)

    assert response.status_code == 404
    assert "File not found" in response.json()["detail"]

def test_update_file_metadata(client, test_user):
    """Test updating file metadata"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")

    # Upload a file first
    file_content, filename = create_test_file("Test content", "test.txt")
    upload_response = client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": (filename, file_content, "text/plain")},
        data={"title": "Original Title"}
    )
    file_id = upload_response.json()["id"]

    # Update metadata
    response = client.put(
        f"/api/v1/files/{file_id}",
        headers=headers,
        json={"title": "Updated Title", "tags": ["updated", "test"]}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["file"]["title"] == "Updated Title"
    assert "updated" in data["file"]["tags"]

def test_delete_file(client, test_user):
    """Test deleting a file"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")

    # Upload a file first
    file_content, filename = create_test_file("Test content", "test.txt")
    upload_response = client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": (filename, file_content, "text/plain")},
        data={"title": "Test Document"}
    )
    file_id = upload_response.json()["id"]

    # Delete file
    response = client.delete(f"/api/v1/files/{file_id}", headers=headers)

    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]

    # Verify file is deleted
    get_response = client.get(f"/api/v1/files/{file_id}", headers=headers)
    assert get_response.status_code == 404

def test_get_file_stats(client, test_user):
    """Test getting file statistics"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")

    # Upload a file first
    file_content, filename = create_test_file("Test content", "test.txt")
    client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": (filename, file_content, "text/plain")},
        data={"title": "Test Document"}
    )

    # Get stats
    response = client.get("/api/v1/files/stats", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert "files_by_type" in data
    assert "processing_stats" in data

def test_upload_pdf_file(client, test_user):
    """Test uploading a PDF file"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")

    # Create a simple PDF-like content (this is just for testing the API)
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
    file_content = BytesIO(pdf_content)

    response = client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": ("test.pdf", file_content, "application/pdf")},
        data={"title": "Test PDF Document"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["document_type"] == "pdf"

def test_upload_image_file(client, test_user):
    """Test uploading an image file"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")

    # Create a simple PNG-like content (this is just for testing the API)
    png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    file_content = BytesIO(png_content)

    response = client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": ("test.png", file_content, "image/png")},
        data={"title": "Test Image"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["document_type"] == "image"

def test_search_files(client, test_user):
    """Test searching files"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")

    # Upload multiple files
    files_data = [
        ("Document One", "content one", "doc1.txt"),
        ("Document Two", "content two", "doc2.txt"),
        ("Report", "report content", "report.txt")
    ]

    for title, content, filename in files_data:
        file_content, _ = create_test_file(content, filename)
        client.post(
            "/api/v1/files/upload",
            headers=headers,
            files={"file": (filename, file_content, "text/plain")},
            data={"title": title}
        )

    # Search for "Document"
    response = client.get("/api/v1/files/?search=Document", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 2  # Should find "Document One" and "Document Two"

def test_filter_files_by_type(client, test_user):
    """Test filtering files by document type"""
    headers = get_auth_headers(client, "test@example.com", "testpassword123")

    # Upload different file types
    text_content, _ = create_test_file("Text content", "test.txt")
    client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": ("test.txt", text_content, "text/plain")},
        data={"title": "Text Document"}
    )

    pdf_content = b"%PDF-1.4\n"
    pdf_file = BytesIO(pdf_content)
    client.post(
        "/api/v1/files/upload",
        headers=headers,
        files={"file": ("test.pdf", pdf_file, "application/pdf")},
        data={"title": "PDF Document"}
    )

    # Filter by text type
    response = client.get("/api/v1/files/?document_type=text", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["files"]) == 1
    assert data["files"][0]["document_type"] == "text"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])