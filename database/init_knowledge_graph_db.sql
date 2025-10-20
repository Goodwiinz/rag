-- Database Initialization Script for Knowledge Graph Architecture
-- This script initializes the complete database stack for the corrected architecture
-- Run this after starting the Docker services to set up all databases properly

-- Database: PostgreSQL (rag_graph)
-- Port: 5433
-- Credentials: rag_user / rag_password2024

\echo '🚀 Initializing Knowledge Graph Database Architecture...'

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Create core schema if not exists
CREATE SCHEMA IF NOT EXISTS graph;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS cache;

-- Set up timezone and encoding
SET timezone = 'UTC';
SET client_encoding = 'UTF8';

-- Create custom types for graph operations
DO $$
BEGIN
    -- Create enum types if they don't exist
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'computation_status') THEN
        CREATE TYPE computation_status AS ENUM ('pending', 'queued', 'running', 'completed', 'failed', 'cancelled');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'insight_severity') THEN
        CREATE TYPE insight_severity AS ENUM ('low', 'medium', 'high', 'critical');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'insight_category') THEN
        CREATE TYPE insight_category AS ENUM ('quality', 'connectivity', 'performance', 'growth', 'security');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'graph_algorithm_type') THEN
        CREATE TYPE graph_algorithm_type AS ENUM ('centrality', 'community_detection', 'pathfinding', 'clustering', 'similarity');
    END IF;
END $$;

-- Create optimized table spaces for better performance (optional)
-- CREATE TABLESPACE graph_fast LOCATION '/var/lib/postgresql/data/graph_fast';

-- Run the main migration
\i 005_correct_knowledge_graph_architecture.sql

-- Insert default configuration data
\echo '📊 Inserting default configuration data...'

-- Default graph algorithm configurations
INSERT INTO graph_computation_cache (
    organization_id,
    computation_type,
    computation_version,
    algorithm_name,
    input_parameters,
    result_data,
    expires_at,
    created_by_user_id
) VALUES
(
    (SELECT id FROM organizations WHERE name = 'Default Organization' LIMIT 1),
    'centrality',
    'v1.0',
    'pagerank',
    '{"damping_factor": 0.85, "max_iterations": 100, "tolerance": 0.0001}',
    '{"status": "template", "description": "PageRank centrality computation template"}',
    NOW() + INTERVAL '1 year',
    NULL
) ON CONFLICT DO NOTHING;

-- Default user preferences for graph visualization
INSERT INTO user_graph_preferences (
    user_id,
    organization_id,
    default_layout_algorithm,
    node_color_scheme,
    edge_color_scheme,
    show_labels,
    label_threshold,
    confidence_threshold,
    strength_threshold,
    preferred_centrality_metric,
    show_community_clusters,
    show_isolated_nodes,
    max_nodes_for_realtime,
    animation_enabled
) SELECT
    u.id,
    u.organization_id,
    'force',
    'type_based',
    'type_based',
    true,
    50,
    0.5,
    0.3,
    'degree_centrality',
    true,
    false,
    500,
    true
FROM users u
WHERE u.id = (SELECT id FROM users LIMIT 1)
ON CONFLICT (user_id, organization_id) DO NOTHING;

-- Create sample graph insights for demonstration
INSERT INTO graph_insights (
    organization_id,
    insight_type,
    severity,
    category,
    title,
    description,
    detailed_analysis,
    impact_score,
    confidence,
    urgency_score,
    recommended_actions,
    action_priority,
    generated_by,
    is_active
) SELECT
    o.id,
    'quality_issue',
    'medium',
    'quality',
    'Graph Database Ready',
    'Knowledge graph database has been successfully initialized',
    'The PostgreSQL database for knowledge graph analytics has been configured with all required tables, indexes, and constraints. The system is ready to handle graph operations.',
    0.8,
    1.0,
    0.5,
    '{"actions": ["Begin ingesting entities", "Configure graph algorithms", "Set up monitoring"]}',
    1,
    'system',
    true
FROM organizations o
WHERE o.name = 'Default Organization'
ON CONFLICT DO NOTHING;

-- Create performance monitoring setup
\echo '📈 Setting up performance monitoring...'

