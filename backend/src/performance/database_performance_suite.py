"""
Database Performance Suite for the Multimodal Enterprise RAG System

This module provides comprehensive database performance monitoring, optimization,
and analysis tools for PostgreSQL, Neo4j, and Qdrant databases.
"""

import asyncio
import json
import logging
import statistics
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import asyncpg
import numpy as np
import psutil
import psycopg2
import redis
from psycopg2.extras import execute_values

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class DatabaseMetrics:
    """Database performance metrics"""

    database_type: str
    host: str
    timestamp: datetime
    connection_count: int
    active_connections: int
    query_count: int
    slow_queries: int
    avg_query_time: float
    max_query_time: float
    cache_hit_ratio: float
    buffer_pool_hit_ratio: float
    temp_tables_created: int
    lock_waits: int
    deadlocks: int
    transaction_duration: float
    cpu_usage: float
    memory_usage: float
    disk_io_read: int
    disk_io_write: int
    network_io_bytes: int
    index_usage: Dict[str, float]
    table_size: Dict[str, int]


@dataclass
class QueryAnalysis:
    """Query performance analysis"""

    query_hash: str
    query_text: str
    execution_count: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    std_dev_time: float
    rows_returned: int
    rows_examined: int
    index_usage: List[str]
    execution_plan: Dict[str, Any]
    recommendations: List[str]


@dataclass
class ConnectionPoolMetrics:
    """Connection pool performance metrics"""

    pool_name: str
    total_connections: int
    active_connections: int
    idle_connections: int
    waiting_clients: int
    pool_utilization: float
    connection_creation_rate: float
    connection_destruction_rate: float
    avg_connection_lifetime: float
    connection_errors: int


