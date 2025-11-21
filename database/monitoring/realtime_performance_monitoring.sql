-- Real-Time Performance Monitoring and Connection Pooling Setup
-- Comprehensive monitoring solution for database performance and connection management

-- =================================================================
-- PERFORMANCE MONITORING VIEWS
-- =================================================================

-- Real-time database performance overview
CREATE OR REPLACE VIEW realtime_database_performance AS
WITH connection_stats AS (
    SELECT
        count(*) as total_connections,
        count(*) FILTER (WHERE state = 'active') as active_connections,
        count(*) FILTER (WHERE state = 'idle') as idle_connections,
        count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
        avg(EXTRACT(EPOCH FROM (now() - query_start))) FILTER (WHERE state = 'active') as avg_query_duration_seconds,
        max(EXTRACT(EPOCH FROM (now() - query_start))) FILTER (WHERE state = 'active') as max_query_duration_seconds
    FROM pg_stat_activity
    WHERE datname = current_database()
),
buffer_cache_stats AS (
    SELECT
        sum(blks_hit) as total_hits,
        sum(blks_read) as total_reads,
        round(sum(blks_hit)::decimal / NULLIF(sum(blks_hit + blks_read), 0) * 100, 2) as cache_hit_ratio_percent
    FROM pg_stat_database
    WHERE datname = current_database()
),
lock_stats AS (
    SELECT
        count(*) as total_locks,
        count(*) FILTER (WHERE granted = false) as waiting_locks,
        count(DISTINCT pid) as blocked_sessions
    FROM pg_locks
    WHERE database = (SELECT oid FROM pg_database WHERE datname = current_database())
),
size_stats AS (
    SELECT
        pg_size_pretty(pg_database_size(current_database())) as database_size,
        pg_size_pretty(sum(pg_relation_size(schemaname||'.'||tablename))) as total_table_size,
        pg_size_pretty(sum(pg_relation_size(schemaname||'.'||indexname))) as total_index_size
    FROM pg_tables
    CROSS JOIN pg_indexes
    WHERE schemaname = 'public'
)
SELECT
    NOW() as monitoring_timestamp,
    cs.total_connections,
    cs.active_connections,
    cs.idle_connections,
    cs.idle_in_transaction,
    cs.avg_query_duration_seconds,
    cs.max_query_duration_seconds,
    bcs.total_hits,
    bcs.total_reads,
    bcs.cache_hit_ratio_percent,
    ls.total_locks,
    ls.waiting_locks,
    ls.blocked_sessions,
    ss.database_size,
    ss.total_table_size,
    ss.total_index_size,
    CASE
        WHEN cs.active_connections > (SELECT setting::integer FROM pg_settings WHERE name = 'max_connections') * 0.8 THEN 'WARNING'
        WHEN bcs.cache_hit_ratio_percent < 95 THEN 'ATTENTION'
        WHEN ls.blocked_sessions > 5 THEN 'CRITICAL'
        WHEN cs.max_query_duration_seconds > 30 THEN 'ATTENTION'
        ELSE 'HEALTHY'
    END as overall_health_status
FROM connection_stats cs, buffer_cache_stats bcs, lock_stats ls, size_stats ss;

-- Slow queries monitoring view
CREATE OR REPLACE VIEW realtime_slow_queries AS
SELECT
    pid,
    now() - query_start as duration_seconds,
    now() - query_start as duration_interval,
    state,
    wait_event_type,
    wait_event,
    substring(query, 1, 200) as query_preview,
    usename,
    application_name,
    client_addr,
    datname,
    CASE
        WHEN now() - query_start > INTERVAL '5 minutes' THEN 'CRITICAL'
        WHEN now() - query_start > INTERVAL '2 minutes' THEN 'WARNING'
        WHEN now() - query_start > INTERVAL '30 seconds' THEN 'ATTENTION'
        ELSE 'NORMAL'
    END as performance_category
FROM pg_stat_activity
WHERE state = 'active'
    AND datname = current_database()
    AND query !~ '^.*pg_stat_activity.*$'
    AND now() - query_start > INTERVAL '10 seconds'
ORDER BY now() - query_start DESC;

