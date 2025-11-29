-- WebSocket Integration Schema for Real-Time Updates
-- Extends existing WebSocket schema with document processing-specific features

BEGIN;

-- Create specialized status updates for document processing
CREATE TABLE IF NOT EXISTS document_processing_updates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Update identification
    update_id VARCHAR(255) NOT NULL UNIQUE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    job_execution_id UUID REFERENCES processing_job_executions(id) ON DELETE CASCADE,
    stage_execution_id UUID REFERENCES stage_executions(id) ON DELETE CASCADE,

    -- Update classification
    update_type VARCHAR(50) NOT NULL CHECK (update_type IN (
        'status_change', 'progress_update', 'stage_complete', 'stage_failed',
        'agent_update', 'error_occurred', 'resource_warning', 'completion',
        'batch_update', 'queue_position', 'eta_update', 'quality_metric'
    )),
    update_level VARCHAR(20) DEFAULT 'info' CHECK (update_level IN ('debug', 'info', 'warning', 'error', 'critical')),
    priority VARCHAR(20) DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'critical', 'urgent')),

    -- Update content
    title VARCHAR(255) NOT NULL,
    message TEXT,
    update_data JSONB DEFAULT '{}',

    -- Progress information
    progress_percentage DECIMAL(5,2),
    current_stage VARCHAR(100),
    current_step VARCHAR(255),
    estimated_remaining_seconds INTEGER,

    -- Performance information
    processing_rate DECIMAL(10,2),  -- items per second
    quality_score DECIMAL(5,4),
    error_rate DECIMAL(5,4),

    -- Delivery configuration
    target_connections TEXT[] DEFAULT '{}',  -- Specific connection IDs
    target_users UUID[] DEFAULT '{}',        -- Specific user IDs
    target_channels TEXT[] DEFAULT '{}',     -- Broadcast channels
    broadcast_all BOOLEAN DEFAULT FALSE,

    -- Delivery tracking
    created_at TIMESTAMPTZ DEFAULT NOW(),
    scheduled_for TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,

    -- Delivery status
    delivery_status VARCHAR(50) DEFAULT 'pending' CHECK (delivery_status IN (
        'pending', 'scheduled', 'sending', 'sent', 'delivered', 'acknowledged', 'failed', 'expired'
    )),
    delivery_attempts INTEGER DEFAULT 0,
    max_delivery_attempts INTEGER DEFAULT 3,

    -- Delivery results
    delivery_errors JSONB DEFAULT '{}',
    successful_deliveries INTEGER DEFAULT 0,
    failed_deliveries INTEGER DEFAULT 0,

    -- User interaction
    requires_acknowledgment BOOLEAN DEFAULT FALSE,
    acknowledged_by UUID[] DEFAULT '{}',
    acknowledgment_required_by TIMESTAMPTZ,

    -- Update metadata
    is_dismissible BOOLEAN DEFAULT TRUE,
    action_required BOOLEAN DEFAULT FALSE,
    action_url VARCHAR(500),
    action_button_text VARCHAR(100),

    -- Throttling and deduplication
    deduplication_key VARCHAR(255),
    throttle_key VARCHAR(255),
    last_throttled_at TIMESTAMPTZ,

    -- Caching and performance
    is_cached BOOLEAN DEFAULT FALSE,
    cache_ttl_seconds INTEGER DEFAULT 300,
    cache_hit_count INTEGER DEFAULT 0,

    -- Analytics
    click_count INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    engagement_duration_ms INTEGER,

    created_by_user_id UUID REFERENCES users(id),
    processing_metadata JSONB DEFAULT '{}',

    -- Constraints
    CONSTRAINT valid_progress CHECK (progress_percentage IS NULL OR (progress_percentage >= 0 AND progress_percentage <= 100)),
    CONSTRAINT valid_quality CHECK (quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1)),
    CONSTRAINT valid_error_rate CHECK (error_rate IS NULL OR (error_rate >= 0 AND error_rate <= 1))
);

