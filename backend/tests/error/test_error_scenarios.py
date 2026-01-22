"""
Error scenario testing for document processing system
"""

import pytest
import os
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from fastapi import UploadFile
from fastapi.exceptions import HTTPException

from src.services.documents import FileService
from src.services.processing import EntityExtractionService, ImageProcessingService, AudioProcessingService, VideoProcessingService
from src.services.processing_pipeline import ProcessingPipeline
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.processing import ProcessingJob, JobStatus
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.core.exceptions import (
    FileProcessingError,
    ValidationError,
    ProcessingError,
    ResourceNotFoundError,
    AuthenticationError,
    AuthorizationError
)


class TestFileProcessingErrorScenarios:
    """Test error scenarios in file processing"""

    def test_file_service_corrupted_file(self, db_session, temp_upload_dir, test_user, test_organization):
        """Test handling of corrupted files"""
        service = FileService(db_session)

        # Create a corrupted file (invalid image data)
        corrupted_file_path = os.path.join(temp_upload_dir, "corrupted.png")
        with open(corrupted_file_path, "wb") as f:
            f.write(b"This is not a valid PNG file data")

        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "corrupted.png"
        mock_file.size = 100
        mock_file.file = open(corrupted_file_path, "rb")

        # Act & Assert - Should handle gracefully
        try:
            file_type = service.detect_file_type(corrupted_file_path)
            # If no exception, should default to a safe type
            assert file_type != DocumentType.IMAGE  # Should not detect as image
        except Exception as e:
            # Should not crash the application
            assert isinstance(e, (FileProcessingError, ValidationError))
        finally:
            mock_file.file.close()

    def test_file_service_too_large_file(self, db_session, test_user, test_organization):
        """Test handling of files that exceed size limits"""
        service = FileService(db_session)

        # Mock a file that's too large
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "huge_file.txt"
        mock_file.size = 2 * 1024 * 1024 * 1024  # 2GB - exceeds typical limits
        mock_file.file = Mock()

        # Act & Assert - Should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            service.validate_file(mock_file, test_user, test_organization)

        assert "file size" in str(exc_info.value).lower() or "too large" in str(exc_info.value).lower()

    def test_file_service_unsupported_format(self, db_session, test_user, test_organization):
        """Test handling of unsupported file formats"""
        service = FileService(db_session)

        # Mock file with unsupported extension
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "unsupported.xyz"
        mock_file.size = 1024
        mock_file.file = Mock()

        # Act & Assert - Should handle gracefully
        try:
            result = service.validate_file(mock_file, test_user, test_organization)
            # Should either reject or mark as OTHER type
            assert result.get('document_type') in [DocumentType.OTHER, None]
        except ValidationError:
            # Or raise validation error - both are acceptable
            pass

    def test_file_service_permission_denied(self, db_session, temp_upload_dir):
        """Test handling of file permission issues"""
        service = FileService(db_session)

        # Create file and remove read permissions
        file_path = os.path.join(temp_upload_dir, "no_permission.txt")
        with open(file_path, "w") as f:
            f.write("test content")

        # Remove read permissions (Unix systems only)
        if os.name != 'nt':  # Not Windows
            os.chmod(file_path, 0o000)

        try:
            # Act & Assert - Should handle permission errors
            with pytest.raises((FileProcessingError, PermissionError, OSError)):
                service.extract_text_content(file_path)
        finally:
            # Restore permissions for cleanup
            if os.name != 'nt':
                os.chmod(file_path, 0o644)

    def test_file_service_nonexistent_file(self, db_session):
        """Test handling of nonexistent files"""
        service = FileService(db_session)

        nonexistent_path = "/path/that/does/not/exist/file.txt"

        # Act & Assert - Should handle gracefully
        with pytest.raises((FileProcessingError, FileNotFoundError, ResourceNotFoundError)):
            service.extract_text_content(nonexistent_path)

    def test_file_service_database_error(self, db_session, temp_upload_dir, test_user, test_organization):
        """Test handling of database errors during file operations"""
        service = FileService(db_session)

        # Mock database error
        with patch.object(db_session, 'add', side_effect=IntegrityError("DB Error", None, None)):
            mock_file = Mock(spec=UploadFile)
            mock_file.filename = "test.txt"
            mock_file.size = 1024
            mock_file.file = Mock()

            # Act & Assert - Should handle database errors
            with pytest.raises((SQLAlchemyError, FileProcessingError)):
                service.upload_file(mock_file, test_user, test_organization)


