"""
Tenant service for multi-tenancy support
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.postgres_models import TenantGraphSettings

logger = logging.getLogger(__name__)


class TenantService:
    """Service for managing tenant-specific configurations and access control"""

    def __init__(self):
        self.tenant_settings_cache = {}

    async def verify_tenant_access(self, tenant_id: str, resource: str, action: str = "read") -> bool:
        """Verify if tenant has access to a specific resource"""
        try:
            # Get tenant settings
            settings = await self.get_tenant_settings(tenant_id)

            # Check if tenant is active and has graph access
            if not settings:
                logger.warning(f"No settings found for tenant {tenant_id}")
                return False

            # Add more sophisticated access control logic here
            # For now, just check if tenant exists
            return True

        except Exception as e:
            logger.error(f"Error verifying tenant access for {tenant_id}: {e}")
            return False

    async def get_tenant_settings(self, tenant_id: str, db: AsyncSession = None) -> Optional[TenantGraphSettings]:
        """Get tenant-specific settings"""
        try:
            # Check cache first
            if tenant_id in self.tenant_settings_cache:
                return self.tenant_settings_cache[tenant_id]

            if db:
                # Query from database
                stmt = select(TenantGraphSettings).where(TenantGraphSettings.tenant_id == tenant_id)
                result = await db.execute(stmt)
                settings = result.scalar_one_or_none()

                if settings:
                    # Cache the settings
                    self.tenant_settings_cache[tenant_id] = settings
                    return settings
                else:
                    # Create default settings for new tenant
                    return await self.create_default_tenant_settings(tenant_id, db)

            return None

        except Exception as e:
            logger.error(f"Error getting tenant settings for {tenant_id}: {e}")
            return None

    async def create_default_tenant_settings(self, tenant_id: str, db: AsyncSession) -> TenantGraphSettings:
        """Create default settings for a new tenant"""
        try:
            settings = TenantGraphSettings(
                tenant_id=tenant_id,
                # Use default values from the model
            )

            db.add(settings)
            await db.commit()

            # Cache the settings
            self.tenant_settings_cache[tenant_id] = settings

            logger.info(f"Created default settings for tenant {tenant_id}")
            return settings

        except Exception as e:
            logger.error(f"Error creating default tenant settings for {tenant_id}: {e}")
            raise

    async def update_tenant_settings(
        self,
        tenant_id: str,
        updates: Dict[str, Any],
        db: AsyncSession
    ) -> Optional[TenantGraphSettings]:
        """Update tenant settings"""
        try:
            stmt = select(TenantGraphSettings).where(TenantGraphSettings.tenant_id == tenant_id)
            result = await db.execute(stmt)
            settings = result.scalar_one_or_none()

            if not settings:
                settings = await self.create_default_tenant_settings(tenant_id, db)

            # Update allowed fields
            allowed_fields = [
                'entity_confidence_threshold',
                'relationship_confidence_threshold',
                'max_entities_per_document',
                'max_relationships_per_document',
                'enable_caching',
                'cache_ttl_seconds',
                'enable_websocket_updates',
                'enable_analytics',
                'analytics_computation_interval',
                'enable_tenant_isolation',
                'max_api_requests_per_minute'
            ]

            for field, value in updates.items():
                if field in allowed_fields and hasattr(settings, field):
                    setattr(settings, field, value)

            await db.commit()

            # Update cache
            self.tenant_settings_cache[tenant_id] = settings

            logger.info(f"Updated settings for tenant {tenant_id}")
            return settings

        except Exception as e:
            logger.error(f"Error updating tenant settings for {tenant_id}: {e}")
            await db.rollback()
            return None

    async def delete_tenant_settings(self, tenant_id: str, db: AsyncSession) -> bool:
        """Delete tenant settings"""
        try:
            stmt = select(TenantGraphSettings).where(TenantGraphSettings.tenant_id == tenant_id)
            result = await db.execute(stmt)
            settings = result.scalar_one_or_none()

            if settings:
                await db.delete(settings)
                await db.commit()

                # Remove from cache
                if tenant_id in self.tenant_settings_cache:
                    del self.tenant_settings_cache[tenant_id]

                logger.info(f"Deleted settings for tenant {tenant_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting tenant settings for {tenant_id}: {e}")
            await db.rollback()
            return False

    def clear_tenant_cache(self, tenant_id: str):
        """Clear tenant settings from cache"""
        if tenant_id in self.tenant_settings_cache:
            del self.tenant_settings_cache[tenant_id]

    async def get_tenant_limits(self, tenant_id: str, db: AsyncSession) -> Dict[str, Any]:
        """Get tenant resource limits"""
        settings = await self.get_tenant_settings(tenant_id, db)
        if not settings:
            return {}

        return {
            "max_entities_per_document": settings.max_entities_per_document,
            "max_relationships_per_document": settings.max_relationships_per_document,
            "entity_confidence_threshold": settings.entity_confidence_threshold,
            "relationship_confidence_threshold": settings.relationship_confidence_threshold,
            "max_api_requests_per_minute": settings.max_api_requests_per_minute
        }

    async def is_feature_enabled(self, tenant_id: str, feature: str, db: AsyncSession) -> bool:
        """Check if a feature is enabled for tenant"""
        settings = await self.get_tenant_settings(tenant_id, db)
        if not settings:
            return False

        feature_mapping = {
            "caching": settings.enable_caching,
            "websocket_updates": settings.enable_websocket_updates,
            "analytics": settings.enable_analytics,
            "tenant_isolation": settings.enable_tenant_isolation
        }

        return feature_mapping.get(feature, False)


# Global tenant service instance
tenant_service = TenantService()