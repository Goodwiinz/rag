"""
Test API key authentication security for public endpoints
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
import json

from src.main import app
from src.core.api_key_auth import APIKey, generate_api_key
from src.core.database import get_db


client = TestClient(app)


class TestAPIKeyAuthentication:
    """Test API key authentication functionality"""
    
    def setup_method(self):
        """Setup test data"""
        self.valid_api_key, self.valid_key_hash = generate_api_key()
        self.invalid_api_key = "rag_invalid_key_123456789"
        self.expired_api_key, self.expired_key_hash = generate_api_key()
        
        # Mock database API key records
        self.valid_api_key_record = {
            "id": "test-key-id",
            "name": "Test API Key",
            "key_hash": self.valid_key_hash,
            "key_prefix": self.valid_api_key[:8],
            "is_active": True,
            "rate_limit_per_hour": 100,
            "expires_at": None,
            "usage_count": 0,
            "last_used_at": None
        }
        
        self.expired_api_key_record = {
            "id": "expired-key-id",
            "name": "Expired API Key",
            "key_hash": self.expired_key_hash,
            "key_prefix": self.expired_api_key[:8],
            "is_active": True,
            "rate_limit_per_hour": 100,
            "expires_at": datetime.now(timezone.utc) - timedelta(days=1),  # Expired yesterday
            "usage_count": 0,
            "last_used_at": None
        }

    @patch('src.core.api_key_auth.get_db')
    def test_valid_api_key_authentication(self, mock_get_db):
        """Test successful authentication with valid API key"""
        # Mock database response
        mock_db = mock_get_db.return_value
        mock_db.query.return_value.filter.return_value.first.return_value = type('APIKey', (), self.valid_api_key_record)
        
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": f"Bearer {self.valid_api_key}"},
            json={
                "query": "test search",
                "search_type": "HYBRID",
                "limit": 10
            }
        )
        
        # Should succeed (or fail for other reasons, not auth)
        assert response.status_code != 401
        assert response.status_code != 403

    def test_missing_api_key(self):
        """Test request without API key"""
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            json={
                "query": "test search",
                "search_type": "HYBRID",
                "limit": 10
            }
        )
        
        assert response.status_code == 403  # Missing auth header

    def test_invalid_api_key_format(self):
        """Test request with invalid API key format"""
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": "Bearer invalid_format"},
            json={
                "query": "test search",
                "search_type": "HYBRID",
                "limit": 10
            }
        )
        
        assert response.status_code == 401

    @patch('src.core.api_key_auth.get_db')
    def test_nonexistent_api_key(self, mock_get_db):
        """Test request with API key not in database"""
        # Mock database to return None (key not found)
        mock_db = mock_get_db.return_value
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": f"Bearer {self.invalid_api_key}"},
            json={
                "query": "test search",
                "search_type": "HYBRID",
                "limit": 10
            }
        )
        
        assert response.status_code == 401

    @patch('src.core.api_key_auth.get_db')
    def test_expired_api_key(self, mock_get_db):
        """Test request with expired API key"""
        # Mock database response with expired key
        mock_db = mock_get_db.return_value
        mock_db.query.return_value.filter.return_value.first.return_value = type('APIKey', (), self.expired_api_key_record)
        
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": f"Bearer {self.expired_api_key}"},
            json={
                "query": "test search",
                "search_type": "HYBRID",
                "limit": 10
            }
        )
        
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    @patch('src.core.api_key_auth.get_db')
    @patch('src.core.api_key_auth.api_key_auth')
    def test_rate_limit_enforcement(self, mock_auth, mock_get_db):
        """Test rate limiting for API keys"""
        # Mock database response
        mock_db = mock_get_db.return_value
        mock_db.query.return_value.filter.return_value.first.return_value = type('APIKey', (), self.valid_api_key_record)
        
        # Mock rate limiter to return False (rate limit exceeded)
        mock_auth.check_rate_limit.return_value = False
        mock_auth.get_current_usage.return_value = 101  # Over limit
        
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": f"Bearer {self.valid_api_key}"},
            json={
                "query": "test search",
                "search_type": "HYBRID",
                "limit": 10
            }
        )
        
        assert response.status_code == 429  # Too Many Requests
        assert "rate limit" in response.json()["detail"].lower()

    @patch('src.core.api_key_auth.get_db')
    def test_inactive_api_key(self, mock_get_db):
        """Test request with inactive API key"""
        # Create inactive key record
        inactive_key_record = self.valid_api_key_record.copy()
        inactive_key_record["is_active"] = False
        
        # Mock database response
        mock_db = mock_get_db.return_value
        mock_db.query.return_value.filter.return_value.first.return_value = type('APIKey', (), inactive_key_record)
        
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": f"Bearer {self.valid_api_key}"},
            json={
                "query": "test search",
                "search_type": "HYBRID",
                "limit": 10
            }
        )
        
        assert response.status_code == 401

    def test_old_public_endpoint_removed(self):
        """Test that old public endpoint is no longer accessible"""
        # Try the old vulnerable endpoint
        response = client.post(
            "/api/v1/search/public/hybrid",
            json={
                "query": "test search",
                "search_type": "HYBRID",
                "limit": 10
            }
        )
        
        # Should return 404 Not Found since endpoint no longer exists
        assert response.status_code == 404

    @patch('src.core.api_key_auth.get_db')
    def test_health_check_authentication(self, mock_get_db):
        """Test health check endpoint requires authentication"""
        # Mock database response
        mock_db = mock_get_db.return_value
        mock_db.query.return_value.filter.return_value.first.return_value = type('APIKey', (), self.valid_api_key_record)
        
        # Test authenticated health check
        response = client.get(
            "/api/v1/search/authenticated/health",
            headers={"Authorization": f"Bearer {self.valid_api_key}"}
        )
        
        # Should succeed (or fail for other reasons, not auth)
        assert response.status_code != 401
        assert response.status_code != 403

    def test_health_check_without_auth(self):
        """Test health check fails without authentication"""
        # Try old public health endpoint
        response = client.get("/api/v1/search/public/health")
        assert response.status_code == 404  # Endpoint removed
        
        # Try authenticated endpoint without auth
        response = client.get("/api/v1/search/authenticated/health")
        assert response.status_code == 403  # Missing auth header


class TestAPIKeyManagement:
    """Test API key management endpoints"""
    
    @patch('src.core.dependencies.get_current_user')
    @patch('src.core.api_key_auth.get_db')
    def test_create_api_key_admin_only(self, mock_get_db, mock_user):
        """Test API key creation requires admin role"""
        # Mock admin user
        mock_admin = type('User', (), {
            'id': 'admin-user-id',
            'email': 'admin@test.com',
            'role': type('Role', (), {'value': 'admin'}),
            'has_permission': lambda role: True
        })
        mock_user.return_value = mock_admin
        
        # Mock database
        mock_db = mock_get_db.return_value
        
        response = client.post(
            "/api/v1/api-keys/",
            headers={"Authorization": "Bearer admin-token"},
            json={
                "name": "Test API Key",
                "description": "Test key for security testing",
                "rate_limit_per_hour": 50
            }
        )
        
        # Should succeed for admin
        assert response.status_code in [200, 201]

    @patch('src.core.dependencies.get_current_user')
    def test_create_api_key_non_admin_denied(self, mock_user):
        """Test API key creation denied for non-admin users"""
        # Mock non-admin user
        mock_user_obj = type('User', (), {
            'id': 'user-id',
            'email': 'user@test.com',
            'role': type('Role', (), {'value': 'user'}),
            'has_permission': lambda role: False
        })
        mock_user.return_value = mock_user_obj
        
        response = client.post(
            "/api/v1/api-keys/",
            headers={"Authorization": "Bearer user-token"},
            json={
                "name": "Test API Key",
                "description": "Unauthorized attempt",
                "rate_limit_per_hour": 50
            }
        )
        
        # Should be denied
        assert response.status_code == 403


class TestSecurityLogging:
    """Test security-related logging functionality"""
    
    @patch('src.core.api_key_auth.get_db')
    @patch('src.api.search.search.logger')
    def test_api_access_logging(self, mock_logger, mock_get_db):
        """Test that API access is properly logged"""
        # Mock database response
        mock_db = mock_get_db.return_value
        valid_key, valid_hash = generate_api_key()
        api_key_record = {
            "id": "test-key-id",
            "name": "Test Key",
            "key_hash": valid_hash,
            "key_prefix": valid_key[:8],
            "is_active": True,
            "rate_limit_per_hour": 100,
            "expires_at": None,
            "usage_count": 0,
            "last_used_at": None
        }
        mock_db.query.return_value.filter.return_value.first.return_value = type('APIKey', (), api_key_record)
        
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": f"Bearer {valid_key}"},
            json={
                "query": "test security logging",
                "search_type": "HYBRID",
                "limit": 5
            }
        )
        
        # Verify logging was called
        assert mock_logger.info.called

    @patch('src.core.api_key_auth.get_db')  
    @patch('src.api.search.search.logger')
    def test_failed_auth_logging(self, mock_logger, mock_get_db):
        """Test that failed authentication attempts are logged"""
        # Mock database to return None (key not found)
        mock_db = mock_get_db.return_value
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        response = client.post(
            "/api/v1/search/authenticated/hybrid",
            headers={"Authorization": "Bearer invalid_key"},
            json={
                "query": "unauthorized attempt",
                "search_type": "HYBRID",
                "limit": 5
            }
        )
        
        # Should log the failed attempt
        assert response.status_code == 401
        # Note: Actual logging verification would depend on implementation


class TestVulnerabilityRegression:
    """Test that original vulnerability is fixed"""
    
    def test_public_search_blocked(self):
        """Ensure public search without authentication is blocked"""
        # All these should fail without proper API key
        test_cases = [
            "/api/v1/search/public/hybrid",
            "/api/v1/search/public/health",
        ]
        
        for endpoint in test_cases:
            response = client.post(endpoint, json={"query": "test"})
            assert response.status_code == 404, f"Endpoint {endpoint} should not exist"
    
    def test_data_isolation_with_api_key(self):
        """Test that API key access doesn't bypass organization isolation inappropriately"""
        # This would need to be implemented based on the actual business logic
        # for how API keys should handle cross-organization access
        pass
    
    def test_no_anonymous_access(self):
        """Verify no endpoints allow anonymous access to search functionality"""
        search_endpoints = [
            "/api/v1/search/",
            "/api/v1/search/hybrid",
            "/api/v1/search/authenticated/hybrid",
        ]
        
        for endpoint in search_endpoints:
            # Test without any authentication
            response = client.post(endpoint, json={"query": "test"})
            # Should require authentication
            assert response.status_code in [401, 403, 422], f"Endpoint {endpoint} allows anonymous access"


if __name__ == "__main__":
    pytest.main([__file__])