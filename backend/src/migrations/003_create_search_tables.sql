-- Migration 003: Create search and analytics tables with time-series partitioning
-- Supports comprehensive search tracking and performance monitoring

BEGIN;

-- Search queries table (partitioned for time-series efficiency)
CREATE TABLE search_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES user_sessions(id) ON DELETE SET NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Query information
    query_text TEXT NOT NULL,
    query_type VARCHAR(50) DEFAULT 'hybrid' CHECK (query_type IN ('semantic', 'keyword', 'hybrid', 'graph', 'multimodal')),
    query_filters JSONB DEFAULT '{}',
    query_parameters JSONB DEFAULT '{}',

    -- Search results
    total_results INTEGER DEFAULT 0,
    returned_results INTEGER DEFAULT 10,
    result_document_ids JSONB DEFAULT '[]',
    result_scores JSONB DEFAULT '[]',

    -- Performance metrics
    total_time_ms INTEGER NOT NULL,
    vector_search_time_ms INTEGER,
    graph_search_time_ms INTEGER,
    keyword_search_time_ms INTEGER,
    reranking_time_ms INTEGER,

    -- System metrics
    cache_hit BOOLEAN DEFAULT FALSE,
    embedding_cache_hit BOOLEAN DEFAULT FALSE,

    -- User interaction
    clicked_result_positions INTEGER[] DEFAULT '{}',
    clicked_document_ids JSONB DEFAULT '[]',
    user_satisfaction_score INTEGER CHECK (user_satisfaction_score >= 1 AND user_satisfaction_score <= 5),
    user_feedback TEXT,

    -- Context
    session_query_number INTEGER DEFAULT 1, -- Position in session
    referrer_query_id UUID REFERENCES search_queries(id),

    -- Metadata
    client_timestamp TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ
) PARTITION BY RANGE (created_at);

-- Create monthly partitions for search_queries
CREATE TABLE search_queries_y2024m01 PARTITION OF search_queries
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE search_queries_y2024m02 PARTITION OF search_queries
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

CREATE TABLE search_queries_y2024m03 PARTITION OF search_queries
    FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');

-- Search results detailed tracking
CREATE TABLE search_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_query_id UUID NOT NULL REFERENCES search_queries(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,

    -- Result information
    rank_position INTEGER NOT NULL,
    relevance_score DECIMAL(10,8) NOT NULL,
    confidence_score DECIMAL(5,4) DEFAULT 1.0,

    -- Matching details
    match_type VARCHAR(100), -- semantic, keyword, graph, hybrid
    matched_snippets JSONB DEFAULT '[]',
    highlight_spans JSONB DEFAULT '[]',

    -- Context information
    context_before TEXT,
    context_after TEXT,
    context_window_size INTEGER DEFAULT 200,

    -- Multi-modal matching
    matched_modalities JSONB DEFAULT '[]',
    modality_scores JSONB DEFAULT '{}',

    -- User interaction
    was_clicked BOOLEAN DEFAULT FALSE,
    clicked_at TIMESTAMPTZ,
    dwell_time_ms INTEGER,
    scroll_percentage INTEGER,

    -- Feedback
    user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),
    feedback_text TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_rank CHECK (rank_position > 0),
    CONSTRAINT valid_relevance CHECK (relevance_score >= 0 AND relevance_score <= 1)
);

-- Search sessions for tracking user search behavior
CREATE TABLE search_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Session information
    session_token VARCHAR(255) UNIQUE NOT NULL,
    start_time TIMESTAMPTZ DEFAULT NOW(),
    end_time TIMESTAMPTZ,

    -- Session metrics
    total_queries INTEGER DEFAULT 0,
    total_results INTEGER DEFAULT 0,
    total_clicks INTEGER DEFAULT 0,
    avg_response_time_ms INTEGER,
    session_duration_seconds INTEGER,

    -- Session context
    start_query_text TEXT, -- First query in session
    session_topic JSONB, -- Detected session topics
    user_intent JSONB, -- Detected user intents

    -- Technology used
    search_types_used JSONB DEFAULT '[]',
    features_used JSONB DEFAULT '[]',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RAG Triad evaluation results
