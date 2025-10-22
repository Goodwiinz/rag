-- Migration 007: Create Knowledge Graph Analytics Dashboard Schema
-- Comprehensive analytics infrastructure for entity, relationship, graph, and document analytics

BEGIN;

-- Enable required extensions for analytics
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ============================================================================
-- ANALYTICS AGGREGATION TABLES (Core Performance Tables)
-- ============================================================================

-- Entity analytics aggregations (time-series optimized)
CREATE TABLE entity_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Time bucket for aggregations
    time_bucket TIMESTAMPTZ NOT NULL,
    bucket_type VARCHAR(20) NOT NULL CHECK (bucket_type IN ('hour', 'day', 'week', 'month')),

    -- Entity count analytics
    total_entities INTEGER DEFAULT 0,
    new_entities INTEGER DEFAULT 0,
    entity_growth_rate DECIMAL(10,6) DEFAULT 0,

    -- Entity type breakdown
    entity_type_counts JSONB DEFAULT '{}', -- {"person": 150, "organization": 75, ...}
    entity_type_percentages JSONB DEFAULT '{}',

    -- Quality analytics
    avg_confidence_score DECIMAL(5,4) DEFAULT 0,
    high_quality_entities INTEGER DEFAULT 0, -- confidence > 0.8
    low_quality_entities INTEGER DEFAULT 0,  -- confidence < 0.5

    -- Processing analytics
    entities_processed INTEGER DEFAULT 0,
    processing_success_rate DECIMAL(5,4) DEFAULT 0,
    avg_processing_time_ms INTEGER DEFAULT 0,

    -- Document association
    entities_per_document DECIMAL(8,4) DEFAULT 0,
    documents_with_entities INTEGER DEFAULT 0,

    -- Modality breakdown
    entity_modality_counts JSONB DEFAULT '{}', -- {"text": 200, "image": 50, "audio": 10}

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(organization_id, time_bucket, bucket_type)
) PARTITION BY RANGE (time_bucket);

-- Create partitions for entity analytics
CREATE TABLE entity_analytics_y2024m01 PARTITION OF entity_analytics
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE entity_analytics_y2024m02 PARTITION OF entity_analytics
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

CREATE TABLE entity_analytics_y2024q1 PARTITION OF entity_analytics
    FOR VALUES FROM ('2024-01-01') TO ('2024-04-01');

-- Relationship analytics aggregations
CREATE TABLE relationship_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Time bucket
    time_bucket TIMESTAMPTZ NOT NULL,
    bucket_type VARCHAR(20) NOT NULL CHECK (bucket_type IN ('hour', 'day', 'week', 'month')),

    -- Relationship count analytics
    total_relationships INTEGER DEFAULT 0,
    new_relationships INTEGER DEFAULT 0,
    relationship_growth_rate DECIMAL(10,6) DEFAULT 0,

    -- Relationship type breakdown
    relationship_type_counts JSONB DEFAULT '{}', -- {"works_for": 100, "located_in": 50, ...}
    relationship_strength_distribution JSONB DEFAULT '{}', -- {"high": 30, "medium": 60, "low": 10}

    -- Quality analytics
    avg_confidence_score DECIMAL(5,4) DEFAULT 0,
    high_confidence_relationships INTEGER DEFAULT 0, -- confidence > 0.8
    avg_relationship_strength DECIMAL(5,4) DEFAULT 0,

    -- Graph connectivity
    avg_connections_per_entity DECIMAL(8,4) DEFAULT 0,
    isolated_entities INTEGER DEFAULT 0,
    hub_entities INTEGER DEFAULT 0, -- entities with >50 connections

    -- Bidirectional relationships
    bidirectional_relationships INTEGER DEFAULT 0,
    bidirectional_percentage DECIMAL(5,4) DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(organization_id, time_bucket, bucket_type)
) PARTITION BY RANGE (time_bucket);

