-- A/B Testing System Database Schema for Multimodal Enterprise RAG
-- Logical Data Model Documentation
--
-- This schema supports high-volume A/B testing for query improvements
-- Target: 10,000+ queries per hour with sub-10ms performance

====================================================================
LOGICAL DATA MODEL
====================================================================

Core Entities:
--------------
1. EXPERIMENTS - A/B test configurations
2. VARIANTS - Test variants (control vs treatment)
3. TRAFFIC_ALLOCATIONS - User assignment rules
4. USER_ASSIGNMENTS - Real-time user experiment mapping
5. QUERY_EVENTS - Individual query interactions
6. METRICS - Performance measurements
7. STATISTICAL_ANALYSES - Significance testing results
8. USER_SEGMENTS - Targeting criteria
9. EXPERIMENT_TARGETING - Segment-experiment relationships

Key Design Principles:
---------------------
- High-performance read patterns for real-time routing
- Time-series optimized for metrics collection
- Probabilistic user assignment with consistency
- Statistical significance calculation support
- Configurable traffic ramping
- Multi-dimensional user segmentation

====================================================================
PHYSICAL SCHEMA DESIGN
====================================================================/

-- Create indexes for sub-10ms query performance
-- Use partitioning for high-volume tables
-- Implement proper foreign key relationships
-- Add constraints for data consistency

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- ====================================================================
-- 1. EXPERIMENTS TABLE
-- ====================================================================
-- Purpose: Store A/B test configurations and metadata
-- Access Pattern: Frequent reads for experiment routing
-- Estimated Rows: 100-1000 active experiments

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
    target_segments JSONB DEFAULT '[]', -- Array of segment criteria
    exclude_segments JSONB DEFAULT '[]',

    -- Statistical Configuration
    confidence_level DECIMAL(3,2) DEFAULT 0.95 CHECK (confidence_level > 0 AND confidence_level <= 1),
    minimum_sample_size INTEGER DEFAULT 1000,
    expected_improvement DECIMAL(5,2) DEFAULT 5.0, -- Expected improvement percentage
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

-- ====================================================================
-- 2. VARIANTS TABLE
-- ====================================================================
-- Purpose: Define test variants (control and treatments)
-- Access Pattern: Read during query routing for configuration
-- Estimated Rows: 2-5 per experiment

CREATE TABLE ab_variants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    experiment_id UUID NOT NULL REFERENCES ab_experiments(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,

    -- Variant Configuration
    is_control BOOLEAN DEFAULT false,
    traffic_weight INTEGER NOT NULL DEFAULT 1 CHECK (traffic_weight > 0),
    configuration JSONB NOT NULL DEFAULT '{}', -- Variant-specific settings

    -- RAG System Configuration
    retrieval_config JSONB DEFAULT '{}', -- Retrieval parameters
    ranking_config JSONB DEFAULT '{}', -- Ranking parameters
    synthesis_config JSONB DEFAULT '{}', -- Synthesis parameters
    agent_config JSONB DEFAULT '{}', -- Agent orchestration settings

    -- Performance Metrics
    baseline_metrics JSONB DEFAULT '{}', -- Expected baseline values

    -- Status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'disabled', 'paused')),

    -- Metadata
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT unique_variant_name_per_experiment UNIQUE(experiment_id, name),
    CONSTRAINT at_least_one_control CHECK (
        -- Ensure at least one control variant per experiment
        EXISTS (
            SELECT 1 FROM ab_variants v2
            WHERE v2.experiment_id = ab_variants.experiment_id
            AND v2.is_control = true
            AND v2.is_deleted = false
        )
    )
);

-- ====================================================================
-- 3. USER_SEGMENTS TABLE
-- ====================================================================
-- Purpose: Define user segments for targeting
-- Access Pattern: Read during user assignment
-- Estimated Rows: 50-200 segments

CREATE TABLE ab_user_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,

    -- Segment Definition
    criteria JSONB NOT NULL DEFAULT '{}', -- Segment rules
    segment_type VARCHAR(50) NOT NULL CHECK (segment_type IN ('static', 'dynamic', 'behavioral', 'demographic')),

    -- Segment Properties
    size_estimate INTEGER,
    refresh_frequency VARCHAR(50) DEFAULT 'daily', -- How often to refresh segment membership
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

