"""
Document Processing Real-time Service
Bridges document processing events with WebSocket broadcasting for live updates
"""

import asyncio
import json
import logging
from datetime import datetime, timezone as dt_timezone, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from .base import BaseService
from .websocket_manager import connection_manager, WebSocketMessage, MessageType, Priority
from .status_update_service import (
    status_update_service,
    ProcessingProgress,
    Channel,
    UpdateFrequency
)
from ..core.database import get_async_session
from ..core.config import settings
from ..models.document import Document, ProcessingStatus as DocumentProcessingStatus
from ..models.processing import ProcessingJob, JobStatus, JobType
from ..models.websocket_status import StatusUpdate, UpdateType, Priority as UpdatePriority

logger = logging.getLogger(__name__)

class ProcessingEventType(Enum):
    """Document processing event types"""
    DOCUMENT_UPLOADED = "document_uploaded"
    PROCESSING_STARTED = "processing_started"
    PROCESSING_COMPLETED = "processing_completed"
    PROCESSING_FAILED = "processing_failed"
    PROCESSING_CANCELLED = "processing_cancelled"
    PROCESSING_RETRY = "processing_retry"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    PROGRESS_UPDATE = "progress_update"
    STAGE_CHANGED = "stage_changed"
    ERROR_OCCURRED = "error_occurred"
    WARNING_ISSUED = "warning_issued"

@dataclass
class ProcessingEvent:
    """Document processing event"""
    event_id: str
    event_type: ProcessingEventType
    document_id: str
    job_id: Optional[str] = None
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    timestamp: datetime = None
    data: Dict[str, Any] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(dt_timezone.utc)
        if self.data is None:
            self.data = {}
        if self.metadata is None:
            self.metadata = {}

