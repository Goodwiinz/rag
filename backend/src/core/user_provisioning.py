import logging
import secrets
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import TokenData, get_password_hash
from src.models.organization import Organization, StorageTier
from src.models.user import User, UserRole

logger = logging.getLogger(__name__)

_FREE_STORAGE = Organization.get_default_storage_limit(StorageTier.FREE)


async def ensure_user_and_org(
    db: AsyncSession,
    token_data: TokenData,
) -> Optional[User]:
    """JIT-provision User + Organization on first authenticated request.
    Returns existing or newly created User, or None on failure."""
    if not token_data.user_id:
        return None

    result = await db.execute(select(User).where(User.id == token_data.user_id))
    existing = result.scalars().first()
    if existing:
        return existing

    org = await _resolve_or_create_org(db, token_data)
    return await _create_user(db, token_data, org)


async def _resolve_or_create_org(
    db: AsyncSession,
    token_data: TokenData,
) -> Optional[Organization]:
    org_id = token_data.organization_id

    if org_id:
        result = await db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        org = result.scalars().first()
        if org:
            return org
        org = Organization(
            id=org_id,
            name=f"org-{str(org_id)[:8]}",
            storage_tier=StorageTier.FREE,
            storage_used_bytes=0,
            storage_limit_bytes=_FREE_STORAGE,
            is_active=True,
            is_deleted=False,
        )
    else:
        result = await db.execute(
            select(Organization).where(Organization.name == "Default Organization")
        )
        org = result.scalars().first()
        if org:
            return org
        org = Organization(
            name="Default Organization",
            storage_tier=StorageTier.FREE,
            storage_used_bytes=0,
            storage_limit_bytes=_FREE_STORAGE,
            is_active=True,
            is_deleted=False,
        )

    db.add(org)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        if org_id:
            result = await db.execute(
                select(Organization).where(Organization.id == org_id)
            )
        else:
            result = await db.execute(
                select(Organization).where(
                    Organization.name == "Default Organization"
                )
            )
        org = result.scalars().first()

    return org


async def _create_user(
    db: AsyncSession,
    token_data: TokenData,
    org: Optional[Organization],
) -> Optional[User]:
    email = token_data.email or f"{token_data.user_id}@provisioned.local"
    prefix = email.split("@")[0]
    parts = prefix.split(".")
    first_name = parts[0].capitalize()
    last_name = parts[-1].capitalize() if len(parts) > 1 else "User"

    user = User(
        id=token_data.user_id,
        email=email,
        password_hash=get_password_hash(secrets.token_urlsafe(32)),
        first_name=first_name,
        last_name=last_name,
        role=UserRole.USER,
        is_active=True,
        is_deleted=False,
        organization_id=str(org.id) if org else None,
    )
    db.add(user)
    try:
        await db.flush()
        logger.info(
            f"JIT-provisioned user {token_data.user_id} "
            f"in org {org.id if org else 'none'}"
        )
    except IntegrityError:
        await db.rollback()
        result = await db.execute(
            select(User).where(User.id == token_data.user_id)
        )
        user = result.scalars().first()

    return user
