-- Migration 001: Add Monitoring and Observability Schema
-- This migration extends the existing RAG system database with comprehensive monitoring capabilities

-- =============================================
-- Migration Metadata
-- =============================================

-- Create migrations tracking table if it doesn't exist
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    execution_time_ms INTEGER,
    checksum VARCHAR(64)
);

-- Record this migration
INSERT INTO schema_migrations (migration_name, description, checksum)
VALUES (
    '001_add_monitoring_schema.sql',
    'Add comprehensive monitoring and observability schema for SLI/SLO tracking, performance monitoring, user analytics, and business metrics',
    md5('001_add_monitoring_schema_monitoring_system_v1')
) ON CONFLICT (migration_name) DO NOTHING;

-- =============================================
-- Prerequisites and Extensions
-- =============================================

-- Install required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Enable partitioning (PostgreSQL 10+)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'partitioned'
    ) THEN
        RAISE NOTICE 'Partitioned extension already exists';
    END IF;
END $$;

-- =============================================
-- SLI/SLO Monitoring Tables
-- =============================================

-- Service Level Indicators (SLIs) table
CREATE TABLE IF NOT EXISTS service_level_indicators (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sli_name VARCHAR(255) NOT NULL,
    sli_category VARCHAR(100) NOT NULL,
    description TEXT,
    organization_id UUID REFERENCES organizations(id),

    -- SLI configuration
    metric_source VARCHAR(100) NOT NULL,
    metric_query JSONB NOT NULL,
    aggregation_window_minutes INTEGER NOT NULL DEFAULT 5,
    aggregation_function VARCHAR(50) NOT NULL DEFAULT 'avg',

    -- SLO targets
    slo_target_percentile FLOAT NOT NULL,
    slo_target_value FLOAT NOT NULL,
    slo_target_unit VARCHAR(50) NOT NULL,
    slo_period_days INTEGER NOT NULL DEFAULT 30,

    -- Alerting configuration
    alert_burn_rate_threshold FLOAT DEFAULT 2.0,
    alert_notification_channels JSONB,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,

    CONSTRAINT chk_sli_category CHECK (sli_category IN ('availability', 'latency', 'throughput', 'error_rate', 'quality', 'business')),
    CONSTRAINT chk_aggregation_function CHECK (aggregation_function IN ('avg', 'p95', 'p99', 'p999', 'sum', 'rate', 'count'))
);

-- Create initial SLIs for common RAG system metrics
INSERT INTO service_level_indicators (sli_name, sli_category, description, metric_source, metric_query, slo_target_percentile, slo_target_value, slo_target_unit) VALUES
('system_uptime', 'availability', 'System uptime percentage', 'synthetic_tests', '{"type": "http_check", "endpoint": "/health"}', 99.5, 99.5, '%'),
('api_response_time', 'latency', 'API response time for all endpoints', 'prometheus', '{"query": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"}', 95.0, 3000, 'ms'),
('search_response_time', 'latency', 'Search query response time', 'application_logs', '{"metric": "search_duration_ms"}', 95.0, 2000, 'ms'),
('query_success_rate', 'quality', 'RAG query success rate', 'application_logs', '{"metric": "rag_query_success", "type": "rate"}', 99.0, 99.0, '%'),
('rag_faithfulness', 'quality', 'RAG response faithfulness score', 'evaluation_framework', '{"metric": "faithfulness_score", "source": "deepeval"}', 90.0, 0.9, 'score')
ON CONFLICT DO NOTHING;

-- =============================================
-- Performance Monitoring Tables
-- =============================================

