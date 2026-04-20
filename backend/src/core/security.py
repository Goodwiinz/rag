"""
Security utilities for authentication and authorization.

Supabase-only JWT verification — custom token creation has been removed.
The frontend uses Supabase SSR with cookie-based sessions; the backend
only verifies Supabase-issued JWTs (HS256 via shared secret or ES256 via JWKS).
"""

import logging
import secrets
from datetime import datetime
from typing import Any, Dict, Optional

import bcrypt  # Changed from passlib
import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from pydantic import BaseModel
from starlette.datastructures import Address
from starlette.requests import HTTPConnection

from src.core.config import settings

logger = logging.getLogger(__name__)

# Cache for Supabase JWKS keys
_supabase_jwks_cache: Optional[Dict] = None

# JWT Bearer scheme
security = HTTPBearer()


class TokenData(BaseModel):
    """Token data model"""

    user_id: Optional[str] = None
    email: Optional[str] = None
    organization_id: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[datetime] = None


def _extract_forwarded_ip(headers: Any) -> Optional[str]:
    """Return the trusted client IP from X-Forwarded-For when present."""
    if headers is None:
        return None

    forwarded_for = headers.get("X-Forwarded-For")
    if not forwarded_for:
        return None

    ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
    return ips[-1] if ips else None


def _install_proxy_aware_client_patch() -> None:
    """Make request.client.host reflect trusted X-Forwarded-For values."""
    if getattr(HTTPConnection, "_proxy_aware_client_installed", False):
        return

    original_client = HTTPConnection.client
    if not isinstance(original_client, property) or original_client.fget is None:
        return

    def _proxy_aware_client(self):
        forwarded_ip = _extract_forwarded_ip(getattr(self, "headers", None))
        if forwarded_ip:
            base_client = original_client.fget(self)
            port = getattr(base_client, "port", 0) if base_client else 0
            return Address(forwarded_ip, port)
        return original_client.fget(self)

    HTTPConnection.client = property(_proxy_aware_client)
    HTTPConnection._proxy_aware_client_installed = True


