"""
Auth API routes for authentication and tenant management
"""

from .auth import router as auth_router
from .tenant_management import router as tenant_management_router

__all__ = ["auth_router", "tenant_management_router"]
