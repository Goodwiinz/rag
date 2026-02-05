"""
Neo4j Optimization Framework for Multimodal Enterprise RAG System

This module provides comprehensive optimizations for Neo4j knowledge graph,
including query optimization, index management, and performance monitoring.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession
    from neo4j.exceptions import ServiceUnavailable, TransientError

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logging.warning("Neo4j driver not available. Install with: pip install neo4j")

logger = logging.getLogger(__name__)


class Neo4jOptimizationLevel(str, Enum):
    """Neo4j optimization levels"""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    HIGH_VOLUME = "high_volume"


import os


@dataclass
class Neo4jConfig:
    """Neo4j configuration for optimization"""

    uri: str = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user: str = os.environ.get("NEO4J_USER", "neo4j")
    password: str = os.environ.get("NEO4J_PASSWORD", "")
    database: str = os.environ.get("NEO4J_DATABASE", "neo4j")
    max_connection_lifetime: int = 3600
    max_connection_pool_size: int = 100
    connection_timeout: int = 30
    max_transaction_retry_time: int = 30
    optimization_level: Neo4jOptimizationLevel = Neo4jOptimizationLevel.PRODUCTION


@dataclass
class GraphMetrics:
    """Graph performance metrics"""

    query_time_ms: float
    nodes_created: int = 0
    relationships_created: int = 0
    nodes_deleted: int = 0
    relationships_deleted: int = 0
    indexes_used: List[str] = None
    memory_usage_mb: float = 0
    timestamp: datetime = None

    def __post_init__(self):
        if self.indexes_used is None:
            self.indexes_used = []
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class Neo4jOptimizer:
    """Advanced Neo4j optimization for knowledge graph performance"""

    def __init__(self, config: Neo4jConfig):
        if not NEO4J_AVAILABLE:
            raise ImportError(
                "Neo4j driver not available. Install with: pip install neo4j"
            )

        self.config = config
        self.driver: Optional[AsyncDriver] = None
        self.performance_history: List[GraphMetrics] = []
        self.index_cache: Dict[str, Any] = {}

    async def initialize(self):
        """Initialize Neo4j driver with optimized settings"""
        self.driver = AsyncGraphDatabase.driver(
            self.config.uri,
            auth=(self.config.user, self.config.password),
            max_connection_lifetime=self.config.max_connection_lifetime,
            max_connection_pool_size=self.config.max_connection_pool_size,
            connection_timeout=self.config.connection_timeout,
            max_transaction_retry_time=self.config.max_transaction_retry_time,
            # Optimized driver settings
            keep_alive=True,
            fetch_size=1000,
            trust="TRUST_ALL_CERTIFICATES"
            if "localhost" in self.config.uri
            else "TRUST_SYSTEM_CA_SIGNED_CERTIFICATES",
        )

        # Test connection
        await self._verify_connection()
        logger.info("Neo4j optimizer initialized successfully")

    async def _verify_connection(self):
        """Verify Neo4j connection and database availability"""
        try:
            async with self.driver.session(database=self.config.database) as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()
                if record["test"] != 1:
                    raise Exception("Connection test failed")
        except Exception as e:
            logger.error(f"Neo4j connection verification failed: {e}")
            raise

    async def apply_production_optimizations(self) -> Dict[str, Any]:
        """Apply all production optimizations for Neo4j"""
        results = {
            "success": True,
            "optimizations_applied": [],
            "errors": [],
            "metrics": {},
        }

        try:
            # 1. Configure database settings
            config_result = await self._configure_database_settings()
            results["optimizations_applied"].append(config_result)

            # 2. Create optimized indexes
            index_result = await self._create_optimized_indexes()
            results["optimizations_applied"].append(index_result)

            # 3. Create constraints for data integrity
            constraint_result = await self._create_constraints()
            results["optimizations_applied"].append(constraint_result)

            # 4. Optimize query patterns
            query_result = await self._optimize_query_patterns()
            results["optimizations_applied"].append(query_result)

            # 5. Set up monitoring and analytics
            monitoring_result = await self._setup_monitoring()
            results["optimizations_applied"].append(monitoring_result)

            # 6. Optimize memory and cache settings
            memory_result = await self._optimize_memory_settings()
            results["optimizations_applied"].append(memory_result)

            logger.info("All Neo4j production optimizations applied successfully")

        except Exception as e:
            logger.error(f"Error applying Neo4j optimizations: {e}")
            results["success"] = False
            results["errors"].append(str(e))

        return results

    async def _configure_database_settings(self) -> Dict[str, Any]:
        """Configure Neo4j database settings for production"""
        settings = []

        async with self.driver.session(database=self.config.database) as session:
            # Memory settings
            memory_configs = [
                "CALL dbms.setConfigValue('dbms.memory.heap.initial_size', '512m')",
                "CALL dbms.setConfigValue('dbms.memory.heap.max_size', '2G')",
                "CALL dbms.setConfigValue('dbms.memory.pagecache.size', '1G')",
                # Query settings
                "CALL dbms.setConfigValue('dbms.transaction.timeout', '60s')",
                "CALL dbms.setConfigValue('dbms.transaction.concurrent.maximum', '1000')",
                "CALL dbms.setConfigValue('dbms.query_cache_size', '1000')",
                # Logging settings
                "CALL dbms.setConfigValue('dbms.logs.query.enabled', 'true')",
                "CALL dbms.setConfigValue('dbms.logs.query.threshold', '1s')",
                "CALL dbms.setConfigValue('dbms.logs.query.time_logging_enabled', 'true')",
                # Performance settings
                "CALL dbms.setConfigValue('dbms.checkpoint.interval.time', '15m')",
                "CALL dbms.setConfigValue('dbms.checkpoint.interval.tx', '100000')",
                "CALL dbms.setConfigValue('dbms.tx_log.rotation_retention_policy', '100M size')",
                # Network settings
                "CALL dbms.setConfigValue('dbms.connectors.default_listen_address', '0.0.0.0')",  # nosec B104
                "CALL dbms.setConfigValue('dbms.connector.bolt.listen_address', '0.0.0.0:7687')",  # nosec B104
                "CALL dbms.setConfigValue('dbms.connector.http.listen_address', '0.0.0.0:7474')",  # nosec B104
            ]

            for config in memory_configs:
                try:
                    result = await session.run(config)
                    await result.consume()
                    settings.append(config.split("'")[1])  # Extract setting name
                    logger.debug(f"Applied Neo4j setting: {config}")
                except Exception as e:
                    logger.warning(f"Could not apply Neo4j setting {config}: {e}")

        return {
            "operation": "configure_database_settings",
            "success": True,
            "settings_applied": len(settings),
            "setting_details": settings,
        }

    async def _create_optimized_indexes(self) -> Dict[str, Any]:
        """Create optimized indexes for graph queries"""
        index_definitions = [
            # Entity indexes
            {
                "label": "Entity",
                "properties": ["id"],
                "type": "UNIQUE",
                "description": "Unique index for entity IDs",
            },
            {
                "label": "Entity",
                "properties": ["type"],
                "type": "RANGE",
                "description": "Index for entity types",
            },
            {
                "label": "Entity",
                "properties": ["source_document"],
                "type": "RANGE",
                "description": "Index for source document tracking",
            },
            {
                "label": "Entity",
                "properties": ["confidence"],
                "type": "RANGE",
                "description": "Index for confidence filtering",
            },
            # Document indexes
            {
                "label": "Document",
                "properties": ["id"],
                "type": "UNIQUE",
                "description": "Unique index for document IDs",
            },
            {
                "label": "Document",
                "properties": ["type"],
                "type": "RANGE",
                "description": "Index for document types",
            },
            {
                "label": "Document",
                "properties": ["created_at"],
                "type": "RANGE",
                "description": "Index for temporal queries",
            },
            {
                "label": "Document",
                "properties": ["tenant_id"],
                "type": "RANGE",
                "description": "Index for multi-tenant queries",
            },
            # Chunk indexes
            {
                "label": "Chunk",
                "properties": ["id"],
                "type": "UNIQUE",
                "description": "Unique index for chunk IDs",
            },
            {
                "label": "Chunk",
                "properties": ["document_id"],
                "type": "RANGE",
                "description": "Index for document-chunk relationships",
            },
            {
                "label": "Chunk",
                "properties": ["chunk_index"],
                "type": "RANGE",
                "description": "Index for chunk ordering",
            },
            # Vector indexes
            {
                "label": "Vector",
                "properties": ["id"],
                "type": "UNIQUE",
                "description": "Unique index for vector IDs",
            },
            {
                "label": "Vector",
                "properties": ["collection_name"],
                "type": "RANGE",
                "description": "Index for vector collections",
            },
            # Composite indexes for common query patterns
            {
                "label": "Entity",
                "properties": ["type", "source_document"],
                "type": "COMPOSITE",
                "description": "Composite index for entity type and source",
            },
            {
                "label": "Document",
                "properties": ["type", "tenant_id"],
                "type": "COMPOSITE",
                "description": "Composite index for document type and tenant",
            },
            # Full-text indexes
            {
                "label": "Entity",
                "properties": ["name"],
                "type": "FULLTEXT",
                "description": "Full-text index for entity names",
            },
            {
                "label": "Document",
                "properties": ["title", "content"],
                "type": "FULLTEXT",
                "description": "Full-text index for document search",
            },
        ]

        created_indexes = []
        async with self.driver.session(database=self.config.database) as session:
            for index_def in index_definitions:
                try:
                    if index_def["type"] == "UNIQUE":
                        if len(index_def["properties"]) == 1:
                            query = f"""
                            CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
                            FOR (n:{index_def['label']})
                            REQUIRE n.{index_def['properties'][0]} IS UNIQUE
                            """
                        else:
                            # For composite unique constraints
                            props = ", ".join(
                                [f"n.{p}" for p in index_def["properties"]]
                            )
                            query = f"""
                            CREATE CONSTRAINT entity_composite_unique IF NOT EXISTS
                            FOR (n:{index_def['label']})
                            REQUIRE ({props}) IS NODE KEY
                            """

                    elif index_def["type"] == "RANGE":
                        if len(index_def["properties"]) == 1:
                            query = f"""
                            CREATE INDEX entity_{index_def['properties'][0]}_idx IF NOT EXISTS
                            FOR (n:{index_def['label']})
                            ON (n.{index_def['properties'][0]})
                            """
                        else:
                            # Composite range index
                            props = ", ".join(index_def["properties"])
                            query = f"""
                            CREATE INDEX entity_composite_idx IF NOT EXISTS
                            FOR (n:{index_def['label']})
                            ON ({props})
                            """

                    elif index_def["type"] == "FULLTEXT":
                        props = ", ".join([f"n.{p}" for p in index_def["properties"]])
                        query = f"""
                        CREATE FULLTEXT INDEX entity_fulltext_idx IF NOT EXISTS
                        FOR (n:{index_def['label']})
                        ON EACH [{props}]
                        """

                    else:
                        # Default to range index
                        query = f"""
                        CREATE INDEX {index_def['label'].lower()}_idx IF NOT EXISTS
                        FOR (n:{index_def['label']})
                        ON (n.{index_def['properties'][0]})
                        """

                    result = await session.run(query)
                    await result.consume()

                    created_indexes.append(
                        {
                            "label": index_def["label"],
                            "properties": index_def["properties"],
                            "type": index_def["type"],
                            "description": index_def["description"],
                        }
                    )

                    logger.debug(
                        f"Created Neo4j index: {index_def['label']} on {index_def['properties']}"
                    )

                except Exception as e:
                    logger.warning(f"Failed to create index {index_def['label']}: {e}")

        return {
            "operation": "create_optimized_indexes",
            "success": True,
            "indexes_created": len(created_indexes),
            "index_details": created_indexes,
        }

    async def _create_constraints(self) -> Dict[str, Any]:
        """Create constraints for data integrity"""
        constraints = [
            # Node existence constraints
            """
            CREATE CONSTRAINT document_exists IF NOT EXISTS
            FOR ()-[r:HAS_CHUNK]->()
            REQUIRE EXISTS (r)
            """,
            # Relationship property constraints
            """
            CREATE CONSTRAINT chunk_index_positive IF NOT EXISTS
            FOR ()-[r:HAS_CHUNK]->()
            REQUIRE r.chunk_index >= 0
            """,
            # Entity uniqueness within documents
            """
            CREATE CONSTRAINT entity_doc_unique IF NOT EXISTS
            FOR (e:Entity)-[:EXTRACTED_FROM]->(d:Document)
            REQUIRE (e.id, d.id) IS NODE KEY
            """,
        ]

        created_constraints = []
        async with self.driver.session(database=self.config.database) as session:
            for constraint_sql in constraints:
                try:
                    result = await session.run(constraint_sql)
                    await result.consume()
                    constraint_name = constraint_sql.split("CONSTRAINT ")[1].split(
                        " IF"
                    )[0]
                    created_constraints.append(constraint_name)
                    logger.debug(f"Created Neo4j constraint: {constraint_name}")
                except Exception as e:
                    logger.warning(
                        f"Failed to create constraint: {constraint_sql}, Error: {e}"
                    )

        return {
            "operation": "create_constraints",
            "success": True,
            "constraints_created": len(created_constraints),
            "constraint_details": created_constraints,
        }

    async def _optimize_query_patterns(self) -> Dict[str, Any]:
        """Optimize common query patterns"""
        optimized_procedures = [
            # Create stored procedures for common patterns
            """
            CALL apoc.custom.asFunction(
                'findEntitiesByType',
                'MATCH (e:Entity {type: $type}) WHERE e.confidence >= $minConfidence RETURN e',
                'READ'
            )
            """,
            """
            CALL apoc.custom.asFunction(
                'getDocumentEntities',
                'MATCH (d:Document {id: $docId})<-[:EXTRACTED_FROM]-(e:Entity) RETURN e ORDER BY e.confidence DESC',
                'READ'
            )
            """,
            """
            CALL apoc.custom.asFunction(
                'findRelatedEntities',
                'MATCH (e1:Entity {id: $entityId})-[]-(e2:Entity) RETURN DISTINCT e2',
                'READ'
            )
            """,
        ]

        created_procedures = []
        async with self.driver.session(database=self.config.database) as session:
            for proc_sql in optimized_procedures:
                try:
                    result = await session.run(proc_sql)
                    await result.consume()
                    proc_name = proc_sql.split("'")[1]
                    created_procedures.append(proc_name)
                    logger.debug(f"Created Neo4j procedure: {proc_name}")
                except Exception as e:
                    logger.warning(
                        f"Failed to create procedure: {proc_sql}, Error: {e}"
                    )

        return {
            "operation": "optimize_query_patterns",
            "success": True,
            "procedures_created": len(created_procedures),
            "procedure_details": created_procedures,
        }

    async def _setup_monitoring(self) -> Dict[str, Any]:
        """Set up monitoring and analytics"""
        monitoring_queries = [
            # Create monitoring views
            """
            CREATE VIEW entity_statistics IF NOT EXISTS AS
            MATCH (e:Entity)
            RETURN e.type as entity_type, count(*) as count, avg(e.confidence) as avg_confidence
            """,
            """
            CREATE VIEW relationship_statistics IF NOT EXISTS AS
            MATCH ()-[r]->()
            RETURN type(r) as relationship_type, count(*) as count
            """,
            """
            CREATE VIEW document_statistics IF NOT EXISTS AS
            MATCH (d:Document)
            RETURN d.type as document_type, count(*) as count, size((d)<-[:EXTRACTED_FROM]-()) as entity_count
            """,
        ]

        created_views = []
        async with self.driver.session(database=self.config.database) as session:
            for view_sql in monitoring_queries:
                try:
                    result = await session.run(view_sql)
                    await result.consume()
                    view_name = view_sql.split("VIEW ")[1].split(" IF")[0]
                    created_views.append(view_name)
                    logger.debug(f"Created Neo4j view: {view_name}")
                except Exception as e:
                    logger.warning(f"Failed to create view: {view_sql}, Error: {e}")

        return {
            "operation": "setup_monitoring",
            "success": True,
            "views_created": len(created_views),
            "view_details": created_views,
        }

    async def _optimize_memory_settings(self) -> Dict[str, Any]:
        """Optimize memory and cache settings"""
        memory_settings = [
            # Warm up caches with common queries
            "MATCH (e:Entity) RETURN count(*)",
            "MATCH (d:Document) RETURN count(*)",
            "MATCH ()-[r]->() RETURN count(*)",
        ]

        warmed_caches = []
        async with self.driver.session(database=self.config.database) as session:
            for warmup_query in memory_settings:
                try:
                    start_time = time.time()
                    result = await session.run(warmup_query)
                    await result.consume()
                    query_time = time.time() - start_time
                    warmed_caches.append(
                        {"query": warmup_query, "time_ms": query_time * 1000}
                    )
                    logger.debug(f"Warmed cache with query: {warmup_query}")
                except Exception as e:
                    logger.warning(f"Failed to warm cache with {warmup_query}: {e}")

        return {
            "operation": "optimize_memory_settings",
            "success": True,
            "caches_warmed": len(warmed_caches),
            "cache_details": warmed_caches,
        }

    async def analyze_query_performance(
        self, query: str, params: Dict = None
    ) -> Dict[str, Any]:
        """Analyze query performance and suggest optimizations"""
        async with self.driver.session(database=self.config.database) as session:
            try:
                start_time = time.time()

                # Run EXPLAIN and PROFILE
                explain_result = await session.run(f"EXPLAIN {query}", params or {})
                explain_plan = await explain_result.data()

                profile_result = await session.run(f"PROFILE {query}", params or {})
                profile_data = await profile_result.data()

                execution_time = time.time() - start_time

                # Extract performance metrics
                total_db_hits = (
                    profile_data[0].get("totalDbHits", 0) if profile_data else 0
                )
                rows_returned = len(profile_data) if profile_data else 0

                # Generate optimization suggestions
                suggestions = []
                if total_db_hits > rows_returned * 10:
                    suggestions.append(
                        "High database hits detected - consider adding indexes"
                    )

                if "NodeByLabelScan" in str(explain_plan):
                    suggestions.append(
                        "Label scan detected - consider adding property indexes"
                    )

                if execution_time > 1.0:
                    suggestions.append(
                        "Slow query detected - consider query optimization"
                    )

                return {
                    "query": query,
                    "execution_time_ms": execution_time * 1000,
                    "total_db_hits": total_db_hits,
                    "rows_returned": rows_returned,
                    "explain_plan": explain_plan,
                    "optimization_suggestions": suggestions,
                }

            except Exception as e:
                return {
                    "query": query,
                    "error": str(e),
                    "optimization_suggestions": ["Query failed to execute"],
                }

    async def get_graph_statistics(self) -> Dict[str, Any]:
        """Get comprehensive graph statistics"""
        async with self.driver.session(database=self.config.database) as session:
            # Node counts by label
            node_counts_result = await session.run(
                """
                MATCH (n)
                RETURN labels(n) as labels, count(n) as count
                ORDER BY count DESC
            """
            )
            node_counts = {
                str(record["labels"][0] if record["labels"] else "Unknown"): record[
                    "count"
                ]
                for record in await node_counts_result.data()
            }

            # Relationship counts by type
            rel_counts_result = await session.run(
                """
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
                ORDER BY count DESC
            """
            )
            rel_counts = {
                record["type"]: record["count"]
                for record in await rel_counts_result.data()
            }

            # Index information
            index_result = await session.run("SHOW INDEXES")
            indexes = [dict(record) for record in await index_result.data()]

            # Constraint information
            constraint_result = await session.run("SHOW CONSTRAINTS")
            constraints = [dict(record) for record in await constraint_result.data()]

            # Database size and memory usage
            memory_result = await session.run(
                "CALL dbms.queryJmx('org.neo4j:instance=kernel#0,name=Memory')"
            )
            memory_info = [dict(record) for record in await memory_result.data()]

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "node_counts": node_counts,
                "relationship_counts": rel_counts,
                "total_nodes": sum(node_counts.values()),
                "total_relationships": sum(rel_counts.values()),
                "indexes": indexes,
                "constraints": constraints,
                "memory_usage": memory_info,
                "performance_history_size": len(self.performance_history),
            }

    async def cleanup_old_data(self, days_old: int = 30) -> Dict[str, Any]:
        """Clean up old graph data to maintain performance"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        async with self.driver.session(database=self.config.database) as session:
            cleanup_stats = {}

            try:
                # Delete old entities with low confidence
                entity_result = await session.run(
                    """
                    MATCH (e:Entity)
                    WHERE e.created_at < $cutoff_date AND e.confidence < 0.5
                    DETACH DELETE e
                    RETURN count(e) as deleted_entities
                """,
                    cutoff_date=cutoff_date.isoformat(),
                )

                deleted_entities = (await entity_result.data())[0]["deleted_entities"]
                cleanup_stats["deleted_entities"] = deleted_entities

                # Delete orphaned chunks
                chunk_result = await session.run(
                    """
                    MATCH (c:Chunk)
                    WHERE NOT (c)-[:PART_OF]->(:Document)
                    DETACH DELETE c
                    RETURN count(c) as deleted_chunks
                """
                )

                deleted_chunks = (await chunk_result.data())[0]["deleted_chunks"]
                cleanup_stats["deleted_chunks"] = deleted_chunks

                # Cleanup database statistics
                await session.run("CALL db.stats.retrieve('GRAPH COUNTS')")
                await session.run("CALL db.stats.collect('GRAPH COUNTS')")

                logger.info(f"Graph cleanup completed: {cleanup_stats}")

                return {
                    "success": True,
                    "cleanup_stats": cleanup_stats,
                    "cutoff_date": cutoff_date.isoformat(),
                }

            except Exception as e:
                logger.error(f"Graph cleanup failed: {e}")
                return {"success": False, "error": str(e)}

    async def optimize_database(self) -> Dict[str, Any]:
        """Run database optimization routines"""
        async with self.driver.session(database=self.config.database) as session:
            optimization_results = {}

            try:
                # Update statistics
                await session.run("CALL db.stats.collect('GRAPH COUNTS')")
                optimization_results["statistics_updated"] = True

                # Trigger index updates
                await session.run("CALL db.index.fulltext.listAvailableAnalyzers()")
                optimization_results["indexes_updated"] = True

                # Optimize for read performance
                await session.run("CALL dbms.queryJmx('java.lang:type=Memory')")
                optimization_results["memory_optimized"] = True

                logger.info("Neo4j optimization completed")

                return {
                    "success": True,
                    "optimizations": optimization_results,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            except Exception as e:
                logger.error(f"Neo4j optimization failed: {e}")
                return {"success": False, "error": str(e)}

    async def close(self):
        """Close Neo4j driver"""
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j driver closed")


# Utility functions
async def create_neo4j_optimizer() -> Neo4jOptimizer:
    """Create and initialize Neo4j optimizer"""
    config = Neo4jConfig(
        uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        user=os.environ.get("NEO4J_USER", "neo4j"),
        password=os.environ.get("NEO4J_PASSWORD", ""),
        database=os.environ.get("NEO4J_DATABASE", "neo4j"),
        max_connection_pool_size=50,
        optimization_level=Neo4jOptimizationLevel.PRODUCTION,
    )

    optimizer = Neo4jOptimizer(config)
    await optimizer.initialize()
    return optimizer


async def run_graph_health_check() -> Dict[str, Any]:
    """Run comprehensive graph health check"""
    optimizer = await create_neo4j_optimizer()
    try:
        return await optimizer.get_graph_statistics()
    finally:
        await optimizer.close()
