"""
Document Management API Contract Tests
Comprehensive testing for document upload, listing, details, deletion, and processing status
"""

import pytest
import json
import uuid
import tempfile
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List
from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.mark.contract
@pytest.mark.documents
class TestDocumentUploadAPI:
    """Test document upload endpoints"""

    def test_upload_single_document_success(self, test_client: TestClient, auth_headers, sample_files):
        """Test successful single document upload"""
        headers = auth_headers({"email": "test@example.com", "first_name": "Test", "last_name": "User"})

        # Upload text file
        filename, file_content, mime_type = sample_files["text"]
        files = {"file": (filename, file_content, mime_type)}
        data = {
            "title": "Test Document",
            "tags": json.dumps(["test", "document"]),
            "is_public": "true"
        }

        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        assert response.status_code == 201
        response_data = response.json()

        # Verify response structure
        assert "id" in response_data
        assert response_data["title"] == "Test Document"
        assert response_data["filename"] == filename
        assert response_data["mime_type"] == mime_type
        assert response_data["document_type"] == "text"
        assert "test" in response_data["tags"]
        assert response_data["is_public"] is True
        assert response_data["processing_status"] in ["pending", "processing"]

    def test_upload_pdf_document_success(self, test_client: TestClient, auth_headers, sample_files):
        """Test successful PDF document upload"""
        headers = auth_headers({"email": "pdf@example.com", "first_name": "PDF", "last_name": "User"})

        filename, file_content, mime_type = sample_files["pdf"]
        files = {"file": (filename, file_content, mime_type)}
        data = {
            "title": "PDF Test Document",
            "tags": json.dumps(["pdf", "test"]),
            "metadata": json.dumps({"pages": 10, "author": "Test Author"})
        }

        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        assert response.status_code == 201
        response_data = response.json()

        assert response_data["document_type"] == "pdf"
        assert response_data["title"] == "PDF Test Document"
        assert "pdf" in response_data["tags"]

    def test_upload_image_document_success(self, test_client: TestClient, auth_headers, sample_files):
        """Test successful image document upload"""
        headers = auth_headers({"email": "image@example.com", "first_name": "Image", "last_name": "User"})

        filename, file_content, mime_type = sample_files["image"]
        files = {"file": (filename, file_content, mime_type)}
        data = {
            "title": "Image Test Document",
            "tags": json.dumps(["image", "test"]),
            "metadata": json.dumps({"width": 800, "height": 600})
        }

        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        assert response.status_code == 201
        response_data = response.json()

        assert response_data["document_type"] == "image"
        assert response_data["mime_type"] == "image/jpeg"

    def test_upload_audio_document_success(self, test_client: TestClient, auth_headers, sample_files):
        """Test successful audio document upload"""
        headers = auth_headers({"email": "audio@example.com", "first_name": "Audio", "last_name": "User"})

        filename, file_content, mime_type = sample_files["audio"]
        files = {"file": (filename, file_content, mime_type)}
        data = {
            "title": "Audio Test Document",
            "tags": json.dumps(["audio", "test"]),
            "metadata": json.dumps({"duration": 120, "sample_rate": 44100})
        }

        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        assert response.status_code == 201
        response_data = response.json()

        assert response_data["document_type"] == "audio"
        assert response_data["mime_type"] == "audio/mpeg"

    def test_upload_video_document_success(self, test_client: TestClient, auth_headers, sample_files):
        """Test successful video document upload"""
        headers = auth_headers({"email": "video@example.com", "first_name": "Video", "last_name": "User"})

        filename, file_content, mime_type = sample_files["video"]
        files = {"file": (filename, file_content, mime_type)}
        data = {
            "title": "Video Test Document",
            "tags": json.dumps(["video", "test"]),
            "metadata": json.dumps({"duration": 3600, "resolution": "1080p"})
        }

        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        assert response.status_code == 201
        response_data = response.json()

        assert response_data["document_type"] == "video"
        assert response_data["mime_type"] == "video/mp4"

    def test_upload_document_unauthorized(self, test_client: TestClient, sample_files):
        """Test document upload without authentication"""
        filename, file_content, mime_type = sample_files["text"]
        files = {"file": (filename, file_content, mime_type)}
        data = {"title": "Unauthorized Document"}

        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data
        )

        assert response.status_code == 401
        response_data = response.json()
        assert "error" in response_data

    def test_upload_document_invalid_file_type(self, test_client: TestClient, auth_headers):
        """Test upload with unsupported file type"""
        headers = auth_headers({"email": "invalid@example.com", "first_name": "Invalid", "last_name": "User"})

        # Create a file with unsupported extension
        files = {"file": ("test.xyz", b"invalid file content", "application/xyz")}
        data = {"title": "Invalid File"}

        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        assert response.status_code == 400
        response_data = response.json()
        assert "file" in str(response_data).lower() or "type" in str(response_data).lower()

    def test_upload_document_missing_title(self, test_client: TestClient, auth_headers, sample_files):
        """Test upload without required title field"""
        headers = auth_headers({"email": "notitle@example.com", "first_name": "NoTitle", "last_name": "User"})

        filename, file_content, mime_type = sample_files["text"]
        files = {"file": (filename, file_content, mime_type)}
        data = {}  # Missing title

        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        assert response.status_code == 422  # Validation error

    def test_upload_oversized_file(self, test_client: TestClient, auth_headers):
        """Test upload with file exceeding size limits"""
        headers = auth_headers({"email": "bigfile@example.com", "first_name": "Big", "last_name": "File"})

        # Create a large file (simulated)
        large_content = b"x" * (200 * 1024 * 1024)  # 200MB
        files = {"file": ("large.txt", BytesIO(large_content), "text/plain")}
        data = {"title": "Large File"}

        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        assert response.status_code == 413  # Payload Too Large


