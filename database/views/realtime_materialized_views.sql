-- Real-Time Materialized Views for Dashboard Performance
-- Optimized materialized views with efficient refresh strategies

-- =================================================================
-- REAL-TIME DASHBOARD VIEWS
-- =================================================================

-- Organization Real-Time Dashboard Summary
-- Materialized view for fast organization dashboard queries
CREATE MATERIALIZED VIEW realtime_org_dashboard_summary AS
WITH org_document_stats AS (
    SELECT
        organization_id,
        COUNT(*) FILTER (WHERE processing_status = 'pending') as pending_count,
        COUNT(*) FILTER (WHERE processing_status = 'processing') as processing_count,
        COUNT(*) FILTER (WHERE processing_status = 'completed') as completed_count,
        COUNT(*) FILTER (WHERE processing_status = 'failed') as failed_count,
        COUNT(*) FILTER (WHERE processing_status = 'retrying') as retrying_count,
        COALESCE(AVG(processing_progress), 0) as avg_progress,
        COUNT(DISTINCT processing_batch_id) FILTER (WHERE processing_batch_id IS NOT NULL) as active_batches,
        SUM(file_size_bytes) as total_storage_bytes,
        MAX(created_at) as last_upload_at
    FROM documents
    WHERE is_deleted = false
    GROUP BY organization_id
),
org_job_stats AS (
    SELECT
        organization_id,
        COUNT(*) FILTER (WHERE execution_status IN ('running', 'queued')) as active_jobs,
        COUNT(*) FILTER (WHERE execution_status = 'completed') as completed_jobs,
        COUNT(*) FILTER (WHERE execution_status = 'failed') as failed_jobs,
        COALESCE(AVG(overall_progress), 0) as avg_job_progress,
        COUNT(DISTINCT primary_worker_id) as active_workers,
        AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) FILTER (WHERE execution_status = 'completed') as avg_duration_seconds
    FROM processing_job_executions
    WHERE is_deleted = false
        AND created_at >= NOW() - INTERVAL '24 hours'
    GROUP BY organization_id
),
org_performance_stats AS (
    SELECT
        pje.organization_id,
        COUNT(DISTINCT pje.id) as jobs_last_hour,
        COALESCE(AVG(rul.cpu_percent), 0) as avg_cpu_usage,
        COALESCE(AVG(rul.memory_used_mb), 0) as avg_memory_usage,
        COUNT(DISTINCT pel.id) FILTER (WHERE pel.occurred_at >= NOW() - INTERVAL '1 hour') as errors_last_hour
    FROM processing_job_executions pje
    LEFT JOIN resource_usage_logs rul ON pje.id = rul.job_execution_id
        AND rul.timestamp >= NOW() - INTERVAL '1 hour'
    LEFT JOIN processing_error_logs pel ON pje.id = pel.job_execution_id
        AND pel.occurred_at >= NOW() - INTERVAL '24 hours'
    WHERE pje.created_at >= NOW() - INTERVAL '1 hour'
    GROUP BY pje.organization_id
)
SELECT
    o.id as organization_id,
    o.name as organization_name,
    o.storage_tier,
    o.max_storage_gb,

    -- Document metrics
    COALESCE(ods.pending_count, 0) as pending_documents,
    COALESCE(ods.processing_count, 0) as processing_documents,
    COALESCE(ods.completed_count, 0) as completed_documents,
    COALESCE(ods.failed_count, 0) as failed_documents,
    COALESCE(ods.retrying_count, 0) as retrying_documents,
    COALESCE(ods.avg_progress, 0) as avg_document_progress,
    COALESCE(ods.active_batches, 0) as active_batches,
    COALESCE(ods.total_storage_bytes, 0) as total_storage_bytes,
    ROUND(COALESCE(ods.total_storage_bytes, 0) / (1024.0^3), 2) as total_storage_gb,
    ods.last_upload_at,

    -- Job metrics
    COALESCE(ojs.active_jobs, 0) as active_jobs,
    COALESCE(ojs.completed_jobs, 0) as completed_jobs_24h,
    COALESCE(ojs.failed_jobs, 0) as failed_jobs_24h,
    COALESCE(ojs.avg_job_progress, 0) as avg_job_progress,
    COALESCE(ojs.active_workers, 0) as active_workers,
    COALESCE(ojs.avg_duration_seconds, 0) as avg_job_duration_seconds,

    -- Performance metrics
    COALESCE(ops.jobs_last_hour, 0) as jobs_last_hour,
    COALESCE(ops.avg_cpu_usage, 0) as avg_cpu_usage_percent,
    COALESCE(ops.avg_memory_usage, 0) as avg_memory_usage_mb,
    COALESCE(ops.errors_last_hour, 0) as errors_last_24h,

    -- Calculated metrics
    GREATEST(ods.avg_progress, ojs.avg_job_progress) as overall_progress_percent,
    ROUND(COALESCE(ojs.completed_jobs, 0) * 100.0 / NULLIF(COALESCE(ojs.completed_jobs, 0) + COALESCE(ojs.failed_jobs, 0), 0), 2) as success_rate_24h_percent,

    -- Storage percentage
    CASE
        WHEN o.max_storage_gb > 0 THEN
            ROUND((COALESCE(ods.total_storage_bytes, 0) / (1024.0^3)) / o.max_storage_gb * 100, 2)
        ELSE 0
    END as storage_usage_percent,

    -- Health score (0-100)
    LEAST(100, GREATEST(0,
        (GREATEST(ods.avg_progress, ojs.avg_job_progress) * 0.3) +
        (ROUND(COALESCE(ojs.completed_jobs, 0) * 100.0 / NULLIF(COALESCE(ojs.completed_jobs, 0) + COALESCE(ojs.failed_jobs, 0), 0), 2) * 0.3) +
        (CASE WHEN COALESCE(ops.avg_cpu_usage, 0) < 80 THEN (100 - COALESCE(ops.avg_cpu_usage, 0)) * 0.2 ELSE 0 END) +
        (CASE WHEN COALESCE(ops.errors_last_hour, 0) = 0 THEN 20 ELSE GREATEST(0, 20 - COALESCE(ops.errors_last_hour, 0) * 2) END)
    )) as health_score,

    -- Timestamps
    NOW() as last_updated

