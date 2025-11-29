"""
WebSocket message schemas and format specifications
Standardized message formats for real-time document processing updates
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum
import uuid

# Base message schemas

class BaseMessage(BaseModel):
    """Base WebSocket message schema"""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = Field(..., description="Message type identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    organization_id: Optional[str] = None

# Connection management messages

class ConnectMessage(BaseMessage):
    """Connection establishment message"""
    type: str = "connect"
    connection_id: str
    status: str
    metadata: Optional[Dict[str, Any]] = None

class DisconnectMessage(BaseMessage):
    """Connection termination message"""
    type: str = "disconnect"
    reason: str
    code: Optional[int] = None

class PingMessage(BaseMessage):
    """Ping message for connection health check"""
    type: str = "ping"
    sequence: Optional[int] = None

class PongMessage(BaseMessage):
    """Pong response message"""
    type: str = "pong"
    sequence: Optional[int] = None
    ping_timestamp: Optional[datetime] = None

class ErrorMessage(BaseMessage):
    """Error message"""
    type: str = "error"
    error_code: str
    error_message: str
    details: Optional[Dict[str, Any]] = None
    retry_after: Optional[float] = None  # Seconds

# Subscription management messages

class SubscribeMessage(BaseMessage):
    """Subscription request message"""
    type: str = "subscribe"
    channel: str
    filters: Optional[Dict[str, Any]] = None

class UnsubscribeMessage(BaseMessage):
    """Unsubscription request message"""
    type: str = "unsubscribe"
    channel: str

class SubscriptionConfirmedMessage(BaseMessage):
    """Subscription confirmation message"""
    type: str = "subscription_confirmed"
    channel: str
    subscription_id: Optional[str] = None

# Document processing messages

class DocumentMetadata(BaseModel):
    """Document metadata schema"""
    document_id: str
    title: str
    filename: str
    file_type: str
    file_size_bytes: int
    mime_type: str
    organization_id: str
    uploaded_by_user_id: str
    created_at: datetime
    tags: Optional[List[str]] = None

class ProcessingStep(BaseModel):
    """Processing step information"""
    step_name: str
    step_id: str
    status: str  # pending, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    progress_percent: Optional[float] = Field(None, ge=0, le=100)
    details: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class DocumentStatusUpdateMessage(BaseMessage):
    """Document processing status update"""
    type: str = "doc_status_update"
    document_id: str
    status: str  # queued, processing, completed, failed
    previous_status: Optional[str] = None
    metadata: DocumentMetadata
    processing_steps: Optional[List[ProcessingStep]] = None
    overall_progress: Optional[float] = Field(None, ge=0, le=100)

class DocumentProcessingStartMessage(BaseMessage):
    """Document processing started"""
    type: str = "doc_processing_start"
    document_id: str
    metadata: DocumentMetadata
    processing_pipeline: str
    estimated_duration_seconds: Optional[float] = None
    steps: List[ProcessingStep]

class DocumentProcessingProgressMessage(BaseMessage):
    """Document processing progress update"""
    type: str = "doc_processing_progress"
    document_id: str
    current_step: ProcessingStep
    overall_progress: float = Field(..., ge=0, le=100)
    estimated_remaining_seconds: Optional[float] = None
    throughput_stats: Optional[Dict[str, Any]] = None

class DocumentProcessingCompleteMessage(BaseMessage):
    """Document processing completed"""
    type: str = "doc_processing_complete"
    document_id: str
    metadata: DocumentMetadata
    processing_summary: Dict[str, Any]
    final_status: str
    total_duration_seconds: float
    steps_completed: List[ProcessingStep]
    search_indexed: bool = False
    vector_embedded: bool = False
    quality_score: Optional[float] = Field(None, ge=0, le=100)

class DocumentProcessingErrorMessage(BaseMessage):
    """Document processing failed"""
    type: str = "doc_processing_error"
    document_id: str
    metadata: DocumentMetadata
    error_code: str
    error_message: str
    error_details: Optional[Dict[str, Any]] = None
    failed_step: Optional[ProcessingStep] = None
    retry_attempt: int = 0
    max_retries: int = 3
    can_retry: bool = False
    retry_after_seconds: Optional[float] = None

# System notification messages

class SystemAnnouncementMessage(BaseMessage):
    """System-wide announcement"""
    type: str = "system_announcement"
    announcement_type: str  # maintenance, outage, feature, security
    title: str
    message: str
    severity: str  # info, warning, error, critical
    action_required: bool = False
    action_url: Optional[str] = None
    valid_until: Optional[datetime] = None

class UserNotificationMessage(BaseMessage):
    """User-specific notification"""
    type: str = "user_notification"
    notification_id: str
    category: str  # info, success, warning, error
    title: str
    message: str
    action_url: Optional[str] = None
    read: bool = False
    expires_at: Optional[datetime] = None

class OrganizationNotificationMessage(BaseMessage):
    """Organization-specific notification"""
    type: str = "org_notification"
    notification_id: str
    category: str
    title: str
    message: str
    target_roles: Optional[List[str]] = None
    action_url: Optional[str] = None
    expires_at: Optional[datetime] = None

# Batch operation messages

class BatchOperationMessage(BaseMessage):
    """Batch operation status update"""
    type: str = "batch_operation_update"
    batch_id: str
    operation_type: str  # upload, delete, reprocess
    status: str  # pending, running, completed, failed, cancelled
    total_items: int
    processed_items: int
    failed_items: int
    progress_percent: float = Field(..., ge=0, le=100)
    estimated_remaining_seconds: Optional[float] = None
    details: Optional[Dict[str, Any]] = None

class BatchItemUpdateMessage(BaseMessage):
    """Individual item status within a batch operation"""
    type: str = "batch_item_update"
    batch_id: str
    document_id: str
    item_status: str
    item_result: Optional[Dict[str, Any]] = None
    item_error: Optional[str] = None

# Real-time query messages

class QueryStatusMessage(BaseMessage):
    """Query processing status"""
    type: str = "query_status_update"
    query_id: str
    status: str  # queued, processing, completed, failed
    query_type: str
    progress_percent: float = Field(None, ge=0, le=100)
    processing_stages: Optional[List[ProcessingStep]] = None
    estimated_remaining_seconds: Optional[float] = None

class QueryResultMessage(BaseMessage):
    """Query result notification"""
    type: str = "query_result"
    query_id: str
    result_count: int
    result_preview: Optional[List[Dict[str, Any]]] = None
    total_processing_time_ms: float
    cache_hit: bool = False

# Performance and monitoring messages

class PerformanceMetricsMessage(BaseMessage):
    """System performance metrics"""
    type: str = "performance_metrics"
    metrics: Dict[str, Any] = Field(..., description="Key-value metric pairs")
    collection_time: datetime = Field(default_factory=datetime.utcnow)
    service_name: str
    instance_id: Optional[str] = None

class HealthCheckMessage(BaseMessage):
    """Service health check"""
    type: str = "health_check"
    service_name: str
    status: str  # healthy, degraded, unhealthy
    checks: Dict[str, Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# Message routing and filtering

class MessageFilter(BaseModel):
    """Message filter specification"""
    user_ids: Optional[List[str]] = None
    organization_ids: Optional[List[str]] = None
    document_types: Optional[List[str]] = None
    processing_statuses: Optional[List[str]] = None
    severity_levels: Optional[List[str]] = None
    custom_filters: Optional[Dict[str, Any]] = None

class RoutingRule(BaseModel):
    """Message routing rule"""
    rule_id: str
    name: str
    description: Optional[str] = None
    filter: MessageFilter
    actions: List[Dict[str, Any]]
    priority: int = Field(default=0, ge=0)
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Message validation and transformation

class MessageValidator:
    """Message validation utilities"""

    @staticmethod
    def validate_message_type(message: Dict[str, Any]) -> bool:
        """Validate message type and structure"""
        required_fields = ['type', 'timestamp']
        return all(field in message for field in required_fields)

    @staticmethod
    def sanitize_message(message: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize message content"""
        # Remove any potentially sensitive data
        sensitive_keys = ['password', 'token', 'secret', 'key']
        sanitized = message.copy()

        for key, value in sanitized.items():
            if isinstance(value, dict):
                sanitized[key] = MessageValidator.sanitize_message(value)
            elif any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = '[REDACTED]'

        return sanitized

    @staticmethod
    def compress_message(message: Dict[str, Any]) -> Dict[str, Any]:
        """Compress message for bandwidth optimization"""
        # Remove None values and empty collections
        compressed = {}
        for key, value in message.items():
            if value is not None and value != [] and value != {}:
                compressed[key] = value
        return compressed

