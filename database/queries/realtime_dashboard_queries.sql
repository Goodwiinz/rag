-- Real-Time Dashboard Optimized Queries
-- High-performance queries specifically designed for real-time dashboard displays

-- =================================================================
-- ORGANIZATION DASHBOARD QUERIES
-- =================================================================

-- 1. Organization Overview Dashboard Query (Sub-100ms)
-- Returns comprehensive overview metrics for a single organization
EXPLAIN (ANALYZE, BUFFERS)
WITH organization_metrics AS (
    SELECT
        o.id,
        o.name,

        -- Document metrics (optimized with index)
        doc_stats.pending_count,
        doc_stats.processing_count,
        doc_stats.completed_count,
        doc_stats.failed_count,
        doc_stats.avg_progress,

        -- Job metrics (optimized with index)
        job_stats.active_jobs,
        job_stats.avg_job_progress,
        job_stats.workers_active,

        -- Performance metrics (optimized with time-based index)
        perf_stats.avg_duration_seconds,
        perf_stats.success_rate,
        perf_stats.error_rate_last_hour,

        -- System health
        health_stats.avg_cpu_usage,
        health_stats.avg_memory_usage,
        health_stats.critical_errors_count,

        -- Throughput metrics (last hour)
        throughput_stats.documents_per_hour,
        throughput_stats.jobs_per_hour
    FROM organizations o

    -- Document statistics (using optimized index)
    LEFT JOIN LATERAL (
        SELECT
            COUNT(*) FILTER (WHERE processing_status = 'pending') as pending_count,
            COUNT(*) FILTER (WHERE processing_status = 'processing') as processing_count,
            COUNT(*) FILTER (WHERE processing_status = 'completed') as completed_count,
            COUNT(*) FILTER (WHERE processing_status = 'failed') as failed_count,
            COALESCE(AVG(processing_progress), 0) as avg_progress
        FROM documents d
        WHERE d.organization_id = o.id
            AND d.is_deleted = false
    ) doc_stats ON true

    -- Job statistics (using optimized index)
    LEFT JOIN LATERAL (
        SELECT
            COUNT(*) FILTER (WHERE execution_status IN ('running', 'queued')) as active_jobs,
            COALESCE(AVG(overall_progress), 0) as avg_job_progress,
            COUNT(DISTINCT primary_worker_id) as workers_active
        FROM processing_job_executions pje
        WHERE pje.organization_id = o.id
            AND pje.is_deleted = false
            AND pje.execution_status IN ('running', 'queued', 'retrying')
    ) job_stats ON true

    -- Performance statistics (using time-based index)
    LEFT JOIN LATERAL (
        SELECT
            COALESCE(AVG(EXTRACT(EPOCH FROM (completed_at - started_at))), 0) as avg_duration_seconds,
            ROUND(COUNT(*) FILTER (WHERE execution_status = 'completed') * 100.0 / NULLIF(COUNT(*), 0), 2) as success_rate,
            COUNT(*) FILTER (WHERE occurred_at >= NOW() - INTERVAL '1 hour' AND severity IN ('error', 'critical')) as error_rate_last_hour
        FROM processing_job_executions pje
        LEFT JOIN processing_error_logs pel ON pje.id = pel.job_execution_id
        WHERE pje.organization_id = o.id
            AND pje.execution_status IN ('completed', 'failed')
            AND pje.started_at >= NOW() - INTERVAL '24 hours'
    ) perf_stats ON true

    -- System health statistics (using recent data index)
    LEFT JOIN LATERAL (
        SELECT
            COALESCE(AVG(cpu_percent), 0) as avg_cpu_usage,
            COALESCE(AVG(memory_used_mb), 0) as avg_memory_usage,
            COUNT(*) FILTER (WHERE severity = 'critical') as critical_errors_count
        FROM resource_usage_logs rul
        LEFT JOIN processing_error_logs pel ON rul.job_execution_id = pel.job_execution_id
        WHERE rul.timestamp >= NOW() - INTERVAL '1 hour'
            AND rul.job_execution_id IN (
                SELECT id FROM processing_job_executions WHERE organization_id = o.id
            )
    ) health_stats ON true

    -- Throughput statistics (last hour)
    LEFT JOIN LATERAL (
        SELECT
            COUNT(DISTINCT document_id) as documents_per_hour,
            COUNT(*) as jobs_per_hour
        FROM processing_job_executions
        WHERE organization_id = o.id
            AND execution_status = 'completed'
            AND completed_at >= NOW() - INTERVAL '1 hour'
    ) throughput_stats ON true
)
SELECT
    id,
    name,
    pending_count,
    processing_count,
    completed_count,
    failed_count,
    avg_progress,
    active_jobs,
    avg_job_progress,
    workers_active,
    avg_duration_seconds,
    success_rate,
    error_rate_last_hour,
    avg_cpu_usage,
    avg_memory_usage,
    critical_errors_count,
    documents_per_hour,
    jobs_per_hour,
    -- Performance score (0-100)
    LEAST(100, GREATEST(0,
        CASE
            WHEN avg_progress > 0 THEN avg_progress * 0.4
            ELSE 0
        END +
        CASE
            WHEN success_rate > 0 THEN success_rate * 0.3
            ELSE 0
        END +
        CASE
            WHEN avg_cpu_usage < 80 THEN (100 - avg_cpu_usage) * 0.2
            ELSE 0
        END +
        CASE
            WHEN error_rate_last_hour = 0 THEN 10
            ELSE GREATEST(0, 10 - error_rate_last_hour)
        END
    )) as performance_score