-- Application performance metrics
CREATE TABLE IF NOT EXISTS performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(255) NOT NULL,
    metric_category VARCHAR(100) NOT NULL,
    component_name VARCHAR(255) NOT NULL,
    organization_id UUID REFERENCES organizations(id),

    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    value FLOAT NOT NULL,
    unit VARCHAR(50),

    p50 FLOAT,
    p90 FLOAT,
    p95 FLOAT,
    p99 FLOAT,
    p999 FLOAT,
    min_value FLOAT,
    max_value FLOAT,
    std_deviation FLOAT,

    request_count INTEGER DEFAULT 1,
    error_count INTEGER DEFAULT 0,
    total_request_size_bytes BIGINT,
    total_response_size_bytes BIGINT,

    environment VARCHAR(50) DEFAULT 'production',
    node_id VARCHAR(100),
    pod_name VARCHAR(255),
    deployment_version VARCHAR(100),

    tags JSONB,
    trace_id VARCHAR(255),
    span_id VARCHAR(255),

    metric_date DATE NOT NULL GENERATED ALWAYS AS (DATE(timestamp)) STORED,
    metric_hour INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(HOUR FROM timestamp)) STORED,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    batch_id VARCHAR(100),
    processed BOOLEAN DEFAULT FALSE,

    CONSTRAINT chk_metric_category CHECK (metric_category IN (
        'api', 'database', 'cache', 'search', 'ml_inference', 'file_processing',
        'external_service', 'queue', 'storage', 'network', 'system'
    ))
);

-- Database performance metrics
CREATE TABLE IF NOT EXISTS database_performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    database_type VARCHAR(50) NOT NULL,
    database_instance VARCHAR(255) NOT NULL,
    organization_id UUID REFERENCES organizations(id),

    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,

    active_connections INTEGER,
    idle_connections INTEGER,
    max_connections INTEGER,
    connection_utilization_percent FLOAT,

    queries_per_second FLOAT,
    slow_queries_count INTEGER DEFAULT 0,
    avg_query_time_ms FLOAT,
    p95_query_time_ms FLOAT,
    p99_query_time_ms FLOAT,

    cpu_usage_percent FLOAT,
    memory_usage_bytes BIGINT,
    memory_usage_percent FLOAT,
    disk_usage_bytes BIGINT,
    disk_usage_percent FLOAT,
    disk_io_read_mb_per_sec FLOAT,
    disk_io_write_mb_per_sec FLOAT,

    database_metrics JSONB,

    metric_date DATE NOT NULL GENERATED ALWAYS AS (DATE(timestamp)) STORED,
    metric_hour INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(HOUR FROM timestamp)) STORED,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- User Analytics Tables
-- =============================================

-- Enhanced user sessions
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID REFERENCES organizations(id) NOT NULL,

    session_id VARCHAR(255) NOT NULL UNIQUE,
    session_token_hash VARCHAR(255),

    session_start TIMESTAMP WITH TIME ZONE NOT NULL,
    session_end TIMESTAMP WITH TIME ZONE,
    session_duration_seconds INTEGER,
    last_activity TIMESTAMP WITH TIME ZONE NOT NULL,

    session_status VARCHAR(50) NOT NULL DEFAULT 'active',
    termination_reason VARCHAR(100),

    user_agent TEXT,
    ip_address INET,
    country VARCHAR(2),
    city VARCHAR(100),
    device_type VARCHAR(50),
    browser VARCHAR(100),
    os VARCHAR(100),

    authentication_method VARCHAR(50),
    mfa_verified BOOLEAN DEFAULT FALSE,

    pages_viewed INTEGER DEFAULT 0,
    searches_performed INTEGER DEFAULT 0,
    documents_viewed INTEGER DEFAULT 0,
    api_requests_made INTEGER DEFAULT 0,
    data_uploaded_mb FLOAT DEFAULT 0,
    data_downloaded_mb FLOAT DEFAULT 0,

    security_flags JSONB,
    risk_score FLOAT CHECK (risk_score >= 0 AND risk_score <= 100),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_session_status CHECK (session_status IN ('active', 'expired', 'terminated', 'invalidated'))
);

-- User activity events
CREATE TABLE IF NOT EXISTS user_activity_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID REFERENCES organizations(id) NOT NULL,
    session_id VARCHAR(255) NOT NULL,

    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(100) NOT NULL,
    event_action VARCHAR(255) NOT NULL,
    event_description TEXT,

    event_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    event_duration_ms INTEGER,

    page_url TEXT,
    api_endpoint VARCHAR(500),
    referrer_url TEXT,

    event_properties JSONB,
    request_payload JSONB,
    response_payload JSONB,

    response_time_ms INTEGER,
    database_query_time_ms INTEGER,
    external_service_time_ms INTEGER,

    business_value FLOAT,
    conversion_step VARCHAR(100),

    user_agent TEXT,
    ip_address INET,
    device_fingerprint VARCHAR(255),

    event_date DATE NOT NULL GENERATED ALWAYS AS (DATE(event_timestamp)) STORED,
    event_hour INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(HOUR FROM event_timestamp)) STORED,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    batch_id VARCHAR(100),

    CONSTRAINT chk_event_category CHECK (event_category IN (
        'search', 'document', 'upload', 'download', 'view', 'interaction',
        'api', 'authentication', 'error', 'performance'
    ))
);

