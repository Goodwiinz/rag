-- Migration 011: Real-time Document Processing Status Enhancements
-- This migration enhances the existing document schema to support real-time status tracking
-- with WebSocket connections, progress monitoring, and multi-stage processing visualization

-- Create extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Enhanced Documents Table - Add real-time tracking columns
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS current_processing_stage VARCHAR(100) DEFAULT 'queued',
ADD COLUMN IF NOT EXISTS processing_progress DECIMAL(5,2) DEFAULT 0.0
    CHECK (processing_progress >= 0 AND processing_progress <= 100),
ADD COLUMN IF NOT EXISTS estimated_completion_time TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS worker_assignment_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS queue_priority INTEGER DEFAULT 5
    CHECK (queue_priority BETWEEN 1 AND 10),
ADD COLUMN IF NOT EXISTS processing_metadata JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS real_time_status JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS last_status_update TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS concurrent_processing_id UUID,
ADD COLUMN IF NOT EXISTS retry_attempt INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS max_retry_attempts INTEGER DEFAULT 3,
ADD COLUMN IF NOT EXISTS processing_session_id UUID DEFAULT uuid_generate_v4();

-- Add updated_at trigger if it doesn't exist
CREATE OR REPLACE FUNCTION update_last_status_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_status_update = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for real-time status updates
CREATE TRIGGER update_documents_last_status_update
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_last_status_update();

-- 2. WebSocket Connection Management Table
CREATE TABLE IF NOT EXISTS websocket_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(255),
    socket_id VARCHAR(255),
    connected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    client_ip INET,
    user_agent TEXT,
    connection_metadata JSONB DEFAULT '{}',
    subscription_channels TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    disconnect_reason VARCHAR(100),
    disconnected_at TIMESTAMP WITH TIME ZONE,
    message_count_sent INTEGER DEFAULT 0,
    message_count_received INTEGER DEFAULT 0,
    bytes_sent BIGINT DEFAULT 0,
    bytes_received BIGINT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT websocket_connections_connection_id_not_empty
        CHECK (length(trim(connection_id)) > 0),
    CONSTRAINT websocket_connections_counts_valid
        CHECK (message_count_sent >= 0 AND message_count_received >= 0),
    CONSTRAINT websocket_connections_bytes_valid
        CHECK (bytes_sent >= 0 AND bytes_received >= 0)
);

-- 3. Real-time Status Update Queue Table
CREATE TABLE IF NOT EXISTS realtime_status_updates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    update_type VARCHAR(50) NOT NULL CHECK (update_type IN (
        'status_change', 'progress_update', 'stage_change', 'error', 'completion', 'queue_update'
    )),
    previous_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    progress_percentage DECIMAL(5,2) CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    current_stage VARCHAR(100),
    message_content TEXT,
    update_metadata JSONB DEFAULT '{}',
    priority INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    target_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    target_channels TEXT[] DEFAULT '{}',
    broadcast_all BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    delivery_status VARCHAR(20) DEFAULT 'pending' CHECK (delivery_status IN (
        'pending', 'processing', 'delivered', 'failed', 'expired'
    )),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '1 hour'),

    -- Constraints
    CONSTRAINT realtime_updates_message_content_required
        CHECK (update_type NOT IN ('status_change', 'progress_update', 'stage_change', 'completion') OR message_content IS NOT NULL)
);

-- 4. Document Processing Stages Table
CREATE TABLE IF NOT EXISTS document_processing_stages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    stage_name VARCHAR(100) NOT NULL,
    stage_order INTEGER NOT NULL,
    stage_type VARCHAR(50) NOT NULL CHECK (stage_type IN (
        'upload', 'validation', 'ocr', 'transcription', 'entity_extraction',
        'embedding', 'indexing', 'quality_check', 'completion'
    )),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN (
        'pending', 'running', 'completed', 'failed', 'skipped', 'cancelled'
    )),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    estimated_duration_seconds INTEGER,
    actual_duration_seconds INTEGER,
    progress_percentage DECIMAL(5,2) DEFAULT 0.0
        CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    worker_id VARCHAR(100),
    error_message TEXT,
    stage_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT processing_stages_unique_order
        UNIQUE(document_id, stage_order),
    CONSTRAINT processing_stages_duration_positive
        CHECK (actual_duration_seconds IS NULL OR actual_duration_seconds >= 0)
);

