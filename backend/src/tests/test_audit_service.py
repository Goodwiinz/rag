"""
Comprehensive tests for audit and compliance service
Tests audit logging, compliance reporting, and security monitoring
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from src.services.audit_service import AuditService, log_audit_event
from src.models.audit import (
    AuditEvent, ComplianceReport, SecurityIncident, DataRetentionPolicy,
    AuditEventType, AuditSeverity
)
from src.models.user import User
from src.models.organization import Organization
from src.exceptions.analytics_exceptions import ConfigurationException


class TestAuditService:
    """Test audit service functionality"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.count.return_value = 0
        db.add = Mock()
        db.commit = Mock()
        db.flush = Mock()
        db.refresh = Mock()
        db.rollback = Mock()
        db.delete = Mock()
        return db

    @pytest.fixture
    def audit_service(self, mock_db):
        """Create audit service instance"""
        return AuditService(mock_db)

    @pytest.fixture
    def mock_organization(self):
        """Create mock organization"""
        org = Mock(spec=Organization)
        org.id = "org-123"
        org.name = "Test Organization"
        return org

    @pytest.fixture
    def mock_user(self):
        """Create mock user"""
        user = Mock(spec=User)
        user.id = "user-123"
        user.email = "test@example.com"
        user.first_name = "Test"
        user.last_name = "User"
        return user

    def test_log_event_success(self, audit_service, mock_db):
        """Test successful audit event logging"""
        event_data = {
            "event_type": AuditEventType.USER_LOGIN,
            "action": "User login",
            "user_id": "user-123",
            "organization_id": "org-123",
            "success": True,
            "severity": AuditSeverity.LOW
        }

        event = audit_service.log_event(**event_data)

        assert event is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_log_event_with_context(self, audit_service, mock_db):
        """Test audit event logging with automatic context"""
        with patch('src.services.audit_service.get_current_user_id', return_value="user-123"), \
             patch('src.services.audit_service.get_current_tenant_id', return_value="org-123"):

            event = audit_service.log_event(
                event_type=AuditEventType.DOCUMENT_ACCESS,
                action="Document access",
                details={"document_id": "doc-123"}
            )

        assert event is not None
        assert event.user_id == "user-123"
        assert event.organization_id == "org-123"

    def test_log_event_with_enum_conversion(self, audit_service, mock_db):
        """Test audit event logging with enum to string conversion"""
        event = audit_service.log_event(
            event_type=AuditEventType.USER_LOGIN,
            action="Test login",
            user_id="user-123",
            organization_id="org-123",
            severity=AuditSeverity.MEDIUM
        )

        assert event is not None
        assert event.event_type == AuditEventType.USER_LOGIN.value
        assert event.severity == AuditSeverity.MEDIUM.value

    def test_log_user_login_success(self, audit_service, mock_db):
        """Test successful user login logging"""
        event = audit_service.log_user_login(
            user_id="user-123",
            organization_id="org-123",
            success=True,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0"
        )

        assert event is not None
        assert event.event_type == AuditEventType.USER_LOGIN.value
        assert event.success is True
        assert event.severity == AuditSeverity.LOW.value
        assert event.ip_address == "192.168.1.1"
        assert event.user_agent == "Mozilla/5.0"

    def test_log_user_login_failed(self, audit_service, mock_db):
        """Test failed user login logging"""
        event = audit_service.log_user_login(
            user_id="user-123",
            organization_id="org-123",
            success=False,
            error_message="Invalid credentials"
        )

        assert event is not None
        assert event.event_type == AuditEventType.USER_LOGIN_FAILED.value
        assert event.success is False
        assert event.error_message == "Invalid credentials"
        assert event.severity == AuditSeverity.MEDIUM.value

    def test_log_user_logout(self, audit_service, mock_db):
        """Test user logout logging"""
        event = audit_service.log_user_logout(
            user_id="user-123",
            organization_id="org-123",
            session_id="session-123"
        )

        assert event is not None
        assert event.event_type == AuditEventType.USER_LOGOUT.value
        assert event.session_id == "session-123"

    def test_log_document_access(self, audit_service, mock_db):
        """Test document access logging"""
        event = audit_service.log_document_access(
            user_id="user-123",
            organization_id="org-123",
            document_id="doc-123",
            action="view"
        )

        assert event is not None
        assert event.event_type == AuditEventType.DOCUMENT_ACCESS.value
        assert event.resource_type == "document"
        assert event.resource_id == "doc-123"

    def test_log_search_query(self, audit_service, mock_db):
        """Test search query logging"""
        event = audit_service.log_search_query(
            user_id="user-123",
            organization_id="org-123",
            query="test query",
            result_count=10
        )

        assert event is not None
        assert event.event_type == AuditEventType.SEARCH_QUERY.value
        assert event.details["query"] == "test query"
        assert event.details["result_count"] == 10

    def test_log_security_event(self, audit_service, mock_db):
        """Test security event logging"""
        event = audit_service.log_security_event(
            event_type=AuditEventType.ACCESS_VIOLATION,
            description="Unauthorized access attempt",
            organization_id="org-123",
            user_id="user-123",
            severity=AuditSeverity.HIGH,
            ip_address="192.168.1.1"
        )

        assert event is not None
        assert event.event_type == AuditEventType.ACCESS_VIOLATION.value
        assert event.severity == AuditSeverity.HIGH.value
        assert event.action == "Unauthorized access attempt"

    def test_get_audit_events_basic(self, audit_service, mock_db):
        """Test getting audit events with basic filtering"""
        mock_event = Mock(spec=AuditEvent)
        mock_event.to_dict.return_value = {"id": "event-123"}
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_event]

        events = audit_service.get_audit_events(
            organization_id="org-123",
            limit=10,
            offset=0
        )

        assert len(events) == 1
        assert events[0].to_dict() == {"id": "event-123"}

    def test_get_audit_events_with_filters(self, audit_service, mock_db):
        """Test getting audit events with multiple filters"""
        mock_event = Mock(spec=AuditEvent)
        mock_event.to_dict.return_value = {"id": "event-123"}
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_event]

        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc)

        events = audit_service.get_audit_events(
            organization_id="org-123",
            event_types=[AuditEventType.USER_LOGIN.value],
            user_id="user-123",
            severity=AuditSeverity.LOW.value,
            success=True,
            start_date=start_date,
            end_date=end_date,
            limit=10,
            offset=0
        )

        assert len(events) == 1
        # Verify multiple filter calls
        assert mock_db.query.return_value.filter.call_count >= 4

    def test_get_user_activity_summary(self, audit_service, mock_db):
        """Test getting user activity summary"""
        # Mock total events count
        mock_db.query.return_value.filter.return_value.scalar.return_value = 100

        # Mock failed events count
        mock_db.query.return_value.filter.return_value.scalar.return_value = 5

        # Mock event types
        mock_event_type = Mock()
        mock_event_type.event_type = AuditEventType.USER_LOGIN.value
        mock_event_type.count = 50
        mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = [mock_event_type]

        # Mock recent events
        mock_recent_event = Mock(spec=AuditEvent)
        mock_recent_event.to_dict.return_value = {"id": "recent-123"}
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_recent_event]

        summary = audit_service.get_user_activity_summary(
            organization_id="org-123",
            user_id="user-123",
            days=30
        )

        assert summary["period_days"] == 30
        assert summary["total_events"] == 100
        assert summary["failed_events"] == 5
        assert summary["success_rate"] == 95.0
        assert len(summary["event_types"]) == 1
        assert len(summary["recent_activity"]) == 1

    def test_create_compliance_report_success(self, audit_service, mock_db):
        """Test successful compliance report creation"""
        with patch.object(audit_service, '_generate_compliance_data') as mock_generate:
            mock_report = Mock(spec=ComplianceReport)
            mock_report.id = "report-123"
            mock_report.to_dict.return_value = {"id": "report-123"}
            mock_db.add.return_value = None
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None

            mock_generate.return_value = None

            report = audit_service.create_compliance_report(
                organization_id="org-123",
                report_type="security_summary",
                report_name="Monthly Security Report",
                period_start=datetime.now(timezone.utc) - timedelta(days=30),
                period_end=datetime.now(timezone.utc),
                generated_by="user-123"
            )

        assert report is not None

    def test_generate_security_summary(self, audit_service, mock_db):
        """Test security summary report generation"""
        # Mock security events
        mock_security_event = Mock(spec=AuditEvent)
        mock_security_event.to_dict.return_value = {"id": "event-123", "severity": "high"}
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_security_event]

        # Mock login statistics
        mock_db.query.return_value.filter.return_value.scalar.side_effect = [100, 5]  # successful, failed

        # Mock active users
        mock_db.query.return_value.filter.return_value.scalar.return_value = 20

        mock_report = Mock(spec=ComplianceReport)
        mock_report.organization_id = "org-123"
        mock_report.period_start = datetime.now(timezone.utc) - timedelta(days=30)
        mock_report.period_end = datetime.now(timezone.utc)

        result = audit_service._generate_security_summary(
            org_id="org-123",
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc)
        )

        assert "data" in result
        assert "metrics" in result
        assert "summary" in result
        assert result["metrics"]["total_security_events"] == 1
        assert result["metrics"]["successful_logins"] == 100
        assert result["metrics"]["failed_logins"] == 5

    def test_generate_access_audit(self, audit_service, mock_db):
        """Test access audit report generation"""
        # Mock access events
        mock_access_event = Mock(spec=AuditEvent)
        mock_access_event.to_dict.return_value = {"id": "access-123"}
        mock_access_event.success = True
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_access_event]

        # Mock violations
        mock_db.query.return_value.filter.return_value.all.return_value = []

        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        end_date = datetime.now(timezone.utc)

        result = audit_service._generate_access_audit(
            org_id="org-123",
            start_date=start_date,
            end_date=end_date
        )

        assert "data" in result
        assert "metrics" in result
        assert "summary" in result
        assert result["metrics"]["total_access_events"] == 1
        assert result["metrics"]["access_violations"] == 0

    def test_generate_data_retention_report(self, audit_service, mock_db):
        """Test data retention report generation"""
        # Mock export events
        mock_export_event = Mock(spec=AuditEvent)
        mock_export_event.to_dict.return_value = {"id": "export-123", "details": {"file_size": 1024}}
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_export_event]

        # Mock privacy requests
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = audit_service._generate_data_retention_report(
            org_id="org-123",
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc)
        )

        assert "data" in result
        assert "metrics" in result
        assert "summary" in result
        assert result["metrics"]["data_exports"] == 1
        assert result["metrics"]["privacy_requests"] == 0

    def test_create_security_incident_success(self, audit_service, mock_db):
        """Test successful security incident creation"""
        with patch('src.services.audit_service.uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.hex = "test1234567890abcdef"

            mock_incident = Mock(spec=SecurityIncident)
            mock_incident.id = "incident-123"
            mock_incident.to_dict.return_value = {"id": "incident-123"}
            mock_db.add.return_value = None
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None

            with patch.object(audit_service, 'log_security_event') as mock_log:
                incident = audit_service.create_security_incident(
                    organization_id="org-123",
                    title="Test Incident",
                    description="Test security incident",
                    severity="high",
                    category="unauthorized_access"
                )

        assert incident is not None
        mock_log.assert_called_once()

    def test_get_security_incidents_basic(self, audit_service, mock_db):
        """Test getting security incidents with basic filtering"""
        mock_incident = Mock(spec=SecurityIncident)
        mock_incident.to_dict.return_value = {"id": "incident-123"}
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_incident]

        incidents = audit_service.get_security_incidents(
            organization_id="org-123",
            limit=10,
            offset=0
        )

        assert len(incidents) == 1
        assert incidents[0].to_dict() == {"id": "incident-123"}

    def test_get_security_incidents_with_filters(self, audit_service, mock_db):
        """Test getting security incidents with filters"""
        mock_incident = Mock(spec=SecurityIncident)
        mock_incident.to_dict.return_value = {"id": "incident-123"}
        mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_incident]

        incidents = audit_service.get_security_incidents(
            organization_id="org-123",
            status="open",
            severity="high",
            category="unauthorized_access",
            limit=10,
            offset=0
        )

        assert len(incidents) == 1
        # Verify multiple filter calls
        assert mock_db.query.return_value.filter.call_count >= 3

    def test_cleanup_old_audit_events(self, audit_service, mock_db):
        """Test cleanup of old audit events"""
        # Mock count query
        mock_db.query.return_value.filter.return_value.scalar.return_value = 1000

        # Mock delete query
        mock_db.query.return_value.filter.return_value.delete.return_value = 1000

        deleted_count = audit_service.cleanup_old_audit_events(retention_days=365)

        assert deleted_count == 1000
        mock_db.commit.assert_called_once()

    def test_cleanup_old_audit_events_error(self, audit_service, mock_db):
        """Test cleanup error handling"""
        mock_db.query.return_value.filter.return_value.delete.side_effect = Exception("Database error")

        deleted_count = audit_service.cleanup_old_audit_events(retention_days=365)

        assert deleted_count == 0
        mock_db.rollback.assert_called_once()

    def test_log_event_database_error(self, audit_service, mock_db):
        """Test audit event logging with database error"""
        mock_db.add.side_effect = Exception("Database error")

        with pytest.raises(Exception):
            audit_service.log_event(
                event_type=AuditEventType.USER_LOGIN,
                action="Test login",
                user_id="user-123",
                organization_id="org-123"
            )

        mock_db.rollback.assert_called_once()

    def test_context_manager(self, mock_db):
        """Test audit service as context manager"""
        with AuditService(mock_db) as audit:
            assert audit.db == mock_db

        mock_db.close.assert_called_once()