-- Real-time processing performance metrics
CREATE OR REPLACE VIEW realtime_processing_performance AS
WITH processing_throughput AS (
    SELECT
        COUNT(*) FILTER (WHERE execution_status = 'completed' AND completed_at >= NOW() - INTERVAL '1 hour') as jobs_completed_hour,
        COUNT(*) FILTER (WHERE execution_status = 'started' AND started_at >= NOW() - INTERVAL '1 hour') as jobs_started_hour,
        COUNT(DISTINCT document_id) FILTER (WHERE execution_status = 'completed' AND completed_at >= NOW() - INTERVAL '1 hour') as documents_processed_hour,
        COUNT(DISTINCT primary_worker_id) FILTER (WHERE execution_status IN ('running', 'queued')) as active_workers,
        ROUND(AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) FILTER (WHERE execution_status = 'completed' AND completed_at >= NOW() - INTERVAL '1 hour'), 2) as avg_processing_time_seconds
    FROM processing_job_executions
    WHERE created_at >= NOW() - INTERVAL '24 hours'
        AND is_deleted = false
),
error_rates AS (
    SELECT
        COUNT(*) FILTER (WHERE execution_status = 'failed' AND completed_at >= NOW() - INTERVAL '1 hour') as failed_jobs_hour,
        COUNT(DISTINCT pel.id) FILTER (WHERE pel.occurred_at >= NOW() - INTERVAL '1 hour' AND pel.severity IN ('error', 'critical')) as error_count_hour,
        COUNT(DISTINCT pel.id) FILTER (WHERE pel.occurred_at >= NOW() - INTERVAL '1 hour' AND pel.severity = 'critical') as critical_errors_hour
    FROM processing_job_executions pje
    LEFT JOIN processing_error_logs pel ON pje.id = pel.job_execution_id
    WHERE pje.created_at >= NOW() - INTERVAL '24 hours'
        AND pje.is_deleted = false
),
resource_utilization AS (
    SELECT
        AVG(cpu_percent) as avg_cpu_usage,
        MAX(cpu_percent) as max_cpu_usage,
        AVG(memory_used_mb) as avg_memory_usage,
        MAX(memory_used_mb) as max_memory_usage,
        COUNT(DISTINCT worker_id) as workers_monitored
    FROM resource_usage_logs
    WHERE timestamp >= NOW() - INTERVAL '30 minutes'
),
queue_status AS (
    SELECT
        COUNT(*) FILTER (WHERE processing_status = 'pending') as pending_count,
        COUNT(*) FILTER (WHERE processing_status = 'processing') as processing_count,
        COUNT(*) FILTER (WHERE processing_status = 'retrying') as retrying_count,
        COUNT(*) FILTER (WHERE processing_status = 'failed') as failed_count,
        AVG(processing_progress) FILTER (WHERE processing_status = 'processing') as avg_progress_percentage
    FROM documents
    WHERE is_deleted = false
)
SELECT
    NOW() as monitoring_timestamp,

    -- Throughput metrics
    pt.jobs_completed_hour,
    pt.jobs_started_hour,
    pt.documents_processed_hour,
    pt.active_workers,
    pt.avg_processing_time_seconds,

    -- Error metrics
    er.failed_jobs_hour,
    er.error_count_hour,
    er.critical_errors_hour,
    ROUND(pt.jobs_completed_hour * 100.0 / NULLIF(pt.jobs_started_hour, 0), 2) as success_rate_percent,

    -- Resource metrics
    ROUND(ru.avg_cpu_usage, 2) as avg_cpu_usage_percent,
    ru.max_cpu_usage,
    ROUND(ru.avg_memory_usage, 2) as avg_memory_usage_mb,
    ru.max_memory_usage,
    ru.workers_monitored,

    -- Queue metrics
    qs.pending_count,
    qs.processing_count,
    qs.retrying_count,
    qs.failed_count,
    ROUND(COALESCE(qs.avg_progress_percentage, 0), 2) as avg_queue_progress_percent,

    -- Performance indicators
    CASE
        WHEN er.critical_errors_hour > 0 THEN 'CRITICAL'
        WHEN er.error_count_hour > 10 OR pt.success_rate_percent < 80 THEN 'WARNING'
        WHEN ru.avg_cpu_usage > 90 OR ru.max_memory_usage > 16384 THEN 'ATTENTION'
        WHEN qs.pending_count > 100 THEN 'HIGH_LOAD'
        ELSE 'HEALTHY'
    END as system_performance_status,

    -- Calculated throughput score
    LEAST(100, GREATEST(0,
        (pt.jobs_completed_hour * 2) +
        (CASE WHEN pt.success_rate_percent > 95 THEN 20 ELSE pt.success_rate_percent * 0.2 END) +
        (CASE WHEN ru.avg_cpu_usage < 80 THEN 20 - ru.avg_cpu_usage * 0.25 ELSE 0 END) +
        (CASE WHEN er.error_count_hour = 0 THEN 10 ELSE GREATEST(0, 10 - er.error_count_hour) END) +
        (CASE WHEN qs.pending_count < 20 THEN 10 ELSE GREATEST(0, 10 - qs.pending_count * 0.1) END)
    )) as performance_score

