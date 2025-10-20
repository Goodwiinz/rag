-- Migration 005: Correct Knowledge Graph Architecture
-- Fixes critical architectural violation where graph algorithms were in frontend
-- Implements proper backend-first knowledge graph processing

BEGIN;

-- Create corrected graph analytics tables
-- These tables support backend computation of graph algorithms

-- Graph computation cache for algorithm results
CREATE TABLE IF NOT EXISTS graph_computation_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Computation identification
    computation_type VARCHAR(100) NOT NULL, -- 'centrality', 'community_detection', 'pathfinding'
    computation_version VARCHAR(50) NOT NULL, -- Version of algorithm/parameters
    algorithm_name VARCHAR(100) NOT NULL, -- Specific algorithm used

    -- Input parameters (as JSON for flexibility)
    input_parameters JSONB NOT NULL,

    -- Results (cached computation output)
    result_data JSONB NOT NULL,

    -- Performance metrics
    computation_time_ms INTEGER,
    node_count INTEGER,
    edge_count INTEGER,
    memory_usage_mb INTEGER,

    -- Cache management
    expires_at TIMESTAMPTZ NOT NULL,
    hit_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ DEFAULT NOW(),

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by_user_id UUID REFERENCES users(id),

    -- Prevent duplicate computations
    UNIQUE(organization_id, computation_type, computation_version, md5(input_parameters::text))
);

-- Real-time graph analytics snapshots
CREATE TABLE IF NOT EXISTS graph_analytics_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    snapshot_timestamp TIMESTAMPTZ DEFAULT NOW(),

    -- Overall graph metrics
    total_nodes INTEGER NOT NULL DEFAULT 0,
    total_edges INTEGER NOT NULL DEFAULT 0,
    graph_density DECIMAL(15,12) NOT NULL DEFAULT 0,
    average_degree DECIMAL(10,4) NOT NULL DEFAULT 0,
    connected_components INTEGER NOT NULL DEFAULT 0,
    largest_component_size INTEGER NOT NULL DEFAULT 0,

    -- Quality metrics
    average_confidence DECIMAL(5,4) NOT NULL DEFAULT 0,
    high_quality_nodes INTEGER NOT NULL DEFAULT 0, -- confidence > 0.8
    low_quality_nodes INTEGER NOT NULL DEFAULT 0,  -- confidence < 0.5

    -- Distribution data (JSON for flexibility)
    entity_type_distribution JSONB DEFAULT '{}',
    relationship_type_distribution JSONB DEFAULT '{}',
    centrality_distribution JSONB DEFAULT '{}',

    -- Performance metrics for algorithms
    centrality_computation_time_ms INTEGER,
    clustering_computation_time_ms INTEGER,
    pathfinding_computation_time_ms INTEGER,

    -- Change tracking (since last snapshot)
    nodes_added_since_last_snapshot INTEGER DEFAULT 0,
    nodes_removed_since_last_snapshot INTEGER DEFAULT 0,
    edges_added_since_last_snapshot INTEGER DEFAULT 0,
    edges_removed_since_last_snapshot INTEGER DEFAULT 0,

    -- Indexes for time-series queries
    INDEX idx_graph_snapshots_org_time (organization_id, snapshot_timestamp DESC),
    INDEX idx_graph_snapshots_timestamp (snapshot_timestamp DESC)
);

-- User graph preferences and views
CREATE TABLE IF NOT EXISTS user_graph_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Visualization preferences
    default_layout_algorithm VARCHAR(50) DEFAULT 'force',
    node_color_scheme VARCHAR(50) DEFAULT 'type_based',
    edge_color_scheme VARCHAR(50) DEFAULT 'type_based',
    show_labels BOOLEAN DEFAULT true,
    label_threshold INTEGER DEFAULT 50,

    -- Filter preferences
    default_entity_types TEXT[] DEFAULT '{}',
    default_relationship_types TEXT[] DEFAULT '{}',
    confidence_threshold DECIMAL(5,4) DEFAULT 0.5 CHECK (confidence_threshold >= 0 AND confidence_threshold <= 1),
    strength_threshold DECIMAL(5,4) DEFAULT 0.3 CHECK (strength_threshold >= 0 AND strength_threshold <= 1),

    -- Analytics preferences
    preferred_centrality_metric VARCHAR(100) DEFAULT 'degree_centrality',
    show_community_clusters BOOLEAN DEFAULT true,
    show_isolated_nodes BOOLEAN DEFAULT false,

    -- Performance preferences
    max_nodes_for_realtime INTEGER DEFAULT 500,
    animation_enabled BOOLEAN DEFAULT true,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, organization_id)
);

