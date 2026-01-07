"""
Security Tests for Critical Security Fixes

Tests for:
1. WebSocket authentication security (JWT tokens not in URL)
2. SQL injection prevention via enum validation
3. CORS configuration
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import WebSocket
from fastapi.testclient import TestClient

from src.core.websocket_auth import WebSocketAuthenticator, WebSocketAuthError
from src.shared.enums import (
    DocumentSortField,
    SortOrder,
    EntitySortField,
    JobSortField,
    validate_sort_field,
    SORT_FIELD_MAPPINGS,
)
from src.core.config import Settings


class TestWebSocketAuthentication:
    """Tests for secure WebSocket authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_with_bearer_header(self):
        """Test authentication via Authorization header."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.headers = {
            "authorization": "Bearer test-jwt-token-12345"
        }
        mock_websocket.cookies = {}

        with patch("src.core.websocket_auth.jwt.decode") as mock_decode:
            mock_decode.return_value = {
                "sub": "user123",
                "organization_id": "org123",
                "exp": 9999999999,
            }

            result = await WebSocketAuthenticator.authenticate(mock_websocket)

            assert result["sub"] == "user123"
            assert result["organization_id"] == "org123"
            mock_decode.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_with_subprotocol(self):
        """Test authentication via Sec-WebSocket-Protocol header."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.headers = {
            "sec-websocket-protocol": "auth, test-jwt-token-subprotocol"
        }
        mock_websocket.cookies = {}

        with patch("src.core.websocket_auth.jwt.decode") as mock_decode:
            mock_decode.return_value = {
                "sub": "user456",
                "organization_id": "org456",
            }

            result = await WebSocketAuthenticator.authenticate(mock_websocket)

            assert result["sub"] == "user456"
            mock_decode.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_with_cookie(self):
        """Test authentication via cookie (fallback)."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.headers = {}
        mock_websocket.cookies = {"access_token": "test-cookie-token"}

        with patch("src.core.websocket_auth.jwt.decode") as mock_decode:
            mock_decode.return_value = {
                "sub": "user789",
                "organization_id": "org789",
            }

            result = await WebSocketAuthenticator.authenticate(mock_websocket)

            assert result["sub"] == "user789"

    @pytest.mark.asyncio
    async def test_authenticate_no_token_raises_error(self):
        """Test that missing token raises WebSocketAuthError."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.headers = {}
        mock_websocket.cookies = {}

        with pytest.raises(WebSocketAuthError) as exc_info:
            await WebSocketAuthenticator.authenticate(mock_websocket)

        assert exc_info.value.code == 4001
        assert "No authentication token" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_authenticate_expired_token_raises_error(self):
        """Test that expired token raises WebSocketAuthError."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.headers = {
            "authorization": "Bearer expired-token"
        }
        mock_websocket.cookies = {}

        with patch("src.core.websocket_auth.jwt.decode") as mock_decode:
            from jwt import ExpiredSignatureError
            mock_decode.side_effect = ExpiredSignatureError("Token expired")

            with pytest.raises(WebSocketAuthError) as exc_info:
                await WebSocketAuthenticator.authenticate(mock_websocket)

            assert exc_info.value.code == 4002
            assert "expired" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_authenticate_invalid_token_raises_error(self):
        """Test that invalid token raises WebSocketAuthError."""
        mock_websocket = MagicMock(spec=WebSocket)
        mock_websocket.headers = {
            "authorization": "Bearer invalid-token"
        }
        mock_websocket.cookies = {}

        with patch("src.core.websocket_auth.jwt.decode") as mock_decode:
            from jwt import InvalidTokenError
            mock_decode.side_effect = InvalidTokenError("Invalid token")

            with pytest.raises(WebSocketAuthError) as exc_info:
                await WebSocketAuthenticator.authenticate(mock_websocket)

            assert exc_info.value.code == 4003


class TestSQLInjectionPrevention:
    """Tests for SQL injection prevention via enum validation."""

    def test_document_sort_field_valid_values(self):
        """Test that DocumentSortField only allows safe values."""
        valid_fields = [
            "created_at",
            "updated_at",
            "title",
            "filename",
            "file_size_bytes",
            "processing_status",
            "document_type",
        ]

        for field in valid_fields:
            assert DocumentSortField(field).value == field

    def test_document_sort_field_rejects_injection(self):
        """Test that DocumentSortField rejects SQL injection attempts."""
        injection_attempts = [
            "created_at; DROP TABLE documents; --",
            "title OR 1=1",
            "filename' UNION SELECT * FROM users --",
            "invalid_field",
            "*",
            "1",
            "",
        ]

        for attempt in injection_attempts:
            with pytest.raises(ValueError):
                DocumentSortField(attempt)

    def test_sort_order_valid_values(self):
        """Test that SortOrder only allows asc/desc."""
        assert SortOrder("asc") == SortOrder.ASC
        assert SortOrder("desc") == SortOrder.DESC

    def test_sort_order_rejects_injection(self):
        """Test that SortOrder rejects SQL injection attempts."""
        injection_attempts = [
            "asc; DROP TABLE documents; --",
            "ASC",  # Case sensitive
            "DESC",
            "ascending",
            "",
        ]

        for attempt in injection_attempts:
            with pytest.raises(ValueError):
                SortOrder(attempt)

    def test_validate_sort_field_function(self):
        """Test the validate_sort_field utility function."""
        # Valid fields
        assert validate_sort_field("Document", "created_at") is True
        assert validate_sort_field("Document", "title") is True
        assert validate_sort_field("Entity", "name") is True
        assert validate_sort_field("ProcessingJob", "status") is True

        # Invalid fields
        assert validate_sort_field("Document", "invalid_field") is False
        assert validate_sort_field("Document", "DROP TABLE") is False
        assert validate_sort_field("UnknownModel", "created_at") is False

    def test_sort_field_mappings_completeness(self):
        """Test that all expected models have sort field mappings."""
        expected_models = ["Document", "Entity", "ProcessingJob", "User", "Organization"]

        for model in expected_models:
            assert model in SORT_FIELD_MAPPINGS
            assert len(SORT_FIELD_MAPPINGS[model]) > 0


class TestCORSConfiguration:
    """Tests for CORS configuration security."""

    def test_cors_origins_list_parsing(self):
        """Test CORS origins are properly parsed from comma-separated string."""
        settings = Settings(
            CORS_ORIGINS="http://localhost:3000,http://example.com,https://secure.com"
        )

        origins = settings.cors_origins_list
        assert "http://localhost:3000" in origins
        assert "http://example.com" in origins
        assert "https://secure.com" in origins
        assert len(origins) == 3

    def test_cors_default_origins(self):
        """Test that default CORS origins are set for development."""
        settings = Settings()

        origins = settings.cors_origins_list
        # Should have localhost:3000 as default
        assert any("localhost:3000" in origin for origin in origins)

    def test_cors_allowed_headers_not_wildcard(self):
        """Test that CORS headers are not using wildcard."""
        settings = Settings()

        headers = settings.cors_headers_list
        # Should have specific headers, not wildcard
        assert "*" not in headers
        assert "Authorization" in headers
        assert "Content-Type" in headers

    def test_cors_allowed_methods_not_wildcard(self):
        """Test that CORS methods are not using wildcard."""
        settings = Settings()

        methods = settings.cors_methods_list
        # Should have specific methods, not wildcard
        assert "*" not in methods
        assert "GET" in methods
        assert "POST" in methods
        assert "DELETE" in methods

    def test_cors_max_age_reasonable(self):
        """Test that CORS max age is set to a reasonable value."""
        settings = Settings()

        # Should be set (not None/0) but not excessively long
        assert settings.CORS_MAX_AGE > 0
        assert settings.CORS_MAX_AGE <= 86400 * 7  # No more than 7 days


class TestSecretKeyValidation:
    """Tests for secret key validation."""

    def test_secret_key_rejects_weak_values_in_production(self):
        """Test that weak secret keys are rejected in production."""
        import os

        original_env = os.environ.get("ENVIRONMENT")
        try:
            os.environ["ENVIRONMENT"] = "production"

            with pytest.raises(ValueError) as exc_info:
                Settings(SECRET_KEY="change-in-production")

            assert "strong value" in str(exc_info.value).lower()
        finally:
            if original_env:
                os.environ["ENVIRONMENT"] = original_env
            else:
                os.environ.pop("ENVIRONMENT", None)

    def test_secret_key_minimum_length(self):
        """Test that secret keys must meet minimum length."""
        with pytest.raises(ValueError) as exc_info:
            Settings(SECRET_KEY="short")

        assert "32 characters" in str(exc_info.value)

    def test_jwt_secret_key_validation(self):
        """Test that JWT secret keys are validated similarly."""
        import os

        original_env = os.environ.get("ENVIRONMENT")
        try:
            os.environ["ENVIRONMENT"] = "production"

            with pytest.raises(ValueError):
                Settings(JWT_SECRET_KEY="jwt-secret-weak")
        finally:
            if original_env:
                os.environ["ENVIRONMENT"] = original_env
            else:
                os.environ.pop("ENVIRONMENT", None)


class TestWebSocketAuthError:
    """Tests for WebSocketAuthError exception class."""

    def test_error_with_custom_code(self):
        """Test WebSocketAuthError with custom error code."""
        error = WebSocketAuthError("Custom error", code=4100)

        assert error.message == "Custom error"
        assert error.code == 4100
        assert str(error) == "Custom error"

    def test_error_default_code(self):
        """Test WebSocketAuthError with default error code."""
        error = WebSocketAuthError("Default code error")

        assert error.code == 4001


# Integration-style tests (would require test fixtures)
class TestAPISecurityIntegration:
    """Integration tests for API security (requires app context)."""

    @pytest.mark.skip(reason="Requires full app context with database")
    def test_documents_api_sort_field_validation(self):
        """Test that documents API validates sort_by field."""
        # This would test the actual API endpoint
        pass

    @pytest.mark.skip(reason="Requires full app context")
    def test_websocket_rejects_token_in_query_params(self):
        """Test that WebSocket endpoint doesn't accept token in query params."""
        # This would test the actual WebSocket endpoint
        pass
