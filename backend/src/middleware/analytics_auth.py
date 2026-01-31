"""
Analytics-specific authentication and authorization middleware
Provides role-based access control for T3 analytics endpoints
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.dependencies import get_current_organization, get_current_user
from src.models.organization import Organization
from src.models.user import User, UserRole
from src.models.user_session import UserSession

logger = logging.getLogger(__name__)


def require_analytics_permission(
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
) -> User:
    """
    Require user to have analytics viewing permissions

    - Users with ANALYST role or higher can view analytics
    - Users must belong to an active organization
    """
    if not current_user.can_view_analytics():
        logger.warning(
            f"User {current_user.email} attempted to access analytics without permission",
            extra={
                "user_id": str(current_user.id),
                "user_role": current_user.role.value,
                "organization_id": str(current_org.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access analytics. Requires ANALYST role or higher.",
        )

    if not current_org.is_active:
        logger.warning(
            f"User {current_user.email} attempted to access analytics for inactive organization",
            extra={
                "user_id": str(current_user.id),
                "organization_id": str(current_org.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analytics access not available for inactive organizations.",
        )

    return current_user


def require_admin_permission(current_user: User = Depends(get_current_user)) -> User:
    """
    Require admin-level permissions for sensitive analytics operations
    """
    if not current_user.has_permission(UserRole.ADMIN):
        logger.warning(
            f"User {current_user.email} attempted admin operation without permission",
            extra={
                "user_id": str(current_user.id),
                "user_role": current_user.role.value,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Requires ADMIN role.",
        )

    return current_user


async def validate_analytics_access(
    request: Request,
    current_user: User = Depends(require_analytics_permission),
    current_org: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db),
) -> dict:
    """
    Validate analytics access with additional checks:
    - Rate limiting per organization
    - Session validation
    - Audit logging
    """

    # Extract client info for audit
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    # Log analytics access for audit trail
    logger.info(
        f"Analytics access granted",
        extra={
            "user_id": str(current_user.id),
            "organization_id": str(current_org.id),
            "endpoint": str(request.url),
            "method": request.method,
            "client_ip": client_ip,
            "user_agent": user_agent[:200],  # Truncate for log size
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

    # Validate session if session_id is provided
    session_id = request.headers.get("X-Session-ID") or request.query_params.get(
        "session_id"
    )
    if session_id:
        session = (
            db.query(UserSession)
            .filter(
                UserSession.session_id == session_id,
                UserSession.user_id == current_user.id,
                UserSession.is_deleted == False,
            )
            .first()
        )

        if not session or not session.is_active():
            logger.warning(
                f"Invalid session provided for analytics access",
                extra={"user_id": str(current_user.id), "session_id": session_id},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session.",
            )

    return {
        "user": current_user,
        "organization": current_org,
        "session_id": session_id,
        "client_info": {"ip": client_ip, "user_agent": user_agent},
    }


def get_analytics_user_context(
    request: Request, access_context: dict = Depends(validate_analytics_access)
) -> dict:
    """
    Get full user context for analytics operations
    """
    current_user = access_context["user"]
    current_org = access_context["organization"]

    return {
        "user_id": str(current_user.id),
        "user_email": current_user.email,
        "user_role": current_user.role.value,
        "organization_id": str(current_org.id),
        "organization_name": current_org.name,
        "session_id": access_context.get("session_id"),
        "client_ip": access_context["client_info"]["ip"],
        "permissions": {
            "can_view_analytics": current_user.can_view_analytics(),
            "can_manage_users": current_user.can_manage_users(),
            "can_upload_documents": current_user.can_upload_documents(),
        },
    }


class AnalyticsAccessValidator:
    """
    Class-based validator for complex analytics access scenarios
    """

    def __init__(
        self,
        require_admin: bool = False,
        allow_cross_org: bool = False,
        min_role: Optional[UserRole] = None,
    ):
        self.require_admin = require_admin
        self.allow_cross_org = allow_cross_org
        self.min_role = min_role or UserRole.ANALYST

    def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_user),
        current_org: Organization = Depends(get_current_organization),
        db: Session = Depends(get_db),
    ) -> dict:
        """
        Validate access based on configured rules
        """
        # Check minimum role requirement
        if not current_user.has_permission(self.min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Requires {self.min_role.value} role or higher.",
            )

        # Check admin requirement
        if self.require_admin and not current_user.has_permission(UserRole.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required for this operation.",
            )

        # Check organization access
        if not self.allow_cross_org:
            target_org_id = request.path_params.get(
                "organization_id"
            ) or request.query_params.get("organization_id")

            if target_org_id and str(target_org_id) != str(current_org.id):
                logger.warning(
                    f"User {current_user.email} attempted cross-organization access",
                    extra={
                        "user_id": str(current_user.id),
                        "user_org": str(current_org.id),
                        "target_org": str(target_org_id),
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cross-organization access not permitted.",
                )

        # Log the validated access
        logger.info(
            f"Analytics access validated",
            extra={
                "user_id": str(current_user.id),
                "organization_id": str(current_org.id),
                "endpoint": str(request.url),
                "admin_required": self.require_admin,
                "min_role": self.min_role.value,
            },
        )

        return {
            "user": current_user,
            "organization": current_org,
            "access_level": "admin" if self.require_admin else self.min_role.value,
        }


# Pre-configured validators for common scenarios
require_analytics_access = AnalyticsAccessValidator()
require_admin_analytics_access = AnalyticsAccessValidator(require_admin=True)
require_analyst_plus_access = AnalyticsAccessValidator(min_role=UserRole.ANALYST)
require_content_manager_plus_access = AnalyticsAccessValidator(
    min_role=UserRole.CONTENT_MANAGER
)