-- Graph computation job tracking
CREATE TABLE IF NOT EXISTS graph_computation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),

    -- Job identification
    job_type VARCHAR(100) NOT NULL, -- 'centrality_analysis', 'clustering', 'pathfinding'
    algorithm_name VARCHAR(100) NOT NULL, -- 'pagerank', 'louvain', 'dijkstra'

    -- Job parameters
    input_parameters JSONB NOT NULL,

    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'queued', 'running', 'completed', 'failed', 'cancelled')),
    progress_percentage INTEGER DEFAULT 0 CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    current_step VARCHAR(500),
    steps_completed INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0,

    -- Timing
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    estimated_completion TIMESTAMPTZ,

    -- Resource usage
    cpu_time_ms INTEGER,
    memory_used_mb INTEGER,
    nodes_processed INTEGER DEFAULT 0,
    edges_processed INTEGER DEFAULT 0,

    -- Results
    result_location VARCHAR(500), -- S3 path or similar for large results
    result_summary JSONB, -- Summary of results

    -- Error handling
    error_message TEXT,
    error_details JSONB,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Indexes for job management
    INDEX idx_graph_jobs_org_status (organization_id, status),
    INDEX idx_graph_jobs_user_status (user_id, status),
    INDEX idx_graph_jobs_created_at (created_at DESC),
    INDEX idx_graph_jobs_type_status (job_type, status)
);

-- Entity-specific analytics cache
CREATE TABLE IF NOT EXISTS entity_analytics_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Centrality metrics
    degree_centrality DECIMAL(15,8),
    betweenness_centrality DECIMAL(15,8),
    closeness_centrality DECIMAL(15,8),
    eigenvector_centrality DECIMAL(15,8),
    pagerank_score DECIMAL(15,8),

    -- Local structure metrics
    clustering_coefficient DECIMAL(10,8),
    neighbor_count INTEGER,
    ego_network_density DECIMAL(10,8),

    -- Network role indicators
    is_bridge_node BOOLEAN DEFAULT false,
    is_peripheral BOOLEAN DEFAULT false,
    is_hub_node BOOLEAN DEFAULT false,
    community_id VARCHAR(100),
    community_importance DECIMAL(5,4),

    -- Temporal metrics
    importance_trend JSONB, -- Historical importance scores
    connection_velocity DECIMAL(10,4), -- Rate of new connections
    activity_score DECIMAL(5,4), -- Recent activity level

    -- Computation metadata
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    algorithm_version VARCHAR(50),
    computation_time_ms INTEGER,
    computation_parameters JSONB,

    -- Cache management
    expires_at TIMESTAMPTZ,
    hit_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(entity_id, organization_id),

    -- Indexes for analytics queries
    INDEX idx_entity_analytics_org (organization_id),
    INDEX idx_entity_analytics_pagerank (pagerank_score DESC),
    INDEX idx_entity_analytics_community (community_id),
    INDEX idx_entity_analytics_computed (computed_at DESC)
);