-- Real-time subscription management
CREATE TABLE IF NOT EXISTS realtime_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Subscription identification
    subscription_id VARCHAR(255) NOT NULL UNIQUE,
    connection_id VARCHAR(255) NOT NULL REFERENCES websocket_connections(connection_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Subscription configuration
    subscription_type VARCHAR(50) NOT NULL CHECK (subscription_type IN (
        'document_processing', 'job_updates', 'stage_progress', 'system_notifications',
        'error_alerts', 'performance_metrics', 'batch_operations', 'queue_status'
    )),

    -- Subscription filters
    filter_criteria JSONB DEFAULT '{}',
    document_types TEXT[] DEFAULT '{}',
    processing_stages TEXT[] DEFAULT '{}',
    update_types TEXT[] DEFAULT '{}',
    priority_levels TEXT[] DEFAULT '{}',

    -- Subscription scope
    document_ids UUID[] DEFAULT '{}',
    job_execution_ids UUID[] DEFAULT '{}',
    user_ids UUID[] DEFAULT '{}',

    -- Subscription settings
    is_active BOOLEAN DEFAULT TRUE,
    receive_updates BOOLEAN DEFAULT TRUE,
    receive_errors BOOLEAN DEFAULT FALSE,
    receive_progress BOOLEAN DEFAULT TRUE,
    receive_completions BOOLEAN DEFAULT TRUE,

    -- Throttling settings
    max_updates_per_minute INTEGER DEFAULT 30,
    current_rate INTEGER DEFAULT 0,
    rate_window_start TIMESTAMPTZ DEFAULT NOW(),

    -- Subscription metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,

    -- Performance tracking
    total_updates_sent INTEGER DEFAULT 0,
    total_updates_filtered INTEGER DEFAULT 0,
    last_update_sent_at TIMESTAMPTZ,
    average_delivery_latency_ms INTEGER,

    subscription_metadata JSONB DEFAULT '{}',

    -- Constraints
    CONSTRAINT valid_rate CHECK (max_updates_per_minute >= 0)
);

-- Update queue for reliable delivery
CREATE TABLE IF NOT EXISTS update_delivery_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Queue identification
    queue_id VARCHAR(255) NOT NULL UNIQUE,
    update_id UUID NOT NULL REFERENCES document_processing_updates(id) ON DELETE CASCADE,
    connection_id VARCHAR(255) NOT NULL,

    -- Queue status
    queue_status VARCHAR(50) DEFAULT 'queued' CHECK (queue_status IN (
        'queued', 'processing', 'sent', 'delivered', 'failed', 'cancelled', 'expired'
    )),

    -- Delivery timing
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    processing_started_at TIMESTAMPTZ,
    delivery_attempted_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,

    -- Delivery configuration
    priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    max_attempts INTEGER DEFAULT 3,
    current_attempt INTEGER DEFAULT 0,

    -- Retry configuration
    retry_delay_seconds INTEGER DEFAULT 5,
    backoff_multiplier DECIMAL(3,2) DEFAULT 2.0,
    max_retry_delay_seconds INTEGER DEFAULT 300,

    -- Delivery tracking
    delivery_method VARCHAR(50) DEFAULT 'websocket',
    delivery_metadata JSONB DEFAULT '{}',

    -- Error tracking
    last_error_message TEXT,
    last_error_type VARCHAR(100),
    error_details JSONB DEFAULT '{}',

    -- Performance tracking
    processing_duration_ms INTEGER,
    delivery_duration_ms INTEGER,
    total_duration_ms INTEGER,

    queue_metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_attempt CHECK (current_attempt <= max_attempts),
    CONSTRAINT valid_priority CHECK (priority >= 1 AND priority <= 10)
);

-- Connection performance metrics
CREATE TABLE IF NOT EXISTS connection_performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Connection identification
    connection_id VARCHAR(255) NOT NULL REFERENCES websocket_connections(connection_id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Metrics period
    metrics_period_start TIMESTAMPTZ NOT NULL,
    metrics_period_end TIMESTAMPTZ NOT NULL,
    metrics_window_minutes INTEGER DEFAULT 5,

    -- Update metrics
    updates_sent INTEGER DEFAULT 0,
    updates_delivered INTEGER DEFAULT 0,
    updates_failed INTEGER DEFAULT 0,
    updates_filtered INTEGER DEFAULT 0,

    -- Performance metrics
    average_latency_ms DECIMAL(10,2),
    max_latency_ms INTEGER,
    min_latency_ms INTEGER,
    p95_latency_ms INTEGER,

    -- Throughput metrics
    messages_per_second DECIMAL(10,2),
    bytes_per_second DECIMAL(10,2),
    updates_per_second DECIMAL(10,2),

    -- Error metrics
    error_rate DECIMAL(5,4),
    timeout_count INTEGER DEFAULT 0,
    reconnection_count INTEGER DEFAULT 0,

    -- Resource metrics
    memory_usage_mb INTEGER,
    cpu_usage_percent DECIMAL(5,2),

    -- Quality metrics
    message_loss_rate DECIMAL(5,4),
    duplicate_rate DECIMAL(5,4),
    out_of_order_rate DECIMAL(5,4),

    metrics_metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_period CHECK (metrics_period_end > metrics_period_start),
    CONSTRAINT valid_metrics_window CHECK (metrics_window_minutes > 0)
);

