-- Comprehensive Indexing Strategy for Real-Time Status Queries
-- Optimized indexes specifically designed for sub-100ms dashboard query performance

-- =================================================================
-- DOCUMENT TABLE INDEXES
-- =================================================================

-- Primary composite index for real-time status queries
-- This is the most critical index for dashboard performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_realtime_status_composite
ON documents(organization_id, processing_status, processing_progress DESC, last_status_update DESC)
WHERE is_deleted = false;

-- High-priority queue index for worker assignment
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_priority_queue
ON documents(processing_priority DESC, created_at ASC, processing_status ASC)
WHERE processing_status IN ('pending', 'processing', 'retrying') AND is_deleted = false;

-- Worker assignment index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_worker_assignment
ON documents(current_execution_id) WHERE current_execution_id IS NOT NULL;

-- Batch processing index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_batch_processing
ON documents(processing_batch_id, processing_status, processing_progress DESC)
WHERE processing_batch_id IS NOT NULL AND is_deleted = false;

-- Organization-specific status index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_org_status_time
ON documents(organization_id, processing_status, created_at DESC)
WHERE is_deleted = false;

-- Progress-based index for real-time monitoring
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_progress_monitoring
ON documents(processing_progress DESC, last_status_update DESC)
WHERE processing_status = 'processing' AND is_deleted = false;

-- Error recovery index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_error_recovery
ON documents(organization_id, processing_error, retry_count, created_at DESC)
WHERE processing_status = 'failed' AND retry_count < max_retries;

-- Full-text search for document titles (admin dashboard)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_title_search
ON documents USING GIN(title gin_trgm_ops)
WHERE organization_id IS NOT NULL AND is_deleted = false;

-- Metadata filtering index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_metadata_gin
ON documents USING GIN(document_metadata)
WHERE is_deleted = false;

-- =================================================================
-- PROCESSING JOB EXECUTIONS INDEXES
-- =================================================================

-- Real-time job status composite index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_executions_realtime_composite
ON processing_job_executions(organization_id, execution_status, overall_progress DESC, started_at DESC)
WHERE is_deleted = false;

-- Worker current assignments index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_executions_worker_assignments
ON processing_job_executions(primary_worker_id, execution_status, started_at DESC)
WHERE primary_worker_id IS NOT NULL AND execution_status IN ('running', 'queued', 'retrying');

-- Batch job tracking index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_executions_batch_tracking
ON processing_job_executions(batch_id, execution_status, overall_progress DESC)
WHERE batch_id IS NOT NULL AND is_deleted = false;

-- Active jobs monitoring index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_executions_active_monitoring
ON processing_job_executions(execution_status, overall_progress DESC, updated_at DESC)
WHERE execution_status IN ('running', 'queued', 'retrying') AND is_deleted = false;

-- Performance analysis index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_executions_performance_analysis
ON processing_job_executions(started_at DESC, completed_at DESC, execution_status)
WHERE execution_status IN ('completed', 'failed') AND started_at >= NOW() - INTERVAL '7 days';

-- Retry queue index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_executions_retry_queue
ON processing_job_executions(next_retry_at, execution_status, retry_count)
WHERE execution_status = 'failed' AND next_retry_at IS NOT NULL;

-- Execution ID lookup index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_executions_execution_id
ON processing_job_executions(execution_id)
WHERE execution_id IS NOT NULL;

-- =================================================================
-- STAGE EXECUTIONS INDEXES
-- =================================================================

-- Active stage monitoring index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stage_executions_active_monitoring
ON stage_executions(stage_status, progress_percentage DESC, last_progress_update DESC)
WHERE stage_status IN ('running', 'pending');

-- Job-stage relationship index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stage_executions_job_stage_composite
ON stage_executions(job_execution_id, stage_order, stage_status)
WHERE stage_status IN ('pending', 'running', 'completed', 'failed');

-- Worker stage performance index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stage_executions_worker_performance
ON stage_executions(worker_id, stage_status, duration_ms)
WHERE worker_id IS NOT NULL AND duration_ms IS NOT NULL;

