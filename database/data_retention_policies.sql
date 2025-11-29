-- Comprehensive Data Retention and Archival Policies
-- Optimized for compliance, performance, and storage efficiency

-- =============================================
-- Data Retention Policy Configuration
-- =============================================

-- Create retention policies table
CREATE TABLE IF NOT EXISTS retention_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    policy_name VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL,

    -- Retention periods
    detailed_retention_days INTEGER NOT NULL DEFAULT 30, -- High-resolution data
    hourly_retention_days INTEGER DEFAULT 90, -- Hourly aggregated data
    daily_retention_days INTEGER DEFAULT 365, -- Daily aggregated data
    monthly_retention_years INTEGER DEFAULT 7, -- Monthly aggregated data

    -- Archival configuration
    archive_after_days INTEGER DEFAULT 365,
    archive_storage VARCHAR(100) DEFAULT 's3', -- 's3', 'glacier', 'local', 'gcs'
    archive_compression BOOLEAN DEFAULT TRUE,
    archive_encryption BOOLEAN DEFAULT TRUE,

    -- Purge configuration
    auto_purge_enabled BOOLEAN DEFAULT TRUE,
    purge_after_days INTEGER,
    purge_confirmation_required BOOLEAN DEFAULT TRUE,
    purge_batch_size INTEGER DEFAULT 10000,

    -- Policy management
    policy_enabled BOOLEAN DEFAULT TRUE,
    policy_priority INTEGER DEFAULT 1, -- Higher number = higher priority
    dry_run BOOLEAN DEFAULT TRUE, -- Set to FALSE to enable actual deletion

    -- Execution tracking
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE,
    run_status VARCHAR(50), -- 'success', 'failed', 'running', 'scheduled'
    run_error_message TEXT,
    run_duration_seconds INTEGER,

    -- Statistics
    total_records_processed BIGINT DEFAULT 0,
    total_records_archived BIGINT DEFAULT 0,
    total_records_purged BIGINT DEFAULT 0,
    storage_saved_gb FLOAT DEFAULT 0,
    cost_saved_usd DECIMAL(12,2) DEFAULT 0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_run_status CHECK (run_status IN ('success', 'failed', 'running', 'scheduled', 'disabled'))
);

-- Create default retention policies for monitoring tables
INSERT INTO retention_policies (policy_name, table_name, detailed_retention_days, hourly_retention_days, daily_retention_days, monthly_retention_years, archive_after_days, purge_after_days, policy_priority) VALUES
-- High-frequency metrics (keep shorter periods)
('performance_metrics_retention', 'performance_metrics', 7, 30, 90, 2, 365, 1825, 10),
('sli_measurements_retention', 'sli_measurements', 14, 60, 365, 7, 1095, 2555, 10),
('user_activity_events_retention', 'user_activity_events', 30, 90, 365, 7, 1095, 2555, 9),
('resource_utilization_metrics_retention', 'resource_utilization_metrics', 7, 30, 365, 3, 1095, 1825, 8),

-- Business metrics (keep longer for analytics)
('search_quality_metrics_retention', 'search_quality_metrics', 30, 90, 1095, 10, 1825, 3650, 7),
('document_processing_metrics_retention', 'document_processing_metrics', 90, 365, 1825, 10, 2555, 3650, 7),
('rag_quality_metrics_retention', 'rag_quality_metrics', 90, 365, 1825, 10, 2555, 3650, 7),

-- Health and alerts (keep for compliance)
('service_health_status_retention', 'service_health_status', 30, 90, 730, 5, 1825, 2555, 6),
('system_alerts_retention', 'system_alerts', 365, 1095, 2555, 15, 3650, 3650, 6),

-- User data (keep longest for privacy compliance)
('user_sessions_retention', 'user_sessions', 90, 365, 1825, 10, 2555, 2555, 5),
('feature_usage_metrics_retention', 'feature_usage_metrics', 365, 1095, 1825, 10, 2555, 3650, 5),

-- Database metrics (medium retention)
('database_performance_metrics_retention', 'database_performance_metrics', 30, 90, 730, 3, 1095, 1825, 8),
('queue_monitoring_metrics_retention', 'queue_monitoring_metrics', 30, 90, 730, 3, 1095, 1825, 8)
ON CONFLICT (policy_name) DO NOTHING;

-- =============================================
-- Data Aggregation Tables
-- =============================================

-- Hourly aggregated performance metrics
CREATE TABLE IF NOT EXISTS performance_metrics_hourly (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(255) NOT NULL,
    metric_category VARCHAR(100) NOT NULL,
    component_name VARCHAR(255) NOT NULL,
    organization_id UUID REFERENCES organizations(id),

    hour_bucket TIMESTAMP WITH TIME ZONE NOT NULL,
    sample_count INTEGER NOT NULL,

    avg_value FLOAT NOT NULL,
    min_value FLOAT NOT NULL,
    max_value FLOAT NOT NULL,
    sum_value FLOAT NOT NULL,
    p50_value FLOAT,
    p90_value FLOAT,
    p95_value FLOAT,
    p99_value FLOAT,
    std_deviation FLOAT,

    total_requests INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    error_rate FLOAT,

    environment VARCHAR(50) DEFAULT 'production',
    tags JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(metric_name, component_name, organization_id, hour_bucket)
);

