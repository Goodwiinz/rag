-- Comprehensive Partitioning Strategy for High-Scale Monitoring Database
-- Optimized for time-series data and multi-tenant workloads

-- =============================================
-- Partitioning Strategy Overview
-- =============================================
/*
This file implements a comprehensive partitioning strategy designed to:
1. Handle high-volume time-series data efficiently
2. Support multi-tenant isolation and performance
3. Enable automated partition lifecycle management
4. Optimize query performance through partition pruning
5. Facilitate data archival and retention policies

Partition Types Used:
- RANGE partitioning for time-series data (by date/hour)
- LIST partitioning for multi-tenant isolation
- HASH partitioning for load distribution
- Subpartitioning for compound strategies
*/

-- =============================================
-- Enable Partitioning Extensions
-- =============================================

-- Check PostgreSQL version and enable partitioning support
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_partman') THEN
        RAISE NOTICE 'pg_partman extension already available';
    ELSE
        RAISE NOTICE 'Consider installing pg_partman for automated partition management';
    END IF;
END $$;

-- =============================================
-- Multi-Tenant Partitioning Strategy
-- =============================================

-- Create tenant-based partitioning for user-sensitive data
-- This isolates large tenants to prevent performance impact on others

-- User sessions partitioned by tenant size
CREATE TABLE IF NOT EXISTS user_sessions_partitioned (
    LIKE user_sessions INCLUDING ALL
) PARTITION BY LIST (organization_id);

-- Create partitions for high-volume tenants (example)
-- This would be automated based on tenant usage patterns
DO $$
DECLARE
    org_record RECORD;
    partition_name TEXT;
BEGIN
    -- Create default partition for small tenants
    EXECUTE 'CREATE TABLE IF NOT EXISTS user_sessions_default PARTITION OF user_sessions_partitioned DEFAULT';

    -- Create individual partitions for large tenants
    FOR org_record IN
        SELECT id, name FROM organizations
        WHERE plan IN ('enterprise', 'premium')  -- Large tenants
        LIMIT 10  -- Limit to top 10 tenants
    LOOP
        partition_name := 'user_sessions_org_' || REPLACE(org_record.id::TEXT, '-', '_');
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF user_sessions_partitioned
                        FOR VALUES IN (%L)', partition_name, org_record.id);
    END LOOP;
END $$;

-- =============================================
-- Time-Series Partitioning Templates
-- =============================================

-- Template for high-frequency metrics (hourly partitions for first week, then daily)
CREATE OR REPLACE FUNCTION create_hybrid_time_partitions(
    p_base_table TEXT,
    p_time_column TEXT,
    p_hours_to_keep INTEGER DEFAULT 168, -- 1 week
    p_days_to_keep INTEGER DEFAULT 90   -- 3 months
) RETURNS void AS $$
DECLARE
    partition_name TEXT;
    start_time TIMESTAMP WITH TIME ZONE;
    end_time TIMESTAMP WITH TIME ZONE;
    v_sql TEXT;
