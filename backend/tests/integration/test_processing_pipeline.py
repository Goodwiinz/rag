"""
Integration tests for end-to-end document processing workflows
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import tempfile
import os

from src.services.file_service import FileService
from src.services.entity_extraction_service import EntityExtractionService
from src.services.image_processing_service import ImageProcessingService
from src.services.audio_processing_service import AudioProcessingService
from src.services.video_processing_service import VideoProcessingService
from src.services.processing_pipeline import ProcessingPipeline
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.processing import ProcessingJob, JobType, JobStatus
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.core.database import get_db
from src.core.celery_app import celery_app


class TestDocumentProcessingIntegration:
    """Test end-to-end document processing workflows"""

    @pytest.fixture
    def processing_pipeline(self, db_session):
        """Create processing pipeline with all services"""
        return ProcessingPipeline(db_session)

    @pytest.fixture
    def mock_celery_task(self):
        """Mock Celery task for testing"""
        with patch('src.services.processing_pipeline.process_document_task.delay') as mock_task:
            mock_task.return_value = AsyncMock(id='test-task-123')
            yield mock_task

    def test_text_document_end_to_end_processing(self, db_session, sample_text_file, test_user, test_organization, processing_pipeline, mock_celery_task):
        """Test complete processing workflow for text documents"""
        # Arrange
        file_service = FileService(db_session)

        # Create a mock upload file
        from fastapi import UploadFile
        mock_upload_file = UploadFile(
            filename="test_document.txt",
            file=open(sample_text_file, "rb")
        )

        # Act - Upload file
        upload_result = file_service.upload_file(
            file=mock_upload_file,
            user=test_user,
            organization=test_organization
        )

        # Assert - Upload successful
        assert upload_result['success']
        document_id = upload_result['document_id']

        # Verify document was created in database
        document = db_session.query(Document).filter(Document.id == document_id).first()
        assert document is not None
        assert document.status == ProcessingStatus.PENDING
        assert document.document_type == DocumentType.TEXT

        # Act - Start processing
        processing_result = processing_pipeline.start_processing(document_id)

        # Assert - Processing started
        assert processing_result['success']
        assert 'job_id' in processing_result

        # Verify processing job was created
        job = db_session.query(ProcessingJob).filter(
            ProcessingJob.document_id == document_id
        ).first()
        assert job is not None
        assert job.job_type == JobType.DOCUMENT_PROCESSING
        assert job.status == JobStatus.PENDING

        # Mock successful processing
        with patch('src.services.processing_pipeline.ProcessingPipeline._process_text_content') as mock_process_text:
            mock_process_text.return_value = {
                'text_content': 'Processed text content',
                'entities': [
                    {'name': 'John Doe', 'type': 'PERSON', 'confidence': 0.95},
                    {'name': 'Acme Corp', 'type': 'ORGANIZATION', 'confidence': 0.88}
                ],
                'metadata': {'word_count': 100, 'language': 'en'}
            }

            # Simulate processing completion
            job.status = JobStatus.COMPLETED
            job.progress_percentage = 100
            job.completed_at = datetime.utcnow()
            job.result = json.dumps({
                'processed_text': 'Processed text content',
                'entities_extracted': 2,
                'processing_time': 2.5
            })
            db_session.commit()

            # Verify final document state
            document = db_session.query(Document).filter(Document.id == document_id).first()
            assert document.status == ProcessingStatus.COMPLETED
            assert document.processed_at is not None
            assert document.text_content == 'Processed text content'

    def test_image_document_end_to_end_processing(self, db_session, sample_image_file, test_user, test_organization, processing_pipeline):
        """Test complete processing workflow for image documents"""
        # Arrange
        file_service = FileService(db_session)

        from fastapi import UploadFile
        mock_upload_file = UploadFile(
            filename="test_image.png",
            file=open(sample_image_file, "rb")
        )

        # Act - Upload file
        upload_result = file_service.upload_file(
            file=mock_upload_file,
            user=test_user,
            organization=test_organization
        )

        # Assert - Upload successful
        assert upload_result['success']
        document_id = upload_result['document_id']

        # Verify document was created
        document = db_session.query(Document).filter(Document.id == document_id).first()
        assert document is not None
        assert document.document_type == DocumentType.IMAGE

        # Act - Start processing
        processing_result = processing_pipeline.start_processing(document_id)

        # Assert - Processing started
        assert processing_result['success']

        # Mock image processing with OCR
        with patch('src.services.image_processing_service.ImageProcessingService.process_image') as mock_process:
            mock_process.return_value = {
                'extracted_text': 'Text extracted from image via OCR',
                'metadata': {
                    'width': 800,
                    'height': 600,
                    'format': 'PNG',
                    'ocr_confidence': 0.85
                },
                'quality_score': 0.9
            }

            # Simulate processing job completion
            job = db_session.query(ProcessingJob).filter(
                ProcessingJob.document_id == document_id
            ).first()
            job.status = JobStatus.COMPLETED
            job.progress_percentage = 100
            job.completed_at = datetime.utcnow()
            job.result = json.dumps({
                'ocr_text': 'Text extracted from image via OCR',
                'image_processed': True,
                'processing_time': 5.2
            })
            db_session.commit()

            # Verify final document state
            document = db_session.query(Document).filter(Document.id == document_id).first()
            assert document.status == ProcessingStatus.COMPLETED
            assert document.processed_at is not None

    def test_audio_document_end_to_end_processing(self, db_session, sample_audio_file, test_user, test_organization, processing_pipeline):
        """Test complete processing workflow for audio documents"""
        # Arrange
        file_service = FileService(db_session)

        from fastapi import UploadFile
        mock_upload_file = UploadFile(
            filename="test_audio.mp3",
            file=open(sample_audio_file, "rb")
        )

        # Act - Upload file
        upload_result = file_service.upload_file(
            file=mock_upload_file,
            user=test_user,
            organization=test_organization
        )

        # Assert - Upload successful
        assert upload_result['success']
        document_id = upload_result['document_id']

        # Verify document was created
        document = db_session.query(Document).filter(Document.id == document_id).first()
        assert document is not None
        assert document.document_type == DocumentType.AUDIO

        # Act - Start processing
        processing_result = processing_pipeline.start_processing(document_id)

        # Assert - Processing started
        assert processing_result['success']

        # Mock audio processing with transcription
        with patch('src.services.audio_processing_service.AudioProcessingService.process_audio') as mock_process:
            mock_process.return_value = {
                'transcription': 'Transcribed text from audio file',
                'metadata': {
                    'duration': 120.5,
                    'format': 'MP3',
                    'sample_rate': 44100,
                    'language': 'en'
                },
                'quality_score': 0.85
            }

            # Simulate processing job completion
            job = db_session.query(ProcessingJob).filter(
                ProcessingJob.document_id == document_id
            ).first()
            job.status = JobStatus.COMPLETED
            job.progress_percentage = 100
            job.completed_at = datetime.utcnow()
            job.result = json.dumps({
                'transcription': 'Transcribed text from audio file',
                'audio_processed': True,
                'processing_time': 15.3
            })
            db_session.commit()

            # Verify final document state
            document = db_session.query(Document).filter(Document.id == document_id).first()
            assert document.status == ProcessingStatus.COMPLETED
            assert document.processed_at is not None

    def test_video_document_end_to_end_processing(self, db_session, sample_video_file, test_user, test_organization, processing_pipeline):
        """Test complete processing workflow for video documents"""
        # Arrange
        file_service = FileService(db_session)

        from fastapi import UploadFile
        mock_upload_file = UploadFile(
            filename="test_video.mp4",
            file=open(sample_video_file, "rb")
        )

        # Act - Upload file
        upload_result = file_service.upload_file(
            file=mock_upload_file,
            user=test_user,
            organization=test_organization
        )

        # Assert - Upload successful
        assert upload_result['success']
        document_id = upload_result['document_id']

        # Verify document was created
        document = db_session.query(Document).filter(Document.id == document_id).first()
        assert document is not None
        assert document.document_type == DocumentType.VIDEO

        # Act - Start processing
        processing_result = processing_pipeline.start_processing(document_id)

        # Assert - Processing started
        assert processing_result['success']

        # Mock video processing with audio extraction
        with patch('src.services.video_processing_service.VideoProcessingService.process_video') as mock_process:
            mock_process.return_value = {
                'metadata': {
                    'duration': 300.0,
                    'width': 1920,
                    'height': 1080,
                    'format': 'MP4',
                    'fps': 30
                },
                'audio_transcription': 'Transcribed text from video audio track',
                'keyframes_data': {
                    'keyframe_count': 10,
                    'sample_frames': ['frame1.jpg', 'frame2.jpg']
                },
                'quality_score': 0.88
            }

            # Simulate processing job completion
            job = db_session.query(ProcessingJob).filter(
                ProcessingJob.document_id == document_id
            ).first()
            job.status = JobStatus.COMPLETED
            job.progress_percentage = 100
            job.completed_at = datetime.utcnow()
            job.result = json.dumps({
                'video_processed': True,
                'audio_extracted': True,
                'transcription': 'Transcribed text from video audio track',
                'processing_time': 45.7
            })
            db_session.commit()

            # Verify final document state
            document = db_session.query(Document).filter(Document.id == document_id).first()
            assert document.status == ProcessingStatus.COMPLETED
            assert document.processed_at is not None

    def test_bulk_document_processing_workflow(self, db_session, temp_upload_dir, test_user, test_organization, processing_pipeline):
        """Test processing multiple documents in bulk"""
        # Arrange - Create multiple test files
        test_files = []
        for i in range(3):
            file_path = os.path.join(temp_upload_dir, f"test_file_{i}.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Test content for file {i}. This contains entities like Test Corp and John Doe.")
            test_files.append(file_path)

        file_service = FileService(db_session)
        document_ids = []

        # Act - Upload multiple files
        for file_path in test_files:
            from fastapi import UploadFile
            mock_upload_file = UploadFile(
                filename=os.path.basename(file_path),
                file=open(file_path, "rb")
            )

            upload_result = file_service.upload_file(
                file=mock_upload_file,
                user=test_user,
                organization=test_organization
            )

            assert upload_result['success']
            document_ids.append(upload_result['document_id'])

        # Act - Start bulk processing
        bulk_result = processing_pipeline.start_bulk_processing(document_ids)

        # Assert - Bulk processing started
        assert bulk_result['success']
        assert len(bulk_result['job_ids']) == 3

        # Verify all processing jobs were created
        jobs = db_session.query(ProcessingJob).filter(
            ProcessingJob.document_id.in_(document_ids)
        ).all()
        assert len(jobs) == 3

        # Mock completion of all jobs
        for job in jobs:
            job.status = JobStatus.COMPLETED
            job.progress_percentage = 100
            job.completed_at = datetime.utcnow()
            job.result = json.dumps({
                'processed': True,
                'entities_extracted': 2,
                'processing_time': 2.1
            })
        db_session.commit()

        # Verify all documents are completed
        completed_documents = db_session.query(Document).filter(
            Document.id.in_(document_ids),
            Document.status == ProcessingStatus.COMPLETED
        ).all()
        assert len(completed_documents) == 3

    def test_processing_error_handling_workflow(self, db_session, sample_text_file, test_user, test_organization, processing_pipeline):
        """Test error handling in document processing workflow"""
        # Arrange
        file_service = FileService(db_session)

        from fastapi import UploadFile
        mock_upload_file = UploadFile(
            filename="test_file.txt",
            file=open(sample_text_file, "rb")
        )

        # Act - Upload file
        upload_result = file_service.upload_file(
            file=mock_upload_file,
            user=test_user,
            organization=test_organization
        )

        # Assert - Upload successful
        assert upload_result['success']
        document_id = upload_result['document_id']

        # Act - Start processing
        processing_result = processing_pipeline.start_processing(document_id)

        # Assert - Processing started
        assert processing_result['success']

        # Simulate processing failure
        job = db_session.query(ProcessingJob).filter(
            ProcessingJob.document_id == document_id
        ).first()

        job.status = JobStatus.FAILED
        job.error_message = "Simulated processing error: Entity extraction failed"
        job.completed_at = datetime.utcnow()
        job.retry_count = 1
        db_session.commit()

        # Verify document state reflects failure
        document = db_session.query(Document).filter(Document.id == document_id).first()
        assert document.status == ProcessingStatus.FAILED
        assert document.error_message is not None

        # Act - Retry processing
        retry_result = processing_pipeline.retry_processing(document_id)

        # Assert - Retry initiated
        assert retry_result['success']

        # Verify new job was created for retry
        retry_job = db_session.query(ProcessingJob).filter(
            ProcessingJob.document_id == document_id,
            ProcessingJob.status == JobStatus.PENDING
        ).first()
        assert retry_job is not None
        assert retry_job.retry_count == 2

    def test_processing_pipeline_status_tracking(self, db_session, sample_text_file, test_user, test_organization, processing_pipeline):
        """Test status tracking throughout processing pipeline"""
        # Arrange
        file_service = FileService(db_session)

        from fastapi import UploadFile
        mock_upload_file = UploadFile(
            filename="test_file.txt",
            file=open(sample_text_file, "rb")
        )

        # Act - Upload file
        upload_result = file_service.upload_file(
            file=mock_upload_file,
            user=test_user,
            organization=test_organization
        )

        document_id = upload_result['document_id']

        # Act - Start processing
        processing_result = processing_pipeline.start_processing(document_id)

        # Test status tracking at different stages
        job = db_session.query(ProcessingJob).filter(
            ProcessingJob.document_id == document_id
        ).first()

        # Initial status
        status_result = processing_pipeline.get_processing_status(document_id)
        assert status_result['document_id'] == document_id
        assert status_result['status'] == JobStatus.PENDING.value
        assert status_result['progress_percentage'] == 0

        # Update job with in-progress status
        job.status = JobStatus.IN_PROGRESS
        job.progress_percentage = 50
        job.current_step = "Extracting entities"
        db_session.commit()

        # Check in-progress status
        status_result = processing_pipeline.get_processing_status(document_id)
        assert status_result['status'] == JobStatus.IN_PROGRESS.value
        assert status_result['progress_percentage'] == 50
        assert status_result['current_step'] == "Extracting entities"

        # Complete processing
        job.status = JobStatus.COMPLETED
        job.progress_percentage = 100
        job.completed_at = datetime.utcnow()
        job.result = json.dumps({'processed': True})
        db_session.commit()

        # Check final status
        status_result = processing_pipeline.get_processing_status(document_id)
        assert status_result['status'] == JobStatus.COMPLETED.value
        assert status_result['progress_percentage'] == 100
        assert 'completed_at' in status_result

    def test_concurrent_document_processing(self, db_session, temp_upload_dir, test_user, test_organization, processing_pipeline):
        """Test concurrent processing of multiple documents"""
        # Arrange - Create multiple test files
        document_ids = []
        file_service = FileService(db_session)

        for i in range(5):
            file_path = os.path.join(temp_upload_dir, f"concurrent_test_{i}.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Concurrent test content {i}")

            from fastapi import UploadFile
            mock_upload_file = UploadFile(
                filename=f"concurrent_test_{i}.txt",
                file=open(file_path, "rb")
            )

            upload_result = file_service.upload_file(
                file=mock_upload_file,
                user=test_user,
                organization=test_organization
            )

            document_ids.append(upload_result['document_id'])

        # Act - Start processing for all documents concurrently
        processing_results = []
        for doc_id in document_ids:
            result = processing_pipeline.start_processing(doc_id)
            processing_results.append(result)

        # Assert - All processing jobs started
        assert all(result['success'] for result in processing_results)

        # Verify all jobs exist and are in pending state
        jobs = db_session.query(ProcessingJob).filter(
            ProcessingJob.document_id.in_(document_ids)
        ).all()
        assert len(jobs) == 5
        assert all(job.status == JobStatus.PENDING for job in jobs)

        # Mock concurrent processing completion
        for i, job in enumerate(jobs):
            job.status = JobStatus.COMPLETED
            job.progress_percentage = 100
            job.completed_at = datetime.utcnow() + timedelta(seconds=i)
            job.result = json.dumps({
                'processed': True,
                'concurrent_id': i,
                'processing_time': 1.5 + i * 0.2
            })
        db_session.commit()

        # Verify all documents completed successfully
        completed_docs = db_session.query(Document).filter(
            Document.id.in_(document_ids),
            Document.status == ProcessingStatus.COMPLETED
        ).all()
        assert len(completed_docs) == 5

    def test_processing_pipeline_cleanup(self, db_session, sample_text_file, test_user, test_organization, processing_pipeline):
        """Test cleanup operations in processing pipeline"""
        # Arrange
        file_service = FileService(db_session)

        from fastapi import UploadFile
        mock_upload_file = UploadFile(
            filename="test_file.txt",
            file=open(sample_text_file, "rb")
        )

        # Upload and process file
        upload_result = file_service.upload_file(
            file=mock_upload_file,
            user=test_user,
            organization=test_organization
        )

        document_id = upload_result['document_id']
        processing_pipeline.start_processing(document_id)

        # Complete processing
        job = db_session.query(ProcessingJob).filter(
            ProcessingJob.document_id == document_id
        ).first()
        job.status = JobStatus.COMPLETED
        job.progress_percentage = 100
        job.completed_at = datetime.utcnow()
        db_session.commit()

        # Act - Clean up old completed jobs
        cleanup_result = processing_pipeline.cleanup_old_jobs(days_old=1)

        # Assert - Cleanup completed successfully
        assert cleanup_result['success']
        assert 'jobs_cleaned' in cleanup_result

        # Verify job is still there (within retention period)
        remaining_job = db_session.query(ProcessingJob).filter(
            ProcessingJob.document_id == document_id
        ).first()
        assert remaining_job is not None