-- Daily aggregated performance metrics
CREATE TABLE IF NOT EXISTS performance_metrics_daily (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(255) NOT NULL,
    metric_category VARCHAR(100) NOT NULL,
    component_name VARCHAR(255) NOT NULL,
    organization_id UUID REFERENCES organizations(id),

    day_bucket DATE NOT NULL,
    sample_count INTEGER NOT NULL,

    avg_value FLOAT NOT NULL,
    min_value FLOAT NOT NULL,
    max_value FLOAT NOT NULL,
    sum_value FLOAT NOT NULL,
    p50_value FLOAT,
    p90_value FLOAT,
    p95_value FLOAT,
    p99_value FLOAT,
    std_deviation FLOAT,

    total_requests INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    error_rate FLOAT,

    environment VARCHAR(50) DEFAULT 'production',
    tags JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(metric_name, component_name, organization_id, day_bucket)
);

-- Hourly aggregated user activity
CREATE TABLE IF NOT EXISTS user_activity_hourly (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    hour_bucket TIMESTAMP WITH TIME ZONE NOT NULL,

    unique_users INTEGER NOT NULL,
    unique_sessions INTEGER NOT NULL,
    total_events INTEGER NOT NULL,
    total_page_views INTEGER DEFAULT 0,
    total_searches INTEGER DEFAULT 0,
    total_downloads INTEGER DEFAULT 0,
    total_uploads INTEGER DEFAULT 0,

    avg_session_duration_seconds FLOAT,
    avg_event_duration_ms FLOAT,
    total_business_value DECIMAL(12,2),
    conversion_rate FLOAT,

    device_types JSONB,
    event_types JSONB,
    top_pages JSONB,
    top_events JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(organization_id, hour_bucket)
);

-- Daily aggregated search quality
CREATE TABLE IF NOT EXISTS search_quality_daily (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    day_bucket DATE NOT NULL,

    total_searches INTEGER NOT NULL,
    unique_searchers INTEGER NOT NULL,
    avg_response_time_ms FLOAT,
    p95_response_time_ms FLOAT,

    avg_relevance_score FLOAT,
    avg_diversity_score FLOAT,
    avg_freshness_score FLOAT,
    avg_quality_score FLOAT,

    total_clicks INTEGER DEFAULT 0,
    click_through_rate FLOAT,
    avg_user_rating FLOAT,
    total_rated_searches INTEGER DEFAULT 0,

    searches_with_no_results INTEGER DEFAULT 0,
    searches_with_filters INTEGER DEFAULT 0,

    query_types JSONB,
    search_scopes JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(organization_id, day_bucket)
);

-- =============================================
-- Archival Storage Functions
-- =============================================

-- Function to create archive table structure
CREATE OR REPLACE FUNCTION create_archive_table(table_name TEXT, archive_suffix TEXT DEFAULT 'archive')
RETURNS TEXT AS $$
DECLARE
    archive_table_name TEXT;
    sql TEXT;
BEGIN
    archive_table_name := table_name || '_' || archive_suffix;

    -- Create archive table with same structure
    sql := format('CREATE TABLE IF NOT EXISTS %I (LIKE %I INCLUDING ALL)', archive_table_name, table_name);
    EXECUTE sql;

    -- Add archive metadata columns
    sql := format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()', archive_table_name);
    EXECUTE sql;

    sql := format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS archive_batch_id VARCHAR(100)', archive_table_name);
    EXECUTE sql;

    sql := format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS archive_reason TEXT', archive_table_name);
    EXECUTE sql;

    -- Create indexes for archive table
    sql := format('CREATE INDEX IF NOT EXISTS idx_%s_archived_at ON %I (archived_at)', archive_table_name, archive_table_name);
    EXECUTE sql;

    sql := format('CREATE INDEX IF NOT EXISTS idx_%s_original_timestamp ON %I (timestamp)', archive_table_name, archive_table_name);
    EXECUTE sql;

    RETURN archive_table_name;
END;
$$ LANGUAGE plpgsql;

-- Function to archive old data
CREATE OR REPLACE FUNCTION archive_old_data(
    p_table_name TEXT,
    p_cutoff_date TIMESTAMP WITH TIME ZONE,
    p_archive_table_name TEXT DEFAULT NULL,
    p_batch_size INTEGER DEFAULT 10000,
    p_batch_id TEXT DEFAULT NULL
)
RETURNS TABLE(
    archived_count BIGINT,
    archive_table TEXT,
    batch_id TEXT,
    execution_time_seconds FLOAT
) AS $$
DECLARE
    v_archive_table TEXT;
    v_sql TEXT;
    v_start_time TIMESTAMP WITH TIME ZONE;
    v_total_archived BIGINT := 0;
    v_batch_count BIGINT;
    v_batch_sql TEXT;