-- 5. Real-time Performance Metrics Table
CREATE TABLE IF NOT EXISTS realtime_performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC NOT NULL,
    metric_unit VARCHAR(50),
    metric_type VARCHAR(50) DEFAULT 'gauge' CHECK (metric_type IN (
        'gauge', 'counter', 'histogram', 'timer'
    )),
    tags JSONB DEFAULT '{}',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source_service VARCHAR(100),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    session_id VARCHAR(255),
    expiration_time TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '24 hours'),

    -- Constraints
    CONSTRAINT performance_metrics_name_not_empty
        CHECK (length(trim(metric_name)) > 0)
);

-- 6. User Subscription Management Table
CREATE TABLE IF NOT EXISTS user_realtime_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_type VARCHAR(50) NOT NULL CHECK (subscription_type IN (
        'document_updates', 'system_status', 'processing_queue', 'error_alerts', 'performance_metrics'
    )),
    subscription_target JSONB DEFAULT '{}',
    filters JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_notification_at TIMESTAMP WITH TIME ZONE,
    notification_count INTEGER DEFAULT 0,

    -- Constraints
    CONSTRAINT user_subscriptions_unique
        UNIQUE(user_id, subscription_type, subscription_target),
    CONSTRAINT user_subscriptions_count_valid
        CHECK (notification_count >= 0)
);

-- 7. System Status Broadcast Table
CREATE TABLE IF NOT EXISTS system_status_broadcasts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    broadcast_type VARCHAR(50) NOT NULL CHECK (broadcast_type IN (
        'system_maintenance', 'feature_update', 'emergency', 'performance_alert', 'capacity_warning'
    )),
    title VARCHAR(200) NOT NULL,
    message_content TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'info' CHECK (severity IN (
        'info', 'warning', 'error', 'critical'
    )),
    is_active BOOLEAN DEFAULT TRUE,
    target_audience VARCHAR(50) DEFAULT 'all' CHECK (target_audience IN (
        'all', 'administrators', 'users', 'premium_users'
    )),
    start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_time TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '24 hours'),
    broadcast_metadata JSONB DEFAULT '{}',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    delivery_count INTEGER DEFAULT 0,
    read_count INTEGER DEFAULT 0,

    -- Constraints
    CONSTRAINT system_broadcasts_title_not_empty
        CHECK (length(trim(title)) > 0),
    CONSTRAINT system_broadcasts_message_not_empty
        CHECK (length(trim(message_content)) > 0),
    CONSTRAINT system_broadcasts_time_valid
        CHECK (end_time IS NULL OR end_time >= start_time),
    CONSTRAINT system_broadcasts_counts_valid
        CHECK (delivery_count >= 0 AND read_count >= 0)
);

-- Create Indexes for Performance