-- Create partitions for relationship analytics
CREATE TABLE relationship_analytics_y2024m01 PARTITION OF relationship_analytics
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE relationship_analytics_y2024m02 PARTITION OF relationship_analytics
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- Graph metrics analytics (computationally expensive, cached)
CREATE TABLE graph_metrics_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Computation metadata
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    computation_version VARCHAR(50) DEFAULT 'v1.0',
    graph_snapshot_id VARCHAR(255), -- Reference to graph state
    computation_time_ms INTEGER,

    -- Centrality metrics (for top entities)
    top_entities_by_centrality JSONB DEFAULT '[]', -- [{"entity_id": uuid, "entity_name": "name", "centrality_score": 0.8, "entity_type": "person"}, ...]
    top_entities_by_betweenness JSONB DEFAULT '[]',
    top_entities_by_closeness JSONB DEFAULT '[]',
    top_entities_by_pagerank JSONB DEFAULT '[]',

    -- Global graph metrics
    graph_density DECIMAL(8,6) DEFAULT 0,
    average_path_length DECIMAL(8,4),
    clustering_coefficient DECIMAL(8,6) DEFAULT 0,
    modularity_score DECIMAL(8,6),

    -- Community structure
    number_of_communities INTEGER DEFAULT 0,
    average_community_size DECIMAL(8,4),
    largest_community_size INTEGER DEFAULT 0,
    community_distribution JSONB DEFAULT '{}', -- {"small": 45, "medium": 15, "large": 5}

    -- Component analysis
    number_of_components INTEGER DEFAULT 1,
    giant_component_size INTEGER DEFAULT 0,
    giant_component_percentage DECIMAL(5,4) DEFAULT 0,

    -- Entity type connectivity
    entity_type_connectivity JSONB DEFAULT '{}', -- Connection patterns between types

    -- Temporal patterns
    temporal_evolution_metrics JSONB DEFAULT '{}', -- How graph evolved over time

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document analytics aggregations
CREATE TABLE document_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Time bucket
    time_bucket TIMESTAMPTZ NOT NULL,
    bucket_type VARCHAR(20) NOT NULL CHECK (bucket_type IN ('hour', 'day', 'week', 'month')),

    -- Document processing metrics
    total_documents INTEGER DEFAULT 0,
    new_documents INTEGER DEFAULT 0,
    processed_documents INTEGER DEFAULT 0,
    processing_success_rate DECIMAL(5,4) DEFAULT 0,

    -- Document type breakdown
    document_type_counts JSONB DEFAULT '{}', -- {"pdf": 100, "text": 50, "image": 25}
    modality_counts JSONB DEFAULT '{}', -- {"text": 150, "image": 30, "audio": 10, "video": 5}

    -- Quality metrics
    avg_quality_score DECIMAL(5,4) DEFAULT 0,
    high_quality_documents INTEGER DEFAULT 0, -- quality > 0.8
    low_quality_documents INTEGER DEFAULT 0,  -- quality < 0.5

    -- Processing performance
    avg_processing_time_ms INTEGER DEFAULT 0,
    processing_bottlenecks JSONB DEFAULT '{}', -- Common failure points

    -- Extraction analytics
    avg_entities_extracted DECIMAL(8,4) DEFAULT 0,
    avg_concepts_extracted DECIMAL(8,4) DEFAULT 0,
    extraction_success_rates JSONB DEFAULT '{}', -- Success rate by extraction type

    -- Storage analytics
    total_storage_gb DECIMAL(10,2) DEFAULT 0,
    avg_document_size_mb DECIMAL(8,2) DEFAULT 0,
    storage_growth_rate DECIMAL(10,6) DEFAULT 0,

    -- Usage analytics
    total_views INTEGER DEFAULT 0,
    total_downloads INTEGER DEFAULT 0,
    avg_views_per_document DECIMAL(8,4) DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(organization_id, time_bucket, bucket_type)
) PARTITION BY RANGE (time_bucket);

-- Create partitions for document analytics
CREATE TABLE document_analytics_y2024m01 PARTITION OF document_analytics
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE document_analytics_y2024m02 PARTITION OF document_analytics
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- User interaction analytics
CREATE TABLE user_interaction_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Time bucket
    time_bucket TIMESTAMPTZ NOT NULL,
    bucket_type VARCHAR(20) NOT NULL CHECK (bucket_type IN ('hour', 'day', 'week', 'month')),

    -- User activity
    active_users INTEGER DEFAULT 0,
    new_users INTEGER DEFAULT 0,
    total_sessions INTEGER DEFAULT 0,
    avg_session_duration_seconds INTEGER DEFAULT 0,

    -- Search analytics
    total_searches INTEGER DEFAULT 0,
    unique_search_queries INTEGER DEFAULT 0,
    avg_search_time_ms INTEGER DEFAULT 0,
    search_success_rate DECIMAL(5,4) DEFAULT 0, -- Users finding relevant results

    -- Query type distribution
    query_type_distribution JSONB DEFAULT '{}', -- {"semantic": 40, "keyword": 30, "hybrid": 25, "graph": 5}
    query_complexity_distribution JSONB DEFAULT '{}', -- {"simple": 60, "medium": 30, "complex": 10}

    -- User satisfaction
    avg_user_satisfaction_score DECIMAL(3,2) DEFAULT 0,
    feedback_submission_rate DECIMAL(5,4) DEFAULT 0,
    complaint_rate DECIMAL(5,4) DEFAULT 0,

    -- Feature usage
    feature_usage JSONB DEFAULT '{}', -- Usage counts by feature
    advanced_feature_adoption_rate DECIMAL(5,4) DEFAULT 0,

    -- Performance from user perspective
    avg_response_time_ms INTEGER DEFAULT 0,
    error_rate DECIMAL(5,4) DEFAULT 0,
    timeout_rate DECIMAL(5,4) DEFAULT 0,

    -- Demographics (if available)
    user_role_distribution JSONB DEFAULT '{}', -- {"admin": 5, "analyst": 20, "user": 75}
    user_experience_level_distribution JSONB DEFAULT '{}', -- {"novice": 30, "intermediate": 50, "expert": 20}

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(organization_id, time_bucket, bucket_type)
) PARTITION BY RANGE (time_bucket);

-- Create partitions for user interaction analytics
CREATE TABLE user_interaction_analytics_y2024m01 PARTITION OF user_interaction_analytics
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE user_interaction_analytics_y2024m02 PARTITION OF user_interaction_analytics
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- ============================================================================
-- REAL-TIME METRICS AND KPIs
-- ============================================================================

-- Real-time dashboard metrics (materialized view for fast access)
CREATE MATERIALIZED VIEW real_time_dashboard_metrics AS
SELECT
    org.id as organization_id,
    org.name as organization_name,

    -- Current entity counts
    COALESCE(entity_stats.total_entities, 0) as total_entities,
    COALESCE(entity_stats.new_entities_today, 0) as new_entities_today,
    COALESCE(entity_stats.avg_confidence, 0) as avg_entity_confidence,

    -- Current relationship counts
    COALESCE(rel_stats.total_relationships, 0) as total_relationships,
    COALESCE(rel_stats.new_relationships_today, 0) as new_relationships_today,
    COALESCE(rel_stats.avg_confidence, 0) as avg_relationship_confidence,

    -- Document metrics
    COALESCE(doc_stats.total_documents, 0) as total_documents,
    COALESCE(doc_stats.documents_processed_today, 0) as documents_processed_today,
    COALESCE(doc_stats.avg_quality_score, 0) as avg_document_quality,
    COALESCE(doc_stats.processing_success_rate, 0) as processing_success_rate,

    -- User activity
    COALESCE(user_stats.active_users_today, 0) as active_users_today,
    COALESCE(user_stats.total_searches_today, 0) as total_searches_today,
    COALESCE(user_stats.avg_response_time, 0) as avg_search_response_time,

    -- System health
    COALESCE(health.avg_system_health, 1.0) as system_health_score,
    COALESCE(health.active_alerts, 0) as active_alerts_count,

    -- Storage metrics
    COALESCE(storage.total_storage_gb, 0) as total_storage_used,
    COALESCE(storage.storage_growth_rate, 0) as storage_growth_rate,

    -- Timestamp
    NOW() as last_updated
