-- Real-Time Processing Performance Optimization
-- Partitioning, indexing, and performance tuning for high-throughput scenarios

BEGIN;

-- Step 1: Partition strategy for high-volume tables
-- These partitions help manage 1000+ concurrent document uploads

-- Partition resource_usage_logs by time for better performance
CREATE TABLE IF NOT EXISTS resource_usage_logs_partitioned (
    LIKE resource_usage_logs INCLUDING ALL
) PARTITION BY RANGE (timestamp);

-- Create monthly partitions for resource usage logs
-- This query creates partitions for the current and next 3 months
DO $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
    i INTEGER;
BEGIN
    FOR i IN 0..3 LOOP
        partition_date := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month' * i);
        partition_name := 'resource_usage_logs_' || TO_CHAR(partition_date, 'YYYY_MM');

        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I PARTITION OF resource_usage_logs_partitioned
            FOR VALUES FROM (%L) TO (%L)',
            partition_name,
            partition_date,
            partition_date + INTERVAL '1 month'
        );

        -- Create indexes for the partition
        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_%s_job_timestamp ON %I(job_execution_id, timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_%s_worker_timestamp ON %I(worker_id, timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_%s_timestamp ON %I(timestamp DESC);
        ',
            partition_name, partition_name,
            partition_name, partition_name,
            partition_name, partition_name
        );
    END LOOP;
END $$;

-- Partition document_status_snapshots by time
CREATE TABLE IF NOT EXISTS document_status_snapshots_partitioned (
    LIKE document_status_snapshots INCLUDING ALL
) PARTITION BY RANGE (created_at);

-- Create weekly partitions for status snapshots
DO $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
    i INTEGER;
BEGIN
    FOR i IN 0..8 LOOP  -- 8 weeks of partitions
        partition_date := DATE_TRUNC('week', CURRENT_DATE + INTERVAL '1 week' * i);
        partition_name := 'document_status_snapshots_' || TO_CHAR(partition_date, 'YYYY_WW');

        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I PARTITION OF document_status_snapshots_partitioned
            FOR VALUES FROM (%L) TO (%L)',
            partition_name,
            partition_date,
            partition_date + INTERVAL '1 week'
        );

        EXECUTE format('
            CREATE INDEX IF NOT EXISTS idx_%s_document_time ON %I(document_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_%s_snapshot_reason ON %I(snapshot_reason, created_at DESC);
        ',
            partition_name, partition_name,
            partition_name, partition_name
        );
    END LOOP;
END $$;

-- Step 2: Create specialized indexes for real-time queries
-- These indexes optimize the common access patterns identified in requirements

-- Compound indexes for dashboard queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_dashboard_realtime
ON documents(processing_status, processing_progress DESC, last_status_update DESC)
WHERE is_deleted = false;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_org_status_priority
ON documents(organization_id, processing_status, processing_priority DESC, created_at ASC)
WHERE processing_status IN ('queued', 'processing', 'retrying');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_file_type_status
ON documents(document_type, processing_status, created_at DESC)
WHERE is_deleted = false;

-- Processing job execution indexes for queue management
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_jobs_queue_performance
ON processing_job_executions(execution_status, processing_priority DESC, queued_at ASC)
WHERE is_deleted = false;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_jobs_worker_performance
ON processing_job_executions(primary_worker_id, execution_status, started_at DESC)
WHERE execution_status IN ('running', 'retrying');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_jobs_batch_optimization
ON processing_job_executions(batch_id, execution_status, started_at DESC)
WHERE batch_id IS NOT NULL;

-- Stage execution indexes for progress tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stage_executions_progress_performance
ON stage_executions(stage_status, progress_percentage DESC, last_progress_update DESC)
WHERE stage_status IN ('running', 'pending');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stage_executions_worker_realtime
ON stage_executions(worker_id, stage_status, started_at DESC)
WHERE stage_status = 'running';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_stage_executions_completion_performance
ON stage_executions(job_execution_id, stage_order, stage_status)
WHERE stage_status IN ('completed', 'failed');

-- WebSocket real-time update indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_updates_realtime_delivery
ON document_processing_updates(delivery_status, priority DESC, scheduled_for ASC)
WHERE delivery_status IN ('pending', 'scheduled');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_updates_connection_performance
ON document_processing_updates(target_connections, delivery_status, created_at DESC)
WHERE array_length(target_connections, 1) > 0;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_updates_expiring_soon
ON document_processing_updates(expires_at, delivery_status)
WHERE expires_at IS NOT NULL
AND delivery_status != 'delivered';

-- Step 3: Create materialized views for high-performance analytics
-- These views pre-compute expensive aggregations for dashboard performance

CREATE MATERIALIZED VIEW IF NOT EXISTS document_processing_summary_mv AS
SELECT
    organization_id,
    DATE_TRUNC('hour', created_at) as hour_bucket,
    document_type,
    processing_status,

    COUNT(*) as document_count,
    SUM(file_size_bytes) as total_size_bytes,
    AVG(file_size_bytes) as avg_size_bytes,

    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed_count,
    COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed_count,
    COUNT(CASE WHEN processing_status = 'processing' THEN 1 END) as processing_count,
    COUNT(CASE WHEN processing_status = 'queued' THEN 1 END) as queued_count,

    AVG(processing_progress) as avg_progress,
    AVG(quality_score) as avg_quality_score,

    MIN(processing_started_at) as min_processing_started,
    MAX(processing_completed_at) as max_processing_completed,

    AVG(CASE
        WHEN processing_started_at IS NOT NULL AND processing_completed_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (processing_completed_at - processing_started_at))
        ELSE NULL
    END) as avg_processing_duration_seconds

