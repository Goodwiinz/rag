-- Real-Time Processing Views for Common Query Patterns
-- Optimized views for dashboard, monitoring, and analytics queries

BEGIN;

-- Document Processing Dashboard View
-- Shows current status of all documents with real-time progress
CREATE OR REPLACE VIEW document_processing_dashboard AS
SELECT
    d.id,
    d.title,
    d.filename,
    d.document_type,
    d.organization_id,
    d.uploaded_by_user_id,
    d.created_at,

    -- Current processing status
    COALESCE(d.processing_status, 'queued') as current_status,
    COALESCE(d.processing_progress, 0) as overall_progress,
    d.current_processing_stage,
    d.estimated_remaining_seconds,
    d.last_status_update,
    d.processing_started_at,
    d.processing_completed_at,

    -- Execution information
    pje.execution_id,
    pje.current_stage as job_current_stage,
    pje.total_stages,
    pje.completed_stages,
    pje.failed_stages,
    pje.primary_worker_id,
    pje.started_at as job_started_at,

    -- Performance metrics
    CASE
        WHEN d.processing_started_at IS NOT NULL AND d.processing_completed_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (d.processing_completed_at - d.processing_started_at))::INTEGER
        ELSE NULL
    END as total_processing_seconds,

    CASE
        WHEN d.processing_started_at IS NOT NULL AND d.processing_completed_at IS NULL
        THEN EXTRACT(EPOCH FROM (NOW() - d.processing_started_at))::INTEGER
        ELSE NULL
    END as current_processing_duration,

    -- Error information
    d.processing_error,
    d.processing_retry_count,
    pje.error_message as job_error_message,

    -- File information
    d.file_size_bytes,
    d.mime_type,

    -- Quality metrics
    d.quality_score,
    d.is_embedded,
    d.is_indexed,

    -- Metadata
    d.tags,
    d.is_deleted,

    -- Calculated fields
    CASE
        WHEN d.processing_status = 'completed' THEN true
        WHEN d.processing_status = 'failed' THEN true
        WHEN d.processing_status = 'cancelled' THEN true
        ELSE false
    END as is_processing_complete,

    CASE
        WHEN d.processing_status = 'completed' THEN true
        ELSE false
    END as is_processing_successful,

    CASE
        WHEN d.processing_status IN ('queued', 'processing', 'retrying') THEN true
        ELSE false
    END as is_active_processing,

    -- Stage progress details
    (
        SELECT json_agg(
            json_build_object(
                'stage_key', se.stage_key,
                'stage_name', se.stage_name,
                'stage_status', se.stage_status,
                'progress_percentage', se.progress_percentage,
                'started_at', se.started_at,
                'duration_ms', se.duration_ms
            )
            ORDER BY se.stage_order
        )
        FROM stage_executions se
        WHERE se.job_execution_id = pje.id
        AND se.is_deleted = false
    ) as stage_progress,

    -- Latest status snapshot
    (
        SELECT json_build_object(
            'timestamp', dss.created_at,
            'progress', dss.processing_progress,
            'error_rate', dss.error_rate,
            'quality_score', dss.quality_score,
            'active_workers', dss.active_workers
        )
        FROM document_status_snapshots dss
        WHERE dss.document_id = d.id
        ORDER BY dss.created_at DESC
        LIMIT 1
    ) as latest_snapshot

FROM documents d
LEFT JOIN processing_job_executions pje ON d.current_execution_id = pje.id
WHERE d.is_deleted = false;

