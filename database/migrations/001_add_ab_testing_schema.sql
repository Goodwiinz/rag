-- Migration 001: Add A/B Testing Schema to Multimodal Enterprise RAG System
-- This migration adds A/B testing functionality to the existing database
-- Version: 1.0.0
-- Compatible with PostgreSQL 15+

BEGIN;

-- Check if migration has already been applied
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ab_experiments') THEN
        RAISE EXCEPTION 'A/B testing tables already exist. Migration may have been partially applied.';
    END IF;
END $$;

-- Create required extensions if they don't exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- ====================================================================
-- A/B TESTING TABLES
-- ====================================================================

-- 1. EXPERIMENTS TABLE
CREATE TABLE ab_experiments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    hypothesis TEXT,
    status VARCHAR(50) NOT NULL CHECK (status IN ('draft', 'running', 'paused', 'completed', 'cancelled')),

    -- Configuration
    traffic_percentage INTEGER NOT NULL DEFAULT 100 CHECK (traffic_percentage >= 0 AND traffic_percentage <= 100),
    is_ramp_enabled BOOLEAN DEFAULT false,
    ramp_schedule JSONB DEFAULT '{}',

    -- Targeting
    target_segments JSONB DEFAULT '[]',
    exclude_segments JSONB DEFAULT '[]',

    -- Statistical Configuration
    confidence_level DECIMAL(3,2) DEFAULT 0.95 CHECK (confidence_level > 0 AND confidence_level <= 1),
    minimum_sample_size INTEGER DEFAULT 1000,
    expected_improvement DECIMAL(5,2) DEFAULT 5.0,
    test_duration_days INTEGER DEFAULT 14,

    -- Metrics Configuration
    primary_metric VARCHAR(100) NOT NULL DEFAULT 'answer_relevancy',
    secondary_metrics JSONB DEFAULT '[]',

    -- Timestamps
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id UUID,

    -- Metadata
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',

    -- Soft delete
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT valid_time_range CHECK (end_time IS NULL OR start_time IS NULL OR end_time > start_time),
    CONSTRAINT valid_experiment_duration CHECK (test_duration_days > 0)
);

-- 2. VARIANTS TABLE
CREATE TABLE ab_variants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    experiment_id UUID NOT NULL REFERENCES ab_experiments(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,

    -- Variant Configuration
    is_control BOOLEAN DEFAULT false,
    traffic_weight INTEGER NOT NULL DEFAULT 1 CHECK (traffic_weight > 0),
    configuration JSONB NOT NULL DEFAULT '{}',

    -- RAG System Configuration
    retrieval_config JSONB DEFAULT '{}',
    ranking_config JSONB DEFAULT '{}',
    synthesis_config JSONB DEFAULT '{}',
    agent_config JSONB DEFAULT '{}',

    -- Performance Metrics
    baseline_metrics JSONB DEFAULT '{}',

    -- Status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'disabled', 'paused')),

    -- Metadata
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT unique_variant_name_per_experiment UNIQUE(experiment_id, name)
);

-- 3. USER_SEGMENTS TABLE
CREATE TABLE ab_user_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,

    -- Segment Definition
    criteria JSONB NOT NULL DEFAULT '{}',
    segment_type VARCHAR(50) NOT NULL CHECK (segment_type IN ('static', 'dynamic', 'behavioral', 'demographic')),

    -- Segment Properties
    size_estimate INTEGER,
    refresh_frequency VARCHAR(50) DEFAULT 'daily',
    is_active BOOLEAN DEFAULT true,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id UUID,

    -- Soft delete
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- 4. USER_ASSIGNMENTS TABLE (Partitioned)
CREATE TABLE ab_user_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255),
    experiment_id UUID NOT NULL REFERENCES ab_experiments(id),
    variant_id UUID NOT NULL REFERENCES ab_variants(id),

    -- Assignment Context
    assignment_context JSONB DEFAULT '{}',
    segment_matches JSONB DEFAULT '[]',
    assignment_hash VARCHAR(64),

    -- Timestamps
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Constraints
    CONSTRAINT unique_user_experiment UNIQUE(user_id, experiment_id),
    CONSTRAINT valid_assignment_hash_length CHECK (assignment_hash IS NULL OR length(assignment_hash) = 64)
) PARTITION BY RANGE (assigned_at);

