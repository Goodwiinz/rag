-- Performance optimization scripts for PostgreSQL database
-- These scripts optimize the database for the Multimodal Enterprise RAG system

-- 1. Memory and performance settings
-- Note: These should be set in postgresql.conf based on available system resources

-- Recommended PostgreSQL configuration settings:
-- shared_buffers = 256MB (25% of RAM on 1GB system, adjust accordingly)
-- effective_cache_size = 1GB (50-75% of total RAM)
-- work_mem = 4MB (per query operation)
-- maintenance_work_mem = 64MB (for maintenance operations)
-- checkpoint_completion_target = 0.9
-- wal_buffers = 16MB
-- default_statistics_target = 100
-- random_page_cost = 1.1 (for SSD storage)
-- effective_io_concurrency = 200 (for SSD)

-- 2. Index optimizations for document search

-- Documents table indexes
CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_documents_title_gin
ON documents USING gin(to_tsvector('english', title));

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_documents_content_gin
ON documents USING gin(to_tsvector('english', content));

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_documents_document_type
ON documents(document_type);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_documents_created_at
ON documents(created_at DESC);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_documents_tenant_id
ON documents(tenant_id);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_documents_file_size
ON documents(file_size);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_documents_processing_status
ON documents(processing_status);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_documents_tenant_type_status
ON documents(tenant_id, document_type, processing_status);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_documents_tenant_created
ON documents(tenant_id, created_at DESC);

-- 3. Search and vector-related indexes

-- Search queries table
CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_search_queries_session_id
ON search_queries(session_id);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_search_queries_created_at
ON search_queries(created_at DESC);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_search_queries_user_id
ON search_queries(user_id);

-- Vector embeddings table (if exists)
CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_vector_embeddings_document_id
ON vector_embeddings(document_id);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_vector_embeddings_embedding_type
ON vector_embeddings(embedding_type);

-- 4. Knowledge graph and entity indexes

-- Entities table
CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_entities_name_trgm
ON entities USING gin(name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_entities_type
ON entities(entity_type);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_entities_tenant_id
ON entities(tenant_id);

-- Entity relationships table
CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_entity_relationships_source_id
ON entity_relationships(source_entity_id);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_entity_relationships_target_id
ON entity_relationships(target_entity_id);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_entity_relationships_relation_type
ON entity_relationships(relation_type);

-- 5. Analytics and metrics tables

-- Quality metrics table
CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_quality_metrics_document_id
ON quality_metrics(document_id);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_quality_metrics_metric_type
ON quality_metrics(metric_type);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_quality_metrics_created_at
ON quality_metrics(created_at DESC);

-- User behavior table
CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_user_behavior_session_id
ON user_behavior(session_id);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_user_behavior_user_id
ON user_behavior(user_id);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_user_behavior_action_type
ON user_behavior(action_type);

CREATE INDEX IF NOT EXISTS CONCURRENTLY idx_user_behavior_created_at
ON user_behavior(created_at DESC);

-- 6. Partitioning for large tables (if needed)

-- Partition search queries by date for better performance
-- This is an example - implement based on actual data volume
/*
CREATE TABLE search_queries_y2024m01 PARTITION OF search_queries
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE search_queries_y2024m02 PARTITION OF search_queries
FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
*/

-- 7. Materialized views for complex aggregations

-- Document statistics materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_document_stats AS
SELECT
    tenant_id,
    document_type,
    processing_status,
    COUNT(*) as total_documents,
    SUM(file_size) as total_file_size,
    AVG(file_size) as avg_file_size,
    MIN(created_at) as earliest_document,
    MAX(created_at) as latest_document
FROM documents
GROUP BY tenant_id, document_type, processing_status;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_document_stats_unique
ON mv_document_stats(tenant_id, document_type, processing_status);

-- Search statistics materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_search_stats AS
SELECT
    DATE_TRUNC('day', created_at) as search_date,
    COUNT(*) as total_searches,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT session_id) as unique_sessions,
    AVG(result_count) as avg_results
FROM search_queries
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', created_at);

CREATE INDEX IF NOT EXISTS idx_mv_search_stats_date
ON mv_search_stats(search_date);

-- 8. Trigger functions for automatic updates

-- Function to refresh materialized views
CREATE OR REPLACE FUNCTION refresh_document_stats()
RETURNS trigger AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_document_stats;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger to refresh stats after document changes
-- Note: Use judiciously as this can impact performance
/*
CREATE TRIGGER trigger_refresh_document_stats
    AFTER INSERT OR UPDATE OR DELETE ON documents
    FOR EACH STATEMENT
    EXECUTE FUNCTION refresh_document_stats();
*/

-- 9. Performance monitoring queries

-- Query to find slow queries
SELECT
    query,
    calls,
    total_time,
    mean_time,
    rows,
    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Query to find missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public'
ORDER BY n_distinct DESC;

-- Query to monitor index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- 10. VACUUM and ANALYZE optimization

-- Set up autovacuum tuning
ALTER TABLE documents SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05,
    autovacuum_vacuum_cost_delay = '10ms'
);

ALTER TABLE search_queries SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02
);

ALTER TABLE quality_metrics SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);

-- 11. Connection pooling optimization

-- Recommended pgBouncer configuration for transaction pooling:
-- pool_mode = transaction
-- max_client_conn = 100
-- default_pool_size = 20
-- min_pool_size = 5
-- reserve_pool_size = 5
-- reserve_pool_timeout = 5
-- server_reset_query = DISCARD ALL

-- 12. Query optimization examples

-- Optimized document search query
EXPLAIN (ANALYZE, BUFFERS)
SELECT d.id, d.title, d.document_type, d.created_at
FROM documents d
WHERE d.tenant_id = $1
    AND d.processing_status = 'completed'
    AND (
        to_tsvector('english', d.title) @@ to_tsquery('english', $2)
        OR to_tsvector('english', d.content) @@ to_tsquery('english', $2)
    )
ORDER BY d.created_at DESC
LIMIT $3;

-- Optimized search analytics query
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as search_count,
    COUNT(DISTINCT user_id) as unique_users,
    AVG(result_count) as avg_results
FROM search_queries
WHERE created_at >= NOW() - INTERVAL '24 hours'
    AND tenant_id = $1
GROUP BY DATE_TRUNC('hour', created_at)
ORDER BY hour DESC;