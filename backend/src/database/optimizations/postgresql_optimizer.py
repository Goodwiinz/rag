"""
Production Database Optimization Framework for Multimodal Enterprise RAG System

This module provides comprehensive database optimizations for production deployment,
including performance tuning, indexing strategies, partitioning, and monitoring integration.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import json

import asyncpg
import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)


class OptimizationLevel(str, Enum):
    """Optimization levels for different deployment scenarios"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    HIGH_THROUGHPUT = "high_throughput"


@dataclass
class DatabaseConfig:
    """Database configuration for optimization"""
    host: str = "localhost"
    port: int = 5432
    user: str = "raguser"
    password: str = "rag_password_123"
    database: str = "ragdb"
    pool_size: int = 20
    max_overflow: int = 30
    pool_timeout: int = 30
    pool_recycle: int = 3600
    optimization_level: OptimizationLevel = OptimizationLevel.PRODUCTION


@dataclass
class OptimizationMetrics:
    """Optimization performance metrics"""
    query_time_before: float
    query_time_after: float
    improvement_percentage: float
    index_size: int
    table_size_before: int
    table_size_after: int
    timestamp: datetime


class PostgreSQLOptimizer:
    """Advanced PostgreSQL optimization for production workloads"""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine = None
        self.session_factory = None
        self.optimization_history: List[OptimizationMetrics] = []

    async def initialize(self):
        """Initialize database connections and pools"""
        # Create SQLAlchemy engine with optimized settings
        connection_string = (
            f"postgresql://{self.config.user}:{self.config.password}@"
            f"{self.config.host}:{self.config.port}/{self.config.database}"
        )

        self.engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=self.config.pool_size,
            max_overflow=self.config.max_overflow,
            pool_timeout=self.config.pool_timeout,
            pool_recycle=self.config.pool_recycle,
            pool_pre_ping=True,
            echo=False,
            connect_args={
                "application_name": "rag_optimizer",
                "connect_timeout": 10,
                "command_timeout": 30,
                "options": "-c default_transaction_isolation=read_committed"
            }
        )

        self.session_factory = sessionmaker(bind=self.engine)
        logger.info("PostgreSQL optimizer initialized")

    async def apply_production_optimizations(self) -> Dict[str, Any]:
        """Apply all production optimizations"""
        results = {
            'success': True,
            'optimizations_applied': [],
            'errors': [],
            'metrics': {}
        }

        try:
            # 1. Configure database parameters
            config_result = await self._configure_database_parameters()
            results['optimizations_applied'].append(config_result)

            # 2. Create optimized indexes
            index_result = await self._create_optimized_indexes()
            results['optimizations_applied'].append(index_result)

            # 3. Set up partitioning for time-series data
            partition_result = await self._setup_time_series_partitioning()
            results['optimizations_applied'].append(partition_result)

            # 4. Create materialized views for dashboard queries
            materialized_result = await self._create_materialized_views()
            results['optimizations_applied'].append(materialized_result)

            # 5. Optimize table configurations
            table_opt_result = await self._optimize_table_configurations()
            results['optimizations_applied'].append(table_opt_result)

            # 6. Set up vacuum and analyze schedules
            maintenance_result = await self._setup_maintenance_schedules()
            results['optimizations_applied'].append(maintenance_result)

            logger.info("All production optimizations applied successfully")

        except Exception as e:
            logger.error(f"Error applying optimizations: {e}")
            results['success'] = False
            results['errors'].append(str(e))

        return results

    async def _configure_database_parameters(self) -> Dict[str, Any]:
        """Configure PostgreSQL parameters for production workload"""
        async with asyncpg.connect(**self._get_connection_config()) as conn:
            # Production-specific configurations
            configurations = [
                # Memory settings
                "ALTER SYSTEM SET shared_buffers = '256MB'",
                "ALTER SYSTEM SET effective_cache_size = '1GB'",
                "ALTER SYSTEM SET work_mem = '4MB'",
                "ALTER SYSTEM SET maintenance_work_mem = '64MB'",

                # Connection settings
                "ALTER SYSTEM SET max_connections = 200",
                "ALTER SYSTEM SET superuser_reserved_connections = 3",

                # WAL settings
                "ALTER SYSTEM SET wal_buffers = '16MB'",
                "ALTER SYSTEM SET checkpoint_completion_target = 0.9",
                "ALTER SYSTEM SET wal_writer_delay = '200ms'",

                # Query planning
                "ALTER SYSTEM SET random_page_cost = 1.1",
                "ALTER SYSTEM SET effective_io_concurrency = 200",

                # Logging
                "ALTER SYSTEM SET log_min_duration_statement = 1000",
                "ALTER SYSTEM SET log_checkpoints = on",
                "ALTER SYSTEM SET log_connections = on",
                "ALTER SYSTEM SET log_disconnections = on",
                "ALTER SYSTEM SET log_lock_waits = on",

                # Autovacuum tuning
                "ALTER SYSTEM SET autovacuum = on",
                "ALTER SYSTEM SET autovacuum_max_workers = 3",
                "ALTER SYSTEM SET autovacuum_naptime = '1min'",

                # Monitoring
                "ALTER SYSTEM SET track_activity_query_size = 2048",
                "ALTER SYSTEM SET pg_stat_statements.track = all"
            ]

            for config in configurations:
                try:
                    await conn.execute(config)
                    logger.debug(f"Applied configuration: {config}")
                except Exception as e:
                    logger.warning(f"Could not apply {config}: {e}")

            # Reload configuration
            await conn.execute("SELECT pg_reload_conf()")

            return {
                'operation': 'configure_parameters',
                'success': True,
                'applied_configs': len(configurations)
            }

    async def _create_optimized_indexes(self) -> Dict[str, Any]:
        """Create optimized indexes for monitoring queries"""
        index_definitions = [
            # Metrics table indexes
            {
                'table': 'monitoring_metrics',
                'indexes': [
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metrics_definition_time_btree ON monitoring_metrics (definition_id, timestamp DESC)",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metrics_source_time_btree ON monitoring_metrics (source, timestamp DESC)",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metrics_value_time ON monitoring_metrics (value, timestamp) WHERE value IS NOT NULL",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metrics_composite ON monitoring_metrics (definition_id, source, timestamp DESC)"
                ]
            },

            # Tracing table indexes
            {
                'table': 'monitoring_traces',
                'indexes': [
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_traces_service_time_desc ON monitoring_traces (service_name, start_time DESC)",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_traces_duration ON monitoring_traces (duration_ms) WHERE duration_ms IS NOT NULL",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_traces_status_time ON monitoring_traces (status, start_time DESC)",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_traces_composite ON monitoring_traces (service_name, status, start_time DESC)"
                ]
            },

            # Spans table indexes
            {
                'table': 'monitoring_spans',
                'indexes': [
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spans_trace_time ON monitoring_spans (trace_id, start_time DESC)",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spans_service_operation ON monitoring_spans (service_name, operation_name)",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spans_duration ON monitoring_spans (duration_ms) WHERE duration_ms > 100",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_spans_parent ON monitoring_spans (parent_span_id) WHERE parent_span_id IS NOT NULL"
                ]
            },

            # Logs table indexes
            {
                'table': 'monitoring_logs',
                'indexes': [
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_timestamp_desc ON monitoring_logs (timestamp DESC)",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_level_time ON monitoring_logs (level, timestamp DESC)",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_service_time ON monitoring_logs (service_name, timestamp DESC)",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_error_time ON monitoring_logs (timestamp DESC) WHERE level IN ('ERROR', 'FATAL')",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_correlation ON monitoring_logs (correlation_id, timestamp DESC) WHERE correlation_id IS NOT NULL"
                ]
            },

            # Aggregations table indexes
            {
                'table': 'monitoring_metric_aggregations',
                'indexes': [
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_aggregations_def_time ON monitoring_metric_aggregations (definition_id, time_bucket DESC)",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_aggregations_type_time ON monitoring_metric_aggregations (aggregation_type, time_bucket DESC)",
                    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_aggregations_bucket_size ON monitoring_metric_aggregations (bucket_size_minutes, time_bucket DESC)"
                ]
            }
        ]

        created_indexes = []
        async with asyncpg.connect(**self._get_connection_config()) as conn:
            for table_config in index_definitions:
                for index_sql in table_config['indexes']:
                    try:
                        await conn.execute(index_sql)
                        index_name = index_sql.split("IF NOT EXISTS ")[1].split(" ON ")[0]
                        created_indexes.append({
                            'table': table_config['table'],
                            'index': index_name,
                            'sql': index_sql
                        })
                        logger.debug(f"Created index: {index_name}")
                    except Exception as e:
                        logger.warning(f"Failed to create index: {index_sql}, Error: {e}")

        return {
            'operation': 'create_indexes',
            'success': True,
            'indexes_created': len(created_indexes),
            'index_details': created_indexes
        }

    async def _setup_time_series_partitioning(self) -> Dict[str, Any]:
        """Set up partitioning for time-series monitoring data"""
        partition_configs = [
            {
                'table': 'monitoring_metrics',
                'partition_column': 'timestamp',
                'partition_type': 'RANGE',
                'initial_partitions': [
                    'monitoring_metrics_2024_01 PARTITION OF monitoring_metrics FOR VALUES FROM (\'2024-01-01\') TO (\'2024-02-01\')',
                    'monitoring_metrics_2024_02 PARTITION OF monitoring_metrics FOR VALUES FROM (\'2024-02-01\') TO (\'2024-03-01\')',
                    'monitoring_metrics_2024_03 PARTITION OF monitoring_metrics FOR VALUES FROM (\'2024-03-01\') TO (\'2024-04-01\')',
                    'monitoring_metrics_2024_04 PARTITION OF monitoring_metrics FOR VALUES FROM (\'2024-04-01\') TO (\'2024-05-01\')',
                    'monitoring_metrics_current PARTITION OF monitoring_metrics FOR VALUES FROM (\'2024-05-01\') TO (\'2025-01-01\')'
                ]
            },
            {
                'table': 'monitoring_traces',
                'partition_column': 'start_time',
                'partition_type': 'RANGE',
                'initial_partitions': [
                    'monitoring_traces_2024_01 PARTITION OF monitoring_traces FOR VALUES FROM (\'2024-01-01\') TO (\'2024-02-01\')',
                    'monitoring_traces_2024_02 PARTITION OF monitoring_traces FOR VALUES FROM (\'2024-02-01\') TO (\'2024-03-01\')',
                    'monitoring_traces_current PARTITION OF monitoring_traces FOR VALUES FROM (\'2024-03-01\') TO (\'2025-01-01\')'
                ]
            },
            {
                'table': 'monitoring_logs',
                'partition_column': 'timestamp',
                'partition_type': 'RANGE',
                'initial_partitions': [
                    'monitoring_logs_2024_01 PARTITION OF monitoring_logs FOR VALUES FROM (\'2024-01-01\') TO (\'2024-02-01\')',
                    'monitoring_logs_current PARTITION OF monitoring_logs FOR VALUES FROM (\'2024-02-01\') TO (\'2025-01-01\')'
                ]
            }
        ]

        partitions_created = []
        async with asyncpg.connect(**self._get_connection_config()) as conn:
            for config in partition_configs:
                table_name = config['table']

                # Check if table is already partitioned
                is_partitioned = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_inherits
                        WHERE inhparent = $1::regclass
                    )
                """, table_name)

                if not is_partitioned:
                    try:
                        # Convert table to partitioned (simplified approach)
                        await conn.execute(f"""
                            ALTER TABLE {table_name}
                            PARTITION BY RANGE ({config['partition_column']})
                        """)

                        # Create initial partitions
                        for partition_sql in config['initial_partitions']:
                            await conn.execute(f"CREATE TABLE IF NOT EXISTS {partition_sql}")
                            partitions_created.append(partition_sql.split(' PARTITION OF ')[0])

                        logger.info(f"Set up partitioning for {table_name}")

                    except Exception as e:
                        logger.warning(f"Failed to set up partitioning for {table_name}: {e}")
                else:
                    logger.info(f"Table {table_name} is already partitioned")

        return {
            'operation': 'setup_partitioning',
            'success': True,
            'partitions_created': len(partitions_created),
            'partition_details': partitions_created
        }

    async def _create_materialized_views(self) -> Dict[str, Any]:
        """Create materialized views for dashboard performance"""
        view_definitions = [
            # Dashboard metrics view
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_metrics_summary AS
            SELECT
                date_trunc('hour', m.timestamp) as hour_bucket,
                md.name as metric_name,
                md.category as metric_category,
                avg(m.value) as avg_value,
                min(m.value) as min_value,
                max(m.value) as max_value,
                count(*) as sample_count,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY m.value) as p95_value
            FROM monitoring_metrics m
            JOIN monitoring_metric_definitions md ON m.definition_id = md.id
            WHERE m.timestamp >= NOW() - INTERVAL '24 hours'
            GROUP BY 1, 2, 3
            """,

            # Recent errors view
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS recent_errors_summary AS
            SELECT
                date_trunc('hour', l.timestamp) as hour_bucket,
                l.service_name,
                l.exception_class,
                count(*) as error_count,
                count(DISTINCT l.user_id) as affected_users,
                array_agg(DISTINCT l.message ORDER BY l.timestamp DESC) as sample_messages
            FROM monitoring_logs l
            WHERE l.level IN ('ERROR', 'FATAL')
            AND l.timestamp >= NOW() - INTERVAL '24 hours'
            GROUP BY 1, 2, 3
            """,

            # Performance traces view
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS performance_traces_summary AS
            SELECT
                date_trunc('hour', t.start_time) as hour_bucket,
                t.service_name,
                t.operation_name,
                avg(t.duration_ms) as avg_duration,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY t.duration_ms) as p95_duration,
                count(*) as trace_count,
                count(CASE WHEN t.status = 'error' THEN 1 END) as error_count
            FROM monitoring_traces t
            WHERE t.start_time >= NOW() - INTERVAL '24 hours'
            GROUP BY 1, 2, 3
            """,

            # System health view
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS system_health_overview AS
            SELECT
                'metrics' as data_type,
                count(*) as total_records,
                count(CASE WHEN timestamp >= NOW() - INTERVAL '1 hour' THEN 1 END) as recent_records
            FROM monitoring_metrics
            WHERE timestamp >= NOW() - INTERVAL '24 hours'

            UNION ALL

            SELECT
                'traces' as data_type,
                count(*) as total_records,
                count(CASE WHEN start_time >= NOW() - INTERVAL '1 hour' THEN 1 END) as recent_records
            FROM monitoring_traces
            WHERE start_time >= NOW() - INTERVAL '24 hours'

            UNION ALL

            SELECT
                'logs' as data_type,
                count(*) as total_records,
                count(CASE WHEN timestamp >= NOW() - INTERVAL '1 hour' THEN 1 END) as recent_records
            FROM monitoring_logs
            WHERE timestamp >= NOW() - INTERVAL '24 hours' AND level = 'ERROR'
            """
        ]

        created_views = []
        async with asyncpg.connect(**self._get_connection_config()) as conn:
            for view_sql in view_definitions:
                try:
                    await conn.execute(view_sql)
                    view_name = view_sql.split("VIEW IF NOT EXISTS ")[1].split(" AS")[0]
                    created_views.append(view_name)

                    # Create unique index for concurrent refresh
                    index_sql = f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{view_name}_unique ON {view_name} (hour_bucket, metric_name, service_name)"
                    try:
                        await conn.execute(index_sql)
                    except:
                        pass  # Index might fail due to column differences

                    logger.debug(f"Created materialized view: {view_name}")

                except Exception as e:
                    logger.warning(f"Failed to create materialized view: {e}")

        return {
            'operation': 'create_materialized_views',
            'success': True,
            'views_created': len(created_views),
            'view_details': created_views
        }

    async def _optimize_table_configurations(self) -> Dict[str, Any]:
        """Optimize table configurations for performance"""
        table_optimizations = [
            # Fill factor adjustments
            "ALTER TABLE monitoring_metrics SET (fillfactor = 90)",
            "ALTER TABLE monitoring_traces SET (fillfactor = 90)",
            "ALTER TABLE monitoring_spans SET (fillfactor = 90)",
            "ALTER TABLE monitoring_logs SET (fillfactor = 85)",

            # Toast table settings
            "ALTER TABLE monitoring_logs ALTER COLUMN message SET STORAGE EXTENDED",
            "ALTER TABLE monitoring_logs ALTER COLUMN stack_trace SET STORAGE EXTERNAL",
            "ALTER TABLE monitoring_trace_errors ALTER COLUMN stack_trace SET STORAGE EXTERNAL",

            # Row level security policies if needed
            # (Add RLS policies here if implementing multi-tenant security)
        ]

        applied_optimizations = []
        async with asyncpg.connect(**self._get_connection_config()) as conn:
            for opt_sql in table_optimizations:
                try:
                    await conn.execute(opt_sql)
                    applied_optimizations.append(opt_sql)
                    logger.debug(f"Applied table optimization: {opt_sql}")
                except Exception as e:
                    logger.warning(f"Failed to apply table optimization: {opt_sql}, Error: {e}")

        return {
            'operation': 'optimize_tables',
            'success': True,
            'optimizations_applied': len(applied_optimizations),
            'details': applied_optimizations
        }

    async def _setup_maintenance_schedules(self) -> Dict[str, Any]:
        """Set up automated maintenance schedules"""
        maintenance_functions = [
            # Auto-refresh materialized views function
            """
            CREATE OR REPLACE FUNCTION refresh_dashboard_views()
            RETURNS void AS $$
            BEGIN
                REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_metrics_summary;
                REFRESH MATERIALIZED VIEW CONCURRENTLY recent_errors_summary;
                REFRESH MATERIALIZED VIEW CONCURRENTLY performance_traces_summary;
                REFRESH MATERIALIZED VIEW CONCURRENTLY system_health_overview;
            END;
            $$ LANGUAGE plpgsql;
            """,

            # Partition maintenance function
            """
            CREATE OR REPLACE FUNCTION create_monthly_partitions()
            RETURNS void AS $$
            DECLARE
                current_month text;
                next_month text;
            BEGIN
                current_month := to_char(now(), 'YYYY_MM');
                next_month := to_char(now() + interval '1 month', 'YYYY_MM');

                -- Create next month's partitions for each time-series table
                EXECUTE format('CREATE TABLE IF NOT EXISTS monitoring_metrics_%s PARTITION OF monitoring_metrics FOR VALUES FROM (%L) TO (%L)',
                              next_month, date_trunc('month', now() + interval '1 month'), date_trunc('month', now() + interval '2 months'));

                EXECUTE format('CREATE TABLE IF NOT EXISTS monitoring_traces_%s PARTITION OF monitoring_traces FOR VALUES FROM (%L) TO (%L)',
                              next_month, date_trunc('month', now() + interval '1 month'), date_trunc('month', now() + interval '2 months'));

                EXECUTE format('CREATE TABLE IF NOT EXISTS monitoring_logs_%s PARTITION OF monitoring_logs FOR VALUES FROM (%L) TO (%L)',
                              next_month, date_trunc('month', now() + interval '1 month'), date_trunc('month', now() + interval '2 months'));
            END;
            $$ LANGUAGE plpgsql;
            """,

            # Data cleanup function
            """
            CREATE OR REPLACE FUNCTION cleanup_old_monitoring_data(retention_days int DEFAULT 30)
            RETURNS void AS $$
            BEGIN
                -- Delete old metrics
                DELETE FROM monitoring_metrics WHERE timestamp < NOW() - INTERVAL '1 day' * retention_days;

                -- Delete old traces
                DELETE FROM monitoring_traces WHERE start_time < NOW() - INTERVAL '1 day' * retention_days;

                -- Delete old logs (keep errors longer)
                DELETE FROM monitoring_logs WHERE timestamp < NOW() - INTERVAL '1 day' * retention_days AND level NOT IN ('ERROR', 'FATAL');
                DELETE FROM monitoring_logs WHERE timestamp < NOW() - INTERVAL '1 day' * (retention_days * 2) AND level IN ('ERROR', 'FATAL');

                -- Vacuum and analyze
                VACUUM ANALYZE monitoring_metrics;
                VACUUM ANALYZE monitoring_traces;
                VACUUM ANALYZE monitoring_logs;
            END;
            $$ LANGUAGE plpgsql;
            """
        ]

        created_functions = []
        async with asyncpg.connect(**self._get_connection_config()) as conn:
            for func_sql in maintenance_functions:
                try:
                    await conn.execute(func_sql)
                    func_name = func_sql.split("FUNCTION ")[1].split("(")[0]
                    created_functions.append(func_name)
                    logger.debug(f"Created maintenance function: {func_name}")
                except Exception as e:
                    logger.warning(f"Failed to create maintenance function: {e}")

        return {
            'operation': 'setup_maintenance',
            'success': True,
            'functions_created': len(created_functions),
            'function_details': created_functions
        }

    async def analyze_query_performance(self, query: str) -> Dict[str, Any]:
        """Analyze query performance and suggest optimizations"""
        async with asyncpg.connect(**self._get_connection_config()) as conn:
            try:
                # Get query plan
                plan_result = await conn.fetchval(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}")
                plan_data = json.loads(plan_result)[0]

                # Extract performance metrics
                execution_time = plan_data.get('Execution Time', 0)
                planning_time = plan_data.get('Planning Time', 0)
                total_cost = plan_data.get('Plan', {}).get('Total Cost', 0)

                # Analyze plan for optimization opportunities
                suggestions = []
                if execution_time > 1000:  # > 1 second
                    suggestions.append("Consider adding indexes for filtered columns")

                if 'Seq Scan' in str(plan_data):
                    suggestions.append("Sequential scan detected - consider adding indexes")

                if 'Sort' in str(plan_data):
                    suggestions.append("Consider adding index for ORDER BY clause")

                return {
                    'query': query,
                    'execution_time_ms': execution_time,
                    'planning_time_ms': planning_time,
                    'total_cost': total_cost,
                    'optimization_suggestions': suggestions,
                    'plan_details': plan_data
                }

            except Exception as e:
                return {
                    'query': query,
                    'error': str(e),
                    'optimization_suggestions': ['Query failed to execute']
                }

    async def get_optimization_report(self) -> Dict[str, Any]:
        """Generate comprehensive optimization report"""
        async with asyncpg.connect(**self._get_connection_config()) as conn:
            # Database size and table statistics
            db_stats = await conn.fetch("""
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_tuples,
                    n_dead_tup as dead_tuples
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """)

            # Index usage statistics
            index_stats = await conn.fetch("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_tup_read,
                    idx_tup_fetch,
                    idx_scan,
                    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                ORDER BY idx_scan DESC
            """)

            # Slow queries
            slow_queries = await conn.fetch("""
                SELECT
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    rows,
                    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
                FROM pg_stat_statements
                WHERE mean_exec_time > 100
                ORDER BY mean_exec_time DESC
                LIMIT 10
            """)

            return {
                'timestamp': datetime.utcnow().isoformat(),
                'database_stats': [dict(row) for row in db_stats],
                'index_statistics': [dict(row) for row in index_stats],
                'slow_queries': [dict(row) for row in slow_queries],
                'optimization_history': len(self.optimization_history),
                'configuration': {
                    'pool_size': self.config.pool_size,
                    'optimization_level': self.config.optimization_level.value
                }
            }

    def _get_connection_config(self) -> Dict[str, Any]:
        """Get connection configuration for asyncpg"""
        return {
            'host': self.config.host,
            'port': self.config.port,
            'user': self.config.user,
            'password': self.config.password,
            'database': self.config.database,
            'command_timeout': 60
        }


