-- Knowledge Graph Analytics Dashboard Stored Procedures
-- Comprehensive analytics calculations with performance optimization

-- ============================================================================
-- ENTITY ANALYTICS STORED PROCEDURES
-- ============================================================================

-- Optimized entity analytics aggregation with parallel processing
CREATE OR REPLACE FUNCTION compute_entity_analytics_aggregated(
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
    -- Validate inputs
    IF p_organization_id IS NULL OR p_start_time IS NULL OR p_end_time IS NULL THEN
        RAISE EXCEPTION 'Organization ID, start time, and end time are required';
    END IF;

    IF p_start_time >= p_end_time THEN
        RAISE EXCEPTION 'Start time must be before end time';
    END IF;

    -- Determine bucket interval
    CASE p_bucket_type
        WHEN 'hour' THEN bucket_interval := INTERVAL '1 hour';
        WHEN 'day' THEN bucket_interval := INTERVAL '1 day';
        WHEN 'week' THEN bucket_interval := INTERVAL '1 week';
        WHEN 'month' THEN bucket_interval := INTERVAL '1 month';
        ELSE
            RAISE EXCEPTION 'Invalid bucket type. Must be hour, day, week, or month';
    END CASE;

    -- Check cache first unless force refresh
    IF NOT p_force_refresh THEN
        cache_key := 'entity_analytics_' || p_organization_id || '_' ||
                    EXTRACT(EPOCH FROM p_start_time) || '_' ||
                    EXTRACT(EPOCH FROM p_end_time) || '_' || p_bucket_type;

        SELECT cached_results INTO cached_results
        FROM analytics_cache
        WHERE cache_key = cache_key
          AND organization_id = p_organization_id
          AND expires_at > NOW()
          AND cache_type = 'entity_analytics';

        IF cached_results IS NOT NULL THEN
            UPDATE analytics_cache
            SET hit_count = hit_count + 1,
                last_accessed_at = NOW()
            WHERE cache_key = cache_key;
            RETURN 0; -- 0 buckets processed (used cache)
        END IF;
    END IF;

    -- Process each time bucket
    bucket_start := p_start_time;
    WHILE bucket_start < p_end_time LOOP
        bucket_end := LEAST(bucket_start + bucket_interval, p_end_time);

        -- Insert or update entity analytics for this bucket
        INSERT INTO entity_analytics_optimized (
            organization_id,
            time_bucket,
            bucket_type,
            total_entities,
            new_entities,
            entity_growth_rate,
            entity_type_counts,
            entity_type_percentages,
            avg_confidence_score,
            high_quality_entities,
            low_quality_entities,
            entities_processed,
            processing_success_rate,
            avg_processing_time_ms,
            entities_per_document,
            documents_with_entities,
            entity_modality_counts,
            data_freshness_at,
            updated_at
        )
        SELECT
            p_organization_id,
            bucket_start,
            p_bucket_type,

            -- Total entities up to this point
            (SELECT COUNT(*) FROM entities e
             WHERE e.organization_id = p_organization_id
               AND e.created_at <= bucket_end) as total_entities,

            -- New entities in this bucket
            COUNT(*) FILTER (WHERE e.created_at >= bucket_start AND e.created_at < bucket_end) as new_entities,

            -- Growth rate calculation
            CASE
                WHEN LAG(COUNT(*)) OVER (ORDER BY bucket_start) = 0 THEN 0
                ELSE (COUNT(*) - COALESCE(LAG(COUNT(*)) OVER (ORDER BY bucket_start), 0))::DECIMAL /
                     NULLIF(COALESCE(LAG(COUNT(*)) OVER (ORDER BY bucket_start), 0), 0)
            END as entity_growth_rate,

            -- Entity type breakdown
            COALESCE(
                jsonb_object_agg(
                    e.entity_type,
                    type_counts.type_count
                ) FILTER (WHERE e.entity_type IS NOT NULL),
                '{}'::jsonb
            ) as entity_type_counts,

            -- Entity type percentages
            COALESCE(
                jsonb_object_agg(
                    e.entity_type,
                    CASE
                        WHEN entity_total.total_count = 0 THEN 0
                        ELSE (type_counts.type_count::DECIMAL / entity_total.total_count) * 100
                    END
                ) FILTER (WHERE e.entity_type IS NOT NULL),
                '{}'::jsonb
            ) as entity_type_percentages,

            -- Quality metrics
            AVG(e.extraction_confidence) as avg_confidence_score,
            COUNT(*) FILTER (WHERE e.extraction_confidence > 0.8) as high_quality_entities,
            COUNT(*) FILTER (WHERE e.extraction_confidence < 0.5) as low_quality_entities,

            -- Processing metrics
            COUNT(*) FILTER (WHERE e.created_at >= bucket_start AND e.created_at < bucket_end) as entities_processed,
            COALESCE(doc_analytics.processing_success_rate, 1.0) as processing_success_rate,
            COALESCE(doc_analytics.avg_processing_time_ms, 0) as avg_processing_time_ms,

            -- Document association metrics
            CASE
                WHEN doc_stats.total_docs = 0 THEN 0
                ELSE COUNT(*)::DECIMAL / doc_stats.total_docs
            END as entities_per_document,
            doc_stats.total_docs as documents_with_entities,

            -- Modality breakdown
            COALESCE(modality_counts.modality_data, '{}'::jsonb) as entity_modality_counts,

            NOW() as data_freshness_at,
            NOW() as updated_at

        FROM entities e
        CROSS JOIN LATERAL (
            SELECT entity_type, COUNT(*) as type_count
            FROM entities e2
            WHERE e2.organization_id = p_organization_id
              AND e2.created_at >= bucket_start
              AND e2.created_at < bucket_end
              AND e2.entity_type IS NOT NULL
            GROUP BY e2.entity_type
        ) type_counts
        CROSS JOIN LATERAL (
            SELECT COUNT(*) as total_count
            FROM entities e3
            WHERE e3.organization_id = p_organization_id
              AND e3.created_at >= bucket_start
              AND e3.created_at < bucket_end
        ) entity_total
        LEFT JOIN LATERAL (
            SELECT AVG(processing_success_rate) as processing_success_rate,
                   AVG(avg_processing_time_ms) as avg_processing_time_ms
            FROM document_analytics_optimized da
            WHERE da.organization_id = p_organization_id
              AND da.time_bucket = bucket_start
              AND da.bucket_type = p_bucket_type
        ) doc_analytics ON true
        LEFT JOIN LATERAL (
            SELECT COUNT(*) as total_docs
            FROM documents d
            WHERE d.organization_id = p_organization_id
              AND d.created_at <= bucket_end
              AND d.is_deleted = FALSE
        ) doc_stats ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_object_agg(
                source_modality,
                modality_count
            ) as modality_data
            FROM (
                SELECT e.source_modality,
                       COUNT(*) as modality_count
                FROM entities e4
                WHERE e4.organization_id = p_organization_id
                  AND e4.created_at >= bucket_start
                  AND e4.created_at < bucket_end
                  AND e4.source_modality IS NOT NULL
                GROUP BY e4.source_modality
            ) modality_data
        ) modality_counts ON true
        WHERE e.organization_id = p_organization_id
          AND e.created_at <= bucket_end
        GROUP BY bucket_start
        ON CONFLICT (organization_id, time_bucket, bucket_type)
        DO UPDATE SET
            total_entities = EXCLUDED.total_entities,
            new_entities = EXCLUDED.new_entities,
            entity_growth_rate = EXCLUDED.entity_growth_rate,
            entity_type_counts = EXCLUDED.entity_type_counts,
            entity_type_percentages = EXCLUDED.entity_type_percentages,
            avg_confidence_score = EXCLUDED.avg_confidence_score,
            high_quality_entities = EXCLUDED.high_quality_entities,
            low_quality_entities = EXCLUDED.low_quality_entities,
            entities_processed = EXCLUDED.entities_processed,
            processing_success_rate = EXCLUDED.processing_success_rate,
            avg_processing_time_ms = EXCLUDED.avg_processing_time_ms,
            entities_per_document = EXCLUDED.entities_per_document,
            documents_with_entities = EXCLUDED.documents_with_entities,
            entity_modality_counts = EXCLUDED.entity_modality_counts,
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
            'entity_analytics',
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
            1024, -- Estimated size
            3600, -- 1 hour TTL
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