-- Create initial partitions
CREATE TABLE ab_user_assignments_y2024m10 PARTITION OF ab_user_assignments
    FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');

CREATE TABLE ab_user_assignments_y2024m11 PARTITION OF ab_user_assignments
    FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');

CREATE TABLE ab_user_assignments_y2024m12 PARTITION OF ab_user_assignments
    FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');

-- 5. QUERY_EVENTS TABLE (Partitioned Time-Series)
CREATE TABLE ab_query_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id VARCHAR(255) UNIQUE NOT NULL,

    -- Context
    user_id VARCHAR(255),
    session_id VARCHAR(255),
    experiment_id UUID REFERENCES ab_experiments(id),
    variant_id UUID REFERENCES ab_variants(id),

    -- Query Information
    query_text TEXT NOT NULL,
    query_hash VARCHAR(64),
    query_type VARCHAR(50) DEFAULT 'search' CHECK (query_type IN ('search', 'reasoning', 'multimodal')),

    -- Performance Metrics
    query_latency_ms INTEGER,
    total_latency_ms INTEGER,
    retrieval_count INTEGER,
    rerank_count INTEGER,

    -- System Metrics
    vector_search_latency_ms INTEGER,
    graph_search_latency_ms INTEGER,
    keyword_search_latency_ms INTEGER,
    synthesis_latency_ms INTEGER,

    -- Query Features
    query_complexity_score DECIMAL(3,2),
    modality_types JSONB DEFAULT '[]',

    -- Event Details
    event_type VARCHAR(50) NOT NULL DEFAULT 'query_completion' CHECK (event_type IN ('query_completion', 'user_feedback', 'error', 'timeout')),
    response_status VARCHAR(50) DEFAULT 'success',
    error_details JSONB,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT valid_query_latency CHECK (query_latency_ms IS NULL OR query_latency_ms >= 0),
    CONSTRAINT valid_total_latency CHECK (total_latency_ms IS NULL OR total_latency_ms >= 0)
) PARTITION BY RANGE (created_at);

-- Create initial partitions for query events
CREATE TABLE ab_query_events_y2024m10d01 PARTITION OF ab_query_events
    FOR VALUES FROM ('2024-10-17') TO ('2024-10-18');

CREATE TABLE ab_query_events_y2024m10d02 PARTITION OF ab_query_events
    FOR VALUES FROM ('2024-10-18') TO ('2024-10-19');

CREATE TABLE ab_query_events_y2024m10d03 PARTITION OF ab_query_events
    FOR VALUES FROM ('2024-10-19') TO ('2024-10-20');

CREATE TABLE ab_query_events_y2024m10d04 PARTITION OF ab_query_events
    FOR VALUES FROM ('2024-10-20') TO ('2024-10-21');

CREATE TABLE ab_query_events_y2024m10d05 PARTITION OF ab_query_events
    FOR VALUES FROM ('2024-10-21') TO ('2024-10-22');

CREATE TABLE ab_query_events_y2024m10d06 PARTITION OF ab_query_events
    FOR VALUES FROM ('2024-10-22') TO ('2024-10-23');

CREATE TABLE ab_query_events_y2024m10d07 PARTITION OF ab_query_events
    FOR VALUES FROM ('2024-10-23') TO ('2024-10-24');

