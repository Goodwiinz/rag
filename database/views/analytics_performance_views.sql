-- Knowledge Graph Analytics Dashboard Performance Views
-- Optimized views and materialized views for high-performance analytics queries

-- ============================================================================
-- HIGH-PERFORMANCE REAL-TIME VIEWS
-- ============================================================================

-- Optimized real-time dashboard metrics materialized view
CREATE MATERIALIZED VIEW real_time_dashboard_metrics_optimized AS
WITH org_stats AS (
    SELECT
        o.id as organization_id,
        o.name as organization_name,
        o.current_storage_gb,
        o.storage_limit_gb,
        o.subscription_tier
    FROM organizations o
    WHERE o.is_active = TRUE
),
entity_metrics AS (
    SELECT
        e.organization_id,
        COUNT(*) as total_entities,
        COUNT(*) FILTER (WHERE e.created_at >= CURRENT_DATE) as new_entities_today,
        COUNT(*) FILTER (WHERE e.extraction_confidence > 0.8) as high_quality_entities,
        COUNT(*) FILTER (WHERE e.extraction_confidence < 0.5) as low_quality_entities,
        AVG(e.extraction_confidence) as avg_entity_confidence,
        COUNT(DISTINCT e.entity_type) as unique_entity_types
    FROM entities e
    WHERE e.is_deleted = FALSE
    GROUP BY e.organization_id
),
relationship_metrics AS (
    SELECT
        er.organization_id,
        COUNT(*) as total_relationships,
        COUNT(*) FILTER (WHERE er.created_at >= CURRENT_DATE) as new_relationships_today,
        COUNT(*) FILTER (WHERE er.confidence > 0.8) as high_confidence_relationships,
        AVG(er.confidence) as avg_relationship_confidence,
        COUNT(*) FILTER (WHERE er.is_bidirectional = TRUE) as bidirectional_relationships,
        CASE
            WHEN COUNT(*) = 0 THEN 0
            ELSE (COUNT(*) FILTER (WHERE er.is_bidirectional = TRUE))::DECIMAL / COUNT(*)
        END as bidirectional_percentage
    FROM entity_relationships er
    GROUP BY er.organization_id
),
document_metrics AS (
    SELECT
        d.organization_id,
        COUNT(*) as total_documents,
        COUNT(*) FILTER (WHERE d.processing_completed_at >= CURRENT_DATE) as documents_processed_today,
        COUNT(*) FILTER (WHERE d.processing_status = 'indexed') as indexed_documents,
        AVG(d.quality_score) as avg_document_quality,
        COUNT(*) FILTER (WHERE d.quality_score > 0.8) as high_quality_documents,
        SUM(d.file_size_bytes) / (1024.0^3) as total_storage_used,
        CASE
            WHEN COUNT(*) = 0 THEN 0
            ELSE COUNT(*) FILTER (WHERE d.processing_status = 'indexed')::DECIMAL / COUNT(*)
        END as processing_success_rate
    FROM documents d
    WHERE d.is_deleted = FALSE
    GROUP BY d.organization_id
),
user_metrics AS (
    SELECT
        sq.organization_id,
        COUNT(DISTINCT sq.user_id) as active_users_today,
        COUNT(*) as total_searches_today,
        AVG(sq.total_time_ms) as avg_search_response_time,
        COUNT(*) FILTER (WHERE sq.result_count > 0)::DECIMAL / COUNT(*) as search_success_rate,
        COUNT(DISTINCT sq.query_text) as unique_searches_today
    FROM search_queries sq
    WHERE sq.created_at >= CURRENT_DATE
    GROUP BY sq.organization_id
),
performance_metrics AS (
    SELECT
        organization_id,
        AVG(avg_response_time_ms) as avg_system_response_time,
        AVG(error_rate) as avg_error_rate,
        AVG(timeout_rate) as avg_timeout_rate
    FROM user_interaction_analytics_optimized uia
    WHERE uia.time_bucket >= CURRENT_DATE - INTERVAL '7 days'
      AND uia.bucket_type = 'day'
    GROUP BY organization_id
)
SELECT
    os.organization_id,
    os.organization_name,
    os.subscription_tier,

    -- Entity metrics
    COALESCE(em.total_entities, 0) as total_entities,
    COALESCE(em.new_entities_today, 0) as new_entities_today,
    COALESCE(em.avg_entity_confidence, 0) as avg_entity_confidence,
    COALESCE(em.high_quality_entities, 0) as high_quality_entities,
    COALESCE(em.low_quality_entities, 0) as low_quality_entities,
    COALESCE(em.unique_entity_types, 0) as unique_entity_types,

    -- Relationship metrics
    COALESCE(rm.total_relationships, 0) as total_relationships,
    COALESCE(rm.new_relationships_today, 0) as new_relationships_today,
    COALESCE(rm.avg_relationship_confidence, 0) as avg_relationship_confidence,
    COALESCE(rm.bidirectional_percentage, 0) as bidirectional_percentage,

    -- Document metrics
    COALESCE(dm.total_documents, 0) as total_documents,
    COALESCE(dm.documents_processed_today, 0) as documents_processed_today,
    COALESCE(dm.avg_document_quality, 0) as avg_document_quality,
    COALESCE(dm.processing_success_rate, 0) as processing_success_rate,
    COALESCE(dm.total_storage_used, 0) as total_storage_used,
    COALESCE(os.current_storage_gb, 0) as reported_storage_used,

    -- User metrics
    COALESCE(um.active_users_today, 0) as active_users_today,
    COALESCE(um.total_searches_today, 0) as total_searches_today,
    COALESCE(um.avg_search_response_time, 0) as avg_search_response_time,
    COALESCE(um.search_success_rate, 0) as search_success_rate,
    COALESCE(um.unique_searches_today, 0) as unique_searches_today,

    -- Performance metrics
    COALESCE(pm.avg_system_response_time, 0) as avg_system_response_time,
    COALESCE(pm.avg_error_rate, 0) as avg_error_rate,
    COALESCE(pm.avg_timeout_rate, 0) as avg_timeout_rate,

    -- Calculated metrics
    CASE
        WHEN COALESCE(dm.total_documents, 0) = 0 THEN 0
        ELSE COALESCE(em.total_entities, 0)::DECIMAL / COALESCE(dm.total_documents, 1)
    END as entities_per_document_ratio,

    CASE
        WHEN COALESCE(em.total_entities, 0) = 0 THEN 0
        ELSE COALESCE(rm.total_relationships, 0)::DECIMAL / COALESCE(em.total_entities, 1)
    END as relationships_per_entity_ratio,

    -- Storage utilization
    CASE
        WHEN os.storage_limit_gb = 0 THEN 0
        ELSE (COALESCE(dm.total_storage_used, 0) / os.storage_limit_gb) * 100
    END as storage_utilization_percentage,

    -- System health score (0-1)
    LEAST(1.0, GREATEST(0,
        (COALESCE(em.avg_entity_confidence, 0) * 0.3 +
         COALESCE(rm.avg_relationship_confidence, 0) * 0.2 +
         COALESCE(dm.avg_document_quality, 0) * 0.2 +
         COALESCE(um.search_success_rate, 0) * 0.2 +
         (1 - COALESCE(pm.avg_error_rate, 0)) * 0.1)
    )) as system_health_score,

    -- Performance grade
    CASE
        WHEN COALESCE(pm.avg_system_response_time, 0) <= 1000 THEN 'excellent'
        WHEN COALESCE(pm.avg_system_response_time, 0) <= 2000 THEN 'good'
        WHEN COALESCE(pm.avg_system_response_time, 0) <= 5000 THEN 'fair'
        ELSE 'poor'
    END as performance_grade,

    -- Data freshness
    NOW() as last_updated,
    EXTRACT(EPOCH FROM (NOW() - GREATEST(
        COALESCE((SELECT MAX(created_at) FROM entities e2 WHERE e2.organization_id = os.organization_id), NOW() - INTERVAL '1 year'),
        COALESCE((SELECT MAX(created_at) FROM entity_relationships er2 WHERE er2.organization_id = os.organization_id), NOW() - INTERVAL '1 year'),
        COALESCE((SELECT MAX(created_at) FROM documents d2 WHERE d2.organization_id = os.organization_id), NOW() - INTERVAL '1 year')
    ))) as data_freshness_seconds