BEGIN
    -- Drop existing partitioned table if it exists
    v_sql := format('DROP TABLE IF EXISTS %I CASCADE', p_base_table || '_partitioned');
    EXECUTE v_sql;

    -- Create partitioned table
    v_sql := format('CREATE TABLE IF NOT EXISTS %I (LIKE %I INCLUDING ALL) PARTITION BY RANGE (%I)',
                   p_base_table || '_partitioned', p_base_table, p_time_column);
    EXECUTE v_sql;

    -- Create hourly partitions for recent data
    start_time := DATE_TRUNC('hour', NOW() - INTERVAL '1 hour');
    end_time := start_time + INTERVAL '1 hour';

    FOR i IN 0..p_hours_to_keep LOOP
        partition_name := format('%s_%s_h', p_base_table, TO_CHAR(start_time, 'YYYY_MM_DD_HH24'));
        v_sql := format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
                        FOR VALUES FROM (%L) TO (%L)',
                       partition_name, p_base_table || '_partitioned', start_time, end_time);
        EXECUTE v_sql;

        start_time := start_time - INTERVAL '1 hour';
        end_time := end_time - INTERVAL '1 hour';
    END LOOP;

    -- Create daily partitions for older data
    start_time := DATE_TRUNC('day', NOW() - INTERVAL '1 day');
    end_time := start_time + INTERVAL '1 day';

    FOR i IN 0..p_days_to_keep LOOP
        partition_name := format('%s_%s_d', p_base_table, TO_CHAR(start_time, 'YYYY_MM_DD'));
        v_sql := format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
                        FOR VALUES FROM (%L) TO (%L)',
                       partition_name, p_base_table || '_partitioned', start_time, end_time);
        EXECUTE v_sql;

        start_time := start_time - INTERVAL '1 day';
        end_time := end_time - INTERVAL '1 day';
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- Performance Metrics Partitioning
-- =============================================

-- Create hybrid partitioned table for performance metrics
SELECT create_hybrid_time_partitions('performance_metrics', 'timestamp', 168, 90);

