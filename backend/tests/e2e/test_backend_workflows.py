"""
End-to-End Backend Workflow Tests

Comprehensive end-to-end tests for the complete backend workflows:
- Document upload → processing → search → results
- Multi-modal processing (text, images, audio, video)
- Knowledge graph entity extraction and relationship building
- Vector search and hybrid search workflows
- User management and authentication flows
- Organization and multi-tenancy workflows
"""

import pytest
import asyncio
import json
import time
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.main import app
from src.core.database import get_db
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.entity import Entity, EntityType, ExtractionMethod
from src.models.processing import ProcessingJob, JobType, JobStatus
from src.services.processing_pipeline import ProcessingPipeline
from src.services.search import VectorService
from src.services.knowledge_graph import KnowledgeGraphService
from src.services.search import HybridSearchService
from src.core.security import create_access_token


class TestDocumentProcessingWorkflow:
    """Test complete document processing workflow"""

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
    def auth_headers(self, test_admin_user):
        """Create authentication headers"""
        token = create_access_token(data={"sub": str(test_admin_user.id)})
        return {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    def sample_text_document(self, temp_upload_dir):
        """Create sample text document for testing"""
        file_path = os.path.join(temp_upload_dir, "workflow_test.txt")
        content = """
        Machine Learning in Modern Healthcare

        The healthcare industry has been revolutionized by machine learning technologies.
        Companies like Google Health and Microsoft Healthcare are developing innovative
        solutions for disease diagnosis and treatment planning.

        Dr. Sarah Johnson from Johns Hopkins University has published research on
        using deep learning for cancer detection. Her work has achieved 95% accuracy
        in early-stage breast cancer diagnosis.

        The implementation of ML systems in hospitals requires careful consideration
        of patient privacy, data security, and regulatory compliance with HIPAA.
        Healthcare providers must ensure that AI models are trained on diverse
        and representative datasets to avoid bias.

        Recent studies show that ML-powered diagnostic tools can reduce
        misdiagnosis rates by up to 40% while improving patient outcomes.
        """
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

    @pytest.fixture
    def sample_pdf_document(self, temp_upload_dir):
        """Create sample PDF document for testing"""
        file_path = os.path.join(temp_upload_dir, "workflow_test.pdf")

        # Create a simple PDF using reportlab
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter

            c = canvas.Canvas(file_path, pagesize=letter)
            c.setFont("Helvetica", 12)

            text_lines = [
                "Financial Analysis Report - Q4 2024",
                "",
                "Company: TechCorp Industries",
                "Revenue: $50.2M (+15% YoY)",
                "Net Income: $8.7M (+22% YoY)",
                "",
                "Key Financial Metrics:",
                "- Operating Margin: 17.3%",
                "- R&D Investment: $7.5M",
                "- Employee Count: 1,250",
                "",
                "Contact: finance@techcorp.com",
                "Phone: (555) 123-4567"
            ]

            y_position = 750
            for line in text_lines:
                c.drawString(50, y_position, line)
                y_position -= 20

            c.save()
        except ImportError:
            # Fallback: create a simple text file with .pdf extension
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("Fallback PDF content for testing")

        return file_path

    def test_complete_text_document_workflow(self, client, auth_headers, sample_text_document,
                                           db_session, test_admin_user, test_organization):
        """Test complete workflow for text document processing"""
        # Step 1: Upload document
        with open(sample_text_document, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("ml_healthcare.txt", f, "text/plain")},
                headers=auth_headers,
                data={"description": "ML in Healthcare document"}
            )

        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        assert upload_data["success"]
        document_id = upload_data["document_id"]

        # Step 2: Verify document is created in database
        document = db_session.query(Document).filter(Document.id == document_id).first()
        assert document is not None
        assert document.title == "ml_healthcare.txt"
        assert document.processing_status == ProcessingStatus.PENDING

        # Step 3: Start processing
        process_response = client.post(
            f"/api/v1/documents/{document_id}/process",
            headers=auth_headers
        )

        assert process_response.status_code == 200
        process_data = process_response.json()
        assert process_data["success"]
        assert "job_id" in process_data

        # Step 4: Mock processing pipeline completion
        with patch('src.services.processing_pipeline.ProcessingPipeline._process_text_content') as mock_process:
            mock_process.return_value = {
                'text_content': document.content_text,
                'entities': [
                    {'name': 'Google Health', 'type': 'ORGANIZATION', 'confidence': 0.95},
                    {'name': 'Microsoft Healthcare', 'type': 'ORGANIZATION', 'confidence': 0.92},
                    {'name': 'Dr. Sarah Johnson', 'type': 'PERSON', 'confidence': 0.98},
                    {'name': 'Johns Hopkins University', 'type': 'ORGANIZATION', 'confidence': 0.96},
                    {'name': 'HIPAA', 'type': 'LAW', 'confidence': 0.94},
                    {'name': 'machine learning', 'type': 'CONCEPT', 'confidence': 0.97}
                ],
                'metadata': {
                    'word_count': 250,
                    'language': 'en',
                    'processing_time': 2.3
                }
            }

            # Update processing job
            job = db_session.query(ProcessingJob).filter(
                ProcessingJob.document_id == document_id
            ).first()
            job.status = JobStatus.COMPLETED
            job.progress_percentage = 100
            job.completed_at = time.time()
            job.result = json.dumps({
                'processed_text': document.content_text,
                'entities_extracted': 6,
                'processing_time': 2.3
            })
            db_session.commit()

            # Update document status
            document.processing_status = ProcessingStatus.COMPLETED
            document.processed_at = time.time()
            db_session.commit()

        # Step 5: Create entities in database
        entities_data = [
            Entity(
                name="Google Health",
                entity_type=EntityType.ORGANIZATION,
                confidence_score=0.95,
                extraction_method=ExtractionMethod.SPACY_NER,
                document_id=document_id,
                organization_id=test_organization.id,
                metadata={"position": [100, 112]}
            ),
            Entity(
                name="Microsoft Healthcare",
                entity_type=EntityType.ORGANIZATION,
                confidence_score=0.92,
                extraction_method=ExtractionMethod.SPACY_NER,
                document_id=document_id,
                organization_id=test_organization.id,
                metadata={"position": [140, 160]}
            ),
            Entity(
                name="Dr. Sarah Johnson",
                entity_type=EntityType.PERSON,
                confidence_score=0.98,
                extraction_method=ExtractionMethod.SPACY_NER,
                document_id=document_id,
                organization_id=test_organization.id,
                metadata={"position": [180, 198]}
            )
        ]

        for entity in entities_data:
            db_session.add(entity)
        db_session.commit()

        # Step 6: Verify processed document details
        doc_response = client.get(
            f"/api/v1/documents/{document_id}",
            headers=auth_headers
        )

        assert doc_response.status_code == 200
        doc_data = doc_response.json()
        assert doc_data["processing_status"] == ProcessingStatus.COMPLETED.value
        assert doc_data["processed_at"] is not None

        # Step 7: Test document search
        search_response = client.get(
            "/api/v1/documents/search?query=machine learning healthcare",
            headers=auth_headers
        )

        assert search_response.status_code == 200
        search_data = search_response.json()
        assert search_data["total"] >= 1

        # Step 8: Test entity-based search
        entity_search_response = client.get(
            "/api/v1/documents/search?entities=Google Health&entities=Dr. Sarah Johnson",
            headers=auth_headers
        )

        assert entity_search_response.status_code == 200

        # Step 9: Test document statistics
        stats_response = client.get(
            f"/api/v1/documents/{document_id}/statistics",
            headers=auth_headers
        )

        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert "entity_count" in stats_data
        assert "word_count" in stats_data

        # Step 10: Test document deletion with cleanup
        delete_response = client.delete(
            f"/api/v1/documents/{document_id}",
            headers=auth_headers
        )

        assert delete_response.status_code == 200
        delete_data = delete_response.json()
        assert delete_data["success"]

        # Verify cleanup
        deleted_doc = db_session.query(Document).filter(Document.id == document_id).first()
        assert deleted_doc is None

        deleted_entities = db_session.query(Entity).filter(
            Entity.document_id == document_id
        ).count()
        assert deleted_entities == 0

    def test_pdf_document_workflow(self, client, auth_headers, sample_pdf_document,
                                  db_session, test_admin_user, test_organization):
        """Test PDF document processing workflow"""
        # Upload PDF document
        with open(sample_pdf_document, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("financial_report.pdf", f, "application/pdf")},
                headers=auth_headers,
                data={"description": "Q4 2024 Financial Report"}
            )

        assert upload_response.status_code == 200
        document_id = upload_response.json()["document_id"]

        # Mock PDF processing with OCR
        with patch('src.services.processing_pipeline.ProcessingPipeline._process_pdf_content') as mock_pdf_process:
            mock_pdf_process.return_value = {
                'text_content': 'Financial Analysis Report - Q4 2024\nCompany: TechCorp Industries\nRevenue: $50.2M\nNet Income: $8.7M',
                'entities': [
                    {'name': 'TechCorp Industries', 'type': 'ORGANIZATION', 'confidence': 0.96},
                    {'name': 'finance@techcorp.com', 'type': 'EMAIL', 'confidence': 0.98},
                    {'name': '(555) 123-4567', 'type': 'PHONE', 'confidence': 0.94}
                ],
                'metadata': {
                    'pages_processed': 1,
                    'ocr_used': True,
                    'processing_time': 5.2
                }
            }

            # Start and complete processing
            client.post(f"/api/v1/documents/{document_id}/process", headers=auth_headers)

            job = db_session.query(ProcessingJob).filter(
                ProcessingJob.document_id == document_id
            ).first()
            job.status = JobStatus.COMPLETED
            job.completed_at = time.time()
            db_session.commit()

            document = db_session.query(Document).filter(Document.id == document_id).first()
            document.processing_status = ProcessingStatus.COMPLETED
            document.processed_at = time.time()
            db_session.commit()

        # Verify PDF processing results
        doc_response = client.get(f"/api/v1/documents/{document_id}", headers=auth_headers)
        assert doc_response.status_code == 200

        # Test financial content search
        search_response = client.get(
            "/api/v1/documents/search?query=revenue financial TechCorp",
            headers=auth_headers
        )
        assert search_response.status_code == 200

    def test_bulk_document_processing_workflow(self, client, auth_headers, temp_upload_dir,
                                             db_session, test_admin_user, test_organization):
        """Test bulk document processing workflow"""
        # Create multiple test documents
        documents_data = [
            {"filename": "doc1.txt", "content": "First document about artificial intelligence and deep learning"},
            {"filename": "doc2.txt", "content": "Second document about data science and machine learning"},
            {"filename": "doc3.txt", "content": "Third document about neural networks and computer vision"}
        ]

        document_ids = []

        # Upload documents
        for doc_data in documents_data:
            file_path = os.path.join(temp_upload_dir, doc_data["filename"])
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(doc_data["content"])

            with open(file_path, "rb") as f:
                upload_response = client.post(
                    "/api/v1/documents/upload",
                    files={"file": (doc_data["filename"], f, "text/plain")},
                    headers=auth_headers,
                    data={"description": f"Bulk test document {doc_data['filename']}"}
                )

            assert upload_response.status_code == 200
            document_ids.append(upload_response.json()["document_id"])

        # Start bulk processing
        bulk_process_response = client.post(
            "/api/v1/documents/bulk-process",
            json={"document_ids": document_ids},
            headers=auth_headers
        )

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
            job.completed_at = time.time()
            db_session.commit()

            document = db_session.query(Document).filter(Document.id == doc_id).first()
            document.processing_status = ProcessingStatus.COMPLETED
            document.processed_at = time.time()
            db_session.commit()

        # Verify all documents are processed
        documents_response = client.get(
            "/api/v1/documents?limit=20",
            headers=auth_headers
        )

        assert documents_response.status_code == 200
        docs_data = documents_response.json()

        processed_docs = [
            doc for doc in docs_data["items"]
            if doc["id"] in document_ids
        ]
        assert len(processed_docs) == 3
        assert all(doc["processing_status"] == ProcessingStatus.COMPLETED.value for doc in processed_docs)

        # Test cross-document search
        search_response = client.get(
            "/api/v1/documents/search?query=machine learning",
            headers=auth_headers
        )
        assert search_response.status_code == 200
        search_data = search_response.json()
        assert search_data["total"] >= 2  # Should find documents 1 and 2