-- Stage type performance analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stage_executions_type_performance
ON stage_executions(stage_key, started_at DESC, duration_ms)
WHERE stage_status = 'completed' AND started_at >= NOW() - INTERVAL '7 days';

-- Quality metrics index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stage_executions_quality_metrics
ON stage_executions(output_quality_score DESC, confidence_score DESC, started_at DESC)
WHERE output_quality_score IS NOT NULL;

-- Stage progress monitoring
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stage_executions_progress_monitoring
ON stage_executions(progress_percentage DESC, last_progress_update DESC)
WHERE stage_status = 'running';

-- =================================================================
-- AGENT EXECUTIONS INDEXES
-- =================================================================

-- Agent performance monitoring index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_executions_performance_monitoring
ON agent_executions(agent_type, execution_status, started_at DESC, duration_ms)
WHERE started_at >= NOW() - INTERVAL '24 hours';

-- Cost tracking index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_executions_cost_tracking
ON agent_executions(cost_usd DESC, started_at DESC)
WHERE cost_usd > 0;

-- Stage-agent relationship index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_executions_stage_relationship
ON agent_executions(stage_execution_id, agent_type, execution_status);

-- Worker-agent performance index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_executions_worker_performance
ON agent_executions(agent_id, execution_status, completed_at DESC)
WHERE agent_id IS NOT NULL;

-- Token usage analysis index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_agent_executions_token_usage
ON agent_executions(tokens_used DESC, started_at DESC)
WHERE tokens_used > 0;

-- =================================================================
-- RESOURCE USAGE LOGS INDEXES (PARTITIONED)
-- =================================================================

-- Real-time resource monitoring index (last hour)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resource_usage_realtime_monitoring
ON resource_usage_logs(timestamp DESC, job_execution_id, worker_id)
WHERE timestamp >= NOW() - INTERVAL '1 hour';

-- Worker resource tracking index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resource_usage_worker_tracking
ON resource_usage_logs(worker_id, timestamp DESC)
WHERE worker_id IS NOT NULL AND timestamp >= NOW() - INTERVAL '6 hours';

-- Job resource usage index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resource_usage_job_tracking
ON resource_usage_logs(job_execution_id, timestamp DESC);

-- High resource usage alert index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resource_usage_high_usage_alerts
ON resource_usage_logs(timestamp DESC, cpu_percent, memory_used_mb)
WHERE (cpu_percent > 90 OR memory_used_mb > 8192) AND timestamp >= NOW() - INTERVAL '2 hours';

-- System resource trends index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resource_usage_system_trends
ON resource_usage_logs(timestamp DESC, cpu_percent, memory_used_mb, load_average_1min)
WHERE timestamp >= NOW() - INTERVAL '24 hours';

-- =================================================================
-- PROCESSING ERROR LOGS INDEXES
-- =================================================================

-- Recent critical errors index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_error_logs_recent_critical
ON processing_error_logs(severity, occurred_at DESC, error_type)
WHERE severity IN ('critical', 'fatal') AND occurred_at >= NOW() - INTERVAL '24 hours';

-- Error pattern analysis index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_error_logs_pattern_analysis
ON processing_error_logs(error_type, error_category, occurred_at DESC)
WHERE occurred_at >= NOW() - INTERVAL '7 days';

-- Worker error tracking index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_error_logs_worker_tracking
ON processing_error_logs(job_execution_id, occurred_at DESC, severity)
WHERE job_execution_id IS NOT NULL AND occurred_at >= NOW() - INTERVAL '24 hours';

-- Error recovery index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_error_logs_recovery_analysis
ON processing_error_logs(error_category, recovery_possible, manual_intervention_required, occurred_at DESC)
WHERE occurred_at >= NOW() - INTERVAL '24 hours';

-- Document error history index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_error_logs_document_history
ON processing_error_logs(document_id, occurred_at DESC)
WHERE document_id IS NOT NULL;

-- =================================================================
-- DOCUMENT STATUS SNAPSHOTS INDEXES
-- =================================================================

