"""
WebSocket Message Schemas for Real-Time Document Processing
Defines standardized message formats for different types of updates
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime, timezone
from enum import Enum
import uuid

class MessageType(str, Enum):
    """WebSocket message types"""
    # Connection management
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"

    # Document processing
    DOCUMENT_STATUS_UPDATE = "document_status_update"
    PROCESSING_PROGRESS = "processing_progress"
    STAGE_COMPLETE = "stage_complete"
    STAGE_FAILED = "stage_failed"
    PROCESSING_COMPLETE = "processing_complete"

    # Quality and metrics
    QUALITY_METRICS = "quality_metrics"
    PERFORMANCE_UPDATE = "performance_update"
    ERROR_OCCURRED = "error_occurred"

    # System notifications
    SYSTEM_NOTIFICATION = "system_notification"
    MAINTENANCE_ALERT = "maintenance_alert"

    # Batch operations
    BATCH_UPDATE = "batch_update"
    QUEUE_STATUS = "queue_status"

class ProcessingStage(str, Enum):
    """Processing pipeline stages"""
    QUEUED = "queued"
    INGESTION = "ingestion"
    EXTRACTION = "extraction"
    OCR_PROCESSING = "ocr_processing"
    TRANSCRIPTION = "transcription"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    QUALITY_CHECK = "quality_check"
    COMPLETED = "completed"
    FAILED = "failed"

class DocumentType(str, Enum):
    """Document types"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    PDF = "pdf"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    MULTIMODAL = "multimodal"

class SeverityLevel(str, Enum):
    """Message severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class PriorityLevel(str, Enum):
    """Message priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"
    URGENT = "urgent"

class BaseMessage(BaseModel):
    """Base WebSocket message structure"""
    type: MessageType = Field(..., description="Message type identifier")
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique message identifier")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="Message expiration time")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class MessageMetadata(BaseModel):
    """Message metadata"""
    connection_id: Optional[str] = None
    organization_id: Optional[str] = None
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    source_service: Optional[str] = None
    version: str = "1.0"

class ConnectionMessage(BaseModel):
    """Connection establishment message"""
    type: MessageType = MessageType.CONNECTED
    data: Dict[str, Any] = Field(..., description="Connection data")

class DocumentStatusData(BaseModel):
    """Document status update data"""
    document_id: str = Field(..., description="Document UUID")
    processing_status: ProcessingStage = Field(..., description="Current processing status")
    progress_percentage: Optional[float] = Field(None, ge=0, le=100)
    current_stage: ProcessingStage = Field(..., description="Current processing stage")
    current_step: Optional[str] = Field(None, description="Current step description")

    # Timing information
    processing_duration_seconds: Optional[float] = Field(None)
    estimated_remaining_seconds: Optional[int] = Field(None)
    processing_started_at: Optional[datetime] = None

    # Error and retry information
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)

    # Performance metrics
    processing_rate: Optional[float] = Field(None, description="Items per second")
    memory_usage_mb: Optional[float] = Field(None)
    cpu_usage_percent: Optional[float] = Field(None, ge=0, le=100)

    # Document metadata
    document_type: DocumentType
    file_size_bytes: int
    file_name: str

    # Additional metadata
    stage_metadata: Dict[str, Any] = Field(default_factory=dict)

class DocumentStatusUpdate(BaseModel):
    """Document status update message"""
    type: MessageType = MessageType.DOCUMENT_STATUS_UPDATE
    data: DocumentStatusData
    metadata: Optional[MessageMetadata] = None
    priority: PriorityLevel = PriorityLevel.NORMAL
    severity: SeverityLevel = SeverityLevel.INFO

class ProcessingProgressData(BaseModel):
    """Processing progress data"""
    job_execution_id: Optional[str] = None
    stage_execution_id: Optional[str] = None
    document_id: str

    # Progress information
    stage: ProcessingStage
    step: str
    progress_percentage: float = Field(..., ge=0, le=100)
    items_processed: int = Field(..., ge=0)
    total_items: int = Field(..., ge=0)

    # Performance metrics
    processing_rate: Optional[float] = Field(None, description="Items per second")
    average_step_duration_ms: Optional[float] = Field(None)
    estimated_completion: Optional[datetime] = None

    # Resource usage
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = Field(None, ge=0, le=100)
    gpu_usage_percent: Optional[float] = Field(None, ge=0, le=100)
    disk_io_rate_mb_s: Optional[float] = None

    # Quality metrics
    current_quality_score: Optional[float] = Field(None, ge=0, le=1)
    error_rate: Optional[float] = Field(None, ge=0, le=1)

    @validator('estimated_completion', pre=True, always=True)
    def calculate_estimated_completion(cls, v, values):
        if v is not None:
            return v
        # Calculate estimated completion if not provided
        if 'progress_percentage' in values and 'processing_rate' in values:
            progress = values['progress_percentage']
            rate = values.get('processing_rate')
            if rate and rate > 0:
                remaining_items = (100 - progress) / 100 * values.get('total_items', 1)
                estimated_seconds = remaining_items / rate
                return datetime.now(timezone.utc).timestamp() + estimated_seconds
        return None