class DocumentRealtimeService(BaseService):
    """
    Real-time service for document processing events

    This service monitors document processing events and broadcasts
    real-time updates to connected WebSocket clients.
    """

    def __init__(self):
        super().__init__()
        self._active_documents: Set[str] = set()
        self._document_progress: Dict[str, ProcessingProgress] = {}
        self._event_history: List[ProcessingEvent] = []
        self._subscribers: Dict[str, Set[str]] = {}  # document_id -> set of connection_ids
        self._background_tasks: List[asyncio.Task] = []

        # Configuration
        self.max_event_history = 1000
        self.progress_update_interval = 2.0  # seconds
        self.cleanup_interval = 3600  # 1 hour

    async def initialize(self):
        """Initialize the document real-time service"""
        await super().initialize()

        # Start background tasks
        self._background_tasks = [
            asyncio.create_task(self._monitor_document_processing()),
            asyncio.create_task(self._cleanup_old_data()),
            asyncio.create_task(self._update_progress_indicators())
        ]

        logger.info("Document Real-time Service initialized")

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down Document Real-time Service...")

        # Cancel background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        await super().shutdown()
        logger.info("Document Real-time Service shutdown complete")

    async def track_document_processing(self, document_id: str, user_id: str = None, organization_id: str = None):
        """
        Start tracking a document for real-time updates

        Args:
            document_id: Document ID to track
            user_id: User ID who owns the document
            organization_id: Organization ID that owns the document
        """
        try:
            self._active_documents.add(document_id)

            # Create tracking event
            event = ProcessingEvent(
                event_id=str(uuid.uuid4()),
                event_type=ProcessingEventType.PROCESSING_STARTED,
                document_id=document_id,
                user_id=user_id,
                organization_id=organization_id,
                data={"tracking_started": True}
            )

            await self._process_event(event)
            logger.info(f"Started tracking document {document_id}")

        except Exception as e:
            logger.error(f"Error tracking document {document_id}: {e}")

    async def stop_tracking_document(self, document_id: str):
        """Stop tracking a document"""
        try:
            self._active_documents.discard(document_id)
            self._document_progress.pop(document_id, None)

            # Create tracking event
            event = ProcessingEvent(
                event_id=str(uuid.uuid4()),
                event_type=ProcessingEventType.PROCESSING_COMPLETED,
                document_id=document_id,
                data={"tracking_stopped": True}
            )

            await self._process_event(event)
            logger.info(f"Stopped tracking document {document_id}")

        except Exception as e:
            logger.error(f"Error stopping document tracking {document_id}: {e}")

    async def broadcast_document_event(self, event: ProcessingEvent):
        """
        Broadcast a document processing event to subscribed clients

        Args:
            event: Processing event to broadcast
        """
        try:
            await self._process_event(event)
        except Exception as e:
            logger.error(f"Error broadcasting document event: {e}")

    async def update_document_progress(self, document_id: str, current_step: str,
                                     progress_percentage: float,
                                     total_steps: int = None,
                                     completed_steps: int = None,
                                     current_operation: str = None,
                                     step_details: Dict[str, Any] = None,
                                     warnings: List[str] = None,
                                     errors: List[str] = None):
        """
        Update processing progress for a document

        Args:
            document_id: Document ID
            current_step: Current processing step
            progress_percentage: Overall progress percentage (0-100)
            total_steps: Total number of steps
            completed_steps: Number of completed steps
            current_operation: Description of current operation
            step_details: Detailed step information
            warnings: List of warnings
            errors: List of errors
        """
        try:
            # Calculate estimated remaining time
            estimated_remaining = None
            if document_id in self._document_progress:
                previous_progress = self._document_progress[document_id]
                if (previous_progress.progress_percentage < progress_percentage and
                    previous_progress.progress_percentage > 0):
                    # Simple linear estimation
                    progress_delta = progress_percentage - previous_progress.progress_percentage
                    if progress_delta > 0:
                        time_since_last = (datetime.now(dt_timezone.utc) - previous_progress.timestamp).total_seconds()
                        if time_since_last > 0:
                            time_per_percent = time_since_last / progress_delta
                            remaining_percent = 100 - progress_percentage
                            estimated_remaining = time_per_percent * remaining_percent

            # Update progress tracking
            self._document_progress[document_id] = ProcessingProgress(
                document_id=document_id,
                current_step=current_step,
                total_steps=total_steps or 1,
                completed_steps=completed_steps or int(progress_percentage),
                progress_percentage=progress_percentage,
                estimated_remaining_seconds=estimated_remaining,
                current_operation=current_operation or current_step,
                step_details=step_details or {},
                warnings=warnings or [],
                errors=errors or []
            )

            # Create progress update event
            event = ProcessingEvent(
                event_id=str(uuid.uuid4()),
                event_type=ProcessingEventType.PROGRESS_UPDATE,
                document_id=document_id,
                data={
                    "progress_percentage": progress_percentage,
                    "current_step": current_step,
                    "current_operation": current_operation,
                    "estimated_remaining_seconds": estimated_remaining,
                    "step_details": step_details or {},
                    "warnings": warnings or [],
                    "errors": errors or []
                }
            )

            await self._process_event(event)

        except Exception as e:
            logger.error(f"Error updating document progress {document_id}: {e}")

    async def handle_document_status_change(self, document_id: str, old_status: DocumentProcessingStatus,
                                          new_status: DocumentProcessingStatus, error: str = None):
        """
        Handle document processing status changes

        Args:
            document_id: Document ID
            old_status: Previous processing status
            new_status: New processing status
            error: Error message if status changed to failed
        """
        try:
            # Determine event type based on status change
            if new_status == DocumentProcessingStatus.COMPLETED:
                event_type = ProcessingEventType.PROCESSING_COMPLETED
                await self.stop_tracking_document(document_id)
            elif new_status == DocumentProcessingStatus.FAILED:
                event_type = ProcessingEventType.PROCESSING_FAILED
                await self.stop_tracking_document(document_id)
            elif new_status == DocumentProcessingStatus.PROCESSING:
                event_type = ProcessingEventType.PROCESSING_STARTED
                await self.track_document_processing(document_id)
            elif new_status == DocumentProcessingStatus.RETRYING:
                event_type = ProcessingEventType.PROCESSING_RETRY
            else:
                return  # Skip other status changes for now

            # Get document details for the event
            async with get_async_session() as session:
                result = await session.execute(
                    select(Document)
                    .options(selectinload(Document.uploaded_by_user))
                    .options(selectinload(Document.organization))
                    .where(Document.id == document_id)
                )
                document = result.scalar_one_or_none()

                if not document:
                    logger.warning(f"Document {document_id} not found for status change event")
                    return

            # Create status change event
            event = ProcessingEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                document_id=document_id,
                user_id=str(document.uploaded_by_user_id),
                organization_id=str(document.organization_id),
                data={
                    "old_status": old_status.value,
                    "new_status": new_status.value,
                    "error": error,
                    "document_title": document.title,
                    "document_filename": document.filename,
                    "document_type": document.document_type.value,
                    "processing_started_at": document.processing_started_at.isoformat() if document.processing_started_at else None,
                    "processing_completed_at": document.processing_completed_at.isoformat() if document.processing_completed_at else None,
                    "retry_count": document.processing_retry_count
                }
            )

            await self._process_event(event)

            # Also broadcast via status update service
            await status_update_service.broadcast_document_update(
                document_id=document_id,
                status=new_status,
                error=error
            )

        except Exception as e:
            logger.error(f"Error handling document status change {document_id}: {e}")

    async def handle_job_status_change(self, job_id: str, document_id: str, old_status: JobStatus,
                                     new_status: JobStatus, progress: float = None, error: str = None):
        """
        Handle processing job status changes

        Args:
            job_id: Processing job ID
            document_id: Document ID
            old_status: Previous job status
            new_status: New job status
            progress: Job progress percentage
            error: Error message if job failed
        """
        try:
            # Determine event type
            if new_status == JobStatus.COMPLETED:
                event_type = ProcessingEventType.JOB_COMPLETED
            elif new_status == JobStatus.FAILED:
                event_type = ProcessingEventType.JOB_FAILED
            elif new_status == JobStatus.RUNNING:
                event_type = ProcessingEventType.JOB_STARTED
            else:
                return  # Skip other status changes

            # Get job details
            async with get_async_session() as session:
                result = await session.execute(
                    select(ProcessingJob)
                    .options(selectinload(ProcessingJob.document))
                    .options(selectinload(ProcessingJob.created_by_user))
                    .where(ProcessingJob.id == job_id)
                )
                job = result.scalar_one_or_none()

                if not job:
                    logger.warning(f"Job {job_id} not found for status change event")
                    return

            # Create job status change event
            event = ProcessingEvent(
                event_id=str(uuid.uuid4()),
                event_type=event_type,
                document_id=document_id,
                job_id=job_id,
                user_id=str(job.created_by_user_id) if job.created_by_user_id else None,
                organization_id=str(job.organization_id),
                data={
                    "job_type": job.job_type.value,
                    "old_status": old_status.value,
                    "new_status": new_status.value,
                    "progress_percentage": progress or job.progress_percentage,
                    "current_step": job.current_step,
                    "total_steps": job.total_steps,
                    "completed_steps": job.completed_steps,
                    "error": error or job.error_message,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "duration_seconds": job.duration_seconds,
                    "retry_count": job.retry_count
                }
            )

            await self._process_event(event)

            # Also broadcast via status update service
            await status_update_service.broadcast_job_update(
                job_id=job_id,
                status=new_status,
                progress=progress,
                error=error
            )

        except Exception as e:
            logger.error(f"Error handling job status change {job_id}: {e}")

    async def get_document_event_history(self, document_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get event history for a specific document

        Args:
            document_id: Document ID
            limit: Maximum number of events to return

        Returns:
            List of event dictionaries
        """
        try:
            events = [
                event for event in self._event_history
                if event.document_id == document_id
            ]

            # Sort by timestamp (newest first) and limit
            events.sort(key=lambda e: e.timestamp, reverse=True)
            events = events[:limit]

            return [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.data,
                    "metadata": event.metadata
                }
                for event in events
            ]

        except Exception as e:
            logger.error(f"Error getting event history for document {document_id}: {e}")
            return []

    async def _process_event(self, event: ProcessingEvent):
        """Process a document processing event"""
        try:
            # Add to event history
            self._event_history.append(event)

            # Trim event history if too long
            if len(self._event_history) > self.max_event_history:
                self._event_history = self._event_history[-self.max_event_history:]

            # Get document information if not provided
            if not event.user_id or not event.organization_id:
                async with get_async_session() as session:
                    result = await session.execute(
                        select(Document)
                        .where(Document.id == event.document_id)
                    )
                    document = result.scalar_one_or_none()
                    if document:
                        event.user_id = event.user_id or str(document.uploaded_by_user_id)
                        event.organization_id = event.organization_id or str(document.organization_id)

            # Create WebSocket message
            message = WebSocketMessage(
                type=MessageType.DOCUMENT_PROCESSING,
                data={
                    "event": {
                        "event_id": event.event_id,
                        "event_type": event.event_type.value,
                        "document_id": event.document_id,
                        "job_id": event.job_id,
                        "timestamp": event.timestamp.isoformat(),
                        "data": event.data,
                        "metadata": event.metadata
                    }
                },
                timestamp=event.timestamp,
                priority=self._get_priority_for_event(event.event_type),
                target_channels=[Channel.DOCUMENT_PROCESSING.value]
            )

            # Broadcast to relevant users
            if event.user_id:
                await connection_manager.broadcast_to_user(event.user_id, message)

            # Broadcast to organization if specified
            if event.organization_id:
                await connection_manager.broadcast_to_organization(event.organization_id, message)

            # Log to database
            await self._log_event_to_database(event)

        except Exception as e:
            logger.error(f"Error processing event {event.event_id}: {e}")

    async def _monitor_document_processing(self):
        """Background task to monitor active document processing"""
        while True:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds

                # Check for documents that need progress updates
                current_time = datetime.now(dt_timezone.utc)
                stale_documents = []

                for document_id, progress in self._document_progress.items():
                    # If no update in 30 seconds, send a heartbeat update
                    if (current_time - progress.timestamp).total_seconds() > 30:
                        stale_documents.append(document_id)

                for document_id in stale_documents:
                    progress = self._document_progress[document_id]
                    await self.update_document_progress(
                        document_id=document_id,
                        current_step=progress.current_step,
                        progress_percentage=progress.progress_percentage,
                        current_operation=progress.current_operation
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in document processing monitor: {e}")
                await asyncio.sleep(5)

    async def _update_progress_indicators(self):
        """Background task to update progress indicators"""
        while True:
            try:
                await asyncio.sleep(self.progress_update_interval)

                # Update progress for active documents
                for document_id in list(self._active_documents):
                    # This could be enhanced to calculate actual progress from job status
                    pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in progress indicator update: {e}")
                await asyncio.sleep(1)

    async def _cleanup_old_data(self):
        """Periodic cleanup of old data"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)

                current_time = datetime.now(dt_timezone.utc)
                cutoff_time = current_time - timedelta(hours=24)

                # Clean up old event history
                old_events = [
                    event for event in self._event_history
                    if event.timestamp < cutoff_time
                ]

                if old_events:
                    self._event_history = [
                        event for event in self._event_history
                        if event.timestamp >= cutoff_time
                    ]
                    logger.info(f"Cleaned up {len(old_events)} old document processing events")

                # Clean up progress data for inactive documents
                inactive_progress = [
                    doc_id for doc_id, progress in self._document_progress.items()
                    if doc_id not in self._active_documents and
                    (current_time - progress.timestamp).total_seconds() > 3600  # 1 hour
                ]

                for doc_id in inactive_progress:
                    del self._document_progress[doc_id]

                if inactive_progress:
                    logger.info(f"Cleaned up progress data for {len(inactive_progress)} inactive documents")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    async def _log_event_to_database(self, event: ProcessingEvent):
        """Log event to database"""
        try:
            async with get_async_session() as session:
                status_update = StatusUpdate(
                    update_id=event.event_id,
                    update_type=UpdateType.DOCUMENT_PROCESSING,
                    title=f"Document {event.event_type.value.replace('_', ' ').title()}",
                    message=f"Document processing event: {event.event_type.value}",
                    update_data={
                        "document_id": event.document_id,
                        "job_id": event.job_id,
                        "event_type": event.event_type.value,
                        "event_data": event.data,
                        "metadata": event.metadata
                    },
                    target_users=[event.user_id] if event.user_id else [],
                    target_organizations=[event.organization_id] if event.organization_id else [],
                    priority=self._map_event_priority(event.event_type)
                )

                session.add(status_update)
                await session.commit()

        except Exception as e:
            logger.error(f"Failed to log event to database: {e}")

    def _get_priority_for_event(self, event_type: ProcessingEventType) -> Priority:
        """Get WebSocket message priority for event type"""
        priority_map = {
            ProcessingEventType.DOCUMENT_UPLOADED: Priority.NORMAL,
            ProcessingEventType.PROCESSING_STARTED: Priority.NORMAL,
            ProcessingEventType.PROCESSING_COMPLETED: Priority.NORMAL,
            ProcessingEventType.PROCESSING_FAILED: Priority.HIGH,
            ProcessingEventType.PROCESSING_CANCELLED: Priority.NORMAL,
            ProcessingEventType.PROCESSING_RETRY: Priority.NORMAL,
            ProcessingEventType.JOB_STARTED: Priority.NORMAL,
            ProcessingEventType.JOB_COMPLETED: Priority.NORMAL,
            ProcessingEventType.JOB_FAILED: Priority.HIGH,
            ProcessingEventType.PROGRESS_UPDATE: Priority.LOW,
            ProcessingEventType.STAGE_CHANGED: Priority.NORMAL,
            ProcessingEventType.ERROR_OCCURRED: Priority.HIGH,
            ProcessingEventType.WARNING_ISSUED: Priority.NORMAL
        }
        return priority_map.get(event_type, Priority.NORMAL)

    def _map_event_priority(self, event_type: ProcessingEventType) -> UpdatePriority:
        """Map event priority to database priority"""
        priority_map = {
            Priority.CRITICAL: UpdatePriority.CRITICAL,
            Priority.HIGH: UpdatePriority.HIGH,
            Priority.NORMAL: UpdatePriority.NORMAL,
            Priority.LOW: UpdatePriority.LOW
        }
        return priority_map.get(self._get_priority_for_event(event_type), UpdatePriority.NORMAL)

# Global service instance
document_realtime_service = DocumentRealtimeService()

# Add missing import for uuid
import uuid