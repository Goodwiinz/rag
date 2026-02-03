"""
Analytics-specific permissions and access control
Defines granular permissions for T3 analytics features
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set

from src.models.user import UserRole


class AnalyticsPermission(Enum):
    """Granular analytics permissions"""

    # Basic Analytics
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_BASIC_METRICS = "view_basic_metrics"
    VIEW_OWN_METRICS = "view_own_metrics"

    # User Behavior Analytics
    VIEW_USER_BEHAVIOR = "view_user_behavior"
    VIEW_SESSION_DATA = "view_session_data"
    VIEW_SEARCH_ANALYTICS = "view_search_analytics"
    VIEW_DOCUMENT_ANALYTICS = "view_document_analytics"

    # Quality Analytics
    VIEW_QUALITY_METRICS = "view_quality_metrics"
    VIEW_QUALITY_ALERTS = "view_quality_alerts"
    MANAGE_QUALITY_THRESHOLDS = "manage_quality_thresholds"
    ACKNOWLEDGE_ALERTS = "acknowledge_alerts"

    # Performance Analytics
    VIEW_PERFORMANCE_METRICS = "view_performance_metrics"
    VIEW_SYSTEM_HEALTH = "view_system_health"
    VIEW_PERFORMANCE_ALERTS = "view_performance_alerts"

    # Advanced Analytics
    VIEW_ADVANCED_ANALYTICS = "view_advanced_analytics"
    VIEW_PREDICTIVE_ANALYTICS = "view_predictive_analytics"
    VIEW_COMPARATIVE_ANALYTICS = "view_comparative_analytics"

    # Export and Reporting
    EXPORT_BASIC_REPORTS = "export_basic_reports"
    EXPORT_DETAILED_REPORTS = "export_detailed_reports"
    GENERATE_CUSTOM_REPORTS = "generate_custom_reports"
    SCHEDULE_REPORTS = "schedule_reports"

    # Administrative
    MANAGE_ANALYTICS_SETTINGS = "manage_analytics_settings"
    VIEW_ALL_ORG_DATA = "view_all_org_data"
    MANAGE_ACCESS_CONTROL = "manage_access_control"
    VIEW_AUDIT_LOGS = "view_audit_logs"

    # Data Privacy
    VIEW_ANONYMIZED_DATA = "view_anonymized_data"
    MANAGE_DATA_RETENTION = "manage_data_retention"
    PROCESS_GDPR_REQUESTS = "process_gdpr_requests"


@dataclass
class PermissionSet:
    """Set of analytics permissions for a role"""

    permissions: Set[AnalyticsPermission]
    description: str


# Define permission sets for each role
ROLE_PERMISSIONS: Dict[UserRole, PermissionSet] = {
    UserRole.USER: PermissionSet(
        permissions={
            AnalyticsPermission.VIEW_OWN_METRICS,
            AnalyticsPermission.VIEW_BASIC_METRICS,
            AnalyticsPermission.EXPORT_BASIC_REPORTS,
        },
        description="Basic users can view their own metrics and basic analytics",
    ),
    UserRole.ANALYST: PermissionSet(
        permissions={
            # Basic Analytics
            AnalyticsPermission.VIEW_DASHBOARD,
            AnalyticsPermission.VIEW_BASIC_METRICS,
            AnalyticsPermission.VIEW_OWN_METRICS,
            # User Behavior Analytics
            AnalyticsPermission.VIEW_USER_BEHAVIOR,
            AnalyticsPermission.VIEW_SESSION_DATA,
            AnalyticsPermission.VIEW_SEARCH_ANALYTICS,
            AnalyticsPermission.VIEW_DOCUMENT_ANALYTICS,
            # Quality Analytics
            AnalyticsPermission.VIEW_QUALITY_METRICS,
            AnalyticsPermission.VIEW_QUALITY_ALERTS,
            AnalyticsPermission.ACKNOWLEDGE_ALERTS,
            # Performance Analytics
            AnalyticsPermission.VIEW_PERFORMANCE_METRICS,
            AnalyticsPermission.VIEW_SYSTEM_HEALTH,
            AnalyticsPermission.VIEW_PERFORMANCE_ALERTS,
            # Export and Reporting
            AnalyticsPermission.EXPORT_BASIC_REPORTS,
            AnalyticsPermission.EXPORT_DETAILED_REPORTS,
            AnalyticsPermission.GENERATE_CUSTOM_REPORTS,
            # Data Privacy
            AnalyticsPermission.VIEW_ANONYMIZED_DATA,
        },
        description="Analysts can access most analytics features and generate reports",
    ),
    UserRole.CONTENT_MANAGER: PermissionSet(
        permissions={
            # All ANALYST permissions
            AnalyticsPermission.VIEW_DASHBOARD,
            AnalyticsPermission.VIEW_BASIC_METRICS,
            AnalyticsPermission.VIEW_OWN_METRICS,
            AnalyticsPermission.VIEW_USER_BEHAVIOR,
            AnalyticsPermission.VIEW_SESSION_DATA,
            AnalyticsPermission.VIEW_SEARCH_ANALYTICS,
            AnalyticsPermission.VIEW_DOCUMENT_ANALYTICS,
            AnalyticsPermission.VIEW_QUALITY_METRICS,
            AnalyticsPermission.VIEW_QUALITY_ALERTS,
            AnalyticsPermission.ACKNOWLEDGE_ALERTS,
            AnalyticsPermission.VIEW_PERFORMANCE_METRICS,
            AnalyticsPermission.VIEW_SYSTEM_HEALTH,
            AnalyticsPermission.VIEW_PERFORMANCE_ALERTS,
            AnalyticsPermission.EXPORT_BASIC_REPORTS,
            AnalyticsPermission.EXPORT_DETAILED_REPORTS,
            AnalyticsPermission.GENERATE_CUSTOM_REPORTS,
            AnalyticsPermission.VIEW_ANONYMIZED_DATA,
            # Additional content management permissions
            AnalyticsPermission.MANAGE_QUALITY_THRESHOLDS,
            AnalyticsPermission.VIEW_ADVANCED_ANALYTICS,
            AnalyticsPermission.SCHEDULE_REPORTS,
            AnalyticsPermission.MANAGE_DATA_RETENTION,
        },
        description="Content managers have extended analytics permissions for content oversight",
    ),
    UserRole.ADMIN: PermissionSet(
        permissions={
            # All CONTENT_MANAGER permissions
            AnalyticsPermission.VIEW_DASHBOARD,
            AnalyticsPermission.VIEW_BASIC_METRICS,
            AnalyticsPermission.VIEW_OWN_METRICS,
            AnalyticsPermission.VIEW_USER_BEHAVIOR,
            AnalyticsPermission.VIEW_SESSION_DATA,
            AnalyticsPermission.VIEW_SEARCH_ANALYTICS,
            AnalyticsPermission.VIEW_DOCUMENT_ANALYTICS,
            AnalyticsPermission.VIEW_QUALITY_METRICS,
            AnalyticsPermission.VIEW_QUALITY_ALERTS,
            AnalyticsPermission.ACKNOWLEDGE_ALERTS,
            AnalyticsPermission.VIEW_PERFORMANCE_METRICS,
            AnalyticsPermission.VIEW_SYSTEM_HEALTH,
            AnalyticsPermission.VIEW_PERFORMANCE_ALERTS,
            AnalyticsPermission.EXPORT_BASIC_REPORTS,
            AnalyticsPermission.EXPORT_DETAILED_REPORTS,
            AnalyticsPermission.GENERATE_CUSTOM_REPORTS,
            AnalyticsPermission.VIEW_ANONYMIZED_DATA,
            AnalyticsPermission.MANAGE_QUALITY_THRESHOLDS,
            AnalyticsPermission.VIEW_ADVANCED_ANALYTICS,
            AnalyticsPermission.SCHEDULE_REPORTS,
            AnalyticsPermission.MANAGE_DATA_RETENTION,
            # Administrative permissions
            AnalyticsPermission.VIEW_PREDICTIVE_ANALYTICS,
            AnalyticsPermission.VIEW_COMPARATIVE_ANALYTICS,
            AnalyticsPermission.MANAGE_ANALYTICS_SETTINGS,
            AnalyticsPermission.VIEW_ALL_ORG_DATA,
            AnalyticsPermission.MANAGE_ACCESS_CONTROL,
            AnalyticsPermission.VIEW_AUDIT_LOGS,
            AnalyticsPermission.PROCESS_GDPR_REQUESTS,
        },
        description="Administrators have full access to all analytics features",
    ),
}


class AnalyticsPermissionsChecker:
    """
    Check analytics permissions for users and roles
    """

    @staticmethod
    def has_permission(user_role: UserRole, permission: AnalyticsPermission) -> bool:
        """
        Check if a role has a specific permission
        """
        role_permissions = ROLE_PERMISSIONS.get(user_role)
        if not role_permissions:
            return False

        return permission in role_permissions.permissions

    @staticmethod
    def has_any_permission(
        user_role: UserRole, permissions: List[AnalyticsPermission]
    ) -> bool:
        """
        Check if a role has any of the specified permissions
        """
        return any(
            AnalyticsPermissionsChecker.has_permission(user_role, perm)
            for perm in permissions
        )

    @staticmethod
    def has_all_permissions(
        user_role: UserRole, permissions: List[AnalyticsPermission]
    ) -> bool:
        """
        Check if a role has all of the specified permissions
        """
        return all(
            AnalyticsPermissionsChecker.has_permission(user_role, perm)
            for perm in permissions
        )

    @staticmethod
    def get_role_permissions(user_role: UserRole) -> Set[AnalyticsPermission]:
        """
        Get all permissions for a role
        """
        role_permissions = ROLE_PERMISSIONS.get(user_role)
        return role_permissions.permissions if role_permissions else set()

    @staticmethod
    def get_accessible_features(user_role: UserRole) -> Dict[str, List[str]]:
        """
        Get accessible analytics features grouped by category
        """
        permissions = AnalyticsPermissionsChecker.get_role_permissions(user_role)

        features = {
            "dashboard": [],
            "user_behavior": [],
            "quality": [],
            "performance": [],
            "reports": [],
            "admin": [],
            "privacy": [],
        }

        # Map permissions to features
        permission_to_feature = {
            # Dashboard
            AnalyticsPermission.VIEW_DASHBOARD: "dashboard",
            AnalyticsPermission.VIEW_BASIC_METRICS: "dashboard",
            AnalyticsPermission.VIEW_OWN_METRICS: "dashboard",
            # User Behavior
            AnalyticsPermission.VIEW_USER_BEHAVIOR: "user_behavior",
            AnalyticsPermission.VIEW_SESSION_DATA: "user_behavior",
            AnalyticsPermission.VIEW_SEARCH_ANALYTICS: "user_behavior",
            AnalyticsPermission.VIEW_DOCUMENT_ANALYTICS: "user_behavior",
            # Quality
            AnalyticsPermission.VIEW_QUALITY_METRICS: "quality",
            AnalyticsPermission.VIEW_QUALITY_ALERTS: "quality",
            AnalyticsPermission.MANAGE_QUALITY_THRESHOLDS: "quality",
            AnalyticsPermission.ACKNOWLEDGE_ALERTS: "quality",
            # Performance
            AnalyticsPermission.VIEW_PERFORMANCE_METRICS: "performance",
            AnalyticsPermission.VIEW_SYSTEM_HEALTH: "performance",
            AnalyticsPermission.VIEW_PERFORMANCE_ALERTS: "performance",
            # Reports
            AnalyticsPermission.EXPORT_BASIC_REPORTS: "reports",
            AnalyticsPermission.EXPORT_DETAILED_REPORTS: "reports",
            AnalyticsPermission.GENERATE_CUSTOM_REPORTS: "reports",
            AnalyticsPermission.SCHEDULE_REPORTS: "reports",
            # Admin
            AnalyticsPermission.MANAGE_ANALYTICS_SETTINGS: "admin",
            AnalyticsPermission.VIEW_ALL_ORG_DATA: "admin",
            AnalyticsPermission.MANAGE_ACCESS_CONTROL: "admin",
            AnalyticsPermission.VIEW_AUDIT_LOGS: "admin",
            # Privacy
            AnalyticsPermission.VIEW_ANONYMIZED_DATA: "privacy",
            AnalyticsPermission.MANAGE_DATA_RETENTION: "privacy",
            AnalyticsPermission.PROCESS_GDPR_REQUESTS: "privacy",
        }

        for permission in permissions:
            feature_category = permission_to_feature.get(permission)
            if feature_category:
                features[feature_category].append(permission.value)

        return features

    @staticmethod
    def can_access_endpoint(user_role: UserRole, endpoint_path: str) -> bool:
        """
        Check if a role can access a specific analytics endpoint
        """
        # Define endpoint permissions mapping
        endpoint_permissions = {
            # Dashboard endpoints
            "/api/analytics/dashboard": [AnalyticsPermission.VIEW_DASHBOARD],
            "/api/analytics/overview": [AnalyticsPermission.VIEW_BASIC_METRICS],
            # User behavior endpoints
            "/api/analytics/user-behavior": [AnalyticsPermission.VIEW_USER_BEHAVIOR],
            "/api/analytics/sessions": [AnalyticsPermission.VIEW_SESSION_DATA],
            "/api/analytics/search-analytics": [
                AnalyticsPermission.VIEW_SEARCH_ANALYTICS
            ],
            "/api/analytics/document-analytics": [
                AnalyticsPermission.VIEW_DOCUMENT_ANALYTICS
            ],
            # Quality endpoints
            "/api/analytics/quality/metrics": [
                AnalyticsPermission.VIEW_QUALITY_METRICS
            ],
            "/api/analytics/quality/alerts": [AnalyticsPermission.VIEW_QUALITY_ALERTS],
            "/api/analytics/quality/thresholds": [
                AnalyticsPermission.MANAGE_QUALITY_THRESHOLDS
            ],
            "/api/analytics/quality/acknowledge": [
                AnalyticsPermission.ACKNOWLEDGE_ALERTS
            ],
            # Performance endpoints
            "/api/analytics/performance/metrics": [
                AnalyticsPermission.VIEW_PERFORMANCE_METRICS
            ],
            "/api/analytics/performance/health": [
                AnalyticsPermission.VIEW_SYSTEM_HEALTH
            ],
            "/api/analytics/performance/alerts": [
                AnalyticsPermission.VIEW_PERFORMANCE_ALERTS
            ],
            # Export endpoints
            "/api/analytics/export/basic": [AnalyticsPermission.EXPORT_BASIC_REPORTS],
            "/api/analytics/export/detailed": [
                AnalyticsPermission.EXPORT_DETAILED_REPORTS
            ],
            "/api/analytics/reports/generate": [
                AnalyticsPermission.GENERATE_CUSTOM_REPORTS
            ],
            "/api/analytics/reports/schedule": [AnalyticsPermission.SCHEDULE_REPORTS],
            # Admin endpoints
            "/api/analytics/admin/settings": [
                AnalyticsPermission.MANAGE_ANALYTICS_SETTINGS
            ],
            "/api/analytics/admin/organizations": [
                AnalyticsPermission.VIEW_ALL_ORG_DATA
            ],
            "/api/analytics/admin/access": [AnalyticsPermission.MANAGE_ACCESS_CONTROL],
            "/api/analytics/admin/audit": [AnalyticsPermission.VIEW_AUDIT_LOGS],
        }

        # Find matching endpoint permissions
        required_permissions = []
        for pattern, perms in endpoint_permissions.items():
            if endpoint_path.startswith(pattern):
                required_permissions.extend(perms)
                break

        # If no specific permissions required, allow access for all roles
        if not required_permissions:
            return True

        # Check if user has any of the required permissions
        return AnalyticsPermissionsChecker.has_any_permission(
            user_role, required_permissions
        )


def require_analytics_permission(permission: AnalyticsPermission):
    """
    Decorator factory to require specific analytics permission
    """

    def permission_checker(user_role: UserRole) -> bool:
        return AnalyticsPermissionsChecker.has_permission(user_role, permission)

    return permission_checker


def get_user_analytics_summary(user_role: UserRole) -> Dict:
    """
    Get a summary of analytics access for a user role
    """
    role_permissions = ROLE_PERMISSIONS.get(user_role)
    accessible_features = AnalyticsPermissionsChecker.get_accessible_features(user_role)

    return {
        "role": user_role.value,
        "description": role_permissions.description
        if role_permissions
        else "No access",
        "total_permissions": len(
            AnalyticsPermissionsChecker.get_role_permissions(user_role)
        ),
        "accessible_features": {k: len(v) for k, v in accessible_features.items()},
        "feature_categories": {k: v for k, v in accessible_features.items() if v},
    }
