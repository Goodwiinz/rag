"""
Organization model for multi-tenancy
"""

from enum import Enum as PyEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import BaseModel


class StorageTier(PyEnum):
    """Storage tiers for organizations"""

    FREE = "free"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class Organization(BaseModel):
    """Organization model for multi-tenancy"""

    __tablename__ = "organizations"

    # Basic information
    name = Column(String(255), unique=True, index=True, nullable=False)

    # Storage configuration
    storage_tier = Column(Enum(StorageTier), nullable=False, default=StorageTier.FREE)
    storage_used_bytes = Column(BigInteger, default=0, nullable=False)
    storage_limit_bytes = Column(BigInteger, nullable=False)

    # Organization status
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    users = relationship("User", back_populates="organization")
    documents = relationship("Document", back_populates="organization")
    search_sessions = relationship("SearchSession", back_populates="organization")
    search_events = relationship("SearchEvent", back_populates="organization")
    roles = relationship("Role", back_populates="organization")

    # Analytics relationships (using string references to avoid circular imports)
    user_sessions = relationship(
        "src.models.user_session.UserSession", back_populates="organization"
    )
    analytics_events = relationship(
        "src.models.analytics_event.AnalyticsEvent", back_populates="organization"
    )
    performance_logs = relationship(
        "src.models.performance_log.PerformanceLog", back_populates="organization"
    )

    # Encrypted profile relationship
    encrypted_profile = relationship(
        "EncryptedOrganizationProfile", back_populates="organization", uselist=False
    )

    # Audit relationship
    audit_events = relationship("AuditEvent", back_populates="organization")

    # A/B Testing relationship
    ab_experiments = relationship("Experiment", back_populates="organization")

    def __repr__(self):
        return f"<Organization(name={self.name}, tier={self.storage_tier.value})>"

    @property
    def storage_limit_gb(self) -> float:
        """Get storage limit in GB"""
        return self.storage_limit_bytes / (1024**3)

    @property
    def storage_used_gb(self) -> float:
        """Get storage used in GB"""
        return self.storage_used_bytes / (1024**3)

    @property
    def storage_percentage_used(self) -> float:
        """Get percentage of storage used"""
        if self.storage_limit_bytes == 0:
            return 0.0
        return (self.storage_used_bytes / self.storage_limit_bytes) * 100

    @property
    def storage_available_bytes(self) -> int:
        """Get available storage in bytes"""
        return max(0, self.storage_limit_bytes - self.storage_used_bytes)

    @property
    def storage_available_gb(self) -> float:
        """Get available storage in GB"""
        return self.storage_available_bytes / (1024**3)

    def can_upload_file(self, file_size_bytes: int) -> bool:
        """Check if organization can upload a file of given size"""
        return (
            self.is_active
            and self.storage_available_bytes >= file_size_bytes
            and file_size_bytes <= self.max_file_size_bytes
        )

    @property
    def max_file_size_bytes(self) -> int:
        """Get maximum file size based on storage tier"""
        tier_limits = {
            StorageTier.FREE: 10 * 1024 * 1024,  # 10MB
            StorageTier.PROFESSIONAL: 100 * 1024 * 1024,  # 100MB
            StorageTier.ENTERPRISE: 1024 * 1024 * 1024,  # 1GB
        }
        return tier_limits.get(self.storage_tier, 10 * 1024 * 1024)

    @property
    def max_file_size_mb(self) -> float:
        """Get maximum file size in MB"""
        return self.max_file_size_bytes / (1024 * 1024)

    def update_storage_usage(self, size_change_bytes: int):
        """Update storage usage by adding/subtracting bytes"""
        new_usage = self.storage_used_bytes + size_change_bytes
        self.storage_used_bytes = max(0, new_usage)

    def check_storage_quota(self) -> dict:
        """Check storage quota status"""
        return {
            "tier": self.storage_tier.value,
            "limit_gb": self.storage_limit_gb,
            "used_gb": self.storage_used_gb,
            "available_gb": self.storage_available_gb,
            "percentage_used": self.storage_percentage_used,
            "max_file_size_mb": self.max_file_size_mb,
            "at_quota_limit": self.storage_percentage_used >= 100,
            "near_quota_limit": self.storage_percentage_used >= 90,
        }

    @classmethod
    def get_default_storage_limit(cls, tier: StorageTier) -> int:
        """Get default storage limit in bytes for a tier"""
        tier_limits = {
            StorageTier.FREE: 10 * 1024**3,  # 10GB
            StorageTier.PROFESSIONAL: 100 * 1024**3,  # 100GB
            StorageTier.ENTERPRISE: 1024 * 1024**3,  # 1TB
        }
        return tier_limits.get(tier, 10 * 1024**3)

    def to_dict(self) -> dict:
        """Convert to dictionary with computed fields"""
        data = super().to_dict()
        data.update(
            {
                "storage_tier": self.storage_tier.value,
                "storage_limit_gb": self.storage_limit_gb,
                "storage_used_gb": self.storage_used_gb,
                "storage_available_gb": self.storage_available_gb,
                "storage_percentage_used": self.storage_percentage_used,
                "max_file_size_mb": self.max_file_size_mb,
            }
        )
        return data
