-- Extended Analytics Procedures for Knowledge Graph Dashboard
-- Document analytics, user interactions, and performance optimization

-- ============================================================================
-- DOCUMENT ANALYTICS STORED PROCEDURES
-- ============================================================================

-- Comprehensive document analytics calculation
CREATE OR REPLACE FUNCTION compute_document_analytics_aggregated(
    p_organization_id UUID,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ,
    p_bucket_type VARCHAR(20) DEFAULT 'day',
    p_force_refresh BOOLEAN DEFAULT FALSE
) RETURNS INTEGER AS $$
DECLARE
    total_buckets_processed INTEGER := 0;
    bucket_start TIMESTAMPTZ;
    bucket_end TIMESTAMPTZ;
    bucket_interval INTERVAL;
    computation_start TIMESTAMPTZ := NOW();
    cache_key VARCHAR(255);
    cached_results JSONB;
BEGIN
    -- Input validation
    IF p_organization_id IS NULL OR p_start_time IS NULL OR p_end_time IS NULL THEN
        RAISE EXCEPTION 'Organization ID, start time, and end time are required';
    END IF;

    IF p_start_time >= p_end_time THEN
        RAISE EXCEPTION 'Start time must be before end time';
    END IF;

    CASE p_bucket_type
        WHEN 'hour' THEN bucket_interval := INTERVAL '1 hour';
        WHEN 'day' THEN bucket_interval := INTERVAL '1 day';
        WHEN 'week' THEN bucket_interval := INTERVAL '1 week';
        WHEN 'month' THEN bucket_interval := INTERVAL '1 month';
        ELSE
            RAISE EXCEPTION 'Invalid bucket type. Must be hour, day, week, or month';
    END CASE;

    -- Check cache
    IF NOT p_force_refresh THEN
        cache_key := 'document_analytics_' || p_organization_id || '_' ||
                    EXTRACT(EPOCH FROM p_start_time) || '_' ||
                    EXTRACT(EPOCH FROM p_end_time) || '_' || p_bucket_type;

        SELECT cached_results INTO cached_results
        FROM analytics_cache
        WHERE cache_key = cache_key
          AND organization_id = p_organization_id
          AND expires_at > NOW()
          AND cache_type = 'document_analytics';

        IF cached_results IS NOT NULL THEN
            UPDATE analytics_cache
            SET hit_count = hit_count + 1,
                last_accessed_at = NOW()
            WHERE cache_key = cache_key;
            RETURN 0;
        END IF;
    END IF;

    -- Process each time bucket
    bucket_start := p_start_time;
    WHILE bucket_start < p_end_time LOOP
        bucket_end := LEAST(bucket_start + bucket_interval, p_end_time);

        INSERT INTO document_analytics_optimized (
            organization_id,
            time_bucket,
            bucket_type,
            total_documents,
            new_documents,
            processed_documents,
            processing_success_rate,
            document_type_counts,
            modality_counts,
            avg_quality_score,
            high_quality_documents,
            low_quality_documents,
            avg_processing_time_ms,
            processing_bottlenecks,
            avg_entities_extracted,
            avg_concepts_extracted,
            extraction_success_rates,
            total_storage_gb,
            avg_document_size_mb,
            storage_growth_rate,
            total_views,
            total_downloads,
            avg_views_per_document,
            processing_efficiency_score,
            storage_utilization_rate,
            data_freshness_at,
            updated_at
        )
        SELECT
            p_organization_id,
            bucket_start,
            p_bucket_type,

            -- Total documents up to this point
            (SELECT COUNT(*) FROM documents d
             WHERE d.organization_id = p_organization_id
               AND d.created_at <= bucket_end
               AND d.is_deleted = FALSE) as total_documents,

            -- New documents in this bucket
            COUNT(*) FILTER (WHERE d.created_at >= bucket_start AND d.created_at < bucket_end) as new_documents,

            -- Processed documents
            COUNT(*) FILTER (
                d.processing_completed_at >= bucket_start
                AND d.processing_completed_at < bucket_end
            ) as processed_documents,

            -- Processing success rate
            CASE
                WHEN COUNT(*) FILTER (
                    d.created_at >= bucket_start AND d.created_at < bucket_end
                ) = 0 THEN 0
                ELSE (COUNT(*) FILTER (
                    d.processing_status = 'indexed'
                    AND d.created_at >= bucket_start AND d.created_at < bucket_end
                )::DECIMAL / COUNT(*) FILTER (
                    d.created_at >= bucket_start AND d.created_at < bucket_end
                ))
            END as processing_success_rate,

            -- Document type breakdown
            COALESCE(
                jsonb_object_agg(d.file_type, type_counts.type_count)
                FILTER (WHERE d.file_type IS NOT NULL),
                '{}'::jsonb
            ) as document_type_counts,

            -- Modality breakdown
            COALESCE(
                jsonb_object_agg(d.document_modality, modality_counts.modality_count)
                FILTER (WHERE d.document_modality IS NOT NULL),
                '{"text": 0, "image": 0, "audio": 0, "video": 0}'::jsonb
            ) as modality_counts,

            -- Quality metrics
            AVG(d.quality_score) as avg_quality_score,
            COUNT(*) FILTER (WHERE d.quality_score > 0.8) as high_quality_documents,
            COUNT(*) FILTER (WHERE d.quality_score < 0.5) as low_quality_documents,

            -- Processing performance
            AVG(EXTRACT(EPOCH FROM (d.processing_completed_at - d.created_at)) * 1000) as avg_processing_time_ms,

            -- Processing bottlenecks
            COALESCE(bottleneck_analysis.bottleneck_data, '{}'::jsonb) as processing_bottlenecks,

            -- Extraction analytics
            COALESCE(extraction_metrics.avg_entities_per_doc, 0) as avg_entities_extracted,
            COALESCE(extraction_metrics.avg_concepts_per_doc, 0) as avg_concepts_extracted,
            COALESCE(extraction_metrics.extraction_success_rates, '{}'::jsonb) as extraction_success_rates,

            -- Storage analytics
            COALESCE(SUM(d.file_size_bytes) / (1024.0^3), 0) as total_storage_gb,
            COALESCE(AVG(d.file_size_bytes) / (1024.0^2), 0) as avg_document_size_mb,
            COALESCE(storage_growth.growth_rate, 0) as storage_growth_rate,

            -- Usage analytics
            COALESCE(usage_metrics.total_views, 0) as total_views,
            COALESCE(usage_metrics.total_downloads, 0) as total_downloads,
            COALESCE(usage_metrics.avg_views_per_doc, 0) as avg_views_per_document,

            -- Efficiency scores
            COALESCE(efficiency_scores.processing_efficiency, 0) as processing_efficiency_score,
            COALESCE(efficiency_scores.storage_utilization, 0) as storage_utilization_rate,

            NOW() as data_freshness_at,
            NOW() as updated_at

        FROM documents d
        LEFT JOIN LATERAL (
            SELECT file_type, COUNT(*) as type_count
            FROM documents d2
            WHERE d2.organization_id = p_organization_id
              AND d2.created_at >= bucket_start
              AND d2.created_at < bucket_end
              AND d2.is_deleted = FALSE
              AND d2.file_type IS NOT NULL
            GROUP BY d2.file_type
        ) type_counts ON true
        LEFT JOIN LATERAL (
            SELECT document_modality, COUNT(*) as modality_count
            FROM documents d3
            WHERE d3.organization_id = p_organization_id
              AND d3.created_at >= bucket_start
              AND d3.created_at < bucket_end
              AND d3.is_deleted = FALSE
              AND d3.document_modality IS NOT NULL
            GROUP BY d3.document_modality
        ) modality_counts ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_build_object(
                'processing_failures', COUNT(*) FILTER (WHERE processing_status = 'failed'),
                'processing_timeouts', COUNT(*) FILTER (WHERE processing_status = 'timeout'),
                'validation_errors', COUNT(*) FILTER (WHERE processing_status = 'validation_error')
            ) as bottleneck_data
            FROM documents d4
            WHERE d4.organization_id = p_organization_id
              AND d4.created_at >= bucket_start
              AND d4.created_at < bucket_end
              AND d4.is_deleted = FALSE
        ) bottleneck_analysis ON true
        LEFT JOIN LATERAL (
            SELECT
                AVG(entity_counts.entity_count) as avg_entities_per_doc,
                AVG(concept_counts.concept_count) as avg_concepts_per_doc,
                jsonb_build_object(
                    'entity_extraction', AVG(entity_counts.entity_count) FILTER (WHERE entity_counts.entity_count > 0),
                    'concept_extraction', AVG(concept_counts.concept_count) FILTER (WHERE concept_counts.concept_count > 0)
                ) as extraction_success_rates
            FROM (
                SELECT
                    de.document_id,
                    COUNT(de.entity_id) as entity_count
                FROM document_entities de
                JOIN documents d5 ON d5.id = de.document_id
                WHERE d5.organization_id = p_organization_id
                  AND d5.created_at >= bucket_start
                  AND d5.created_at < bucket_end
                GROUP BY de.document_id
            ) entity_counts
            FULL OUTER JOIN (
                SELECT
                    dc.document_id,
                    COUNT(dc.concept_id) as concept_count
                FROM document_concepts dc
                JOIN documents d6 ON d6.id = dc.document_id
                WHERE d6.organization_id = p_organization_id
                  AND d6.created_at >= bucket_start
                  AND d6.created_at < bucket_end
                GROUP BY dc.document_id
            ) concept_counts ON entity_counts.document_id = concept_counts.document_id
        ) extraction_metrics ON true
        LEFT JOIN LATERAL (
            SELECT
                CASE
                    WHEN previous_period.total_size = 0 THEN 0
                    ELSE (current_period.total_size - previous_period.total_size)::DECIMAL / previous_period.total_size
                END as growth_rate
            FROM (
                SELECT SUM(file_size_bytes) as total_size
                FROM documents d7
                WHERE d7.organization_id = p_organization_id
                  AND d7.created_at >= bucket_start
                  AND d7.created_at < bucket_end
                  AND d7.is_deleted = FALSE
            ) current_period
            CROSS JOIN (
                SELECT SUM(file_size_bytes) as total_size
                FROM documents d8
                WHERE d8.organization_id = p_organization_id
                  AND d8.created_at >= bucket_start - bucket_interval
                  AND d8.created_at < bucket_start
                  AND d8.is_deleted = FALSE
            ) previous_period
        ) storage_growth ON true
        LEFT JOIN LATERAL (
            SELECT
                SUM(usage_counts.view_count) as total_views,
                SUM(usage_counts.download_count) as total_downloads,
                AVG(usage_counts.view_count) as avg_views_per_doc
            FROM (
                SELECT
                    d9.id as document_id,
                    COALESCE(access_log.view_count, 0) as view_count,
                    COALESCE(access_log.download_count, 0) as download_count
                FROM documents d9
                LEFT JOIN LATERAL (
                    SELECT
                        document_id,
                        COUNT(*) FILTER (WHERE action = 'view') as view_count,
                        COUNT(*) FILTER (WHERE action = 'download') as download_count
                    FROM document_access_logs dal
                    WHERE dal.accessed_at >= bucket_start
                      AND dal.accessed_at < bucket_end
                    GROUP BY document_id
                ) access_log ON d9.id = access_log.document_id
                WHERE d9.organization_id = p_organization_id
                  AND d9.created_at <= bucket_end
                  AND d9.is_deleted = FALSE
            ) usage_counts
        ) usage_metrics ON true
        LEFT JOIN LATERAL (
            SELECT
                AVG(CASE
                    WHEN d10.processing_completed_at IS NOT NULL THEN
                        EXTRACT(EPOCH FROM (d10.processing_completed_at - d10.created_at))
                    ELSE NULL
                END) / 30000 as processing_efficiency, -- efficiency per 30 seconds
                SUM(d10.file_size_bytes) / (1024.0^3) / 100.0 as storage_utilization -- percentage of 100GB
            FROM documents d10
            WHERE d10.organization_id = p_organization_id
              AND d10.created_at <= bucket_end
              AND d10.is_deleted = FALSE
        ) efficiency_scores ON true
        WHERE d.organization_id = p_organization_id
          AND d.created_at <= bucket_end
          AND d.is_deleted = FALSE
        GROUP BY bucket_start
        ON CONFLICT (organization_id, time_bucket, bucket_type)
        DO UPDATE SET
            total_documents = EXCLUDED.total_documents,
            new_documents = EXCLUDED.new_documents,
            processed_documents = EXCLUDED.processed_documents,
            processing_success_rate = EXCLUDED.processing_success_rate,
            document_type_counts = EXCLUDED.document_type_counts,
            modality_counts = EXCLUDED.modality_counts,
            avg_quality_score = EXCLUDED.avg_quality_score,
            high_quality_documents = EXCLUDED.high_quality_documents,
            low_quality_documents = EXCLUDED.low_quality_documents,
            avg_processing_time_ms = EXCLUDED.avg_processing_time_ms,
            processing_bottlenecks = EXCLUDED.processing_bottlenecks,
            avg_entities_extracted = EXCLUDED.avg_entities_extracted,
            avg_concepts_extracted = EXCLUDED.avg_concepts_extracted,
            extraction_success_rates = EXCLUDED.extraction_success_rates,
            total_storage_gb = EXCLUDED.total_storage_gb,
            avg_document_size_mb = EXCLUDED.avg_document_size_mb,
            storage_growth_rate = EXCLUDED.storage_growth_rate,
            total_views = EXCLUDED.total_views,
            total_downloads = EXCLUDED.total_downloads,
            avg_views_per_document = EXCLUDED.avg_views_per_document,
            processing_efficiency_score = EXCLUDED.processing_efficiency_score,
            storage_utilization_rate = EXCLUDED.storage_utilization_rate,
            data_freshness_at = EXCLUDED.data_freshness_at,
            updated_at = EXCLUDED.updated_at;

        total_buckets_processed := total_buckets_processed + 1;
        bucket_start := bucket_end;
    END LOOP;

    -- Cache the results
    IF total_buckets_processed > 0 THEN
        INSERT INTO analytics_cache (
            organization_id,
            cache_key,
            cache_type,
            computation_parameters,
            cached_results,
            result_size_bytes,
            cache_ttl_seconds,
            computation_time_ms,
            expires_at
        ) VALUES (
            p_organization_id,
            cache_key,
            'document_analytics',
            jsonb_build_object(
                'start_time', p_start_time,
                'end_time', p_end_time,
                'bucket_type', p_bucket_type
            ),
            jsonb_build_object(
                'buckets_processed', total_buckets_processed,
                'computation_time_ms', EXTRACT(EPOCH FROM (NOW() - computation_start)) * 1000,
                'processed_at', NOW()
            ),
            1536,
            3600,
            EXTRACT(EPOCH FROM (NOW() - computation_start)) * 1000,
            NOW() + INTERVAL '1 hour'
        ) ON CONFLICT (cache_key, organization_id, cache_type)
        DO UPDATE SET
            cached_results = EXCLUDED.cached_results,
            computation_time_ms = EXCLUDED.computation_time_ms,
            last_accessed_at = NOW(),
            expires_at = EXCLUDED.expires_at;
    END IF;

    RETURN total_buckets_processed;