class TestMultimodalProcessingWorkflow:
    """Test multimodal document processing workflows"""

    @pytest.fixture
    def sample_image_document(self, temp_upload_dir):
        """Create sample image document"""
        file_path = os.path.join(temp_upload_dir, "test_image.jpg")

        # Create a simple PNG image
        try:
            from PIL import Image, ImageDraw, ImageFont
            import numpy as np

            # Create a simple image with text
            img = Image.new('RGB', (800, 600), color='white')
            draw = ImageDraw.Draw(img)

            # Add some text to simulate a document
            try:
                font = ImageFont.truetype("arial.ttf", 24)
            except:
                font = ImageFont.load_default()

            draw.text((50, 50), "Invoice #12345", fill='black', font=font)
            draw.text((50, 100), "Company: Tech Solutions Inc.", fill='black', font=font)
            draw.text((50, 150), "Amount: $2,500.00", fill='black', font=font)
            draw.text((50, 200), "Date: 2024-01-15", fill='black', font=font)

            # Save as JPEG
            img.save(file_path, 'JPEG')

        except ImportError:
            # Fallback: create a simple binary file
            with open(file_path, "wb") as f:
                f.write(b"\xFF\xD8\xFF\xE0\x00\x10JFIF")  # JPEG header
                f.write(b"\x00" * 1000)  # Dummy content

        return file_path

    @pytest.fixture
    def sample_audio_document(self, temp_upload_dir):
        """Create sample audio document"""
        file_path = os.path.join(temp_upload_dir, "test_audio.mp3")

        # Create a simple audio file
        try:
            import wave
            import struct

            # Create a simple WAV file
            sample_rate = 44100
            duration = 2  # 2 seconds
            frequency = 440  # A4 note

            wav_file = wave.open(file_path.replace('.mp3', '.wav'), 'w')
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)

            # Generate sine wave
            for i in range(int(sample_rate * duration)):
                value = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
                wav_file.writeframes(struct.pack('<h', value))

            wav_file.close()

            # Rename to mp3 (for testing purposes)
            os.rename(file_path.replace('.mp3', '.wav'), file_path)

        except (ImportError, NameError):
            # Fallback: create a simple binary file
            with open(file_path, "wb") as f:
                f.write(b"ID3\x04\x00\x00\x00\x00\x00\x00")  # MP3 header
                f.write(b"\x00" * 2000)  # Dummy content

        return file_path

    def test_image_processing_workflow(self, client, auth_headers, sample_image_document,
                                     db_session, test_admin_user, test_organization):
        """Test image document processing workflow"""
        # Upload image document
        with open(sample_image_document, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("invoice.jpg", f, "image/jpeg")},
                headers=auth_headers,
                data={"description": "Invoice document image"}
            )

        assert upload_response.status_code == 200
        document_id = upload_response.json()["document_id"]

        # Mock image processing with OCR and object detection
        with patch('src.services.processing_pipeline.ProcessingPipeline._process_image_content') as mock_image_process:
            mock_image_process.return_value = {
                'text_content': 'Invoice #12345\nCompany: Tech Solutions Inc.\nAmount: $2,500.00\nDate: 2024-01-15',
                'entities': [
                    {'name': 'Tech Solutions Inc.', 'type': 'ORGANIZATION', 'confidence': 0.92},
                    {'name': '$2,500.00', 'type': 'MONEY', 'confidence': 0.95},
                    {'name': '2024-01-15', 'type': 'DATE', 'confidence': 0.98}
                ],
                'metadata': {
                    'ocr_confidence': 0.91,
                    'objects_detected': ['document', 'text'],
                    'processing_time': 3.8
                }
            }

            # Start and complete processing
            client.post(f"/api/v1/documents/{document_id}/process", headers=auth_headers)

            job = db_session.query(ProcessingJob).filter(
                ProcessingJob.document_id == document_id
            ).first()
            job.status = JobStatus.COMPLETED
            job.completed_at = time.time()
            db_session.commit()

            document = db_session.query(Document).filter(Document.id == document_id).first()
            document.processing_status = ProcessingStatus.COMPLETED
            document.processed_at = time.time()
            db_session.commit()

        # Verify image processing results
        doc_response = client.get(f"/api/v1/documents/{document_id}", headers=auth_headers)
        assert doc_response.status_code == 200

        # Test OCR text search
        search_response = client.get(
            "/api/v1/documents/search?query=invoice Tech Solutions",
            headers=auth_headers
        )
        assert search_response.status_code == 200

    def test_audio_processing_workflow(self, client, auth_headers, sample_audio_document,
                                     db_session, test_admin_user, test_organization):
        """Test audio document processing workflow"""
        # Upload audio document
        with open(sample_audio_document, "rb") as f:
            upload_response = client.post(
                "/api/v1/documents/upload",
                files={"file": ("meeting_audio.mp3", f, "audio/mpeg")},
                headers=auth_headers,
                data={"description": "Meeting recording"}
            )

        assert upload_response.status_code == 200
        document_id = upload_response.json()["document_id"]

        # Mock audio processing with transcription
        with patch('src.services.processing_pipeline.ProcessingPipeline._process_audio_content') as mock_audio_process:
            mock_audio_process.return_value = {
                'text_content': 'Welcome to the quarterly review meeting. Today we will discuss the financial results and strategic initiatives for the next quarter.',
                'entities': [
                    {'name': 'quarterly review', 'type': 'EVENT', 'confidence': 0.89},
                    {'name': 'financial results', 'type': 'CONCEPT', 'confidence': 0.92}
                ],
                'metadata': {
                    'duration_seconds': 120,
                    'transcription_confidence': 0.87,
                    'language_detected': 'en',
                    'processing_time': 15.2
                }
            }

            # Start and complete processing
            client.post(f"/api/v1/documents/{document_id}/process", headers=auth_headers)

            job = db_session.query(ProcessingJob).filter(
                ProcessingJob.document_id == document_id
            ).first()
            job.status = JobStatus.COMPLETED
            job.completed_at = time.time()
            db_session.commit()

            document = db_session.query(Document).filter(Document.id == document_id).first()
            document.processing_status = ProcessingStatus.COMPLETED
            document.processed_at = time.time()
            db_session.commit()

        # Verify audio processing results
        doc_response = client.get(f"/api/v1/documents/{document_id}", headers=auth_headers)
        assert doc_response.status_code == 200

        # Test transcription search
        search_response = client.get(
            "/api/v1/documents/search?query=financial quarterly meeting",
            headers=auth_headers
        )
        assert search_response.status_code == 200


