-- Migration 005: Create monitoring, performance, and system health tables
-- Comprehensive system observability and alerting infrastructure

BEGIN;

-- Performance metrics collection (partitioned by time)
CREATE TABLE performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,

    -- Metric identification
    metric_name VARCHAR(255) NOT NULL,
    metric_category VARCHAR(100) NOT NULL, -- system, search, processing, user_experience
    metric_type VARCHAR(50) NOT NULL, -- counter, gauge, histogram, timer

    -- Metric values
    value DECIMAL(15,6) NOT NULL,
    unit VARCHAR(50),

    -- Thresholds and alerts
    threshold_warning DECIMAL(15,6),
    threshold_critical DECIMAL(15,6),
    alert_triggered BOOLEAN DEFAULT FALSE,

    -- Context
    component VARCHAR(100), -- api_worker, search_engine, embedding_service, etc.
    environment VARCHAR(50) DEFAULT 'production',
    node_id VARCHAR(100),

    -- Additional data
    tags JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',

    -- Timing
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (timestamp);

-- Create weekly partitions for performance metrics
CREATE TABLE performance_metrics_y2024w01 PARTITION OF performance_metrics
    FOR VALUES FROM ('2024-01-01') TO ('2024-01-08');

CREATE TABLE performance_metrics_y2024w02 PARTITION OF performance_metrics
    FOR VALUES FROM ('2024-01-08') TO ('2024-01-15');

-- System health monitoring
CREATE TABLE system_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Component identification
    component_name VARCHAR(100) NOT NULL,
    component_type VARCHAR(50) NOT NULL, -- database, vector_store, cache, api, worker
    node_id VARCHAR(100),

    -- Health status
    status VARCHAR(50) NOT NULL CHECK (status IN ('healthy', 'degraded', 'critical', 'offline')),
    health_score DECIMAL(3,2) CHECK (health_score >= 0 AND health_score <= 1),

    -- Performance metrics
    response_time_ms INTEGER,
    success_rate DECIMAL(5,4),
    error_rate DECIMAL(5,4),

    -- Resource usage
    cpu_usage_percent DECIMAL(5,2),
    memory_usage_mb DECIMAL(10,2),
    memory_usage_percent DECIMAL(5,2),
    disk_usage_gb DECIMAL(10,2),
    disk_usage_percent DECIMAL(5,2),

    -- Dependencies
    dependencies JSONB DEFAULT '{}', -- Status of dependent services
    health_checks JSONB DEFAULT '{}', -- Individual health check results

    -- Status tracking
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    consecutive_failures INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(component_name, node_id)
);

-- Error tracking and logging (partitioned by time)
CREATE TABLE error_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Error identification
    error_id VARCHAR(100) UNIQUE NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_code VARCHAR(50),
    error_message TEXT NOT NULL,
    error_stack TEXT,

    -- Severity and classification
    severity VARCHAR(50) DEFAULT 'error' CHECK (severity IN ('warning', 'error', 'critical')),
    category VARCHAR(100), -- validation, authentication, processing, infrastructure

    -- Context
    component VARCHAR(100),
    function_name VARCHAR(255),
    line_number INTEGER,

    -- User and organization context
    organization_id UUID REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    session_id UUID REFERENCES user_sessions(id),

    -- Request context
    request_id VARCHAR(255),
    endpoint VARCHAR(255),
    http_method VARCHAR(10),
    http_status_code INTEGER,

    -- System context
    node_id VARCHAR(100),
    environment VARCHAR(50),
    version VARCHAR(50),

    -- Additional context
    context_data JSONB DEFAULT '{}',
    system_metadata JSONB DEFAULT '{}',

    -- Resolution tracking
    resolution_status VARCHAR(50) DEFAULT 'open' CHECK (resolution_status IN ('open', 'investigating', 'resolved', 'wont_fix')),
    resolved_by UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,

    occurred_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (occurred_at);

