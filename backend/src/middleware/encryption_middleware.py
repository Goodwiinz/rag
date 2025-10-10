"""
Encryption middleware for automatic request/response encryption.

This middleware provides:
- Automatic encryption of sensitive request data
- Response data filtering and masking
- Encryption context management
- Security headers for encrypted communication
"""

import json
import logging
from typing import Dict, Any, Optional, List, Callable
from fastapi import Request, Response, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..core.encryption import get_field_encryption, EncryptionError
from ..services.encryption_service import EncryptionService
from ..core.database import get_db

logger = logging.getLogger(__name__)


class EncryptionMiddleware(BaseHTTPMiddleware):
    """
    Middleware for handling encryption in HTTP requests and responses.

    Features:
    - Automatic encryption of sensitive request fields
    - Response data masking for PII
    - Security headers for encrypted communication
    - Request context tracking for encryption operations
    """

    def __init__(
        self,
        app,
        encrypt_request_fields: bool = True,
        mask_response_fields: bool = True,
        sensitive_fields: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None
    ):
        super().__init__(app)
        self.encrypt_request_fields = encrypt_request_fields
        self.mask_response_fields = mask_response_fields
        self.sensitive_fields = sensitive_fields or [
            'ssn', 'social_security_number', 'tax_id', 'credit_card',
            'bank_account', 'password', 'secret', 'token', 'api_key',
            'email_personal', 'phone_home', 'address', 'birth_date'
        ]
        self.exclude_paths = exclude_paths or [
            '/health', '/metrics', '/docs', '/openapi.json', '/favicon.ico'
        ]

        # Field patterns for automatic detection
        self.sensitive_patterns = [
            'ssn', 'social_security', 'tax_id', 'ein', 'credit_card',
            'bank_account', 'routing', 'password', 'secret', 'token',
            'api_key', 'private_key', 'certificate', 'passport',
            'driver_license', 'birth_date', 'email', 'phone', 'address'
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and apply encryption logic"""

        # Skip encryption for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            response = await call_next(request)
            return response

        # Store original request for encryption context
        encryption_context = {
            'request_id': self._generate_request_id(),
            'user_id': None,
            'organization_id': None,
            'ip_address': request.client.host if request.client else None,
            'user_agent': request.headers.get('user-agent'),
            'encrypted_fields': [],
            'masked_fields': []
        }

        # Process request encryption if enabled
        if self.encrypt_request_fields and request.method in ['POST', 'PUT', 'PATCH']:
            request = await self._process_request_encryption(request, encryption_context)

        # Process the request
        response = await call_next(request)

        # Process response masking if enabled
        if self.mask_response_fields and response.headers.get('content-type', '').startswith('application/json'):
            response = await self._process_response_masking(response, encryption_context)

        # Add security headers
        response = self._add_security_headers(response, encryption_context)

        return response

    async def _process_request_encryption(
        self,
        request: Request,
        context: Dict[str, Any]
    ) -> Request:
        """Process and encrypt sensitive fields in request body"""

        try:
            # Read request body
            body = await request.body()

            if not body:
                return request

            # Parse JSON body
            try:
                request_data = json.loads(body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return request  # Not JSON, skip encryption

            # Identify and encrypt sensitive fields
            encrypted_data = self._encrypt_sensitive_fields(request_data, context)

            # If data was encrypted, update request body
            if context['encrypted_fields']:
                encrypted_body = json.dumps(encrypted_data).encode('utf-8')

                # Create new request with encrypted body
                request._body = encrypted_body

                logger.debug(f"Encrypted {len(context['encrypted_fields'])} fields in request")

            return request

        except Exception as e:
            logger.error(f"Error processing request encryption: {str(e)}")
            return request

    def _encrypt_sensitive_fields(
        self,
        data: Dict[str, Any],
        context: Dict[str, Any],
        field_path: str = ""
    ) -> Dict[str, Any]:
        """Recursively encrypt sensitive fields in data"""

        if isinstance(data, dict):
            encrypted_data = {}
            for key, value in data.items():
                current_path = f"{field_path}.{key}" if field_path else key

                if self._is_sensitive_field(key, current_path, value):
                    try:
                        # Encrypt the field
                        field_encryption = get_field_encryption()
                        encrypted_value = field_encryption.encrypt_field(value, current_path)
                        encrypted_data[key] = encrypted_value
                        context['encrypted_fields'].append(current_path)

                    except EncryptionError as e:
                        logger.warning(f"Failed to encrypt field {current_path}: {str(e)}")
                        encrypted_data[key] = value
                else:
                    # Recursively process nested objects
                    encrypted_data[key] = self._encrypt_sensitive_fields(
                        value, context, current_path
                    )

            return encrypted_data

        elif isinstance(data, list):
            return [
                self._encrypt_sensitive_fields(item, context, f"{field_path}[]")
                for item in data
            ]

        else:
            return data

    def _is_sensitive_field(self, field_name: str, field_path: str, value: Any) -> bool:
        """Check if a field should be encrypted"""

        # Skip if value is None or already looks encrypted
        if value is None or (isinstance(value, str) and value.startswith('{"encrypted_data":')):
            return False

        field_lower = field_name.lower()
        path_lower = field_path.lower()

        # Check exact matches
        if field_lower in self.sensitive_fields:
            return True

        # Check pattern matches
        for pattern in self.sensitive_patterns:
            if pattern in field_lower or pattern in path_lower:
                return True

        # Check if value looks like sensitive data
        if isinstance(value, str):
            # SSN pattern (XXX-XX-XXXX)
            if len(value) == 11 and value[3] == '-' and value[6] == '-':
                return True

            # Credit card pattern (16 digits, possibly spaced)
            if all(c.isdigit() or c == ' ' for c in value) and len(value.replace(' ', '')) >= 13:
                return True

        return False

    async def _process_response_masking(
        self,
        response: Response,
        context: Dict[str, Any]
    ) -> Response:
        """Process and mask sensitive fields in response body"""

        try:
            # Read response body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk

            if not response_body:
                return Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )

            # Parse JSON response
            try:
                response_data = json.loads(response_body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )

            # Mask sensitive fields
            masked_data = self._mask_sensitive_fields(response_data, context)

            # Create new response with masked data
            masked_body = json.dumps(masked_data).encode('utf-8')

            return Response(
                content=masked_body,
                status_code=response.status_code,
                headers=dict(response.headers)
            )

        except Exception as e:
            logger.error(f"Error processing response masking: {str(e)}")
            return response

    def _mask_sensitive_fields(
        self,
        data: Dict[str, Any],
        context: Dict[str, Any],
        field_path: str = ""
    ) -> Dict[str, Any]:
        """Recursively mask sensitive fields in response data"""

        if isinstance(data, dict):
            masked_data = {}
            for key, value in data.items():
                current_path = f"{field_path}.{key}" if field_path else key

                if self._should_mask_field(key, current_path, value):
                    masked_value = self._mask_value(value, key)
                    masked_data[key] = masked_value
                    context['masked_fields'].append(current_path)
                else:
                    # Recursively process nested objects
                    masked_data[key] = self._mask_sensitive_fields(
                        value, context, current_path
                    )

            return masked_data

        elif isinstance(data, list):
            return [
                self._mask_sensitive_fields(item, context, f"{field_path}[]")
                for item in data
            ]

        else:
            return data

    def _should_mask_field(self, field_name: str, field_path: str, value: Any) -> bool:
        """Check if a field should be masked in response"""

        if value is None:
            return False

        field_lower = field_name.lower()
        path_lower = field_path.lower()

        # Check exact matches
        if field_lower in self.sensitive_fields:
            return True

        # Check pattern matches
        for pattern in self.sensitive_patterns:
            if pattern in field_lower or pattern in path_lower:
                return True

        return False

    def _mask_value(self, value: Any, field_name: str) -> str:
        """Mask a sensitive value based on field type"""

        if not isinstance(value, str):
            value = str(value)

        field_lower = field_name.lower()

        # Email masking
        if 'email' in field_lower and '@' in value:
            local, domain = value.split('@', 1)
            if len(local) <= 2:
                return f"{'*' * len(local)}@{domain}"
            return f"{local[0]}{'*' * (len(local) - 2)}{local[-1]}@{domain}"

        # Phone masking
        elif 'phone' in field_lower:
            if len(value) >= 4:
                return f"{'*' * (len(value) - 4)}{value[-4:]}"
            return '*' * len(value)

        # SSN masking
        elif 'ssn' in field_lower or 'social_security' in field_lower:
            if len(value) >= 4:
                return f"***-**-{value[-4:]}"
            return '*' * len(value)

        # Credit card masking
        elif 'credit_card' in field_lower or 'card' in field_lower:
            # Remove non-digits
            digits = ''.join(c for c in value if c.isdigit())
            if len(digits) >= 4:
                return f"{'*' * (len(digits) - 4)}{digits[-4:]}"
            return '*' * len(value)

        # Default masking
        else:
            if len(value) <= 2:
                return '*' * len(value)
            return f"{value[0]}{'*' * (len(value) - 2)}{value[-1]}"

    def _add_security_headers(self, response: Response, context: Dict[str, Any]) -> Response:
        """Add security headers related to encryption"""

        # Add custom headers for encryption context
        response.headers['X-Request-ID'] = context['request_id']

        if context['encrypted_fields']:
            response.headers['X-Encrypted-Fields-Count'] = str(len(context['encrypted_fields']))

        if context['masked_fields']:
            response.headers['X-Masked-Fields-Count'] = str(len(context['masked_fields']))

        # Standard security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # CSP header for additional security
        response.headers['Content-Security-Policy'] = "default-src 'self'"

        return response

    def _generate_request_id(self) -> str:
        """Generate unique request ID"""
        import secrets
        return secrets.token_hex(16)


class EncryptionContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware for managing encryption context throughout request lifecycle.

    This middleware:
    - Extracts user and organization context for encryption
    - Provides encryption context to downstream services
    - Logs encryption operations for audit trails
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and establish encryption context"""

        # Try to extract user context from JWT token
        user_id = None
        organization_id = None

        try:
            # This would integrate with your authentication system
            # For now, we'll try to get from headers (simplified)
            auth_header = request.headers.get('authorization')
            if auth_header and auth_header.startswith('Bearer '):
                # In a real implementation, decode JWT token here
                # For demo, we'll skip JWT decoding
                pass
        except Exception as e:
            logger.warning(f"Failed to extract user context for encryption: {str(e)}")

        # Store encryption context in request state
        request.state.encryption_context = {
            'user_id': user_id,
            'organization_id': organization_id,
            'ip_address': request.client.host if request.client else None,
            'user_agent': request.headers.get('user-agent'),
            'request_path': request.url.path,
            'request_method': request.method
        }

        # Process request
        response = await call_next(request)

        return response


def get_encryption_context(request: Request) -> Dict[str, Any]:
    """Get encryption context from request state"""
    return getattr(request.state, 'encryption_context', {})


# Convenience function for adding encryption middleware
def add_encryption_middleware(
    app,
    encrypt_request_fields: bool = True,
    mask_response_fields: bool = True,
    sensitive_fields: Optional[List[str]] = None,
    exclude_paths: Optional[List[str]] = None
):
    """Add encryption middleware to FastAPI app"""

    # Add context middleware first
    app.add_middleware(EncryptionContextMiddleware)

    # Add encryption middleware
    app.add_middleware(
        EncryptionMiddleware,
        encrypt_request_fields=encrypt_request_fields,
        mask_response_fields=mask_response_fields,
        sensitive_fields=sensitive_fields,
        exclude_paths=exclude_paths
    )