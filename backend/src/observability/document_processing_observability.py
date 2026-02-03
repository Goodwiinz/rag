"""
Real-time Document Processing Observability Module
Comprehensive monitoring for document processing pipeline with WebSocket status tracking
"""

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

import psutil

from src.models.websocket_status import (
    ConnectionEvent,
    StatusUpdate,
    WebSocketConnection,
)

from ..monitoring.metrics import business_metrics
from ..monitoring.opentelemetry import otel_manager, trace_context, trace_span

logger = logging.getLogger(__name__)


class DocumentProcessingStatus(Enum):
    """Document processing status states"""

    QUEUED = "queued"
    UPLOADING = "uploading"
    VALIDATING = "validating"
    EXTRACTING_TEXT = "extracting_text"
    EXTRACTING_ENTITIES = "extracting_entities"
    GENERATING_EMBEDDINGS = "generating_embeddings"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class ProcessingStage(Enum):
    """Processing pipeline stages"""

    UPLOAD = "upload"
    PREPROCESSING = "preprocessing"
    OCR = "ocr"
    TEXT_EXTRACTION = "text_extraction"
    ENTITY_RECOGNITION = "entity_recognition"
    VECTOR_EMBEDDING = "vector_embedding"
    GRAPH_INDEXING = "graph_indexing"
    QUALITY_CHECK = "quality_check"
    FINALIZATION = "finalization"


@dataclass
class DocumentProcessingMetric:
    """Individual document processing metric"""

    document_id: str
    processing_stage: ProcessingStage
    status: DocumentProcessingStatus
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    file_size_bytes: Optional[int] = None
    file_type: Optional[str] = None
    pages_count: Optional[int] = None
    text_extraction_duration_ms: Optional[float] = None
    entity_count: Optional[int] = None
    embedding_count: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    worker_id: Optional[str] = None
    queue_wait_time_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None


@dataclass
class WebSocketMetric:
    """WebSocket connection and performance metric"""

    connection_id: str
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    event_type: str = ""
    timestamp: float = field(default_factory=time.time)
    latency_ms: Optional[float] = None
    message_size_bytes: Optional[int] = None
    processing_time_ms: Optional[float] = None
    error_type: Optional[str] = None
    client_info: Dict[str, Any] = field(default_factory=dict)
    server_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealthMetric:
    """System health and resource utilization metric"""

    timestamp: float = field(default_factory=time.time)
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_available_gb: Optional[float] = None
    disk_usage_percent: Optional[float] = None
    disk_free_gb: Optional[float] = None
    network_io_bytes_sent: Optional[int] = None
    network_io_bytes_recv: Optional[int] = None
    active_connections: Optional[int] = None
    queue_size: Optional[int] = None
    processing_jobs_active: Optional[int] = None
    error_rate_1m: Optional[float] = None
    avg_response_time_1m: Optional[float] = None


from .prometheus_metrics import PrometheusMetricsCollector

# Global instances
prometheus_collector = PrometheusMetricsCollector()


