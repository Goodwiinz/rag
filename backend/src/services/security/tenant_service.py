"""
Tenant management services for multi-tenancy
Handles organization management, quotas, and tenant operations
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.exceptions.analytics_exceptions import (
    ConfigurationException,
    InsufficientDataException,
    PermissionDeniedException,
)
from src.models.document import Document
from src.models.organization import Organization, StorageTier
from src.models.user import User

logger = logging.getLogger(__name__)


class TenantService:
    """Service for managing tenant operations and quotas"""

    def __init__(self, db: Session = None):
        self.db = db or next(get_db())

    def create_organization(
        self, name: str, storage_tier: StorageTier = StorageTier.FREE
    ) -> Organization:
        """Create a new organization with default settings"""
        try:
            # Check if organization name already exists
            existing_org = (
                self.db.query(Organization).filter(Organization.name == name).first()
            )
            if existing_org:
                raise ConfigurationException(
                    config_key="organization_name",
                    config_value=name,
                    reason="Organization name already exists",
                )

            # Create new organization
            organization = Organization(
                name=name,
                storage_tier=storage_tier,
                storage_limit_bytes=Organization.get_default_storage_limit(
                    storage_tier
                ),
                storage_used_bytes=0,
                is_active=True,
            )

            self.db.add(organization)
            self.db.commit()
            self.db.refresh(organization)

            logger.info(f"Created organization: {name} with tier: {storage_tier.value}")
            return organization

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create organization {name}: {e}")
            raise

    def get_organization(self, organization_id: str) -> Optional[Organization]:
        """Get organization by ID with tenant validation"""
        from src.middleware.multi_tenancy import (
            get_current_tenant_id,
            validate_tenant_access,
        )

        # Validate tenant access
        if not validate_tenant_access(organization_id):
            raise PermissionDeniedException(
                required_permission="organization_read",
                user_role=get_current_user_role() or "unknown",
                details={"organization_id": organization_id},
            )

        return (
            self.db.query(Organization)
            .filter(Organization.id == organization_id)
            .first()
        )

    def update_organization(self, organization_id: str, **kwargs) -> Organization:
        """Update organization settings with tenant validation"""
        from src.middleware.multi_tenancy import (
            get_current_tenant_id,
            validate_tenant_access,
        )

        # Validate tenant access
        if not validate_tenant_access(organization_id):
            raise PermissionDeniedException(
                required_permission="organization_update",
                user_role=get_current_user_role() or "unknown",
                details={"organization_id": organization_id},
            )

        organization = (
            self.db.query(Organization)
            .filter(Organization.id == organization_id)
            .first()
        )
        if not organization:
            raise ConfigurationException(
                config_key="organization_id",
                config_value=organization_id,
                reason="Organization not found",
            )

        # Update allowed fields
        allowed_fields = ["name", "is_active"]
        for field, value in kwargs.items():
            if field in allowed_fields:
                setattr(organization, field, value)

        # Handle storage tier changes separately
        if "storage_tier" in kwargs:
            new_tier = kwargs["storage_tier"]
            if isinstance(new_tier, str):
                new_tier = StorageTier(new_tier)

            # Check if this would exceed new limits
            current_usage = organization.storage_used_bytes
            new_limit = Organization.get_default_storage_limit(new_tier)

            if current_usage > new_limit:
                raise ConfigurationException(
                    config_key="storage_tier",
                    config_value=new_tier.value,
                    reason=f"Current usage ({current_usage} bytes) exceeds new tier limit ({new_limit} bytes)",
                )

            organization.storage_tier = new_tier
            organization.storage_limit_bytes = new_limit

        self.db.commit()
        self.db.refresh(organization)

        logger.info(f"Updated organization: {organization_id}")
        return organization

    def upgrade_storage_tier(
        self, organization_id: str, new_tier: StorageTier
    ) -> Organization:
        """Upgrade organization storage tier"""
        organization = self.get_organization(organization_id)
        if not organization:
            raise ConfigurationException(
                config_key="organization_id",
                config_value=organization_id,
                reason="Organization not found",
            )

        # Only allow upgrades (not downgrades that would exceed limits)
        if (
            StorageTier[new_tier.value].value
            < StorageTier[organization.storage_tier.value].value
        ):
            current_usage = organization.storage_used_bytes
            new_limit = Organization.get_default_storage_limit(new_tier)

            if current_usage > new_limit:
                raise ConfigurationException(
                    config_key="storage_tier_downgrade",
                    config_value=new_tier.value,
                    reason=f"Current usage exceeds new tier limit",
                )

        return self.update_organization(organization_id, storage_tier=new_tier)

    def get_storage_quota_status(self, organization_id: str) -> Dict[str, Any]:
        """Get detailed storage quota status for organization"""
        organization = self.get_organization(organization_id)
        if not organization:
            raise ConfigurationException(
                config_key="organization_id",
                config_value=organization_id,
                reason="Organization not found",
            )

        # Get additional storage analytics
        document_stats = self._get_document_storage_stats(organization_id)

        quota_status = organization.check_storage_quota()
        quota_status.update(
            {
                "document_count": document_stats["document_count"],
                "file_type_breakdown": document_stats["file_type_breakdown"],
                "average_file_size_mb": document_stats["average_file_size_mb"],
                "largest_file_size_mb": document_stats["largest_file_size_mb"],
                "storage_efficiency_score": self._calculate_storage_efficiency(
                    organization_id, document_stats
                ),
            }
        )

        return quota_status

    def _get_document_storage_stats(self, organization_id: str) -> Dict[str, Any]:
        """Get detailed document storage statistics"""
        try:
            # Document count
            doc_count = (
                self.db.query(func.count(Document.id))
                .filter(Document.organization_id == organization_id)
                .scalar()
                or 0
            )

            # File type breakdown
            file_type_stats = (
                self.db.query(
                    Document.file_type,
                    func.count(Document.id).label("count"),
                    func.sum(Document.file_size_bytes).label("total_size"),
                )
                .filter(Document.organization_id == organization_id)
                .group_by(Document.file_type)
                .all()
            )

            file_type_breakdown = {
                stat.file_type: {
                    "count": stat.count,
                    "total_size_mb": (stat.total_size or 0) / (1024 * 1024),
                }
                for stat in file_type_stats
            }

            # Average and largest file sizes
            size_stats = (
                self.db.query(
                    func.avg(Document.file_size_bytes).label("avg_size"),
                    func.max(Document.file_size_bytes).label("max_size"),
                )
                .filter(
                    Document.organization_id == organization_id,
                    Document.file_size_bytes.isnot(None),
                )
                .first()
            )

            return {
                "document_count": doc_count,
                "file_type_breakdown": file_type_breakdown,
                "average_file_size_mb": (size_stats.avg_size or 0) / (1024 * 1024),
                "largest_file_size_mb": (size_stats.max_size or 0) / (1024 * 1024),
            }

        except Exception as e:
            logger.error(f"Error getting document storage stats: {e}")
            return {
                "document_count": 0,
                "file_type_breakdown": {},
                "average_file_size_mb": 0,
                "largest_file_size_mb": 0,
            }

    def _calculate_storage_efficiency(
        self, organization_id: str, stats: Dict[str, Any]
    ) -> float:
        """Calculate storage efficiency score (0-100)"""
        try:
            if stats["document_count"] == 0:
                return 100.0

            # Factors for efficiency calculation
            file_type_diversity = (
                len(stats["file_type_breakdown"]) / 10
            )  # Normalize to 0-1
            avg_file_size_score = min(
                stats["average_file_size_mb"] / 10, 1.0
            )  # Optimal around 10MB

            # Calculate efficiency score
            efficiency = (file_type_diversity * 30) + (avg_file_size_score * 70)
            return min(efficiency, 100.0)

        except Exception:
            return 50.0  # Default middle score

    def get_user_count(self, organization_id: str) -> int:
        """Get number of users in organization"""
        from src.middleware.multi_tenancy import validate_tenant_access

        if not validate_tenant_access(organization_id):
            raise PermissionDeniedException(
                required_permission="organization_users_read",
                user_role=get_current_user_role() or "unknown",
                details={"organization_id": organization_id},
            )

        return (
            self.db.query(func.count(User.id))
            .filter(User.organization_id == organization_id)
            .scalar()
            or 0
        )

    def get_organization_users(
        self, organization_id: str, limit: int = 50, offset: int = 0
    ) -> List[User]:
        """Get paginated list of users in organization"""
        from src.middleware.multi_tenancy import validate_tenant_access

        if not validate_tenant_access(organization_id):
            raise PermissionDeniedException(
                required_permission="organization_users_read",
                user_role=get_current_user_role() or "unknown",
                details={"organization_id": organization_id},
            )

        return (
            self.db.query(User)
            .filter(User.organization_id == organization_id)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_organization_analytics(
        self, organization_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """Get organization analytics summary"""
        from src.middleware.multi_tenancy import validate_tenant_access
        from src.models.analytics_event import AnalyticsEvent
        from src.models.user_session import UserSession

        if not validate_tenant_access(organization_id):
            raise PermissionDeniedException(
                required_permission="organization_analytics",
                user_role=get_current_user_role() or "unknown",
                details={"organization_id": organization_id},
            )

        start_date = datetime.utcnow() - timedelta(days=days)

        try:
            # Analytics events count
            events_count = (
                self.db.query(func.count(AnalyticsEvent.id))
                .filter(
                    and_(
                        AnalyticsEvent.organization_id == organization_id,
                        AnalyticsEvent.created_at >= start_date,
                    )
                )
                .scalar()
                or 0
            )

            # Active sessions count
            active_sessions = (
                self.db.query(func.count(UserSession.id))
                .filter(
                    and_(
                        UserSession.organization_id == organization_id,
                        UserSession.created_at >= start_date,
                    )
                )
                .scalar()
                or 0
            )

            # Storage growth
            storage_growth = self._calculate_storage_growth(organization_id, days)

            return {
                "period_days": days,
                "analytics_events_count": events_count,
                "active_sessions_count": active_sessions,
                "storage_growth_mb": storage_growth,
                "daily_averages": {
                    "events_per_day": events_count / max(days, 1),
                    "sessions_per_day": active_sessions / max(days, 1),
                    "storage_growth_per_day_mb": storage_growth / max(days, 1),
                },
            }

        except Exception as e:
            logger.error(f"Error getting organization analytics: {e}")
            return {
                "period_days": days,
                "analytics_events_count": 0,
                "active_sessions_count": 0,
                "storage_growth_mb": 0,
                "daily_averages": {
                    "events_per_day": 0,
                    "sessions_per_day": 0,
                    "storage_growth_per_day_mb": 0,
                },
                "error": str(e),
            }

    def _calculate_storage_growth(self, organization_id: str, days: int) -> float:
        """Calculate storage growth in MB over specified period"""
        try:
            # This is a simplified calculation
            # In production, you'd track historical storage usage
            current_usage = (
                self.db.query(func.sum(Document.file_size_bytes))
                .filter(Document.organization_id == organization_id)
                .scalar()
                or 0
            )

            # Estimate growth based on recent uploads
            recent_uploads = (
                self.db.query(func.sum(Document.file_size_bytes))
                .filter(
                    and_(
                        Document.organization_id == organization_id,
                        Document.created_at >= datetime.utcnow() - timedelta(days=days),
                    )
                )
                .scalar()
                or 0
            )

            return recent_uploads / (1024 * 1024)  # Convert to MB

        except Exception:
            return 0.0

    def validate_organization_limits(self, organization_id: str) -> Dict[str, Any]:
        """Validate organization against various limits and return status"""
        organization = self.get_organization(organization_id)
        if not organization:
            raise ConfigurationException(
                config_key="organization_id",
                config_value=organization_id,
                reason="Organization not found",
            )

        user_count = self.get_user_count(organization_id)
        document_count = self._get_document_storage_stats(organization_id)[
            "document_count"
        ]

        # Define limits per tier
        tier_limits = {
            StorageTier.FREE: {
                "max_users": 5,
                "max_documents": 100,
                "api_calls_per_day": 1000,
            },
            StorageTier.PROFESSIONAL: {
                "max_users": 50,
                "max_documents": 5000,
                "api_calls_per_day": 10000,
            },
            StorageTier.ENTERPRISE: {
                "max_users": None,  # Unlimited
                "max_documents": None,  # Unlimited
                "api_calls_per_day": None,  # Unlimited
            },
        }

        limits = tier_limits.get(organization.storage_tier, {})

        validation_result = {
            "organization_id": organization_id,
            "storage_tier": organization.storage_tier.value,
            "limits_status": {
                "storage": {
                    "used": organization.storage_used_gb,
                    "limit": organization.storage_limit_gb,
                    "percentage": organization.storage_percentage_used,
                    "status": "ok"
                    if organization.storage_percentage_used < 90
                    else "warning",
                },
                "users": {
                    "used": user_count,
                    "limit": limits.get("max_users", "unlimited"),
                    "status": "ok"
                    if limits.get("max_users") is None
                    or user_count < limits.get("max_users")
                    else "exceeded",
                },
                "documents": {
                    "used": document_count,
                    "limit": limits.get("max_documents", "unlimited"),
                    "status": "ok"
                    if limits.get("max_documents") is None
                    or document_count < limits.get("max_documents")
                    else "exceeded",
                },
            },
            "overall_status": "ok",
        }

        # Determine overall status
        for limit_type, limit_info in validation_result["limits_status"].items():
            if limit_info["status"] == "exceeded":
                validation_result["overall_status"] = "error"
            elif (
                limit_info["status"] == "warning"
                and validation_result["overall_status"] == "ok"
            ):
                validation_result["overall_status"] = "warning"

        return validation_result

    def close(self):
        """Close database session"""
        if self.db:
            self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Utility functions


def get_tenant_service() -> TenantService:
    """Get tenant service instance"""
    return TenantService()


def check_tenant_permission(
    required_permission: str, organization_id: str = None
) -> bool:
    """Check if current user has permission for tenant operation"""
    from src.middleware.multi_tenancy import (
        get_current_tenant_id,
        get_current_user_role,
    )

    current_role = get_current_user_role()
    current_tenant = get_current_tenant_id()

    # Super admins have all permissions
    if current_role == "super_admin":
        return True

    # Check organization access if specified
    if organization_id and current_tenant != organization_id:
        return False

    # Role-based permissions
    role_permissions = {
        "admin": [
            "organization_read",
            "organization_update",
            "organization_users_read",
            "organization_analytics",
            "tenant_access",
            "update_access",
            "delete_access",
        ],
        "content_manager": [
            "organization_read",
            "organization_users_read",
            "tenant_access",
            "update_access",
        ],
        "analyst": ["organization_read", "organization_analytics", "tenant_access"],
        "user": ["organization_read", "tenant_access"],
    }

    user_permissions = role_permissions.get(current_role, [])
    return required_permission in user_permissions