FROM org_stats os
LEFT JOIN entity_metrics em ON os.organization_id = em.organization_id
LEFT JOIN relationship_metrics rm ON os.organization_id = rm.organization_id
LEFT JOIN document_metrics dm ON os.organization_id = dm.organization_id
LEFT JOIN user_metrics um ON os.organization_id = um.organization_id
LEFT JOIN performance_metrics pm ON os.organization_id = pm.organization_id;

-- Create unique index for efficient refreshing
CREATE UNIQUE INDEX idx_real_time_dashboard_metrics_optimized_org
    ON real_time_dashboard_metrics_optimized(organization_id);

-- Create partial indexes for common filters
CREATE INDEX idx_real_time_dashboard_metrics_health
    ON real_time_dashboard_metrics_optimized(system_health_score DESC)
    WHERE system_health_score > 0.5;

CREATE INDEX idx_real_time_dashboard_metrics_storage
    ON real_time_dashboard_metrics_optimized(storage_utilization_percentage DESC)
    WHERE storage_utilization_percentage > 80;

-- Function to refresh the materialized view
CREATE OR REPLACE FUNCTION refresh_real_time_dashboard_metrics_optimized()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY real_time_dashboard_metrics_optimized;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ENTITY ANALYTICS PERFORMANCE VIEWS
-- ============================================================================

