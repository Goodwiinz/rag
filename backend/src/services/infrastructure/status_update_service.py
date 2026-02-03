"""
Real-time status update service for document processing and system events
"""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.core.database import get_async_session
from src.models.document import Document, ProcessingStatus
from src.models.organization import Organization
from src.models.processing import JobStatus, JobType, ProcessingJob
from src.models.user import User
from src.models.websocket_status import NotificationTemplate
from src.models.websocket_status import Priority as UpdatePriority
from src.models.websocket_status import StatusUpdate, UpdateType
from src.services.base import BaseService
from src.services.websocket.websocket_manager import (
    MessageType,
    Priority,
    WebSocketMessage,
    connection_manager,
)

logger = logging.getLogger(__name__)


class UpdateFrequency(Enum):
    """Status update frequency levels"""

    REALTIME = "realtime"  # Every 100-500ms
    FREQUENT = "frequent"  # Every 1-2 seconds
    NORMAL = "normal"  # Every 5-10 seconds
    PERIODIC = "periodic"  # Every 30-60 seconds


class Channel(Enum):
    """WebSocket notification channels"""

    DOCUMENT_PROCESSING = "document_processing"
    JOB_STATUS = "job_status"
    SYSTEM_STATUS = "system_status"
    USER_NOTIFICATIONS = "user_notifications"
    QUOTA_ALERTS = "quota_alerts"
    QUALITY_METRICS = "quality_metrics"
    ADMIN_ALERTS = "admin_alerts"


@dataclass
class ProcessingProgress:
    """Processing progress tracking"""

    document_id: str
    current_step: str
    total_steps: int
    completed_steps: int
    progress_percentage: float
    estimated_remaining_seconds: Optional[float]
    current_operation: str
    step_details: Dict[str, Any]
    warnings: List[str]
    errors: List[str]


@dataclass
class SystemStatus:
    """System status information"""

    active_jobs: int
    queued_jobs: int
    completed_jobs_today: int
    failed_jobs_today: int
    average_processing_time_seconds: float
    system_load_percentage: float
    memory_usage_percentage: float
    storage_usage_gb: float
    active_connections: int
    error_rate_last_hour: float