FROM organizations org
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) as total_entities,
        COUNT(CASE WHEN created_at >= CURRENT_DATE THEN 1 END) as new_entities_today,
        AVG(extraction_confidence) as avg_confidence
    FROM entities e
    WHERE e.organization_id = org.id
) entity_stats ON true
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) as total_relationships,
        COUNT(CASE WHEN created_at >= CURRENT_DATE THEN 1 END) as new_relationships_today,
        AVG(confidence) as avg_confidence
    FROM entity_relationships er
    WHERE er.organization_id = org.id
) rel_stats ON true
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) as total_documents,
        COUNT(CASE WHEN processing_completed_at >= CURRENT_DATE THEN 1 END) as documents_processed_today,
        AVG(quality_score) as avg_quality_score,
        COUNT(CASE WHEN processing_status = 'indexed' THEN 1 END)::DECIMAL / COUNT(*) as processing_success_rate
    FROM documents d
    WHERE d.organization_id = org.id AND d.is_deleted = FALSE
) doc_stats ON true
LEFT JOIN LATERAL (
    SELECT
        COUNT(DISTINCT sq.user_id) as active_users_today,
        COUNT(*) as total_searches_today,
        AVG(sq.total_time_ms) as avg_response_time
    FROM search_queries sq
    WHERE sq.organization_id = org.id
      AND sq.created_at >= CURRENT_DATE
      AND sq.is_deleted = FALSE
) user_stats ON true
LEFT JOIN LATERAL (
    SELECT
        AVG(health_score) as avg_system_health,
        COUNT(CASE WHEN status != 'healthy' THEN 1 END) as active_alerts
    FROM system_health sh
    WHERE sh.updated_at >= NOW() - INTERVAL '1 hour'
) health ON true
LEFT JOIN LATERAL (
    SELECT
        SUM(file_size_bytes) / (1024.0^3) as total_storage_gb,
        -- Calculate growth rate comparing to last week
        (SUM(file_size_bytes) - COALESCE(last_week.sum_size, 0)) / (NULLIF(COALESCE(last_week.sum_size, 0), 0)) as storage_growth_rate
    FROM documents d
    LEFT JOIN LATERAL (
        SELECT SUM(file_size_bytes) as sum_size
        FROM documents dw
        WHERE dw.organization_id = org.id
          AND dw.created_at >= CURRENT_DATE - INTERVAL '7 days'
          AND dw.created_at < CURRENT_DATE
          AND dw.is_deleted = FALSE
    ) last_week ON true
    WHERE d.organization_id = org.id
      AND d.is_deleted = FALSE
) storage ON true;

-- Create unique index for materialized view refresh
CREATE UNIQUE INDEX idx_real_time_dashboard_metrics_org
    ON real_time_dashboard_metrics(organization_id);

-- ============================================================================
-- DASHBOARD CONFIGURATION AND PERSONALIZATION
-- ============================================================================

-- Dashboard configurations for users and organizations
CREATE TABLE dashboard_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE, -- NULL for org-wide defaults

    -- Configuration metadata
    config_name VARCHAR(255) NOT NULL,
    config_type VARCHAR(50) DEFAULT 'user' CHECK (config_type IN ('user', 'role', 'organization')),
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,

    -- Layout configuration
    layout JSONB DEFAULT '{}', -- Grid layout, widget positions, sizes

    -- Widget configurations
    widgets JSONB DEFAULT '[]', -- Array of widget configurations

    -- Data filters and scope
    time_range_default VARCHAR(50) DEFAULT '7d', -- 1d, 7d, 30d, 90d, custom
    filters JSONB DEFAULT '{}', -- Default filters applied

    -- Refresh settings
    auto_refresh_enabled BOOLEAN DEFAULT TRUE,
    auto_refresh_interval_seconds INTEGER DEFAULT 300, -- 5 minutes

    -- Access permissions
    view_permissions JSONB DEFAULT '[]',
    edit_permissions JSONB DEFAULT '[]',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unique constraints
    UNIQUE(organization_id, user_id, config_name)
);

-- Widget definitions and templates
CREATE TABLE widget_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Widget identification
    widget_name VARCHAR(255) NOT NULL,
    widget_type VARCHAR(100) NOT NULL, -- chart, metric, table, heatmap, network_graph
    widget_category VARCHAR(100) NOT NULL, -- entity, relationship, document, user, system

    -- Widget configuration
    data_source VARCHAR(255) NOT NULL, -- Table, view, or API endpoint
    data_query TEXT, -- SQL query or data fetching logic
    default_config JSONB DEFAULT '{}',

    -- Visualization settings
    chart_type VARCHAR(50), -- line, bar, pie, scatter, heatmap, etc.
    color_scheme JSONB DEFAULT '{}',
    axis_config JSONB DEFAULT '{}',

    -- Performance settings
    cache_duration_seconds INTEGER DEFAULT 300,
    max_data_points INTEGER DEFAULT 1000,

    -- Access control
    required_permissions JSONB DEFAULT '[]',
    widget_roles JSONB DEFAULT '[]', -- Roles that can use this widget

    -- Metadata
    description TEXT,
    version VARCHAR(50) DEFAULT '1.0',
    is_system_widget BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(widget_name, widget_type)
);

