-- Comprehensive Indexing Strategy for Production Monitoring Database
-- Optimized for high-performance queries and time-series data

-- =============================================
-- Table Partitioning Strategy
-- =============================================

-- Enable PostgreSQL partitioning extension
CREATE EXTENSION IF NOT EXISTS partitioned;

-- Time-based partitioning for high-volume tables

-- 1. SLI Measurements (partitioned by month)
CREATE TABLE IF NOT EXISTS sli_measurements (
    LIKE sli_measurements INCLUDING ALL
) PARTITION BY RANGE (measurement_date);

-- Create monthly partitions for current and future months
DO $$
DECLARE
    start_date DATE := DATE_TRUNC('month', CURRENT_DATE);
    end_date DATE := start_date + INTERVAL '2 years';
    current_date DATE := start_date;
BEGIN
    WHILE current_date < end_date LOOP
        EXECUTE format('CREATE TABLE IF NOT EXISTS sli_measurements_%s PARTITION OF sli_measurements
                        FOR VALUES FROM (%L) TO (%L)',
                       TO_CHAR(current_date, 'YYYY_MM'),
                       current_date,
                       current_date + INTERVAL '1 month');
        current_date := current_date + INTERVAL '1 month';
    END LOOP;
END $$;

-- 2. Performance Metrics (partitioned by month)
CREATE TABLE IF NOT EXISTS performance_metrics_partitioned (
    LIKE performance_metrics INCLUDING ALL
) PARTITION BY RANGE (metric_date);

DO $$
DECLARE
    start_date DATE := DATE_TRUNC('month', CURRENT_DATE);
    end_date DATE := start_date + INTERVAL '2 years';
    current_date DATE := start_date;
BEGIN
    WHILE current_date < end_date LOOP
        EXECUTE format('CREATE TABLE IF NOT EXISTS performance_metrics_%s PARTITION OF performance_metrics_partitioned
                        FOR VALUES FROM (%L) TO (%L)',
                       TO_CHAR(current_date, 'YYYY_MM'),
                       current_date,
                       current_date + INTERVAL '1 month');
        current_date := current_date + INTERVAL '1 month';
    END LOOP;
END $$;

-- 3. User Activity Events (partitioned by week for better query performance)
CREATE TABLE IF NOT EXISTS user_activity_events_partitioned (
    LIKE user_activity_events INCLUDING ALL
) PARTITION BY RANGE (event_date);

DO $$
DECLARE
    start_date DATE := DATE_TRUNC('week', CURRENT_DATE);
    end_date DATE := start_date + INTERVAL '1 year';
    current_date DATE := start_date;
BEGIN
    WHILE current_date < end_date LOOP
        EXECUTE format('CREATE TABLE IF NOT EXISTS user_activity_events_%s PARTITION OF user_activity_events_partitioned
                        FOR VALUES FROM (%L) TO (%L)',
                       TO_CHAR(current_date, 'YYYY_WW'),
                       current_date,
                       current_date + INTERVAL '1 week');
        current_date := current_date + INTERVAL '1 week';
    END LOOP;
END $$;

-- 4. Search Quality Metrics (partitioned by month)
CREATE TABLE IF NOT EXISTS search_quality_metrics_partitioned (
    LIKE search_quality_metrics INCLUDING ALL
) PARTITION BY RANGE (search_date);

DO $$
DECLARE
    start_date DATE := DATE_TRUNC('month', CURRENT_DATE);
    end_date DATE := start_date + INTERVAL '2 years';
    current_date DATE := start_date;
BEGIN
    WHILE current_date < current_date + INTERVAL '2 years' LOOP
        EXECUTE format('CREATE TABLE IF NOT EXISTS search_quality_metrics_%s PARTITION OF search_quality_metrics_partitioned
                        FOR VALUES FROM (%L) TO (%L)',
                       TO_CHAR(current_date, 'YYYY_MM'),
                       current_date,
                       current_date + INTERVAL '1 month');
        current_date := current_date + INTERVAL '1 month';
    END LOOP;
END $$;