FROM organizations o
LEFT JOIN org_document_stats ods ON o.id = ods.organization_id
LEFT JOIN org_job_stats ojs ON o.id = ojs.organization_id
LEFT JOIN org_performance_stats ops ON o.id = ops.organization_id
WHERE o.is_active = true AND o.is_deleted = false;

-- Create indexes for efficient querying
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_org_dashboard_org
ON realtime_org_dashboard_summary(organization_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_org_dashboard_health
ON realtime_org_dashboard_summary(health_score DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_org_dashboard_active_jobs
ON realtime_org_dashboard_summary(active_jobs DESC, processing_documents DESC);

-- =================================================================
-- WORKER PERFORMANCE DASHBOARD
-- =================================================================

-- Worker Performance Real-Time Summary
CREATE MATERIALIZED VIEW realtime_worker_performance AS
WITH worker_job_metrics AS (
    SELECT
        primary_worker_id as worker_id,
        COUNT(*) FILTER (WHERE execution_status = 'running') as running_jobs,
        COUNT(*) FILTER (WHERE execution_status = 'queued') as queued_jobs,
        COUNT(*) FILTER (WHERE execution_status = 'completed' AND completed_at >= NOW() - INTERVAL '1 hour') as completed_jobs_hour,
        COUNT(*) FILTER (WHERE execution_status = 'failed' AND completed_at >= NOW() - INTERVAL '1 hour') as failed_jobs_hour,
        COALESCE(AVG(overall_progress), 0) as avg_progress,
        COALESCE(AVG(EXTRACT(EPOCH FROM (completed_at - started_at))), 0) as avg_duration_seconds,
        MIN(started_at) FILTER (WHERE execution_status = 'running') as earliest_started
    FROM processing_job_executions
    WHERE primary_worker_id IS NOT NULL
        AND is_deleted = false
        AND created_at >= NOW() - INTERVAL '24 hours'
    GROUP BY primary_worker_id
),
worker_resource_metrics AS (
    SELECT
        rul.worker_id,
        COALESCE(AVG(rul.cpu_percent), 0) as avg_cpu_usage,
        COALESCE(AVG(rul.memory_used_mb), 0) as avg_memory_usage,
        COALESCE(AVG(rul.process_memory_mb), 0) as avg_process_memory,
        COUNT(DISTINCT rul.job_execution_id) as jobs_monitored
    FROM resource_usage_logs rul
    WHERE rul.timestamp >= NOW() - INTERVAL '1 hour'
        AND rul.worker_id IS NOT NULL
    GROUP BY rul.worker_id
),
worker_quality_metrics AS (
    SELECT
        ae.agent_type,
        pje.primary_worker_id,
        COUNT(*) as total_executions,
        COALESCE(AVG(ae.confidence_score), 0) as avg_confidence,
        COALESCE(SUM(ae.cost_usd), 0) as total_cost,
        COALESCE(AVG(ae.tokens_used), 0) as avg_tokens_used
    FROM agent_executions ae
    JOIN processing_job_executions pje ON ae.job_execution_id = pje.id
    WHERE ae.completed_at >= NOW() - INTERVAL '24 hours'
        AND pje.primary_worker_id IS NOT NULL
    GROUP BY ae.agent_type, pje.primary_worker_id
),
worker_error_metrics AS (
    SELECT
        pje.primary_worker_id,
        COUNT(*) FILTER (WHERE pel.severity IN ('error', 'critical', 'fatal')) as error_count,
        COUNT(*) FILTER (WHERE pel.severity = 'critical') as critical_error_count
    FROM processing_job_executions pje
    LEFT JOIN processing_error_logs pel ON pje.id = pel.job_execution_id
        AND pel.occurred_at >= NOW() - INTERVAL '24 hours'
    WHERE pje.primary_worker_id IS NOT NULL
        AND pje.created_at >= NOW() - INTERVAL '24 hours'
    GROUP BY pje.primary_worker_id
)
SELECT
    wjm.worker_id,
    wjm.running_jobs,
    wjm.queued_jobs,
    wjm.completed_jobs_hour,
    wjm.failed_jobs_hour,
    wjm.avg_progress,
    wjm.avg_duration_seconds,
    wjm.earliest_started,

    -- Resource metrics
    COALESCE(wrm.avg_cpu_usage, 0) as avg_cpu_usage_percent,
    COALESCE(wrm.avg_memory_usage, 0) as avg_memory_usage_mb,
    COALESCE(wrm.avg_process_memory, 0) as avg_process_memory_mb,
    COALESCE(wrm.jobs_monitored, 0) as jobs_monitored,

    -- Quality metrics
    json_agg(
        json_build_object(
            'agent_type', wqm.agent_type,
            'executions', wqm.total_executions,
            'avg_confidence', wqm.avg_confidence,
            'total_cost', wqm.total_cost,
            'avg_tokens_used', wqm.avg_tokens_used
        )
    ) FILTER (WHERE wqm.agent_type IS NOT NULL) as agent_performance,

    -- Error metrics
    COALESCE(wem.error_count, 0) as error_count_24h,
    COALESCE(wem.critical_error_count, 0) as critical_error_count_24h,

    -- Calculated metrics
    ROUND((wjm.completed_jobs_hour + wjm.failed_jobs_hour) * 100.0 / NULLIF(wjm.running_jobs + wjm.queued_jobs + wjm.completed_jobs_hour + wjm.failed_jobs_hour, 0), 2) as throughput_rate_percent,
    ROUND(wjm.completed_jobs_hour * 100.0 / NULLIF(wjm.completed_jobs_hour + wjm.failed_jobs_hour, 0), 2) as success_rate_hour_percent,

    -- Efficiency score (0-100)
    LEAST(100, GREATEST(0,
        (wjm.avg_progress * 0.3) +
        (CASE WHEN wrm.avg_cpu_usage < 80 THEN (100 - wrm.avg_cpu_usage) * 0.25 ELSE 0 END) +
        (CASE WHEN COALESCE(wem.error_count, 0) = 0 THEN 25 ELSE GREATEST(0, 25 - COALESCE(wem.error_count, 0) * 2) END) +
        (CASE WHEN wjm.avg_duration_seconds > 0 THEN LEAST(20, 10000 / wjm.avg_duration_seconds) ELSE 0 END) +
        (wjm.running_jobs * 5)
    )) as efficiency_score,

    -- Status classification
    CASE
        WHEN wjm.running_jobs = 0 AND wjm.queued_jobs = 0 THEN 'idle'
        WHEN wjm.running_jobs >= 5 OR COALESCE(wrm.avg_cpu_usage, 0) > 90 THEN 'overloaded'
        WHEN wjm.running_jobs > 0 THEN 'active'
        WHEN wjm.queued_jobs > 0 THEN 'waiting'
        ELSE 'idle'
    END as worker_status,

    NOW() as last_updated

FROM worker_job_metrics wjm
LEFT JOIN worker_resource_metrics wrm ON wjm.worker_id = wrm.worker_id
LEFT JOIN worker_quality_metrics wqm ON wjm.worker_id = wqm.primary_worker_id
LEFT JOIN worker_error_metrics wem ON wjm.worker_id = wem.primary_worker_id
WHERE wjm.worker_id IS NOT NULL
GROUP BY wjm.worker_id, wjm.running_jobs, wjm.queued_jobs, wjm.completed_jobs_hour, wjm.failed_jobs_hour,
         wjm.avg_progress, wjm.avg_duration_seconds, wjm.earliest_started,
         wrm.avg_cpu_usage, wrm.avg_memory_usage, wrm.avg_process_memory, wrm.jobs_monitored,
         wem.error_count, wem.critical_error_count
ORDER BY efficiency_score DESC;

-- Create indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_worker_performance_worker
ON realtime_worker_performance(worker_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_worker_efficiency
ON realtime_worker_performance(efficiency_score DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_worker_status
ON realtime_worker_performance(worker_status, active_jobs DESC);

-- =================================================================
-- PROCESSING QUEUE REAL-TIME VIEW
-- =================================================================

-- Processing Queue Real-Time Status
CREATE MATERIALIZED VIEW realtime_processing_queue AS
WITH queue_status AS (
    SELECT
        d.id as document_id,
        d.title,
        d.filename,
        d.processing_status,
        d.processing_progress,
        d.current_processing_stage,
        d.processing_priority,
        d.estimated_remaining_seconds,
        d.processing_batch_id,
        d.created_at,
        d.last_status_update,
        d.organization_id,

        -- Job execution details
        pje.execution_id as job_execution_id,
        pje.execution_status as job_status,
        pje.overall_progress as job_progress,
        pje.primary_worker_id,
        pje.started_at as job_started_at,

        -- Current stage details
        se.stage_name as current_stage_name,
        se.progress_percentage as stage_progress,
        se.started_at as stage_started_at,
        se.worker_id as stage_worker_id,

        -- Queue timing
        EXTRACT(EPOCH FROM (NOW() - d.created_at))::INTEGER as queue_time_seconds,
        EXTRACT(EPOCH FROM (NOW() - d.last_status_update))::INTEGER as time_since_update_seconds,

        -- Worker information
        w.worker_status as worker_current_status,
        w.efficiency_score as worker_efficiency,

        -- Row number for priority ordering
        ROW_NUMBER() OVER (
            PARTITION BY d.organization_id
            ORDER BY
                d.processing_priority DESC,
                d.processing_status ASC, -- pending -> processing -> retrying
                d.created_at ASC
        ) as queue_priority_rank

    FROM documents d
    LEFT JOIN processing_job_executions pje ON d.current_execution_id = pje.execution_id
    LEFT JOIN stage_executions se ON pje.id = se.job_execution_id AND se.stage_status = 'running'
    LEFT JOIN realtime_worker_performance w ON pje.primary_worker_id = w.worker_id
    WHERE d.processing_status IN ('pending', 'processing', 'retrying')
        AND d.is_deleted = false
)
SELECT
    *
FROM queue_status;

-- Create indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_queue_org_priority
ON realtime_processing_queue(organization_id, processing_priority DESC, queue_priority_rank);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_queue_status
ON realtime_processing_queue(processing_status, queue_time_seconds);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_queue_worker
ON realtime_processing_queue(primary_worker_id, processing_status) WHERE primary_worker_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_queue_batch
ON realtime_processing_queue(processing_batch_id, processing_status) WHERE processing_batch_id IS NOT NULL;

-- =================================================================
-- ERROR ANALYSIS REAL-TIME VIEW
-- =================================================================

-- Real-Time Error Analysis Dashboard
CREATE MATERIALIZED VIEW realtime_error_analysis AS
WITH error_trends AS (
    SELECT
        pel.error_type,
        pel.error_category,
        pel.severity,
        COUNT(*) as error_count,
        COUNT(*) FILTER (WHERE pel.severity = 'critical') as critical_count,
        COUNT(*) FILTER (WHERE pel.severity = 'fatal') as fatal_count,
        COUNT(*) FILTER (WHERE pel.occurred_at >= NOW() - INTERVAL '1 hour') as last_hour_count,
        MIN(pel.occurred_at) as first_occurrence,
        MAX(pel.occurred_at) as last_occurrence,
        COUNT(DISTINCT pje.primary_worker_id) as affected_workers,
        COUNT(DISTINCT pje.document_id) as affected_documents,
        COUNT(DISTINCT pje.organization_id) as affected_organizations

    FROM processing_error_logs pel
    JOIN processing_job_executions pje ON pel.job_execution_id = pje.id
    WHERE pel.occurred_at >= NOW() - INTERVAL '24 hours'
    GROUP BY pel.error_type, pel.error_category, pel.severity
),
error_patterns AS (
    SELECT
        DATE_TRUNC('hour', pel.occurred_at) as hour_bucket,
        pel.error_category,
        COUNT(*) as error_count,
        COUNT(*) FILTER (WHERE pel.severity IN ('critical', 'fatal')) as critical_count
    FROM processing_error_logs pel
    WHERE pel.occurred_at >= NOW() - INTERVAL '24 hours'
    GROUP BY DATE_TRUNC('hour', pel.occurred_at), pel.error_category
),
worker_errors AS (
    SELECT
        pje.primary_worker_id,
        COUNT(pel.id) as error_count_24h,
        COUNT(pel.id) FILTER (WHERE pel.severity = 'critical') as critical_errors_24h,
        COUNT(pel.id) FILTER (WHERE pel.occurred_at >= NOW() - INTERVAL '1 hour') as errors_last_hour,
        json_agg(DISTINCT pel.error_type) FILTER (WHERE pel.occurred_at >= NOW() - INTERVAL '6 hours') as recent_error_types
    FROM processing_job_executions pje
    LEFT JOIN processing_error_logs pel ON pje.id = pel.job_execution_id
        AND pel.occurred_at >= NOW() - INTERVAL '24 hours'
    WHERE pje.primary_worker_id IS NOT NULL
        AND pje.created_at >= NOW() - INTERVAL '24 hours'
    GROUP BY pje.primary_worker_id
)
SELECT
    et.error_type,
    et.error_category,
    et.severity,
    et.error_count,
    et.critical_count,
    et.fatal_count,
    et.last_hour_count,
    et.first_occurrence,
    et.last_occurrence,
    et.affected_workers,
    et.affected_documents,
    et.affected_organizations,

    -- Pattern analysis
    json_agg(
        json_build_object(
            'hour', ep.hour_bucket,
            'error_count', ep.error_count,
            'critical_count', ep.critical_count
        )
        ORDER BY ep.hour_bucket
    ) as hourly_pattern,

    -- Worker impact
    json_agg(
        json_build_object(
            'worker_id', we.primary_worker_id,
            'error_count_24h', we.error_count_24h,
            'critical_errors_24h', we.critical_errors_24h,
            'errors_last_hour', we.errors_last_hour,
            'recent_error_types', we.recent_error_types
        )
    ) FILTER (WHERE we.error_count_24h > 0) as worker_impact,

    -- Risk assessment
    CASE
        WHEN et.critical_count > 5 OR et.fatal_count > 0 THEN 'critical'
        WHEN et.last_hour_count > 10 OR et.critical_count > 2 THEN 'high'
        WHEN et.last_hour_count > 5 OR et.error_count > 20 THEN 'medium'
        WHEN et.error_count > 5 THEN 'low'
        ELSE 'minimal'
    END as risk_level,

    -- Trend indicator
    CASE
        WHEN et.last_hour_count > et.error_count / 24.0 * 2 THEN 'increasing'
        WHEN et.last_hour_count < et.error_count / 24.0 * 0.5 THEN 'decreasing'
        ELSE 'stable'
    END as trend_indicator,

    NOW() as last_updated

FROM error_trends et
LEFT JOIN error_patterns ep ON et.error_category = ep.error_category
LEFT JOIN worker_errors we ON true -- Join all worker errors
GROUP BY et.error_type, et.error_category, et.severity, et.error_count, et.critical_count,
         et.fatal_count, et.last_hour_count, et.first_occurrence, et.last_occurrence,
         et.affected_workers, et.affected_documents, et.affected_organizations
ORDER BY et.error_count DESC, et.critical_count DESC;

-- Create indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_error_analysis_type
ON realtime_error_analysis(error_type, error_category);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_error_risk
ON realtime_error_analysis(risk_level, error_count DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_error_trend
ON realtime_error_analysis(trend_indicator, last_hour_count DESC);

-- =================================================================
-- REFRESH FUNCTIONS
-- =================================================================

-- Function to refresh all real-time dashboard materialized views
CREATE OR REPLACE FUNCTION refresh_realtime_dashboard_views()
RETURNS TABLE(view_name TEXT, refresh_time_ms INTEGER, status TEXT) AS $$
DECLARE
    v_start_time TIMESTAMP;
    v_end_time TIMESTAMP;
    v_view_name TEXT;
BEGIN
    -- Refresh organization dashboard summary
    v_start_time := clock_timestamp();
    REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_org_dashboard_summary;
    v_end_time := clock_timestamp();
    v_view_name := 'realtime_org_dashboard_summary';

    RETURN QUERY SELECT v_view_name, EXTRACT(MILLISECONDS FROM (v_end_time - v_start_time))::INTEGER, 'success';

    -- Refresh worker performance
    v_start_time := clock_timestamp();
    REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_worker_performance;
    v_end_time := clock_timestamp();
    v_view_name := 'realtime_worker_performance';

    RETURN QUERY SELECT v_view_name, EXTRACT(MILLISECONDS FROM (v_end_time - v_start_time))::INTEGER, 'success';

    -- Refresh processing queue
    v_start_time := clock_timestamp();
    REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_processing_queue;
    v_end_time := clock_timestamp();
    v_view_name := 'realtime_processing_queue';

    RETURN QUERY SELECT v_view_name, EXTRACT(MILLISECONDS FROM (v_end_time - v_start_time))::INTEGER, 'success';

    -- Refresh error analysis
    v_start_time := clock_timestamp();
    REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_error_analysis;
    v_end_time := clock_timestamp();
    v_view_name := 'realtime_error_analysis';

    RETURN QUERY SELECT v_view_name, EXTRACT(MILLISECONDS FROM (v_end_time - v_start_time))::INTEGER, 'success';
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT SELECT ON ALL MATERIALIZED VIEWS IN SCHEMA public TO authenticated_users;
GRANT EXECUTE ON FUNCTION refresh_realtime_dashboard_views() TO authenticated_users;