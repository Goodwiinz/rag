-- Migration 009: Real-Time Status Query Optimizations
-- Implements comprehensive database optimizations for real-time status tracking and dashboard queries

BEGIN;

-- Enable required extensions for performance optimization
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_prewarm";
CREATE EXTENSION IF NOT EXISTS "pg_buffercache";

-- =================================================================
-- OPTIMIZED INDEXING STRATEGY FOR REAL-TIME QUERIES
-- =================================================================

-- Composite indexes for dashboard status queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_status_org_time
ON documents(organization_id, processing_status, created_at DESC)
WHERE is_deleted = false;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_realtime_dashboard
ON documents(processing_status, processing_progress DESC, last_status_update DESC, organization_id)
WHERE is_deleted = false AND processing_status IN ('pending', 'processing', 'retrying');

-- Partial indexes for common query patterns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_active_processing
ON documents(current_execution_id, processing_progress, last_status_update)
WHERE current_execution_id IS NOT NULL AND processing_status = 'processing';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_failed_retry
ON documents(organization_id, processing_error, created_at DESC)
WHERE processing_status = 'failed' AND retry_count < max_retries;

-- Job execution optimized indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_executions_realtime
ON processing_job_executions(execution_status, overall_progress DESC, started_at DESC, organization_id)
WHERE is_deleted = false;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_executions_worker_queue
ON processing_job_executions(primary_worker_id, execution_status, queued_at ASC)
WHERE execution_status IN ('queued', 'retrying');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_executions_batch_status
ON processing_job_executions(batch_id, execution_status, overall_progress DESC);

-- Stage execution performance indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stage_executions_active
ON stage_executions(stage_status, progress_percentage DESC, last_progress_update DESC)
WHERE stage_status IN ('running', 'pending');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stage_executions_performance
ON stage_executions(stage_key, duration_ms, started_at DESC)
WHERE stage_status = 'completed' AND duration_ms IS NOT NULL;

-- Resource monitoring indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resource_usage_realtime
ON resource_usage_logs(timestamp DESC, job_execution_id, worker_id)
WHERE timestamp >= NOW() - INTERVAL '1 hour';

-- Error monitoring indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_error_logs_recent
ON processing_error_logs(severity, occurred_at DESC)
WHERE occurred_at >= NOW() - INTERVAL '24 hours';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_error_logs_active_jobs
ON processing_error_logs(job_execution_id, error_category, occurred_at DESC);

-- =================================================================
-- PARTITIONING FOR HIGH-VOLUME TABLES
-- =================================================================

-- Partition processing_metrics by month for better performance
CREATE TABLE IF NOT EXISTS processing_metrics_partitioned (
    LIKE processing_metrics INCLUDING ALL
) PARTITION BY RANGE (metric_period_start);

-- Create current and future partitions
DO $$
DECLARE
    start_date DATE;
    i INTEGER;
BEGIN
    start_date := DATE_TRUNC('month', CURRENT_DATE);

    -- Create partitions for current month and next 11 months
    FOR i IN 0..11 LOOP
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS processing_metrics_%s PARTITION OF processing_metrics_partitioned
            FOR VALUES FROM (%L) TO (%L)',
            to_char(start_date + INTERVAL '1 month' * i, 'YYYY_MM'),
            start_date + INTERVAL '1 month' * i,
            start_date + INTERVAL '1 month' * (i + 1)
        );
    END LOOP;
END $$;

-- Partition resource_usage_logs by day for high-frequency data
CREATE TABLE IF NOT EXISTS resource_usage_logs_partitioned (
    LIKE resource_usage_logs INCLUDING ALL
) PARTITION BY RANGE (timestamp);

-- Create partitions for current day and next 30 days
DO $$
DECLARE
    start_date TIMESTAMP;
    i INTEGER;
BEGIN
    start_date := DATE_TRUNC('day', CURRENT_TIMESTAMP);

    -- Create partitions for current day and next 30 days
    FOR i IN 0..30 LOOP
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS resource_usage_logs_%s PARTITION OF resource_usage_logs_partitioned
            FOR VALUES FROM (%L) TO (%L)',
            to_char(start_date + INTERVAL '1 day' * i, 'YYYY_MM_DD'),
            start_date + INTERVAL '1 day' * i,
            start_date + INTERVAL '1 day' * (i + 1)
        );
    END LOOP;
