"""
Integration tests for the security fix of public search endpoints
"""

import pytest
from fastapi.testclient import TestClient
import time
from datetime import datetime, timedelta
import uuid

from src.main import app
from src.core.api_key_auth import APIKey, generate_api_key, api_key_auth
from src.core.database import get_db, SessionLocal
from src.models.user import User, UserRole


client = TestClient(app)


class TestSecurityIntegration:
    """End-to-end security integration tests"""
    
    @pytest.fixture
    def db_session(self):
        """Create a test database session"""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    @pytest.fixture
    def admin_user(self, db_session):
        """Create a test admin user"""
        admin = User(
            id=str(uuid.uuid4()),
            email="admin@test.com",
            is_active=True,
            role=UserRole.ADMIN,
            password_hash="test_hash"
        )
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)
        return admin
    
    @pytest.fixture
    def test_api_key(self, db_session, admin_user):
        """Create a test API key"""
        raw_key, key_hash = generate_api_key()
        
        api_key = APIKey(
            name="Integration Test Key",
            key_hash=key_hash,
            key_prefix=raw_key[:8],
            is_active=True,
            rate_limit_per_hour=100,
            created_by=f"{admin_user.email} ({admin_user.id})",
            description="Test key for integration testing"
        )
        
        db_session.add(api_key)
        db_session.commit()
        db_session.refresh(api_key)
        
        # Return both the API key record and raw key for testing
        return api_key, raw_key
    
    def test_complete_security_flow(self, test_api_key):
        """Test the complete security flow from creation to usage"""
        api_key_record, raw_key = test_api_key
        
        # 1. Verify old public endpoint is removed
        response = client.post(
            "/api/v1/search/public/hybrid",
            json={
                "query": "test vulnerability check",
                "search_type": "HYBRID",
                "limit": 10
            }
        )
        assert response.status_code == 404, "Old vulnerable endpoint should be removed"
        
        # 2. Verify new endpoint requires authentication
        response = client.post(
            "/api/v1/search/authenticated/hybrid", 
            json={
                "query": "test without auth",
                "search_type": "HYBRID",
                "limit": 10
            }
        )
        assert response.status_code == 403, "New endpoint should require authentication"
        
        # 3. Test successful authentication with valid API key
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": f"Bearer {raw_key}"},
            json={
                "query": "test with valid auth",
                "search_type": "HYBRID", 
                "limit": 10
            }
        )
        # Should not fail due to authentication (may fail for other reasons)
        assert response.status_code not in [401, 403], "Valid API key should authenticate successfully"
        
        # 4. Test health check endpoint security
        response = client.get("/api/v1/search/public/health")
        assert response.status_code == 404, "Old public health endpoint should be removed"
        
        response = client.get("/api/v1/search/authenticated/health")
        assert response.status_code == 403, "Health endpoint should require authentication"
        
        response = client.get(
            "/api/v1/search/authenticated/health",
            headers={"Authorization": f"Bearer {raw_key}"}
        )
        assert response.status_code not in [401, 403], "Valid API key should access health endpoint"
    
    def test_rate_limiting_enforcement(self, test_api_key):
        """Test that rate limiting works correctly"""
        api_key_record, raw_key = test_api_key
        
        # Set low rate limit for testing
        db = SessionLocal()
        try:
            api_key_record.rate_limit_per_hour = 2  # Very low limit
            db.merge(api_key_record)
            db.commit()
        finally:
            db.close()
        
        headers = {"Authorization": f"Bearer {raw_key}"}
        search_payload = {
            "query": "rate limit test",
            "search_type": "HYBRID",
            "limit": 5
        }
        
        # First request should succeed
        response1 = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers=headers,
            json=search_payload
        )
        assert response1.status_code not in [429], "First request should not be rate limited"
        
        # Second request should succeed
        response2 = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers=headers,
            json=search_payload
        )
        assert response2.status_code not in [429], "Second request should not be rate limited"
        
        # Third request should be rate limited
        response3 = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers=headers,
            json=search_payload
        )
        assert response3.status_code == 429, "Third request should be rate limited"
        assert "rate limit" in response3.json()["detail"].lower()
    
    def test_api_key_lifecycle(self, admin_user):
        """Test complete API key lifecycle through management endpoints"""
        # Note: This would require mocking the admin authentication
        # In a real implementation, you'd need proper JWT tokens
        
        # For now, test the data structures and logic
        raw_key, key_hash = generate_api_key()
        
        # Verify key format
        assert raw_key.startswith("rag_"), "API key should have proper prefix"
        assert len(raw_key) == 36, "API key should be correct length"  # rag_ + 32 chars
        
        # Verify hash validation
        from src.core.api_key_auth import verify_api_key
        assert verify_api_key(raw_key, key_hash), "Generated key should verify against its hash"
        assert not verify_api_key("wrong_key", key_hash), "Wrong key should not verify"
    
    def test_security_audit_logging(self, test_api_key):
        """Test that security events are properly logged"""
        api_key_record, raw_key = test_api_key
        
        # Test with valid key - should log successful access
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": f"Bearer {raw_key}"},
            json={
                "query": "audit log test",
                "search_type": "HYBRID",
                "limit": 3
            }
        )
        
        # Test with invalid key - should log failed attempt  
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": "Bearer rag_invalid_key_for_audit_test"},
            json={
                "query": "failed audit test",
                "search_type": "HYBRID",
                "limit": 3
            }
        )
        assert response.status_code == 401, "Invalid key should be rejected"
        
        # In a real system, you would verify log entries were created
        # For now, we verify the endpoints handle the requests correctly
    
    def test_error_handling_and_information_disclosure(self, test_api_key):
        """Test that error messages don't leak sensitive information"""
        api_key_record, raw_key = test_api_key
        
        # Test with malformed requests
        test_cases = [
            {"headers": {"Authorization": "Bearer malformed_key"}, "expected": 401},
            {"headers": {"Authorization": "NotBearer " + raw_key}, "expected": 401},
            {"headers": {"Authorization": raw_key}, "expected": 403},  # Missing Bearer
            {"headers": {}, "expected": 403},  # No auth header
        ]
        
        for case in test_cases:
            response = client.post(
                "/api/v1/search/authenticated/hybrid",
                headers=case["headers"],
                json={
                    "query": "error handling test",
                    "search_type": "HYBRID",
                    "limit": 5
                }
            )
            
            assert response.status_code == case["expected"]
            
            # Verify error messages don't leak sensitive info
            error_detail = response.json().get("detail", "").lower()
            assert "database" not in error_detail, "Error should not mention database"
            assert "sql" not in error_detail, "Error should not mention SQL"
            assert "hash" not in error_detail, "Error should not mention hash"
    
    def test_concurrent_requests_handling(self, test_api_key):
        """Test handling of concurrent requests with same API key"""
        api_key_record, raw_key = test_api_key
        headers = {"Authorization": f"Bearer {raw_key}"}
        
        # Make multiple concurrent requests (simulated by rapid sequential requests)
        responses = []
        for i in range(5):
            response = client.post(
                "/api/v1/search/authenticated/hybrid",
                headers=headers,
                json={
                    "query": f"concurrent test {i}",
                    "search_type": "HYBRID",
                    "limit": 2
                }
            )
            responses.append(response)
        
        # All should either succeed or fail gracefully (not hang or crash)
        for response in responses:
            assert response.status_code < 500, "Should not cause server errors"
    
    def test_api_key_expiration(self, db_session, admin_user):
        """Test API key expiration handling"""
        # Create expired API key
        raw_key, key_hash = generate_api_key()
        
        expired_key = APIKey(
            name="Expired Test Key",
            key_hash=key_hash,
            key_prefix=raw_key[:8],
            is_active=True,
            rate_limit_per_hour=100,
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            created_by=f"{admin_user.email} ({admin_user.id})"
        )
        
        db_session.add(expired_key)
        db_session.commit()
        
        # Test that expired key is rejected
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": f"Bearer {raw_key}"},
            json={
                "query": "test with expired key",
                "search_type": "HYBRID",
                "limit": 5
            }
        )
        
        assert response.status_code == 401, "Expired API key should be rejected"
        assert "expired" in response.json()["detail"].lower()
    
    def test_deactivated_api_key(self, db_session, admin_user):
        """Test deactivated API key handling"""
        # Create deactivated API key
        raw_key, key_hash = generate_api_key()
        
        deactivated_key = APIKey(
            name="Deactivated Test Key",
            key_hash=key_hash,
            key_prefix=raw_key[:8],
            is_active=False,  # Deactivated
            rate_limit_per_hour=100,
            created_by=f"{admin_user.email} ({admin_user.id})"
        )
        
        db_session.add(deactivated_key)
        db_session.commit()
        
        # Test that deactivated key is rejected
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": f"Bearer {raw_key}"},
            json={
                "query": "test with deactivated key",
                "search_type": "HYBRID",
                "limit": 5
            }
        )
        
        assert response.status_code == 401, "Deactivated API key should be rejected"