FROM processing_throughput pt, error_rates er, resource_utilization ru, queue_status qs;

-- =================================================================
-- CONNECTION POOLING MONITORING
-- =================================================================

-- Connection pool status view
CREATE OR REPLACE VIEW connection_pool_status AS
WITH pool_metrics AS (
    SELECT
        application_name,
        count(*) as active_connections,
        count(*) FILTER (WHERE state = 'active') as active_queries,
        count(*) FILTER (WHERE state = 'idle') as idle_connections,
        count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction,
        avg(EXTRACT(EPOCH FROM (now() - query_start))) FILTER (WHERE state = 'active') as avg_query_time_seconds,
        max(EXTRACT(EPOCH FROM (now() - query_start))) FILTER (WHERE state = 'active') as max_query_time_seconds
    FROM pg_stat_activity
    WHERE datname = current_database()
        AND application_name IS NOT NULL
    GROUP BY application_name
),
total_pool AS (
    SELECT
        count(*) as total_connections,
        count(*) FILTER (WHERE state = 'active') as total_active,
        (SELECT setting::integer FROM pg_settings WHERE name = 'max_connections') as max_connections,
        ROUND(count(*) * 100.0 / (SELECT setting::integer FROM pg_settings WHERE name = 'max_connections'), 2) as utilization_percent
    FROM pg_stat_activity
    WHERE datname = current_database()
)
SELECT
    NOW() as monitoring_timestamp,
    tp.total_connections,
    tp.total_active,
    tp.max_connections,
    tp.utilization_percent,
    json_agg(
        json_build_object(
            'application_name', pm.application_name,
            'active_connections', pm.active_connections,
            'active_queries', pm.active_queries,
            'idle_connections', pm.idle_connections,
            'idle_in_transaction', pm.idle_in_transaction,
            'avg_query_time_seconds', ROUND(pm.avg_query_time_seconds, 3),
            'max_query_time_seconds', ROUND(pm.max_query_time_seconds, 3),
            'connection_efficiency', CASE
                WHEN pm.active_connections > 0 THEN
                    ROUND(pm.active_queries * 100.0 / pm.active_connections, 2)
                ELSE 0
            END
        )
        ORDER BY pm.active_connections DESC
    ) as application_breakdown,
    CASE
        WHEN tp.utilization_percent > 90 THEN 'CRITICAL'
        WHEN tp.utilization_percent > 80 THEN 'WARNING'
        WHEN tp.utilization_percent > 70 THEN 'ATTENTION'
        ELSE 'HEALTHY'
    END as pool_health_status
FROM pool_metrics pm, total_pool tp;

-- =================================================================
-- PERFORMANCE ALERT FUNCTIONS
-- =================================================================