-- =============================================
-- System Health Tables
-- =============================================

-- Service health status
CREATE TABLE IF NOT EXISTS service_health_status (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_name VARCHAR(255) NOT NULL,
    service_type VARCHAR(100) NOT NULL,
    service_instance VARCHAR(255),
    organization_id UUID REFERENCES organizations(id),

    health_status VARCHAR(50) NOT NULL,
    status_reason VARCHAR(500),
    health_score FLOAT CHECK (health_score >= 0 AND health_score <= 100),

    check_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    check_duration_ms INTEGER,
    check_type VARCHAR(100),
    check_url VARCHAR(500),
    check_status_code INTEGER,

    dependencies JSONB,
    dependency_status JSONB,

    response_time_ms INTEGER,
    cpu_usage_percent FLOAT,
    memory_usage_percent FLOAT,
    error_rate_percent FLOAT,

    active_connections INTEGER,
    queue_depth INTEGER,
    cache_hit_rate FLOAT,

    environment VARCHAR(50) DEFAULT 'production',
    region VARCHAR(50),
    availability_zone VARCHAR(50),
    node_id VARCHAR(100),

    alert_triggered BOOLEAN DEFAULT FALSE,
    alert_severity VARCHAR(50),
    last_alert_sent TIMESTAMP WITH TIME ZONE,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    first_failure_timestamp TIMESTAMP WITH TIME ZONE,
    failure_duration_minutes INTEGER,

    CONSTRAINT chk_health_status CHECK (health_status IN ('healthy', 'degraded', 'unhealthy', 'unknown')),
    CONSTRAINT chk_alert_severity CHECK (alert_severity IN ('info', 'warning', 'critical'))
);

-- System alerts
CREATE TABLE IF NOT EXISTS system_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_name VARCHAR(255) NOT NULL,
    alert_type VARCHAR(100) NOT NULL,
    alert_severity VARCHAR(50) NOT NULL,
    organization_id UUID REFERENCES organizations(id),

    triggered_at TIMESTAMP WITH TIME ZONE NOT NULL,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,

    alert_status VARCHAR(50) NOT NULL DEFAULT 'open',

    alert_description TEXT,
    alert_details JSONB,
    affected_services JSONB,
    affected_components JSONB,

    metric_name VARCHAR(255),
    metric_value FLOAT,
    threshold_value FLOAT,
    threshold_operator VARCHAR(10),

    business_impact VARCHAR(500),
    affected_users_count INTEGER DEFAULT 0,
    estimated_revenue_impact DECIMAL(12,2),

    assigned_to VARCHAR(255),
    response_actions JSONB,
    resolution_summary TEXT,

    notification_sent BOOLEAN DEFAULT FALSE,
    notification_channels JSONB,
    stakeholders_notified JSONB,

    post_mortem_required BOOLEAN DEFAULT FALSE,
    post_mortem_completed BOOLEAN DEFAULT FALSE,
    post_mortem_url VARCHAR(500),
    lessons_learned TEXT,

    prevention_measures JSONB,
    monitoring_improvements JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_alert_severity CHECK (alert_severity IN ('info', 'warning', 'error', 'critical')),
    CONSTRAINT chk_alert_status CHECK (alert_status IN ('open', 'acknowledged', 'resolved', 'suppressed'))
);

-- =============================================
-- Business Metrics Tables
-- =============================================

