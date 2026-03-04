"""Supabase client initialization."""

import structlog
from supabase import Client, create_client

from src.core.config import settings

logger = structlog.get_logger(__name__)

_supabase_client: Client | None = None


def get_supabase_client() -> Client | None:
    """Get or create the Supabase client singleton."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.warning(
            "supabase_not_configured",
            msg="SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set",
        )
        return None

    try:
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
        logger.info("supabase_client_initialized", url=settings.SUPABASE_URL)
        return _supabase_client
    except Exception as exc:
        logger.error("supabase_client_init_failed", error=str(exc))
        return None