-- Create monthly partitions for error logs
CREATE TABLE error_logs_y2024m01 PARTITION OF error_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE error_logs_y2024m02 PARTITION OF error_logs
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- User interaction events (partitioned by time)
CREATE TABLE user_interaction_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID REFERENCES users(id),
    session_id UUID REFERENCES user_sessions(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),

    event_type VARCHAR(100) NOT NULL, -- click, hover, scroll, download, share, etc.
    event_action VARCHAR(100) NOT NULL,

    -- Event context
    component VARCHAR(100), -- search_results, document_viewer, etc.
    element_id VARCHAR(255),
    element_type VARCHAR(100),

    -- Document/Query context
    document_id VARCHAR(255),
    query_id UUID REFERENCES search_queries(id),
    result_position INTEGER,

    -- Event data
    event_data JSONB DEFAULT '{}',
    coordinates JSONB, -- x, y coordinates for UI events

    client_timestamp TIMESTAMPTZ,
    server_timestamp TIMESTAMPTZ DEFAULT NOW(),

    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (server_timestamp);

-- Create monthly partitions for user interaction events
CREATE TABLE user_interaction_events_y2024m01 PARTITION OF user_interaction_events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE user_interaction_events_y2024m02 PARTITION OF user_interaction_events
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- System alerts and notifications
CREATE TABLE system_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Alert identification
    alert_name VARCHAR(255) NOT NULL,
    alert_type VARCHAR(100) NOT NULL, -- performance, availability, security, capacity
    severity VARCHAR(50) NOT NULL CHECK (severity IN ('info', 'warning', 'critical', 'emergency')),

    -- Alert configuration
    rule_name VARCHAR(255),
    rule_condition JSONB,
    threshold_value DECIMAL(15,6),
    current_value DECIMAL(15,6),

    -- Status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'acknowledged', 'resolved', 'suppressed')),

    -- Context
    component VARCHAR(100),
    organization_id UUID REFERENCES organizations(id),
    node_id VARCHAR(100),

    -- Timing
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id),

    -- Notification
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_channels JSONB DEFAULT '[]',
    notification_attempts INTEGER DEFAULT 0,

    -- Details
    alert_details JSONB DEFAULT '{}',
    resolution_notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- API usage tracking
CREATE TABLE api_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Request information
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    http_status_code INTEGER NOT NULL,

    -- User context
    user_id UUID REFERENCES users(id),
    organization_id UUID REFERENCES organizations(id),
    session_id UUID REFERENCES user_sessions(id),

    -- Performance
    response_time_ms INTEGER,
    request_size_bytes INTEGER,
    response_size_bytes INTEGER,

    -- Request details
    request_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    referer VARCHAR(500),

    -- API key and authentication
    api_key_id VARCHAR(255),
    auth_method VARCHAR(50),

    -- Rate limiting
    rate_limited BOOLEAN DEFAULT FALSE,
    rate_limit_reason VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Create monthly partitions for API usage logs
CREATE TABLE api_usage_logs_y2024m01 PARTITION OF api_usage_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE api_usage_logs_y2024m02 PARTITION OF api_usage_logs
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- Resource usage tracking
CREATE TABLE resource_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Resource identification
    resource_type VARCHAR(100) NOT NULL, -- database, storage, compute, bandwidth
    resource_id VARCHAR(255) NOT NULL,
    organization_id UUID REFERENCES organizations(id),

    -- Usage metrics
    usage_amount DECIMAL(15,6) NOT NULL,
    usage_unit VARCHAR(50) NOT NULL,
    cost_usd DECIMAL(10,6),

    -- Quota information
    quota_limit DECIMAL(15,6),
    quota_remaining DECIMAL(15,6),
    quota_exceeded BOOLEAN DEFAULT FALSE,

    -- Time period
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,

    -- Additional data
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(resource_type, resource_id, organization_id, period_start, period_end)
);

