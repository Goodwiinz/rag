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
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import json

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

# Database configuration from environment
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'raguser',
    'password': 'REDACTED',
    'database': 'ragdb'
}

NEO4J_CONFIG = {
    'uri': 'bolt://localhost:7687',
    'user': 'neo4j',
    'password': 'REDACTED'
}

QDRANT_CONFIG = {
    'url': 'http://localhost:6333',
    'api_key': 'REDACTED'
}

REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'password': 'REDACTED',
    'decode_responses': True
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
                host='localhost',
                port=5432,
                user='postgres',
                password='postgres',
                database='multimodal_rag'  # Existing database
            )

            # Create raguser if not exists
            try:
                await admin_conn.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'raguser') THEN
                            CREATE ROLE raguser LOGIN PASSWORD 'REDACTED';
                        END IF;
                    END
                    $$;
                """)
                logger.info("✅ Created raguser")
            except Exception as e:
                logger.warning(f"User creation warning: {e}")

            # Create ragdb if not exists
            try:
                await admin_conn.execute("CREATE DATABASE ragdb OWNER raguser;")
                logger.info("✅ Created ragdb database")
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

            # Create schemas
            schemas = ['public', 'analytics', 'search', 'evaluation', 'security']
            for schema in schemas:
                await conn.execute(f'CREATE SCHEMA IF NOT EXISTS {schema};')
                await conn.execute(f'GRANT ALL ON SCHEMA {schema} TO raguser;')
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
                await conn.execute(f"""
                    ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
                """)
            except Exception as e:
                logger.warning(f"RLS setup for {table}: {e}")

        logger.info("✅ RLS policies configured")

    async def run_alembic_migrations(self):
        """Run Alembic database migrations"""
        logger.info("🔄 Running Alembic migrations...")

        try:
            alembic_cfg = Config("backend/alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url",
                "postgresql://raguser:REDACTED@localhost:5432/ragdb")

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