END $$;

-- =================================================================
-- MATERIALIZED VIEWS FOR DASHBOARD PERFORMANCE
-- =================================================================

-- Real-time dashboard summary materialized view
CREATE MATERIALIZED VIEW realtime_dashboard_summary AS
SELECT
    o.id as organization_id,
    o.name as organization_name,

    -- Document counts by status
    COUNT(DISTINCT d.id) FILTER (WHERE d.processing_status = 'pending') as pending_documents,
    COUNT(DISTINCT d.id) FILTER (WHERE d.processing_status = 'processing') as processing_documents,
    COUNT(DISTINCT d.id) FILTER (WHERE d.processing_status = 'completed') as completed_documents,
    COUNT(DISTINCT d.id) FILTER (WHERE d.processing_status = 'failed') as failed_documents,
    COUNT(DISTINCT d.id) FILTER (WHERE d.processing_status = 'retrying') as retrying_documents,

    -- Active job executions
    COUNT(DISTINCT pje.id) FILTER (WHERE pje.execution_status IN ('running', 'queued')) as active_jobs,
    COUNT(DISTINCT pje.id) FILTER (WHERE pje.execution_status = 'failed') as failed_jobs,

    -- Progress metrics
    COALESCE(AVG(d.processing_progress), 0) as avg_processing_progress,
    COALESCE(AVG(pje.overall_progress), 0) as avg_job_progress,

    -- Performance metrics
    COALESCE(AVG(pje.started_at, pje.completed_at), 0) as avg_processing_time_seconds,
    COUNT(DISTINCT pje.primary_worker_id) as active_workers,

    -- Resource usage (last hour)
    COALESCE(AVG(rul.cpu_percent), 0) as avg_cpu_usage,
    COALESCE(AVG(rul.memory_used_mb), 0) as avg_memory_usage,

    -- Error rates (last 24 hours)
    COUNT(DISTINCT pel.id) FILTER (WHERE pel.occurred_at >= NOW() - INTERVAL '24 hours') as recent_errors,
    COUNT(DISTINCT pel.id) FILTER (WHERE pel.severity = 'critical' AND pel.occurred_at >= NOW() - INTERVAL '24 hours') as critical_errors,

    -- Last updated timestamps
    MAX(d.last_status_update) as last_document_update,
    MAX(pje.updated_at) as last_job_update,
    MAX(rul.timestamp) as last_resource_update

FROM organizations o
LEFT JOIN documents d ON o.id = d.organization_id AND d.is_deleted = false
LEFT JOIN processing_job_executions pje ON o.id = pje.organization_id AND pje.is_deleted = false
LEFT JOIN resource_usage_logs rul ON o.id = (SELECT organization_id FROM processing_job_executions WHERE id = rul.job_execution_id LIMIT 1)
    AND rul.timestamp >= NOW() - INTERVAL '1 hour'
LEFT JOIN processing_error_logs pel ON o.id = (SELECT organization_id FROM processing_job_executions WHERE id = pel.job_execution_id LIMIT 1)
WHERE o.is_active = true AND o.is_deleted = false
GROUP BY o.id, o.name;

-- Create unique index for concurrent refresh
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_dashboard_summary_org
ON realtime_dashboard_summary(organization_id);

