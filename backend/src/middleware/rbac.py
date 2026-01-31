"""
RBAC middleware for fine-grained permission checking
Integrates with multi-tenancy middleware to provide role-based access control
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException, Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.routing import Match

from src.exceptions.analytics_exceptions import PermissionDeniedException
from src.middleware.multi_tenancy import get_current_tenant_id, get_current_user_id
from src.models.permission import Permission
from src.services.security.rbac_service import RBACService

logger = logging.getLogger(__name__)

# Cache for user permissions to reduce database queries
_permission_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl = 300  # 5 minutes


class RBACMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce RBAC policies on API requests"""

    def __init__(self, app, permission_requirements: Dict[str, List[str]] = None):
        super().__init__(app)
        self.permission_requirements = permission_requirements or {}
        self.rbac_service = RBACService()
        self._initialize_default_permissions()

    def _initialize_default_permissions(self):
        """Initialize default permission requirements for common endpoint patterns"""
        default_requirements = {
            # Document management
            r"/api/documents.*": ["document_read"],
            "POST:/api/documents": ["document_create"],
            "PUT:/api/documents/.*": ["document_update"],
            "DELETE:/api/documents/.*": ["document_delete"],
            # User management
            r"/api/users.*": ["user_read"],
            "POST:/api/users": ["user_create"],
            "PUT:/api/users/.*": ["user_update"],
            "DELETE:/api/users/.*": ["user_delete"],
            "POST:/api/users/.*/roles": ["user_manage_roles"],
            "DELETE:/api/users/.*/roles/.*": ["user_manage_roles"],
            # Organization management
            r"/api/organizations.*": ["organization_read"],
            "POST:/api/organizations": ["organization_create"],
            "PUT:/api/organizations/.*": ["organization_update"],
            "DELETE:/api/organizations/.*": ["organization_delete"],
            # Analytics
            r"/api/analytics.*": ["analytics_read"],
            "POST:/api/analytics/export": ["analytics_export"],
            "PUT:/api/analytics/.*": ["analytics_manage"],
            # System administration
            r"/api/system/health": ["system_health"],
            r"/api/system/logs": ["system_logs"],
            r"/api/system/admin": ["system_admin"],
            # Billing
            r"/api/billing.*": ["billing_read"],
            "PUT:/api/billing/.*": ["billing_manage"],
            # Audit
            r"/api/audit.*": ["audit_read"],
            "PUT:/api/audit/.*": ["audit_manage"],
        }

        # Merge with provided requirements
        for pattern, permissions in default_requirements.items():
            if pattern not in self.permission_requirements:
                self.permission_requirements[pattern] = permissions

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and enforce RBAC policies"""

        # Skip RBAC for health checks and auth endpoints
        if self._should_skip_rbac(request):
            response = await call_next(request)
            return response

        try:
            # Get user and organization context
            user_id = get_current_user_id()
            organization_id = get_current_tenant_id()

            if not user_id or not organization_id:
                # Allow access to public endpoints, deny others
                if self._is_public_endpoint(request):
                    response = await call_next(request)
                    return response
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required for access control",
                    )

            # Get required permissions for this endpoint
            required_permissions = self._get_required_permissions(request)

            if required_permissions:
                # Check user permissions
                await self._check_permissions(
                    user_id, organization_id, required_permissions, request
                )

                # Cache permissions for future requests
                self._cache_user_permissions(
                    user_id, organization_id, required_permissions
                )

            response = await call_next(request)
            return response

        except PermissionDeniedException as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Access denied: {str(e)}"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"RBAC middleware error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during access control",
            )

    def _should_skip_rbac(self, request: Request) -> bool:
        """Check if RBAC should be skipped for this endpoint"""
        skip_paths = [
            "/health",
            "/auth/login",
            "/auth/register",
            "/auth/refresh",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/static",
            "/favicon.ico",
        ]

        return any(request.url.path.startswith(path) for path in skip_paths)

    def _is_public_endpoint(self, request: Request) -> bool:
        """Check if endpoint is public (no authentication required)"""
        public_paths = [
            "/health",
            "/auth/login",
            "/auth/register",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

        return any(request.url.path.startswith(path) for path in public_paths)

    def _get_required_permissions(self, request: Request) -> List[str]:
        """Get required permissions for the current endpoint"""
        path = request.url.path
        method = request.method

        # Check exact method:path matches first
        key = f"{method}:{path}"
        if key in self.permission_requirements:
            return self.permission_requirements[key]

        # Check pattern matches
        for pattern, permissions in self.permission_requirements.items():
            if ":" in pattern:
                pattern_method, pattern_path = pattern.split(":", 1)
                if pattern_method != method:
                    continue
            else:
                pattern_path = pattern

            # Simple pattern matching (can be enhanced with regex)
            if self._path_matches_pattern(path, pattern_path):
                return permissions

        return []

    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches pattern"""
        # Handle wildcard patterns
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return path.startswith(prefix)

        # Handle exact match
        return path == pattern

    async def _check_permissions(
        self,
        user_id: str,
        organization_id: str,
        required_permissions: List[str],
        request: Request,
    ) -> bool:
        """Check if user has required permissions"""
        try:
            # Check cache first
            cache_key = f"{user_id}:{organization_id}"
            if cache_key in _permission_cache:
                cached_data = _permission_cache[cache_key]
                if time.time() - cached_data["timestamp"] < _cache_ttl:
                    cached_permissions = cached_data["permissions"]
                    if all(perm in cached_permissions for perm in required_permissions):
                        return True

            # Check permissions from database
            user_permissions = self.rbac_service.get_user_permissions(
                user_id, organization_id
            )

            # Verify all required permissions are present
            missing_permissions = [
                perm for perm in required_permissions if perm not in user_permissions
            ]
            if missing_permissions:
                logger.warning(
                    f"Access denied for user {user_id} on {request.method} {request.url.path}. "
                    f"Missing permissions: {missing_permissions}"
                )
                raise PermissionDeniedException(
                    required_permission=missing_permissions[0],
                    user_role="unknown",
                    details={
                        "user_id": user_id,
                        "organization_id": organization_id,
                        "missing_permissions": missing_permissions,
                        "endpoint": f"{request.method} {request.url.path}",
                    },
                )

            return True

        except PermissionDeniedException:
            raise
        except Exception as e:
            logger.error(f"Error checking permissions: {e}")
            raise PermissionDeniedException(
                required_permission=required_permissions[0]
                if required_permissions
                else "unknown",
                user_role="unknown",
                details={"error": "Permission check failed"},
            )

    def _cache_user_permissions(
        self, user_id: str, organization_id: str, required_permissions: List[str]
    ):
        """Cache user permissions for future requests"""
        try:
            cache_key = f"{user_id}:{organization_id}"
            _permission_cache[cache_key] = {
                "permissions": required_permissions,
                "timestamp": time.time(),
            }

            # Clean old cache entries
            current_time = time.time()
            expired_keys = [
                key
                for key, data in _permission_cache.items()
                if current_time - data["timestamp"] > _cache_ttl
            ]
            for key in expired_keys:
                del _permission_cache[key]

        except Exception as e:
            logger.error(f"Error caching permissions: {e}")


