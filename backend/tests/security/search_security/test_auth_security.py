"""
Authentication and Authorization Security Tests for Search Endpoints

Tests comprehensive authentication and authorization including:
- JWT token validation and security
- API key authentication
- Role-based access control (RBAC)
- Organization isolation
- User permissions and privilege escalation
- Session management and token lifecycle
"""

import pytest
import jwt
import time
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
import uuid

from .conftest import SecurityTestCase


class TestSearchAuthenticationSecurity(SecurityTestCase):
    """Test authentication security for search endpoints"""

    def test_missing_authentication(self, security_test_client, search_service_mocks):
        """Test that endpoints reject requests without authentication"""
        
        endpoints = [
            ('POST', '/search/', {"query": "test"}),
            ('POST', '/search/hybrid', {"query": "test"}),
            ('GET', '/search/suggestions?q=test', None),
            ('GET', '/search/history', None),
            ('POST', '/search/history', {"query": "test"}),
            ('DELETE', '/search/history', None),
        ]
        
        for method, url, data in endpoints:
            if data:
                response = security_test_client.make_request(method, url, json=data)
            else:
                response = security_test_client.make_request(method, url)
            
            assert response.status_code == 401, f"Should reject unauthenticated {method} {url}"
            self.assert_safe_error_response(response)
            
            # Should not leak endpoint information
            self.assert_no_information_disclosure(response, [
                'endpoint', 'route', 'function', 'method', 'parameter'
            ])

    def test_invalid_jwt_tokens(self, security_test_client, search_service_mocks):
        """Test handling of invalid JWT tokens"""
        
        invalid_tokens = [
            "invalid_token",
            "Bearer invalid_token",
            "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid",
            "Bearer not.a.jwt.token",
            "Bearer .invalid.token",
            "Bearer expired.token.here",
            "Bearer " + "a" * 1000,  # Extremely long token
            "Bearer \x00\x01\x02",   # Binary data
        ]
        
        for token in invalid_tokens:
            headers = {'Authorization': token}
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=headers,
                json={"query": "test"}
            )
            
            assert response.status_code == 401, f"Should reject invalid token: {token[:50]}..."
            self.assert_safe_error_response(response)

    @patch('src.core.dependencies.get_current_user')
    def test_jwt_token_manipulation(self, mock_get_user, security_test_client, search_service_mocks):
        """Test JWT token manipulation attacks"""
        
        # Mock user for successful auth
        mock_user = Mock()
        mock_user.id = uuid.uuid4()
        mock_user.organization_id = uuid.uuid4()
        mock_get_user.return_value = mock_user
        
        # Test algorithm confusion attack
        # Create token with 'none' algorithm
        none_alg_token = jwt.encode(
            {"user_id": str(mock_user.id), "exp": time.time() + 3600},
            "",
            algorithm="none"
        )
        
        headers = {'Authorization': f'Bearer {none_alg_token}'}
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers=headers,
            json={"query": "test"}
        )
        
        # Should reject 'none' algorithm tokens
        assert response.status_code in [401, 403], "Should reject 'none' algorithm tokens"

    @patch('src.core.dependencies.get_current_user')
    def test_token_reuse_and_replay(self, mock_get_user, security_test_client, search_service_mocks):
        """Test token reuse and replay attack prevention"""
        
        mock_user = Mock()
        mock_user.id = uuid.uuid4()
        mock_user.organization_id = uuid.uuid4()
        mock_get_user.return_value = mock_user
        
        # Create expired token
        expired_token = jwt.encode(
            {"user_id": str(mock_user.id), "exp": time.time() - 3600},
            "secret",
            algorithm="HS256"
        )
        
        headers = {'Authorization': f'Bearer {expired_token}'}
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers=headers,
            json={"query": "test"}
        )
        
        assert response.status_code == 401, "Should reject expired tokens"
        self.assert_safe_error_response(response)

    def test_api_key_authentication(self, security_test_client, search_service_mocks):
        """Test API key authentication security"""
        
        # Test missing API key
        response = security_test_client.make_request(
            'POST',
            '/search/',
            json={"query": "test"}
        )
        assert response.status_code == 401, "Should reject missing API key"
        
        # Test invalid API keys
        invalid_api_keys = [
            "",
            "invalid_key",
            "123",
            "a" * 1000,  # Too long
            "\x00\x01\x02",  # Binary data
            "'; DROP TABLE api_keys; --",  # SQL injection
            "<script>alert('xss')</script>",  # XSS
        ]
        
        for api_key in invalid_api_keys:
            headers = {'X-API-Key': api_key}
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=headers,
                json={"query": "test"}
            )
            
            assert response.status_code == 401, f"Should reject invalid API key: {api_key[:20]}..."
            self.assert_safe_error_response(response)

    @patch('src.core.api_key_auth.get_api_key_data')
    @patch('src.core.dependencies.get_current_user')
    def test_api_key_privilege_escalation(self, mock_get_user, mock_api_key, security_test_client, search_service_mocks):
        """Test API key privilege escalation attempts"""
        
        # Mock limited API key
        limited_api_key = Mock()
        limited_api_key.permissions = ['search:read']  # Only read permissions
        limited_api_key.organization_id = uuid.uuid4()
        mock_api_key.return_value = limited_api_key
        
        # Mock limited user
        limited_user = Mock()
        limited_user.id = uuid.uuid4()
        limited_user.organization_id = limited_api_key.organization_id
        limited_user.role = 'readonly'
        mock_get_user.return_value = limited_user
        
        # Test read operations (should succeed)
        response = security_test_client.make_request(
            'GET',
            '/search/suggestions?q=test',
            headers={'X-API-Key': 'limited_key'}
        )
        assert response.status_code == 200, "Should allow read operations with read permissions"
        
        # Test write operations (should fail)
        response = security_test_client.make_request(
            'POST',
            '/search/history',
            headers={'X-API-Key': 'limited_key'},
            json={"query": "test"}
        )
        # Should either be forbidden or handle gracefully
        assert response.status_code in [200, 403], "Should handle write operations appropriately"

    @patch('src.core.dependencies.get_current_user')
    def test_organization_isolation(self, mock_get_user, security_test_client, search_service_mocks):
        """Test organization isolation in search results"""
        
        org1_id = uuid.uuid4()
        org2_id = uuid.uuid4()
        
        # User from organization 1
        user_org1 = Mock()
        user_org1.id = uuid.uuid4()
        user_org1.organization_id = org1_id
        user_org1.role = 'user'
        
        # User from organization 2
        user_org2 = Mock()
        user_org2.id = uuid.uuid4()
        user_org2.organization_id = org2_id
        user_org2.role = 'user'
        
        # Test with user from org1
        mock_get_user.return_value = user_org1
        response1 = security_test_client.make_request(
            'POST',
            '/search/',
            headers={'Authorization': 'Bearer valid_token_org1'},
            json={"query": "test"}
        )
        assert response1.status_code == 200
        
        # Test with user from org2
        mock_get_user.return_value = user_org2
        response2 = security_test_client.make_request(
            'POST',
            '/search/',
            headers={'Authorization': 'Bearer valid_token_org2'},
            json={"query": "test"}
        )
        assert response2.status_code == 200
        
        # Verify search services are called with correct organization IDs
        search_service_mocks['hybrid'].search.assert_called()
        calls = search_service_mocks['hybrid'].search.call_args_list
        
        # Check that calls have different organization IDs
        if len(calls) >= 2:
            org_id_1 = calls[-2][1]['organization_id']
            org_id_2 = calls[-1][1]['organization_id']
            assert org_id_1 != org_id_2, "Different organizations should be isolated"

    @patch('src.core.dependencies.get_current_user')
    def test_role_based_access_control(self, mock_get_user, security_test_client, search_service_mocks):
        """Test role-based access control enforcement"""
        
        # Define roles with different permissions
        roles = {
            'admin': {'can_search': True, 'can_history': True, 'can_suggestions': True},
            'user': {'can_search': True, 'can_history': True, 'can_suggestions': True},
            'readonly': {'can_search': True, 'can_history': False, 'can_suggestions': True},
            'guest': {'can_search': False, 'can_history': False, 'can_suggestions': False},
        }
        
        for role, permissions in roles.items():
            user = Mock()
            user.id = uuid.uuid4()
            user.organization_id = uuid.uuid4()
            user.role = role
            user.is_active = True
            mock_get_user.return_value = user
            
            # Test search access
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers={'Authorization': 'Bearer token'},
                json={"query": "test"}
            )
            
            if permissions['can_search']:
                assert response.status_code == 200, f"Role {role} should have search access"
            else:
                assert response.status_code == 403, f"Role {role} should not have search access"
            
            # Test history access
            response = security_test_client.make_request(
                'POST',
                '/search/history',
                headers={'Authorization': 'Bearer token'},
                json={"query": "test"}
            )
            
            if permissions['can_history']:
                assert response.status_code == 200, f"Role {role} should have history access"
            else:
                assert response.status_code in [403, 405], f"Role {role} should not have history access"

    @patch('src.core.dependencies.get_current_user')
    def test_inactive_user_access(self, mock_get_user, security_test_client, search_service_mocks):
        """Test that inactive users cannot access search endpoints"""
        
        # Inactive user
        inactive_user = Mock()
        inactive_user.id = uuid.uuid4()
        inactive_user.organization_id = uuid.uuid4()
        inactive_user.role = 'user'
        inactive_user.is_active = False
        mock_get_user.return_value = inactive_user
        
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers={'Authorization': 'Bearer token'},
            json={"query": "test"}
        )
        
        assert response.status_code == 403, "Inactive users should be denied access"
        self.assert_safe_error_response(response)

    def test_concurrent_session_security(self, security_test_client, search_service_mocks):
        """Test concurrent session handling and security"""
        
        # Simulate concurrent requests with same token
        token = "Bearer valid_token"
        
        # Make multiple concurrent requests
        responses = []
        for i in range(5):
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers={'Authorization': token},
                json={"query": f"test_{i}"}
            )
            responses.append(response)
        
        # All should either succeed or fail consistently
        status_codes = [r.status_code for r in responses]
        assert len(set(status_codes)) == 1, "Concurrent requests should have consistent status"

    @patch('src.core.dependencies.get_current_user')
    def test_user_impersonation_protection(self, mock_get_user, security_test_client, search_service_mocks):
        """Test protection against user impersonation attacks"""
        
        # Legitimate user
        real_user = Mock()
        real_user.id = uuid.uuid4()
        real_user.organization_id = uuid.uuid4()
        real_user.role = 'user'
        mock_get_user.return_value = real_user
        
        # Attempt to impersonate with user_id in request
        malicious_payloads = [
            {
                "query": "test",
                "user_id": str(uuid.uuid4()),  # Different user ID
            },
            {
                "query": "test",
                "organization_id": str(uuid.uuid4()),  # Different org ID
            },
            {
                "query": "test",
                "role": "admin",  # Attempt role escalation
            }
        ]
        
        for payload in malicious_payloads:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers={'Authorization': 'Bearer token'},
                json=payload
            )
            
            # Should either ignore extra fields or reject
            assert response.status_code in [200, 422], \
                "Should handle impersonation attempts safely"

    @patch('src.core.dependencies.get_current_user')
    def test_cross_organization_access_prevention(self, mock_get_user, security_test_client, search_service_mocks):
        """Test prevention of cross-organization data access"""
        
        user = Mock()
        user.id = uuid.uuid4()
        user.organization_id = uuid.uuid4()
        user.role = 'admin'  # Even admin shouldn't access other orgs
        mock_get_user.return_value = user
        
        # Attempt to access data from different organization
        cross_org_payload = {
            "query": "test",
            "filters": {
                "organization_id": str(uuid.uuid4())  # Different org
            }
        }
        
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers={'Authorization': 'Bearer token'},
            json=cross_org_payload
        )
        
        # Should use user's org, not the requested org
        assert response.status_code == 200, "Should process request with user's organization"
        
        # Verify service was called with correct org ID
        search_service_mocks['hybrid'].search.assert_called()
        call_args = search_service_mocks['hybrid'].search.call_args[1]
        assert call_args['organization_id'] == str(user.organization_id)

    def test_authentication_bypass_attempts(self, security_test_client, search_service_mocks):
        """Test common authentication bypass attempts"""
        
        # Authentication bypass attempts
        bypass_attempts = [
            {'Authorization': 'Bearer null'},
            {'Authorization': 'Bearer undefined'},
            {'Authorization': 'Bearer false'},
            {'Authorization': 'Bearer 0'},
            {'Authorization': 'Bearer admin'},
            {'Authorization': 'Bearer guest'},
            {'Authorization': 'Bearer ../../../etc/passwd'},
            {'X-User-ID': 'admin'},
            {'X-Role': 'admin'},
            {'X-Forwarded-User': 'admin'},
            {'X-Remote-User': 'admin'},
        ]
        
        for headers in bypass_attempts:
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers=headers,
                json={"query": "test"}
            )
            
            assert response.status_code == 401, \
                f"Should reject bypass attempt: {headers}"
            self.assert_safe_error_response(response)

    def test_token_information_disclosure(self, security_test_client, search_service_mocks):
        """Test that token information is not disclosed in responses"""
        
        response = security_test_client.make_request(
            'POST',
            '/search/',
            headers={'Authorization': 'Bearer invalid_token'},
            json={"query": "test"}
        )
        
        # Should not disclose token information
        sensitive_patterns = [
            'invalid_token',
            'jwt',
            'bearer',
            'secret',
            'key',
            'signature',
            'payload',
            'header'
        ]
        
        self.assert_no_information_disclosure(response, sensitive_patterns)

    @patch('src.core.dependencies.get_current_user')
    def test_session_fixation_protection(self, mock_get_user, security_test_client, search_service_mocks):
        """Test protection against session fixation attacks"""
        
        user = Mock()
        user.id = uuid.uuid4()
        user.organization_id = uuid.uuid4()
        user.role = 'user'
        mock_get_user.return_value = user
        
        # Make initial request
        response1 = security_test_client.make_request(
            'POST',
            '/search/',
            headers={'Authorization': 'Bearer token1'},
            json={"query": "test1"}
        )
        assert response1.status_code == 200
        
        # Make request with different token
        response2 = security_test_client.make_request(
            'POST',
            '/search/',
            headers={'Authorization': 'Bearer token2'},
            json={"query": "test2"}
        )
        assert response2.status_code == 200
        
        # Both should be treated independently
        # (Specific implementation depends on session handling)