class TestSearchAndRetrievalWorkflow:
    """Test search and retrieval workflows"""

    def test_hybrid_search_workflow(self, client, auth_headers, db_session,
                                  test_admin_user, test_organization):
        """Test hybrid search combining vector and keyword search"""
        # Create test documents with different content
        test_documents = [
            {
                "title": "Machine Learning Basics",
                "content": "Machine learning is a subset of artificial intelligence that focuses on algorithms and statistical models.",
                "entities": ["machine learning", "artificial intelligence", "algorithms"]
            },
            {
                "title": "Deep Learning Applications",
                "content": "Deep learning uses neural networks with multiple layers to analyze various forms of data.",
                "entities": ["deep learning", "neural networks", "data analysis"]
            },
            {
                "title": "Natural Language Processing",
                "content": "NLP enables computers to understand and process human language effectively.",
                "entities": ["Natural Language Processing", "NLP", "human language"]
            }
        ]

        document_ids = []

        # Create documents in database
        for doc_data in test_documents:
            document = Document(
                title=doc_data["title"],
                filename=f"search_test_{len(document_ids)}.txt",
                file_path=f"/test/search_test_{len(document_ids)}.txt",
                file_size_bytes=len(doc_data["content"]),
                mime_type="text/plain",
                document_type=DocumentType.TEXT,
                processing_status=ProcessingStatus.COMPLETED,
                content_text=doc_data["content"],
                processed_at=time.time(),
                organization_id=test_organization.id,
                uploaded_by_user_id=test_admin_user.id
            )
            db_session.add(document)
            db_session.flush()
            document_ids.append(document.id)

            # Create entities
            for entity_name in doc_data["entities"]:
                entity = Entity(
                    name=entity_name,
                    entity_type=EntityType.CONCEPT,
                    confidence_score=0.9,
                    extraction_method=ExtractionMethod.SPACY_NER,
                    document_id=document.id,
                    organization_id=test_organization.id
                )
                db_session.add(entity)

        db_session.commit()

        # Test keyword search
        keyword_response = client.get(
            "/api/v1/documents/search?query=machine learning algorithms",
            headers=auth_headers
        )
        assert keyword_response.status_code == 200
        keyword_data = keyword_response.json()
        assert keyword_data["total"] >= 1

        # Test semantic search (mock vector search)
        with patch('src.services.hybrid_search_service.HybridSearchService.search') as mock_hybrid_search:
            mock_hybrid_search.return_value = {
                "results": [
                    {
                        "document_id": document_ids[0],
                        "title": test_documents[0]["title"],
                        "score": 0.95,
                        "content_snippet": "Machine learning is a subset of artificial intelligence..."
                    },
                    {
                        "document_id": document_ids[1],
                        "title": test_documents[1]["title"],
                        "score": 0.87,
                        "content_snippet": "Deep learning uses neural networks with multiple layers..."
                    }
                ],
                "total": 2,
                "search_type": "hybrid"
            }

            semantic_response = client.get(
                "/api/v1/search/semantic?query=AI and machine learning methods",
                headers=auth_headers
            )
            assert semantic_response.status_code == 200

        # Test faceted search
        facet_response = client.get(
            "/api/v1/documents/search?query=learning&facets=true",
            headers=auth_headers
        )
        assert facet_response.status_code == 200

        # Test entity-based search
        entity_response = client.get(
            "/api/v1/documents/search?entities=machine learning&entities=neural networks",
            headers=auth_headers
        )
        assert entity_response.status_code == 200

        # Test search with filters
        filter_response = client.get(
            f"/api/v1/documents/search?query=learning&document_type=text&date_from=2024-01-01",
            headers=auth_headers
        )
        assert filter_response.status_code == 200

    def test_search_result_ranking_and_pagination(self, client, auth_headers, db_session,
                                                test_admin_user, test_organization):
        """Test search result ranking and pagination"""
        # Create multiple documents for pagination testing
        for i in range(15):
            document = Document(
                title=f"Search Test Document {i+1}",
                filename=f"search_pagination_{i+1}.txt",
                file_path=f"/test/search_pagination_{i+1}.txt",
                file_size_bytes=500,
                mime_type="text/plain",
                document_type=DocumentType.TEXT,
                processing_status=ProcessingStatus.COMPLETED,
                content_text=f"This is test document {i+1} about search functionality and pagination testing.",
                processed_at=time.time(),
                organization_id=test_organization.id,
                uploaded_by_user_id=test_admin_user.id
            )
            db_session.add(document)

        db_session.commit()

        # Test pagination
        page1_response = client.get(
            "/api/v1/documents/search?query=search test&limit=5&offset=0",
            headers=auth_headers
        )
        assert page1_response.status_code == 200
        page1_data = page1_response.json()
        assert len(page1_data["items"]) <= 5

        page2_response = client.get(
            "/api/v1/documents/search?query=search test&limit=5&offset=5",
            headers=auth_headers
        )
        assert page2_response.status_code == 200
        page2_data = page2_response.json()

        # Verify pagination works (no overlapping results)
        if page1_data["items"] and page2_data["items"]:
            page1_ids = {item["id"] for item in page1_data["items"]}
            page2_ids = {item["id"] for item in page2_data["items"]}
            assert len(page1_ids.intersection(page2_ids)) == 0