class StatusUpdateService(BaseService):
    """Real-time status update service with intelligent throttling and batching"""

    def __init__(self):
        super().__init__()
        self._update_cache: Dict[str, Dict[str, Any]] = {}
        self._update_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._batch_updates: Dict[str, List[Dict[str, Any]]] = {}
        self._last_update_time: Dict[str, datetime] = {}
        self._update_frequencies: Dict[str, UpdateFrequency] = {}
        self._subscribers: Dict[str, Set[str]] = {}

        # Background tasks
        self._processor_task: Optional[asyncio.Task] = None
        self._broadcaster_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None

        # Configuration
        self.batch_size = 50
        self.batch_timeout = 2.0  # seconds
        self.max_cache_age = timedelta(minutes=5)
        self.default_frequency = UpdateFrequency.NORMAL

    async def initialize(self):
        """Initialize the status update service"""
        await super().initialize()

        # Start background tasks
        self._processor_task = asyncio.create_task(self._process_update_queue())
        self._broadcaster_task = asyncio.create_task(self._broadcast_batch_updates())
        self._cleanup_task = asyncio.create_task(self._cleanup_old_data())

        logger.info("Status Update Service initialized")

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down Status Update Service...")

        # Cancel background tasks
        tasks = [self._processor_task, self._broadcaster_task, self._cleanup_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Process remaining updates
        await self._process_remaining_updates()

        await super().shutdown()
        logger.info("Status Update Service shutdown complete")

    async def subscribe_to_updates(
        self,
        connection_id: str,
        update_types: List[str],
        frequency: UpdateFrequency = UpdateFrequency.NORMAL,
    ):
        """Subscribe a connection to specific update types"""
        for update_type in update_types:
            if update_type not in self._subscribers:
                self._subscribers[update_type] = set()
            self._subscribers[update_type].add(connection_id)
            self._update_frequencies[connection_id] = frequency

        logger.info(f"Connection {connection_id} subscribed to updates: {update_types}")

    async def unsubscribe_from_updates(
        self, connection_id: str, update_types: List[str] = None
    ):
        """Unsubscribe a connection from updates"""
        if update_types is None:
            # Remove from all subscriptions
            for update_type in self._subscribers:
                self._subscribers[update_type].discard(connection_id)
            self._update_frequencies.pop(connection_id, None)
        else:
            for update_type in update_types:
                if update_type in self._subscribers:
                    self._subscribers[update_type].discard(connection_id)

        logger.info(f"Connection {connection_id} unsubscribed from updates")

    async def broadcast_document_update(
        self,
        document_id: str,
        status: ProcessingStatus,
        progress: ProcessingProgress = None,
        error: str = None,
    ):
        """Broadcast document processing status update"""
        try:
            # Get document information
            async with get_async_session() as session:
                result = await session.execute(
                    select(Document)
                    .options(selectinload(Document.uploaded_by_user))
                    .options(selectinload(Document.organization))
                    .where(Document.id == document_id)
                )
                document = result.scalar_one_or_none()

                if not document:
                    logger.warning(f"Document not found: {document_id}")
                    return

                # Prepare update data
                update_data = {
                    "document_id": str(document.id),
                    "title": document.title,
                    "filename": document.filename,
                    "document_type": document.document_type.value,
                    "processing_status": status.value,
                    "processing_started_at": document.processing_started_at.isoformat()
                    if document.processing_started_at
                    else None,
                    "processing_completed_at": document.processing_completed_at.isoformat()
                    if document.processing_completed_at
                    else None,
                    "processing_error": error or document.processing_error,
                    "processing_retry_count": document.processing_retry_count,
                    "updated_at": datetime.now(dt_timezone.utc).isoformat(),
                }

                # Add progress information if available
                if progress:
                    update_data.update(
                        {
                            "progress_percentage": progress.progress_percentage,
                            "current_step": progress.current_step,
                            "total_steps": progress.total_steps,
                            "completed_steps": progress.completed_steps,
                            "current_operation": progress.current_operation,
                            "estimated_remaining_seconds": progress.estimated_remaining_seconds,
                            "step_details": progress.step_details,
                            "warnings": progress.warnings,
                            "errors": progress.errors,
                        }
                    )

                # Create WebSocket message
                message = WebSocketMessage(
                    type=MessageType.DOCUMENT_PROCESSING,
                    data=update_data,
                    timestamp=datetime.now(dt_timezone.utc),
                    priority=self._get_priority_for_status(status),
                    target_channels=[Channel.DOCUMENT_PROCESSING.value],
                )

                # Add to update queue
                await self._queue_update(
                    "document_processing", document_id, update_data, message
                )

                # Broadcast to specific user
                await connection_manager.broadcast_to_user(
                    str(document.uploaded_by_user_id), message
                )

                # Log to database
                await self._log_status_update(
                    update_type=UpdateType.DOCUMENT_PROCESSING,
                    title=f"Document {document.title}",
                    message=f"Status updated to {status.value}",
                    update_data=update_data,
                    target_users=[str(document.uploaded_by_user_id)],
                    target_organizations=[str(document.organization_id)],
                )

        except Exception as e:
            logger.error(f"Error broadcasting document update: {e}")

    async def broadcast_job_update(
        self,
        job_id: str,
        status: JobStatus,
        progress: float = None,
        current_step: str = None,
        error: str = None,
    ):
        """Broadcast job status update"""
        try:
            # Get job information
            async with get_async_session() as session:
                result = await session.execute(
                    select(ProcessingJob)
                    .options(selectinload(ProcessingJob.document))
                    .options(selectinload(ProcessingJob.created_by_user))
                    .options(selectinload(ProcessingJob.organization))
                    .where(ProcessingJob.id == job_id)
                )
                job = result.scalar_one_or_none()

                if not job:
                    logger.warning(f"Job not found: {job_id}")
                    return

                # Update job progress if provided
                if progress is not None:
                    job.update_progress(current_step, progress)

                # Prepare update data
                update_data = {
                    "job_id": str(job.id),
                    "job_type": job.job_type.value,
                    "status": status.value,
                    "priority": job.priority.value,
                    "progress_percentage": job.progress_percentage,
                    "current_step": job.current_step,
                    "total_steps": job.total_steps,
                    "completed_steps": job.completed_steps,
                    "started_at": job.started_at.isoformat()
                    if job.started_at
                    else None,
                    "completed_at": job.completed_at.isoformat()
                    if job.completed_at
                    else None,
                    "duration_seconds": job.duration_seconds,
                    "error_message": error or job.error_message,
                    "retry_count": job.retry_count,
                    "updated_at": datetime.now(dt_timezone.utc).isoformat(),
                }

                # Add document information if available
                if job.document:
                    update_data.update(
                        {
                            "document_id": str(job.document.id),
                            "document_title": job.document.title,
                        }
                    )

                # Create WebSocket message
                message = WebSocketMessage(
                    type=MessageType.JOB_STATUS,
                    data=update_data,
                    timestamp=datetime.now(dt_timezone.utc),
                    priority=self._get_priority_for_job_status(status),
                    target_channels=[Channel.JOB_STATUS.value],
                )

                # Add to update queue
                await self._queue_update("job_status", job_id, update_data, message)

                # Broadcast to user if job has one
                if job.created_by_user_id:
                    await connection_manager.broadcast_to_user(
                        str(job.created_by_user_id), message
                    )

                # Log to database
                target_users = (
                    [str(job.created_by_user_id)] if job.created_by_user_id else []
                )
                target_orgs = [str(job.organization_id)]

                await self._log_status_update(
                    update_type=UpdateType.JOB_STATUS,
                    title=f"Job {job.job_type.value}",
                    message=f"Status updated to {status.value}",
                    update_data=update_data,
                    target_users=target_users,
                    target_organizations=target_orgs,
                )

        except Exception as e:
            logger.error(f"Error broadcasting job update: {e}")

    async def broadcast_system_notification(
        self,
        title: str,
        message: str,
        notification_type: str = "info",
        target_users: List[str] = None,
        target_organizations: List[str] = None,
        action_url: str = None,
    ):
        """Broadcast system notification"""
        try:
            # Prepare notification data
            notification_data = {
                "title": title,
                "message": message,
                "type": notification_type,
                "timestamp": datetime.now(dt_timezone.utc).isoformat(),
                "action_url": action_url,
                "id": str(uuid.uuid4()),
            }

            # Create WebSocket message
            ws_message = WebSocketMessage(
                type=MessageType.SYSTEM_NOTIFICATION,
                data=notification_data,
                timestamp=datetime.now(dt_timezone.utc),
                priority=Priority.HIGH
                if notification_type in ["error", "warning"]
                else Priority.NORMAL,
                target_channels=[Channel.USER_NOTIFICATIONS.value],
            )

            # Broadcast to targets
            if target_users:
                for user_id in target_users:
                    await connection_manager.broadcast_to_user(user_id, ws_message)

            if target_organizations:
                for org_id in target_organizations:
                    await connection_manager.broadcast_to_organization(
                        org_id, ws_message
                    )

            # If no specific targets, broadcast to all
            if not target_users and not target_organizations:
                await connection_manager.broadcast_to_channel(
                    Channel.USER_NOTIFICATIONS.value, ws_message
                )

            # Log to database
            await self._log_status_update(
                update_type=UpdateType.USER_NOTIFICATION,
                title=title,
                message=message,
                update_data=notification_data,
                target_users=target_users or [],
                target_organizations=target_organizations or [],
            )

        except Exception as e:
            logger.error(f"Error broadcasting system notification: {e}")

    async def get_system_status(self) -> SystemStatus:
        """Get current system status"""
        try:
            async with get_async_session() as session:
                # Get job statistics
                current_time = datetime.now(dt_timezone.utc)
                today_start = current_time.replace(
                    hour=0, minute=0, second=0, microsecond=0
                )

                # Active jobs
                active_jobs_result = await session.execute(
                    select(func.count(ProcessingJob.id)).where(
                        ProcessingJob.status.in_([JobStatus.RUNNING, JobStatus.QUEUED])
                    )
                )
                active_jobs = active_jobs_result.scalar() or 0

                # Queued jobs
                queued_jobs_result = await session.execute(
                    select(func.count(ProcessingJob.id)).where(
                        ProcessingJob.status == JobStatus.QUEUED
                    )
                )
                queued_jobs = queued_jobs_result.scalar() or 0

                # Today's completed jobs
                completed_today_result = await session.execute(
                    select(func.count(ProcessingJob.id)).where(
                        and_(
                            ProcessingJob.status == JobStatus.COMPLETED,
                            ProcessingJob.completed_at >= today_start,
                        )
                    )
                )
                completed_jobs_today = completed_today_result.scalar() or 0

                # Today's failed jobs
                failed_today_result = await session.execute(
                    select(func.count(ProcessingJob.id)).where(
                        and_(
                            ProcessingJob.status == JobStatus.FAILED,
                            ProcessingJob.completed_at >= today_start,
                        )
                    )
                )
                failed_jobs_today = failed_today_result.scalar() or 0

                # Average processing time
                avg_time_result = await session.execute(
                    select(func.avg(ProcessingJob.duration_seconds)).where(
                        and_(
                            ProcessingJob.status == JobStatus.COMPLETED,
                            ProcessingJob.completed_at >= today_start,
                        )
                    )
                )
                avg_processing_time = avg_time_result.scalar() or 0.0

                # Get WebSocket connection stats
                ws_stats = connection_manager.get_connection_stats()

                return SystemStatus(
                    active_jobs=active_jobs,
                    queued_jobs=queued_jobs,
                    completed_jobs_today=completed_jobs_today,
                    failed_jobs_today=failed_jobs_today,
                    average_processing_time_seconds=float(avg_processing_time),
                    system_load_percentage=0.0,  # Would need system monitoring
                    memory_usage_percentage=0.0,  # Would need system monitoring
                    storage_usage_gb=0.0,  # Would need storage monitoring
                    active_connections=ws_stats["total_connections"],
                    error_rate_last_hour=0.0,  # Would need error tracking
                )

        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return SystemStatus(
                active_jobs=0,
                queued_jobs=0,
                completed_jobs_today=0,
                failed_jobs_today=0,
                average_processing_time_seconds=0.0,
                system_load_percentage=0.0,
                memory_usage_percentage=0.0,
                storage_usage_gb=0.0,
                active_connections=0,
                error_rate_last_hour=0.0,
            )

    async def _queue_update(
        self,
        update_type: str,
        entity_id: str,
        update_data: Dict[str, Any],
        message: WebSocketMessage,
    ):
        """Queue an update for processing"""
        try:
            # Check if we should throttle this update
            if self._should_throttle_update(entity_id):
                return

            # Add to cache
            self._update_cache[entity_id] = {
                "data": update_data,
                "timestamp": datetime.now(dt_timezone.utc),
                "message": message,
            }

            # Add to queue for processing
            await self._update_queue.put(
                {
                    "type": update_type,
                    "entity_id": entity_id,
                    "data": update_data,
                    "message": asdict(message),
                }
            )

        except Exception as e:
            logger.error(f"Error queuing update: {e}")

    def _should_throttle_update(self, entity_id: str) -> bool:
        """Check if an update should be throttled"""
        if entity_id not in self._last_update_time:
            return False

        time_since_last = (
            datetime.now(dt_timezone.utc) - self._last_update_time[entity_id]
        ).total_seconds()

        # Get throttle interval based on frequency (simplified)
        throttle_interval = 1.0  # Default 1 second

        return time_since_last < throttle_interval

    async def _process_update_queue(self):
        """Process updates from the queue"""
        while True:
            try:
                # Get update from queue
                update = await asyncio.wait_for(self._update_queue.get(), timeout=1.0)

                entity_id = update["entity_id"]
                self._last_update_time[entity_id] = datetime.now(dt_timezone.utc)

                # Add to batch for broadcasting
                update_type = update["type"]
                if update_type not in self._batch_updates:
                    self._batch_updates[update_type] = []
                self._batch_updates[update_type].append(update)

                # Check if we should broadcast the batch
                if len(self._batch_updates[update_type]) >= self.batch_size:
                    await self._broadcast_update_batch(update_type)

            except asyncio.TimeoutError:
                # Check for batches that need broadcasting due to timeout
                for update_type in list(self._batch_updates.keys()):
                    if self._batch_updates[update_type]:
                        await self._broadcast_update_batch(update_type)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing update queue: {e}")

    async def _broadcast_update_batch(self, update_type: str):
        """Broadcast a batch of updates"""
        if (
            update_type not in self._batch_updates
            or not self._batch_updates[update_type]
        ):
            return

        batch = self._batch_updates[update_type].copy()
        self._batch_updates[update_type].clear()

        try:
            # Group updates by channel
            channel_batches = {}
            for batch_item in batch:
                message_dict = batch_item["message"]
                message = WebSocketMessage(**message_dict)

                for channel in message.target_channels:
                    if channel not in channel_batches:
                        channel_batches[channel] = []
                    channel_batches[channel].append(message)

            # Broadcast each channel batch
            for channel, messages in channel_batches.items():
                # Create batch message
                batch_message = WebSocketMessage(
                    type=MessageType.STATUS_UPDATE,
                    data={
                        "batch": True,
                        "update_type": update_type,
                        "updates": [
                            {
                                "id": msg.message_id,
                                "type": msg.type.value,
                                "data": msg.data,
                                "timestamp": msg.timestamp.isoformat(),
                                "priority": msg.priority.value,
                            }
                            for msg in messages
                        ],
                        "total_updates": len(messages),
                    },
                    timestamp=datetime.now(dt_timezone.utc),
                    target_channels=[channel],
                )

                await connection_manager.broadcast_to_channel(channel, batch_message)

        except Exception as e:
            logger.error(f"Error broadcasting update batch: {e}")

    async def _broadcast_batch_updates(self):
        """Periodic broadcasting of batched updates"""
        while True:
            try:
                await asyncio.sleep(self.batch_timeout)

                # Broadcast all pending batches
                for update_type in list(self._batch_updates.keys()):
                    if self._batch_updates[update_type]:
                        await self._broadcast_update_batch(update_type)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch broadcasting: {e}")

    async def _cleanup_old_data(self):
        """Periodic cleanup of old data"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour

                current_time = datetime.now(dt_timezone.utc)
                expired_entities = []

                # Clean up old cache entries
                for entity_id, cache_entry in self._update_cache.items():
                    if current_time - cache_entry["timestamp"] > self.max_cache_age:
                        expired_entities.append(entity_id)

                for entity_id in expired_entities:
                    del self._update_cache[entity_id]
                    self._last_update_time.pop(entity_id, None)

                if expired_entities:
                    logger.info(
                        f"Cleaned up {len(expired_entities)} expired status update cache entries"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")

    async def _process_remaining_updates(self):
        """Process any remaining updates before shutdown"""
        try:
            # Process remaining queue items
            while not self._update_queue.empty():
                update = self._update_queue.get_nowait()
                entity_id = update["entity_id"]
                self._last_update_time[entity_id] = datetime.now(dt_timezone.utc)

            # Broadcast remaining batches
            for update_type in list(self._batch_updates.keys()):
                if self._batch_updates[update_type]:
                    await self._broadcast_update_batch(update_type)

        except Exception as e:
            logger.error(f"Error processing remaining updates: {e}")

    async def _log_status_update(
        self,
        update_type: UpdateType,
        title: str,
        message: str,
        update_data: Dict[str, Any],
        target_users: List[str] = None,
        target_organizations: List[str] = None,
    ):
        """Log status update to database"""
        try:
            async with get_async_session() as session:
                status_update = StatusUpdate(
                    update_id=str(uuid.uuid4()),
                    update_type=update_type,
                    title=title,
                    message=message,
                    update_data=update_data,
                    target_users=target_users,
                    target_organizations=target_organizations,
                    priority=self._map_priority(update_type),
                )

                session.add(status_update)
                await session.commit()

        except Exception as e:
            logger.error(f"Failed to log status update to database: {e}")

    def _get_priority_for_status(self, status: ProcessingStatus) -> Priority:
        """Get WebSocket message priority for document status"""
        priority_map = {
            ProcessingStatus.COMPLETED: Priority.NORMAL,
            ProcessingStatus.FAILED: Priority.HIGH,
            ProcessingStatus.PROCESSING: Priority.NORMAL,
            ProcessingStatus.PENDING: Priority.LOW,
            ProcessingStatus.RETRYING: Priority.NORMAL,
        }
        return priority_map.get(status, Priority.NORMAL)

    def _get_priority_for_job_status(self, status: JobStatus) -> Priority:
        """Get WebSocket message priority for job status"""
        priority_map = {
            JobStatus.COMPLETED: Priority.NORMAL,
            JobStatus.FAILED: Priority.HIGH,
            JobStatus.RUNNING: Priority.NORMAL,
            JobStatus.QUEUED: Priority.LOW,
            JobStatus.CANCELLED: Priority.NORMAL,
            JobStatus.RETRYING: Priority.NORMAL,
        }
        return priority_map.get(status, Priority.NORMAL)

    def _map_priority(self, update_type: UpdateType) -> UpdatePriority:
        """Map WebSocket priority to database priority"""
        priority_map = {
            Priority.CRITICAL: UpdatePriority.CRITICAL,
            Priority.HIGH: UpdatePriority.HIGH,
            Priority.NORMAL: UpdatePriority.NORMAL,
            Priority.LOW: UpdatePriority.LOW,
        }
        return priority_map.get(Priority.NORMAL, UpdatePriority.NORMAL)


# Global status update service instance
status_update_service = StatusUpdateService()