-- Enhanced Documents indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_current_stage ON documents(current_processing_stage);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_processing_progress ON documents(processing_progress);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_worker_assignment ON documents(worker_assignment_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_queue_priority ON documents(queue_priority DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_last_status_update ON documents(last_status_update DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_session_id ON documents(processing_session_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_status_progress ON documents(status, processing_progress);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_realtime_lookup ON documents(uploaded_by, status, last_status_update DESC);

-- WebSocket Connections indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_websocket_connections_user_id ON websocket_connections(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_websocket_connections_session_id ON websocket_connections(session_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_websocket_connections_active ON websocket_connections(is_active) WHERE is_active = TRUE;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_websocket_connections_last_activity ON websocket_connections(last_activity DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_websocket_connections_channels_gin ON websocket_connections USING gin(subscription_channels);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_websocket_connections_created_at ON websocket_connections(created_at DESC);

-- Real-time Status Updates indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_updates_document_id ON realtime_status_updates(document_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_updates_target_user ON realtime_status_updates(target_user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_updatestatus ON realtime_status_updates(delivery_status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_updates_priority ON realtime_status_updates(priority DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_updates_created_at ON realtime_status_updates(created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_updates_expires_at ON realtime_status_updates(expires_at);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_realtime_updates_broadcast_target ON realtime_status_updates(broadcast_all, target_user_id) WHERE broadcast_all = TRUE;

-- Document Processing Stages indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_stages_document_id ON document_processing_stages(document_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_stages_status ON document_processing_stages(status);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_stages_type ON document_processing_stages(stage_type);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_stages_order ON document_processing_stages(document_id, stage_order);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_stages_progress ON document_processing_stages(progress_percentage);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_stages_worker ON document_processing_stages(worker_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_stages_updated_at ON document_processing_stages(updated_at DESC);

-- Real-time Performance Metrics indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_name ON realtime_performance_metrics(metric_name);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_timestamp ON realtime_performance_metrics(timestamp DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_user ON realtime_performance_metrics(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_document ON realtime_performance_metrics(document_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_tags_gin ON realtime_performance_metrics USING gin(tags);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_expiration ON realtime_performance_metrics(expiration_time) WHERE expiration_time IS NOT NULL;

-- User Subscriptions indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_subscriptions_user ON user_realtime_subscriptions(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_subscriptions_type ON user_realtime_subscriptions(subscription_type);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_subscriptions_active ON user_realtime_subscriptions(is_active) WHERE is_active = TRUE;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_subscriptions_last_notification ON user_realtime_subscriptions(last_notification_at DESC);

-- System Status Broadcasts indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_broadcasts_active ON system_status_broadcasts(is_active) WHERE is_active = TRUE;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_broadcasts_type ON system_status_broadcasts(broadcast_type);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_broadcasts_audience ON system_status_broadcasts(target_audience);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_broadcasts_time_range ON system_status_broadcasts(start_time, end_time);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_broadcasts_severity ON system_status_broadcasts(severity);

-- Create Materialized Views for Real-time Dashboards

-- Real-time Document Processing Dashboard View
CREATE MATERIALIZED VIEW IF NOT EXISTS realtime_document_dashboard AS
SELECT
    d.id,
    d.title,
    d.filename,
    d.file_type,
    d.status,
    d.current_processing_stage,
    d.processing_progress,
    d.queue_priority,
    d.worker_assignment_id,
    d.last_status_update,
    d.uploaded_at,
    d.processing_started_at,
    u.email as uploaded_by_email,
    u.full_name as uploaded_by_name,
    -- Stage information
    COUNT(DISTINCT ps.id) as total_stages,
    COUNT(CASE WHEN ps.status = 'completed' THEN 1 END) as completed_stages,
    COUNT(CASE WHEN ps.status = 'running' THEN 1 END) as running_stages,
    COUNT(CASE WHEN ps.status = 'failed' THEN 1 END) as failed_stages,
    -- Performance calculations
    CASE
        WHEN d.status = 'processing' THEN
            CASE
                WHEN COUNT(ps.id) = 0 THEN 0
                ELSE ROUND((COUNT(CASE WHEN ps.status = 'completed' THEN 1 END) * 100.0 / COUNT(ps.id)), 2)
            END
        WHEN d.status = 'processed' THEN 100
        WHEN d.status = 'failed' THEN 0
        ELSE d.processing_progress
    END as calculated_progress,
    -- Time calculations
    CASE
        WHEN d.processing_started_at IS NOT NULL THEN
            EXTRACT(EPOCH FROM (NOW() - d.processing_started_at))::INTEGER
        ELSE NULL
    END as processing_duration_seconds,
    -- Queue position (approximate based on priority and upload time)
    COUNT(*) OVER (PARTITION BY d.status, d.queue_priority ORDER BY d.uploaded_at DESC, d.last_status_update DESC) as queue_position
FROM documents d
JOIN users u ON d.uploaded_by = u.id
LEFT JOIN document_processing_stages ps ON d.id = ps.document_id
WHERE d.is_deleted = FALSE
GROUP BY d.id, d.title, d.filename, d.file_type, d.status,
         d.current_processing_stage, d.processing_progress, d.queue_priority,
         d.worker_assignment_id, d.last_status_update, d.uploaded_at,
         d.processing_started_at, u.email, u.full_name;

-- Real-time System Status View
CREATE MATERIALIZED VIEW IF NOT EXISTS realtime_system_status AS
SELECT
    -- Document counts by status
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE) as total_documents,
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE AND status = 'uploaded') as queued_documents,
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE AND status = 'processing') as processing_documents,
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE AND status = 'processed') as processed_documents,
    (SELECT COUNT(*) FROM documents WHERE is_deleted = FALSE AND status = 'failed') as failed_documents,

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
    (SELECT COUNT(*) FROM document_processing_jobs
     WHERE status = 'running') as active_jobs,

    -- Current timestamp
    NOW() as status_timestamp;

-- Create Views for Common Real-time Queries

-- Document Real-time Status View
CREATE OR REPLACE VIEW document_realtime_status AS
SELECT
    d.*,
    u.email as uploaded_by_email,
    u.full_name as uploaded_by_name,
    -- Processing stages aggregation
    json_agg(
        json_build_object(
            'stage_name', ps.stage_name,
            'stage_order', ps.stage_order,
            'status', ps.status,
            'progress', ps.progress_percentage,
            'started_at', ps.started_at,
            'completed_at', ps.completed_at,
            'error_message', ps.error_message
        ) ORDER BY ps.stage_order
    ) FILTER (WHERE ps.id IS NOT NULL) as processing_stages,
    -- Active WebSocket connections for this user
    (SELECT COUNT(*) FROM websocket_connections wc
     WHERE wc.user_id = d.uploaded_by AND wc.is_active = TRUE) as user_active_connections,
    -- Recent status updates
    (SELECT json_agg(
        json_build_object(
            'update_type', rsu.update_type,
            'new_status', rsu.new_status,
            'progress', rsu.progress_percentage,
            'message', rsu.message_content,
            'created_at', rsu.created_at
        ) ORDER BY rsu.created_at DESC
    ) FILTER (WHERE rsu.id IS NOT NULL) FROM (
        SELECT * FROM realtime_status_updates
        WHERE document_id = d.id
        ORDER BY created_at DESC
        LIMIT 10
    ) rsu) as recent_status_updates
FROM documents d
JOIN users u ON d.uploaded_by = u.id
LEFT JOIN document_processing_stages ps ON d.id = ps.document_id
WHERE d.is_deleted = FALSE
GROUP BY d.id, u.email, u.full_name;

-- WebSocket Management View
CREATE OR REPLACE VIEW websocket_connection_summary AS
SELECT
    wc.*,
    u.email as user_email,
    u.full_name as user_name,
    -- Documents user is currently processing
    (SELECT COUNT(*) FROM documents d
     WHERE d.uploaded_by = wc.user_id AND d.status IN ('processing', 'uploaded')) as user_processing_documents,
    -- Subscription counts
    ARRAY_LENGTH(wc.subscription_channels, 1) as channel_count,
    -- Connection age
    EXTRACT(EPOCH FROM (NOW() - wc.connected_at))::INTEGER as connection_age_seconds,
    -- Last activity age
    EXTRACT(EPOCH FROM (NOW() - wc.last_activity))::INTEGER as last_activity_seconds
FROM websocket_connections wc
JOIN users u ON wc.user_id = u.id;

-- Create Updated At Triggers for New Tables
CREATE TRIGGER update_websocket_connections_updated_at
    BEFORE UPDATE ON websocket_connections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_realtime_status_updates_updated_at
    BEFORE UPDATE ON realtime_status_updates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_processing_stages_updated_at
    BEFORE UPDATE ON document_processing_stages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_realtime_subscriptions_updated_at
    BEFORE UPDATE ON user_realtime_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create Row Level Security (RLS) Policies for New Tables
ALTER TABLE websocket_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE realtime_status_updates ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_processing_stages ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_realtime_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE realtime_performance_metrics ENABLE ROW LEVEL SECURITY;

-- WebSocket Connections RLS Policy
CREATE POLICY websocket_connections_user_policy ON websocket_connections
    FOR ALL
    TO authenticated_users
    USING (user_id = current_user_id())
    WITH CHECK (user_id = current_user_id());

-- Real-time Status Updates RLS Policy
CREATE POLICY realtime_status_updates_user_policy ON realtime_status_updates
    FOR SELECT
    TO authenticated_users
    USING (target_user_id = current_user_id() OR broadcast_all = TRUE);

-- Document Processing Stages RLS Policy
CREATE POLICY document_processing_stages_user_policy ON document_processing_stages
    FOR ALL
    TO authenticated_users
    USING (EXISTS (
        SELECT 1 FROM documents d
        WHERE d.id = document_processing_stages.document_id
        AND d.uploaded_by = current_user_id()
    ));

-- User Real-time Subscriptions RLS Policy
CREATE POLICY user_realtime_subscriptions_user_policy ON user_realtime_subscriptions
    FOR ALL
    TO authenticated_users
    USING (user_id = current_user_id())
    WITH CHECK (user_id = current_user_id());

-- Real-time Performance Metrics RLS Policy
CREATE POLICY realtime_performance_metrics_user_policy ON realtime_performance_metrics
    FOR SELECT
    TO authenticated_users
    USING (user_id = current_user_id() OR user_id IS NULL);

-- Grant Permissions
GRANT ALL ON websocket_connections TO authenticated_users;
GRANT SELECT ON realtime_status_updates TO authenticated_users;
GRANT ALL ON document_processing_stages TO authenticated_users;
GRANT ALL ON user_realtime_subscriptions TO authenticated_users;
GRANT SELECT ON realtime_performance_metrics TO authenticated_users;
GRANT SELECT ON system_status_broadcasts TO authenticated_users;

-- Grant access to views
GRANT SELECT ON document_realtime_status TO authenticated_users;
GRANT SELECT ON websocket_connection_summary TO authenticated_users;
GRANT SELECT ON realtime_document_dashboard TO authenticated_users;
GRANT SELECT ON realtime_system_status TO authenticated_users;

-- Create Functions for Real-time Operations

-- Function to update document processing status with real-time notifications
CREATE OR REPLACE FUNCTION update_document_realtime_status(
    p_document_id UUID,
    p_new_status VARCHAR(50),
    p_progress DECIMAL(5,2) DEFAULT NULL,
    p_stage VARCHAR(100) DEFAULT NULL,
    p_worker_id VARCHAR(100) DEFAULT NULL,
    p_message TEXT DEFAULT NULL,
    p_broadcast BOOLEAN DEFAULT FALSE
) RETURNS BOOLEAN AS $$
DECLARE
    v_old_status VARCHAR(50);
    v_user_id UUID;
    v_update_id UUID;
BEGIN
    -- Get old status and user info
    SELECT status, uploaded_by INTO v_old_status, v_user_id
    FROM documents
    WHERE id = p_document_id;

    -- Update document status
    UPDATE documents
    SET
        status = p_new_status,
        processing_progress = COALESCE(p_progress, processing_progress),
        current_processing_stage = COALESCE(p_stage, current_processing_stage),
        worker_assignment_id = COALESCE(p_worker_id, worker_assignment_id),
        last_status_update = NOW()
    WHERE id = p_document_id;

    -- Create real-time status update
    INSERT INTO realtime_status_updates (
        document_id,
        update_type,
        previous_status,
        new_status,
        progress_percentage,
        current_stage,
        message_content,
        target_user_id,
        broadcast_all
    ) VALUES (
        p_document_id,
        'status_change',
        v_old_status,
        p_new_status,
        p_progress,
        p_stage,
        p_message,
        v_user_id,
        p_broadcast
    ) RETURNING id INTO v_update_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function to get active WebSocket connections for a user
CREATE OR REPLACE FUNCTION get_user_websocket_connections(
    p_user_id UUID
) RETURNS TABLE (
    connection_id VARCHAR,
    session_id VARCHAR,
    connected_at TIMESTAMP WITH TIME ZONE,
    last_activity TIMESTAMP WITH TIME ZONE,
    subscription_channels TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        wc.connection_id,
        wc.session_id,
        wc.connected_at,
        wc.last_activity,
        wc.subscription_channels
    FROM websocket_connections wc
    WHERE wc.user_id = p_user_id
    AND wc.is_active = TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function to create materialized view refresh job
CREATE OR REPLACE FUNCTION refresh_realtime_views()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_document_dashboard;
    REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_system_status;
END;
$$ LANGUAGE plpgsql;

-- Add Comments for Documentation
COMMENT ON TABLE websocket_connections IS 'Tracks active WebSocket connections for real-time communication';
COMMENT ON TABLE realtime_status_updates IS 'Queue for real-time status update messages to be delivered via WebSocket';
COMMENT ON TABLE document_processing_stages IS 'Detailed tracking of multi-stage document processing pipeline';
COMMENT ON TABLE realtime_performance_metrics IS 'Time-series metrics for system performance monitoring';
COMMENT ON TABLE user_realtime_subscriptions IS 'User preferences for real-time notifications and updates';
COMMENT ON TABLE system_status_broadcasts IS 'System-wide announcements and alerts';

-- Migration completed successfully
-- Run ANALYZE to update table statistics
ANALYZE websocket_connections;
ANALYZE realtime_status_updates;
ANALYZE document_processing_stages;
ANALYZE realtime_performance_metrics;
ANALYZE user_realtime_subscriptions;
ANALYZE system_status_broadcasts;

-- Create initial indexes optimization
REINDEX INDEX CONCURRENTLY idx_documents_current_stage;
REINDEX INDEX CONCURRENTLY idx_websocket_connections_user_id;
REINDEX INDEX CONCURRENTLY idx_realtime_updates_document_id;

-- Schedule periodic refresh of materialized views (requires pg_cron extension)
-- SELECT cron.schedule('refresh-realtime-views', '*/30 * * * *', 'SELECT refresh_realtime_views();');

-- Migration complete - Real-time document processing status system is ready