-- Real-Time Processing Queue View
-- Shows documents currently being processed with performance metrics
CREATE OR REPLACE VIEW processing_queue_realtime AS
SELECT
    pje.id,
    pje.execution_id,
    pje.document_id,
    d.title,
    d.filename,
    d.document_type,
    pje.organization_id,

    -- Queue information
    pje.queued_at,
    pje.started_at,
    pje.completed_at,
    pje.execution_status,
    pje.overall_progress,
    pje.current_stage,
    pje.total_stages,
    pje.completed_stages,
    pje.estimated_remaining_seconds,

    -- Worker information
    pje.primary_worker_id,
    pje.worker_pool_id,
    pje.worker_capabilities,

    -- Performance metrics
    EXTRACT(EPOCH FROM (COALESCE(pje.completed_at, NOW()) - pje.started_at))::INTEGER as current_duration_seconds,
    CASE
        WHEN pje.total_stages > 0 AND pje.completed_stages > 0
        THEN (EXTRACT(EPOCH FROM (COALESCE(pje.completed_at, NOW()) - pje.started_at))::INTEGER / pje.completed_stages)
        ELSE NULL
    END as average_stage_duration_seconds,

    -- Priority and scheduling
    d.processing_priority,
    pje.batch_id,
    pje.retry_count,
    pje.max_retries,
    pje.next_retry_at,

    -- Resource usage
    pje.allocated_memory_mb,
    pje.allocated_cpu_cores,

    -- Error tracking
    pje.error_message,
    pje.error_details,

    -- Active stage information
    (
        SELECT json_build_object(
            'stage_key', se.stage_key,
            'stage_name', se.stage_name,
            'stage_status', se.stage_status,
            'progress_percentage', se.progress_percentage,
            'current_step', se.current_step,
            'total_steps', se.total_steps,
            'worker_id', se.worker_id,
            'duration_ms', se.duration_ms,
            'started_at', se.started_at
        )
        FROM stage_executions se
        WHERE se.job_execution_id = pje.id
        AND se.stage_status = 'running'
        ORDER BY se.started_at DESC
        LIMIT 1
    ) as active_stage,

    -- Resource usage from logs
    (
        SELECT json_build_object(
            'cpu_percent', AVG(rul.cpu_percent),
            'memory_mb', AVG(rul.memory_used_mb),
            'last_update', MAX(rul.timestamp)
        )
        FROM resource_usage_logs rul
        WHERE rul.job_execution_id = pje.id
        AND rul.timestamp >= NOW() - INTERVAL '5 minutes'
    ) as current_resource_usage,

    -- Recent errors
    (
        SELECT json_agg(
            json_build_object(
                'error_type', pel.error_type,
                'error_message', pel.error_message,
                'occurred_at', pel.occurred_at,
                'severity', pel.severity
            )
            ORDER BY pel.occurred_at DESC
        )
        FROM processing_error_logs pel
        WHERE pel.job_execution_id = pje.id
        AND pel.occurred_at >= NOW() - INTERVAL '1 hour'
        LIMIT 5
    ) as recent_errors

FROM processing_job_executions pje
JOIN documents d ON pje.document_id = d.id
WHERE pje.is_deleted = false
AND pje.execution_status IN ('queued', 'running', 'retrying')
AND d.is_deleted = false;

-- Processing Performance Analytics View
-- Aggregated performance metrics for analytics and monitoring
CREATE OR REPLACE VIEW processing_performance_analytics AS
SELECT
    pm.organization_id,
    pm.metric_period_start,
    pm.metric_period_end,
    pm.metric_type,

    -- Performance metrics
    pm.total_duration_ms,
    pm.average_stage_duration_ms,
    pm.slowest_stage_duration_ms,
    pm.fastest_stage_duration_ms,

    -- Quality metrics
    pm.overall_quality_score,
    pm.accuracy_score,
    pm.completeness_score,
    pm.consistency_score,

    -- Resource metrics
    pm.total_memory_mb,
    pm.peak_memory_mb,
    pm.total_cpu_ms,
    pm.peak_cpu_percent,

    -- Cost metrics
    pm.total_cost_usd,
    pm.cost_per_token,
    pm.cost_per_mb,

    -- Throughput metrics
    pm.tokens_per_second,
    pm.mb_per_second,
    pm.pages_per_second,

    -- Error metrics
    pm.error_count,
    pm.error_rate,
    pm.retry_count,
    pm.timeout_count,

    -- Calculated efficiency metrics
    CASE
        WHEN pm.total_duration_ms > 0
        THEN (pm.total_duration_ms::DECIMAL / 1000.0) / NULLIF(pm.total_memory_mb, 0)
        ELSE NULL
    END as seconds_per_mb,

    CASE
        WHEN pm.total_duration_ms > 0 AND pm.total_memory_mb > 0
        THEN (pm.total_memory_mb::DECIMAL * pm.total_cpu_ms::DECIMAL) / (pm.total_duration_ms::DECIMAL)
        ELSE NULL
    END as resource_efficiency_score,

    -- Document counts
    (
        SELECT COUNT(DISTINCT pje2.document_id)
        FROM processing_job_executions pje2
        WHERE pje2.organization_id = pm.organization_id
        AND pje2.started_at >= pm.metric_period_start
        AND pje2.started_at < pm.metric_period_end
        AND pje2.is_deleted = false
    ) as documents_processed,

    -- Success rate
    CASE
        WHEN (
            SELECT COUNT(*)
            FROM processing_job_executions pje2
            WHERE pje2.organization_id = pm.organization_id
            AND pje2.started_at >= pm.metric_period_start
            AND pje2.started_at < pm.metric_period_end
            AND pje2.is_deleted = false
        ) > 0
        THEN (
            SELECT COUNT(*)
            FROM processing_job_executions pje2
            WHERE pje2.organization_id = pm.organization_id
            AND pje2.started_at >= pm.metric_period_start
            AND pje2.started_at < pm.metric_period_end
            AND pje2.execution_status = 'completed'
            AND pje2.is_deleted = false
        )::DECIMAL / (
            SELECT COUNT(*)
            FROM processing_job_executions pje2
            WHERE pje2.organization_id = pm.organization_id
            AND pje2.started_at >= pm.metric_period_start
            AND pje2.started_at < pm.metric_period_end
            AND pje2.is_deleted = false
        )
        ELSE NULL
    END as success_rate,

    pm.metric_metadata

