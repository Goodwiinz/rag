-- Migration 007b: Optimized Knowledge Graph Analytics Dashboard Implementation
-- Enhanced performance with advanced indexing, stored procedures, and security features

BEGIN;

-- Enable required extensions for analytics and performance
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "intarray";
CREATE EXTENSION IF NOT EXISTS "pg_partman";

-- ============================================================================
-- OPTIMIZED ANALYTICS AGGREGATION TABLES (Core Performance Tables)
-- ============================================================================

-- Entity analytics aggregations with enhanced partitioning and indexing
CREATE TABLE entity_analytics_optimized (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Time bucket for aggregations with optimized data types
    time_bucket TIMESTAMPTZ NOT NULL,
    bucket_type VARCHAR(20) NOT NULL CHECK (bucket_type IN ('hour', 'day', 'week', 'month')),

    -- Entity count analytics with optimized storage
    total_entities INTEGER DEFAULT 0,
    new_entities INTEGER DEFAULT 0,
    entity_growth_rate DECIMAL(10,6) DEFAULT 0,

    -- Entity type breakdown using JSONB with GIN index
    entity_type_counts JSONB DEFAULT '{}',
    entity_type_percentages JSONB DEFAULT '{}',

    -- Quality analytics
    avg_confidence_score DECIMAL(5,4) DEFAULT 0,
    high_quality_entities INTEGER DEFAULT 0,
    low_quality_entities INTEGER DEFAULT 0,

    -- Processing analytics
    entities_processed INTEGER DEFAULT 0,
    processing_success_rate DECIMAL(5,4) DEFAULT 0,
    avg_processing_time_ms INTEGER DEFAULT 0,

    -- Document association
    entities_per_document DECIMAL(8,4) DEFAULT 0,
    documents_with_entities INTEGER DEFAULT 0,

    -- Modality breakdown
    entity_modality_counts JSONB DEFAULT '{}',

    -- Enhanced metadata for optimization
    computation_version VARCHAR(50) DEFAULT 'v1.0',
    data_freshness_at TIMESTAMPTZ DEFAULT NOW(),
    cache_key VARCHAR(255),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(organization_id, time_bucket, bucket_type)
) PARTITION BY RANGE (time_bucket);

-- Create optimized partition table structure
CREATE OR REPLACE FUNCTION create_entity_analytics_partitions()
RETURNS void AS $$
DECLARE
    start_date date;
    end_date date;
    partition_name text;
    months_to_create integer := 24; -- Create partitions for next 24 months
BEGIN
    FOR i IN 0..months_to_create LOOP
        start_date := date_trunc('month', CURRENT_DATE + (i || ' months')::interval);
        end_date := start_date + interval '1 month';
        partition_name := 'entity_analytics_y' || to_char(start_date, 'YYYY') || 'm' || lpad(extract(month from start_date)::text, 2, '0');

        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF entity_analytics_optimized FOR VALUES FROM (%L) TO (%L)',
                      partition_name, start_date, end_date);
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Create optimized indexes for entity analytics
CREATE INDEX CONCURRENTLY idx_entity_analytics_org_time_brin
    ON entity_analytics_optimized USING BRIN (organization_id, time_bucket);

CREATE INDEX CONCURRENTLY idx_entity_analytics_gin_entity_types
    ON entity_analytics_optimized USING GIN (entity_type_counts);

CREATE INDEX CONCURRENTLY idx_entity_analytics_gin_modalities
    ON entity_analytics_optimized USING GIN (entity_modality_counts);

CREATE INDEX CONCURRENTLY idx_entity_analytics_composite_lookup
    ON entity_analytics_optimized (organization_id, bucket_type, time_bucket DESC);

CREATE INDEX CONCURRENTLY idx_entity_analytics_growth_rate
    ON entity_analytics_optimized (entity_growth_rate DESC, time_bucket DESC)
    WHERE entity_growth_rate > 0;