FROM organization_metrics
WHERE id = $1; -- organization_id parameter

-- =================================================================
-- REAL-TIME PROCESSING QUEUE QUERY
-- =================================================================

-- 2. Active Processing Queue with Worker Assignment (Sub-50ms)
-- Returns current processing queue with worker information and ETA
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    d.id as document_id,
    d.title,
    d.filename,
    d.processing_status,
    d.processing_progress,
    d.current_processing_stage,
    d.processing_priority,
    d.estimated_remaining_seconds,
    d.last_status_update,

    -- Queue metrics
    EXTRACT(EPOCH FROM (NOW() - d.created_at))::INTEGER as queue_time_seconds,
    EXTRACT(EPOCH FROM (NOW() - d.last_status_update))::INTEGER as time_since_last_update_seconds,

    -- Worker information
    pje.primary_worker_id,
    pje.execution_id,
    pje.execution_status as job_status,
    pje.overall_progress as job_progress,

    -- Current stage details
    se.stage_name as current_stage_name,
    se.progress_percentage as stage_progress,
    se.started_at as stage_started_at,

    -- Performance metrics
    se.duration_ms as stage_duration_ms,
    pel.error_count as recent_error_count,

    -- ETA calculation
    CASE
        WHEN d.estimated_remaining_seconds IS NOT NULL THEN d.estimated_remaining_seconds
        WHEN pje.started_at IS NOT NULL AND pje.overall_progress > 0 THEN
            (EXTRACT(EPOCH FROM (NOW() - pje.started_at))::INTEGER / pje.overall_progress * 100)::INTEGER
        ELSE NULL
    END as eta_seconds
FROM documents d
LEFT JOIN processing_job_executions pje ON d.current_execution_id = pje.execution_id
LEFT JOIN stage_executions se ON pje.id = se.job_execution_id AND se.stage_status = 'running'
LEFT JOIN (
    SELECT job_execution_id, COUNT(*) as error_count
    FROM processing_error_logs
    WHERE occurred_at >= NOW() - INTERVAL '1 hour'
    GROUP BY job_execution_id
) pel ON pje.id = pel.job_execution_id
WHERE d.organization_id = $1 -- organization_id parameter
    AND d.processing_status IN ('pending', 'processing', 'retrying')
    AND d.is_deleted = false
ORDER BY
    d.processing_priority DESC,
    d.processing_status ASC, -- pending -> processing -> retrying
    d.created_at ASC
LIMIT $2; -- limit parameter

-- =================================================================
-- WORKER PERFORMANCE AND UTILIZATION QUERY
-- =================================================================