-- Search quality metrics
CREATE TABLE IF NOT EXISTS search_quality_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id VARCHAR(255),

    search_id UUID,
    query_text TEXT NOT NULL,
    query_type VARCHAR(100),
    search_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,

    total_response_time_ms INTEGER,
    vector_search_time_ms INTEGER,
    graph_search_time_ms INTEGER,
    keyword_search_time_ms INTEGER,
    reranking_time_ms INTEGER,

    total_results_count INTEGER,
    returned_results_count INTEGER,
    results_filtered_count INTEGER,

    relevance_score FLOAT CHECK (relevance_score >= 0 AND relevance_score <= 1),
    diversity_score FLOAT CHECK (diversity_score >= 0 AND diversity_score <= 1),
    freshness_score FLOAT CHECK (freshness_score >= 0 AND freshness_score <= 1),
    overall_quality_score FLOAT CHECK (overall_quality_score >= 0 AND overall_quality_score <= 1),

    clicked_results INTEGER DEFAULT 0,
    clicked_result_positions JSONB,
    time_to_first_click_ms INTEGER,
    session_search_position INTEGER,

    user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),
    user_feedback TEXT,
    feedback_helpful BOOLEAN,

    filters_applied JSONB,
    sort_order VARCHAR(100),
    search_scope VARCHAR(100),
    search_context JSONB,

    cache_hit BOOLEAN DEFAULT FALSE,
    cache_response_time_ms INTEGER,
    database_queries_count INTEGER,
    external_api_calls_count INTEGER,

    conversion_event VARCHAR(100),
    business_value DECIMAL(8,2),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,

    search_date DATE NOT NULL GENERATED ALWAYS AS (DATE(search_timestamp)) STORED,
    search_hour INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(HOUR FROM search_timestamp)) STORED
);

-- Document processing metrics
CREATE TABLE IF NOT EXISTS document_processing_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    document_id UUID,
    document_name VARCHAR(1000),
    document_type VARCHAR(100),
    document_size_bytes BIGINT,
    file_extension VARCHAR(10),

    upload_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    processing_started TIMESTAMP WITH TIME ZONE,
    processing_completed TIMESTAMP WITH TIME ZONE,
    total_processing_time_seconds INTEGER,

    upload_time_seconds INTEGER,
    validation_time_seconds INTEGER,
    ocr_time_seconds INTEGER,
    transcription_time_seconds INTEGER,
    embedding_time_seconds INTEGER,
    indexing_time_seconds INTEGER,
    quality_check_time_seconds INTEGER,

    processing_status VARCHAR(50) NOT NULL,
    failure_reason VARCHAR(500),
    failure_stage VARCHAR(100),
    retry_count INTEGER DEFAULT 0,

    ocr_quality_score FLOAT CHECK (ocr_quality_score >= 0 AND ocr_quality_score <= 1),
    transcription_quality_score FLOAT CHECK (transcription_quality_score >= 0 AND transcription_quality_score <= 1),
    overall_quality_score FLOAT CHECK (overall_quality_score >= 0 AND overall_quality_score <= 1),

    pages_processed INTEGER,
    text_extracted_chars INTEGER,
    entities_extracted INTEGER,
    metadata_extracted_fields INTEGER,

    cpu_time_seconds FLOAT,
    memory_peak_mb FLOAT,
    gpu_time_seconds FLOAT,
    api_calls_made INTEGER,

    processing_cost_usd DECIMAL(10,4),
    storage_cost_usd_per_month DECIMAL(10,4),

    processing_node VARCHAR(255),
    environment VARCHAR(50) DEFAULT 'production',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    batch_id VARCHAR(100),

    CONSTRAINT chk_processing_status CHECK (processing_status IN ('success', 'failed', 'partial', 'timeout'))
);

-- =============================================
-- Configuration Tables
-- =============================================

-- Monitoring dashboards
CREATE TABLE IF NOT EXISTS monitoring_dashboards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),

    dashboard_name VARCHAR(255) NOT NULL,
    dashboard_description TEXT,
    dashboard_type VARCHAR(100) NOT NULL,

    layout_config JSONB NOT NULL,
    time_range_default VARCHAR(50) DEFAULT '1h',
    refresh_interval_seconds INTEGER DEFAULT 30,

    is_public BOOLEAN DEFAULT FALSE,
    allowed_roles JSONB,
    allowed_users JSONB,

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed TIMESTAMP WITH TIME ZONE,
    access_count INTEGER DEFAULT 0,

    is_deleted BOOLEAN DEFAULT FALSE,

    CONSTRAINT chk_dashboard_type CHECK (dashboard_type IN ('sli', 'performance', 'business', 'health', 'custom'))
);