-- ============================================================================
-- CUSTOM ANALYTICS REPORTS
-- ============================================================================

-- Custom report definitions
CREATE TABLE custom_analytics_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by_user_id UUID NOT NULL REFERENCES users(id),

    -- Report identification
    report_name VARCHAR(255) NOT NULL,
    report_description TEXT,
    report_category VARCHAR(100),

    -- Report configuration
    report_definition JSONB NOT NULL, -- Complete report definition
    data_sources JSONB DEFAULT '[]', -- List of data sources used
    visualizations JSONB DEFAULT '[]', -- Chart and visualization definitions

    -- Scheduling and automation
    schedule_config JSONB DEFAULT '{}', -- Cron-like scheduling
    auto_generate BOOLEAN DEFAULT FALSE,
    next_run_at TIMESTAMPTZ,

    -- Output configuration
    output_formats JSONB DEFAULT '[]', -- pdf, csv, json, etc.
    delivery_methods JSONB DEFAULT '[]', -- email, download, webhook, etc.
    recipients JSONB DEFAULT '[]',

    -- Access control
    is_public BOOLEAN DEFAULT FALSE,
    share_with_roles JSONB DEFAULT '[]',
    share_with_users JSONB DEFAULT '[]',

    -- Metadata
    version INTEGER DEFAULT 1,
    is_template BOOLEAN DEFAULT FALSE,
    template_category VARCHAR(100),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(organization_id, report_name)
);

-- Report execution history
CREATE TABLE report_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES custom_analytics_reports(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Execution metadata
    executed_by_user_id UUID REFERENCES users(id),
    execution_type VARCHAR(50) DEFAULT 'manual' CHECK (execution_type IN ('manual', 'scheduled', 'api')),

    -- Execution details
    execution_parameters JSONB DEFAULT '{}',
    data_freshness_at TIMESTAMPTZ,

    -- Performance metrics
    execution_time_ms INTEGER,
    data_points_processed INTEGER,
    memory_usage_mb INTEGER,

    -- Results
    execution_status VARCHAR(50) DEFAULT 'running' CHECK (execution_status IN ('running', 'completed', 'failed', 'cancelled')),
    result_file_paths JSONB DEFAULT '[]',
    result_data_preview JSONB,

    -- Error handling
    error_message TEXT,
    error_details JSONB DEFAULT '{}',
    retry_count INTEGER DEFAULT 0,

    -- Output delivery
    delivery_status JSONB DEFAULT '{}',
    delivery_attempts INTEGER DEFAULT 0,

    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (started_at);

-- Create partitions for report executions
CREATE TABLE report_executions_y2024m01 PARTITION OF report_executions
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE report_executions_y2024m02 PARTITION OF report_executions
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- ============================================================================
-- ANALYTICS CACHING AND PERFORMANCE OPTIMIZATION
-- ============================================================================

-- Computed results cache for expensive operations
CREATE TABLE analytics_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,

    -- Cache identification
    cache_key VARCHAR(255) NOT NULL,
    cache_type VARCHAR(100) NOT NULL, -- graph_metrics, entity_analytics, custom_query

    -- Cache metadata
    computation_parameters JSONB DEFAULT '{}',
    data_freshness_at TIMESTAMPTZ,

    -- Computed results (compressed JSON)
    cached_results JSONB NOT NULL,
    result_size_bytes INTEGER,

    -- Cache management
    cache_ttl_seconds INTEGER DEFAULT 3600, -- 1 hour default
    hit_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),

    -- Performance metrics
    computation_time_ms INTEGER,
    is_warm_cache BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,

    UNIQUE(cache_key, organization_id, cache_type)
);

-- Precomputed aggregations for common dashboard queries
CREATE TABLE dashboard_aggregations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Aggregation identification
    aggregation_name VARCHAR(255) NOT NULL,
    aggregation_type VARCHAR(100) NOT NULL, -- hourly, daily, weekly, monthly

    -- Time period
    time_bucket TIMESTAMPTZ NOT NULL,
    time_bucket_type VARCHAR(20) NOT NULL CHECK (time_bucket_type IN ('hour', 'day', 'week', 'month')),

    -- Precomputed data
    aggregated_data JSONB NOT NULL,
    data_points INTEGER DEFAULT 0,

    -- Metadata
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    computation_time_ms INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(organization_id, aggregation_name, aggregation_type, time_bucket)
) PARTITION BY RANGE (time_bucket);

-- Create partitions for dashboard aggregations
CREATE TABLE dashboard_aggregations_y2024m01 PARTITION OF dashboard_aggregations
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE dashboard_aggregations_y2024m02 PARTITION OF dashboard_aggregations
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- ============================================================================
-- ALERTING AND NOTIFICATIONS
-- ============================================================================

-- Analytics-specific alerts
CREATE TABLE analytics_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Alert identification
    alert_name VARCHAR(255) NOT NULL,
    alert_type VARCHAR(100) NOT NULL, -- metric_threshold, data_quality, performance, capacity

    -- Alert configuration
    alert_condition JSONB NOT NULL, -- Conditions for triggering
    threshold_values JSONB DEFAULT '{}',

    -- Status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'triggered', 'acknowledged', 'resolved', 'suppressed')),
    severity VARCHAR(50) NOT NULL CHECK (severity IN ('info', 'warning', 'critical', 'emergency')),

    -- Trigger tracking
    last_triggered_at TIMESTAMPTZ,
    trigger_count INTEGER DEFAULT 0,
    consecutive_triggers INTEGER DEFAULT 0,

    -- Context
    affected_metrics JSONB DEFAULT '[]',
    related_entities JSONB DEFAULT '[]',

    -- Notification settings
    notification_channels JSONB DEFAULT '[]',
    notification_cooldown_minutes INTEGER DEFAULT 60,
    last_notification_at TIMESTAMPTZ,

    -- Resolution tracking
    acknowledged_by UUID REFERENCES users(id),
    acknowledged_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,

    -- Alert details
    alert_details JSONB DEFAULT '{}',
    resolution_notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Alert history and notifications
