"""
Real-time analytics models for WebSocket streaming and live metrics
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, validator
from sqlalchemy import JSON, BigInteger, Boolean, Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from ..base import GUID
from ..base import BaseModel as SQLBaseModel


class SubscriptionType(str, Enum):
    """Types of real-time subscriptions"""

    METRICS = "metrics"
    EVENTS = "events"
    KPI = "kpi"
    DASHBOARD = "dashboard"
    GRAPH = "graph"
    SEARCH = "search"
    USER_ACTIVITY = "user_activity"
    SYSTEM_HEALTH = "system_health"


class WebSocketMessageType(str, Enum):
    """WebSocket message types"""

    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    DATA = "data"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
    AUTH = "auth"
    HEARTBEAT = "heartbeat"


class RealtimeSubscription(SQLBaseModel):
    """Real-time subscription model"""

    __tablename__ = "realtime_subscriptions"

    # User and session
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    websocket_id = Column(String(255), nullable=False, index=True)

    # Subscription configuration
    subscription_type = Column(SQLEnum(SubscriptionType), nullable=False, index=True)
    channel = Column(
        String(255), nullable=False, index=True
    )  # Subscription channel/topic
    filters = Column(JSON, nullable=True)  # Subscription filters

    # Configuration
    batch_size = Column(Integer, default=100, nullable=False)
    update_interval = Column(Integer, default=1000, nullable=False)  # milliseconds
    max_buffer_size = Column(Integer, default=1000, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    last_activity = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    message_count = Column(Integer, default=0, nullable=False)
    error_count = Column(Integer, default=0, nullable=False)

    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True)
    auto_renew = Column(Boolean, default=True, nullable=False)


class LiveMetric(SQLBaseModel):
    """Live metric data for real-time updates"""

    __tablename__ = "live_metrics"

    # Metric identification
    metric_id = Column(String(255), nullable=False, index=True)
    metric_name = Column(String(255), nullable=False, index=True)
    channel = Column(String(255), nullable=False, index=True)

    # Current value
    current_value = Column(Float, nullable=False)
    previous_value = Column(Float, nullable=True)
    change_percentage = Column(Float, nullable=True)

    # Time series data
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    time_window = Column(String(50), nullable=False)  # 1m, 5m, 1h, etc.

    # Aggregation metadata
    aggregation_type = Column(String(50), nullable=False)
    sample_count = Column(Integer, nullable=False)
    data_quality_score = Column(Float, nullable=True)

    # Dimensions and filters
    dimensions = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)

    # Status
    is_anomaly = Column(Boolean, default=False, nullable=False)
    alert_threshold_min = Column(Float, nullable=True)
    alert_threshold_max = Column(Float, nullable=True)

    # Metadata
    source = Column(String(255), nullable=True)  # Data source
    confidence = Column(Float, nullable=True)  # Confidence in the value


class EventStream(SQLBaseModel):
    """Event stream for real-time event processing"""

    __tablename__ = "event_streams"

    # Event identification
    event_type = Column(String(100), nullable=False, index=True)
    event_name = Column(String(255), nullable=False, index=True)
    source = Column(String(255), nullable=False, index=True)

    # Event data
    payload = Column(JSON, nullable=False)
    event_metadata = Column(
        JSON, nullable=True
    )  # Renamed from 'metadata' to avoid SQLAlchemy conflict

    # Context
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(255), nullable=True, index=True)
    request_id = Column(String(255), nullable=True, index=True)
    correlation_id = Column(String(255), nullable=True, index=True)

    # Processing
    processed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    processing_latency_ms = Column(Integer, nullable=True)
    status = Column(String(50), default="processed", nullable=False)
    error_message = Column(Text, nullable=True)

    # Routing
    routing_key = Column(String(255), nullable=True, index=True)
    channels = Column(JSON, nullable=True)  # Channels to publish to


class WebSocketConnection(SQLBaseModel):
    """WebSocket connection tracking"""

    __tablename__ = "websocket_connections"
    __table_args__ = {"extend_existing": True}

    # Connection identification
    connection_id = Column(String(255), nullable=False, unique=True, index=True)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)

    # Connection details
    client_ip = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=True)
    origin = Column(String(500), nullable=True)

    # Status
    is_connected = Column(Boolean, default=True, nullable=False)
    connected_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    disconnected_at = Column(DateTime(timezone=True), nullable=True)
    last_ping = Column(DateTime(timezone=True), nullable=True)
    last_pong = Column(DateTime(timezone=True), nullable=True)

    # Statistics
    messages_sent = Column(Integer, default=0, nullable=False)
    messages_received = Column(Integer, default=0, nullable=False)
    bytes_sent = Column(BigInteger, default=0, nullable=False)
    bytes_received = Column(BigInteger, default=0, nullable=False)

    # Subscriptions
    active_subscriptions = Column(Integer, default=0, nullable=False)
    max_subscriptions = Column(Integer, default=100, nullable=False)


# Pydantic models for API serialization


class WebSocketMessage(BaseModel):
    """WebSocket message base model"""

    type: WebSocketMessageType
    message_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SubscribeMessage(WebSocketMessage):
    """WebSocket subscribe message"""

    subscription_type: SubscriptionType
    channel: str
    filters: Optional[Dict[str, Any]] = None
    batch_size: Optional[int] = 100
    update_interval: Optional[int] = 1000

    model_config = ConfigDict(from_attributes=True)


class UnsubscribeMessage(WebSocketMessage):
    """WebSocket unsubscribe message"""

    subscription_id: Optional[str] = None
    channel: Optional[str] = None
    subscription_type: Optional[SubscriptionType] = None

    model_config = ConfigDict(from_attributes=True)


class DataMessage(WebSocketMessage):
    """WebSocket data message"""

    channel: str
    data_type: str  # metric, event, kpi, etc.
    payload: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ErrorMessage(WebSocketMessage):
    """WebSocket error message"""

    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    retry_after: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class AuthMessage(WebSocketMessage):
    """WebSocket authentication message"""

    token: str
    refresh_token: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class HeartbeatMessage(WebSocketMessage):
    """WebSocket heartbeat message"""

    sequence: Optional[int] = None
    latency_ms: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class SubscriptionConfig(BaseModel):
    """Subscription configuration"""

    subscription_type: SubscriptionType
    channel: str
    filters: Optional[Dict[str, Any]] = None
    batch_size: int = Field(default=100, ge=1, le=1000)
    update_interval: int = Field(default=1000, ge=100, le=300000)
    max_buffer_size: int = Field(default=1000, ge=100, le=10000)
    expires_at: Optional[datetime] = None
    auto_renew: bool = True

    @validator("channel")
    def validate_channel(cls, v):
        """Validate channel name"""
        import re

        if not re.match(r"^[a-zA-Z0-9._-]+$", v):
            raise ValueError(
                "Channel can only contain alphanumeric characters, dots, hyphens, and underscores"
            )
        return v

    model_config = ConfigDict(from_attributes=True)


class SubscriptionCreate(BaseModel):
    """Create subscription request"""

    config: SubscriptionConfig
    websocket_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SubscriptionResponse(BaseModel):
    """Subscription response"""

    id: uuid.UUID
    user_id: uuid.UUID
    session_id: str
    websocket_id: str
    subscription_type: SubscriptionType
    channel: str
    filters: Optional[Dict[str, Any]]
    batch_size: int
    update_interval: int
    max_buffer_size: int
    is_active: bool
    last_activity: datetime
    message_count: int
    error_count: int
    expires_at: Optional[datetime]
    auto_renew: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LiveMetricData(BaseModel):
    """Live metric data"""

    metric_id: str
    metric_name: str
    channel: str
    current_value: float
    previous_value: Optional[float]
    change_percentage: Optional[float]
    timestamp: datetime
    time_window: str
    aggregation_type: str
    sample_count: int
    data_quality_score: Optional[float]
    dimensions: Optional[Dict[str, Any]]
    tags: Optional[List[str]]
    is_anomaly: bool
    alert_threshold_min: Optional[float]
    alert_threshold_max: Optional[float]
    source: Optional[str]
    confidence: Optional[float]

    model_config = ConfigDict(from_attributes=True)


class EventStreamData(BaseModel):
    """Event stream data"""

    event_type: str
    event_name: str
    source: str
    payload: Dict[str, Any]
    metadata: Optional[Dict[str, Any]]
    user_id: Optional[uuid.UUID]
    session_id: Optional[str]
    request_id: Optional[str]
    correlation_id: Optional[str]
    processed_at: datetime
    processing_latency_ms: Optional[int]
    status: str
    error_message: Optional[str]
    routing_key: Optional[str]
    channels: Optional[List[str]]

    model_config = ConfigDict(from_attributes=True)


class ConnectionStats(BaseModel):
    """WebSocket connection statistics"""

    connection_id: str
    user_id: uuid.UUID
    session_id: str
    client_ip: str
    is_connected: bool
    connected_at: datetime
    disconnected_at: Optional[datetime]
    last_ping: Optional[datetime]
    last_pong: Optional[datetime]
    messages_sent: int
    messages_received: int
    bytes_sent: int
    bytes_received: int
    active_subscriptions: int
    max_subscriptions: int
    uptime_seconds: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class RealtimeAnalyticsSummary(BaseModel):
    """Real-time analytics summary"""

    total_connections: int
    active_subscriptions: int
    messages_per_second: float
    events_per_second: float
    metrics_updated: int
    alerts_triggered: int
    system_health: str  # healthy, degraded, critical
    last_updated: datetime

    model_config = ConfigDict(from_attributes=True)


class ChannelMetrics(BaseModel):
    """Channel-specific metrics"""

    channel: str
    subscription_count: int
    messages_per_second: float
    average_message_size: float
    last_message_at: Optional[datetime]
    error_rate: float

    model_config = ConfigDict(from_attributes=True)


class RealtimeDashboard(BaseModel):
    """Real-time dashboard configuration"""

    dashboard_id: uuid.UUID
    channels: List[str]
    widgets: List[Dict[str, Any]]
    update_interval: int
    auto_refresh: bool
    last_data_update: Optional[datetime]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