-- Processing performance trends materialized view
CREATE MATERIALIZED VIEW processing_performance_trends AS
SELECT
    DATE_TRUNC('hour', pje.started_at) as hour_bucket,
    pje.organization_id,
    o.name as organization_name,

    -- Throughput metrics
    COUNT(*) as jobs_completed,
    COUNT(DISTINCT pje.document_id) as documents_processed,
    COUNT(DISTINCT pje.primary_worker_id) as workers_used,

    -- Performance metrics
    AVG(EXTRACT(EPOCH FROM (pje.completed_at - pje.started_at))) as avg_duration_seconds,
    MIN(EXTRACT(EPOCH FROM (pje.completed_at - pje.started_at))) as min_duration_seconds,
    MAX(EXTRACT(EPOCH FROM (pje.completed_at - pje.started_at))) as max_duration_seconds,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (pje.completed_at - pje.started_at))) as median_duration_seconds,

    -- Success rates
    COUNT(*) FILTER (WHERE pje.execution_status = 'completed') as successful_jobs,
    COUNT(*) FILTER (WHERE pje.execution_status = 'failed') as failed_jobs,
    ROUND(COUNT(*) FILTER (WHERE pje.execution_status = 'completed') * 100.0 / NULLIF(COUNT(*), 0), 2) as success_rate_percent,

    -- Quality metrics
    AVG(pme.overall_quality_score) as avg_quality_score,
    AVG(pme.accuracy_score) as avg_accuracy_score,

    -- Resource metrics
    AVG(pme.total_memory_mb) as avg_memory_usage,
    AVG(pme.peak_cpu_percent) as avg_cpu_usage,
    SUM(pme.total_cost_usd) as total_cost_usd

FROM processing_job_executions pje
JOIN organizations o ON pje.organization_id = o.id
LEFT JOIN processing_metrics pme ON pje.id = pme.job_execution_id
WHERE pje.started_at >= NOW() - INTERVAL '7 days'
    AND pje.execution_status IN ('completed', 'failed')
    AND pje.is_deleted = false
GROUP BY DATE_TRUNC('hour', pje.started_at), pje.organization_id, o.name
ORDER BY hour_bucket DESC, organization_name;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_performance_trends_hour_org
ON processing_performance_trends(hour_bucket DESC, organization_id);

-- =================================================================
-- STORED PROCEDURES FOR REAL-TIME OPERATIONS
-- =================================================================

-- Function to get real-time dashboard data for an organization
CREATE OR REPLACE FUNCTION get_realtime_dashboard_data(p_organization_id UUID)
RETURNS TABLE(
    pending_documents BIGINT,
    processing_documents BIGINT,
    completed_documents BIGINT,
    failed_documents BIGINT,
    retrying_documents BIGINT,
    active_jobs BIGINT,
    avg_progress DECIMAL(5,2),
    avg_cpu_usage DECIMAL(5,2),
    avg_memory_usage DECIMAL(5,2),
    recent_errors BIGINT,
    critical_errors BIGINT,
    estimated_completion_time TIMESTAMPTZ,
    throughput_per_hour DECIMAL(10,2)
) AS $$
BEGIN
    RETURN QUERY
    WITH current_status AS (
        SELECT
            COUNT(DISTINCT d.id) FILTER (WHERE d.processing_status = 'pending') as pending,
            COUNT(DISTINCT d.id) FILTER (WHERE d.processing_status = 'processing') as processing,
            COUNT(DISTINCT d.id) FILTER (WHERE d.processing_status = 'completed') as completed,
            COUNT(DISTINCT d.id) FILTER (WHERE d.processing_status = 'failed') as failed,
            COUNT(DISTINCT d.id) FILTER (WHERE d.processing_status = 'retrying') as retrying,
            COALESCE(AVG(d.processing_progress), 0) as avg_doc_progress,
            MAX(d.last_status_update) as last_update
        FROM documents d
        WHERE d.organization_id = p_organization_id
            AND d.is_deleted = false
    ),
    job_status AS (
        SELECT
            COUNT(DISTINCT je.id) FILTER (WHERE je.execution_status IN ('running', 'queued')) as active,
            COALESCE(AVG(je.overall_progress), 0) as avg_job_progress,
            COUNT(DISTINCT je.primary_worker_id) as active_workers
        FROM processing_job_executions je
        WHERE je.organization_id = p_organization_id
            AND je.is_deleted = false
            AND je.execution_status IN ('running', 'queued', 'retrying')
    ),
    resource_status AS (
        SELECT
            COALESCE(AVG(rul.cpu_percent), 0) as avg_cpu,
            COALESCE(AVG(rul.memory_used_mb), 0) as avg_memory
        FROM resource_usage_logs rul
        WHERE rul.timestamp >= NOW() - INTERVAL '1 hour'
            AND rul.job_execution_id IN (
                SELECT id FROM processing_job_executions
                WHERE organization_id = p_organization_id
            )
    ),
    error_status AS (
        SELECT
            COUNT(*) FILTER (WHERE severity IN ('error', 'critical', 'fatal')) as recent_errors,
            COUNT(*) FILTER (WHERE severity = 'critical') as critical_errors
        FROM processing_error_logs pel
        WHERE pel.occurred_at >= NOW() - INTERVAL '24 hours'
            AND pel.job_execution_id IN (
                SELECT id FROM processing_job_executions
                WHERE organization_id = p_organization_id
            )
    ),
    throughput_status AS (
        SELECT
            COUNT(DISTINCT document_id) as documents_per_hour
        FROM processing_job_executions
        WHERE organization_id = p_organization_id
            AND execution_status = 'completed'
            AND completed_at >= NOW() - INTERVAL '1 hour'
    )
    SELECT
        cs.pending,
        cs.processing,
        cs.completed,
        cs.failed,
        cs.retrying,
        js.active,
        GREATEST(cs.avg_doc_progress, js.avg_job_progress),
        rs.avg_cpu,
        rs.avg_memory,
        es.recent_errors,
        es.critical_errors,
        NOW() + (
            CASE
                WHEN cs.processing > 0 THEN
                    (SELECT AVG(estimated_remaining_seconds)
                     FROM processing_job_executions
                     WHERE organization_id = p_organization_id
                        AND execution_status = 'running'
                        AND estimated_remaining_seconds IS NOT NULL)
                ELSE NULL
            END || ' seconds')::INTERVAL,
        ts.documents_per_hour * 1.0
    FROM current_status cs, job_status js, resource_status rs, error_status es, throughput_status ts;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get processing queue status