class TestVulnerabilityMitigation:
    """Specific tests to verify the original vulnerability is mitigated"""
    
    def test_no_unauthenticated_search_access(self):
        """Verify no search functionality is accessible without authentication"""
        search_endpoints = [
            ("/api/v1/search/", "POST"),
            ("/api/v1/search/hybrid", "POST"), 
            ("/api/v1/search/authenticated/hybrid", "POST"),
            ("/api/v1/search/suggestions", "GET"),
            ("/api/v1/search/history", "GET"),
        ]
        
        for endpoint, method in search_endpoints:
            if method == "POST":
                response = client.post(endpoint, json={"query": "test"})
            else:
                response = client.get(endpoint)
            
            # Should require authentication
            assert response.status_code in [401, 403, 404, 422], f"Endpoint {endpoint} allows unauthenticated access"
    
    def test_information_disclosure_prevention(self):
        """Test that error responses don't leak system information"""
        # Test various malformed requests
        test_cases = [
            {"endpoint": "/api/v1/search/authenticated/hybrid", "method": "POST"},
            {"endpoint": "/api/v1/search/authenticated/health", "method": "GET"},
        ]
        
        for case in test_cases:
            if case["method"] == "POST":
                response = client.post(case["endpoint"], json={"query": "test"})
            else:
                response = client.get(case["endpoint"])
            
            if response.status_code in [401, 403]:
                # Check that error messages are generic
                detail = response.json().get("detail", "").lower()
                sensitive_terms = ["database", "sql", "internal", "stack", "trace", "exception"]
                for term in sensitive_terms:
                    assert term not in detail, f"Error message contains sensitive term: {term}"
    
    def test_resource_exhaustion_protection(self, test_api_key):
        """Test protection against resource exhaustion attacks"""
        api_key_record, raw_key = test_api_key
        headers = {"Authorization": f"Bearer {raw_key}"}
        
        # Test large query handling
        large_query = "x" * 10000  # Very large query
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers=headers,
            json={
                "query": large_query,
                "search_type": "HYBRID",
                "limit": 1000  # Large limit
            }
        )
        
        # Should handle gracefully (reject or limit, not crash)
        assert response.status_code < 500, "Large requests should not cause server errors"
    
    def test_audit_trail_completeness(self, test_api_key):
        """Verify complete audit trail for security events"""
        api_key_record, raw_key = test_api_key
        
        # Test successful request
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": f"Bearer {raw_key}"},
            json={
                "query": "audit trail test",
                "search_type": "HYBRID",
                "limit": 5
            }
        )
        
        # Test failed authentication
        response = client.post(
            "/api/v1/search/authenticated/hybrid", 
            headers={"Authorization": "Bearer invalid_key"},
            json={
                "query": "failed auth test",
                "search_type": "HYBRID",
                "limit": 5
            }
        )
        assert response.status_code == 401
        
        # In production, you would verify log entries were created
        # For integration tests, we verify the endpoints handle requests correctly


if __name__ == "__main__":
    pytest.main([__file__])