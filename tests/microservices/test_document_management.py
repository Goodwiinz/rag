"""
Tests for Document Management Service
"""

import pytest
import uuid
import io
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from httpx import AsyncClient

from backend.src.services.document_management import app
from backend.src.shared.schemas import DocumentType, ProcessingStatus


class TestDocumentManagementService:
    """Test Document Management Service functionality"""

    @pytest.fixture
    def client(self):
        """Create test client for Document Management Service"""
        return TestClient(app)

    @pytest.fixture
    async def http_client(self):
        """Create async HTTP client"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    @patch('backend.src.services.document_management.check_storage_quota')
    @patch('backend.src.services.document_management.save_uploaded_file')
    @patch('backend.src.services.document_management.calculate_file_hash')
    @patch('backend.src.services.document_management.validate_file_upload')
    async def test_upload_document_success(
        self,
        mock_validate,
        mock_hash,
        mock_save,
        mock_quota,
        http_client,
        sample_organization,
        sample_regular_user
    ):
        """Test successful document upload"""
        # Mock successful validation
        mock_validate.return_value = (DocumentType.TEXT, "text/plain")
        mock_hash.return_value = "test_hash"
        mock_save.return_value = "/uploads/test_file.txt"
        mock_quota.return_value = (True, 1024, 52428800)  # has_quota, current, limit

        # Prepare file upload
        file_content = b"Test document content"
        file_data = io.BytesIO(file_content)

        # Test upload
        response = await http_client.post(
            "/documents/upload",
            files={"file": ("test.txt", file_data, "text/plain")},
            data={
                "title": "Test Document",
                "tags": '["test", "upload"]',
                "is_public": "false",
                "custom_metadata": '{"author": "Test User"}',
                "organization_id": str(sample_organization.id),
                "uploaded_by_user_id": str(sample_regular_user.id)
            }
        )

        assert response.status_code == 201

        data = response.json()
        assert data["title"] == "Test Document"
        assert data["document_type"] == DocumentType.TEXT.value
        assert data["processing_status"] == ProcessingStatus.QUEUED.value

    async def test_upload_document_invalid_file_type(self, http_client):
        """Test document upload with invalid file type"""
        # Mock invalid file validation
        with patch('backend.src.services.document_management.validate_file_upload') as mock_validate:
            from backend.src.shared.exceptions import FileUploadError
            mock_validate.side_effect = FileUploadError(
                message="Invalid file type",
                filename="test.exe"
            )

            file_content = b"Test content"
            file_data = io.BytesIO(file_content)

            response = await http_client.post(
                "/documents/upload",
                files={"file": ("test.exe", file_data, "application/x-executable")},
                data={
                    "title": "Test Executable",
                    "organization_id": str(uuid.uuid4()),
                    "uploaded_by_user_id": str(uuid.uuid4())
                }
            )

            assert response.status_code == 400

    async def test_upload_document_quota_exceeded(self, http_client):
        """Test document upload when storage quota is exceeded"""
        with patch('backend.src.services.document_management.validate_file_upload') as mock_validate:
            with patch('backend.src.services.document_management.check_storage_quota') as mock_quota:
                from backend.src.shared.exceptions import StorageQuotaError

                mock_validate.return_value = (DocumentType.TEXT, "text/plain")
                mock_quota.return_value = (False, 52428800, 52428800)  # no_quota, current, limit

                file_content = b"Test content"
                file_data = io.BytesIO(file_content)

                response = await http_client.post(
                    "/documents/upload",
                    files={"file": ("test.txt", file_data, "text/plain")},
                    data={
                        "title": "Test Document",
                        "organization_id": str(uuid.uuid4()),
                        "uploaded_by_user_id": str(uuid.uuid4())
                    }
                )

                assert response.status_code == 409

    async def test_list_documents(self, http_client, sample_organization):
        """Test document listing"""
        response = await http_client.get(
            "/documents",
            params={
                "organization_id": str(sample_organization.id),
                "page": 1,
                "limit": 10
            }
        )

        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert isinstance(data["data"], list)

    async def test_list_documents_with_filters(self, http_client, sample_organization):
        """Test document listing with filters"""
        response = await http_client.get(
            "/documents",
            params={
                "organization_id": str(sample_organization.id),
                "document_type": DocumentType.PDF.value,
                "processing_status": ProcessingStatus.COMPLETED.value,
                "search": "test",
                "page": 1,
                "limit": 10
            }
        )

        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert "pagination" in data

    async def test_get_document_details(self, http_client, sample_organization):
        """Test getting document details"""
        document_id = uuid.uuid4()

        response = await http_client.get(
            f"/documents/{document_id}",
            params={
                "organization_id": str(sample_organization.id)
            }
        )

        # Should return 404 for non-existent document
        assert response.status_code == 404

    async def test_update_document_metadata(self, http_client, sample_organization):
        """Test updating document metadata"""
        document_id = uuid.uuid4()

        update_data = {
            "title": "Updated Title",
            "tags": ["updated", "test"],
            "is_public": True
        }

        response = await http_client.put(
            f"/documents/{document_id}",
            json=update_data,
            params={
                "organization_id": str(sample_organization.id),
                "user_id": str(uuid.uuid4())
            }
        )

        # Should return 404 for non-existent document
        assert response.status_code == 404

    async def test_delete_document(self, http_client, sample_organization):
        """Test document deletion"""
        document_id = uuid.uuid4()

        response = await http_client.delete(
            f"/documents/{document_id}",
            params={
                "organization_id": str(sample_organization.id),
                "user_id": str(uuid.uuid4())
            }
        )

        # Should return 404 for non-existent document
        assert response.status_code == 404

    async def test_get_processing_status(self, http_client, sample_organization):
        """Test getting document processing status"""
        document_id = uuid.uuid4()

        response = await http_client.get(
            f"/documents/{document_id}/processing-status",
            params={
                "organization_id": str(sample_organization.id)
            }
        )

        # Should return 404 for non-existent document
        assert response.status_code == 404

    async def test_download_document(self, http_client, sample_organization):
        """Test document download"""
        document_id = uuid.uuid4()

        response = await http_client.get(
            f"/documents/{document_id}/download",
            params={
                "organization_id": str(sample_organization.id)
            }
        )

        # Should return 404 for non-existent document
        assert response.status_code == 404

    async def test_get_storage_quota(self, http_client, sample_organization):
        """Test storage quota information"""
        with patch('backend.src.services.document_management.Organization') as mock_org:
            # Mock organization
            mock_org_instance = MagicMock()
            mock_org_instance.storage_tier = MagicMock()
            mock_org_instance.storage_tier.value = "free"
            mock_org_instance.storage_limit_bytes = 52428800
            mock_org.query.return_value.scalar_one_or_none.return_value = mock_org_instance

            with patch('backend.src.services.document_management.func') as mock_func:
                # Mock storage usage calculation
                mock_func.coalesce.return_value = MagicMock()
                mock_func.coalesce.return_value.scalar.return_value = 1024000

                response = await http_client.get(
                    "/storage/quota",
                    params={
                        "organization_id": str(sample_organization.id)
                    }
                )

                assert response.status_code == 200

                data = response.json()
                assert "organization_id" in data
                assert "storage_tier" in data
                assert "quota_limit_bytes" in data
                assert "current_usage_bytes" in data
                assert "usage_percentage" in data

    async def test_duplicate_file_detection(self, http_client, sample_organization):
        """Test duplicate file detection"""
        with patch('backend.src.services.document_management.validate_file_upload') as mock_validate:
            with patch('backend.src.services.document_management.calculate_file_hash') as mock_hash:
                with patch('backend.src.services.document_management.check_storage_quota') as mock_quota:
                    from backend.src.shared.exceptions import ConflictError

                    mock_validate.return_value = (DocumentType.TEXT, "text/plain")
                    mock_hash.return_value = "duplicate_hash"
                    mock_quota.return_value = (True, 1024, 52428800)

                    # Mock existing document with same hash
                    with patch('backend.src.services.document_management.Document') as mock_doc:
                        mock_doc.query.return_value.scalar_one_or_none.return_value = MagicMock()

                        file_content = b"Test content"
                        file_data = io.BytesIO(file_content)

                        response = await http_client.post(
                            "/documents/upload",
                            files={"file": ("test.txt", file_data, "text/plain")},
                            data={
                                "title": "Test Document",
                                "organization_id": str(sample_organization.id),
                                "uploaded_by_user_id": str(uuid.uuid4())
                            }
                        )

                        # Should detect duplicate
                        assert response.status_code == 409

    def test_file_validation(self):
        """Test file validation logic"""
        from backend.src.services.document_management import validate_file_upload
        from fastapi import UploadFile

        # Test valid file
        valid_file = MagicMock(spec=UploadFile)
        valid_file.size = 1024
        valid_file.content_type = "text/plain"
        valid_file.filename = "test.txt"

        doc_type, mime_type = validate_file_upload(valid_file)
        assert doc_type == DocumentType.TEXT
        assert mime_type == "text/plain"

        # Test oversized file
        oversized_file = MagicMock(spec=UploadFile)
        oversized_file.size = 100 * 1024 * 1024  # 100MB
        oversized_file.content_type = "text/plain"
        oversized_file.filename = "large.txt"

        with pytest.raises(Exception):  # Should raise FileUploadError
            validate_file_upload(oversized_file)

    async def test_file_storage_operations(self):
        """Test file storage operations"""
        from backend.src.services.document_management import save_uploaded_file, delete_file_from_storage
        from pathlib import Path
        import tempfile

        # Test file saving
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock upload directory
            with patch('backend.src.services.document_management.DOCUMENT_SERVICE_CONFIG') as mock_config:
                mock_config.__getitem__ = lambda self, key: temp_dir if key == "upload_dir" else key

                test_file = MagicMock(spec=UploadFile)
                test_file.filename = "test.txt"
                test_file.read = AsyncMock(return_value=b"test content")

                # Reset file position
                test_file.seek = AsyncMock()

                file_path = await save_uploaded_file(
                    test_file,
                    uuid.uuid4(),
                    uuid.uuid4()
                )

                assert Path(file_path).exists()
                assert Path(file_path).name.endswith(".txt")

                # Test file deletion
                deleted = await delete_file_from_storage(file_path)
                assert deleted is True
                assert not Path(file_path).exists()

    def test_get_document_type_from_mime(self):
        """Test document type detection from MIME type"""
        from backend.src.services.document_management import get_document_type_from_mime

        # Test known MIME types
        assert get_document_type_from_mime("application/pdf") == DocumentType.PDF
        assert get_document_type_from_mime("text/plain") == DocumentType.TEXT
        assert get_document_type_from_mime("image/jpeg") == DocumentType.IMAGE
        assert get_document_type_from_mime("audio/mpeg") == DocumentType.AUDIO
        assert get_document_type_from_mime("video/mp4") == DocumentType.VIDEO

        # Test unknown MIME type
        assert get_document_type_from_mime("application/octet-stream") == DocumentType.MULTIMODAL

    async def test_background_processing_scheduling(self):
        """Test background processing job scheduling"""
        from backend.src.services.document_management import schedule_document_processing

        with patch('backend.src.services.document_management.event_logger') as mock_logger:
            await schedule_document_processing(
                str(uuid.uuid4()),
                uuid.uuid4(),
                uuid.uuid4()
            )

            # Should log processing scheduled event
            mock_logger.log_event.assert_called_once()

    def test_pagination_parameters(self):
        """Test pagination parameter validation"""
        from backend.src.services.document_management import DocumentListRequest

        # Test valid pagination
        valid_request = DocumentListRequest(page=1, limit=20)
        assert valid_request.page == 1
        assert valid_request.limit == 20

        # Test invalid pagination (would be validated by Pydantic)
        with pytest.raises(Exception):  # Would raise validation error
            DocumentListRequest(page=0, limit=0)

    async def test_search_functionality(self, http_client, sample_organization):
        """Test document search functionality"""
        response = await http_client.get(
            "/documents",
            params={
                "organization_id": str(sample_organization.id),
                "search": "test query",
                "page": 1,
                "limit": 10
            }
        )

        assert response.status_code == 200

        data = response.json()
        assert "data" in data
        assert "pagination" in data

    async def test_tag_filtering(self, http_client, sample_organization):
        """Test tag-based filtering"""
        response = await http_client.get(
            "/documents",
            params={
                "organization_id": str(sample_organization.id),
                "tags": ["test", "important"],
                "page": 1,
                "limit": 10
            }
        )

        assert response.status_code == 200

    async def test_date_range_filtering(self, http_client, sample_organization):
        """Test date range filtering"""
        from datetime import datetime, timezone

        response = await http_client.get(
            "/documents",
            params={
                "organization_id": str(sample_organization.id),
                "date_from": datetime.now(timezone.utc).isoformat(),
                "date_to": datetime.now(timezone.utc).isoformat(),
                "page": 1,
                "limit": 10
            }
        )

        assert response.status_code == 200

    async def test_public_document_access(self, http_client, sample_organization):
        """Test public document access control"""
        response = await http_client.get(
            "/documents",
            params={
                "organization_id": str(sample_organization.id),
                "is_public": True,
                "page": 1,
                "limit": 10
            }
        )

        assert response.status_code == 200

    def test_filename_sanitization(self):
        """Test filename sanitization"""
        from backend.src.services.document_management import sanitize_filename

        # Test dangerous characters
        dangerous_name = "../../../etc/passwd"
        safe_name = sanitize_filename(dangerous_name)
        assert ".." not in safe_name
        assert "/" not in safe_name

        # Test long filename
        long_name = "a" * 300
        safe_long_name = sanitize_filename(long_name)
        assert len(safe_long_name) <= 255

    def test_file_size_formatting(self):
        """Test file size formatting"""
        from backend.src.services.document_management import format_file_size

        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1024 * 1024) == "1.0 MB"
        assert format_file_size(1024 * 1024 * 1024) == "1.0 GB"
        assert format_file_size(0) == "0 B"