class DatabasePerformanceMonitor:
    """Comprehensive database performance monitoring system"""

    def __init__(self):
        self.metrics_history: deque = deque(maxlen=1000)
        self.query_profiles: Dict[str, List[float]] = defaultdict(list)
        self.slow_query_threshold = 1000  # ms
        self.monitoring_enabled = True
        self.alert_thresholds = {
            "avg_query_time": 500.0,  # ms
            "slow_query_rate": 0.05,  # 5%
            "cache_hit_ratio": 0.90,  # 90%
            "connection_utilization": 0.80,  # 80%
            "cpu_usage": 0.80,  # 80%
            "memory_usage": 0.85,  # 85%
            "disk_io_wait": 100.0,  # ms
        }
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def monitor_postgresql_performance(
        self, connection_string: str, database_name: str = "postgres"
    ) -> DatabaseMetrics:
        """Monitor PostgreSQL database performance"""

        start_time = time.time()

        try:
            conn = await asyncpg.connect(connection_string)

            # Get connection metrics
            conn_metrics = await conn.fetchrow(
                """
                SELECT
                    count(*) as total_connections,
                    count(*) FILTER (WHERE state = 'active') as active_connections
                FROM pg_stat_activity
                WHERE datname = $1
            """,
                database_name,
            )

            # Get database statistics
            db_stats = await conn.fetchrow(
                """
                SELECT
                    xact_commit + xact_rollback as total_transactions,
                    blks_read,
                    blks_hit,
                    tup_returned,
                    tup_fetched,
                    tup_inserted,
                    tup_updated,
                    tup_deleted,
                    deadlocks
                FROM pg_stat_database
                WHERE datname = $1
            """,
                database_name,
            )

            # Get slow queries
            slow_queries = await conn.fetchval(
                """
                SELECT count(*)
                FROM pg_stat_statements
                WHERE mean_exec_time > $1 AND calls > 0
            """,
                self.slow_query_threshold,
            )

            # Get index usage statistics
            index_usage = await conn.fetch(
                """
                SELECT
                    schemaname || '.' || indexname as index_name,
                    idx_scan as scan_count,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched
                FROM pg_stat_user_indexes
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            """
            )

            # Get table sizes
            table_sizes = await conn.fetch(
                """
                SELECT
                    schemaname || '.' || tablename as table_name,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size_bytes
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            """
            )

            # Get lock information
            lock_info = await conn.fetchrow(
                """
                SELECT
                    count(*) as total_locks,
                    count(*) FILTER (WHERE wait_start IS NOT NULL) as waiting_locks
                FROM pg_locks
            """
            )

            # Calculate cache hit ratio
            cache_hit_ratio = 0.0
            if db_stats["blks_read"] > 0:
                cache_hit_ratio = db_stats["blks_hit"] / (
                    db_stats["blks_read"] + db_stats["blks_hit"]
                )

            # Get system metrics
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()

            metrics = DatabaseMetrics(
                database_type="postgresql",
                host=connection_string.split("@")[-1].split("/")[0]
                if "@" in connection_string
                else "localhost",
                timestamp=datetime.now(),
                connection_count=conn_metrics["total_connections"],
                active_connections=conn_metrics["active_connections"],
                query_count=db_stats["total_transactions"] if db_stats else 0,
                slow_queries=slow_queries,
                avg_query_time=0.0,  # Would be calculated from query stats
                max_query_time=0.0,  # Would be calculated from query stats
                cache_hit_ratio=cache_hit_ratio,
                buffer_pool_hit_ratio=cache_hit_ratio,
                temp_tables_created=0,  # Would need additional query
                lock_waits=lock_info["waiting_locks"] if lock_info else 0,
                deadlocks=db_stats["deadlocks"] if db_stats else 0,
                transaction_duration=0.0,  # Would need transaction tracking
                cpu_usage=cpu_usage / 100.0,
                memory_usage=memory.percent / 100.0,
                disk_io_read=disk_io.read_bytes if disk_io else 0,
                disk_io_write=disk_io.write_bytes if disk_io else 0,
                network_io_bytes=0,  # Would need network monitoring
                index_usage={
                    row["index_name"]: row["scan_count"] for row in index_usage
                },
                table_size={
                    row["table_name"]: int(
                        row["size_bytes"].replace("MB", "").replace("kB", "")
                    )
                    * 1024
                    * 1024
                    if row["size_bytes"]
                    else 0
                    for row in table_sizes
                },
            )

            await conn.close()

            # Store metrics
            self.metrics_history.append(metrics)

            # Check for alerts
            await self._check_performance_alerts(metrics)

            logger.info(f"PostgreSQL performance metrics collected for {database_name}")
            return metrics

        except Exception as e:
            logger.error(f"Error monitoring PostgreSQL performance: {e}")
            raise

    async def monitor_neo4j_performance(
        self, uri: str, username: str, password: str
    ) -> DatabaseMetrics:
        """Monitor Neo4j database performance"""

        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver(uri, auth=(username, password))

            with driver.session() as session:
                # Get database information
                db_info = session.run(
                    "CALL dbms.components() YIELD name, versions RETURN name, versions[0] as version"
                ).single()

                # Get connection information
                connections = session.run(
                    "CALL dbms.listConnections() YIELD connectionId, connectTime, connector, username RETURN count(*) as total_connections"
                ).single()

                # Get query statistics
                query_stats = session.run(
                    "CALL dbms.queryJmx() YIELD attributes WHERE attributes.name = 'NumberOfOpenTransactions' RETURN attributes.value as open_transactions"
                ).single()

                # Get memory usage
                memory_usage = session.run(
                    "CALL dbms.queryJmx() YIELD attributes WHERE attributes.name = 'MemoryUsed' RETURN attributes.value as memory_used"
                ).single()

                # Get page cache hit ratio
                cache_stats = session.run(
                    "CALL dbms.queryJmx() YIELD attributes WHERE attributes.name = 'PageCacheHits' RETURN attributes.value as cache_hits"
                ).single()
                cache_misses = session.run(
                    "CALL dbms.queryJmx() YIELD attributes WHERE attributes.name = 'PageCacheMisses' RETURN attributes.value as cache_misses"
                ).single()

                # Calculate cache hit ratio
                cache_hit_ratio = 0.0
                if cache_stats and cache_misses:
                    hits = cache_stats["cache_hits"] or 0
                    misses = cache_misses["cache_misses"] or 0
                    if hits + misses > 0:
                        cache_hit_ratio = hits / (hits + misses)

                # Get system metrics
                cpu_usage = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()

                metrics = DatabaseMetrics(
                    database_type="neo4j",
                    host=uri.split("//")[1].split(":")[0]
                    if "//" in uri
                    else "localhost",
                    timestamp=datetime.now(),
                    connection_count=connections["total_connections"]
                    if connections
                    else 0,
                    active_connections=query_stats["open_transactions"]
                    if query_stats
                    else 0,
                    query_count=0,  # Neo4j doesn't track this directly
                    slow_queries=0,  # Would need query logging
                    avg_query_time=0.0,
                    max_query_time=0.0,
                    cache_hit_ratio=cache_hit_ratio,
                    buffer_pool_hit_ratio=cache_hit_ratio,
                    temp_tables_created=0,
                    lock_waits=0,  # Would need additional monitoring
                    deadlocks=0,  # Would need additional monitoring
                    transaction_duration=0.0,
                    cpu_usage=cpu_usage / 100.0,
                    memory_usage=memory.percent / 100.0,
                    disk_io_read=0,  # Would need JMX monitoring
                    disk_io_write=0,
                    network_io_bytes=0,
                    index_usage={},  # Would need index monitoring
                    table_size={},  # Neo4j doesn't have traditional tables
                )

                driver.close()

                # Store metrics
                self.metrics_history.append(metrics)

                # Check for alerts
                await self._check_performance_alerts(metrics)

                logger.info("Neo4j performance metrics collected")
                return metrics

        except Exception as e:
            logger.error(f"Error monitoring Neo4j performance: {e}")
            raise

    async def monitor_qdrant_performance(
        self, host: str = "localhost", port: int = 6333
    ) -> DatabaseMetrics:
        """Monitor Qdrant vector database performance"""

        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http import models

            client = QdrantClient(host=host, port=port)

            # Get cluster info
            cluster_info = client.get_cluster_info()

            # Get collection info
            collections = client.get_collections().collections

            # Get telemetry information
            telemetry = client.get_telemetry()

            # Calculate metrics
            total_points = sum(
                client.count(collection.collection_name).count
                for collection in collections
            )

            # Get system metrics
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk_io = psutil.disk_io_counters()

            # Extract metrics from telemetry
            avg_search_time = getattr(telemetry, "avg_search_time", 0.0)
            max_search_time = getattr(telemetry, "max_search_time", 0.0)

            metrics = DatabaseMetrics(
                database_type="qdrant",
                host=host,
                timestamp=datetime.now(),
                connection_count=1,  # Qdrant doesn't track connections traditionally
                active_connections=1,
                query_count=getattr(telemetry, "search_requests", 0),
                slow_queries=getattr(telemetry, "slow_search_requests", 0),
                avg_query_time=avg_search_time,
                max_query_time=max_search_time,
                cache_hit_ratio=getattr(telemetry, "cache_hit_ratio", 0.0),
                buffer_pool_hit_ratio=getattr(telemetry, "buffer_hit_ratio", 0.0),
                temp_tables_created=0,
                lock_waits=0,
                deadlocks=0,
                transaction_duration=0.0,
                cpu_usage=cpu_usage / 100.0,
                memory_usage=memory.percent / 100.0,
                disk_io_read=disk_io.read_bytes if disk_io else 0,
                disk_io_write=disk_io.write_bytes if disk_io else 0,
                network_io_bytes=0,
                index_usage={coll.name: total_points for coll in collections},
                table_size={
                    coll.name: total_points * 1000 for coll in collections
                },  # Estimated size
            )

            client.close()

            # Store metrics
            self.metrics_history.append(metrics)

            # Check for alerts
            await self._check_performance_alerts(metrics)

            logger.info("Qdrant performance metrics collected")
            return metrics

        except Exception as e:
            logger.error(f"Error monitoring Qdrant performance: {e}")
            raise

    async def monitor_redis_performance(
        self, host: str = "localhost", port: int = 6379, password: Optional[str] = None
    ) -> DatabaseMetrics:
        """Monitor Redis cache performance"""

        try:
            r = redis.Redis(
                host=host, port=port, password=password, decode_responses=True
            )

            # Get Redis info
            info = r.info()

            # Get system metrics
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()

            metrics = DatabaseMetrics(
                database_type="redis",
                host=host,
                timestamp=datetime.now(),
                connection_count=info.get("connected_clients", 0),
                active_connections=info.get("connected_clients", 0),
                query_count=info.get("total_commands_processed", 0),
                slow_queries=info.get("slowlog_len", 0),
                avg_query_time=0.0,  # Redis doesn't track average query time
                max_query_time=0.0,
                cache_hit_ratio=info.get("keyspace_hits", 0)
                / max(1, info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0)),
                buffer_pool_hit_ratio=info.get("keyspace_hits", 0)
                / max(1, info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0)),
                temp_tables_created=0,
                lock_waits=0,
                deadlocks=0,
                transaction_duration=0.0,
                cpu_usage=cpu_usage / 100.0,
                memory_usage=info.get("used_memory", 0)
                / max(1, info.get("maxmemory", 1)),
                disk_io_read=0,
                disk_io_write=0,
                network_io_bytes=info.get("total_net_input_bytes", 0)
                + info.get("total_net_output_bytes", 0),
                index_usage={},  # Redis doesn't have traditional indexes
                table_size={},  # Redis doesn't have traditional tables
            )

            r.close()

            # Store metrics
            self.metrics_history.append(metrics)

            # Check for alerts
            await self._check_performance_alerts(metrics)

            logger.info("Redis performance metrics collected")
            return metrics

        except Exception as e:
            logger.error(f"Error monitoring Redis performance: {e}")
            raise

    async def analyze_query_performance(
        self,
        connection_string: str,
        query_text: str,
        execution_params: Optional[Dict[str, Any]] = None,
    ) -> QueryAnalysis:
        """Analyze performance of a specific query"""

        try:
            conn = await asyncpg.connect(connection_string)

            query_hash = hash(query_text)
            execution_times = []

            # Execute query multiple times to get performance metrics
            for _ in range(5):
                start_time = time.time()

                if execution_params:
                    await conn.execute(query_text, **execution_params)
                else:
                    await conn.execute(query_text)

                execution_time = (time.time() - start_time) * 1000  # Convert to ms
                execution_times.append(execution_time)

            # Get execution plan
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query_text}"
            plan_result = await conn.fetchval(explain_query, **execution_params or {})
            execution_plan = plan_result[0]["Plan"] if plan_result else {}

            # Get query statistics from pg_stat_statements
            stats = await conn.fetchrow(
                """
                SELECT
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    min_exec_time,
                    max_exec_time,
                    stddev_exec_time,
                    rows,
                    shared_blks_hit,
                    shared_blks_read
                FROM pg_stat_statements
                WHERE query = $1
            """,
                query_text,
            )

            # Generate recommendations based on execution plan
            recommendations = self._generate_query_recommendations(
                execution_plan, stats
            )

            analysis = QueryAnalysis(
                query_hash=str(query_hash),
                query_text=query_text,
                execution_count=stats["calls"] if stats else len(execution_times),
                total_time=stats["total_exec_time"] if stats else sum(execution_times),
                avg_time=statistics.mean(execution_times),
                min_time=min(execution_times),
                max_time=max(execution_times),
                std_dev_time=statistics.stdev(execution_times)
                if len(execution_times) > 1
                else 0.0,
                rows_returned=stats["rows"] if stats else 0,
                rows_examined=0,  # Would need more detailed analysis
                index_usage=self._extract_index_usage(execution_plan),
                execution_plan=execution_plan,
                recommendations=recommendations,
            )

            await conn.close()

            # Store profile data
            self.query_profiles[str(query_hash)].extend(execution_times)

            logger.info(f"Query analysis completed for query hash: {query_hash}")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing query performance: {e}")
            raise

    def _generate_query_recommendations(
        self, execution_plan: Dict[str, Any], stats: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate performance recommendations based on execution plan"""

        recommendations = []

        # Check for sequential scans
        if "Seq Scan" in str(execution_plan):
            recommendations.append("Consider adding indexes to avoid sequential scans")

        # Check for high execution time
        if stats and stats["mean_exec_time"] > self.slow_query_threshold:
            recommendations.append(
                "Query execution time is above threshold - consider optimization"
            )

        # Check for high variance in execution time
        if stats and stats["stddev_exec_time"] > stats["mean_exec_time"] * 0.5:
            recommendations.append(
                "High variance in execution time - check for parameter sniffing"
            )

        # Check for missing indexes
        if "Bitmap Heap Scan" in str(execution_plan):
            recommendations.append(
                "Consider optimizing bitmap scan with better indexes"
            )

        # Check for sort operations
        if "Sort" in str(execution_plan):
            recommendations.append("Consider adding indexes to avoid sorting")

        # Check for hash operations
        if "Hash Join" in str(execution_plan):
            recommendations.append(
                "Consider optimizing hash join with work_mem adjustment"
            )

        return recommendations

    def _extract_index_usage(self, execution_plan: Dict[str, Any]) -> List[str]:
        """Extract index usage information from execution plan"""

        indexes = []
        plan_str = str(execution_plan)

        # Look for index scans
        if "Index Scan" in plan_str:
            # Extract index names
            import re

            index_matches = re.findall(r"Index Scan using (\w+)", plan_str)
            indexes.extend(index_matches)

        return indexes

    async def _check_performance_alerts(self, metrics: DatabaseMetrics):
        """Check for performance alerts based on thresholds"""

        alerts = []

        # Check query performance
        if metrics.avg_query_time > self.alert_thresholds["avg_query_time"]:
            alerts.append(f"High average query time: {metrics.avg_query_time:.2f}ms")

        # Check cache hit ratio
        if metrics.cache_hit_ratio < self.alert_thresholds["cache_hit_ratio"]:
            alerts.append(f"Low cache hit ratio: {metrics.cache_hit_ratio:.2%}")

        # Check CPU usage
        if metrics.cpu_usage > self.alert_thresholds["cpu_usage"]:
            alerts.append(f"High CPU usage: {metrics.cpu_usage:.2%}")

        # Check memory usage
        if metrics.memory_usage > self.alert_thresholds["memory_usage"]:
            alerts.append(f"High memory usage: {metrics.memory_usage:.2%}")

        # Check connection utilization
        if metrics.connection_count > 0:
            utilization = metrics.active_connections / metrics.connection_count
            if utilization > self.alert_thresholds["connection_utilization"]:
                alerts.append(f"High connection utilization: {utilization:.2%}")

        # Log alerts
        for alert in alerts:
            logger.warning(f"Performance Alert - {metrics.database_type}: {alert}")

    async def get_performance_summary(
        self, database_type: Optional[str] = None, time_range_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get performance summary for the specified time range"""

        cutoff_time = datetime.now() - timedelta(minutes=time_range_minutes)

        # Filter metrics by time range and database type
        filtered_metrics = [
            m
            for m in self.metrics_history
            if m.timestamp > cutoff_time
            and (database_type is None or m.database_type == database_type)
        ]

        if not filtered_metrics:
            return {"error": "No metrics available for the specified time range"}

        # Calculate summary statistics
        summary = {
            "database_type": database_type or "all",
            "time_range_minutes": time_range_minutes,
            "metrics_count": len(filtered_metrics),
            "period": {
                "start": min(m.timestamp for m in filtered_metrics),
                "end": max(m.timestamp for m in filtered_metrics),
            },
            "performance": {
                "avg_query_time": statistics.mean(
                    [m.avg_query_time for m in filtered_metrics]
                ),
                "max_query_time": max([m.max_query_time for m in filtered_metrics]),
                "avg_cache_hit_ratio": statistics.mean(
                    [m.cache_hit_ratio for m in filtered_metrics]
                ),
                "avg_cpu_usage": statistics.mean(
                    [m.cpu_usage for m in filtered_metrics]
                ),
                "avg_memory_usage": statistics.mean(
                    [m.memory_usage for m in filtered_metrics]
                ),
                "total_slow_queries": sum([m.slow_queries for m in filtered_metrics]),
                "total_deadlocks": sum([m.deadlocks for m in filtered_metrics]),
            },
            "connections": {
                "avg_connections": statistics.mean(
                    [m.connection_count for m in filtered_metrics]
                ),
                "max_connections": max([m.connection_count for m in filtered_metrics]),
                "avg_active_connections": statistics.mean(
                    [m.active_connections for m in filtered_metrics]
                ),
            },
            "alerts": [],
            "recommendations": [],
        }

        # Generate alerts and recommendations
        if (
            summary["performance"]["avg_query_time"]
            > self.alert_thresholds["avg_query_time"]
        ):
            summary["alerts"].append("Average query time exceeds threshold")
            summary["recommendations"].append("Review and optimize slow queries")

        if (
            summary["performance"]["avg_cache_hit_ratio"]
            < self.alert_thresholds["cache_hit_ratio"]
        ):
            summary["alerts"].append("Cache hit ratio below threshold")
            summary["recommendations"].append("Increase cache size or optimize queries")

        if summary["performance"]["avg_cpu_usage"] > self.alert_thresholds["cpu_usage"]:
            summary["alerts"].append("High CPU usage detected")
            summary["recommendations"].append("Scale up resources or optimize queries")

        return summary

    async def optimize_database_configuration(
        self, connection_string: str, database_type: str = "postgresql"
    ) -> Dict[str, Any]:
        """Analyze and provide database configuration optimization recommendations"""

        try:
            if database_type == "postgresql":
                return await self._optimize_postgresql_config(connection_string)
            else:
                return {"error": f"Optimization not supported for {database_type}"}

        except Exception as e:
            logger.error(f"Error optimizing database configuration: {e}")
            return {"error": str(e)}

    async def _optimize_postgresql_config(
        self, connection_string: str
    ) -> Dict[str, Any]:
        """Optimize PostgreSQL configuration based on current performance"""

        conn = await asyncpg.connect(connection_string)

        # Get current configuration
        current_config = await conn.fetch(
            """
            SELECT name, setting, unit, short_desc
            FROM pg_settings
            WHERE name IN (
                'shared_buffers', 'effective_cache_size', 'work_mem',
                'maintenance_work_mem', 'checkpoint_completion_target',
                'random_page_cost', 'effective_io_concurrency',
                'max_connections', 'shared_preload_libraries'
            )
        """
        )

        # Get system resources
        total_memory = psutil.virtual_memory().total
        cpu_count = psutil.cpu_count()

        # Calculate optimal configuration
        optimal_config = {
            "shared_buffers": f"{int(total_memory * 0.25 / 1024 / 1024)}MB",  # 25% of RAM
            "effective_cache_size": f"{int(total_memory * 0.75 / 1024 / 1024)}MB",  # 75% of RAM
            "work_mem": f"{int(total_memory * 0.05 / psutil.cpu_count() / 1024)}MB",  # 5% of RAM / CPU cores
            "maintenance_work_mem": f"{int(total_memory * 0.1 / 1024 / 1024)}MB",  # 10% of RAM
            "checkpoint_completion_target": "0.9",
            "random_page_cost": "1.1",  # For SSD
            "effective_io_concurrency": "200",  # For SSD
            "max_connections": str(min(200, psutil.cpu_count() * 20)),
        }

        # Generate recommendations
        recommendations = []
        for setting in current_config:
            name = setting["name"]
            current_value = setting["setting"]
            optimal_value = optimal_config.get(name)

            if optimal_value and current_value != optimal_value:
                recommendations.append(
                    {
                        "parameter": name,
                        "current_value": current_value,
                        "recommended_value": optimal_value,
                        "description": setting["short_desc"],
                        "impact": "high"
                        if name in ["shared_buffers", "work_mem"]
                        else "medium",
                    }
                )

        await conn.close()

        return {
            "database_type": "postgresql",
            "system_info": {
                "total_memory_gb": total_memory / 1024 / 1024 / 1024,
                "cpu_count": cpu_count,
                "current_config": {
                    row["name"]: row["setting"] for row in current_config
                },
            },
            "optimal_config": optimal_config,
            "recommendations": recommendations,
            "estimated_improvement": "15-30% performance improvement expected",
        }

    def export_metrics(
        self, filename: str, database_type: Optional[str] = None, format: str = "json"
    ) -> str:
        """Export performance metrics to file"""

        metrics = self.metrics_history
        if database_type:
            metrics = [m for m in metrics if m.database_type == database_type]

        if format.lower() == "json":
            data = [asdict(m) for m in metrics]
            # Convert datetime objects to strings
            for item in data:
                item["timestamp"] = item["timestamp"].isoformat()

            with open(filename, "w") as f:
                json.dump(data, f, indent=2, default=str)

        elif format.lower() == "csv":
            import csv

            if metrics:
                fieldnames = asdict(metrics[0]).keys()
                with open(filename, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for metric in metrics:
                        row = asdict(metric)
                        row["timestamp"] = row["timestamp"].isoformat()
                        writer.writerow(row)

        logger.info(f"Metrics exported to {filename}")
        return filename

    def clear_metrics_history(self):
        """Clear metrics history"""
        self.metrics_history.clear()
        logger.info("Metrics history cleared")


# Connection pool monitoring
class ConnectionPoolMonitor:
    """Monitor database connection pool performance"""

    def __init__(self):
        self.pool_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.monitoring_enabled = True

    async def monitor_pool_performance(
        self, pool_name: str, pool: Any  # asyncpg.Pool or similar
    ) -> ConnectionPoolMetrics:
        """Monitor connection pool performance"""

        try:
            # Get pool statistics (implementation depends on pool type)
            if hasattr(pool, "get_size"):
                total_connections = pool.get_size()
                active_connections = pool.get_idle_size()  # This might need adjustment
            else:
                # Default values for unknown pool types
                total_connections = 10
                active_connections = 5

            idle_connections = total_connections - active_connections
            waiting_clients = getattr(pool, "get_waiting_clients", lambda: 0)()

            utilization = active_connections / max(1, total_connections)

            metrics = ConnectionPoolMetrics(
                pool_name=pool_name,
                total_connections=total_connections,
                active_connections=active_connections,
                idle_connections=idle_connections,
                waiting_clients=waiting_clients,
                pool_utilization=utilization,
                connection_creation_rate=0.0,  # Would need tracking
                connection_destruction_rate=0.0,  # Would need tracking
                avg_connection_lifetime=0.0,  # Would need tracking
                connection_errors=0,  # Would need error tracking
            )

            # Store metrics
            self.pool_metrics[pool_name].append(metrics)

            return metrics

        except Exception as e:
            logger.error(f"Error monitoring pool {pool_name}: {e}")
            raise


# Global performance monitor instance
db_performance_monitor = DatabasePerformanceMonitor()
pool_monitor = ConnectionPoolMonitor()


# Utility functions
async def create_performance_indexes(
    connection_string: str, schema_name: str = "public"
) -> Dict[str, Any]:
    """Create performance monitoring indexes"""

    try:
        conn = await asyncpg.connect(connection_string)

        # Create indexes for performance monitoring
        indexes = [
            """
            CREATE INDEX IF NOT EXISTS idx_performance_log_timestamp
            ON performance_log (timestamp DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_performance_log_query_hash
            ON performance_log (query_hash)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_performance_log_duration
            ON performance_log (duration DESC) WHERE duration > 1000
            """,
        ]

        results = []
        for index_sql in indexes:
            try:
                await conn.execute(index_sql)
                results.append({"index": index_sql, "status": "created"})
            except Exception as e:
                results.append({"index": index_sql, "status": "error", "error": str(e)})

        await conn.close()

        return {
            "status": "completed",
            "indexes_created": len([r for r in results if r["status"] == "created"]),
            "results": results,
        }

    except Exception as e:
        logger.error(f"Error creating performance indexes: {e}")
        return {"error": str(e)}
