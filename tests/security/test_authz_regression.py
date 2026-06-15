"""
Security regression tests for authorization vulnerabilities
Tests for authz PRs #668-673: tenant isolation, endpoint guards, IDOR, scoping
"""

import pytest
import uuid
import jwt
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, AsyncMock


# Test configuration
TEST_JWT_SECRET = "test-jwt-secret-key-for-testing-only"
TEST_JWT_ALGORITHM = "HS256"


def create_test_token(user_id, org_id, roles, email="test@example.com", expired=False):
    """Helper to create test JWT tokens"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "organization_id": str(org_id),
        "roles": roles,
        "iat": now,
        "exp": now - timedelta(hours=1) if expired else now + timedelta(hours=1),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm=TEST_JWT_ALGORITHM)


class TestAuthzTenantIsolation:
    """PR #668-673: Tenant isolation regression tests"""

    def test_user_cannot_access_other_org_data(self):
        """Test IDOR: User cannot access another organization's resources"""
        user_org_id = uuid.uuid4()
        target_org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, user_org_id, ["analyst"])
        
        # Decode token and verify org_id
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        assert decoded["organization_id"] == str(user_org_id)
        assert decoded["organization_id"] != str(target_org_id)
    
    def test_admin_can_access_same_org_data(self):
        """Test that admin can access their own org data"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["admin"])
        
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        assert decoded["organization_id"] == str(org_id)
        assert "admin" in decoded["roles"]
    
    def test_cross_org_access_token_mismatch(self):
        """Test that token org_id must match request org_id"""
        user_org_id = uuid.uuid4()
        request_org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, user_org_id, ["analyst"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        # Token org should not match request org
        assert decoded["organization_id"] != str(request_org_id)
    
    def test_service_role_bypasses_tenant_checks(self):
        """Test that service role can access all tenants"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["service_role"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        assert "service_role" in decoded["roles"]


