"""Verify the kg_sync_runs audit table is created by Alembic migration w1b2c3d4e5f6.

This test is positioned per the Task 1 spec (tests/unit/) but the assertion
necessarily runs against a real PostgreSQL instance because the migration
uses PG-specific types (UUID, JSONB) and ``gen_random_uuid()``.

Provide a PG connection via ``TEST_PG_ASYNC_URL`` (asyncpg DSN). The fixture
skips cleanly if no DB is reachable so this file is safe to run alongside
the pure-unit suite.
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


def _resolve_async_dsn() -> str | None:
    override = os.environ.get("TEST_PG_ASYNC_URL")
    if override:
        return override
    # Fallback: local Supabase from backend/alembic.ini, converted to asyncpg.
    return "postgresql+asyncpg://postgres:postgres@localhost:54322/postgres"


@pytest_asyncio.fixture()
async def db_session():
    dsn = _resolve_async_dsn()
    if not dsn:
        pytest.skip("TEST_PG_ASYNC_URL not set; cannot verify migration against Postgres")
    engine = create_async_engine(dsn, future=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text

            await conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"Test PostgreSQL DB unreachable: {exc}")

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Session() as session:
            yield session
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_kg_sync_runs_table_exists(db_session):
    def _inspect(conn):
        insp = inspect(conn)
        assert "kg_sync_runs" in insp.get_table_names()
        cols = {c["name"] for c in insp.get_columns("kg_sync_runs")}
        assert {
            "id", "run_id", "started_at", "completed_at",
            "orphan_count", "missing_count", "drift_count",
            "fixed_count", "status", "error", "metadata",
        }.issubset(cols)
    await db_session.run_sync(lambda s: _inspect(s.connection()))
