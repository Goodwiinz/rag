#!/usr/bin/env python3
"""
Comprehensive Database Health Check System for Multimodal Enterprise RAG System

This script provides detailed health monitoring for all four databases:
- PostgreSQL
- Neo4j
- Qdrant
- Redis
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import asyncpg
import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from neo4j import AsyncGraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    print("Warning: Neo4j driver not available. Install with: pip install neo4j")

try:
    from qdrant_client import QdrantClient
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    print("Warning: Qdrant client not available. Install with: pip install qdrant-client")

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("Warning: Redis client not available. Install with: pip install redis")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configurations
POSTGRES_CONFIG = {
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


class HealthCheckResult:
    """Health check result container"""

    def __init__(self, service: str, status: str, message: str,
                 metrics: Dict[str, Any] = None, response_time: float = 0):
        self.service = service
        self.status = status  # 'healthy', 'warning', 'error'
        self.message = message
        self.metrics = metrics or {}
        self.response_time = response_time
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'service': self.service,
            'status': self.status,
            'message': self.message,
            'metrics': self.metrics,
            'response_time_ms': round(self.response_time * 1000, 2),
            'timestamp': self.timestamp.isoformat()
        }


class DatabaseHealthChecker:
    """Comprehensive database health checker"""

    def __init__(self):
        self.results: List[HealthCheckResult] = []

    async def check_all_databases(self) -> Dict[str, Any]:
        """Run health checks on all databases"""
        logger.info("Starting comprehensive database health checks...")

        self.results = []

        # PostgreSQL health check
        pg_result = await self._check_postgresql()
        self.results.append(pg_result)

        # Neo4j health check
        if NEO4J_AVAILABLE:
            neo4j_result = await self._check_neo4j()
            self.results.append(neo4j_result)
        else:
            self.results.append(HealthCheckResult(
                "Neo4j", "error", "Neo4j driver not available"
            ))

        # Qdrant health check
        if QDRANT_AVAILABLE:
            qdrant_result = await self._check_qdrant()
            self.results.append(qdrant_result)
        else:
            self.results.append(HealthCheckResult(
                "Qdrant", "error", "Qdrant client not available"
            ))

        # Redis health check
        if REDIS_AVAILABLE:
            redis_result = await self._check_redis()
            self.results.append(redis_result)
        else:
            self.results.append(HealthCheckResult(
                "Redis", "error", "Redis client not available"
            ))

        return self._generate_summary()

    async def _check_postgresql(self) -> HealthCheckResult:
        """Check PostgreSQL database health"""
        start_time = time.time()

        try:
            # Test connection
            conn = await asyncpg.connect(**POSTGRES_CONFIG)

            # Basic connectivity test
            await conn.fetchval("SELECT 1")

            # Get database statistics
            metrics = {}

            # Database size
            db_size = await conn.fetchval("""
                SELECT pg_size_pretty(pg_database_size(current_database())) as size
            """)
            metrics['database_size'] = db_size

            # Table counts
            table_count = await conn.fetchval("""
                SELECT count(*) FROM information_schema.tables
                WHERE table_schema = 'public'
            """)
            metrics['table_count'] = table_count

            # Active connections
            active_connections = await conn.fetchval("""
                SELECT count(*) FROM pg_stat_activity
                WHERE datname = current_database() AND state = 'active'
            """)
            metrics['active_connections'] = active_connections

            # Recent queries (last 5 minutes)
            recent_queries = await conn.fetchval("""
                SELECT count(*) FROM pg_stat_statements
                WHERE calls > 0 AND mean_exec_time > 0
            """)
            metrics['recent_queries'] = recent_queries or 0

            # Check for slow queries
            slow_queries = await conn.fetchval("""
                SELECT count(*) FROM pg_stat_statements
                WHERE mean_exec_time > 1000
            """)
            metrics['slow_queries'] = slow_queries or 0

            await conn.close()

            response_time = time.time() - start_time

            # Determine health status
            if slow_queries > 10:
                status = "warning"
                message = f"Database healthy but {slow_queries} slow queries detected"
            elif active_connections > 80:
                status = "warning"
                message = f"Database healthy but high connection count: {active_connections}"
            else:
                status = "healthy"
                message = "Database operating normally"

            return HealthCheckResult("PostgreSQL", status, message, metrics, response_time)

        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult("PostgreSQL", "error", str(e), {}, response_time)

    async def _check_neo4j(self) -> HealthCheckResult:
        """Check Neo4j database health"""
        start_time = time.time()

        try:
            driver = AsyncGraphDatabase.driver(**NEO4J_CONFIG)

            async with driver.session() as session:
                # Basic connectivity test
                result = await session.run("RETURN 1 as test")
                record = await result.single()

                # Get database statistics
                metrics = {}

                # Node counts by type
                node_result = await session.run("""
                    MATCH (n)
                    RETURN labels(n) as labels, count(n) as count
                    ORDER BY count DESC
                """)
                node_counts = {}
                async for record in node_result:
                    label = record["labels"][0] if record["labels"] else "Unknown"
                    node_counts[f"{label}_nodes"] = record["count"]
                metrics.update(node_counts)

                # Relationship counts by type
                rel_result = await session.run("""
                    MATCH ()-[r]->()
                    RETURN type(r) as type, count(r) as count
                    ORDER BY count DESC
                """)
                rel_counts = {}
                async for record in rel_result:
                    rel_type = record["type"] or "UNKNOWN"
                    rel_counts[f"{rel_type}_relationships"] = record["count"]
                metrics.update(rel_counts)

                # Index information
                index_result = await session.run("SHOW INDEXES")
                index_count = 0
                async for record in index_result:
                    index_count += 1
                metrics['indexes'] = index_count

                # Constraint information
                constraint_result = await session.run("SHOW CONSTRAINTS")
                constraint_count = 0
                async for record in constraint_result:
                    constraint_count += 1
                metrics['constraints'] = constraint_count

            await driver.close()

            response_time = time.time() - start_time

            # Determine health status
            total_nodes = sum(v for k, v in node_counts.items() if k.endswith('_nodes'))
            total_rels = sum(v for k, v in rel_counts.items() if k.endswith('_relationships'))

            if total_nodes == 0:
                status = "warning"
                message = "Graph database connected but no data found"
            else:
                status = "healthy"
                message = f"Graph database healthy with {total_nodes} nodes and {total_rels} relationships"

            return HealthCheckResult("Neo4j", status, message, metrics, response_time)

        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult("Neo4j", "error", str(e), {}, response_time)

    async def _check_qdrant(self) -> HealthCheckResult:
        """Check Qdrant vector database health"""
        start_time = time.time()

        try:
            client = QdrantClient(**QDRANT_CONFIG)

            # Basic health check
            health_response = client.http.models.api.http.Health()

            # Get cluster information
            metrics = {}

            # Collection information
            collections = client.get_collections()
            collection_names = []
            collection_sizes = []

            for collection in collections.collections:
                collection_names.append(collection.name)
                try:
                    collection_info = client.get_collection(collection.name)
                    collection_sizes.append(collection_info.points_count)
                except:
                    collection_sizes.append(0)

            metrics['collections'] = len(collection_names)
            metrics['collection_names'] = collection_names
            metrics['total_vectors'] = sum(collection_sizes)

            # Performance metrics if available
            try:
                cluster_info = client.get_cluster_info()
                metrics['cluster_status'] = 'healthy'
            except:
                metrics['cluster_status'] = 'standalone'

            response_time = time.time() - start_time

            # Determine health status
            if metrics['total_vectors'] == 0:
                status = "warning"
                message = "Vector database healthy but no vectors found"
            else:
                status = "healthy"
                message = f"Vector database healthy with {metrics['total_vectors']} vectors across {metrics['collections']} collections"

            return HealthCheckResult("Qdrant", status, message, metrics, response_time)

        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult("Qdrant", "error", str(e), {}, response_time)

    async def _check_redis(self) -> HealthCheckResult:
        """Check Redis cache health"""
        start_time = time.time()

        try:
            client = redis.Redis(**REDIS_CONFIG)

            # Basic connectivity test
            await client.ping()

            # Get Redis information
            info = await client.info()
            metrics = {}

            # Memory usage
            used_memory = info.get('used_memory_human', '0B')
            metrics['memory_usage'] = used_memory

            # Connected clients
            connected_clients = info.get('connected_clients', '0')
            metrics['connected_clients'] = connected_clients

            # Total keys
            key_count = await client.dbsize()
            metrics['total_keys'] = key_count

            # Hit rate
            hits = int(info.get('keyspace_hits', 0))
            misses = int(info.get('keyspace_misses', 0))
            total_requests = hits + misses
            hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0
            metrics['hit_rate_percent'] = round(hit_rate, 2)

            # Operations per second
            ops_per_sec = info.get('instantaneous_ops_per_sec', '0')
            metrics['operations_per_second'] = ops_per_sec

            # Uptime
            uptime_seconds = info.get('uptime_in_seconds', '0')
            metrics['uptime_seconds'] = uptime_seconds

            await client.close()

            response_time = time.time() - start_time

            # Determine health status
            if hit_rate < 50:
                status = "warning"
                message = f"Redis healthy but low hit rate: {hit_rate:.1f}%"
            elif int(connected_clients) > 100:
                status = "warning"
                message = f"Redis healthy but high client count: {connected_clients}"
            else:
                status = "healthy"
                message = f"Redis cache healthy with {key_count} keys and {hit_rate:.1f}% hit rate"

            return HealthCheckResult("Redis", status, message, metrics, response_time)

        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult("Redis", "error", str(e), {}, response_time)

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate overall health summary"""
        total_checks = len(self.results)
        healthy_count = sum(1 for r in self.results if r.status == 'healthy')
        warning_count = sum(1 for r in self.results if r.status == 'warning')
        error_count = sum(1 for r in self.results if r.status == 'error')

        overall_status = "healthy"
        if error_count > 0:
            overall_status = "error"
        elif warning_count > 0:
            overall_status = "warning"

        # Calculate average response time
        avg_response_time = sum(r.response_time for r in self.results) / total_checks

        summary = {
            'overall_status': overall_status,
            'total_checks': total_checks,
            'healthy_services': healthy_count,
            'warning_services': warning_count,
            'error_services': error_count,
            'average_response_time_ms': round(avg_response_time * 1000, 2),
            'timestamp': datetime.utcnow().isoformat(),
            'services': [r.to_dict() for r in self.results]
        }

        return summary

    def print_summary(self, summary: Dict[str, Any]):
        """Print formatted health summary"""
        print(f"\n{'='*60}")
        print(f"🏥 DATABASE HEALTH CHECK REPORT")
        print(f"{'='*60}")
        print(f"Overall Status: {summary['overall_status'].upper()}")
        print(f"Timestamp: {summary['timestamp']}")
        print(f"Average Response Time: {summary['average_response_time_ms']}ms")
        print(f"\nService Summary:")
        print(f"  ✅ Healthy: {summary['healthy_services']}")
        print(f"  ⚠️  Warning: {summary['warning_services']}")
        print(f"  ❌ Error: {summary['error_services']}")

        print(f"\n{'='*60}")
        print("SERVICE DETAILS")
        print(f"{'='*60}")

        for service in summary['services']:
            status_icon = "✅" if service['status'] == 'healthy' else "⚠️" if service['status'] == 'warning' else "❌"
            print(f"\n{status_icon} {service['service']} ({service['status']})")
            print(f"   Message: {service['message']}")
            print(f"   Response Time: {service['response_time_ms']}ms")

            if service['metrics']:
                print("   Metrics:")
                for key, value in service['metrics'].items():
                    print(f"     {key}: {value}")

        print(f"\n{'='*60}")

    def save_report(self, summary: Dict[str, Any], output_path: str = None):
        """Save health report to file"""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"health_report_{timestamp}.json"

        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"\n📄 Health report saved to: {output_path}")


async def main():
    """Main health check function"""
    checker = DatabaseHealthChecker()

    try:
        # Run all health checks
        summary = await checker.check_all_databases()

        # Print summary
        checker.print_summary(summary)

        # Save report
        checker.save_report(summary)

        # Exit with appropriate code
        if summary['overall_status'] == 'error':
            sys.exit(1)
        elif summary['overall_status'] == 'warning':
            sys.exit(2)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n⚠️ Health check interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Health check failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())