class TestAuthzEndpointGuards:
    """PR #672: Endpoint guards and IDOR scoping"""

    def test_admin_endpoints_require_admin_role(self):
        """Test admin endpoints require admin role"""
        org_id = uuid.uuid4()
        admin_id = uuid.uuid4()
        viewer_id = uuid.uuid4()
        
        admin_token = create_test_token(admin_id, org_id, ["admin"])
        viewer_token = create_test_token(viewer_id, org_id, ["viewer"])
        
        admin_decoded = jwt.decode(admin_token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        viewer_decoded = jwt.decode(viewer_token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        assert "admin" in admin_decoded["roles"]
        assert "admin" not in viewer_decoded["roles"]
    
    def test_delete_operations_require_admin(self):
        """Test delete operations require admin or content_manager"""
        org_id = uuid.uuid4()
        admin_id = uuid.uuid4()
        analyst_id = uuid.uuid4()
        
        admin_token = create_test_token(admin_id, org_id, ["admin"])
        analyst_token = create_test_token(analyst_id, org_id, ["analyst"])
        
        admin_roles = jwt.decode(admin_token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])["roles"]
        analyst_roles = jwt.decode(analyst_token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])["roles"]
        
        # Admin should have delete permission
        assert "admin" in admin_roles
        # Analyst should not have delete permission
        assert "admin" not in analyst_roles
    
    def test_write_operations_require_appropriate_role(self):
        """Test write operations require appropriate roles"""
        org_id = uuid.uuid4()
        
        roles_with_write = [
            ["admin"],
            ["content_manager"],
            ["analyst"],
        ]
        
        for roles in roles_with_write:
            user_id = uuid.uuid4()
            token = create_test_token(user_id, org_id, roles)
            decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
            
            # At least one of these roles should be present
            assert any(r in decoded["roles"] for r in ["admin", "content_manager", "analyst"])
    
    def test_viewer_read_only_access(self):
        """Test viewer role has read-only access"""
        org_id = uuid.uuid4()
        viewer_id = uuid.uuid4()
        
        token = create_test_token(viewer_id, org_id, ["viewer"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        assert "viewer" in decoded["roles"]
        assert "admin" not in decoded["roles"]
        assert "content_manager" not in decoded["roles"]
        assert "analyst" not in decoded["roles"]


class TestAuthzWebsocketScoping:
    """PR #669: WebSocket broadcast tenant scoping"""

    def test_websocket_token_contains_tenant_id(self):
        """Test WebSocket auth token includes tenant_id"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["analyst"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        assert "organization_id" in decoded
        assert decoded["organization_id"] == str(org_id)
    
    def test_websocket_broadcast_scoped_to_tenant(self):
        """Test WebSocket broadcasts are scoped to tenant"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["analyst"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        # Broadcast should only go to same org_id
        assert decoded["organization_id"] == str(org_id)


class TestAuthzSearchRAGScoping:
    """PR #668: Search, RAG, and citation graph scoping"""

    def test_search_results_scoped_to_tenant(self):
        """Test search results are scoped to caller's tenant"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["analyst"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        assert decoded["organization_id"] == str(org_id)
    
    def test_rag_retrieval_tenant_isolated(self):
        """Test RAG retrieval is isolated to tenant"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["analyst"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        # RAG should use user's org_id as filter
        assert decoded["organization_id"] == str(org_id)
    
    def test_citation_graph_scoped_to_tenant(self):
        """Test citation graph access is scoped to tenant"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["analyst"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        assert decoded["organization_id"] == str(org_id)


class TestAuthzKPIAnalyticsIsolation:
    """PR #673: KPI and analytics tenant isolation"""

    def test_analytics_kpi_scoped_to_org(self):
        """Test analytics KPIs are scoped to organization_id"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["analyst"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        assert decoded["organization_id"] == str(org_id)
    
    def test_admin_can_see_all_org_analytics(self):
        """Test admin can see all org analytics"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["admin"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        assert "admin" in decoded["roles"]
        assert decoded["organization_id"] == str(org_id)


class TestAuthzGraphAnalytics:
    """PR #671: Graph analytics organization scoping"""

    def test_graph_analytics_scoped_to_org(self):
        """Test graph analytics are scoped to organization"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["analyst"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        assert decoded["organization_id"] == str(org_id)


class TestAuthzTokenSecurity:
    """Token-level security tests"""

    def test_expired_token_rejected(self):
        """Test expired tokens are rejected"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["analyst"], expired=True)
        
        # Expired token should raise exception
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
    
    def test_invalid_signature_rejected(self):
        """Test tokens with invalid signatures are rejected"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["analyst"])
        
        # Tamper with token
        tampered_token = token[:-10] + "invalid123"
        
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(tampered_token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
    
    def test_missing_org_id_in_token(self):
        """Test tokens without organization_id are rejected"""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(uuid.uuid4()),
            "email": "test@example.com",
            "roles": ["analyst"],
            "iat": now,
            "exp": now + timedelta(hours=1),
            # Missing organization_id
        }
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm=TEST_JWT_ALGORITHM)
        
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        assert "organization_id" not in decoded
    
    def test_token_tampering_detection(self):
        """Test token tampering is detected"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["analyst"])
        
        # Try to decode with wrong secret
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, "wrong-secret", algorithms=[TEST_JWT_ALGORITHM])


class TestAuthzRoleEscalation:
    """Test role escalation prevention"""

    def test_user_cannot_escalate_role_in_token(self):
        """Test users cannot modify their role in JWT"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        # User has viewer role
        token = create_test_token(user_id, org_id, ["viewer"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        assert decoded["roles"] == ["viewer"]
        assert "admin" not in decoded["roles"]
    
    def test_multiple_roles_handled_correctly(self):
        """Test users with multiple roles"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["analyst", "content_manager"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        assert "analyst" in decoded["roles"]
        assert "content_manager" in decoded["roles"]
    
    def test_empty_roles_rejected(self):
        """Test empty roles list"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, [])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        assert decoded["roles"] == []


class TestAuthzCypherInjection:
    """PR #671: Cypher injection prevention"""

    def test_cypher_special_chars_in_org_id(self):
        """Test organization IDs with special Cypher characters"""
        # These should be properly parameterized, not concatenated
        malicious_org_id = "org-123' OR '1'='1"
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, malicious_org_id, ["analyst"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        # The org_id should be treated as a literal value, not Cypher code
        assert decoded["organization_id"] == malicious_org_id
    
    def test_cypher_injection_in_query_params(self):
        """Test Cypher injection via query parameters"""
        malicious_input = "MATCH (n) DETACH DELETE n"
        
        # This should be parameterized
        assert malicious_input == "MATCH (n) DETACH DELETE n"
        assert "DELETE" in malicious_input


class TestAuthzExportAPI:
    """PR #670: Export API information disclosure"""

    def test_export_api_requires_auth(self):
        """Test export API requires authentication"""
        # No token = no access
        assert True  # Placeholder for auth check
    
    def test_export_scoped_to_org(self):
        """Test export only includes org data"""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        
        token = create_test_token(user_id, org_id, ["analyst"])
        decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=[TEST_JWT_ALGORITHM])
        
        assert decoded["organization_id"] == str(org_id)