@pytest.mark.contract
@pytest.mark.documents
class TestDocumentListingAPI:
    """Test document listing endpoints"""

    def test_list_documents_success(self, test_client: TestClient, auth_headers, test_database):
        """Test successful document listing"""
        headers = auth_headers({"email": "list@example.com", "first_name": "List", "last_name": "User"})

        response = test_client.get("/api/v1/documents", headers=headers)

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "documents" in response_data
        assert "pagination" in response_data
        assert isinstance(response_data["documents"], list)
        assert "total_count" in response_data["pagination"]
        assert "page" in response_data["pagination"]
        assert "page_size" in response_data["pagination"]

    def test_list_documents_with_pagination(self, test_client: TestClient, auth_headers):
        """Test document listing with pagination parameters"""
        headers = auth_headers({"email": "paginate@example.com", "first_name": "Paginate", "last_name": "User"})

        # Test first page
        response = test_client.get(
            "/api/v1/documents?page=1&page_size=5",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        assert response_data["pagination"]["page"] == 1
        assert response_data["pagination"]["page_size"] == 5
        assert len(response_data["documents"]) <= 5

    def test_list_documents_with_filters(self, test_client: TestClient, auth_headers):
        """Test document listing with filters"""
        headers = auth_headers({"email": "filter@example.com", "first_name": "Filter", "last_name": "User"})

        # Test filtering by document type
        response = test_client.get(
            "/api/v1/documents?document_type=pdf",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # All returned documents should be PDFs
        for doc in response_data["documents"]:
            assert doc["document_type"] == "pdf"

    def test_list_documents_with_search(self, test_client: TestClient, auth_headers):
        """Test document listing with search query"""
        headers = auth_headers({"email": "search@example.com", "first_name": "Search", "last_name": "User"})

        response = test_client.get(
            "/api/v1/documents?search=test",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Should return documents matching search query
        assert "documents" in response_data
        assert "pagination" in response_data

    def test_list_documents_unauthorized(self, test_client: TestClient):
        """Test document listing without authentication"""
        response = test_client.get("/api/v1/documents")

        assert response.status_code == 401

    def test_list_documents_invalid_page(self, test_client: TestClient, auth_headers):
        """Test document listing with invalid page parameter"""
        headers = auth_headers({"email": "invalidpage@example.com", "first_name": "Invalid", "last_name": "Page"})

        response = test_client.get(
            "/api/v1/documents?page=0",
            headers=headers
        )

        assert response.status_code == 422  # Validation error


@pytest.mark.contract
@pytest.mark.documents
class TestDocumentDetailsAPI:
    """Test document details endpoint"""

    def test_get_document_details_success(self, test_client: TestClient, auth_headers, test_database):
        """Test successful document details retrieval"""
        headers = auth_headers({"email": "details@example.com", "first_name": "Details", "last_name": "User"})

        # First upload a document
        files = {"file": ("test.txt", BytesIO(b"Test content"), "text/plain")}
        data = {"title": "Test Document Details"}

        upload_response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        assert upload_response.status_code == 201
        document_id = upload_response.json()["id"]

        # Get document details
        response = test_client.get(
            f"/api/v1/documents/{document_id}",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert response_data["id"] == document_id
        assert response_data["title"] == "Test Document Details"
        assert "content_text" in response_data
        assert "metadata" in response_data
        assert "processing_started_at" in response_data
        assert "processing_completed_at" in response_data
        assert "processing_error" in response_data
        assert "processing_retry_count" in response_data

    def test_get_document_details_not_found(self, test_client: TestClient, auth_headers):
        """Test document details for non-existent document"""
        headers = auth_headers({"email": "notfound@example.com", "first_name": "NotFound", "last_name": "User"})

        fake_id = str(uuid.uuid4())
        response = test_client.get(
            f"/api/v1/documents/{fake_id}",
            headers=headers
        )

        assert response.status_code == 404
        response_data = response.json()
        assert "not found" in response_data["error"]["message"].lower()

    def test_get_document_details_unauthorized(self, test_client: TestClient):
        """Test document details without authentication"""
        document_id = str(uuid.uuid4())
        response = test_client.get(f"/api/v1/documents/{document_id}")

        assert response.status_code == 401

    def test_get_document_details_invalid_id(self, test_client: TestClient, auth_headers):
        """Test document details with invalid ID format"""
        headers = auth_headers({"email": "invalidid@example.com", "first_name": "Invalid", "last_name": "ID"})

        response = test_client.get(
            "/api/v1/documents/invalid-uuid",
            headers=headers
        )

        assert response.status_code == 422  # Validation error


@pytest.mark.contract
@pytest.mark.documents
class TestDocumentDeletionAPI:
    """Test document deletion endpoint"""

    def test_delete_document_success(self, test_client: TestClient, auth_headers):
        """Test successful document deletion"""
        headers = auth_headers({"email": "delete@example.com", "first_name": "Delete", "last_name": "User"})

        # First upload a document
        files = {"file": ("delete_test.txt", BytesIO(b"Content to delete"), "text/plain")}
        data = {"title": "Document to Delete"}

        upload_response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        assert upload_response.status_code == 201
        document_id = upload_response.json()["id"]

        # Delete the document
        response = test_client.delete(
            f"/api/v1/documents/{document_id}",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()
        assert response_data["message"] == "Document deleted successfully"

        # Verify document is deleted
        get_response = test_client.get(
            f"/api/v1/documents/{document_id}",
            headers=headers
        )
        assert get_response.status_code == 404

    def test_delete_document_not_found(self, test_client: TestClient, auth_headers):
        """Test deletion of non-existent document"""
        headers = auth_headers({"email": "delnotfound@example.com", "first_name": "Delete", "last_name": "NotFound"})

        fake_id = str(uuid.uuid4())
        response = test_client.delete(
            f"/api/v1/documents/{fake_id}",
            headers=headers
        )

        assert response.status_code == 404

    def test_delete_document_unauthorized(self, test_client: TestClient):
        """Test document deletion without authentication"""
        document_id = str(uuid.uuid4())
        response = test_client.delete(f"/api/v1/documents/{document_id}")

        assert response.status_code == 401

    def test_delete_other_user_document(self, test_client: TestClient, auth_headers):
        """Test deletion of document owned by another user"""
        # User 1 uploads document
        headers1 = auth_headers({"email": "user1@example.com", "first_name": "User", "last_name": "One"})

        files = {"file": ("user1_doc.txt", BytesIO(b"User 1 content"), "text/plain")}
        data = {"title": "User 1 Document"}

        upload_response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers1
        )

        document_id = upload_response.json()["id"]

        # User 2 tries to delete User 1's document
        headers2 = auth_headers({"email": "user2@example.com", "first_name": "User", "last_name": "Two"})

        response = test_client.delete(
            f"/api/v1/documents/{document_id}",
            headers=headers2
        )

        assert response.status_code == 403  # Forbidden


@pytest.mark.contract
@pytest.mark.documents
class TestDocumentProcessingStatusAPI:
    """Test document processing status endpoint"""

    def test_get_processing_status_success(self, test_client: TestClient, auth_headers):
        """Test successful processing status retrieval"""
        headers = auth_headers({"email": "status@example.com", "first_name": "Status", "last_name": "User"})

        # Upload a document
        files = {"file": ("status_test.txt", BytesIO(b"Content for status test"), "text/plain")}
        data = {"title": "Status Test Document"}

        upload_response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        document_id = upload_response.json()["id"]

        # Get processing status
        response = test_client.get(
            f"/api/v1/documents/{document_id}/status",
            headers=headers
        )

        assert response.status_code == 200
        response_data = response.json()

        # Verify response structure
        assert "document_id" in response_data
        assert "status" in response_data
        assert "progress" in response_data
        assert "started_at" in response_data
        assert "estimated_completion" in response_data
        assert "error_message" in response_data

        # Status should be one of the expected values
        valid_statuses = ["pending", "processing", "completed", "failed"]
        assert response_data["status"] in valid_statuses

    def test_get_processing_status_not_found(self, test_client: TestClient, auth_headers):
        """Test processing status for non-existent document"""
        headers = auth_headers({"email": "statusnotfound@example.com", "first_name": "Status", "last_name": "NotFound"})

        fake_id = str(uuid.uuid4())
        response = test_client.get(
            f"/api/v1/documents/{fake_id}/status",
            headers=headers
        )

        assert response.status_code == 404

    def test_get_processing_status_unauthorized(self, test_client: TestClient):
        """Test processing status without authentication"""
        document_id = str(uuid.uuid4())
        response = test_client.get(f"/api/v1/documents/{document_id}/status")

        assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.documents
@pytest.mark.performance
class TestDocumentUploadPerformance:
    """Performance tests for document upload functionality"""

    def test_small_file_upload_performance(self, test_client: TestClient, auth_headers, performance_tracker):
        """Test small file upload performance"""
        headers = auth_headers({"email": "perf_small@example.com", "first_name": "Perf", "last_name": "Small"})

        # Create small test file (1KB)
        small_content = b"x" * 1024
        files = {"file": ("small.txt", BytesIO(small_content), "text/plain")}
        data = {"title": "Small Performance Test"}

        performance_tracker.start_timer("small_file_upload")

        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        duration = performance_tracker.end_timer("small_file_upload")

        assert response.status_code == 201
        assert duration < 5.0  # Should complete within 5 seconds

    def test_medium_file_upload_performance(self, test_client: TestClient, auth_headers, performance_tracker):
        """Test medium file upload performance"""
        headers = auth_headers({"email": "perf_medium@example.com", "first_name": "Perf", "last_name": "Medium"})

        # Create medium test file (1MB)
        medium_content = b"x" * (1024 * 1024)
        files = {"file": ("medium.txt", BytesIO(medium_content), "text/plain")}
        data = {"title": "Medium Performance Test"}

        performance_tracker.start_timer("medium_file_upload")

        response = test_client.post(
            "/api/v1/documents/upload",
            files=files,
            data=data,
            headers=headers
        )

        duration = performance_tracker.end_timer("medium_file_upload")

        assert response.status_code == 201
        assert duration < 30.0  # Should complete within 30 seconds

    def test_concurrent_uploads_performance(self, test_client: TestClient, auth_headers, performance_tracker):
        """Test concurrent file upload performance"""
        import threading
        import queue

        headers = auth_headers({"email": "perf_concurrent@example.com", "first_name": "Perf", "last_name": "Concurrent"})

        results = queue.Queue()

        def upload_file(file_id):
            """Upload a file in a separate thread"""
            content = f"Concurrent test content {file_id}".encode()
            files = {"file": (f"concurrent_{file_id}.txt", BytesIO(content), "text/plain")}
            data = {"title": f"Concurrent Test {file_id}"}

            start_time = time.time()

            response = test_client.post(
                "/api/v1/documents/upload",
                files=files,
                data=data,
                headers=headers
            )

            duration = time.time() - start_time
            results.put((response.status_code, duration))

        # Start 5 concurrent uploads
        threads = []
        performance_tracker.start_timer("concurrent_uploads")

        for i in range(5):
            thread = threading.Thread(target=upload_file, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all uploads to complete
        for thread in threads:
            thread.join()

        total_duration = performance_tracker.end_timer("concurrent_uploads")

        # Collect results
        successful_uploads = 0
        upload_durations = []

        while not results.empty():
            status, duration = results.get()
            if status == 201:
                successful_uploads += 1
                upload_durations.append(duration)

        assert successful_uploads >= 4  # At least 4 out of 5 should succeed
        assert len(upload_durations) > 0

        avg_upload_time = sum(upload_durations) / len(upload_durations)
        assert avg_upload_time < 60.0  # Average upload time should be reasonable


# Import time for the concurrent test
import time
from io import BytesIO