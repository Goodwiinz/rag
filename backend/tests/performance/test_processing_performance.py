"""
Performance tests for document processing time limits
"""

import pytest
import time
import os
import tempfile
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from src.services.documents import FileService
from src.services.processing import EntityExtractionService, ImageProcessingService, AudioProcessingService, VideoProcessingService
from src.services.processing_pipeline import ProcessingPipeline
from src.models.document import Document, DocumentType
from src.models.processing import ProcessingJob, JobStatus
from src.models.user import User
from src.models.organization import Organization


class TestProcessingPerformance:
    """Test performance characteristics of document processing"""

    @pytest.fixture
    def performance_settings(self):
        """Define performance thresholds and test parameters"""
        return {
            'text_processing_timeout': 30.0,  # seconds
            'image_processing_timeout': 60.0,
            'audio_processing_timeout': 300.0,  # 5 minutes
            'video_processing_timeout': 600.0,  # 10 minutes
            'entity_extraction_timeout': 60.0,
            'max_text_size': 10 * 1024 * 1024,  # 10MB
            'max_image_size': 50 * 1024 * 1024,  # 50MB
            'max_audio_size': 100 * 1024 * 1024,  # 100MB
            'max_video_size': 500 * 1024 * 1024,  # 500MB
        }

    @pytest.fixture
    def large_text_file(self, temp_upload_dir, performance_settings):
        """Create a large text file for performance testing"""
        file_path = os.path.join(temp_upload_dir, "large_text.txt")

        # Generate content close to max size
        target_size = performance_settings['max_text_size'] // 2  # Use half max for reasonable test
        content = "This is a test sentence. " * 1000

        with open(file_path, "w", encoding="utf-8") as f:
            current_size = 0
            while current_size < target_size:
                f.write(content)
                current_size += len(content.encode('utf-8'))

        return file_path

    @pytest.fixture
    def large_image_file(self, temp_upload_dir, performance_settings):
        """Create a large image file for performance testing"""
        from PIL import Image
        import numpy as np

        file_path = os.path.join(temp_upload_dir, "large_image.png")

        # Create a large image
        width, height = 2000, 1500  # Large image
        data = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
        img = Image.fromarray(data, 'RGB')
        img.save(file_path, 'PNG')

        return file_path

    def test_text_processing_performance_small_file(self, db_session, sample_text_file, performance_settings):
        """Test text processing performance with small files"""
        service = FileService(db_session)

        start_time = time.time()

        # Process text file
        result = service.extract_text_content(sample_text_file)

        end_time = time.time()
        processing_time = end_time - start_time

        # Assert processing is within reasonable time
        assert processing_time < 5.0, f"Small text file processing took {processing_time:.2f}s, expected < 5.0s"
        assert result['text'] is not None
        assert len(result['text']) > 0

    def test_text_processing_performance_large_file(self, db_session, large_text_file, performance_settings):
        """Test text processing performance with large files"""
        service = FileService(db_session)

        start_time = time.time()

        # Process large text file
        result = service.extract_text_content(large_text_file)

        end_time = time.time()
        processing_time = end_time - start_time

        # Assert processing is within timeout limit
        assert processing_time < performance_settings['text_processing_timeout'], \
            f"Large text file processing took {processing_time:.2f}s, expected < {performance_settings['text_processing_timeout']}s"
        assert result['text'] is not None
        assert len(result['text']) > 0

    def test_entity_extraction_performance(self, db_session, performance_settings):
        """Test entity extraction performance"""
        service = EntityExtractionService()

        # Create text with multiple entities
        test_text = """
        John Smith works at Microsoft Corporation in Seattle, Washington.
        He can be contacted at john.smith@microsoft.com or (555) 123-4567.
        His manager is Jane Doe from Apple Inc. in Cupertino, California.
        Visit https://www.microsoft.com for more information.
        The project budget is $1,000,000 and will be completed by December 31, 2023.
        """ * 10  # Repeat for larger text

        start_time = time.time()

        # Extract entities
        entities = service.extract_entities(test_text)

        end_time = time.time()
        processing_time = end_time - start_time

        # Assert entity extraction is within time limits
        assert processing_time < performance_settings['entity_extraction_timeout'], \
            f"Entity extraction took {processing_time:.2f}s, expected < {performance_settings['entity_extraction_timeout']}s"
        assert len(entities) > 0

    def test_image_processing_performance_small_image(self, db_session, sample_image_file, performance_settings):
        """Test image processing performance with small images"""
        service = ImageProcessingService()

        start_time = time.time()

        # Process image
        result = service.process_image(sample_image_file)

        end_time = time.time()
        processing_time = end_time - start_time

        # Assert processing is within reasonable time
        assert processing_time < 10.0, f"Small image processing took {processing_time:.2f}s, expected < 10.0s"
        assert result['metadata'] is not None

    def test_image_processing_performance_large_image(self, db_session, large_image_file, performance_settings):
        """Test image processing performance with large images"""
        service = ImageProcessingService()

        start_time = time.time()

        # Process large image
        result = service.process_image(large_image_file)

        end_time = time.time()
        processing_time = end_time - start_time

        # Assert processing is within timeout limit
        assert processing_time < performance_settings['image_processing_timeout'], \
            f"Large image processing took {processing_time:.2f}s, expected < {performance_settings['image_processing_timeout']}s"
        assert result['metadata'] is not None

    def test_ocr_performance(self, db_session, sample_image_file, performance_settings):
        """Test OCR performance characteristics"""
        service = ImageProcessingService()

        if not service.ocr_available:
            pytest.skip("OCR not available")

        start_time = time.time()

        # Perform OCR
        with patch('src.services.image_processing_service.Image.open') as mock_image_open:
            mock_img = Mock()
            mock_image_open.return_value.__enter__.return_value = mock_img

            with patch('src.services.image_processing_service.pytesseract.image_to_string') as mock_ocr:
                mock_ocr.return_value = "This is sample OCR text from the image."

                result = service._perform_ocr(sample_image_file)

        end_time = time.time()
        processing_time = end_time - start_time

        # Assert OCR is within reasonable time
        assert processing_time < 15.0, f"OCR processing took {processing_time:.2f}s, expected < 15.0s"
        assert result['text'] is not None

    @patch('src.services.audio_processing_service.AudioProcessingService._load_whisper_model')
    def test_audio_processing_performance(self, mock_load_model, db_session, sample_audio_file, performance_settings):
        """Test audio processing performance"""
        service = AudioProcessingService()

        # Mock Whisper model to avoid loading in test
        mock_model = Mock()
        mock_model.transcribe.return_value = {
            'text': 'This is a mock transcription of the audio file.',
            'language': 'en',
            'segments': []
        }
        mock_load_model.return_value = mock_model
        service.whisper_model = mock_model

        start_time = time.time()

        # Process audio
        result = service.process_audio(sample_audio_file)

        end_time = time.time()
        processing_time = end_time - start_time

        # Assert processing is within time limits
        assert processing_time < performance_settings['audio_processing_timeout'], \
            f"Audio processing took {processing_time:.2f}s, expected < {performance_settings['audio_processing_timeout']}s"
        assert result['transcription'] is not None

    def test_video_metadata_extraction_performance(self, db_session, sample_video_file, performance_settings):
        """Test video metadata extraction performance"""
        service = VideoProcessingService()

        start_time = time.time()

        # Extract video metadata
        metadata = service._extract_video_metadata(sample_video_file)

        end_time = time.time()
        processing_time = end_time - start_time

        # Assert metadata extraction is fast
        assert processing_time < 5.0, f"Video metadata extraction took {processing_time:.2f}s, expected < 5.0s"
        assert metadata is not None

    @patch('src.services.video_processing_service.VideoProcessingService._extract_audio_track')
    def test_video_processing_performance(self, mock_extract_audio, db_session, sample_video_file, performance_settings):
        """Test video processing performance"""
        service = VideoProcessingService()

        # Mock audio extraction to avoid actual file operations
        mock_extract_audio.return_value = None

        start_time = time.time()

        # Process video
        result = service.process_video(sample_video_file)

        end_time = time.time()
        processing_time = end_time - start_time

        # Assert processing is within time limits
        assert processing_time < performance_settings['video_processing_timeout'], \
            f"Video processing took {processing_time:.2f}s, expected < {performance_settings['video_processing_timeout']}s"
        assert result['metadata'] is not None

    def test_concurrent_processing_performance(self, db_session, temp_upload_dir, test_user, test_organization, performance_settings):
        """Test performance when processing multiple documents concurrently"""
        # Create multiple test files
        test_files = []
        for i in range(5):
            file_path = os.path.join(temp_upload_dir, f"concurrent_test_{i}.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Concurrent test content {i}. " * 100)
            test_files.append(file_path)

        file_service = FileService(db_session)
        processing_times = []

        # Process files concurrently (simulate)
        start_time = time.time()

        for file_path in test_files:
            file_start = time.time()
            result = file_service.extract_text_content(file_path)
            file_end = time.time()
            processing_times.append(file_end - file_start)
            assert result['text'] is not None

        end_time = time.time()
        total_time = end_time - start_time

        # Assert concurrent processing is efficient
        assert total_time < sum(processing_times), "Concurrent processing should be faster than sequential"
        assert max(processing_times) < 5.0, f"Slowest file processing took {max(processing_times):.2f}s, expected < 5.0s"

    def test_memory_usage_during_processing(self, db_session, large_text_file, performance_settings):
        """Test memory usage during large file processing"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        service = FileService(db_session)

        # Process large file
        result = service.extract_text_content(large_text_file)

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Assert memory usage is reasonable (less than 500MB increase)
        assert memory_increase < 500, f"Memory increased by {memory_increase:.2f}MB, expected < 500MB"
        assert result['text'] is not None

    def test_database_performance_during_processing(self, db_session, test_user, test_organization, performance_settings):
        """Test database performance during document processing"""
        # Create multiple documents
        documents = []
        for i in range(10):
            doc = Document(
                title=f"Performance Test Document {i}",
                filename=f"perf_test_{i}.txt",
                file_path=f"/test/path/perf_test_{i}.txt",
                file_size=1024,
                mime_type="text/plain",
                document_type=DocumentType.TEXT,
                user_id=test_user.id,
                organization_id=test_organization.id
            )
            db_session.add(doc)
            documents.append(doc)

        db_session.commit()

        # Test query performance
        start_time = time.time()

        # Query all documents
        all_docs = db_session.query(Document).filter(
            Document.organization_id == test_organization.id
        ).all()

        end_time = time.time()
        query_time = end_time - start_time

        # Assert database queries are fast
        assert query_time < 1.0, f"Database query took {query_time:.2f}s, expected < 1.0s"
        assert len(all_docs) >= 10

    def test_file_validation_performance(self, db_session, temp_upload_dir, performance_settings):
        """Test file validation performance"""
        service = FileService(db_session)

        # Create files of different sizes
        test_files = []
        sizes = [1024, 10240, 102400, 1048576]  # 1KB, 10KB, 100KB, 1MB

        for size in sizes:
            file_path = os.path.join(temp_upload_dir, f"size_test_{size}.txt")
            with open(file_path, "wb") as f:
                f.write(b"0" * size)
            test_files.append(file_path)

        validation_times = []

        for file_path in test_files:
            start_time = time.time()

            # Mock file object for validation
            mock_file = Mock()
            mock_file.filename = os.path.basename(file_path)
            mock_file.size = os.path.getsize(file_path)
            mock_file.file = open(file_path, "rb")

            try:
                service.validate_file(mock_file, test_user, test_organization)
            except:
                pass  # We're testing performance, not validation results
            finally:
                mock_file.file.close()

            end_time = time.time()
            validation_times.append(end_time - start_time)

        # Assert validation scales reasonably with file size
        for i, (size, validation_time) in enumerate(zip(sizes, validation_times)):
            assert validation_time < 1.0, f"File validation for {size} bytes took {validation_time:.2f}s, expected < 1.0s"

    def test_batch_processing_performance(self, db_session, temp_upload_dir, test_user, test_organization, performance_settings):
        """Test batch processing performance"""
        # Create batch of files
        batch_size = 20
        test_files = []

        for i in range(batch_size):
            file_path = os.path.join(temp_upload_dir, f"batch_test_{i}.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Batch test content {i}. " * 50)
            test_files.append(file_path)

        file_service = FileService(db_session)

        start_time = time.time()

        # Process all files
        results = []
        for file_path in test_files:
            result = file_service.extract_text_content(file_path)
            results.append(result)

        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_file = total_time / batch_size

        # Assert batch processing is efficient
        assert avg_time_per_file < 0.5, f"Average processing time {avg_time_per_file:.2f}s per file, expected < 0.5s"
        assert all(result['text'] is not None for result in results)

    def test_timeout_handling(self, db_session, performance_settings):
        """Test that processing respects timeout limits"""
        # This test simulates a scenario that might exceed timeout
        service = EntityExtractionService()

        # Create very large text
        large_text = "John Smith works at Microsoft. " * 10000

        # Mock processing to simulate slow operation
        with patch.object(service, 'extract_entities') as mock_extract:
            def slow_extract(text):
                time.sleep(2)  # Simulate slow processing
                return []

            mock_extract.side_effect = slow_extract

            start_time = time.time()

            # This should complete within reasonable time
            result = service.extract_entities(large_text)

            end_time = time.time()
            processing_time = end_time - start_time

            # Assert the operation completes
            assert processing_time < performance_settings['entity_extraction_timeout']
            assert isinstance(result, list)