BEGIN
    v_start_time := NOW();

    -- Determine archive table name
    IF p_archive_table_name IS NULL THEN
        v_archive_table := create_archive_table(p_table_name);
    ELSE
        v_archive_table := p_archive_table_name;
    END IF;

    -- Get column names (excluding generated columns)
    SELECT string_agg(quote_ident(column_name), ', ')
    INTO v_sql
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = p_table_name
    AND is_generated = 'NO'
    AND column_name NOT IN ('id', 'created_at', 'updated_at');

    -- Archive data in batches
    v_batch_sql := format('
        WITH batch AS (
            SELECT id
            FROM %I
            WHERE timestamp < %L
            LIMIT %s
        )
        INSERT INTO %I (%s, archived_at, archive_batch_id, archive_reason)
        SELECT %s, NOW(), %L, ''Automated archival based on retention policy''
        FROM %I t
        JOIN batch b ON t.id = b.id
        RETURNING COUNT(*)',
        p_table_name, p_cutoff_date, p_batch_size,
        v_archive_table, v_sql, v_sql,
        p_batch_id, p_table_name
    );

    EXECUTE v_batch_sql INTO v_batch_count;
    v_total_archived := v_total_archived + v_batch_count;

    -- Delete archived data from source table in batches
    IF v_batch_count > 0 THEN
        v_batch_sql := format('
            DELETE FROM %I
            WHERE id IN (
                SELECT id
                FROM %I
                WHERE timestamp < %L
                LIMIT %s
            )',
            p_table_name, p_table_name, p_cutoff_date, p_batch_size
        );

        EXECUTE v_batch_sql;
    END IF;

    RETURN QUERY SELECT v_total_archived, v_archive_table, p_batch_id, EXTRACT(EPOCH FROM (NOW() - v_start_time));
END;
$$ LANGUAGE plpgsql;

-- S3 archival function (requires aws_s3 extension)
CREATE OR REPLACE FUNCTION archive_to_s3(
    p_table_name TEXT,
    p_cutoff_date TIMESTAMP WITH TIME ZONE,
    p_s3_bucket TEXT,
    p_s3_prefix TEXT DEFAULT 'monitoring-archive',
    p_compression BOOLEAN DEFAULT TRUE,
    p_encryption BOOLEAN DEFAULT TRUE
)
RETURNS TABLE(
    archived_count BIGINT,
    s3_path TEXT,
    file_size_bytes BIGINT,
    execution_time_seconds FLOAT
) AS $$
DECLARE
    v_sql TEXT;
    v_start_time TIMESTAMP WITH TIME ZONE;
    v_filename TEXT;
    v_s3_path TEXT;
    v_count BIGINT;
BEGIN
    v_start_time := NOW();
    v_filename := format('%s_%s_%s.csv.gz',
        p_table_name,
        TO_CHAR(p_cutoff_date, 'YYYY-MM-DD'),
        TO_CHAR(NOW(), 'YYYY-MM-DD_HH24-MI-SS')
    );
    v_s3_path := format('%s/%s/%s', p_s3_prefix, p_table_name, v_filename);

    -- Create temporary table for data to archive
    v_sql := format('CREATE TEMP TABLE temp_archive_data AS SELECT * FROM %I WHERE timestamp < %L', p_table_name, p_cutoff_date);
    EXECUTE v_sql;

    -- Get count before archival
    EXECUTE format('SELECT COUNT(*) FROM temp_archive_data') INTO v_count;

    -- Export to S3 using COPY command (requires aws_s3 extension)
    IF v_count > 0 THEN
        v_sql := format('COPY temp_archive_data TO %L WITH (FORMAT CSV, HEADER, COMPRESSION GZIP)',
            's3://' || p_s3_bucket || '/' || v_s3_path
        );

        BEGIN
            EXECUTE v_sql;
        EXCEPTION WHEN OTHERS THEN
            -- Fallback to local file if S3 fails
            RAISE NOTICE 'S3 upload failed, using local backup: %', SQLERRM;
            v_sql := format('COPY temp_archive_data TO %L WITH (FORMAT CSV, HEADER, COMPRESSION GZIP)',
                '/tmp/' || v_filename
            );
            EXECUTE v_sql;
        END;

        -- Delete archived data
        v_sql := format('DELETE FROM %I WHERE timestamp < %L', p_table_name, p_cutoff_date);
        EXECUTE v_sql;
    END IF;

    -- Clean up temp table
    DROP TABLE IF EXISTS temp_archive_data;

    RETURN QUERY SELECT v_count, v_s3_path, 0::BIGINT, EXTRACT(EPOCH FROM (NOW() - v_start_time));
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- Data Aggregation Functions
-- =============================================

