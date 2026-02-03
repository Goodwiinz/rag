"""
Security utilities for authentication and authorization
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union

import bcrypt  # Changed from passlib
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from src.core.config import settings

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


def verify_token(token: str) -> Optional[TokenData]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")  # sub contains the user ID
        email: str = payload.get("email")  # email is a separate field
        organization_id: str = payload.get("organization_id")
        role: str = payload.get("role")
        exp: int = payload.get("exp")

        if user_id is None:
            return None

        token_data = TokenData(
            user_id=user_id,
            email=email,
            organization_id=organization_id,
            role=role,
            exp=datetime.utcfromtimestamp(exp) if exp else None,
        )
        return token_data

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

    return hashlib.sha256(data.encode()).hexdigest() == hashed


class RateLimiter:
    """Simple rate limiter for authentication endpoints"""

    def __init__(self, max_attempts: int = 5, window_minutes: int = 15):
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        self.attempts = {}  # Simple in-memory storage

    def is_allowed(self, identifier: str) -> bool:
        """Check if identifier is allowed to make an attempt"""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=self.window_minutes)

        # Clean old attempts
        if identifier in self.attempts:
            self.attempts[identifier] = [
                attempt_time
                for attempt_time in self.attempts[identifier]
                if attempt_time > window_start
            ]
        else:
            self.attempts[identifier] = []

        # Check if under limit
        if len(self.attempts[identifier]) >= self.max_attempts:
            return False

        # Record this attempt
        self.attempts[identifier].append(now)
        return True

    def get_remaining_attempts(self, identifier: str) -> int:
        """Get remaining attempts for identifier"""
        if identifier not in self.attempts:
            return self.max_attempts

        now = datetime.utcnow()
        window_start = now - timedelta(minutes=self.window_minutes)

        # Count recent attempts
        recent_attempts = [
            attempt_time
            for attempt_time in self.attempts[identifier]
            if attempt_time > window_start
        ]

        return max(0, self.max_attempts - len(recent_attempts))


# Global rate limiter instance (will be initialized after settings import)
# Use higher limits for development to avoid blocking during testing
auth_rate_limiter = RateLimiter(
    max_attempts=settings.AUTH_RATE_LIMIT_ATTEMPTS,
    window_minutes=settings.AUTH_RATE_LIMIT_WINDOW_MINUTES,
)