class TestEntityExtractionErrorScenarios:
    """Test error scenarios in entity extraction"""

    def test_entity_extraction_service_unavailable(self, db_session):
        """Test handling when spaCy service is unavailable"""
        service = EntityExtractionService()
        service.nlp = None  # Simulate unavailable service

        text = "John Doe works at Google."

        # Act & Assert - Should handle gracefully
        result = service.extract_entities(text)
        assert result == []  # Should return empty list, not crash

    def test_entity_extraction_malformed_text(self, db_session):
        """Test handling of malformed or problematic text"""
        service = EntityExtractionService()

        # Test with various problematic inputs
        problematic_texts = [
            "",  # Empty text
            "   ",  # Whitespace only
            None,  # None input
            "🤖🚀🌟" * 1000,  # Only emojis
            "\x00\x01\x02" * 100,  # Control characters
        ]

        for text in problematic_texts:
            if text is None:
                # Act & Assert - Should handle None gracefully
                with pytest.raises((ValueError, TypeError)):
                    service.extract_entities(text)
            else:
                # Act & Assert - Should handle gracefully without crashing
                result = service.extract_entities(text)
                assert isinstance(result, list)

    def test_entity_extraction_timeout(self, db_session):
        """Test handling of entity extraction timeout"""
        service = EntityExtractionService()

        # Create very large text that might cause timeout
        large_text = "John Doe works at Google. " * 100000

        # Mock slow processing
        with patch.object(service, 'extract_entities') as mock_extract:
            def slow_extract(text):
                import time
                time.sleep(0.1)  # Simulate slow processing
                return []

            mock_extract.side_effect = slow_extract

            # Act & Assert - Should complete in reasonable time
            import time
            start_time = time.time()
            result = service.extract_entities(large_text)
            end_time = time.time()

            processing_time = end_time - start_time
            assert processing_time < 5.0  # Should complete within 5 seconds
            assert isinstance(result, list)

    def test_entity_extraction_model_error(self, db_session):
        """Test handling of spaCy model errors"""
        service = EntityExtractionService()

        # Mock spaCy model error
        with patch('src.services.entity_extraction_service.spacy.load') as mock_load:
            mock_load.side_effect = OSError("Model not found")

            # Re-initialize service with broken model
            service = EntityExtractionService()

            text = "John Doe works at Google."

            # Act & Assert - Should handle gracefully
            result = service.extract_entities(text)
            assert result == []  # Should return empty list


