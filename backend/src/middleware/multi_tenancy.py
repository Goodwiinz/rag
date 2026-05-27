"""
Multi-tenancy middleware for RAG Analytics
Provides organization-based data isolation and tenant-aware request handling
"""

import logging
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable, Optional

import sentry_sdk
from fastapi import HTTPException, Request, Response, status
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.database import AsyncSessionLocal
from src.core.security import verify_token
from src.core.user_provisioning import ensure_user_and_org
from src.exceptions.analytics_exceptions import PermissionDeniedException
from src.middleware.responses import error_response
from src.models.organization import Organization
from src.models.user import User

logger = logging.getLogger(__name__)

# Context variables for tenant information
tenant_context: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)
user_context: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
role_context: ContextVar[Optional[str]] = ContextVar("user_role", default=None)


class MultiTenancyMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and validate tenant information from requests"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and set tenant context"""

        if self._should_skip_tenant_validation(request):
            return await call_next(request)

        try:
            async with AsyncSessionLocal() as db:
                tenant_info = await self._extract_tenant_info(request, db)

                if not tenant_info:
                    return await call_next(request)
                await self._validate_tenant_access(
                    tenant_info["organization_id"], db
                )

                request.state.db = db

                with tenant_context_manager(
                    organization_id=tenant_info["organization_id"],
                    user_id=tenant_info["user_id"],
                    user_role=tenant_info["role"],
                ):
                    request.state.tenant_id = tenant_info["organization_id"]
                    request.state.user_id = tenant_info["user_id"]
                    request.state.user_role = tenant_info["role"]
                    sentry_sdk.set_user({"id": str(tenant_info["user_id"])})
                    sentry_sdk.set_tag("tenant_id", str(tenant_info["organization_id"]))
                    return await call_next(request)

        except PermissionDeniedException as e:
            return error_response(403, str(e))
        except Exception as e:
            logger.error(f"Multi-tenancy middleware error: {e}")
            return error_response(500, "Internal server error during tenant validation", "internal_error")

    def _should_skip_tenant_validation(self, request: Request) -> bool:
        """Check if tenant validation should be skipped for this endpoint"""
        skip_paths = [
            "/health",
            "/auth/login",
            "/auth/register",
            "/auth/refresh",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/sentry-debug",
        ]

        return any(request.url.path.startswith(path) for path in skip_paths)

    async def _extract_tenant_info(
        self, request: Request, db: Optional[AsyncSession] = None
    ) -> Optional[dict]:
        """Extract tenant information by verifying the Bearer JWT and resolving org via DB."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]
        try:
            token_data = verify_token(token)
        except Exception:
            return None
        if not token_data or not token_data.user_id:
            return None

        # Fast path: org_id already embedded in JWT (CLI tokens, future Supabase tokens)
        if token_data.organization_id:
            # JIT-provision only when we haven't resolved the user from DB yet.
            # Uses a separate session to avoid tainting the caller's session
            # with a potential rollback from IntegrityError (duplicate insert).
            try:
                async with AsyncSessionLocal() as prov_db:
                    provisioned = await ensure_user_and_org(prov_db, token_data)
                    if provisioned:
                        await prov_db.commit()
            except Exception as e:
                logger.debug("JIT-provision skipped (non-fatal): %s", e)
            return {
                "organization_id": str(token_data.organization_id),
                "user_id": str(token_data.user_id),
                "role": token_data.role or "user",
            }

        # Fallback: resolve org from DB (current Supabase JWTs don't embed org_id).
        # Reuses the caller's session — no extra connection needed.
        try:
            result = await db.execute(
                select(User).where(User.id == token_data.user_id)
            )
            user = result.scalars().first()
            if not user:
                # User doesn't exist yet — JIT-provision, then re-query.
                try:
                    async with AsyncSessionLocal() as prov_db:
                        await ensure_user_and_org(prov_db, token_data)
                        await prov_db.commit()
                except Exception as e:
                    logger.debug("JIT-provision skipped (non-fatal): %s", e)
                result = await db.execute(
                    select(User).where(User.id == token_data.user_id)
                )
                user = result.scalars().first()
            if not user or not user.organization_id:
                return None
            return {
                "organization_id": str(user.organization_id),
                "user_id": str(token_data.user_id),
                "role": token_data.role or "user",
            }
        except Exception as e:
            logger.error(f"Error resolving tenant from token: {e}")
            return None

    async def _validate_tenant_access(
        self,
        organization_id: str,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        """Validate that the organization exists and is active"""
        try:
            if db is not None:
                result = await db.execute(
                    select(Organization).where(
                        Organization.id == organization_id,
                        Organization.is_active == True,
                    )
                )
                organization = result.scalars().first()
            else:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(Organization).where(
                            Organization.id == organization_id,
                            Organization.is_active == True,
                        )
                    )
                    organization = result.scalars().first()

            if not organization:
                raise PermissionDeniedException(
                    required_permission="organization_access",
                    user_role="unknown",
                    details={"organization_id": organization_id},
                )

            return True

        except PermissionDeniedException:
            raise
        except Exception as e:
            logger.error(f"Error validating tenant access: {e}")
            raise PermissionDeniedException(
                required_permission="organization_access",
                user_role="unknown",
                details={"organization_id": organization_id, "error": str(e)},
            )

# Row Level Security functions


def get_current_tenant_id() -> Optional[str]:
    """Get current tenant ID from context"""
    return tenant_context.get()


def get_current_user_id() -> Optional[str]:
    """Get current user ID from context"""
    return user_context.get()


def get_current_user_role() -> Optional[str]:
    """Get current user role from context"""
    return role_context.get()


# Database row-level security


def add_row_level_security_filters(query, model_class):
    """Add organization filter to query for row-level security"""
    tenant_id = get_current_tenant_id()

    if tenant_id and hasattr(model_class, "organization_id"):
        query = query.filter(model_class.organization_id == tenant_id)

    return query


def enforce_tenant_access(model_class):
    """Decorator to enforce tenant access on database operations"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tenant_id = get_current_tenant_id()

            if not tenant_id and hasattr(model_class, "organization_id"):
                raise PermissionDeniedException(
                    required_permission="tenant_access",
                    user_role=get_current_user_role() or "unknown",
                    details={"model": model_class.__name__},
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


# PostgreSQL Row Level Security setup


def setup_row_level_security(db: Session):
    """Set up PostgreSQL Row Level Security policies"""

    # Enable RLS on relevant tables
    tables_with_rls = [
        "documents",
        "users",
        "analytics_events",
        "user_sessions",
        "performance_logs",
        "quality_metrics",
    ]

    for table_name in tables_with_rls:
        try:
            # Enable RLS
            enable_rls_sql = f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;"
            db.execute(enable_rls_sql)

            # Create policy for organization-based access
            policy_sql = f"""
            CREATE POLICY tenant_isolation_policy ON {table_name}
                FOR ALL TO authenticated_role
                USING (organization_id = current_setting('app.current_organization_id')::uuid);
            """
            db.execute(policy_sql)

            logger.info(f"RLS policy created for table: {table_name}")

        except Exception as e:
            logger.warning(f"Failed to create RLS policy for {table_name}: {e}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to commit RLS policies: {e}")


# Context manager for setting organization context

from contextlib import contextmanager


@contextmanager
def tenant_context_manager(organization_id: str, user_id: str, user_role: str = "user"):
    """Context manager for setting tenant information"""
    try:
        # Set context
        token_tenant = tenant_context.set(organization_id)
        token_user = user_context.set(user_id)
        token_role = role_context.set(user_role)

        yield

    finally:
        # Reset context
        tenant_context.reset(token_tenant)
        user_context.reset(token_user)
        role_context.reset(token_role)


# Utility functions for tenant validation

# Role-based permissions mapping
ROLE_PERMISSIONS = {
    "super_admin": [
        "organization_create",
        "organization_read",
        "organization_update",
        "organization_delete",
        "organization_users_read",
        "organization_users_manage",
        "organization_analytics",
        "tenant_access",
        "cross_tenant_access",
        "update_access",
        "delete_access",
        "system_admin",
        "audit_logs",
        "security_management",
    ],
    "admin": [
        "organization_read",
        "organization_update",
        "organization_users_read",
        "organization_users_manage",
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


def check_tenant_permission(required_permission: str) -> bool:
    """Check if the current user has the required permission based on their role"""
    current_role = get_current_user_role()

    if not current_role:
        return False

    user_permissions = ROLE_PERMISSIONS.get(current_role, [])
    return required_permission in user_permissions


def validate_tenant_access(organization_id: str) -> bool:
    """Validate that current user has access to the specified organization"""
    current_tenant = get_current_tenant_id()

    if not current_tenant:
        return False

    return current_tenant == organization_id


def validate_cross_tenant_access(organization_ids: list) -> bool:
    """Validate access to multiple organizations (for admin users)"""
    current_role = get_current_user_role()
    current_tenant = get_current_tenant_id()

    # Admin users can access cross-tenant data
    if current_role in ["admin", "super_admin"]:
        return True

    # Regular users can only access their own tenant
    return current_tenant in organization_ids


# Database event listeners for automatic tenant filtering


@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(
    conn, cursor, statement, parameters, context, executemany
):
    """Add tenant filtering to SELECT queries automatically"""
    tenant_id = get_current_tenant_id()

    if tenant_id and statement.strip().upper().startswith("SELECT"):
        # TODO: Implement automatic query modification for tenant filtering
        # This is complex and requires SQL parsing - implement as needed
        pass


# Tenant-aware query builder


class TenantAwareQuery:
    """Helper class for building tenant-aware queries"""

    def __init__(self, db_session: Session, model_class):
        self.db = db_session
        self.model_class = model_class
        self.tenant_id = get_current_tenant_id()

    def filter_by_tenant(self):
        """Add tenant filter to query"""
        query = self.db.query(self.model_class)

        if self.tenant_id and hasattr(self.model_class, "organization_id"):
            query = query.filter(self.model_class.organization_id == self.tenant_id)

        return query

    def get_with_tenant_filter(self, entity_id: str):
        """Get entity by ID with tenant filter"""
        query = self.filter_by_tenant()
        return query.filter(self.model_class.id == entity_id).first()

    def create_with_tenant(self, **kwargs):
        """Create entity with current tenant context"""
        if self.tenant_id and hasattr(self.model_class, "organization_id"):
            kwargs["organization_id"] = self.tenant_id

        entity = self.model_class(**kwargs)
        self.db.add(entity)
        return entity

    def update_with_tenant_validation(self, entity_id: str, **kwargs):
        """Update entity with tenant validation"""
        entity = self.get_with_tenant_filter(entity_id)

        if not entity:
            raise PermissionDeniedException(
                required_permission="update_access",
                user_role=get_current_user_role() or "unknown",
                details={"entity_id": entity_id, "model": self.model_class.__name__},
            )

        for key, value in kwargs.items():
            setattr(entity, key, value)

        return entity

    def delete_with_tenant_validation(self, entity_id: str):
        """Delete entity with tenant validation"""
        entity = self.get_with_tenant_filter(entity_id)

        if not entity:
            raise PermissionDeniedException(
                required_permission="delete_access",
                user_role=get_current_user_role() or "unknown",
                details={"entity_id": entity_id, "model": self.model_class.__name__},
            )

        self.db.delete(entity)
        return entity


# Export main components
__all__ = [
    "MultiTenancyMiddleware",
    "get_current_tenant_id",
    "get_current_user_id",
    "get_current_user_role",
    "add_row_level_security_filters",
    "enforce_tenant_access",
    "setup_row_level_security",
    "tenant_context_manager",
    "check_tenant_permission",
    "validate_tenant_access",
    "validate_cross_tenant_access",
    "TenantAwareQuery",
    "ROLE_PERMISSIONS",
]