FROM documents
WHERE is_deleted = false
GROUP BY organization_id, DATE_TRUNC('hour', created_at), document_type, processing_status;

CREATE UNIQUE INDEX IF NOT EXISTS idx_document_processing_summary_mv_unique
ON document_processing_summary_mv(organization_id, hour_bucket, document_type, processing_status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_processing_summary_mv_time
ON document_processing_summary_mv(hour_bucket DESC, organization_id);

-- Real-time queue status materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS processing_queue_status_mv AS
SELECT
    organization_id,
    processing_status as status,
    COUNT(*) as count,
    AVG(processing_progress) as avg_progress,
    MIN(created_at) as oldest_in_queue,
    MAX(created_at) as newest_in_queue,
    AVG(estimated_remaining_seconds) as avg_remaining_seconds,

    -- Performance metrics
    AVG(CASE
        WHEN processing_started_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (NOW() - processing_started_at))
        ELSE NULL
    END) as avg_processing_time_seconds,

    -- Error rate
    COUNT(CASE WHEN processing_error IS NOT NULL THEN 1 END)::DECIMAL / COUNT(*) as error_rate,

    -- Priority breakdown
    COUNT(CASE WHEN processing_priority >= 8 THEN 1 END) as high_priority_count,
    COUNT(CASE WHEN processing_priority <= 3 THEN 1 END) as low_priority_count

FROM documents
WHERE is_deleted = false
AND processing_status IN ('queued', 'processing', 'retrying')
GROUP BY organization_id, processing_status;