-- Graph insights and recommendations
CREATE TABLE IF NOT EXISTS graph_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Insight classification
    insight_type VARCHAR(100) NOT NULL, -- 'centrality_anomaly', 'community_shift', 'quality_issue', 'performance_alert'
    severity VARCHAR(20) DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    category VARCHAR(50) NOT NULL, -- 'quality', 'connectivity', 'performance', 'growth', 'security'

    -- Content
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    detailed_analysis TEXT,

    -- Quantitative metrics
    impact_score DECIMAL(5,4) CHECK (impact_score >= 0 AND impact_score <= 1),
    confidence DECIMAL(5,4) CHECK (confidence >= 0 AND confidence <= 1),
    urgency_score DECIMAL(5,4) CHECK (urgency_score >= 0 AND urgency_score <= 1),

    -- Affected elements
    affected_entity_ids UUID[] DEFAULT '{}',
    affected_relationship_ids UUID[] DEFAULT '{}',
    affected_users UUID[] DEFAULT '{}',

    -- Context and evidence
    graph_snapshot_before JSONB,
    graph_snapshot_after JSONB,
    supporting_metrics JSONB,
    evidence_snippets TEXT[],

    -- Recommendations
    recommended_actions JSONB,
    action_priority INTEGER DEFAULT 1,
    estimated_effort_hours INTEGER,
    potential_impact_description TEXT,

    -- Generation metadata
    generated_by VARCHAR(100) DEFAULT 'system', -- 'system', 'user', 'ml_model'
    ml_model_version VARCHAR(50),
    generation_parameters JSONB,

    -- Lifecycle management
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,

    -- User interaction
    acknowledged_by_user_id UUID REFERENCES users(id),
    acknowledged_at TIMESTAMPTZ,
    user_feedback TEXT,
    feedback_rating INTEGER CHECK (feedback_rating >= 1 AND feedback_rating <= 5),

    -- Resolution tracking
    resolved BOOLEAN DEFAULT false,
    resolved_by_user_id UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Indexes for insight queries
    INDEX idx_graph_insights_org_active (organization_id, is_active),
    INDEX idx_graph_insights_severity (severity),
    INDEX idx_graph_insights_category (category),
    INDEX idx_graph_insights_type (insight_type),
    INDEX idx_graph_insights_impact (impact_score DESC),
    INDEX idx_graph_insights_created (created_at DESC)
);

-- Performance metrics tracking
CREATE TABLE IF NOT EXISTS graph_performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),

    -- Operation details
    operation_type VARCHAR(100) NOT NULL, -- 'centrality_computation', 'layout', 'pathfinding'
    algorithm_name VARCHAR(100),

    -- Scale metrics
    entity_count INTEGER NOT NULL,
    relationship_count INTEGER NOT NULL,
    graph_density DECIMAL(15,12),

    -- Performance metrics
    computation_time_ms INTEGER NOT NULL,
    memory_usage_mb INTEGER,
    cpu_usage_percent DECIMAL(5,2),

    -- Cache performance
    cache_hit_rate DECIMAL(5,4),
    cache_misses INTEGER,
    cache_hits INTEGER,

    -- User experience metrics
    ui_response_time_ms INTEGER,
    total_user_time_ms INTEGER,

    -- System metrics
    database_query_time_ms INTEGER,
    neo4j_query_time_ms INTEGER,
    redis_operation_time_ms INTEGER,

    -- Quality metrics
    result_quality_score DECIMAL(5,4),
    error_count INTEGER DEFAULT 0,

    -- Context
    request_parameters JSONB,
    user_agent TEXT,
    session_id UUID,

    -- Timestamp
    timestamp TIMESTAMPTZ DEFAULT NOW(),

    -- Indexes for performance analysis
    INDEX idx_graph_perf_org_time (organization_id, timestamp DESC),
    INDEX idx_graph_perf_operation (operation_type, timestamp DESC),
    INDEX idx_graph_perf_algorithm (algorithm_name, timestamp DESC),
    INDEX idx_graph_perf_user_time (user_id, timestamp DESC)
);

-- Enhance existing tables with graph analytics support

-- Add graph-related columns to entities table
ALTER TABLE entities
ADD COLUMN IF NOT EXISTS graph_node_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS importance_score DECIMAL(5,4),
ADD COLUMN IF NOT EXISTS centrality_metrics JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS community_info JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS graph_analytics JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS last_graph_update TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS graph_analytics_version VARCHAR(50);

-- Add graph-related columns to entity_relationships table
ALTER TABLE entity_relationships
ADD COLUMN IF NOT EXISTS graph_relationship_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS pathfinding_weight DECIMAL(5,4) DEFAULT 1.0,
ADD COLUMN IF NOT EXISTS graph_analytics JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS last_graph_update TIMESTAMPTZ;

-- Create improved indexes for graph operations

-- Entity indexes for graph queries
CREATE INDEX IF NOT EXISTS idx_entities_graph_node_id ON entities(graph_node_id) WHERE graph_node_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_entities_importance_score ON entities(importance_score DESC) WHERE importance_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_entities_last_graph_update ON entities(last_graph_update DESC);
CREATE INDEX IF NOT EXISTS idx_entities_org_graph_analytics ON entities(organization_id, last_graph_update) WHERE graph_analytics IS NOT NULL;

