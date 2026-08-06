"""
Integration layer for document processing pipeline with WebSocket status updates
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_async_session
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.processing import JobStatus, JobType, ProcessingJob
from src.models.websocket_status import UpdateType
from src.services.base import BaseService
from src.services.infrastructure.status_update_service import status_update_service
from src.services.websocket.websocket_manager import (
    MessageType,
    Priority,
    WebSocketMessage,
    connection_manager,
)

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStep:
    """Definition of a processing step"""

    name: str
    description: str
    estimated_duration_seconds: float
    weight: float  # Relative weight for progress calculation


class DocumentProcessingStages:
    """Standard document processing stages"""

    INGESTION = [
        ProcessingStep(
            "file_validation", "Validating file format and integrity", 1.0, 5.0
        ),
        ProcessingStep("virus_scan", "Scanning for security threats", 3.0, 10.0),
        ProcessingStep("initial_processing", "Initial file processing", 2.0, 15.0),
    ]

    TEXT_EXTRACTION = [
        ProcessingStep("ocr_processing", "Extracting text via OCR", 5.0, 25.0),
        ProcessingStep("text_cleanup", "Cleaning and normalizing text", 2.0, 10.0),
        ProcessingStep(
            "metadata_extraction", "Extracting document metadata", 1.0, 10.0
        ),
    ]

    CONTENT_ANALYSIS = [
        ProcessingStep("entity_extraction", "Extracting named entities", 3.0, 20.0),
        ProcessingStep("topic_modeling", "Analyzing topics and themes", 4.0, 20.0),
        ProcessingStep("quality_assessment", "Assessing content quality", 2.0, 10.0),
    ]

    EMBEDDING_GENERATION = [
        ProcessingStep("chunking", "Splitting content into chunks", 2.0, 15.0),
        ProcessingStep(
            "embedding_generation", "Generating vector embeddings", 5.0, 30.0
        ),
        ProcessingStep(
            "vector_storage", "Storing embeddings in vector store", 1.0, 5.0
        ),
    ]

    GRAPH_INDEXING = [
        ProcessingStep(
            "relationship_extraction", "Extracting relationships", 3.0, 20.0
        ),
        ProcessingStep("graph_construction", "Building knowledge graph", 4.0, 25.0),
        ProcessingStep("graph_indexing", "Indexing in graph database", 2.0, 10.0),
    ]

    @classmethod
    def get_all_steps(cls, document_type: DocumentType) -> List[ProcessingStep]:
        """Get all processing steps for a document type"""
        all_steps = []

        # All documents go through ingestion
        all_steps.extend(cls.INGESTION)

        # Text-based documents need text extraction
        if document_type in [DocumentType.TEXT, DocumentType.PDF]:
            all_steps.extend(cls.TEXT_EXTRACTION)

        # Images need special processing
        if document_type == DocumentType.IMAGE:
            all_steps.extend(
                [
                    ProcessingStep(
                        "image_analysis", "Analyzing image content", 4.0, 25.0
                    ),
                    ProcessingStep("object_detection", "Detecting objects", 3.0, 20.0),
                    ProcessingStep(
                        "caption_generation", "Generating image captions", 2.0, 15.0
                    ),
                ]
            )

        # Audio/video need transcription
        if document_type in [DocumentType.AUDIO, DocumentType.VIDEO]:
            all_steps.extend(
                [
                    ProcessingStep(
                        "audio_extraction", "Extracting audio from video", 2.0, 10.0
                    ),
                    ProcessingStep(
                        "transcription", "Transcribing audio content", 6.0, 35.0
                    ),
                    ProcessingStep(
                        "speaker_identification", "Identifying speakers", 2.0, 15.0
                    ),
                ]
            )

        # All documents go through content analysis and embedding
        all_steps.extend(cls.CONTENT_ANALYSIS)
        all_steps.extend(cls.EMBEDDING_GENERATION)
        all_steps.extend(cls.GRAPH_INDEXING)

        return all_steps


class ProcessingIntegrationService(BaseService):
    """Integration service for document processing with real-time updates"""

    def __init__(self):
        super().__init__()
        self._active_jobs: Dict[str, Dict[str, Any]] = {}
        self._progress_callbacks: Dict[str, List[Callable]] = {}
        self._step_timers: Dict[str, asyncio.Task] = {}

    async def initialize(self):
        """Initialize the processing integration service"""
        await super().initialize()
        logger.info("Processing Integration Service initialized")

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down Processing Integration Service...")

        # Cancel all step timers
        for timer in self._step_timers.values():
            if not timer.done():
                timer.cancel()
                try:
                    await timer
                except asyncio.CancelledError:
                    pass

        await super().shutdown()
        logger.info("Processing Integration Service shutdown complete")

    @asynccontextmanager
    async def processing_context(
        self,
        document_id: str,
        job_id: str = None,
        processing_type: str = "document_processing",
    ):
        """Context manager for processing with automatic status updates"""
        try:
            # Get document information
            async with get_async_session() as session:
                result = await session.execute(
                    select(Document)
                    .options(selectinload(Document.organization))
                    .where(Document.id == document_id)
                )
                document = result.scalar_one_or_none()

                if not document:
                    raise ValueError(f"Document not found: {document_id}")

            # Initialize processing context
            processing_steps = DocumentProcessingStages.get_all_steps(
                document.document_type
            )
            total_weight = sum(step.weight for step in processing_steps)

            context = {
                "document_id": document_id,
                "job_id": job_id,
                "document_type": document.document_type,
                "organization_id": str(document.organization_id),
                "processing_steps": processing_steps,
                "total_weight": total_weight,
                "completed_weight": 0.0,
                "current_step_index": 0,
                "start_time": datetime.now(dt_timezone.utc),
                "step_times": {},
                "errors": [],
                "warnings": [],
            }

            # Store context
            if job_id:
                self._active_jobs[job_id] = context

            # Update document status to processing
            await self._update_document_status(document_id, ProcessingStatus.PROCESSING)

            # Start processing
            await self._broadcast_processing_start(document_id, context)

            yield context

        except Exception as e:
            logger.error(f"Processing failed for document {document_id}: {e}")

            # Update status to failed
            await self._update_document_status(
                document_id, ProcessingStatus.FAILED, str(e)
            )

            # Broadcast failure
            await self._broadcast_processing_error(
                document_id, str(e), context if "context" in locals() else None
            )

        finally:
            # Cleanup
            if job_id and job_id in self._active_jobs:
                del self._active_jobs[job_id]

            if job_id and job_id in self._step_timers:
                self._step_timers[job_id].cancel()
                del self._step_timers[job_id]

    async def update_step_progress(
        self,
        job_id: str,
        step_name: str,
        progress_percentage: float,
        details: Dict[str, Any] = None,
    ):
        """Update progress for current processing step"""
        if job_id not in self._active_jobs:
            logger.warning(f"No active processing context for job: {job_id}")
            return

        context = self._active_jobs[job_id]
        document_id = context["document_id"]

        # Find current step
        current_step = None
        for i, step in enumerate(context["processing_steps"]):
            if step.name == step_name:
                current_step = step
                context["current_step_index"] = i
                break

        if not current_step:
            logger.warning(f"Step not found in processing pipeline: {step_name}")
            return

        # Calculate overall progress
        step_weight = current_step.weight
        step_progress = (progress_percentage / 100.0) * step_weight
        overall_progress = (
            (context["completed_weight"] + step_progress) / context["total_weight"]
        ) * 100.0

        # Create progress update
        progress_data = {
            "step_name": step_name,
            "step_description": current_step.description,
            "step_progress": progress_percentage,
            "overall_progress": min(100.0, overall_progress),
            "current_operation": details.get("operation", step_name)
            if details
            else step_name,
            "estimated_remaining_seconds": self._calculate_remaining_time(
                context, progress_percentage
            ),
            "details": details or {},
        }

        # Broadcast progress update
        await self._broadcast_processing_progress(document_id, progress_data)

        # Update job if available
        if context["job_id"]:
            await self._update_job_progress(
                context["job_id"], current_step.name, overall_progress
            )

    async def complete_step(
        self, job_id: str, step_name: str, result: Dict[str, Any] = None
    ):
        """Mark a processing step as completed"""
        if job_id not in self._active_jobs:
            return

        context = self._active_jobs[job_id]
        document_id = context["document_id"]

        # Find and complete step
        current_step = None
        for i, step in enumerate(context["processing_steps"]):
            if step.name == step_name:
                current_step = step
                context["current_step_index"] = i + 1
                break

        if not current_step:
            return

        # Update completed weight
        context["completed_weight"] += current_step.weight
        context["step_times"][step_name] = datetime.now(dt_timezone.utc)

        # Calculate new overall progress
        overall_progress = (
            context["completed_weight"] / context["total_weight"]
        ) * 100.0

        # Broadcast step completion
        completion_data = {
            "completed_step": step_name,
            "step_description": current_step.description,
            "overall_progress": overall_progress,
            "result": result or {},
        }

        await self._broadcast_step_completion(document_id, completion_data)

        # Update job if available
        if context["job_id"]:
            await self._update_job_progress(
                context["job_id"], "Completed", overall_progress
            )

    async def add_processing_warning(
        self, job_id: str, warning: str, details: Dict[str, Any] = None
    ):
        """Add a processing warning"""
        if job_id not in self._active_jobs:
            return

        context = self._active_jobs[job_id]
        context["warnings"].append(
            {
                "message": warning,
                "details": details or {},
                "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            }
        )

        # Broadcast warning
        await self._broadcast_processing_warning(
            context["document_id"], warning, details
        )

    async def complete_processing(
        self, document_id: str, result: Dict[str, Any] = None
    ):
        """Mark document processing as completed"""
        try:
            # Update document status
            await self._update_document_status(document_id, ProcessingStatus.COMPLETED)

            # Get document for final update
            async with get_async_session() as session:
                document_result = await session.execute(
                    select(Document)
                    .options(selectinload(Document.uploaded_by_user))
                    .where(Document.id == document_id)
                )
                document = document_result.scalar_one_or_none()

                if not document:
                    logger.error(f"Document not found for completion: {document_id}")
                    return

                # Mark as embedded and indexed
                document.is_embedded = True
                document.is_indexed = True
                document.processing_completed_at = datetime.now(dt_timezone.utc)

                await session.commit()

            # Broadcast completion
            await self._broadcast_processing_completion(document_id, result or {})

            logger.info(f"Document processing completed: {document_id}")

        except Exception as e:
            logger.error(f"Error completing processing for {document_id}: {e}")

    async def handle_document_upload(
        self, document_id: str, user_id: str, organization_id: str
    ):
        """Handle new document upload with initial status updates"""
        try:
            # Get document information
            async with get_async_session() as session:
                result = await session.execute(
                    select(Document)
                    .options(selectinload(Document.uploaded_by_user))
                    .where(Document.id == document_id)
                )
                document = result.scalar_one_or_none()

                if not document:
                    logger.error(f"Document not found: {document_id}")
                    return

            # Create initial job
            job = ProcessingJob(
                job_type=JobType.DOCUMENT_INGESTION,
                status=JobStatus.PENDING,
                priority=JobPriority.NORMAL,
                document_id=document_id,
                organization_id=organization_id,
                created_by_user_id=user_id,
                total_steps=len(
                    DocumentProcessingStages.get_all_steps(document.document_type)
                ),
            )

            async with get_async_session() as session:
                session.add(job)
                await session.commit()
                await session.refresh(job)

            # Broadcast upload notification
            await status_update_service.broadcast_system_notification(
                title=f"Document Uploaded: {document.title}",
                message=f"Your document '{document.title}' has been uploaded and is ready for processing.",
                notification_type="info",
                target_users=[str(document.uploaded_by_user_id)],
            )

            # Queue job for processing
            await self._queue_job_for_processing(str(job.id))

            logger.info(f"Document upload handled: {document_id}, job: {job.id}")

        except Exception as e:
            logger.error(f"Error handling document upload: {e}")

    async def _update_document_status(
        self, document_id: str, status: ProcessingStatus, error: str = None
    ):
        """Update document processing status"""
        try:
            async with get_async_session() as session:
                await session.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(
                        processing_status=status,
                        processing_error=error,
                        processing_completed_at=datetime.now(dt_timezone.utc)
                        if status
                        in [ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]
                        else None,
                    )
                )
                await session.commit()

        except Exception as e:
            logger.error(f"Error updating document status: {e}")

    async def _update_job_progress(
        self, job_id: str, current_step: str, progress_percentage: float
    ):
        """Update job progress"""
        try:
            async with get_async_session() as session:
                result = await session.execute(
                    select(ProcessingJob).where(ProcessingJob.id == job_id)
                )
                job = result.scalar_one_or_none()

                if job:
                    job.update_progress(current_step, progress_percentage)
                    await session.commit()

        except Exception as e:
            logger.error(f"Error updating job progress: {e}")

    async def _queue_job_for_processing(self, job_id: str):
        """Queue a job for processing"""
        try:
            async with get_async_session() as session:
                result = await session.execute(
                    select(ProcessingJob).where(ProcessingJob.id == job_id)
                )
                job = result.scalar_one_or_none()

                if job:
                    job.queue_job()
                    await session.commit()

                    # Broadcast job status update
                    await status_update_service.broadcast_job_update(
                        job_id=job_id, status=JobStatus.QUEUED
                    )

        except Exception as e:
            logger.error(f"Error queuing job for processing: {e}")

    async def _broadcast_processing_start(
        self, document_id: str, context: Dict[str, Any]
    ):
        """Broadcast processing start notification"""
        steps_info = [
            {
                "name": step.name,
                "description": step.description,
                "estimated_duration": step.estimated_duration_seconds,
            }
            for step in context["processing_steps"]
        ]

        await status_update_service.broadcast_document_update(
            document_id=document_id,
            status=ProcessingStatus.PROCESSING,
            progress=ProcessingProgress(
                document_id=document_id,
                current_step=context["processing_steps"][0].name,
                total_steps=len(context["processing_steps"]),
                completed_steps=0,
                progress_percentage=0.0,
                estimated_remaining_seconds=sum(
                    step.estimated_duration_seconds
                    for step in context["processing_steps"]
                ),
                current_operation=context["processing_steps"][0].description,
                step_details={"total_steps": len(context["processing_steps"])},
                warnings=[],
                errors=[],
            ),
        )

        # Broadcast system notification
        await status_update_service.broadcast_system_notification(
            title="Processing Started",
            message=f"Document processing has started for document ID: {document_id}",
            notification_type="info",
        )

    async def _broadcast_processing_progress(
        self, document_id: str, progress_data: Dict[str, Any]
    ):
        """Broadcast processing progress update"""
        await status_update_service.broadcast_document_update(
            document_id=document_id,
            status=ProcessingStatus.PROCESSING,
            progress=ProcessingProgress(
                document_id=document_id,
                current_step=progress_data["step_name"],
                total_steps=0,  # Will be filled by service
                completed_steps=0,
                progress_percentage=progress_data["overall_progress"],
                estimated_remaining_seconds=progress_data[
                    "estimated_remaining_seconds"
                ],
                current_operation=progress_data["current_operation"],
                step_details=progress_data["details"],
                warnings=[],
                errors=[],
            ),
        )

    async def _broadcast_step_completion(
        self, document_id: str, completion_data: Dict[str, Any]
    ):
        """Broadcast step completion notification"""
        await status_update_service.broadcast_system_notification(
            title=f"Step Completed: {completion_data['completed_step']}",
            message=f"Processing step '{completion_data['step_description']}' has been completed.",
            notification_type="success",
        )

    async def _broadcast_processing_warning(
        self, document_id: str, warning: str, details: Dict[str, Any]
    ):
        """Broadcast processing warning"""
        await status_update_service.broadcast_system_notification(
            title="Processing Warning",
            message=f"Warning during document processing: {warning}",
            notification_type="warning",
        )

    async def _broadcast_processing_error(
        self, document_id: str, error: str, context: Dict[str, Any]
    ):
        """Broadcast processing error"""
        await status_update_service.broadcast_document_update(
            document_id=document_id, status=ProcessingStatus.FAILED, error=error
        )

        await status_update_service.broadcast_system_notification(
            title="Processing Failed",
            message=f"Document processing failed: {error}",
            notification_type="error",
        )

    async def _broadcast_processing_completion(
        self, document_id: str, result: Dict[str, Any]
    ):
        """Broadcast processing completion"""
        await status_update_service.broadcast_document_update(
            document_id=document_id, status=ProcessingStatus.COMPLETED
        )

        await status_update_service.broadcast_system_notification(
            title="Processing Completed",
            message=f"Document processing has completed successfully for document ID: {document_id}",
            notification_type="success",
            action_url=f"/documents/{document_id}",
        )

    def _calculate_remaining_time(
        self, context: Dict[str, Any], current_step_progress: float
    ) -> float:
        """Calculate estimated remaining processing time"""
        try:
            current_step_index = context["current_step_index"]
            processing_steps = context["processing_steps"]
            start_time = context["start_time"]

            # Time elapsed so far
            elapsed_time = (datetime.now(dt_timezone.utc) - start_time).total_seconds()

            # Weight of completed steps
            completed_weight = context["completed_weight"]

            # Current step weight and remaining portion
            if current_step_index < len(processing_steps):
                current_step = processing_steps[current_step_index]
                current_step_weight = current_step.weight
                remaining_step_weight = current_step_weight * (
                    1 - current_step_progress / 100.0
                )
            else:
                remaining_step_weight = 0

            # Weight of future steps
            future_weight = sum(
                step.weight for step in processing_steps[current_step_index + 1 :]
            )

            # Total remaining weight
            total_remaining_weight = remaining_step_weight + future_weight

            # Estimate remaining time based on average processing rate
            if completed_weight > 0:
                processing_rate = elapsed_time / completed_weight
                estimated_remaining = total_remaining_weight * processing_rate
            else:
                # Fallback: estimate based on step durations
                estimated_remaining = 0
                if current_step_index < len(processing_steps):
                    current_step = processing_steps[current_step_index]
                    estimated_remaining += current_step.estimated_duration_seconds * (
                        1 - current_step_progress / 100.0
                    )
                for step in processing_steps[current_step_index + 1 :]:
                    estimated_remaining += step.estimated_duration_seconds

            return max(0, estimated_remaining)

        except Exception:
            return None


# Global processing integration service instance
processing_integration_service = ProcessingIntegrationService()