-- Entity growth trends optimized view
CREATE MATERIALIZED VIEW entity_growth_trends_optimized AS
WITH time_series AS (
    SELECT
        organization_id,
        time_bucket,
        bucket_type,
        total_entities,
        new_entities,
        entity_growth_rate,
        LAG(total_entities) OVER (
            PARTITION BY organization_id, bucket_type
            ORDER BY time_bucket
        ) as previous_total_entities,
        LAG(new_entities) OVER (
            PARTITION BY organization_id, bucket_type
            ORDER BY time_bucket
        ) as previous_new_entities,
        LAG(entity_growth_rate) OVER (
            PARTITION BY organization_id, bucket_type
            ORDER BY time_bucket
        ) as previous_growth_rate
    FROM entity_analytics_optimized
    WHERE bucket_type IN ('day', 'week', 'month')
),
growth_calculations AS (
    SELECT
        organization_id,
        time_bucket,
        bucket_type,
        total_entities,
        new_entities,
        entity_growth_rate,
        previous_total_entities,
        previous_new_entities,
        previous_growth_rate,
        -- Growth trend analysis
        CASE
            WHEN entity_growth_rate > previous_growth_rate THEN 'accelerating'
            WHEN entity_growth_rate < previous_growth_rate THEN 'decelerating'
            ELSE 'stable'
        END as growth_trend,
        -- Weekly growth average
        AVG(entity_growth_rate) OVER (
            PARTITION BY organization_id, bucket_type
            ORDER BY time_bucket
            RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
        ) as avg_growth_rate_7d,
        -- Monthly growth average
        AVG(entity_growth_rate) OVER (
            PARTITION BY organization_id, bucket_type
            ORDER BY time_bucket
            RANGE BETWEEN INTERVAL '30 days' PRECEDING AND CURRENT ROW
        ) as avg_growth_rate_30d
    FROM time_series
)
SELECT * FROM growth_calculations;

CREATE INDEX idx_entity_growth_trends_org_time
    ON entity_growth_trends_optimized(organization_id, time_bucket DESC);

CREATE INDEX idx_entity_growth_trends_growth_rate
    ON entity_growth_trends_optimized(entity_growth_rate DESC, time_bucket DESC);