-- Create indexes for monitoring tables
CREATE INDEX idx_performance_metrics_name_time ON performance_metrics(metric_name, timestamp DESC);
CREATE INDEX idx_performance_metrics_category_time ON performance_metrics(metric_category, timestamp DESC);
CREATE INDEX idx_performance_metrics_org_time ON performance_metrics(organization_id, timestamp DESC) WHERE organization_id IS NOT NULL;
CREATE INDEX idx_performance_metrics_alert ON performance_metrics(alert_triggered, timestamp DESC);
CREATE INDEX idx_performance_metrics_component ON performance_metrics(component, timestamp DESC);

CREATE INDEX idx_system_health_status ON system_health(status, health_score);
CREATE INDEX idx_system_health_component ON system_health(component_type, node_id);
CREATE INDEX idx_system_health_updated ON system_health(updated_at DESC);
CREATE INDEX idx_system_health_failures ON system_health(consecutive_failures DESC);

CREATE INDEX idx_error_logs_type ON error_logs(error_type, occurred_at DESC);
CREATE INDEX idx_error_logs_severity ON error_logs(severity, occurred_at DESC);
CREATE INDEX idx_error_logs_component ON error_logs(component, occurred_at DESC);
CREATE INDEX idx_error_logs_status ON error_logs(resolution_status, occurred_at DESC);
CREATE INDEX idx_error_logs_organization ON error_logs(organization_id, occurred_at DESC);
CREATE INDEX idx_error_logs_user ON error_logs(user_id, occurred_at DESC);

CREATE INDEX idx_interaction_events_user ON user_interaction_events(user_id, server_timestamp DESC);
CREATE INDEX idx_interaction_events_session ON user_interaction_events(session_id, server_timestamp DESC);
CREATE INDEX idx_interaction_events_type ON user_interaction_events(event_type, server_timestamp DESC);
CREATE INDEX idx_interaction_events_component ON user_interaction_events(component, server_timestamp DESC);
CREATE INDEX idx_interaction_events_org ON user_interaction_events(organization_id, server_timestamp DESC);

CREATE INDEX idx_system_alerts_type ON system_alerts(alert_type, severity, status);
CREATE INDEX idx_system_alerts_component ON system_alerts(component, status);
CREATE INDEX idx_system_alerts_triggered ON system_alerts(triggered_at DESC);
CREATE INDEX idx_system_alerts_org ON system_alerts(organization_id, triggered_at DESC);

CREATE INDEX idx_api_usage_endpoint ON api_usage_logs(endpoint, created_at DESC);
CREATE INDEX idx_api_usage_user ON api_usage_logs(user_id, created_at DESC);
CREATE INDEX idx_api_usage_org ON api_usage_logs(organization_id, created_at DESC);
CREATE INDEX idx_api_usage_status ON api_usage_logs(http_status_code, created_at DESC);
CREATE INDEX idx_api_usage_response_time ON api_usage_logs(response_time_ms DESC, created_at DESC);

CREATE INDEX idx_resource_usage_type ON resource_usage(resource_type, organization_id, period_start DESC);
CREATE INDEX idx_resource_usage_quota ON resource_usage(quota_exceeded, period_start DESC);
CREATE INDEX idx_resource_usage_cost ON resource_usage(cost_usd DESC, period_start DESC);

-- Enable Row Level Security where appropriate
ALTER TABLE system_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE error_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_interaction_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_usage_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE resource_usage ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for monitoring tables
CREATE POLICY error_logs_org_policy ON error_logs
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY interaction_events_org_policy ON user_interaction_events
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Function to automatically create alert on threshold violation
CREATE OR REPLACE FUNCTION check_metric_thresholds()
RETURNS TRIGGER AS $$
DECLARE
    alert_id UUID;
    is_critical BOOLEAN;
