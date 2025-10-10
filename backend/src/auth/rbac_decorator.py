"""
Role-Based Access Control (RBAC) decorators for analytics endpoints
Provides fine-grained access control for T3 analytics features
"""

from functools import wraps
from typing import List, Optional, Callable, Any
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session

from src.models.user import User, UserRole
from src.core.dependencies import get_current_user
from src.core.database import get_db
from src.auth.analytics_permissions import (
    AnalyticsPermission,
    AnalyticsPermissionsChecker
)


def require_permission(permission: AnalyticsPermission):
    """
    Decorator requiring a specific analytics permission
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs (injected by FastAPI dependencies)
            current_user: Optional[User] = kwargs.get('current_user')

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if not AnalyticsPermissionsChecker.has_permission(current_user.role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {permission.value}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_any_permission(permissions: List[AnalyticsPermission]):
    """
    Decorator requiring any of the specified analytics permissions
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user: Optional[User] = kwargs.get('current_user')

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if not AnalyticsPermissionsChecker.has_any_permission(current_user.role, permissions):
                permission_names = [p.value for p in permissions]
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required any of: {', '.join(permission_names)}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_all_permissions(permissions: List[AnalyticsPermission]):
    """
    Decorator requiring all of the specified analytics permissions
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user: Optional[User] = kwargs.get('current_user')

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if not AnalyticsPermissionsChecker.has_all_permissions(current_user.role, permissions):
                permission_names = [p.value for p in permissions]
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required all of: {', '.join(permission_names)}"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_min_role(min_role: UserRole):
    """
    Decorator requiring minimum user role
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user: Optional[User] = kwargs.get('current_user')

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if not current_user.has_permission(min_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required role: {min_role.value} or higher"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_organization_access(allow_cross_org: bool = False):
    """
    Decorator for organization-based access control
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user: Optional[User] = kwargs.get('current_user')

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            # Extract organization_id from path or query parameters
            # This depends on how the endpoint is defined
            target_org_id = kwargs.get('organization_id') or \
                          kwargs.get('org_id') or \
                          getattr(kwargs.get('request'), 'query_params', {}).get('organization_id')

            if target_org_id and not allow_cross_org:
                # User can only access their own organization's data
                if str(target_org_id) != str(current_user.organization_id):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cross-organization access not permitted"
                    )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def conditional_access(condition_func: Callable[[User], bool],
                     error_message: str = "Access denied"):
    """
    Decorator for conditional access based on custom logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user: Optional[User] = kwargs.get('current_user')

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )

            if not condition_func(current_user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=error_message
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


# FastAPI dependency versions for better integration

def require_permission_dep(permission: AnalyticsPermission):
    """
    FastAPI dependency requiring a specific analytics permission
    """
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not AnalyticsPermissionsChecker.has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission.value}"
            )
        return current_user
    return dependency


def require_any_permission_dep(permissions: List[AnalyticsPermission]):
    """
    FastAPI dependency requiring any of the specified analytics permissions
    """
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not AnalyticsPermissionsChecker.has_any_permission(current_user.role, permissions):
            permission_names = [p.value for p in permissions]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required any of: {', '.join(permission_names)}"
            )
        return current_user
    return dependency


def require_min_role_dep(min_role: UserRole):
    """
    FastAPI dependency requiring minimum user role
    """
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.has_permission(min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {min_role.value} or higher"
            )
        return current_user
    return dependency


# Common permission combinations for analytics endpoints

# Dashboard access
require_dashboard_access = require_permission_dep(AnalyticsPermission.VIEW_DASHBOARD)
require_basic_metrics_access = require_permission_dep(AnalyticsPermission.VIEW_BASIC_METRICS)

# User behavior analytics
require_user_behavior_access = require_permission_dep(AnalyticsPermission.VIEW_USER_BEHAVIOR)
require_session_data_access = require_permission_dep(AnalyticsPermission.VIEW_SESSION_DATA)
require_search_analytics_access = require_permission_dep(AnalyticsPermission.VIEW_SEARCH_ANALYTICS)

# Quality analytics
require_quality_metrics_access = require_permission_dep(AnalyticsPermission.VIEW_QUALITY_METRICS)
require_quality_alerts_access = require_permission_dep(AnalyticsPermission.VIEW_QUALITY_ALERTS)
require_manage_thresholds_access = require_permission_dep(AnalyticsPermission.MANAGE_QUALITY_THRESHOLDS)

# Performance analytics
require_performance_metrics_access = require_permission_dep(AnalyticsPermission.VIEW_PERFORMANCE_METRICS)
require_system_health_access = require_permission_dep(AnalyticsPermission.VIEW_SYSTEM_HEALTH)

# Export and reporting
require_basic_export_access = require_permission_dep(AnalyticsPermission.EXPORT_BASIC_REPORTS)
require_detailed_export_access = require_permission_dep(AnalyticsPermission.EXPORT_DETAILED_REPORTS)
require_custom_reports_access = require_permission_dep(AnalyticsPermission.GENERATE_CUSTOM_REPORTS)

# Administrative
require_admin_settings_access = require_permission_dep(AnalyticsPermission.MANAGE_ANALYTICS_SETTINGS)
require_admin_all_data_access = require_permission_dep(AnalyticsPermission.VIEW_ALL_ORG_DATA)
require_audit_logs_access = require_permission_dep(AnalyticsPermission.VIEW_AUDIT_LOGS)

# Multi-permission requirements
require_analyst_access = require_any_permission_dep([
    AnalyticsPermission.VIEW_DASHBOARD,
    AnalyticsPermission.VIEW_USER_BEHAVIOR,
    AnalyticsPermission.VIEW_QUALITY_METRICS,
    AnalyticsPermission.VIEW_PERFORMANCE_METRICS
])

require_advanced_analytics_access = require_any_permission_dep([
    AnalyticsPermission.VIEW_ADVANCED_ANALYTICS,
    AnalyticsPermission.VIEW_PREDICTIVE_ANALYTICS,
    AnalyticsPermission.VIEW_COMPARATIVE_ANALYTICS
])

require_full_analytics_access = require_min_role_dep(UserRole.ADMIN)