# Message serializers

class MessageSerializer:
    """Message serialization utilities"""

    @staticmethod
    def serialize_message(message: BaseModel) -> str:
        """Serialize message to JSON string"""
        return message.json(exclude_none=True)

    @staticmethod
    def deserialize_message(message_data: str, message_type: str) -> BaseModel:
        """Deserialize message from JSON string"""
        # Map message types to their corresponding models
        type_mapping = {
            'connect': ConnectMessage,
            'disconnect': DisconnectMessage,
            'ping': PingMessage,
            'pong': PongMessage,
            'error': ErrorMessage,
            'subscribe': SubscribeMessage,
            'unsubscribe': UnsubscribeMessage,
            'subscription_confirmed': SubscriptionConfirmedMessage,
            'doc_status_update': DocumentStatusUpdateMessage,
            'doc_processing_start': DocumentProcessingStartMessage,
            'doc_processing_progress': DocumentProcessingProgressMessage,
            'doc_processing_complete': DocumentProcessingCompleteMessage,
            'doc_processing_error': DocumentProcessingErrorMessage,
            'system_announcement': SystemAnnouncementMessage,
            'user_notification': UserNotificationMessage,
            'org_notification': OrganizationNotificationMessage,
            'batch_operation_update': BatchOperationMessage,
            'batch_item_update': BatchItemUpdateMessage,
            'query_status_update': QueryStatusMessage,
            'query_result': QueryResultMessage,
            'performance_metrics': PerformanceMetricsMessage,
            'health_check': HealthCheckMessage,
        }

        message_class = type_mapping.get(message_type)
        if not message_class:
            raise ValueError(f"Unknown message type: {message_type}")

        return message_class.parse_raw(message_data)