-- Function to aggregate performance metrics to hourly
CREATE OR REPLACE FUNCTION aggregate_performance_metrics_hourly(
    p_hour_bucket TIMESTAMP WITH TIME ZONE,
    p_organization_id UUID DEFAULT NULL
)
RETURNS TABLE(
    records_processed INTEGER,
    aggregates_created INTEGER,
    execution_time_ms INTEGER
) AS $$
DECLARE
    v_start_time TIMESTAMP WITH TIME ZONE;
    v_processed INTEGER := 0;
    v_created INTEGER := 0;
BEGIN
    v_start_time := NOW();

    -- Insert hourly aggregates
    INSERT INTO performance_metrics_hourly (
        metric_name, metric_category, component_name, organization_id,
        hour_bucket, sample_count, avg_value, min_value, max_value, sum_value,
        p50_value, p90_value, p95_value, p99_value, std_deviation,
        total_requests, total_errors, error_rate, environment, tags
    )
    SELECT
        metric_name,
        metric_category,
        component_name,
        organization_id,
        p_hour_bucket,
        COUNT(*) as sample_count,
        AVG(value) as avg_value,
        MIN(value) as min_value,
        MAX(value) as max_value,
        SUM(value) as sum_value,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY value) as p50_value,
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY value) as p90_value,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY value) as p95_value,
        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY value) as p99_value,
        STDDEV(value) as std_deviation,
        SUM(COALESCE(request_count, 1)) as total_requests,
        SUM(COALESCE(error_count, 0)) as total_errors,
        CASE WHEN SUM(COALESCE(request_count, 1)) > 0
             THEN SUM(COALESCE(error_count, 0))::FLOAT / SUM(COALESCE(request_count, 1))
             ELSE 0 END as error_rate,
        MAX(environment) as environment,
        jsonb_build_object('top_components', jsonb_agg(DISTINCT component_name)) as tags
    FROM performance_metrics
    WHERE DATE_TRUNC('hour', timestamp) = p_hour_bucket
      AND (p_organization_id IS NULL OR organization_id = p_organization_id)
    GROUP BY metric_name, metric_category, component_name, organization_id
    ON CONFLICT (metric_name, component_name, organization_id, hour_bucket)
    DO UPDATE SET
        sample_count = EXCLUDED.sample_count,
        avg_value = EXCLUDED.avg_value,
        min_value = EXCLUDED.min_value,
        max_value = EXCLUDED.max_value,
        sum_value = EXCLUDED.sum_value,
        p50_value = EXCLUDED.p50_value,
        p90_value = EXCLUDED.p90_value,
        p95_value = EXCLUDED.p95_value,
        p99_value = EXCLUDED.p99_value,
        std_deviation = EXCLUDED.std_deviation,
        total_requests = EXCLUDED.total_requests,
        total_errors = EXCLUDED.total_errors,
        error_rate = EXCLUDED.error_rate,
        tags = EXCLUDED.tags;

    GET DIAGNOSTICS v_created = ROW_COUNT;

    -- Count processed records
    SELECT COUNT(*) INTO v_processed
    FROM performance_metrics
    WHERE DATE_TRUNC('hour', timestamp) = p_hour_bucket
      AND (p_organization_id IS NULL OR organization_id = p_organization_id);

    RETURN QUERY SELECT v_processed, v_created, EXTRACT(MILLISECOND FROM (NOW() - v_start_time))::INTEGER;
END;
$$ LANGUAGE plpgsql;

-- Function to aggregate user activity to hourly
CREATE OR REPLACE FUNCTION aggregate_user_activity_hourly(
    p_hour_bucket TIMESTAMP WITH TIME ZONE,
    p_organization_id UUID DEFAULT NULL
)
RETURNS TABLE(
    records_processed INTEGER,
    aggregates_created INTEGER,
    execution_time_ms INTEGER
) AS $$
DECLARE
    v_start_time TIMESTAMP WITH TIME ZONE;
    v_processed INTEGER := 0;
    v_created INTEGER := 0;
