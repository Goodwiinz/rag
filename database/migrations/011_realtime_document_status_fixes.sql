-- Migration 011b: Real-time Document Status Enhancement Fixes
-- This migration fixes issues with the previous migration and adds missing components

-- Fix table references and create proper views with correct column names

-- Drop and recreate materialized views with correct column references
DROP MATERIALIZED VIEW IF EXISTS realtime_document_dashboard;
DROP MATERIALIZED VIEW IF EXISTS realtime_system_status;

-- Recreate Real-time Document Processing Dashboard View
CREATE MATERIALIZED VIEW realtime_document_dashboard AS
SELECT
    d.id,
    d.title,
    d.filename,
    d.document_type as file_type,
    d.processing_status as status,
    d.current_processing_stage,
    d.processing_progress,
    d.queue_priority,
    d.worker_assignment_id,
    d.last_status_update,
    d.created_at as uploaded_at,
    d.processing_started_at,
    u.email as uploaded_by_email,
    u.first_name || ' ' || COALESCE(u.last_name, '') as uploaded_by_name,
    -- Stage information
    COUNT(DISTINCT ps.id) as total_stages,
    COUNT(CASE WHEN ps.status = 'completed' THEN 1 END) as completed_stages,
    COUNT(CASE WHEN ps.status = 'running' THEN 1 END) as running_stages,
    COUNT(CASE WHEN ps.status = 'failed' THEN 1 END) as failed_stages,
    -- Performance calculations
    CASE
        WHEN d.processing_status = 'processing' THEN
            CASE
                WHEN COUNT(ps.id) = 0 THEN 0
                ELSE ROUND((COUNT(CASE WHEN ps.status = 'completed' THEN 1 END) * 100.0 / COUNT(ps.id)), 2)
            END
        WHEN d.processing_status = 'completed' THEN 100
        WHEN d.processing_status = 'failed' THEN 0
        ELSE d.processing_progress
    END as calculated_progress,
    -- Time calculations
    CASE
        WHEN d.processing_started_at IS NOT NULL THEN
            EXTRACT(EPOCH FROM (NOW() - d.processing_started_at))::INTEGER
        ELSE NULL
    END as processing_duration_seconds
FROM documents d
JOIN users u ON d.uploaded_by_user_id = u.id
LEFT JOIN document_processing_stages ps ON d.id = ps.document_id
WHERE d.is_deleted = FALSE
GROUP BY d.id, d.title, d.filename, d.document_type, d.processing_status,
         d.current_processing_stage, d.processing_progress, d.queue_priority,
         d.worker_assignment_id, d.last_status_update, d.created_at,
         d.processing_started_at, u.email, u.first_name, u.last_name;

-- Recreate Real-time System Status View
CREATE MATERIALIZED VIEW realtime_system_status AS
SELECT
    -- Document counts by status
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE) as total_documents,
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE AND processing_status = 'uploaded') as queued_documents,
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE AND processing_status = 'processing') as processing_documents,
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE AND processing_status = 'completed') as processed_documents,
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE AND processing_status = 'failed') as failed_documents,

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
     WHERE status = 'running') as active_jobs,

    -- Current timestamp
    NOW() as status_timestamp;

-- Create indexes for the materialized views
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_document_dashboard_id ON realtime_document_dashboard(id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_document_dashboard_status ON realtime_document_dashboard(status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_document_dashboard_progress ON realtime_document_dashboard(processing_progress);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_document_dashboard_user ON realtime_document_dashboard(uploaded_by_email);

-- Create functions for refresh
CREATE OR REPLACE FUNCTION refresh_realtime_views()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_document_dashboard;
    REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_system_status;
END;
$$ LANGUAGE plpgsql;

-- Create updated_at function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Grant appropriate permissions
GRANT SELECT ON realtime_document_dashboard TO PUBLIC;
GRANT SELECT ON realtime_system_status TO PUBLIC;

-- Analyze tables for query optimization
ANALYZE realtime_document_dashboard;
ANALYZE realtime_system_status;

-- Migration completed successfully