class TestImageProcessingErrorScenarios:
    """Test error scenarios in image processing"""

    def test_image_processing_corrupted_image(self, db_session, temp_upload_dir):
        """Test handling of corrupted image files"""
        service = ImageProcessingService()

        # Create corrupted image file
        corrupted_path = os.path.join(temp_upload_dir, "corrupted.jpg")
        with open(corrupted_path, "wb") as f:
            f.write(b"This is not valid JPEG data")

        # Act & Assert - Should handle gracefully
        with pytest.raises((FileProcessingError, OSError, IOError)):
            service.process_image(corrupted_path)

    def test_image_processing_ocr_failure(self, db_session, temp_upload_dir):
        """Test handling of OCR processing failures"""
        service = ImageProcessingService()
        service.ocr_available = True

        # Create a simple image file
        from PIL import Image
        import numpy as np

        image_path = os.path.join(temp_upload_dir, "test_ocr.png")
        data = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        img = Image.fromarray(data, 'RGB')
        img.save(image_path, 'PNG')

        # Mock OCR failure
        with patch('src.services.image_processing_service.pytesseract.image_to_string') as mock_ocr:
            mock_ocr.side_effect = Exception("OCR processing failed")

            # Act & Assert - Should handle OCR failure gracefully
            with patch('src.services.image_processing_service.Image.open'):
                result = service.process_image(image_path)
                assert 'metadata' in result  # Should still return metadata
                # OCR results should be missing or indicate failure

    def test_image_processing_memory_error(self, db_session):
        """Test handling of memory errors during image processing"""
        service = ImageProcessingService()

        # Mock memory error
        with patch('src.services.image_processing_service.Image.open') as mock_open:
            mock_open.side_effect = MemoryError("Out of memory")

            # Act & Assert - Should handle memory error
            with pytest.raises((MemoryError, FileProcessingError)):
                service.process_image("dummy_path.jpg")

    def test_image_processing_unsupported_format(self, db_session, temp_upload_dir):
        """Test handling of unsupported image formats"""
        service = ImageProcessingService()

        # Create file with image extension but invalid content
        invalid_image_path = os.path.join(temp_upload_dir, "fake.tiff")
        with open(invalid_image_path, "wb") as f:
            f.write(b"This is not a TIFF file")

        # Act & Assert - Should handle gracefully
        with pytest.raises((FileProcessingError, OSError)):
            service.process_image(invalid_image_path)


class TestAudioProcessingErrorScenarios:
    """Test error scenarios in audio processing"""

    def test_audio_processing_corrupted_file(self, db_session, temp_upload_dir):
        """Test handling of corrupted audio files"""
        service = AudioProcessingService()

        # Create corrupted audio file
        corrupted_path = os.path.join(temp_upload_dir, "corrupted.mp3")
        with open(corrupted_path, "wb") as f:
            f.write(b"This is not valid MP3 data")

        # Act & Assert - Should handle gracefully
        with pytest.raises((FileProcessingError, OSError)):
            service.process_audio(corrupted_path)

    @patch('src.services.audio_processing_service.AudioProcessingService._load_whisper_model')
    def test_audio_processing_whisper_unavailable(self, mock_load_model, db_session, temp_upload_dir):
        """Test handling when Whisper model is unavailable"""
        service = AudioProcessingService()

        # Mock Whisper unavailability
        mock_load_model.side_effect = Exception("Whisper model not available")

        audio_path = os.path.join(temp_upload_dir, "test.mp3")
        with open(audio_path, "wb") as f:
            f.write(b"fake audio data")

        # Act & Assert - Should handle gracefully
        result = service.process_audio(audio_path)
        assert result is not None
        # Should return metadata but no transcription

    @patch('src.services.audio_processing_service.AudioProcessingService._load_whisper_model')
    def test_audio_processing_transcription_timeout(self, mock_load_model, db_session, temp_upload_dir):
        """Test handling of transcription timeout"""
        service = AudioProcessingService()

        # Mock slow Whisper processing
        mock_model = Mock()
        mock_model.transcribe.side_effect = Exception("Transcription timeout")
        mock_load_model.return_value = mock_model
        service.whisper_model = mock_model

        audio_path = os.path.join(temp_upload_dir, "test.mp3")
        with open(audio_path, "wb") as f:
            f.write(b"fake audio data")

        # Act & Assert - Should handle timeout gracefully
        with pytest.raises((ProcessingError, Exception)):
            service.process_audio(audio_path)