-- 5. Resource Utilization Metrics (partitioned by week)
CREATE TABLE IF NOT EXISTS resource_utilization_metrics_partitioned (
    LIKE resource_utilization_metrics INCLUDING ALL
) PARTITION BY RANGE (metric_date);

DO $$
DECLARE
    start_date DATE := DATE_TRUNC('week', CURRENT_DATE);
    end_date DATE := start_date + INTERVAL '1 year';
    current_date DATE := start_date;
BEGIN
    WHILE current_date < end_date LOOP
        EXECUTE format('CREATE TABLE IF NOT EXISTS resource_utilization_%s PARTITION OF resource_utilization_metrics_partitioned
                        FOR VALUES FROM (%L) TO (%L)',
                       TO_CHAR(current_date, 'YYYY_WW'),
                       current_date,
                       current_date + INTERVAL '1 week');
        current_date := current_date + INTERVAL '1 week';
    END LOOP;
END $$;

-- =============================================
-- Specialized Indexes for Query Performance
-- =============================================

-- Time-Series Query Optimization
-- Indexes for time-range queries with organization filtering

-- SLI Measurement optimized indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sli_measurements_time_series
ON sli_measurements (organization_id, measurement_time DESC, measurement_value)
WHERE measurement_time >= NOW() - INTERVAL '30 days';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sli_measurements_sli_time_composite
ON sli_measurements (sli_id, measurement_time DESC, meets_slo)
WHERE measurement_time >= NOW() - INTERVAL '7 days';

-- Performance metrics with partial indexes for recent data
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_recent_by_name
ON performance_metrics (metric_name, timestamp DESC, value)
WHERE timestamp >= NOW() - INTERVAL '24 hours';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_category_performance
ON performance_metrics (metric_category, component_name, timestamp DESC, p95)
WHERE timestamp >= NOW() - INTERVAL '7 days';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_error_analysis
ON performance_metrics (organization_id, timestamp DESC, error_count, request_count)
WHERE error_count > 0 AND timestamp >= NOW() - INTERVAL '24 hours';

-- User activity with session optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_session_timeline
ON user_activity_events (session_id, event_timestamp DESC, event_type)
WHERE event_timestamp >= NOW() - INTERVAL '7 days';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_user_engagement
ON user_activity_events (user_id, event_timestamp DESC, event_duration_ms, business_value)
WHERE event_timestamp >= NOW() - INTERVAL '30 days';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_conversion_funnel
ON user_activity_events (organization_id, event_timestamp DESC, conversion_step, business_value)
WHERE conversion_step IS NOT NULL AND event_timestamp >= NOW() - INTERVAL '30 days';

-- Search quality with relevance optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_quality_performance_analysis
ON search_quality_metrics (organization_id, search_timestamp DESC, total_response_time_ms, relevance_score)
WHERE search_timestamp >= NOW() - INTERVAL '7 days';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_quality_user_feedback
ON search_quality_metrics (user_id, search_timestamp DESC, user_rating, user_feedback)
WHERE user_rating IS NOT NULL AND search_timestamp >= NOW() - INTERVAL '30 days';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_quality_no_results
ON search_quality_metrics (organization_id, search_timestamp DESC, returned_results_count)
WHERE returned_results_count = 0 AND search_timestamp >= NOW() - INTERVAL '24 hours';

-- RAG quality with triad scoring optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rag_quality_triad_analysis
ON rag_quality_metrics (organization_id, query_timestamp DESC, rag_triad_score, faithfulness_score)
WHERE query_timestamp >= NOW() - INTERVAL '7 days';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rag_quality_hallucination_detection
ON rag_quality_metrics (organization_id, query_timestamp DESC, hallucination_detected, hallucination_severity)
WHERE hallucination_detected = TRUE AND query_timestamp >= NOW() - INTERVAL '30 days';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rag_quality_user_satisfaction
ON rag_quality_metrics (user_id, query_timestamp DESC, user_satisfaction_score, helpful_vote)
WHERE user_satisfaction_score IS NOT NULL AND query_timestamp >= NOW() - INTERVAL '30 days';

-- =============================================
-- JSONB and Full-Text Search Indexes
-- =============================================