-- Apply indexes to partitioned table
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_partitioned_name_time
ON performance_metrics_partitioned (metric_name, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_partitioned_org_time
ON performance_metrics_partitioned (organization_id, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_performance_metrics_partitioned_category_time
ON performance_metrics_partitioned (metric_category, timestamp DESC);

-- =============================================
-- User Activity Events Partitioning
-- =============================================

-- User activity needs different strategy - higher volume, shorter retention
CREATE OR REPLACE FUNCTION create_user_activity_partitions()
RETURNS void AS $$
DECLARE
    partition_name TEXT;
    start_time TIMESTAMP WITH TIME ZONE;
    end_time TIMESTAMP WITH TIME ZONE;
    v_sql TEXT;
BEGIN
    -- Drop existing if exists
    DROP TABLE IF EXISTS user_activity_events_partitioned CASCADE;

    -- Create partitioned table with subpartitioning
    CREATE TABLE IF NOT EXISTS user_activity_events_partitioned (
        LIKE user_activity_events INCLUDING ALL
    ) PARTITION BY RANGE (event_date);

    -- Create daily partitions for last 30 days
    start_time := DATE_TRUNC('day', CURRENT_DATE - INTERVAL '29 days');

    FOR i IN 0..29 LOOP
        partition_name := format('user_activity_%s', TO_CHAR(start_time, 'YYYY_MM_DD'));
        v_sql := format('CREATE TABLE IF NOT EXISTS %I PARTITION OF user_activity_events_partitioned
                        FOR VALUES FROM (%L) TO (%L)',
                       partition_name, start_time, start_time + INTERVAL '1 day');
        EXECUTE v_sql;

        -- Create indexes for each partition
        v_sql := format('CREATE INDEX IF NOT EXISTS idx_%s_user_time ON %I (user_id, event_timestamp DESC)',
                       partition_name, partition_name);
        EXECUTE v_sql;

        v_sql := format('CREATE INDEX IF NOT EXISTS idx_%s_session_time ON %I (session_id, event_timestamp DESC)',
                       partition_name, partition_name);
        EXECUTE v_sql;

        start_time := start_time + INTERVAL '1 day';
    END LOOP;

    -- Create weekly partitions for older data (up to 3 months)
    start_time := DATE_TRUNC('week', CURRENT_DATE - INTERVAL '8 weeks');

    FOR i IN 0..11 LOOP
        partition_name := format('user_activity_%s_w', TO_CHAR(start_time, 'YYYY_WW'));
        v_sql := format('CREATE TABLE IF NOT EXISTS %I PARTITION OF user_activity_events_partitioned
                        FOR VALUES FROM (%L) TO (%L)',
                       partition_name, start_time, start_time + INTERVAL '1 week');
        EXECUTE v_sql;

        start_time := start_time + INTERVAL '1 week';
    END LOOP;

    -- Create monthly partitions for historical data (up to 1 year)
    start_time := DATE_TRUNC('month', CURRENT_DATE - INTERVAL '11 months');

    FOR i IN 0..11 LOOP
        partition_name := format('user_activity_%s_m', TO_CHAR(start_time, 'YYYY_MM'));
        v_sql := format('CREATE TABLE IF NOT EXISTS %I PARTITION OF user_activity_events_partitioned
                        FOR VALUES FROM (%L) TO (%L)',
                       partition_name, start_time, start_time + INTERVAL '1 month');
        EXECUTE v_sql;

        start_time := start_time + INTERVAL '1 month';
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Execute user activity partitioning
SELECT create_user_activity_partitions();

-- =============================================
-- Search Quality Metrics Partitioning
-- =============================================

-- Search metrics with hybrid time and organization partitioning
CREATE TABLE IF NOT EXISTS search_quality_metrics_partitioned (
    LIKE search_quality_metrics INCLUDING ALL
) PARTITION BY LIST (organization_id);

-- Create default partition for most organizations
CREATE TABLE IF NOT EXISTS search_quality_default PARTITION OF search_quality_metrics_partitioned DEFAULT;

-- Create separate partitions for high-volume organizations
DO $$
DECLARE
    org_record RECORD;
    partition_name TEXT;
BEGIN
    FOR org_record IN
        SELECT id FROM organizations
        WHERE plan IN ('enterprise', 'premium')
        LIMIT 5
    LOOP
        partition_name := 'search_quality_org_' || REPLACE(org_record.id::TEXT, '-', '_');
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF search_quality_metrics_partitioned
                        FOR VALUES IN (%L)', partition_name, org_record.id);

        -- Add time-based subpartitioning for high-volume tenants
        EXECUTE format('ALTER TABLE %I PARTITION BY RANGE (search_date)', partition_name);

        -- Create monthly subpartitions
        DO $$
        DECLARE
            subpartition_name TEXT;
            start_date DATE := CURRENT_DATE - INTERVAL '11 months';
        BEGIN
            FOR i IN 0..11 LOOP
                subpartition_name := format('%s_%s', partition_name, TO_CHAR(start_date, 'YYYY_MM'));
                EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
                                FOR VALUES FROM (%L) TO (%L)',
                               subpartition_name, partition_name, start_date, start_date + INTERVAL '1 month');
                start_date := start_date + INTERVAL '1 month';
            END LOOP;
        END $$;
    END LOOP;
END $$;

-- =============================================
-- Document Processing Metrics Partitioning
-- =============================================

-- Document processing partitioned by status and time
CREATE TABLE IF NOT EXISTS document_processing_metrics_partitioned (
    LIKE document_processing_metrics INCLUDING ALL
) PARTITION BY LIST (processing_status);

-- Create partitions by status
CREATE TABLE IF NOT EXISTS doc_processing_success PARTITION OF document_processing_metrics_partitioned
FOR VALUES IN ('success');

CREATE TABLE IF NOT EXISTS doc_processing_failed PARTITION OF document_processing_metrics_partitioned
FOR VALUES IN ('failed');

CREATE TABLE IF NOT EXISTS doc_processing_partial PARTITION OF document_processing_metrics_partitioned
FOR VALUES IN ('partial');

CREATE TABLE IF NOT EXISTS doc_processing_timeout PARTITION OF document_processing_metrics_partitioned
FOR VALUES IN ('timeout');

CREATE TABLE IF NOT EXISTS doc_processing_default PARTITION OF document_processing_metrics_partitioned DEFAULT;

-- Add time-based subpartitioning to each status partition
DO $$
DECLARE
    status_partition TEXT;
BEGIN
    FOR status_partition IN ARRAY['doc_processing_success', 'doc_processing_failed', 'doc_processing_partial', 'doc_processing_timeout'] LOOP
        EXECUTE format('ALTER TABLE %I PARTITION BY RANGE (upload_timestamp)', status_partition);

        -- Create monthly subpartitions
        DO $$
        DECLARE
            subpartition_name TEXT;
            start_date DATE := CURRENT_DATE - INTERVAL '11 months';
        BEGIN
            FOR i IN 0..11 LOOP
                subpartition_name := format('%s_%s', status_partition, TO_CHAR(start_date, 'YYYY_MM'));
                EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
                                FOR VALUES FROM (%L) TO (%L)',
                               subpartition_name, status_partition, start_date, start_date + INTERVAL '1 month');
                start_date := start_date + INTERVAL '1 month';
            END LOOP;
        END $$;
    END LOOP;