-- Real-time event log for debugging and analytics
CREATE TABLE IF NOT EXISTS realtime_event_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event identification
    event_id VARCHAR(255) NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50) NOT NULL CHECK (event_category IN (
        'connection', 'subscription', 'update', 'delivery', 'error', 'performance', 'system'
    )),

    -- Event context
    connection_id VARCHAR(255) REFERENCES websocket_connections(connection_id) ON DELETE CASCADE,
    update_id UUID REFERENCES document_processing_updates(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,

    -- Event details
    event_data JSONB DEFAULT '{}',
    event_metadata JSONB DEFAULT '{}',

    -- Event impact
    affected_connections INTEGER DEFAULT 0,
    affected_users INTEGER DEFAULT 0,
    affected_updates INTEGER DEFAULT 0,

    -- Performance impact
    processing_time_ms INTEGER,
    memory_impact_mb INTEGER,
    cpu_impact_percent DECIMAL(5,2),

    -- Error information
    error_occurred BOOLEAN DEFAULT FALSE,
    error_type VARCHAR(100),
    error_message TEXT,
    error_severity VARCHAR(20) DEFAULT 'error' CHECK (error_severity IN ('debug', 'info', 'warning', 'error', 'critical')),

    -- Timing
    occurred_at TIMESTAMPTZ DEFAULT NOW(),
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,

    -- Event correlation
    correlation_id VARCHAR(255),
    parent_event_id VARCHAR(255) REFERENCES realtime_event_log(event_id),
    related_events TEXT[] DEFAULT '{}',

    -- System context
    server_instance VARCHAR(100),
    service_version VARCHAR(50),
    configuration_snapshot JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Update aggregation for dashboard and analytics
CREATE TABLE IF NOT EXISTS realtime_update_aggregates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Aggregation identification
    aggregate_key VARCHAR(255) NOT NULL,
    aggregation_type VARCHAR(50) NOT NULL CHECK (aggregation_type IN (
        'hourly', 'daily', 'weekly', 'monthly', 'realtime_window'
    )),

    -- Aggregation scope
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    document_type VARCHAR(50),
    processing_stage VARCHAR(100),

    -- Time window
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    window_duration_minutes INTEGER NOT NULL,

    -- Update counts
    total_updates BIGINT DEFAULT 0,
    status_change_updates BIGINT DEFAULT 0,
    progress_updates BIGINT DEFAULT 0,
    completion_updates BIGINT DEFAULT 0,
    error_updates BIGINT DEFAULT 0,

    -- Performance metrics
    average_delivery_latency_ms DECIMAL(10,2),
    p95_delivery_latency_ms INTEGER,
    success_rate DECIMAL(5,4),
    throughput_updates_per_second DECIMAL(10,2),

    -- User engagement
    unique_users INTEGER DEFAULT 0,
    unique_connections INTEGER DEFAULT 0,
    average_engagement_duration_ms INTEGER,

    -- Resource usage
    total_bytes_sent BIGINT DEFAULT 0,
    average_message_size_bytes INTEGER DEFAULT 0,
    peak_concurrent_updates INTEGER DEFAULT 0,

    -- Error metrics
    error_rate DECIMAL(5,4),
    timeout_rate DECIMAL(5,4),
    reconnection_rate DECIMAL(5,4),

    aggregates_metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_window CHECK (window_end > window_start),
    CONSTRAINT valid_duration CHECK (window_duration_minutes > 0),
    CONSTRAINT valid_success_rate CHECK (success_rate >= 0 AND success_rate <= 1),
    CONSTRAINT valid_rates CHECK (error_rate >= 0 AND error_rate <= 1),
    UNIQUE(aggregate_key, window_start, window_end)
);