-- Function to check for performance issues and generate alerts
CREATE OR REPLACE FUNCTION generate_performance_alerts()
RETURNS TABLE(
    alert_type VARCHAR(50),
    severity VARCHAR(20),
    message TEXT,
    metric_value DECIMAL(15,6),
    threshold_value DECIMAL(15,6),
    alert_timestamp TIMESTAMPTZ,
    details JSONB
) AS $$
BEGIN
    -- Check for slow queries
    RETURN QUERY
    SELECT
        'slow_query'::VARCHAR(50),
        CASE
            WHEN duration_seconds > 300 THEN 'critical'::VARCHAR(20)
            WHEN duration_seconds > 120 THEN 'warning'::VARCHAR(20)
            ELSE 'attention'::VARCHAR(20)
        END,
        'Slow query detected: ' || substring(query, 1, 100) || '...',
        EXTRACT(EPOCH FROM (now() - query_start))::DECIMAL(15,6),
        30.0::DECIMAL(15,6),
        NOW() as alert_timestamp,
        json_build_object(
            'pid', pid,
            'duration_seconds', EXTRACT(EPOCH FROM (now() - query_start)),
            'user', usename,
            'application', application_name,
            'client_addr', client_addr,
            'wait_event', wait_event
        ) as details
    FROM pg_stat_activity
    WHERE state = 'active'
        AND datname = current_database()
        AND now() - query_start > INTERVAL '30 seconds';

    -- Check for high memory usage
    RETURN QUERY
    SELECT
        'high_memory_usage'::VARCHAR(50),
        CASE
            WHEN avg_memory_usage_mb > 8192 THEN 'critical'::VARCHAR(20)
            WHEN avg_memory_usage_mb > 6144 THEN 'warning'::VARCHAR(20)
            ELSE 'attention'::VARCHAR(20)
        END,
        'High memory usage detected in processing workers',
        avg_memory_usage_mb::DECIMAL(15,6),
        4096.0::DECIMAL(15,6),
        NOW() as alert_timestamp,
        json_build_object(
            'avg_memory_usage_mb', avg_memory_usage_mb,
            'max_memory_usage_mb', max_memory_usage_mb,
            'workers_monitored', workers_monitored
        ) as details
    FROM realtime_processing_performance
    WHERE avg_memory_usage_mb > 4096;

    -- Check for connection pool exhaustion
    RETURN QUERY
    SELECT
        'connection_pool_exhaustion'::VARCHAR(50),
        CASE
            WHEN utilization_percent > 95 THEN 'critical'::VARCHAR(20)
            WHEN utilization_percent > 85 THEN 'warning'::VARCHAR(20)
            ELSE 'attention'::VARCHAR(20)
        END,
        'Connection pool utilization is high',
        utilization_percent::DECIMAL(15,6),
        80.0::DECIMAL(15,6),
        NOW() as alert_timestamp,
        json_build_object(
            'total_connections', total_connections,
            'max_connections', max_connections,
            'utilization_percent', utilization_percent
        ) as details
    FROM connection_pool_status
    WHERE utilization_percent > 80;

    -- Check for cache hit ratio degradation
    RETURN QUERY
    SELECT
        'cache_hit_ratio_low'::VARCHAR(50),
        CASE
            WHEN cache_hit_ratio_percent < 90 THEN 'critical'::VARCHAR(20)
            WHEN cache_hit_ratio_percent < 95 THEN 'warning'::VARCHAR(20)
            ELSE 'attention'::VARCHAR(20)
        END,
        'Database cache hit ratio is below optimal threshold',
        cache_hit_ratio_percent::DECIMAL(15,6),
        98.0::DECIMAL(15,6),
        NOW() as alert_timestamp,
        json_build_object(
            'cache_hit_ratio_percent', cache_hit_ratio_percent,
            'total_hits', total_hits,
            'total_reads', total_reads
        ) as details
    FROM realtime_database_performance
    WHERE cache_hit_ratio_percent < 98;

    -- Check for processing queue buildup
    RETURN QUERY
    SELECT
        'processing_queue_buildup'::VARCHAR(50),
        CASE
            WHEN pending_count > 200 THEN 'critical'::VARCHAR(20)
            WHEN pending_count > 100 THEN 'warning'::VARCHAR(20)
            ELSE 'attention'::VARCHAR(20)
        END,
        'Document processing queue is building up',
        pending_count::DECIMAL(15,6),
        50.0::DECIMAL(15,6),
        NOW() as alert_timestamp,
        json_build_object(
            'pending_count', pending_count,
            'processing_count', processing_count,
            'retrying_count', retrying_count,
            'failed_count', failed_count,
            'active_workers', active_workers
        ) as details
    FROM realtime_processing_performance
    WHERE pending_count > 50;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get performance statistics summary