class DocumentProcessingObservability:
    """Comprehensive observability for document processing pipeline"""

    def __init__(self, max_metrics_history: int = 10000):
        self.max_metrics_history = max_metrics_history

        # In-memory metrics storage (in production, use time-series database)
        self.document_metrics: deque = deque(maxlen=max_metrics_history)
        self.websocket_metrics: deque = deque(maxlen=max_metrics_history)
        self.system_metrics: deque = deque(maxlen=max_metrics_history)

        # Active processing tracking
        self.active_documents: Dict[str, DocumentProcessingMetric] = {}
        self.stage_start_times: Dict[str, float] = {}

        # Performance aggregations
        self.stage_performance: Dict[str, List[float]] = defaultdict(list)
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.throughput_history: deque = deque(
            maxlen=3600
        )  # 1 hour at 1-second granularity

        # WebSocket connection tracking
        self.websocket_connections: Dict[str, WebSocketMetric] = {}

        # Background monitoring tasks
        self._monitoring_tasks: List[asyncio.Task] = []
        self._shutdown = False

    async def start_document_processing(
        self,
        document_id: str,
        file_size_bytes: int,
        file_type: str,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> str:
        """Start tracking document processing"""
        current_time = time.time()
        trace_id = (
            otel_manager.get_trace_id()
            if hasattr(otel_manager, "get_trace_id")
            else None
        )

        metric = DocumentProcessingMetric(
            document_id=document_id,
            processing_stage=ProcessingStage.UPLOAD,
            status=DocumentProcessingStatus.UPLOADING,
            start_time=current_time,
            file_size_bytes=file_size_bytes,
            file_type=file_type,
            trace_id=trace_id,
            metadata={
                "user_id": user_id,
                "organization_id": organization_id,
                "start_timestamp": datetime.utcnow().isoformat(),
            },
        )

        self.active_documents[document_id] = metric
        self.stage_start_times[
            f"{document_id}_{ProcessingStage.UPLOAD.value}"
        ] = current_time

        # Record OpenTelemetry metrics
        otel_manager.increment_counter(
            "document_processing_started",
            {
                "document_id": document_id,
                "file_type": file_type,
                "file_size_tier": self._get_file_size_tier(file_size_bytes),
            },
        )

        # Record Prometheus metrics
        prometheus_collector.record_document_processing_start(
            file_type=file_type, user_role="user"  # Default role
        )
        prometheus_collector.update_processing_queue_metrics(
            queue_size=0,  # Need to get actual queue size if available
            active_jobs=len(self.active_documents),
        )

        # Record business metrics
        business_metrics.track_document_processing(
            file_size_bytes=file_size_bytes,
            duration_seconds=0,  # Will be updated on completion
            entities_extracted=0,  # Will be updated on completion
            file_type=file_type,
        )

        # Send WebSocket update
        await self._send_websocket_update(
            update_type="document_processing_started",
            data={
                "document_id": document_id,
                "file_type": file_type,
                "status": DocumentProcessingStatus.UPLOADING.value,
                "progress_percentage": 0.0,
            },
            target_users=[user_id] if user_id else None,
            target_organizations=[organization_id] if organization_id else None,
        )

        logger.info(f"Started tracking document processing: {document_id}")
        return document_id

    async def update_processing_stage(
        self,
        document_id: str,
        stage: ProcessingStage,
        status: DocumentProcessingStatus,
        additional_data: Optional[Dict[str, Any]] = None,
    ):
        """Update document processing stage"""
        if document_id not in self.active_documents:
            logger.warning(f"Document {document_id} not found in active tracking")
            return

        current_time = time.time()
        metric = self.active_documents[document_id]

        # Calculate stage duration
        stage_key = f"{document_id}_{stage.value}"
        if stage_key in self.stage_start_times:
            stage_duration_ms = (
                current_time - self.stage_start_times[stage_key]
            ) * 1000
            self.stage_performance[stage.value].append(stage_duration_ms)

            # Keep only recent performance data
            if len(self.stage_performance[stage.value]) > 1000:
                self.stage_performance[stage.value] = self.stage_performance[
                    stage.value
                ][-1000:]

        # Update metric
        metric.processing_stage = stage
        metric.status = status
        metric.metadata.update(additional_data or {})

        # Record OpenTelemetry span
        with trace_context(
            f"document_processing_{stage.value}", component="document_processing"
        ):
            otel_manager.set_span_attribute("document_id", document_id)
            otel_manager.set_span_attribute("processing_stage", stage.value)
            otel_manager.set_span_attribute("status", status.value)

            if additional_data:
                for key, value in additional_data.items():
                    otel_manager.set_span_attribute(f"processing.{key}", value)

        # Record metrics
        otel_manager.increment_counter(
            "document_processing_stage_updates",
            {"document_id": document_id, "stage": stage.value, "status": status.value},
        )

        # Calculate progress percentage
        progress_percentage = self._calculate_progress_percentage(stage)

        # Send WebSocket update
        await self._send_websocket_update(
            update_type="document_processing_progress",
            data={
                "document_id": document_id,
                "stage": stage.value,
                "status": status.value,
                "progress_percentage": progress_percentage,
                "additional_data": additional_data,
            },
        )

        # Start timing new stage
        self.stage_start_times[f"{document_id}_{stage.value}"] = current_time

        logger.info(
            f"Updated document {document_id} to stage {stage.value} with status {status.value}"
        )

    async def complete_document_processing(
        self,
        document_id: str,
        entities_extracted: int = 0,
        embedding_count: int = 0,
        pages_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ):
        """Complete document processing tracking"""
        if document_id not in self.active_documents:
            logger.warning(f"Document {document_id} not found in active tracking")
            return

        current_time = time.time()
        metric = self.active_documents[document_id]

        # Calculate total duration
        metric.end_time = current_time
        metric.duration_ms = (current_time - metric.start_time) * 1000
        metric.entities_extracted = entities_extracted
        metric.embedding_count = embedding_count
        metric.pages_count = pages_count

        if error_message:
            metric.status = DocumentProcessingStatus.FAILED
            metric.error_message = error_message
            self.error_counts[
                f"document_processing_{metric.processing_stage.value}"
            ] += 1
        else:
            metric.status = DocumentProcessingStatus.COMPLETED

        # Move to historical metrics
        self.document_metrics.append(metric)
        del self.active_documents[document_id]

        # Clean up stage start times
        keys_to_remove = [
            key
            for key in self.stage_start_times.keys()
            if key.startswith(f"{document_id}_")
        ]
        for key in keys_to_remove:
            del self.stage_start_times[key]

        # Record final metrics
        labels = {
            "document_id": document_id,
            "file_type": metric.file_type,
            "status": metric.status.value,
            "file_size_tier": self._get_file_size_tier(metric.file_size_bytes or 0),
        }

        if metric.duration_ms:
            otel_manager.record_metric(
                "document_processing_duration_ms", metric.duration_ms, labels
            )

        if entities_extracted > 0:
            otel_manager.record_metric(
                "document_entities_extracted", entities_extracted, labels
            )

        if embedding_count > 0:
            otel_manager.record_metric(
                "document_embeddings_generated", embedding_count, labels
            )

        # Record Prometheus metrics
        prometheus_collector.record_document_processing_complete(
            file_type=metric.file_type,
            status=metric.status.value,
            duration_seconds=metric.duration_ms / 1000,
            user_role="user",
            entities_count=entities_extracted,
            embeddings_count=embedding_count,
            file_size_bytes=metric.file_size_bytes,
        )
        prometheus_collector.update_processing_queue_metrics(
            queue_size=0, active_jobs=len(self.active_documents)
        )

        # Update business metrics
        if metric.duration_ms and metric.file_size_bytes:
            business_metrics.track_document_processing(
                file_size_bytes=metric.file_size_bytes,
                duration_seconds=metric.duration_ms / 1000,
                entities_extracted=entities_extracted,
                file_type=metric.file_type,
            )

        # Record throughput
        self.throughput_history.append(
            {
                "timestamp": current_time,
                "document_id": document_id,
                "status": metric.status.value,
                "duration_ms": metric.duration_ms,
            }
        )

        # Send WebSocket update
        await self._send_websocket_update(
            update_type="document_processing_completed",
            data={
                "document_id": document_id,
                "status": metric.status.value,
                "duration_ms": metric.duration_ms,
                "entities_extracted": entities_extracted,
                "embedding_count": embedding_count,
                "error_message": error_message,
            },
        )

        logger.info(
            f"Completed tracking document {document_id} with status {metric.status.value}"
        )

    async def track_websocket_event(
        self,
        connection_id: str,
        event_type: str,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        latency_ms: Optional[float] = None,
        message_size_bytes: Optional[int] = None,
        processing_time_ms: Optional[float] = None,
        error_type: Optional[str] = None,
        client_info: Optional[Dict[str, Any]] = None,
        server_info: Optional[Dict[str, Any]] = None,
    ):
        """Track WebSocket connection event"""
        metric = WebSocketMetric(
            connection_id=connection_id,
            user_id=user_id,
            organization_id=organization_id,
            event_type=event_type,
            latency_ms=latency_ms,
            message_size_bytes=message_size_bytes,
            processing_time_ms=processing_time_ms,
            error_type=error_type,
            client_info=client_info or {},
            server_info=server_info or {},
        )

        self.websocket_metrics.append(metric)
        self.websocket_connections[connection_id] = metric

        # Record OpenTelemetry metrics
        otel_manager.increment_counter(
            "websocket_events_total",
            {
                "event_type": event_type,
                "user_id": user_id or "anonymous",
                "has_error": str(bool(error_type)).lower(),
            },
        )

        if latency_ms is not None:
            otel_manager.record_metric(
                "websocket_latency_ms",
                latency_ms,
                {"event_type": event_type, "user_id": user_id or "anonymous"},
            )

        if message_size_bytes is not None:
            otel_manager.record_metric(
                "websocket_message_size_bytes",
                message_size_bytes,
                {"event_type": event_type},
            )

        # Record Prometheus metrics
        if event_type == "connect":
            prometheus_collector.record_websocket_connection(connected=True)
        elif event_type == "disconnect":
            prometheus_collector.record_websocket_connection(connected=False)
        elif event_type == "message":
            prometheus_collector.record_websocket_message(
                message_type="unknown",
                direction="unknown",
                status="success" if not error_type else "error",
                duration_seconds=(latency_ms or 0) / 1000,
                message_size_bytes=message_size_bytes,
            )

        if error_type:
            prometheus_collector.record_websocket_error(error_type=error_type)

        # Update business metrics
        business_metrics.track_api_request(
            endpoint="/websocket",
            method="WS",
            status_code=200 if not error_type else 500,
            duration_seconds=(latency_ms or 0) / 1000,
            request_size=message_size_bytes or 0,
            response_size=0,
        )

    async def collect_system_health_metrics(self):
        """Collect system health and resource metrics"""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            network = psutil.net_io_counters()

            # Get WebSocket connection count
            active_connections = len(
                [
                    w
                    for w in self.websocket_connections.values()
                    if w.timestamp > time.time() - 300
                ]
            )  # Last 5 minutes

            # Get processing job counts
            processing_jobs_active = len(self.active_documents)

            # Calculate error rate and response time from recent metrics
            recent_metrics = [
                m
                for m in self.document_metrics
                if m.end_time and m.end_time > time.time() - 60
            ]  # Last minute

            error_rate_1m = None
            avg_response_time_1m = None

            if recent_metrics:
                error_count = len(
                    [
                        m
                        for m in recent_metrics
                        if m.status == DocumentProcessingStatus.FAILED
                    ]
                )
                error_rate_1m = (error_count / len(recent_metrics)) * 100

                completed_metrics = [m for m in recent_metrics if m.duration_ms]
                if completed_metrics:
                    avg_response_time_1m = sum(
                        m.duration_ms for m in completed_metrics
                    ) / len(completed_metrics)

            metric = SystemHealthMetric(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_available_gb=memory.available / (1024**3),
                disk_usage_percent=(disk.used / disk.total) * 100,
                disk_free_gb=disk.free / (1024**3),
                network_io_bytes_sent=network.bytes_sent,
                network_io_bytes_recv=network.bytes_recv,
                active_connections=active_connections,
                processing_jobs_active=processing_jobs_active,
                error_rate_1m=error_rate_1m,
                avg_response_time_1m=avg_response_time_1m,
            )

            self.system_metrics.append(metric)

            # Record OpenTelemetry metrics
            otel_manager.record_metric("system_cpu_percent", cpu_percent)
            otel_manager.record_metric("system_memory_percent", memory.percent)
            otel_manager.record_metric(
                "system_disk_usage_percent", metric.disk_usage_percent
            )
            otel_manager.record_metric("active_connections", active_connections)
            otel_manager.record_metric("processing_jobs_active", processing_jobs_active)

            if error_rate_1m is not None:
                otel_manager.record_metric("error_rate_1m", error_rate_1m)

            if avg_response_time_1m is not None:
                otel_manager.record_metric("avg_response_time_1m", avg_response_time_1m)

            # Record Prometheus metrics
            # Note: PrometheusMetricsCollector has its own background collection,
            # but we can sync some application-specific metrics here
            prometheus_collector.update_processing_queue_metrics(
                queue_size=0, active_jobs=processing_jobs_active
            )
            prometheus_collector.update_documents_count(
                status="processing", file_type="all", count=processing_jobs_active
            )

            # Update business metrics
            business_metrics.metrics["memory_usage_bytes"].set(
                memory.total * (memory.percent / 100)
            )
            business_metrics.metrics["cpu_usage_percent"].set(cpu_percent)
            business_metrics.metrics["active_connections_total"].set(active_connections)

        except Exception as e:
            logger.error(f"Failed to collect system health metrics: {e}")

    async def get_real_time_dashboard_data(self) -> Dict[str, Any]:
        """Get real-time dashboard data"""
        current_time = time.time()

        # Active processing documents
        active_processing = [
            {
                "document_id": metric.document_id,
                "stage": metric.processing_stage.value,
                "status": metric.status.value,
                "duration_seconds": (current_time - metric.start_time),
                "file_type": metric.file_type,
                "progress_percentage": self._calculate_progress_percentage(
                    metric.processing_stage
                ),
            }
            for metric in self.active_documents.values()
        ]

        # Recent completions (last hour)
        recent_completions = [
            {
                "document_id": metric.document_id,
                "status": metric.status.value,
                "duration_ms": metric.duration_ms,
                "file_type": metric.file_type,
                "entities_extracted": metric.entities_extracted,
                "completed_at": metric.end_time,
            }
            for metric in self.document_metrics
            if metric.end_time and metric.end_time > current_time - 3600
        ]

        # Stage performance statistics
        stage_stats = {}
        for stage, durations in self.stage_performance.items():
            if durations:
                stage_stats[stage] = {
                    "avg_duration_ms": sum(durations) / len(durations),
                    "min_duration_ms": min(durations),
                    "max_duration_ms": max(durations),
                    "p95_duration_ms": sorted(durations)[int(len(durations) * 0.95)],
                    "count": len(durations),
                }

        # Error rates by stage
        error_rates = {}
        total_errors = sum(self.error_counts.values())
        for stage, count in self.error_counts.items():
            error_rates[stage] = {
                "count": count,
                "percentage": (count / max(total_errors, 1)) * 100,
            }

        # Current system health
        current_system_health = self.system_metrics[-1] if self.system_metrics else None

        # WebSocket connection health
        recent_websocket_metrics = [
            metric
            for metric in self.websocket_metrics
            if metric.timestamp > current_time - 300  # Last 5 minutes
        ]

        websocket_health = {
            "total_events": len(recent_websocket_metrics),
            "avg_latency_ms": sum(m.latency_ms or 0 for m in recent_websocket_metrics)
            / max(len(recent_websocket_metrics), 1),
            "error_rate": len([m for m in recent_websocket_metrics if m.error_type])
            / max(len(recent_websocket_metrics), 1)
            * 100,
            "active_connections": len(
                set(m.connection_id for m in recent_websocket_metrics)
            ),
        }

        return {
            "timestamp": current_time,
            "active_processing": active_processing,
            "recent_completions": recent_completions,
            "stage_performance": stage_stats,
            "error_rates": error_rates,
            "system_health": asdict(current_system_health)
            if current_system_health
            else None,
            "websocket_health": websocket_health,
            "throughput_last_hour": len(
                [
                    t
                    for t in self.throughput_history
                    if t["timestamp"] > current_time - 3600
                ]
            ),
        }

    def _calculate_progress_percentage(self, stage: ProcessingStage) -> float:
        """Calculate progress percentage based on current stage"""
        stage_weights = {
            ProcessingStage.UPLOAD: 5,
            ProcessingStage.PREPROCESSING: 10,
            ProcessingStage.OCR: 25,
            ProcessingStage.TEXT_EXTRACTION: 40,
            ProcessingStage.ENTITY_RECOGNITION: 60,
            ProcessingStage.VECTOR_EMBEDDING: 80,
            ProcessingStage.GRAPH_INDEXING: 90,
            ProcessingStage.QUALITY_CHECK: 95,
            ProcessingStage.FINALIZATION: 100,
        }
        return stage_weights.get(stage, 0.0)

    def _get_file_size_tier(self, size_bytes: int) -> str:
        """Get file size tier for metrics categorization"""
        if size_bytes < 1024 * 1024:  # < 1MB
            return "small"
        elif size_bytes < 10 * 1024 * 1024:  # < 10MB
            return "medium"
        elif size_bytes < 100 * 1024 * 1024:  # < 100MB
            return "large"
        else:
            return "xlarge"

    async def _send_websocket_update(
        self,
        update_type: str,
        data: Dict[str, Any],
        target_users: Optional[List[str]] = None,
        target_organizations: Optional[List[str]] = None,
    ):
        """Send WebSocket update to connected clients via Redis Pub/Sub"""
        try:
            from ..websocket.redis_integration import get_websocket_redis_manager

            redis_manager = get_websocket_redis_manager()
            if not redis_manager or not redis_manager._redis_client:
                # If redis manager is not initialized (e.g. in tests or standalone scripts),
                # we just log the update
                logger.debug(
                    f"Redis manager not available, skipping WebSocket update: {update_type}"
                )
                return

            # Construct message for document_processing_events channel
            # This matches the format expected by setup_document_processing_listeners in server.py
            event_data = {
                "type": "document_status_change",
                "data": {
                    "document_id": data.get("document_id"),
                    "user_id": target_users[0] if target_users else None,
                    "organization_id": target_organizations[0]
                    if target_organizations
                    else None,
                    "status": data.get("status"),
                    "metadata": {
                        "update_type": update_type,
                        "progress_percentage": data.get("progress_percentage"),
                        "stage": data.get("stage"),
                        "additional_data": data.get("additional_data"),
                        "error_message": data.get("error_message"),
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                },
            }

            # Publish to Redis
            await redis_manager.publish("document_processing_events", event_data)
            logger.debug(
                f"Published WebSocket update: {update_type} -> {data.get('document_id')}"
            )

        except Exception as e:
            logger.error(f"Failed to send WebSocket update: {e}")

    async def start_monitoring_tasks(self):
        """Start background monitoring tasks"""
        if self._monitoring_tasks:
            return  # Already started

        # System metrics collection task
        self._monitoring_tasks.append(asyncio.create_task(self._system_metrics_loop()))

        # Cleanup old metrics task
        self._monitoring_tasks.append(asyncio.create_task(self._cleanup_metrics_loop()))

        # Start Prometheus metrics server
        try:
            prometheus_collector.start_metrics_server(port=8002)
            await prometheus_collector.start_background_collection()
        except Exception as e:
            logger.warning(f"Failed to start Prometheus metrics server: {e}")

        logger.info("Started observability monitoring tasks")

    async def stop_monitoring_tasks(self):
        """Stop background monitoring tasks"""
        self._shutdown = True

        for task in self._monitoring_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._monitoring_tasks.clear()
        logger.info("Stopped observability monitoring tasks")

    async def _system_metrics_loop(self):
        """Background loop for collecting system metrics"""
        while not self._shutdown:
            try:
                await self.collect_system_health_metrics()
                await asyncio.sleep(30)  # Collect every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in system metrics loop: {e}")
                await asyncio.sleep(5)  # Brief delay on error

    async def _cleanup_metrics_loop(self):
        """Background loop for cleaning up old metrics"""
        while not self._shutdown:
            try:
                current_time = time.time()
                cutoff_time = current_time - 24 * 3600  # 24 hours ago

                # Clean old WebSocket metrics
                self.websocket_metrics = deque(
                    [m for m in self.websocket_metrics if m.timestamp > cutoff_time],
                    maxlen=self.max_metrics_history,
                )

                # Clean old system metrics
                self.system_metrics = deque(
                    [m for m in self.system_metrics if m.timestamp > cutoff_time],
                    maxlen=self.max_metrics_history,
                )

                # Clean old throughput history
                self.throughput_history = deque(
                    [
                        t
                        for t in self.throughput_history
                        if t["timestamp"] > cutoff_time
                    ],
                    maxlen=3600,
                )

                await asyncio.sleep(3600)  # Clean every hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup metrics loop: {e}")
                await asyncio.sleep(300)  # 5 minute delay on error


# Global observability instance
document_processing_observability = DocumentProcessingObservability()


# Convenience functions for easy integration
async def start_document_tracking(
    document_id: str,
    file_size_bytes: int,
    file_type: str,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
) -> str:
    """Start tracking document processing"""
    return await document_processing_observability.start_document_processing(
        document_id, file_size_bytes, file_type, user_id, organization_id
    )


async def update_processing_stage(
    document_id: str,
    stage: ProcessingStage,
    status: DocumentProcessingStatus,
    additional_data: Optional[Dict[str, Any]] = None,
):
    """Update document processing stage"""
    await document_processing_observability.update_processing_stage(
        document_id, stage, status, additional_data
    )


async def complete_document_tracking(
    document_id: str,
    entities_extracted: int = 0,
    embedding_count: int = 0,
    pages_count: Optional[int] = None,
    error_message: Optional[str] = None,
):
    """Complete document processing tracking"""
    await document_processing_observability.complete_document_processing(
        document_id, entities_extracted, embedding_count, pages_count, error_message
    )


async def track_websocket_event(
    connection_id: str,
    event_type: str,
    user_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    **kwargs,
):
    """Track WebSocket event"""
    await document_processing_observability.track_websocket_event(
        connection_id, event_type, user_id, organization_id, **kwargs
    )


async def get_dashboard_data() -> Dict[str, Any]:
    """Get real-time dashboard data"""
    return await document_processing_observability.get_real_time_dashboard_data()