-- Entity type distribution optimized view
CREATE MATERIALIZED VIEW entity_type_distribution_optimized AS
WITH entity_type_stats AS (
    SELECT
        organization_id,
        time_bucket,
        bucket_type,
        entity_type_counts,
        -- Extract entity type counts and calculate percentages
        (SELECT jsonb_object_keys(entity_type_counts)) as entity_type,
        (entity_type_counts -> (SELECT jsonb_object_keys(entity_type_counts)))::INTEGER as type_count
    FROM entity_analytics_optimized
    WHERE entity_type_counts != '{}'::jsonb
),
type_calculations AS (
    SELECT
        organization_id,
        time_bucket,
        bucket_type,
        entity_type,
        type_count,
        SUM(type_count) OVER (PARTITION BY organization_id, time_bucket, bucket_type) as total_entities_in_bucket,
        -- Calculate percentage
        (type_count::DECIMAL / SUM(type_count) OVER (PARTITION BY organization_id, time_bucket, bucket_type)) * 100 as type_percentage,
        -- Rank by count within bucket
        RANK() OVER (PARTITION BY organization_id, time_bucket, bucket_type ORDER BY type_count DESC) as type_rank,
        -- 7-day trend for this type
        LAG(type_count, 7) OVER (PARTITION BY organization_id, entity_type, bucket_type ORDER BY time_bucket) as count_7d_ago,
        -- Growth rate for this entity type
        CASE
            WHEN LAG(type_count, 7) OVER (PARTITION BY organization_id, entity_type, bucket_type ORDER BY time_bucket) = 0 THEN NULL
            ELSE (type_count - LAG(type_count, 7) OVER (PARTITION BY organization_id, entity_type, bucket_type ORDER BY time_bucket))::DECIMAL /
                 LAG(type_count, 7) OVER (PARTITION BY organization_id, entity_type, bucket_type ORDER BY time_bucket)
        END as type_growth_rate
    FROM entity_type_stats
)
SELECT
    organization_id,
    time_bucket,
    bucket_type,
    entity_type,
    type_count,
    type_percentage,
    type_rank,
    count_7d_ago,
    type_growth_rate,
    -- Trend classification
    CASE
        WHEN type_growth_rate > 0.1 THEN 'rapid_growth'
        WHEN type_growth_rate > 0.05 THEN 'moderate_growth'
        WHEN type_growth_rate > -0.05 THEN 'stable'
        WHEN type_growth_rate > -0.1 THEN 'declining'
        ELSE 'rapid_decline'
    END as type_trend_classification
FROM type_calculations
WHERE type_rank <= 10; -- Top 10 entity types per bucket

CREATE INDEX idx_entity_type_distribution_org_time
    ON entity_type_distribution_optimized(organization_id, time_bucket DESC);

CREATE INDEX idx_entity_type_distribution_type
    ON entity_type_distribution_optimized(entity_type, time_bucket DESC);

-- ============================================================================
-- RELATIONSHIP ANALYTICS PERFORMANCE VIEWS
-- ============================================================================

-- Relationship strength analysis optimized view
CREATE MATERIALIZED VIEW relationship_strength_analysis_optimized AS
WITH relationship_stats AS (
    SELECT
        organization_id,
        time_bucket,
        bucket_type,
        total_relationships,
        avg_relationship_strength,
        avg_connections_per_entity,
        hub_entities,
        bridge_entities,
        bidirectional_percentage,
        relationship_strength_distribution,
        -- Extract strength categories
        (relationship_strength_distribution->>'high')::INTEGER as high_strength_count,
        (relationship_strength_distribution->>'medium')::INTEGER as medium_strength_count,
        (relationship_strength_distribution->>'low')::INTEGER as low_strength_count
    FROM relationship_analytics_optimized
    WHERE bucket_type IN ('day', 'week', 'month')
),
strength_calculations AS (
    SELECT
        organization_id,
        time_bucket,
        bucket_type,
        total_relationships,
        avg_relationship_strength,
        avg_connections_per_entity,
        hub_entities,
        bridge_entities,
        bidirectional_percentage,
        high_strength_count,
        medium_strength_count,
        low_strength_count,
        -- Calculate percentages
        CASE
            WHEN total_relationships = 0 THEN 0
            ELSE (high_strength_count::DECIMAL / total_relationships) * 100
        END as high_strength_percentage,
        CASE
            WHEN total_relationships = 0 THEN 0
            ELSE (medium_strength_count::DECIMAL / total_relationships) * 100
        END as medium_strength_percentage,
        CASE
            WHEN total_relationships = 0 THEN 0
            ELSE (low_strength_count::DECIMAL / total_relationships) * 100
        END as low_strength_percentage,
        -- Connectivity health score
        LEAST(1.0, GREATEST(0,
            (avg_relationship_strength * 0.5 +
             bidirectional_percentage * 0.3 +
             CASE
                 WHEN avg_connections_per_entity >= 3 THEN 1.0
                 WHEN avg_connections_per_entity >= 2 THEN 0.8
                 WHEN avg_connections_per_entity >= 1 THEN 0.6
                 ELSE 0.3
             END * 0.2)
        )) as connectivity_health_score,
        -- 7-day moving averages
        AVG(avg_relationship_strength) OVER (
            PARTITION BY organization_id, bucket_type
            ORDER BY time_bucket
            RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
        ) as avg_strength_7d,
        AVG(avg_connections_per_entity) OVER (
            PARTITION BY organization_id, bucket_type
            ORDER BY time_bucket
            RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
        ) as avg_connections_7d
    FROM relationship_stats
)
SELECT * FROM strength_calculations;