BEGIN
    -- Check if threshold is violated
    is_critical := (
        NEW.threshold_critical IS NOT NULL AND NEW.value >= NEW.threshold_critical
    ) OR (
        NEW.threshold_critical IS NOT NULL AND NEW.value <= NEW.threshold_critical
    );

    IF is_critical OR (
        NEW.threshold_warning IS NOT NULL AND (
            NEW.value >= NEW.threshold_warning OR NEW.value <= NEW.threshold_warning
        )
    ) THEN
        -- Create system alert
        INSERT INTO system_alerts (
            alert_name,
            alert_type,
            severity,
            rule_name,
            threshold_value,
            current_value,
            component,
            organization_id,
            node_id,
            alert_details
        ) VALUES (
            format('%s threshold violation', NEW.metric_name),
            'performance',
            CASE WHEN is_critical THEN 'critical' ELSE 'warning' END,
            format('metric_threshold_%s', NEW.metric_name),
            COALESCE(NEW.threshold_warning, NEW.threshold_critical),
            NEW.value,
            NEW.component,
            NEW.organization_id,
            NEW.node_id,
            jsonb_build_object(
                'metric_name', NEW.metric_name,
                'metric_category', NEW.metric_category,
                'value', NEW.value,
                'unit', NEW.unit,
                'threshold_warning', NEW.threshold_warning,
                'threshold_critical', NEW.threshold_critical
            )
        ) RETURNING id INTO alert_id;

        -- Set alert_triggered flag
        NEW.alert_triggered := TRUE;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER performance_metric_alert_trigger
    AFTER INSERT ON performance_metrics
    FOR EACH ROW
    WHEN (NEW.threshold_warning IS NOT NULL OR NEW.threshold_critical IS NOT NULL)
    EXECUTE FUNCTION check_metric_thresholds();

-- Function to aggregate performance metrics
CREATE OR REPLACE FUNCTION aggregate_performance_metrics()
RETURNS VOID AS $$
DECLARE
    aggregation_period INTERVAL := INTERVAL '5 minutes';
BEGIN
    -- Aggregate metrics into summary table
    INSERT INTO performance_metrics_summary (
        metric_name,
        metric_category,
        component,
        organization_id,
        time_bucket,
        avg_value,
        min_value,
        max_value,
        sum_value,
        count_value
    )
    SELECT
        metric_name,
        metric_category,
        component,
        organization_id,
        date_bin(aggregation_period, timestamp, TIMESTAMP '2024-01-01') as time_bucket,
        AVG(value) as avg_value,
        MIN(value) as min_value,
        MAX(value) as max_value,
        SUM(value) as sum_value,
        COUNT(*) as count_value
    FROM performance_metrics
    WHERE timestamp >= NOW() - aggregation_period
      AND timestamp < NOW()
    GROUP BY
        metric_name,
        metric_category,
        component,
        organization_id,
        date_bin(aggregation_period, timestamp, TIMESTAMP '2024-01-01')
    ON CONFLICT (metric_name, metric_category, component, organization_id, time_bucket)
    DO UPDATE SET
        avg_value = EXCLUDED.avg_value,
        min_value = EXCLUDED.min_value,
        max_value = EXCLUDED.max_value,
        sum_value = EXCLUDED.sum_value,
        count_value = EXCLUDED.count_value,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- Create summary table for aggregated metrics
CREATE TABLE performance_metrics_summary (
    metric_name VARCHAR(255) NOT NULL,
    metric_category VARCHAR(100) NOT NULL,
    component VARCHAR(100),
    organization_id UUID REFERENCES organizations(id),
    time_bucket TIMESTAMPTZ NOT NULL,
    avg_value DECIMAL(15,6),
    min_value DECIMAL(15,6),
    max_value DECIMAL(15,6),
    sum_value DECIMAL(15,6),
    count_value INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (metric_name, metric_category, component, organization_id, time_bucket)
);

CREATE INDEX idx_perf_summary_time ON performance_metrics_summary(time_bucket DESC);
CREATE INDEX idx_perf_summary_org ON performance_metrics_summary(organization_id, time_bucket DESC);
CREATE INDEX idx_perf_summary_category ON performance_metrics_summary(metric_category, time_bucket DESC);

COMMIT;