-- Create indexes for WebSocket real-time performance
CREATE INDEX IF NOT EXISTS idx_document_updates_document ON document_processing_updates(document_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_document_updates_job ON document_processing_updates(job_execution_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_document_updates_stage ON document_processing_updates(stage_execution_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_document_updates_type ON document_processing_updates(update_type, delivery_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_document_updates_priority ON document_processing_updates(priority, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_document_updates_delivery ON document_processing_updates(delivery_status, scheduled_for ASC);
CREATE INDEX IF NOT EXISTS idx_document_updates_expires ON document_processing_updates(expires_at, delivery_status);
CREATE INDEX IF NOT EXISTS idx_document_updates_deduplication ON document_processing_updates(deduplication_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_realtime_subscriptions_connection ON realtime_subscriptions(connection_id, subscription_type);
CREATE INDEX IF NOT EXISTS idx_realtime_subscriptions_user ON realtime_subscriptions(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_realtime_subscriptions_org ON realtime_subscriptions(organization_id, subscription_type);
CREATE INDEX IF NOT EXISTS idx_realtime_subscriptions_rate ON realtime_subscriptions(rate_window_start, current_rate);
CREATE INDEX IF NOT EXISTS idx_realtime_subscriptions_activity ON realtime_subscriptions(last_activity_at DESC);

CREATE INDEX IF NOT EXISTS idx_update_queue_update ON update_delivery_queue(update_id, queue_status);
CREATE INDEX IF NOT EXISTS idx_update_queue_connection ON update_delivery_queue(connection_id, queue_status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_update_queue_priority ON update_delivery_queue(priority DESC, queued_at ASC) WHERE queue_status = 'queued';
CREATE INDEX IF NOT EXISTS idx_update_queue_retry ON update_delivery_queue(next_retry_at, queue_status) WHERE queue_status = 'failed';
CREATE INDEX IF NOT EXISTS idx_update_queue_expires ON update_delivery_queue(expires_at, queue_status);

CREATE INDEX IF NOT EXISTS idx_connection_metrics_connection ON connection_performance_metrics(connection_id, metrics_period_start DESC);
CREATE INDEX IF NOT EXISTS idx_connection_metrics_org_period ON connection_performance_metrics(organization_id, metrics_period_start DESC);
CREATE INDEX IF NOT EXISTS idx_connection_metrics_window ON connection_performance_metrics(metrics_window_minutes, metrics_period_start DESC);

CREATE INDEX IF NOT EXISTS idx_realtime_events_type ON realtime_event_log(event_type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_realtime_events_category ON realtime_event_log(event_category, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_realtime_events_connection ON realtime_event_log(connection_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_realtime_events_error ON realtime_event_log(error_occurred, error_severity, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_realtime_events_correlation ON realtime_event_log(correlation_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_update_aggregates_key ON realtime_update_aggregates(aggregate_key, window_start DESC);
CREATE INDEX IF NOT EXISTS idx_update_aggregates_org ON realtime_update_aggregates(organization_id, aggregation_type, window_start DESC);
CREATE INDEX IF NOT EXISTS idx_update_aggregates_type ON realtime_update_aggregates(aggregation_type, window_start DESC);

-- Enable Row Level Security
ALTER TABLE document_processing_updates ENABLE ROW LEVEL SECURITY;
ALTER TABLE realtime_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE update_delivery_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE connection_performance_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE realtime_event_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE realtime_update_aggregates ENABLE ROW LEVEL SECURITY;

-- RLS policies
CREATE POLICY document_updates_org_policy ON document_processing_updates
    FOR ALL TO authenticated_users
    USING (document_id IN (
        SELECT id FROM documents
        WHERE organization_id = current_setting('app.current_organization_id', true)::UUID
    ));

CREATE POLICY realtime_subscriptions_org_policy ON realtime_subscriptions
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Triggers for automatic cleanup and management
CREATE OR REPLACE FUNCTION cleanup_expired_realtime_data()
RETURNS TRIGGER AS $$
BEGIN
    -- Clean up expired updates
    DELETE FROM document_processing_updates
    WHERE expires_at IS NOT NULL
    AND expires_at < NOW()
    AND delivery_status IN ('delivered', 'acknowledged', 'expired');

    -- Clean up old event logs (keep 7 days)
    DELETE FROM realtime_event_log
    WHERE occurred_at < NOW() - INTERVAL '7 days';

    -- Clean up old performance metrics (keep 30 days)
    DELETE FROM connection_performance_metrics
    WHERE metrics_period_end < NOW() - INTERVAL '30 days';

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create scheduled cleanup trigger (would need pg_cron extension for actual scheduling)
-- This is just a placeholder that would be called by a scheduled job

COMMIT;