CREATE INDEX idx_relationship_strength_org_time
    ON relationship_strength_analysis_optimized(organization_id, time_bucket DESC);

CREATE INDEX idx_relationship_strength_health
    ON relationship_strength_analysis_optimized(connectivity_health_score DESC, time_bucket DESC);

-- ============================================================================
-- DOCUMENT PROCESSING PERFORMANCE VIEWS
-- ============================================================================

-- Document processing performance optimized view
CREATE MATERIALIZED VIEW document_processing_performance_optimized AS
WITH processing_stats AS (
    SELECT
        organization_id,
        time_bucket,
        bucket_type,
        total_documents,
        processed_documents,
        processing_success_rate,
        avg_processing_time_ms,
        avg_quality_score,
        processing_bottlenecks,
        total_storage_gb,
        avg_document_size_mb,
        storage_growth_rate,
        processing_efficiency_score,
        storage_utilization_rate
    FROM document_analytics_optimized
    WHERE bucket_type IN ('hour', 'day', 'week')
),
performance_calculations AS (
    SELECT
        organization_id,
        time_bucket,
        bucket_type,
        total_documents,
        processed_documents,
        processing_success_rate,
        avg_processing_time_ms,
        avg_quality_score,
        processing_bottlenecks,
        total_storage_gb,
        avg_document_size_mb,
        storage_growth_rate,
        processing_efficiency_score,
        storage_utilization_rate,
        -- Performance categorization
        CASE
            WHEN processing_success_rate >= 0.95 THEN 'excellent'
            WHEN processing_success_rate >= 0.85 THEN 'good'
            WHEN processing_success_rate >= 0.70 THEN 'fair'
            ELSE 'poor'
        END as processing_performance_grade,
        -- Speed categorization
        CASE
            WHEN avg_processing_time_ms <= 5000 THEN 'fast'
            WHEN avg_processing_time_ms <= 15000 THEN 'normal'
            WHEN avg_processing_time_ms <= 30000 THEN 'slow'
            ELSE 'very_slow'
        END as processing_speed_category,
        -- Quality categorization
        CASE
            WHEN avg_quality_score >= 0.9 THEN 'excellent'
            WHEN avg_quality_score >= 0.8 THEN 'good'
            WHEN avg_quality_score >= 0.7 THEN 'fair'
            ELSE 'poor'
        END as quality_grade,
        -- Storage efficiency
        CASE
            WHEN storage_utilization_rate <= 0.5 THEN 'efficient'
            WHEN storage_utilization_rate <= 0.8 THEN 'normal'
            WHEN storage_utilization_rate <= 0.95 THEN 'high'
            ELSE 'critical'
        END as storage_efficiency_category,
        -- Overall processing score (0-100)
        LEAST(100, GREATEST(0,
            (processing_success_rate * 40 +
             (1 - LEAST(1.0, avg_processing_time_ms / 30000)) * 30 +
             avg_quality_score * 20 +
             (1 - storage_utilization_rate) * 10)
        )) as overall_processing_score,
        -- 7-day trends
        LAG(processing_success_rate, 7) OVER (
            PARTITION BY organization_id, bucket_type
            ORDER BY time_bucket
        ) as success_rate_7d_ago,
        LAG(avg_processing_time_ms, 7) OVER (
            PARTITION BY organization_id, bucket_type
            ORDER BY time_bucket
        ) as processing_time_7d_ago,
        -- Trend analysis
        CASE
            WHEN processing_success_rate > LAG(processing_success_rate, 7) OVER (
                PARTITION BY organization_id, bucket_type
                ORDER BY time_bucket
            ) THEN 'improving'
            WHEN processing_success_rate < LAG(processing_success_rate, 7) OVER (
                PARTITION BY organization_id, bucket_type
                ORDER BY time_bucket
            ) THEN 'declining'
            ELSE 'stable'
        END as processing_trend
    FROM processing_stats
)
SELECT * FROM performance_calculations;