# Decorators for permission checking


def require_permission(permission_name: str):
    """Decorator to require specific permission for a function"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = get_current_user_id()
            organization_id = get_current_tenant_id()

            if not user_id or not organization_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            with RBACService() as rbac:
                if not rbac.user_has_permission(
                    user_id, permission_name, organization_id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: {permission_name} required",
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_any_permission(permission_names: List[str]):
    """Decorator to require any of the specified permissions"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = get_current_user_id()
            organization_id = get_current_tenant_id()

            if not user_id or not organization_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            with RBACService() as rbac:
                if not rbac.user_has_any_permission(
                    user_id, permission_names, organization_id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: one of {permission_names} required",
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_all_permissions(permission_names: List[str]):
    """Decorator to require all of the specified permissions"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = get_current_user_id()
            organization_id = get_current_tenant_id()

            if not user_id or not organization_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            with RBACService() as rbac:
                if not rbac.user_has_all_permissions(
                    user_id, permission_names, organization_id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: all of {permission_names} required",
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_role(role_name: str):
    """Decorator to require specific role"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = get_current_user_id()
            organization_id = get_current_tenant_id()

            if not user_id or not organization_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            with RBACService() as rbac:
                user_roles = rbac.get_user_roles(user_id, organization_id)
                if not any(role.name == role_name for role in user_roles):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied: role '{role_name}' required",
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_any_role(role_names: List[str]):
    """Decorator to require any of the specified roles"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = get_current_user_id()
            organization_id = get_current_tenant_id()

            if not user_id or not organization_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            with RBACService() as rbac:
                user_roles = rbac.get_user_roles(user_id, organization_id)
                user_role_names = {role.name for role in user_roles}
                required_role_names = set(role_names)

                if not user_role_names & required_role_names:  # No intersection
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied: one of roles {role_names} required",
                    )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Utility functions for permission checking


def has_permission(
    permission_name: str, user_id: str = None, organization_id: str = None
) -> bool:
    """Check if current user (or specified user) has permission"""
    if not user_id:
        user_id = get_current_user_id()
    if not organization_id:
        organization_id = get_current_tenant_id()

    if not user_id or not organization_id:
        return False

    with RBACService() as rbac:
        return rbac.user_has_permission(user_id, permission_name, organization_id)


def has_any_permission(
    permission_names: List[str], user_id: str = None, organization_id: str = None
) -> bool:
    """Check if current user (or specified user) has any of the permissions"""
    if not user_id:
        user_id = get_current_user_id()
    if not organization_id:
        organization_id = get_current_tenant_id()

    if not user_id or not organization_id:
        return False

    with RBACService() as rbac:
        return rbac.user_has_any_permission(user_id, permission_names, organization_id)


def has_role(role_name: str, user_id: str = None, organization_id: str = None) -> bool:
    """Check if current user (or specified user) has role"""
    if not user_id:
        user_id = get_current_user_id()
    if not organization_id:
        organization_id = get_current_tenant_id()

    if not user_id or not organization_id:
        return False

    with RBACService() as rbac:
        user_roles = rbac.get_user_roles(user_id, organization_id)
        return any(role.name == role_name for role in user_roles)


def get_current_user_permissions(organization_id: str = None) -> List[str]:
    """Get current user's permissions"""
    user_id = get_current_user_id()
    if not organization_id:
        organization_id = get_current_tenant_id()

    if not user_id or not organization_id:
        return []

    with RBACService() as rbac:
        return list(rbac.get_user_permissions(user_id, organization_id))


def get_current_user_roles(organization_id: str = None) -> List[str]:
    """Get current user's roles"""
    user_id = get_current_user_id()
    if not organization_id:
        organization_id = get_current_tenant_id()

    if not user_id or not organization_id:
        return []

    with RBACService() as rbac:
        roles = rbac.get_user_roles(user_id, organization_id)
        return [role.name for role in roles]


# Clear permission cache (useful for testing or when permissions change)


def clear_permission_cache():
    """Clear the permission cache"""
    global _permission_cache
    _permission_cache.clear()
    logger.info("Permission cache cleared")


def clear_user_permission_cache(user_id: str, organization_id: str):
    """Clear specific user's permission cache"""
    cache_key = f"{user_id}:{organization_id}"
    if cache_key in _permission_cache:
        del _permission_cache[cache_key]
        logger.info(
            f"Permission cache cleared for user {user_id} in organization {organization_id}"
        )