-- 6. QUALITY_METRICS TABLE (Partitioned)
CREATE TABLE ab_quality_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query_event_id UUID NOT NULL REFERENCES ab_query_events(id),

    -- Core RAG Metrics
    answer_relevancy DECIMAL(5,2) CHECK (answer_relevancy >= 0 AND answer_relevancy <= 100),
    faithfulness DECIMAL(5,2) CHECK (faithfulness >= 0 AND faithfulness <= 100),
    contextual_relevancy DECIMAL(5,2) CHECK (contextual_relevancy >= 0 AND contextual_relevancy <= 100),

    -- Additional Quality Metrics
    response_coherence DECIMAL(5,2) CHECK (response_coherence >= 0 AND response_coherence <= 100),
    completeness DECIMAL(5,2) CHECK (completeness >= 0 AND completeness <= 100),
    conciseness DECIMAL(5,2) CHECK (conciseness >= 0 AND conciseness <= 100),

    -- User Experience Metrics
    user_satisfaction_score INTEGER CHECK (user_satisfaction_score >= 1 AND user_satisfaction_score <= 5),
    user_feedback TEXT,
    user_clicked_results BOOLEAN DEFAULT false,
    user_dwell_time_ms INTEGER,

    -- Business Metrics
    task_completion_rate DECIMAL(5,2),
    conversion_rate DECIMAL(5,2),

    -- Evaluation Details
    evaluation_method VARCHAR(50) DEFAULT 'automated' CHECK (evaluation_method IN ('automated', 'human', 'hybrid')),
    confidence_score DECIMAL(5,2) CHECK (confidence_score >= 0 AND confidence_score <= 100),
    evaluation_model VARCHAR(100),

    -- Context
    ground_truth_data JSONB,
    evaluation_parameters JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT valid_confidence_score CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100))
) PARTITION BY RANGE (created_at);

-- Create initial partitions for quality metrics
CREATE TABLE ab_quality_metrics_y2024m10 PARTITION OF ab_quality_metrics
    FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');

-- 7. STATISTICAL_ANALYSES TABLE
CREATE TABLE ab_statistical_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    experiment_id UUID NOT NULL REFERENCES ab_experiments(id),
    metric_name VARCHAR(100) NOT NULL,

    -- Analysis Window
    analysis_period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    analysis_period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    sample_size INTEGER NOT NULL,

    -- Statistical Results
    control_mean DECIMAL(10,4),
    control_std_dev DECIMAL(10,4),
    control_sample_size INTEGER,

    treatment_mean DECIMAL(10,4),
    treatment_std_dev DECIMAL(10,4),
    treatment_sample_size INTEGER,

    -- Significance Testing
    effect_size DECIMAL(10,4),
    confidence_interval_lower DECIMAL(10,4),
    confidence_interval_upper DECIMAL(10,4),
    p_value DECIMAL(15,8),

    -- Results
    is_significant BOOLEAN DEFAULT false,
    is_positive_impact BOOLEAN DEFAULT false,
    relative_improvement DECIMAL(5,2),
    absolute_improvement DECIMAL(10,4),

    -- Test Configuration
    statistical_test VARCHAR(50) DEFAULT 'two_sample_t_test' CHECK (statistical_test IN ('two_sample_t_test', 'mann_whitney', 'chi_square', 'bootstrap')),
    confidence_level DECIMAL(3,2) DEFAULT 0.95,
    minimum_detectable_effect DECIMAL(5,2),

    -- Metadata
    analysis_metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT valid_analysis_period CHECK (analysis_period_end > analysis_period_start),
    CONSTRAINT valid_relative_improvement CHECK (relative_improvement IS NULL OR relative_improvement >= -100),
    CONSTRAINT valid_p_value CHECK (p_value IS NULL OR (p_value >= 0 AND p_value <= 1))
);

-- 8. EXPERIMENT_TARGETING TABLE
CREATE TABLE ab_experiment_targeting (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    experiment_id UUID NOT NULL REFERENCES ab_experiments(id) ON DELETE CASCADE,
    segment_id UUID NOT NULL REFERENCES ab_user_segments(id) ON DELETE CASCADE,

    -- Targeting Configuration
    is_inclusion BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 1,
    traffic_percentage INTEGER DEFAULT 100 CHECK (traffic_percentage >= 0 AND traffic_percentage <= 100),

    -- Constraints
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_experiment_segment UNIQUE(experiment_id, segment_id)
);