CREATE OR REPLACE FUNCTION get_processing_queue_status(p_limit INTEGER DEFAULT 100)
RETURNS TABLE(
    document_id UUID,
    document_title VARCHAR,
    processing_status VARCHAR(100),
    processing_progress DECIMAL(5,2),
    current_stage VARCHAR(100),
    estimated_remaining_seconds INTEGER,
    queue_time_seconds INTEGER,
    priority INTEGER,
    worker_id VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.title,
        d.processing_status,
        d.processing_progress,
        d.current_processing_stage,
        d.estimated_remaining_seconds,
        EXTRACT(EPOCH FROM (NOW() - d.created_at))::INTEGER as queue_time,
        d.processing_priority,
        pje.primary_worker_id
    FROM documents d
    LEFT JOIN processing_job_executions pje ON d.current_execution_id = pje.execution_id
    WHERE d.processing_status IN ('pending', 'processing', 'retrying')
        AND d.is_deleted = false
    ORDER BY
        d.processing_priority DESC,
        d.processing_status ASC,
        d.created_at ASC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to update document processing progress atomically
CREATE OR REPLACE FUNCTION update_document_progress(
    p_document_id UUID,
    p_progress DECIMAL(5,2),
    p_stage VARCHAR(100) DEFAULT NULL,
    p_remaining_seconds INTEGER DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE documents
    SET
        processing_progress = p_progress,
        current_processing_stage = COALESCE(p_stage, current_processing_stage),
        estimated_remaining_seconds = COALESCE(p_remaining_seconds, estimated_remaining_seconds),
        processing_error = COALESCE(p_error_message, processing_error),
        processing_status = CASE
            WHEN p_error_message IS NOT NULL THEN 'failed'
            WHEN p_progress >= 100 THEN 'completed'
            WHEN p_progress > 0 THEN 'processing'
            ELSE 'pending'
        END,
        last_status_update = NOW()
    WHERE id = p_document_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =================================================================
-- DATABASE TRIGGERS FOR AUTOMATIC MAINTENANCE
-- =================================================================

-- Trigger to automatically refresh materialized views
CREATE OR REPLACE FUNCTION refresh_dashboard_materialized_views()
RETURNS TRIGGER AS $$
BEGIN
    -- Refresh only if data has changed significantly
    IF TG_OP = 'UPDATE' AND (
        OLD.processing_status != NEW.processing_status OR
        OLD.processing_progress != NEW.processing_progress OR
        NEW.processing_status IN ('completed', 'failed')
    ) THEN
        PERFORM pg_notify('dashboard_refresh', json_build_object(
            'table', TG_TABLE_NAME,
            'operation', TG_OP,
            'document_id', NEW.id,
            'organization_id', NEW.organization_id,
            'status', NEW.processing_status
        )::text);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER document_status_change_trigger
    AFTER UPDATE OF processing_status, processing_progress ON documents
    FOR EACH ROW
    EXECUTE FUNCTION refresh_dashboard_materialized_views();

-- Function to clean up old resource usage logs
CREATE OR REPLACE FUNCTION cleanup_old_resource_logs()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM resource_usage_logs
    WHERE timestamp < NOW() - INTERVAL '7 days';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- =================================================================
-- PERFORMANCE MONITORING FUNCTIONS
-- =================================================================

-- Function to get slow queries
CREATE OR REPLACE FUNCTION get_slow_processing_queries(p_threshold_ms INTEGER DEFAULT 1000)
RETURNS TABLE(
    query TEXT,
    calls BIGINT,
    total_time DOUBLE PRECISION,
    mean_time DOUBLE PRECISION,
    rows BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pg_stat_statements.query,
        pg_stat_statements.calls,
        pg_stat_statements.total_exec_time,
        pg_stat_statements.mean_exec_time,
        pg_stat_statements.rows
    FROM pg_stat_statements
    WHERE pg_stat_statements.mean_exec_time > p_threshold_ms
        AND pg_stat_statements.query LIKE '%processing_%'
    ORDER BY pg_stat_statements.mean_exec_time DESC
    LIMIT 20;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get database performance metrics
CREATE OR REPLACE FUNCTION get_database_performance_metrics()
RETURNS TABLE(
    metric_name VARCHAR(100),
    metric_value DECIMAL(15,6),
    metric_unit VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        'active_connections'::VARCHAR(100),
        COUNT(*)::DECIMAL(15,6),
        'connections'::VARCHAR(50)
    FROM pg_stat_activity
    WHERE state = 'active';

    RETURN QUERY
    SELECT
        'cache_hit_ratio'::VARCHAR(100),
        ROUND((blks_hit::DECIMAL / NULLIF(blks_hit + blks_read, 0)) * 100, 2),
        'percent'::VARCHAR(50)
    FROM pg_stat_database
    WHERE datname = current_database();

    RETURN QUERY
    SELECT
        'transaction_rate'::VARCHAR(100),
        (xact_commit + xact_rollback)::DECIMAL / EXTRACT(EPOCH FROM (NOW() - stats_reset)),
        'transactions_per_second'::VARCHAR(50)
    FROM pg_stat_database
    WHERE datname = current_database();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =================================================================
-- CONNECTION POOLING CONFIGURATION
-- =================================================================

-- Create a function to monitor connection pool usage
CREATE OR REPLACE FUNCTION get_connection_pool_stats()
RETURNS TABLE(
    pool_name VARCHAR(100),
    active_connections INTEGER,
    idle_connections INTEGER,
    total_connections INTEGER,
    max_connections INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        'main_pool'::VARCHAR(100),
        COUNT(*) FILTER (WHERE state = 'active'),
        COUNT(*) FILTER (WHERE state = 'idle'),
        COUNT(*),
        (SELECT setting::INTEGER FROM pg_settings WHERE name = 'max_connections')
    FROM pg_stat_activity
    WHERE datname = current_database();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =================================================================
-- FINAL SETUP
-- =================================================================

-- Grant execute permissions to application role
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated_users;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO authenticated_users;
GRANT SELECT ON ALL MATERIALIZED VIEWS IN SCHEMA public TO authenticated_users;

-- Create a scheduled job for maintenance (requires pg_cron extension)
-- SELECT cron.schedule('cleanup-old-logs', '0 2 * * *', 'SELECT cleanup_old_resource_logs();');
-- SELECT cron.schedule('refresh-dashboard', '*/5 * * * *', 'REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_dashboard_summary;');

-- Analyze tables for better query planning
ANALYZE documents;
ANALYZE processing_job_executions;
ANALYZE stage_executions;
ANALYZE resource_usage_logs;
ANALYZE processing_error_logs;
ANALYZE realtime_dashboard_summary;
ANALYZE processing_performance_trends;

COMMIT;