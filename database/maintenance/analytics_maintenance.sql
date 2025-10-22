-- Knowledge Graph Analytics Dashboard Maintenance Scripts
-- Comprehensive monitoring, maintenance, and optimization procedures

-- ============================================================================
-- AUTOMATED MAINTENANCE FUNCTIONS
-- ============================================================================

-- Comprehensive analytics maintenance function
CREATE OR REPLACE FUNCTION run_analytics_maintenance(
    p_maintenance_type TEXT DEFAULT 'full',
    p_organization_id UUID DEFAULT NULL,
    p_dry_run BOOLEAN DEFAULT FALSE
) RETURNS TABLE(
    task_name TEXT,
    status TEXT,
    records_processed INTEGER,
    duration_ms INTEGER,
    details TEXT
) AS $$
DECLARE
    maintenance_start TIMESTAMPTZ := NOW();
    org_filter TEXT;
BEGIN
    -- Build organization filter
    IF p_organization_id IS NOT NULL THEN
        org_filter := 'AND organization_id = ''' || p_organization_id::TEXT || '''';
    ELSE
        org_filter := '';
    END IF;

    -- Return results from maintenance tasks
    RETURN QUERY
    -- Task 1: Clean up expired cache entries
    SELECT
        'cache_cleanup' as task_name,
        'completed' as status,
        cache_cleanup.records_processed as records_processed,
        cache_cleanup.duration_ms as duration_ms,
        cache_cleanup.details as details
    FROM (SELECT * FROM cleanup_expired_cache(p_dry_run)) cache_cleanup

    UNION ALL

    -- Task 2: Update outdated analytics aggregations
    SELECT
        'analytics_aggregation_update' as task_name,
        'completed' as status,
        agg_update.records_processed as records_processed,
        agg_update.duration_ms as duration_ms,
        agg_update.details as details
    FROM (SELECT * FROM update_outdated_analytics(p_dry_run, p_organization_id)) agg_update

    UNION ALL

    -- Task 3: Optimize table statistics
    SELECT
        'statistics_optimization' as task_name,
        'completed' as status,
        stats_opt.records_processed as records_processed,
        stats_opt.duration_ms as duration_ms,
        stats_opt.details as details
    FROM (SELECT * FROM optimize_analytics_statistics(p_dry_run)) stats_opt

    UNION ALL

    -- Task 4: Partition maintenance
    SELECT
        'partition_maintenance' as task_name,
        'completed' as status,
        part_maint.records_processed as records_processed,
        part_maint.duration_ms as duration_ms,
        part_maint.details as details
    FROM (SELECT * FROM maintain_analytics_partitions(p_dry_run)) part_maint

    UNION ALL

    -- Task 5: Index maintenance
    SELECT
        'index_maintenance' as task_name,
        'completed' as status,
        index_maint.records_processed as records_processed,
        index_maint.duration_ms as duration_ms,
        index_maint.details as details
    FROM (SELECT * FROM maintain_analytics_indexes(p_dry_run)) index_maint

    UNION ALL

    -- Task 6: Data validation and consistency checks
    SELECT
        'data_validation' as task_name,
        'completed' as status,
        data_val.records_processed as records_processed,
        data_val.duration_ms as duration_ms,
        data_val.details as details
    FROM (SELECT * FROM validate_analytics_data(p_dry_run, p_organization_id)) data_val

    UNION ALL

    -- Task 7: Performance monitoring and alerting
    SELECT
        'performance_monitoring' as task_name,
        'completed' as status,
        perf_mon.records_processed as records_processed,
        perf_mon.duration_ms as duration_ms,
        perf_mon.details as details
    FROM (SELECT * FROM monitor_analytics_performance(p_dry_run)) perf_mon

    UNION ALL

    -- Summary task
    SELECT
        'maintenance_summary' as task_name,
        'completed' as status,
        0 as records_processed,
        EXTRACT(EPOCH FROM (NOW() - maintenance_start)) * 1000 as duration_ms,
        jsonb_build_object(
            'total_duration_ms', EXTRACT(EPOCH FROM (NOW() - maintenance_start)) * 1000,
            'maintenance_type', p_maintenance_type,
            'dry_run', p_dry_run,
            'organization_id', p_organization_id,
            'completed_at', NOW()
        )::TEXT as details;
END;
$$ LANGUAGE plpgsql;

-- Cache cleanup function
CREATE OR REPLACE FUNCTION cleanup_expired_cache(
    p_dry_run BOOLEAN DEFAULT FALSE
) RETURNS TABLE(
    records_processed INTEGER,
    duration_ms INTEGER,
    details TEXT
) AS $$
DECLARE
    cleanup_start TIMESTAMPTZ := NOW();
    deleted_count INTEGER := 0;
    total_size_freed BIGINT := 0;
BEGIN
    IF NOT p_dry_run THEN
        -- Delete expired cache entries
        DELETE FROM analytics_cache
        WHERE expires_at < NOW()
        RETURNING COUNT(*) INTO deleted_count;

        -- Calculate space freed (approximate)
        SELECT SUM(result_size_bytes) INTO total_size_freed
        FROM analytics_cache
        WHERE expires_at < NOW();
    ELSE
        -- Count what would be deleted
        SELECT COUNT(*) INTO deleted_count
        FROM analytics_cache
        WHERE expires_at < NOW();

        SELECT COALESCE(SUM(result_size_bytes), 0) INTO total_size_freed
        FROM analytics_cache
        WHERE expires_at < NOW();
    END IF;

    RETURN QUERY SELECT
        deleted_count as records_processed,
        EXTRACT(EPOCH FROM (NOW() - cleanup_start)) * 1000 as duration_ms,
        jsonb_build_object(
            'size_freed_mb', ROUND(total_size_freed / (1024.0^2), 2),
            'dry_run', p_dry_run,
            'cache_type', 'expired_entries'
        )::TEXT as details;
END;
$$ LANGUAGE plpgsql;

-- Update outdated analytics function
CREATE OR REPLACE FUNCTION update_outdated_analytics(
    p_dry_run BOOLEAN DEFAULT FALSE,
    p_organization_id UUID DEFAULT NULL
) RETURNS TABLE(
    records_processed INTEGER,
    duration_ms INTEGER,
    details TEXT
) AS $$
DECLARE
    update_start TIMESTAMPTZ := NOW();
    updated_buckets INTEGER := 0;
    org_filter TEXT;
BEGIN
    IF p_organization_id IS NOT NULL THEN
        org_filter := 'AND organization_id = ''' || p_organization_id::TEXT || '''';
    ELSE
        org_filter := '';
    END IF;

    IF NOT p_dry_run THEN
        -- Update entity analytics for missing recent data
        INSERT INTO entity_analytics_optimized (
            organization_id,
            time_bucket,
            bucket_type,
            total_entities,
            new_entities,
            entity_growth_rate,
            entity_type_counts,
            avg_confidence_score,
            data_freshness_at,
            updated_at
        )
        SELECT
            org.id as organization_id,
            time_bucket,
            'day' as bucket_type,
            COUNT(*) FILTER (WHERE e.created_at <= time_bucket + INTERVAL '1 day') as total_entities,
            COUNT(*) FILTER (WHERE e.created_at >= time_bucket AND e.created_at < time_bucket + INTERVAL '1 day') as new_entities,
            0 as entity_growth_rate,
            jsonb_build_object('total', COUNT(*)) as entity_type_counts,
            AVG(e.extraction_confidence) as avg_confidence_score,
            NOW() as data_freshness_at,
            NOW() as updated_at
        FROM organizations org
        CROSS JOIN (
            SELECT generate_series(
                CURRENT_DATE - INTERVAL '7 days',
                CURRENT_DATE - INTERVAL '1 day',
                INTERVAL '1 day'
            )::TIMESTAMPTZ as time_bucket
        ) time_series
        LEFT JOIN entities e ON e.organization_id = org.id
        WHERE org.is_active = TRUE
          AND NOT EXISTS (
              SELECT 1 FROM entity_analytics_optimized eao
              WHERE eao.organization_id = org.id
                AND eao.time_bucket = time_series.time_bucket
                AND eao.bucket_type = 'day'
          )
        GROUP BY org.id, time_bucket
        ON CONFLICT (organization_id, time_bucket, bucket_type) DO NOTHING;

        GET DIAGNOSTICS updated_buckets = ROW_COUNT;
    ELSE
        -- Count what would be updated
        SELECT COUNT(*) INTO updated_buckets
        FROM organizations org
        CROSS JOIN (
            SELECT generate_series(
                CURRENT_DATE - INTERVAL '7 days',
                CURRENT_DATE - INTERVAL '1 day',
                INTERVAL '1 day'
            )::TIMESTAMPTZ as time_bucket
        ) time_series
        WHERE org.is_active = TRUE
          AND NOT EXISTS (
              SELECT 1 FROM entity_analytics_optimized eao
              WHERE eao.organization_id = org.id
                AND eao.time_bucket = time_series.time_bucket
                AND eao.bucket_type = 'day'
          );
    END IF;

    RETURN QUERY SELECT
        updated_buckets as records_processed,
        EXTRACT(EPOCH FROM (NOW() - update_start)) * 1000 as duration_ms,
        jsonb_build_object(
            'updated_buckets', updated_buckets,
            'dry_run', p_dry_run,
            'analytics_type', 'entity_analytics'
        )::TEXT as details;
END;
$$ LANGUAGE plpgsql;

-- Statistics optimization function
CREATE OR REPLACE FUNCTION optimize_analytics_statistics(
    p_dry_run BOOLEAN DEFAULT FALSE
) RETURNS TABLE(
    records_processed INTEGER,
    duration_ms INTEGER,
    details TEXT
) AS $$
DECLARE
    stats_start TIMESTAMPTZ := NOW();
    tables_analyzed INTEGER := 0;
    table_record RECORD;
    sql_statement TEXT;
BEGIN
    -- List of analytics tables to analyze
    FOR table_record IN VALUES
        ('entity_analytics_optimized'),
        ('relationship_analytics_optimized'),
        ('graph_metrics_analytics_optimized'),
        ('document_analytics_optimized'),
        ('user_interaction_analytics_optimized'),
        ('analytics_cache'),
        ('analytics_alerts'),
        ('analytics_security_log')
    LOOP
        IF NOT p_dry_run THEN
            -- Analyze table with higher statistics target for better query planning
            sql_statement := format('ANALYZE %I', table_record.column1);
            EXECUTE sql_statement;
            tables_analyzed := tables_analyzed + 1;
        ELSE
            -- Check if table exists and would be analyzed
            BEGIN
                EXECUTE format('SELECT 1 FROM %I LIMIT 1', table_record.column1);
                tables_analyzed := tables_analyzed + 1;
            EXCEPTION WHEN undefined_table THEN
                -- Table doesn't exist, skip
                CONTINUE;
            END;
        END IF;
    END LOOP;

    RETURN QUERY SELECT
        tables_analyzed as records_processed,
        EXTRACT(EPOCH FROM (NOW() - stats_start)) * 1000 as duration_ms,
        jsonb_build_object(
            'tables_analyzed', tables_analyzed,
            'dry_run', p_dry_run,
            'operation', 'statistics_optimization'
        )::TEXT as details;
END;
$$ LANGUAGE plpgsql;

-- Partition maintenance function
CREATE OR REPLACE FUNCTION maintain_analytics_partitions(
    p_dry_run BOOLEAN DEFAULT FALSE
) RETURNS TABLE(
    records_processed INTEGER,
    duration_ms INTEGER,
    details TEXT
) AS $$
DECLARE
    part_start TIMESTAMPTZ := NOW();
    partitions_created INTEGER := 0;
    partitions_dropped INTEGER := 0;
    current_month DATE;
    future_months INTEGER := 6; -- Create partitions 6 months ahead
    retention_months INTEGER := 24; -- Keep partitions for 24 months
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
    sql_statement TEXT;
BEGIN
    -- Create future partitions
    FOR i IN 0..future_months LOOP
        current_month := DATE_TRUNC('month', CURRENT_DATE + (i || ' months')::INTERVAL);
        start_date := current_month;
        end_date := current_month + INTERVAL '1 month';

        -- Entity analytics partitions
        partition_name := 'entity_analytics_y' || to_char(current_month, 'YYYY') || 'm' || lpad(extract(month from current_month)::text, 2, '0');

        IF NOT p_dry_run THEN
            sql_statement := format('CREATE TABLE IF NOT EXISTS %I PARTITION OF entity_analytics_optimized FOR VALUES FROM (%L) TO (%L)',
                                 partition_name, start_date, end_date);
            EXECUTE sql_statement;
            partitions_created := partitions_created + 1;
        ELSE
            -- Check if partition would be created
            BEGIN
                EXECUTE format('SELECT 1 FROM %I LIMIT 1', partition_name);
            EXCEPTION WHEN undefined_table THEN
                partitions_created := partitions_created + 1;
            END;
        END IF;
    END LOOP;

    -- Drop old partitions (beyond retention period)
    FOR i IN retention_months..retention_months+12 LOOP -- Check up to 12 months beyond retention
        current_month := DATE_TRUNC('month', CURRENT_DATE - (i || ' months')::INTERVAL);

        -- Check for entity analytics partitions to drop
        partition_name := 'entity_analytics_y' || to_char(current_month, 'YYYY') || 'm' || lpad(extract(month from current_month)::text, 2, '0');

        IF NOT p_dry_run THEN
            sql_statement := format('DROP TABLE IF EXISTS %I CASCADE', partition_name);
            EXECUTE sql_statement;
            GET DIAGNOSTICS partitions_dropped = ROW_COUNT;
        ELSE
            -- Check if partition exists and would be dropped
            BEGIN
                EXECUTE format('SELECT 1 FROM %I LIMIT 1', partition_name);
                partitions_dropped := partitions_dropped + 1;
            EXCEPTION WHEN undefined_table THEN
                CONTINUE;
            END;
        END IF;
    END LOOP;

    RETURN QUERY SELECT
        (partitions_created + partitions_dropped) as records_processed,
        EXTRACT(EPOCH FROM (NOW() - part_start)) * 1000 as duration_ms,
        jsonb_build_object(
            'partitions_created', partitions_created,
            'partitions_dropped', partitions_dropped,
            'dry_run', p_dry_run,
            'retention_months', retention_months,
            'future_months', future_months
        )::TEXT as details;
END;
$$ LANGUAGE plpgsql;

-- Index maintenance function
CREATE OR REPLACE FUNCTION maintain_analytics_indexes(
    p_dry_run BOOLEAN DEFAULT FALSE
) RETURNS TABLE(
    records_processed INTEGER,
    duration_ms INTEGER,
    details TEXT
) AS $$
DECLARE
    index_start TIMESTAMPTZ := NOW();
    indexes_rebuilt INTEGER := 0;
    index_record RECORD;
    sql_statement TEXT;
    index_usage_ratio DECIMAL;
BEGIN
    -- Check for fragmented or unused indexes
    FOR index_record IN
    SELECT
        schemaname,
        tablename,
        indexname,
        idx_scan,
        idx_tup_read,
        idx_tup_fetch,
        pg_size_pretty(pg_relation_size(indexrelid)) as index_size
    FROM pg_stat_user_indexes
    WHERE schemaname = 'public'
      AND tablename LIKE '%analytics%'
      OR tablename LIKE '%entity_%'
      OR tablename LIKE '%relationship_%'
      OR tablename LIKE '%document_%'
      OR tablename LIKE '%user_%'
    ORDER BY idx_scan ASC
    LIMIT 10 -- Focus on least used indexes
    LOOP
        -- Calculate usage ratio (scans vs potential size)
        IF index_record.idx_scan > 0 THEN
            index_usage_ratio := index_record.idx_scan::DECIMAL / NULLIF(pg_relation_size(index_record.indexname::regclass), 0);
        ELSE
            index_usage_ratio := 0;
        END IF;

        -- Consider rebuilding if heavily used or large and rarely used
        IF NOT p_dry_run THEN
            IF index_record.idx_scan > 10000 OR (index_usage_ratio < 0.1 AND pg_relation_size(index_record.indexname::regclass) > 100*1024*1024) THEN
                sql_statement := format('REINDEX INDEX CONCURRENTLY %I', index_record.indexname);
                EXECUTE sql_statement;
                indexes_rebuilt := indexes_rebuilt + 1;
            END IF;
        ELSE
            -- Count what would be rebuilt
            IF index_record.idx_scan > 10000 OR (index_usage_ratio < 0.1 AND pg_relation_size(index_record.indexname::regclass) > 100*1024*1024) THEN
                indexes_rebuilt := indexes_rebuilt + 1;
            END IF;
        END IF;
    END LOOP;

    RETURN QUERY SELECT
        indexes_rebuilt as records_processed,
        EXTRACT(EPOCH FROM (NOW() - index_start)) * 1000 as duration_ms,
        jsonb_build_object(
            'indexes_rebuilt', indexes_rebuilt,
            'dry_run', p_dry_run,
            'operation', 'index_maintenance'
        )::TEXT as details;
END;
$$ LANGUAGE plpgsql;

-- Data validation function
CREATE OR REPLACE FUNCTION validate_analytics_data(
    p_dry_run BOOLEAN DEFAULT FALSE,
    p_organization_id UUID DEFAULT NULL
) RETURNS TABLE(
    records_processed INTEGER,
    duration_ms INTEGER,
    details TEXT
) AS $$
DECLARE
    validation_start TIMESTAMPTZ := NOW();
    validation_errors INTEGER := 0;
    error_details JSONB := '[]'::JSONB;
    org_filter TEXT;
BEGIN
    IF p_organization_id IS NOT NULL THEN
        org_filter := 'AND organization_id = ''' || p_organization_id::TEXT || '''';
    ELSE
        org_filter := '';
    END IF;

    -- Validation 1: Check for negative counts in analytics tables
    BEGIN
        IF NOT p_dry_run THEN
            -- Fix negative values
            UPDATE entity_analytics_optimized
            SET total_entities = 0, updated_at = NOW()
            WHERE total_entities < 0 || org_filter;

            UPDATE relationship_analytics_optimized
            SET total_relationships = 0, updated_at = NOW()
            WHERE total_relationships < 0 || org_filter;

            GET DIAGNOSTICS validation_errors = ROW_COUNT;
        ELSE
            -- Count negative values
            SELECT COUNT(*) INTO validation_errors
            FROM (
                SELECT 'entity_analytics' as table_name, COUNT(*) as error_count
                FROM entity_analytics_optimized
                WHERE total_entities < 0 || org_filter
                UNION ALL
                SELECT 'relationship_analytics' as table_name, COUNT(*) as error_count
                FROM relationship_analytics_optimized
                WHERE total_relationships < 0 || org_filter
            ) errors;
        END IF;

        error_details := jsonb_build_object(
            'negative_counts_fixed', validation_errors,
            'validation_type', 'data_integrity'
        );
    END;

    -- Validation 2: Check for orphaned records
    BEGIN
        DECLARE
            orphaned_count INTEGER;
        BEGIN
            IF NOT p_dry_run THEN
                -- Find and clean orphaned analytics records
                DELETE FROM entity_analytics_optimized eao
                WHERE NOT EXISTS (
                    SELECT 1 FROM organizations o
                    WHERE o.id = eao.organization_id AND o.is_active = TRUE
                ) || org_filter;

                GET DIAGNOSTICS orphaned_count = ROW_COUNT;
                validation_errors := validation_errors + orphaned_count;
            ELSE
                SELECT COUNT(*) INTO orphaned_count
                FROM entity_analytics_optimized eao
                WHERE NOT EXISTS (
                    SELECT 1 FROM organizations o
                    WHERE o.id = eao.organization_id AND o.is_active = TRUE
                ) || org_filter;

                validation_errors := validation_errors + orphaned_count;
            END IF;

            error_details := error_details || jsonb_build_object(
                'orphaned_records_cleaned', orphaned_count,
                'validation_type', 'referential_integrity'
            );
        END;
    END;

    -- Validation 3: Check for duplicate time buckets
    BEGIN
        DECLARE
            duplicate_count INTEGER;
        BEGIN
            IF NOT p_dry_run THEN
                -- Remove duplicate time bucket entries
                WITH duplicates AS (
                    SELECT id, ROW_NUMBER() OVER (
                        PARTITION BY organization_id, time_bucket, bucket_type
                        ORDER BY updated_at DESC
                    ) as rn
                    FROM entity_analytics_optimized
                    WHERE organization_id IS NOT NULL || org_filter
                )
                DELETE FROM entity_analytics_optimized
                WHERE id IN (SELECT id FROM duplicates WHERE rn > 1);

                GET DIAGNOSTICS duplicate_count = ROW_COUNT;
                validation_errors := validation_errors + duplicate_count;
            ELSE
                SELECT COUNT(*) - COUNT(DISTINCT organization_id || time_bucket || bucket_type) INTO duplicate_count
                FROM entity_analytics_optimized
                WHERE organization_id IS NOT NULL || org_filter;

                validation_errors := validation_errors + COALESCE(duplicate_count, 0);
            END IF;

            error_details := error_details || jsonb_build_object(
                'duplicate_buckets_cleaned', duplicate_count,
                'validation_type', 'uniqueness_validation'
            );
        END;
    END;

    RETURN QUERY SELECT
        validation_errors as records_processed,
        EXTRACT(EPOCH FROM (NOW() - validation_start)) * 1000 as duration_ms,
        error_details::TEXT as details;
END;
$$ LANGUAGE plpgsql;

-- Performance monitoring function
CREATE OR REPLACE FUNCTION monitor_analytics_performance(
    p_dry_run BOOLEAN DEFAULT FALSE
) RETURNS TABLE(
    records_processed INTEGER,
    duration_ms INTEGER,
    details TEXT
) AS $$
DECLARE
    monitoring_start TIMESTAMPTZ := NOW();
    slow_queries_count INTEGER := 0;
    performance_alerts INTEGER := 0;
    performance_details JSONB := '[]'::JSONB;
BEGIN
    -- Monitor slow queries
    SELECT COUNT(*) INTO slow_queries_count
    FROM pg_stat_statements
    WHERE query LIKE '%analytics%'
      AND mean_exec_time > 5000 -- Queries taking more than 5 seconds
      AND calls > 10; -- At least 10 calls

    performance_details := jsonb_build_object(
        'slow_queries_detected', slow_queries_count,
        'performance_threshold_ms', 5000
    );

    -- Check for table bloat
    BEGIN
        DECLARE
            bloated_tables INTEGER;
        BEGIN
            SELECT COUNT(*) INTO bloated_tables
            FROM (
                SELECT
                    schemaname,
                    tablename,
                    ROUND(CASE WHEN otta=0 THEN 0.0 ELSE sml.relpages/otta::numeric END,1) AS tbloat,
                    CASE WHEN relpages < otta THEN 0 ELSE relpages::bigint - otta END AS wastedpages
                FROM (
                    SELECT
                        schemaname, tablename, cc.reltuples, cc.relpages, bs,
                        CEIL((cc.reltuples*((datahdr+ma-
                            (CASE WHEN datahdr%ma=0 THEN ma ELSE datahdr%ma END))+nullhdr+4))/(bs-20::float)) AS otta
                    FROM (
                        SELECT
                            ma,bs,schemaname,tablename,
                            (datawidth+(hdr+ma-(CASE WHEN hdr%ma=0 THEN ma ELSE hdr%ma END)))::numeric AS datahdr,
                            (maxfracsum*(nullhdr+ma-(CASE WHEN nullhdr%ma=0 THEN ma ELSE nullhdr%ma END))) AS nullhdr
                        FROM (
                            SELECT
                                schemaname, tablename, hdr, ma, bs,
                                SUM((1-null_frac)*avg_width) AS datawidth,
                                MAX(null_frac) AS maxfracsum,
                                hdr+(
                                    SELECT 1+COUNT(*)*(8-CASE WHEN avg_width<=248 THEN 1 ELSE 8 END)
                                    FROM pg_stats s2
                                    WHERE null_frac<>0 AND s2.schemaname=s.schemaname AND s2.tablename=s.tablename
                                ) AS nullhdr
                            FROM pg_stats s, (
                                SELECT
                                    (SELECT current_setting('block_size')::integer) AS bs,
                                    CASE WHEN substring(v,12,3) IN ('8.0','8.1','8.2') THEN 27 ELSE 23 END AS hdr,
                                    CASE WHEN v ~ 'mingw32' THEN 8 ELSE 4 END AS ma
                                FROM (SELECT version() AS v) AS foo
                            ) AS constants
                            WHERE schemaname='public'
                              AND tablename LIKE '%analytics%'
                            GROUP BY 1,2,3,4,5
                        ) AS foo
                    ) AS rs
                    JOIN pg_class cc ON cc.relname = rs.tablename
                    JOIN pg_namespace nn ON cc.relnamespace = nn.oid AND nn.nspname = rs.schemaname AND nn.nspname <> 'information_schema'
                ) AS sml
                WHERE tbloat > 1.5 OR wastedpages > 10
            ) bloated_analysis;

            performance_details := performance_details || jsonb_build_object(
                'bloated_tables_detected', bloated_tables,
                'maintenance_type', 'bloat_analysis'
            );

            IF NOT p_dry_run AND bloated_tables > 0 THEN
                -- Schedule vacuum for bloated tables
                performance_alerts := performance_alerts + bloated_tables;
            END IF;
        END;
    END;

    -- Check cache hit ratios
    BEGIN
        DECLARE
            cache_hit_ratio DECIMAL;
        BEGIN
            SELECT
                CASE
                    WHEN sum(blks_hit) + sum(blks_read) = 0 THEN 0
                    ELSE sum(blks_hit)::DECIMAL / (sum(blks_hit) + sum(blks_read))
                END INTO cache_hit_ratio
            FROM pg_stat_database
            WHERE datname = current_database();

            performance_details := performance_details || jsonb_build_object(
                'cache_hit_ratio', ROUND(cache_hit_ratio * 100, 2),
                'cache_performance', CASE
                    WHEN cache_hit_ratio > 0.95 THEN 'excellent'
                    WHEN cache_hit_ratio > 0.90 THEN 'good'
                    WHEN cache_hit_ratio > 0.80 THEN 'fair'
                    ELSE 'poor'
                END
            );

            IF cache_hit_ratio < 0.80 THEN
                performance_alerts := performance_alerts + 1;
            END IF;
        END;
    END;

    RETURN QUERY SELECT
        (slow_queries_count + performance_alerts) as records_processed,
        EXTRACT(EPOCH FROM (NOW() - monitoring_start)) * 1000 as duration_ms,
        performance_details::TEXT as details;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- HEALTH CHECK AND MONITORING FUNCTIONS
-- ============================================================================

-- Comprehensive health check function
CREATE OR REPLACE FUNCTION analytics_health_check(
    p_detailed BOOLEAN DEFAULT FALSE
) RETURNS TABLE(
    check_name TEXT,
    status TEXT,
    value NUMERIC,
    threshold NUMERIC,
    details TEXT
) AS $$
BEGIN
    -- Check 1: Database connectivity
    RETURN QUERY SELECT
        'database_connectivity' as check_name,
        'healthy' as status,
        1 as value,
        1 as threshold,
        'Database is accessible and responding' as details;

    -- Check 2: Table sizes
    RETURN QUERY SELECT
        'analytics_table_sizes' as check_name,
        CASE
            WHEN total_size_gb < 10 THEN 'healthy'
            WHEN total_size_gb < 50 THEN 'warning'
            ELSE 'critical'
        END as status,
        total_size_gb as value,
        50 as threshold,
        jsonb_build_object(
            'total_size_gb', total_size_gb,
            'tables_checked', table_count
        )::TEXT as details
    FROM (
        SELECT
            SUM(pg_total_relation_size(schemaname||'.'||tablename)) / (1024.0^3) as total_size_gb,
            COUNT(*) as table_count
        FROM pg_tables
        WHERE schemaname = 'public'
          AND (tablename LIKE '%analytics%' OR tablename LIKE '%entity_%' OR tablename LIKE '%relationship_%')
    ) size_info;

    -- Check 3: Index usage
    RETURN QUERY SELECT
        'index_usage' as check_name,
        CASE
            WHEN unused_indexes = 0 THEN 'healthy'
            WHEN unused_indexes < 5 THEN 'warning'
            ELSE 'critical'
        END as status,
        unused_indexes as value,
        5 as threshold,
        jsonb_build_object(
            'unused_indexes', unused_indexes,
            'total_indexes', total_indexes
        )::TEXT as details
    FROM (
        SELECT
            COUNT(*) FILTER (WHERE idx_scan = 0) as unused_indexes,
            COUNT(*) as total_indexes
        FROM pg_stat_user_indexes
        WHERE schemaname = 'public'
          AND (tablename LIKE '%analytics%' OR tablename LIKE '%entity_%' OR tablename LIKE '%relationship_%')
    ) index_info;

    -- Check 4: Cache performance
    RETURN QUERY SELECT
        'cache_performance' as check_name,
        CASE
            WHEN cache_hit_ratio > 0.95 THEN 'healthy'
            WHEN cache_hit_ratio > 0.90 THEN 'warning'
            ELSE 'critical'
        END as status,
        cache_hit_ratio as value,
        0.90 as threshold,
        jsonb_build_object(
            'cache_hit_ratio', ROUND(cache_hit_ratio * 100, 2),
            'recommendation', CASE
                WHEN cache_hit_ratio < 0.90 THEN 'Consider increasing shared_buffers or optimizing queries'
                ELSE 'Cache performance is optimal'
            END
        )::TEXT as details
    FROM (
        SELECT
            CASE
                WHEN sum(blks_hit) + sum(blks_read) = 0 THEN 0
                ELSE sum(blks_hit)::DECIMAL / (sum(blks_hit) + sum(blks_read))
            END as cache_hit_ratio
        FROM pg_stat_database
        WHERE datname = current_database()
    ) cache_info;

    -- Check 5: Recent activity
    RETURN QUERY SELECT
        'recent_analytics_activity' as check_name,
        CASE
            WHEN recent_computations > 0 THEN 'healthy'
            ELSE 'warning'
        END as status,
        recent_computations as value,
        1 as threshold,
        jsonb_build_object(
            'computations_last_24h', recent_computations,
            'last_computation', last_computation_time
        )::TEXT as details
    FROM (
        SELECT
            COUNT(*) as recent_computations,
            MAX(created_at) as last_computation_time
        FROM analytics_cache
        WHERE created_at >= NOW() - INTERVAL '24 hours'
    ) activity_info;

    -- Additional detailed checks if requested
    IF p_detailed THEN
        -- Check 6: Partition health
        RETURN QUERY SELECT
            'partition_health' as check_name,
            CASE
                WHEN missing_partitions = 0 THEN 'healthy'
                ELSE 'warning'
            END as status,
            missing_partitions as value,
            0 as threshold,
            jsonb_build_object(
                'missing_partitions', missing_partitions,
                'total_partitions', total_partitions
            )::TEXT as details
        FROM (
            SELECT
                COUNT(*) FILTER (WHERE partition_status = 'missing') as missing_partitions,
                COUNT(*) as total_partitions
            FROM (
                SELECT
                    CASE WHEN relname IS NOT NULL THEN 'exists' ELSE 'missing' END as partition_status
                FROM (
                    SELECT 'entity_analytics_y' || to_char(DATE_TRUNC('month', CURRENT_DATE + (n || ' months')::INTERVAL), 'YYYY') || 'm' || lpad(extract(month FROM DATE_TRUNC('month', CURRENT_DATE + (n || ' months')::INTERVAL))::text, 2, '0') as expected_partition
                    FROM generate_series(0, 2) n
                ) expected_partitions
                LEFT JOIN pg_class pg ON pg.relname = expected_partitions.expected_partition
            ) partition_check
        ) partition_info;

        -- Check 7: Security audit
        RETURN QUERY SELECT
            'security_audit' as check_name,
            CASE
                WHEN security_violations_24h = 0 THEN 'healthy'
                WHEN security_violations_24h < 10 THEN 'warning'
                ELSE 'critical'
            END as status,
            security_violations_24h as value,
            10 as threshold,
            jsonb_build_object(
                'violations_24h', security_violations_24h,
                'last_violation', last_violation_time
            )::TEXT as details
        FROM (
            SELECT
                COUNT(*) as security_violations_24h,
                MAX(created_at) as last_violation_time
            FROM analytics_security_log
            WHERE security_level = 'high'
              AND created_at >= NOW() - INTERVAL '24 hours'
        ) security_info;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SCHEDULING AND AUTOMATION
-- ============================================================================

-- Schedule regular maintenance (this would typically be called by pg_cron or external scheduler)
CREATE OR REPLACE FUNCTION schedule_analytics_maintenance() RETURNS VOID AS $$
BEGIN
    -- This function would be called by cron jobs
    -- Example schedule:
    -- - Full maintenance: Daily at 2 AM
    -- - Cache cleanup: Every 4 hours
    -- - Statistics update: Every 6 hours
    -- - Partition maintenance: Weekly on Sunday at 3 AM
    -- - Health check: Hourly

    -- Log the scheduled maintenance
    INSERT INTO analytics_maintenance_log (
        maintenance_type,
        scheduled_at,
        status,
        details
    ) VALUES (
        'scheduled_maintenance',
        NOW(),
        'scheduled',
        jsonb_build_object(
            'next_run', NOW() + INTERVAL '1 day',
            'maintenance_types', ARRAY['cache_cleanup', 'statistics_update', 'health_check']
        )
    );
END;
$$ LANGUAGE plpgsql;

-- Maintenance log table
CREATE TABLE IF NOT EXISTS analytics_maintenance_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    maintenance_type VARCHAR(100) NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'pending',
    details JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_analytics_maintenance_log_type_time
    ON analytics_maintenance_log (maintenance_type, scheduled_at DESC);

CREATE INDEX idx_analytics_maintenance_log_status
    ON analytics_maintenance_log (status, scheduled_at DESC);