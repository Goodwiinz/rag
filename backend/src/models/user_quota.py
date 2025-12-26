"""
User Storage Quota model for managing individual user storage limits and usage
"""

import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Enum, ForeignKey, Text, JSON, BigInteger
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from datetime import datetime, timezone as dt_timezone
from typing import Optional

from .base import BaseModel, GUID

class QuotaStatus(PyEnum):
    """Quota status types"""
    HEALTHY = "healthy"           # Under 80% usage
    WARNING = "warning"           # 80-95% usage
    CRITICAL = "critical"         # 95-99% usage
    EXCEEDED = "exceeded"         # Over quota
    SUSPENDED = "suspended"       # Account suspended due to overage

class QuotaType(PyEnum):
    """Types of quotas"""
    STORAGE = "storage"           # File storage quota
    DOCUMENTS = "documents"       # Number of documents quota
    QUERIES = "queries"          # Monthly query quota
    BANDWIDTH = "bandwidth"       # Monthly bandwidth quota

class UserQuota(BaseModel):
    """User storage quota and usage tracking model"""

    __tablename__ = "user_quotas"

    # User reference
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False, index=True)

    # Storage quotas (in bytes)
    storage_quota_bytes = Column(BigInteger, nullable=False, default=5*1024*1024*1024)  # 5GB default
    storage_used_bytes = Column(BigInteger, nullable=False, default=0)
    storage_allocated_bytes = Column(BigInteger, nullable=False, default=0)  # Sum of document sizes

    # Document quotas
    document_quota = Column(Integer, nullable=False, default=1000)  # Max documents
    document_count = Column(Integer, nullable=False, default=0)

    # Query quotas
    monthly_query_quota = Column(Integer, nullable=False, default=10000)  # Max queries per month
    monthly_query_count = Column(Integer, nullable=False, default=0)
    current_month_queries = Column(Integer, nullable=False, default=0)

    # Bandwidth quotas (in bytes per month)
    monthly_bandwidth_quota_bytes = Column(BigInteger, nullable=False, default=100*1024*1024*1024)  # 100GB
    monthly_bandwidth_used_bytes = Column(BigInteger, nullable=False, default=0)

    # File size limits
    max_file_size_bytes = Column(BigInteger, nullable=False, default=50*1024*1024)  # 50MB
    allowed_file_types = Column(JSON, nullable=True)  # List of allowed MIME types

    # Quota status
    quota_status = Column(Enum(QuotaStatus), nullable=False, default=QuotaStatus.HEALTHY, index=True)
    status_updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Usage tracking
    last_usage_calculation = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    usage_calculation_error = Column(Text, nullable=True)
    usage_calculation_retry_count = Column(Integer, default=0, nullable=False)

    # Notifications
    warning_sent_at = Column(DateTime(timezone=True), nullable=True)
    critical_sent_at = Column(DateTime(timezone=True), nullable=True)
    exceeded_sent_at = Column(DateTime(timezone=True), nullable=True)
    suspension_sent_at = Column(DateTime(timezone=True), nullable=True)

    # Grace period
    grace_period_ends_at = Column(DateTime(timezone=True), nullable=True)
    is_suspended = Column(Boolean, default=False, nullable=False)
    suspension_reason = Column(Text, nullable=True)

    # Auto-cleanup settings
    enable_auto_cleanup = Column(Boolean, default=False, nullable=False)
    cleanup_threshold_days = Column(Integer, default=365, nullable=False)  # Clean docs older than this
    last_cleanup_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="quota")
    organization = relationship("Organization")
    quota_adjustments = relationship("QuotaAdjustment", back_populates="user_quota", cascade="all, delete-orphan")
    quota_alerts = relationship("QuotaAlert", back_populates="user_quota", cascade="all, delete-orphan")
    usage_snapshots = relationship("UsageSnapshot", back_populates="user_quota", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserQuota(user_id={self.user_id}, status={self.quota_status.value}, usage={self.storage_percentage}%)>"

    @property
    def storage_percentage(self) -> float:
        """Get storage usage as percentage"""
        if self.storage_quota_bytes == 0:
            return 100.0
        return (self.storage_used_bytes / self.storage_quota_bytes) * 100

    @property
    def storage_remaining_bytes(self) -> int:
        """Get remaining storage in bytes"""
        return max(0, self.storage_quota_bytes - self.storage_used_bytes)

    @property
    def storage_remaining_mb(self) -> float:
        """Get remaining storage in MB"""
        return self.storage_remaining_bytes / (1024 * 1024)

    @property
    def storage_used_mb(self) -> float:
        """Get used storage in MB"""
        return self.storage_used_bytes / (1024 * 1024)

    @property
    def storage_quota_mb(self) -> float:
        """Get storage quota in MB"""
        return self.storage_quota_bytes / (1024 * 1024)

    @property
    def document_percentage(self) -> float:
        """Get document usage as percentage"""
        if self.document_quota == 0:
            return 100.0
        return (self.document_count / self.document_quota) * 100

    @property
    def query_percentage(self) -> float:
        """Get monthly query usage as percentage"""
        if self.monthly_query_quota == 0:
            return 100.0
        return (self.current_month_queries / self.monthly_query_quota) * 100

    @property
    def bandwidth_percentage(self) -> float:
        """Get monthly bandwidth usage as percentage"""
        if self.monthly_bandwidth_quota_bytes == 0:
            return 100.0
        return (self.monthly_bandwidth_used_bytes / self.monthly_bandwidth_quota_bytes) * 100

    @property
    def is_over_quota(self) -> bool:
        """Check if user is over any quota"""
        return (
            self.storage_used_bytes > self.storage_quota_bytes or
            self.document_count > self.document_quota or
            self.current_month_queries > self.monthly_query_quota or
            self.monthly_bandwidth_used_bytes > self.monthly_bandwidth_quota_bytes
        )

    @property
    def can_upload_file(self, file_size_bytes: int) -> bool:
        """Check if user can upload a file of given size"""
        return (
            not self.is_suspended and
            self.storage_used_bytes + file_size_bytes <= self.storage_quota_bytes and
            file_size_bytes <= self.max_file_size_bytes
        )

    @property
    def days_until_cleanup(self) -> Optional[int]:
        """Get days until automatic cleanup"""
        if not self.enable_auto_cleanup or not self.cleanup_threshold_days:
            return None
        # This would typically be calculated based on oldest document
        return None

    def update_storage_usage(self, delta_bytes: int):
        """Update storage usage by adding/subtracting bytes"""
        self.storage_used_bytes = max(0, self.storage_used_bytes + delta_bytes)
        self.last_usage_calculation = datetime.utcnow()
        self._update_quota_status()

    def update_document_count(self, delta: int):
        """Update document count"""
        self.document_count = max(0, self.document_count + delta)
        self._update_quota_status()

    def update_query_count(self):
        """Increment monthly query count"""
        self.current_month_queries += 1
        self._update_quota_status()

    def update_bandwidth_usage(self, delta_bytes: int):
        """Update monthly bandwidth usage"""
        self.monthly_bandwidth_used_bytes = max(0, self.monthly_bandwidth_used_bytes + delta_bytes)
        self._update_quota_status()

    def reset_monthly_counters(self):
        """Reset monthly counters (called at start of month)"""
        self.current_month_queries = 0
        self.monthly_bandwidth_used_bytes = 0

    def _update_quota_status(self):
        """Update quota status based on current usage"""
        old_status = self.quota_status

        if self.is_over_quota:
            self.quota_status = QuotaStatus.EXCEEDED
        elif self.storage_percentage >= 95:
            self.quota_status = QuotaStatus.CRITICAL
        elif self.storage_percentage >= 80:
            self.quota_status = QuotaStatus.WARNING
        else:
            self.quota_status = QuotaStatus.HEALTHY

        if old_status != self.quota_status:
            self.status_updated_at = datetime.utcnow()

    def grant_grace_period(self, days: int = 7):
        """Grant grace period for quota overage"""
        self.grace_period_ends_at = datetime.utcnow() + timedelta(days=days)

    def suspend_account(self, reason: str = "Quota exceeded"):
        """Suspend account due to quota overage"""
        self.is_suspended = True
        self.suspension_reason = reason
        self.quota_status = QuotaStatus.SUSPENDED
        self.status_updated_at = datetime.utcnow()

    def unsuspend_account(self):
        """Unsuspend account"""
        self.is_suspended = False
        self.suspension_reason = None
        self._update_quota_status()

    def adjust_quota(self, storage_bytes: int = None, document_count: int = None,
                    query_quota: int = None, reason: str = None):
        """Adjust user quota limits"""
        if storage_bytes is not None:
            self.storage_quota_bytes = storage_bytes
        if document_count is not None:
            self.document_quota = document_count
        if query_quota is not None:
            self.monthly_query_quota = query_quota

        # Create quota adjustment record
        adjustment = QuotaAdjustment(
            user_quota_id=self.id,
            storage_bytes_delta=storage_bytes - self.storage_quota_bytes if storage_bytes else 0,
            document_count_delta=document_count - self.document_count if document_count else 0,
            query_quota_delta=query_quota - self.monthly_query_quota if query_quota else 0,
            reason=reason
        )
        self.quota_adjustments.append(adjustment)
        self._update_quota_status()

    def get_usage_summary(self) -> dict:
        """Get comprehensive usage summary"""
        return {
            'storage': {
                'used_mb': self.storage_used_mb,
                'quota_mb': self.storage_quota_mb,
                'remaining_mb': self.storage_remaining_mb,
                'percentage': self.storage_percentage,
                'status': self.quota_status.value
            },
            'documents': {
                'count': self.document_count,
                'quota': self.document_quota,
                'percentage': self.document_percentage
            },
            'queries': {
                'current_month': self.current_month_queries,
                'quota': self.monthly_query_quota,
                'percentage': self.query_percentage
            },
            'bandwidth': {
                'used_mb': self.monthly_bandwidth_used_bytes / (1024 * 1024),
                'quota_mb': self.monthly_bandwidth_quota_bytes / (1024 * 1024),
                'percentage': self.bandwidth_percentage
            },
            'limits': {
                'max_file_size_mb': self.max_file_size_bytes / (1024 * 1024),
                'allowed_file_types': self.allowed_file_types
            },
            'status': {
                'is_suspended': self.is_suspended,
                'suspension_reason': self.suspension_reason,
                'grace_period_ends': self.grace_period_ends_at.isoformat() if self.grace_period_ends_at else None
            }
        }

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        data = super().to_dict()

        # Convert enum values
        data['quota_status'] = self.quota_status.value if self.quota_status else None

        # Add computed fields
        data.update({
            'storage_percentage': self.storage_percentage,
            'storage_remaining_mb': self.storage_remaining_mb,
            'storage_used_mb': self.storage_used_mb,
            'storage_quota_mb': self.storage_quota_mb,
            'document_percentage': self.document_percentage,
            'query_percentage': self.query_percentage,
            'bandwidth_percentage': self.bandwidth_percentage,
            'is_over_quota': self.is_over_quota,
            'days_until_cleanup': self.days_until_cleanup
        })

        return data

    @classmethod
    def get_users_over_quota(cls, organization_id: Optional[uuid.UUID] = None) -> list:
        """Get users who are over their quota"""
        query = cls.query.filter(
            cls.quota_status.in_([QuotaStatus.EXCEEDED, QuotaStatus.CRITICAL]),
            cls.is_deleted == False
        )

        if organization_id:
            query = query.filter(cls.organization_id == organization_id)

        return query.all()

    @classmethod
    def get_users_nearing_quota(cls, organization_id: Optional[uuid.UUID] = None, threshold: float = 80.0) -> list:
        """Get users nearing their quota limit"""
        query = cls.query.filter(
            cls.quota_status == QuotaStatus.WARNING,
            cls.is_deleted == False
        )

        if organization_id:
            query = query.filter(cls.organization_id == organization_id)

        return query.all()


class QuotaAdjustment(BaseModel):
    """Record of quota adjustments for audit trail"""

    __tablename__ = "quota_adjustments"

    user_quota_id = Column(GUID(), ForeignKey("user_quotas.id"), nullable=False)

    # Adjustment details
    storage_bytes_delta = Column(BigInteger, nullable=False, default=0)
    document_count_delta = Column(Integer, nullable=False, default=0)
    query_quota_delta = Column(Integer, nullable=False, default=0)
    bandwidth_quota_delta = Column(BigInteger, nullable=False, default=0)

    # Adjustment metadata
    reason = Column(Text, nullable=True)
    adjusted_by_user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)
    adjustment_type = Column(String(50), nullable=False, default="manual")  # manual, automatic, promotion

    # Previous values for audit
    previous_storage_quota = Column(BigInteger, nullable=True)
    previous_document_quota = Column(Integer, nullable=True)
    previous_query_quota = Column(Integer, nullable=True)

    # Relationships
    user_quota = relationship("UserQuota", back_populates="quota_adjustments")
    adjusted_by_user = relationship("User")


