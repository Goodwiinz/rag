"""
Database optimization scripts for enhanced document processing performance
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from sqlalchemy import text, Index, and_, or_, func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import VACUUM, ANALYZE

logger = logging.getLogger(__name__)


class DatabaseOptimizer:
    """
    Database optimization utilities for document processing performance
    """

    def __init__(self, db: Session):
        self.db = db

    def analyze_table_statistics(self, table_name: str) -> Dict:
        """
        Analyze table statistics and provide recommendations
        """
        try:
            # Get table row count
            count_query = text(f"SELECT COUNT(*) as row_count FROM {table_name}")
            count_result = self.db.execute(count_query).fetchone()
            row_count = count_result.row_count if count_result else 0

            # Get table size
            size_query = text(f"""
                SELECT
                    pg_size_pretty(pg_total_relation_size('{table_name}')) as total_size,
                    pg_size_pretty(pg_relation_size('{table_name}')) as table_size,
                    pg_size_pretty(pg_total_relation_size('{table_name}') - pg_relation_size('{table_name}')) as index_size
            """)
            size_result = self.db.execute(size_query).fetchone()

            # Get index usage statistics
            index_query = text(f"""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_tup_read,
                    idx_tup_fetch,
                    idx_scan
                FROM pg_stat_user_indexes
                WHERE tablename = '{table_name}'
                ORDER BY idx_scan DESC
            """)
            index_results = self.db.execute(index_query).fetchall()

            return {
                'table_name': table_name,
                'row_count': row_count,
                'size_info': {
                    'total_size': size_result.total_size if size_result else 'Unknown',
                    'table_size': size_result.table_size if size_result else 'Unknown',
                    'index_size': size_result.index_size if size_result else 'Unknown'
                },
                'index_usage': [
                    {
                        'index_name': row.indexname,
                        'tuples_read': row.idx_tup_read,
                        'tuples_fetched': row.idx_tup_fetch,
                        'scans': row.idx_scan
                    }
                    for row in index_results
                ]
            }

        except Exception as e:
            logger.error(f"Error analyzing table {table_name}: {e}")
            return {'error': str(e)}

    def create_missing_indexes(self) -> Dict[str, List[str]]:
        """
        Create recommended indexes for performance optimization
        """
        created_indexes = {}

        try:
            # Documents table indexes
            documents_indexes = [
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_org_type_status ON documents (organization_id, document_type, processing_status)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_processing_queue_priority ON documents (processing_status, priority DESC, created_at)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_searchable_content ON documents (organization_id, is_embedded, is_indexed, document_type) WHERE is_deleted = false",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_user_recent ON documents (uploaded_by_user_id, created_at DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_metadata_gin ON documents USING GIN (document_metadata)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_tags_gin ON documents USING GIN (tags)"
            ]

            created_indexes['documents'] = self._execute_index_commands(documents_indexes)

            # Processing history indexes
            processing_history_indexes = [
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_history_document_timeline ON processing_history (document_id, created_at, stage)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_history_org_stage_status ON processing_history (organization_id, stage, status)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_history_processor_queue ON processing_history (status, processor_id, created_at) WHERE status IN ('pending', 'running')",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_history_error_retry ON processing_history (status, retry_count, created_at) WHERE status = 'failed'",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_history_duration_analysis ON processing_history (duration_seconds, stage, organization_id)"
            ]

            created_indexes['processing_history'] = self._execute_index_commands(processing_history_indexes)

            # Multimodal content indexes
            multimodal_content_indexes = [
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_multimodal_content_document_sequence ON multimodal_content (document_id, content_type, sequence_order)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_multimodal_content_org_type_indexed ON multimodal_content (organization_id, content_type, is_indexed)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_multimodal_content_quality_filter ON multimodal_content (quality_score, content_type) WHERE quality_score >= 0.5",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_multimodal_content_media_specific ON multimodal_content (content_type, media_duration_seconds, media_format) WHERE content_type IN ('audio', 'video')",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_multimodal_content_language_specific ON multimodal_content (language_code, content_type, word_count)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_multimodal_content_metadata_gin ON multimodal_content USING GIN (content_metadata)"
            ]

            created_indexes['multimodal_content'] = self._execute_index_commands(multimodal_content_indexes)

            # Document versions indexes
            document_versions_indexes = [
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_versions_document_current ON document_versions (document_id, is_current_version)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_versions_org_timeline ON document_versions (organization_id, created_at DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_versions_user_versions ON document_versions (created_by_user_id, created_at DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_versions_major_minor ON document_versions (document_id, is_major_version, version_number)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_versions_hash_lookup ON document_versions (file_hash)"
            ]

            created_indexes['document_versions'] = self._execute_index_commands(document_versions_indexes)

            # Quality metrics indexes
            quality_metrics_indexes = [
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quality_metrics_document_type_time ON document_quality_metrics (document_id, metric_type, created_at DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quality_metrics_threshold_analysis ON document_quality_metrics (meets_threshold, metric_type, metric_value)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quality_metrics_assessment_confidence ON document_quality_metrics (assessment_method, confidence_score, created_at)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quality_metrics_org_metric_summary ON document_quality_metrics (organization_id, metric_type, created_at DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_quality_metrics_details_gin ON document_quality_metrics USING GIN (metric_details)"
            ]

            created_indexes['document_quality_metrics'] = self._execute_index_commands(quality_metrics_indexes)

            # Access log indexes (for time-series analysis)
            access_log_indexes = [
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_access_log_document_timeline ON document_access_log (document_id, created_at DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_access_log_user_timeline ON document_access_log (user_id, created_at DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_access_log_security_analysis ON document_access_log (is_suspicious, threat_score, created_at DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_access_log_access_pattern ON document_access_log (access_type, access_result, created_at DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_access_log_ip_analysis ON document_access_log (ip_address, created_at DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_access_log_response_analysis ON document_access_log (response_status_code, response_time_ms)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_access_log_session_tracking ON document_access_log (session_id, created_at DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_access_log_security_flags_gin ON document_access_log USING GIN (security_flags)"
            ]

            created_indexes['document_access_log'] = self._execute_index_commands(access_log_indexes)

            # Processing jobs indexes
            processing_jobs_indexes = [
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_jobs_queue_priority_time ON processing_jobs (status, priority DESC, created_at)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_jobs_org_type_status ON processing_jobs (organization_id, job_type, status)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_jobs_progress_tracking ON processing_jobs (status, progress_percentage, created_at)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_jobs_worker_performance ON processing_jobs (worker_id, duration_seconds, created_at DESC)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_jobs_retry_analysis ON processing_jobs (status, retry_count, created_at)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_jobs_config_gin ON processing_jobs USING GIN (config)",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_jobs_artifacts_gin ON processing_jobs USING GIN (artifacts)"
            ]

            created_indexes['processing_jobs'] = self._execute_index_commands(processing_jobs_indexes)

            logger.info("Database indexes created successfully")
            return created_indexes

        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            return {'error': str(e)}

    def _execute_index_commands(self, index_commands: List[str]) -> List[str]:
        """Execute index creation commands and return successful ones"""
        successful_indexes = []

        for command in index_commands:
            try:
                self.db.execute(text(command))
                self.db.commit()
                successful_indexes.append(command)
                logger.info(f"Successfully created index: {command}")
            except Exception as e:
                logger.warning(f"Failed to create index: {command}. Error: {e}")
                self.db.rollback()

        return successful_indexes

    def optimize_table_maintenance(self) -> Dict[str, str]:
        """
        Run table maintenance operations for performance optimization
        """
        results = {}

        try:
            # Tables to optimize
            tables = [
                'documents',
                'processing_history',
                'document_versions',
                'multimodal_content',
                'document_quality_metrics',
                'document_access_log',
                'processing_jobs'
            ]

            for table in tables:
                try:
                    # Update table statistics
                    analyze_query = text(f"ANALYZE {table}")
                    self.db.execute(analyze_query)
                    results[f"{table}_analyze"] = "completed"

                    # Check if table needs vacuum (high bloat)
                    bloat_query = text(f"""
                        SELECT
                            schemaname,
                            tablename,
                            ROUND(CASE WHEN otta=0 THEN 0.0 ELSE sml.relpages/otta::numeric END,1) AS tbloat,
                            CASE WHEN relpages < otta THEN 0 ELSE relpages::bigint - otta END AS wastedpages,
                            CASE WHEN relpages < otta THEN 0 ELSE bs*(sml.relpages-otta)::bigint END AS wastedbytes,
                            CASE WHEN relpages < otta THEN 0 ELSE (bs*(relpages-otta))::bigint END AS wastedsize
                        FROM (
                            SELECT
                                schemaname, tablename, cc.reltuples, cc.relpages, bs,
                                CEIL((cc.reltuples*((datahdr+ma-
                                    (CASE WHEN datahdr%ma=0 THEN ma ELSE datahdr%ma END))+nullhdr2+4))/(bs-20::float)) AS otta
                            FROM (
                                SELECT
                                    ma,bs,schemaname,tablename,
                                    (datawidth+(hdr+ma-(CASE WHEN hdr%ma=0 THEN ma ELSE hdr%ma END)))::numeric AS datahdr,
                                    (maxfracsum*(nullhdr+ma-(CASE WHEN nullhdr%ma=0 THEN ma ELSE nullhdr%ma END))) AS nullhdr2
                                FROM (
                                    SELECT
                                        schemaname, tablename, hdr, ma, bs,
                                        SUM((1-null_frac)*avg_width) AS datawidth,
                                        MAX(null_frac) AS maxfracsum,
                                        hdr+(
                                            SELECT 1+COUNT(*)*(8-CASE WHEN avg_width<=248 THEN 1 ELSE 8 END)
                                            FROM pg_stats s2
                                            WHERE s2.schemaname=s.schemaname AND s2.tablename=s.tablename AND null_frac<>0
                                        ) AS nullhdr
                                    FROM pg_stats s, (
                                        SELECT
                                            (SELECT current_setting('block_size')::numeric) AS bs,
                                            CASE WHEN substring(v,12,3) IN ('8.0','8.1','8.2') THEN 27 ELSE 23 END AS hdr,
                                            CASE WHEN v ~ 'mingw32' THEN 8 ELSE 4 END AS ma
                                        FROM (SELECT version() AS v) AS foo
                                    ) AS constants
                                    WHERE schemaname='public'
                                    GROUP BY 1,2,3,4,5
                                ) AS foo
                            ) AS rs
                            JOIN pg_class cc ON cc.relname = rs.tablename
                            JOIN pg_namespace nn ON cc.relnamespace = nn.oid AND nn.nspname = rs.schemaname AND nn.nspname <> 'information_schema'
                        ) AS sml
                        WHERE tbloat > 1.5 AND tablename = '{table}'
                    """)

                    bloat_result = self.db.execute(bloat_query).fetchone()

                    if bloat_result and bloat_result.tbloat > 1.5:
                        # Run vacuum if significant bloat detected
                        vacuum_query = text(f"VACUUM ANALYZE {table}")
                        self.db.execute(vacuum_query)
                        results[f"{table}_vacuum"] = f"completed (bloat: {bloat_result.tbloat})"
                        logger.info(f"Vacuumed table {table} due to bloat: {bloat_result.tbloat}")
                    else:
                        results[f"{table}_vacuum"] = "skipped (low bloat)"

                except Exception as e:
                    logger.error(f"Error optimizing table {table}: {e}")
                    results[f"{table}_error"] = str(e)

            logger.info("Table maintenance completed")
            return results

        except Exception as e:
            logger.error(f"Critical error during table maintenance: {e}")
            return {'error': str(e)}

    def create_partitioned_tables(self) -> Dict[str, str]:
        """
        Create partitioned tables for large datasets
        """
        results = {}

        try:
            # Create partitioned access log table by date
            partition_access_log = text("""
                -- Create partitioned table for access logs
                CREATE TABLE IF NOT EXISTS document_access_log_partitioned (
                    LIKE document_access_log INCLUDING ALL
                ) PARTITION BY RANGE (created_at);

                -- Create partitions for current and future months
                DO $$
                DECLARE
                    start_date date;
                    end_date date;
                    partition_name text;
                BEGIN
                    FOR i IN 0..12 LOOP
                        start_date := date_trunc('month', CURRENT_DATE + interval '1 month' * i);
                        end_date := start_date + interval '1 month';
                        partition_name := 'document_access_log_' || to_char(start_date, 'YYYY_MM');

                        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF document_access_log_partitioned
                                       FOR VALUES FROM (%L) TO (%L)',
                                       partition_name, start_date, end_date);
                    END LOOP;
                END $$;
            """)

            self.db.execute(partition_access_log)
            results['access_log_partitioning'] = 'completed'

            # Create partitioned processing history table
            partition_processing_history = text("""
                -- Create partitioned table for processing history
                CREATE TABLE IF NOT EXISTS processing_history_partitioned (
                    LIKE processing_history INCLUDING ALL
                ) PARTITION BY RANGE (created_at);

                -- Create partitions for current and future quarters
                DO $$
                DECLARE
                    start_date date;
                    end_date date;
                    partition_name text;
                BEGIN
                    FOR i IN 0..8 LOOP
                        start_date := date_trunc('quarter', CURRENT_DATE + interval '3 months' * i);
                        end_date := start_date + interval '3 months';
                        partition_name := 'processing_history_' || to_char(start_date, 'YYYY_Q');

                        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF processing_history_partitioned
                                       FOR VALUES FROM (%L) TO (%L)',
                                       partition_name, start_date, end_date);
                    END LOOP;
                END $$;
            """)

            self.db.execute(partition_processing_history)
            results['processing_history_partitioning'] = 'completed'

            logger.info("Table partitioning completed")
            return results

        except Exception as e:
            logger.error(f"Error creating partitioned tables: {e}")
            return {'error': str(e)}

    def setup_query_performance_monitoring(self) -> Dict[str, str]:
        """
        Set up query performance monitoring
        """
        results = {}

        try:
            # Enable pg_stat_statements if not already enabled
            check_extension = text("SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'")
            extension_exists = self.db.execute(check_extension).fetchone()

            if not extension_exists:
                create_extension = text("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
                self.db.execute(create_extension)
                results['pg_stat_statements'] = 'enabled'
            else:
                results['pg_stat_statements'] = 'already_enabled'

            # Create performance monitoring view
            create_monitoring_view = text("""
                CREATE OR REPLACE VIEW slow_queries AS
                SELECT
                    query,
                    calls,
                    total_time,
                    mean_time,
                    rows,
                    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
                FROM pg_stat_statements
                WHERE mean_time > 1000  -- queries taking more than 1 second on average
                ORDER BY mean_time DESC
                LIMIT 50;
            """)

            self.db.execute(create_monitoring_view)
            results['slow_queries_view'] = 'created'

            # Create index usage monitoring view
            create_index_usage_view = text("""
                CREATE OR REPLACE VIEW index_usage_report AS
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch,
                    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
                FROM pg_stat_user_indexes
                WHERE idx_scan = 0
                ORDER BY pg_relation_size(indexrelid) DESC;
            """)

            self.db.execute(create_index_usage_view)
            results['index_usage_view'] = 'created'

            # Create table size monitoring view
            create_table_size_view = text("""
                CREATE OR REPLACE VIEW table_size_report AS
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS index_size,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_rows,
                    n_dead_tup as dead_rows
                FROM pg_stat_user_tables
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
            """)

            self.db.execute(create_table_size_view)
            results['table_size_view'] = 'created'

            self.db.commit()
            logger.info("Query performance monitoring setup completed")
            return results

        except Exception as e:
            logger.error(f"Error setting up query performance monitoring: {e}")
            return {'error': str(e)}

    def run_full_optimization(self) -> Dict:
        """
        Run complete database optimization suite
        """
        logger.info("Starting full database optimization")

        results = {
            'index_creation': self.create_missing_indexes(),
            'table_maintenance': self.optimize_table_maintenance(),
            'partitioning': self.create_partitioned_tables(),
            'performance_monitoring': self.setup_query_performance_monitoring(),
            'timestamp': datetime.utcnow().isoformat()
        }

        logger.info("Database optimization completed")
        return results


def analyze_database_performance(db: Session) -> Dict:
    """
    Analyze overall database performance and provide recommendations
    """
    optimizer = DatabaseOptimizer(db)

    # Analyze key tables
    tables_to_analyze = [
        'documents',
        'processing_history',
        'document_versions',
        'multimodal_content',
        'document_quality_metrics',
        'document_access_log',
        'processing_jobs'
    ]

    analysis = {
        'table_analysis': {},
        'recommendations': [],
        'performance_summary': {}
    }

    for table in tables_to_analyze:
        analysis['table_analysis'][table] = optimizer.analyze_table_statistics(table)

    # Get slow queries
    try:
        slow_queries_query = text("""
            SELECT query, calls, total_time, mean_time, rows
            FROM pg_stat_statements
            WHERE mean_time > 500
            ORDER BY mean_time DESC
            LIMIT 10
        """)

        slow_queries = db.execute(slow_queries_query).fetchall()
        analysis['performance_summary']['slow_queries'] = [
            {
                'query': row.query[:200] + '...' if len(row.query) > 200 else row.query,
                'calls': row.calls,
                'mean_time_ms': row.mean_time,
                'total_time_ms': row.total_time
            }
            for row in slow_queries
        ]
    except Exception as e:
        logger.warning(f"Could not retrieve slow queries: {e}")
        analysis['performance_summary']['slow_queries'] = []

    # Generate recommendations
    analysis['recommendations'] = _generate_performance_recommendations(analysis)

    return analysis


def _generate_performance_recommendations(analysis: Dict) -> List[str]:
    """Generate performance recommendations based on analysis"""
    recommendations = []

    for table_name, table_info in analysis['table_analysis'].items():
        if 'error' in table_info:
            recommendations.append(f"Fix error in table {table_name}: {table_info['error']}")
            continue

        # Check for unused indexes
        unused_indexes = [idx for idx in table_info.get('index_usage', []) if idx['scans'] == 0]
        if unused_indexes:
            recommendations.append(f"Consider removing unused indexes on {table_name}: {[idx['index_name'] for idx in unused_indexes]}")

        # Check for large tables
        if 'MB' in table_info.get('size_info', {}).get('total_size', ''):
            size_str = table_info['size_info']['total_size']
            if 'GB' in size_str:
                size_gb = float(size_str.replace('GB', '').strip())
                if size_gb > 10:
                    recommendations.append(f"Large table {table_name} ({size_str} GB) - consider partitioning")

    # Add general recommendations
    if analysis['performance_summary'].get('slow_queries'):
        recommendations.append("Found slow queries - review and optimize query performance")

    recommendations.append("Run regular VACUUM and ANALYZE operations")
    recommendations.append("Monitor index usage and remove unused indexes")
    recommendations.append("Consider connection pooling for high-traffic applications")

    return recommendations