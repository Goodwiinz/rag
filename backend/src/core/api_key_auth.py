"""
API Key Authentication for Public Endpoints
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import asyncio
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, select
import logging
import redis.asyncio as redis

from src.core.database import Base, get_db
from src.core.security import RateLimiter
from src.core.config import settings

logger = logging.getLogger(__name__)

# API Key Bearer scheme  
api_key_security = HTTPBearer()

class APIKey(Base):
    """API Key model for public endpoint access"""
    __tablename__ = "api_keys"
    
    id = Column(String, primary_key=True, default=lambda: secrets.token_hex(16))
    name = Column(String, nullable=False)  # Human readable name
    key_hash = Column(String, nullable=False, unique=True)  # Hashed API key
    key_prefix = Column(String(8), nullable=False)  # First 8 chars for identification 
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    rate_limit_per_hour = Column(Integer, default=100, nullable=False)  # Requests per hour
    allowed_endpoints = Column(Text, nullable=True)  # JSON array of allowed endpoints
    created_by = Column(String, nullable=True)  # Admin who created the key
    description = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration
    organization_id = Column(String, nullable=True)  # Organization the key is scoped to


class APIKeyUsageLog(Base):
    """API Key usage log model for audit trail"""
    __tablename__ = "api_key_usage_log"
    
    id = Column(String, primary_key=True, default=lambda: secrets.token_hex(16))
    api_key_id = Column(String, nullable=False)  # Foreign key to api_keys
    endpoint = Column(String(255), nullable=False)  # API endpoint accessed
    method = Column(String(10), nullable=False)  # HTTP method used
    client_ip = Column(String(45), nullable=True)  # Client IP address
    user_agent = Column(Text, nullable=True)  # Client user agent
    request_size_bytes = Column(Integer, nullable=True)  # Request payload size
    response_status = Column(Integer, nullable=True)  # HTTP response status
    response_time_ms = Column(Integer, nullable=True)  # Response time in milliseconds
    search_query = Column(Text, nullable=True)  # Search query for search endpoints
    results_count = Column(Integer, nullable=True)  # Number of results returned
    error_message = Column(Text, nullable=True)  # Error message if request failed
    accessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # When the API was accessed

class APIKeyData(BaseModel):
    """API Key data model"""
    id: str
    name: str
    key_prefix: str
    is_active: bool
    rate_limit_per_hour: int
    last_used_at: Optional[datetime]
    usage_count: int
    organization_id: Optional[str] = None

class APIKeyCreate(BaseModel):
    """API Key creation request"""
    name: str
    description: Optional[str] = None
    rate_limit_per_hour: int = 100
    expires_days: Optional[int] = None  # Days until expiration
    allowed_endpoints: Optional[list] = None

class APIKeyResponse(BaseModel):
    """API Key creation response (includes raw key)"""
    id: str
    name: str
    api_key: str  # This is shown ONLY during creation
    key_prefix: str
    rate_limit_per_hour: int
    expires_at: Optional[datetime]
    organization_id: Optional[str] = None

def hash_api_key(raw_key: str) -> str:
    """Hash an API key using SHA-256"""
    return hashlib.sha256(raw_key.encode()).hexdigest()

def generate_api_key() -> tuple[str, str]:
    """Generate API key and return (raw_key, hash)"""
    raw_key = f"rag_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(32))}"
    key_hash = hash_api_key(raw_key)
    return raw_key, key_hash

def verify_api_key(raw_key: str, key_hash: str) -> bool:
    """Verify API key against hash using constant-time comparison"""
    return secrets.compare_digest(hash_api_key(raw_key), key_hash)

# Rate limiter for API key endpoints
api_key_rate_limiter = RateLimiter(max_attempts=1000, window_minutes=60)


class RedisRateLimiter:
    """Redis-based rate limiter for distributed environments"""
    
    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis: Optional[redis.Redis] = None
        
    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection"""
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis
    
    async def track_usage(self, key_id: str, endpoint: str):
        """Track API key usage for rate limiting"""
        now = datetime.utcnow()
        hour_key = now.replace(minute=0, second=0, microsecond=0)
        
        redis_client = await self._get_redis()
        redis_key = f"rate_limit:{key_id}:{hour_key.isoformat()}"
        
        try:
            # Use atomic INCR operation for thread-safe counting
            current_count = await redis_client.incr(redis_key)
            
            # Set TTL of 1 hour only on first increment
            if current_count == 1:
                await redis_client.expire(redis_key, 3600)  # 1 hour TTL
                
            logger.info(f"API key usage tracked: key={key_id}, endpoint={endpoint}, hour={hour_key}, count={current_count}")
            
        except Exception as e:
            logger.error(f"Failed to track usage in Redis for key {key_id}: {e}")
            # Fail gracefully - don't block API calls if Redis is down
    
    async def check_rate_limit(self, key_id: str, rate_limit: int) -> bool:
        """Check if API key is within rate limit"""
        now = datetime.utcnow()
        hour_key = now.replace(minute=0, second=0, microsecond=0)
        
        redis_client = await self._get_redis()
        redis_key = f"rate_limit:{key_id}:{hour_key.isoformat()}"
        
        try:
            current_usage = await redis_client.get(redis_key)
            current_usage = int(current_usage) if current_usage else 0
            
            return current_usage < rate_limit
            
        except Exception as e:
            logger.error(f"Failed to check rate limit in Redis for key {key_id}: {e}")
            # Fail open - allow request if Redis is down to avoid blocking API
            return True
    
    async def get_current_usage(self, key_id: str) -> int:
        """Get current hour usage for API key"""
        now = datetime.utcnow()
        hour_key = now.replace(minute=0, second=0, microsecond=0)
        
        redis_client = await self._get_redis()
        redis_key = f"rate_limit:{key_id}:{hour_key.isoformat()}"
        
        try:
            current_usage = await redis_client.get(redis_key)
            return int(current_usage) if current_usage else 0
            
        except Exception as e:
            logger.error(f"Failed to get current usage from Redis for key {key_id}: {e}")
            return 0
    
    async def close(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()


# Global Redis rate limiter instance
redis_rate_limiter = RedisRateLimiter()

class APIKeyAuth:
    """API Key authentication and rate limiting using Redis"""
    
    def __init__(self):
        self.rate_limiter = redis_rate_limiter
    
    async def track_usage(self, key_id: str, endpoint: str):
        """Track API key usage for rate limiting"""
        await self.rate_limiter.track_usage(key_id, endpoint)
    
    async def check_rate_limit(self, key_id: str, rate_limit: int) -> bool:
        """Check if API key is within rate limit"""
        return await self.rate_limiter.check_rate_limit(key_id, rate_limit)
    
    async def get_current_usage(self, key_id: str) -> int:
        """Get current hour usage for API key"""
        return await self.rate_limiter.get_current_usage(key_id)

# Global API key auth instance
api_key_auth = APIKeyAuth()


async def cleanup_api_key_auth():
    """Cleanup function for API key authentication resources"""
    await redis_rate_limiter.close()

async def get_api_key_data(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(api_key_security),
    db: AsyncSession = Depends(get_db)
) -> tuple[APIKeyData, str]:
    """
    Validate API key and return key data with endpoint tracking
    
    Returns:
        tuple: (APIKeyData, endpoint_path)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        raw_key = credentials.credentials
        if not raw_key or not raw_key.startswith("rag_"):
            logger.warning(f"Invalid API key format from {request.client.host}")
            raise credentials_exception
        
        # Extract prefix to narrow down candidates
        # API keys are format: rag_<32 chars>
        # key_prefix stores the first 8 chars of the raw key (rag_ + 4 chars)
        key_prefix = raw_key[:8]
        
        # Hash the raw key to query directly
        key_hash = hash_api_key(raw_key)

        # Find potential API keys by both prefix and hash to prevent memory exhaustion
        # Retain timing attack mitigation by verifying below
        stmt = select(APIKey).where(
            APIKey.key_prefix == key_prefix,
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        )
        result = await db.execute(stmt)
        candidate_keys = result.scalars().all()

        api_key_record = None
        for key in candidate_keys:
             if verify_api_key(raw_key, key.key_hash):
                 api_key_record = key
                 break
        
        if not api_key_record:
            logger.warning(f"API key not found or invalid from {request.client.host}")
            raise credentials_exception
        
        # Check if expired
        if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
            logger.warning(f"Expired API key used: {api_key_record.key_prefix}***")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired"
            )
        
        # Check rate limit
        if not await api_key_auth.check_rate_limit(api_key_record.id, api_key_record.rate_limit_per_hour):
            current_usage = await api_key_auth.get_current_usage(api_key_record.id)
            # Window is an hourly bucket keyed on the current hour; clients can retry
            # once the next bucket starts. Clamp to at least 1s per RFC 9110.
            now = datetime.utcnow()
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            retry_after = max(1, int((next_hour - now).total_seconds()))
            logger.warning(f"Rate limit exceeded for API key {api_key_record.key_prefix}*** (usage: {current_usage}/{api_key_record.rate_limit_per_hour})")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Limit: {api_key_record.rate_limit_per_hour} requests per hour",
                headers={"Retry-After": str(retry_after)},
            )
        
        # Track usage
        endpoint = request.url.path
        await api_key_auth.track_usage(api_key_record.id, endpoint)
        
        # Update usage stats in database
        api_key_record.last_used_at = datetime.utcnow()
        api_key_record.usage_count += 1
        await db.commit()
        
        logger.info(f"Valid API key used: {api_key_record.name} ({api_key_record.key_prefix}***) from {request.client.host}")
        
        return APIKeyData(
            id=api_key_record.id,
            name=api_key_record.name, 
            key_prefix=api_key_record.key_prefix,
            is_active=api_key_record.is_active,
            rate_limit_per_hour=api_key_record.rate_limit_per_hour,
            last_used_at=api_key_record.last_used_at,
            usage_count=api_key_record.usage_count,
            organization_id=api_key_record.organization_id
        ), endpoint
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating API key: {e}")
        raise credentials_exception

# Optional API key dependency (for endpoints that can work with or without API key)
async def get_api_key_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> Optional[tuple[APIKeyData, str]]:
    """Optional API key validation - returns None if no key provided"""
    if not credentials:
        return None
    
    try:
        return await get_api_key_data(request, credentials, db)
    except HTTPException:
        # Log the attempt but don't raise exception for optional auth
        logger.warning(f"Invalid API key attempt from {request.client.host}")
        return None

def require_api_key(
    api_key_data: tuple[APIKeyData, str] = Depends(get_api_key_data)
) -> APIKeyData:
    """Require valid API key - dependency that raises exception if invalid"""
    return api_key_data[0]

def log_api_access(
    api_key_data: Optional[tuple[APIKeyData, str]],
    request: Request,
    action: str,
    details: dict = None
):
    """Log API access for security audit"""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    if api_key_data:
        api_key, endpoint = api_key_data
        logger.info(f"API Access: key={api_key.name} ({api_key.key_prefix}***), "
                   f"ip={client_ip}, ua='{user_agent}', action={action}, "
                   f"endpoint={endpoint}, details={details}")
    else:
        logger.warning(f"Unauthenticated API attempt: ip={client_ip}, ua='{user_agent}', "
                      f"action={action}, details={details}")