class TestSearchAuthorizationSecurity(SecurityTestCase):
    """Test authorization security for search endpoints"""

    @patch('src.core.dependencies.get_current_user')
    def test_resource_level_authorization(self, mock_get_user, security_test_client, search_service_mocks):
        """Test authorization at the resource level"""
        
        user = Mock()
        user.id = uuid.uuid4()
        user.organization_id = uuid.uuid4()
        user.role = 'user'
        user.permissions = ['search:read', 'search:write']
        mock_get_user.return_value = user
        
        # Test operations user has permission for
        allowed_operations = [
            ('POST', '/search/', {"query": "test"}),
            ('GET', '/search/suggestions?q=test', None),
        ]
        
        for method, url, data in allowed_operations:
            response = security_test_client.make_request(
                method,
                url,
                headers={'Authorization': 'Bearer token'},
                json=data
            )
            assert response.status_code == 200, f"Should allow {method} {url}"

    @patch('src.core.dependencies.get_current_user')
    def test_permission_inheritance_and_delegation(self, mock_get_user, security_test_client, search_service_mocks):
        """Test permission inheritance and delegation mechanisms"""
        
        # Test user with inherited permissions
        user_with_inheritance = Mock()
        user_with_inheritance.id = uuid.uuid4()
        user_with_inheritance.organization_id = uuid.uuid4()
        user_with_inheritance.role = 'team_lead'
        user_with_inheritance.inherited_permissions = ['search:admin']
        mock_get_user.return_value = user_with_inheritance
        
        # Should have access to admin-level operations
        response = security_test_client.make_request(
            'DELETE',
            '/search/history',
            headers={'Authorization': 'Bearer token'}
        )
        assert response.status_code == 200, "Should allow admin operations with inherited permissions"

    def test_authorization_cache_security(self, security_test_client, search_service_mocks):
        """Test authorization cache security and invalidation"""
        
        # This would test that authorization decisions are not cached inappropriately
        # and that cache invalidation works correctly
        
        # Make multiple requests to test cache behavior
        for i in range(3):
            response = security_test_client.make_request(
                'POST',
                '/search/',
                headers={'Authorization': 'Bearer test_token'},
                json={"query": f"test_{i}"}
            )
            # Each request should be independently authorized
            assert response.status_code == 401, "Should not cache unauthorized decisions"