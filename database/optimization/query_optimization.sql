-- Knowledge Graph Analytics Dashboard Query Optimization
-- Connection pooling configuration, query hints, and performance tuning

-- ============================================================================
-- CONNECTION POOLING CONFIGURATION
-- ============================================================================

-- Configuration for PgBouncer or similar connection pooler
-- These settings should be applied in the connection pooler configuration

-- Recommended PgBouncer configuration settings:
/*
[databases]
analytics_db = host=localhost port=5432 dbname=your_db_name

[pgbouncer]
listen_port = 6432
listen_addr = 127.0.0.1
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
logfile = /var/log/pgbouncer/pgbouncer.log
pidfile = /var/run/pgbouncer/pgbouncer.pid
admin_users = postgres
stats_users = stats, postgres

# Pooler mode options
pool_mode = transaction

# Connection pool settings
max_client_conn = 200
default_pool_size = 25
min_pool_size = 5
reserve_pool_size = 5
reserve_pool_timeout = 5
max_db_connections = 50
max_user_connections = 50

# Timeout settings
server_reset_query = DISCARD ALL
server_check_delay = 30
server_check_query = select 1
server_lifetime = 3600
server_idle_timeout = 600

# Analytics-specific settings
ignore_startup_parameters = extra_float_digits
track_extra_parameters = search_path,application_name
*/

-- Function to configure session settings for optimal analytics performance
CREATE OR REPLACE FUNCTION configure_analytics_session(
    p_session_type TEXT DEFAULT 'analytics',
    p_work_mem_mb INTEGER DEFAULT 256
) RETURNS VOID AS $$
BEGIN
    -- Configure memory settings based on session type
    CASE p_session_type
        WHEN 'analytics_heavy' THEN
            -- Heavy analytics operations (large aggregations, graph computations)
            EXECUTE 'SET work_mem = ''' || p_work_mem_mb || 'MB''';
            EXECUTE 'SET maintenance_work_mem = ''' || (p_work_mem_mb * 4) || 'MB''';
            EXECUTE 'SET shared_preload_libraries = ''pg_stat_statements, auto_explain''';
            EXECUTE 'SET temp_file_limit = ''8GB''';
            EXECUTE 'SET max_parallel_workers_per_gather = 4';
            EXECUTE 'SET max_parallel_workers = 8';
            EXECUTE 'SET parallel_tuple_cost = 0.1';
            EXECUTE 'SET parallel_setup_cost = 1000.0';

        WHEN 'analytics_light' THEN
            -- Light analytics operations (dashboard queries, real-time data)
            EXECUTE 'SET work_mem = ''64MB''';
            EXECUTE 'SET maintenance_work_mem = ''256MB''';
            EXECUTE 'SET max_parallel_workers_per_gather = 2';
            EXECUTE 'SET parallel_tuple_cost = 0.2';
            EXECUTE 'SET parallel_setup_cost = 2000.0';

        WHEN 'real_time' THEN
            -- Real-time dashboard queries (fast response required)
            EXECUTE 'SET work_mem = ''32MB''';
            EXECUTE 'SET max_parallel_workers_per_gather = 1';
            EXECUTE 'SET enable_seqscan = off';
            EXECUTE 'SET enable_bitmapscan = on';
            EXECUTE 'SET random_page_cost = 1.1';
            EXECUTE 'SET effective_cache_size = ''8GB''';

        WHEN 'export' THEN
            -- Data export operations (large result sets)
            EXECUTE 'SET work_mem = ''128MB''';
            EXECUTE 'SET maintenance_work_mem = ''512MB''';
            EXECUTE 'SET temp_file_limit = ''16GB''';
            EXECUTE 'SET max_parallel_workers_per_gather = 8';
            EXECUTE 'SET statement_timeout = ''1800000'''; -- 30 minutes

        ELSE
            -- Default analytics settings
            EXECUTE 'SET work_mem = ''' || p_work_mem_mb || 'MB''';
            EXECUTE 'SET maintenance_work_mem = ''' || (p_work_mem_mb * 2) || 'MB''';
            EXECUTE 'SET max_parallel_workers_per_gather = 2';
            EXECUTE 'SET temp_file_limit = ''4GB''';
    END CASE;

    -- Common optimizations for all analytics sessions
    EXECUTE 'SET statement_timeout = ''300000'''; -- 5 minutes default
    EXECUTE 'SET lock_timeout = ''60000'''; -- 1 minute lock timeout
    EXECUTE 'SET idle_in_transaction_session_timeout = ''300000'''; -- 5 minutes
    EXECUTE 'SET jit = off'; -- Disable JIT for analytics (usually faster)
    EXECUTE 'SET timezone = ''UTC''';
    EXECUTE 'SET extra_float_digits = 3';
    EXECUTE 'SET application_name = ''analytics_session''';

    -- Log session configuration
    INSERT INTO analytics_session_log (
        session_type,
        work_mem_mb,
        configuration_details,
        created_at
    ) VALUES (
        p_session_type,
        p_work_mem_mb,
        jsonb_build_object(
            'work_mem', p_work_mem_mb || 'MB',
            'maintenance_work_mem', CASE p_session_type
                WHEN 'analytics_heavy' THEN (p_work_mem_mb * 4) || 'MB'
                WHEN 'analytics_light' THEN '256MB'
                WHEN 'real_time' THEN 'N/A'
                WHEN 'export' THEN '512MB'
                ELSE (p_work_mem_mb * 2) || 'MB'
            END,
            'max_parallel_workers', CASE p_session_type
                WHEN 'analytics_heavy' THEN 8
                WHEN 'analytics_light' THEN 4
                WHEN 'real_time' THEN 2
                WHEN 'export' THEN 8
                ELSE 4
            END,
            'configured_at', NOW()
        ),
        NOW()
    );