CREATE INDEX CONCURRENTLY idx_entity_analytics_quality_filter
    ON entity_analytics_optimized (avg_confidence_score DESC, time_bucket DESC)
    WHERE avg_confidence_score > 0.5;

-- Relationship analytics aggregations with optimized structure
CREATE TABLE relationship_analytics_optimized (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    time_bucket TIMESTAMPTZ NOT NULL,
    bucket_type VARCHAR(20) NOT NULL CHECK (bucket_type IN ('hour', 'day', 'week', 'month')),

    -- Relationship count analytics
    total_relationships INTEGER DEFAULT 0,
    new_relationships INTEGER DEFAULT 0,
    relationship_growth_rate DECIMAL(10,6) DEFAULT 0,

    -- Relationship type breakdown with optimized JSONB
    relationship_type_counts JSONB DEFAULT '{}',
    relationship_strength_distribution JSONB DEFAULT '{}',

    -- Quality analytics
    avg_confidence_score DECIMAL(5,4) DEFAULT 0,
    high_confidence_relationships INTEGER DEFAULT 0,
    avg_relationship_strength DECIMAL(5,4) DEFAULT 0,

    -- Graph connectivity metrics
    avg_connections_per_entity DECIMAL(8,4) DEFAULT 0,
    isolated_entities INTEGER DEFAULT 0,
    hub_entities INTEGER DEFAULT 0,
    bridge_entities INTEGER DEFAULT 0,

    -- Bidirectional relationships
    bidirectional_relationships INTEGER DEFAULT 0,
    bidirectional_percentage DECIMAL(5,4) DEFAULT 0,

    -- Enhanced metadata
    computation_version VARCHAR(50) DEFAULT 'v1.0',
    data_freshness_at TIMESTAMPTZ DEFAULT NOW(),
    graph_snapshot_id VARCHAR(255),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(organization_id, time_bucket, bucket_type)
) PARTITION BY RANGE (time_bucket);

-- Optimized indexes for relationship analytics
CREATE INDEX CONCURRENTLY idx_relationship_analytics_org_time_brin
    ON relationship_analytics_optimized USING BRIN (organization_id, time_bucket);

CREATE INDEX CONCURRENTLY idx_relationship_analytics_gin_types
    ON relationship_analytics_optimized USING GIN (relationship_type_counts);

CREATE INDEX CONCURRENTLY idx_relationship_analytics_gin_strength
    ON relationship_analytics_optimized USING GIN (relationship_strength_distribution);

CREATE INDEX CONCURRENTLY idx_relationship_analytics_connectivity
    ON relationship_analytics_optimized (avg_connections_per_entity DESC, time_bucket DESC)
    WHERE avg_connections_per_entity > 1.0;

CREATE INDEX CONCURRENTLY idx_relationship_analytics_hub_filter
    ON relationship_analytics_optimized (hub_entities DESC, time_bucket DESC)
    WHERE hub_entities > 0;

