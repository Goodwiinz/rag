"""
Integration tests for Document API with processing pipeline
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from datetime import datetime
import json
import tempfile
import os
from fastapi.testclient import TestClient
from fastapi import UploadFile

from src.main import app
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.processing import ProcessingJob, JobType, JobStatus
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.services.file_service import FileService
from src.services.processing_pipeline import ProcessingPipeline
from src.core.database import get_db


class TestDocumentAPIIntegration:
    """Test Document API integration with processing pipeline"""

    @pytest.fixture
    def client(self, db_session):
        """Create test client with database session override"""
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
    def auth_headers(self, test_user):
        """Create authentication headers for test user"""
        from src.core.security import create_access_token
        token = create_access_token(data={"sub": str(test_user.id)})
        return {"Authorization": f"Bearer {token}"}

    def test_upload_and_process_document_workflow(self, client, auth_headers, sample_text_file, temp_upload_dir, db_session, test_user, test_organization):
        """Test complete upload and process document workflow through API"""
        # Arrange
        with open(sample_text_file, "rb") as test_file:
            # Act - Upload document
            upload_response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("test_document.txt", test_file, "text/plain")},
                headers=auth_headers,
                data={"description": "Test document for processing"}
            )

        # Assert - Upload successful
        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        assert upload_data["success"]
        assert "document_id" in upload_data
        document_id = upload_data["document_id"]

        # Verify document exists in database
        document = db_session.query(Document).filter(Document.id == document_id).first()
        assert document is not None
        assert document.status == ProcessingStatus.PENDING

        # Act - Start processing
        process_response = client.post(
            f"/api/v1/documents/{document_id}/process",
            headers=auth_headers
        )

        # Assert - Processing started
        assert process_response.status_code == 200
        process_data = process_response.json()
        assert process_data["success"]
        assert "job_id" in process_data

        # Verify processing job was created
        job = db_session.query(ProcessingJob).filter(
            ProcessingJob.document_id == document_id
        ).first()
        assert job is not None
        assert job.job_type == JobType.DOCUMENT_PROCESSING

        # Mock processing completion
        with patch('src.services.processing_pipeline.ProcessingPipeline._process_text_content') as mock_process:
            mock_process.return_value = {
                'text_content': 'Processed text content with entities',
                'entities': [
                    {'name': 'John Doe', 'type': 'PERSON', 'confidence': 0.95},
                    {'name': 'Test Corporation', 'type': 'ORGANIZATION', 'confidence': 0.88}
                ],
                'metadata': {'word_count': 150, 'language': 'en'}
            }

            job.status = JobStatus.COMPLETED
            job.progress_percentage = 100
            job.completed_at = datetime.utcnow()
            job.result = json.dumps({
                'processed_text': 'Processed text content with entities',
                'entities_extracted': 2,
                'processing_time': 3.2
            })
            db_session.commit()

            # Act - Get document details after processing
            document_response = client.get(
                f"/api/v1/documents/{document_id}",
                headers=auth_headers
            )

            # Assert - Document shows as processed
            assert document_response.status_code == 200
            document_data = document_response.json()
            assert document_data["status"] == ProcessingStatus.COMPLETED.value
            assert document_data["processed_at"] is not None
            assert document_data["text_content"] == "Processed text content with entities"

    def test_get_documents_with_processing_status(self, client, auth_headers, db_session, test_user, test_organization):
        """Test retrieving documents with their processing status"""
        # Arrange - Create documents with different statuses
        documents = []
        for i, status in enumerate([ProcessingStatus.PENDING, ProcessingStatus.PROCESSING, ProcessingStatus.COMPLETED]):
            doc = Document(
                title=f"Test Document {i}",
                filename=f"test_file_{i}.txt",
                file_path=f"/test/path/test_file_{i}.txt",
                file_size=1024,
                mime_type="text/plain",
                document_type=DocumentType.TEXT,
                status=status,
                user_id=test_user.id,
                organization_id=test_organization.id
            )
            if status == ProcessingStatus.COMPLETED:
                doc.processed_at = datetime.utcnow()
                doc.text_content = f"Processed content for document {i}"

            db_session.add(doc)
            db_session.flush()
            documents.append(doc)

        db_session.commit()

        # Act - Get documents list
        response = client.get(
            "/api/v1/documents",
            headers=auth_headers
        )

        # Assert - Documents retrieved with correct status
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 3

        # Find our test documents in the response
        doc_statuses = {doc["id"]: doc["status"] for doc in data["items"]}

        for doc in documents:
            assert doc.id in doc_statuses
            assert doc_statuses[doc.id] == doc.status.value

    def test_search_processed_documents(self, client, auth_headers, db_session, test_user, test_organization):
        """Test searching through processed documents"""
        # Arrange - Create processed documents with searchable content
        documents = []
        content_samples = [
            "This document discusses machine learning algorithms and neural networks",
            "The financial report shows quarterly earnings and revenue growth",
            "Technical documentation for API integration and deployment"
        ]

        for i, content in enumerate(content_samples):
            doc = Document(
                title=f"Search Test Document {i}",
                filename=f"search_test_{i}.txt",
                file_path=f"/test/path/search_test_{i}.txt",
                file_size=1024,
                mime_type="text/plain",
                document_type=DocumentType.TEXT,
                status=ProcessingStatus.COMPLETED,
                text_content=content,
                processed_at=datetime.utcnow(),
                user_id=test_user.id,
                organization_id=test_organization.id
            )
            db_session.add(doc)
            documents.append(doc)

        db_session.commit()

        # Act - Search for specific terms
        search_response = client.get(
            "/api/v1/documents/search?query=machine learning",
            headers=auth_headers
        )

        # Assert - Search results correct
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert search_data["total"] == 1
        assert "machine learning" in search_data["items"][0]["text_content"].lower()

        # Act - Search for another term
        financial_search = client.get(
            "/api/v1/documents/search?query=financial",
            headers=auth_headers
        )

        # Assert - Financial document found
        assert financial_search.status_code == 200
        financial_data = financial_search.json()
        assert financial_data["total"] == 1
        assert "financial" in financial_data["items"][0]["text_content"].lower()

    def test_bulk_upload_and_processing(self, client, auth_headers, temp_upload_dir, db_session, test_user, test_organization):
        """Test bulk upload and processing of multiple documents"""
        # Arrange - Create multiple test files
        test_files = []
        for i in range(3):
            file_path = os.path.join(temp_upload_dir, f"bulk_test_{i}.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Bulk test content {i}. This contains important information.")
            test_files.append(file_path)

        document_ids = []

        # Act - Upload files in bulk
        for i, file_path in enumerate(test_files):
            with open(file_path, "rb") as test_file:
                upload_response = client.post(
                    "/api/v1/documents/upload",
                    files={"file": (f"bulk_test_{i}.txt", test_file, "text/plain")},
                    headers=auth_headers,
                    data={"description": f"Bulk test document {i}"}
                )

                assert upload_response.status_code == 200
                document_ids.append(upload_response.json()["document_id"])

        # Act - Start bulk processing
        bulk_process_response = client.post(
            "/api/v1/documents/bulk-process",
            json={"document_ids": document_ids},
            headers=auth_headers
        )

        # Assert - Bulk processing initiated
        assert bulk_process_response.status_code == 200
        bulk_data = bulk_process_response.json()
        assert bulk_data["success"]
        assert len(bulk_data["job_ids"]) == 3

        # Mock completion of all processing jobs
        for doc_id in document_ids:
            job = db_session.query(ProcessingJob).filter(
                ProcessingJob.document_id == doc_id
            ).first()
            job.status = JobStatus.COMPLETED
            job.progress_percentage = 100
            job.completed_at = datetime.utcnow()
            job.result = json.dumps({'processed': True, 'processing_time': 2.0})

        db_session.commit()

        # Act - Get documents to verify all completed
        documents_response = client.get(
            "/api/v1/documents?limit=10",
            headers=auth_headers
        )

        # Assert - All documents processed
        assert documents_response.status_code == 200
        docs_data = documents_response.json()

        processed_docs = [
            doc for doc in docs_data["items"]
            if doc["id"] in document_ids
        ]
        assert len(processed_docs) == 3
        assert all(doc["status"] == ProcessingStatus.COMPLETED.value for doc in processed_docs)

    def test_processing_status_monitoring(self, client, auth_headers, sample_text_file, db_session, test_user, test_organization):
        """Test monitoring document processing status through API"""
        # Arrange - Upload document
        with open(sample_text_file, "rb") as test_file:
            upload_response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("status_test.txt", test_file, "text/plain")},
                headers=auth_headers
            )

        document_id = upload_response.json()["document_id"]

        # Act - Start processing
        process_response = client.post(
            f"/api/v1/documents/{document_id}/process",
            headers=auth_headers
        )

        # Act - Check processing status
        status_response = client.get(
            f"/api/v1/documents/{document_id}/processing-status",
            headers=auth_headers
        )

        # Assert - Status monitoring works
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["document_id"] == document_id
        assert status_data["status"] == JobStatus.PENDING.value
        assert status_data["progress_percentage"] == 0

        # Update job status
        job = db_session.query(ProcessingJob).filter(
            ProcessingJob.document_id == document_id
        ).first()
        job.status = JobStatus.IN_PROGRESS
        job.progress_percentage = 60
        job.current_step = "Extracting entities"
        db_session.commit()

        # Act - Check updated status
        updated_status_response = client.get(
            f"/api/v1/documents/{document_id}/processing-status",
            headers=auth_headers
        )

        # Assert - Updated status reflected
        assert updated_status_response.status_code == 200
        updated_status_data = updated_status_response.json()
        assert updated_status_data["status"] == JobStatus.IN_PROGRESS.value
        assert updated_status_data["progress_percentage"] == 60
        assert updated_status_data["current_step"] == "Extracting entities"

    def test_error_handling_in_processing_api(self, client, auth_headers, sample_text_file, db_session, test_user, test_organization):
        """Test error handling in document processing API"""
        # Arrange - Upload document
        with open(sample_text_file, "rb") as test_file:
            upload_response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("error_test.txt", test_file, "text/plain")},
                headers=auth_headers
            )

        document_id = upload_response.json()["document_id"]

        # Act - Start processing
        process_response = client.post(
            f"/api/v1/documents/{document_id}/process",
            headers=auth_headers
        )

        # Simulate processing failure
        job = db_session.query(ProcessingJob).filter(
            ProcessingJob.document_id == document_id
        ).first()
        job.status = JobStatus.FAILED
        job.error_message = "Simulated processing failure: Entity extraction error"
        job.completed_at = datetime.utcnow()
        job.retry_count = 1
        db_session.commit()

        # Act - Check processing status after failure
        status_response = client.get(
            f"/api/v1/documents/{document_id}/processing-status",
            headers=auth_headers
        )

        # Assert - Error status properly reported
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["status"] == JobStatus.FAILED.value
        assert "error_message" in status_data
        assert "Entity extraction error" in status_data["error_message"]

        # Act - Retry processing
        retry_response = client.post(
            f"/api/v1/documents/{document_id}/retry-processing",
            headers=auth_headers
        )

        # Assert - Retry initiated
        assert retry_response.status_code == 200
        retry_data = retry_response.json()
        assert retry_data["success"]

    def test_document_deletion_with_processing_cleanup(self, client, auth_headers, sample_text_file, db_session, test_user, test_organization):
        """Test document deletion and cleanup of processing data"""
        # Arrange - Upload and process document
        with open(sample_text_file, "rb") as test_file:
            upload_response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("delete_test.txt", test_file, "text/plain")},
                headers=auth_headers
            )

        document_id = upload_response.json()["document_id"]

        # Start and complete processing
        process_response = client.post(
            f"/api/v1/documents/{document_id}/process",
            headers=auth_headers
        )

        job = db_session.query(ProcessingJob).filter(
            ProcessingJob.document_id == document_id
        ).first()
        job.status = JobStatus.COMPLETED
        job.progress_percentage = 100
        job.completed_at = datetime.utcnow()
        job.result = json.dumps({'processed': True})
        db_session.commit()

        # Verify document and job exist
        document = db_session.query(Document).filter(Document.id == document_id).first()
        assert document is not None
        assert job is not None

        # Act - Delete document
        delete_response = client.delete(
            f"/api/v1/documents/{document_id}",
            headers=auth_headers
        )

        # Assert - Document deleted successfully
        assert delete_response.status_code == 200
        delete_data = delete_response.json()
        assert delete_data["success"]

        # Verify document and processing job are cleaned up
        deleted_document = db_session.query(Document).filter(Document.id == document_id).first()
        assert deleted_document is None

        deleted_job = db_session.query(ProcessingJob).filter(
            ProcessingJob.document_id == document_id
        ).first()
        assert deleted_job is None

    def test_unauthorized_processing_operations(self, client, sample_text_file):
        """Test that unauthorized users cannot process documents"""
        # Act - Try to upload without authentication
        with open(sample_text_file, "rb") as test_file:
            upload_response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("unauthorized.txt", test_file, "text/plain")}
            )

        # Assert - Upload fails without authentication
        assert upload_response.status_code == 401

        # Act - Try to access processing endpoint without authentication
        process_response = client.post(
            "/api/v1/documents/123/process"
        )

        # Assert - Processing fails without authentication
        assert process_response.status_code == 401

    def test_document_permissions_in_processing(self, client, auth_headers, sample_text_file, db_session, test_organization):
        """Test that users can only process their own documents"""
        # Arrange - Create another user
        other_user = User(
            email="other@example.com",
            username="otheruser",
            hashed_password="hashed_password",
            role=UserRole.USER,
            organization_id=test_organization.id
        )
        db_session.add(other_user)
        db_session.commit()

        # Create document for other user
        other_document = Document(
            title="Other User Document",
            filename="other_doc.txt",
            file_path="/test/other_doc.txt",
            file_size=1024,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            status=ProcessingStatus.PENDING,
            user_id=other_user.id,
            organization_id=test_organization.id
        )
        db_session.add(other_document)
        db_session.commit()

        # Act - Try to process other user's document
        process_response = client.post(
            f"/api/v1/documents/{other_document.id}/process",
            headers=auth_headers
        )

        # Assert - Access denied
        assert process_response.status_code == 404  # Document not found for this user