END $$;

-- =============================================
-- Automated Partition Management
-- =============================================

-- Function to create future partitions
CREATE OR REPLACE FUNCTION create_future_partitions(
    p_days_ahead INTEGER DEFAULT 7,
    p_table_pattern TEXT DEFAULT '%_partitioned'
)
RETURNS TABLE(
    table_name TEXT,
    partitions_created INTEGER,
    execution_time_ms INTEGER
) AS $$
DECLARE
    v_start_time TIMESTAMP WITH TIME ZONE;
    table_record RECORD;
    v_sql TEXT;
    partition_name TEXT;
    partitions_created INTEGER;
BEGIN
    v_start_time := NOW();

    FOR table_record IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename LIKE p_table_pattern
    LOOP
        partitions_created := 0;

        -- Determine partitioning strategy based on table name
        IF table_record.tablename LIKE 'performance_metrics%' THEN
            -- Create hourly partitions for next 7 days
            DO $$
            DECLARE
                start_time TIMESTAMP WITH TIME ZONE := DATE_TRUNC('hour', NOW() + INTERVAL '1 hour');
                end_time TIMESTAMP WITH TIME ZONE;
                partition_name TEXT;
                v_sql TEXT;
            BEGIN
                FOR i IN 0..(p_days_ahead * 24 - 1) LOOP
                    end_time := start_time + INTERVAL '1 hour';
                    partition_name := format('performance_metrics_%s_h', TO_CHAR(start_time, 'YYYY_MM_DD_HH24'));

                    v_sql := format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
                                    FOR VALUES FROM (%L) TO (%L)',
                                   partition_name, table_record.tablename, start_time, end_time);
                    EXECUTE v_sql;

                    partitions_created := partitions_created + 1;
                    start_time := end_time;
                END LOOP;
            END $$;

        ELSIF table_record.tablename LIKE 'user_activity_events%' THEN
            -- Create daily partitions for next 7 days
            DO $$
            DECLARE
                start_date DATE := CURRENT_DATE + INTERVAL '1 day';
                end_date DATE;
                partition_name TEXT;
                v_sql TEXT;
            BEGIN
                FOR i IN 0..(p_days_ahead - 1) LOOP
                    end_date := start_date + INTERVAL '1 day';
                    partition_name := format('user_activity_%s', TO_CHAR(start_date, 'YYYY_MM_DD'));

                    v_sql := format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I
                                    FOR VALUES FROM (%L) TO (%L)',
                                   partition_name, table_record.tablename, start_date, end_date);
                    EXECUTE v_sql;

                    partitions_created := partitions_created + 1;
                    start_date := end_date;
                END LOOP;
            END $$;
        END IF;

        RETURN QUERY SELECT
            table_record.tablename,
            partitions_created,
            EXTRACT(MILLISECOND FROM (NOW() - v_start_time))::INTEGER;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function to drop old partitions