CREATE TABLE analytics_alert_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id UUID NOT NULL REFERENCES analytics_alerts(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Event details
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('triggered', 'acknowledged', 'resolved', 'suppressed')),
    previous_status VARCHAR(50),
    new_status VARCHAR(50),

    -- Event context
    trigger_values JSONB DEFAULT '{}',
    context_data JSONB DEFAULT '{}',

    -- Notification details
    notifications_sent JSONB DEFAULT '[]',
    notification_results JSONB DEFAULT '{}',

    -- User actions
    action_taken_by UUID REFERENCES users(id),
    action_notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Create partitions for alert history
CREATE TABLE analytics_alert_history_y2024m01 PARTITION OF analytics_alert_history
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE analytics_alert_history_y2024m02 PARTITION OF analytics_alert_history
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- ============================================================================
-- INDEXES FOR PERFORMANCE OPTIMIZATION
-- ============================================================================

-- Analytics tables indexes
CREATE INDEX idx_entity_analytics_org_time ON entity_analytics(organization_id, time_bucket DESC);
CREATE INDEX idx_entity_analytics_bucket_type ON entity_analytics(bucket_type, time_bucket DESC);
CREATE INDEX idx_entity_analytics_growth ON entity_analytics(entity_growth_rate DESC, time_bucket DESC);

CREATE INDEX idx_relationship_analytics_org_time ON relationship_analytics(organization_id, time_bucket DESC);
CREATE INDEX idx_relationship_analytics_bucket_type ON relationship_analytics(bucket_type, time_bucket DESC);
CREATE INDEX idx_relationship_analytics_connectivity ON relationship_analytics(avg_connections_per_entity DESC, time_bucket DESC);

CREATE INDEX idx_graph_metrics_analytics_org ON graph_metrics_analytics(organization_id, computed_at DESC);
CREATE INDEX idx_graph_metrics_analytics_density ON graph_metrics_analytics(graph_density DESC, computed_at DESC);
CREATE INDEX idx_graph_metrics_analytics_snapshot ON graph_metrics_analytics(graph_snapshot_id, computed_at DESC);

CREATE INDEX idx_document_analytics_org_time ON document_analytics(organization_id, time_bucket DESC);
CREATE INDEX idx_document_analytics_processing ON document_analytics(processing_success_rate DESC, time_bucket DESC);
CREATE INDEX idx_document_analytics_quality ON document_analytics(avg_quality_score DESC, time_bucket DESC);

CREATE INDEX idx_user_interaction_analytics_org_time ON user_interaction_analytics(organization_id, time_bucket DESC);
CREATE INDEX idx_user_interaction_analytics_activity ON user_interaction_analytics(active_users DESC, time_bucket DESC);
CREATE INDEX idx_user_interaction_analytics_satisfaction ON user_interaction_analytics(avg_user_satisfaction_score DESC, time_bucket DESC);

-- Dashboard configuration indexes
CREATE INDEX idx_dashboard_configurations_org ON dashboard_configurations(organization_id, is_active);
CREATE INDEX idx_dashboard_configurations_user ON dashboard_configurations(user_id, is_active);
CREATE INDEX idx_dashboard_configurations_type ON dashboard_configurations(config_type, is_default);

CREATE INDEX idx_widget_definitions_type ON widget_definitions(widget_type, widget_category);
CREATE INDEX idx_widget_permissions ON widget_definitions(required_permissions);
CREATE INDEX idx_widget_active ON widget_definitions(is_active, widget_type);

-- Report indexes
CREATE INDEX idx_custom_reports_org ON custom_analytics_reports(organization_id, created_at DESC);
CREATE INDEX idx_custom_reports_category ON custom_analytics_reports(report_category, is_active);
CREATE INDEX idx_custom_reports_template ON custom_analytics_reports(is_template, template_category);

CREATE INDEX idx_report_executions_report ON report_executions(report_id, started_at DESC);
CREATE INDEX idx_report_executions_status ON report_executions(execution_status, started_at DESC);
CREATE INDEX idx_report_executions_org ON report_executions(organization_id, started_at DESC);

-- Cache indexes
CREATE INDEX idx_analytics_cache_key ON analytics_cache(cache_key, cache_type);
CREATE INDEX idx_analytics_cache_expires ON analytics_cache(expires_at);
CREATE INDEX idx_analytics_cache_access ON analytics_cache(last_accessed_at DESC);
CREATE INDEX idx_analytics_cache_type ON analytics_cache(cache_type, organization_id);

CREATE INDEX idx_dashboard_aggregations_org_time ON dashboard_aggregations(organization_id, time_bucket DESC);
CREATE INDEX idx_dashboard_aggregations_name ON dashboard_aggregations(aggregation_name, aggregation_type);

-- Alert indexes
CREATE INDEX idx_analytics_alerts_org ON analytics_alerts(organization_id, status);
CREATE INDEX idx_analytics_alerts_type ON analytics_alerts(alert_type, severity);
CREATE INDEX idx_analytics_alerts_triggered ON analytics_alerts(last_triggered_at DESC);
CREATE INDEX idx_analytics_alerts_severity ON analytics_alerts(severity, status);

CREATE INDEX idx_analytics_alert_history_alert ON analytics_alert_history(alert_id, created_at DESC);
CREATE INDEX idx_analytics_alert_history_event ON analytics_alert_history(event_type, created_at DESC);

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