-- JSONB GIN indexes for flexible querying
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_tags_gin
ON performance_metrics USING GIN (tags);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_properties_gin
ON user_activity_events USING GIN (event_properties);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_alerts_details_gin
ON system_alerts USING GIN (alert_details);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_service_health_dependencies_gin
ON service_health_status USING GIN (dependencies);

-- Partial GIN indexes for common JSONB queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_component_tags_gin
ON performance_metrics USING GIN (tags)
WHERE component_name IN ('api', 'database', 'search');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_search_events_gin
ON user_activity_events USING GIN (event_properties)
WHERE event_category = 'search';

-- Full-text search indexes for error analysis and documentation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_alerts_description_fts
ON system_alerts USING GIN (to_tsvector('english', alert_description));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_slo_breach_root_cause_fts
ON slo_breach_events USING GIN (to_tsvector('english', root_cause_details));

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_feedback_fts
ON user_activity_events USING GIN (to_tsvector('english', COALESCE(event_description, '') || ' ' || COALESCE(user_feedback, '')))
WHERE user_feedback IS NOT NULL;

-- =============================================
-- BRIN Indexes for Time-Series Data
-- =============================================

-- BRIN indexes for very large time-series tables (efficient for time-range queries)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_timestamp_brin
ON performance_metrics USING BRIN (timestamp);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sli_measurements_time_brin
ON sli_measurements USING BRIN (measurement_time);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_resource_utilization_timestamp_brin
ON resource_utilization_metrics USING BRIN (timestamp);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_database_performance_timestamp_brin
ON database_performance_metrics USING BRIN (timestamp);

-- =============================================
-- Composite Indexes for Specific Query Patterns
-- =============================================

-- SLI monitoring dashboard queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sli_dashboard_composite
ON sli_measurements (sli_id, measurement_date DESC, meets_slo, slo_budget_consumed);

-- Performance monitoring dashboard queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_dashboard_composite
ON performance_metrics (metric_category, organization_id, metric_date DESC, p95, error_count);

-- System health overview queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_service_health_overview
ON service_health_status (organization_id, health_status, check_timestamp DESC, alert_triggered);

-- Alert management queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_management_composite
ON system_alerts (organization_id, alert_status, alert_severity, triggered_at DESC);

-- Document processing analytics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_processing_analytics
ON document_processing_metrics (organization_id, processing_status, upload_timestamp DESC, total_processing_time_seconds);

-- Queue monitoring for operations
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_queue_operations_composite
ON queue_monitoring_metrics (queue_name, queue_depth, error_rate_percent, timestamp DESC);

-- User session analytics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_session_analytics
ON user_sessions (organization_id, session_start DESC, session_duration_seconds, session_status);

-- Feature adoption tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_feature_adoption_composite
ON feature_usage_metrics (feature_name, organization_id, usage_timestamp DESC, user_satisfaction_score);

-- =============================================
-- Functional Indexes for Computed Values
-- =============================================

-- Indexes for time-based computations
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_hourly_bucket
ON performance_metrics (DATE_TRUNC('hour', timestamp), metric_name, value);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_daily_active_users
ON user_activity_events (DATE_TRUNC('day', event_timestamp), user_id)
WHERE event_type IN ('session_start', 'page_view');

-- Indexes for performance ratio calculations
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_error_rate
ON performance_metrics (component_name, timestamp DESC)
WHERE request_count > 0;

-- Indexes for quality score ranges
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_search_quality_by_score_range
ON search_quality_metrics (organization_id, relevance_score, search_timestamp DESC)
WHERE relevance_score >= 0.7;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_rag_quality_by_triad_score
ON rag_quality_metrics (organization_id, rag_triad_score, query_timestamp DESC)
WHERE rag_triad_score >= 0.8;

-- =============================================
-- Covering Indexes for High-Frequency Queries
-- =============================================

-- Dashboard queries covering indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_dashboard_cover
ON performance_metrics (organization_id, metric_category, timestamp DESC)
INCLUDE (metric_name, value, p95, error_count, component_name);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sli_measurements_dashboard_cover
ON sli_measurements (sli_id, measurement_time DESC)
INCLUDE (measurement_value, meets_slo, slo_budget_consumed, sample_size);