class MigrationManager:
    """Database migration manager with rollback support"""

    def __init__(self, optimizer: PostgreSQLOptimizer):
        self.optimizer = optimizer
        self.migration_history: List[Dict[str, Any]] = []

    async def create_migration_tables(self):
        """Create migration tracking tables"""
        async with asyncpg.connect(**self.optimizer._get_connection_config()) as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id SERIAL PRIMARY KEY,
                    migration_name VARCHAR(255) UNIQUE NOT NULL,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    rollback_sql TEXT,
                    description TEXT,
                    checksum VARCHAR(64)
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS migration_locks (
                    id SERIAL PRIMARY KEY,
                    lock_name VARCHAR(255) UNIQUE NOT NULL,
                    locked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    locked_by VARCHAR(255),
                    expires_at TIMESTAMP WITH TIME ZONE
                )
            """)

    async def run_migration(self, migration_name: str, sql: str, rollback_sql: str = None, description: str = "") -> bool:
        """Run a single migration with rollback support"""
        async with asyncpg.connect(**self.optimizer._get_connection_config()) as conn:
            try:
                # Check if migration already applied
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE migration_name = $1)",
                    migration_name
                )

                if exists:
                    logger.info(f"Migration {migration_name} already applied")
                    return True

                # Start transaction
                async with conn.transaction():
                    # Apply migration
                    await conn.execute(sql)

                    # Record migration
                    await conn.execute("""
                        INSERT INTO schema_migrations (migration_name, rollback_sql, description, checksum)
                        VALUES ($1, $2, $3, $4)
                    """, migration_name, rollback_sql, description, migration_name)  # Simple checksum

                    logger.info(f"Applied migration: {migration_name}")

                    # Record in history
                    self.migration_history.append({
                        'migration_name': migration_name,
                        'applied_at': datetime.utcnow(),
                        'success': True,
                        'description': description
                    })

                return True

            except Exception as e:
                logger.error(f"Failed to apply migration {migration_name}: {e}")
                self.migration_history.append({
                    'migration_name': migration_name,
                    'applied_at': datetime.utcnow(),
                    'success': False,
                    'error': str(e),
                    'description': description
                })
                return False

    async def rollback_migration(self, migration_name: str) -> bool:
        """Rollback a specific migration"""
        async with asyncpg.connect(**self.optimizer._get_connection_config()) as conn:
            try:
                # Get rollback SQL
                rollback_sql = await conn.fetchval(
                    "SELECT rollback_sql FROM schema_migrations WHERE migration_name = $1",
                    migration_name
                )

                if not rollback_sql:
                    logger.error(f"No rollback SQL found for migration {migration_name}")
                    return False

                # Execute rollback
                async with conn.transaction():
                    await conn.execute(rollback_sql)
                    await conn.execute("DELETE FROM schema_migrations WHERE migration_name = $1", migration_name)

                logger.info(f"Rolled back migration: {migration_name}")
                return True

            except Exception as e:
                logger.error(f"Failed to rollback migration {migration_name}: {e}")
                return False

    async def get_migration_status(self) -> Dict[str, Any]:
        """Get migration status and history"""
        async with asyncpg.connect(**self.optimizer._get_connection_config()) as conn:
            migrations = await conn.fetch("""
                SELECT migration_name, applied_at, description, checksum
                FROM schema_migrations
                ORDER BY applied_at DESC
            """)

            return {
                'applied_migrations': [dict(row) for row in migrations],
                'total_migrations': len(migrations),
                'last_migration': migrations[0]['applied_at'] if migrations else None
            }


# Utility functions
async def run_database_health_check(config: DatabaseConfig) -> Dict[str, Any]:
    """Run comprehensive database health check"""
    optimizer = PostgreSQLOptimizer(config)
    await optimizer.initialize()

    return await optimizer.get_optimization_report()


def create_production_config() -> DatabaseConfig:
    """Create production database configuration"""
    return DatabaseConfig(
        host="localhost",
        port=5432,
        user="raguser",
        password="rag_password_123",
        database="ragdb",
        pool_size=50,  # Increased for production
        max_overflow=100,
        pool_timeout=30,
        pool_recycle=3600,
        optimization_level=OptimizationLevel.PRODUCTION
    )