BEGIN
    v_start_time := NOW();

    INSERT INTO user_activity_hourly (
        organization_id, hour_bucket, unique_users, unique_sessions, total_events,
        total_page_views, total_searches, total_downloads, total_uploads,
        avg_session_duration_seconds, avg_event_duration_ms, total_business_value, conversion_rate,
        device_types, event_types, top_pages, top_events
    )
    SELECT
        organization_id,
        p_hour_bucket,
        COUNT(DISTINCT user_id) as unique_users,
        COUNT(DISTINCT session_id) as unique_sessions,
        COUNT(*) as total_events,
        COUNT(CASE WHEN event_type = 'page_view' THEN 1 END) as total_page_views,
        COUNT(CASE WHEN event_type = 'search_query' THEN 1 END) as total_searches,
        COUNT(CASE WHEN event_type = 'download' THEN 1 END) as total_downloads,
        COUNT(CASE WHEN event_type = 'upload' THEN 1 END) as total_uploads,
        AVG(event_duration_ms) / 1000.0 as avg_session_duration_seconds,
        AVG(event_duration_ms) as avg_event_duration_ms,
        COALESCE(SUM(business_value), 0) as total_business_value,
        CASE WHEN COUNT(*) > 0
             THEN COUNT(CASE WHEN business_value > 0 THEN 1 END)::FLOAT / COUNT(*)
             ELSE 0 END as conversion_rate,
        jsonb_build_object('desktop', COUNT(CASE WHEN device_type = 'desktop' THEN 1 END),
                           'mobile', COUNT(CASE WHEN device_type = 'mobile' THEN 1 END),
                           'tablet', COUNT(CASE WHEN device_type = 'tablet' THEN 1 END)) as device_types,
        jsonb_build_object('search', COUNT(CASE WHEN event_category = 'search' THEN 1 END),
                           'document', COUNT(CASE WHEN event_category = 'document' THEN 1 END),
                           'interaction', COUNT(CASE WHEN event_category = 'interaction' THEN 1 END)) as event_types,
        jsonb_agg(DISTINCT page_url ORDER BY COUNT(*) DESC) as top_pages,
        jsonb_agg(DISTINCT event_type ORDER BY COUNT(*) DESC) as top_events
    FROM user_activity_events
    WHERE DATE_TRUNC('hour', event_timestamp) = p_hour_bucket
      AND (p_organization_id IS NULL OR organization_id = p_organization_id)
    GROUP BY organization_id
    ON CONFLICT (organization_id, hour_bucket)
    DO UPDATE SET
        unique_users = EXCLUDED.unique_users,
        unique_sessions = EXCLUDED.unique_sessions,
        total_events = EXCLUDED.total_events,
        total_page_views = EXCLUDED.total_page_views,
        total_searches = EXCLUDED.total_searches,
        total_downloads = EXCLUDED.total_downloads,
        total_uploads = EXCLUDED.total_uploads,
        avg_session_duration_seconds = EXCLUDED.avg_session_duration_seconds,
        avg_event_duration_ms = EXCLUDED.avg_event_duration_ms,
        total_business_value = EXCLUDED.total_business_value,
        conversion_rate = EXCLUDED.conversion_rate,
        device_types = EXCLUDED.device_types,
        event_types = EXCLUDED.event_types,
        top_pages = EXCLUDED.top_pages,
        top_events = EXCLUDED.top_events;

    GET DIAGNOSTICS v_created = ROW_COUNT;

    SELECT COUNT(*) INTO v_processed
    FROM user_activity_events
    WHERE DATE_TRUNC('hour', event_timestamp) = p_hour_bucket
      AND (p_organization_id IS NULL OR organization_id = p_organization_id);

    RETURN QUERY SELECT v_processed, v_created, EXTRACT(MILLISECOND FROM (NOW() - v_start_time))::INTEGER;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- Retention Policy Execution Engine
-- =============================================

-- Main retention policy execution function
CREATE OR REPLACE FUNCTION execute_retention_policies(
    p_organization_id UUID DEFAULT NULL,
    p_dry_run BOOLEAN DEFAULT TRUE,
    p_force_execution BOOLEAN DEFAULT FALSE
)
RETURNS TABLE(
    policy_name TEXT,
    table_name TEXT,
    action_taken TEXT,
    records_processed BIGINT,
    records_archived BIGINT,
    records_purged BIGINT,
    storage_saved_gb FLOAT,
    execution_time_seconds FLOAT,
    status TEXT,
    error_message TEXT
) AS $$
DECLARE
    policy_record RECORD;
    v_start_time TIMESTAMP WITH TIME ZONE;
    v_execution_time FLOAT;
    v_cutoff_detailed TIMESTAMP WITH TIME ZONE;
    v_cutoff_hourly TIMESTAMP WITH TIME ZONE;
    v_cutoff_daily TIMESTAMP WITH TIME ZONE;
    v_cutoff_monthly TIMESTAMP WITH TIME ZONE;
    v_records_count BIGINT;
    v_archived_count BIGINT;
    v_purged_count BIGINT;
    v_sql TEXT;
    v_error_message TEXT;
    v_batch_id TEXT;