-- Enable RLS on analytics tables
ALTER TABLE entity_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE relationship_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE graph_metrics_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_interaction_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE dashboard_configurations ENABLE ROW LEVEL SECURITY;
ALTER TABLE custom_analytics_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE dashboard_aggregations ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_alert_history ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY entity_analytics_org_policy ON entity_analytics
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY relationship_analytics_org_policy ON relationship_analytics
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY graph_metrics_analytics_org_policy ON graph_metrics_analytics
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY document_analytics_org_policy ON document_analytics
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY user_interaction_analytics_org_policy ON user_interaction_analytics
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- ============================================================================
-- TRIGGERS AND STORED PROCEDURES
-- ============================================================================

-- Function to update real-time dashboard metrics
CREATE OR REPLACE FUNCTION refresh_real_time_dashboard_metrics()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY real_time_dashboard_metrics;
END;
$$ LANGUAGE plpgsql;

-- Function to automatically create time-based partitions
CREATE OR REPLACE FUNCTION create_analytics_partitions()
RETURNS VOID AS $$
DECLARE
    current_month DATE;
    next_month DATE;
    partition_name TEXT;
BEGIN
    current_month := DATE_TRUNC('month', CURRENT_DATE);
    next_month := current_month + INTERVAL '1 month';

    -- Create partitions for each analytics table
    FOR partition_name IN ARRAY[
        'entity_analytics_y' || to_char(current_month, 'YYYY') || 'm' || LPAD(EXTRACT(MONTH FROM current_month)::TEXT, 2, '0'),
        'relationship_analytics_y' || to_char(current_month, 'YYYY') || 'm' || LPAD(EXTRACT(MONTH FROM current_month)::TEXT, 2, '0'),
        'document_analytics_y' || to_char(current_month, 'YYYY') || 'm' || LPAD(EXTRACT(MONTH FROM current_month)::TEXT, 2, '0'),
        'user_interaction_analytics_y' || to_char(current_month, 'YYYY') || 'm' || LPAD(EXTRACT(MONTH FROM current_month)::TEXT, 2, '0'),
        'report_executions_y' || to_char(current_month, 'YYYY') || 'm' || LPAD(EXTRACT(MONTH FROM current_month)::TEXT, 2, '0'),
        'analytics_alert_history_y' || to_char(current_month, 'YYYY') || 'm' || LPAD(EXTRACT(MONTH FROM current_month)::TEXT, 2, '0')
    ] LOOP
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                       partition_name, 'entity_analytics', current_month, next_month);
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function to aggregate entity analytics
CREATE OR REPLACE FUNCTION aggregate_entity_analytics(
    p_organization_id UUID,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ,
    p_bucket_type VARCHAR(20)
) RETURNS VOID AS $$
DECLARE
    time_bucket TIMESTAMPTZ;
    bucket_interval INTERVAL;
BEGIN
    -- Determine bucket interval
    CASE p_bucket_type
        WHEN 'hour' THEN bucket_interval := INTERVAL '1 hour';
        WHEN 'day' THEN bucket_interval := INTERVAL '1 day';
        WHEN 'week' THEN bucket_interval := INTERVAL '1 week';
        WHEN 'month' THEN bucket_interval := INTERVAL '1 month';
    END CASE;

    -- Generate time buckets and aggregate data
    FOR time_bucket IN
        SELECT generate_series(p_start_time, p_end_time, bucket_interval) AS bucket
    LOOP
        INSERT INTO entity_analytics (
            organization_id,
            time_bucket,
            bucket_type,
            total_entities,
            new_entities,
            entity_growth_rate,
            entity_type_counts,
            avg_confidence_score,
            entities_processed,
            processing_success_rate,
            entities_per_document
        )
        SELECT
            p_organization_id,
            time_bucket.bucket,
            p_bucket_type,
            COUNT(*) FILTER (WHERE e.created_at <= time_bucket.bucket + bucket_interval) as total_entities,
            COUNT(*) FILTER (WHERE e.created_at >= time_bucket.bucket AND e.created_at < time_bucket.bucket + bucket_interval) as new_entities,
            -- Calculate growth rate
            CASE
                WHEN LAG(COUNT(*)) OVER (ORDER BY time_bucket.bucket) = 0 THEN 0
                ELSE (COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY time_bucket.bucket))::DECIMAL / NULLIF(LAG(COUNT(*)) OVER (ORDER BY time_bucket.bucket), 0)
            END as entity_growth_rate,
            jsonb_object_agg(e.entity_type, type_count) as entity_type_counts,
            AVG(e.extraction_confidence) as avg_confidence_score,
            COUNT(*) FILTER (WHERE e.created_at >= time_bucket.bucket AND e.created_at < time_bucket.bucket + bucket_interval) as entities_processed,
            -- Calculate processing success rate from documents
            COALESCE(success_rate.avg_success, 1.0) as processing_success_rate,
            CASE
                WHEN doc_count.total_docs = 0 THEN 0
                ELSE COUNT(*)::DECIMAL / doc_count.total_docs
            END as entities_per_document
        FROM entities e
        CROSS JOIN LATERAL (
            SELECT entity_type, COUNT(*) as type_count
            FROM entities e2
            WHERE e2.organization_id = p_organization_id
              AND e2.created_at >= time_bucket.bucket
              AND e2.created_at < time_bucket.bucket + bucket_interval
            GROUP BY entity_type
        ) type_counts
        LEFT JOIN LATERAL (
            SELECT AVG(processing_success_rate) as avg_success
            FROM document_analytics da
            WHERE da.organization_id = p_organization_id
              AND da.time_bucket >= time_bucket.bucket
              AND da.time_bucket < time_bucket.bucket + bucket_interval
              AND da.bucket_type = p_bucket_type
        ) success_rate ON true
        LEFT JOIN LATERAL (
            SELECT COUNT(*) as total_docs
            FROM documents d
            WHERE d.organization_id = p_organization_id
              AND d.created_at <= time_bucket.bucket + bucket_interval
              AND d.is_deleted = FALSE
        ) doc_count ON true
        WHERE e.organization_id = p_organization_id
          AND e.created_at <= time_bucket.bucket + bucket_interval
        GROUP BY time_bucket.bucket
        ON CONFLICT (organization_id, time_bucket, bucket_type)
        DO UPDATE SET
            total_entities = EXCLUDED.total_entities,
            new_entities = EXCLUDED.new_entities,
            entity_growth_rate = EXCLUDED.entity_growth_rate,
            entity_type_counts = EXCLUDED.entity_type_counts,
            avg_confidence_score = EXCLUDED.avg_confidence_score,
            entities_processed = EXCLUDED.entities_processed,
            processing_success_rate = EXCLUDED.processing_success_rate,
            entities_per_document = EXCLUDED.entities_per_document;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function to clean up expired cache entries