FROM processing_metrics pm
WHERE pm.is_deleted = false;

-- WebSocket Connection Status View
-- Real-time view of active WebSocket connections
CREATE OR REPLACE VIEW websocket_connections_status AS
SELECT
    wsc.connection_id,
    wsc.user_id,
    wsc.organization_id,
    wsc.connection_status,
    wsc.connected_at,
    wsc.last_heartbeat,
    wsc.client_type,
    wsc.client_version,

    -- Connection metrics
    wsc.messages_sent,
    wsc.messages_received,
    wsc.bytes_sent,
    wsc.bytes_received,
    wsc.connection_duration_seconds,
    wsc.average_latency_ms,

    -- Error tracking
    wsc.error_count,
    wsc.last_error,
    wsc.reconnect_attempts,

    -- Subscription information
    wsc.subscription_channels,
    (
        SELECT COUNT(*)
        FROM realtime_subscriptions rs
        WHERE rs.connection_id = wsc.connection_id
        AND rs.is_active = true
        AND rs.is_deleted = false
    ) as active_subscription_count,

    -- Recent activity
    (
        SELECT json_agg(
            json_build_object(
                'update_type', dpu.update_type,
                'title', dpu.title,
                'created_at', dpu.created_at,
                'delivery_status', dpu.delivery_status
            )
            ORDER BY dpu.created_at DESC
        )
        FROM document_processing_updates dpu
        WHERE dpu.target_connections @> ARRAY[wsc.connection_id]
        AND dpu.created_at >= NOW() - INTERVAL '10 minutes'
        LIMIT 10
    ) as recent_updates,

    -- Performance metrics
    (
        SELECT json_build_object(
            'avg_latency_ms', AVG(cpm.average_latency_ms),
            'messages_per_second', AVG(cpm.messages_per_second),
            'success_rate', 1 - AVG(cpm.error_rate)
        )
        FROM connection_performance_metrics cpm
        WHERE cpm.connection_id = wsc.connection_id
        AND cpm.metrics_period_start >= NOW() - INTERVAL '1 hour'
    ) as performance_summary,

    -- Connection health
    CASE
        WHEN wsc.last_heartbeat < NOW() - INTERVAL '5 minutes' THEN 'unhealthy'
        WHEN wsc.error_count > 10 THEN 'degraded'
        WHEN wsc.reconnect_attempts > 3 THEN 'unstable'
        ELSE 'healthy'
    END as health_status,

    -- Time since last activity
    EXTRACT(EPOCH FROM (NOW() - wsc.last_heartbeat))::INTEGER as seconds_since_heartbeat,
    EXTRACT(EPOCH FROM (NOW() - wsc.connected_at))::INTEGER as total_connection_seconds

FROM websocket_connections wsc
WHERE wsc.is_deleted = false;

-- Document Processing Stage Analytics View
-- Performance metrics by processing stage
CREATE OR REPLACE VIEW processing_stage_analytics AS
SELECT
    dps.stage_key,
    dps.stage_name,
    dps.stage_type,
    dps.stage_order,

    -- Execution statistics
    COUNT(DISTINCT se.job_execution_id) as total_executions,
    COUNT(DISTINCT CASE WHEN se.stage_status = 'completed' THEN se.id END) as successful_executions,
    COUNT(DISTINCT CASE WHEN se.stage_status = 'failed' THEN se.id END) as failed_executions,

    -- Success rate
    CASE
        WHEN COUNT(*) > 0
        THEN COUNT(CASE WHEN se.stage_status = 'completed' THEN 1 END)::DECIMAL / COUNT(*)
        ELSE NULL
    END as success_rate,

    -- Performance metrics
    AVG(se.duration_ms) as average_duration_ms,
    MIN(se.duration_ms) as min_duration_ms,
    MAX(se.duration_ms) as max_duration_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY se.duration_ms) as p95_duration_ms,

    -- Resource usage
    AVG(se.memory_peak_mb) as average_memory_mb,
    AVG(se.cpu_time_ms) as average_cpu_time_ms,

    -- Quality metrics
    AVG(se.output_quality_score) as average_quality_score,
    AVG(se.confidence_score) as average_confidence_score,

    -- Retry statistics
    AVG(se.retry_count) as average_retries,
    MAX(se.retry_count) as max_retries,

    -- Worker distribution
    COUNT(DISTINCT se.worker_id) as unique_workers,

    -- Recent performance (last 24 hours)
    (
        SELECT json_build_object(
            'executions_24h', COUNT(*),
            'success_rate_24h', COUNT(CASE WHEN stage_status = 'completed' THEN 1 END)::DECIMAL / COUNT(*),
            'avg_duration_24h', AVG(duration_ms)
        )
        FROM stage_executions se_24h
        WHERE se_24h.stage_key = dps.stage_key
        AND se_24h.started_at >= NOW() - INTERVAL '24 hours'
        AND se_24h.is_deleted = false
    ) as recent_performance,

    -- Common errors
    (
        SELECT json_agg(
            json_build_object(
                'error_type', se.error_type,
                'count', COUNT(*),
                'last_occurred', MAX(se.started_at)
            )
            ORDER BY COUNT(*) DESC
        )
        FROM stage_executions se_err
        WHERE se_err.stage_key = dps.stage_key
        AND se_err.error_type IS NOT NULL
        AND se_err.is_deleted = false
        AND se_err.started_at >= NOW() - INTERVAL '7 days'
        GROUP BY se_err.error_type
        LIMIT 5
    ) as common_errors