CREATE INDEX idx_document_processing_org_time
    ON document_processing_performance_optimized(organization_id, time_bucket DESC);

CREATE INDEX idx_document_processing_score
    ON document_processing_performance_optimized(overall_processing_score DESC, time_bucket DESC);

-- ============================================================================
-- USER ENGAGEMENT PERFORMANCE VIEWS
-- ============================================================================

-- User engagement metrics optimized view
CREATE MATERIALIZED VIEW user_engagement_metrics_optimized AS
WITH engagement_stats AS (
    SELECT
        organization_id,
        time_bucket,
        bucket_type,
        active_users,
        new_users,
        total_sessions,
        avg_session_duration_seconds,
        total_searches,
        unique_search_queries,
        avg_search_time_ms,
        search_success_rate,
        zero_result_search_rate,
        avg_user_satisfaction_score,
        user_engagement_score,
        avg_response_time_ms,
        error_rate,
        timeout_rate,
        session_quality_score,
        search_effectiveness_score
    FROM user_interaction_analytics_optimized
    WHERE bucket_type IN ('day', 'week', 'month')
),
engagement_calculations AS (
    SELECT
        organization_id,
        time_bucket,
        bucket_type,
        active_users,
        new_users,
        total_sessions,
        avg_session_duration_seconds,
        total_searches,
        unique_search_queries,
        avg_search_time_ms,
        search_success_rate,
        zero_result_search_rate,
        avg_user_satisfaction_score,
        user_engagement_score,
        avg_response_time_ms,
        error_rate,
        timeout_rate,
        session_quality_score,
        search_effectiveness_score,
        -- Engagement categorization
        CASE
            WHEN avg_user_satisfaction_score >= 4.5 THEN 'very_high'
            WHEN avg_user_satisfaction_score >= 3.5 THEN 'high'
            WHEN avg_user_satisfaction_score >= 2.5 THEN 'medium'
            ELSE 'low'
        END as satisfaction_level,
        -- Activity intensity
        CASE
            WHEN total_sessions >= 100 THEN 'very_high'
            WHEN total_sessions >= 50 THEN 'high'
            WHEN total_sessions >= 20 THEN 'medium'
            ELSE 'low'
        END as activity_level,
        -- Response performance
        CASE
            WHEN avg_response_time_ms <= 1000 THEN 'excellent'
            WHEN avg_response_time_ms <= 2000 THEN 'good'
            WHEN avg_response_time_ms <= 5000 THEN 'fair'
            ELSE 'poor'
        END as response_performance,
        -- Search effectiveness
        CASE
            WHEN search_success_rate >= 0.9 THEN 'excellent'
            WHEN search_success_rate >= 0.8 THEN 'good'
            WHEN search_success_rate >= 0.7 THEN 'fair'
            ELSE 'poor'
        END as search_effectiveness_level,
        -- User retention calculation
        CASE
            WHEN active_users = 0 THEN 0
            ELSE (active_users - new_users)::DECIMAL / NULLIF(
                LAG(active_users, 7) OVER (PARTITION BY organization_id, bucket_type ORDER BY time_bucket), 0
            )
        END as user_retention_rate,
        -- Session quality score
        LEAST(100, GREATEST(0,
            (session_quality_score * 50 +
             search_effectiveness_score * 30 +
             (1 - error_rate) * 20)
        )) as overall_session_score,
        -- Engagement velocity (change in engagement)
        user_engagement_score - LAG(user_engagement_score, 7) OVER (
            PARTITION BY organization_id, bucket_type
            ORDER BY time_bucket
        ) as engagement_velocity,
        -- 7-day averages
        AVG(avg_user_satisfaction_score) OVER (
            PARTITION BY organization_id, bucket_type
            ORDER BY time_bucket
            RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
        ) as avg_satisfaction_7d,
        AVG(search_success_rate) OVER (
            PARTITION BY organization_id, bucket_type
            ORDER BY time_bucket
            RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW
        ) as avg_search_success_7d
    FROM engagement_stats
)
SELECT * FROM engagement_calculations;