-- ====================================================================
-- INDEXES FOR PERFORMANCE OPTIMIZATION
-- ====================================================================

-- Indexes for ab_experiments
CREATE INDEX idx_ab_experiments_status ON ab_experiments(status) WHERE is_deleted = false;
CREATE INDEX idx_ab_experiments_active_time ON ab_experiments(start_time, end_time)
    WHERE status = 'running' AND is_deleted = false;
CREATE INDEX idx_ab_experiments_tags ON ab_experiments USING gin(tags) WHERE is_deleted = false;
CREATE INDEX idx_ab_experiments_created_at ON ab_experiments(created_at DESC) WHERE is_deleted = false;

-- Indexes for ab_variants
CREATE INDEX idx_ab_variants_experiment_id ON ab_variants(experiment_id) WHERE is_deleted = false;
CREATE INDEX idx_ab_variants_experiment_active ON ab_variants(experiment_id, status)
    WHERE is_deleted = false;
CREATE INDEX idx_ab_variants_control ON ab_variants(experiment_id, is_control)
    WHERE is_deleted = false;

-- Indexes for ab_user_segments
CREATE INDEX idx_ab_user_segments_active ON ab_user_segments(is_active) WHERE is_deleted = false;
CREATE INDEX idx_ab_user_segments_type ON ab_user_segments(segment_type) WHERE is_deleted = false;
CREATE INDEX idx_ab_user_segments_criteria ON ab_user_segments USING gin(criteria) WHERE is_deleted = false;

-- Indexes for ab_user_assignments (critical for performance)
CREATE INDEX idx_ab_user_assignments_user_id ON ab_user_assignments(user_id, experiment_id, is_active);
CREATE INDEX idx_ab_user_assignments_experiment_active ON ab_user_assignments(experiment_id, is_active, assigned_at DESC);
CREATE INDEX idx_ab_user_assignments_variant_active ON ab_user_assignments(variant_id, is_active);
CREATE INDEX idx_ab_user_assignments_session ON ab_user_assignments(session_id, experiment_id);
CREATE INDEX idx_ab_user_assignments_hash ON ab_user_assignments(assignment_hash);

-- Indexes for ab_query_events (time-series optimized)
CREATE INDEX idx_ab_query_events_user_session ON ab_query_events(user_id, session_id, created_at DESC);
CREATE INDEX idx_ab_query_events_experiment_variant ON ab_query_events(experiment_id, variant_id, created_at DESC);
CREATE INDEX idx_ab_query_events_created_at ON ab_query_events(created_at DESC);
CREATE INDEX idx_ab_query_events_query_type ON ab_query_events(query_type, created_at DESC);
CREATE INDEX idx_ab_query_events_status ON ab_query_events(response_status, created_at DESC);
CREATE INDEX idx_ab_query_events_hash ON ab_query_events(query_hash, created_at DESC);

-- Indexes for ab_quality_metrics
CREATE INDEX idx_ab_quality_metrics_query_event ON ab_quality_metrics(query_event_id);
CREATE INDEX idx_ab_quality_metrics_created_at ON ab_quality_metrics(created_at DESC);

-- Indexes for ab_statistical_analyses
CREATE INDEX idx_ab_statistical_analyses_experiment_metric ON ab_statistical_analyses(experiment_id, metric_name, created_at DESC);
CREATE INDEX idx_ab_statistical_analyses_significant ON ab_statistical_analyses(is_significant, created_at DESC);
CREATE INDEX idx_ab_statistical_analyses_period ON ab_statistical_analyses(analysis_period_end DESC);

-- Indexes for ab_experiment_targeting
CREATE INDEX idx_ab_experiment_targeting_experiment ON ab_experiment_targeting(experiment_id);
CREATE INDEX idx_ab_experiment_targeting_segment ON ab_experiment_targeting(segment_id);
CREATE INDEX idx_ab_experiment_targeting_priority ON ab_experiment_targeting(priority DESC);