class TestAuditUtilityFunctions:
    """Test audit utility functions"""

    def test_log_audit_event_success(self):
        """Test log_audit_event utility function"""
        with patch('src.services.audit_service.AuditService') as mock_audit_class:
            mock_audit = Mock()
            mock_event = Mock()
            mock_audit.log_event.return_value = mock_event
            mock_audit_class.return_value.__enter__.return_value = mock_audit

            result = log_audit_event(
                event_type=AuditEventType.USER_LOGIN,
                action="Test login",
                user_id="user-123",
                organization_id="org-123"
            )

        assert result == mock_event
        mock_audit.log_event.assert_called_once_with(
            event_type=AuditEventType.USER_LOGIN,
            action="Test login",
            user_id="user-123",
            organization_id="org-123"
        )


class TestAuditIntegration:
    """Integration tests for audit system"""

    def test_end_to_end_audit_workflow(self):
        """Test complete audit workflow from logging to retrieval"""
        with patch('src.services.audit_service.AuditService') as mock_audit_class:
            mock_audit = Mock()
            mock_event = Mock()
            mock_event.to_dict.return_value = {
                "id": "event-123",
                "event_type": AuditEventType.USER_LOGIN.value,
                "user_id": "user-123",
                "organization_id": "org-123"
            }
            mock_audit.log_event.return_value = mock_event
            mock_audit.get_audit_events.return_value = [mock_event]
            mock_audit_class.return_value.__enter__.return_value = mock_audit

            # Log event
            event = mock_audit.log_event(
                event_type=AuditEventType.USER_LOGIN,
                action="User login",
                user_id="user-123",
                organization_id="org-123"
            )

            # Retrieve events
            events = mock_audit.get_audit_events(
                organization_id="org-123",
                event_types=[AuditEventType.USER_LOGIN.value]
            )

        assert event is not None
        assert len(events) == 1
        assert events[0].to_dict()["event_type"] == AuditEventType.USER_LOGIN.value

    def test_compliance_report_generation_workflow(self):
        """Test compliance report generation workflow"""
        with patch('src.services.audit_service.AuditService') as mock_audit_class:
            mock_audit = Mock()
            mock_report = Mock()
            mock_report.id = "report-123"
            mock_report.to_dict.return_value = {"id": "report-123"}
            mock_audit.create_compliance_report.return_value = mock_report
            mock_audit_class.return_value.__enter__.return_value = mock_audit

            # Create report
            report = mock_audit.create_compliance_report(
                organization_id="org-123",
                report_type="security_summary",
                report_name="Monthly Report",
                period_start=datetime.now(timezone.utc) - timedelta(days=30),
                period_end=datetime.now(timezone.utc),
                generated_by="user-123"
            )

        assert report is not None
        assert report.to_dict()["id"] == "report-123"

    def test_security_incident_workflow(self):
        """Test security incident workflow"""
        with patch('src.services.audit_service.AuditService') as mock_audit_class:
            mock_audit = Mock()
            mock_incident = Mock()
            mock_incident.id = "incident-123"
            mock_incident.to_dict.return_value = {"id": "incident-123"}
            mock_audit.create_security_incident.return_value = mock_incident
            mock_audit.get_security_incidents.return_value = [mock_incident]
            mock_audit_class.return_value.__enter__.return_value = mock_audit

            # Create incident
            incident = mock_audit.create_security_incident(
                organization_id="org-123",
                title="Security Incident",
                description="Test incident",
                severity="high",
                category="unauthorized_access"
            )

            # Retrieve incidents
            incidents = mock_audit.get_security_incidents(
                organization_id="org-123",
                severity="high"
            )

        assert incident is not None
        assert len(incidents) == 1
        assert incidents[0].to_dict()["id"] == "incident-123"


if __name__ == "__main__":
    pytest.main([__file__])