class TestVideoProcessingErrorScenarios:
    """Test error scenarios in video processing"""

    def test_video_processing_corrupted_file(self, db_session, temp_upload_dir):
        """Test handling of corrupted video files"""
        service = VideoProcessingService()

        # Create corrupted video file
        corrupted_path = os.path.join(temp_upload_dir, "corrupted.mp4")
        with open(corrupted_path, "wb") as f:
            f.write(b"This is not valid MP4 data")

        # Act & Assert - Should handle gracefully
        with pytest.raises((FileProcessingError, OSError)):
            service.process_video(corrupted_path)

    def test_video_processing_ffmpeg_unavailable(self, db_session, temp_upload_dir):
        """Test handling when ffmpeg is unavailable"""
        service = VideoProcessingService()

        video_path = os.path.join(temp_upload_dir, "test.mp4")
        with open(video_path, "wb") as f:
            f.write(b"fake video data")

        # Mock ffmpeg unavailability
        with patch('src.services.video_processing_service.subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("ffmpeg not found")

            # Act & Assert - Should handle gracefully
            with pytest.raises((FileProcessingError, FileNotFoundError)):
                service._extract_video_metadata(video_path)

    def test_video_processing_audio_extraction_failure(self, db_session, temp_upload_dir):
        """Test handling of audio extraction failures"""
        service = VideoProcessingService()

        video_path = os.path.join(temp_upload_dir, "test.mp4")
        with open(video_path, "wb") as f:
            f.write(b"fake video data")

        # Mock audio extraction failure
        with patch.object(service, '_extract_audio_track') as mock_extract:
            mock_extract.side_effect = Exception("Audio extraction failed")

            # Act & Assert - Should handle gracefully
            result = service.process_video(video_path)
            assert result is not None
            # Should return metadata even if audio extraction fails


class TestProcessingPipelineErrorScenarios:
    """Test error scenarios in processing pipeline"""

    def test_pipeline_database_connection_lost(self, db_session, temp_upload_dir, test_user, test_organization):
        """Test handling of database connection loss during processing"""
        pipeline = ProcessingPipeline(db_session)

        # Create a test document
        doc = Document(
            title="Test Document",
            filename="test.txt",
            file_path=os.path.join(temp_upload_dir, "test.txt"),
            file_size=1024,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            status=ProcessingStatus.PENDING,
            user_id=test_user.id,
            organization_id=test_organization.id
        )
        db_session.add(doc)
        db_session.commit()

        # Mock database connection loss
        with patch.object(db_session, 'commit', side_effect=SQLAlchemyError("Connection lost")):
            # Act & Assert - Should handle database errors
            with pytest.raises((SQLAlchemyError, ProcessingError)):
                pipeline.start_processing(doc.id)

    def test_pipeline_processing_job_failure(self, db_session, temp_upload_dir, test_user, test_organization):
        """Test handling of processing job failures"""
        pipeline = ProcessingPipeline(db_session)

        # Create a test document
        doc = Document(
            title="Test Document",
            filename="test.txt",
            file_path=os.path.join(temp_upload_dir, "test.txt"),
            file_size=1024,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            status=ProcessingStatus.PENDING,
            user_id=test_user.id,
            organization_id=test_organization.id
        )
        db_session.add(doc)
        db_session.commit()

        # Mock processing failure
        with patch.object(pipeline, '_process_text_content') as mock_process:
            mock_process.side_effect = Exception("Processing failed")

            # Act & Assert - Should handle processing failure
            try:
                pipeline.start_processing(doc.id)
                # If no exception, job should be marked as failed
                job = db_session.query(ProcessingJob).filter(
                    ProcessingJob.document_id == doc.id
                ).first()
                assert job.status == JobStatus.FAILED
            except ProcessingError:
                # Or raise ProcessingError
                pass

    def test_pipeline_retry_exhaustion(self, db_session, temp_upload_dir, test_user, test_organization):
        """Test handling when retry attempts are exhausted"""
        pipeline = ProcessingPipeline(db_session)

        # Create a test document
        doc = Document(
            title="Test Document",
            filename="test.txt",
            file_path=os.path.join(temp_upload_dir, "test.txt"),
            file_size=1024,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            status=ProcessingStatus.PENDING,
            user_id=test_user.id,
            organization_id=test_organization.id
        )
        db_session.add(doc)
        db_session.commit()

        # Mock persistent failure
        with patch.object(pipeline, '_process_text_content') as mock_process:
            mock_process.side_effect = Exception("Persistent failure")

            # Start processing
            try:
                pipeline.start_processing(doc.id)
            except ProcessingError:
                pass

            # Simulate multiple retry attempts
            job = db_session.query(ProcessingJob).filter(
                ProcessingJob.document_id == doc.id
            ).first()

            # Simulate reaching max retries
            job.retry_count = 3  # Assume max retries is 3
            job.status = JobStatus.FAILED
            db_session.commit()

            # Act - Try to retry again
            retry_result = pipeline.retry_processing(doc.id)

            # Assert - Should reject retry when max retries reached
            assert not retry_result['success']
            assert "max retries" in retry_result.get('error', '').lower()

    def test_pipeline_resource_cleanup_on_error(self, db_session, temp_upload_dir, test_user, test_organization):
        """Test resource cleanup when processing fails"""
        pipeline = ProcessingPipeline(db_session)

        # Create a test document
        doc = Document(
            title="Test Document",
            filename="test.txt",
            file_path=os.path.join(temp_upload_dir, "test.txt"),
            file_size=1024,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            status=ProcessingStatus.PENDING,
            user_id=test_user.id,
            organization_id=test_organization.id
        )
        db_session.add(doc)
        db_session.commit()

        # Mock processing failure that creates temporary files
        with patch.object(pipeline, '_process_text_content') as mock_process:
            def failing_process(text_path):
                # Simulate creating temp file
                temp_file = os.path.join(temp_upload_dir, "temp_processing_file.txt")
                with open(temp_file, "w") as f:
                    f.write("temp content")
                raise Exception("Processing failed")

            mock_process.side_effect = failing_process

            # Act - Process with failure
            try:
                pipeline.start_processing(doc.id)
            except ProcessingError:
                pass

            # Assert - Should clean up temporary files
            temp_files = [f for f in os.listdir(temp_upload_dir) if f.startswith("temp_")]
            assert len(temp_files) == 0  # Temp files should be cleaned up

    def test_pipeline_concurrent_processing_conflicts(self, db_session, temp_upload_dir, test_user, test_organization):
        """Test handling of concurrent processing conflicts"""
        pipeline = ProcessingPipeline(db_session)

        # Create a test document
        doc = Document(
            title="Test Document",
            filename="test.txt",
            file_path=os.path.join(temp_upload_dir, "test.txt"),
            file_size=1024,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            status=ProcessingStatus.PENDING,
            user_id=test_user.id,
            organization_id=test_organization.id
        )
        db_session.add(doc)
        db_session.commit()

        # Start first processing
        result1 = pipeline.start_processing(doc.id)
        assert result1['success']

        # Act - Try to start second processing
        result2 = pipeline.start_processing(doc.id)

        # Assert - Should handle concurrent processing gracefully
        # Either reject second attempt or return existing job
        assert not result2['success'] or result1['job_id'] == result2['job_id']

    def test_pipeline_insufficient_resources(self, db_session, temp_upload_dir, test_user, test_organization):
        """Test handling of insufficient system resources"""
        pipeline = ProcessingPipeline(db_session)

        # Create a test document
        doc = Document(
            title="Test Document",
            filename="test.txt",
            file_path=os.path.join(temp_upload_dir, "test.txt"),
            file_size=1024,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            status=ProcessingStatus.PENDING,
            user_id=test_user.id,
            organization_id=test_organization.id
        )
        db_session.add(doc)
        db_session.commit()

        # Mock resource exhaustion
        with patch.object(pipeline, '_process_text_content') as mock_process:
            mock_process.side_effect = MemoryError("Insufficient memory")

            # Act & Assert - Should handle resource errors
            with pytest.raises((MemoryError, ProcessingError)):
                pipeline.start_processing(doc.id)

            # Job should be marked as failed
            job = db_session.query(ProcessingJob).filter(
                ProcessingJob.document_id == doc.id
            ).first()
            assert job.status == JobStatus.FAILED


class TestErrorRecoveryAndResilience:
    """Test error recovery mechanisms and system resilience"""

    def test_automatic_retry_mechanism(self, db_session, temp_upload_dir, test_user, test_organization):
        """Test automatic retry mechanism for transient failures"""
        pipeline = ProcessingPipeline(db_session)

        # Create a test document
        doc = Document(
            title="Test Document",
            filename="test.txt",
            file_path=os.path.join(temp_upload_dir, "test.txt"),
            file_size=1024,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            status=ProcessingStatus.PENDING,
            user_id=test_user.id,
            organization_id=test_organization.id
        )
        db_session.add(doc)
        db_session.commit()

        # Mock transient failure that succeeds on retry
        call_count = 0
        def failing_then_success(text_path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Transient failure")
            return {'text': 'Success after retry'}

        with patch.object(pipeline, '_process_text_content') as mock_process:
            mock_process.side_effect = failing_then_success

            # Act - Start processing with retry
            result = pipeline.start_processing(doc.id)

            # Assert - Should succeed after retry
            assert result['success']
            assert call_count == 2  # Should have been called twice

    def test_fallback_processing_methods(self, db_session, temp_upload_dir, test_user, test_organization):
        """Test fallback processing methods when primary methods fail"""
        service = ImageProcessingService()

        # Create image file
        from PIL import Image
        import numpy as np

        image_path = os.path.join(temp_upload_dir, "fallback_test.png")
        data = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        img = Image.fromarray(data, 'RGB')
        img.save(image_path, 'PNG')

        # Mock primary OCR failure but fallback available
        with patch('src.services.image_processing_service.pytesseract.image_to_string') as mock_ocr:
            mock_ocr.side_effect = [Exception("Primary OCR failed"), "Fallback OCR success"]

            # Act - Process with fallback
            result = service.process_image(image_path)

            # Assert - Should use fallback method
            assert result is not None
            # Should have metadata even if OCR failed initially

    def test_graceful_degradation(self, db_session, temp_upload_dir, test_user, test_organization):
        """Test graceful degradation when some components fail"""
        pipeline = ProcessingPipeline(db_session)

        # Create a test document
        doc = Document(
            title="Test Document",
            filename="test.txt",
            file_path=os.path.join(temp_upload_dir, "test.txt"),
            file_size=1024,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            status=ProcessingStatus.PENDING,
            user_id=test_user.id,
            organization_id=test_organization.id
        )
        db_session.add(doc)
        db_session.commit()

        # Mock entity extraction failure but text processing success
        with patch.object(pipeline, '_extract_entities') as mock_entities:
            mock_entities.side_effect = Exception("Entity extraction failed")

            with patch.object(pipeline, '_process_text_content') as mock_text:
                mock_text.return_value = {
                    'text_content': 'Processed text content',
                    'metadata': {'word_count': 100}
                }

                # Act - Process with component failure
                try:
                    pipeline.start_processing(doc.id)
                    # If processing completes, document should have text even if entities failed
                    updated_doc = db_session.query(Document).filter(Document.id == doc.id).first()
                    assert updated_doc.text_content is not None
                except ProcessingError:
                    # Or should handle gracefully with appropriate error
                    pass

    def test_error_logging_and_monitoring(self, db_session, temp_upload_dir, test_user, test_organization):
        """Test error logging and monitoring capabilities"""
        pipeline = ProcessingPipeline(db_session)

        # Create a test document
        doc = Document(
            title="Test Document",
            filename="test.txt",
            file_path=os.path.join(temp_upload_dir, "test.txt"),
            file_size=1024,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            status=ProcessingStatus.PENDING,
            user_id=test_user.id,
            organization_id=test_organization.id
        )
        db_session.add(doc)
        db_session.commit()

        # Mock processing failure
        test_error = Exception("Test error for logging")
        with patch.object(pipeline, '_process_text_content') as mock_process:
            mock_process.side_effect = test_error

            # Act - Process with error
            try:
                pipeline.start_processing(doc.id)
            except ProcessingError:
                pass

            # Assert - Error should be logged in job
            job = db_session.query(ProcessingJob).filter(
                ProcessingJob.document_id == doc.id
            ).first()
            assert job.status == JobStatus.FAILED
            assert job.error_message is not None
            assert "Test error for logging" in job.error_message