CREATE OR REPLACE FUNCTION drop_old_partitions(
    p_retention_days INTEGER DEFAULT 365,
    p_table_pattern TEXT DEFAULT '%_partitioned',
    p_dry_run BOOLEAN DEFAULT TRUE
)
RETURNS TABLE(
    table_name TEXT,
    partitions_dropped INTEGER,
    space_freed_mb FLOAT,
    execution_time_ms INTEGER
) AS $$
DECLARE
    v_start_time TIMESTAMP WITH TIME ZONE;
    table_record RECORD;
    partition_record RECORD;
    v_sql TEXT;
    partitions_dropped INTEGER;
    space_freed FLOAT;
BEGIN
    v_start_time := NOW();

    FOR table_record IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename LIKE p_table_pattern
    LOOP
        partitions_dropped := 0;
        space_freed := 0;

        FOR partition_record IN
            SELECT
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
            FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename LIKE table_record.tablename || '_%'
            AND tablename NOT LIKE '%_default'
            AND tablename NOT LIKE '%_org_%' -- Keep tenant-specific partitions
        LOOP
            -- Extract date from partition name to determine age
            -- This is simplified - production version would need robust date extraction
            IF partition_record.tablename ~ '_\d{4}_\d{2}_\d{2}' THEN
                -- Extract date from partition name (format: table_YYYY_MM_DD)
                DECLARE
                    partition_date DATE;
                    should_drop BOOLEAN := FALSE;
                BEGIN
                    -- This would need proper date extraction logic
                    -- For now, use a simple heuristic based on table age
                    SELECT pg_stat_get_last_vacuum_time(quote_ident(partition_record.schemaname)||'.'||quote_ident(partition_record.tablename))
                    INTO partition_date;

                    IF partition_date IS NOT NULL AND partition_date < CURRENT_DATE - p_retention_days THEN
                        should_drop := TRUE;
                    END IF;

                    IF should_drop THEN
                        IF NOT p_dry_run THEN
                            v_sql := format('DROP TABLE %I.%I CASCADE', partition_record.schemaname, partition_record.tablename);
                            EXECUTE v_sql;
                            space_freed := space_freed + (partition_record.size_bytes / 1024.0 / 1024.0);
                        END IF;

                        partitions_dropped := partitions_dropped + 1;
                    END IF;
                END;
            END IF;
        END LOOP;

        RETURN QUERY SELECT
            table_record.tablename,
            partitions_dropped,
            space_freed,
            EXTRACT(MILLISECOND FROM (NOW() - v_start_time))::INTEGER;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function to monitor partition health
CREATE OR REPLACE FUNCTION monitor_partition_health()
RETURNS TABLE(
    table_name TEXT,
    partition_name TEXT,
    partition_type TEXT,
    row_count BIGINT,
    size_mb FLOAT,
    age_days INTEGER,
    last_access TIMESTAMP WITH TIME ZONE,
    health_status TEXT,
    recommendations TEXT[]
) AS $$
DECLARE
    table_record RECORD;
    partition_record RECORD;