-- ====================================================================
-- 4. USER_ASSIGNMENTS TABLE (Partitioned)
-- ====================================================================
-- Purpose: Store user-to-variant assignments for consistency
-- Access Pattern: Very high read volume during query routing
-- Estimated Rows: Millions (10M+)
-- Partitioning: By date for performance

CREATE TABLE ab_user_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL, -- External user identifier
    session_id VARCHAR(255), -- Session identifier for session-based tests
    experiment_id UUID NOT NULL REFERENCES ab_experiments(id),
    variant_id UUID NOT NULL REFERENCES ab_variants(id),

    -- Assignment Context
    assignment_context JSONB DEFAULT '{}', -- Context at assignment time
    segment_matches JSONB DEFAULT '[]', -- Which segments matched
    assignment_hash VARCHAR(64), -- Consistent hash for reproducibility

    -- Timestamps
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Constraints
    CONSTRAINT unique_user_experiment UNIQUE(user_id, experiment_id),
    CONSTRAINT valid_assignment_hash_length CHECK (assignment_hash IS NULL OR length(assignment_hash) = 64)
) PARTITION BY RANGE (assigned_at);

-- Create monthly partitions for user assignments
CREATE TABLE ab_user_assignments_y2024m01 PARTITION OF ab_user_assignments
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE ab_user_assignments_y2024m02 PARTITION OF ab_user_assignments
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- Add more partitions as needed

-- ====================================================================
-- 5. QUERY_EVENTS TABLE (Partitioned Time-Series)
-- ====================================================================
-- Purpose: Store individual query interactions and metrics
-- Access Pattern: High-volume inserts for metrics collection
-- Estimated Rows: 10,000+ per hour (240K+ per day)
-- Partitioning: By date for performance and retention

CREATE TABLE ab_query_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id VARCHAR(255) UNIQUE NOT NULL, -- Unique event identifier

    -- Context
    user_id VARCHAR(255),
    session_id VARCHAR(255),
    experiment_id UUID REFERENCES ab_experiments(id),
    variant_id UUID REFERENCES ab_variants(id),

    -- Query Information
    query_text TEXT NOT NULL,
    query_hash VARCHAR(64), -- For deduplication
    query_type VARCHAR(50) DEFAULT 'search', -- search, reasoning, multimodal

    -- Performance Metrics (captured at query time)
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
    modality_types JSONB DEFAULT '[]', -- ['text', 'image', 'audio', 'video']

    -- Event Details
    event_type VARCHAR(50) NOT NULL DEFAULT 'query_completion',
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

-- Create daily partitions for query events (automated management)
CREATE TABLE ab_query_events_y2024m01d01 PARTITION OF ab_query_events
    FOR VALUES FROM ('2024-01-01') TO ('2024-01-02');

CREATE TABLE ab_query_events_y2024m01d02 PARTITION OF ab_query_events
    FOR VALUES FROM ('2024-01-02') TO ('2024-01-03');

-- Additional partitions will be created automatically

-- ====================================================================
-- 6. QUALITY_METRICS TABLE (Partitioned)
-- ====================================================================
-- Purpose: Store detailed quality metrics for each query event
-- Access Pattern: Batch inserts from evaluation system
-- Estimated Rows: Similar to query_events
-- Note: Extends existing quality metrics system

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
    confidence_score DECIMAL(5,2),
    evaluation_model VARCHAR(100),

    -- Context
    ground_truth_data JSONB,
    evaluation_parameters JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT valid_confidence_score CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100))
) PARTITION BY RANGE (created_at);

-- Create partitions for quality metrics
CREATE TABLE ab_quality_metrics_y2024m01 PARTITION OF ab_quality_metrics
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- ====================================================================
-- 7. STATISTICAL_ANALYSES TABLE
-- ====================================================================
-- Purpose: Store statistical significance calculations
-- Access Pattern: Batch calculations, periodic reads for dashboards
-- Estimated Rows: Multiple per experiment per metric

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
    effect_size DECIMAL(10,4), -- Cohen's d
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