-- 3. Worker Performance Dashboard (Sub-100ms)
-- Returns detailed performance metrics for all active workers
EXPLAIN (ANALYZE, BUFFERS)
WITH worker_performance AS (
    SELECT
        pje.primary_worker_id as worker_id,

        -- Basic metrics
        COUNT(*) as total_jobs,
        COUNT(*) FILTER (WHERE execution_status = 'running') as running_jobs,
        COUNT(*) FILTER (WHERE execution_status = 'queued') as queued_jobs,
        COUNT(*) FILTER (WHERE execution_status = 'completed') as completed_jobs,
        COUNT(*) FILTER (WHERE execution_status = 'failed') as failed_jobs,

        -- Performance metrics
        COALESCE(AVG(EXTRACT(EPOCH FROM (completed_at - started_at))), 0) as avg_job_duration_seconds,
        COALESCE(AVG(overall_progress), 0) as avg_progress,

        -- Quality metrics
        COALESCE(AVG(se.output_quality_score), 0) as avg_quality_score,
        COUNT(DISTINCT se.stage_execution_id) as total_stages_completed,

        -- Resource usage (last hour)
        COALESCE(AVG(rul.cpu_percent), 0) as avg_cpu_usage,
        COALESCE(AVG(rul.memory_used_mb), 0) as avg_memory_usage,
        COALESCE(AVG(rul.network_rx_mb + rul.network_tx_mb), 0) as avg_network_usage,

        -- Cost metrics
        COALESCE(SUM(ae.cost_usd), 0) as total_cost_usd,
        COALESCE(AVG(ae.cost_usd), 0) as avg_cost_per_job,

        -- Error metrics (last 24 hours)
        COUNT(DISTINCT pel.id) FILTER (WHERE pel.occurred_at >= NOW() - INTERVAL '24 hours') as recent_errors,
        COUNT(DISTINCT pel.id) FILTER (WHERE pel.severity = 'critical' AND pel.occurred_at >= NOW() - INTERVAL '24 hours') as critical_errors

    FROM processing_job_executions pje
    LEFT JOIN stage_executions se ON pje.id = se.job_execution_id AND se.stage_status = 'completed'
    LEFT JOIN resource_usage_logs rul ON pje.id = rul.job_execution_id
        AND rul.timestamp >= NOW() - INTERVAL '1 hour'
    LEFT JOIN agent_executions ae ON se.id = ae.stage_execution_id
    LEFT JOIN processing_error_logs pel ON pje.id = pel.job_execution_id
        AND pel.occurred_at >= NOW() - INTERVAL '24 hours'

    WHERE pje.organization_id = $1 -- organization_id parameter
        AND pje.is_deleted = false
        AND pje.primary_worker_id IS NOT NULL

    GROUP BY pje.primary_worker_id
)
SELECT
    worker_id,
    total_jobs,
    running_jobs,
    queued_jobs,
    completed_jobs,
    failed_jobs,

    -- Performance ratios
    ROUND(completed_jobs * 100.0 / NULLIF(total_jobs, 0), 2) as completion_rate_percent,
    ROUND(failed_jobs * 100.0 / NULLIF(total_jobs, 0), 2) as failure_rate_percent,
    ROUND(running_jobs * 100.0 / NULLIF(total_jobs, 0), 2) as utilization_percent,

    -- Performance metrics
    avg_job_duration_seconds,
    avg_progress,
    avg_quality_score,
    total_stages_completed,

    -- Resource metrics
    avg_cpu_usage,
    avg_memory_usage,
    avg_network_usage,

    -- Cost metrics
    total_cost_usd,
    avg_cost_per_job,

    -- Error metrics
    recent_errors,
    critical_errors,

    -- Efficiency score (0-100)
    LEAST(100, GREATEST(0,
        (avg_progress * 0.3) +
        (avg_quality_score * 100 * 0.3) +
        (CASE WHEN avg_cpu_usage < 80 THEN (100 - avg_cpu_usage) ELSE 0 END * 0.2) +
        (CASE WHEN recent_errors = 0 THEN 20 ELSE GREATEST(0, 20 - recent_errors) END * 0.2)
    )) as efficiency_score

FROM worker_performance
WHERE worker_id IS NOT NULL
ORDER BY efficiency_score DESC, total_jobs DESC;

-- =================================================================
-- ERROR ANALYSIS AND ALERTS QUERY
-- =================================================================

