"""
Database configuration and utilities for microservices
"""

import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import event
from sqlalchemy.engine import Engine

from ..config.knowledge_graph_config import config

# Create async engine
engine = create_async_engine(
    config.DATABASE_URL,
    echo=config.DEBUG,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections"""
    await engine.dispose()


# Database event listeners for performance monitoring
@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log query start time"""
    context._query_start_time = context._query_start_time = time.time()


@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log query execution time"""
    total = time.time() - context._query_start_time
    if total > 1.0:  # Log slow queries
        logger.warning(f"Slow query ({total:.2f}s): {statement[:100]}...")


# Database health check
async def check_database_health() -> dict:
    """Check database connectivity and health"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
        return {
            "status": "healthy",
            "connection": "active",
            "pool_size": engine.pool.size(),
            "checked_out": engine.pool.checkedout()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "connection": "failed",
            "error": str(e)
        }