CREATE UNIQUE INDEX IF NOT EXISTS idx_processing_queue_status_mv_unique
ON processing_queue_status_mv(organization_id, status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_queue_status_mv_count
ON processing_queue_status_mv(count DESC);

-- Step 4: Create optimized stored procedures for common operations
-- These procedures batch operations for better performance

CREATE OR REPLACE FUNCTION update_document_progress_batch(
    p_document_ids UUID[],
    p_progress_values DECIMAL[],
    p_stage_updates TEXT[]
) RETURNS INTEGER AS $$
DECLARE
    updated_count INTEGER := 0;
    i INTEGER;
BEGIN
    -- Validate input arrays
    IF array_length(p_document_ids, 1) IS NULL OR
       array_length(p_progress_values, 1) IS NULL OR
       array_length(p_stage_updates, 1) IS NULL OR
       array_length(p_document_ids, 1) != array_length(p_progress_values, 1) OR
       array_length(p_document_ids, 1) != array_length(p_stage_updates, 1) THEN
        RAISE EXCEPTION 'Invalid input arrays: all arrays must have same length and not be null';
    END IF;

    -- Perform batch update
    FOR i IN 1..array_length(p_document_ids, 1) LOOP
        UPDATE documents
        SET
            processing_progress = p_progress_values[i],
            current_processing_stage = p_stage_updates[i],
            last_status_update = NOW()
        WHERE id = p_document_ids[i]
        AND is_deleted = false;

        GET DIAGNOSTICS updated_count = ROW_COUNT;
    END LOOP;

    RETURN updated_count;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_realtime_queue_status(
    p_organization_id UUID,
    p_status_filter TEXT DEFAULT NULL
) RETURNS TABLE (
    status TEXT,
    count BIGINT,
    avg_progress DECIMAL,
    oldest_waiting_minutes INTEGER,
    estimated_completion_minutes INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.processing_status,
        COUNT(*)::BIGINT,
        AVG(d.processing_progress),
        EXTRACT(EPOCH FROM (NOW() - MIN(d.created_at)))::INTEGER / 60 as oldest_waiting_minutes,
        CASE
            WHEN AVG(d.estimated_remaining_seconds) IS NOT NULL
            THEN ROUND(AVG(d.estimated_remaining_seconds)::INTEGER / 60)
            ELSE NULL
        END as estimated_completion_minutes
    FROM documents d
    WHERE d.organization_id = p_organization_id
    AND d.is_deleted = false
    AND d.processing_status IN ('queued', 'processing', 'retrying')
    AND (p_status_filter IS NULL OR d.processing_status = p_status_filter)
    GROUP BY d.processing_status
    ORDER BY
        CASE d.processing_status
            WHEN 'queued' THEN 1
            WHEN 'processing' THEN 2
            WHEN 'retrying' THEN 3
        END;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION cleanup_old_realtime_data(
    p_retention_days INTEGER DEFAULT 7
) RETURNS TABLE (
    table_name TEXT,
    rows_deleted BIGINT
) AS $$
BEGIN
    -- Clean up old status snapshots
    RETURN QUERY
    SELECT 'document_status_snapshots' as table_name, COUNT(*) as rows_deleted
    FROM document_status_snapshots
    WHERE created_at < NOW() - INTERVAL '1 day' * p_retention_days;

    DELETE FROM document_status_snapshots
    WHERE created_at < NOW() - INTERVAL '1 day' * p_retention_days;

    -- Clean up old resource usage logs
    RETURN QUERY
    SELECT 'resource_usage_logs' as table_name, COUNT(*) as rows_deleted
    FROM resource_usage_logs
    WHERE timestamp < NOW() - INTERVAL '1 day' * p_retention_days;

    DELETE FROM resource_usage_logs
    WHERE timestamp < NOW() - INTERVAL '1 day' * p_retention_days;

    -- Clean up delivered/acknowledged updates
    RETURN QUERY
    SELECT 'document_processing_updates' as table_name, COUNT(*) as rows_deleted
    FROM document_processing_updates
    WHERE delivery_status IN ('delivered', 'acknowledged')
    AND created_at < NOW() - INTERVAL '1 day' * p_retention_days;

    DELETE FROM document_processing_updates
    WHERE delivery_status IN ('delivered', 'acknowledged')
    AND created_at < NOW() - INTERVAL '1 day' * p_retention_days;

    -- Clean up old event logs
    RETURN QUERY
    SELECT 'realtime_event_log' as table_name, COUNT(*) as rows_deleted
    FROM realtime_event_log
    WHERE occurred_at < NOW() - INTERVAL '1 day' * p_retention_days;

    DELETE FROM realtime_event_log
    WHERE occurred_at < NOW() - INTERVAL '1 day' * p_retention_days;
END;
$$ LANGUAGE plpgsql;

-- Step 5: Create refresh schedule for materialized views
-- These functions help maintain the materialized views

CREATE OR REPLACE FUNCTION refresh_realtime_materialized_views() RETURNS VOID AS $$
BEGIN
    -- Refresh document processing summary
    REFRESH MATERIALIZED VIEW CONCURRENTLY document_processing_summary_mv;

    -- Refresh queue status
    REFRESH MATERIALIZED VIEW CONCURRENTLY processing_queue_status_mv;
END;
$$ LANGUAGE plpgsql;

-- Step 6: Create performance monitoring function
CREATE OR REPLACE FUNCTION get_realtime_performance_metrics(
    p_organization_id UUID DEFAULT NULL,
    p_time_window_minutes INTEGER DEFAULT 5
) RETURNS TABLE (
    metric_name TEXT,
    metric_value DECIMAL,
    metric_unit TEXT
) AS $$
BEGIN
    RETURN QUERY
    -- Average processing time
    SELECT 'avg_processing_duration_seconds' as metric_name,
           AVG(EXTRACT(EPOCH FROM (d.processing_completed_at - d.processing_started_at))) as metric_value,
           'seconds' as metric_unit
    FROM documents d
    WHERE d.processing_status = 'completed'
    AND d.processing_completed_at >= NOW() - INTERVAL '1 minute' * p_time_window_minutes
    AND (p_organization_id IS NULL OR d.organization_id = p_organization_id)
    AND d.is_deleted = false

    UNION ALL

    -- Processing success rate
    SELECT 'processing_success_rate' as metric_name,
           (COUNT(CASE WHEN d.processing_status = 'completed' THEN 1 END)::DECIMAL /
            COUNT(CASE WHEN d.processing_status IN ('completed', 'failed') THEN 1 END)) * 100 as metric_value,
           'percent' as metric_unit
    FROM documents d
    WHERE d.processing_completed_at >= NOW() - INTERVAL '1 minute' * p_time_window_minutes
    AND (p_organization_id IS NULL OR d.organization_id = p_organization_id)
    AND d.is_deleted = false
    AND d.processing_status IN ('completed', 'failed')

    UNION ALL

    -- Queue length
    SELECT 'queue_length' as metric_name,
           COUNT(*)::DECIMAL as metric_value,
           'documents' as metric_unit
    FROM documents d
    WHERE d.processing_status = 'queued'
    AND (p_organization_id IS NULL OR d.organization_id = p_organization_id)
    AND d.is_deleted = false

    UNION ALL

    -- Average quality score
    SELECT 'avg_quality_score' as metric_name,
           AVG(d.quality_score) as metric_value,
           'score' as metric_unit
    FROM documents d
    WHERE d.quality_score IS NOT NULL
    AND d.created_at >= NOW() - INTERVAL '1 minute' * p_time_window_minutes
    AND (p_organization_id IS NULL OR d.organization_id = p_organization_id)
    AND d.is_deleted = false;
END;
$$ LANGUAGE plpgsql;

-- Step 7: Add constraints for data integrity
ALTER TABLE documents ADD CONSTRAINT chk_processing_progress_range
CHECK (processing_progress >= 0 AND processing_progress <= 100);

ALTER TABLE processing_job_executions ADD CONSTRAINT chk_overall_progress_range
CHECK (overall_progress >= 0 AND overall_progress <= 100);

ALTER TABLE stage_executions ADD CONSTRAINT chk_stage_progress_range
CHECK (progress_percentage >= 0 AND progress_percentage <= 100);

-- Step 8: Create indexes for partition management
CREATE INDEX IF NOT EXISTS idx_resource_usage_logs_partition_trigger
ON resource_usage_logs (timestamp);

-- Create trigger function to manage partitions automatically
CREATE OR REPLACE FUNCTION manage_resource_usage_partitions()
RETURNS TRIGGER AS $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
BEGIN
    -- This function would be called by a scheduled job
    -- to create new partitions as needed
    partition_date := DATE_TRUNC('month', NEW.timestamp);
    partition_name := 'resource_usage_logs_' || TO_CHAR(partition_date, 'YYYY_MM');

    -- Check if partition exists, create if needed
    PERFORM 1 FROM pg_tables WHERE tablename = partition_name;
    IF NOT FOUND THEN
        EXECUTE format('
            CREATE TABLE %I PARTITION OF resource_usage_logs_partitioned
            FOR VALUES FROM (%L) TO (%L)',
            partition_name,
            partition_date,
            partition_date + INTERVAL '1 month'
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Performance analysis queries for monitoring
COMMENT ON FUNCTION update_document_progress_batch IS 'Batch update document progress for better performance';
COMMENT ON FUNCTION get_realtime_queue_status IS 'Get real-time processing queue status';
COMMENT ON FUNCTION cleanup_old_realtime_data IS 'Clean up old realtime data to maintain performance';
COMMENT ON FUNCTION refresh_realtime_materialized_views IS 'Refresh materialized views for dashboard performance';
COMMENT ON FUNCTION get_realtime_performance_metrics IS 'Get performance metrics for monitoring';

COMMIT;