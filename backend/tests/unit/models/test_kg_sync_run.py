"""Roundtrip test for the KGSyncRun ORM model.

Uses a real PostgreSQL DB because the underlying table relies on PG-specific
types (UUID, JSONB) and ``gen_random_uuid()``. Provide a DSN via
``TEST_PG_ASYNC_URL`` (asyncpg). When unset the test skips cleanly so it is
safe to run alongside the pure-unit suite.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.models.kg_sync_run import KGSyncRun


def _resolve_async_dsn() -> str | None:
    return os.environ.get("TEST_PG_ASYNC_URL")


@pytest_asyncio.fixture()
async def db_session():
    dsn = _resolve_async_dsn()
    if not dsn:
        pytest.skip("TEST_PG_ASYNC_URL not set; skipping KGSyncRun roundtrip test")
    engine = create_async_engine(dsn, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text

            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.fail(f"Test PostgreSQL DB unreachable: {exc}")

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as session:
            yield session
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_kg_sync_run_insert_roundtrip(db_session):
    row = KGSyncRun(
        run_id="kg-sync-2026-05-21-test",
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    assert row.id is not None
    assert row.orphan_count == 0
