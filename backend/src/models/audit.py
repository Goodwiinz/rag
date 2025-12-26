"""
Audit and compliance models for security logging
Comprehensive audit trail for all system activities and compliance reporting
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import Column, String, DateTime, Boolean, Text, Integer, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .base import Base


class AuditEventType(str, Enum):
    """Types of audit events"""
    # Authentication events
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_LOGIN_FAILED = "user_login_failed"
    USER_REGISTER = "user_register"
    USER_PASSWORD_CHANGE = "user_password_change"
    USER_PASSWORD_RESET = "user_password_reset"

    # Authorization events
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"

    # Data access events
    DOCUMENT_ACCESS = "document_access"
    DOCUMENT_CREATE = "document_create"
    DOCUMENT_UPDATE = "document_update"
    DOCUMENT_DELETE = "document_delete"
    DOCUMENT_DOWNLOAD = "document_download"

    # Search events
    SEARCH_QUERY = "search_query"
    SEARCH_RESULT_CLICK = "search_result_click"
    SEARCH_EXPORT = "search_export"

    # System events
    SYSTEM_CONFIG_CHANGE = "system_config_change"
    SECURITY_EVENT = "security_event"
    ERROR_EVENT = "error_event"
    PERFORMANCE_ALERT = "performance_alert"

    # Compliance events
    DATA_EXPORT = "data_export"
    DATA_RETENTION_CLEANUP = "data_retention_cleanup"
    PRIVACY_REQUEST = "privacy_request"
    ACCESS_VIOLATION = "access_violation"


class AuditSeverity(str, Enum):
    """Severity levels for audit events"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditEvent(Base):
    """Main audit event record"""
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Event identification
    event_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True, default=AuditSeverity.MEDIUM.value)

    # User and organization context
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    session_id = Column(String(255), nullable=True, index=True)

    # Event details
    action = Column(String(255), nullable=False)
    resource_type = Column(String(100), nullable=True, index=True)
    resource_id = Column(String(255), nullable=True, index=True)

    # Request context
    ip_address = Column(String(45), nullable=True, index=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    endpoint = Column(String(255), nullable=True)
    http_method = Column(String(10), nullable=True)

    # Event data
    details = Column(JSON, nullable=True)
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)

    # Result
    success = Column(Boolean, nullable=False, default=True, index=True)
    error_message = Column(Text, nullable=True)
    error_code = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", back_populates="audit_events")
    organization = relationship("Organization", back_populates="audit_events")

    def __repr__(self):
        return f"<AuditEvent(id={self.id}, type={self.event_type}, user_id={self.user_id})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert audit event to dictionary"""
        return {
            "id": str(self.id),
            "event_type": self.event_type,
            "severity": self.severity,
            "user_id": str(self.user_id) if self.user_id else None,
            "organization_id": str(self.organization_id),
            "session_id": self.session_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "endpoint": self.endpoint,
            "http_method": self.http_method,
            "details": self.details,
            "old_values": self.old_values,
            "new_values": self.new_values,
            "success": self.success,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ComplianceReport(Base):
    """Compliance report generation and tracking"""
    __tablename__ = "compliance_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Report identification
    report_type = Column(String(100), nullable=False, index=True)
    report_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Organization context
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    generated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Report period
    period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end = Column(DateTime(timezone=True), nullable=False, index=True)

    # Report data
    data = Column(JSON, nullable=False)
    metrics = Column(JSON, nullable=False)
    summary = Column(Text, nullable=True)

    # File information
    file_path = Column(String(500), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    file_format = Column(String(20), nullable=True, default="json")

    # Status
    status = Column(String(20), nullable=False, default="pending", index=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    generated_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization")
    generator = relationship("User")

    def __repr__(self):
        return f"<ComplianceReport(id={self.id}, type={self.report_type}, org={self.organization_id})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert compliance report to dictionary"""
        return {
            "id": str(self.id),
            "report_type": self.report_type,
            "report_name": self.report_name,
            "description": self.description,
            "organization_id": str(self.organization_id),
            "generated_by": str(self.generated_by),
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "data": self.data,
            "metrics": self.metrics,
            "summary": self.summary,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "file_format": self.file_format,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }


class DataRetentionPolicy(Base):
    """Data retention policies for compliance"""
    __tablename__ = "data_retention_policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Policy identification
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    policy_type = Column(String(100), nullable=False, index=True)  # audit, documents, user_data, etc.

    # Retention rules
    retention_days = Column(Integer, nullable=False)
    retention_period = Column(String(50), nullable=False)  # days, months, years

    # Conditions
    conditions = Column(JSON, nullable=True)  # Conditions for applying retention

    # Action
    action = Column(String(50), nullable=False, default="delete")  # delete, archive, anonymize

    # Status
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Organization context (null for global policies)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_run_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization")

    def __repr__(self):
        return f"<DataRetentionPolicy(id={self.id}, name={self.name}, type={self.policy_type})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert retention policy to dictionary"""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "policy_type": self.policy_type,
            "retention_days": self.retention_days,
            "retention_period": self.retention_period,
            "conditions": self.conditions,
            "action": self.action,
            "is_active": self.is_active,
            "organization_id": str(self.organization_id) if self.organization_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None
        }


class SecurityIncident(Base):
    """Security incident tracking and response"""
    __tablename__ = "security_incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Incident identification
    incident_id = Column(String(100), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    # Classification
    severity = Column(String(20), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="open", index=True)

    # Organization context
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)

    # Incident details
    detected_at = Column(DateTime(timezone=True), nullable=False, index=True)
    source = Column(String(100), nullable=True)  # automated, user_report, external
    source_details = Column(JSON, nullable=True)

    # Impact assessment
    affected_users = Column(JSON, nullable=True)  # List of affected user IDs
    affected_resources = Column(JSON, nullable=True)  # List of affected resource IDs
    impact_assessment = Column(Text, nullable=True)

    # Response
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    response_actions = Column(JSON, nullable=True)  # Timeline of response actions
    resolution = Column(Text, nullable=True)

    # Metrics
    resolution_time_hours = Column(Integer, nullable=True)
    damage_assessment = Column(String(50), nullable=True)  # low, medium, high, critical

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization = relationship("Organization")
    assignee = relationship("User")

    def __repr__(self):
        return f"<SecurityIncident(id={self.id}, incident_id={self.incident_id}, severity={self.severity})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert security incident to dictionary"""
        return {
            "id": str(self.id),
            "incident_id": self.incident_id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "category": self.category,
            "status": self.status,
            "organization_id": str(self.organization_id),
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "source": self.source,
            "source_details": self.source_details,
            "affected_users": self.affected_users,
            "affected_resources": self.affected_resources,
            "impact_assessment": self.impact_assessment,
            "assigned_to": str(self.assigned_to) if self.assigned_to else None,
            "response_actions": self.response_actions,
            "resolution": self.resolution,
            "resolution_time_hours": self.resolution_time_hours,
            "damage_assessment": self.damage_assessment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None
        }


# Indexes for performance
Index('idx_audit_events_org_user_date', AuditEvent.organization_id, AuditEvent.user_id, AuditEvent.created_at)
Index('idx_audit_events_type_success', AuditEvent.event_type, AuditEvent.success)
Index('idx_audit_events_resource', AuditEvent.resource_type, AuditEvent.resource_id)
Index('idx_compliance_reports_org_type', ComplianceReport.organization_id, ComplianceReport.report_type)
Index('idx_security_incidents_org_status', SecurityIncident.organization_id, SecurityIncident.status)