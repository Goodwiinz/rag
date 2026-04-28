#!/usr/bin/env python3
"""
Complete Database Setup Script for Multimodal Enterprise RAG System

This script initializes and configures all four databases:
1. PostgreSQL - Main relational database with comprehensive schema
2. Neo4j - Knowledge graph with entities and relationships
3. Qdrant - Vector database for embeddings
4. Redis - Cache and real-time data structures
"""

import asyncio
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import json

_VALID_PG_IDENT = re.compile(r'^[a-z_][a-z0-9_]{0,62}$')


def _safe_pg_identifier(name: str, kind: str = "identifier") -> str:
    """Validate a PostgreSQL identifier against an allowlist before interpolation."""
    if not _VALID_PG_IDENT.match(name):
        raise ValueError(f"Invalid PostgreSQL {kind}: {name!r}")
    return name

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent / "backend"))

import asyncpg
import psycopg2
from psycopg2.extras import execute_batch
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, CreateCollection
import redis.asyncio as redis
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def _require_env(name: str) -> str:
    """Read a required environment variable, failing fast if absent."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Environment variable {name} is required. "
            "Refusing to fall back to hardcoded credentials (issue #367)."
        )
    return value


# Database configuration from environment
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '5432')),
    'user': os.environ.get('DB_USER', 'raguser'),
    'password': _require_env('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME', 'ragdb'),
}

NEO4J_CONFIG = {
    'uri': os.environ.get('NEO4J_URI', 'bolt://localhost:7687'),
    'user': os.environ.get('NEO4J_USER', 'neo4j'),
    'password': _require_env('NEO4J_PASSWORD'),
}

QDRANT_CONFIG = {
    'url': os.environ.get('QDRANT_URL', 'http://localhost:6333'),
    'api_key': os.environ.get('QDRANT_API_KEY') or None,
}

REDIS_CONFIG = {
    'host': os.environ.get('REDIS_HOST', 'localhost'),
    'port': int(os.environ.get('REDIS_PORT', '6379')),
    'password': os.environ.get('REDIS_PASSWORD') or None,
    'decode_responses': True,
}


class DatabaseSetup:
    """Complete database setup and initialization"""

    def __init__(self):
        self.postgres_engine = None
        self.neo4j_driver = None
        self.qdrant_client = None
        self.redis_client = None

    async def setup_all_databases(self):
        """Setup all databases in sequence"""
        logger.info("Starting complete database setup for Multimodal Enterprise RAG System")

        try:
            # 1. PostgreSQL Setup
            await self.setup_postgresql()

            # 2. Neo4j Setup
            await self.setup_neo4j()

            # 3. Qdrant Setup
            await self.setup_qdrant()

            # 4. Redis Setup
            await self.setup_redis()

            # 5. Run database health checks
            await self.run_health_checks()

            logger.info("✅ Complete database setup finished successfully!")

        except Exception as e:
            logger.error(f"❌ Database setup failed: {e}")
            raise

    async def setup_postgresql(self):
        """Setup PostgreSQL database with schema and migrations"""
        logger.info("🐘 Setting up PostgreSQL database...")

        try:
            # First, connect as postgres superuser to create user and database
            admin_conn = await asyncpg.connect(
                host=os.environ.get('POSTGRES_ADMIN_HOST', DB_CONFIG['host']),
                port=int(os.environ.get('POSTGRES_ADMIN_PORT', str(DB_CONFIG['port']))),
                user=os.environ.get('POSTGRES_ADMIN_USER', 'postgres'),
                password=_require_env('POSTGRES_ADMIN_PASSWORD'),
                database=os.environ.get('POSTGRES_ADMIN_DATABASE', 'multimodal_rag'),
            )

            # Create raguser if not exists. CREATE ROLE doesn't accept protocol
            # parameters for the identifier, so the user name is validated against
            # an allowlist before interpolation; the password is passed as a bound
            # parameter to asyncpg.
            try:
                role_name = _safe_pg_identifier(DB_CONFIG['user'], 'role name')
                exists = await admin_conn.fetchval(
                    "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = $1",
                    role_name,
                )
                if not exists:
                    await admin_conn.execute(
                        f'CREATE ROLE {role_name} LOGIN PASSWORD $1',
                        DB_CONFIG['password'],
                    )
                    logger.info("✅ Created %s", role_name)
                else:
                    logger.info("✅ Role already exists: %s", role_name)
            except Exception as e:
                logger.warning(f"User creation warning: {e}")

            # Create ragdb if not exists
            try:
                db_name = _safe_pg_identifier(DB_CONFIG['database'], 'database name')
                role_name = _safe_pg_identifier(DB_CONFIG['user'], 'role name')
                await admin_conn.execute(
                    f'CREATE DATABASE {db_name} OWNER {role_name};'
                )
                logger.info("✅ Created %s database", db_name)
            except Exception as e:
                if "already exists" not in str(e):
                    logger.warning(f"Database creation warning: {e}")

            await admin_conn.close()

            # Connect as raguser to setup schema
            conn = await asyncpg.connect(**DB_CONFIG)

            # Enable required extensions
            await conn.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS \"pg_trgm\";")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS \"btree_gin\";")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS \"btree_gist\";")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS \"pg_stat_statements\";")
            logger.info("✅ Enabled PostgreSQL extensions")

            # Create schemas (identifiers validated against allowlist before interpolation)
            schemas = ['public', 'analytics', 'search', 'evaluation', 'security']
            role_name = _safe_pg_identifier(DB_CONFIG['user'], 'role name')
            for schema in schemas:
                schema_name = _safe_pg_identifier(schema, 'schema name')
                await conn.execute(f'CREATE SCHEMA IF NOT EXISTS {schema_name};')
                await conn.execute(f'GRANT ALL ON SCHEMA {schema_name} TO {role_name};')
            logger.info("✅ Created database schemas")

            # Row Level Security setup for multi-tenancy
            await self.setup_rls_policies(conn)

            await conn.close()

            # Run Alembic migrations
            await self.run_alembic_migrations()

            logger.info("✅ PostgreSQL setup completed")

        except Exception as e:
            logger.error(f"❌ PostgreSQL setup failed: {e}")
            raise

    async def setup_rls_policies(self, conn):
        """Setup Row Level Security for multi-tenant isolation"""
        logger.info("🔒 Setting up Row Level Security policies...")

        # Enable RLS on key tables
        rls_tables = [
            'users', 'organizations', 'documents', 'entities',
            'search_queries', 'analytics_events', 'processing_jobs'
        ]

        for table in rls_tables:
            try:
                table_name = _safe_pg_identifier(table, 'table name')
                await conn.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;")
            except Exception as e:
                logger.warning(f"RLS setup for {table}: {e}")

        logger.info("✅ RLS policies configured")

    async def run_alembic_migrations(self):
        """Run Alembic database migrations"""
        logger.info("🔄 Running Alembic migrations...")

        try:
            from urllib.parse import quote_plus
            alembic_cfg = Config("backend/alembic.ini")
            alembic_url = (
                f"postgresql://{quote_plus(DB_CONFIG['user'])}:{quote_plus(DB_CONFIG['password'])}"
                f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
            )
            alembic_cfg.set_main_option("sqlalchemy.url", alembic_url)

            command.upgrade(alembic_cfg, "head")
            logger.info("✅ Alembic migrations completed")

        except Exception as e:
            logger.error(f"❌ Alembic migration failed: {e}")
            # Continue without failing the entire setup
            logger.warning("Continuing with database setup...")

    async def setup_neo4j(self):
        """Setup Neo4j knowledge graph with indexes and constraints"""
        logger.info("🔷 Setting up Neo4j knowledge graph...")

        try:
            self.neo4j_driver = AsyncGraphDatabase.driver(**NEO4J_CONFIG)

            async with self.neo4j_driver.session() as session:
                # Create uniqueness constraints
                constraints = [
                    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
                    "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
                    "CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
                    "CREATE CONSTRAINT organization_id_unique IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE"
                ]

                for constraint in constraints:
                    try:
                        await session.run(constraint)
                    except Exception as e:
                        logger.warning(f"Constraint creation: {e}")

                # Create indexes for performance
                indexes = [
                    "CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON (e.name)",
                    "CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type)",
                    "CREATE INDEX document_title_index IF NOT EXISTS FOR (d:Document) ON (d.title)",
                    "CREATE INDEX document_type_index IF NOT EXISTS FOR (d:Document) ON (d.type)",
                    "CREATE FULLTEXT INDEX entity_content_index IF NOT EXISTS FOR (e:Entity) ON EACH [e.name, e.description]",
                    "CREATE FULLTEXT INDEX document_content_index IF NOT EXISTS FOR (d:Document) ON EACH [d.title, d.content]"
                ]

                for index in indexes:
                    try:
                        await session.run(index)
                    except Exception as e:
                        logger.warning(f"Index creation: {e}")

                logger.info("✅ Neo4j constraints and indexes created")

            await self.neo4j_driver.close()
            logger.info("✅ Neo4j setup completed")

        except Exception as e:
            logger.error(f"❌ Neo4j setup failed: {e}")
            raise

    async def setup_qdrant(self):
        """Setup Qdrant vector database with collections"""
        logger.info("🔺 Setting up Qdrant vector database...")

        try:
            self.qdrant_client = QdrantClient(**QDRANT_CONFIG)

            # Define collections
            collections = {
                "documents": {
                    "vectors": VectorParams(size=1536, distance=Distance.COSINE),
                    "payload_schema": {
                        "document_id": "keyword",
                        "title": "text",
                        "content_type": "keyword",
                        "organization_id": "keyword",
                        "created_at": "integer"
                    }
                },
                "entities": {
                    "vectors": VectorParams(size=1536, distance=Distance.COSINE),
                    "payload_schema": {
                        "entity_id": "keyword",
                        "entity_type": "keyword",
                        "name": "text",
                        "organization_id": "keyword",
                        "created_at": "integer"
                    }
                },
                "multimodal": {
                    "vectors": VectorParams(size=1536, distance=Distance.COSINE),
                    "payload_schema": {
                        "content_id": "keyword",
                        "modality": "keyword",
                        "organization_id": "keyword",
                        "created_at": "integer"
                    }
                }
            }

            # Create collections
            for collection_name, config in collections.items():
                try:
                    # Check if collection exists
                    collections_list = self.qdrant_client.get_collections().collections
                    exists = any(c.name == collection_name for c in collections_list)

                    if not exists:
                        self.qdrant_client.create_collection(
                            collection_name=collection_name,
                            vectors_config=config["vectors"]
                        )
                        logger.info(f"✅ Created Qdrant collection: {collection_name}")
                    else:
                        logger.info(f"✅ Qdrant collection already exists: {collection_name}")

                except Exception as e:
                    logger.error(f"❌ Failed to create collection {collection_name}: {e}")

            logger.info("✅ Qdrant setup completed")

        except Exception as e:
            logger.error(f"❌ Qdrant setup failed: {e}")
            raise

    async def setup_redis(self):
        """Setup Redis with data structures and configurations"""
        logger.info("🔴 Setting up Redis cache and data structures...")

        try:
            self.redis_client = redis.Redis(**REDIS_CONFIG)

            # Test connection
            await self.redis_client.ping()

            # Configure Redis settings
            await self.redis_client.config_set("maxmemory", "256mb")
            await self.redis_client.config_set("maxmemory-policy", "allkeys-lru")

            # Setup pub/sub channels
            channels = ["search_updates", "processing_jobs", "notifications"]
            for channel in channels:
                await self.redis_client.sadd("active_channels", channel)

            # Create rate limiting structures
            await self.redis_client.hset("rate_limits", mapping={
                "search_per_minute": "60",
                "upload_per_hour": "100",
                "api_requests_per_minute": "1000"
            })

            # Setup caching templates
            cache_configs = {
                "search_cache": {"ttl": 3600, "max_size": 1000},
                "document_cache": {"ttl": 7200, "max_size": 500},
                "user_cache": {"ttl": 1800, "max_size": 2000}
            }

            for cache_name, config in cache_configs.items():
                await self.redis_client.hset("cache_configs", mapping={
                    f"{cache_name}_ttl": config["ttl"],
                    f"{cache_name}_max_size": config["max_size"]
                })

            logger.info("✅ Redis setup completed")
            await self.redis_client.close()

        except Exception as e:
            logger.error(f"❌ Redis setup failed: {e}")
            raise

    async def run_health_checks(self):
        """Run comprehensive health checks on all databases"""
        logger.info("🏥 Running database health checks...")

        health_results = {}

        # PostgreSQL health check
        try:
            conn = await asyncpg.connect(**DB_CONFIG)
            result = await conn.fetchval("SELECT 1")
            health_results["postgresql"] = "✅ Healthy"
            await conn.close()
        except Exception as e:
            health_results["postgresql"] = f"❌ {e}"

        # Neo4j health check
        try:
            driver = AsyncGraphDatabase.driver(**NEO4J_CONFIG)
            async with driver.session() as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()
                health_results["neo4j"] = "✅ Healthy"
            await driver.close()
        except Exception as e:
            health_results["neo4j"] = f"❌ {e}"

        # Qdrant health check
        try:
            client = QdrantClient(**QDRANT_CONFIG)
            collections = client.get_collections()
            health_results["qdrant"] = f"✅ Healthy ({len(collections.collections)} collections)"
        except Exception as e:
            health_results["qdrant"] = f"❌ {e}"

        # Redis health check
        try:
            client = redis.Redis(**REDIS_CONFIG)
            await client.ping()
            info = await client.info()
            health_results["redis"] = f"✅ Healthy ({info['used_memory_human']} memory used)"
            await client.close()
        except Exception as e:
            health_results["redis"] = f"❌ {e}"

        # Print health results
        logger.info("📊 Database Health Check Results:")
        for db, status in health_results.items():
            logger.info(f"  {db}: {status}")

        return health_results


async def main():
    """Main setup function"""
    setup = DatabaseSetup()
    await setup.setup_all_databases()


if __name__ == "__main__":
    asyncio.run(main())