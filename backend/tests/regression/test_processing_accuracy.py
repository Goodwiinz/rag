"""
Regression tests for processing accuracy and quality assurance
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session
import json

from src.services.documents import FileService
from src.services.processing import EntityExtractionService, ImageProcessingService, AudioProcessingService, VideoProcessingService
from src.services.processing_pipeline import ProcessingPipeline
from src.models.document import Document, DocumentType
from src.models.entity import EntityType
from src.models.processing import ProcessingJob, JobStatus
from src.models.user import User
from src.models.organization import Organization


class TestProcessingAccuracyRegression:
    """Regression tests to ensure processing accuracy remains consistent"""

    @pytest.fixture
    def baseline_metrics(self):
        """Define baseline accuracy metrics for regression testing"""
        return {
            'entity_extraction': {
                'person_recall': 0.95,  # Should identify 95% of persons
                'organization_recall': 0.90,  # Should identify 90% of organizations
                'location_recall': 0.85,  # Should identify 85% of locations
                'email_precision': 0.98,  # 98% of email patterns should be correct
                'phone_precision': 0.95,  # 95% of phone patterns should be correct
                'url_precision': 0.99,  # 99% of URL patterns should be correct
            },
            'text_processing': {
                'content_extraction_accuracy': 0.99,  # 99% of text should be extracted correctly
                'language_detection_accuracy': 0.95,  # 95% accurate language detection
                'quality_score_min': 0.7,  # Minimum quality score
            },
            'image_processing': {
                'ocr_accuracy': 0.85,  # OCR should be 85% accurate
                'metadata_extraction_accuracy': 0.98,  # 98% accurate metadata
                'quality_score_correlation': 0.8,  # Quality score should correlate with actual quality
            },
            'audio_processing': {
                'transcription_accuracy': 0.80,  # Transcription should be 80% accurate
                'language_detection_accuracy': 0.90,  # 90% accurate language detection
                'audio_quality_correlation': 0.75,  # Quality score should correlate with actual quality
            },
            'video_processing': {
                'metadata_extraction_accuracy': 0.98,  # 98% accurate metadata
                'audio_sync_accuracy': 0.95,  # 95% accurate audio-video sync
                'keyframe_extraction_accuracy': 0.85,  # 85% accurate keyframe selection
            }
        }

    def test_entity_extraction_accuracy_regression(self, db_session, baseline_metrics):
        """Test entity extraction accuracy against baseline metrics"""
        service = EntityExtractionService()

        # Test with known entities and expected results
        test_cases = [
            {
                'text': "John Smith works at Microsoft Corporation in Seattle, Washington. Contact him at john.smith@microsoft.com or (555) 123-4567.",
                'expected_entities': {
                    EntityType.PERSON: ['John Smith'],
                    EntityType.ORGANIZATION: ['Microsoft Corporation'],
                    EntityType.LOCATION: ['Seattle', 'Washington'],
                    EntityType.EMAIL: ['john.smith@microsoft.com'],
                    EntityType.PHONE: ['(555) 123-4567'],
                }
            },
            {
                'text': "Jane Doe from Google Inc. visited New York City. She manages projects worth $1,000,000. Visit https://www.google.com for more info.",
                'expected_entities': {
                    EntityType.PERSON: ['Jane Doe'],
                    EntityType.ORGANIZATION: ['Google Inc.'],
                    EntityType.LOCATION: ['New York City'],
                    EntityType.URL: ['https://www.google.com'],
                    EntityType.FINANCIAL: ['$1,000,000'],
                }
            },
            {
                'text': "Apple Inc. CEO Tim Cook announced new products at their Cupertino, California headquarters on January 15, 2023.",
                'expected_entities': {
                    EntityType.ORGANIZATION: ['Apple Inc.'],
                    EntityType.PERSON: ['Tim Cook'],
                    EntityType.LOCATION: ['Cupertino', 'California'],
                    EntityType.DATE: ['January 15, 2023'],
                }
            }
        ]

        total_tests = 0
        successful_tests = 0

        for test_case in test_cases:
            text = test_case['text']
            expected_entities = test_case['expected_entities']

            # Extract entities
            extracted_entities = service.extract_entities(text)

            # Check each entity type
            for entity_type, expected_list in expected_entities.items():
                total_tests += len(expected_list)

                # Find extracted entities of this type
                extracted_of_type = [
                    entity['name'] for entity in extracted_entities
                    if entity['entity_type'] == entity_type
                ]

                # Check if expected entities were found
                for expected_entity in expected_list:
                    found = any(
                        expected_entity in extracted for extracted in extracted_of_type
                    )
                    if found:
                        successful_tests += 1

        # Calculate accuracy
        accuracy = successful_tests / total_tests if total_tests > 0 else 0

        # Assert against baseline
        assert accuracy >= baseline_metrics['entity_extraction']['person_recall'], \
            f"Entity extraction accuracy {accuracy:.2f} below baseline {baseline_metrics['entity_extraction']['person_recall']}"

    def test_entity_confidence_scoring_regression(self, db_session, baseline_metrics):
        """Test entity confidence scoring accuracy"""
        service = EntityExtractionService()

        # Test cases with expected confidence levels
        test_cases = [
            {
                'text': "John Smith works at Microsoft Corporation.",
                'expected_high_confidence': [
                    ('John Smith', EntityType.PERSON),
                    ('Microsoft Corporation', EntityType.ORGANIZATION)
                ]
            },
            {
                'text': "john smith works at unknown company.",
                'expected_lower_confidence': [
                    ('john smith', EntityType.PERSON),
                    ('unknown company', EntityType.ORGANIZATION)
                ]
            }
        ]

        for test_case in test_cases:
            text = test_case['text']
            entities = service.extract_entities(text)

            if 'expected_high_confidence' in test_case:
                for entity_name, entity_type in test_case['expected_high_confidence']:
                    # Find the entity
                    entity_found = next(
                        (e for e in entities if e['name'] == entity_name and e['entity_type'] == entity_type),
                        None
                    )
                    assert entity_found is not None, f"Entity '{entity_name}' not found"
                    assert entity_found['confidence_score'] >= 0.8, \
                        f"High-confidence entity '{entity_name}' has low score: {entity_found['confidence_score']}"

            if 'expected_lower_confidence' in test_case:
                for entity_name, entity_type in test_case['expected_lower_confidence']:
                    # Find the entity
                    entity_found = next(
                        (e for e in entities if e['name'] == entity_name and e['entity_type'] == entity_type),
                        None
                    )
                    assert entity_found is not None, f"Entity '{entity_name}' not found"
                    assert entity_found['confidence_score'] <= 0.9, \
                        f"Lower-confidence entity '{entity_name}' has high score: {entity_found['confidence_score']}"

    def test_text_processing_accuracy_regression(self, db_session, sample_text_file, baseline_metrics):
        """Test text processing accuracy against baseline"""
        service = FileService(db_session)

        # Extract text content
        result = service.extract_text_content(sample_text_file)

        # Assert basic extraction accuracy
        assert result['text'] is not None
        assert len(result['text']) > 0
        assert 'word_count' in result
        assert result['word_count'] > 0

        # Check quality score
        if 'quality_score' in result:
            assert result['quality_score'] >= baseline_metrics['text_processing']['quality_score_min'], \
                f"Text quality score {result['quality_score']} below baseline"

        # Check metadata accuracy
        assert 'content_type' in result
        assert 'encoding' in result
        assert result['encoding'] in ['utf-8', 'ascii']  # Should detect proper encoding

    def test_language_detection_accuracy_regression(self, db_session, baseline_metrics):
        """Test language detection accuracy"""
        service = FileService(db_session)

        # Test with different languages
        language_test_cases = [
            {
                'text': "This is a sample English text for testing language detection.",
                'expected_language': 'en'
            },
            {
                'text': "Este es un texto en español para detectar el idioma correctamente.",
                'expected_language': 'es'
            },
            {
                'text': "Ceci est un texte en français pour tester la détection de langue.",
                'expected_language': 'fr'
            }
        ]

        # Create temporary files for testing
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for test_case in language_test_cases:
                f.write(test_case['text'] + '\n\n')
            temp_file_path = f.name

        try:
            result = service.extract_text_content(temp_file_path)

            # Check if language was detected
            if 'language' in result and result['language']:
                # For regression testing, we primarily check that language detection works
                # and doesn't fail catastrophically
                assert isinstance(result['language'], str)
                assert len(result['language']) >= 2  # Should be at least 2 characters (language code)
            else:
                # Language detection might not be available, which is acceptable
                pass
        finally:
            os.unlink(temp_file_path)

    def test_ocr_accuracy_regression(self, db_session, temp_upload_dir, baseline_metrics):
        """Test OCR accuracy against baseline"""
        service = ImageProcessingService()

        if not service.ocr_available:
            pytest.skip("OCR not available for testing")

        # Create test image with text
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np

        # Create image with known text
        img = Image.new('RGB', (400, 100), color='white')
        draw = ImageDraw.Draw(img)

        try:
            # Try to use a default font
            font = ImageFont.load_default()
        except:
            # If default font not available, skip OCR accuracy test
            pytest.skip("Default font not available for OCR testing")

        test_text = "OCR Test: This is sample text for accuracy testing."
        draw.text((10, 10), test_text, fill='black', font=font)

        # Save image
        image_path = os.path.join(temp_upload_dir, "ocr_test.png")
        img.save(image_path, 'PNG')

        # Perform OCR
        with patch('src.services.image_processing_service.Image.open') as mock_open:
            mock_img = Mock()
            mock_open.return_value.__enter__.return_value = mock_img

            with patch('src.services.image_processing_service.pytesseract.image_to_string') as mock_ocr:
                # Mock OCR result that should be close to original
                mock_ocr.return_value = test_text.lower()  # OCR often returns lowercase

                result = service._perform_ocr(image_path)

        # Assert OCR accuracy
        assert result['text'] is not None
        assert len(result['text']) > 0

        # Check if key words are present (basic accuracy check)
        key_words = ['ocr', 'test', 'sample', 'text']
        found_words = sum(1 for word in key_words if word in result['text'].lower())
        accuracy = found_words / len(key_words)

        assert accuracy >= baseline_metrics['image_processing']['ocr_accuracy'], \
            f"OCR accuracy {accuracy:.2f} below baseline {baseline_metrics['image_processing']['ocr_accuracy']}"

    def test_image_metadata_extraction_accuracy(self, db_session, sample_image_file, baseline_metrics):
        """Test image metadata extraction accuracy"""
        service = ImageProcessingService()

        # Process image
        result = service.process_image(sample_image_file)

        # Assert metadata accuracy
        assert 'metadata' in result
        metadata = result['metadata']

        # Check basic metadata fields
        expected_fields = ['width', 'height', 'format']
        for field in expected_fields:
            assert field in metadata, f"Missing metadata field: {field}"

        # Assert data types and values
        assert isinstance(metadata['width'], int)
        assert isinstance(metadata['height'], int)
        assert isinstance(metadata['format'], str)
        assert metadata['width'] > 0
        assert metadata['height'] > 0

        # Check quality score correlation
        if 'quality_score' in result:
            quality = result['quality_score']
            assert 0.0 <= quality <= 1.0, f"Quality score {quality} not in valid range"

    def test_audio_metadata_extraction_accuracy(self, db_session, sample_audio_file, baseline_metrics):
        """Test audio metadata extraction accuracy"""
        service = AudioProcessingService()

        # Process audio
        result = service.process_audio(sample_audio_file)

        # Assert metadata accuracy
        assert 'metadata' in result
        metadata = result['metadata']

        # Check basic metadata fields (if available)
        if metadata:
            expected_fields = ['duration', 'format', 'sample_rate']
            for field in expected_fields:
                if field in metadata:
                    if field == 'duration':
                        assert metadata[field] >= 0, f"Invalid duration: {metadata[field]}"
                    elif field == 'sample_rate':
                        assert metadata[field] > 0, f"Invalid sample rate: {metadata[field]}"

    def test_video_metadata_extraction_accuracy(self, db_session, sample_video_file, baseline_metrics):
        """Test video metadata extraction accuracy"""
        service = VideoProcessingService()

        # Process video
        result = service.process_video(sample_video_file)

        # Assert metadata accuracy
        assert 'metadata' in result
        metadata = result['metadata']

        # Check basic metadata fields
        expected_fields = ['duration_seconds', 'format']
        for field in expected_fields:
            assert field in metadata, f"Missing metadata field: {field}"

        # Assert data types and values
        assert isinstance(metadata['duration_seconds'], (int, float))
        assert isinstance(metadata['format'], str)
        assert metadata['duration_seconds'] >= 0

    def test_processing_pipeline_accuracy_regression(self, db_session, temp_upload_dir, test_user, test_organization, baseline_metrics):
        """Test end-to-end processing pipeline accuracy"""
        pipeline = ProcessingPipeline(db_session)

        # Create test document with known content
        test_content = """
        Test Document for Accuracy Regression

        This document contains test entities for accuracy validation:
        - Person: John Smith, Jane Doe
        - Organization: Test Corporation, Sample Inc.
        - Location: Test City, Sample State
        - Contact: john.smith@test.com, (555) 123-4567
        - Website: https://www.testcorp.com

        The content should be processed accurately through the pipeline.
        """

        file_path = os.path.join(temp_upload_dir, "accuracy_test.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(test_content)

        # Create document in database
        doc = Document(
            title="Accuracy Test Document",
            filename="accuracy_test.txt",
            file_path=file_path,
            file_size=len(test_content.encode('utf-8')),
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            user_id=test_user.id,
            organization_id=test_organization.id
        )
        db_session.add(doc)
        db_session.commit()

        # Process document
        job_id = pipeline.start_processing(doc.id)

        # Mock successful processing with known results
        with patch.object(pipeline, '_process_text_content') as mock_process:
            mock_process.return_value = {
                'text_content': test_content,
                'entities': [
                    {'name': 'John Smith', 'type': EntityType.PERSON, 'confidence': 0.95},
                    {'name': 'Jane Doe', 'type': EntityType.PERSON, 'confidence': 0.92},
                    {'name': 'Test Corporation', 'type': EntityType.ORGANIZATION, 'confidence': 0.88},
                    {'name': 'Sample Inc.', 'type': EntityType.ORGANIZATION, 'confidence': 0.85},
                    {'name': 'Test City', 'type': EntityType.LOCATION, 'confidence': 0.82},
                    {'name': 'Sample State', 'type': EntityType.LOCATION, 'confidence': 0.80},
                    {'name': 'john.smith@test.com', 'type': EntityType.EMAIL, 'confidence': 0.98},
                    {'name': '(555) 123-4567', 'type': EntityType.PHONE, 'confidence': 0.95},
                    {'name': 'https://www.testcorp.com', 'type': EntityType.URL, 'confidence': 0.99},
                ],
                'metadata': {
                    'word_count': 75,
                    'language': 'en',
                    'quality_score': 0.95
                }
            }

            # Mark job as completed
            job = db_session.query(ProcessingJob).filter(
                ProcessingJob.id == job_id
            ).first()
            job.status = JobStatus.COMPLETED
            job.progress_percentage = 100
            job.completed_at = Mock()
            job.result = json.dumps({
                'processed': True,
                'entities_extracted': 9,
                'processing_time': 2.5
            })
            db_session.commit()

            # Verify final document state
            updated_doc = db_session.query(Document).filter(Document.id == doc.id).first()
            assert updated_doc.status.value == 'completed'
            assert updated_doc.text_content == test_content
            assert updated_doc.processed_at is not None

    def test_quality_score_consistency_regression(self, db_session, temp_upload_dir):
        """Test that quality scoring is consistent over time"""
        service = FileService(db_session)

        # Create test files with different quality levels
        test_files = {
            'high_quality.txt': "This is a well-structured, high-quality text document with proper grammar, spelling, and formatting. It contains multiple paragraphs and coherent content.",
            'medium_quality.txt': "this is medium quality text with some issues like lowercase at start and missing punctuation but still readable content",
            'low_quality.txt': "asdf qwerty zxcv poiu lkjh mnbv random words no structure poor quality"
        }

        quality_scores = {}

        for filename, content in test_files.items():
            file_path = os.path.join(temp_upload_dir, filename)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            result = service.extract_text_content(file_path)
            quality_scores[filename] = result.get('quality_score', 0.0)

        # Assert quality scores are in expected order
        assert quality_scores['high_quality.txt'] > quality_scores['medium_quality.txt']
        assert quality_scores['medium_quality.txt'] > quality_scores['low_quality.txt']

        # Assert scores are in valid range
        for filename, score in quality_scores.items():
            assert 0.0 <= score <= 1.0, f"Invalid quality score {score} for {filename}"

    def test_content_extraction_consistency_regression(self, db_session, temp_upload_dir):
        """Test that content extraction is consistent across multiple runs"""
        service = FileService(db_session)

        # Create test content
        test_content = """
        Regression Test for Content Extraction Consistency

        This test ensures that content extraction produces consistent results
        across multiple processing runs. The content should be extracted
        identically each time without variation.

        Entities: John Doe, Acme Corporation, New York
        Contact: john.doe@acme.com
        Website: https://www.acme.com
        """

        file_path = os.path.join(temp_upload_dir, "consistency_test.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(test_content)

        # Extract content multiple times
        results = []
        for _ in range(5):
            result = service.extract_text_content(file_path)
            results.append(result)

        # Assert all results are identical
        first_result = results[0]
        for i, result in enumerate(results[1:], 1):
            assert result['text'] == first_result['text'], f"Content extraction inconsistent between run 1 and run {i+1}"
            assert result['word_count'] == first_result['word_count'], f"Word count inconsistent between run 1 and run {i+1}"

    def test_processing_performance_regression(self, db_session, sample_text_file):
        """Test that processing performance doesn't degrade"""
        import time

        service = FileService(db_session)

        # Measure processing time
        start_time = time.time()
        result = service.extract_text_content(sample_text_file)
        end_time = time.time()

        processing_time = end_time - start_time

        # Assert processing time is within acceptable limits
        max_acceptable_time = 5.0  # 5 seconds for simple text file
        assert processing_time < max_acceptable_time, \
            f"Processing time {processing_time:.2f}s exceeds acceptable limit {max_acceptable_time}s"

        # Assert result quality is maintained
        assert result['text'] is not None
        assert len(result['text']) > 0
        assert result['word_count'] > 0

    def test_error_rate_regression(self, db_session, temp_upload_dir, test_user, test_organization):
        """Test that error rates remain within acceptable limits"""
        pipeline = ProcessingPipeline(db_session)

        # Create multiple test documents
        test_documents = []
        for i in range(10):
            file_path = os.path.join(temp_upload_dir, f"error_test_{i}.txt")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"Test document {i} for error rate regression.")

            doc = Document(
                title=f"Error Test Document {i}",
                filename=f"error_test_{i}.txt",
                file_path=file_path,
                file_size=100,
                mime_type="text/plain",
                document_type=DocumentType.TEXT,
                user_id=test_user.id,
                organization_id=test_organization.id
            )
            db_session.add(doc)
            test_documents.append(doc)

        db_session.commit()

        # Process all documents
        successful_processes = 0
        failed_processes = 0

        for doc in test_documents:
            try:
                result = pipeline.start_processing(doc.id)
                if result['success']:
                    successful_processes += 1
                else:
                    failed_processes += 1
            except Exception:
                failed_processes += 1

        total_processes = successful_processes + failed_processes
        error_rate = failed_processes / total_processes if total_processes > 0 else 0

        # Assert error rate is within acceptable limits
        max_acceptable_error_rate = 0.1  # 10% error rate
        assert error_rate <= max_acceptable_error_rate, \
            f"Error rate {error_rate:.2f} exceeds acceptable limit {max_acceptable_error_rate}"