class QuotaAlert(BaseModel):
    """Quota alert notifications sent to users"""

    __tablename__ = "quota_alerts"

    user_quota_id = Column(GUID(), ForeignKey("user_quotas.id"), nullable=False)

    # Alert details
    alert_type = Column(String(50), nullable=False)  # warning, critical, exceeded, suspension
    alert_threshold = Column(Float, nullable=True)  # Percentage threshold that triggered alert

    # Alert content
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    email_sent = Column(Boolean, default=False, nullable=False)
    in_app_sent = Column(Boolean, default=False, nullable=False)

    # Delivery tracking
    sent_at = Column(DateTime(timezone=True), nullable=True)
    email_sent_at = Column(DateTime(timezone=True), nullable=True)
    in_app_sent_at = Column(DateTime(timezone=True), nullable=True)
    delivery_error = Column(Text, nullable=True)

    # User interaction
    read_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    action_taken = Column(String(100), nullable=True)  # upgrade, cleanup, ignore

    # Relationships
    user_quota = relationship("UserQuota", back_populates="quota_alerts")


class UsageSnapshot(BaseModel):
    """Periodic usage snapshots for analytics and trend analysis"""

    __tablename__ = "usage_snapshots"

    user_quota_id = Column(GUID(), ForeignKey("user_quotas.id"), nullable=False)

    # Snapshot period
    snapshot_date = Column(DateTime(timezone=True), nullable=False, index=True)
    snapshot_type = Column(String(20), nullable=False, default="daily")  # daily, weekly, monthly

    # Usage metrics at snapshot time
    storage_used_bytes = Column(BigInteger, nullable=False)
    document_count = Column(Integer, nullable=False)
    monthly_query_count = Column(Integer, nullable=False)
    monthly_bandwidth_used_bytes = Column(BigInteger, nullable=False)

    # Growth metrics
    storage_growth_24h = Column(BigInteger, nullable=False, default=0)
    document_growth_24h = Column(Integer, nullable=False, default=0)
    query_growth_24h = Column(Integer, nullable=False, default=0)

    # System metrics
    processing_queue_size = Column(Integer, nullable=False, default=0)
    failed_documents_24h = Column(Integer, nullable=False, default=0)
    average_query_latency_ms = Column(Float, nullable=True)

    # Relationships
    user_quota = relationship("UserQuota", back_populates="usage_snapshots")

    @classmethod
    def create_daily_snapshot(cls, user_quota_id: uuid.UUID):
        """Create daily usage snapshot"""
        from datetime import date
        snapshot_date = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=dt_timezone.utc)

        # Check if snapshot already exists for today
        existing = cls.query.filter(
            cls.user_quota_id == user_quota_id,
            cls.snapshot_date == snapshot_date,
            cls.snapshot_type == "daily"
        ).first()

        if existing:
            return existing

        return cls(
            user_quota_id=user_quota_id,
            snapshot_date=snapshot_date,
            snapshot_type="daily"
        )