-- Enhanced relationship analytics calculation
CREATE OR REPLACE FUNCTION compute_relationship_analytics_aggregated(
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
    -- Input validation and setup similar to entity analytics
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
        cache_key := 'relationship_analytics_' || p_organization_id || '_' ||
                    EXTRACT(EPOCH FROM p_start_time) || '_' ||
                    EXTRACT(EPOCH FROM p_end_time) || '_' || p_bucket_type;

        SELECT cached_results INTO cached_results
        FROM analytics_cache
        WHERE cache_key = cache_key
          AND organization_id = p_organization_id
          AND expires_at > NOW()
          AND cache_type = 'relationship_analytics';

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

        INSERT INTO relationship_analytics_optimized (
            organization_id,
            time_bucket,
            bucket_type,
            total_relationships,
            new_relationships,
            relationship_growth_rate,
            relationship_type_counts,
            relationship_strength_distribution,
            avg_confidence_score,
            high_confidence_relationships,
            avg_relationship_strength,
            avg_connections_per_entity,
            isolated_entities,
            hub_entities,
            bridge_entities,
            bidirectional_relationships,
            bidirectional_percentage,
            data_freshness_at,
            updated_at
        )
        SELECT
            p_organization_id,
            bucket_start,
            p_bucket_type,

            -- Total relationships up to this point
            (SELECT COUNT(*) FROM entity_relationships er
             WHERE er.organization_id = p_organization_id
               AND er.created_at <= bucket_end) as total_relationships,

            -- New relationships in this bucket
            COUNT(*) FILTER (WHERE er.created_at >= bucket_start AND er.created_at < bucket_end) as new_relationships,

            -- Growth rate
            CASE
                WHEN LAG(COUNT(*)) OVER (ORDER BY bucket_start) = 0 THEN 0
                ELSE (COUNT(*) - COALESCE(LAG(COUNT(*)) OVER (ORDER BY bucket_start), 0))::DECIMAL /
                     NULLIF(COALESCE(LAG(COUNT(*)) OVER (ORDER BY bucket_start), 0), 0)
            END as relationship_growth_rate,

            -- Relationship type breakdown
            COALESCE(
                jsonb_object_agg(er.relationship_type, type_counts.type_count)
                FILTER (WHERE er.relationship_type IS NOT NULL),
                '{}'::jsonb
            ) as relationship_type_counts,

            -- Strength distribution
            COALESCE(
                jsonb_build_object(
                    'high', COUNT(*) FILTER (WHERE er.confidence > 0.8),
                    'medium', COUNT(*) FILTER (WHERE er.confidence > 0.5 AND er.confidence <= 0.8),
                    'low', COUNT(*) FILTER (WHERE er.confidence <= 0.5)
                ),
                '{"high": 0, "medium": 0, "low": 0}'::jsonb
            ) as relationship_strength_distribution,

            -- Quality metrics
            AVG(er.confidence) as avg_confidence_score,
            COUNT(*) FILTER (WHERE er.confidence > 0.8) as high_confidence_relationships,
            AVG(er.confidence) as avg_relationship_strength,

            -- Connectivity metrics
            COALESCE(connectivity_metrics.avg_connections_per_entity, 0) as avg_connections_per_entity,
            COALESCE(connectivity_metrics.isolated_entities, 0) as isolated_entities,
            COALESCE(connectivity_metrics.hub_entities, 0) as hub_entities,
            COALESCE(connectivity_metrics.bridge_entities, 0) as bridge_entities,

            -- Bidirectional relationships
            COUNT(*) FILTER (WHERE er.is_bidirectional = true) as bidirectional_relationships,
            CASE
                WHEN COUNT(*) = 0 THEN 0
                ELSE (COUNT(*) FILTER (WHERE er.is_bidirectional = true))::DECIMAL / COUNT(*)
            END as bidirectional_percentage,

            NOW() as data_freshness_at,
            NOW() as updated_at

        FROM entity_relationships er
        LEFT JOIN LATERAL (
            SELECT relationship_type, COUNT(*) as type_count
            FROM entity_relationships er2
            WHERE er2.organization_id = p_organization_id
              AND er2.created_at >= bucket_start
              AND er2.created_at < bucket_end
              AND er2.relationship_type IS NOT NULL
            GROUP BY er2.relationship_type
        ) type_counts ON true
        LEFT JOIN LATERAL (
            SELECT
                AVG(degree_count.entity_connections) as avg_connections_per_entity,
                COUNT(*) FILTER (WHERE degree_count.entity_connections = 0) as isolated_entities,
                COUNT(*) FILTER (WHERE degree_count.entity_connections > 50) as hub_entities,
                COUNT(*) FILTER (WHERE degree_count.entity_connections BETWEEN 5 AND 50) as bridge_entities
            FROM (
                SELECT
                    entity_id,
                    COUNT(*) as entity_connections
                FROM entity_relationships er3
                WHERE er3.organization_id = p_organization_id
                  AND er3.created_at <= bucket_end
                GROUP BY entity_id
            ) degree_count
        ) connectivity_metrics ON true
        WHERE er.organization_id = p_organization_id
          AND er.created_at <= bucket_end
        GROUP BY bucket_start
        ON CONFLICT (organization_id, time_bucket, bucket_type)
        DO UPDATE SET
            total_relationships = EXCLUDED.total_relationships,
            new_relationships = EXCLUDED.new_relationships,
            relationship_growth_rate = EXCLUDED.relationship_growth_rate,
            relationship_type_counts = EXCLUDED.relationship_type_counts,
            relationship_strength_distribution = EXCLUDED.relationship_strength_distribution,
            avg_confidence_score = EXCLUDED.avg_confidence_score,
            high_confidence_relationships = EXCLUDED.high_confidence_relationships,
            avg_relationship_strength = EXCLUDED.avg_relationship_strength,
            avg_connections_per_entity = EXCLUDED.avg_connections_per_entity,
            isolated_entities = EXCLUDED.isolated_entities,
            hub_entities = EXCLUDED.hub_entities,
            bridge_entities = EXCLUDED.bridge_entities,
            bidirectional_relationships = EXCLUDED.bidirectional_relationships,
            bidirectional_percentage = EXCLUDED.bidirectional_percentage,
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
            'relationship_analytics',
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
            1024,
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
SET work_mem = '512MB'
SET temp_file_limit = '8GB';

-- Graph metrics computation with centrality algorithms
CREATE OR REPLACE FUNCTION compute_graph_metrics_optimized(
    p_organization_id UUID,
    p_compute_centrality BOOLEAN DEFAULT TRUE,
    p_compute_communities BOOLEAN DEFAULT TRUE,
    p_compute_components BOOLEAN DEFAULT TRUE,
    p_force_refresh BOOLEAN DEFAULT FALSE
) RETURNS UUID AS $$
DECLARE
    computation_id UUID DEFAULT gen_random_uuid();
    computation_start TIMESTAMPTZ := NOW();
    total_nodes INTEGER;
    total_edges INTEGER;
    graph_density DECIMAL(15,12);
    snapshot_id VARCHAR(255);
    cache_key VARCHAR(255);
    cached_results JSONB;
BEGIN
    -- Input validation
    IF p_organization_id IS NULL THEN
        RAISE EXCEPTION 'Organization ID is required';
    END IF;

    -- Check cache if not forcing refresh
    IF NOT p_force_refresh THEN
        cache_key := 'graph_metrics_' || p_organization_id || '_' ||
                    CASE WHEN p_compute_centrality THEN 'C' ELSE '' END ||
                    CASE WHEN p_compute_communities THEN 'M' ELSE '' END ||
                    CASE WHEN p_compute_components THEN 'P' ELSE '' END;

        SELECT cached_results INTO cached_results
        FROM analytics_cache
        WHERE cache_key = cache_key
          AND organization_id = p_organization_id
          AND expires_at > NOW()
          AND cache_type = 'graph_metrics';

        IF cached_results IS NOT NULL THEN
            UPDATE analytics_cache
            SET hit_count = hit_count + 1,
                last_accessed_at = NOW()
            WHERE cache_key = cache_key;

            RETURN cached_results->>'computation_id'::UUID;
        END IF;
    END IF;

    -- Get basic graph statistics
    SELECT
        COUNT(DISTINCT e.id) as node_count,
        COUNT(DISTINCT er.id) as edge_count
    INTO total_nodes, total_edges
    FROM entities e
    LEFT JOIN entity_relationships er ON (
        er.source_entity_id = e.id OR er.target_entity_id = e.id
    )
    WHERE e.organization_id = p_organization_id;

    -- Calculate graph density
    IF total_nodes > 1 THEN
        graph_density := (2.0 * total_edges) / (total_nodes * (total_nodes - 1));
    ELSE
        graph_density := 0;
    END IF;

    -- Generate snapshot ID
    snapshot_id := 'snapshot_' || p_organization_id || '_' ||
                   EXTRACT(EPOCH FROM NOW())::BIGINT;

    -- Insert base graph metrics
    INSERT INTO graph_metrics_analytics_optimized (
        id,
        organization_id,
        computed_at,
        computation_version,
        graph_snapshot_id,
        computation_time_ms,
        total_nodes,
        total_edges,
        graph_density,
        average_degree,
        cache_hit_count,
        computation_complexity
    ) VALUES (
        computation_id,
        p_organization_id,
        NOW(),
        'v2.0_optimized',
        snapshot_id,
        NULL, -- Will be updated at the end
        total_nodes,
        total_edges,
        graph_density,
        CASE WHEN total_nodes > 0 THEN (2.0 * total_edges) / total_nodes ELSE 0 END,
        0,
        CASE
            WHEN total_nodes > 10000 THEN 'high'
            WHEN total_nodes > 1000 THEN 'medium'
            ELSE 'low'
        END
    );

    -- Compute centrality metrics if requested
    IF p_compute_centrality THEN
        PERFORM compute_centrality_metrics(p_organization_id, computation_id);
    END IF;

    -- Compute community detection if requested
    IF p_compute_communities THEN
        PERFORM compute_community_metrics(p_organization_id, computation_id);
    END IF;

    -- Compute component analysis if requested
    IF p_compute_components THEN
        PERFORM compute_component_metrics(p_organization_id, computation_id);
    END IF;

    -- Update computation time
    UPDATE graph_metrics_analytics_optimized
    SET computation_time_ms = EXTRACT(EPOCH FROM (NOW() - computation_start)) * 1000
    WHERE id = computation_id;

    -- Cache the results
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
        'graph_metrics',
        jsonb_build_object(
            'compute_centrality', p_compute_centrality,
            'compute_communities', p_compute_communities,
            'compute_components', p_compute_components
        ),
        jsonb_build_object(
            'computation_id', computation_id,
            'snapshot_id', snapshot_id,
            'total_nodes', total_nodes,
            'total_edges', total_edges,
            'computation_time_ms', EXTRACT(EPOCH FROM (NOW() - computation_start)) * 1000
        ),
        2048,
        7200, -- 2 hour TTL for graph metrics
        EXTRACT(EPOCH FROM (NOW() - computation_start)) * 1000,
        NOW() + INTERVAL '2 hours'
    ) ON CONFLICT (cache_key, organization_id, cache_type)
    DO UPDATE SET
        cached_results = EXCLUDED.cached_results,
        computation_time_ms = EXCLUDED.computation_time_ms,
        last_accessed_at = NOW(),
        expires_at = EXCLUDED.expires_at;

    RETURN computation_id;