-- Recent snapshots index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_status_snapshots_recent
ON document_status_snapshots(document_id, created_at DESC)
WHERE created_at >= NOW() - INTERVAL '24 hours';

-- Job execution snapshots index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_status_snapshots_job_execution
ON document_status_snapshots(job_execution_id, snapshot_reason, created_at DESC)
WHERE job_execution_id IS NOT NULL;

-- Periodic snapshot analysis index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_status_snapshots_periodic_analysis
ON document_status_snapshots(snapshot_reason, created_at DESC)
WHERE snapshot_reason = 'periodic' AND created_at >= NOW() - INTERVAL '7 days';

-- Progress milestone index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_status_snapshots_progress_milestones
ON document_status_snapshots(processing_progress, snapshot_reason, created_at DESC)
WHERE snapshot_reason IN ('progress_milestone', 'status_change');

-- =================================================================
-- ANALYTICS AND PERFORMANCE INDEXES
-- =================================================================

-- Processing metrics time-series index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_metrics_timeseries
ON processing_metrics(organization_id, metric_period_start DESC, metric_type)
WHERE metric_period_start >= NOW() - INTERVAL '30 days';

-- Organization performance metrics index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_metrics_org_performance
ON processing_metrics(organization_id, overall_quality_score DESC, metric_period_start DESC)
WHERE overall_quality_score IS NOT NULL;

-- Cost analysis index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_metrics_cost_analysis
ON processing_metrics(total_cost_usd DESC, metric_period_start DESC)
WHERE total_cost_usd > 0;

-- Throughput analysis index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_metrics_throughput
ON processing_metrics(metric_type, metric_period_start DESC, tokens_per_second)
WHERE tokens_per_second > 0;

-- =================================================================
-- OPTIMIZATION INDEXES FOR JOIN OPERATIONS
-- =================================================================

-- Document-Join execution bridge index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_bridge_execution
ON documents(current_execution_id, organization_id, processing_status)
WHERE current_execution_id IS NOT NULL;

-- Job-Document relationship index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_executions_bridge_document
ON processing_job_executions(document_id, organization_id, execution_status)
WHERE document_id IS NOT NULL;

-- Stage-Job relationship optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stage_executions_bridge_job
ON stage_executions(job_execution_id, stage_status, stage_order)
WHERE job_execution_id IS NOT NULL;

-- Multi-table join optimization index
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resource_usage_bridge_job_worker
ON resource_usage_logs(job_execution_id, worker_id, timestamp DESC)
WHERE job_execution_id IS NOT NULL AND worker_id IS NOT NULL;

-- =================================================================
-- PARTIAL INDEXES FOR COMMON QUERY PATTERNS
-- =================================================================

-- Active documents only (exclude deleted)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_active_only
ON documents(organization_id, processing_status, last_status_update DESC)
WHERE is_deleted = false;

-- Currently processing documents
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_currently_processing
ON documents(organization_id, processing_progress DESC, current_execution_id)
WHERE processing_status = 'processing' AND is_deleted = false;

-- Failed documents that can be retried
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_retry_eligible
ON documents(organization_id, retry_count, created_at DESC)
WHERE processing_status = 'failed' AND retry_count < max_retries AND is_deleted = false;

-- High priority documents
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_high_priority
ON documents(processing_priority DESC, created_at ASC)
WHERE processing_priority >= 8 AND processing_status IN ('pending', 'retrying') AND is_deleted = false;

-- Recent completed documents
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_recently_completed
ON documents(organization_id, last_status_update DESC)
WHERE processing_status = 'completed' AND last_status_update >= NOW() - INTERVAL '1 hour' AND is_deleted = false;

-- =================================================================
-- INDEX MAINTENANCE FUNCTIONS
-- =================================================================

