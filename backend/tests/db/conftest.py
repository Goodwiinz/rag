"""Local fixtures for DB-level integration tests.

These tests hit the real local PostgreSQL dev DB (already migrated to head)
because behaviors under test — partial unique indexes, ``ON CONFLICT`` —
do not exist on SQLite. A self-contained async engine is built here so the
project-wide test conftest's SQLite override (which is set via env vars at
import time) does not affect us.

Fixtures provided
-----------------
``db_session``       async ``AsyncSession`` against the dev DB, rolled back at end.
``user_factory``     async factory returning a persisted ``User`` (auto-creates org).
``thread_factory``   async factory returning a persisted ``Thread`` (auto-creates
                     workspace + conversation + user as needed).

The DSN can be overridden with ``TEST_PG_ASYNC_URL``. Default targets the
Supabase local stack at ``localhost:54322`` per ``backend/alembic.ini``.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator, Awaitable, Callable, Optional
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Initialize encryption so encrypted_string columns (User.first_name etc.)
# round-trip when we insert rows.
os.environ.setdefault(
    "ENCRYPTION_MASTER_KEY",
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
)

from src.core.encryption import EncryptionKeyType, get_key_manager, initialize_encryption

initialize_encryption()
_km = get_key_manager()
if _km.get_active_key(EncryptionKeyType.DATA) is None:
    _km.generate_key(EncryptionKeyType.DATA)

from src.models import (  # noqa: E402  (must come after encryption init)
    Conversation,
    Organization,
    StorageTier,
    Thread,
    User,
    UserRole,
    Workspace,
)


DEFAULT_ADMIN_DSN = "postgresql://postgres:postgres@localhost:54322/postgres"
DEFAULT_TEST_DB = "chat_msg_idempotency_test"

# Mirror of the partial unique index DDL in alembic revision v0a1b2c3d4e5.
# Keep the WHERE clause + column order byte-identical to the migration so
# tests exercise the same index shape production uses.
_CLIENT_MSG_INDEX_DDL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS "
    "uq_chat_messages_thread_client_msg_user "
    "ON chat_messages (thread_id, client_message_id) "
    "WHERE client_message_id IS NOT NULL AND role = 'user'"
)

_ALLOWED_CLEANUP_TABLES = frozenset(
    {"chat_messages", "threads", "conversations", "workspaces", "users", "organizations"}
)


def _resolve_admin_dsn() -> str:
    return os.environ.get("TEST_PG_ADMIN_DSN", DEFAULT_ADMIN_DSN)


def _resolve_test_dsn() -> str:
    base = _resolve_admin_dsn()
    # Replace database segment after the last '/'.
    head, _, _ = base.rpartition("/")
    return f"{head}/{DEFAULT_TEST_DB}"


def _to_async(dsn: str) -> str:
    if dsn.startswith("postgresql://"):
        return "postgresql+asyncpg://" + dsn[len("postgresql://") :]
    return dsn


def _ensure_test_db_provisioned() -> str:
    """Create an empty test DB if missing and provision schema for tests.

    The shared local Postgres has a pre-existing migration-history bug
    (``f931599b6b5b`` emits a bare ``CREATE TYPE processingstage`` while a
    later column also creates it implicitly, raising ``DuplicateObject``).
    Rather than fight that here, we provision the test DB from SQLAlchemy
    metadata (``Base.metadata.create_all``) and then manually install the
    partial unique index whose behavior these tests verify — keeping the
    Alembic migration file as the source of truth in production while
    letting tests run against the current model schema in this environment.

    Returns the async DSN for the test DB. Honors ``TEST_PG_ASYNC_URL`` in
    the caller, which short-circuits this entirely.
    """
    import psycopg2  # type: ignore
    from psycopg2 import extensions as pg_ext  # type: ignore

    admin_dsn = _resolve_admin_dsn()
    try:
        conn = psycopg2.connect(admin_dsn)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Local PostgreSQL unreachable at {admin_dsn}: {exc}")
    conn.set_isolation_level(pg_ext.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DEFAULT_TEST_DB,))
    exists = cur.fetchone() is not None
    if not exists:
        cur.execute(f'CREATE DATABASE "{DEFAULT_TEST_DB}"')
    cur.close()
    conn.close()

    test_sync_dsn = _resolve_test_dsn()
    # Bootstrap is idempotent (CREATE TABLE IF NOT EXISTS via metadata.create_all,
    # CREATE INDEX IF NOT EXISTS), so run on every entry. This also rescues
    # half-provisioned DBs from earlier interrupted runs without requiring
    # destructive cleanup of shared local infrastructure.
    _bootstrap_schema_from_models(test_sync_dsn)
    _ensure_required_columns_and_indexes(test_sync_dsn)

    return _to_async(test_sync_dsn)


def _ensure_required_columns_and_indexes(sync_dsn: str) -> None:
    """Idempotently bring a pre-existing test DB up to date with the
    column + partial index this test file requires. Avoids the need to
    drop and recreate the DB when developer-local schema drifts."""
    from sqlalchemy import create_engine, text

    engine = create_engine(sync_dsn, future=True)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE chat_messages "
                    "ADD COLUMN IF NOT EXISTS client_message_id uuid"
                )
            )
            conn.execute(text(_CLIENT_MSG_INDEX_DDL))
    finally:
        engine.dispose()


def _bootstrap_schema_from_models(sync_dsn: str) -> None:
    """Build the entire schema from ``Base.metadata`` then add the partial
    unique index that lives in the Alembic migration but isn't represented
    on the model (we keep migrations as the source of truth for indexes)."""
    from sqlalchemy import create_engine, text
    from src.models import Base  # noqa: WPS433 - intentional import here

    engine = create_engine(sync_dsn, future=True)
    try:
        with engine.begin() as conn:
            Base.metadata.create_all(conn)
        with engine.begin() as conn:
            conn.execute(text(_CLIENT_MSG_INDEX_DDL))
    finally:
        engine.dispose()


@pytest_asyncio.fixture()
async def _engine():
    # Function-scoped to keep asyncpg connections bound to the current
    # event loop. NullPool avoids cross-loop pool reuse.
    from sqlalchemy.pool import NullPool

    # Allow pointing at an already-migrated DB (e.g. local Supabase `postgres`)
    # to skip the per-run provisioning step, which depends on a clean alembic
    # history. When TEST_PG_ASYNC_URL is unset we fall back to creating and
    # migrating a dedicated test DB.
    override = os.environ.get("TEST_PG_ASYNC_URL")
    dsn = override if override else _ensure_test_db_provisioned()
    engine = create_async_engine(dsn, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"Test PostgreSQL DB unreachable: {exc}")
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(_engine) -> AsyncGenerator[AsyncSession, None]:
    """Function-scoped async session. We commit during tests (we're verifying
    constraint behavior on commit), so we clean up rows by tracking PKs and
    deleting at teardown."""
    Session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        # Stash created PKs on the session for teardown cleanup.
        session.info["_created"] = {
            "chat_messages": [],
            "threads": [],
            "conversations": [],
            "workspaces": [],
            "users": [],
            "organizations": [],
        }
        try:
            yield session
        finally:
            await _cleanup(session)
            await session.close()


async def _cleanup(session: AsyncSession) -> None:
    from sqlalchemy import text

    created = session.info.get("_created", {})
    # Reverse dependency order. chat_messages cascades from threads, but we
    # delete explicitly in case of orphan inserts via raw model instances.
    try:
        await session.rollback()
    except Exception:
        pass
    for table, ids in [
        ("chat_messages", created.get("chat_messages", [])),
        ("threads", created.get("threads", [])),
        ("conversations", created.get("conversations", [])),
        ("workspaces", created.get("workspaces", [])),
        ("users", created.get("users", [])),
        ("organizations", created.get("organizations", [])),
    ]:
        if not ids:
            continue
        if table not in _ALLOWED_CLEANUP_TABLES:
            # Defense in depth: the table name is interpolated into a text()
            # DELETE below, so refuse anything not on the explicit allowlist
            # to keep the f-string from ever becoming an injection vector if
            # the _created dict gains untrusted keys in the future.
            continue
        try:
            await session.execute(
                text(f"DELETE FROM {table} WHERE id = ANY(:ids)"),  # nosec B608
                {"ids": [str(i) for i in ids]},
            )
            await session.commit()
        except Exception:
            await session.rollback()


@pytest_asyncio.fixture()
async def organization_factory(db_session: AsyncSession):
    async def _make(**overrides) -> Organization:
        org = Organization(
            id=uuid4(),
            name=overrides.get("name", f"TestOrg-{uuid4().hex[:8]}"),
            storage_tier=StorageTier.FREE,
            storage_limit_bytes=Organization.get_default_storage_limit(StorageTier.FREE),
            is_active=True,
        )
        db_session.add(org)
        await db_session.commit()
        await db_session.refresh(org)
        db_session.info["_created"]["organizations"].append(org.id)
        return org

    return _make


@pytest_asyncio.fixture()
async def user_factory(
    db_session: AsyncSession,
    organization_factory: Callable[..., Awaitable[Organization]],
):
    async def _make(*, organization: Optional[Organization] = None, **overrides) -> User:
        org = organization or await organization_factory()
        user = User(
            id=uuid4(),
            email=overrides.get("email", f"u-{uuid4().hex[:8]}@example.com"),
            password_hash="hash-not-real",
            first_name=overrides.get("first_name", "Test"),
            last_name=overrides.get("last_name", "User"),
            role=UserRole.USER,
            is_active=True,
            organization_id=org.id,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        db_session.info["_created"]["users"].append(user.id)
        return user

    return _make


@pytest_asyncio.fixture()
async def thread_factory(
    db_session: AsyncSession,
    user_factory: Callable[..., Awaitable[User]],
):
    async def _make(*, user: Optional[User] = None) -> Thread:
        owner = user or await user_factory()
        workspace = Workspace(
            id=uuid4(),
            name=f"ws-{uuid4().hex[:8]}",
            owner_id=owner.id,
            organization_id=owner.organization_id,
        )
        db_session.add(workspace)
        await db_session.commit()
        await db_session.refresh(workspace)
        db_session.info["_created"]["workspaces"].append(workspace.id)

        conversation = Conversation(
            id=uuid4(),
            title="test-conversation",
            workspace_id=workspace.id,
            created_by_id=owner.id,
        )
        db_session.add(conversation)
        await db_session.commit()
        await db_session.refresh(conversation)
        db_session.info["_created"]["conversations"].append(conversation.id)

        thread = Thread(
            id=uuid4(),
            title="test-thread",
            conversation_id=conversation.id,
            created_by_id=owner.id,
            message_count=0,
        )
        db_session.add(thread)
        await db_session.commit()
        await db_session.refresh(thread)
        db_session.info["_created"]["threads"].append(thread.id)
        return thread

    return _make