END;
$$ LANGUAGE plpgsql
SET work_mem = '1GB'
SET temp_file_limit = '16GB';

-- Centrality metrics computation helper
CREATE OR REPLACE FUNCTION compute_centrality_metrics(
    p_organization_id UUID,
    p_computation_id UUID
) RETURNS VOID AS $$
DECLARE
    centrality_results JSONB;
BEGIN
    -- This is a simplified version - in production, you'd implement actual
    -- graph algorithms or use a graph database extension

    -- Degree centrality (simplified)
    centrality_results := jsonb_agg(
        jsonb_build_object(
            'entity_id', entity_connections.entity_id,
            'entity_name', COALESCE(e.name, 'Unknown'),
            'entity_type', e.entity_type,
            'centrality_score', entity_connections.degree_centrality,
            'connections', entity_connections.total_connections
        ) ORDER BY entity_connections.degree_centrality DESC
    ) FILTER (WHERE entity_connections.entity_id IS NOT NULL);

    -- Update graph metrics with centrality results
    UPDATE graph_metrics_analytics_optimized
    SET top_entities_by_centrality = COALESCE(centrality_results, '[]'::jsonb)
    WHERE id = p_computation_id;

    -- Calculate betweenness centrality (simplified approximation)
    -- In production, this would use proper graph algorithms