BEGIN
    -- Generate batch ID for this execution run
    v_batch_id := format('retention_%s_%s', TO_CHAR(NOW(), 'YYYY-MM-DD_HH24-MI-SS'), COALESCE(p_organization_id::TEXT, 'all'));

    FOR policy_record IN
        SELECT * FROM retention_policies
        WHERE policy_enabled = TRUE
          AND (p_organization_id IS NULL OR organization_id IS NULL OR organization_id = p_organization_id)
          AND (p_force_execution = TRUE OR next_run <= NOW() OR next_run IS NULL)
        ORDER BY policy_priority DESC
    LOOP
        v_start_time := NOW();
        v_error_message := NULL;
        v_records_count := 0;
        v_archived_count := 0;
        v_purged_count := 0;

        BEGIN
            -- Calculate cutoff dates
            v_cutoff_detailed := NOW() - (policy_record.detailed_retention_days || ' days')::INTERVAL;
            v_cutoff_hourly := NOW() - (policy_record.hourly_retention_days || ' days')::INTERVAL;
            v_cutoff_daily := NOW() - (policy_record.daily_retention_days || ' days')::INTERVAL;
            v_cutoff_monthly := NOW() - (policy_record.monthly_retention_years || ' years')::INTERVAL;

            -- Get count of records to process
            v_sql := format('SELECT COUNT(*) FROM %I WHERE timestamp < %L', policy_record.table_name, v_cutoff_detailed);
            EXECUTE v_sql INTO v_records_count;

            IF v_records_count = 0 THEN
                RETURN QUERY SELECT
                    policy_record.policy_name,
                    policy_record.table_name,
                    'no_action' as action_taken,
                    v_records_count,
                    v_archived_count,
                    v_purged_count,
                    0.0 as storage_saved_gb,
                    0.0 as execution_time_seconds,
                    'completed' as status,
                    'No records to process' as error_message;
                CONTINUE;
            END IF;

            -- Step 1: Archive old data if configured
            IF policy_record.archive_after_days IS NOT NULL AND policy_record.archive_storage IS NOT NULL THEN
                IF NOT p_dry_run THEN
                    -- Archive based on storage type
                    IF policy_record.archive_storage = 's3' THEN
                        SELECT archived_count INTO v_archived_count
                        FROM archive_to_s3(policy_record.table_name, v_cutoff_detailed, 'monitoring-archive-bucket', 'monitoring-archive')
                        LIMIT 1;
                    ELSE
                        SELECT archived_count INTO v_archived_count
                        FROM archive_old_data(policy_record.table_name, v_cutoff_detailed, NULL, 10000, v_batch_id)
                        LIMIT 1;
                    END IF;
                ELSE
                    v_archived_count := v_records_count; -- Simulate archival
                END IF;
            END IF;

            -- Step 2: Purge data if configured and beyond retention period
            IF policy_record.purge_after_days IS NOT NULL THEN
                v_cutoff_purge := NOW() - (policy_record.purge_after_days || ' days')::INTERVAL;

                IF NOT p_dry_run AND policy_record.purge_confirmation_required = FALSE THEN
                    v_sql := format('DELETE FROM %I WHERE timestamp < %L', policy_record.table_name, v_cutoff_purge);
                    EXECUTE v_sql;
                    GET DIAGNOSTICS v_purged_count = ROW_COUNT;
                ELSIF p_dry_run THEN
                    v_sql := format('SELECT COUNT(*) FROM %I WHERE timestamp < %L', policy_record.table_name, v_cutoff_purge);
                    EXECUTE v_sql INTO v_purged_count;
                END IF;
            END IF;

            -- Step 3: Aggregate data to hourly if table supports it
            IF policy_record.table_name IN ('performance_metrics', 'user_activity_events', 'search_quality_metrics') THEN
                IF NOT p_dry_run THEN
                    -- Aggregate data for the cutoff period
                    IF policy_record.table_name = 'performance_metrics' THEN
                        PERFORM aggregate_performance_metrics_hourly(v_cutoff_hourly, policy_record.organization_id);
                    ELSIF policy_record.table_name = 'user_activity_events' THEN
                        PERFORM aggregate_user_activity_hourly(v_cutoff_hourly, policy_record.organization_id);
                    END IF;
                END IF;
            END IF;

            -- Calculate storage savings (estimate)
            -- This would need actual table size analysis in production
            DECLARE
                v_avg_row_size FLOAT;
                v_total_size_gb FLOAT;
            BEGIN
                v_avg_row_size := 1.0; -- KB average row size (should be calculated)
                v_total_size_gb := (v_records_count * v_avg_row_size) / 1024 / 1024;
            END;

            -- Update policy execution tracking
            IF NOT p_dry_run THEN
                UPDATE retention_policies SET
                    last_run = NOW(),
                    next_run = NOW() + INTERVAL '1 day', -- Run daily
                    run_status = 'success',
                    run_error_message = NULL,
                    total_records_processed = total_records_processed + v_records_count,
                    total_records_archived = total_records_archived + v_archived_count,
                    total_records_purged = total_records_purged + v_purged_count,
                    storage_saved_gb = storage_saved_gb + v_total_size_gb,
                    run_duration_seconds = EXTRACT(EPOCH FROM (NOW() - v_start_time))
                WHERE id = policy_record.id;
            END IF;

            v_execution_time := EXTRACT(EPOCH FROM (NOW() - v_start_time));

            RETURN QUERY SELECT
                policy_record.policy_name,
                policy_record.table_name,
                CASE
                    WHEN v_archived_count > 0 AND v_purged_count > 0 THEN 'archived_and_purged'
                    WHEN v_archived_count > 0 THEN 'archived'
                    WHEN v_purged_count > 0 THEN 'purged'
                    ELSE 'aggregated'
                END as action_taken,
                v_records_count,
                v_archived_count,
                v_purged_count,
                v_total_size_gb as storage_saved_gb,
                v_execution_time as execution_time_seconds,
                'completed' as status,
                NULL as error_message;

        EXCEPTION WHEN OTHERS THEN
            v_error_message := SQLERRM;
            v_execution_time := EXTRACT(EPOCH FROM (NOW() - v_start_time));

            IF NOT p_dry_run THEN
                UPDATE retention_policies SET
                    run_status = 'failed',
                    run_error_message = v_error_message,
                    run_duration_seconds = v_execution_time
                WHERE id = policy_record.id;
            END IF;

            RETURN QUERY SELECT
                policy_record.policy_name,
                policy_record.table_name,
                'error' as action_taken,
                v_records_count,
                v_archived_count,
                v_purged_count,
                0.0 as storage_saved_gb,
                v_execution_time as execution_time_seconds,
                'failed' as status,
                v_error_message as error_message;
        END;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- Monitoring and Reporting Views