-- Create a function to log performance metrics
CREATE OR REPLACE FUNCTION log_graph_performance(
    p_operation_type VARCHAR(100),
    p_algorithm_name VARCHAR(100),
    p_entity_count INTEGER,
    p_relationship_count INTEGER,
    p_computation_time_ms INTEGER,
    p_memory_usage_mb INTEGER DEFAULT NULL,
    p_cache_hit_rate DECIMAL(5,4) DEFAULT NULL,
    p_user_id UUID DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    metric_id UUID;
    org_id UUID;
BEGIN
    -- Get organization from user or use default
    IF p_user_id IS NOT NULL THEN
        SELECT organization_id INTO org_id FROM users WHERE id = p_user_id;
    ELSE
        SELECT id INTO org_id FROM organizations WHERE name = 'Default Organization' LIMIT 1;
    END IF;

    INSERT INTO graph_performance_metrics (
        organization_id,
        user_id,
        operation_type,
        algorithm_name,
        entity_count,
        relationship_count,
        computation_time_ms,
        memory_usage_mb,
        cache_hit_rate,
        timestamp
    ) VALUES (
        org_id,
        p_user_id,
        p_operation_type,
        p_algorithm_name,
        p_entity_count,
        p_relationship_count,
        p_computation_time_ms,
        p_memory_usage_mb,
        p_cache_hit_rate,
        NOW()
    ) RETURNING id INTO metric_id;

    RETURN metric_id;
END;
$$ LANGUAGE plpgsql;

-- Create function for automatic graph statistics updates
CREATE OR REPLACE FUNCTION update_graph_statistics(
    p_organization_id UUID DEFAULT NULL
) RETURNS TABLE (
    total_entities BIGINT,
    total_relationships BIGINT,
    graph_density DECIMAL(15,12),
    snapshot_timestamp TIMESTAMPTZ,
    computation_time_ms INTEGER
) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    org_id UUID;
BEGIN
    start_time := clock_timestamp();

    -- Use provided org_id or get default
    IF p_organization_id IS NOT NULL THEN
        org_id := p_organization_id;
    ELSE
        SELECT id INTO org_id FROM organizations WHERE name = 'Default Organization' LIMIT 1;
    END IF;

    -- Create new analytics snapshot
    INSERT INTO graph_analytics_snapshots (
        organization_id,
        total_nodes,
        total_edges,
        average_confidence,
        centrality_computation_time_ms,
        snapshot_timestamp
    ) SELECT
        org_id,
        (SELECT COUNT(*) FROM entities WHERE organization_id = org_id AND is_deleted = false),
        (SELECT COUNT(*) FROM entity_relationships WHERE organization_id = org_id),
        (SELECT COALESCE(AVG(confidence), 0) FROM entities WHERE organization_id = org_id AND is_deleted = false),
        EXTRACT(MILLISECONDS FROM (clock_timestamp() - start_time))::INTEGER,
        NOW();

    end_time := clock_timestamp();

    -- Return updated statistics
    RETURN QUERY
    SELECT
        COALESCE(gas.total_nodes, 0),
        COALESCE(gas.total_edges, 0),
        COALESCE(gas.graph_density, 0),
        gas.snapshot_timestamp,
        EXTRACT(MILLISECONDS FROM (end_time - start_time))::INTEGER
    FROM graph_analytics_snapshots gas
    WHERE gas.organization_id = org_id
    ORDER BY gas.snapshot_timestamp DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Create trigger functions for automatic cache invalidation
CREATE OR REPLACE FUNCTION invalidate_computation_cache_trigger()
RETURNS TRIGGER AS $$
BEGIN
    -- Invalidate relevant computation caches when entities or relationships change
    PERFORM invalidate_graph_caches(NEW.organization_id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Set up Row Level Security helper functions
CREATE OR REPLACE FUNCTION set_graph_organization_id()
RETURNS TRIGGER AS $$
BEGIN
    -- Automatically set organization_id for graph tables if not provided
    IF TG_OP = 'INSERT' AND NEW.organization_id IS NULL THEN
        NEW.organization_id := current_setting('app.current_organization_id', true)::uuid;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create indexes for performance optimization
\echo '⚡ Creating performance indexes...'

-- Composite indexes for common query patterns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_entities_org_type_confidence
ON entities(organization_id, entity_type, confidence DESC)
WHERE is_deleted = false;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_relationships_org_type_strength
ON entity_relationships(organization_id, relationship_type, relationship_strength DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_graph_jobs_status_created
ON graph_computation_jobs(status, created_at DESC)
WHERE status IN ('pending', 'queued', 'running');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_entity_analytics_computed_expires
ON entity_analytics_cache(computed_at DESC, expires_at)
WHERE expires_at > NOW();

-- Partial indexes for better performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_entities_high_importance
ON entities(id, importance_score DESC)
WHERE importance_score > 0.7 AND is_deleted = false;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_relationships_high_strength
ON entity_relationships(id, relationship_strength DESC)
WHERE relationship_strength > 0.8;

-- Create materialized views for complex analytics (refresh manually or on schedule)
\echo '📊 Creating materialized views...'

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_entity_importance_summary AS
SELECT
    e.organization_id,
    e.entity_type,
    COUNT(*) as total_entities,
    COUNT(*) FILTER (WHERE e.confidence > 0.8) as high_confidence_entities,
    COUNT(*) FILTER (WHERE e.confidence < 0.5) as low_confidence_entities,
    AVG(e.confidence) as average_confidence,
    COALESCE(AVG(eac.pagerank_score), 0) as average_pagerank,
    COALESCE(AVG(eac.degree_centrality), 0) as average_degree_centrality,
    MAX(e.created_at) as latest_entity_created
FROM entities e
LEFT JOIN entity_analytics_cache eac ON e.id = eac.entity_id
WHERE e.is_deleted = false
GROUP BY e.organization_id, e.entity_type;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_entity_importance_summary_unique
ON mv_entity_importance_summary(organization_id, entity_type);

-- Create refresh function for materialized view
CREATE OR REPLACE FUNCTION refresh_entity_importance_summary()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_entity_importance_summary;
END;
$$ LANGUAGE plpgsql;

-- Configure database settings for graph workloads
\echo '🔧 Configuring database settings...'

-- Set work_mem higher for graph queries (temporarily)
ALTER SYSTEM SET work_mem = '64MB';
ALTER SYSTEM SET maintenance_work_mem = '256MB';
ALTER SYSTEM SET effective_cache_size = '2GB';
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET seq_page_cost = 1.0;

-- Enable better logging for monitoring
ALTER SYSTEM SET log_min_duration_statement = 1000; -- Log queries taking > 1s
ALTER SYSTEM SET log_checkpoints = on;
ALTER SYSTEM SET log_connections = on;
ALTER SYSTEM SET log_disconnections = on;
ALTER SYSTEM SET log_lock_waits = on;

-- Apply configuration changes
SELECT pg_reload_conf();

-- Create monitoring queries helper function
CREATE OR REPLACE FUNCTION get_database_health_stats()
RETURNS TABLE (
    metric_name TEXT,
    metric_value TEXT,
    status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        'Database Size'::TEXT,
        pg_size_pretty(pg_database_size(current_database()))::TEXT,
        CASE
            WHEN pg_database_size(current_database()) > 10000000000 THEN 'Large'
            WHEN pg_database_size(current_database()) > 1000000000 THEN 'Medium'
            ELSE 'Small'
        END::TEXT

    UNION ALL

    SELECT
        'Active Connections'::TEXT,
        COUNT(*)::TEXT,
        CASE
            WHEN COUNT(*) > 80 THEN 'High'
            WHEN COUNT(*) > 50 THEN 'Medium'
            ELSE 'Low'
        END::TEXT
    FROM pg_stat_activity
    WHERE state = 'active'

    UNION ALL

    SELECT
        'Cache Hit Ratio'::TEXT,
        ROUND((blks_hit::float / NULLIF(blks_hit + blks_read, 0)) * 100, 2)::TEXT || '%',
        CASE
            WHEN (blks_hit::float / NULLIF(blks_hit + blks_read, 0)) > 0.95 THEN 'Excellent'
            WHEN (blks_hit::float / NULLIF(blks_hit + blks_read, 0)) > 0.90 THEN 'Good'
            ELSE 'Poor'
        END::TEXT
    FROM pg_stat_database
    WHERE datname = current_database()

    UNION ALL

    SELECT
        'Graph Tables Count'::TEXT,
        COUNT(*)::TEXT,
        CASE
            WHEN COUNT(*) >= 7 THEN 'Complete'
            WHEN COUNT(*) >= 5 THEN 'Partial'
            ELSE 'Incomplete'
        END::TEXT
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name LIKE '%graph%'
    AND table_type = 'BASE TABLE';
END;
$$ LANGUAGE plpgsql;

-- Create automated maintenance jobs
\echo '🔧 Setting up automated maintenance...'

-- Create a function to clean up expired cache entries
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS TABLE (
    table_name TEXT,
    entries_removed INTEGER
) AS $$
DECLARE
    cleanup_count INTEGER;
BEGIN
    -- Clean up expired computation cache
    DELETE FROM graph_computation_cache
    WHERE expires_at < NOW();
    GET DIAGNOSTICS cleanup_count = ROW_COUNT;
    RETURN QUERY SELECT 'graph_computation_cache'::TEXT, cleanup_count::INTEGER;

    -- Clean up expired analytics cache
    DELETE FROM entity_analytics_cache
    WHERE expires_at < NOW();
    GET DIAGNOSTICS cleanup_count = ROW_COUNT;
    RETURN QUERY SELECT 'entity_analytics_cache'::TEXT, cleanup_count::INTEGER;

    -- Clean up old performance metrics (keep last 30 days)
    DELETE FROM graph_performance_metrics
    WHERE timestamp < NOW() - INTERVAL '30 days';
    GET DIAGNOSTICS cleanup_count = ROW_COUNT;
    RETURN QUERY SELECT 'graph_performance_metrics'::TEXT, cleanup_count::INTEGER;

    -- Clean up resolved insights older than 90 days
    DELETE FROM graph_insights
    WHERE resolved = true
    AND resolved_at < NOW() - INTERVAL '90 days';
    GET DIAGNOSTICS cleanup_count = ROW_COUNT;
    RETURN QUERY SELECT 'graph_insights'::TEXT, cleanup_count::INTEGER;
END;
$$ LANGUAGE plpgsql;

-- Grant necessary permissions to the application user
\echo '🔒 Setting up permissions...'

-- Grant usage on schemas
GRANT USAGE ON SCHEMA graph TO rag_user;
GRANT USAGE ON SCHEMA analytics TO rag_user;
GRANT USAGE ON SCHEMA cache TO rag_user;

-- Grant permissions on tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rag_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA graph TO rag_user;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO rag_user;
GRANT SELECT, UPDATE, DELETE ON ALL TABLES IN SCHEMA cache TO rag_user;

-- Grant permissions on sequences
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rag_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA graph TO rag_user;

-- Grant permissions on functions
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO rag_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA graph TO rag_user;

-- Set up default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rag_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO rag_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO rag_user;

-- Create initial health check
\echo '🏥 Running initial health check...'

-- Test database connectivity and basic operations
DO $$
DECLARE
    health_status TEXT;
    table_count INTEGER;
    index_count INTEGER;
BEGIN
    -- Count graph-related tables
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name LIKE '%graph%'
    AND table_type = 'BASE TABLE';

    -- Count indexes
    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE schemaname = 'public';

    -- Log initialization status
    RAISE NOTICE '✅ PostgreSQL Knowledge Graph database initialized successfully!';
    RAISE NOTICE '📊 Graph tables created: %', table_count;
    RAISE NOTICE '⚡ Indexes created: %', index_count;
    RAISE NOTICE '🔒 Row Level Security enabled';
    RAISE NOTICE '📈 Performance monitoring configured';
    RAISE NOTICE '🔧 Maintenance procedures ready';

    -- Insert initialization record
    INSERT INTO graph_performance_metrics (
        organization_id,
        operation_type,
        algorithm_name,
        entity_count,
        relationship_count,
        computation_time_ms,
        timestamp
    ) VALUES (
        (SELECT id FROM organizations WHERE name = 'Default Organization' LIMIT 1),
        'database_initialization',
        'system_setup',
        table_count,
        index_count,
        0,
        NOW()
    );
END $$;

-- Create final summary view
\echo '📋 Creating initialization summary...'

CREATE OR REPLACE VIEW initialization_summary AS
SELECT
    'PostgreSQL Knowledge Graph Database' as system_name,
    version() as postgresql_version,
    current_database() as database_name,
    current_user as current_user,
    NOW() as initialization_time,
    (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE') as total_tables,
    (SELECT COUNT(*) FROM information_schema.tables WHERE table_name LIKE '%graph%' AND table_type = 'BASE TABLE') as graph_tables,
    (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public') as total_indexes,
    (SELECT pg_size_pretty(pg_database_size(current_database()))) as database_size;

-- Display summary
SELECT * FROM initialization_summary;

\echo '🎉 Knowledge Graph Database Initialization Complete!'
\echo ''
\echo 'Database connection information:'
\echo '  Host: localhost'
\echo '  Port: 5433'
\echo '  Database: rag_graph'
\echo '  User: rag_user'
\echo '  Password: rag_password2024'
\echo ''
\echo 'Next steps:'
\echo '  1. Verify Neo4j initialization (http://localhost:7474)'
\echo '  2. Setup Qdrant collections (curl http://localhost:6333/collections)'
\echo '  3. Configure Redis caching (redis-cli -h localhost -p 6380)'
\echo '  4. Start graph services (./scripts/deploy-graph-services.sh deploy)'
\echo '  5. Run integration tests (./scripts/test-integration.sh)'
\echo ''