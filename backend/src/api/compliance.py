"""
Compliance and audit API endpoints
Provides audit log access, compliance reporting, and security monitoring
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

from src.core.database import get_db
from src.middleware.multi_tenancy import get_current_tenant_id, get_current_user_id
from src.middleware.rbac import require_permission
from src.services.audit_service import AuditService, AuditEventType, AuditSeverity
from src.models.audit import AuditEvent, ComplianceReport, SecurityIncident
from src.exceptions.analytics_exceptions import (
    PermissionDeniedException,
    ConfigurationException,
    create_permission_denied_http_exception
)

router = APIRouter(prefix="/compliance", tags=["Compliance"])


# Pydantic models for request/response

class AuditEventResponse(BaseModel):
    """Response model for audit event data"""
    id: str
    event_type: str
    severity: str
    user_id: Optional[str]
    organization_id: str
    session_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    endpoint: Optional[str]
    http_method: Optional[str]
    details: Optional[Dict[str, Any]]
    old_values: Optional[Dict[str, Any]]
    new_values: Optional[Dict[str, Any]]
    success: bool
    error_message: Optional[str]
    error_code: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class ComplianceReportRequest(BaseModel):
    """Request model for creating compliance report"""
    report_type: str = Field(..., description="Type of compliance report")
    report_name: str = Field(..., description="Name of the report")
    period_start: datetime = Field(..., description="Start date for report period")
    period_end: datetime = Field(..., description="End date for report period")
    description: Optional[str] = Field(None, description="Report description")


class ComplianceReportResponse(BaseModel):
    """Response model for compliance report data"""
    id: str
    report_type: str
    report_name: str
    description: Optional[str]
    organization_id: str
    generated_by: str
    period_start: str
    period_end: str
    data: Dict[str, Any]
    metrics: Dict[str, Any]
    summary: Optional[str]
    file_path: Optional[str]
    file_size_bytes: Optional[int]
    file_format: str
    status: str
    error_message: Optional[str]
    created_at: str
    generated_at: Optional[str]
    expires_at: Optional[str]

    class Config:
        from_attributes = True


class SecurityIncidentRequest(BaseModel):
    """Request model for creating security incident"""
    title: str = Field(..., description="Incident title")
    description: str = Field(..., description="Incident description")
    severity: str = Field(..., description="Incident severity")
    category: str = Field(..., description="Incident category")
    detected_at: Optional[datetime] = Field(None, description="Detection time")
    source: str = Field(default="automated", description="Source of detection")
    source_details: Optional[Dict[str, Any]] = Field(None, description="Source details")
    affected_users: Optional[List[str]] = Field(None, description="Affected user IDs")
    affected_resources: Optional[List[str]] = Field(None, description="Affected resource IDs")
    impact_assessment: Optional[str] = Field(None, description="Impact assessment")


class SecurityIncidentResponse(BaseModel):
    """Response model for security incident data"""
    id: str
    incident_id: str
    title: str
    description: str
    severity: str
    category: str
    status: str
    organization_id: str
    detected_at: str
    source: str
    source_details: Optional[Dict[str, Any]]
    affected_users: Optional[List[str]]
    affected_resources: Optional[List[str]]
    impact_assessment: Optional[str]
    assigned_to: Optional[str]
    response_actions: Optional[Dict[str, Any]]
    resolution: Optional[str]
    resolution_time_hours: Optional[int]
    damage_assessment: Optional[str]
    created_at: str
    updated_at: str
    resolved_at: Optional[str]

    class Config:
        from_attributes = True


class UserActivitySummaryResponse(BaseModel):
    """Response model for user activity summary"""
    period_days: int
    total_events: int
    failed_events: int
    success_rate: float
    event_types: Dict[str, int]
    recent_activity: List[AuditEventResponse]


# Helper functions

def get_audit_service() -> AuditService:
    """Get audit service instance"""
    return AuditService()


# API Endpoints

@router.get("/audit/events", response_model=List[AuditEventResponse])
async def get_audit_events(
    event_types: Optional[List[str]] = Query(None, description="Filter by event types"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    success: Optional[bool] = Query(None, description="Filter by success status"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of events"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    audit_service: AuditService = Depends(get_audit_service),
    _: str = Depends(require_permission("audit_read"))
):
    """Get audit events with filtering and pagination"""
    try:
        organization_id = get_current_tenant_id()
        if not organization_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Organization context required"
            )

        events = audit_service.get_audit_events(
            organization_id=organization_id,
            event_types=event_types,
            user_id=user_id,
            resource_type=resource_type,
            severity=severity,
            success=success,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )

        return [AuditEventResponse(**event.to_dict()) for event in events]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit events"
        )


@router.get("/audit/events/{event_id}", response_model=AuditEventResponse)
async def get_audit_event(
    event_id: str = Path(..., description="Event ID"),
    audit_service: AuditService = Depends(get_audit_service),
    _: str = Depends(require_permission("audit_read"))
):
    """Get specific audit event details"""
    try:
        organization_id = get_current_tenant_id()

        event = audit_service.db.query(AuditEvent).filter(
            AuditEvent.id == event_id,
            AuditEvent.organization_id == organization_id
        ).first()

        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit event not found"
            )

        return AuditEventResponse(**event.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit event"
        )


@router.get("/audit/users/{user_id}/activity", response_model=UserActivitySummaryResponse)
async def get_user_activity_summary(
    user_id: str = Path(..., description="User ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    audit_service: AuditService = Depends(get_audit_service),
    _: str = Depends(require_permission("audit_read"))
):
    """Get activity summary for a specific user"""
    try:
        organization_id = get_current_tenant_id()

        summary = audit_service.get_user_activity_summary(
            organization_id=organization_id,
            user_id=user_id,
            days=days
        )

        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User activity not found"
            )

        return UserActivitySummaryResponse(**summary)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user activity summary"
        )


@router.post("/reports", response_model=ComplianceReportResponse, status_code=status.HTTP_201_CREATED)
async def create_compliance_report(
    report_data: ComplianceReportRequest,
    background_tasks: BackgroundTasks,
    audit_service: AuditService = Depends(get_audit_service),
    _: str = Depends(require_permission("compliance_manage"))
):
    """Create a compliance report"""
    try:
        organization_id = get_current_tenant_id()
        user_id = get_current_user_id()

        if not organization_id or not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        # Validate date range
        if report_data.period_start >= report_data.period_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Period start must be before period end"
            )

        # Limit report period to 1 year
        max_period = timedelta(days=365)
        if report_data.period_end - report_data.period_start > max_period:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Report period cannot exceed 1 year"
            )

        # Create report
        report = audit_service.create_compliance_report(
            organization_id=organization_id,
            report_type=report_data.report_type,
            report_name=report_data.report_name,
            period_start=report_data.period_start,
            period_end=report_data.period_end,
            generated_by=user_id,
            description=report_data.description
        )

        return ComplianceReportResponse(**report.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create compliance report"
        )


@router.get("/reports", response_model=List[ComplianceReportResponse])
async def get_compliance_reports(
    report_type: Optional[str] = Query(None, description="Filter by report type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of reports"),
    offset: int = Query(0, ge=0, description="Number of reports to skip"),
    audit_service: AuditService = Depends(get_audit_service),
    _: str = Depends(require_permission("compliance_read"))
):
    """Get compliance reports with filtering"""
    try:
        organization_id = get_current_tenant_id()
        if not organization_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Organization context required"
            )

        query = audit_service.db.query(ComplianceReport).filter(
            ComplianceReport.organization_id == organization_id
        )

        if report_type:
            query = query.filter(ComplianceReport.report_type == report_type)
        if status:
            query = query.filter(ComplianceReport.status == status)

        reports = query.order_by(desc(ComplianceReport.created_at)).offset(offset).limit(limit).all()

        return [ComplianceReportResponse(**report.to_dict()) for report in reports]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve compliance reports"
        )


@router.get("/reports/{report_id}", response_model=ComplianceReportResponse)
async def get_compliance_report(
    report_id: str = Path(..., description="Report ID"),
    audit_service: AuditService = Depends(get_audit_service),
    _: str = Depends(require_permission("compliance_read"))
):
    """Get specific compliance report"""
    try:
        organization_id = get_current_tenant_id()

        report = audit_service.db.query(ComplianceReport).filter(
            ComplianceReport.id == report_id,
            ComplianceReport.organization_id == organization_id
        ).first()

        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Compliance report not found"
            )

        return ComplianceReportResponse(**report.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve compliance report"
        )


@router.post("/security/incidents", response_model=SecurityIncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_security_incident(
    incident_data: SecurityIncidentRequest,
    audit_service: AuditService = Depends(get_audit_service),
    _: str = Depends(require_permission("security_manage"))
):
    """Create a security incident"""
    try:
        organization_id = get_current_tenant_id()
        if not organization_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Organization context required"
            )

        incident = audit_service.create_security_incident(
            organization_id=organization_id,
            title=incident_data.title,
            description=incident_data.description,
            severity=incident_data.severity,
            category=incident_data.category,
            detected_at=incident_data.detected_at,
            source=incident_data.source,
            source_details=incident_data.source_details,
            affected_users=incident_data.affected_users,
            affected_resources=incident_data.affected_resources,
            impact_assessment=incident_data.impact_assessment
        )

        return SecurityIncidentResponse(**incident.to_dict())

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create security incident"
        )


@router.get("/security/incidents", response_model=List[SecurityIncidentResponse])
async def get_security_incidents(
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of incidents"),
    offset: int = Query(0, ge=0, description="Number of incidents to skip"),
    audit_service: AuditService = Depends(get_audit_service),
    _: str = Depends(require_permission("security_read"))
):
    """Get security incidents with filtering"""
    try:
        organization_id = get_current_tenant_id()
        if not organization_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Organization context required"
            )

        incidents = audit_service.get_security_incidents(
            organization_id=organization_id,
            status=status,
            severity=severity,
            category=category,
            limit=limit,
            offset=offset
        )

        return [SecurityIncidentResponse(**incident.to_dict()) for incident in incidents]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security incidents"
        )


@router.get("/security/incidents/{incident_id}", response_model=SecurityIncidentResponse)
async def get_security_incident(
    incident_id: str = Path(..., description="Incident ID"),
    audit_service: AuditService = Depends(get_audit_service),
    _: str = Depends(require_permission("security_read"))
):
    """Get specific security incident"""
    try:
        organization_id = get_current_tenant_id()

        incident = audit_service.db.query(SecurityIncident).filter(
            SecurityIncident.id == incident_id,
            SecurityIncident.organization_id == organization_id
        ).first()

        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Security incident not found"
            )

        return SecurityIncidentResponse(**incident.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security incident"
        )


@router.post("/cleanup/audit-events", response_model=Dict[str, Any])
async def cleanup_old_audit_events(
    retention_days: int = Query(365, ge=30, le=2555, description="Retention period in days"),
    audit_service: AuditService = Depends(get_audit_service),
    _: str = Depends(require_permission("system_admin"))
):
    """Clean up old audit events based on retention policy"""
    try:
        deleted_count = audit_service.cleanup_old_audit_events(retention_days)

        return {
            "message": "Audit cleanup completed",
            "retention_days": retention_days,
            "deleted_events": deleted_count
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup audit events"
        )


@router.get("/dashboard", response_model=Dict[str, Any])
async def get_compliance_dashboard(
    days: int = Query(30, ge=1, le=365, description="Number of days for dashboard data"),
    audit_service: AuditService = Depends(get_audit_service),
    _: str = Depends(require_permission("compliance_read"))
):
    """Get compliance dashboard data"""
    try:
        organization_id = get_current_tenant_id()
        if not organization_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Organization context required"
            )

        start_date = datetime.utcnow() - timedelta(days=days)

        # Get recent audit events
        recent_events = audit_service.db.query(AuditEvent).filter(
            AuditEvent.organization_id == organization_id,
            AuditEvent.created_at >= start_date
        ).order_by(AuditEvent.created_at.desc()).limit(100).all()

        # Get event type breakdown
        event_types = audit_service.db.query(
            AuditEvent.event_type,
            func.count(AuditEvent.id).label('count')
        ).filter(
            and_(
                AuditEvent.organization_id == organization_id,
                AuditEvent.created_at >= start_date
            )
        ).group_by(AuditEvent.event_type).all()

        # Get severity breakdown
        severity_breakdown = audit_service.db.query(
            AuditEvent.severity,
            func.count(AuditEvent.id).label('count')
        ).filter(
            and_(
                AuditEvent.organization_id == organization_id,
                AuditEvent.created_at >= start_date
            )
        ).group_by(AuditEvent.severity).all()

        # Get failed events
        failed_events = audit_service.db.query(func.count(AuditEvent.id)).filter(
            and_(
                AuditEvent.organization_id == organization_id,
                AuditEvent.success == False,
                AuditEvent.created_at >= start_date
            )
        ).scalar()

        # Get total events
        total_events = audit_service.db.query(func.count(AuditEvent.id)).filter(
            and_(
                AuditEvent.organization_id == organization_id,
                AuditEvent.created_at >= start_date
            )
        ).scalar()

        # Get open security incidents
        open_incidents = audit_service.db.query(func.count(SecurityIncident.id)).filter(
            and_(
                SecurityIncident.organization_id == organization_id,
                SecurityIncident.status == "open"
            )
        ).scalar()

        dashboard_data = {
            "period_days": days,
            "total_events": total_events or 0,
            "failed_events": failed_events or 0,
            "success_rate": ((total_events - failed_events) / total_events * 100) if total_events > 0 else 100,
            "open_incidents": open_incidents or 0,
            "event_types": {et.event_type: et.count for et in event_types},
            "severity_breakdown": {sb.severity: sb.count for sb in severity_breakdown},
            "recent_events": [event.to_dict() for event in recent_events[:10]]
        }

        return dashboard_data

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve compliance dashboard data"
        )