-- 4. Critical Error and Alert Dashboard (Sub-50ms)
-- Returns recent errors, patterns, and system health alerts
EXPLAIN (ANALYZE, BUFFERS)
WITH recent_errors AS (
    SELECT
        pel.id,
        pel.error_type,
        pel.error_category,
        pel.severity,
        pel.error_message,
        pel.occurred_at,
        pje.document_id,
        d.title as document_title,
        pje.primary_worker_id,
        se.stage_name,
        pel.impact_level,
        pel.recovery_possible,

        -- Error frequency analysis
        COUNT(*) OVER (PARTITION BY pel.error_type, DATE_TRUNC('hour', pel.occurred_at)) as error_type_hourly_count,
        COUNT(*) OVER (PARTITION BY pel.error_category, DATE_TRUNC('hour', pel.occurred_at)) as error_category_hourly_count,

        -- Error patterns
        LAG(pel.occurred_at) OVER (PARTITION BY pje.primary_worker_id ORDER BY pel.occurred_at) as prev_error_time,
        LAG(pel.error_type) OVER (PARTITION BY pje.primary_worker_id ORDER BY pel.occurred_at) as prev_error_type

    FROM processing_error_logs pel
    JOIN processing_job_executions pje ON pel.job_execution_id = pje.id
    LEFT JOIN documents d ON pje.document_id = d.id
    LEFT JOIN stage_executions se ON pel.stage_execution_id = se.id

    WHERE pje.organization_id = $1 -- organization_id parameter
        AND pel.occurred_at >= NOW() - INTERVAL '24 hours'
        AND pel.severity IN ('error', 'critical', 'fatal')
),
error_patterns AS (
    SELECT
        error_type,
        error_category,
        COUNT(*) as error_count,
        COUNT(*) FILTER (WHERE severity = 'critical') as critical_count,
        COUNT(*) FILTER (WHERE severity = 'fatal') as fatal_count,
        MIN(occurred_at) as first_occurrence,
        MAX(occurred_at) as last_occurrence,
        COUNT(DISTINCT primary_worker_id) as affected_workers,
        COUNT(DISTINCT document_id) as affected_documents

    FROM recent_errors
    GROUP BY error_type, error_category
),
system_health AS (
    SELECT
        -- System health metrics
        (SELECT COUNT(*) FROM processing_job_executions WHERE organization_id = $1 AND execution_status = 'failed' AND updated_at >= NOW() - INTERVAL '1 hour') as failed_jobs_last_hour,
        (SELECT COUNT(*) FROM processing_error_logs pel JOIN processing_job_executions pje ON pel.job_execution_id = pje.id WHERE pje.organization_id = $1 AND pel.severity = 'critical' AND pel.occurred_at >= NOW() - INTERVAL '1 hour') as critical_errors_last_hour,

        -- Resource health
        (SELECT COALESCE(AVG(cpu_percent), 0) FROM resource_usage_logs rul JOIN processing_job_executions pje ON rul.job_execution_id = pje.id WHERE pje.organization_id = $1 AND rul.timestamp >= NOW() - INTERVAL '30 minutes') as avg_cpu_last_30min,
        (SELECT COALESCE(AVG(memory_used_mb), 0) FROM resource_usage_logs rul JOIN processing_job_executions pje ON rul.job_execution_id = pje.id WHERE pje.organization_id = $1 AND rul.timestamp >= NOW() - INTERVAL '30 minutes') as avg_memory_last_30min,

        -- Queue health
        (SELECT COUNT(*) FROM documents WHERE organization_id = $1 AND processing_status IN ('pending', 'retrying') AND is_deleted = false) as queue_size,
        (SELECT AVG(processing_priority) FROM documents WHERE organization_id = $1 AND processing_status IN ('pending', 'retrying') AND is_deleted = false) as avg_queue_priority
)
SELECT
    -- Recent critical errors
    json_agg(
        json_build_object(
            'id', id,
            'error_type', error_type,
            'error_category', error_category,
            'severity', severity,
            'error_message', error_message,
            'occurred_at', occurred_at,
            'document_title', document_title,
            'worker_id', primary_worker_id,
            'stage_name', stage_name,
            'impact_level', impact_level,
            'recovery_possible', recovery_possible,
            'error_frequency', error_type_hourly_count,
            'repeat_error', prev_error_type = error_type AND prev_error_time > occurred_at - INTERVAL '5 minutes'
        )
        ORDER BY occurred_at DESC
    ) FILTER (WHERE severity = 'critical') as critical_errors,

    -- Error patterns
    json_agg(
        json_build_object(
            'error_type', error_type,
            'error_category', error_category,
            'error_count', error_count,
            'critical_count', critical_count,
            'fatal_count', fatal_count,
            'first_occurrence', first_occurrence,
            'last_occurrence', last_occurrence,
            'affected_workers', affected_workers,
            'affected_documents', affected_documents,
            'is_trending', error_count > 5 AND (last_occurrence - first_occurrence) < INTERVAL '2 hours'
        )
    ) FILTER (WHERE error_count > 1) as error_patterns,

    -- System health alerts
    json_build_object(
        'failed_jobs_last_hour', failed_jobs_last_hour,
        'critical_errors_last_hour', critical_errors_last_hour,
        'avg_cpu_last_30min', ROUND(avg_cpu_last_30min, 2),
        'avg_memory_last_30min', ROUND(avg_memory_last_30min, 2),
        'queue_size', queue_size,
        'avg_queue_priority', ROUND(COALESCE(avg_queue_priority, 0), 2),
        'health_status', CASE
            WHEN critical_errors_last_hour > 5 OR failed_jobs_last_hour > 10 THEN 'critical'
            WHEN critical_errors_last_hour > 0 OR failed_jobs_last_hour > 5 OR avg_cpu_last_30min > 90 THEN 'warning'
            WHEN avg_cpu_last_30min > 80 OR queue_size > 50 THEN 'attention'
            ELSE 'healthy'
        END,
        'requires_action', critical_errors_last_hour > 0 OR failed_jobs_last_hour > 10
    ) as system_health

FROM recent_errors, error_patterns, system_health
WHERE severity = 'critical'
LIMIT 20;