"""
Unit tests for Document API endpoints
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, mock_open
from fastapi.testclient import TestClient
from httpx import AsyncClient
import json
import io
from typing import Dict, Any

from conftest_fastapi import *


class TestDocumentEndpoints:
    """Test class for document endpoints"""

    @pytest.fixture
    def document_service_mock(self):
        """Mock document service"""
        service = Mock()
        service.upload_document = AsyncMock()
        service.get_document = AsyncMock()
        service.get_documents = AsyncMock()
        service.update_document = AsyncMock()
        service.delete_document = AsyncMock()
        service.process_document = AsyncMock()
        service.get_document_status = AsyncMock()
        return service

    @pytest.fixture
    def processing_service_mock(self):
        """Mock processing service"""
        service = Mock()
        service.start_processing = AsyncMock()
        service.get_processing_status = AsyncMock()
        service.cancel_processing = AsyncMock()
        return service

    @pytest.fixture
    def override_document_dependencies(self, test_app, document_service_mock, processing_service_mock):
        """Override document service dependencies"""
        from src.services.documents import FileService as DocumentService
        from src.services.processing import ProcessingPipeline
        document_service = DocumentService()
        processing_service = ProcessingPipeline()

        # Store original methods
        original_upload = document_service.upload_document
        original_get = document_service.get_document
        original_get_all = document_service.get_documents
        original_update = document_service.update_document
        original_delete = document_service.delete_document
        original_process = document_service.process_document
        original_status = document_service.get_document_status

        original_start = processing_service.start_processing
        original_get_status = processing_service.get_processing_status
        original_cancel = processing_service.cancel_processing

        # Override with mocks
        document_service.upload_document = document_service_mock.upload_document
        document_service.get_document = document_service_mock.get_document
        document_service.get_documents = document_service_mock.get_documents
        document_service.update_document = document_service_mock.update_document
        document_service.delete_document = document_service_mock.delete_document
        document_service.process_document = document_service_mock.process_document
        document_service.get_document_status = document_service_mock.get_document_status

        processing_service.start_processing = processing_service_mock.start_processing
        processing_service.get_processing_status = processing_service_mock.get_processing_status
        processing_service.cancel_processing = processing_service_mock.cancel_processing

        yield

        # Restore original methods
        document_service.upload_document = original_upload
        document_service.get_document = original_get
        document_service.get_documents = original_get_all
        document_service.update_document = original_update
        document_service.delete_document = original_delete
        document_service.process_document = original_process
        document_service.get_document_status = original_status

        processing_service.start_processing = original_start
        processing_service.get_processing_status = original_get_status
        processing_service.cancel_processing = original_cancel

    @pytest.mark.unit
    @pytest.mark.documents
    def test_upload_document_success(self, test_client: TestClient, document_service_mock, sample_documents_data, mock_auth_headers, override_document_dependencies):
        """Test successful document upload"""
        # Setup mock response
        uploaded_doc = {
            "id": "doc-123",
            "title": "Test Document",
            "filename": "test.pdf",
            "content_type": "application/pdf",
            "size": 1024,
            "status": "uploaded",
            "created_at": "2024-01-01T10:00:00Z",
            "metadata": {
                "pages": 10,
                "author": "Test Author"
            }
        }
        document_service_mock.upload_document.return_value = uploaded_doc

        # Create mock file content
        file_content = b"mock pdf content"

        # Make request
        response = test_client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.pdf", file_content, "application/pdf")},
            data={
                "title": "Test Document",
                "tags": json.dumps(["test", "document"]),
                "metadata": json.dumps({"author": "Test Author"})
            },
            headers=mock_auth_headers
        )

        # Assertions
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "doc-123"
        assert data["title"] == "Test Document"
        assert data["filename"] == "test.pdf"
        assert data["status"] == "uploaded"

        # Verify service calls
        document_service_mock.upload_document.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.documents
    def test_upload_document_invalid_file_type(self, test_client: TestClient, mock_auth_headers):
        """Test document upload with invalid file type"""
        # Create mock file with invalid type
        file_content = b"mock executable content"

        # Make request
        response = test_client.post(
            "/api/v1/documents/upload",
            files={"file": ("malware.exe", file_content, "application/x-executable")},
            data={"title": "Malicious File"},
            headers=mock_auth_headers
        )

        # Assertions
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "file type" in data["error"]["message"].lower()

    @pytest.mark.unit
    @pytest.mark.documents
    def test_upload_file_too_large(self, test_client: TestClient, mock_auth_headers):
        """Test document upload with file too large"""
        # Create mock large file content (simulate 100MB)
        file_content = b"x" * (100 * 1024 * 1024)

        # Make request
        response = test_client.post(
            "/api/v1/documents/upload",
            files={"file": ("large.pdf", file_content, "application/pdf")},
            data={"title": "Large File"},
            headers=mock_auth_headers
        )

        # Assertions
        assert response.status_code == 413  # Payload Too Large
        data = response.json()
        assert "error" in data
        assert "too large" in data["error"]["message"].lower()

    @pytest.mark.unit
    @pytest.mark.documents
    def test_get_document_success(self, test_client: TestClient, document_service_mock, sample_documents_data, mock_auth_headers, override_document_dependencies):
        """Test successful document retrieval"""
        # Setup mock response
        document = sample_documents_data[0]
        document_service_mock.get_document.return_value = document

        # Make request
        response = test_client.get(f"/api/v1/documents/{document['id']}", headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == document["id"]
        assert data["title"] == document["title"]
        assert data["content"] == document["content"]

        # Verify service calls
        document_service_mock.get_document.assert_called_once_with(document["id"], mock_auth_headers["Authorization"].split(" ")[1])

    @pytest.mark.unit
    @pytest.mark.documents
    def test_get_document_not_found(self, test_client: TestClient, document_service_mock, mock_auth_headers, override_document_dependencies):
        """Test document retrieval with non-existent document"""
        # Setup mock response
        document_service_mock.get_document.return_value = None

        # Make request
        response = test_client.get("/api/v1/documents/non-existent-id", headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "not found" in data["error"]["message"].lower()

    @pytest.mark.unit
    @pytest.mark.documents
    def test_get_documents_list(self, test_client: TestClient, document_service_mock, sample_documents_data, mock_auth_headers, override_document_dependencies):
        """Test getting list of documents"""
        # Setup mock response
        documents_response = {
            "documents": sample_documents_data,
            "total": len(sample_documents_data),
            "page": 1,
            "per_page": 10,
            "total_pages": 1
        }
        document_service_mock.get_documents.return_value = documents_response

        # Make request
        response = test_client.get("/api/v1/documents/", headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total" in data
        assert len(data["documents"]) == len(sample_documents_data)

        # Verify service calls
        document_service_mock.get_documents.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.documents
    def test_get_documents_with_filters(self, test_client: TestClient, document_service_mock, mock_auth_headers, override_document_dependencies):
        """Test getting documents with filters"""
        # Setup mock response
        filtered_docs = [
            doc for doc in sample_documents_data
            if doc["document_type"] == "pdf"
        ]
        documents_response = {
            "documents": filtered_docs,
            "total": len(filtered_docs),
            "filters_applied": ["document_type"]
        }
        document_service_mock.get_documents.return_value = documents_response

        # Make request with filters
        response = test_client.get(
            "/api/v1/documents/",
            params={
                "document_type": "pdf",
                "tags": ["machine learning"],
                "date_from": "2024-01-01",
                "date_to": "2024-12-31",
                "limit": 5,
                "offset": 0
            },
            headers=mock_auth_headers
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert all(doc["document_type"] == "pdf" for doc in data["documents"])

    @pytest.mark.unit
    @pytest.mark.documents
    def test_update_document_success(self, test_client: TestClient, document_service_mock, sample_documents_data, mock_auth_headers, override_document_dependencies):
        """Test successful document update"""
        # Setup mock response
        document = sample_documents_data[0].copy()
        document["title"] = "Updated Title"
        document["tags"] = ["updated", "tags"]
        document_service_mock.update_document.return_value = document

        # Update data
        update_data = {
            "title": "Updated Title",
            "tags": ["updated", "tags"],
            "metadata": {"updated_by": "test user"}
        }

        # Make request
        response = test_client.put(
            f"/api/v1/documents/{document['id']}",
            json=update_data,
            headers=mock_auth_headers
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["tags"] == ["updated", "tags"]

        # Verify service calls
        document_service_mock.update_document.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.documents
    def test_delete_document_success(self, test_client: TestClient, document_service_mock, sample_documents_data, mock_auth_headers, override_document_dependencies):
        """Test successful document deletion"""
        # Setup mock response
        document_service_mock.delete_document.return_value = True

        document_id = sample_documents_data[0]["id"]

        # Make request
        response = test_client.delete(f"/api/v1/documents/{document_id}", headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Document deleted successfully"

        # Verify service calls
        document_service_mock.delete_document.assert_called_once_with(document_id, mock_auth_headers["Authorization"].split(" ")[1])

    @pytest.mark.unit
    @pytest.mark.documents
    def test_delete_document_not_found(self, test_client: TestClient, document_service_mock, mock_auth_headers, override_document_dependencies):
        """Test document deletion with non-existent document"""
        # Setup mock response
        document_service_mock.delete_document.return_value = False

        # Make request
        response = test_client.delete("/api/v1/documents/non-existent-id", headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "not found" in data["error"]["message"].lower()

    @pytest.mark.unit
    @pytest.mark.documents
    def test_process_document_success(self, test_client: TestClient, processing_service_mock, mock_auth_headers, override_document_dependencies):
        """Test successful document processing"""
        # Setup mock response
        processing_response = {
            "task_id": "task-123",
            "status": "processing",
            "document_id": "doc-123",
            "processing_type": "full",
            "started_at": "2024-01-01T10:00:00Z"
        }
        processing_service_mock.start_processing.return_value = processing_response

        document_id = "doc-123"
        processing_data = {
            "processing_type": "full",
            "extract_entities": True,
            "generate_embeddings": True,
            "create_graph_nodes": True
        }

        # Make request
        response = test_client.post(
            f"/api/v1/documents/{document_id}/process",
            json=processing_data,
            headers=mock_auth_headers
        )

        # Assertions
        assert response.status_code == 202  # Accepted
        data = response.json()
        assert data["task_id"] == "task-123"
        assert data["status"] == "processing"

        # Verify service calls
        processing_service_mock.start_processing.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.documents
    def test_get_processing_status(self, test_client: TestClient, processing_service_mock, mock_auth_headers, override_document_dependencies):
        """Test getting document processing status"""
        # Setup mock response
        status_response = {
            "task_id": "task-123",
            "status": "completed",
            "progress": 100,
            "document_id": "doc-123",
            "started_at": "2024-01-01T10:00:00Z",
            "completed_at": "2024-01-01T10:05:00Z",
            "results": {
                "entities_extracted": 25,
                "embeddings_generated": 15,
                "graph_nodes_created": 20
            }
        }
        processing_service_mock.get_processing_status.return_value = status_response

        # Make request
        response = test_client.get("/api/v1/documents/processing/task-123/status", headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert "results" in data

        # Verify service calls
        processing_service_mock.get_processing_status.assert_called_once_with("task-123")

    @pytest.mark.unit
    @pytest.mark.documents
    def test_cancel_processing(self, test_client: TestClient, processing_service_mock, mock_auth_headers, override_document_dependencies):
        """Test canceling document processing"""
        # Setup mock response
        processing_service_mock.cancel_processing.return_value = {
            "task_id": "task-123",
            "status": "cancelled",
            "cancelled_at": "2024-01-01T10:03:00Z"
        }

        # Make request
        response = test_client.post("/api/v1/documents/processing/task-123/cancel", headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

        # Verify service calls
        processing_service_mock.cancel_processing.assert_called_once_with("task-123")

    @pytest.mark.unit
    @pytest.mark.documents
    def test_download_document(self, test_client: TestClient, document_service_mock, mock_auth_headers, override_document_dependencies):
        """Test document download"""
        # Setup mock response
        document_content = b"mock document content"
        document_service_mock.get_document_content.return_value = document_content

        document_id = "doc-123"

        # Make request
        response = test_client.get(f"/api/v1/documents/{document_id}/download", headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        assert response.content == document_content
        assert "Content-Disposition" in response.headers

        # Verify service calls
        document_service_mock.get_document_content.assert_called_once_with(document_id, mock_auth_headers["Authorization"].split(" ")[1])

    @pytest.mark.unit
    @pytest.mark.documents
    def test_document_search(self, test_client: TestClient, document_service_mock, sample_documents_data, mock_auth_headers, override_document_dependencies):
        """Test searching within documents"""
        # Setup mock response
        search_results = [
            {
                "document_id": doc["id"],
                "title": doc["title"],
                "content_snippet": "...artificial intelligence...",
                "score": 0.95,
                "highlight": "...<mark>artificial intelligence</mark>..."
            }
            for doc in sample_documents_data if "artificial intelligence" in doc["content"]
        ]
        document_service_mock.search_documents.return_value = {
            "results": search_results,
            "total": len(search_results),
            "query": "artificial intelligence"
        }

        # Make request
        response = test_client.get(
            "/api/v1/documents/search",
            params={"q": "artificial intelligence", "limit": 10},
            headers=mock_auth_headers
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data
        assert len(data["results"]) == len(search_results)

        # Verify service calls
        document_service_mock.search_documents.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.documents
    def test_batch_operations(self, test_client: TestClient, document_service_mock, mock_auth_headers, override_document_dependencies):
        """Test batch document operations"""
        # Setup mock response
        batch_result = {
            "operation": "delete",
            "processed": 3,
            "successful": 2,
            "failed": 1,
            "results": [
                {"document_id": "doc-1", "status": "success"},
                {"document_id": "doc-2", "status": "success"},
                {"document_id": "doc-3", "status": "failed", "error": "Document not found"}
            ]
        }
        document_service_mock.batch_delete_documents.return_value = batch_result

        # Batch operation data
        batch_data = {
            "document_ids": ["doc-1", "doc-2", "doc-3"],
            "operation": "delete"
        }

        # Make request
        response = test_client.post("/api/v1/documents/batch", json=batch_data, headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["operation"] == "delete"
        assert data["processed"] == 3
        assert data["successful"] == 2
        assert data["failed"] == 1

        # Verify service calls
        document_service_mock.batch_delete_documents.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.documents
    def test_document_analytics(self, test_client: TestClient, document_service_mock, mock_auth_headers, override_document_dependencies):
        """Test document analytics endpoint"""
        # Setup mock response
        analytics_data = {
            "total_documents": 150,
            "document_types": {
                "pdf": 80,
                "txt": 40,
                "video": 20,
                "image": 10
            },
            "processing_status": {
                "completed": 120,
                "processing": 20,
                "failed": 5,
                "pending": 5
            },
            "storage_usage_mb": 2048,
            "average_processing_time_seconds": 45
        }
        document_service_mock.get_document_analytics.return_value = analytics_data

        # Make request
        response = test_client.get("/api/v1/documents/analytics", headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "total_documents" in data
        assert "document_types" in data
        assert "processing_status" in data
        assert data["total_documents"] == 150

    @pytest.mark.unit
    @pytest.mark.documents
    def test_document_error_handling(self, test_client: TestClient, document_service_mock, mock_auth_headers, override_document_dependencies):
        """Test document endpoint error handling"""
        # Setup mock to raise exception
        document_service_mock.get_document.side_effect = Exception("Database connection failed")

        # Make request
        response = test_client.get("/api/v1/documents/doc-123", headers=mock_auth_headers)

        # Assertions
        assert response.status_code == 500
        data = response.json()
        assert "error" in data

    @pytest.mark.unit
    @pytest.mark.documents
    def test_document_validation_errors(self, test_client: TestClient, mock_auth_headers):
        """Test document endpoint validation errors"""
        # Test with invalid document ID
        response = test_client.get("/api/v1/documents/", headers=mock_auth_headers)
        # Should succeed as it's a list endpoint

        # Test with invalid data for update
        update_data = {
            "title": "",  # Empty title should fail validation
            "tags": "not-a-list"  # Should be a list
        }

        response = test_client.put("/api/v1/documents/doc-123", json=update_data, headers=mock_auth_headers)

        # Should return validation error
        assert response.status_code in [400, 422]

    @pytest.mark.unit
    @pytest.mark.documents
    @pytest.mark.parametrize("endpoint,method,expected_status", [
        ("/api/v1/documents/", "GET", 200),
        ("/api/v1/documents/upload", "POST", 201),
        ("/api/v1/documents/doc-123", "GET", 200),
        ("/api/v1/documents/doc-123", "PUT", 200),
        ("/api/v1/documents/doc-123", "DELETE", 200),
        ("/api/v1/documents/doc-123/process", "POST", 202),
        ("/api/v1/documents/analytics", "GET", 200),
    ])
    def test_document_endpoint_accessibility(self, test_client: TestClient, endpoint: str, method: str, expected_status: int, mock_auth_headers, override_document_dependencies):
        """Test that document endpoints are accessible with proper authentication"""
        # Setup basic mock responses
        from unittest.mock import Mock

        with patch('src.services.document_service.document_service') as mock_service:
            if method == "GET" and endpoint == "/api/v1/documents/":
                mock_service.get_documents.return_value = {"documents": [], "total": 0}
            elif method == "GET" and endpoint.endswith("/analytics"):
                mock_service.get_document_analytics.return_value = {"total_documents": 0}
            elif method == "GET":
                mock_service.get_document.return_value = {"id": "doc-123", "title": "Test"}
            elif method == "POST" and "upload" in endpoint:
                mock_service.upload_document.return_value = {"id": "doc-123", "title": "Test"}
            elif method == "POST" and "process" in endpoint:
                mock_service.process_document.return_value = {"task_id": "task-123", "status": "processing"}
            elif method == "PUT":
                mock_service.update_document.return_value = {"id": "doc-123", "title": "Updated"}
            elif method == "DELETE":
                mock_service.delete_document.return_value = True

            # Make request
            if method == "GET":
                response = test_client.get(endpoint, headers=mock_auth_headers)
            elif method == "POST":
                if "upload" in endpoint:
                    response = test_client.post(
                        endpoint,
                        files={"file": ("test.txt", b"content", "text/plain")},
                        data={"title": "Test"},
                        headers=mock_auth_headers
                    )
                else:
                    response = test_client.post(endpoint, json={}, headers=mock_auth_headers)
            elif method == "PUT":
                response = test_client.put(endpoint, json={"title": "Updated"}, headers=mock_auth_headers)
            elif method == "DELETE":
                response = test_client.delete(endpoint, headers=mock_auth_headers)

            # Should not return 401 (unauthorized) as we have auth headers
            assert response.status_code != 401