CREATE OR REPLACE FUNCTION cleanup_analytics_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM analytics_cache
    WHERE expires_at < NOW()
    RETURNING COUNT(*) INTO deleted_count;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update organization analytics on entity changes
CREATE OR REPLACE FUNCTION update_entity_analytics_trigger()
RETURNS TRIGGER AS $$
BEGIN
    -- Trigger background job to update analytics
    -- This would typically be handled by a background worker
    -- For now, we'll just mark the organization as needing analytics update
    PERFORM pg_notify('analytics_update', jsonb_build_object(
        'organization_id', NEW.organization_id,
        'entity_id', NEW.id,
        'action', TG_OP,
        'timestamp', NOW()
    )::text);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Create triggers for real-time analytics updates
CREATE TRIGGER entity_analytics_update_trigger
    AFTER INSERT OR UPDATE OR DELETE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION update_entity_analytics_trigger();

CREATE TRIGGER relationship_analytics_update_trigger
    AFTER INSERT OR UPDATE OR DELETE ON entity_relationships
    FOR EACH ROW
    EXECUTE FUNCTION update_entity_analytics_trigger();

-- ============================================================================
-- VIEWS FOR COMMON ANALYTICS QUERIES
-- ============================================================================

-- Entity growth trend view
CREATE VIEW entity_growth_trends AS
SELECT
    organization_id,
    time_bucket,
    bucket_type,
    total_entities,
    new_entities,
    entity_growth_rate,
    LAG(total_entities) OVER (
        PARTITION BY organization_id, bucket_type
        ORDER BY time_bucket
    ) as previous_total_entities,
    LAG(new_entities) OVER (
        PARTITION BY organization_id, bucket_type
        ORDER BY time_bucket
    ) as previous_new_entities
FROM entity_analytics
WHERE bucket_type IN ('day', 'week', 'month');

-- Relationship strength distribution view
CREATE VIEW relationship_strength_analysis AS
SELECT
    organization_id,
    time_bucket,
    bucket_type,
    total_relationships,
    avg_relationship_strength,
    avg_connections_per_entity,
    hub_entities,
    bidirectional_percentage,
    -- Strength categories
    (relationship_strength_distribution->>'high')::INTEGER as high_strength_count,
    (relationship_strength_distribution->>'medium')::INTEGER as medium_strength_count,
    (relationship_strength_distribution->>'low')::INTEGER as low_strength_count
FROM relationship_analytics
WHERE bucket_type IN ('day', 'week', 'month');

-- Document processing performance view
CREATE VIEW document_processing_performance AS
SELECT
    organization_id,
    time_bucket,
    bucket_type,
    total_documents,
    processed_documents,
    processing_success_rate,
    avg_processing_time_ms,
    avg_quality_score,
    processing_bottlenecks,
    -- Performance categories
    CASE
        WHEN processing_success_rate >= 0.95 THEN 'excellent'
        WHEN processing_success_rate >= 0.85 THEN 'good'
        WHEN processing_success_rate >= 0.70 THEN 'fair'
        ELSE 'poor'
    END as performance_grade,
    -- Processing efficiency
    CASE
        WHEN avg_processing_time_ms <= 5000 THEN 'fast'
        WHEN avg_processing_time_ms <= 15000 THEN 'normal'
        WHEN avg_processing_time_ms <= 30000 THEN 'slow'
        ELSE 'very_slow'
    END as processing_speed_category
FROM document_analytics
WHERE bucket_type IN ('hour', 'day', 'week');

-- User engagement metrics view
CREATE VIEW user_engagement_metrics AS
SELECT
    organization_id,
    time_bucket,
    bucket_type,
    active_users,
    total_sessions,
    avg_session_duration_seconds,
    total_searches,
    avg_user_satisfaction_score,
    avg_response_time_ms,
    -- Engagement categories
    CASE
        WHEN avg_user_satisfaction_score >= 4.5 THEN 'very_high'
        WHEN avg_user_satisfaction_score >= 3.5 THEN 'high'
        WHEN avg_user_satisfaction_score >= 2.5 THEN 'medium'
        ELSE 'low'
    END as satisfaction_level,
    -- Activity intensity
    CASE
        WHEN total_sessions >= 100 THEN 'very_high'
        WHEN total_sessions >= 50 THEN 'high'
        WHEN total_sessions >= 20 THEN 'medium'
        ELSE 'low'
    END as activity_level,
    -- Response performance
    CASE
        WHEN avg_response_time_ms <= 1000 THEN 'excellent'
        WHEN avg_response_time_ms <= 2000 THEN 'good'
        WHEN avg_response_time_ms <= 5000 THEN 'fair'
        ELSE 'poor'
    END as response_performance