-- =============================================

-- Data retention status dashboard
CREATE OR REPLACE VIEW retention_status_dashboard AS
SELECT
    rp.policy_name,
    rp.table_name,
    rp.detailed_retention_days,
    rp.hourly_retention_days,
    rp.daily_retention_days,
    rp.monthly_retention_years,
    rp.archive_after_days,
    rp.purge_after_days,
    rp.policy_enabled,
    rp.last_run,
    rp.next_run,
    rp.run_status,
    rp.total_records_processed,
    rp.total_records_archived,
    rp.total_records_purged,
    rp.storage_saved_gb,
    CASE
        WHEN rp.last_run IS NULL THEN 'never_run'
        WHEN rp.last_run < NOW() - INTERVAL '2 days' THEN 'overdue'
        WHEN rp.last_run < NOW() - INTERVAL '1 day' THEN 'warning'
        ELSE 'current'
    END as health_status,
    pg_total_relation_size(rp.table_name::regclass) as current_table_size_bytes,
    pg_size_pretty(pg_total_relation_size(rp.table_name::regclass)) as current_table_size_pretty
FROM retention_policies rp
LEFT JOIN pg_tables pt ON pt.tablename = rp.table_name
WHERE pt.schemaname = 'public'
ORDER BY rp.policy_priority DESC, rp.last_run DESC NULLS LAST;

-- Data growth trends
CREATE OR REPLACE VIEW data_growth_trends AS
SELECT
    schemaname,
    tablename,
    pg_total_relation_size(schemaname||'.'||tablename) as total_bytes,
    pg_relation_size(schemaname||'.'||tablename) as table_bytes,
    pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename) as index_bytes,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_pretty,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_pretty,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_pretty,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = schemaname AND table_name = tablename) as column_count,
    (SELECT COUNT(*) FROM pg_indexes WHERE schemaname = schemaname AND tablename = tablename) as index_count
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE ANY(ARRAY['%metrics%', '%measurements%', '%events%', '%sessions%', '%alerts%'])
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Archive storage estimation
CREATE OR REPLACE VIEW archive_storage_estimation AS
SELECT
    rp.table_name,
    rp.detailed_retention_days,
    rp.archive_after_days,
    CASE
        WHEN pg_total_relation_size(rp.table_name::regclass) > 0 THEN
            (pg_total_relation_size(rp.table_name::regclass) *
             (rp.archive_after_days::FLOAT / GREATEST(rp.detailed_retention_days, 1)))
        ELSE 0
    END as estimated_archive_size_bytes,
    CASE
        WHEN pg_total_relation_size(rp.table_name::regclass) > 0 THEN
            pg_size_pretty(pg_total_relation_size(rp.table_name::regclass) *
                          (rp.archive_after_days::FLOAT / GREATEST(rp.detailed_retention_days, 1)))
        ELSE '0 bytes'
    END as estimated_archive_size_pretty,
    CASE
        WHEN rp.archive_storage = 's3' THEN 'Standard S3: $0.023/GB/month'
        WHEN rp.archive_storage = 'glacier' THEN 'Glacier: $0.004/GB/month'
        WHEN rp.archive_storage = 'local' THEN 'Local storage: No additional cost'
        ELSE 'Unknown storage type'
    END as storage_cost_estimate,
    CASE
        WHEN pg_total_relation_size(rp.table_name::regclass) > 0 THEN
            (pg_total_relation_size(rp.table_name::regclass) / 1024.0 / 1024.0 / 1024.0 *
             (rp.archive_after_days::FLOAT / GREATEST(rp.detailed_retention_days, 1)) *
             CASE rp.archive_storage
                 WHEN 's3' THEN 0.023
                 WHEN 'glacier' THEN 0.004
                 ELSE 0
             END)
        ELSE 0
    END as estimated_monthly_cost_usd
