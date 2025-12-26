"""
User session model for T3 analytics
Tracks user sessions for behavior analytics and engagement metrics
"""

from sqlalchemy import Column, String, Text, Integer, Float, DateTime, Boolean, JSON, ForeignKey, Index, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from .base import BaseModel, GUID


class SessionStatus(enum.Enum):
    """User session status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class UserSession(BaseModel):
    """
    User session tracking for analytics
    """
    __tablename__ = "user_sessions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # User and organization
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    # Session identifiers
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    session_token = Column(String(512), nullable=True)  # For session validation

    # Session metadata
    status = Column(Enum(SessionStatus), default=SessionStatus.ACTIVE, nullable=False)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    device_type = Column(String(50), nullable=True)  # mobile, desktop, tablet, etc.
    browser = Column(String(100), nullable=True)
    os = Column(String(100), nullable=True)
    location_country = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    location_city = Column(String(100), nullable=True)

    # Session timing
    started_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_activity = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)  # Calculated on session end

    # Session metrics
    total_searches = Column(Integer, default=0, nullable=False)
    total_documents_viewed = Column(Integer, default=0, nullable=False)
    total_downloads = Column(Integer, default=0, nullable=False)
    total_clicks = Column(Integer, default=0, nullable=False)
    engagement_score = Column(Float, default=0.0, nullable=False)

    # Behavioral data
    search_queries = Column(JSONB, nullable=True)  # List of search queries
    viewed_documents = Column(JSONB, nullable=True)  # List of document IDs
    clicked_results = Column(JSONB, nullable=True)  # Click result tracking
    navigation_path = Column(JSONB, nullable=True)  # Page navigation flow

    # Session quality metrics
    bounce_rate = Column(Float, default=0.0, nullable=False)
    conversion_events = Column(JSONB, nullable=True)  # Track important actions
    satisfaction_rating = Column(Integer, nullable=True)  # 1-5 user rating

    # Technical metrics
    avg_response_time = Column(Float, nullable=True)  # Average API response time
    error_count = Column(Integer, default=0, nullable=False)
    page_load_time = Column(Float, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)

    # Relationships
    user = relationship("User", back_populates="sessions")
    organization = relationship("Organization", back_populates="user_sessions")

    # Indexes for performance
    __table_args__ = (
        Index('idx_user_sessions_user_id', 'user_id'),
        Index('idx_user_sessions_organization_id', 'organization_id'),
        Index('idx_user_sessions_session_id', 'session_id'),
        Index('idx_user_sessions_status', 'status'),
        Index('idx_user_sessions_started_at', 'started_at'),
        Index('idx_user_sessions_last_activity', 'last_activity'),
        Index('idx_user_sessions_user_org', 'user_id', 'organization_id'),
        Index('idx_user_sessions_active_sessions', 'user_id', 'status', 'last_activity'),
    )

    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, session_id={self.session_id}, status={self.status.value})>"

    def is_active(self):
        """Check if session is currently active"""
        return self.status == SessionStatus.ACTIVE and self.ended_at is None

    def is_expired(self, max_age_hours=24):
        """Check if session has expired based on last activity"""
        if not self.last_activity:
            return True
        return (datetime.utcnow() - self.last_activity).total_seconds() > (max_age_hours * 3600)

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def end_session(self):
        """End the current session and calculate duration"""
        if self.ended_at is None:
            self.ended_at = datetime.utcnow()
            self.duration_seconds = int((self.ended_at - self.started_at).total_seconds())
            if self.status == SessionStatus.ACTIVE:
                self.status = SessionStatus.INACTIVE
            self.updated_at = datetime.utcnow()

    def calculate_engagement_score(self):
        """Calculate engagement score based on session activity"""
        score = 0.0

        # Use safe access with fallback to 0
        total_searches = self.total_searches or 0
        total_documents_viewed = self.total_documents_viewed or 0
        total_downloads = self.total_downloads or 0
        total_clicks = self.total_clicks or 0
        duration_seconds = self.duration_seconds or 0

        # Base score for having activity
        if total_searches > 0:
            score += 20

        # Search activity
        score += min(total_searches * 2, 30)

        # Document interaction
        score += min(total_documents_viewed * 3, 25)

        # Download activity
        score += min(total_downloads * 5, 15)

        # Click activity
        score += min(total_clicks * 0.5, 10)

        # Duration bonus
        if duration_seconds:
            duration_minutes = duration_seconds / 60
            score += min(duration_minutes * 0.5, 10)

        self.engagement_score = min(score, 100.0)  # Cap at 100
        return self.engagement_score

    def add_search_event(self, query, results_count=0, response_time=0):
        """Add a search event to the session"""
        if not self.search_queries:
            self.search_queries = []

        search_event = {
            "query": query,
            "timestamp": datetime.utcnow().isoformat(),
            "results_count": results_count,
            "response_time": response_time
        }
        self.search_queries.append(search_event)
        self.total_searches = (self.total_searches or 0) + 1
        self.update_activity()

    def add_document_view(self, document_id, view_duration=0):
        """Add a document view event"""
        if not self.viewed_documents:
            self.viewed_documents = []

        view_event = {
            "document_id": str(document_id),
            "timestamp": datetime.utcnow().isoformat(),
            "view_duration_seconds": view_duration
        }
        self.viewed_documents.append(view_event)
        self.total_documents_viewed = (self.total_documents_viewed or 0) + 1
        self.update_activity()

    def add_download_event(self, document_id):
        """Add a download event"""
        if not self.conversion_events:
            self.conversion_events = []

        download_event = {
            "type": "download",
            "document_id": str(document_id),
            "timestamp": datetime.utcnow().isoformat()
        }
        self.conversion_events.append(download_event)
        self.total_downloads = (self.total_downloads or 0) + 1
        self.update_activity()

    def get_session_summary(self):
        """Get a summary of session activity"""
        return {
            "session_id": self.session_id,
            "duration_seconds": self.duration_seconds,
            "total_searches": self.total_searches,
            "total_documents_viewed": self.total_documents_viewed,
            "total_downloads": self.total_downloads,
            "engagement_score": self.engagement_score,
            "bounce_rate": self.bounce_rate,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None
        }