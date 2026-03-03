"""
WebSocket Status Update models for real-time processing updates and notifications
"""

import uuid
from datetime import datetime
from datetime import timezone as dt_timezone
from enum import Enum as PyEnum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .base import GUID, BaseModel


class ConnectionStatus(PyEnum):
    """WebSocket connection status"""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    TIMEOUT = "timeout"


class UpdateType(PyEnum):
    """Types of real-time updates"""

    DOCUMENT_PROCESSING = "document_processing"
    JOB_STATUS = "job_status"
    SYSTEM_STATUS = "system_status"
    USER_NOTIFICATION = "user_notification"
    QUOTA_ALERT = "quota_alert"
    EVALUATION_RESULT = "evaluation_result"
    SEARCH_PROGRESS = "search_progress"
    BATCH_OPERATION = "batch_operation"


class Priority(PyEnum):
    """Update priority levels"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class WebSocketConnection(BaseModel):
    """Active WebSocket connection tracking"""

    __tablename__ = "websocket_connections"

    # Connection identification
    connection_id = Column(String(255), nullable=False, unique=True, index=True)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(
        GUID(), ForeignKey("organizations.id"), nullable=False, index=True
    )
    session_id = Column(String(255), nullable=True, index=True)

    # Connection details
    connection_status = Column(
        Enum(ConnectionStatus), nullable=False, default=ConnectionStatus.CONNECTING
    )
    connected_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    last_heartbeat = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    disconnected_at = Column(DateTime(timezone=True), nullable=True)

    # Client information
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    client_type = Column(String(50), nullable=True)  # web, mobile, desktop
    client_version = Column(String(50), nullable=True)

    # Connection configuration
    subscription_channels = Column(JSON, nullable=True)  # Subscribed channels/topics
    update_filter = Column(JSON, nullable=True)  # Filter for received updates
    max_message_size = Column(
        Integer, default=1024 * 1024, nullable=False
    )  # 1MB default
    heartbeat_interval = Column(Integer, default=30, nullable=False)  # seconds

    # Connection metrics
    messages_sent = Column(Integer, default=0, nullable=False)
    messages_received = Column(Integer, default=0, nullable=False)
    bytes_sent = Column(Integer, default=0, nullable=False)
    bytes_received = Column(Integer, default=0, nullable=False)
    connection_duration_seconds = Column(Integer, nullable=True)
    average_latency_ms = Column(Float, nullable=True)

    # Error tracking
    error_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    reconnect_attempts = Column(Integer, default=0, nullable=False)
    max_reconnect_attempts = Column(Integer, default=5, nullable=False)

    # Relationships
    user = relationship("User")
    organization = relationship("Organization")
    status_updates = relationship(
        "StatusUpdate", back_populates="connection", cascade="all, delete-orphan"
    )
    connection_events = relationship(
        "ConnectionEvent", back_populates="connection", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_ws_connections_user_status", "user_id", "connection_status"),
        Index("idx_ws_connections_heartbeat", "last_heartbeat"),
        Index("idx_ws_connections_org", "organization_id", "connected_at"),
    )

    def __repr__(self):
        return f"<WebSocketConnection(id={self.connection_id}, user_id={self.user_id}, status={self.connection_status.value})>"

    @property
    def is_connected(self) -> bool:
        """Check if connection is active"""
        return self.connection_status == ConnectionStatus.CONNECTED

    @property
    def is_stale(self) -> bool:
        """Check if connection is stale (no recent heartbeat)"""
        heartbeat_timeout = dt_timezone.utc.localize(
            datetime.utcnow()
        ) - dt_timezone.timedelta(minutes=5)
        return self.last_heartbeat < heartbeat_timeout

    @property
    def can_reconnect(self) -> bool:
        """Check if connection can attempt reconnection"""
        return self.reconnect_attempts < self.max_reconnect_attempts

    def update_heartbeat(self):
        """Update connection heartbeat"""
        self.last_heartbeat = datetime.utcnow()
        if self.connected_at:
            self.connection_duration_seconds = int(
                (self.last_heartbeat - self.connected_at).total_seconds()
            )

    def record_message_sent(self, size_bytes: int):
        """Record sent message statistics"""
        self.messages_sent += 1
        self.bytes_sent += size_bytes

    def record_message_received(self, size_bytes: int):
        """Record received message statistics"""
        self.messages_received += 1
        self.bytes_received += size_bytes

    def record_error(self, error_message: str):
        """Record connection error"""
        self.error_count += 1
        self.last_error = error_message
        self.last_error_at = datetime.utcnow()

    def increment_reconnect_attempts(self):
        """Increment reconnection attempt counter"""
        self.reconnect_attempts += 1

    def reset_reconnect_attempts(self):
        """Reset reconnection attempt counter"""
        self.reconnect_attempts = 0

    def subscribe_to_channel(self, channel: str):
        """Subscribe to a notification channel"""
        if not self.subscription_channels:
            self.subscription_channels = []
        if channel not in self.subscription_channels:
            self.subscription_channels.append(channel)

    def unsubscribe_from_channel(self, channel: str):
        """Unsubscribe from a notification channel"""
        if self.subscription_channels and channel in self.subscription_channels:
            self.subscription_channels.remove(channel)

    def is_subscribed_to_channel(self, channel: str) -> bool:
        """Check if subscribed to a channel"""
        return self.subscription_channels and channel in self.subscription_channels

    def disconnect(self, reason: str = None):
        """Mark connection as disconnected"""
        self.connection_status = ConnectionStatus.DISCONNECTED
        self.disconnected_at = datetime.utcnow()
        if reason:
            self.last_error = reason
            self.last_error_at = self.disconnected_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = super().to_dict()

        # Convert enum values
        data["connection_status"] = (
            self.connection_status.value if self.connection_status else None
        )

        # Add computed properties
        data.update(
            {
                "is_connected": self.is_connected,
                "is_stale": self.is_stale,
                "can_reconnect": self.can_reconnect,
            }
        )

        # Remove sensitive information
        data.pop("ip_address", None)
        data.pop("user_agent", None)

        return data

    @classmethod
    def get_active_connections(
        cls,
        user_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
    ) -> List:
        """Get active WebSocket connections"""
        query = cls.query.filter(
            cls.connection_status == ConnectionStatus.CONNECTED, cls.is_deleted == False
        )

        if user_id:
            query = query.filter(cls.user_id == user_id)
        if organization_id:
            query = query.filter(cls.organization_id == organization_id)

        return query.all()

    @classmethod
    def get_stale_connections(cls, timeout_minutes: int = 5) -> List:
        """Get stale connections for cleanup"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        return cls.query.filter(
            cls.last_heartbeat < cutoff_time,
            cls.connection_status == ConnectionStatus.CONNECTED,
            cls.is_deleted == False,
        ).all()


