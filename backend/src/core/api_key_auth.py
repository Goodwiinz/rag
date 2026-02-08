"""
API Key Authentication for Public Endpoints
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, UUID
import logging

from src.core.database import Base, get_db
from src.core.security import RateLimiter

logger = logging.getLogger(__name__)

# API Key Bearer scheme  
api_key_security = HTTPBearer()

class APIKey(Base):
    """API Key model for public endpoint access"""
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=lambda: str(secrets.token_hex(16)))
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

class APIKeyData(BaseModel):
    """API Key data model"""
    id: str
    name: str
    key_prefix: str
    is_active: bool
    rate_limit_per_hour: int
    last_used_at: Optional[datetime]
    usage_count: int

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

def generate_api_key() -> tuple[str, str]:
    """Generate API key and return (raw_key, hash)"""
    raw_key = f"rag_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(32))}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, key_hash

def verify_api_key(raw_key: str, key_hash: str) -> bool:
    """Verify API key against hash"""
    return hashlib.sha256(raw_key.encode()).hexdigest() == key_hash

# Rate limiter for API key endpoints
api_key_rate_limiter = RateLimiter(max_attempts=1000, window_minutes=60)

class APIKeyAuth:
    """API Key authentication and rate limiting"""
    
    def __init__(self):
        self.usage_tracking = {}  # Track usage per key for rate limiting
    
    def track_usage(self, key_id: str, endpoint: str):
        """Track API key usage for rate limiting"""
        now = datetime.utcnow()
        hour_key = now.replace(minute=0, second=0, microsecond=0)
        
        if key_id not in self.usage_tracking:
            self.usage_tracking[key_id] = {}
        
        if hour_key not in self.usage_tracking[key_id]:
            # Clean old entries
            self.usage_tracking[key_id] = {
                k: v for k, v in self.usage_tracking[key_id].items() 
                if k > now - timedelta(hours=1)
            }
            self.usage_tracking[key_id][hour_key] = 0
        
        self.usage_tracking[key_id][hour_key] += 1
        
        logger.info(f"API key usage tracked: key={key_id}, endpoint={endpoint}, hour={hour_key}")
    
    def check_rate_limit(self, key_id: str, rate_limit: int) -> bool:
        """Check if API key is within rate limit"""
        if key_id not in self.usage_tracking:
            return True
        
        now = datetime.utcnow()
        hour_key = now.replace(minute=0, second=0, microsecond=0)
        
        current_usage = self.usage_tracking[key_id].get(hour_key, 0)
        return current_usage < rate_limit
    
    def get_current_usage(self, key_id: str) -> int:
        """Get current hour usage for API key"""
        if key_id not in self.usage_tracking:
            return 0
        
        now = datetime.utcnow()
        hour_key = now.replace(minute=0, second=0, microsecond=0)
        return self.usage_tracking[key_id].get(hour_key, 0)

# Global API key auth instance
api_key_auth = APIKeyAuth()

async def get_api_key_data(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(api_key_security),
    db: Session = Depends(get_db)
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
        
        # Get key hash
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Find API key in database
        api_key_record = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()
        
        if not api_key_record:
            logger.warning(f"API key not found or inactive from {request.client.host}")
            raise credentials_exception
        
        # Check if expired
        if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
            logger.warning(f"Expired API key used: {api_key_record.key_prefix}***")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired"
            )
        
        # Check rate limit
        if not api_key_auth.check_rate_limit(api_key_record.id, api_key_record.rate_limit_per_hour):
            current_usage = api_key_auth.get_current_usage(api_key_record.id)
            logger.warning(f"Rate limit exceeded for API key {api_key_record.key_prefix}*** (usage: {current_usage}/{api_key_record.rate_limit_per_hour})")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Limit: {api_key_record.rate_limit_per_hour} requests per hour"
            )
        
        # Track usage
        endpoint = request.url.path
        api_key_auth.track_usage(api_key_record.id, endpoint)
        
        # Update usage stats in database
        api_key_record.last_used_at = datetime.utcnow()
        api_key_record.usage_count += 1
        db.commit()
        
        logger.info(f"Valid API key used: {api_key_record.name} ({api_key_record.key_prefix}***) from {request.client.host}")
        
        return APIKeyData(
            id=api_key_record.id,
            name=api_key_record.name, 
            key_prefix=api_key_record.key_prefix,
            is_active=api_key_record.is_active,
            rate_limit_per_hour=api_key_record.rate_limit_per_hour,
            last_used_at=api_key_record.last_used_at,
            usage_count=api_key_record.usage_count
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
    db: Session = Depends(get_db)
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