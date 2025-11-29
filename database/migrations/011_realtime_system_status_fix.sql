-- Migration 011d: Real-time System Status View Fix
-- This migration creates the system status view with correct enum values

-- Create Real-time System Status View
CREATE MATERIALIZED VIEW realtime_system_status AS
SELECT
    -- Document counts by status
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE) as total_documents,
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE AND processing_status = 'PENDING') as queued_documents,
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE AND processing_status = 'PROCESSING') as processing_documents,
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE AND processing_status = 'COMPLETED') as processed_documents,
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE AND processing_status = 'FAILED') as failed_documents,

    -- WebSocket connection stats
    (SELECT COUNT(*) FROM websocket_connections WHERE is_active = TRUE) as active_websocket_connections,
    (SELECT COUNT(DISTINCT user_id) FROM websocket_connections WHERE is_active = TRUE) as connected_users,

    -- Performance metrics (last 5 minutes)
    (SELECT AVG(metric_value::numeric) FROM realtime_performance_metrics
     WHERE metric_name = 'document_processing_duration'
     AND timestamp >= NOW() - INTERVAL '5 minutes') as avg_processing_time_5min,

    (SELECT COUNT(*) FROM realtime_status_updates
     WHERE created_at >= NOW() - INTERVAL '5 minutes') as updates_last_5min,

    -- System health
    (SELECT COUNT(*) FROM processing_jobs
     WHERE status = 'RUNNING') as active_jobs,

    -- Current timestamp
    NOW() as status_timestamp;

-- Create indexes for the materialized view
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_system_status_timestamp ON realtime_system_status(status_timestamp);

-- Grant appropriate permissions
GRANT SELECT ON realtime_system_status TO PUBLIC;

-- Analyze table for query optimization
ANALYZE realtime_system_status;

-- Migration completed successfully