FROM retention_policies rp
JOIN pg_tables pt ON pt.tablename = rp.table_name
WHERE pt.schemaname = 'public'
  AND rp.archive_after_days IS NOT NULL
  AND rp.policy_enabled = TRUE;

-- =============================================
-- Automated Scheduling
-- =============================================

-- Create function to schedule retention jobs (requires pg_cron)
CREATE OR REPLACE FUNCTION schedule_retention_jobs()
RETURNS void AS $$
BEGIN
    -- Schedule daily retention policy execution at 2 AM
    -- SELECT cron.schedule('daily-retention', '0 2 * * *', 'SELECT execute_retention_policies(NULL, FALSE, FALSE);');

    -- Schedule weekly dry-run for compliance checking at 3 AM on Sundays
    -- SELECT cron.schedule('weekly-retention-dryrun', '0 3 * * 0', 'SELECT execute_retention_policies(NULL, TRUE, FALSE);');

    -- Schedule hourly aggregation for performance metrics
    -- SELECT cron.schedule('hourly-aggregation', '0 * * * *', 'SELECT aggregate_performance_metrics_hourly(date_trunc(''hour'', NOW() - interval ''1 hour''), NULL);');

    -- Schedule hourly aggregation for user activity
    -- SELECT cron.schedule('hourly-user-aggregation', '5 * * * *', 'SELECT aggregate_user_activity_hourly(date_trunc(''hour'', NOW() - interval ''1 hour''), NULL);');

    RAISE NOTICE 'Retention jobs scheduled. Uncomment the cron.schedule() calls to activate.';
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- Example Usage and Testing
-- =============================================

-- Test dry run of retention policies
-- SELECT * FROM execute_retention_policies(NULL, TRUE, FALSE);

-- Test specific organization
-- SELECT * FROM execute_retention_policies('uuid-of-org', TRUE, FALSE);

-- Force execution (bypass schedule check)
-- SELECT * FROM execute_retention_policies(NULL, FALSE, TRUE);

-- Test aggregation functions
-- SELECT * FROM aggregate_performance_metrics_hourly(date_trunc('hour', NOW() - interval '1 hour'), NULL);

-- View current retention status
-- SELECT * FROM retention_status_dashboard;

-- View data growth trends
-- SELECT * FROM data_growth_trends;

-- Estimate archive storage needs
-- SELECT * FROM archive_storage_estimation;

-- Schedule automated jobs
-- SELECT schedule_retention_jobs();

-- =============================================
-- Compliance and Audit
-- =============================================

-- Create audit log for retention actions
CREATE TABLE IF NOT EXISTS retention_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id VARCHAR(100) NOT NULL,
    policy_name VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    action_taken VARCHAR(100) NOT NULL,
    records_processed BIGINT NOT NULL,
    records_archived BIGINT DEFAULT 0,
    records_purged BIGINT DEFAULT 0,
    storage_saved_gb FLOAT DEFAULT 0,
    execution_time_seconds FLOAT NOT NULL,
    status VARCHAR(50) NOT NULL,
    error_message TEXT,
    executed_by VARCHAR(100) DEFAULT 'system',
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    organization_id UUID REFERENCES organizations(id)
);

-- Create trigger to log retention executions
CREATE OR REPLACE FUNCTION log_retention_execution()
RETURNS TRIGGER AS $$
BEGIN
    -- This would be called by the retention execution function
    -- Implementation would log to retention_audit_log table
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Compliance reporting view
CREATE OR REPLACE VIEW compliance_retention_report AS
SELECT
    DATE_TRUNC('month', executed_at) as report_month,
    policy_name,
    table_name,
    COUNT(*) as executions,
    SUM(records_processed) as total_records_processed,
    SUM(records_archived) as total_records_archived,
    SUM(records_purged) as total_records_purged,
    SUM(storage_saved_gb) as total_storage_saved_gb,
    AVG(execution_time_seconds) as avg_execution_time_seconds,
    MAX(executed_at) as last_execution,
    status
FROM retention_audit_log
WHERE executed_at >= NOW() - INTERVAL '12 months'
GROUP BY report_month, policy_name, table_name, status
ORDER BY report_month DESC, total_records_processed DESC;

-- Initialize retention audit logging
-- This would be called from within the execute_retention_policies function
-- to maintain an audit trail of all retention actions for compliance.

COMMIT;