class ProcessingProgress(BaseModel):
    """Processing progress update message"""
    type: MessageType = MessageType.PROCESSING_PROGRESS
    data: ProcessingProgressData
    metadata: Optional[MessageMetadata] = None
    priority: PriorityLevel = PriorityLevel.NORMAL

class StageCompletionData(BaseModel):
    """Stage completion data"""
    job_execution_id: Optional[str] = None
    stage_execution_id: Optional[str] = None
    document_id: str

    # Stage information
    stage: ProcessingStage
    stage_name: str
    success: bool
    completion_time: datetime

    # Performance metrics
    duration_seconds: float
    items_processed: int
    average_processing_rate: float

    # Results
    results: Dict[str, Any] = Field(default_factory=dict)
    extracted_entities: Optional[List[str]] = None
    extracted_keywords: Optional[List[str]] = None
    generated_summary: Optional[str] = None

    # Quality assessment
    stage_quality_score: Optional[float] = Field(None, ge=0, le=1)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

class StageComplete(BaseModel):
    """Stage completion message"""
    type: MessageType = MessageType.STAGE_COMPLETE
    data: StageCompletionData
    metadata: Optional[MessageMetadata] = None
    priority: PriorityLevel = PriorityLevel.HIGH

class QualityMetricsData(BaseModel):
    """Document quality metrics"""
    document_id: str
    processing_complete: bool

    # RAG Triad metrics
    answer_relevancy: Optional[float] = Field(None, ge=0, le=1)
    faithfulness: Optional[float] = Field(None, ge=0, le=1)
    contextual_relevancy: Optional[float] = Field(None, ge=0, le=1)

    # Processing quality metrics
    extraction_accuracy: Optional[float] = Field(None, ge=0, le=1)
    transcription_accuracy: Optional[float] = Field(None, ge=0, le=1)
    ocr_accuracy: Optional[float] = Field(None, ge=0, le=1)
    embedding_quality: Optional[float] = Field(None, ge=0, le=1)

    # Overall quality score
    processing_quality_score: Optional[float] = Field(None, ge=0, le=1)

    # Performance metrics
    processing_latency_ms: Optional[int] = None
    throughput_items_per_second: Optional[float] = None
    resource_efficiency: Optional[float] = Field(None, ge=0, le=1)

    # Recommendations
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)

    @validator('processing_quality_score', pre=True, always=True)
    def calculate_overall_quality(cls, v, values):
        if v is not None:
            return v
        # Calculate overall quality score from individual metrics
        metrics = [
            values.get('extraction_accuracy', 0),
            values.get('transcription_accuracy', 0),
            values.get('ocr_accuracy', 0),
            values.get('embedding_quality', 0)
        ]
        return sum(m for m in metrics if m is not None) / len([m for m in metrics if m is not None])

class QualityMetrics(BaseModel):
    """Quality metrics update message"""
    type: MessageType = MessageType.QUALITY_METRICS
    data: QualityMetricsData
    metadata: Optional[MessageMetadata] = None
    priority: PriorityLevel = PriorityLevel.NORMAL

class ErrorData(BaseModel):
    """Error occurrence data"""
    document_id: Optional[str] = None
    job_execution_id: Optional[str] = None
    stage_execution_id: Optional[str] = None

    # Error information
    error_type: str
    error_code: str
    error_message: str
    error_details: Optional[Dict[str, Any]] = None

    # Context information
    stage: Optional[ProcessingStage] = None
    step: Optional[str] = None
    operation: Optional[str] = None

    # Error severity and impact
    severity: SeverityLevel
    is_recoverable: bool = True
    requires_user_action: bool = False
    estimated_recovery_time_seconds: Optional[int] = None

    # Retry information
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[datetime] = None

    # Related errors
    related_error_ids: List[str] = Field(default_factory=list)
    caused_by: Optional[str] = None

class ErrorOccurred(BaseModel):
    """Error occurrence message"""
    type: MessageType = MessageType.ERROR_OCCURRED
    data: ErrorData
    metadata: Optional[MessageMetadata] = None
    priority: PriorityLevel = PriorityLevel.HIGH

class SystemNotificationData(BaseModel):
    """System notification data"""
    notification_type: str = Field(..., description="Type of notification")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Detailed notification message")

    # Severity and urgency
    severity: SeverityLevel = SeverityLevel.INFO
    priority: PriorityLevel = PriorityLevel.NORMAL

    # Scope and impact
    affected_systems: List[str] = Field(default_factory=list)
    affected_organizations: List[str] = Field(default_factory=list)
    affected_users: List[str] = Field(default_factory=list)

    # Action information
    action_required: bool = False
    action_url: Optional[str] = None
    action_button_text: Optional[str] = None
    auto_dismiss: bool = True
    dismiss_after_seconds: Optional[int] = None

    # Timing
    scheduled_for: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    estimated_resolution: Optional[datetime] = None

    # Additional metadata
    notification_metadata: Dict[str, Any] = Field(default_factory=dict)