-- API response optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_activity_api_response
ON user_activity_events (user_id, event_timestamp DESC)
INCLUDE (event_type, event_action, event_properties, response_time_ms);

-- Alert system optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_system_alerts_response_cover
ON system_alerts (alert_status, triggered_at DESC)
INCLUDE (alert_name, alert_severity, alert_description, organization_id);

-- =============================================
-- Statistics and Query Plan Optimization
-- =============================================

-- Extended statistics for better query planning
CREATE STATISTICS IF NOT EXISTS sli_measurements_stats (organization_id, measurement_time, meets_slo)
ON sli_measurements (organization_id, measurement_time, meets_slo);

CREATE STATISTICS IF NOT EXISTS performance_metrics_stats (metric_category, organization_id, timestamp)
ON performance_metrics (metric_category, organization_id, timestamp);

CREATE STATISTICS IF NOT EXISTS user_activity_stats (user_id, event_timestamp, event_type)
ON user_activity_events (user_id, event_timestamp, event_type);

-- Multi-column statistics for complex queries
CREATE STATISTICS IF NOT EXISTS search_quality_stats (organization_id, search_timestamp, relevance_score, user_rating)
ON search_quality_metrics (organization_id, search_timestamp, relevance_score, user_rating);

-- =============================================
-- Index Maintenance and Monitoring
-- =============================================

-- Create a function to automatically update table statistics
CREATE OR REPLACE FUNCTION update_monitoring_table_stats()
RETURNS void AS $$
DECLARE
    table_name text;
BEGIN
    -- Update statistics for high-traffic tables
    FOR table_name IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename LIKE '%metrics%'
        OR tablename LIKE '%measurements%'
        OR tablename LIKE '%events%'
    LOOP
        EXECUTE 'ANALYZE ' || table_name;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Create index usage monitoring view
CREATE OR REPLACE VIEW index_usage_monitoring AS
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid::regclass)) as index_size,
    CASE
        WHEN idx_scan = 0 THEN 'UNUSED'
        WHEN idx_scan < 100 THEN 'LOW_USAGE'
        WHEN idx_scan < 1000 THEN 'MEDIUM_USAGE'
        ELSE 'HIGH_USAGE'
    END as usage_category
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- Create bloat monitoring view for index maintenance
CREATE OR REPLACE VIEW index_bloat_monitoring AS
SELECT
    current_database(),
    nspname AS schema_name,
    relname AS table_name,
    indexname AS index_name,
    ROUND(
        (
            (psai.avg_leaf_density - 100) *
            (psai.avg_leaf_density - 100) /
            (psai.avg_leaf_density * psai.avg_leaf_density)
        )::NUMERIC, 2
    ) AS bloat_percentage,
    pg_size_pretty(
        (
            (
                (psai.avg_leaf_density - 100) *
                (psai.avg_leaf_density - 100) /
                (psai.avg_leaf_density * psai.avg_leaf_density)
            )::NUMERIC *
            pg_relation_size(indexrelid::regclass) / 100
        )::BIGINT
    ) AS bloat_size,
    pg_size_pretty(pg_relation_size(indexrelid::regclass)) AS index_size
FROM pg_stat_all_indexes psai
JOIN pg_class pc ON pc.oid = psai.indexrelid
JOIN pg_namespace pn ON pn.oid = pc.relnamespace
WHERE pn.nspname = 'public'
AND psai.avg_leaf_density < 100
ORDER BY bloat_percentage DESC;

-- =============================================
-- Automated Index Maintenance
-- =============================================

