"""
Security Audit Service
Comprehensive audit logging and security monitoring for database operations
Implements GDPR compliance and security best practices
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import settings

logger = logging.getLogger(__name__)


class SecurityEventType(Enum):
    """Security event types"""

    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET_REQUEST = "password_reset_request"
    PASSWORD_RESET_SUCCESS = "password_reset_success"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"

    # Authorization events
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    ROLE_CHANGE = "role_change"
    ACCESS_DENIED = "access_denied"

    # Data access events
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"
    FILE_DELETE = "file_delete"
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"
    SEARCH_QUERY = "search_query"

    # Configuration events
    SYSTEM_CONFIG_CHANGE = "system_config_change"
    USER_CREATE = "user_create"
    USER_DELETE = "user_delete"
    USER_UPDATE = "user_update"
    ORG_CREATE = "org_create"
    ORG_UPDATE = "org_update"
    ORG_DELETE = "org_delete"

    # Security events
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    MALICIOUS_REQUEST = "malicious_request"
    INJECTION_ATTEMPT = "injection_attempt"
    XSS_ATTEMPT = "xss_attempt"
    CSRF_ATTEMPT = "csrf_attempt"
    BRUTE_FORCE_DETECTED = "brute_force_detected"
    BLOCKED_IP_ACCESS = "blocked_ip_access"

    # System events
    BACKUP_INITIATED = "backup_initiated"
    BACKUP_COMPLETED = "backup_completed"
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    ERROR_OCCURRED = "error_occurred"


class SecuritySeverity(Enum):
    """Security event severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


Base = declarative_base()


class SecurityAuditLog(Base):
    """Security audit log model"""

    __tablename__ = "security_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(10), nullable=False, index=True)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.now(timezone.utc),
        index=True,
    )

    # User information
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(50), nullable=True)
    organization_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Request information
    ip_address = Column(String(45), nullable=True, index=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(255), nullable=True, index=True)
    session_id = Column(String(255), nullable=True)

    # Event details
    resource_id = Column(String(255), nullable=True)
    resource_type = Column(String(50), nullable=True)
    action = Column(String(100), nullable=True)
    outcome = Column(String(20), nullable=True)  # success, failure, error

    # Additional data
    event_data = Column(JSON, nullable=True)
    event_metadata = Column(
        JSON, nullable=True
    )  # Renamed from 'metadata' to avoid SQLAlchemy reserved name conflict

    # Compliance fields
    data_retention_days = Column(Integer, default=2555)  # 7 years default
    gdpr_relevant = Column(Boolean, default=False, index=True)
    compliance_tags = Column(JSON, nullable=True)