-- ====================================================================
-- TRIGGERS AND FUNCTIONS
-- ====================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add updated_at triggers
CREATE TRIGGER update_ab_experiments_updated_at BEFORE UPDATE ON ab_experiments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ab_variants_updated_at BEFORE UPDATE ON ab_variants
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ab_user_segments_updated_at BEFORE UPDATE ON ab_user_segments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ab_experiment_targeting_updated_at BEFORE UPDATE ON ab_experiment_targeting
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to validate experiment constraints
CREATE OR REPLACE FUNCTION validate_experiment_constraints()
RETURNS TRIGGER AS $$
BEGIN
    -- Ensure experiment has valid time range
    IF NEW.start_time IS NOT NULL AND NEW.end_time IS NOT NULL AND NEW.start_time >= NEW.end_time THEN
        RAISE EXCEPTION 'Start time must be before end time';
    END IF;

    -- Validate traffic percentage
    IF NEW.traffic_percentage < 0 OR NEW.traffic_percentage > 100 THEN
        RAISE EXCEPTION 'Traffic percentage must be between 0 and 100';
    END IF;

    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER validate_ab_experiments BEFORE INSERT OR UPDATE ON ab_experiments
    FOR EACH ROW EXECUTE FUNCTION validate_experiment_constraints();

-- ====================================================================
-- VIEWS FOR COMMON QUERIES
-- ====================================================================

-- View for active experiments with variants
CREATE VIEW v_active_experiments AS
SELECT
    e.id as experiment_id,
    e.name as experiment_name,
    e.status,
    e.start_time,
    e.end_time,
    e.traffic_percentage,
    e.primary_metric,
    v.id as variant_id,
    v.name as variant_name,
    v.is_control,
    v.traffic_weight,
    v.configuration,
    ROW_NUMBER() OVER (PARTITION BY e.id ORDER BY v.is_control DESC, v.traffic_weight DESC) as variant_rank
FROM ab_experiments e
JOIN ab_variants v ON e.id = v.experiment_id
WHERE e.status = 'running'
    AND e.is_deleted = false
    AND v.is_deleted = false
    AND v.status = 'active'
    AND (e.start_time IS NULL OR e.start_time <= CURRENT_TIMESTAMP)
    AND (e.end_time IS NULL OR e.end_time > CURRENT_TIMESTAMP);

-- ====================================================================
-- INTEGRATION WITH EXISTING SCHEMA
-- ====================================================================

-- Add foreign key references to existing tables if they exist
DO $$
BEGIN
    -- Check if organizations table exists and add references
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'organizations') THEN
        ALTER TABLE ab_experiments ADD CONSTRAINT fk_ab_experiments_organization
            FOREIGN KEY (organization_id) REFERENCES organizations(id);

        ALTER TABLE ab_user_segments ADD CONSTRAINT fk_ab_user_segments_organization
            FOREIGN KEY (organization_id) REFERENCES organizations(id);
    END IF;

    -- Check if users table exists and add references
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users') THEN
        ALTER TABLE ab_experiments ADD CONSTRAINT fk_ab_experiments_created_by_user
            FOREIGN KEY (created_by_user_id) REFERENCES users(id);

        ALTER TABLE ab_user_segments ADD CONSTRAINT fk_ab_user_segments_created_by_user
            FOREIGN KEY (created_by_user_id) REFERENCES users(id);
    END IF;
END $$;

-- ====================================================================
-- SAMPLE DATA FOR TESTING
-- ====================================================================

-- Insert sample user segments
INSERT INTO ab_user_segments (id, name, description, criteria, segment_type) VALUES
    (uuid_generate_v4(), 'All Users', 'All users in the system', '{}', 'static'),
    (uuid_generate_v4(), 'Power Users', 'Users with high query volume', '{"min_queries_per_day": 10}', 'dynamic'),
    (uuid_generate_v4(), 'New Users', 'Users who joined in last 30 days', '{"days_since_signup": {"max": 30}}', 'dynamic');