-- ====================================================================
-- 8. EXPERIMENT_TARGETING TABLE
-- ====================================================================
-- Purpose: Define which experiments apply to which segments
-- Access Pattern: Read during experiment selection
-- Estimated Rows: Hundreds to thousands

CREATE TABLE ab_experiment_targeting (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    experiment_id UUID NOT NULL REFERENCES ab_experiments(id) ON DELETE CASCADE,
    segment_id UUID NOT NULL REFERENCES ab_user_segments(id) ON DELETE CASCADE,

    -- Targeting Configuration
    is_inclusion BOOLEAN DEFAULT true, -- true for inclusion, false for exclusion
    priority INTEGER DEFAULT 1, -- Higher priority takes precedence
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
CREATE INDEX idx_ab_quality_metrics_experiment_variant ON ab_quality_metrics(query_event_id)
    INCLUDE (answer_relevancy, faithfulness, contextual_relevancy);
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

-- View for experiment performance summary
CREATE VIEW v_experiment_performance_summary AS
SELECT
    e.id as experiment_id,
    e.name as experiment_name,
    e.primary_metric,
    e.status,
    COUNT(DISTINCT qa.user_id) as total_users,
    COUNT(qe.id) as total_queries,
    AVG(qm.answer_relevancy) as avg_answer_relevancy,
    AVG(qm.faithfulness) as avg_faithfulness,
    AVG(qm.contextual_relevancy) as avg_contextual_relevancy,
    AVG(qe.query_latency_ms) as avg_query_latency_ms,
    AVG(qe.total_latency_ms) as avg_total_latency_ms,
    MAX(qe.created_at) as last_query_at,
    sa.is_significant as is_statistically_significant,
    sa.relative_improvement as observed_improvement
FROM ab_experiments e
LEFT JOIN ab_user_assignments qa ON e.id = qa.experiment_id AND qa.is_active = true
LEFT JOIN ab_query_events qe ON qa.experiment_id = qe.experiment_id
LEFT JOIN ab_quality_metrics qm ON qe.id = qm.query_event_id
LEFT JOIN ab_statistical_analyses sa ON e.id = sa.experiment_id AND sa.metric_name = e.primary_metric
WHERE e.is_deleted = false
GROUP BY e.id, e.name, e.primary_metric, e.status, sa.is_significant, sa.relative_improvement;

-- ====================================================================
-- STATISTICAL FUNCTIONS
-- ====================================================================

-- Function to calculate statistical significance for experiment
CREATE OR REPLACE FUNCTION calculate_experiment_significance(
    p_experiment_id UUID,
    p_metric_name VARCHAR(100) DEFAULT 'answer_relevancy',
    p_confidence_level DECIMAL(3,2) DEFAULT 0.95
)
RETURNS TABLE(
    control_mean DECIMAL,
    treatment_mean DECIMAL,
    effect_size DECIMAL,
    p_value DECIMAL,
    is_significant BOOLEAN,
    relative_improvement DECIMAL
) AS $$
DECLARE
    v_control_variant_id UUID;
    v_analysis_start TIMESTAMP WITH TIME ZONE;
    v_analysis_end TIMESTAMP WITH TIME ZONE;
BEGIN
    -- Get control variant
    SELECT id INTO v_control_variant_id
    FROM ab_variants
    WHERE experiment_id = p_experiment_id AND is_control = true AND is_deleted = false;

    -- Calculate analysis window (last 7 days or experiment start)
    SELECT COALESCE(start_time, CURRENT_TIMESTAMP - INTERVAL '7 days'),
           COALESCE(end_time, CURRENT_TIMESTAMP)
    INTO v_analysis_start, v_analysis_end
    FROM ab_experiments
    WHERE id = p_experiment_id;

    -- Return statistical calculation results
    RETURN QUERY
    WITH control_metrics AS (
        SELECT qm.answer_relevancy
        FROM ab_quality_metrics qm
        JOIN ab_query_events qe ON qm.query_event_id = qe.id
        JOIN ab_user_assignments ua ON qe.experiment_id = ua.experiment_id AND qe.user_id = ua.user_id
        WHERE ua.experiment_id = p_experiment_id
            AND ua.variant_id = v_control_variant_id
            AND qm.created_at BETWEEN v_analysis_start AND v_analysis_end
    ),
    treatment_metrics AS (
        SELECT qm.answer_relevancy
        FROM ab_quality_metrics qm
        JOIN ab_query_events qe ON qm.query_event_id = qe.id
        JOIN ab_user_assignments ua ON qe.experiment_id = ua.experiment_id AND qe.user_id = ua.user_id
        WHERE ua.experiment_id = p_experiment_id
            AND ua.variant_id != v_control_variant_id
            AND qm.created_at BETWEEN v_analysis_start AND v_analysis_end
    )
    SELECT
        AVG(c.answer_relevancy) as control_mean,
        AVG(t.answer_relevancy) as treatment_mean,
        -- Simplified effect size calculation
        (AVG(t.answer_relevancy) - AVG(c.answer_relevancy)) /
        NULLIF(STDDEV(c.answer_relevancy), 0) as effect_size,
        -- Placeholder p-value (would need proper statistical calculation)
        0.05 as p_value,
        CASE WHEN 0.05 < (1 - p_confidence_level) THEN true ELSE false END as is_significant,
        -- Relative improvement calculation
        CASE WHEN AVG(c.answer_relevancy) > 0
            THEN ((AVG(t.answer_relevancy) - AVG(c.answer_relevancy)) / AVG(c.answer_relevancy)) * 100
            ELSE NULL END as relative_improvement
    FROM control_metrics c, treatment_metrics t;

    RETURN;
END;
$$ LANGUAGE plpgsql;

-- ====================================================================
-- RETENTION POLICIES
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

-- Function to create daily partitions for query_events (for next 7 days)
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

-- Create a schedule for automatic partition management (requires pg_cron extension)
-- SELECT cron.schedule('create-partitions', '0 0 * * *', 'SELECT create_monthly_partition_user_assignments(); SELECT create_daily_partition_query_events();');

-- ====================================================================
-- SECURITY AND PRIVACY
-- ====================================================================

-- Row Level Security for user data privacy
ALTER TABLE ab_user_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE ab_query_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE ab_quality_metrics ENABLE ROW LEVEL SECURITY;

-- Policy for user data access (example - adjust based on your auth system)
CREATE POLICY user_assignments_policy ON ab_user_assignments
    FOR ALL TO authenticated_users
    USING (user_id = current_setting('app.current_user_id', true));

-- ====================================================================
-- PERFORMANCE MONITORING
-- ====================================================================

-- Create function to monitor table sizes and query performance
CREATE OR REPLACE FUNCTION monitor_ab_testing_performance()
RETURNS TABLE(
    table_name text,
    row_estimate bigint,
    total_size_mb numeric,
    index_size_mb numeric,
    partition_count bigint
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        schemaname||'.'||tablename as table_name,
        n_tup_ins + n_tup_upd - n_tup_del as row_estimate,
        pg_total_relation_size(schemaname||'.'||tablename)/1024/1024 as total_size_mb,
        pg_indexes_size(schemaname||'.'||tablename)/1024/1024 as index_size_mb,
        (SELECT count(*) FROM pg_inherits WHERE inhparent = c.oid) as partition_count
    FROM pg_tables t
    JOIN pg_class c ON c.relname = t.tablename
    WHERE schemaname = 'public'
        AND tablename LIKE 'ab_%'
    ORDER BY total_size_mb DESC;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (adjust based on your user roles)
GRANT SELECT ON ALL TABLES IN SCHEMA public TO read_only_users;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_users;
GRANT ALL ON ALL TABLES IN SCHEMA public TO admin_users;

-- ====================================================================
-- SAMPLE DATA FOR TESTING
-- ====================================================================

-- Insert sample experiment (for development/testing)
INSERT INTO ab_experiments (id, name, description, status, primary_metric, start_time, end_time)
VALUES (
    uuid_generate_v4(),
    'Improved Retrieval Ranking Algorithm',
    'Test new vector ranking algorithm for better document relevance',
    'running',
    'answer_relevancy',
    CURRENT_TIMESTAMP - INTERVAL '1 day',
    CURRENT_TIMESTAMP + INTERVAL '13 days'
) ON CONFLICT DO NOTHING;