CREATE INDEX idx_user_engagement_org_time
    ON user_engagement_metrics_optimized(organization_id, time_bucket DESC);

CREATE INDEX idx_user_engagement_score
    ON user_engagement_metrics_optimized(overall_session_score DESC, time_bucket DESC);

-- ============================================================================
-- SYSTEM HEALTH MONITORING VIEW
-- ============================================================================

-- System health dashboard optimized view
CREATE MATERIALIZED VIEW system_health_dashboard_optimized AS
WITH health_metrics AS (
    SELECT
        os.organization_id,
        os.organization_name,
        os.subscription_tier,
        rtm.*,
        -- Recent trends
        entity_trend.recent_growth_rate as entity_growth_trend,
        document_trend.processing_trend as document_processing_trend,
        user_trend.engagement_trend as user_engagement_trend,
        relationship_trend.connectivity_trend as relationship_connectivity_trend
    FROM organizations os
    JOIN real_time_dashboard_metrics_optimized rtm ON os.id = rtm.organization_id
    LEFT JOIN LATERAL (
        SELECT entity_growth_rate as recent_growth_rate
        FROM entity_analytics_optimized ega
        WHERE ega.organization_id = os.id
          AND ega.bucket_type = 'day'
          AND ega.time_bucket >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY ega.time_bucket DESC
        LIMIT 1
    ) entity_trend ON true
    LEFT JOIN LATERAL (
        SELECT processing_success_rate as processing_trend
        FROM document_analytics_optimized dga
        WHERE dga.organization_id = os.id
          AND dga.bucket_type = 'day'
          AND dga.time_bucket >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY dga.time_bucket DESC
        LIMIT 1
    ) document_trend ON true
    LEFT JOIN LATERAL (
        SELECT avg_user_satisfaction_score as engagement_trend
        FROM user_interaction_analytics_optimized uia
        WHERE uia.organization_id = os.id
          AND uia.bucket_type = 'day'
          AND uia.time_bucket >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY uia.time_bucket DESC
        LIMIT 1
    ) user_trend ON true
    LEFT JOIN LATERAL (
        SELECT avg_relationship_strength as connectivity_trend
        FROM relationship_analytics_optimized ra
        WHERE ra.organization_id = os.id
          AND ra.bucket_type = 'day'
          AND ra.time_bucket >= CURRENT_DATE - INTERVAL '7 days'
        ORDER BY ra.time_bucket DESC
        LIMIT 1
    ) relationship_trend ON true
),
health_calculations AS (
    SELECT
        *,
        -- Overall health status
        CASE
            WHEN system_health_score >= 0.9 THEN 'excellent'
            WHEN system_health_score >= 0.7 THEN 'good'
            WHEN system_health_score >= 0.5 THEN 'fair'
            ELSE 'poor'
        END as overall_health_status,
        -- Storage status
        CASE
            WHEN storage_utilization_percentage >= 90 THEN 'critical'
            WHEN storage_utilization_percentage >= 80 THEN 'warning'
            WHEN storage_utilization_percentage >= 60 THEN 'caution'
            ELSE 'healthy'
        END as storage_status,
        -- Performance status
        CASE
            WHEN avg_system_response_time <= 1000 THEN 'excellent'
            WHEN avg_system_response_time <= 2000 THEN 'good'
            WHEN avg_system_response_time <= 5000 THEN 'fair'
            ELSE 'poor'
        END as performance_status,
        -- Quality status
        CASE
            WHEN avg_entity_confidence >= 0.8 AND avg_document_quality >= 0.8 THEN 'excellent'
            WHEN avg_entity_confidence >= 0.7 AND avg_document_quality >= 0.7 THEN 'good'
            WHEN avg_entity_confidence >= 0.6 AND avg_document_quality >= 0.6 THEN 'fair'
            ELSE 'poor'
        END as quality_status,
        -- Activity status
        CASE
            WHEN active_users_today >= 10 THEN 'very_active'
            WHEN active_users_today >= 5 THEN 'active'
            WHEN active_users_today >= 1 THEN 'minimal'
            ELSE 'inactive'
        END as activity_status,
        -- Growth status
        CASE
            WHEN new_entities_today >= 10 AND new_relationships_today >= 10 THEN 'rapid_growth'
            WHEN new_entities_today >= 5 AND new_relationships_today >= 5 THEN 'moderate_growth'
            WHEN new_entities_today >= 1 OR new_relationships_today >= 1 THEN 'slow_growth'
            ELSE 'no_growth'
        END as growth_status,
        -- Alert level
        CASE
            WHEN storage_utilization_percentage >= 90 OR system_health_score < 0.5 THEN 'critical'
            WHEN storage_utilization_percentage >= 80 OR system_health_score < 0.7 THEN 'warning'
            WHEN storage_utilization_percentage >= 70 OR system_health_score < 0.8 THEN 'info'
            ELSE 'normal'
        END as alert_level,
        -- Action items
        CASE
            WHEN storage_utilization_percentage >= 90 THEN ARRAY['immediate_storage_cleanup_required']
            WHEN storage_utilization_percentage >= 80 THEN ARRAY['storage_cleanup_recommended']
            WHEN avg_system_response_time > 5000 THEN ARRAY['performance_optimization_required']
            WHEN system_health_score < 0.7 THEN ARRAY['quality_improvement_needed']
            WHEN active_users_today = 0 THEN ARRAY['user_engagement_needed']
            ELSE ARRAY[]::TEXT[]
        END as recommended_actions
    FROM health_metrics
)
SELECT * FROM health_calculations;

