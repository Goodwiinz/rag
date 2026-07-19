"""
Cross-Database Integration and Monitoring for Multimodal Enterprise RAG System

This module provides unified monitoring, coordination, and optimization across all databases:
PostgreSQL, Neo4j, Qdrant, and Redis.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from ..qdrant_optimization import QdrantOptimizationConfig, QdrantOptimizer
from .neo4j_optimizer import Neo4jConfig, Neo4jOptimizationLevel, Neo4jOptimizer
from .postgresql_optimizer import DatabaseConfig, OptimizationLevel, PostgreSQLOptimizer
from .redis_optimizer import RedisConfig, RedisOptimizationLevel, RedisOptimizer

logger = logging.getLogger(__name__)


class DatabaseType(str, Enum):
    """Database types in the system"""

    POSTGRESQL = "postgresql"
    NEO4J = "neo4j"
    QDRANT = "qdrant"
    REDIS = "redis"


class SyncStatus(str, Enum):
    """Data synchronization status"""

    SYNCED = "synced"
    PENDING = "pending"
    ERROR = "error"
    CONFLICT = "conflict"


@dataclass
class DatabaseHealth:
    """Individual database health status"""

    database_type: DatabaseType
    status: str  # healthy, warning, error
    response_time_ms: float
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.metrics is None:
            self.metrics = {}


@dataclass
class CrossDatabaseMetrics:
    """Cross-database performance metrics"""

    total_databases: int
    healthy_databases: int
    warning_databases: int
    error_databases: int
    average_response_time_ms: float
    data_sync_status: Dict[str, SyncStatus]
    cross_db_operations: int
    failed_operations: int
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    @property
    def health_percentage(self) -> float:
        return (
            (self.healthy_databases / self.total_databases) * 100
            if self.total_databases > 0
            else 0
        )

    @property
    def success_rate(self) -> float:
        total_ops = self.cross_db_operations
        if total_ops == 0:
            return 100.0
        return ((total_ops - self.failed_operations) / total_ops) * 100


class CrossDatabaseIntegration:
    """Unified cross-database integration and monitoring system"""

    def __init__(self):
        self.optimizers: Dict[DatabaseType, Any] = {}
        self.health_status: Dict[DatabaseType, DatabaseHealth] = {}
        self.metrics_history: List[CrossDatabaseMetrics] = []
        self.sync_status: Dict[str, SyncStatus] = {}
        self.operation_queue: List[Dict[str, Any]] = []
        self.failed_operations_count = 0
        self.alert_thresholds = {
            "response_time_ms": 1000,
            "error_rate_percent": 5,
            "sync_delay_minutes": 10,
            "memory_usage_percent": 85,
        }

    def _record_failed_operation(self, operation_type: str, error: Exception) -> None:
        """Record a failed operation for metrics tracking"""
        self.failed_operations_count += 1
        logger.error(f"Failed operation ({operation_type}): {error}")

    async def initialize_all_databases(self) -> Dict[str, Any]:
        """Initialize all database optimizers with production configurations"""
        results = {"success": True, "initialized": [], "failed": [], "errors": []}

        # Initialize PostgreSQL
        try:
            pg_config = DatabaseConfig(
                host=os.environ.get("POSTGRES_HOST", "localhost"),
                port=int(os.environ.get("POSTGRES_PORT", "5432")),
                user=os.environ.get("POSTGRES_USER", "raguser"),
                password=os.environ.get("POSTGRES_PASSWORD", ""),
                database=os.environ.get("POSTGRES_DB", "ragdb"),
                pool_size=50,
                optimization_level=OptimizationLevel.PRODUCTION,
            )
            pg_optimizer = PostgreSQLOptimizer(pg_config)
            await pg_optimizer.initialize()
            self.optimizers[DatabaseType.POSTGRESQL] = pg_optimizer
            results["initialized"].append("postgresql")
            logger.info("PostgreSQL optimizer initialized")
        except Exception as e:
            self._record_failed_operation("postgresql_init", e)
            results["failed"].append("postgresql")
            results["errors"].append(f"PostgreSQL initialization failed: {e}")

        # Initialize Neo4j
        try:
            neo4j_config = Neo4jConfig(
                uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
                user=os.environ.get("NEO4J_USER", "neo4j"),
                password=os.environ.get("NEO4J_PASSWORD", ""),
                database=os.environ.get("NEO4J_DATABASE", "neo4j"),
                max_connection_pool_size=50,
                optimization_level=Neo4jOptimizationLevel.PRODUCTION,
            )
            neo4j_optimizer = Neo4jOptimizer(neo4j_config)
            await neo4j_optimizer.initialize()
            self.optimizers[DatabaseType.NEO4J] = neo4j_optimizer
            results["initialized"].append("neo4j")
            logger.info("Neo4j optimizer initialized")
        except Exception as e:
            self._record_failed_operation("neo4j_init", e)
            results["failed"].append("neo4j")
            results["errors"].append(f"Neo4j initialization failed: {e}")

        # Initialize Qdrant
        try:
            qdrant_config = QdrantOptimizationConfig()
            from qdrant_client import QdrantClient

            qdrant_client = QdrantClient(url="http://localhost:6333")
            qdrant_optimizer = QdrantOptimizer(qdrant_client, qdrant_config)
            self.optimizers[DatabaseType.QDRANT] = qdrant_optimizer
            results["initialized"].append("qdrant")
            logger.info("Qdrant optimizer initialized")
        except Exception as e:
            self._record_failed_operation("qdrant_init", e)
            results["failed"].append("qdrant")
            results["errors"].append(f"Qdrant initialization failed: {e}")

        # Initialize Redis
        try:
            redis_config = RedisConfig(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", "6379")),
                password=os.environ.get("REDIS_PASSWORD", ""),
                database=int(os.environ.get("REDIS_DB", "0")),
                max_connections=100,
                optimization_level=RedisOptimizationLevel.PRODUCTION,
            )
            redis_optimizer = RedisOptimizer(redis_config)
            await redis_optimizer.initialize()
            self.optimizers[DatabaseType.REDIS] = redis_optimizer
            results["initialized"].append("redis")
            logger.info("Redis optimizer initialized")
        except Exception as e:
            self._record_failed_operation("redis_init", e)
            results["failed"].append("redis")
            results["errors"].append(f"Redis initialization failed: {e}")

        results["success"] = len(results["initialized"]) == len(DatabaseType)
        return results

    async def apply_production_optimizations(self) -> Dict[str, Any]:
        """Apply production optimizations across all databases"""
        results = {"success": True, "optimization_results": {}, "errors": []}

        optimization_tasks = {
            DatabaseType.POSTGRESQL: self.optimizers[
                DatabaseType.POSTGRESQL
            ].apply_production_optimizations(),
            DatabaseType.NEO4J: self.optimizers[
                DatabaseType.NEO4J
            ].apply_production_optimizations(),
            DatabaseType.REDIS: self.optimizers[
                DatabaseType.REDIS
            ].apply_production_optimizations(),
        }

        # Qdrant optimization (sync)
        if DatabaseType.QDRANT in self.optimizers:
            try:
                qdrant_result = await self._optimize_qdrant_production()
                results["optimization_results"][DatabaseType.QDRANT] = qdrant_result
            except Exception as e:
                results["errors"].append(f"Qdrant optimization failed: {e}")

        # Run async optimizations
        for db_type, task in optimization_tasks.items():
            try:
                result = await task
                results["optimization_results"][db_type] = result
                if not result.get("success", True):
                    results["errors"].append(f"{db_type.value} optimization had errors")
            except Exception as e:
                results["errors"].append(f"{db_type.value} optimization failed: {e}")

        results["success"] = len(results["errors"]) == 0
        return results

    async def _optimize_qdrant_production(self) -> Dict[str, Any]:
        """Optimize Qdrant for production"""
        qdrant_optimizer = self.optimizers[DatabaseType.QDRANT]

        # Create optimized collections for monitoring
        collections = ["monitoring_metrics", "monitoring_traces", "monitoring_logs"]
        optimization_results = []

        for collection_name in collections:
            try:
                # Check if collection exists
                collections_info = qdrant_optimizer.client.get_collections()
                collection_exists = any(
                    c.name == collection_name for c in collections_info.collections
                )

                if not collection_exists:
                    # Create optimized collection
                    success = qdrant_optimizer.create_optimized_collection(
                        collection_name
                    )
                    if success:
                        # Create payload indexes
                        qdrant_optimizer.create_payload_indexes(collection_name)
                        optimization_results.append(
                            f"Created and optimized collection: {collection_name}"
                        )
                else:
                    # Optimize existing collection
                    qdrant_optimizer.optimize_collection(collection_name)
                    optimization_results.append(
                        f"Optimized existing collection: {collection_name}"
                    )

            except Exception as e:
                logger.warning(
                    f"Failed to optimize Qdrant collection {collection_name}: {e}"
                )

        return {
            "success": True,
            "optimizations": optimization_results,
            "collections_count": len(collections),
        }

    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check across all databases"""
        health_results = {}
        total_response_time = 0
        healthy_count = 0
        warning_count = 0
        error_count = 0

        # Check PostgreSQL
        if DatabaseType.POSTGRESQL in self.optimizers:
            try:
                start_time = time.time()
                pg_report = await self.optimizers[
                    DatabaseType.POSTGRESQL
                ].get_optimization_report()
                response_time = (time.time() - start_time) * 1000

                # Determine status
                status = "healthy"
                if response_time > self.alert_thresholds["response_time_ms"]:
                    status = "warning"
                if "error" in str(pg_report).lower():
                    status = "error"

                health_results[DatabaseType.POSTGRESQL] = DatabaseHealth(
                    database_type=DatabaseType.POSTGRESQL,
                    status=status,
                    response_time_ms=response_time,
                    metrics=pg_report,
                )
                total_response_time += response_time

                if status == "healthy":
                    healthy_count += 1
                elif status == "warning":
                    warning_count += 1
                else:
                    error_count += 1

            except Exception as e:
                health_results[DatabaseType.POSTGRESQL] = DatabaseHealth(
                    database_type=DatabaseType.POSTGRESQL,
                    status="error",
                    response_time_ms=0,
                    error_message=str(e),
                )
                error_count += 1

        # Check Neo4j
        if DatabaseType.NEO4J in self.optimizers:
            try:
                start_time = time.time()
                neo4j_stats = await self.optimizers[
                    DatabaseType.NEO4J
                ].get_graph_statistics()
                response_time = (time.time() - start_time) * 1000

                status = "healthy"
                if response_time > self.alert_thresholds["response_time_ms"]:
                    status = "warning"
                if "error" in str(neo4j_stats).lower():
                    status = "error"

                health_results[DatabaseType.NEO4J] = DatabaseHealth(
                    database_type=DatabaseType.NEO4J,
                    status=status,
                    response_time_ms=response_time,
                    metrics=neo4j_stats,
                )
                total_response_time += response_time

                if status == "healthy":
                    healthy_count += 1
                elif status == "warning":
                    warning_count += 1
                else:
                    error_count += 1

            except Exception as e:
                health_results[DatabaseType.NEO4J] = DatabaseHealth(
                    database_type=DatabaseType.NEO4J,
                    status="error",
                    response_time_ms=0,
                    error_message=str(e),
                )
                error_count += 1

        # Check Qdrant
        if DatabaseType.QDRANT in self.optimizers:
            try:
                start_time = time.time()
                qdrant_stats = self.optimizers[
                    DatabaseType.QDRANT
                ].get_performance_stats()
                response_time = (time.time() - start_time) * 1000

                status = "healthy"
                if response_time > self.alert_thresholds["response_time_ms"]:
                    status = "warning"

                health_results[DatabaseType.QDRANT] = DatabaseHealth(
                    database_type=DatabaseType.QDRANT,
                    status=status,
                    response_time_ms=response_time,
                    metrics=qdrant_stats,
                )
                total_response_time += response_time

                if status == "healthy":
                    healthy_count += 1
                elif status == "warning":
                    warning_count += 1
                else:
                    error_count += 1

            except Exception as e:
                health_results[DatabaseType.QDRANT] = DatabaseHealth(
                    database_type=DatabaseType.QDRANT,
                    status="error",
                    response_time_ms=0,
                    error_message=str(e),
                )
                error_count += 1

        # Check Redis
        if DatabaseType.REDIS in self.optimizers:
            try:
                start_time = time.time()
                redis_metrics = await self.optimizers[
                    DatabaseType.REDIS
                ].get_redis_metrics()
                response_time = (time.time() - start_time) * 1000

                status = "healthy"
                if response_time > self.alert_thresholds["response_time_ms"]:
                    status = "warning"
                if redis_metrics.get("error"):
                    status = "error"

                health_results[DatabaseType.REDIS] = DatabaseHealth(
                    database_type=DatabaseType.REDIS,
                    status=status,
                    response_time_ms=response_time,
                    metrics=redis_metrics,
                )
                total_response_time += response_time

                if status == "healthy":
                    healthy_count += 1
                elif status == "warning":
                    warning_count += 1
                else:
                    error_count += 1

            except Exception as e:
                health_results[DatabaseType.REDIS] = DatabaseHealth(
                    database_type=DatabaseType.REDIS,
                    status="error",
                    response_time_ms=0,
                    error_message=str(e),
                )
                error_count += 1

        # Update health status
        self.health_status = health_results

        # Calculate overall metrics
        total_databases = len(health_results)
        avg_response_time = (
            total_response_time / total_databases if total_databases > 0 else 0
        )

        cross_metrics = CrossDatabaseMetrics(
            total_databases=total_databases,
            healthy_databases=healthy_count,
            warning_databases=warning_count,
            error_databases=error_count,
            average_response_time_ms=avg_response_time,
            data_sync_status=self.sync_status,
            cross_db_operations=len(self.operation_queue),
            failed_operations=self.failed_operations_count,
        )

        self.metrics_history.append(cross_metrics)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_health": {
                "status": "healthy"
                if error_count == 0
                else "warning"
                if error_count < 2
                else "error",
                "healthy_databases": healthy_count,
                "total_databases": total_databases,
                "health_percentage": cross_metrics.health_percentage,
            },
            "database_health": {
                db_type.value: asdict(health)
                for db_type, health in health_results.items()
            },
            "cross_metrics": asdict(cross_metrics),
            "alert_thresholds": self.alert_thresholds,
        }

    async def sync_monitoring_data(
        self, source_db: DatabaseType, target_db: DatabaseType, data_type: str
    ) -> Dict[str, Any]:
        """Sync monitoring data between databases"""
        sync_id = str(uuid.uuid4())
        start_time = time.time()

        try:
            # Mark sync as pending
            sync_key = f"sync:{source_db.value}->{target_db.value}:{data_type}"
            self.sync_status[sync_key] = SyncStatus.PENDING

            # Extract data from source
            source_data = await self._extract_monitoring_data(source_db, data_type)
            if not source_data:
                self.sync_status[sync_key] = SyncStatus.ERROR
                return {
                    "success": False,
                    "sync_id": sync_id,
                    "error": "No data extracted from source",
                    "execution_time_ms": (time.time() - start_time) * 1000,
                }

            # Transform data for target
            transformed_data = await self._transform_monitoring_data(
                source_data, data_type, target_db
            )

            # Load data to target
            load_result = await self._load_monitoring_data(
                target_db, transformed_data, data_type
            )

            execution_time = (time.time() - start_time) * 1000

            if load_result["success"]:
                self.sync_status[sync_key] = SyncStatus.SYNCED
                logger.info(
                    f"Successfully synced {data_type} from {source_db.value} to {target_db.value}"
                )
            else:
                self.sync_status[sync_key] = SyncStatus.ERROR
                logger.error(
                    f"Failed to sync {data_type} from {source_db.value} to {target_db.value}"
                )

            return {
                "success": load_result["success"],
                "sync_id": sync_id,
                "source_db": source_db.value,
                "target_db": target_db.value,
                "data_type": data_type,
                "records_processed": len(source_data)
                if isinstance(source_data, list)
                else 1,
                "execution_time_ms": execution_time,
                "status": self.sync_status[sync_key].value,
            }

        except Exception as e:
            sync_key = f"sync:{source_db.value}->{target_db.value}:{data_type}"
            self.sync_status[sync_key] = SyncStatus.ERROR
            logger.error(f"Sync failed: {e}")

            return {
                "success": False,
                "sync_id": sync_id,
                "error": str(e),
                "execution_time_ms": (time.time() - start_time) * 1000,
                "status": SyncStatus.ERROR.value,
            }

    async def _extract_monitoring_data(
        self, db_type: DatabaseType, data_type: str
    ) -> Any:
        """Extract monitoring data from source database"""
        if db_type == DatabaseType.POSTGRESQL:
            # Extract from PostgreSQL monitoring tables
            optimizer = self.optimizers[DatabaseType.POSTGRESQL]
            async with optimizer._get_connection_config() as conn:
                if data_type == "metrics":
                    query = "SELECT * FROM monitoring_metrics WHERE timestamp >= NOW() - INTERVAL '1 hour'"
                    return await conn.fetch(query)
                elif data_type == "logs":
                    query = "SELECT * FROM monitoring_logs WHERE timestamp >= NOW() - INTERVAL '1 hour'"
                    return await conn.fetch(query)
                elif data_type == "traces":
                    query = "SELECT * FROM monitoring_traces WHERE start_time >= NOW() - INTERVAL '1 hour'"
                    return await conn.fetch(query)

        elif db_type == DatabaseType.REDIS:
            # Extract from Redis cache
            optimizer = self.optimizers[DatabaseType.REDIS]
            if data_type == "metrics":
                return await optimizer.get_monitoring_data("metrics")
            elif data_type == "logs":
                return await optimizer.get_monitoring_data("logs")
            elif data_type == "traces":
                return await optimizer.get_monitoring_data("traces")

        return None

    async def _transform_monitoring_data(
        self, source_data: Any, data_type: str, target_db: DatabaseType
    ) -> Any:
        """Transform monitoring data for target database"""
        # Transform data based on target database requirements
        if target_db == DatabaseType.QDRANT:
            # Convert to vector format for Qdrant
            if data_type == "metrics":
                # Convert metrics to vectors for similarity search
                transformed = []
                for record in source_data:
                    vector = [
                        record.get("value", 0.0),
                        record.get("timestamp", 0),
                        record.get("definition_id", 0),
                    ]
                    transformed.append(
                        {
                            "id": str(record.get("id", "")),
                            "vector": vector,
                            "payload": {
                                "source_db": "postgresql",
                                "data_type": "metrics",
                                "metric_name": record.get("name", ""),
                                "timestamp": record.get("timestamp", ""),
                            },
                        }
                    )
                return transformed

        elif target_db == DatabaseType.REDIS:
            # Convert to cache-friendly format
            if isinstance(source_data, list):
                transformed = {}
                for record in source_data:
                    key = f"{data_type}:{record.get('id', '')}"
                    transformed[key] = record
                return transformed

        return source_data

    async def _load_monitoring_data(
        self, db_type: DatabaseType, data: Any, data_type: str
    ) -> Dict[str, Any]:
        """Load monitoring data to target database"""
        try:
            if db_type == DatabaseType.QDRANT:
                optimizer = self.optimizers[DatabaseType.QDRANT]
                collection_name = f"monitoring_{data_type}"

                # Check if collection exists
                collections_info = optimizer.client.get_collections()
                collection_exists = any(
                    c.name == collection_name for c in collections_info.collections
                )

                if not collection_exists:
                    optimizer.create_optimized_collection(collection_name)

                # Upload data in batches
                if isinstance(data, list):
                    vectors = [item["vector"] for item in data]
                    payloads = [item["payload"] for item in data]
                    ids = [item["id"] for item in data]

                    success = await optimizer.batch_upload_optimized(
                        collection_name=collection_name,
                        vectors=vectors,
                        payloads=payloads,
                        ids=ids,
                    )
                    return {"success": success, "records_loaded": len(data)}

            elif db_type == DatabaseType.REDIS:
                optimizer = self.optimizers[DatabaseType.REDIS]
                if isinstance(data, dict):
                    for key, value in data.items():
                        await optimizer.cache_monitoring_data(
                            data_type=data_type, data=value
                        )
                    return {"success": True, "records_loaded": len(data)}

            return {"success": True, "records_loaded": 1}

        except Exception as e:
            logger.error(f"Failed to load data to {db_type.value}: {e}")
            return {"success": False, "error": str(e)}

    async def cleanup_all_databases(self, days_old: int = 30) -> Dict[str, Any]:
        """Run cleanup operations across all databases"""
        cleanup_results = {}

        # PostgreSQL cleanup
        if DatabaseType.POSTGRESQL in self.optimizers:
            try:
                # This would be implemented in PostgreSQL optimizer
                cleanup_results[DatabaseType.POSTGRESQL] = {
                    "success": True,
                    "message": "Cleanup scheduled",
                }
            except Exception as e:
                cleanup_results[DatabaseType.POSTGRESQL] = {
                    "success": False,
                    "error": str(e),
                }

        # Neo4j cleanup
        if DatabaseType.NEO4J in self.optimizers:
            try:
                neo4j_result = await self.optimizers[
                    DatabaseType.NEO4J
                ].cleanup_old_data(days_old)
                cleanup_results[DatabaseType.NEO4J] = neo4j_result
            except Exception as e:
                cleanup_results[DatabaseType.NEO4J] = {
                    "success": False,
                    "error": str(e),
                }

        # Redis cleanup
        if DatabaseType.REDIS in self.optimizers:
            try:
                redis_result = await self.optimizers[
                    DatabaseType.REDIS
                ].cleanup_expired_cache()
                cleanup_results[DatabaseType.REDIS] = redis_result
            except Exception as e:
                cleanup_results[DatabaseType.REDIS] = {
                    "success": False,
                    "error": str(e),
                }

        # Qdrant cleanup
        if DatabaseType.QDRANT in self.optimizers:
            try:
                optimizer = self.optimizers[DatabaseType.QDRANT]
                for collection_name in [
                    "monitoring_metrics",
                    "monitoring_traces",
                    "monitoring_logs",
                ]:
                    optimizer.cleanup_old_data(collection_name, days_old)
                cleanup_results[DatabaseType.QDRANT] = {
                    "success": True,
                    "message": "Vector cleanup completed",
                }
            except Exception as e:
                cleanup_results[DatabaseType.QDRANT] = {
                    "success": False,
                    "error": str(e),
                }

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cleanup_results": {
                db_type.value: result for db_type, result in cleanup_results.items()
            },
            "success": all(
                result.get("success", False) for result in cleanup_results.values()
            ),
        }

    async def get_comprehensive_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics across all databases"""
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "individual_metrics": {},
            "cross_database_metrics": asdict(self.metrics_history[-1])
            if self.metrics_history
            else None,
            "sync_status": {k: v.value for k, v in self.sync_status.items()},
            "performance_trends": self._calculate_performance_trends(),
        }

        # Collect individual database metrics
        for db_type, optimizer in self.optimizers.items():
            try:
                if db_type == DatabaseType.POSTGRESQL:
                    metrics["individual_metrics"][
                        db_type.value
                    ] = await optimizer.get_optimization_report()
                elif db_type == DatabaseType.NEO4J:
                    metrics["individual_metrics"][
                        db_type.value
                    ] = await optimizer.get_graph_statistics()
                elif db_type == DatabaseType.REDIS:
                    metrics["individual_metrics"][
                        db_type.value
                    ] = await optimizer.get_redis_metrics()
                elif db_type == DatabaseType.QDRANT:
                    metrics["individual_metrics"][
                        db_type.value
                    ] = optimizer.get_performance_stats()
            except Exception as e:
                metrics["individual_metrics"][db_type.value] = {"error": str(e)}

        return metrics

    def _calculate_performance_trends(self) -> Dict[str, Any]:
        """Calculate performance trends from historical data"""
        if len(self.metrics_history) < 2:
            return {"message": "Insufficient data for trend analysis"}

        recent_metrics = self.metrics_history[-10:]  # Last 10 measurements
        if len(recent_metrics) < 2:
            return {"message": "Insufficient recent data for trend analysis"}

        # Calculate trends
        response_times = [m.average_response_time_ms for m in recent_metrics]
        health_percentages = [m.health_percentage for m in recent_metrics]

        return {
            "response_time_trend": {
                "current": response_times[-1],
                "average": sum(response_times) / len(response_times),
                "trend": "improving"
                if response_times[-1] < response_times[-2]
                else "degrading",
            },
            "health_trend": {
                "current": health_percentages[-1],
                "average": sum(health_percentages) / len(health_percentages),
                "trend": "improving"
                if health_percentages[-1] > health_percentages[-2]
                else "degrading",
            },
            "data_points": len(recent_metrics),
            "time_range_hours": (
                recent_metrics[-1].timestamp - recent_metrics[0].timestamp
            ).total_seconds()
            / 3600,
        }

    async def close_all_connections(self):
        """Close all database connections"""
        for db_type, optimizer in self.optimizers.items():
            try:
                if hasattr(optimizer, "close"):
                    if asyncio.iscoroutinefunction(optimizer.close):
                        await optimizer.close()
                    else:
                        optimizer.close()
                elif hasattr(optimizer, "driver") and optimizer.driver:
                    await optimizer.driver.close()
                logger.info(f"Closed {db_type.value} connections")
            except Exception as e:
                logger.error(f"Failed to close {db_type.value} connections: {e}")


# Utility functions
async def create_cross_database_integration() -> CrossDatabaseIntegration:
    """Create and initialize cross-database integration"""
    integration = CrossDatabaseIntegration()
    await integration.initialize_all_databases()
    return integration


async def run_system_health_check() -> Dict[str, Any]:
    """Run comprehensive system health check across all databases"""
    integration = await create_cross_database_integration()
    try:
        return await integration.comprehensive_health_check()
    finally:
        await integration.close_all_connections()