FROM document_processing_stages dps
LEFT JOIN stage_executions se ON dps.stage_key = se.stage_key AND se.is_deleted = false
WHERE dps.is_active = true
GROUP BY dps.id, dps.stage_key, dps.stage_name, dps.stage_type, dps.stage_order;

-- Real-Time Error Monitoring View
-- Dashboard for monitoring processing errors
CREATE OR REPLACE VIEW processing_error_monitor AS
SELECT
    pel.id,
    pel.error_id,
    pel.job_execution_id,
    pje.document_id,
    d.title as document_title,
    pel.error_type,
    pel.error_category,
    pel.severity,
    pel.error_message,
    pel.impact_level,

    -- Error timing
    pel.occurred_at,
    pel.detected_at,
    pel.resolved_at,
    EXTRACT(EPOCH FROM (pel.detected_at - pel.occurred_at))::INTEGER as detection_delay_seconds,

    -- Error context
    pel.error_context,
    pel.system_state,
    pel.affected_components,
    pel.recovery_possible,

    -- Resolution information
    pel.resolution_method,
    pel.resolution_details,
    pel.prevented_recurrence,

    -- Processing context
    pje.execution_id,
    pje.current_stage,
    pje.execution_status,

    -- Document context
    d.document_type,
    d.file_size_bytes,
    d.uploaded_by_user_id,

    -- Error frequency analysis
    (
        SELECT COUNT(*) as error_count
        FROM processing_error_logs pel_count
        WHERE pel_count.error_type = pel.error_type
        AND pel_count.occurred_at >= NOW() - INTERVAL '24 hours'
        AND pel_count.is_deleted = false
    ) as same_error_count_24h,

    (
        SELECT COUNT(*) as org_error_count
        FROM processing_error_logs pel_org
        WHERE pel_org.organization_id = pje.organization_id
        AND pel_org.occurred_at >= NOW() - INTERVAL '1 hour'
        AND pel_org.is_deleted = false
    ) as org_error_count_1h,

    -- Escalation criteria
    CASE
        WHEN pel.severity = 'critical' THEN 'immediate'
        WHEN pel.impact_level = 'critical' THEN 'high'
        WHEN pel.same_error_count_24h > 5 THEN 'medium'
        WHEN pel.org_error_count_1h > 10 THEN 'medium'
        ELSE 'low'
    END as escalation_level,

    -- Resolution SLA
    CASE
        WHEN pel.severity = 'critical' THEN 300  -- 5 minutes
        WHEN pel.severity = 'error' THEN 1800     -- 30 minutes
        WHEN pel.severity = 'warning' THEN 3600   -- 1 hour
        ELSE 7200                                  -- 2 hours
    END as resolution_sla_seconds,

    pel.error_metadata

FROM processing_error_logs pel
JOIN processing_job_executions pje ON pel.job_execution_id = pje.id
JOIN documents d ON pje.document_id = d.id
WHERE pel.is_deleted = false
ORDER BY pel.occurred_at DESC;

-- Create indexes for views (PostgreSQL supports indexes on views through materialized views or underlying tables)
-- For performance-critical queries, consider creating materialized views

COMMENT ON VIEW document_processing_dashboard IS 'Real-time dashboard view showing document processing status and progress';
COMMENT ON VIEW processing_queue_realtime IS 'Live view of documents currently in processing queue with performance metrics';
COMMENT ON VIEW processing_performance_analytics IS 'Aggregated performance analytics for processing metrics';
COMMENT ON VIEW websocket_connections_status IS 'Real-time status of WebSocket connections and subscriptions';
COMMENT ON VIEW processing_stage_analytics IS 'Performance analytics by processing stage';
COMMENT ON VIEW processing_error_monitor IS 'Error monitoring dashboard for processing issues';

COMMIT;