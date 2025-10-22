-- Knowledge Graph Analytics Dashboard Database Triggers
-- Automated data maintenance, validation, and analytics updates

-- ============================================================================
-- ENTITY CHANGE TRIGGERS
-- ============================================================================

-- Enhanced entity change notification trigger
CREATE OR REPLACE FUNCTION trigger_entity_analytics_update()
RETURNS TRIGGER AS $$
DECLARE
    notification_payload JSONB;
    analytics_update_type VARCHAR(50);
BEGIN
    -- Determine the type of change
    IF TG_OP = 'INSERT' THEN
        analytics_update_type := 'entity_created';
        notification_payload := jsonb_build_object(
            'organization_id', NEW.organization_id,
            'entity_id', NEW.id,
            'entity_type', NEW.entity_type,
            'action', TG_OP,
            'timestamp', NOW(),
            'confidence', NEW.extraction_confidence,
            'source_modality', NEW.source_modality,
            'requires_analytics_update', true
        );
    ELSIF TG_OP = 'UPDATE' THEN
        analytics_update_type := 'entity_updated';
        notification_payload := jsonb_build_object(
            'organization_id', NEW.organization_id,
            'entity_id', NEW.id,
            'entity_type', NEW.entity_type,
            'action', TG_OP,
            'timestamp', NOW(),
            'old_confidence', OLD.extraction_confidence,
            'new_confidence', NEW.extraction_confidence,
            'confidence_changed', (OLD.extraction_confidence IS DISTINCT FROM NEW.extraction_confidence),
            'type_changed', (OLD.entity_type IS DISTINCT FROM NEW.entity_type),
            'requires_analytics_update', (
                OLD.extraction_confidence IS DISTINCT FROM NEW.extraction_confidence OR
                OLD.entity_type IS DISTINCT FROM NEW.entity_type OR
                OLD.source_modality IS DISTINCT FROM NEW.source_modality
            )
        );
    ELSIF TG_OP = 'DELETE' THEN
        analytics_update_type := 'entity_deleted';
        notification_payload := jsonb_build_object(
            'organization_id', OLD.organization_id,
            'entity_id', OLD.id,
            'entity_type', OLD.entity_type,
            'action', TG_OP,
            'timestamp', NOW(),
            'confidence', OLD.extraction_confidence,
            'source_modality', OLD.source_modality,
            'requires_analytics_update', true
        );
    END IF;

    -- Send notification for real-time analytics updates
    PERFORM pg_notify('analytics_entity_update', notification_payload::text);

    -- Queue immediate analytics update if significant change
    IF notification_payload->>'requires_analytics_update' = 'true' THEN
        PERFORM pg_notify('analytics_immediate_update', jsonb_build_object(
            'organization_id', COALESCE(NEW.organization_id, OLD.organization_id),
            'analytics_type', 'entity',
            'update_type', analytics_update_type,
            'priority', CASE
                WHEN TG_OP = 'DELETE' THEN 'high'
                WHEN analytics_update_type = 'entity_created' THEN 'medium'
                ELSE 'low'
            END,
            'timestamp', NOW()
        )::text);
    END IF;

    -- Log the change for audit trail
    INSERT INTO analytics_change_log (
        organization_id,
        table_name,
        record_id,
        operation_type,
        old_values,
        new_values,
        change_timestamp,
        requires_analytics_update
    ) VALUES (
        COALESCE(NEW.organization_id, OLD.organization_id),
        TG_TABLE_NAME,
        COALESCE(NEW.id, OLD.id),
        TG_OP,
        CASE WHEN TG_OP = 'DELETE' THEN row_to_json(OLD) ELSE NULL END,
        CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN row_to_json(NEW) ELSE NULL END,
        NOW(),
        (notification_payload->>'requires_analytics_update')::BOOLEAN
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Create triggers for entity table changes
DROP TRIGGER IF EXISTS entity_analytics_trigger ON entities;
CREATE TRIGGER entity_analytics_trigger
    AFTER INSERT OR UPDATE OR DELETE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION trigger_entity_analytics_update();

-- ============================================================================
-- RELATIONSHIP CHANGE TRIGGERS
-- ============================================================================

-- Relationship change notification trigger
CREATE OR REPLACE FUNCTION trigger_relationship_analytics_update()
RETURNS TRIGGER AS $$
DECLARE
    notification_payload JSONB;
    analytics_update_type VARCHAR(50);
BEGIN
    -- Determine the type of change
    IF TG_OP = 'INSERT' THEN
        analytics_update_type := 'relationship_created';
        notification_payload := jsonb_build_object(
            'organization_id', NEW.organization_id,
            'relationship_id', NEW.id,
            'relationship_type', NEW.relationship_type,
            'source_entity_id', NEW.source_entity_id,
            'target_entity_id', NEW.target_entity_id,
            'action', TG_OP,
            'timestamp', NOW(),
            'confidence', NEW.confidence,
            'is_bidirectional', NEW.is_bidirectional,
            'requires_analytics_update', true
        );
    ELSIF TG_OP = 'UPDATE' THEN
        analytics_update_type := 'relationship_updated';
        notification_payload := jsonb_build_object(
            'organization_id', NEW.organization_id,
            'relationship_id', NEW.id,
            'relationship_type', NEW.relationship_type,
            'source_entity_id', NEW.source_entity_id,
            'target_entity_id', NEW.target_entity_id,
            'action', TG_OP,
            'timestamp', NOW(),
            'old_confidence', OLD.confidence,
            'new_confidence', NEW.confidence,
            'confidence_changed', (OLD.confidence IS DISTINCT FROM NEW.confidence),
            'bidirectional_changed', (OLD.is_bidirectional IS DISTINCT FROM NEW.is_bidirectional),
            'requires_analytics_update', (
                OLD.confidence IS DISTINCT FROM NEW.confidence OR
                OLD.relationship_type IS DISTINCT FROM NEW.relationship_type OR
                OLD.is_bidirectional IS DISTINCT FROM NEW.is_bidirectional
            )
        );
    ELSIF TG_OP = 'DELETE' THEN
        analytics_update_type := 'relationship_deleted';
        notification_payload := jsonb_build_object(
            'organization_id', OLD.organization_id,
            'relationship_id', OLD.id,
            'relationship_type', OLD.relationship_type,
            'source_entity_id', OLD.source_entity_id,
            'target_entity_id', OLD.target_entity_id,
            'action', TG_OP,
            'timestamp', NOW(),
            'confidence', OLD.confidence,
            'is_bidirectional', OLD.is_bidirectional,
            'requires_analytics_update', true
        );
    END IF;

    -- Send notification for real-time analytics updates
    PERFORM pg_notify('analytics_relationship_update', notification_payload::text);

    -- Queue immediate analytics update if significant change
    IF notification_payload->>'requires_analytics_update' = 'true' THEN
        PERFORM pg_notify('analytics_immediate_update', jsonb_build_object(
            'organization_id', COALESCE(NEW.organization_id, OLD.organization_id),
            'analytics_type', 'relationship',
            'update_type', analytics_update_type,
            'priority', CASE
                WHEN TG_OP = 'DELETE' THEN 'high'
                WHEN analytics_update_type = 'relationship_created' THEN 'medium'
                ELSE 'low'
            END,
            'timestamp', NOW()
        )::text);
    END IF;

    -- Log the change for audit trail
    INSERT INTO analytics_change_log (
        organization_id,
        table_name,
        record_id,
        operation_type,
        old_values,
        new_values,
        change_timestamp,
        requires_analytics_update
    ) VALUES (
        COALESCE(NEW.organization_id, OLD.organization_id),
        TG_TABLE_NAME,
        COALESCE(NEW.id, OLD.id),
        TG_OP,
        CASE WHEN TG_OP = 'DELETE' THEN row_to_json(OLD) ELSE NULL END,
        CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN row_to_json(NEW) ELSE NULL END,
        NOW(),
        (notification_payload->>'requires_analytics_update')::BOOLEAN
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Create triggers for relationship table changes
DROP TRIGGER IF EXISTS relationship_analytics_trigger ON entity_relationships;
CREATE TRIGGER relationship_analytics_trigger
    AFTER INSERT OR UPDATE OR DELETE ON entity_relationships
    FOR EACH ROW
    EXECUTE FUNCTION trigger_relationship_analytics_update();

-- ============================================================================
-- DOCUMENT PROCESSING TRIGGERS
-- ============================================================================

-- Document status change trigger for analytics
CREATE OR REPLACE FUNCTION trigger_document_analytics_update()
RETURNS TRIGGER AS $$
DECLARE
    notification_payload JSONB;
    analytics_update_type VARCHAR(50);
    significant_change BOOLEAN := FALSE;
BEGIN
    -- Determine change significance
    IF TG_OP = 'INSERT' THEN
        analytics_update_type := 'document_created';
        significant_change := TRUE;
    ELSIF TG_OP = 'UPDATE' THEN
        -- Check for significant changes that affect analytics
        significant_change := (
            OLD.processing_status IS DISTINCT FROM NEW.processing_status OR
            OLD.quality_score IS DISTINCT FROM NEW.quality_score OR
            OLD.is_deleted IS DISTINCT FROM NEW.is_deleted OR
            OLD.file_size_bytes IS DISTINCT FROM NEW.file_size_bytes
        );

        IF NEW.processing_status = 'indexed' AND OLD.processing_status != 'indexed' THEN
            analytics_update_type := 'document_processed';
        ELSIF NEW.is_deleted AND NOT OLD.is_deleted THEN
            analytics_update_type := 'document_deleted';
        ELSIF OLD.is_deleted AND NOT NEW.is_deleted THEN
            analytics_update_type := 'document_restored';
        ELSE
            analytics_update_type := 'document_updated';
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        analytics_update_type := 'document_permanently_deleted';
        significant_change := TRUE;
    END IF;

    -- Build notification payload
    notification_payload := jsonb_build_object(
        'organization_id', COALESCE(NEW.organization_id, OLD.organization_id),
        'document_id', COALESCE(NEW.id, OLD.id),
        'file_type', COALESCE(NEW.file_type, OLD.file_type),
        'document_modality', COALESCE(NEW.document_modality, OLD.document_modality),
        'action', TG_OP,
        'timestamp', NOW(),
        'processing_status', COALESCE(NEW.processing_status, OLD.processing_status),
        'quality_score', COALESCE(NEW.quality_score, OLD.quality_score),
        'file_size_bytes', COALESCE(NEW.file_size_bytes, OLD.file_size_bytes),
        'is_deleted', COALESCE(NEW.is_deleted, OLD.is_deleted),
        'requires_analytics_update', significant_change
    );

    -- Send notification for real-time analytics updates
    IF significant_change THEN
        PERFORM pg_notify('analytics_document_update', notification_payload::text);

        -- Queue immediate analytics update
        PERFORM pg_notify('analytics_immediate_update', jsonb_build_object(
            'organization_id', COALESCE(NEW.organization_id, OLD.organization_id),
            'analytics_type', 'document',
            'update_type', analytics_update_type,
            'priority', CASE
                WHEN analytics_update_type IN ('document_processed', 'document_deleted') THEN 'high'
                WHEN analytics_update_type = 'document_created' THEN 'medium'
                ELSE 'low'
            END,
            'timestamp', NOW()
        )::text);
    END IF;

    -- Log the change for audit trail
    INSERT INTO analytics_change_log (
        organization_id,
        table_name,
        record_id,
        operation_type,
        old_values,
        new_values,
        change_timestamp,
        requires_analytics_update
    ) VALUES (
        COALESCE(NEW.organization_id, OLD.organization_id),
        TG_TABLE_NAME,
        COALESCE(NEW.id, OLD.id),
        TG_OP,
        CASE WHEN TG_OP = 'DELETE' THEN row_to_json(OLD) ELSE NULL END,
        CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN row_to_json(NEW) ELSE NULL END,
        NOW(),
        significant_change
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Create triggers for document table changes
DROP TRIGGER IF EXISTS document_analytics_trigger ON documents;
CREATE TRIGGER document_analytics_trigger
    AFTER INSERT OR UPDATE OR DELETE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION trigger_document_analytics_update();

-- ============================================================================
-- SEARCH QUERY TRIGGERS
-- ============================================================================

-- Search query analytics trigger
CREATE OR REPLACE FUNCTION trigger_search_analytics_update()
RETURNS TRIGGER AS $$
DECLARE
    notification_payload JSONB;
    query_complexity VARCHAR(20);
    search_intent VARCHAR(20);
BEGIN
    -- Analyze query complexity
    IF LENGTH(NEW.query_text) < 20 THEN
        query_complexity := 'simple';
    ELSIF LENGTH(NEW.query_text) < 100 THEN
        query_complexity := 'medium';
    ELSE
        query_complexity := 'complex';
    END IF;

    -- Analyze search intent
    IF NEW.query_text ILIKE '%what%' OR NEW.query_text ILIKE '%who%' OR NEW.query_text ILIKE '%where%' THEN
        search_intent := 'factual';
    ELSIF NEW.query_text ILIKE '%why%' OR NEW.query_text ILIKE '%how%' THEN
        search_intent := 'explanatory';
    ELSIF NEW.query_text ILIKE '%compare%' OR NEW.query_text ILIKE '%versus%' THEN
        search_intent := 'comparative';
    ELSIF NEW.query_text ILIKE '%list%' OR NEW.query_text ILIKE '%show me%' THEN
        search_intent := 'enumerative';
    ELSE
        search_intent := 'unknown';
    END IF;

    -- Build notification payload
    notification_payload := jsonb_build_object(
        'organization_id', NEW.organization_id,
        'user_id', NEW.user_id,
        'query_id', NEW.id,
        'action', 'search_executed',
        'timestamp', NEW.created_at,
        'query_text', NEW.query_text,
        'query_length', LENGTH(NEW.query_text),
        'query_complexity', query_complexity,
        'search_intent', search_intent,
        'result_count', NEW.result_count,
        'total_time_ms', NEW.total_time_ms,
        'search_type', NEW.search_type,
        'has_results', (NEW.result_count > 0),
        'performance_category', CASE
            WHEN NEW.total_time_ms <= 1000 THEN 'excellent'
            WHEN NEW.total_time_ms <= 2000 THEN 'good'
            WHEN NEW.total_time_ms <= 5000 THEN 'fair'
            ELSE 'poor'
        END,
        'requires_analytics_update', true
    );

    -- Send notification for real-time analytics updates
    PERFORM pg_notify('analytics_search_update', notification_payload::text);

    -- Queue analytics update (batch processed periodically)
    PERFORM pg_notify('analytics_batch_update', jsonb_build_object(
        'organization_id', NEW.organization_id,
        'analytics_type', 'search',
        'update_type', 'search_query',
        'priority', 'low',
        'timestamp', NEW.created_at
    )::text);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for search queries
DROP TRIGGER IF EXISTS search_analytics_trigger ON search_queries;
CREATE TRIGGER search_analytics_trigger
    AFTER INSERT ON search_queries
    FOR EACH ROW
    EXECUTE FUNCTION trigger_search_analytics_update();

-- ============================================================================
-- USER FEEDBACK TRIGGERS
-- ============================================================================

-- User feedback analytics trigger
CREATE OR REPLACE FUNCTION trigger_feedback_analytics_update()
RETURNS TRIGGER AS $$
DECLARE
    notification_payload JSONB;
    satisfaction_category VARCHAR(20);
BEGIN
    -- Categorize satisfaction
    IF NEW.rating >= 4.5 THEN
        satisfaction_category := 'very_satisfied';
    ELSIF NEW.rating >= 3.5 THEN
        satisfaction_category := 'satisfied';
    ELSIF NEW.rating >= 2.5 THEN
        satisfaction_category := 'neutral';
    ELSE
        satisfaction_category := 'dissatisfied';
    END IF;

    -- Build notification payload
    notification_payload := jsonb_build_object(
        'organization_id', NEW.organization_id,
        'user_id', NEW.user_id,
        'feedback_id', NEW.id,
        'action', 'feedback_submitted',
        'timestamp', NEW.created_at,
        'rating', NEW.rating,
        'satisfaction_category', satisfaction_category,
        'feedback_type', NEW.feedback_type,
        'has_comment', (NEW.comment IS NOT NULL AND LENGTH(TRIM(NEW.comment)) > 0),
        'requires_analytics_update', true
    );

    -- Send notification for real-time analytics updates
    PERFORM pg_notify('analytics_feedback_update', notification_payload::text);

    -- Queue analytics update
    PERFORM pg_notify('analytics_immediate_update', jsonb_build_object(
        'organization_id', NEW.organization_id,
        'analytics_type', 'user_interaction',
        'update_type', 'feedback',
        'priority', CASE
            WHEN NEW.rating <= 2 THEN 'medium'
            ELSE 'low'
        END,
        'timestamp', NEW.created_at
    )::text);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for user feedback
DROP TRIGGER IF EXISTS feedback_analytics_trigger ON user_feedback;
CREATE TRIGGER feedback_analytics_trigger
    AFTER INSERT ON user_feedback
    FOR EACH ROW
    EXECUTE FUNCTION trigger_feedback_analytics_update();

-- ============================================================================
-- MAINTENANCE AND CLEANUP TRIGGERS
-- ============================================================================

-- Cache invalidation trigger for analytics tables
CREATE OR REPLACE FUNCTION trigger_analytics_cache_invalidation()
RETURNS TRIGGER AS $$
DECLARE
    cache_keys_to_invalidate TEXT[];
BEGIN
    -- Determine which cache keys to invalidate based on the table and operation
    IF TG_TABLE_NAME = 'entity_analytics_optimized' THEN
        cache_keys_to_invalidate := ARRAY[
            'entity_analytics_' || COALESCE(NEW.organization_id, OLD.organization_id) || '_%',
            'real_time_dashboard_metrics_' || COALESCE(NEW.organization_id, OLD.organization_id)
        ];
    ELSIF TG_TABLE_NAME = 'relationship_analytics_optimized' THEN
        cache_keys_to_invalidate := ARRAY[
            'relationship_analytics_' || COALESCE(NEW.organization_id, OLD.organization_id) || '_%',
            'graph_metrics_' || COALESCE(NEW.organization_id, OLD.organization_id) || '_%'
        ];
    ELSIF TG_TABLE_NAME = 'document_analytics_optimized' THEN
        cache_keys_to_invalidate := ARRAY[
            'document_analytics_' || COALESCE(NEW.organization_id, OLD.organization_id) || '_%',
            'real_time_dashboard_metrics_' || COALESCE(NEW.organization_id, OLD.organization_id)
        ];
    ELSIF TG_TABLE_NAME = 'user_interaction_analytics_optimized' THEN
        cache_keys_to_invalidate := ARRAY[
            'user_interaction_analytics_' || COALESCE(NEW.organization_id, OLD.organization_id) || '_%',
            'real_time_dashboard_metrics_' || COALESCE(NEW.organization_id, OLD.organization_id)
        ];
    ELSIF TG_TABLE_NAME = 'graph_metrics_analytics_optimized' THEN
        cache_keys_to_invalidate := ARRAY[
            'graph_metrics_' || COALESCE(NEW.organization_id, OLD.organization_id) || '_%'
        ];
    END IF;

    -- Invalidate cache entries
    FOREACH cache_pattern IN ARRAY cache_keys_to_invalidate LOOP
        DELETE FROM analytics_cache
        WHERE organization_id = COALESCE(NEW.organization_id, OLD.organization_id)
          AND cache_key LIKE cache_pattern;
    END LOOP;

    -- Notify cache invalidation
    PERFORM pg_notify('analytics_cache_invalidated', jsonb_build_object(
        'organization_id', COALESCE(NEW.organization_id, OLD.organization_id),
        'table_name', TG_TABLE_NAME,
        'operation', TG_OP,
        'invalidated_keys', cache_keys_to_invalidate,
        'timestamp', NOW()
    )::text);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Create cache invalidation triggers for analytics tables
CREATE TRIGGER entity_analytics_cache_trigger
    AFTER INSERT OR UPDATE OR DELETE ON entity_analytics_optimized
    FOR EACH STATEMENT
    EXECUTE FUNCTION trigger_analytics_cache_invalidation();

CREATE TRIGGER relationship_analytics_cache_trigger
    AFTER INSERT OR UPDATE OR DELETE ON relationship_analytics_optimized
    FOR EACH STATEMENT
    EXECUTE FUNCTION trigger_analytics_cache_invalidation();

CREATE TRIGGER document_analytics_cache_trigger
    AFTER INSERT OR UPDATE OR DELETE ON document_analytics_optimized
    FOR EACH STATEMENT
    EXECUTE FUNCTION trigger_analytics_cache_invalidation();

CREATE TRIGGER user_interaction_analytics_cache_trigger
    AFTER INSERT OR UPDATE OR DELETE ON user_interaction_analytics_optimized
    FOR EACH STATEMENT
    EXECUTE FUNCTION trigger_analytics_cache_invalidation();

CREATE TRIGGER graph_metrics_analytics_cache_trigger
    AFTER INSERT OR UPDATE OR DELETE ON graph_metrics_analytics_optimized
    FOR EACH STATEMENT
    EXECUTE FUNCTION trigger_analytics_cache_invalidation();

-- ============================================================================
-- PERFORMANCE MONITORING TRIGGERS
-- ============================================================================

-- Performance monitoring trigger for slow queries
CREATE OR REPLACE FUNCTION trigger_performance_monitoring()
RETURNS TRIGGER AS $$
DECLARE
    performance_threshold_ms INTEGER := 5000; -- 5 seconds
    is_slow_query BOOLEAN;
BEGIN
    -- Check if this is a slow query
    is_slow_query := COALESCE(NEW.total_time_ms, 0) > performance_threshold_ms;

    IF is_slow_query THEN
        -- Log slow query for performance analysis
        INSERT INTO performance_log (
            organization_id,
            query_type,
            execution_time_ms,
            query_text,
            user_id,
            created_at,
            performance_category
        ) VALUES (
            NEW.organization_id,
            'search_query',
            NEW.total_time_ms,
            LEFT(NEW.query_text, 500), -- Truncate for storage
            NEW.user_id,
            NEW.created_at,
            'slow_query'
        );

        -- Notify performance monitoring
        PERFORM pg_notify('performance_alert', jsonb_build_object(
            'organization_id', NEW.organization_id,
            'user_id', NEW.user_id,
            'query_time_ms', NEW.total_time_ms,
            'query_text', LEFT(NEW.query_text, 200),
            'threshold_ms', performance_threshold_ms,
            'timestamp', NEW.created_at,
            'alert_type', 'slow_search_query'
        )::text);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create performance monitoring trigger
DROP TRIGGER IF EXISTS search_performance_trigger ON search_queries;
CREATE TRIGGER search_performance_trigger
    AFTER INSERT ON search_queries
    FOR EACH ROW
    EXECUTE FUNCTION trigger_performance_monitoring();

-- ============================================================================
-- PARTITION MAINTENANCE TRIGGERS
-- ============================================================================

-- Automatic partition creation trigger
CREATE OR REPLACE FUNCTION trigger_partition_maintenance()
RETURNS TRIGGER AS $$
BEGIN
    -- This trigger is called periodically to ensure partitions exist
    PERFORM create_entity_analytics_partitions();
    PERFORM create_relationship_analytics_partitions();
    PERFORM create_document_analytics_partitions();
    PERFORM create_user_interaction_analytics_partitions();

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- This would typically be called by a scheduled job, not a trigger
-- but keeping the function for use in maintenance scripts

-- ============================================================================
-- UTILITY FUNCTIONS FOR TRIGGER SUPPORT
-- ============================================================================

-- Analytics change log table (if not exists)
CREATE TABLE IF NOT EXISTS analytics_change_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    record_id UUID,
    operation_type VARCHAR(50) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    change_timestamp TIMESTAMPTZ DEFAULT NOW(),
    requires_analytics_update BOOLEAN DEFAULT FALSE,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMPTZ
) PARTITION BY RANGE (change_timestamp);

-- Create partition for current month
CREATE TABLE IF NOT EXISTS analytics_change_log_current PARTITION OF analytics_change_log
    FOR VALUES FROM (DATE_TRUNC('month', CURRENT_DATE)) TO (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month');

-- Performance log table (if not exists)
CREATE TABLE IF NOT EXISTS performance_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    query_type VARCHAR(100) NOT NULL,
    execution_time_ms INTEGER NOT NULL,
    query_text TEXT,
    user_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    performance_category VARCHAR(50) DEFAULT 'normal'
) PARTITION BY RANGE (created_at);

-- Create partition for current month
CREATE TABLE IF NOT EXISTS performance_log_current PARTITION OF performance_log
    FOR VALUES FROM (DATE_TRUNC('month', CURRENT_DATE)) TO (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month');

-- Indexes for change log
CREATE INDEX IF NOT EXISTS idx_analytics_change_log_org_time
    ON analytics_change_log (organization_id, change_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_change_log_unprocessed
    ON analytics_change_log (requires_analytics_update, processed, change_timestamp)
    WHERE requires_analytics_update = TRUE AND processed = FALSE;

-- Indexes for performance log
CREATE INDEX IF NOT EXISTS idx_performance_log_org_time
    ON performance_log (organization_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_performance_log_slow_queries
    ON performance_log (execution_time_ms DESC, created_at DESC)
    WHERE execution_time_ms > 5000;