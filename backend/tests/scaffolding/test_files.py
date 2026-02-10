"""
Tests for file upload and management API endpoints.

Tests cover upload success/failure scenarios, response shape validation,
authentication requirements, and paginated file listing.
"""

import pytest
from datetime import datetime
from io import BytesIO
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

from src.main import app
from src.core.database import get_db
from src.core.dependencies import get_current_user, get_current_organization
from src.services.documents.file_service import FileService, get_file_service
from src.models.document import DocumentType, ProcessingStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_user():
    """Return a Mock that behaves like a User ORM instance."""
    user = Mock()
    user.id = "user-id-1234"
    user.email = "test@example.com"
    user.first_name = "Test"
    user.last_name = "User"
    user.role = Mock(value="user")
    user.organization_id = "org-id-1"
    user.is_active = True
    user.is_deleted = False
    user.organization = _make_mock_organization()
    user.can_upload_documents = Mock(return_value=True)
    user.has_permission = Mock(return_value=True)
    user.to_dict = Mock(return_value={
        "id": user.id,
        "email": user.email,
        "role": "user",
    })
    return user


def _make_mock_organization():
    """Return a Mock that behaves like an Organization ORM instance."""
    org = Mock()
    org.id = "org-id-1"
    org.name = "Test Org"
    org.is_active = True
    org.can_upload_file = Mock(return_value=True)
    org.storage_available_gb = 10.0
    return org


def _make_mock_document(**overrides):
    """Return a Mock that behaves like a Document ORM instance."""
    doc = Mock()
    doc.id = overrides.get("id", "doc-id-1")
    doc.title = overrides.get("title", "Test Document")
    doc.filename = overrides.get("filename", "test.txt")
    doc.document_type = overrides.get("document_type", DocumentType.TEXT)
    doc.file_size_bytes = overrides.get("file_size_bytes", 1024)
    doc.file_size_mb = overrides.get("file_size_mb", 0.001)
    doc.mime_type = overrides.get("mime_type", "text/plain")
    doc.processing_status = overrides.get(
        "processing_status", ProcessingStatus.PENDING
    )
    doc.created_at = overrides.get("created_at", datetime(2025, 1, 15, 12, 0, 0))
    doc.organization_id = overrides.get("organization_id", "org-id-1")
    doc.uploaded_by_user_id = overrides.get("uploaded_by_user_id", "user-id-1234")
    doc.is_deleted = False
    doc.is_public = False
    doc.tags = overrides.get("tags", [])
    doc.to_dict = Mock(return_value={
        "id": str(doc.id),
        "title": doc.title,
        "filename": doc.filename,
        "document_type": doc.document_type.value,
        "file_size_bytes": doc.file_size_bytes,
        "processing_status": doc.processing_status.value,
        "created_at": doc.created_at.isoformat(),
    })
    return doc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_user():
    return _make_mock_user()


@pytest.fixture()
def mock_organization(mock_user):
    return mock_user.organization


@pytest.fixture()
def mock_file_service():
    """Create a mock FileService with async methods."""
    svc = AsyncMock(spec=FileService)
    return svc


@pytest.fixture()
def client(mock_user, mock_organization, mock_file_service):
    """
    Create a TestClient with dependency overrides:
      - get_current_user      -> mock_user
      - get_current_organization -> mock_organization
      - get_db                -> no-op async generator
      - get_file_service      -> mock_file_service
    Lifespan is replaced with a no-op to avoid DB/Redis startup.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _no_lifespan(_app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _no_lifespan

    async def _fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_current_organization] = lambda: mock_organization
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[get_file_service] = lambda: mock_file_service

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        app.router.lifespan_context = original_lifespan


@pytest.fixture()
def unauthenticated_client():
    """
    TestClient WITHOUT auth overrides -- requests should be rejected as 401.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _no_lifespan(_app):
        yield

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _no_lifespan

    # Override only DB to avoid real connection, but leave auth dependency intact
    async def _fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        app.router.lifespan_context = original_lifespan


# ---------------------------------------------------------------------------
# Upload Tests
# ---------------------------------------------------------------------------