FROM user_interaction_analytics
WHERE bucket_type IN ('day', 'week', 'month');

-- System health dashboard view
CREATE VIEW system_health_dashboard AS
SELECT
    org.id as organization_id,
    org.name as organization_name,

    -- Current metrics from materialized view
    rtm.*,

    -- Recent trends
    entity_trend.recent_growth_rate as entity_growth_trend,
    document_trend.processing_trend,
    user_trend.engagement_trend,

    -- Health indicators
    CASE
        WHEN rtm.system_health_score >= 0.9 THEN 'excellent'
        WHEN rtm.system_health_score >= 0.7 THEN 'good'
        WHEN rtm.system_health_score >= 0.5 THEN 'fair'
        ELSE 'poor'
    END as overall_health_status,

    -- Capacity indicators
    CASE
        WHEN org.current_storage_gb >= (org.storage_limit_gb * 0.9) THEN 'critical'
        WHEN org.current_storage_gb >= (org.storage_limit_gb * 0.8) THEN 'warning'
        ELSE 'healthy'
    END as storage_status,

    -- Performance indicators
    CASE
        WHEN rtm.avg_search_response_time <= 1000 THEN 'excellent'
        WHEN rtm.avg_search_response_time <= 2000 THEN 'good'
        WHEN rtm.avg_search_response_time <= 5000 THEN 'fair'
        ELSE 'poor'
    END as performance_status

FROM organizations org
JOIN real_time_dashboard_metrics rtm ON org.id = rtm.organization_id
LEFT JOIN LATERAL (
    SELECT entity_growth_rate as recent_growth_rate
    FROM entity_analytics ega
    WHERE ega.organization_id = org.id
      AND ega.bucket_type = 'day'
      AND ega.time_bucket >= CURRENT_DATE - INTERVAL '7 days'
    ORDER BY ega.time_bucket DESC
    LIMIT 1
) entity_trend ON true
LEFT JOIN LATERAL (
    SELECT processing_success_rate as processing_trend
    FROM document_analytics dga
    WHERE dga.organization_id = org.id
      AND dga.bucket_type = 'day'
      AND dga.time_bucket >= CURRENT_DATE - INTERVAL '7 days'
    ORDER BY dga.time_bucket DESC
    LIMIT 1
) document_trend ON true
LEFT JOIN LATERAL (
    SELECT avg_user_satisfaction_score as engagement_trend
    FROM user_interaction_analytics uia
    WHERE uia.organization_id = org.id
      AND uia.bucket_type = 'day'
      AND uia.time_bucket >= CURRENT_DATE - INTERVAL '7 days'
    ORDER BY uia.time_bucket DESC
    LIMIT 1
) user_trend ON true;

-- ============================================================================
-- INSERT SAMPLE DATA FOR DEVELOPMENT
-- ============================================================================

-- Insert sample widget definitions
INSERT INTO widget_definitions (widget_name, widget_type, widget_category, data_source, chart_type, description) VALUES
('Entity Count Trend', 'line_chart', 'entity', 'entity_analytics', 'line', 'Shows the growth of entities over time'),
('Entity Type Distribution', 'pie_chart', 'entity', 'entity_analytics', 'pie', 'Distribution of entities by type'),
('Relationship Strength Heatmap', 'heatmap', 'relationship', 'relationship_analytics', 'heatmap', 'Visualizes relationship strengths between entity types'),
('Document Processing Success Rate', 'gauge_chart', 'document', 'document_analytics', 'gauge', 'Current document processing success rate'),
('User Activity Timeline', 'area_chart', 'user', 'user_interaction_analytics', 'area', 'User activity patterns over time'),
('System Health Score', 'metric_card', 'system', 'real_time_dashboard_metrics', 'metric', 'Overall system health indicator'),
('Graph Density Trend', 'line_chart', 'graph', 'graph_metrics_analytics', 'line', 'Graph density changes over time'),
('Top Entities by Centrality', 'bar_chart', 'graph', 'graph_metrics_analytics', 'bar', 'Most important entities by centrality score'),
('Search Performance Metrics', 'multi_line_chart', 'user', 'user_interaction_analytics', 'line', 'Search response time and success rate trends'),
('Quality Score Distribution', 'histogram', 'document', 'document_analytics', 'histogram', 'Distribution of document quality scores');

-- Insert sample dashboard configuration
INSERT INTO dashboard_configurations (organization_id, config_name, config_type, layout, widgets, is_default)
SELECT
    id,
    'Default Analytics Dashboard',
    'organization',
    '{"grid": {"columns": 12, "rows": 8}, "widgets": [{"id": "metric_card", "position": {"x": 0, "y": 0, "w": 3, "h": 2}}]}',
    '[{"widget_name": "System Health Score", "position": {"x": 0, "y": 0, "w": 3, "h": 2}}, {"widget_name": "Entity Count Trend", "position": {"x": 3, "y": 0, "w": 6, "h": 3}}, {"widget_name": "Document Processing Success Rate", "position": {"x": 9, "y": 0, "w": 3, "h": 2}}]',
    TRUE
FROM organizations
WHERE slug = 'system-default';

-- Insert sample analytics alerts
INSERT INTO analytics_alerts (organization_id, alert_name, alert_type, alert_condition, severity, notification_channels)
SELECT
    id,
    'Processing Success Rate Drop',
    'metric_threshold',
    '{"metric": "processing_success_rate", "operator": "<", "threshold": 0.8, "consecutive_periods": 2}',
    'warning',
    '["email", "dashboard"]'
FROM organizations
WHERE slug = 'system-default';

COMMIT;