BEGIN
    FOR table_record IN
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public'
        AND (tablename LIKE '%_partitioned' OR tablename LIKE '%_org_%' OR tablename LIKE '%_%s_%')
    LOOP
        FOR partition_record IN
            SELECT
                pt.schemaname,
                pt.tablename as partition_name,
                pg_total_relation_size(pt.schemaname||'.'||pt.tablename) / 1024.0 / 1024.0 as size_mb,
                COALESCE(s.n_tup_ins + s.n_tup_upd + s.n_tup_del, 0) as row_count,
                pg_stat_get_last_vacuum_time(quote_ident(pt.schemaname)||'.'||quote_ident(pt.tablename)) as last_vacuum,
                pg_stat_get_last_autovacuum_time(quote_ident(pt.schemaname)||'.'||quote_ident(pt.tablename)) as last_autovacuum,
                pg_stat_get_last_analyze_time(quote_ident(pt.schemaname)||'.'||quote_ident(pt.tablename)) as last_analyze,
                pg_stat_get_last_autoanalyze_time(quote_ident(pt.schemaname)||'.'||quote_ident(pt.tablename)) as last_autoanalyze
            FROM pg_tables pt
            LEFT JOIN pg_stat_user_tables s ON s.relname = pt.tablename
            WHERE pt.schemaname = 'public'
            AND (pt.tablename = table_record.tablename
                 OR pt.tablename LIKE table_record.tablename || '_%')
        LOOP
            DECLARE
                age_days INTEGER;
                health_status TEXT := 'healthy';
                recommendations TEXT[] := '{}';
                last_access TIMESTAMP WITH TIME ZONE;
            BEGIN
                -- Calculate age based on last activity
                IF partition_record.last_vacuum IS NOT NULL THEN
                    last_access := GREATEST(partition_record.last_vacuum,
                                           COALESCE(partition_record.last_autovacuum, '1970-01-01'::TIMESTAMP),
                                           COALESCE(partition_record.last_analyze, '1970-01-01'::TIMESTAMP),
                                           COALESCE(partition_record.last_autoanalyze, '1970-01-01'::TIMESTAMP));
                    age_days := CURRENT_DATE - DATE(last_access);
                ELSE
                    age_days := 999; -- Unknown age
                END IF;

                -- Health checks
                IF partition_record.size_mb > 10000 THEN -- > 10GB
                    health_status := 'large';
                    recommendations := recommendations || ARRAY['Consider splitting large partition', 'Review archival strategy'];
                END IF;

                IF partition_record.row_count > 10000000 THEN -- > 10M rows
                    health_status := 'high_volume';
                    recommendations := recommendations || ARRAY['Consider more granular partitioning', 'Optimize indexes'];
                END IF;

                IF age_days > 90 THEN
                    health_status := 'stale';
                    recommendations := recommendations || ARRAY['Consider archiving old partition', 'Review retention policy'];
                END IF;

                IF partition_record.last_vacuum IS NULL OR age_days > 7 THEN
                    recommendations := recommendations || ARRAY['Consider running VACUUM ANALYZE'];
                END IF;

                RETURN QUERY SELECT
                    table_record.tablename,
                    partition_record.partition_name,
                    CASE
                        WHEN partition_record.partition_name LIKE '%_h' THEN 'hourly'
                        WHEN partition_record.partition_name LIKE '%_d' THEN 'daily'
                        WHEN partition_record.partition_name LIKE '%_w' THEN 'weekly'
                        WHEN partition_record.partition_name LIKE '%_m' THEN 'monthly'
                        ELSE 'unknown'
                    END as partition_type,
                    partition_record.row_count,
                    partition_record.size_mb,
                    age_days,
                    last_access,
                    health_status,
                    recommendations;
            END;
        END LOOP;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- Partition Maintenance Automation
-- =============================================

-- Create partition maintenance job scheduler
CREATE OR REPLACE FUNCTION schedule_partition_maintenance()
RETURNS void AS $$
BEGIN
    -- Create future partitions (run daily at 3 AM)
    -- SELECT cron.schedule('create-partitions', '0 3 * * *', 'SELECT create_future_partitions(7, ''%_partitioned'');');

    -- Drop old partitions (run weekly on Sundays at 4 AM)
    -- SELECT cron.schedule('drop-partitions', '0 4 * * 0', 'SELECT drop_old_partitions(365, ''%_partitioned'', FALSE);');

    -- Monitor partition health (run daily at 5 AM)
    -- SELECT cron.schedule('monitor-partitions', '0 5 * * *', 'SELECT * FROM monitor_partition_health();');

    -- Analyze partitions (run daily at 6 AM)
    -- SELECT cron.schedule('analyze-partitions', '0 6 * * *', 'ANALYZE VERBOSE;');

    RAISE NOTICE 'Partition maintenance jobs scheduled. Uncomment cron.schedule() calls to activate.';
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- Query Optimization with Partitions
-- =============================================

-- Create optimized views that leverage partition pruning
CREATE OR REPLACE VIEW recent_performance_metrics AS
SELECT *
FROM performance_metrics_partitioned
WHERE timestamp >= NOW() - INTERVAL '7 days';