class TestUploadFile:
    """Tests for POST /api/v1/files/upload"""

    def test_upload_success(self, client, mock_file_service, mock_user, mock_organization):
        """Successful file upload returns 200 with document metadata."""
        mock_doc = _make_mock_document()
        mock_file_service.upload_file.return_value = mock_doc

        file_content = BytesIO(b"Hello, this is test content.")
        response = client.post(
            "/api/v1/files/upload",
            files={"file": ("test.txt", file_content, "text/plain")},
            data={"title": "Test Document"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Document"
        assert data["filename"] == "test.txt"
        assert data["message"] == "File uploaded successfully"
        mock_file_service.upload_file.assert_awaited_once()

    def test_upload_response_shape(self, client, mock_file_service, mock_user, mock_organization):
        """Verify all fields of FileUploadResponse are present."""
        mock_doc = _make_mock_document()
        mock_file_service.upload_file.return_value = mock_doc

        file_content = BytesIO(b"shape test content")
        response = client.post(
            "/api/v1/files/upload",
            files={"file": ("shape.txt", file_content, "text/plain")},
            data={"title": "Shape Test"},
        )

        assert response.status_code == 200
        data = response.json()

        expected_keys = {
            "document_id",
            "upload_id",
            "id",
            "title",
            "filename",
            "document_type",
            "file_size_bytes",
            "file_size_mb",
            "mime_type",
            "processing_status",
            "upload_timestamp",
            "created_at",
            "message",
            "upload_progress",
        }
        assert expected_keys.issubset(set(data.keys())), (
            f"Missing keys: {expected_keys - set(data.keys())}"
        )

    def test_upload_empty_file(self, client, mock_file_service, mock_user, mock_organization):
        """Uploading an empty file returns 400."""
        # The upload endpoint catches exceptions from file_service and re-raises as 400.
        # When file size is 0, the organization's can_upload_file will still pass,
        # but the service layer should raise. Simulate the service raising.
        mock_file_service.upload_file.side_effect = Exception(
            "File is empty or has no content"
        )

        file_content = BytesIO(b"")
        response = client.post(
            "/api/v1/files/upload",
            files={"file": ("empty.txt", file_content, "text/plain")},
            data={"title": "Empty File"},
        )

        assert response.status_code == 400
        # Custom exception handler wraps errors as {"error": {"message": ...}}
        error_msg = response.json()["error"]["message"].lower()
        assert "empty" in error_msg or "content" in error_msg

    def test_upload_invalid_type(self, client, mock_file_service, mock_user, mock_organization):
        """Uploading an unsupported file type returns 400."""
        mock_file_service.upload_file.side_effect = Exception(
            "File extension '.exe' is not allowed"
        )

        file_content = BytesIO(b"\x4d\x5a\x90\x00")  # PE header bytes
        response = client.post(
            "/api/v1/files/upload",
            files={"file": ("malware.exe", file_content, "application/x-msdownload")},
            data={"title": "Bad File"},
        )

        assert response.status_code == 400
        # Custom exception handler wraps errors as {"error": {"message": ...}}
        assert "not allowed" in response.json()["error"]["message"]

    def test_upload_size_limit(self, client, mock_user, mock_organization):
        """Oversized file returns 400 when storage quota is exceeded.

        Note: The upload endpoint's broad except-clause catches the inner
        HTTPException(413) and re-raises it as HTTPException(400).  The
        custom error handler then wraps it as {"error": {"message": ...}}.
        """
        # Simulate organization refusing the upload due to quota
        mock_organization.can_upload_file.return_value = False
        mock_organization.storage_available_gb = 0.01

        # Create a file that reports a non-zero size (we rely on the endpoint's
        # quota check, not the file_service mock).
        file_content = BytesIO(b"x" * 1024)
        response = client.post(
            "/api/v1/files/upload",
            files={"file": ("big.txt", file_content, "text/plain")},
            data={"title": "Huge File"},
        )

        assert response.status_code == 400
        error_msg = response.json()["error"]["message"]
        assert "Insufficient" in error_msg or "storage quota" in error_msg.lower()

    def test_upload_auth_required(self, unauthenticated_client):
        """Upload without auth token returns 401/403."""
        file_content = BytesIO(b"secret content")
        response = unauthenticated_client.post(
            "/api/v1/files/upload",
            files={"file": ("secret.txt", file_content, "text/plain")},
            data={"title": "Secret"},
        )

        # The app uses HTTPBearer which returns 401 or 403 for missing credentials
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# List Files Tests
# ---------------------------------------------------------------------------

class TestListFiles:
    """Tests for GET /api/v1/files/"""

    @patch("src.api.documents.files.select")
    def test_list_files_success(self, mock_select, client, mock_user, mock_organization):
        """GET /api/v1/files/ returns paginated list of files."""
        # The list endpoint directly queries the database via SQLAlchemy.
        # Since get_db is mocked, we need to mock the db.execute chain.
        # The endpoint calls db.execute() twice: once for count, once for docs.
        mock_doc = _make_mock_document()

        # We need the async db session to return proper results
        # This is tricky because the endpoint uses db directly.
        # Instead, let's patch at the DB level via the fixture's mock session.
        from unittest.mock import PropertyMock

        # Create mock for count query result
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 1

        # Create mock for documents query result
        mock_docs_result = Mock()
        mock_docs_scalars = Mock()
        mock_docs_scalars.all.return_value = [mock_doc]
        mock_docs_result.scalars.return_value = mock_docs_scalars

        # Patch the dependency-injected db session
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_docs_result])

        async def _fake_db_with_data():
            yield mock_db

        app.dependency_overrides[get_db] = _fake_db_with_data

        response = client.get("/api/v1/files/")

        assert response.status_code == 200
        data = response.json()
        assert "files" in data
        assert "total" in data
        assert data["total"] == 1
        assert len(data["files"]) == 1
        assert data["page"] == 1
        assert data["size"] == 20

    @patch("src.api.documents.files.select")
    def test_list_files_pagination(self, mock_select, client, mock_user, mock_organization):
        """Pagination params (page, size) are reflected in response."""
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 50

        mock_docs_result = Mock()
        mock_docs_scalars = Mock()
        # Return 5 mock documents for page 2, size 5
        mock_docs = [_make_mock_document(id=f"doc-{i}") for i in range(5)]
        mock_docs_scalars.all.return_value = mock_docs
        mock_docs_result.scalars.return_value = mock_docs_scalars

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_docs_result])

        async def _fake_db_with_data():
            yield mock_db

        app.dependency_overrides[get_db] = _fake_db_with_data

        response = client.get("/api/v1/files/?page=2&size=5")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["size"] == 5
        assert data["total"] == 50
        assert len(data["files"]) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