END;
$$ LANGUAGE plpgsql
SET work_mem = '256MB'
SET temp_file_limit = '4GB';

-- ============================================================================
-- USER INTERACTION ANALYTICS STORED PROCEDURES
-- ============================================================================

-- User interaction analytics with engagement tracking
CREATE OR REPLACE FUNCTION compute_user_interaction_analytics_aggregated(
    p_organization_id UUID,
    p_start_time TIMESTAMPTZ,
    p_end_time TIMESTAMPTZ,
    p_bucket_type VARCHAR(20) DEFAULT 'day',
    p_force_refresh BOOLEAN DEFAULT FALSE
) RETURNS INTEGER AS $$
DECLARE
    total_buckets_processed INTEGER := 0;
    bucket_start TIMESTAMPTZ;
    bucket_end TIMESTAMPTZ;
    bucket_interval INTERVAL;
    computation_start TIMESTAMPTZ := NOW();
    cache_key VARCHAR(255);
    cached_results JSONB;
BEGIN
    -- Input validation
    IF p_organization_id IS NULL OR p_start_time IS NULL OR p_end_time IS NULL THEN
        RAISE EXCEPTION 'Organization ID, start time, and end time are required';
    END IF;

    IF p_start_time >= p_end_time THEN
        RAISE EXCEPTION 'Start time must be before end time';
    END IF;

    CASE p_bucket_type
        WHEN 'hour' THEN bucket_interval := INTERVAL '1 hour';
        WHEN 'day' THEN bucket_interval := INTERVAL '1 day';
        WHEN 'week' THEN bucket_interval := INTERVAL '1 week';
        WHEN 'month' THEN bucket_interval := INTERVAL '1 month';
        ELSE
            RAISE EXCEPTION 'Invalid bucket type. Must be hour, day, week, or month';
    END CASE;

    -- Check cache
    IF NOT p_force_refresh THEN
        cache_key := 'user_interaction_analytics_' || p_organization_id || '_' ||
                    EXTRACT(EPOCH FROM p_start_time) || '_' ||
                    EXTRACT(EPOCH FROM p_end_time) || '_' || p_bucket_type;

        SELECT cached_results INTO cached_results
        FROM analytics_cache
        WHERE cache_key = cache_key
          AND organization_id = p_organization_id
          AND expires_at > NOW()
          AND cache_type = 'user_interaction_analytics';

        IF cached_results IS NOT NULL THEN
            UPDATE analytics_cache
            SET hit_count = hit_count + 1,
                last_accessed_at = NOW()
            WHERE cache_key = cache_key;
            RETURN 0;
        END IF;
    END IF;

    -- Process each time bucket
    bucket_start := p_start_time;
    WHILE bucket_start < p_end_time LOOP
        bucket_end := LEAST(bucket_start + bucket_interval, p_end_time);

        INSERT INTO user_interaction_analytics_optimized (
            organization_id,
            time_bucket,
            bucket_type,
            active_users,
            new_users,
            total_sessions,
            avg_session_duration_seconds,
            user_retention_rate,
            total_searches,
            unique_search_queries,
            avg_search_time_ms,
            search_success_rate,
            zero_result_search_rate,
            query_type_distribution,
            query_complexity_distribution,
            search_intent_distribution,
            avg_user_satisfaction_score,
            feedback_submission_rate,
            complaint_rate,
            user_engagement_score,
            feature_usage,
            advanced_feature_adoption_rate,
            avg_response_time_ms,
            error_rate,
            timeout_rate,
            user_role_distribution,
            user_experience_level_distribution,
            user_device_distribution,
            session_quality_score,
            search_effectiveness_score,
            data_freshness_at,
            updated_at
        )
        SELECT
            p_organization_id,
            bucket_start,
            p_bucket_type,

            -- User activity metrics
            COUNT(DISTINCT sq.user_id) FILTER (WHERE sq.created_at >= bucket_start AND sq.created_at < bucket_end) as active_users,
            COUNT(DISTINCT u.id) FILTER (WHERE u.created_at >= bucket_start AND u.created_at < bucket_end) as new_users,
            session_metrics.total_sessions,
            session_metrics.avg_session_duration,
            COALESCE(retention_metrics.retention_rate, 0) as user_retention_rate,

            -- Search analytics
            COUNT(*) FILTER (WHERE sq.created_at >= bucket_start AND sq.created_at < bucket_end) as total_searches,
            COUNT(DISTINCT sq.query_text) FILTER (WHERE sq.created_at >= bucket_start AND sq.created_at < bucket_end) as unique_search_queries,
            AVG(sq.total_time_ms) FILTER (WHERE sq.created_at >= bucket_start AND sq.created_at < bucket_end) as avg_search_time_ms,
            search_metrics.success_rate,
            search_metrics.zero_result_rate,

            -- Query distribution
            COALESCE(query_types.type_distribution, '{}'::jsonb) as query_type_distribution,
            COALESCE(complexity_levels.complexity_distribution, '{}'::jsonb) as query_complexity_distribution,
            COALESCE(intent_analysis.intent_distribution, '{}'::jsonb) as search_intent_distribution,

            -- User satisfaction metrics
            COALESCE(satisfaction_metrics.avg_satisfaction, 0) as avg_user_satisfaction_score,
            COALESCE(satisfaction_metrics.feedback_rate, 0) as feedback_submission_rate,
            COALESCE(satisfaction_metrics.complaint_rate, 0) as complaint_rate,
            COALESCE(engagement_analysis.engagement_score, 0) as user_engagement_score,

            -- Feature usage
            COALESCE(feature_usage.usage_data, '{}'::jsonb) as feature_usage,
            COALESCE(feature_adoption.adoption_rate, 0) as advanced_feature_adoption_rate,

            -- Performance metrics
            COALESCE(performance_metrics.avg_response_time, 0) as avg_response_time_ms,
            COALESCE(performance_metrics.error_rate, 0) as error_rate,
            COALESCE(performance_metrics.timeout_rate, 0) as timeout_rate,

            -- User demographics
            COALESCE(user_demographics.role_distribution, '{}'::jsonb) as user_role_distribution,
            COALESCE(user_demographics.experience_distribution, '{}'::jsonb) as user_experience_level_distribution,
            COALESCE(user_demographics.device_distribution, '{}'::jsonb) as user_device_distribution,

            -- Quality scores
            COALESCE(quality_scores.session_quality, 0) as session_quality_score,
            COALESCE(quality_scores.search_effectiveness, 0) as search_effectiveness_score,

            NOW() as data_freshness_at,
            NOW() as updated_at

        FROM search_queries sq
        CROSS JOIN LATERAL (
            SELECT
                COUNT(DISTINCT session_id) as total_sessions,
                AVG(session_duration_seconds) as avg_session_duration
            FROM user_sessions us
            WHERE us.organization_id = p_organization_id
              AND us.session_start >= bucket_start
              AND us.session_start < bucket_end
        ) session_metrics ON true
        LEFT JOIN LATERAL (
            SELECT
                CASE
                    WHEN previous_period.active_users = 0 THEN 0
                    ELSE (current_period.active_users::DECIMAL / previous_period.active_users)
                END as retention_rate
            FROM (
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM search_queries sq1
                WHERE sq1.organization_id = p_organization_id
                  AND sq1.created_at >= bucket_start
                  AND sq1.created_at < bucket_end
            ) current_period
            CROSS JOIN (
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM search_queries sq2
                WHERE sq2.organization_id = p_organization_id
                  AND sq2.created_at >= bucket_start - bucket_interval
                  AND sq2.created_at < bucket_start
            ) previous_period
        ) retention_metrics ON true
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) FILTER (WHERE result_count > 0)::DECIMAL / COUNT(*) as success_rate,
                COUNT(*) FILTER (WHERE result_count = 0)::DECIMAL / COUNT(*) as zero_result_rate
            FROM search_queries sq3
            WHERE sq3.organization_id = p_organization_id
              AND sq3.created_at >= bucket_start
              AND sq3.created_at < bucket_end
        ) search_metrics ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_object_agg(query_type, type_count) as type_distribution
            FROM (
                SELECT
                    CASE
                        WHEN query_text LIKE '%graph%' THEN 'graph'
                        WHEN query_text LIKE '%semantic%' THEN 'semantic'
                        WHEN query_text ILIKE '%"%*' OR query_text ILIKE '%\"%' THEN 'keyword'
                        ELSE 'hybrid'
                    END as query_type,
                    COUNT(*) as type_count
                FROM search_queries sq4
                WHERE sq4.organization_id = p_organization_id
                  AND sq4.created_at >= bucket_start
                  AND sq4.created_at < bucket_end
                GROUP BY query_type
            ) query_type_analysis
        ) query_types ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_object_agg(complexity_level, level_count) as complexity_distribution
            FROM (
                SELECT
                    CASE
                        WHEN LENGTH(query_text) < 20 THEN 'simple'
                        WHEN LENGTH(query_text) < 100 THEN 'medium'
                        ELSE 'complex'
                    END as complexity_level,
                    COUNT(*) as level_count
                FROM search_queries sq5
                WHERE sq5.organization_id = p_organization_id
                  AND sq5.created_at >= bucket_start
                  AND sq5.created_at < bucket_end
                GROUP BY complexity_level
            ) complexity_analysis
        ) complexity_levels ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_object_agg(intent_type, intent_count) as intent_distribution
            FROM (
                SELECT
                    CASE
                        WHEN query_text ILIKE '%what%' OR query_text ILIKE '%who%' OR query_text ILIKE '%where%' THEN 'factual'
                        WHEN query_text ILIKE '%why%' OR query_text ILIKE '%how%' THEN 'explanatory'
                        WHEN query_text ILIKE '%compare%' OR query_text ILIKE '%versus%' THEN 'comparative'
                        WHEN query_text ILIKE '%list%' OR query_text ILIKE '%show me%' THEN 'enumerative'
                        ELSE 'unknown'
                    END as intent_type,
                    COUNT(*) as intent_count
                FROM search_queries sq6
                WHERE sq6.organization_id = p_organization_id
                  AND sq6.created_at >= bucket_start
                  AND sq6.created_at < bucket_end
                GROUP BY intent_type
            ) intent_analysis
        ) intent_analysis ON true
        LEFT JOIN LATERAL (
            SELECT
                AVG(rating) as avg_satisfaction,
                COUNT(*) FILTER (WHERE rating IS NOT NULL)::DECIMAL / COUNT(*) as feedback_rate,
                COUNT(*) FILTER (WHERE rating <= 2)::DECIMAL / COUNT(*) as complaint_rate
            FROM user_feedback uf
            WHERE uf.organization_id = p_organization_id
              AND uf.created_at >= bucket_start
              AND uf.created_at < bucket_end
        ) satisfaction_metrics ON true
        LEFT JOIN LATERAL (
            SELECT
                AVG(session_quality_score) as engagement_score
            FROM user_sessions us2
            WHERE us2.organization_id = p_organization_id
              AND us2.session_start >= bucket_start
              AND us2.session_start < bucket_end
        ) engagement_analysis ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_object_agg(feature_name, usage_count) as usage_data
            FROM (
                SELECT
                    uf.feature_name,
                    COUNT(*) as usage_count
                FROM user_feature_usage uf
                WHERE uf.organization_id = p_organization_id
                  AND uf.used_at >= bucket_start
                  AND uf.used_at < bucket_end
                GROUP BY uf.feature_name
            ) feature_analysis
        ) feature_usage ON true
        LEFT JOIN LATERAL (
            SELECT
                COUNT(DISTINCT uf2.user_id FILTER (WHERE uf2.feature_name IN (
                    'advanced_search', 'graph_visualization', 'custom_reports', 'api_access'
                )))::DECIMAL / COUNT(DISTINCT sq7.user_id) as adoption_rate
            FROM user_feature_usage uf2
            JOIN search_queries sq7 ON sq7.user_id = uf2.user_id
            WHERE uf2.organization_id = p_organization_id
              AND uf2.used_at >= bucket_start
              AND uf2.used_at < bucket_end
              AND sq7.created_at >= bucket_start
              AND sq7.created_at < bucket_end
        ) feature_adoption ON true
        LEFT JOIN LATERAL (
            SELECT
                AVG(total_time_ms) as avg_response_time,
                COUNT(*) FILTER (WHERE error_code IS NOT NULL)::DECIMAL / COUNT(*) as error_rate,
                COUNT(*) FILTER (WHERE total_time_ms > 30000)::DECIMAL / COUNT(*) as timeout_rate
            FROM search_queries sq8
            WHERE sq8.organization_id = p_organization_id
              AND sq8.created_at >= bucket_start
              AND sq8.created_at < bucket_end
        ) performance_metrics ON true
        LEFT JOIN LATERAL (
            SELECT
                jsonb_object_agg(role, role_count) as role_distribution,
                jsonb_object_agg(experience_level, exp_count) as experience_distribution,
                jsonb_object_agg(device_type, device_count) as device_distribution
            FROM (
                SELECT u2.role as role, COUNT(*) as role_count
                FROM users u2
                WHERE u2.organization_id = p_organization_id
                GROUP BY u2.role
            ) role_data
            FULL OUTER JOIN (
                SELECT u3.experience_level, COUNT(*) as exp_count
                FROM users u3
                WHERE u3.organization_id = p_organization_id
                GROUP BY u3.experience_level
            ) exp_data ON true
            FULL OUTER JOIN (
                SELECT udl.device_type, COUNT(*) as device_count
                FROM user_device_logs udl
                WHERE udl.organization_id = p_organization_id
                  AND udl.last_seen >= bucket_start
                  AND udl.last_seen < bucket_end
                GROUP BY udl.device_type
            ) device_data ON true
        ) user_demographics ON true
        LEFT JOIN LATERAL (
            SELECT
                AVG(session_quality_score) as session_quality,
                AVG(search_effectiveness_score) as search_effectiveness
            FROM user_sessions us3
            WHERE us3.organization_id = p_organization_id
              AND us3.session_start >= bucket_start
              AND us3.session_start < bucket_end
        ) quality_scores ON true
        WHERE sq.organization_id = p_organization_id
          AND sq.created_at <= bucket_end
        GROUP BY bucket_start
        ON CONFLICT (organization_id, time_bucket, bucket_type)
        DO UPDATE SET
            active_users = EXCLUDED.active_users,
            new_users = EXCLUDED.new_users,
            total_sessions = EXCLUDED.total_sessions,
            avg_session_duration_seconds = EXCLUDED.avg_session_duration_seconds,
            user_retention_rate = EXCLUDED.user_retention_rate,
            total_searches = EXCLUDED.total_searches,
            unique_search_queries = EXCLUDED.unique_search_queries,
            avg_search_time_ms = EXCLUDED.avg_search_time_ms,
            search_success_rate = EXCLUDED.search_success_rate,
            zero_result_search_rate = EXCLUDED.zero_result_search_rate,
            query_type_distribution = EXCLUDED.query_type_distribution,
            query_complexity_distribution = EXCLUDED.query_complexity_distribution,
            search_intent_distribution = EXCLUDED.search_intent_distribution,
            avg_user_satisfaction_score = EXCLUDED.avg_user_satisfaction_score,
            feedback_submission_rate = EXCLUDED.feedback_submission_rate,
            complaint_rate = EXCLUDED.complaint_rate,
            user_engagement_score = EXCLUDED.user_engagement_score,
            feature_usage = EXCLUDED.feature_usage,
            advanced_feature_adoption_rate = EXCLUDED.advanced_feature_adoption_rate,
            avg_response_time_ms = EXCLUDED.avg_response_time_ms,
            error_rate = EXCLUDED.error_rate,
            timeout_rate = EXCLUDED.timeout_rate,
            user_role_distribution = EXCLUDED.user_role_distribution,
            user_experience_level_distribution = EXCLUDED.user_experience_level_distribution,
            user_device_distribution = EXCLUDED.user_device_distribution,
            session_quality_score = EXCLUDED.session_quality_score,
            search_effectiveness_score = EXCLUDED.search_effectiveness_score,
            data_freshness_at = EXCLUDED.data_freshness_at,
            updated_at = EXCLUDED.updated_at;

        total_buckets_processed := total_buckets_processed + 1;
        bucket_start := bucket_end;
    END LOOP;

    -- Cache the results
    IF total_buckets_processed > 0 THEN
        INSERT INTO analytics_cache (
            organization_id,
            cache_key,
            cache_type,
            computation_parameters,
            cached_results,
            result_size_bytes,
            cache_ttl_seconds,
            computation_time_ms,
            expires_at
        ) VALUES (
            p_organization_id,
            cache_key,
            'user_interaction_analytics',
            jsonb_build_object(
                'start_time', p_start_time,
                'end_time', p_end_time,
                'bucket_type', p_bucket_type
            ),
            jsonb_build_object(
                'buckets_processed', total_buckets_processed,
                'computation_time_ms', EXTRACT(EPOCH FROM (NOW() - computation_start)) * 1000,
                'processed_at', NOW()
            ),
            2048,
            3600,
            EXTRACT(EPOCH FROM (NOW() - computation_start)) * 1000,
            NOW() + INTERVAL '1 hour'
        ) ON CONFLICT (cache_key, organization_id, cache_type)
        DO UPDATE SET
            cached_results = EXCLUDED.cached_results,
            computation_time_ms = EXCLUDED.computation_time_ms,
            last_accessed_at = NOW(),
            expires_at = EXCLUDED.expires_at;
    END IF;

    RETURN total_buckets_processed;
