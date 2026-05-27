"""Lazy, idempotent KB provisioning per organization.

Single Postgres advisory lock keyed on the org UUID prevents two concurrent
ingests from creating duplicate KBs. Cached KB UUID stored on the
Organization row.
"""

from __future__ import annotations

import hashlib
import logging
import uuid as uuid_pkg
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.organization import Organization

from .client import DOKnowledgeBaseClient, DOKnowledgeBaseError, get_do_kb_client

logger = logging.getLogger(__name__)

_ADVISORY_LOCK_NAMESPACE = 0x444F4B42  # "DOKB"


def _advisory_lock_key(org_id: str | uuid_pkg.UUID) -> int:
    """Map org UUID to a stable signed 32-bit int for pg_advisory_xact_lock(int, int)."""
    digest = hashlib.sha256(str(org_id).encode("utf-8")).digest()
    raw = int.from_bytes(digest[:4], "big", signed=False)
    # signed 32-bit range
    return raw - (1 << 31) if raw >= (1 << 31) else raw


async def ensure_kb_for_org(
    session: AsyncSession,
    org_id: str | uuid_pkg.UUID,
    *,
    client: Optional[DOKnowledgeBaseClient] = None,
) -> str:
    """Return KB UUID for org, creating + persisting it if missing.

    Caller owns the session/transaction. We commit on KB creation so a
    crash mid-ingest does not orphan the KB on DO's side without a row.
    Raises DOKnowledgeBaseError on DO API failure.
    """
    if not settings.DO_KB_ENABLED:
        raise DOKnowledgeBaseError("DO_KB_ENABLED is false")

    api = client or get_do_kb_client()

    org = await session.get(Organization, org_id)
    if org is None:
        raise DOKnowledgeBaseError(f"organization {org_id} not found")
    if org.do_kb_uuid:
        return org.do_kb_uuid

    lock_key = _advisory_lock_key(org_id)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:ns, :key)").bindparams(
            ns=_ADVISORY_LOCK_NAMESPACE, key=lock_key
        )
    )

    # Re-read inside lock window — another worker may have provisioned.
    refreshed = await session.execute(
        select(Organization.do_kb_uuid).where(Organization.id == org_id)
    )
    cached = refreshed.scalar_one_or_none()
    if cached:
        return cached

    kb_name = f"nous-org-{org_id}"
    logger.info(
        "do_kb provisioning",
        extra={"org_id": str(org_id), "kb_name": kb_name},
    )

    kb = await api.create_kb(
        name=kb_name,
        region=settings.DO_KB_REGION or "",
        project_id=settings.DO_KB_PROJECT_ID or "",
        embedding_model_uuid=settings.DO_KB_EMBEDDING_MODEL_UUID or "",
        tags=[f"org:{org_id}", f"env:{settings.ENVIRONMENT}"],
    )

    org.do_kb_uuid = kb.uuid
    org.do_kb_provisioned_at = datetime.now(timezone.utc)
    await session.commit()

    logger.info(
        "do_kb provisioned",
        extra={"org_id": str(org_id), "kb_uuid": kb.uuid},
    )
    return kb.uuid