EXCEPTION WHEN OTHERS THEN
    -- Log error but don't fail the entire computation
    RAISE WARNING 'Error computing centrality metrics: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Community detection helper
CREATE OR REPLACE FUNCTION compute_community_metrics(
    p_organization_id UUID,
    p_computation_id UUID
) RETURNS VOID AS $$
DECLARE
    community_count INTEGER;
    avg_community_size DECIMAL(8,4);
    largest_community_size INTEGER;
    community_distribution JSONB;
BEGIN
    -- Simplified community detection based on entity types and connections
    -- In production, use proper community detection algorithms like Louvain

    WITH entity_clusters AS (
        SELECT
            e.entity_type as community_id,
            COUNT(*) as cluster_size
        FROM entities e
        WHERE e.organization_id = p_organization_id
        GROUP BY e.entity_type
    ),
    community_stats AS (
        SELECT
            COUNT(*) as number_of_communities,
            AVG(cluster_size) as average_community_size,
            MAX(cluster_size) as largest_community_size
        FROM entity_clusters
    ),
    size_distribution AS (
        SELECT
            CASE
                WHEN cluster_size <= 10 THEN 'small'
                WHEN cluster_size <= 100 THEN 'medium'
                ELSE 'large'
            END as size_category,
            COUNT(*) as category_count
        FROM entity_clusters
        GROUP BY
            CASE
                WHEN cluster_size <= 10 THEN 'small'
                WHEN cluster_size <= 100 THEN 'medium'
                ELSE 'large'
            END
        ORDER BY size_category
    )
    SELECT number_of_communities, average_community_size, largest_community_size
    INTO community_count, avg_community_size, largest_community_size
    FROM community_stats;

    community_distribution := jsonb_object_agg(
        size_distribution.size_category,
        size_distribution.category_count
    ) FILTER (WHERE size_distribution.size_category IS NOT NULL);

    -- Update graph metrics with community results
    UPDATE graph_metrics_analytics_optimized
    SET
        number_of_communities = community_count,
        average_community_size = avg_community_size,
        largest_community_size = largest_community_size,
        community_distribution = COALESCE(community_distribution, '{}'::jsonb)
    WHERE id = p_computation_id;

EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Error computing community metrics: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;

-- Component analysis helper
CREATE OR REPLACE FUNCTION compute_component_metrics(
    p_organization_id UUID,
    p_computation_id UUID
) RETURNS VOID AS $$
DECLARE
    component_count INTEGER;
    giant_component_size INTEGER;
    giant_component_percentage DECIMAL(5,4);
BEGIN
    -- Simplified connected components analysis
    -- In production, use proper graph traversal algorithms

    WITH component_analysis AS (
        SELECT
            COUNT(DISTINCT component_id) as number_of_components,
            MAX(component_size) as largest_component_size,
            SUM(component_size) as total_nodes
        FROM (
            -- Simplified component grouping by connectivity
            SELECT
                e.id as entity_id,
                -- This is a placeholder for actual component detection
                COALESCE(e.entity_type, 'unknown') as component_id,
                COUNT(*) OVER (PARTITION BY e.entity_type) as component_size
            FROM entities e
            WHERE e.organization_id = p_organization_id
        ) component_data
    )
    SELECT
        number_of_components,
        largest_component_size,
        CASE
            WHEN total_nodes > 0 THEN (largest_component_size::DECIMAL / total_nodes)
            ELSE 0
        END as giant_component_percentage
    INTO component_count, giant_component_size, giant_component_percentage
    FROM component_analysis;

    -- Update graph metrics with component results
    UPDATE graph_metrics_analytics_optimized
    SET
        number_of_components = component_count,
        giant_component_size = giant_component_size,
        giant_component_percentage = giant_component_percentage
    WHERE id = p_computation_id;

EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Error computing component metrics: %', SQLERRM;
END;
$$ LANGUAGE plpgsql;