class SecurityAuditService:
    """Service for managing security audit logs"""

    def __init__(self, db_session: Session):
        self.db = db_session

    def log_security_event(
        self,
        event_type: SecurityEventType,
        severity: SecuritySeverity,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        user_role: Optional[str] = None,
        organization_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        outcome: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        gdpr_relevant: bool = False,
        compliance_tags: Optional[List[str]] = None,
    ):
        """Log a security event to the audit trail"""
        try:
            # Create audit log entry
            audit_log = SecurityAuditLog(
                event_type=event_type.value,
                severity=severity.value,
                user_id=user_id,
                user_email=user_email,
                user_role=user_role,
                organization_id=organization_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                session_id=session_id,
                resource_id=resource_id,
                resource_type=resource_type,
                action=action,
                outcome=outcome,
                event_data=self._sanitize_data(event_data) if event_data else None,
                metadata=self._sanitize_data(metadata) if metadata else None,
                gdpr_relevant=gdpr_relevant,
                compliance_tags=compliance_tags or [],
            )

            # Add to database
            self.db.add(audit_log)
            self.db.commit()

            # Log to application logger for immediate visibility
            self._log_to_application_logger(event_type, severity, audit_log)

            # Check for automated response
            self._check_automated_response(event_type, severity, audit_log)

        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
            self.db.rollback()

    def _sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive data before logging"""
        if not data:
            return {}

        sanitized = {}
        sensitive_fields = {
            "password",
            "token",
            "secret",
            "key",
            "auth",
            "credential",
            "ssn",
            "social_security",
            "credit_card",
            "cc_number",
            "api_key",
            "private_key",
            "certificate",
            "cookie",
            "session",
            "jwt",
        }

        for key, value in data.items():
            # Check if key contains sensitive information
            key_lower = key.lower()
            if any(sensitive in key_lower for sensitive in sensitive_fields):
                # Mask sensitive values
                if isinstance(value, str) and len(value) > 4:
                    sanitized[key] = value[:2] + "*" * (len(value) - 4) + value[-2:]
                else:
                    sanitized[key] = "***"
            else:
                # For nested dictionaries
                if isinstance(value, dict):
                    sanitized[key] = self._sanitize_data(value)
                else:
                    sanitized[key] = value

        return sanitized

    def _log_to_application_logger(
        self,
        event_type: SecurityEventType,
        severity: SecuritySeverity,
        audit_log: SecurityAuditLog,
    ):
        """Log event to application logger based on severity"""
        log_message = (
            f"Security Event: {event_type.value} | "
            f"User: {audit_log.user_email or 'Unknown'} | "
            f"IP: {audit_log.ip_address or 'Unknown'} | "
            f"Resource: {audit_log.resource_type}:{audit_log.resource_id or 'N/A'}"
        )

        log_data = {
            "event_type": event_type.value,
            "severity": severity.value,
            "user_id": str(audit_log.user_id) if audit_log.user_id else None,
            "ip_address": audit_log.ip_address,
            "resource_type": audit_log.resource_type,
            "resource_id": audit_log.resource_id,
            "organization_id": str(audit_log.organization_id)
            if audit_log.organization_id
            else None,
        }

        # Log based on severity
        if severity == SecuritySeverity.CRITICAL:
            logger.critical(log_message, extra=log_data)
        elif severity == SecuritySeverity.HIGH:
            logger.error(log_message, extra=log_data)
        elif severity == SecuritySeverity.MEDIUM:
            logger.warning(log_message, extra=log_data)
        else:
            logger.info(log_message, extra=log_data)

    def _check_automated_response(
        self,
        event_type: SecurityEventType,
        severity: SecuritySeverity,
        audit_log: SecurityAuditLog,
    ):
        """Check if automated security response is needed"""
        # Critical events trigger immediate alerts
        if severity == SecuritySeverity.CRITICAL:
            self._trigger_security_alert(audit_log, "CRITICAL_SECURITY_EVENT")

        # Check for patterns requiring automated response
        if event_type in [
            SecurityEventType.BRUTE_FORCE_DETECTED,
            SecurityEventType.INJECTION_ATTEMPT,
            SecurityEventType.MALICIOUS_REQUEST,
            SecurityEventType.BLOCKED_IP_ACCESS,
        ]:
            self._trigger_security_response(audit_log)

        # Check for repeated failures from same IP
        self._check_repeated_failures(audit_log)

    def _trigger_security_alert(self, audit_log: SecurityAuditLog, alert_type: str):
        """Trigger immediate security alert"""
        # This would integrate with alerting systems
        # e.g., Slack, PagerDuty, email, etc.
        logger.critical(
            f"SECURITY ALERT: {alert_type}",
            extra={
                "alert_type": alert_type,
                "event_id": str(audit_log.id),
                "user_id": str(audit_log.user_id),
                "ip_address": audit_log.ip_address,
                "timestamp": audit_log.timestamp.isoformat(),
            },
        )

    def _trigger_security_response(self, audit_log: SecurityAuditLog):
        """Trigger automated security response"""
        # This would implement automated responses like:
        # - Blocking IP addresses
        # - Locking user accounts
        # - Requiring re-authentication
        # - Notifying security team

        logger.error(
            f"Automated security response triggered",
            extra={
                "event_id": str(audit_log.id),
                "ip_address": audit_log.ip_address,
                "user_id": str(audit_log.user_id),
                "action": "security_response_triggered",
            },
        )

    def _check_repeated_failures(self, audit_log: SecurityAuditLog):
        """Check for repeated failures from same IP or user"""
        if not audit_log.ip_address:
            return

        # Query for recent failures from same IP
        recent_failures = (
            self.db.query(SecurityAuditLog)
            .filter(
                SecurityAuditLog.ip_address == audit_log.ip_address,
                SecurityAuditLog.event_type.in_(
                    [
                        SecurityEventType.LOGIN_FAILURE.value,
                        SecurityEventType.ACCESS_DENIED.value,
                        SecurityEventType.INJECTION_ATTEMPT.value,
                    ]
                ),
                SecurityAuditLog.timestamp
                > datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ),
            )
            .count()
        )

        # If too many failures, trigger response
        if recent_failures > 10:
            self._trigger_security_alert(audit_log, "MULTIPLE_SECURITY_FAILURES")

    def search_audit_logs(
        self, filters: Dict[str, Any], page: int = 1, limit: int = 100
    ) -> Dict[str, Any]:
        """Search audit logs with filters"""
        try:
            query = self.db.query(SecurityAuditLog)

            # Apply filters
            if filters.get("event_type"):
                query = query.filter(
                    SecurityAuditLog.event_type == filters["event_type"]
                )

            if filters.get("severity"):
                query = query.filter(SecurityAuditLog.severity == filters["severity"])

            if filters.get("user_id"):
                query = query.filter(SecurityAuditLog.user_id == filters["user_id"])

            if filters.get("organization_id"):
                query = query.filter(
                    SecurityAuditLog.organization_id == filters["organization_id"]
                )

            if filters.get("ip_address"):
                query = query.filter(
                    SecurityAuditLog.ip_address == filters["ip_address"]
                )

            if filters.get("date_from"):
                query = query.filter(SecurityAuditLog.timestamp >= filters["date_from"])

            if filters.get("date_to"):
                query = query.filter(SecurityAuditLog.timestamp <= filters["date_to"])

            # Count total
            total = query.count()

            # Apply pagination
            offset = (page - 1) * limit
            logs = (
                query.order_by(SecurityAuditLog.timestamp.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )

            return {
                "logs": [self._serialize_log(log) for log in logs],
                "total": total,
                "page": page,
                "limit": limit,
                "pages": (total + limit - 1) // limit,
            }

        except Exception as e:
            logger.error(f"Failed to search audit logs: {e}")
            return {"logs": [], "total": 0, "page": 1, "limit": limit, "pages": 0}

    def _serialize_log(self, log: SecurityAuditLog) -> Dict[str, Any]:
        """Serialize audit log for API response"""
        return {
            "id": str(log.id),
            "event_type": log.event_type,
            "severity": log.severity,
            "timestamp": log.timestamp.isoformat(),
            "user_id": str(log.user_id) if log.user_id else None,
            "user_email": log.user_email,
            "user_role": log.user_role,
            "organization_id": str(log.organization_id)
            if log.organization_id
            else None,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "resource_id": log.resource_id,
            "resource_type": log.resource_type,
            "action": log.action,
            "outcome": log.outcome,
            "event_data": log.event_data,
            "metadata": log.metadata,
            "gdpr_relevant": log.gdpr_relevant,
            "compliance_tags": log.compliance_tags,
        }

    def get_security_metrics(
        self,
        organization_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get security metrics for dashboard"""
        try:
            query = self.db.query(SecurityAuditLog)

            if organization_id:
                query = query.filter(
                    SecurityAuditLog.organization_id == organization_id
                )

            if date_from:
                query = query.filter(SecurityAuditLog.timestamp >= date_from)

            if date_to:
                query = query.filter(SecurityAuditLog.timestamp <= date_to)

            # Event counts by type
            event_counts = {}
            for event_type in SecurityEventType:
                count = query.filter(
                    SecurityAuditLog.event_type == event_type.value
                ).count()
                if count > 0:
                    event_counts[event_type.value] = count

            # Severity counts
            severity_counts = {}
            for severity in SecuritySeverity:
                count = query.filter(
                    SecurityAuditLog.severity == severity.value
                ).count()
                severity_counts[severity.value] = count

            # Top attacker IPs
            top_ips = (
                self.db.query(
                    SecurityAuditLog.ip_address,
                    self.db.func.count(SecurityAuditLog.id).label("count"),
                )
                .filter(
                    SecurityAuditLog.severity.in_(["high", "critical"]),
                    SecurityAuditLog.ip_address.isnot(None),
                )
                .group_by(SecurityAuditLog.ip_address)
                .order_by(self.db.func.count(SecurityAuditLog.id).desc())
                .limit(10)
                .all()
            )

            return {
                "event_counts": event_counts,
                "severity_counts": severity_counts,
                "top_attacker_ips": [
                    {"ip": ip, "count": count} for ip, count in top_ips
                ],
                "total_events": query.count(),
            }

        except Exception as e:
            logger.error(f"Failed to get security metrics: {e}")
            return {
                "event_counts": {},
                "severity_counts": {},
                "top_attacker_ips": [],
                "total_events": 0,
            }

    def export_audit_logs(self, filters: Dict[str, Any], format: str = "json") -> bytes:
        """Export audit logs for compliance"""
        try:
            # Get logs
            result = self.search_audit_logs(filters, limit=10000)
            logs = result["logs"]

            if format == "json":
                # Convert to JSON
                export_data = {
                    "export_timestamp": datetime.now(timezone.utc).isoformat(),
                    "filters": filters,
                    "total_records": len(logs),
                    "logs": logs,
                }
                return json.dumps(export_data, indent=2).encode("utf-8")

            elif format == "csv":
                # Convert to CSV
                import csv
                import io

                output = io.StringIO()
                if logs:
                    writer = csv.DictWriter(output, fieldnames=logs[0].keys())
                    writer.writeheader()
                    writer.writerows(logs)

                return output.getvalue().encode("utf-8")

            else:
                raise ValueError(f"Unsupported export format: {format}")

        except Exception as e:
            logger.error(f"Failed to export audit logs: {e}")
            raise

    def cleanup_old_logs(self, retention_days: Optional[int] = None):
        """Clean up old audit logs based on retention policy"""
        try:
            retention_days = retention_days or 2555  # 7 years default
            cutoff_date = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=retention_days)

            # Delete old logs
            deleted = (
                self.db.query(SecurityAuditLog)
                .filter(SecurityAuditLog.timestamp < cutoff_date)
                .delete()
            )

            self.db.commit()

            logger.info(
                f"Cleaned up {deleted} old audit logs",
                extra={"deleted_count": deleted, "cutoff_date": cutoff_date},
            )

            return deleted

        except Exception as e:
            logger.error(f"Failed to cleanup old audit logs: {e}")
            self.db.rollback()
            return 0


# Create audit engine for audit logs (separate from main database if configured)
# Falls back to main DATABASE_URL if AUDIT_DATABASE_URL is not set
_audit_db_url = getattr(settings, "AUDIT_DATABASE_URL", None) or settings.DATABASE_URL
audit_engine = create_engine(_audit_db_url)
AuditSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=audit_engine)


def get_audit_service():
    """Get audit service instance"""
    db = AuditSessionLocal()
    return SecurityAuditService(db)