CREATE TABLE rag_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    search_query_id UUID NOT NULL REFERENCES search_queries(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Evaluation configuration
    evaluation_model VARCHAR(100),
    evaluation_version VARCHAR(50),
    evaluation_config JSONB DEFAULT '{}',

    -- RAG Triad metrics
    answer_relevancy_score DECIMAL(5,4) CHECK (answer_relevancy_score >= 0 AND answer_relevancy_score <= 1),
    answer_relevancy_confidence DECIMAL(5,4),
    answer_relevancy_explanation TEXT,

    faithfulness_score DECIMAL(5,4) CHECK (faithfulness_score >= 0 AND faithfulness_score <= 1),
    faithfulness_confidence DECIMAL(5,4),
    faithfulness_explanation TEXT,
    faithfulness_violations JSONB DEFAULT '[]',

    contextual_relevancy_score DECIMAL(5,4) CHECK (contextual_relevancy_score >= 0 AND contextual_relevancy_score <= 1),
    contextual_relevancy_confidence DECIMAL(5,4),
    contextual_relevancy_explanation TEXT,

    -- Overall assessment
    overall_score DECIMAL(5,4) CHECK (overall_score >= 0 AND overall_score <= 1),
    meets_thresholds BOOLEAN DEFAULT FALSE,

    -- Performance and cost
    evaluation_time_ms INTEGER,
    tokens_used INTEGER,
    cost_usd DECIMAL(10,6),

    -- Evaluation metadata
    reference_answer TEXT,
    retrieved_contexts JSONB DEFAULT '[]',
    generated_answer TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_answer_relevancy CHECK (answer_relevancy_score >= 0 AND answer_relevancy_score <= 1),
    CONSTRAINT valid_faithfulness CHECK (faithfulness_score >= 0 AND faithfulness_score <= 1),
    CONSTRAINT valid_contextual CHECK (contextual_relevancy_score >= 0 AND contextual_relevancy_score <= 1)
);

-- User feedback collection
CREATE TABLE user_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Feedback context
    feedback_type VARCHAR(50) NOT NULL CHECK (feedback_type IN ('search_quality', 'document_quality', 'ui_experience', 'feature_request', 'bug_report')),
    related_entity_type VARCHAR(50), -- search_query, document, feature, etc.
    related_entity_id UUID,

    -- Feedback content
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,
    sentiment_score DECIMAL(5,4) CHECK (sentiment_score >= -1 AND sentiment_score <= 1),
    sentiment_label VARCHAR(20),

    -- System context
    page_url VARCHAR(500),
    user_agent TEXT,
    ip_address INET,
    session_id UUID REFERENCES user_sessions(id),

    -- Processing
    is_reviewed BOOLEAN DEFAULT FALSE,
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    tags JSONB DEFAULT '[]',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for search tables
CREATE INDEX idx_search_queries_user ON search_queries(user_id, created_at DESC);
CREATE INDEX idx_search_queries_session ON search_queries(session_id, created_at DESC);
CREATE INDEX idx_search_queries_organization ON search_queries(organization_id, created_at DESC);
CREATE INDEX idx_search_queries_type ON search_queries(query_type, created_at DESC);
CREATE INDEX idx_search_queries_performance ON search_queries(total_time_ms, created_at DESC);
CREATE INDEX idx_search_queries_text_fts ON search_queries USING GIN(to_tsvector('english', query_text));
CREATE INDEX idx_search_queries_satisfaction ON search_queries(user_satisfaction_score, created_at DESC);

CREATE INDEX idx_search_results_query ON search_results(search_query_id, rank_position);
CREATE INDEX idx_search_results_document ON search_results(document_id, created_at DESC);
CREATE INDEX idx_search_results_score ON search_results(relevance_score DESC);
CREATE INDEX idx_search_results_clicked ON search_results(was_clicked, clicked_at DESC);
CREATE INDEX idx_search_results_match_type ON search_results(match_type, relevance_score DESC);

CREATE INDEX idx_search_sessions_user ON search_sessions(user_id, start_time DESC);
CREATE INDEX idx_search_sessions_organization ON search_sessions(organization_id, start_time DESC);
CREATE INDEX idx_search_sessions_duration ON search_sessions(session_duration_seconds DESC);
CREATE INDEX idx_search_sessions_queries ON search_sessions(total_queries DESC);