CREATE OR REPLACE FUNCTION get_performance_summary(p_time_interval INTERVAL DEFAULT INTERVAL '1 hour')
RETURNS TABLE(
    metric_category VARCHAR(50),
    metric_name VARCHAR(100),
    current_value DECIMAL(15,6),
    previous_value DECIMAL(15,6),
    trend VARCHAR(20),
    status VARCHAR(20)
) AS $$
BEGIN
    RETURN QUERY
    -- Database performance metrics
    WITH current_db_stats AS (
        SELECT cache_hit_ratio_percent, active_connections, total_connections
        FROM realtime_database_performance
    ),
    previous_db_stats AS (
        SELECT
            ROUND(sum(blks_hit)::decimal / NULLIF(sum(blks_hit + blks_read), 0) * 100, 2) as cache_hit_ratio_percent,
            COUNT(*) FILTER (WHERE state = 'active') as active_connections,
            COUNT(*) as total_connections
        FROM pg_stat_database psd
        JOIN pg_stat_activity psa ON psd.datname = psa.datname
        WHERE psd.datname = current_database()
            AND psd.stats_reset >= NOW() - p_time_interval * 2
            AND psd.stats_reset < NOW() - p_time_interval
    )
    SELECT
        'database'::VARCHAR(50),
        'cache_hit_ratio_percent'::VARCHAR(100),
        cds.cache_hit_ratio_percent,
        COALESCE(pds.cache_hit_ratio_percent, 0),
        CASE
            WHEN cds.cache_hit_ratio_percent > COALESCE(pds.cache_hit_ratio_percent, 0) THEN 'improving'
            WHEN cds.cache_hit_ratio_percent < COALESCE(pds.cache_hit_ratio_percent, 0) THEN 'degrading'
            ELSE 'stable'
        END::VARCHAR(20),
        CASE
            WHEN cds.cache_hit_ratio_percent >= 99 THEN 'excellent'
            WHEN cds.cache_hit_ratio_percent >= 95 THEN 'good'
            WHEN cds.cache_hit_ratio_percent >= 90 THEN 'fair'
            ELSE 'poor'
        END::VARCHAR(20)
    FROM current_db_stats cds
    LEFT JOIN previous_db_stats pds ON true;

    -- Processing performance metrics
    WITH current_processing_stats AS (
        SELECT jobs_completed_hour, success_rate_percent, avg_processing_time_seconds
        FROM realtime_processing_performance
    ),
    previous_processing_stats AS (
        SELECT
            COUNT(*) FILTER (WHERE execution_status = 'completed' AND completed_at >= NOW() - p_time_interval * 2 AND completed_at < NOW() - p_time_interval) as jobs_completed_hour,
            ROUND(COUNT(*) FILTER (WHERE execution_status = 'completed') * 100.0 / NULLIF(COUNT(*), 0), 2) as success_rate_percent,
            ROUND(AVG(EXTRACT(EPOCH FROM (completed_at - started_at))), 2) as avg_processing_time_seconds
        FROM processing_job_executions
        WHERE created_at >= NOW() - p_time_interval * 2
            AND is_deleted = false
    )
    SELECT
        'processing'::VARCHAR(50),
        'jobs_completed_per_hour'::VARCHAR(100),
        cps.jobs_completed_hour::DECIMAL(15,6),
        COALESCE(pps.jobs_completed_hour, 0),
        CASE
            WHEN cps.jobs_completed_hour > COALESCE(pps.jobs_completed_hour, 0) THEN 'improving'
            WHEN cps.jobs_completed_hour < COALESCE(pps.jobs_completed_hour, 0) THEN 'degrading'
            ELSE 'stable'
        END::VARCHAR(20),
        CASE
            WHEN cps.jobs_completed_hour >= 50 THEN 'excellent'
            WHEN cps.jobs_completed_hour >= 25 THEN 'good'
            WHEN cps.jobs_completed_hour >= 10 THEN 'fair'
            ELSE 'poor'
        END::VARCHAR(20)
    FROM current_processing_stats cps
    LEFT JOIN previous_processing_stats pps ON true

    UNION ALL

    SELECT
        'processing'::VARCHAR(50),
        'success_rate_percent'::VARCHAR(100),
        cps.success_rate_percent::DECIMAL(15,6),
        COALESCE(pps.success_rate_percent, 0),
        CASE
            WHEN cps.success_rate_percent > COALESCE(pps.success_rate_percent, 0) THEN 'improving'
            WHEN cps.success_rate_percent < COALESCE(pps.success_rate_percent, 0) THEN 'degrading'
            ELSE 'stable'
        END::VARCHAR(20),
        CASE
            WHEN cps.success_rate_percent >= 99 THEN 'excellent'
            WHEN cps.success_rate_percent >= 95 THEN 'good'
            WHEN cps.success_rate_percent >= 90 THEN 'fair'
            ELSE 'poor'
        END::VARCHAR(20)
    FROM current_processing_stats cps
    LEFT JOIN previous_processing_stats pps ON true;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =================================================================
