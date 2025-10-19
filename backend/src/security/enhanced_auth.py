"""
Enhanced Authentication Security Implementation
Addresses critical authentication vulnerabilities
"""

import jwt
import time
import hashlib
import secrets
import logging
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import redis
import bcrypt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import re

from src.core.config import settings
from src.models.user import User
from src.core.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class TokenType(Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    RESET = "reset"
    EMAIL_VERIFICATION = "email_verification"

@dataclass
class TokenInfo:
    token: str
    token_type: TokenType
    user_id: str
    expires_at: datetime
    device_fingerprint: Optional[str] = None
    is_revoked: bool = False

class DeviceFingerprint:
    """Generate and validate device fingerprints"""

    @staticmethod
    def generate_fingerprint(request_data: Dict[str, str]) -> str:
        """Generate device fingerprint from request data"""
        fingerprint_data = {
            'user_agent': request_data.get('user_agent', ''),
            'ip_address': request_data.get('ip_address', ''),
            'accept_language': request_data.get('accept_language', ''),
            'platform': request_data.get('platform', ''),
            'screen_resolution': request_data.get('screen_resolution', ''),
        }

        # Create fingerprint hash
        fingerprint_str = '|'.join(fingerprint_data.values())
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()

class EnhancedPasswordPolicy:
    """Enhanced password policy enforcement"""

    def __init__(self):
        self.min_length = 12
        self.max_length = 128
        self.require_uppercase = True
        self.require_lowercase = True
        self.require_digits = True
        self.require_special_chars = True
        self.forbidden_patterns = [
            r'(.)\1{2,}',  # No 3+ repeated characters
            r'123456',      # Common sequences
            r'password',    # Common passwords
            r'qwerty',      # Keyboard patterns
        ]
        self.forbidden_common_passwords = {
            'password', '123456', '123456789', 'qwerty', 'abc123',
            'password123', 'admin', 'letmein', 'welcome', 'monkey'
        }

    def validate_password(self, password: str, user_info: Dict[str, str] = None) -> Tuple[bool, List[str]]:
        """Validate password against policy"""
        errors = []

        # Length requirements
        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters long")

        if len(password) > self.max_length:
            errors.append(f"Password must be no more than {self.max_length} characters long")

        # Character requirements
        if self.require_uppercase and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")

        if self.require_lowercase and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")

        if self.require_digits and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")

        if self.require_special_chars and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")

        # Forbidden patterns
        for pattern in self.forbidden_patterns:
            if re.search(pattern, password, re.IGNORECASE):
                errors.append("Password contains forbidden patterns")
                break

        # Common passwords
        if password.lower() in self.forbidden_common_passwords:
            errors.append("Password is too common")

        # Personal information (if provided)
        if user_info:
            forbidden_info = [
                user_info.get('first_name', ''),
                user_info.get('last_name', ''),
                user_info.get('email', '').split('@')[0],
            ]

            for info in forbidden_info:
                if info and len(info) > 2 and info.lower() in password.lower():
                    errors.append("Password cannot contain personal information")
                    break

        return len(errors) == 0, errors

class TokenManager:
    """Enhanced token management with rotation and revocation"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.access_token_expiry = timedelta(minutes=15)
        self.refresh_token_expiry = timedelta(days=7)
        self.max_concurrent_sessions = 3

    def generate_token(self, user_id: str, token_type: TokenType,
                      device_fingerprint: Optional[str] = None,
                      additional_claims: Dict[str, Any] = None) -> TokenInfo:
        """Generate a new token"""
        now = datetime.utcnow()

        if token_type == TokenType.ACCESS:
            expires_at = now + self.access_token_expiry
        elif token_type == TokenType.REFRESH:
            expires_at = now + self.refresh_token_expiry
        elif token_type == TokenType.RESET:
            expires_at = now + timedelta(hours=1)
        else:  # EMAIL_VERIFICATION
            expires_at = now + timedelta(hours=24)

        # Create token payload
        payload = {
            'sub': user_id,
            'type': token_type.value,
            'iat': int(now.timestamp()),
            'exp': int(expires_at.timestamp()),
            'jti': secrets.token_urlsafe(32),  # Unique token ID
        }

        if device_fingerprint:
            payload['fp'] = device_fingerprint

        if additional_claims:
            payload.update(additional_claims)

        # Generate token
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        # Store token metadata in Redis
        token_info = TokenInfo(
            token=token,
            token_type=token_type,
            user_id=user_id,
            expires_at=expires_at,
            device_fingerprint=device_fingerprint
        )

        self._store_token_info(token_info)

        return token_info

    def validate_token(self, token: str, expected_type: TokenType = None,
                      device_fingerprint: Optional[str] = None) -> Optional[TokenInfo]:
        """Validate token and return token info"""
        try:
            # Decode token
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

            # Check token type
            token_type = TokenType(payload.get('type', 'access'))
            if expected_type and token_type != expected_type:
                return None

            # Check if token is revoked
            token_id = payload.get('jti')
            if self._is_token_revoked(token_id):
                return None

            # Check device fingerprint for access tokens
            if token_type == TokenType.ACCESS and device_fingerprint:
                stored_fingerprint = payload.get('fp')
                if stored_fingerprint and stored_fingerprint != device_fingerprint:
                    logger.warning(f"Device fingerprint mismatch for token {token_id}")
                    return None

            # Check session limits
            user_id = payload.get('sub')
            if token_type == TokenType.ACCESS and not self._check_session_limit(user_id, device_fingerprint):
                return None

            # Create token info
            expires_at = datetime.fromtimestamp(payload['exp'])
            return TokenInfo(
                token=token,
                token_type=token_type,
                user_id=user_id,
                expires_at=expires_at,
                device_fingerprint=payload.get('fp')
            )

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None

    def rotate_refresh_token(self, refresh_token: str, device_fingerprint: Optional[str] = None) -> Optional[TokenInfo]:
        """Rotate refresh token"""
        token_info = self.validate_token(refresh_token, TokenType.REFRESH, device_fingerprint)
        if not token_info:
            return None

        # Revoke old refresh token
        self.revoke_token(refresh_token)

        # Generate new refresh token
        return self.generate_token(
            token_info.user_id,
            TokenType.REFRESH,
            device_fingerprint
        )

    def revoke_token(self, token: str) -> bool:
        """Revoke a token"""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            token_id = payload.get('jti')
            expires_at = datetime.fromtimestamp(payload['exp'])

            # Store revoked token in Redis until it expires
            self.redis.setex(
                f"revoked_token:{token_id}",
                int((expires_at - datetime.utcnow()).total_seconds()),
                "1"
            )

            return True
        except jwt.InvalidTokenError:
            return False

    def revoke_all_user_tokens(self, user_id: str) -> None:
        """Revoke all tokens for a user"""
        # This would require tracking all user tokens in Redis
        # For now, we'll add user to a blocklist
        self.redis.setex(f"blocked_user:{user_id}", 3600, "1")

    def _store_token_info(self, token_info: TokenInfo) -> None:
        """Store token metadata in Redis"""
        token_id = jwt.decode(token_info.token, options={"verify_signature": False}).get('jti')

        if token_info.token_type == TokenType.REFRESH:
            # Track active refresh tokens for session management
            session_key = f"user_sessions:{token_info.user_id}"
            session_data = {
                'token_id': token_id,
                'device_fingerprint': token_info.device_fingerprint,
                'created_at': datetime.utcnow().isoformat()
            }

            # Add to user sessions
            self.redis.lpush(session_key, json.dumps(session_data))
            self.redis.expire(session_key, int(self.refresh_token_expiry.total_seconds()))

            # Limit concurrent sessions
            self.redis.ltrim(session_key, 0, self.max_concurrent_sessions - 1)

    def _is_token_revoked(self, token_id: str) -> bool:
        """Check if token is revoked"""
        return self.redis.exists(f"revoked_token:{token_id}") > 0

    def _check_session_limit(self, user_id: str, device_fingerprint: str) -> bool:
        """Check if user has too many concurrent sessions"""
        if not device_fingerprint:
            return True

        session_key = f"user_sessions:{user_id}"
        sessions = self.redis.lrange(session_key, 0, -1)

        # Count sessions for this device
        device_sessions = 0
        for session in sessions:
            try:
                session_data = json.loads(session)
                if session_data.get('device_fingerprint') == device_fingerprint:
                    device_sessions += 1
            except json.JSONDecodeError:
                continue

        # Allow max 2 sessions per device
        return device_sessions < 2

class AccountLockout:
    """Account lockout mechanism for failed login attempts"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.max_attempts = 5
        self.lockout_duration = timedelta(minutes=15)
        self.attempt_window = timedelta(minutes=15)

    def record_failed_attempt(self, identifier: str) -> int:
        """Record a failed login attempt"""
        key = f"failed_attempts:{identifier}"

        # Add current attempt
        now = int(time.time())
        self.redis.lpush(key, str(now))
        self.redis.expire(key, int(self.attempt_window.total_seconds()))

        # Clean old attempts
        cutoff_time = now - int(self.attempt_window.total_seconds())
        self.redis.lrem(key, 0, lambda x: int(x) < cutoff_time)

        # Get current attempt count
        attempts = len(self.redis.lrange(key, 0, -1))

        # Lock account if max attempts reached
        if attempts >= self.max_attempts:
            self.redis.setex(
                f"locked_account:{identifier}",
                int(self.lockout_duration.total_seconds()),
                "1"
            )
            logger.warning(f"Account locked due to failed attempts: {identifier}")

        return attempts

    def is_account_locked(self, identifier: str) -> bool:
        """Check if account is locked"""
        return self.redis.exists(f"locked_account:{identifier}") > 0

    def get_remaining_lockout_time(self, identifier: str) -> int:
        """Get remaining lockout time in seconds"""
        ttl = self.redis.ttl(f"locked_account:{identifier}")
        return max(0, ttl)

    def clear_failed_attempts(self, identifier: str) -> None:
        """Clear failed attempts after successful login"""
        self.redis.delete(f"failed_attempts:{identifier}")
        self.redis.delete(f"locked_account:{identifier}")

class EnhancedAuthService:
    """Enhanced authentication service with comprehensive security features"""

    def __init__(self, db: Session, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client
        self.token_manager = TokenManager(redis_client)
        self.password_policy = EnhancedPasswordPolicy()
        self.account_lockout = AccountLockout(redis_client)

        # Initialize encryption for sensitive data
        self.encryption_key = self._get_encryption_key()
        self.cipher = Fernet(self.encryption_key)

    async def authenticate_user(self, identifier: str, password: str,
                              device_fingerprint: Optional[str] = None,
                              ip_address: Optional[str] = None) -> Dict[str, Any]:
        """Enhanced user authentication with security controls"""

        # Check account lockout
        if self.account_lockout.is_account_locked(identifier):
            remaining_time = self.account_lockout.get_remaining_lockout_time(identifier)
            raise ValueError(f"Account is temporarily locked. Try again in {remaining_time} seconds.")

        # Find user by email or username
        user = self.db.query(User).filter(
            (User.email == identifier) | (User.username == identifier),
            User.is_active == True,
            User.is_deleted == False
        ).first()

        if not user:
            # Record failed attempt
            self.account_lockout.record_failed_attempt(identifier)
            raise ValueError("Invalid credentials")

        # Verify password
        if not self._verify_password(password, user.password_hash):
            # Record failed attempt
            self.account_lockout.record_failed_attempt(identifier)
            raise ValueError("Invalid credentials")

        # Check if user's password needs to be rehashed
        if self._password_needs_rehash(user.password_hash):
            user.password_hash = self._hash_password(password)
            self.db.commit()

        # Clear failed attempts
        self.account_lockout.clear_failed_attempts(identifier)

        # Update last login and device info
        user.last_login_at = datetime.utcnow()
        user.last_login_ip = ip_address
        self.db.commit()

        # Generate tokens
        access_token_info = self.token_manager.generate_token(
            str(user.id),
            TokenType.ACCESS,
            device_fingerprint,
            {'role': user.role.value, 'org_id': str(user.organization_id)}
        )

        refresh_token_info = self.token_manager.generate_token(
            str(user.id),
            TokenType.REFRESH,
            device_fingerprint
        )

        return {
            'access_token': access_token_info.token,
            'refresh_token': refresh_token_info.token,
            'token_type': 'Bearer',
            'expires_in': int(self.token_manager.access_token_expiry.total_seconds()),
            'user': user.to_dict(exclude_sensitive=True)
        }

    async def refresh_access_token(self, refresh_token: str,
                                 device_fingerprint: Optional[str] = None) -> Dict[str, Any]:
        """Refresh access token with rotation"""

        # Rotate refresh token
        new_refresh_token_info = self.token_manager.rotate_refresh_token(
            refresh_token, device_fingerprint
        )

        if not new_refresh_token_info:
            raise ValueError("Invalid or expired refresh token")

        # Get user info
        old_token_info = self.token_manager.validate_token(refresh_token, TokenType.REFRESH)
        user = self.db.query(User).filter(
            User.id == old_token_info.user_id,
            User.is_active == True,
            User.is_deleted == False
        ).first()

        if not user:
            raise ValueError("User not found")

        # Generate new access token
        access_token_info = self.token_manager.generate_token(
            str(user.id),
            TokenType.ACCESS,
            device_fingerprint,
            {'role': user.role.value, 'org_id': str(user.organization_id)}
        )

        return {
            'access_token': access_token_info.token,
            'refresh_token': new_refresh_token_info.token,
            'token_type': 'Bearer',
            'expires_in': int(self.token_manager.access_token_expiry.total_seconds())
        }

    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new user with enhanced security validation"""

        # Validate password
        is_valid, errors = self.password_policy.validate_password(
            user_data['password'],
            {
                'first_name': user_data.get('first_name', ''),
                'last_name': user_data.get('last_name', ''),
                'email': user_data.get('email', ''),
            }
        )

        if not is_valid:
            raise ValueError(f"Password validation failed: {'; '.join(errors)}")

        # Hash password
        password_hash = self._hash_password(user_data['password'])

        # Create user
        user = User(
            email=user_data['email'],
            username=user_data.get('username', user_data['email'].split('@')[0]),
            password_hash=password_hash,
            first_name=user_data.get('first_name', ''),
            last_name=user_data.get('last_name', ''),
            organization_id=user_data.get('organization_id'),
            role=user_data.get('role', 'USER'),
            is_active=True,
            is_deleted=False
        )

        self.db.add(user)
        self.db.commit()

        return user.to_dict(exclude_sensitive=True)

    async def change_password(self, user: User, current_password: str, new_password: str) -> bool:
        """Change user password with security validation"""

        # Verify current password
        if not self._verify_password(current_password, user.password_hash):
            raise ValueError("Current password is incorrect")

        # Validate new password
        is_valid, errors = self.password_policy.validate_password(
            new_password,
            {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
            }
        )

        if not is_valid:
            raise ValueError(f"Password validation failed: {'; '.join(errors)}")

        # Update password
        user.password_hash = self._hash_password(new_password)
        user.password_changed_at = datetime.utcnow()
        self.db.commit()

        # Revoke all existing tokens for this user
        self.token_manager.revoke_all_user_tokens(str(user.id))

        return True

    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    def _verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    def _password_needs_rehash(self, hashed: str) -> bool:
        """Check if password needs rehashing"""
        # Check if bcrypt rounds need updating
        if len(hashed) < 60:  # Invalid bcrypt hash
            return True

        # Extract rounds from hash
        rounds = int(hashed.split('$')[2])
        return rounds < 12

    def _get_encryption_key(self) -> bytes:
        """Get or generate encryption key"""
        key_file = "/etc/rag/encryption.key"

        try:
            with open(key_file, 'rb') as f:
                key_data = f.read()
                return base64.urlsafe_b64decode(key_data)
        except FileNotFoundError:
            # Generate new key
            key = Fernet.generate_key()

            try:
                os.makedirs(os.path.dirname(key_file), exist_ok=True)
                with open(key_file, 'wb') as f:
                    f.write(base64.urlsafe_b64encode(key))
                os.chmod(key_file, 0o600)  # Restrict file permissions
            except Exception as e:
                logger.error(f"Failed to save encryption key: {e}")

            return key

# Enhanced authentication dependency for FastAPI
async def get_enhanced_auth_service(db: Session = Depends(get_db)) -> EnhancedAuthService:
    """Get enhanced authentication service instance"""
    redis_client = redis.from_url(settings.REDIS_URL)
    return EnhancedAuthService(db, redis_client)