CREATE INDEX idx_system_health_org
    ON system_health_dashboard_optimized(organization_id);

CREATE INDEX idx_system_health_alert_level
    ON system_health_dashboard_optimized(alert_level, system_health_score);

CREATE INDEX idx_system_health_status
    ON system_health_dashboard_optimized(overall_health_status, storage_status);

-- ============================================================================
-- REFRESH FUNCTIONS FOR ALL MATERIALIZED VIEWS
-- ============================================================================

-- Function to refresh all analytics materialized views
CREATE OR REPLACE FUNCTION refresh_all_analytics_views()
RETURNS TABLE(
    view_name TEXT,
    refresh_status TEXT,
    refresh_time_ms INTEGER
) AS $$
DECLARE
    view_record RECORD;
    start_time TIMESTAMPTZ;
    end_time TIMESTAMPTZ;
BEGIN
    -- List of all materialized views to refresh
    FOR view_record IN VALUES
        ('real_time_dashboard_metrics_optimized'),
        ('entity_growth_trends_optimized'),
        ('entity_type_distribution_optimized'),
        ('relationship_strength_analysis_optimized'),
        ('document_processing_performance_optimized'),
        ('user_engagement_metrics_optimized'),
        ('system_health_dashboard_optimized')
    LOOP
        start_time := NOW();

        BEGIN
            EXECUTE 'REFRESH MATERIALIZED VIEW CONCURRENTLY ' || view_record.column1;
            end_time := NOW();

            RETURN QUERY SELECT
                view_record.column1 as view_name,
                'success' as refresh_status,
                EXTRACT(EPOCH FROM (end_time - start_time)) * 1000 as refresh_time_ms;

        EXCEPTION WHEN OTHERS THEN
            end_time := NOW();

            RETURN QUERY SELECT
                view_record.column1 as view_name,
                'error: ' || SQLERRM as refresh_status,
                EXTRACT(EPOCH FROM (end_time - start_time)) * 1000 as refresh_time_ms;
        END;
    END LOOP;

    RETURN;
END;
$$ LANGUAGE plpgsql;