END;
$$ LANGUAGE plpgsql;

-- Session log table
CREATE TABLE IF NOT EXISTS analytics_session_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_type VARCHAR(50) NOT NULL,
    work_mem_mb INTEGER,
    configuration_details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_analytics_session_log_type_time
    ON analytics_session_log (session_type, created_at DESC);

-- ============================================================================
-- QUERY OPTIMIZATION HINTS AND TEMPLATES
-- ============================================================================

-- Optimized query template for time-series analytics
CREATE OR REPLACE FUNCTION get_analytics_time_series_optimized(
    p_organization_id UUID,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ,
    p_bucket_type VARCHAR(20) DEFAULT 'day',
    p_analytics_type TEXT DEFAULT 'entity'
) RETURNS TABLE(
    time_bucket TIMESTAMPTZ,
    bucket_type VARCHAR(20),
    total_count BIGINT,
    new_count BIGINT,
    growth_rate DECIMAL(10,6),
    quality_score DECIMAL(5,4)
) AS $$
BEGIN
    -- Configure session for optimal performance
    PERFORM configure_analytics_session('analytics_light', 128);

    -- Use optimized query based on analytics type
    CASE p_analytics_type
        WHEN 'entity' THEN
            RETURN QUERY
            SELECT
                eao.time_bucket,
                eao.bucket_type,
                eao.total_entities as total_count,
                eao.new_entities as new_count,
                eao.entity_growth_rate as growth_rate,
                eao.avg_confidence_score as quality_score
            FROM entity_analytics_optimized eao
            WHERE eao.organization_id = p_organization_id
              AND eao.time_bucket >= p_start_time
              AND eao.time_bucket < p_end_time
              AND eao.bucket_type = p_bucket_type
            ORDER BY eao.time_bucket DESC
            LIMIT 1000; -- Prevent runaway queries

        WHEN 'relationship' THEN
            RETURN QUERY
            SELECT
                rao.time_bucket,
                rao.bucket_type,
                rao.total_relationships as total_count,
                rao.new_relationships as new_count,
                rao.relationship_growth_rate as growth_rate,
                rao.avg_confidence_score as quality_score
            FROM relationship_analytics_optimized rao
            WHERE rao.organization_id = p_organization_id
              AND rao.time_bucket >= p_start_time
              AND rao.time_bucket < p_end_time
              AND rao.bucket_type = p_bucket_type
            ORDER BY rao.time_bucket DESC
            LIMIT 1000;

        WHEN 'document' THEN
            RETURN QUERY
            SELECT
                dao.time_bucket,
                dao.bucket_type,
                dao.total_documents as total_count,
                dao.new_documents as new_count,
                dao.storage_growth_rate as growth_rate,
                dao.avg_quality_score as quality_score
            FROM document_analytics_optimized dao
            WHERE dao.organization_id = p_organization_id
              AND dao.time_bucket >= p_start_time
              AND dao.time_bucket < p_end_time
              AND dao.bucket_type = p_bucket_type
            ORDER BY dao.time_bucket DESC
            LIMIT 1000;

        ELSE
            RAISE EXCEPTION 'Invalid analytics type: %', p_analytics_type;
    END CASE;
