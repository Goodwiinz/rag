"""
Integration tests for Document Upload API endpoints
Tests contract validation, error handling, security, and performance
"""

import pytest
import asyncio
import json
import io
import uuid
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, AsyncGenerator
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import status
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
import websockets
from httpx import AsyncClient

# Import test utilities and fixtures
from tests.conftest import (
    test_client, test_db, mock_user, mock_organization,
    mock_file_service, mock_processing_service, mock_quality_service,
    create_test_file, create_test_document, create_test_user,
    cleanup_test_data
)
from tests.factories.document_factory import DocumentFactory, ProcessingJobFactory
from tests.factories.user_factory import UserFactory, OrganizationFactory

# Import actual modules to test
from src.api.document_upload import router, upload_manager
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.processing import ProcessingJob, JobType, JobStatus, JobPriority
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.core.database import get_db


class TestDocumentUploadContract:
    """Test API contract validation and request/response schemas"""

    @pytest.mark.asyncio
    async def test_upload_single_document_success_contract(self, test_client: TestClient):
        """Test successful document upload returns correct contract"""
        # Create test user and auth token
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        # Mock authentication
        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            # Create test file
            test_file = create_test_file(content=b"Test document content", filename="test.pdf")

            # Prepare form data
            form_data = {
                "title": "Test Document",
                "description": "Test document description",
                "tags": "test,document",
                "is_public": False,
                "processing_priority": "normal",
                "enable_quality_check": True,
                "custom_metadata": '{"author": "test_user", "category": "test"}'
            }

            # Mock service responses
            with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service, \
                 patch('src.api.document_upload.get_multimodal_processing_service') as mock_processing_service, \
                 patch('src.api.document_upload.get_document_quality_service') as mock_quality_service:

                # Setup mock responses
                mock_file_service.return_value.validate_and_scan_file = AsyncMock(return_value={
                    "security_scan": {
                        "virus_detected": False,
                        "suspicious_content": False,
                        "file_integrity": "verified",
                        "threats": [],
                        "warnings": []
                    },
                    "file_validation": {
                        "file_type_valid": True,
                        "size_valid": True,
                        "mime_type": "application/pdf"
                    }
                })

                mock_file_service.return_value.upload_file = AsyncMock(return_value=create_test_document())
                mock_processing_service.return_value.estimate_processing_time = Mock(return_value=120)
                mock_quality_service.return_value.quick_quality_assessment = AsyncMock(return_value={
                    "overall_score": 0.85
                })

                with patch('src.api.document_upload.process_document_upload'):
                    response = test_client.post(
                        "/api/v2/documents/upload/single",
                        files={"file": ("test.pdf", test_file, "application/pdf")},
                        data=form_data
                    )

                # Assert response contract
                assert response.status_code == status.HTTP_200_OK
                response_data = response.json()

                # Validate response schema
                required_fields = [
                    "document_id", "upload_id", "title", "filename", "document_type",
                    "file_size_bytes", "file_size_mb", "mime_type", "processing_status",
                    "message", "created_at"
                ]

                for field in required_fields:
                    assert field in response_data, f"Missing required field: {field}"

                # Validate field types and formats
                assert isinstance(response_data["document_id"], str)
                assert isinstance(response_data["upload_id"], str)
                assert len(response_data["upload_id"]) == 36  # UUID format
                assert response_data["title"] == "Test Document"
                assert response_data["processing_status"] in ["uploaded", "queued", "processing", "indexed"]
                assert response_data["file_size_bytes"] > 0
                assert response_data["file_size_mb"] > 0
                assert isinstance(response_data["created_at"], str)

                # Validate optional fields
                optional_fields = ["job_id", "estimated_processing_time", "quality_score", "security_scan_result"]
                for field in optional_fields:
                    if field in response_data:
                        assert response_data[field] is not None

    @pytest.mark.asyncio
    async def test_upload_contract_validation_errors(self, test_client: TestClient):
        """Test contract validation for invalid requests"""
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            # Test missing required fields
            test_file = create_test_file(content=b"Test content")

            # Missing title
            response = test_client.post(
                "/api/v2/documents/upload/single",
                files={"file": ("test.pdf", test_file, "application/pdf")},
                data={"description": "Test description"}  # Missing title
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            # Test invalid processing priority
            response = test_client.post(
                "/api/v2/documents/upload/single",
                files={"file": ("test.pdf", test_file, "application/pdf")},
                data={
                    "title": "Test Document",
                    "processing_priority": "invalid_priority"  # Invalid value
                }
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            # Test invalid JSON in custom_metadata
            response = test_client.post(
                "/api/v2/documents/upload/single",
                files={"file": ("test.pdf", test_file, "application/pdf")},
                data={
                    "title": "Test Document",
                    "custom_metadata": "invalid json string"  # Invalid JSON
                }
            )
            # Should handle gracefully and default to empty dict
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]

    @pytest.mark.asyncio
    async def test_upload_file_type_validation(self, test_client: TestClient):
        """Test file type and MIME type validation"""
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            # Test unsupported file types
            unsupported_files = [
                ("test.exe", b"executable content", "application/x-executable"),
                ("test.sh", b"shell script content", "application/x-sh"),
                ("test.php", b"PHP script content", "application/x-php")
            ]

            for filename, content, mime_type in unsupported_files:
                test_file = create_test_file(content=content, filename=filename)

                with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service:
                    mock_file_service.return_value.validate_and_scan_file = AsyncMock(return_value={
                        "security_scan": {"virus_detected": False, "suspicious_content": False},
                        "file_validation": {"file_type_valid": False, "mime_type": mime_type}
                    })

                    response = test_client.post(
                        "/api/v2/documents/upload/single",
                        files={"file": (filename, test_file, mime_type)},
                        data={"title": "Test Document"}
                    )

                    assert response.status_code == status.HTTP_400_BAD_REQUEST
                    assert "file type" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_file_size_limits(self, test_client: TestClient):
        """Test file size validation and limits"""
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            # Test oversized file
            large_content = b"x" * (500 * 1024 * 1024)  # 500MB
            test_file = create_test_file(content=large_content, filename="large.pdf")

            with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service:
                mock_file_service.return_value.validate_and_scan_file = AsyncMock(return_value={
                    "security_scan": {"virus_detected": False, "suspicious_content": False},
                    "file_validation": {
                        "file_type_valid": True,
                        "size_valid": False,
                        "file_size_mb": 500.0,
                        "max_size_mb": 100.0
                    }
                })

                response = test_client.post(
                    "/api/v2/documents/upload/single",
                    files={"file": ("large.pdf", test_file, "application/pdf")},
                    data={"title": "Large Document"}
                )

                assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                assert "size" in response.json()["detail"].lower()


class TestDocumentUploadSecurity:
    """Test security aspects of document upload"""

    @pytest.mark.asyncio
    async def test_virus_detection_blocks_upload(self, test_client: TestClient):
        """Test that virus detection blocks malicious uploads"""
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            test_file = create_test_file(content=b"Malicious content")

            with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service:
                mock_file_service.return_value.validate_and_scan_file = AsyncMock(return_value={
                    "security_scan": {
                        "virus_detected": True,
                        "suspicious_content": True,
                        "file_integrity": "compromised",
                        "threats": [
                            {"type": "virus", "name": "TestVirus", "severity": "high"}
                        ],
                        "warnings": ["Suspicious patterns detected"]
                    },
                    "file_validation": {"file_type_valid": True, "size_valid": True}
                })

                response = test_client.post(
                    "/api/v2/documents/upload/single",
                    files={"file": ("malicious.pdf", test_file, "application/pdf")},
                    data={"title": "Malicious Document"}
                )

                assert response.status_code == status.HTTP_400_BAD_REQUEST
                assert "malware" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_authentication_required(self, test_client: TestClient):
        """Test that authentication is required for uploads"""
        test_file = create_test_file(content=b"Test content")

        # Test without authentication
        response = test_client.post(
            "/api/v2/documents/upload/single",
            files={"file": ("test.pdf", test_file, "application/pdf")},
            data={"title": "Test Document"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_authorization_validation(self, test_client: TestClient):
        """Test authorization validation for different user roles"""
        test_file = create_test_file(content=b"Test content")

        # Test with different user roles
        for role in [UserRole.VIEWER, UserRole.USER, UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            user_data = create_test_user(role=role)
            org_data = create_test_organization()

            with patch('src.api.document_upload.get_current_user', return_value=user_data), \
                 patch('src.api.document_upload.get_current_organization', return_value=org_data):

                with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service, \
                     patch('src.api.document_upload.get_multimodal_processing_service') as mock_processing_service, \
                     patch('src.api.document_upload.get_document_quality_service') as mock_quality_service:

                    # Setup mocks
                    mock_file_service.return_value.validate_and_scan_file = AsyncMock(return_value({
                        "security_scan": {"virus_detected": False, "suspicious_content": False},
                        "file_validation": {"file_type_valid": True, "size_valid": True}
                    }))

                    mock_file_service.return_value.upload_file = AsyncMock(return_value=create_test_document())
                    mock_processing_service.return_value.estimate_processing_time = Mock(return_value=120)
                    mock_quality_service.return_value.quick_quality_assessment = AsyncMock(return_value({
                        "overall_score": 0.85
                    }))

                    with patch('src.api.document_upload.process_document_upload'):
                        response = test_client.post(
                            "/api/v2/documents/upload/single",
                            files={"file": ("test.pdf", test_file, "application/pdf")},
                            data={"title": "Test Document"}
                        )

                    # Viewer role should not be able to upload
                    if role == UserRole.VIEWER:
                        assert response.status_code == status.HTTP_403_FORBIDDEN
                    else:
                        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_file_content_sanitization(self, test_client: TestClient):
        """Test file content sanitization and security scanning"""
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            # Test file with suspicious content
            suspicious_content = b"Test content with <script>alert('xss')</script> malicious patterns"
            test_file = create_test_file(content=suspicious_content)

            with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service:
                mock_file_service.return_value.validate_and_scan_file = AsyncMock(return_value={
                    "security_scan": {
                        "virus_detected": False,
                        "suspicious_content": True,
                        "file_integrity": "warning",
                        "threats": [],
                        "warnings": ["Suspicious script content detected"]
                    },
                    "file_validation": {"file_type_valid": True, "size_valid": True}
                })

                mock_file_service.return_value.upload_file = AsyncMock(return_value=create_test_document())

                response = test_client.post(
                    "/api/v2/documents/upload/single",
                    files={"file": ("suspicious.pdf", test_file, "application/pdf")},
                    data={"title": "Suspicious Document"}
                )

                # Should allow upload but with warnings
                assert response.status_code == status.HTTP_200_OK
                response_data = response.json()
                assert "security_scan_result" in response_data
                assert response_data["security_scan_result"]["suspicious_content"] is True


class TestDocumentUploadProgress:
    """Test WebSocket progress tracking and real-time updates"""

    @pytest.mark.asyncio
    async def test_websocket_progress_updates(self, test_client: TestClient):
        """Test WebSocket progress updates during upload"""
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            # Generate upload ID
            upload_id = str(uuid.uuid4())

            # Test WebSocket connection
            try:
                async with websockets.connect(
                    f"ws://localhost:8000/api/v2/documents/upload/progress/{upload_id}/ws"
                ) as websocket:

                    # Send progress updates
                    await upload_manager.update_progress(upload_id, 25.0, "Processing file")
                    await upload_manager.update_progress(upload_id, 50.0, "Analyzing content")
                    await upload_manager.update_progress(upload_id, 75.0, "Saving to database")
                    await upload_manager.update_progress(upload_id, 100.0, "Completed")

                    # Receive progress updates
                    messages = []
                    try:
                        while True:
                            message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                            messages.append(json.loads(message))
                    except asyncio.TimeoutError:
                        pass

                    # Validate progress messages
                    assert len(messages) >= 4

                    progress_values = [msg["progress_percentage"] for msg in messages]
                    assert 25.0 in progress_values
                    assert 50.0 in progress_values
                    assert 75.0 in progress_values
                    assert 100.0 in progress_values

                    # Validate message structure
                    for msg in messages:
                        assert "type" in msg
                        assert "upload_id" in msg
                        assert msg["upload_id"] == upload_id
                        assert "progress" in msg or "progress_percentage" in msg
                        assert "current_step" in msg

            except ConnectionRefusedError:
                # WebSocket server not running in test environment - skip
                pytest.skip("WebSocket server not available in test environment")

    @pytest.mark.asyncio
    async def test_progress_endpoint(self, test_client: TestClient):
        """Test HTTP progress endpoint"""
        upload_id = str(uuid.uuid4())

        # Initialize progress tracking
        await upload_manager.update_progress(upload_id, 50.0, "Processing")

        user_data = create_test_user(role=UserRole.USER)

        with patch('src.api.document_upload.get_current_user', return_value=user_data):
            response = test_client.get(f"/api/v2/documents/upload/progress/{upload_id}")

            assert response.status_code == status.HTTP_200_OK
            progress_data = response.json()

            required_fields = [
                "upload_id", "progress_percentage", "current_step",
                "total_steps", "completed_steps"
            ]

            for field in required_fields:
                assert field in progress_data

            assert progress_data["upload_id"] == upload_id
            assert progress_data["progress_percentage"] == 50.0
            assert progress_data["current_step"] == "Processing"

    @pytest.mark.asyncio
    async def test_cancel_upload(self, test_client: TestClient):
        """Test upload cancellation"""
        upload_id = str(uuid.uuid4())

        # Initialize progress tracking
        await upload_manager.update_progress(upload_id, 25.0, "Processing")

        user_data = create_test_user(role=UserRole.USER)

        with patch('src.api.document_upload.get_current_user', return_value=user_data):
            response = test_client.delete(f"/api/v2/documents/upload/cancel/{upload_id}")

            assert response.status_code == status.HTTP_200_OK
            cancel_data = response.json()

            assert cancel_data["upload_id"] == upload_id
            assert "cancelled successfully" in cancel_data["message"].lower()

            # Verify upload is removed from tracking
            response = test_client.get(f"/api/v2/documents/upload/progress/{upload_id}")
            assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDocumentQualityAssessment:
    """Test document quality assessment endpoints"""

    @pytest.mark.asyncio
    async def test_get_document_quality(self, test_client: TestClient, test_db: Session):
        """Test document quality assessment"""
        # Setup test data
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()
        document_data = create_test_document()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            with patch('src.api.document_upload.get_document_quality_service') as mock_quality_service:
                mock_quality_service.return_value.comprehensive_quality_assessment = AsyncMock(return_value={
                    "overall_score": 0.87,
                    "readability_score": 0.82,
                    "content_quality_score": 0.91,
                    "technical_quality_score": 0.88,
                    "recommendations": [
                        "Improve document structure",
                        "Add more descriptive headings"
                    ],
                    "issues": [
                        {
                            "type": "readability",
                            "severity": "medium",
                            "description": "Long paragraphs detected"
                        }
                    ],
                    "processing_time_ms": 1250
                })

                response = test_client.get(f"/api/v2/documents/upload/{document_data.id}/quality")

                assert response.status_code == status.HTTP_200_OK
                quality_data = response.json()

                # Validate response structure
                required_fields = [
                    "document_id", "overall_score", "readability_score",
                    "content_quality_score", "technical_quality_score",
                    "recommendations", "issues", "processing_time_ms"
                ]

                for field in required_fields:
                    assert field in quality_data

                assert quality_data["document_id"] == str(document_data.id)
                assert 0 <= quality_data["overall_score"] <= 1
                assert isinstance(quality_data["recommendations"], list)
                assert isinstance(quality_data["issues"], list)
                assert quality_data["processing_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_quality_assessment_permissions(self, test_client: TestClient, test_db: Session):
        """Test quality assessment access permissions"""
        # Setup test data
        owner_data = create_test_user(role=UserRole.USER)
        other_user_data = create_test_user(role=UserRole.USER, email="other@test.com")
        org_data = create_test_organization()

        # Create document owned by specific user
        document_data = create_test_document(uploaded_by_user_id=owner_data.id)

        # Test other user trying to access private document
        with patch('src.api.document_upload.get_current_user', return_value=other_user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            response = test_client.get(f"/api/v2/documents/upload/{document_data.id}/quality")

            # Should be denied for private document
            assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_security_rescan(self, test_client: TestClient, test_db: Session):
        """Test document security rescan"""
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()
        document_data = create_test_document(uploaded_by_user_id=user_data.id)

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service:
                mock_file_service.return_value.rescan_file_security = AsyncMock(return_value={
                    "scan_status": "passed",
                    "virus_detected": False,
                    "suspicious_content": False,
                    "file_integrity": "verified",
                    "threats": [],
                    "warnings": [],
                    "scan_timestamp": datetime.now(timezone.utc)
                })

                response = test_client.post(f"/api/v2/documents/upload/{document_data.id}/rescan")

                assert response.status_code == status.HTTP_200_OK
                rescan_data = response.json()

                assert rescan_data["document_id"] == str(document_data.id)
                assert "scan_result" in rescan_data
                assert "scanned_at" in rescan_data
                assert rescan_data["scan_result"]["scan_status"] == "passed"


class TestDocumentUploadPerformance:
    """Test performance aspects of document upload"""

    @pytest.mark.asyncio
    async def test_upload_performance_large_file(self, test_client: TestClient):
        """Test upload performance with large files"""
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            # Create moderately large test file (10MB)
            large_content = b"x" * (10 * 1024 * 1024)
            test_file = create_test_file(content=large_content)

            with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service, \
                 patch('src.api.document_upload.get_multimodal_processing_service') as mock_processing_service, \
                 patch('src.api.document_upload.get_document_quality_service') as mock_quality_service:

                mock_file_service.return_value.validate_and_scan_file = AsyncMock(return_value({
                    "security_scan": {"virus_detected": False, "suspicious_content": False},
                    "file_validation": {"file_type_valid": True, "size_valid": True}
                }))

                mock_file_service.return_value.upload_file = AsyncMock(return_value=create_test_document())
                mock_processing_service.return_value.estimate_processing_time = Mock(return_value=300)
                mock_quality_service.return_value.quick_quality_assessment = AsyncMock(return_value({
                    "overall_score": 0.85
                }))

                with patch('src.api.document_upload.process_document_upload'):
                    start_time = time.time()

                    response = test_client.post(
                        "/api/v2/documents/upload/single",
                        files={"file": ("large.pdf", test_file, "application/pdf")},
                        data={"title": "Large Test Document"}
                    )

                    end_time = time.time()
                    upload_time = end_time - start_time

                # Assert successful upload
                assert response.status_code == status.HTTP_200_OK

                # Performance assertion (should complete within reasonable time)
                # This is a loose threshold since test environments vary
                assert upload_time < 30.0, f"Upload took {upload_time:.2f}s, expected < 30s"

    @pytest.mark.asyncio
    async def test_concurrent_uploads(self, test_client: TestClient):
        """Test handling multiple concurrent uploads"""
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service, \
                 patch('src.api.document_upload.get_multimodal_processing_service') as mock_processing_service, \
                 patch('src.api.document_upload.get_document_quality_service') as mock_quality_service:

                mock_file_service.return_value.validate_and_scan_file = AsyncMock(return_value({
                    "security_scan": {"virus_detected": False, "suspicious_content": False},
                    "file_validation": {"file_type_valid": True, "size_valid": True}
                }))

                mock_file_service.return_value.upload_file = AsyncMock(return_value=create_test_document())
                mock_processing_service.return_value.estimate_processing_time = Mock(return_value=120)
                mock_quality_service.return_value.quick_quality_assessment = AsyncMock(return_value({
                    "overall_score": 0.85
                }))

                with patch('src.api.document_upload.process_document_upload'):
                    # Create multiple upload tasks
                    async def upload_document(index: int):
                        test_file = create_test_file(content=f"Test content {index}".encode())
                        response = test_client.post(
                            "/api/v2/documents/upload/single",
                            files={"file": (f"test_{index}.pdf", test_file, "application/pdf")},
                            data={"title": f"Test Document {index}"}
                        )
                        return response

                    # Run concurrent uploads
                    tasks = [upload_document(i) for i in range(5)]
                    responses = await asyncio.gather(*tasks)

                    # All uploads should succeed
                    success_count = sum(1 for resp in responses if resp.status_code == status.HTTP_200_OK)
                    assert success_count == 5, f"Expected 5 successful uploads, got {success_count}"

    @pytest.mark.asyncio
    async def test_memory_usage_during_upload(self, test_client: TestClient):
        """Test memory usage during file upload"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service, \
                 patch('src.api.document_upload.get_multimodal_processing_service') as mock_processing_service, \
                 patch('src.api.document_upload.get_document_quality_service') as mock_quality_service:

                mock_file_service.return_value.validate_and_scan_file = AsyncMock(return_value({
                    "security_scan": {"virus_detected": False, "suspicious_content": False},
                    "file_validation": {"file_type_valid": True, "size_valid": True}
                }))

                mock_file_service.return_value.upload_file = AsyncMock(return_value=create_test_document())
                mock_processing_service.return_value.estimate_processing_time = Mock(return_value=120)
                mock_quality_service.return_value.quick_quality_assessment = AsyncMock(return_value({
                    "overall_score": 0.85
                }))

                with patch('src.api.document_upload.process_document_upload'):
                    # Upload file
                    test_file = create_test_file(content=b"Test content for memory test")
                    response = test_client.post(
                        "/api/v2/documents/upload/single",
                        files={"file": ("memory_test.pdf", test_file, "application/pdf")},
                        data={"title": "Memory Test Document"}
                    )

                final_memory = process.memory_info().rss
                memory_increase = final_memory - initial_memory

                # Assert successful upload
                assert response.status_code == status.HTTP_200_OK

                # Memory increase should be reasonable (less than 100MB for small file)
                assert memory_increase < 100 * 1024 * 1024, \
                    f"Memory increased by {memory_increase / 1024 / 1024:.2f}MB, expected < 100MB"


class TestDocumentUploadErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_corrupted_file_handling(self, test_client: TestClient):
        """Test handling of corrupted or invalid files"""
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            # Test corrupted PDF file
            corrupted_content = b"%PDF-1.4\n%corrupted content here\n%%EOF"
            test_file = create_test_file(content=corrupted_content)

            with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service:
                mock_file_service.return_value.validate_and_scan_file = AsyncMock(return_value({
                    "security_scan": {"virus_detected": False, "suspicious_content": False},
                    "file_validation": {
                        "file_type_valid": True,
                        "size_valid": True,
                        "mime_type": "application/pdf",
                        "corruption_detected": True
                    }
                }))

                response = test_client.post(
                    "/api/v2/documents/upload/single",
                    files={"file": ("corrupted.pdf", test_file, "application/pdf")},
                    data={"title": "Corrupted Document"}
                )

                # Should either accept with warning or reject
                assert response.status_code in [
                    status.HTTP_200_OK,  # Accepted with corruption warning
                    status.HTTP_400_BAD_REQUEST  # Rejected due to corruption
                ]

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, test_client: TestClient):
        """Test handling of network timeouts during upload"""
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service:
                # Simulate timeout during file processing
                mock_file_service.return_value.validate_and_scan_file = AsyncMock(
                    side_effect=asyncio.TimeoutError("Processing timeout")
                )

                test_file = create_test_file(content=b"Test content")
                response = test_client.post(
                    "/api/v2/documents/upload/single",
                    files={"file": ("timeout_test.pdf", test_file, "application/pdf")},
                    data={"title": "Timeout Test Document"}
                )

                # Should handle timeout gracefully
                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                assert "timeout" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_database_error_handling(self, test_client: TestClient):
        """Test handling of database errors during upload"""
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service, \
                 patch('src.core.database.get_db') as mock_get_db:

                # Simulate database error
                mock_get_db.side_effect = Exception("Database connection failed")

                test_file = create_test_file(content=b"Test content")
                response = test_client.post(
                    "/api/v2/documents/upload/single",
                    files={"file": ("db_error_test.pdf", test_file, "application/pdf")},
                    data={"title": "Database Error Test"}
                )

                # Should handle database error gracefully
                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                assert "database" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_file_storage_error_handling(self, test_client: TestClient):
        """Test handling of file storage errors"""
        user_data = create_test_user(role=UserRole.USER)
        org_data = create_test_organization()

        with patch('src.api.document_upload.get_current_user', return_value=user_data), \
             patch('src.api.document_upload.get_current_organization', return_value=org_data):

            with patch('src.api.document_upload.get_enhanced_file_service') as mock_file_service:
                # Simulate storage error
                mock_file_service.return_value.validate_and_scan_file = AsyncMock(return_value({
                    "security_scan": {"virus_detected": False, "suspicious_content": False},
                    "file_validation": {"file_type_valid": True, "size_valid": True}
                }))

                mock_file_service.return_value.upload_file = AsyncMock(
                    side_effect=Exception("Storage quota exceeded")
                )

                test_file = create_test_file(content=b"Test content")
                response = test_client.post(
                    "/api/v2/documents/upload/single",
                    files={"file": ("storage_error.pdf", test_file, "application/pdf")},
                    data={"title": "Storage Error Test"}
                )

                # Should handle storage error gracefully
                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
                assert "storage" in response.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])