class TestUserManagementWorkflow:
    """Test user management and authentication workflows"""

    def test_complete_user_registration_workflow(self, client):
        """Test complete user registration and onboarding workflow"""
        # Step 1: Register new user (creates organization)
        registration_data = {
            "email": "newuser@company.com",
            "password": "StrongPassword123!",
            "first_name": "New",
            "last_name": "User",
            "organization_name": "New Company Inc."
        }

        register_response = client.post("/api/v1/auth/register", json=registration_data)
        assert register_response.status_code == 200
        register_data = register_response.json()
        assert "user" in register_data
        assert register_data["user"]["email"] == "newuser@company.com"
        assert register_data["user"]["role"] == "admin"  # First user becomes admin

        # Step 2: Login with new user
        login_response = client.post("/api/v1/auth/login", json={
            "email": "newuser@company.com",
            "password": "StrongPassword123!"
        })
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "access_token" in login_data
        assert "refresh_token" in login_data

        auth_headers = {"Authorization": f"Bearer {login_data['access_token']}"}

        # Step 3: Complete user profile
        profile_response = client.put("/api/v1/auth/me", headers=auth_headers, json={
            "first_name": "Updated",
            "last_name": "User",
            "phone": "+1-555-0123",
            "department": "Engineering"
        })
        assert profile_response.status_code == 200

        # Step 4: Get user details
        user_response = client.get("/api/v1/auth/me", headers=auth_headers)
        assert user_response.status_code == 200
        user_data = user_response.json()
        assert user_data["user"]["first_name"] == "Updated"

        # Step 5: Change password
        password_response = client.post("/api/v1/auth/change-password", headers=auth_headers, json={
            "current_password": "StrongPassword123!",
            "new_password": "NewStrongPassword456!"
        })
        assert password_response.status_code == 200

        # Step 6: Login with new password
        new_login_response = client.post("/api/v1/auth/login", json={
            "email": "newuser@company.com",
            "password": "NewStrongPassword456!"
        })
        assert new_login_response.status_code == 200

    def test_multi_user_organization_workflow(self, client, db_session):
        """Test multi-user organization management workflow"""
        # Create admin user
        admin_org = Organization(
            name="Multi-User Test Org",
            plan_tier="professional",
            max_users=10,
            storage_quota_gb=50.0,
            is_active=True
        )
        db_session.add(admin_org)
        db_session.commit()

        admin_user = User(
            email="admin@testorg.com",
            first_name="Admin",
            last_name="User",
            role=UserRole.ADMIN,
            organization_id=admin_org.id,
            is_active=True,
            email_verified=True
        )
        admin_user.set_password("AdminPassword123!")
        db_session.add(admin_user)
        db_session.commit()

        # Admin login
        admin_login_response = client.post("/api/v1/auth/login", json={
            "email": "admin@testorg.com",
            "password": "AdminPassword123!"
        })
        admin_token = admin_login_response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Create regular user
        regular_user_data = {
            "email": "regular@testorg.com",
            "password": "UserPassword123!",
            "first_name": "Regular",
            "last_name": "User"
        }

        create_user_response = client.post("/api/v1/auth/users", json=regular_user_data, headers=admin_headers)
        assert create_user_response.status_code == 200

        # Regular user login
        regular_login_response = client.post("/api/v1/auth/login", json={
            "email": "regular@testorg.com",
            "password": "UserPassword123!"
        })
        regular_token = regular_login_response.json()["access_token"]
        regular_headers = {"Authorization": f"Bearer {regular_token}"}

        # Test user permissions
        # Admin can see all users
        admin_users_response = client.get("/api/v1/auth/users", headers=admin_headers)
        assert admin_users_response.status_code == 200
        admin_users_data = admin_users_response.json()
        assert len(admin_users_data["users"]) >= 2

        # Regular user cannot see all users
        regular_users_response = client.get("/api/v1/auth/users", headers=regular_headers)
        assert regular_users_response.status_code == 403

        # Test user role update
        role_update_response = client.put(
            f"/api/v1/auth/users/{admin_users_data['users'][1]['id']}/role",
            headers=admin_headers,
            json={"role": "analyst"}
        )
        assert role_update_response.status_code == 200

        # Test user deactivation
        deactivate_response = client.post(
            f"/api/v1/auth/users/{admin_users_data['users'][1]['id']}/deactivate",
            headers=admin_headers
        )
        assert deactivate_response.status_code == 200


