"""
Security utilities for authentication and authorization
"""

import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

import bcrypt  # Changed from passlib
import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from pydantic import BaseModel

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
    remember_me: bool = False  # Indicates if session should persist for 30 days


class Token(BaseModel):
    """Token response model"""

    access_token: str
    token_type: str
    expires_in: int
    user: Dict[str, Any]


class TokenRefresh(BaseModel):
    """Token refresh request model"""

    refresh_token: str


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
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Get the last IP address in the chain
        # Format: client, proxy1, proxy2
        # If we trust the proxy to append the real client IP, we take the last one?
        # WAIT. Standard practice:
        # If we are behind a trusted proxy (e.g. Nginx, ALB), it adds the connecting client IP to the END of the list.
        # But if the client sends X-Forwarded-For: spoofed_ip, and we are behind 1 proxy:
        # Header becomes: spoofed_ip, real_client_ip.
        # So the LAST IP is the real client IP (as seen by our proxy).
        # This is safe against spoofing if we trust our proxy to append.

        # Split by comma and strip whitespace
        ips = [ip.strip() for ip in forwarded_for.split(",")]
        return ips[-1]

    return request.client.host if request.client else "unknown"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update(
        {"exp": expire, "type": "access"}  # Add token type for verification
    )
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(
    data: dict, expires_delta: Optional[timedelta] = None, remember_me: bool = False
) -> str:
    """Create JWT refresh token

    Args:
        data: Token payload data
        expires_delta: Custom expiration time
        remember_me: If True, use extended 30-day expiration for persistent sessions
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    elif remember_me:
        # Extended session for "Remember Me" - 30 days
        expire = datetime.utcnow() + timedelta(
            days=settings.REMEMBER_ME_REFRESH_TOKEN_DAYS
        )
    else:
        # Default refresh token lifetime
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update(
        {
            "exp": expire,
            "type": "refresh",
            "remember_me": remember_me,  # Track if this is an extended session
        }
    )
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


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
    """Verify JWT token — supports both Supabase (HS256/ES256) and custom JWTs."""
    # Try Supabase JWT first — HS256 with shared secret
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
        # Peek at the token header to check algorithm
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
    except JWTError:
        pass  # Fall through to custom JWT
    except Exception as e:
        logger.debug(f"JWKS verification failed: {e}")

    # Fallback: custom JWT (existing logic)
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        organization_id: str = payload.get("organization_id")
        role: str = payload.get("role")
        exp: int = payload.get("exp")

        if user_id is None:
            return None

        return TokenData(
            user_id=user_id,
            email=email,
            organization_id=organization_id,
            role=role,
            exp=datetime.utcfromtimestamp(exp) if exp else None,
        )
    except JWTError:
        return None


def extract_refresh_token_user_id(token: str) -> Optional[str]:
    """Extract user_id from refresh token without verifying expiration.

    Signature is still verified. Used for rate-limiting identification
    before full token validation.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": False},
        )
        if payload.get("type") != "refresh":
            return None
        return payload.get("sub")
    except JWTError:
        return None


def verify_refresh_token(token: str) -> Optional[TokenData]:
    """Verify and decode refresh token"""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )

        # Check if it's a refresh token
        if payload.get("type") != "refresh":
            return None

        user_id: str = payload.get("sub")
        if user_id is None:
            return None

        # Preserve the remember_me flag from the original refresh token
        remember_me: bool = payload.get("remember_me", False)

        return TokenData(user_id=user_id, remember_me=remember_me)

    except JWTError:
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