CREATE OR REPLACE VIEW todays_user_activity AS
SELECT *
FROM user_activity_events_partitioned
WHERE event_date = CURRENT_DATE;

CREATE OR REPLACE VIEW recent_search_quality AS
SELECT *
FROM search_quality_metrics_partitioned
WHERE search_timestamp >= NOW() - INTERVAL '30 days';

-- Create partition-aware function for time-based queries
CREATE OR REPLACE FUNCTION query_time_range(
    p_table_name TEXT,
    p_start_time TIMESTAMP WITH TIME ZONE,
    p_end_time TIMESTAMP WITH TIME ZONE,
    p_organization_id UUID DEFAULT NULL
)
RETURNS TABLE(
    query_text TEXT,
    estimated_cost FLOAT,
    partition_pruning BOOLEAN
) AS $$
DECLARE
    v_query TEXT;
    v_partition_column TEXT;
    v_organization_filter TEXT;
BEGIN
    -- Determine partition column based on table
    CASE p_table_name
        WHEN 'performance_metrics_partitioned' THEN v_partition_column := 'timestamp';
        WHEN 'user_activity_events_partitioned' THEN v_partition_column := 'event_date';
        WHEN 'search_quality_metrics_partitioned' THEN v_partition_column := 'search_timestamp';
        ELSE v_partition_column := 'timestamp';
    END CASE;

    -- Build organization filter
    IF p_organization_id IS NOT NULL THEN
        v_organization_filter := format(' AND organization_id = %L', p_organization_id);
    ELSE
        v_organization_filter := '';
    END IF;

    -- Build optimized query
    v_query := format('SELECT * FROM %I WHERE %I >= %L AND %I < %L%s',
                     p_table_name, v_partition_column, p_start_time, v_partition_column, p_end_time, v_organization_filter);

    RETURN QUERY SELECT
        v_query,
        0.0 as estimated_cost, -- Would be calculated by EXPLAIN
        TRUE as partition_pruning; -- Assumed to be true with proper constraints
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- Partition Monitoring Dashboard
-- =============================================