class StatusUpdate(BaseModel):
    """Real-time status update messages"""

    __tablename__ = "status_updates"

    # Update identification
    update_id = Column(String(255), nullable=False, unique=True, index=True)
    connection_id = Column(
        GUID(), ForeignKey("websocket_connections.id"), nullable=False, index=True
    )
    update_type = Column(Enum(UpdateType), nullable=False, index=True)
    priority = Column(
        Enum(Priority), nullable=False, default=Priority.NORMAL, index=True
    )

    # Update content
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    update_data = Column(JSON, nullable=True)  # Update-specific data
    progress_percentage = Column(Float, nullable=True)

    # Targeting
    target_users = Column(JSON, nullable=True)  # Specific users to receive update
    target_organizations = Column(JSON, nullable=True)  # Specific organizations
    broadcast_channel = Column(String(100), nullable=True)  # Channel for broadcasting

    # Delivery tracking
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    # Delivery status
    delivery_status = Column(
        String(50), nullable=False, default="pending"
    )  # pending, sent, delivered, read, acknowledged, failed
    delivery_attempts = Column(Integer, default=0, nullable=False)
    max_delivery_attempts = Column(Integer, default=3, nullable=False)
    delivery_error = Column(Text, nullable=True)

    # Update metadata
    expires_at = Column(DateTime(timezone=True), nullable=True)
    requires_acknowledgment = Column(Boolean, default=False, nullable=False)
    is_dismissible = Column(Boolean, default=True, nullable=False)
    action_required = Column(Boolean, default=False, nullable=False)
    action_url = Column(String(500), nullable=True)

    # User interaction
    was_clicked = Column(Boolean, default=False, nullable=False)
    clicked_at = Column(DateTime(timezone=True), nullable=True)
    user_response = Column(JSON, nullable=True)  # User's response to update

    # Relationships
    connection = relationship("src.models.websocket_status.WebSocketConnection", back_populates="status_updates")

    # Indexes
    __table_args__ = (
        Index("idx_status_updates_connection_type", "connection_id", "update_type"),
        Index("idx_status_updates_priority_created", "priority", "created_at"),
        Index("idx_status_updates_status", "delivery_status"),
        Index("idx_status_updates_expires", "expires_at"),
    )

    def __repr__(self):
        return f"<StatusUpdate(id={self.update_id}, type={self.update_type.value}, status={self.delivery_status})>"

    @property
    def is_expired(self) -> bool:
        """Check if update has expired"""
        return self.expires_at and datetime.utcnow() > self.expires_at

    @property
    def can_retry_delivery(self) -> bool:
        """Check if delivery can be retried"""
        return (
            self.delivery_status in ["pending", "failed"]
            and self.delivery_attempts < self.max_delivery_attempts
            and not self.is_expired
        )

    @property
    def is_pending_delivery(self) -> bool:
        """Check if update is pending delivery"""
        return self.delivery_status in ["pending", "sent"] and not self.is_expired

    def mark_sent(self):
        """Mark update as sent"""
        self.delivery_status = "sent"
        self.sent_at = datetime.utcnow()
        self.delivery_attempts += 1

    def mark_delivered(self):
        """Mark update as delivered"""
        self.delivery_status = "delivered"
        self.delivered_at = datetime.utcnow()

    def mark_read(self):
        """Mark update as read"""
        self.delivery_status = "read"
        self.read_at = datetime.utcnow()

    def mark_acknowledged(self, user_response: Dict[str, Any] = None):
        """Mark update as acknowledged"""
        self.delivery_status = "acknowledged"
        self.acknowledged_at = datetime.utcnow()
        if user_response:
            self.user_response = user_response

    def mark_failed(self, error_message: str):
        """Mark update as failed"""
        self.delivery_status = "failed"
        self.delivery_attempts += 1
        self.delivery_error = error_message

    def record_click(self):
        """Record that user clicked on update"""
        self.was_clicked = True
        self.clicked_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = super().to_dict()

        # Convert enum values
        data.update(
            {
                "update_type": self.update_type.value if self.update_type else None,
                "priority": self.priority.value if self.priority else None,
            }
        )

        # Add computed properties
        data.update(
            {
                "is_expired": self.is_expired,
                "can_retry_delivery": self.can_retry_delivery,
                "is_pending_delivery": self.is_pending_delivery,
            }
        )

        # Remove sensitive tracking information
        data.pop("delivery_error", None)
        data.pop("target_users", None)
        data.pop("target_organizations", None)

        return data

    @classmethod
    def get_pending_updates(cls, connection_id: Optional[uuid.UUID] = None) -> List:
        """Get updates pending delivery"""
        query = cls.query.filter(
            cls.delivery_status.in_(["pending", "sent"]), cls.is_deleted == False
        ).order_by(cls.priority.desc(), cls.created_at.asc())

        if connection_id:
            query = query.filter(cls.connection_id == connection_id)

        return query.all()

    @classmethod
    def get_expired_updates(cls) -> List:
        """Get expired updates for cleanup"""
        return cls.query.filter(
            cls.expires_at < datetime.utcnow(),
            cls.delivery_status != "acknowledged",
            cls.is_deleted == False,
        ).all()