-- Function to analyze all real-time critical indexes
CREATE OR REPLACE FUNCTION analyze_realtime_indexes()
RETURNS TABLE(index_name TEXT, index_size TEXT, table_size TEXT, last_analyze TIMESTAMPTZ) AS $$
BEGIN
    RETURN QUERY
    SELECT
        schemaname || '.' || indexname as index_name,
        pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
        pg_size_pretty(pg_relation_size(indrelid)) as table_size,
        schemaname || '.' || tablename as last_analyze
    FROM pg_indexes pg_i
    JOIN pg_stat_user_indexes pg_sui ON pg_i.tablename = pg_sui.relname
    WHERE indexname LIKE ANY(ARRAY[
        'idx_documents_realtime_%',
        'idx_job_executions_realtime_%',
        'idx_stage_executions_%monitoring%',
        'idx_agent_executions_%monitoring%',
        'idx_resource_usage_%monitoring%',
        'idx_error_logs_%recent%',
        'idx_status_snapshots_%recent%'
    ])
    ORDER BY pg_relation_size(indexrelid) DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to identify unused indexes for cleanup
CREATE OR REPLACE FUNCTION identify_unused_realtime_indexes()
RETURNS TABLE(index_name TEXT, table_name TEXT, size_mb DECIMAL(10,2), idx_scan BIGINT, idx_tup_read BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT
        schemaname || '.' || indexrelname as index_name,
        schemaname || '.' || relname as table_name,
        ROUND(pg_relation_size(indexrelid) / 1024.0 / 1024.0, 2) as size_mb,
        idx_scan,
        idx_tup_read
    FROM pg_stat_user_indexes
    WHERE idx_scan < 100 -- Very low usage
        AND indexrelname LIKE ANY(ARRAY[
            'idx_%',
            'realtime_%'
        ])
    ORDER BY pg_relation_size(indexrelid) DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to rebuild fragmented indexes
CREATE OR REPLACE PROCEDURE rebuild_fragmented_realtime_indexes()
LANGUAGE plpgsql
AS $$
DECLARE
    v_index RECORD;
    v_fragmentation_ratio DECIMAL;
BEGIN
    FOR v_index IN
        SELECT
            schemaname,
            indexname,
            pg_relation_size(indexrelid) as index_size
        FROM pg_indexes
        WHERE indexname LIKE ANY(ARRAY[
            'idx_documents_realtime_%',
            'idx_job_executions_realtime_%',
            'idx_stage_executions_%monitoring%',
            'idx_resource_usage_%monitoring%'
        ])
        AND schemaname = 'public'
    LOOP
        -- Check fragmentation (simplified approach)
        -- In production, you might want more sophisticated fragmentation detection
        IF v_index.index_size > 100 * 1024 * 1024 THEN -- Index larger than 100MB
            RAISE NOTICE 'Rebuilding index: %', v_index.indexname;
            EXECUTE 'REINDEX INDEX CONCURRENTLY ' || v_index.schemaname || '.' || v_index.indexname;
        END IF;
    END LOOP;
END;
$$;

-- =================================================================
-- INDEX USAGE MONITORING
-- =================================================================

-- View to monitor critical index usage
CREATE OR REPLACE VIEW realtime_index_usage_monitor AS
SELECT
    schemaname || '.' || indexrelname as index_name,
    schemaname || '.' || relname as table_name,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
    CASE
        WHEN idx_scan = 0 THEN 'UNUSED'
        WHEN idx_scan < 100 THEN 'LOW_USAGE'
        WHEN idx_scan < 1000 THEN 'NORMAL_USAGE'
        ELSE 'HIGH_USAGE'
    END as usage_category,
    last_used as last_used_time
FROM pg_stat_user_indexes
WHERE indexrelname LIKE ANY(ARRAY[
    'idx_%realtime%',
    'idx_%monitoring%',
    'idx_%dashboard%'
])
ORDER BY idx_scan DESC, pg_relation_size(indexrelid) DESC;

-- Grant permissions
GRANT SELECT ON realtime_index_usage_monitor TO authenticated_users;
GRANT EXECUTE ON FUNCTION analyze_realtime_indexes() TO authenticated_users;
GRANT EXECUTE ON FUNCTION identify_unused_realtime_indexes() TO authenticated_users;