END;
$$ LANGUAGE plpgsql;

-- Optimized query template for top N analysis
CREATE OR REPLACE FUNCTION get_top_entities_optimized(
    p_organization_id UUID,
    p_limit INTEGER DEFAULT 100,
    p_metric TEXT DEFAULT 'centrality',
    p_entity_type TEXT DEFAULT NULL
) RETURNS TABLE(
    entity_id UUID,
    entity_name TEXT,
    entity_type TEXT,
    metric_value DECIMAL(15,6),
    confidence_score DECIMAL(5,4),
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    -- Configure session for optimal performance
    PERFORM configure_analytics_session('real_time', 64);

    CASE p_metric
        WHEN 'centrality' THEN
            RETURN QUERY
            SELECT
                entities.id as entity_id,
                entities.name as entity_name,
                entities.entity_type as entity_type,
                COALESCE(centrality_metrics.centrality_score, 0) as metric_value,
                entities.extraction_confidence as confidence_score,
                entities.created_at
            FROM entities
            LEFT JOIN LATERAL (
                SELECT
                    COUNT(*) as centrality_score
                FROM entity_relationships er
                WHERE er.source_entity_id = entities.id OR er.target_entity_id = entities.id
            ) centrality_metrics ON true
            WHERE entities.organization_id = p_organization_id
              AND (p_entity_type IS NULL OR entities.entity_type = p_entity_type)
              AND entities.is_deleted = FALSE
            ORDER BY centrality_metrics.centrality_score DESC NULLS LAST
            LIMIT p_limit;

        WHEN 'recent' THEN
            RETURN QUERY
            SELECT
                entities.id as entity_id,
                entities.name as entity_name,
                entities.entity_type as entity_type,
                EXTRACT(EPOCH FROM (NOW() - entities.created_at)) as metric_value,
                entities.extraction_confidence as confidence_score,
                entities.created_at
            FROM entities
            WHERE entities.organization_id = p_organization_id
              AND (p_entity_type IS NULL OR entities.entity_type = p_entity_type)
              AND entities.is_deleted = FALSE
            ORDER BY entities.created_at DESC
            LIMIT p_limit;

        WHEN 'confidence' THEN
            RETURN QUERY
            SELECT
                entities.id as entity_id,
                entities.name as entity_name,
                entities.entity_type as entity_type,
                entities.extraction_confidence as metric_value,
                entities.extraction_confidence as confidence_score,
                entities.created_at
            FROM entities
            WHERE entities.organization_id = p_organization_id
              AND (p_entity_type IS NULL OR entities.entity_type = p_entity_type)
              AND entities.is_deleted = FALSE
              AND entities.extraction_confidence IS NOT NULL
            ORDER BY entities.extraction_confidence DESC
            LIMIT p_limit;

        ELSE
            RAISE EXCEPTION 'Invalid metric: %', p_metric;
    END CASE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- QUERY PERFORMANCE MONITORING
-- ============================================================================

-- Enable query performance monitoring
CREATE OR REPLACE FUNCTION setup_query_monitoring() RETURNS VOID AS $$
BEGIN
    -- Ensure pg_stat_statements is enabled
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

    -- Configure pg_stat_statements for analytics monitoring
    ALTER SYSTEM SET pg_stat_statements.max = 10000;
    ALTER SYSTEM SET pg_stat_statements.track = 'all';
    ALTER SYSTEM SET pg_stat_statements.track_utility = 'off';
    ALTER SYSTEM SET pg_stat_statements.save = 'on';

    -- Enable auto_explain for slow queries
    CREATE EXTENSION IF NOT EXISTS auto_explain;
    ALTER SYSTEM SET auto_explain.log_min_duration = 5000; -- Log queries taking > 5 seconds
    ALTER SYSTEM SET auto_explain.log_analyze = 'on';
    ALTER SYSTEM SET auto_explain.log_buffers = 'on';
    ALTER SYSTEM SET auto_explain.log_wal = 'on';
    ALTER SYSTEM SET auto_explain.log_timing = 'on';
    ALTER SYSTEM SET auto_explain.log_triggers = 'on';
    ALTER SYSTEM SET auto_explain.log_verbose = 'on';
    ALTER SYSTEM SET auto_explain.log_format = 'json';
    ALTER SYSTEM SET auto_explain.log_nested_statements = 'on';

    -- Reload configuration
    SELECT pg_reload_conf();
END;
$$ LANGUAGE plpgsql;

-- Function to get slow analytics queries
CREATE OR REPLACE FUNCTION get_slow_analytics_queries(
    p_min_exec_time_ms INTEGER DEFAULT 1000,
    p_min_calls INTEGER DEFAULT 5
) RETURNS TABLE(
    query_text TEXT,
    calls BIGINT,
    total_exec_time_ms DECIMAL(15,2),
    avg_exec_time_ms DECIMAL(15,2),
    rows_returned BIGINT,
    shared_blks_hit BIGINT,
    shared_blks_read BIGINT,
    local_blks_hit BIGINT,
    local_blks_read BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        LEFT(ss.query, 200) as query_text, -- Truncate for readability
        ss.calls,
        ROUND(ss.total_exec_time::DECIMAL, 2) as total_exec_time_ms,
        ROUND(ss.mean_exec_time::DECIMAL, 2) as avg_exec_time_ms,
        ss.rows,
        ss.shared_blks_hit,
        ss.shared_blks_read,
        ss.local_blks_hit,
        ss.local_blks_read
    FROM pg_stat_statements ss
    WHERE ss.mean_exec_time > p_min_exec_time_ms
      AND ss.calls > p_min_calls
      AND (
        ss.query LIKE '%analytics%' OR
        ss.query LIKE '%entity_%' OR
        ss.query LIKE '%relationship_%' OR
        ss.query LIKE '%document_%' OR
        ss.query LIKE '%graph_%' OR
        ss.query LIKE '%dashboard%'
      )
    ORDER BY ss.mean_exec_time DESC
    LIMIT 50;
END;
$$ LANGUAGE plpgsql;

-- Function to analyze query patterns
CREATE OR REPLACE FUNCTION analyze_analytics_query_patterns() RETURNS TABLE(
    query_pattern TEXT,
    frequency BIGINT,
    avg_exec_time_ms DECIMAL(15,2),
    total_time_ms DECIMAL(15,2),
    optimization_suggestion TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH query_patterns AS (
        SELECT
            CASE
                WHEN query LIKE '%SELECT%FROM%entity_analytics%' THEN 'entity_analytics_select'
                WHEN query LIKE '%SELECT%FROM%relationship_analytics%' THEN 'relationship_analytics_select'
                WHEN query LIKE '%SELECT%FROM%document_analytics%' THEN 'document_analytics_select'
                WHEN query LIKE '%SELECT%FROM%user_interaction%' THEN 'user_interaction_select'
                WHEN query LIKE '%GROUP BY%time_bucket%' THEN 'time_series_aggregation'
                WHEN query LIKE '%JOIN%entity%' THEN 'entity_join_query'
                WHEN query LIKE '%jsonb_build_object%' THEN 'json_aggregation_query'
                WHEN query LIKE '%COUNT(*)%' THEN 'count_aggregation'
                WHEN query LIKE '%MATERIALIZED VIEW%' THEN 'materialized_view_query'
                WHEN query LIKE '%INSERT%INTO%analytics_%' THEN 'analytics_insert'
                WHEN query LIKE '%UPDATE%analytics_%' THEN 'analytics_update'
                ELSE 'other_analytics_query'
            END as query_pattern,
            calls,
            mean_exec_time,
            total_exec_time,
            rows
        FROM pg_stat_statements
        WHERE query ILIKE '%analytics%'
           OR query ILIKE '%entity_%'
           OR query ILIKE '%relationship_%'
           OR query ILIKE '%document_%'
           OR query ILIKE '%dashboard%'
    )
    SELECT
        qp.query_pattern,
        SUM(qp.calls) as frequency,
        AVG(qp.mean_exec_time) as avg_exec_time_ms,
        SUM(qp.total_exec_time) as total_time_ms,
        CASE
            WHEN qp.query_pattern = 'time_series_aggregation' AND AVG(qp.mean_exec_time) > 2000 THEN
                'Consider using partitioned tables and BRIN indexes for time-series data'
            WHEN qp.query_pattern = 'entity_join_query' AND AVG(qp.mean_exec_time) > 1000 THEN
                'Consider adding foreign key indexes and optimizing join conditions'
            WHEN qp.query_pattern = 'json_aggregation_query' AND AVG(qp.mean_exec_time) > 3000 THEN
                'Consider using JSONB GIN indexes and simplifying JSON operations'
            WHEN qp.query_pattern LIKE '%_analytics_select%' AND AVG(qp.mean_exec_time) > 5000 THEN
                'Consider materialized views for frequently accessed analytics data'
            WHEN qp.query_pattern = 'count_aggregation' AND SUM(qp.calls) > 10000 THEN
                'Consider using summary tables or materialized views for count aggregations'
            ELSE
                'Query performance is within acceptable ranges'
        END as optimization_suggestion
    FROM query_patterns qp
    GROUP BY qp.query_pattern
    HAVING SUM(qp.calls) > 10
    ORDER BY SUM(qp.total_exec_time) DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DYNAMIC INDEX MANAGEMENT
-- ============================================================================

-- Function to suggest missing indexes based on query patterns
CREATE OR REPLACE FUNCTION suggest_missing_indexes() RETURNS TABLE(
    table_name TEXT,
    column_names TEXT[],
    index_type TEXT,
    estimated_benefit INTEGER,
    suggestion_reason TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH missing_indexes AS (
        -- Identify queries that would benefit from specific indexes
        SELECT
            regexp_replace(
                regexp_replace(ss.query, '.*FROM\s+(\w+).*', '\1'),
                '.*WHERE\s+([\w\s,=<>]+).*', '\1'
            ) as potential_index_columns,
            ss.calls,
            ss.mean_exec_time,
            ss.rows
        FROM pg_stat_statements ss
        WHERE ss.query LIKE '%SELECT%'
          AND ss.query NOT LIKE '%pg_stat_statements%'
          AND ss.mean_exec_time > 1000
          AND ss.calls > 10
          AND (ss.query ILIKE '%analytics%' OR ss.query ILIKE '%entity_%')
    )
    SELECT
        mi.potential_index_columns as table_name,
        string_to_array(mi.potential_index_columns, ', ') as column_names,
        CASE
            WHEN mi.potential_index_columns LIKE '%time_bucket%' THEN 'BRIN'
            WHEN mi.potential_index_columns LIKE '%organization_id%' THEN 'B-tree'
            WHEN mi.potential_index_columns LIKE '%type%' THEN 'Hash'
            ELSE 'B-tree'
        END as index_type,
        (mi.calls * mi.mean_exec_time::INTEGER)::INTEGER as estimated_benefit,
        'High-traffic query pattern detected' as suggestion_reason
    FROM missing_indexes mi
    WHERE mi.potential_index_columns NOT LIKE '%regexp_replace%'
      AND mi.potential_index_columns != ''
      AND mi.potential_index_columns IS NOT NULL
    ORDER BY estimated_benefit DESC
    LIMIT 10;
END;
$$ LANGUAGE plpgsql;

-- Function to create recommended indexes automatically
CREATE OR REPLACE FUNCTION create_recommended_indexes(
    p_dry_run BOOLEAN DEFAULT TRUE
) RETURNS TABLE(
    index_name TEXT,
    table_name TEXT,
    status TEXT,
    creation_time_ms INTEGER
) AS $$
DECLARE
    index_rec RECORD;
    creation_start TIMESTAMPTZ;
    sql_statement TEXT;
    index_created BOOLEAN;
BEGIN
    FOR index_rec IN SELECT * FROM suggest_missing_indexes() LOOP
        creation_start := NOW();
        index_created := FALSE;

        -- Generate index name
        index_rec.index_name := 'idx_suggested_' ||
                              lower(regexp_replace(index_rec.table_name, '[^a-zA-Z0-9]', '_', 'g')) ||
                              '_' || md5(index_rec.column_names::TEXT);

        IF NOT p_dry_run THEN
            BEGIN
                -- Check if index already exists
                sql_statement := format('SELECT 1 FROM pg_indexes WHERE indexname = %L', index_rec.index_name);
                EXECUTE sql_statement;

                -- Create index if it doesn't exist
                sql_statement := format('CREATE INDEX CONCURRENTLY %I ON %I (%s)',
                                       index_rec.index_name,
                                       index_rec.table_name,
                                       array_to_string(index_rec.column_names, ', '));
                EXECUTE sql_statement;
                index_created := TRUE;

            EXCEPTION WHEN duplicate_table OR undefined_column THEN
                -- Skip if there's an error (table doesn't exist, column doesn't exist, etc.)
                CONTINUE;
            END;
        END IF;

        RETURN QUERY SELECT
            index_rec.index_name,
            index_rec.table_name,
            CASE WHEN index_created THEN 'created' WHEN p_dry_run THEN 'would_create' ELSE 'skipped' END as status,
            EXTRACT(EPOCH FROM (NOW() - creation_start)) * 1000 as creation_time_ms;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- CONNECTION AND RESOURCE MANAGEMENT
-- ============================================================================

-- Function to monitor connection pool health
CREATE OR REPLACE FUNCTION monitor_connection_health() RETURNS TABLE(
    metric_name TEXT,
    current_value BIGINT,
    max_value BIGINT,
    percentage_used DECIMAL(5,2),
    status TEXT
) AS $$
BEGIN
    -- Active connections
    RETURN QUERY SELECT
        'active_connections' as metric_name,
        COUNT(*) as current_value,
        200::BIGINT as max_value, -- Typical max connections
        ROUND((COUNT(*)::DECIMAL / 200) * 100, 2) as percentage_used,
        CASE
            WHEN COUNT(*) < 150 THEN 'healthy'
            WHEN COUNT(*) < 180 THEN 'warning'
            ELSE 'critical'
        END as status
    FROM pg_stat_activity
    WHERE state = 'active';

    -- Idle connections
    RETURN QUERY SELECT
        'idle_connections' as metric_name,
        COUNT(*) as current_value,
        200::BIGINT as max_value,
        ROUND((COUNT(*)::DECIMAL / 200) * 100, 2) as percentage_used,
        CASE
            WHEN COUNT(*) < 50 THEN 'healthy'
            WHEN COUNT(*) < 100 THEN 'warning'
            ELSE 'critical'
        END as status
    FROM pg_stat_activity
    WHERE state = 'idle';

    -- Analytics-specific connections
    RETURN QUERY SELECT
        'analytics_connections' as metric_name,
        COUNT(*) as current_value,
        50::BIGINT as max_value, -- Analytics connection pool
        ROUND((COUNT(*)::DECIMAL / 50) * 100, 2) as percentage_used,
        CASE
            WHEN COUNT(*) < 40 THEN 'healthy'
            WHEN COUNT(*) < 45 THEN 'warning'
            ELSE 'critical'
        END as status
    FROM pg_stat_activity
    WHERE application_name LIKE '%analytics%'
       OR query LIKE '%analytics_%';
END;
$$ LANGUAGE plpgsql;

-- Function to optimize connection settings based on current load
CREATE OR REPLACE FUNCTION optimize_connection_settings() RETURNS TABLE(
    parameter_name TEXT,
    current_value TEXT,
    recommended_value TEXT,
    reason TEXT
) AS $$
DECLARE
    active_connections INTEGER;
    analytics_connections INTEGER;
BEGIN
    -- Get current connection counts
    SELECT COUNT(*) INTO active_connections
    FROM pg_stat_activity
    WHERE state = 'active';

    SELECT COUNT(*) INTO analytics_connections
    FROM pg_stat_activity
    WHERE application_name LIKE '%analytics%';

    -- Recommend settings based on current load
    IF analytics_connections > 40 THEN
        RETURN QUERY SELECT
            'max_parallel_workers_per_gather' as parameter_name,
            current_setting('max_parallel_workers_per_gather') as current_value,
            '1' as recommended_value,
            'High analytics load - reduce parallelism to prevent connection starvation' as reason;
    ELSIF active_connections < 50 THEN
        RETURN QUERY SELECT
            'max_parallel_workers_per_gather' as parameter_name,
            current_setting('max_parallel_workers_per_gather') as current_value,
            '4' as recommended_value,
            'Low load - can increase parallelism for better performance' as reason;
    END IF;

    -- Work memory recommendations
    IF analytics_connections > 30 THEN
        RETURN QUERY SELECT
            'work_mem' as parameter_name,
            current_setting('work_mem') as current_value,
            '64MB' as recommended_value,
            'High analytics load - reduce work memory per connection' as reason;
    ELSIF analytics_connections < 10 THEN
        RETURN QUERY SELECT
            'work_mem' as parameter_name,
            current_setting('work_mem') as current_value,
            '256MB' as recommended_value,
            'Low analytics load - can increase work memory for better performance' as reason;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PERFORMANCE TESTING FUNCTIONS
-- ============================================================================

-- Function to benchmark analytics queries
CREATE OR REPLACE FUNCTION benchmark_analytics_queries(
    p_organization_id UUID DEFAULT NULL,
    p_iterations INTEGER DEFAULT 5
) RETURNS TABLE(
    query_name TEXT,
    avg_exec_time_ms DECIMAL(15,2),
    min_exec_time_ms DECIMAL(15,2),
    max_exec_time_ms DECIMAL(15,2),
    rows_returned BIGINT,
    status TEXT
) AS $$
DECLARE
    test_org_id UUID;
    start_time TIMESTAMPTZ;
    end_time TIMESTAMPTZ;
    exec_time_ms DECIMAL;
    query_results BIGINT;
    i INTEGER;
BEGIN
    -- Use provided org ID or get first active org
    test_org_id := COALESCE(
        p_organization_id,
        (SELECT id FROM organizations WHERE is_active = TRUE LIMIT 1)
    );

    IF test_org_id IS NULL THEN
        RAISE EXCEPTION 'No active organization found for benchmarking';
    END IF;

    -- Benchmark entity analytics query
    avg_exec_time_ms := 0;
    min_exec_time_ms := 999999;
    max_exec_time_ms := 0;
    query_results := 0;

    FOR i IN 1..p_iterations LOOP
        start_time := NOW();

        SELECT COUNT(*) INTO query_results
        FROM entity_analytics_optimized
        WHERE organization_id = test_org_id
          AND time_bucket >= NOW() - INTERVAL '7 days';

        end_time := NOW();
        exec_time_ms := EXTRACT(EPOCH FROM (end_time - start_time)) * 1000;

        avg_exec_time_ms := avg_exec_time_ms + exec_time_ms;
        min_exec_time_ms := LEAST(min_exec_time_ms, exec_time_ms);
        max_exec_time_ms := GREATEST(max_exec_time_ms, exec_time_ms);
    END LOOP;

    RETURN QUERY SELECT
        'entity_analytics_weekly' as query_name,
        avg_exec_time_ms / p_iterations as avg_exec_time_ms,
        min_exec_time_ms as min_exec_time_ms,
        max_exec_time_ms as max_exec_time_ms,
        query_results as rows_returned,
        CASE WHEN avg_exec_time_ms / p_iterations < 1000 THEN 'excellent'
             WHEN avg_exec_time_ms / p_iterations < 3000 THEN 'good'
             WHEN avg_exec_time_ms / p_iterations < 10000 THEN 'fair'
             ELSE 'poor' END as status;

    -- Similar benchmarks can be added for other query types...
END;
$$ LANGUAGE plpgsql;

-- Initialize the optimization system
SELECT setup_query_monitoring();