-- Graph metrics analytics with caching and optimization
CREATE TABLE graph_metrics_analytics_optimized (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Computation metadata
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    computation_version VARCHAR(50) DEFAULT 'v1.0',
    graph_snapshot_id VARCHAR(255),
    computation_time_ms INTEGER,

    -- Centrality metrics (compressed JSONB for efficiency)
    top_entities_by_centrality JSONB DEFAULT '[]',
    top_entities_by_betweenness JSONB DEFAULT '[]',
    top_entities_by_closeness JSONB DEFAULT '[]',
    top_entities_by_pagerank JSONB DEFAULT '[]',

    -- Global graph metrics
    graph_density DECIMAL(8,6) DEFAULT 0,
    average_path_length DECIMAL(8,4),
    clustering_coefficient DECIMAL(8,6) DEFAULT 0,
    modularity_score DECIMAL(8,6),

    -- Community structure analysis
    number_of_communities INTEGER DEFAULT 0,
    average_community_size DECIMAL(8,4),
    largest_community_size INTEGER DEFAULT 0,
    community_distribution JSONB DEFAULT '{}',

    -- Component analysis
    number_of_components INTEGER DEFAULT 1,
    giant_component_size INTEGER DEFAULT 0,
    giant_component_percentage DECIMAL(5,4) DEFAULT 0,

    -- Entity type connectivity with enhanced JSONB
    entity_type_connectivity JSONB DEFAULT '{}',

    -- Temporal patterns
    temporal_evolution_metrics JSONB DEFAULT '{}',

    -- Performance optimization fields
    cache_hit_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
    computation_complexity VARCHAR(50) DEFAULT 'medium',
    estimated_refresh_cost_ms INTEGER DEFAULT 1000,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Optimized indexes for graph metrics
CREATE INDEX CONCURRENTLY idx_graph_metrics_org_computed
    ON graph_metrics_analytics_optimized (organization_id, computed_at DESC);

CREATE INDEX CONCURRENTLY idx_graph_metrics_density
    ON graph_metrics_analytics_optimized (graph_density DESC, computed_at DESC)
    WHERE graph_density > 0;

CREATE INDEX CONCURRENTLY idx_graph_metrics_snapshot
    ON graph_metrics_analytics_optimized (graph_snapshot_id, computed_at DESC);

CREATE INDEX CONCURRENTLY idx_graph_metrics_gin_centrality
    ON graph_metrics_analytics_optimized USING GIN (top_entities_by_centrality);

CREATE INDEX CONCURRENTLY idx_graph_metrics_gin_communities
    ON graph_metrics_analytics_optimized USING GIN (community_distribution);

-- Document analytics with performance optimizations
CREATE TABLE document_analytics_optimized (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    time_bucket TIMESTAMPTZ NOT NULL,
    bucket_type VARCHAR(20) NOT NULL CHECK (bucket_type IN ('hour', 'day', 'week', 'month')),

    -- Document processing metrics
    total_documents INTEGER DEFAULT 0,
    new_documents INTEGER DEFAULT 0,
    processed_documents INTEGER DEFAULT 0,
    processing_success_rate DECIMAL(5,4) DEFAULT 0,

    -- Document type breakdown
    document_type_counts JSONB DEFAULT '{}',
    modality_counts JSONB DEFAULT '{}',

    -- Quality metrics
    avg_quality_score DECIMAL(5,4) DEFAULT 0,
    high_quality_documents INTEGER DEFAULT 0,
    low_quality_documents INTEGER DEFAULT 0,

    -- Processing performance
    avg_processing_time_ms INTEGER DEFAULT 0,
    processing_bottlenecks JSONB DEFAULT '{}',

    -- Extraction analytics
    avg_entities_extracted DECIMAL(8,4) DEFAULT 0,
    avg_concepts_extracted DECIMAL(8,4) DEFAULT 0,
    extraction_success_rates JSONB DEFAULT '{}',

    -- Storage analytics
    total_storage_gb DECIMAL(10,2) DEFAULT 0,
    avg_document_size_mb DECIMAL(8,2) DEFAULT 0,
    storage_growth_rate DECIMAL(10,6) DEFAULT 0,

    -- Usage analytics
    total_views INTEGER DEFAULT 0,
    total_downloads INTEGER DEFAULT 0,
    avg_views_per_document DECIMAL(8,4) DEFAULT 0,

    -- Enhanced optimization fields
    processing_efficiency_score DECIMAL(5,4) DEFAULT 0,
    storage_utilization_rate DECIMAL(5,4) DEFAULT 0,
    data_freshness_at TIMESTAMPTZ DEFAULT NOW(),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(organization_id, time_bucket, bucket_type)
) PARTITION BY RANGE (time_bucket);

-- Optimized indexes for document analytics
CREATE INDEX CONCURRENTLY idx_document_analytics_org_time_brin
    ON document_analytics_optimized USING BRIN (organization_id, time_bucket);

CREATE INDEX CONCURRENTLY idx_document_analytics_gin_types
    ON document_analytics_optimized USING GIN (document_type_counts);

CREATE INDEX CONCURRENTLY idx_document_analytics_gin_modalities
    ON document_analytics_optimized USING GIN (modality_counts);

CREATE INDEX CONCURRENTLY idx_document_analytics_quality
    ON document_analytics_optimized (avg_quality_score DESC, time_bucket DESC)
    WHERE avg_quality_score > 0.5;

CREATE INDEX CONCURRENTLY idx_document_analytics_processing
    ON document_analytics_optimized (processing_success_rate DESC, time_bucket DESC)
    WHERE processing_success_rate > 0.8;

-- User interaction analytics with enhanced tracking
CREATE TABLE user_interaction_analytics_optimized (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    time_bucket TIMESTAMPTZ NOT NULL,
    bucket_type VARCHAR(20) NOT NULL CHECK (bucket_type IN ('hour', 'day', 'week', 'month')),

    -- User activity metrics
    active_users INTEGER DEFAULT 0,
    new_users INTEGER DEFAULT 0,
    total_sessions INTEGER DEFAULT 0,
    avg_session_duration_seconds INTEGER DEFAULT 0,
    user_retention_rate DECIMAL(5,4) DEFAULT 0,

    -- Search analytics with enhanced tracking
    total_searches INTEGER DEFAULT 0,
    unique_search_queries INTEGER DEFAULT 0,
    avg_search_time_ms INTEGER DEFAULT 0,
    search_success_rate DECIMAL(5,4) DEFAULT 0,
    zero_result_search_rate DECIMAL(5,4) DEFAULT 0,

    -- Query type distribution
    query_type_distribution JSONB DEFAULT '{}',
    query_complexity_distribution JSONB DEFAULT '{}',
    search_intent_distribution JSONB DEFAULT '{}',

    -- User satisfaction metrics
    avg_user_satisfaction_score DECIMAL(3,2) DEFAULT 0,
    feedback_submission_rate DECIMAL(5,4) DEFAULT 0,
    complaint_rate DECIMAL(5,4) DEFAULT 0,
    user_engagement_score DECIMAL(5,4) DEFAULT 0,

    -- Feature usage
    feature_usage JSONB DEFAULT '{}',
    advanced_feature_adoption_rate DECIMAL(5,4) DEFAULT 0,

    -- Performance from user perspective
    avg_response_time_ms INTEGER DEFAULT 0,
    error_rate DECIMAL(5,4) DEFAULT 0,
    timeout_rate DECIMAL(5,4) DEFAULT 0,

    -- User demographics and behavior
    user_role_distribution JSONB DEFAULT '{}',
    user_experience_level_distribution JSONB DEFAULT '{}',
    user_device_distribution JSONB DEFAULT '{}',

    -- Enhanced optimization fields
    session_quality_score DECIMAL(5,4) DEFAULT 0,
    search_effectiveness_score DECIMAL(5,4) DEFAULT 0,
    data_freshness_at TIMESTAMPTZ DEFAULT NOW(),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(organization_id, time_bucket, bucket_type)
) PARTITION BY RANGE (time_bucket);

-- Optimized indexes for user interaction analytics
CREATE INDEX CONCURRENTLY idx_user_interaction_analytics_org_time_brin
    ON user_interaction_analytics_optimized USING BRIN (organization_id, time_bucket);

CREATE INDEX CONCURRENTLY idx_user_interaction_analytics_gin_features
    ON user_interaction_analytics_optimized USING GIN (feature_usage);

CREATE INDEX CONCURRENTLY idx_user_interaction_analytics_gin_queries
    ON user_interaction_analytics_optimized USING GIN (query_type_distribution);

CREATE INDEX CONCURRENTLY idx_user_interaction_analytics_engagement
    ON user_interaction_analytics_optimized (user_engagement_score DESC, time_bucket DESC)
    WHERE user_engagement_score > 0.5;

CREATE INDEX CONCURRENTLY idx_user_interaction_analytics_activity
    ON user_interaction_analytics_optimized (active_users DESC, time_bucket DESC)
    WHERE active_users > 0;

-- Initialize partitions
SELECT create_entity_analytics_partitions();

COMMIT;