-- Create default monitoring dashboards
INSERT INTO monitoring_dashboards (dashboard_name, dashboard_description, dashboard_type, layout_config, created_by) VALUES
('System Overview', 'High-level system health and performance metrics', 'health', '{"widgets": [{"type": "service_health", "position": {"x": 0, "y": 0, "w": 12, "h": 6}}]}', NULL),
('API Performance', 'API response times and error rates', 'performance', '{"widgets": [{"type": "response_time_chart", "position": {"x": 0, "y": 0, "w": 6, "h": 4}}]}', NULL),
('Search Analytics', 'Search quality and user satisfaction metrics', 'business', '{"widgets": [{"type": "search_quality_chart", "position": {"x": 0, "y": 0, "w": 8, "h": 5}}]}', NULL)
ON CONFLICT DO NOTHING;

-- =============================================
-- Core Indexes (Essential for Performance)
-- =============================================

-- SLI measurement indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sli_measurements_sli_time
ON service_level_indicators (sli_name, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sli_measurements_org_time
ON service_level_indicators (organization_id, created_at DESC);

-- Performance metrics indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_name_time
ON performance_metrics (metric_name, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_category_time
ON performance_metrics (metric_category, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_component_time
ON performance_metrics (component_name, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_org_time
ON performance_metrics (organization_id, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_date
ON performance_metrics (metric_date, metric_hour);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_tags
ON performance_metrics USING GIN (tags);

-- User session indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_sessions_user_time
ON user_sessions (user_id, session_start DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_sessions_org_time
ON user_sessions (organization_id, session_start DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_sessions_status
ON user_sessions (session_status, last_activity DESC);

-- User activity indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_user_time
ON user_activity_events (user_id, event_timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_session_time
ON user_activity_events (session_id, event_timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_org_time
ON user_activity_events (organization_id, event_timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_type_time
ON user_activity_events (event_type, event_timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_date
ON user_activity_events (event_date, event_hour);

-- Service health indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_service_health_service_time
ON service_health_status (service_name, check_timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_service_health_status_time
ON service_health_status (health_status, check_timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_service_health_org_time
ON service_health_status (organization_id, check_timestamp DESC);

-- Alert indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_alerts_status_time
ON system_alerts (alert_status, triggered_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_alerts_severity_time
ON system_alerts (alert_severity, triggered_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_alerts_org_time
ON system_alerts (organization_id, triggered_at DESC);

-- Document processing indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_doc_proc_org_time
ON document_processing_metrics (organization_id, upload_timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_doc_proc_status_time
ON document_processing_metrics (processing_status, upload_timestamp DESC);

-- Search quality indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_quality_org_time
ON search_quality_metrics (organization_id, search_timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_quality_user_time
ON search_quality_metrics (user_id, search_timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_quality_date
ON search_quality_metrics (search_date, search_hour);

-- Database performance indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_db_perf_type_instance_time
ON database_performance_metrics (database_type, database_instance, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_db_perf_date
ON database_performance_metrics (metric_date, metric_hour);

-- =============================================
-- Grant Permissions
-- =============================================

-- Grant permissions to the application user
-- Replace 'rag_app_user' with your actual application user name
DO $$
DECLARE
    app_user TEXT := 'rag_app_user';
    table_name TEXT;
BEGIN
    -- Grant usage on schemas
    EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', app_user);

    -- Grant permissions on monitoring tables
    FOR table_name IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename IN (
            'service_level_indicators', 'performance_metrics', 'database_performance_metrics',
            'user_sessions', 'user_activity_events', 'service_health_status', 'system_alerts',
            'search_quality_metrics', 'document_processing_metrics', 'monitoring_dashboards'
        )
    LOOP
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I TO %I', table_name, app_user);
        EXECUTE format('GRANT USAGE ON SEQUENCE %I_id_seq TO %I', table_name, app_user);
    END LOOP;
END $$;

-- =============================================
-- Migration Validation
-- =============================================

-- Create validation function
CREATE OR REPLACE FUNCTION validate_monitoring_schema()
RETURNS TABLE(
    table_name TEXT,
    status TEXT,
    row_count BIGINT,
    index_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        schemaname||'.'||tablename as table_name,
        'exists' as status,
        CASE
            WHEN schemaname = 'pg_catalog' THEN 0
            ELSE (SELECT reltuples FROM pg_class WHERE relname = tablename)
        END as row_count,
        (SELECT COUNT(*) FROM pg_indexes WHERE tablename = t.tablename AND schemaname = t.schemaname) as index_count
    FROM pg_tables t
    WHERE t.tablename IN (
        'service_level_indicators', 'performance_metrics', 'database_performance_metrics',
        'user_sessions', 'user_activity_events', 'service_health_status', 'system_alerts',
        'search_quality_metrics', 'document_processing_metrics', 'monitoring_dashboards'
    )
    AND t.schemaname = 'public'
    ORDER BY t.tablename;
END;
$$ LANGUAGE plpgsql;

-- Run validation
-- SELECT * FROM validate_monitoring_schema();

-- =============================================
-- Performance Optimization Views
-- =============================================

-- Create materialized view for SLI compliance dashboard
CREATE MATERIALIZED VIEW IF NOT EXISTS sli_compliance_summary AS
SELECT
    sli.id,
    sli.sli_name,
    sli.sli_category,
    sli.organization_id,
    COUNT(sm.id) as total_measurements,
    COUNT(CASE WHEN sm.meets_slo THEN 1 END) as compliant_measurements,
    ROUND(
        COUNT(CASE WHEN sm.meets_slo THEN 1 END)::NUMERIC /
        NULLIF(COUNT(sm.id), 0) * 100, 2
    ) as compliance_percentage,
    AVG(sm.measurement_value) as avg_value,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY sm.measurement_value) as p95_value,
    MAX(sm.measurement_time) as last_measurement_time,
    MIN(sm.measurement_time) as first_measurement_time
FROM service_level_indicators sli
LEFT JOIN sli_measurements sm ON sli.id = sm.sli_id
WHERE sm.measurement_time >= NOW() - INTERVAL '24 hours'
GROUP BY sli.id, sli.sli_name, sli.sli_category, sli.organization_id;

-- Create unique index for materialized view refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_sli_compliance_summary_unique
ON sli_compliance_summary (id);

-- Create function to refresh materialized views
CREATE OR REPLACE FUNCTION refresh_monitoring_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY sli_compliance_summary;
END;
$$ LANGUAGE plpgsql;

-- Schedule refresh (requires pg_cron extension)
-- SELECT cron.schedule('refresh-monitoring-views', '*/5 * * * *', 'SELECT refresh_monitoring_views();');

-- =============================================
-- Migration Completion
-- =============================================

-- Update migration record with execution time
UPDATE schema_migrations
SET execution_time_ms = EXTRACT(MILLISECOND FROM (NOW() - created_at))
WHERE migration_name = '001_add_monitoring_schema.sql';

-- Create monitoring setup verification view
CREATE OR REPLACE VIEW monitoring_setup_status AS
SELECT
    '001_add_monitoring_schema.sql' as migration_name,
    'completed' as status,
    NOW() as completion_time,
    COUNT(*) as tables_created,
    (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public' AND tablename IN (
        'service_level_indicators', 'performance_metrics', 'user_sessions',
        'service_health_status', 'system_alerts', 'search_quality_metrics'
    )) as indexes_created
FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN (
    'service_level_indicators', 'performance_metrics', 'database_performance_metrics',
    'user_sessions', 'user_activity_events', 'service_health_status', 'system_alerts',
    'search_quality_metrics', 'document_processing_metrics', 'monitoring_dashboards'
);

COMMIT;

-- Log migration completion
DO $$
BEGIN
    RAISE NOTICE 'Monitoring schema migration completed successfully';
    RAISE NOTICE 'Created % monitoring tables', (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name LIKE ANY(ARRAY['service_level_indicators', 'performance_metrics', '%metrics%', '%sessions%', '%events%', '%health%', '%alerts%']));
    RAISE NOTICE 'Created % indexes for performance optimization', (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE 'idx_%');
    RAISE NOTICE 'Materialized views: sli_compliance_summary';
    RAISE NOTICE 'Validation views: monitoring_setup_status, validate_monitoring_schema()';
END $$;