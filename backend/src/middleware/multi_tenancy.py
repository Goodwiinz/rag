"""
Multi-tenancy middleware for RAG Analytics
Provides organization-based data isolation and tenant-aware request handling
"""

import logging
from typing import Optional, Callable, Any
from functools import wraps
from contextvars import ContextVar
from fastapi import HTTPException, status, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import event
from sqlalchemy.engine import Engine

from src.core.database import get_db
from src.models.user import User
from src.models.organization import Organization
from src.exceptions.analytics_exceptions import PermissionDeniedException

logger = logging.getLogger(__name__)

# Context variables for tenant information
tenant_context: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)
user_context: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
role_context: ContextVar[Optional[str]] = ContextVar('user_role', default=None)


class MultiTenancyMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and validate tenant information from requests"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and set tenant context"""

        # Skip tenant validation for health checks and auth endpoints
        if self._should_skip_tenant_validation(request):
            response = await call_next(request)
            return response

        try:
            # Extract tenant information from JWT token
            tenant_info = await self._extract_tenant_info(request)

            if tenant_info:
                # Set tenant context
                tenant_context.set(tenant_info['organization_id'])
                user_context.set(tenant_info['user_id'])
                role_context.set(tenant_info['role'])

                # Validate tenant access
                await self._validate_tenant_access(tenant_info['organization_id'], request)

                # Add tenant info to request state
                request.state.tenant_id = tenant_info['organization_id']
                request.state.user_id = tenant_info['user_id']
                request.state.user_role = tenant_info['role']

            response = await call_next(request)

            # Clear tenant context after request
            self._clear_tenant_context()

            return response

        except PermissionDeniedException as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Multi-tenancy middleware error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during tenant validation"
            )

    def _should_skip_tenant_validation(self, request: Request) -> bool:
        """Check if tenant validation should be skipped for this endpoint"""
        skip_paths = [
            '/health',
            '/auth/login',
            '/auth/register',
            '/auth/refresh',
            '/docs',
            '/redoc',
            '/openapi.json'
        ]

        return any(request.url.path.startswith(path) for path in skip_paths)

    async def _extract_tenant_info(self, request: Request) -> Optional[dict]:
        """Extract tenant information from JWT token or session"""
        try:
            # Try to get user from request state (set by auth middleware)
            if hasattr(request.state, 'user'):
                user = request.state.user
                return {
                    'organization_id': str(user.organization_id),
                    'user_id': str(user.id),
                    'role': user.role.value if user.role else 'user'
                }

            # TODO: Implement JWT token extraction if needed
            # For now, we'll rely on auth middleware to set user info

            return None

        except Exception as e:
            logger.error(f"Error extracting tenant info: {e}")
            return None

    async def _validate_tenant_access(self, organization_id: str, request: Request) -> bool:
        """Validate that the organization exists and is active"""
        try:
            db = next(get_db())

            # Check if organization exists and is active
            organization = db.query(Organization).filter(
                Organization.id == organization_id,
                Organization.is_active == True
            ).first()

            if not organization:
                raise PermissionDeniedException(
                    required_permission="organization_access",
                    user_role="unknown",
                    details={"organization_id": organization_id}
                )

            db.close()
            return True

        except PermissionDeniedException:
            raise
        except Exception as e:
            logger.error(f"Error validating tenant access: {e}")
            raise PermissionDeniedException(
                required_permission="organization_access",
                user_role="unknown",
                details={"organization_id": organization_id, "error": str(e)}
            )

    def _clear_tenant_context(self):
        """Clear tenant context variables"""
        tenant_context.set(None)
        user_context.set(None)
        role_context.set(None)


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

    if tenant_id and hasattr(model_class, 'organization_id'):
        query = query.filter(model_class.organization_id == tenant_id)

    return query


def enforce_tenant_access(model_class):
    """Decorator to enforce tenant access on database operations"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tenant_id = get_current_tenant_id()

            if not tenant_id and hasattr(model_class, 'organization_id'):
                raise PermissionDeniedException(
                    required_permission="tenant_access",
                    user_role=get_current_user_role() or "unknown",
                    details={"model": model_class.__name__}
                )

            return func(*args, **kwargs)
        return wrapper
    return decorator


# PostgreSQL Row Level Security setup

def setup_row_level_security(db: Session):
    """Set up PostgreSQL Row Level Security policies"""

    # Enable RLS on relevant tables
    tables_with_rls = [
        'documents',
        'users',
        'analytics_events',
        'user_sessions',
        'performance_logs',
        'quality_metrics'
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
def tenant_context_manager(organization_id: str, user_id: str, user_role: str = 'user'):
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
    if current_role in ['admin', 'super_admin']:
        return True

    # Regular users can only access their own tenant
    return current_tenant in organization_ids


# Database event listeners for automatic tenant filtering

@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Add tenant filtering to SELECT queries automatically"""
    tenant_id = get_current_tenant_id()

    if tenant_id and statement.strip().upper().startswith('SELECT'):
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

        if self.tenant_id and hasattr(self.model_class, 'organization_id'):
            query = query.filter(self.model_class.organization_id == self.tenant_id)

        return query

    def get_with_tenant_filter(self, entity_id: str):
        """Get entity by ID with tenant filter"""
        query = self.filter_by_tenant()
        return query.filter(self.model_class.id == entity_id).first()

    def create_with_tenant(self, **kwargs):
        """Create entity with current tenant context"""
        if self.tenant_id and hasattr(self.model_class, 'organization_id'):
            kwargs['organization_id'] = self.tenant_id

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
                details={"entity_id": entity_id, "model": self.model_class.__name__}
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
                details={"entity_id": entity_id, "model": self.model_class.__name__}
            )

        self.db.delete(entity)
        return entity


# Export main components
__all__ = [
    'MultiTenancyMiddleware',
    'get_current_tenant_id',
    'get_current_user_id',
    'get_current_user_role',
    'add_row_level_security_filters',
    'enforce_tenant_access',
    'setup_row_level_security',
    'tenant_context_manager',
    'validate_tenant_access',
    'validate_cross_tenant_access',
    'TenantAwareQuery'
]