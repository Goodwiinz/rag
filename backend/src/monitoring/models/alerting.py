"""
Alerting Database Models

Models for storing alerts, alert rules, and alert history.
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON, Index, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from src.models.base import BaseModel


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertStatus(str, Enum):
    """Alert status"""
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    CLOSED = "closed"


class AlertType(str, Enum):
    """Alert types"""
    SYSTEM = "system"
    APPLICATION = "application"
    BUSINESS = "business"
    SECURITY = "security"
    PERFORMANCE = "performance"
    CUSTOM = "custom"


class ChannelType(str, Enum):
    """Alert channel types"""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"
    PAGERDUTY = "pagerduty"


class AlertRule(BaseModel):
    """Alert rule definitions"""
    __tablename__ = "monitoring_alert_rules"

    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text)
    rule_type = Column(String(50), nullable=False)  # threshold, anomaly, pattern, composite
    severity = Column(String(20), nullable=False, default=AlertSeverity.MEDIUM)
    category = Column(String(100))

    # Rule configuration
    conditions = Column(JSONB, nullable=False)  # Rule conditions and thresholds
    evaluation_window_minutes = Column(Integer, default=5)
    evaluation_interval_seconds = Column(Integer, default=60)
    consecutive_evaluations = Column(Integer, default=1)

    # Data sources
    metric_name = Column(String(255), index=True)
    log_pattern = Column(String(500))
    trace_conditions = Column(JSONB, default=dict)

    # Notification settings
    channels = Column(JSONB, default=list)  # List of channel IDs
    notification_cooldown_minutes = Column(Integer, default=5)
    max_notifications_per_hour = Column(Integer, default=10)

    # Rule state
    is_active = Column(Boolean, default=True)
    current_state = Column(String(50), default="normal")  # normal, warning, critical
    last_evaluation = Column(DateTime(timezone=True))
    last_triggered = Column(DateTime(timezone=True))
    trigger_count = Column(Integer, default=0)

    # Metadata
    tags = Column(JSONB, default=list)
    metadata = Column(JSONB, default=dict)
    created_by = Column(String(255))

    # Relationships
    alerts = relationship("Alert", back_populates="rule")
    history = relationship("AlertHistory", back_populates="rule")

    # Indexes
    __table_args__ = (
        Index('idx_alert_rules_active_type', 'is_active', 'rule_type'),
        Index('idx_alert_rules_severity', 'severity'),
        Index('idx_alert_rules_metric', 'metric_name'),
    )


class Alert(BaseModel):
    """Alert instances"""
    __tablename__ = "monitoring_alerts"

    alert_id = Column(String(128), unique=True, nullable=False, index=True)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_alert_rules.id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, index=True)
    status = Column(String(20), nullable=False, default=AlertStatus.OPEN, index=True)
    alert_type = Column(String(50), nullable=False)

    # Timing
    triggered_at = Column(DateTime(timezone=True), nullable=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    closed_at = Column(DateTime(timezone=True))
    duration_minutes = Column(Float)

    # Alert data
    source_data = Column(JSONB, default=dict)  # Original data that triggered the alert
    context = Column(JSONB, default=dict)  # Additional context information
    metrics = Column(JSONB, default=dict)  # Relevant metrics at trigger time
    labels = Column(JSONB, default=dict)

    # Assignment and ownership
    assigned_to = Column(String(255))
    acknowledged_by = Column(String(255))
    resolved_by = Column(String(255))

    # Notification tracking
    notifications_sent = Column(JSONB, default=list)  # List of sent notifications
    notification_errors = Column(JSONB, default=list)

    # Relationships
    rule = relationship("AlertRule", back_populates="alerts")
    history = relationship("AlertHistory", back_populates="alert", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_alerts_status_severity', 'status', 'severity'),
        Index('idx_alerts_triggered_time', 'triggered_at'),
        Index('idx_alerts_type_time', 'alert_type', 'triggered_at'),
        Index('idx_alerts_assigned', 'assigned_to'),
    )


class AlertHistory(BaseModel):
    """Alert state changes and history"""
    __tablename__ = "monitoring_alert_history"

    alert_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_alerts.id"), nullable=False, index=True)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_alert_rules.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # created, acknowledged, resolved, closed, escalated
    old_status = Column(String(50))
    new_status = Column(String(50))
    old_severity = Column(String(50))
    new_severity = Column(String(50))

    # Event details
    message = Column(Text)
    details = Column(JSONB, default=dict)
    actor = Column(String(255))  # User or system that performed the action
    source = Column(String(100))  # Source of the state change

    # Relationships
    alert = relationship("Alert", back_populates="history")
    rule = relationship("AlertRule", back_populates="history")

    # Indexes
    __table_args__ = (
        Index('idx_alert_history_alert_time', 'alert_id', 'created_at'),
        Index('idx_alert_history_event_type', 'event_type'),
        Index('idx_alert_history_rule_time', 'rule_id', 'created_at'),
    )


class AlertChannel(BaseModel):
    """Alert notification channels"""
    __tablename__ = "monitoring_alert_channels"

    name = Column(String(255), unique=True, nullable=False, index=True)
    channel_type = Column(String(50), nullable=False)  # email, slack, webhook, sms
    description = Column(Text)

    # Channel configuration
    configuration = Column(JSONB, nullable=False)  # Channel-specific config
    is_active = Column(Boolean, default=True)
    test_mode = Column(Boolean, default=False)

    # Rate limiting
    max_notifications_per_minute = Column(Integer, default=10)
    max_notifications_per_hour = Column(Integer, default=100)

    # Channel health
    last_success = Column(DateTime(timezone=True))
    last_failure = Column(DateTime(timezone=True))
    failure_count = Column(Integer, default=0)
    is_healthy = Column(Boolean, default=True)

    # Metadata
    tags = Column(JSONB, default=list)
    created_by = Column(String(255))

    # Relationships
    subscriptions = relationship("AlertSubscription", back_populates="channel")

    # Indexes
    __table_args__ = (
        Index('idx_alert_channels_type_active', 'channel_type', 'is_active'),
        Index('idx_alert_channels_healthy', 'is_healthy'),
    )


class AlertSubscription(BaseModel):
    """Alert subscriptions linking rules to channels"""
    __tablename__ = "monitoring_alert_subscriptions"

    rule_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_alert_rules.id"), nullable=False, index=True)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("monitoring_alert_channels.id"), nullable=False, index=True)

    # Subscription configuration
    is_active = Column(Boolean, default=True)
    min_severity = Column(String(20))  # Minimum severity to notify
    filters = Column(JSONB, default=dict)  # Additional filters

    # Subscription metadata
    created_by = Column(String(255))
    notes = Column(Text)

    # Relationships
    rule = relationship("AlertRule")
    channel = relationship("AlertChannel", back_populates="subscriptions")

    # Indexes
    __table_args__ = (
        Index('idx_alert_subscriptions_rule_channel', 'rule_id', 'channel_id'),
        Index('idx_alert_subscriptions_active', 'is_active'),
    )