-- AUTOMATED MAINTENANCE PROCEDURES
-- =================================================================

-- Procedure to analyze tables and update statistics
CREATE OR REPLACE PROCEDURE analyze_critical_tables()
LANGUAGE plpgsql
AS $$
BEGIN
    -- Analyze high-traffic tables for better query planning
    RAISE NOTICE 'Analyzing critical tables for performance optimization...';

    EXECUTE 'ANALYZE documents';
    EXECUTE 'ANALYZE processing_job_executions';
    EXECUTE 'ANALYZE stage_executions';
    EXECUTE 'ANALYZE agent_executions';
    EXECUTE 'ANALYZE resource_usage_logs';
    EXECUTE 'ANALYZE processing_error_logs';
    EXECUTE 'ANALYZE document_status_snapshots';

    -- Analyze materialized views
    EXECUTE 'ANALYZE realtime_org_dashboard_summary';
    EXECUTE 'ANALYZE realtime_worker_performance';
    EXECUTE 'ANALYZE realtime_processing_queue';
    EXECUTE 'ANALYZE realtime_error_analysis';

    RAISE NOTICE 'Critical tables analysis completed';
END;
$$;

-- Procedure to clean up old monitoring data
CREATE OR REPLACE PROCEDURE cleanup_old_monitoring_data()
LANGUAGE plpgsql
AS $$
DECLARE
    v_deleted_resource_logs INTEGER;
    v_deleted_error_logs INTEGER;
    v_deleted_status_snapshots INTEGER;
    v_deleted_processing_metrics INTEGER;
BEGIN
    -- Clean up old resource usage logs (keep 7 days)
    DELETE FROM resource_usage_logs
    WHERE timestamp < NOW() - INTERVAL '7 days';
    GET DIAGNOSTICS v_deleted_resource_logs = ROW_COUNT;

    -- Clean up old error logs (keep 30 days, except critical ones)
    DELETE FROM processing_error_logs
    WHERE occurred_at < NOW() - INTERVAL '30 days'
        AND severity NOT IN ('critical', 'fatal');
    GET DIAGNOSTICS v_deleted_error_logs = ROW_COUNT;

    -- Clean up old status snapshots (keep 7 days)
    DELETE FROM document_status_snapshots
    WHERE created_at < NOW() - INTERVAL '7 days';
    GET DIAGNOSTICS v_deleted_status_snapshots = ROW_COUNT;

    -- Clean up old processing metrics (keep 90 days)
    DELETE FROM processing_metrics
    WHERE metric_period_end < NOW() - INTERVAL '90 days';
    GET DIAGNOSTICS v_deleted_processing_metrics = ROW_COUNT;

    RAISE NOTICE 'Monitoring data cleanup completed. Deleted: resource_logs=%s, error_logs=%s, status_snapshots=%s, processing_metrics=%s',
        v_deleted_resource_logs, v_deleted_error_logs, v_deleted_status_snapshots, v_deleted_processing_metrics;
END;
$$;

-- Grant permissions
GRANT SELECT ON ALL VIEWS IN SCHEMA public TO authenticated_users;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated_users;
GRANT EXECUTE ON ALL PROCEDURES IN SCHEMA public TO authenticated_users;