class SystemNotification(BaseModel):
    """System notification message"""
    type: MessageType = MessageType.SYSTEM_NOTIFICATION
    data: SystemNotificationData
    metadata: Optional[MessageMetadata] = None
    broadcast_all: bool = False

class BatchUpdateData(BaseModel):
    """Batch operation update data"""
    batch_id: str
    operation_type: str  # upload, delete, reprocess, etc.

    # Batch statistics
    total_items: int
    completed_items: int
    failed_items: int
    processing_items: int

    # Progress information
    progress_percentage: float = Field(..., ge=0, le=100)
    estimated_completion: Optional[datetime] = None

    # Performance metrics
    average_processing_time_ms: Optional[float] = None
    success_rate: float = Field(..., ge=0, le=1)

    # Sample updates (for large batches)
    sample_document_updates: List[DocumentStatusData] = Field(default_factory=list, max_items=10)

    # Batch metadata
    batch_metadata: Dict[str, Any] = Field(default_factory=dict)

class BatchUpdate(BaseModel):
    """Batch operation update message"""
    type: MessageType = MessageType.BATCH_UPDATE
    data: BatchUpdateData
    metadata: Optional[MessageMetadata] = None
    priority: PriorityLevel = PriorityLevel.NORMAL

class QueueStatusData(BaseModel):
    """Queue status information"""
    queue_type: str  # processing, embedding, indexing, etc.

    # Queue statistics
    queue_length: int
    processing_rate: Optional[float] = None
    average_wait_time_seconds: Optional[float] = None

    # System resources
    available_workers: int
    active_workers: int
    max_workers: int

    # Performance metrics
    throughput_per_minute: Optional[float] = None
    average_processing_time_seconds: Optional[float] = None

    # Priority breakdown
    priority_breakdown: Dict[str, int] = Field(default_factory=dict)

    # Estimated times
    estimated_processing_time_for_new_items: Optional[int] = None

class QueueStatus(BaseModel):
    """Queue status update message"""
    type: MessageType = MessageType.QUEUE_STATUS
    data: QueueStatusData
    metadata: Optional[MessageMetadata] = None
    priority: PriorityLevel = PriorityLevel.LOW

# Union type for all WebSocket messages
WebSocketMessage = Union[
    DocumentStatusUpdate,
    ProcessingProgress,
    StageComplete,
    QualityMetrics,
    ErrorOccurred,
    SystemNotification,
    BatchUpdate,
    QueueStatus
]

class MessageFactory:
    """Factory for creating standardized WebSocket messages"""

    @staticmethod
    def create_document_status_update(
        document_id: str,
        processing_status: ProcessingStage,
        current_stage: ProcessingStage,
        progress_percentage: float,
        document_type: DocumentType,
        file_size_bytes: int,
        file_name: str,
        **kwargs
    ) -> DocumentStatusUpdate:
        """Create document status update message"""
        data = DocumentStatusData(
            document_id=document_id,
            processing_status=processing_status,
            current_stage=current_stage,
            progress_percentage=progress_percentage,
            document_type=document_type,
            file_size_bytes=file_size_bytes,
            file_name=file_name,
            **kwargs
        )
        return DocumentStatusUpdate(data=data)

    @staticmethod
    def create_processing_progress(
        document_id: str,
        stage: ProcessingStage,
        step: str,
        progress_percentage: float,
        items_processed: int,
        total_items: int,
        **kwargs
    ) -> ProcessingProgress:
        """Create processing progress message"""
        data = ProcessingProgressData(
            document_id=document_id,
            stage=stage,
            step=step,
            progress_percentage=progress_percentage,
            items_processed=items_processed,
            total_items=total_items,
            **kwargs
        )
        return ProcessingProgress(data=data)

    @staticmethod
    def create_error_message(
        error_message: str,
        error_type: str,
        severity: SeverityLevel = SeverityLevel.ERROR,
        **kwargs
    ) -> ErrorOccurred:
        """Create error message"""
        data = ErrorData(
            error_message=error_message,
            error_type=error_type,
            severity=severity,
            **kwargs
        )
        return ErrorOccurred(data=data)

    @staticmethod
    def create_quality_metrics(
        document_id: str,
        processing_complete: bool,
        **metrics
    ) -> QualityMetrics:
        """Create quality metrics message"""
        data = QualityMetricsData(
            document_id=document_id,
            processing_complete=processing_complete,
            **metrics
        )
        return QualityMetrics(data=data)

    @staticmethod
    def create_system_notification(
        title: str,
        message: str,
        notification_type: str,
        severity: SeverityLevel = SeverityLevel.INFO,
        **kwargs
    ) -> SystemNotification:
        """Create system notification message"""
        data = SystemNotificationData(
            title=title,
            message=message,
            notification_type=notification_type,
            severity=severity,
            **kwargs
        )
        return SystemNotification(data=data)