-- Insert sample experiment for demonstration
INSERT INTO ab_experiments (id, name, description, hypothesis, status, primary_metric, start_time, end_time) VALUES
    (uuid_generate_v4(),
     'Improved Retrieval Ranking Algorithm',
     'Test new vector ranking algorithm for better document relevance',
     'The new ranking algorithm will improve answer relevancy by at least 5%',
     'draft',
     'answer_relevancy',
     CURRENT_TIMESTAMP + INTERVAL '1 day',
     CURRENT_TIMESTAMP + INTERVAL '15 days'
    ) ON CONFLICT DO NOTHING;

-- ====================================================================
-- PARTITION MANAGEMENT FUNCTIONS
-- ====================================================================

-- Function to create monthly partitions for user_assignments
CREATE OR REPLACE FUNCTION create_monthly_partition_user_assignments()
RETURNS void AS $$
DECLARE
    start_date date;
    end_date date;
    partition_name text;
BEGIN
    -- Create partitions for next 3 months
    FOR i IN 0..2 LOOP
        start_date := date_trunc('month', CURRENT_DATE + INTERVAL '1 month' * i);
        end_date := start_date + INTERVAL '1 month';
        partition_name := 'ab_user_assignments_y' || EXTRACT(year FROM start_date) || 'm' || LPAD(EXTRACT(month FROM start_date)::text, 2, '0');

        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF ab_user_assignments FOR VALUES FROM (%L) TO (%L)',
                      partition_name, start_date, end_date);
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function to create daily partitions for query_events
CREATE OR REPLACE FUNCTION create_daily_partition_query_events()
RETURNS void AS $$
DECLARE
    start_date date;
    end_date date;
    partition_name text;
BEGIN
    -- Create partitions for next 7 days
    FOR i IN 0..6 LOOP
        start_date := CURRENT_DATE + i;
        end_date := start_date + INTERVAL '1 day';
        partition_name := 'ab_query_events_y' || EXTRACT(year FROM start_date) ||
                         'm' || LPAD(EXTRACT(month FROM start_date)::text, 2, '0') ||
                         'd' || LPAD(EXTRACT(day FROM start_date)::text, 2, '0');

        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF ab_query_events FOR VALUES FROM (%L) TO (%L)',
                      partition_name, start_date, end_date);
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Create migration tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL UNIQUE,
    description TEXT,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    applied_by VARCHAR(100) DEFAULT CURRENT_USER
);

-- Record this migration
INSERT INTO schema_migrations (version, description) VALUES
('001', 'Add A/B testing schema for Multimodal Enterprise RAG System');

-- Grant permissions (adjust roles based on your system)
DO $$
BEGIN
    -- Create roles if they don't exist
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ab_testing_admin') THEN
        CREATE ROLE ab_testing_admin;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ab_testing_user') THEN
        CREATE ROLE ab_testing_user;
    END IF;

    -- Grant permissions
    GRANT ALL ON ALL TABLES IN SCHEMA public TO ab_testing_admin;
    GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO ab_testing_user;
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO ab_testing_admin;
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO ab_testing_user;
END $$;

-- Create indexes on the migration tracking table
CREATE INDEX IF NOT EXISTS idx_schema_migrations_version ON schema_migrations(version);
CREATE INDEX IF NOT EXISTS idx_schema_migrations_applied_at ON schema_migrations(applied_at DESC);

COMMIT;

-- ====================================================================
-- POST-MIGRATION VERIFICATION
-- ====================================================================

-- Verify all tables were created
DO $$
DECLARE
    table_count integer;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name LIKE 'ab_%';

    IF table_count != 8 THEN
        RAISE EXCEPTION 'Expected 8 A/B testing tables, found %', table_count;
    END IF;

    RAISE NOTICE 'A/B testing schema migration completed successfully. Created % tables.', table_count;
END $$;

-- Check partition creation
DO $$
DECLARE
    partition_count integer;
BEGIN
    SELECT COUNT(*) INTO partition_count
    FROM pg_inherits i
    JOIN pg_class p ON p.oid = i.inhparent
    WHERE p.relname LIKE 'ab_%';

    RAISE NOTICE 'Created % partitions for A/B testing tables.', partition_count;
END $$;