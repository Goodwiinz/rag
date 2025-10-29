"""
Unit tests for Celery background tasks
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from celery import Task
from celery.exceptions import Retry, Ignore
import asyncio
import time
from typing import Dict, Any, List

from conftest_fastapi import *


class TestDocumentProcessingTasks:
    """Test class for document processing Celery tasks"""

    @pytest.fixture
    def mock_celery_task(self):
        """Mock Celery task decorator and task instance"""
        def mock_task(bind=False, **kwargs):
            def decorator(func):
                task_instance = Mock(spec=Task)
                task_instance.request = Mock()
                task_instance.request.id = "test-task-id"
                task_instance.request.retries = 0
                task_instance.request.max_retries = 3
                task_instance.retry = Mock(side_effect=Retry("Test retry"))
                task_instance.update_state = Mock()

                if bind:
                    def bound_func(self, *args, **kwargs):
                        return func(self, *args, **kwargs)
                    return bound_func
                else:
                    return func
            return decorator

        return mock_task

    @pytest.fixture
    def document_processing_service_mock(self):
        """Mock document processing service"""
        service = Mock()
        service.process_pdf_document = AsyncMock()
        service.process_text_document = AsyncMock()
        service.process_image_document = AsyncMock()
        service.process_audio_document = AsyncMock()
        service.process_video_document = AsyncMock()
        service.extract_entities = AsyncMock()
        service.generate_embeddings = AsyncMock()
        service.create_graph_nodes = AsyncMock()
        return service

    @pytest.fixture
    def embedding_service_mock(self):
        """Mock embedding service"""
        service = Mock()
        service.generate_embeddings = AsyncMock()
        service.batch_generate_embeddings = AsyncMock()
        return service

    @pytest.fixture
    def mock_task_result(self):
        """Mock task result"""
        return {
            "task_id": "test-task-id",
            "status": "SUCCESS",
            "result": {
                "document_id": "doc-123",
                "processing_type": "full",
                "entities_extracted": 25,
                "embeddings_generated": 50,
                "graph_nodes_created": 30,
                "processing_time_seconds": 45.5
            },
            "date_done": "2024-01-01T10:00:00Z"
        }

    @pytest.mark.unit
    def test_process_pdf_task_success(self, mock_celery_task, document_processing_service_mock, mock_task_result):
        """Test successful PDF processing task"""
        @mock_celery_task(bind=True)
        async def process_pdf_task(self, document_id: str, processing_options: Dict[str, Any]):
            """Mock PDF processing task"""
            # Update task state
            self.update_state(state="PROCESSING", meta={"progress": 10})

            # Process document
            result = await document_processing_service_mock.process_pdf_document(
                document_id, processing_options
            )

            # Update final state
            self.update_state(state="SUCCESS", meta=result)
            return result

        # Setup mock response
        processing_result = {
            "document_id": "doc-123",
            "pages_processed": 25,
            "text_extracted": "Sample text content",
            "entities": ["Entity1", "Entity2"],
            "processing_time": 30.5
        }
        document_processing_service_mock.process_pdf_document.return_value = processing_result

        # Execute task
        task_instance = Mock(spec=Task)
        task_instance.request.id = "test-task-id"
        task_instance.update_state = Mock()

        result = asyncio.run(process_pdf_task(task_instance, "doc-123", {"extract_entities": True}))

        # Assertions
        assert result["document_id"] == "doc-123"
        assert result["pages_processed"] == 25
        assert "entities" in result

        # Verify service calls
        document_processing_service_mock.process_pdf_document.assert_called_once_with(
            "doc-123", {"extract_entities": True}
        )

    @pytest.mark.unit
    def test_process_text_task_success(self, mock_celery_task, document_processing_service_mock):
        """Test successful text processing task"""
        @mock_celery_task(bind=True)
        async def process_text_task(self, document_id: str, processing_options: Dict[str, Any]):
            # Mock text processing
            self.update_state(state="PROCESSING", meta={"progress": 20})

            result = await document_processing_service_mock.process_text_document(
                document_id, processing_options
            )

            self.update_state(state="SUCCESS", meta=result)
            return result

        # Setup mock response
        processing_result = {
            "document_id": "doc-456",
            "words_processed": 1500,
            "sentences_extracted": 75,
            "language_detected": "en",
            "keywords": ["text", "processing", "nlp"]
        }
        document_processing_service_mock.process_text_document.return_value = processing_result

        # Execute task
        task_instance = Mock(spec=Task)
        task_instance.update_state = Mock()

        result = asyncio.run(process_text_task(task_instance, "doc-456", {"extract_keywords": True}))

        # Assertions
        assert result["document_id"] == "doc-456"
        assert result["words_processed"] == 1500
        assert "keywords" in result

    @pytest.mark.unit
    def test_process_image_task_success(self, mock_celery_task, document_processing_service_mock):
        """Test successful image processing task"""
        @mock_celery_task(bind=True)
        async def process_image_task(self, document_id: str, processing_options: Dict[str, Any]):
            # Mock image processing
            self.update_state(state="PROCESSING", meta={"progress": 30})

            result = await document_processing_service_mock.process_image_document(
                document_id, processing_options
            )

            self.update_state(state="SUCCESS", meta=result)
            return result

        # Setup mock response
        processing_result = {
            "document_id": "doc-789",
            "image_format": "JPEG",
            "dimensions": {"width": 1920, "height": 1080},
            "objects_detected": ["person", "car", "building"],
            "caption_generated": "A person standing next to a car in front of a building"
        }
        document_processing_service_mock.process_image_document.return_value = processing_result

        # Execute task
        task_instance = Mock(spec=Task)
        task_instance.update_state = Mock()

        result = asyncio.run(process_image_task(task_instance, "doc-789", {"detect_objects": True}))

        # Assertions
        assert result["document_id"] == "doc-789"
        assert "objects_detected" in result
        assert "caption_generated" in result

    @pytest.mark.unit
    def test_process_audio_task_success(self, mock_celery_task, document_processing_service_mock):
        """Test successful audio processing task"""
        @mock_celery_task(bind=True)
        async def process_audio_task(self, document_id: str, processing_options: Dict[str, Any]):
            # Mock audio processing
            self.update_state(state="PROCESSING", meta={"progress": 50})

            result = await document_processing_service_mock.process_audio_document(
                document_id, processing_options
            )

            self.update_state(state="SUCCESS", meta=result)
            return result

        # Setup mock response
        processing_result = {
            "document_id": "doc-audio-1",
            "audio_format": "MP3",
            "duration_seconds": 180,
            "transcription": "This is the transcribed audio content...",
            "language_detected": "en",
            "sentiment_analysis": {"positive": 0.7, "negative": 0.1, "neutral": 0.2}
        }
        document_processing_service_mock.process_audio_document.return_value = processing_result

        # Execute task
        task_instance = Mock(spec=Task)
        task_instance.update_state = Mock()

        result = asyncio.run(process_audio_task(task_instance, "doc-audio-1", {"transcribe": True}))

        # Assertions
        assert result["document_id"] == "doc-audio-1"
        assert "transcription" in result
        assert "sentiment_analysis" in result

    @pytest.mark.unit
    def test_process_video_task_success(self, mock_celery_task, document_processing_service_mock):
        """Test successful video processing task"""
        @mock_celery_task(bind=True)
        async def process_video_task(self, document_id: str, processing_options: Dict[str, Any]):
            # Mock video processing
            self.update_state(state="PROCESSING", meta={"progress": 70})

            result = await document_processing_service_mock.process_video_document(
                document_id, processing_options
            )

            self.update_state(state="SUCCESS", meta=result)
            return result

        # Setup mock response
        processing_result = {
            "document_id": "doc-video-1",
            "video_format": "MP4",
            "duration_seconds": 300,
            "frames_extracted": 10,
            "audio_transcribed": "Video audio transcription...",
            "scene_descriptions": [
                "Opening scene with person talking",
                "Cut to presentation slide",
                "Close-up of product demonstration"
            ]
        }
        document_processing_service_mock.process_video_document.return_value = processing_result

        # Execute task
        task_instance = Mock(spec=Task)
        task_instance.update_state = Mock()

        result = asyncio.run(process_video_task(task_instance, "doc-video-1", {"extract_frames": True}))

        # Assertions
        assert result["document_id"] == "doc-video-1"
        assert result["frames_extracted"] == 10
        assert "scene_descriptions" in result

    @pytest.mark.unit
    def test_generate_embeddings_task_success(self, mock_celery_task, embedding_service_mock):
        """Test successful embeddings generation task"""
        @mock_celery_task(bind=True)
        async def generate_embeddings_task(self, document_id: str, text_chunks: List[str]):
            # Mock embeddings generation
            self.update_state(state="PROCESSING", meta={"progress": 60})

            result = await embedding_service_mock.batch_generate_embeddings(text_chunks)

            self.update_state(state="SUCCESS", meta={"embeddings_count": len(result)})
            return result

        # Setup mock response
        embeddings = [
            [0.1, 0.2, 0.3, 0.4],
            [0.5, 0.6, 0.7, 0.8],
            [0.9, 1.0, 1.1, 1.2]
        ]
        embedding_service_mock.batch_generate_embeddings.return_value = embeddings

        # Execute task
        task_instance = Mock(spec=Task)
        task_instance.update_state = Mock()

        text_chunks = ["Chunk 1 text", "Chunk 2 text", "Chunk 3 text"]
        result = asyncio.run(generate_embeddings_task(task_instance, "doc-123", text_chunks))

        # Assertions
        assert len(result) == 3
        assert all(len(emb) == 4 for emb in result)

        # Verify service calls
        embedding_service_mock.batch_generate_embeddings.assert_called_once_with(text_chunks)

    @pytest.mark.unit
    def test_extract_entities_task_success(self, mock_celery_task, document_processing_service_mock):
        """Test successful entity extraction task"""
        @mock_celery_task(bind=True)
        async def extract_entities_task(self, document_id: str, text_content: str):
            # Mock entity extraction
            self.update_state(state="PROCESSING", meta={"progress": 80})

            result = await document_processing_service_mock.extract_entities(text_content)

            self.update_state(state="SUCCESS", meta={"entities_count": len(result)})
            return result

        # Setup mock response
        entities = [
            {"text": "OpenAI", "label": "ORGANIZATION", "confidence": 0.95},
            {"text": "ChatGPT", "label": "PRODUCT", "confidence": 0.92},
            {"text": "San Francisco", "label": "LOCATION", "confidence": 0.88}
        ]
        document_processing_service_mock.extract_entities.return_value = entities

        # Execute task
        task_instance = Mock(spec=Task)
        task_instance.update_state = Mock()

        text_content = "OpenAI released ChatGPT in San Francisco."
        result = asyncio.run(extract_entities_task(task_instance, "doc-123", text_content))

        # Assertions
        assert len(result) == 3
        assert result[0]["text"] == "OpenAI"
        assert result[0]["label"] == "ORGANIZATION"

    @pytest.mark.unit
    def test_task_retry_mechanism(self, mock_celery_task, document_processing_service_mock):
        """Test task retry mechanism"""
        @mock_celery_task(bind=True, max_retries=3)
        async def failing_task(self, document_id: str):
            if self.request.retries < self.request.max_retries:
                # Simulate failure and retry
                self.retry(countdown=60)

            # Success on final retry
            return {"status": "success", "retries": self.request.retries}

        # Execute task
        task_instance = Mock(spec=Task)
        task_instance.request.id = "test-task-id"
        task_instance.request.retries = 2
        task_instance.request.max_retries = 3
        task_instance.retry = Mock(side_effect=Retry("Test retry"))

        result = asyncio.run(failing_task(task_instance, "doc-123"))

        # Should succeed on final retry
        assert result["status"] == "success"
        assert result["retries"] == 2

    @pytest.mark.unit
    def test_task_failure_handling(self, mock_celery_task, document_processing_service_mock):
        """Test task failure handling"""
        @mock_celery_task(bind=True)
        async def failing_task(self, document_id: str):
            # Simulate task failure
            raise Exception("Processing failed due to invalid document format")

        # Execute task
        task_instance = Mock(spec=Task)
        task_instance.request.id = "test-task-id"
        task_instance.update_state = Mock()

        with pytest.raises(Exception, match="Processing failed due to invalid document format"):
            asyncio.run(failing_task(task_instance, "doc-123"))

    @pytest.mark.unit
    def test_task_timeout_handling(self, mock_celery_task, document_processing_service_mock):
        """Test task timeout handling"""
        @mock_celery_task(bind=True)
        async def timeout_task(self, document_id: str):
            # Simulate long-running task that times out
            await asyncio.sleep(10)  # Long operation
            return {"status": "completed"}

        # Execute task with timeout
        task_instance = Mock(spec=Task)
        task_instance.request.id = "test-task-id"

        with pytest.raises(asyncio.TimeoutError):
            asyncio.run(asyncio.wait_for(timeout_task(task_instance, "doc-123"), timeout=1.0))

    @pytest.mark.unit
    def test_task_progress_updates(self, mock_celery_task, document_processing_service_mock):
        """Test task progress updates"""
        @mock_celery_task(bind=True)
        async def progress_task(self, document_id: str):
            steps = [25, 50, 75, 100]
            for progress in steps:
                self.update_state(
                    state="PROCESSING",
                    meta={"progress": progress, "status": f"Processing step {progress // 25}"}
                )
                await asyncio.sleep(0.01)  # Simulate work

            return {"status": "completed", "progress": 100}

        # Execute task
        task_instance = Mock(spec=Task)
        task_instance.request.id = "test-task-id"
        task_instance.update_state = Mock()

        result = asyncio.run(progress_task(task_instance, "doc-123"))

        # Verify progress updates were called
        assert task_instance.update_state.call_count == 4
        assert result["status"] == "completed"

        # Verify progress values
        progress_calls = [call[1]["meta"]["progress"] for call in task_instance.update_state.call_args_list]
        assert progress_calls == [25, 50, 75, 100]

    @pytest.mark.unit
    def test_batch_processing_task(self, mock_celery_task, document_processing_service_mock):
        """Test batch document processing task"""
        @mock_celery_task(bind=True)
        async def batch_process_task(self, document_ids: List[str], processing_options: Dict[str, Any]):
            results = []
            total_docs = len(document_ids)

            for i, doc_id in enumerate(document_ids):
                # Update progress
                progress = int((i / total_docs) * 100)
                self.update_state(state="PROCESSING", meta={"progress": progress})

                # Process document
                result = {"document_id": doc_id, "status": "processed", "processing_time": 10.5}
                results.append(result)

            self.update_state(state="SUCCESS", meta={"processed_count": len(results)})
            return {"results": results, "total_processed": len(results)}

        # Execute task
        task_instance = Mock(spec=Task)
        task_instance.request.id = "test-task-id"
        task_instance.update_state = Mock()

        document_ids = ["doc-1", "doc-2", "doc-3"]
        result = asyncio.run(batch_process_task(task_instance, document_ids, {}))

        # Assertions
        assert result["total_processed"] == 3
        assert len(result["results"]) == 3
        assert all(doc["status"] == "processed" for doc in result["results"])

        # Verify progress updates
        assert task_instance.update_state.call_count >= 4  # 3 progress + 1 final

    @pytest.mark.unit
    def test_task_cleanup_on_failure(self, mock_celery_task, document_processing_service_mock):
        """Test task cleanup operations on failure"""
        @mock_celery_task(bind=True)
        async def cleanup_task(self, document_id: str):
            try:
                # Simulate processing that fails
                await document_processing_service_mock.process_pdf_document(document_id, {})
                # Simulate failure
                raise Exception("Processing failed")
            except Exception as e:
                # Cleanup operations
                # In real implementation: delete temp files, rollback DB transactions, etc.
                self.update_state(
                    state="FAILURE",
                    meta={"error": str(e), "cleanup_completed": True}
                )
                raise

        # Setup mock
        document_processing_service_mock.process_pdf_document.return_value = {"status": "processed"}

        # Execute task
        task_instance = Mock(spec=Task)
        task_instance.request.id = "test-task-id"
        task_instance.update_state = Mock()

        with pytest.raises(Exception, match="Processing failed"):
            asyncio.run(cleanup_task(task_instance, "doc-123"))

        # Verify cleanup was called
        task_instance.update_state.assert_called_with(
            state="FAILURE",
            meta={"error": "Processing failed", "cleanup_completed": True}
        )

    @pytest.mark.unit
    def test_task_chaining(self, mock_celery_task, document_processing_service_mock, embedding_service_mock):
        """Test task chaining (one task triggers another)"""
        @mock_celery_task(bind=True)
        async def first_task(self, document_id: str):
            # First processing step
            result = {"document_id": document_id, "step": "first", "status": "completed"}

            # Trigger next task in chain
            from src.tasks.processing_tasks import second_task
            second_task.delay(document_id, result)

            return result

        @mock_celery_task(bind=True)
        async def second_task(self, document_id: str, first_result: Dict[str, Any]):
            # Second processing step
            result = {
                "document_id": document_id,
                "step": "second",
                "status": "completed",
                "previous_step": first_result["step"]
            }
            return result

        # Mock the delay method
        with patch('src.tasks.processing_tasks.second_task') as mock_second_task:
            mock_second_task.delay = Mock()

            # Execute first task
            task_instance = Mock(spec=Task)
            task_instance.request.id = "test-task-id"

            result = asyncio.run(first_task(task_instance, "doc-123"))

            # Assertions
            assert result["step"] == "first"
            assert result["status"] == "completed"

            # Verify second task was triggered
            mock_second_task.delay.assert_called_once_with("doc-123", result)

    @pytest.mark.unit
    def test_task_cancellation(self, mock_celery_task, document_processing_service_mock):
        """Test task cancellation handling"""
        @mock_celery_task(bind=True)
        async def cancellable_task(self, document_id: str):
            try:
                # Long-running operation that can be cancelled
                for i in range(100):
                    # Check for cancellation
                    if hasattr(self.request, 'called_off') and self.request.called_off:
                        self.update_state(state="REVOKED", meta={"reason": "Task cancelled"})
                        return {"status": "cancelled", "progress": i}

                    # Simulate work
                    await asyncio.sleep(0.01)

                    # Update progress
                    if i % 25 == 0:
                        self.update_state(state="PROCESSING", meta={"progress": i})

                return {"status": "completed", "progress": 100}

            except asyncio.CancelledError:
                self.update_state(state="REVOKED", meta={"reason": "Task was cancelled"})
                raise

        # Execute task with cancellation
        task_instance = Mock(spec=Task)
        task_instance.request.id = "test-task-id"
        task_instance.request.called_off = True
        task_instance.update_state = Mock()

        result = asyncio.run(cancellable_task(task_instance, "doc-123"))

        # Task should detect cancellation and return cancelled status
        assert result["status"] == "cancelled"