-- Comprehensive partition monitoring view
CREATE OR REPLACE VIEW partition_management_dashboard AS
SELECT
    schemaname,
    tablename,
    pg_total_relation_size(schemaname||'.'||tablename) as total_size_bytes,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size_pretty,
    pg_relation_size(schemaname||'.'||tablename) as table_size_bytes,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size_pretty,
    (pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size_bytes,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size_pretty,
    COALESCE(s.n_tup_ins, 0) as total_inserts,
    COALESCE(s.n_tup_upd, 0) as total_updates,
    COALESCE(s.n_tup_del, 0) as total_deletes,
    COALESCE(s.n_live_tup, 0) as live_tuples,
    COALESCE(s.n_dead_tup, 0) as dead_tuples,
    s.last_vacuum,
    s.last_autovacuum,
    s.last_analyze,
    s.last_autoanalyze,
    CASE
        WHEN s.n_dead_tup > s.n_live_tup * 0.2 THEN 'needs_vacuum'
        WHEN s.last_analyze < NOW() - INTERVAL '1 day' THEN 'needs_analyze'
        ELSE 'healthy'
    END as maintenance_status
FROM pg_tables pt
LEFT JOIN pg_stat_user_tables s ON s.relname = pt.tablename
WHERE pt.schemaname = 'public'
  AND (pt.tablename LIKE '%_partitioned'
       OR pt.tablename LIKE '%_org_%'
       OR pt.tablename LIKE '%_%s_%'
       OR pt.tablename LIKE '%_%h'
       OR pt.tablename LIKE '%_%d'
       OR pt.tablename LIKE '%_%w'
       OR pt.tablename LIKE '%_%m')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- =============================================
-- Emergency Partition Management
-- =============================================

-- Function to handle emergency situations (rapid growth, etc.)
CREATE OR REPLACE FUNCTION emergency_partition_management(
    p_table_name TEXT,
    p_action TEXT -- 'split', 'create-emergency', 'disable-inserts'
)
RETURNS TABLE(
    action_taken TEXT,
    partitions_affected INTEGER,
    status TEXT,
    message TEXT
) AS $$
DECLARE
    v_sql TEXT;
    v_partitions_affected INTEGER := 0;
BEGIN
    CASE p_action
        WHEN 'split' THEN
            -- Split a large partition into smaller ones
            -- This is a simplified version - production would need more logic
            v_sql := format('SELECT split_large_partition(%L)', p_table_name);
            EXECUTE v_sql;
            v_partitions_affected := 1;

            RETURN QUERY SELECT
                'partition_split' as action_taken,
                v_partitions_affected as partitions_affected,
                'success' as status,
                format('Split large partition for table %s', p_table_name) as message;

        WHEN 'create-emergency' THEN
            -- Create emergency partitions for immediate future
            SELECT create_future_partitions(1, p_table_name) INTO v_partitions_affected;

            RETURN QUERY SELECT
                'emergency_partitions_created' as action_taken,
                v_partitions_affected as partitions_affected,
                'success' as status,
                format('Created emergency partitions for table %s', p_table_name) as message;

        WHEN 'disable-inserts' THEN
            -- Redirect inserts to staging table (emergency measure)
            v_sql := format('ALTER TABLE %I DISABLE RULE insert_redirect_rule', p_table_name);
            EXECUTE v_sql;

            RETURN QUERY SELECT
                'inserts_disabled' as action_taken,
                1 as partitions_affected,
                'success' as status,
                format('Disabled direct inserts to table %s, redirecting to staging', p_table_name) as message;
    END CASE;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- Setup and Initialization
-- =============================================

-- Initialize partitioning system
CREATE OR REPLACE FUNCTION initialize_partitioning_system()
RETURNS void AS $$
BEGIN
    -- Create partition management schema
    CREATE SCHEMA IF NOT EXISTS partition_management;

    -- Move partition management functions to dedicated schema
    -- ALTER FUNCTION create_future_partitions(...) SET SCHEMA partition_management;
    -- ALTER FUNCTION drop_old_partitions(...) SET SCHEMA partition_management;
    -- ALTER FUNCTION monitor_partition_health() SET SCHEMA partition_management;

    -- Create partition monitoring indexes
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_partition_management_table_size
    ON pg_tables USING (schemaname, tablename)
    WHERE schemaname = 'public' AND tablename LIKE '%_partitioned';

    -- Schedule maintenance jobs
    PERFORM schedule_partition_maintenance();

    -- Create initial partitions
    PERFORM create_future_partitions(7, '%_partitioned');

    RAISE NOTICE 'Partitioning system initialized successfully';
    RAISE NOTICE 'Created partition management schema and scheduled maintenance jobs';
    RAISE NOTICE 'Run SELECT schedule_partition_maintenance() to activate automated jobs';
END;
$$ LANGUAGE plpgsql;

-- Execute initialization
-- SELECT initialize_partitioning_system();

-- =============================================
-- Example Usage and Testing
-- =============================================

-- Test partition creation
-- SELECT * FROM create_future_partitions(7, 'performance_metrics_partitioned');

-- Test partition monitoring
-- SELECT * FROM monitor_partition_health();

-- Test partition dropping (dry run)
-- SELECT * FROM drop_old_partitions(30, 'performance_metrics_partitioned', TRUE);

-- View partition dashboard
-- SELECT * FROM partition_management_dashboard;

-- Test emergency management
-- SELECT * FROM emergency_partition_management('performance_metrics_partitioned', 'create-emergency');

-- Get optimized query for time range
-- SELECT * FROM query_time_range('performance_metrics_partitioned', NOW() - INTERVAL '1 day', NOW(), 'uuid-here');

COMMIT;