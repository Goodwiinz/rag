"""
Audit and compliance service
Provides comprehensive audit logging, compliance reporting, and security monitoring
"""

import logging
import json
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc

from src.models.audit import (
    AuditEvent, ComplianceReport, DataRetentionPolicy, SecurityIncident,
    AuditEventType, AuditSeverity
)
from src.models.user import User
from src.models.organization import Organization
from src.middleware.multi_tenancy import get_current_tenant_id, get_current_user_id
from src.core.database import get_db

logger = logging.getLogger(__name__)


class AuditService:
    """Service for managing audit events and compliance"""

    def __init__(self, db: Session = None):
        self.db = db

    def log_event(
        self,
        event_type: Union[AuditEventType, str],
        action: str,
        user_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
        severity: Union[AuditSeverity, str] = AuditSeverity.MEDIUM,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        endpoint: Optional[str] = None,
        http_method: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> AuditEvent:
        """Log an audit event"""
        try:
            # Get context if not provided
            if not user_id:
                user_id = get_current_user_id()
            if not organization_id:
                organization_id = get_current_tenant_id()

            # Ensure event_type and severity are strings
            if isinstance(event_type, AuditEventType):
                event_type = event_type.value
            if isinstance(severity, AuditSeverity):
                severity = severity.value

            # Create audit event
            audit_event = AuditEvent(
                event_type=event_type,
                severity=severity,
                user_id=user_id,
                organization_id=organization_id,
                session_id=session_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=user_agent,
                endpoint=endpoint,
                http_method=http_method,
                details=details,
                old_values=old_values,
                new_values=new_values,
                success=success,
                error_message=error_message,
                error_code=error_code
            )

            self.db.add(audit_event)
            self.db.commit()
            self.db.refresh(audit_event)

            logger.debug(f"Audit event logged: {event_type} for user {user_id}")
            return audit_event

        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            self.db.rollback()
            raise

    def log_user_login(
        self,
        user_id: str,
        organization_id: str,
        success: bool = True,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> AuditEvent:
        """Log user login attempt"""
        event_type = AuditEventType.USER_LOGIN if success else AuditEventType.USER_LOGIN_FAILED
        severity = AuditSeverity.LOW if success else AuditSeverity.MEDIUM

        return self.log_event(
            event_type=event_type,
            action="User login attempt",
            user_id=user_id,
            organization_id=organization_id,
            success=success,
            error_message=error_message,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent
        )

    def log_user_logout(
        self,
        user_id: str,
        organization_id: str,
        session_id: Optional[str] = None
    ) -> AuditEvent:
        """Log user logout"""
        return self.log_event(
            event_type=AuditEventType.USER_LOGOUT,
            action="User logout",
            user_id=user_id,
            organization_id=organization_id,
            session_id=session_id,
            severity=AuditSeverity.LOW
        )

    def log_document_access(
        self,
        user_id: str,
        organization_id: str,
        document_id: str,
        action: str = "access",
        success: bool = True,
        error_message: Optional[str] = None
    ) -> AuditEvent:
        """Log document access"""
        return self.log_event(
            event_type=AuditEventType.DOCUMENT_ACCESS,
            action=f"Document {action}",
            user_id=user_id,
            organization_id=organization_id,
            resource_type="document",
            resource_id=document_id,
            success=success,
            error_message=error_message,
            severity=AuditSeverity.LOW
        )

    def log_search_query(
        self,
        user_id: str,
        organization_id: str,
        query: str,
        result_count: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditEvent:
        """Log search query"""
        return self.log_event(
            event_type=AuditEventType.SEARCH_QUERY,
            action="Search query executed",
            user_id=user_id,
            organization_id=organization_id,
            resource_type="search_query",
            details={
                "query": query,
                "result_count": result_count
            },
            ip_address=ip_address,
            user_agent=user_agent,
            severity=AuditSeverity.LOW
        )

    def log_security_event(
        self,
        event_type: Union[AuditEventType, str],
        description: str,
        organization_id: str,
        user_id: Optional[str] = None,
        severity: Union[AuditSeverity, str] = AuditSeverity.HIGH,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None
    ) -> AuditEvent:
        """Log security event"""
        return self.log_event(
            event_type=event_type,
            action=description,
            user_id=user_id,
            organization_id=organization_id,
            details=details,
            severity=severity,
            ip_address=ip_address
        )

    def get_audit_events(
        self,
        organization_id: str,
        event_types: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        severity: Optional[str] = None,
        success: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditEvent]:
        """Get audit events with filtering"""
        try:
            query = self.db.query(AuditEvent).filter(
                AuditEvent.organization_id == organization_id
            )

            # Apply filters
            if event_types:
                query = query.filter(AuditEvent.event_type.in_(event_types))
            if user_id:
                query = query.filter(AuditEvent.user_id == user_id)
            if resource_type:
                query = query.filter(AuditEvent.resource_type == resource_type)
            if severity:
                query = query.filter(AuditEvent.severity == severity)
            if success is not None:
                query = query.filter(AuditEvent.success == success)
            if start_date:
                query = query.filter(AuditEvent.created_at >= start_date)
            if end_date:
                query = query.filter(AuditEvent.created_at <= end_date)

            # Order and paginate
            events = query.order_by(desc(AuditEvent.created_at)).offset(offset).limit(limit).all()
            return events

        except Exception as e:
            logger.error(f"Failed to get audit events: {e}")
            return []

    def get_user_activity_summary(
        self,
        organization_id: str,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get activity summary for a user"""
        try:
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Get various metrics
            total_events = self.db.query(func.count(AuditEvent.id)).filter(
                and_(
                    AuditEvent.organization_id == organization_id,
                    AuditEvent.user_id == user_id,
                    AuditEvent.created_at >= start_date
                )
            ).scalar()

            failed_events = self.db.query(func.count(AuditEvent.id)).filter(
                and_(
                    AuditEvent.organization_id == organization_id,
                    AuditEvent.user_id == user_id,
                    AuditEvent.success == False,
                    AuditEvent.created_at >= start_date
                )
            ).scalar()

            # Event type breakdown
            event_types = self.db.query(
                AuditEvent.event_type,
                func.count(AuditEvent.id).label('count')
            ).filter(
                and_(
                    AuditEvent.organization_id == organization_id,
                    AuditEvent.user_id == user_id,
                    AuditEvent.created_at >= start_date
                )
            ).group_by(AuditEvent.event_type).all()

            # Recent activity
            recent_events = self.db.query(AuditEvent).filter(
                and_(
                    AuditEvent.organization_id == organization_id,
                    AuditEvent.user_id == user_id
                )
            ).order_by(desc(AuditEvent.created_at)).limit(10).all()

            return {
                "period_days": days,
                "total_events": total_events or 0,
                "failed_events": failed_events or 0,
                "success_rate": ((total_events - failed_events) / total_events * 100) if total_events > 0 else 100,
                "event_types": {et.event_type: et.count for et in event_types},
                "recent_activity": [event.to_dict() for event in recent_events]
            }

        except Exception as e:
            logger.error(f"Failed to get user activity summary: {e}")
            return {}

    def create_compliance_report(
        self,
        organization_id: str,
        report_type: str,
        report_name: str,
        period_start: datetime,
        period_end: datetime,
        generated_by: str,
        description: Optional[str] = None
    ) -> ComplianceReport:
        """Create a compliance report"""
        try:
            report = ComplianceReport(
                report_type=report_type,
                report_name=report_name,
                description=description,
                organization_id=organization_id,
                generated_by=generated_by,
                period_start=period_start,
                period_end=period_end,
                data={},
                metrics={},
                status="pending"
            )

            self.db.add(report)
            self.db.commit()
            self.db.refresh(report)

            # Generate report data based on type
            self._generate_compliance_data(report)

            return report

        except Exception as e:
            logger.error(f"Failed to create compliance report: {e}")
            self.db.rollback()
            raise

    def _generate_compliance_data(self, report: ComplianceReport):
        """Generate compliance data for report"""
        try:
            org_id = report.organization_id
            start_date = report.period_start
            end_date = report.period_end

            if report.report_type == "security_summary":
                data = self._generate_security_summary(org_id, start_date, end_date)
            elif report.report_type == "access_audit":
                data = self._generate_access_audit(org_id, start_date, end_date)
            elif report.report_type == "data_retention":
                data = self._generate_data_retention_report(org_id, start_date, end_date)
            else:
                data = {"message": "Unknown report type"}

            # Update report with generated data
            report.data = data.get("data", {})
            report.metrics = data.get("metrics", {})
            report.summary = data.get("summary", "")
            report.status = "completed"
            report.generated_at = datetime.now(timezone.utc)

            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to generate compliance data: {e}")
            report.status = "failed"
            report.error_message = str(e)
            self.db.commit()
            raise

    def _generate_security_summary(self, org_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate security summary report data"""
        try:
            # Get security events
            security_events = self.db.query(AuditEvent).filter(
                and_(
                    AuditEvent.organization_id == org_id,
                    AuditEvent.created_at >= start_date,
                    AuditEvent.created_at <= end_date,
                    or_(
                        AuditEvent.event_type.in_([
                            AuditEventType.USER_LOGIN_FAILED,
                            AuditEventType.ACCESS_VIOLATION,
                            AuditEventType.SECURITY_EVENT
                        ]),
                        AuditEvent.severity.in_([AuditSeverity.HIGH.value, AuditSeverity.CRITICAL.value])
                    )
                )
            ).all()

            # Get login statistics
            successful_logins = self.db.query(func.count(AuditEvent.id)).filter(
                and_(
                    AuditEvent.organization_id == org_id,
                    AuditEvent.event_type == AuditEventType.USER_LOGIN,
                    AuditEvent.success == True,
                    AuditEvent.created_at >= start_date,
                    AuditEvent.created_at <= end_date
                )
            ).scalar()

            failed_logins = self.db.query(func.count(AuditEvent.id)).filter(
                and_(
                    AuditEvent.organization_id == org_id,
                    AuditEvent.event_type == AuditEventType.USER_LOGIN_FAILED,
                    AuditEvent.created_at >= start_date,
                    AuditEvent.created_at <= end_date
                )
            ).scalar()

            # Active users
            active_users = self.db.query(func.count(func.distinct(AuditEvent.user_id))).filter(
                and_(
                    AuditEvent.organization_id == org_id,
                    AuditEvent.created_at >= start_date,
                    AuditEvent.created_at <= end_date
                )
            ).scalar()

            data = {
                "security_events": [event.to_dict() for event in security_events],
                "security_incidents": [event.to_dict() for event in security_events if event.severity in [AuditSeverity.HIGH.value, AuditSeverity.CRITICAL.value]]
            }

            metrics = {
                "total_security_events": len(security_events),
                "successful_logins": successful_logins or 0,
                "failed_logins": failed_logins or 0,
                "login_success_rate": ((successful_logins / (successful_logins + failed_logins)) * 100) if (successful_logins + failed_logins) > 0 else 100,
                "active_users": active_users or 0,
                "high_severity_events": len([e for e in security_events if e.severity == AuditSeverity.HIGH.value]),
                "critical_severity_events": len([e for e in security_events if e.severity == AuditSeverity.CRITICAL.value])
            }

            summary = f"Security summary for period {start_date.date()} to {end_date.date()}. " \
                      f"Total security events: {len(security_events)}. " \
                      f"Login success rate: {metrics['login_success_rate']:.1f}%."

            return {"data": data, "metrics": metrics, "summary": summary}

        except Exception as e:
            logger.error(f"Failed to generate security summary: {e}")
            return {"data": {}, "metrics": {}, "summary": f"Error: {str(e)}"}

    def _generate_access_audit(self, org_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate access audit report data"""
        try:
            # Get document access events
            access_events = self.db.query(AuditEvent).filter(
                and_(
                    AuditEvent.organization_id == org_id,
                    AuditEvent.event_type == AuditEventType.DOCUMENT_ACCESS,
                    AuditEvent.created_at >= start_date,
                    AuditEvent.created_at <= end_date
                )
            ).all()

            # Get access violations
            violations = self.db.query(AuditEvent).filter(
                and_(
                    AuditEvent.organization_id == org_id,
                    AuditEvent.event_type == AuditEventType.ACCESS_VIOLATION,
                    AuditEvent.created_at >= start_date,
                    AuditEvent.created_at <= end_date
                )
            ).all()

            # Group by user
            user_access = {}
            for event in access_events:
                user_id = str(event.user_id)
                if user_id not in user_access:
                    user_access[user_id] = {"access_count": 0, "failed_count": 0}
                user_access[user_id]["access_count"] += 1
                if not event.success:
                    user_access[user_id]["failed_count"] += 1

            data = {
                "access_events": [event.to_dict() for event in access_events],
                "access_violations": [event.to_dict() for event in violations],
                "user_access_summary": user_access
            }

            metrics = {
                "total_access_events": len(access_events),
                "access_violations": len(violations),
                "unique_users": len(user_access),
                "failed_access_attempts": sum(user["failed_count"] for user in user_access.values())
            }

            summary = f"Access audit for period {start_date.date()} to {end_date.date()}. " \
                      f"Total access events: {len(access_events)}. " \
                      f"Access violations: {len(violations)}."

            return {"data": data, "metrics": metrics, "summary": summary}

        except Exception as e:
            logger.error(f"Failed to generate access audit: {e}")
            return {"data": {}, "metrics": {}, "summary": f"Error: {str(e)}"}

    def _generate_data_retention_report(self, org_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate data retention report data"""
        try:
            # Get data export events
            export_events = self.db.query(AuditEvent).filter(
                and_(
                    AuditEvent.organization_id == org_id,
                    AuditEvent.event_type == AuditEventType.DATA_EXPORT,
                    AuditEvent.created_at >= start_date,
                    AuditEvent.created_at <= end_date
                )
            ).all()

            # Get privacy requests
            privacy_requests = self.db.query(AuditEvent).filter(
                and_(
                    AuditEvent.organization_id == org_id,
                    AuditEvent.event_type == AuditEventType.PRIVACY_REQUEST,
                    AuditEvent.created_at >= start_date,
                    AuditEvent.created_at <= end_date
                )
            ).all()

            data = {
                "export_events": [event.to_dict() for event in export_events],
                "privacy_requests": [event.to_dict() for event in privacy_requests]
            }

            metrics = {
                "data_exports": len(export_events),
                "privacy_requests": len(privacy_requests),
                "export_volume": sum(event.details.get("file_size", 0) for event in export_events if event.details)
            }

            summary = f"Data retention report for period {start_date.date()} to {end_date.date()}. " \
                      f"Data exports: {len(export_events)}. " \
                      f"Privacy requests: {len(privacy_requests)}."

            return {"data": data, "metrics": metrics, "summary": summary}

        except Exception as e:
            logger.error(f"Failed to generate data retention report: {e}")
            return {"data": {}, "metrics": {}, "summary": f"Error: {str(e)}"}

    def create_security_incident(
        self,
        organization_id: str,
        title: str,
        description: str,
        severity: str,
        category: str,
        detected_at: Optional[datetime] = None,
        source: str = "automated",
        source_details: Optional[Dict[str, Any]] = None,
        affected_users: Optional[List[str]] = None,
        affected_resources: Optional[List[str]] = None,
        impact_assessment: Optional[str] = None
    ) -> SecurityIncident:
        """Create a security incident"""
        try:
            if not detected_at:
                detected_at = datetime.now(timezone.utc)

            # Generate unique incident ID
            incident_id = f"INC-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

            incident = SecurityIncident(
                incident_id=incident_id,
                title=title,
                description=description,
                severity=severity,
                category=category,
                organization_id=organization_id,
                detected_at=detected_at,
                source=source,
                source_details=source_details,
                affected_users=affected_users,
                affected_resources=affected_resources,
                impact_assessment=impact_assessment
            )

            self.db.add(incident)
            self.db.commit()
            self.db.refresh(incident)

            # Log the incident creation
            self.log_security_event(
                event_type=AuditEventType.SECURITY_EVENT,
                description=f"Security incident created: {title}",
                organization_id=organization_id,
                severity=severity,
                details={
                    "incident_id": incident_id,
                    "category": category,
                    "affected_users": len(affected_users) if affected_users else 0
                }
            )

            logger.info(f"Security incident created: {incident_id}")
            return incident

        except Exception as e:
            logger.error(f"Failed to create security incident: {e}")
            self.db.rollback()
            raise

    def get_security_incidents(
        self,
        organization_id: str,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SecurityIncident]:
        """Get security incidents with filtering"""
        try:
            query = self.db.query(SecurityIncident).filter(
                SecurityIncident.organization_id == organization_id
            )

            if status:
                query = query.filter(SecurityIncident.status == status)
            if severity:
                query = query.filter(SecurityIncident.severity == severity)
            if category:
                query = query.filter(SecurityIncident.category == category)

            incidents = query.order_by(desc(SecurityIncident.detected_at)).offset(offset).limit(limit).all()
            return incidents

        except Exception as e:
            logger.error(f"Failed to get security incidents: {e}")
            return []

    def cleanup_old_audit_events(self, retention_days: int = 365) -> int:
        """Clean up old audit events based on retention policy"""
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

            # Count events to be deleted
            count = self.db.query(func.count(AuditEvent.id)).filter(
                AuditEvent.created_at < cutoff_date
            ).scalar()

            # Delete old events
            self.db.query(AuditEvent).filter(
                AuditEvent.created_at < cutoff_date
            ).delete()

            self.db.commit()

            logger.info(f"Cleaned up {count} old audit events older than {retention_days} days")
            return count

        except Exception as e:
            logger.error(f"Failed to cleanup old audit events: {e}")
            self.db.rollback()
            return 0

    def close(self):
        """Close database session"""
        if self.db:
            self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Utility functions

def get_audit_service(db: Session = None) -> AuditService:
    """Get audit service instance"""
    return AuditService(db)


def log_audit_event(
    event_type: Union[AuditEventType, str],
    action: str,
    **kwargs
) -> AuditEvent:
    """Utility function to log audit event"""
    with AuditService() as audit:
        return audit.log_event(event_type, action, **kwargs)