class TestMultiTenancyWorkflow:
    """Test multi-tenancy and data isolation workflows"""

    def test_organization_data_isolation(self, client, db_session):
        """Test that organizations cannot access each other's data"""
        # Create two organizations
        org1 = Organization(
            name="Organization One",
            plan_tier="professional",
            max_users=5,
            storage_quota_gb=10.0,
            is_active=True
        )
        org2 = Organization(
            name="Organization Two",
            plan_tier="professional",
            max_users=5,
            storage_quota_gb=10.0,
            is_active=True
        )
        db_session.add(org1)
        db_session.add(org2)
        db_session.commit()

        # Create users for each organization
        user1 = User(
            email="user1@org1.com",
            first_name="User",
            last_name="One",
            role=UserRole.USER,
            organization_id=org1.id,
            is_active=True,
            email_verified=True
        )
        user1.set_password("Password123!")

        user2 = User(
            email="user2@org2.com",
            first_name="User",
            last_name="Two",
            role=UserRole.USER,
            organization_id=org2.id,
            is_active=True,
            email_verified=True
        )
        user2.set_password("Password123!")

        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()

        # Login as both users
        user1_login = client.post("/api/v1/auth/login", json={
            "email": "user1@org1.com",
            "password": "Password123!"
        })
        user1_headers = {"Authorization": f"Bearer {user1_login.json()['access_token']}"}

        user2_login = client.post("/api/v1/auth/login", json={
            "email": "user2@org2.com",
            "password": "Password123!"
        })
        user2_headers = {"Authorization": f"Bearer {user2_login.json()['access_token']}"}

        # Create documents for each organization
        doc1 = Document(
            title="Org1 Secret Document",
            filename="org1_secret.txt",
            file_path="/test/org1_secret.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            processing_status=ProcessingStatus.COMPLETED,
            content_text="This is confidential information for Organization One",
            organization_id=org1.id,
            uploaded_by_user_id=user1.id
        )
        db_session.add(doc1)

        doc2 = Document(
            title="Org2 Secret Document",
            filename="org2_secret.txt",
            file_path="/test/org2_secret.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            processing_status=ProcessingStatus.COMPLETED,
            content_text="This is confidential information for Organization Two",
            organization_id=org2.id,
            uploaded_by_user_id=user2.id
        )
        db_session.add(doc2)
        db_session.commit()

        # Test data isolation - User1 should only see their documents
        user1_docs_response = client.get("/api/v1/documents", headers=user1_headers)
        assert user1_docs_response.status_code == 200
        user1_docs = user1_docs_response.json()["items"]

        for doc in user1_docs:
            assert doc["organization_id"] == org1.id
            assert doc["title"] != "Org2 Secret Document"

        # Test data isolation - User2 should only see their documents
        user2_docs_response = client.get("/api/v1/documents", headers=user2_headers)
        assert user2_docs_response.status_code == 200
        user2_docs = user2_docs_response.json()["items"]

        for doc in user2_docs:
            assert doc["organization_id"] == org2.id
            assert doc["title"] != "Org1 Secret Document"

        # Test search isolation
        search1_response = client.get("/api/v1/documents/search?query=confidential", headers=user1_headers)
        search1_data = search1_response.json()

        for doc in search1_data["items"]:
            assert doc["organization_id"] == org1.id

    def test_resource_quota_enforcement(self, client, db_session):
        """Test organization resource quota enforcement"""
        # Create organization with limited storage
        limited_org = Organization(
            name="Limited Storage Org",
            plan_tier="free",
            max_users=2,
            storage_quota_gb=1.0,  # 1GB limit
            is_active=True
        )
        db_session.add(limited_org)
        db_session.commit()

        # Create user
        user = User(
            email="user@limited.com",
            first_name="Limited",
            last_name="User",
            role=UserRole.USER,
            organization_id=limited_org.id,
            is_active=True,
            email_verified=True
        )
        user.set_password("Password123!")
        db_session.add(user)
        db_session.commit()

        # Login
        login_response = client.post("/api/v1/auth/login", json={
            "email": "user@limited.com",
            "password": "Password123!"
        })
        headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

        # Test organization statistics
        stats_response = client.get("/api/v1/organization/statistics", headers=headers)
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        assert "storage_used" in stats_data
        assert "storage_quota" in stats_data
        assert stats_data["storage_quota"] == 1.0