CREATE INDEX idx_rag_evaluations_query ON rag_evaluations(search_query_id);
CREATE INDEX idx_rag_evaluations_org ON rag_evaluations(organization_id, created_at DESC);
CREATE INDEX idx_rag_evaluations_overall ON rag_evaluations(overall_score DESC);
CREATE INDEX idx_rag_evaluations_thresholds ON rag_evaluations(meets_thresholds, created_at DESC);
CREATE INDEX idx_rag_evaluations_answer_relevancy ON rag_evaluations(answer_relevancy_score DESC);
CREATE INDEX idx_rag_evaluations_faithfulness ON rag_evaluations(faithfulness_score DESC);
CREATE INDEX idx_rag_evaluations_contextual ON rag_evaluations(contextual_relevancy_score DESC);

CREATE INDEX idx_user_feedback_user ON user_feedback(user_id, created_at DESC);
CREATE INDEX idx_user_feedback_org ON user_feedback(organization_id, created_at DESC);
CREATE INDEX idx_user_feedback_type ON user_feedback(feedback_type, created_at DESC);
CREATE INDEX idx_user_feedback_rating ON user_feedback(rating, created_at DESC);
CREATE INDEX idx_user_feedback_reviewed ON user_feedback(is_reviewed, created_at DESC);

-- Enable Row Level Security
ALTER TABLE search_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag_evaluations ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_feedback ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for search tables
CREATE POLICY search_queries_org_policy ON search_queries
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY search_results_org_policy ON search_results
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY rag_evaluations_org_policy ON rag_evaluations
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Triggers for automatic updates and calculations
CREATE OR REPLACE FUNCTION update_search_session_metrics()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- Update session metrics
        UPDATE search_sessions
        SET
            total_queries = total_queries + 1,
            total_results = total_results + NEW.total_results,
            avg_response_time_ms = CASE
                WHEN avg_response_time_ms IS NULL THEN NEW.total_time_ms
                ELSE ROUND((avg_response_time_ms * total_queries + NEW.total_time_ms) / (total_queries + 1))
            END,
            updated_at = NOW()
        WHERE id = NEW.session_id;

        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER search_session_metrics_trigger
    AFTER INSERT ON search_queries
    FOR EACH ROW
    WHEN (NEW.session_id IS NOT NULL)
    EXECUTE FUNCTION update_search_session_metrics();

CREATE OR REPLACE FUNCTION update_search_result_click()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.was_clicked = TRUE AND (OLD.was_clicked IS FALSE OR OLD.was_clicked IS NULL) THEN
        -- Update query click metrics
        UPDATE search_queries
        SET
            clicked_result_positions = array_append(
                COALESCE(clicked_result_positions, ARRAY[]::INTEGER[]),
                NEW.rank_position
            ),
            clicked_document_ids = array_append(
                COALESCE(clicked_document_ids, ARRAY[]::UUID[]),
                NEW.document_id
            )
        WHERE id = NEW.search_query_id;

        -- Update session click metrics
        UPDATE search_sessions
        SET total_clicks = total_clicks + 1
        WHERE id = (
            SELECT session_id FROM search_queries WHERE id = NEW.search_query_id
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER search_result_click_trigger
    AFTER UPDATE ON search_results
    FOR EACH ROW
    EXECUTE FUNCTION update_search_result_click();

-- Function to create monthly partitions automatically
CREATE OR REPLACE FUNCTION create_monthly_partition(table_name TEXT, start_date DATE)
RETURNS VOID AS $$
DECLARE
    partition_name TEXT;
    end_date DATE;
BEGIN
    partition_name := table_name || '_y' || to_char(start_date, 'YYYY') || 'm' || LPAD(EXTRACT(MONTH FROM start_date)::TEXT, 2, '0');
    end_date := start_date + INTERVAL '1 month';

    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                   partition_name, table_name, start_date, end_date);

    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I (organization_id, created_at DESC)',
                   'idx_' || partition_name || '_org', partition_name);
END;
$$ LANGUAGE plpgsql;

COMMIT;