_install_proxy_aware_client_patch()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    try:
        # Truncate to 72 chars to avoid bcrypt limit and ensure compatibility
        plain_bytes = plain_password[:72].encode("utf-8")
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(plain_bytes, hash_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    # Truncate to 72 chars to avoid bcrypt limit
    pwd_bytes = password[:72].encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def generate_password_reset_token() -> str:
    """Generate a secure password reset token"""
    return secrets.token_urlsafe(32)


def generate_api_key() -> str:
    """Generate a secure API key"""
    return secrets.token_urlsafe(32)


def get_client_ip(request: Request) -> str:
    """
    Get client IP address, handling proxies.

    Checks X-Forwarded-For header first. If present, takes the last IP
    in the list (assuming trusted proxy appends client IP).
    Falls back to request.client.host if not behind a proxy.
    """
    forwarded_ip = _extract_forwarded_ip(request.headers)
    if forwarded_ip:
        return forwarded_ip

    return request.client.host if request.client else "unknown"


def _get_supabase_jwks() -> Optional[Dict]:
    """Fetch and cache JWKS from Supabase for ES256 verification."""
    global _supabase_jwks_cache
    if _supabase_jwks_cache is not None:
        return _supabase_jwks_cache
    try:
        url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
        _supabase_jwks_cache = resp.json()
        logger.info("Fetched Supabase JWKS successfully")
        return _supabase_jwks_cache
    except Exception as e:
        logger.warning(f"Failed to fetch Supabase JWKS: {e}")
        return None


def _extract_supabase_token_data(payload: dict) -> Optional[TokenData]:
    """Extract TokenData from a decoded Supabase JWT payload."""
    user_id = payload.get("sub")
    email = payload.get("email")
    app_metadata = payload.get("app_metadata", {})
    role = app_metadata.get("role", "USER")
    exp = payload.get("exp")
    if user_id:
        return TokenData(
            user_id=user_id,
            email=email,
            organization_id=None,  # Resolved in get_current_user
            role=role,
            exp=datetime.utcfromtimestamp(exp) if exp else None,
        )
    return None


def verify_token(token: str) -> Optional[TokenData]:
    """Verify a Supabase JWT token (HS256 via shared secret or ES256 via JWKS).

    Custom JWT creation/verification has been removed — only Supabase-issued
    tokens are accepted.
    """
    # Try Supabase JWT — HS256 with shared secret
    if settings.SUPABASE_JWT_SECRET:
        try:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
            result = _extract_supabase_token_data(payload)
            if result:
                return result
        except JWTError:
            pass  # Fall through to JWKS/ES256

    # Try Supabase JWT — ES256 via JWKS
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "ES256":
            jwks_data = _get_supabase_jwks()
            if jwks_data and "keys" in jwks_data:
                kid = header.get("kid")
                for key_data in jwks_data["keys"]:
                    if key_data.get("kid") == kid or kid is None:
                        public_key = jwk.construct(key_data)
                        payload = jwt.decode(
                            token,
                            public_key,
                            algorithms=["ES256"],
                            audience="authenticated",
                        )
                        result = _extract_supabase_token_data(payload)
                        if result:
                            return result
    except JWTError as e:
        logger.error(f"ES256 JWTError: {e}")
    except Exception as e:
        logger.error(f"ES256 verification failed: {type(e).__name__}: {e}")

    return None


def get_current_user_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    """Get current user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        token_data = verify_token(token)

        if token_data is None:
            raise credentials_exception

        # Check if token is expired
        if token_data.exp and token_data.exp < datetime.utcnow():
            raise credentials_exception

        return token_data

    except Exception:
        raise credentials_exception


def check_password_strength(password: str) -> Dict[str, Any]:
    """Check password strength and return recommendations"""
    issues = []
    score = 0

    # Length check
    if len(password) < 8:
        issues.append("Password should be at least 8 characters long")
    else:
        score += 1

    # Uppercase check
    if not any(c.isupper() for c in password):
        issues.append("Password should contain at least one uppercase letter")
    else:
        score += 1

    # Lowercase check
    if not any(c.islower() for c in password):
        issues.append("Password should contain at least one lowercase letter")
    else:
        score += 1

    # Number check
    if not any(c.isdigit() for c in password):
        issues.append("Password should contain at least one number")
    else:
        score += 1

    # Special character check
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    if not any(c in special_chars for c in password):
        issues.append("Password should contain at least one special character")
    else:
        score += 1

    # Common patterns check
    common_patterns = ["password", "123456", "qwerty", "admin"]
    password_lower = password.lower()
    if any(pattern in password_lower for pattern in common_patterns):
        issues.append("Password should not contain common patterns")
        score = max(0, score - 2)

    # Determine strength
    if score >= 5:
        strength = "strong"
    elif score >= 3:
        strength = "medium"
    else:
        strength = "weak"

    return {
        "strength": strength,
        "score": score,
        "issues": issues,
        "is_valid": len(issues) == 0,
    }


def generate_secure_random_string(length: int = 32) -> str:
    """Generate a cryptographically secure random string"""
    return secrets.token_urlsafe(length)


def hash_sensitive_data(data: str) -> str:
    """Hash sensitive data for storage"""
    import hashlib

    return hashlib.sha256(data.encode()).hexdigest()


def verify_sensitive_data_hash(data: str, hashed: str) -> bool:
    """Verify sensitive data against its hash"""
    import hashlib
    import secrets

    return secrets.compare_digest(hashlib.sha256(data.encode()).hexdigest(), hashed)


# Import RateLimiter implementations
from src.core.rate_limit import create_rate_limiter, InMemoryRateLimiter as RateLimiter

# Global rate limiter instance (will be initialized after settings import)
# Use higher limits for development to avoid blocking during testing
auth_rate_limiter = create_rate_limiter(
    max_attempts=settings.AUTH_RATE_LIMIT_ATTEMPTS,
    window_minutes=settings.AUTH_RATE_LIMIT_WINDOW_MINUTES,
)