-- Relationship indexes for graph queries
CREATE INDEX IF NOT EXISTS idx_entity_relationships_graph_id ON entity_relationships(graph_relationship_id) WHERE graph_relationship_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_entity_relationships_pathfinding_weight ON entity_relationships(pathfinding_weight DESC);
CREATE INDEX IF NOT EXISTS idx_entity_relationships_last_graph_update ON entity_relationships(last_graph_update DESC);

-- Composite indexes for common graph query patterns
CREATE INDEX IF NOT EXISTS idx_entities_org_type_importance ON entities(organization_id, entity_type, importance_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_relationships_org_type_strength ON entity_relationships(organization_id, relationship_type, relationship_strength DESC);

-- Full-text search indexes for graph entities
CREATE INDEX IF NOT EXISTS idx_entities_graph_search ON entities USING GIN(to_tsvector('english', name || ' ' || COALESCE(description, '') || ' ' || COALESCE(canonical_name, '')));

-- Create triggers for automatic graph analytics updates

-- Function to trigger graph recomputation when entities change
CREATE OR REPLACE FUNCTION trigger_entity_graph_update()
RETURNS TRIGGER AS $$
BEGIN
    -- Mark entity for graph analytics recomputation
    UPDATE entities
    SET
        last_graph_update = NOW(),
        graph_analytics_version = NULL
    WHERE id = NEW.id;

    -- Invalidate related cache entries
    PERFORM pg_notify('graph_invalidation',
        json_build_object(
            'type', 'entity_updated',
            'entity_id', NEW.id,
            'organization_id', NEW.organization_id,
            'timestamp', NOW()
        )::text
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for entity changes
CREATE TRIGGER trigger_entity_insert_graph_update
    AFTER INSERT OR UPDATE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION trigger_entity_graph_update();

CREATE TRIGGER trigger_entity_delete_graph_update
    AFTER DELETE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION trigger_entity_graph_update();

-- Function to trigger graph recomputation when relationships change
CREATE OR REPLACE FUNCTION trigger_relationship_graph_update()
RETURNS TRIGGER AS $$
BEGIN
    -- Mark relationships for graph analytics recomputation
    UPDATE entity_relationships
    SET last_graph_update = NOW()
    WHERE id = NEW.id;

    -- Mark related entities for recomputation
    UPDATE entities
    SET last_graph_update = NOW()
    WHERE id = NEW.source_entity_id OR id = NEW.target_entity_id;

    -- Invalidate related cache entries
    PERFORM pg_notify('graph_invalidation',
        json_build_object(
            'type', 'relationship_updated',
            'relationship_id', NEW.id,
            'source_entity_id', NEW.source_entity_id,
            'target_entity_id', NEW.target_entity_id,
            'organization_id', NEW.organization_id,
            'timestamp', NOW()
        )::text
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for relationship changes
CREATE TRIGGER trigger_relationship_insert_graph_update
    AFTER INSERT OR UPDATE ON entity_relationships
    FOR EACH ROW
    EXECUTE FUNCTION trigger_relationship_graph_update();

CREATE TRIGGER trigger_relationship_delete_graph_update
    AFTER DELETE ON entity_relationships
    FOR EACH ROW
    EXECUTE FUNCTION trigger_relationship_graph_update();

-- Function to update user preferences timestamp
CREATE OR REPLACE FUNCTION update_user_graph_preferences_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_user_graph_preferences_update
    BEFORE UPDATE ON user_graph_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_user_graph_preferences_timestamp();

-- Create views for common graph analytics queries

-- Graph health dashboard view
CREATE OR REPLACE VIEW graph_health_dashboard AS
SELECT
    o.id as organization_id,
    o.name as organization_name,

    -- Current snapshot metrics
    COALESCE(gas.total_nodes, 0) as total_entities,
    COALESCE(gas.total_edges, 0) as total_relationships,
    COALESCE(gas.graph_density, 0) as graph_density,
    COALESCE(gas.average_degree, 0) as average_degree,
    COALESCE(gas.connected_components, 0) as connected_components,
    COALESCE(gas.largest_component_size, 0) as largest_component_size,

    -- Quality metrics
    COALESCE(gas.average_confidence, 0) as average_confidence,
    COALESCE(gas.high_quality_nodes, 0) as high_quality_entities,
    COALESCE(gas.low_quality_nodes, 0) as low_quality_entities,

    -- Performance metrics
    COALESCE(gas.centrality_computation_time_ms, 0) as last_centrality_time_ms,
    COALESCE(gas.clustering_computation_time_ms, 0) as last_clustering_time_ms,

    -- Recent activity
    COALESCE(gas.nodes_added_since_last_snapshot, 0) as nodes_added_recently,
    COALESCE(gas.edges_added_since_last_snapshot, 0) as edges_added_recently,

    -- Timestamp
    COALESCE(gas.snapshot_timestamp, NOW()) as last_snapshot_time

FROM organizations o
LEFT JOIN LATERAL (
    SELECT * FROM graph_analytics_snapshots
    WHERE organization_id = o.id
    ORDER BY snapshot_timestamp DESC
    LIMIT 1
) gas ON true;

-- Entity importance ranking view
CREATE OR REPLACE VIEW entity_importance_ranking AS
SELECT
    e.id as entity_id,
    e.name as entity_name,
    e.entity_type,
    e.organization_id,
    COALESCE(eac.pagerank_score, 0) as pagerank_score,
    COALESCE(eac.degree_centrality, 0) as degree_centrality,
    COALESCE(eac.betweenness_centrality, 0) as betweenness_centrality,
    COALESCE(eac.importance_score, e.confidence, 0) as combined_importance,
    COALESCE(eac.computed_at, e.created_at) as last_analyzed,
    e.confidence as extraction_confidence,
    eac.community_id,
    eac.is_bridge_node,
    eac.is_hub_node

FROM entities e
LEFT JOIN entity_analytics_cache eac ON e.id = eac.entity_id
WHERE e.is_deleted = false
  AND e.organization_id IS NOT NULL;

-- Active graph insights view
CREATE OR REPLACE VIEW active_graph_insights AS
SELECT
    gi.id,
    gi.organization_id,
    gi.insight_type,
    gi.severity,
    gi.category,
    gi.title,
    gi.description,
    gi.impact_score,
    gi.confidence,
    gi.affected_entity_ids,
    gi.recommended_actions,
    gi.action_priority,
    gi.created_at,
    gi.expires_at,
    CASE
        WHEN gi.expires_at < NOW() THEN false
        ELSE gi.is_active
    END as currently_active,
    CASE
        WHEN gi.acknowledged_by_user_id IS NOT NULL THEN true
        ELSE false
    END as is_acknowledged

FROM graph_insights gi
WHERE gi.is_active = true
  AND (gi.expires_at IS NULL OR gi.expires_at > NOW())
ORDER BY
    CASE gi.severity
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
    END,
    gi.impact_score DESC,
    gi.created_at DESC;

-- Enable Row Level Security on new tables
ALTER TABLE graph_computation_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE graph_analytics_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_graph_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE graph_computation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_analytics_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE graph_insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE graph_performance_metrics ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for multi-tenant isolation
CREATE POLICY graph_computation_cache_org_policy ON graph_computation_cache
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

CREATE POLICY graph_analytics_snapshots_org_policy ON graph_analytics_snapshots
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

CREATE POLICY user_graph_preferences_org_policy ON user_graph_preferences
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

CREATE POLICY graph_computation_jobs_org_policy ON graph_computation_jobs
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

CREATE POLICY entity_analytics_cache_org_policy ON entity_analytics_cache
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

CREATE POLICY graph_insights_org_policy ON graph_insights
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

CREATE POLICY graph_performance_metrics_org_policy ON graph_performance_metrics
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

-- Create utility functions for graph operations

-- Function to get graph health summary
CREATE OR REPLACE FUNCTION get_graph_health_summary(org_id UUID)
RETURNS TABLE(
    total_entities BIGINT,
    total_relationships BIGINT,
    graph_density DECIMAL(15,12),
    average_confidence DECIMAL(5,4),
    active_insights BIGINT,
    critical_insights BIGINT,
    latest_snapshot TIMESTAMPTZ,
    computation_queue_size BIGINT
) AS $$
BEGIN
    RETURN QUERY
    WITH latest_snapshot AS (
        SELECT * FROM graph_analytics_snapshots
        WHERE organization_id = org_id
        ORDER BY snapshot_timestamp DESC
        LIMIT 1
    ),
    insight_counts AS (
        SELECT
            COUNT(*) as total_insights,
            COUNT(*) FILTER (WHERE severity = 'critical') as critical_insights
        FROM graph_insights
        WHERE organization_id = org_id
          AND is_active = true
          AND (expires_at IS NULL OR expires_at > NOW())
    ),
    job_queue AS (
        SELECT COUNT(*) as queue_size
        FROM graph_computation_jobs
        WHERE organization_id = org_id
          AND status IN ('pending', 'queued', 'running')
    )
    SELECT
        COALESCE(ls.total_nodes, 0),
        COALESCE(ls.total_edges, 0),
        COALESCE(ls.graph_density, 0),
        COALESCE(ls.average_confidence, 0),
        COALESCE(ic.total_insights, 0),
        COALESCE(ic.critical_insights, 0),
        ls.snapshot_timestamp,
        COALESCE(jq.queue_size, 0)
    FROM latest_snapshot ls
    CROSS JOIN insight_counts ic
    CROSS JOIN job_queue jq;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to queue graph computation job
CREATE OR REPLACE FUNCTION queue_graph_computation(
    p_organization_id UUID,
    p_user_id UUID,
    p_job_type VARCHAR(100),
    p_algorithm_name VARCHAR(100),
    p_input_parameters JSONB,
    p_priority INTEGER DEFAULT 5
) RETURNS UUID AS $$
DECLARE
    job_id UUID;
BEGIN
    INSERT INTO graph_computation_jobs (
        organization_id,
        user_id,
        job_type,
        algorithm_name,
        input_parameters,
        status,
        created_at
    ) VALUES (
        p_organization_id,
        p_user_id,
        p_job_type,
        p_algorithm_name,
        p_input_parameters,
        'queued',
        NOW()
    ) RETURNING id INTO job_id;

    -- Notify background workers
    PERFORM pg_notify('graph_job_queued',
        json_build_object(
            'job_id', job_id,
            'organization_id', p_organization_id,
            'job_type', p_job_type,
            'priority', p_priority
        )::text
    );

    RETURN job_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to invalidate graph caches for organization
CREATE OR REPLACE FUNCTION invalidate_graph_caches(p_organization_id UUID)
RETURNS INTEGER AS $$
DECLARE
    invalidated_count INTEGER := 0;
BEGIN
    -- Invalidate computation cache
    UPDATE graph_computation_cache
    SET expires_at = NOW() - INTERVAL '1 second'
    WHERE organization_id = p_organization_id
      AND expires_at > NOW();

    GET DIAGNOSTICS invalidated_count = ROW_COUNT;

    -- Clear entity analytics cache
    UPDATE entity_analytics_cache
    SET expires_at = NOW() - INTERVAL '1 second'
    WHERE organization_id = p_organization_id
      AND expires_at > NOW();

    GET DIAGNOSTICS invalidated_count = invalidated_count + ROW_COUNT;

    -- Notify subscribers
    PERFORM pg_notify('graph_cache_invalidated',
        json_build_object(
            'organization_id', p_organization_id,
            'invalidated_count', invalidated_count,
            'timestamp', NOW()
        )::text
    );

    RETURN invalidated_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMIT;

-- Log successful migration
DO $$
BEGIN
    RAISE NOTICE '✅ Knowledge Graph Architecture Migration Completed Successfully!';
    RAISE NOTICE '📊 Created % tables for backend graph processing',
        (SELECT count(*) FROM information_schema.tables
         WHERE table_schema = 'public'
         AND table_name IN (
             'graph_computation_cache', 'graph_analytics_snapshots',
             'user_graph_preferences', 'graph_computation_jobs',
             'entity_analytics_cache', 'graph_insights',
             'graph_performance_metrics'
         ));
    RAISE NOTICE '🔍 Added graph analytics columns to existing tables';
    RAISE NOTICE '⚡ Created indexes and triggers for graph operations';
    RAISE NOTICE '🔒 Applied Row Level Security for multi-tenant isolation';
    RAISE NOTICE '📈 Created views for graph analytics and monitoring';
    RAISE NOTICE '🔧 Added utility functions for graph operations';
    RAISE NOTICE '🚀 Ready for backend-first knowledge graph processing';
END $$;