class ConnectionEvent(BaseModel):
    """WebSocket connection lifecycle events"""

    __tablename__ = "connection_events"

    connection_id = Column(
        GUID(), ForeignKey("websocket_connections.id"), nullable=False
    )

    # Event details
    event_type = Column(
        String(50), nullable=False
    )  # connect, disconnect, error, heartbeat, message
    event_data = Column(JSON, nullable=True)  # Event-specific data
    event_timestamp = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Event context
    session_id = Column(String(255), nullable=True)
    client_info = Column(JSON, nullable=True)  # Client information at event time
    server_info = Column(JSON, nullable=True)  # Server information at event time

    # Performance metrics
    latency_ms = Column(Float, nullable=True)
    message_size_bytes = Column(Integer, nullable=True)
    processing_time_ms = Column(Float, nullable=True)

    # Error information
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    error_stack = Column(Text, nullable=True)

    # Relationships
    connection = relationship("src.models.websocket_status.WebSocketConnection", back_populates="connection_events")

    def __repr__(self):
        return f"<ConnectionEvent(type={self.event_type}, connection_id={self.connection_id})>"

    @classmethod
    def get_recent_events(cls, connection_id: uuid.UUID, limit: int = 50) -> List:
        """Get recent events for a connection"""
        return (
            cls.query.filter(
                cls.connection_id == connection_id, cls.is_deleted == False
            )
            .order_by(cls.event_timestamp.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def get_error_events(
        cls, organization_id: Optional[uuid.UUID] = None, hours: int = 24
    ) -> List:
        """Get error events within time window"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        query = cls.query.filter(
            cls.event_type == "error",
            cls.event_timestamp >= cutoff_time,
            cls.is_deleted == False,
        ).order_by(cls.event_timestamp.desc())

        if organization_id:
            query = query.join(WebSocketConnection).filter(
                WebSocketConnection.organization_id == organization_id
            )

        return query.all()


class NotificationTemplate(BaseModel):
    """Templates for different types of notifications"""

    __tablename__ = "notification_templates"

    # Template identification
    template_name = Column(String(100), nullable=False, unique=True, index=True)
    update_type = Column(Enum(UpdateType), nullable=False)
    priority = Column(Enum(Priority), nullable=False, default=Priority.NORMAL)

    # Template content
    title_template = Column(String(255), nullable=False)
    message_template = Column(Text, nullable=True)
    data_schema = Column(JSON, nullable=True)  # Expected data structure

    # Template configuration
    default_ttl_minutes = Column(Integer, nullable=True)  # Time to live
    requires_acknowledgment = Column(Boolean, default=False, nullable=False)
    is_dismissible = Column(Boolean, default=True, nullable=False)
    action_required = Column(Boolean, default=False, nullable=False)
    default_action_url = Column(String(500), nullable=True)

    # Localization
    supported_languages = Column(
        JSON, nullable=True
    )  # List of supported language codes
    translations = Column(JSON, nullable=True)  # Translated templates

    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    def render_template(
        self, data: Dict[str, Any], language: str = "en"
    ) -> Dict[str, str]:
        """Render template with provided data"""
        # Simple template rendering - in production, use a proper templating engine
        title = self.title_template
        message = self.message_template or ""

        # Apply translations if available
        if self.translations and language != "en" and language in self.translations:
            translations = self.translations[language]
            title = translations.get("title", title)
            message = translations.get("message", message)

        # Replace template variables
        for key, value in data.items():
            placeholder = f"{{{key}}}"
            title = title.replace(placeholder, str(value))
            message = message.replace(placeholder, str(value))

        return {"title": title, "message": message}

    def record_usage(self):
        """Record template usage"""
        self.usage_count += 1
        self.last_used_at = datetime.utcnow()

    @classmethod
    def get_template_by_name(
        cls, template_name: str
    ) -> Optional["NotificationTemplate"]:
        """Get template by name"""
        return cls.query.filter(
            cls.template_name == template_name, cls.is_deleted == False
        ).first()