# Message templates

class MessageTemplates:
    """Common message templates"""

    @staticmethod
    def document_queued(document_id: str, metadata: DocumentMetadata) -> DocumentStatusUpdateMessage:
        """Template for document queued message"""
        return DocumentStatusUpdateMessage(
            document_id=document_id,
            status="queued",
            metadata=metadata,
            overall_progress=0.0
        )

    @staticmethod
    def document_processing_started(document_id: str, metadata: DocumentMetadata, steps: List[ProcessingStep]) -> DocumentProcessingStartMessage:
        """Template for document processing started message"""
        return DocumentProcessingStartMessage(
            document_id=document_id,
            metadata=metadata,
            processing_pipeline="standard",
            steps=steps
        )

    @staticmethod
    def document_progress_update(document_id: str, current_step: ProcessingStep, overall_progress: float) -> DocumentProcessingProgressMessage:
        """Template for document progress update message"""
        return DocumentProcessingProgressMessage(
            document_id=document_id,
            current_step=current_step,
            overall_progress=overall_progress
        )

    @staticmethod
    def document_completed(document_id: str, metadata: DocumentMetadata, summary: Dict[str, Any], duration: float) -> DocumentProcessingCompleteMessage:
        """Template for document completion message"""
        return DocumentProcessingCompleteMessage(
            document_id=document_id,
            metadata=metadata,
            processing_summary=summary,
            final_status="completed",
            total_duration_seconds=duration,
            steps_completed=[],
            search_indexed=True,
            vector_embedded=True
        )

    @staticmethod
    def document_error(document_id: str, metadata: DocumentMetadata, error_code: str, error_message: str) -> DocumentProcessingErrorMessage:
        """Template for document error message"""
        return DocumentProcessingErrorMessage(
            document_id=document_id,
            metadata=metadata,
            error_code=error_code,
            error_message=error_message,
            retry_attempt=0,
            max_retries=3,
            can_retry=error_code in ['TEMPORARY_ERROR', 'TIMEOUT', 'RATE_LIMIT']
        )

    @staticmethod
    def system_maintenance_notification(title: str, message: str, start_time: datetime, duration_minutes: int) -> SystemAnnouncementMessage:
        """Template for system maintenance notification"""
        return SystemAnnouncementMessage(
            announcement_type="maintenance",
            title=title,
            message=message,
            severity="warning",
            action_required=False,
            valid_until=start_time
        )

    @staticmethod
    def user_file_upload_success(document_id: str, filename: str) -> UserNotificationMessage:
        """Template for successful file upload notification"""
        return UserNotificationMessage(
            notification_id=str(uuid.uuid4()),
            category="success",
            title="File Upload Successful",
            message=f"Your file '{filename}' has been uploaded and is being processed.",
            read=False
        )