END;
$$ LANGUAGE plpgsql
SET work_mem = '256MB'
SET temp_file_limit = '4GB';

-- ============================================================================
-- MAINTENANCE AND OPTIMIZATION PROCEDURES
-- ============================================================================

-- Automated analytics computation for all organizations
CREATE OR REPLACE FUNCTION compute_all_organization_analytics(
    p_bucket_type VARCHAR(20) DEFAULT 'day',
    p_hours_back INTEGER DEFAULT 24
) RETURNS INTEGER AS $$
DECLARE
    organizations_processed INTEGER := 0;
    org_record RECORD;
    end_time TIMESTAMPTZ := NOW();
    start_time TIMESTAMPTZ := NOW() - (p_hours_back || ' hours')::INTERVAL;
    total_computations INTEGER := 0;
BEGIN
    FOR org_record IN SELECT id FROM organizations WHERE is_active = TRUE LOOP
        BEGIN
            -- Compute entity analytics
            PERFORM compute_entity_analytics_aggregated(
                org_record.id,
                start_time,
                end_time,
                p_bucket_type,
                FALSE
            );

            -- Compute relationship analytics
            PERFORM compute_relationship_analytics_aggregated(
                org_record.id,
                start_time,
                end_time,
                p_bucket_type,
                FALSE
            );

            -- Compute document analytics
            PERFORM compute_document_analytics_aggregated(
                org_record.id,
                start_time,
                end_time,
                p_bucket_type,
                FALSE
            );

            -- Compute user interaction analytics
            PERFORM compute_user_interaction_analytics_aggregated(
                org_record.id,
                start_time,
                end_time,
                p_bucket_type,
                FALSE
            );

            -- Compute graph metrics (less frequently)
            IF p_bucket_type IN ('week', 'month') THEN
                PERFORM compute_graph_metrics_optimized(
                    org_record.id,
                    TRUE, -- compute centrality
                    TRUE, -- compute communities
                    TRUE, -- compute components
                    FALSE -- don't force refresh
                );
            END IF;

            organizations_processed := organizations_processed + 1;
            total_computations := total_computations + 5; -- 5 analytics types per organization

        EXCEPTION WHEN OTHERS THEN
            RAISE WARNING 'Failed to compute analytics for organization %: %', org_record.id, SQLERRM;
        END;
    END LOOP;

    RETURN organizations_processed;
END;
$$ LANGUAGE plpgsql;