-- Function to identify and suggest unused indexes
CREATE OR REPLACE FUNCTION identify_unused_indexes()
RETURNS TABLE(
    schema_name text,
    table_name text,
    index_name text,
    index_size text,
    last_used timestamp,
    recommendation text
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        nspname as schema_name,
        relname as table_name,
        indexname as index_name,
        pg_size_pretty(pg_relation_size(indexrelid::regclass)) as index_size,
        pg_stat_get_last_vacuum_time(indexrelid::regclass) as last_used,
        CASE
            WHEN idx_scan = 0 THEN 'DROP - Never used'
            WHEN idx_scan < 10 AND pg_relation_size(indexrelid::regclass) > 100*1024*1024 THEN 'REVIEW - Low usage, large size'
            WHEN idx_scan < 100 AND pg_relation_size(indexrelid::regclass) > 500*1024*1024 THEN 'REVIEW - Very low usage, very large'
            ELSE 'KEEP - In use'
        END as recommendation
    FROM pg_stat_user_indexes
    JOIN pg_class ON pg_class.oid = indexrelid
    JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
    WHERE nspname = 'public'
    AND idx_scan < 100
    AND pg_relation_size(indexrelid::regclass) > 10*1024*1024  -- Larger than 10MB
    ORDER BY idx_scan ASC, pg_relation_size(indexrelid::regclass) DESC;
END;
$$ LANGUAGE plpgsql;

-- Create a scheduled job to update statistics (requires pg_cron extension)
-- SELECT cron.schedule('update-monitoring-stats', '0 */6 * * *', 'SELECT update_monitoring_table_stats();');

-- =============================================
-- Query Performance Hints and Examples
-- =============================================

-- Example: Efficient SLI dashboard query
-- This query will use the composite index idx_sli_dashboard_composite
/*
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    sli.sli_name,
    DATE_TRUNC('hour', sm.measurement_time) as hour_bucket,
    AVG(sm.measurement_value) as avg_value,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY sm.measurement_value) as p95_value,
    COUNT(*) as measurement_count,
    SUM(CASE WHEN sm.meets_slo THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as slo_compliance_rate
FROM sli_measurements sm
JOIN service_level_indicators sli ON sli.id = sm.sli_id
WHERE sm.organization_id = $1
    AND sm.measurement_time >= NOW() - INTERVAL '24 hours'
    AND sm.sli_id = $2
GROUP BY sli.sli_name, hour_bucket
ORDER BY hour_bucket DESC;
*/

-- Example: Performance trend analysis query
-- This query will use the time-series indexes
/*
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    metric_name,
    component_name,
    DATE_TRUNC('hour', timestamp) as hour_bucket,
    AVG(value) as avg_value,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY value) as p50,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) as p99,
    SUM(error_count)::FLOAT / NULLIF(SUM(request_count), 0) as error_rate
FROM performance_metrics
WHERE organization_id = $1
    AND metric_category = 'api'
    AND timestamp >= NOW() - INTERVAL '7 days'
GROUP BY metric_name, component_name, hour_bucket
ORDER BY hour_bucket DESC, avg_value DESC;
*/

-- Example: User engagement analysis query
-- This query will use the user activity indexes
/*
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    DATE_TRUNC('day', event_timestamp) as day_bucket,
    COUNT(DISTINCT user_id) as active_users,
    COUNT(DISTINCT session_id) as active_sessions,
    COUNT(*) as total_events,
    AVG(event_duration_ms) as avg_event_duration,
    SUM(CASE WHEN business_value > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as conversion_rate
FROM user_activity_events
WHERE organization_id = $1
    AND event_timestamp >= NOW() - INTERVAL '30 days'
GROUP BY day_bucket
ORDER BY day_bucket DESC;
*/

-- Example: Search quality analysis query
-- This query will use the search quality indexes
/*
EXPLAIN (ANALYZE, BUFFERS)
SELECT
    DATE_TRUNC('hour', search_timestamp) as hour_bucket,
    AVG(total_response_time_ms) as avg_response_time,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_response_time_ms) as p95_response_time,
    AVG(relevance_score) as avg_relevance,
    AVG(overall_quality_score) as avg_quality,
    COUNT(*) as total_searches,
    COUNT(CASE WHEN user_rating IS NOT NULL THEN 1 END) as rated_searches,
    AVG(user_rating) as avg_user_rating
FROM search_quality_metrics
WHERE organization_id = $1
    AND search_timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY hour_bucket
ORDER BY hour_bucket DESC;
*/