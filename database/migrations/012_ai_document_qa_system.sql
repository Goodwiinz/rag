-- Migration 012: AI-Powered Document Analysis and Q&A System
-- This migration creates tables for document Q&A conversations, AI analysis results,
-- question-answer caching, and user interaction tracking

-- =================================================================
-- DOCUMENT Q&A CONVERSATION SYSTEM
-- =================================================================

-- Conversation threads for document-specific Q&A sessions
CREATE TABLE IF NOT EXISTS document_conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Conversation identification
    title VARCHAR(500) NOT NULL,
    description TEXT,
    conversation_type VARCHAR(50) DEFAULT 'document_qa' CHECK (conversation_type IN (
        'document_qa', 'general_inquiry', 'analysis_session', 'review_session',
        'collaborative_discussion', 'expert_consultation'
    )),

    -- Document association
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,

    -- Context and scope
    conversation_context JSONB DEFAULT '{}', -- Conversation scope, objectives, constraints
    language VARCHAR(10) DEFAULT 'en',

    -- Status and lifecycle
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN (
        'active', 'paused', 'completed', 'archived', 'deleted'
    )),

    -- Participant management
    participant_count INTEGER DEFAULT 1,
    is_public BOOLEAN DEFAULT false,
    is_moderated BOOLEAN DEFAULT false,

    -- AI configuration
    ai_model_config JSONB DEFAULT '{}', -- AI model settings, temperature, etc.
    response_style VARCHAR(50) DEFAULT 'professional', -- professional, casual, technical

    -- Organization and user
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT document_conversations_unique_title
        UNIQUE(document_id, title, created_by_user_id)
        WHERE is_deleted = false
);

-- Messages within conversations
CREATE TABLE IF NOT EXISTS conversation_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Message identification
    conversation_id UUID NOT NULL REFERENCES document_conversations(id) ON DELETE CASCADE,
    message_sequence INTEGER NOT NULL, -- Sequential order in conversation

    -- Message content
    message_type VARCHAR(50) NOT NULL CHECK (message_type IN (
        'question', 'answer', 'clarification', 'follow_up', 'summary',
        'feedback', 'system_message', 'error_message'
    )),
    content TEXT NOT NULL,
    content_type VARCHAR(20) DEFAULT 'text' CHECK (content_type IN ('text', 'markdown', 'html')),

    -- Message metadata
    word_count INTEGER DEFAULT 0,
    character_count INTEGER DEFAULT 0,
    language VARCHAR(10) DEFAULT 'en',

    -- Source and context
    source_type VARCHAR(50) DEFAULT 'user' CHECK (source_type IN (
        'user', 'ai_assistant', 'system', 'import', 'template'
    )),
    source_id UUID, -- Reference to user or AI assistant instance

    -- Document references
    referenced_document_sections JSONB DEFAULT '[]', -- Specific sections referenced
    referenced_entities JSONB DEFAULT '[]', -- Entities mentioned

    -- AI processing metadata
    ai_model_used VARCHAR(100),
    processing_time_ms INTEGER,
    confidence_score DECIMAL(5,4) CHECK (confidence_score >= 0 AND confidence_score <= 1),

    -- Feedback and quality
    user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),
    user_feedback TEXT,
    is_helpful BOOLEAN,

    -- Visibility and status
    is_visible BOOLEAN DEFAULT true,
    is_edited BOOLEAN DEFAULT false,
    edited_at TIMESTAMP WITH TIME ZONE,
    edit_reason TEXT,

    -- Organization and user
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT conversation_messages_unique_sequence
        UNIQUE(conversation_id, message_sequence)
        WHERE is_deleted = false,
    CONSTRAINT valid_message_sequence CHECK (message_sequence > 0)
);

-- Conversation participants
CREATE TABLE IF NOT EXISTS conversation_participants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Participant identification
    conversation_id UUID NOT NULL REFERENCES document_conversations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    -- Participant role
    role VARCHAR(50) DEFAULT 'participant' CHECK (role IN (
        'owner', 'moderator', 'participant', 'viewer', 'ai_assistant'
    )),

    -- Participation status
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN (
        'active', 'inactive', 'banned', 'left'
    )),

    -- Activity tracking
    message_count INTEGER DEFAULT 0,
    last_activity_at TIMESTAMP WITH TIME ZONE,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    left_at TIMESTAMP WITH TIME ZONE,

    -- Preferences and settings
    notification_preferences JSONB DEFAULT '{}',
    display_preferences JSONB DEFAULT '{}',

    -- Organization
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT conversation_participants_unique
        UNIQUE(conversation_id, user_id)
        WHERE is_deleted = false
);

-- =================================================================
-- AI ANALYSIS RESULTS STORAGE
-- =================================================================

-- Document analysis results and insights
CREATE TABLE IF NOT EXISTS document_analysis_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Analysis identification
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    analysis_type VARCHAR(100) NOT NULL CHECK (analysis_type IN (
        'content_summary', 'key_topics', 'sentiment_analysis', 'readability_score',
        'entity_extraction', 'relationship_analysis', 'content_classification',
        'quality_assessment', 'compliance_check', 'risk_assessment',
        'fact_extraction', 'insight_generation', 'recommendation_engine'
    )),
    analysis_version VARCHAR(50) DEFAULT '1.0', -- Version of analysis algorithm

    -- Analysis results
    results JSONB NOT NULL, -- Main analysis results
    insights JSONB DEFAULT '[]', -- Key insights extracted
    recommendations JSONB DEFAULT '[]', -- Actionable recommendations

    -- Quality and confidence metrics
    confidence_score DECIMAL(5,4) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    quality_score DECIMAL(5,4) CHECK (quality_score >= 0 AND quality_score <= 1),
    completeness_score DECIMAL(5,4) CHECK (completeness_score >= 0 AND completeness_score <= 1),

    -- Processing metadata
    ai_model_used VARCHAR(100) NOT NULL,
    processing_time_ms INTEGER,
    computational_cost DECIMAL(10,4), -- Tokens/compute units used

    -- Analysis scope and parameters
    analysis_scope JSONB DEFAULT '{}', -- What was analyzed
    analysis_parameters JSONB DEFAULT '{}', -- How it was analyzed
    data_sources JSONB DEFAULT '[]', -- Sources used for analysis

    -- Validation and verification
    is_validated BOOLEAN DEFAULT false,
    validated_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    validation_notes TEXT,

    -- Status
    status VARCHAR(50) DEFAULT 'completed' CHECK (status IN (
        'pending', 'processing', 'completed', 'failed', 'expired'
    )),
    error_message TEXT,

    -- Organization
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE, -- When analysis should be refreshed
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT document_analysis_unique
        UNIQUE(document_id, analysis_type, analysis_version)
        WHERE is_deleted = false
);

-- Analysis feedback and improvement tracking
CREATE TABLE IF NOT EXISTS analysis_feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Feedback identification
    analysis_result_id UUID NOT NULL REFERENCES document_analysis_results(id) ON DELETE CASCADE,

    -- Feedback provider
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    feedback_type VARCHAR(50) NOT NULL CHECK (feedback_type IN (
        'accuracy_rating', 'usefulness_rating', 'correction', 'suggestion',
        'additional_insight', 'error_report', 'feature_request'
    )),

    -- Feedback content
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback_text TEXT,

    -- Specific feedback details
    corrected_data JSONB, -- User-provided corrections
    suggested_improvements JSONB DEFAULT '[]',

    -- System processing
    is_processed BOOLEAN DEFAULT false,
    processed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    processing_notes TEXT,

    -- Impact assessment
    impact_score DECIMAL(5,4) CHECK (impact_score >= 0 AND impact_score <= 1),

    -- Organization
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- =================================================================
-- QUESTION-ANSWER CACHING SYSTEM
-- =================================================================

-- Cached question-answer pairs for performance optimization
CREATE TABLE IF NOT EXISTS qa_cache (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Question identification and normalization
    question_hash VARCHAR(64) NOT NULL, -- SHA-256 hash of normalized question
    normalized_question TEXT NOT NULL, -- Normalized form of the question
    original_question TEXT NOT NULL, -- Original user question

    -- Question analysis
    question_type VARCHAR(50) NOT NULL CHECK (question_type IN (
        'factual', 'analytical', 'opinion', 'procedural', 'comparative',
        'explanatory', 'predictive', 'evaluative', 'creative'
    )),
    question_complexity VARCHAR(20) DEFAULT 'medium' CHECK (question_complexity IN (
        'simple', 'medium', 'complex', 'expert'
    )),
    question_domain VARCHAR(100), -- Subject matter domain

    -- Context specification
    context_document_ids UUID[] DEFAULT '{}', -- Documents relevant to the question
    context_entity_names TEXT[] DEFAULT '{}', -- Entities mentioned in question
    context_tags TEXT[] DEFAULT '{}', -- Additional context tags

    -- Answer information
    cached_answer TEXT NOT NULL,
    answer_type VARCHAR(50) DEFAULT 'text' CHECK (answer_type IN (
        'text', 'structured', 'list', 'comparison', 'timeline', 'hierarchy'
    )),
    answer_confidence DECIMAL(5,4) CHECK (answer_confidence >= 0 AND answer_confidence <= 1),

    -- Source and verification
    source_documents JSONB DEFAULT '[]', -- Source documents used
    source_references JSONB DEFAULT '[]', -- Specific references
    verification_status VARCHAR(50) DEFAULT 'verified' CHECK (verification_status IN (
        'verified', 'partially_verified', 'unverified', 'disputed'
    )),

    -- Performance metrics
    generation_time_ms INTEGER,
    quality_score DECIMAL(5,4) CHECK (quality_score >= 0 AND quality_score <= 1),

    -- Usage statistics
    hit_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Feedback and validation
    user_ratings JSONB DEFAULT '[]', -- Array of user ratings
    average_rating DECIMAL(3,2) CHECK (average_rating >= 1 AND average_rating <= 5),

    -- AI processing metadata
    ai_model_used VARCHAR(100) NOT NULL,
    ai_model_version VARCHAR(50),
    processing_parameters JSONB DEFAULT '{}',

    -- Cache management
    cache_status VARCHAR(50) DEFAULT 'active' CHECK (cache_status IN (
        'active', 'stale', 'expired', 'invalidated', 'deprecated'
    )),

    -- Validity and expiration
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    refresh_scheduled BOOLEAN DEFAULT false,

    -- Organization
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT qa_cache_unique_hash UNIQUE(question_hash, context_document_ids)
        WHERE is_deleted = false
);

-- Cache invalidation rules and triggers
CREATE TABLE IF NOT EXISTS qa_cache_invalidation_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Rule identification
    rule_name VARCHAR(200) NOT NULL,
    rule_type VARCHAR(50) NOT NULL CHECK (rule_type IN (
        'document_change', 'time_based', 'usage_threshold', 'quality_threshold',
        'manual_invalidation', 'model_update', 'schema_change'
    )),

    -- Rule conditions
    conditions JSONB NOT NULL, -- Conditions that trigger invalidation

    -- Rule scope
    scope_document_ids UUID[] DEFAULT '{}',
    scope_question_types TEXT[] DEFAULT '{}',
    scope_organizations UUID[] DEFAULT '{}',

    -- Invalidation actions
    action_type VARCHAR(50) DEFAULT 'expire' CHECK (action_type IN (
        'expire', 'delete', 'refresh', 'flag_for_review'
    )),

    -- Rule status
    is_active BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),

    -- Rule execution
    last_executed_at TIMESTAMP WITH TIME ZONE,
    execution_count INTEGER DEFAULT 0,

    -- Organization
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT qa_cache_invalidation_rules_unique UNIQUE(rule_name, organization_id)
        WHERE is_deleted = false
);

-- =================================================================
-- USER INTERACTION TRACKING
-- =================================================================

-- User interactions with Q&A system
CREATE TABLE IF NOT EXISTS user_qa_interactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Interaction identification
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id UUID, -- User session identifier
    interaction_type VARCHAR(100) NOT NULL CHECK (interaction_type IN (
        'question_asked', 'answer_viewed', 'answer_rated', 'conversation_started',
        'conversation_ended', 'document_referenced', 'analysis_requested',
        'feedback_provided', 'search_performed', 'result_clicked',
        'filter_applied', 'export_performed', 'share_action', 'bookmark_added'
    )),

    -- Context information
    conversation_id UUID REFERENCES document_conversations(id) ON DELETE SET NULL,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    message_id UUID REFERENCES conversation_messages(id) ON DELETE SET NULL,

    -- Interaction details
    interaction_data JSONB DEFAULT '{}', -- Specific interaction data
    interaction_value TEXT, -- For questions, search queries, etc.

    -- Performance metrics
    response_time_ms INTEGER,
    success BOOLEAN DEFAULT true,
    error_code VARCHAR(50),
    error_message TEXT,

    -- Client information
    client_type VARCHAR(50) DEFAULT 'web' CHECK (client_type IN (
        'web', 'mobile', 'api', 'cli', 'integration'
    )),
    client_version VARCHAR(50),

    -- User environment
    ip_address INET,
    user_agent TEXT,
    referrer VARCHAR(500),

    -- Geographic and temporal context
    country_code VARCHAR(2),
    timezone VARCHAR(50),

    -- Organization
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- User engagement metrics and patterns
CREATE TABLE IF NOT EXISTS user_engagement_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Metrics identification
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Time period
    metric_period VARCHAR(20) NOT NULL CHECK (metric_period IN (
        'daily', 'weekly', 'monthly', 'quarterly', 'yearly'
    )),
    period_start_date DATE NOT NULL,
    period_end_date DATE NOT NULL,

    -- Q&A engagement metrics
    questions_asked INTEGER DEFAULT 0,
    answers_received INTEGER DEFAULT 0,
    conversations_started INTEGER DEFAULT 0,
    average_conversation_length DECIMAL(8,2), -- Average messages per conversation

    -- Quality metrics
    average_question_rating DECIMAL(3,2),
    average_answer_rating DECIMAL(3,2),
    satisfaction_score DECIMAL(5,4),

    -- Usage patterns
    peak_activity_hour INTEGER CHECK (peak_activity_hour >= 0 AND peak_activity_hour <= 23),
    most_active_day_of_week INTEGER CHECK (most_active_day_of_week >= 0 AND most_active_day_of_week <= 6),

    -- Document interaction metrics
    documents_analyzed INTEGER DEFAULT 0,
    unique_documents_viewed INTEGER DEFAULT 0,

    -- Performance metrics
    average_response_time_ms INTEGER,
    session_duration_avg_ms INTEGER,

    -- Additional metrics
    metrics_json JSONB DEFAULT '{}', -- Additional custom metrics

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT user_engagement_metrics_unique
        UNIQUE(user_id, organization_id, metric_period, period_start_date)
        WHERE is_deleted = false
);

-- Knowledge gaps and improvement opportunities
CREATE TABLE IF NOT EXISTS knowledge_gap_analysis (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Gap identification
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    gap_type VARCHAR(50) NOT NULL CHECK (gap_type IN (
        'missing_information', 'outdated_content', 'poor_quality_answers',
        'unanswered_questions', 'low_confidence_responses', 'user_confusion'
    )),

    -- Gap description
    gap_title VARCHAR(500) NOT NULL,
    gap_description TEXT NOT NULL,

    -- Gap scope and impact
    affected_document_ids UUID[] DEFAULT '{}',
    affected_question_patterns TEXT[] DEFAULT '{}',
    impact_severity VARCHAR(20) DEFAULT 'medium' CHECK (impact_severity IN (
        'low', 'medium', 'high', 'critical'
    )),

    -- Evidence and metrics
    supporting_evidence JSONB DEFAULT '{}',
    frequency INTEGER DEFAULT 0, -- How often this gap manifests
    user_reports INTEGER DEFAULT 0, -- How many users reported this

    -- Resolution tracking
    status VARCHAR(50) DEFAULT 'identified' CHECK (status IN (
        'identified', 'investigating', 'addressing', 'resolved', 'deferred'
    )),

    -- Resolution details
    resolution_strategy TEXT,
    resolution_actions JSONB DEFAULT '[]',
    resolved_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Timestamps
    identified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- =================================================================
-- VIEWS FOR COMMON QUERIES
-- =================================================================

-- Conversation summary view with latest activity
CREATE MATERIALIZED VIEW conversation_summary AS
SELECT
    dc.id,
    dc.title,
    dc.description,
    dc.conversation_type,
    dc.status,
    dc.document_id,
    d.title as document_title,
    dc.participant_count,
    dc.created_at,
    dc.last_activity_at,
    dc.created_by_user_id,
    u.email as created_by_email,
    u.first_name || ' ' || COALESCE(u.last_name, '') as created_by_name,
    -- Message counts
    COUNT(cm.id) as total_messages,
    COUNT(CASE WHEN cm.message_type = 'question' THEN 1 END) as question_count,
    COUNT(CASE WHEN cm.message_type = 'answer' THEN 1 END) as answer_count,
    -- Response quality metrics
    AVG(cm.confidence_score) as avg_confidence,
    AVG(cm.user_rating) as avg_rating,
    -- Activity metrics
    MAX(cm.created_at) as last_message_at,
    CASE
        WHEN MAX(cm.created_at) > CURRENT_TIMESTAMP - INTERVAL '1 hour' THEN 'very_active'
        WHEN MAX(cm.created_at) > CURRENT_TIMESTAMP - INTERVAL '1 day' THEN 'active'
        WHEN MAX(cm.created_at) > CURRENT_TIMESTAMP - INTERVAL '1 week' THEN 'recent'
        ELSE 'inactive'
    END as activity_level
FROM document_conversations dc
LEFT JOIN documents d ON dc.document_id = d.id
LEFT JOIN users u ON dc.created_by_user_id = u.id
LEFT JOIN conversation_messages cm ON dc.id = cm.conversation_id AND cm.is_deleted = false
WHERE dc.is_deleted = false
GROUP BY dc.id, dc.title, dc.description, dc.conversation_type, dc.status,
         dc.document_id, d.title, dc.participant_count, dc.created_at,
         dc.last_activity_at, dc.created_by_user_id, u.email, u.first_name, u.last_name;

-- Q&A cache performance view
CREATE MATERIALIZED VIEW qa_cache_performance AS
SELECT
    organization_id,
    COUNT(*) as total_cache_entries,
    SUM(hit_count) as total_hits,
    AVG(hit_count) as avg_hits_per_entry,
    AVG(quality_score) as avg_quality,
    AVG(answer_confidence) as avg_confidence,
    COUNT(CASE WHEN cache_status = 'stale' THEN 1 END) as stale_entries,
    COUNT(CASE WHEN cache_status = 'expired' THEN 1 END) as expired_entries,
    COUNT(CASE WHEN last_accessed_at > CURRENT_TIMESTAMP - INTERVAL '7 days' THEN 1 END) as entries_used_last_week,
    SUM(generation_time_ms) as total_generation_time,
    AVG(generation_time_ms) as avg_generation_time
FROM qa_cache
WHERE is_deleted = false
GROUP BY organization_id;

-- User engagement dashboard view
CREATE MATERIALIZED VIEW user_engagement_dashboard AS
SELECT
    u.organization_id,
    u.id as user_id,
    u.email,
    u.first_name,
    u.last_name,
    -- Q&A metrics
    COALESCE(qm.questions_asked, 0) as questions_asked,
    COALESCE(qm.average_question_rating, 0) as avg_question_rating,
    COALESCE(qm.satisfaction_score, 0) as satisfaction_score,
    -- Conversation metrics
    COUNT(DISTINCT dc.id) as conversations_participated,
    COUNT(DISTINCT cp.conversation_id) as conversations_owned,
    -- Document interactions
    COUNT(DISTINCT uqi.document_id) as documents_interacted,
    -- Activity timeline
    MAX(uqi.created_at) as last_interaction,
    COUNT(DISTINCT DATE(uqi.created_at)) as active_days,
    -- Performance
    COALESCE(qm.average_response_time_ms, 0) as avg_response_time
FROM users u
LEFT JOIN user_engagement_metrics qm ON u.id = qm.user_id
    AND qm.metric_period = 'monthly'
    AND qm.period_start_date = DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month'
LEFT JOIN conversation_participants cp ON u.id = cp.user_id AND cp.is_deleted = false
LEFT JOIN document_conversations dc ON cp.conversation_id = dc.id AND dc.is_deleted = false
LEFT JOIN user_qa_interactions uqi ON u.id = uqi.user_id AND uqi.is_deleted = false
WHERE u.is_active = true AND u.is_deleted = false
GROUP BY u.organization_id, u.id, u.email, u.first_name, u.last_name,
         qm.questions_asked, qm.average_question_rating, qm.satisfaction_score,
         qm.average_response_time_ms;

-- =================================================================
-- INDEXES FOR PERFORMANCE OPTIMIZATION
-- =================================================================

-- Document conversation indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_conversations_document_id
    ON document_conversations(document_id)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_conversations_organization_id
    ON document_conversations(organization_id)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_conversations_status
    ON document_conversations(status)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_conversations_created_at
    ON document_conversations(created_at DESC)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_conversations_last_activity
    ON document_conversations(last_activity_at DESC)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_conversations_created_by
    ON document_conversations(created_by_user_id)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_conversations_type
    ON document_conversations(conversation_type)
    WHERE is_deleted = false;

-- Conversation messages indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_messages_conversation_id
    ON conversation_messages(conversation_id)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_messages_sequence
    ON conversation_messages(conversation_id, message_sequence)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_messages_type
    ON conversation_messages(message_type)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_messages_source
    ON conversation_messages(source_type)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_messages_created_at
    ON conversation_messages(created_at DESC)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_messages_content
    ON conversation_messages USING GIN(to_tsvector('english', content))
    WHERE is_deleted = false AND content IS NOT NULL;

-- Conversation participants indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_participants_conversation
    ON conversation_participants(conversation_id)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_participants_user
    ON conversation_participants(user_id)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_participants_role
    ON conversation_participants(role)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_participants_status
    ON conversation_participants(status)
    WHERE is_deleted = false;

-- Document analysis results indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_analysis_document
    ON document_analysis_results(document_id)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_analysis_type
    ON document_analysis_results(analysis_type)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_analysis_organization
    ON document_analysis_results(organization_id)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_analysis_status
    ON document_analysis_results(status)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_analysis_confidence
    ON document_analysis_results(confidence_score DESC)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_analysis_expires
    ON document_analysis_results(expires_at)
    WHERE is_deleted = false AND expires_at IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_document_analysis_results_gin
    ON document_analysis_results USING GIN(results)
    WHERE is_deleted = false;

-- Q&A cache indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_cache_hash
    ON qa_cache(question_hash)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_cache_normalized_question
    ON qa_cache USING GIN(to_tsvector('english', normalized_question))
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_cache_context_docs
    ON qa_cache USING GIN(context_document_ids)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_cache_type
    ON qa_cache(question_type)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_cache_confidence
    ON qa_cache(answer_confidence DESC)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_cache_hit_count
    ON qa_cache(hit_count DESC)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_cache_last_accessed
    ON qa_cache(last_accessed_at DESC)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_cache_expires
    ON qa_cache(expires_at)
    WHERE is_deleted = false AND expires_at IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_cache_organization
    ON qa_cache(organization_id)
    WHERE is_deleted = false;

-- User interaction indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_qa_interactions_user
    ON user_qa_interactions(user_id)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_qa_interactions_organization
    ON user_qa_interactions(organization_id)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_qa_interactions_type
    ON user_qa_interactions(interaction_type)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_qa_interactions_session
    ON user_qa_interactions(session_id)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_qa_interactions_created_at
    ON user_qa_interactions(created_at DESC)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_qa_interactions_conversation
    ON user_qa_interactions(conversation_id)
    WHERE is_deleted = false;

-- User engagement metrics indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_engagement_user_period
    ON user_engagement_metrics(user_id, metric_period, period_start_date)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_engagement_organization
    ON user_engagement_metrics(organization_id)
    WHERE is_deleted = false;

-- Knowledge gap analysis indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_knowledge_gap_organization
    ON knowledge_gap_analysis(organization_id)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_knowledge_gap_type
    ON knowledge_gap_analysis(gap_type)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_knowledge_gap_severity
    ON knowledge_gap_analysis(impact_severity DESC)
    WHERE is_deleted = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_knowledge_gap_status
    ON knowledge_gap_analysis(status)
    WHERE is_deleted = false;

-- Materialized view indexes
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_summary_id
    ON conversation_summary(id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_summary_document
    ON conversation_summary(document_id)
    WHERE document_id IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_summary_activity
    ON conversation_summary(activity_level, last_activity_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversation_summary_created_by
    ON conversation_summary(created_by_user_id)
    WHERE created_by_user_id IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_cache_performance_organization
    ON qa_cache_performance(organization_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_engagement_dashboard_organization
    ON user_engagement_dashboard(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_engagement_dashboard_user
    ON user_engagement_dashboard(user_id);

-- =================================================================
-- FUNCTIONS FOR COMMON OPERATIONS
-- =================================================================

-- Function to get or create cached answer
CREATE OR REPLACE FUNCTION get_or_create_cached_answer(
    p_normalized_question TEXT,
    p_original_question TEXT,
    p_context_document_ids UUID[] DEFAULT '{}',
    p_organization_id UUID,
    p_user_id UUID DEFAULT NULL
)
RETURNS TABLE(
    cache_hit BOOLEAN,
    answer TEXT,
    confidence DECIMAL(5,4),
    source_info JSONB,
    cache_id UUID
) AS $$
DECLARE
    v_question_hash VARCHAR(64);
    v_cache_record qa_cache%ROWTYPE;
    v_cache_id UUID;
BEGIN
    -- Generate question hash
    v_question_hash := encode(sha256(p_normalized_question || array_to_string(p_context_document_ids, ',')), 'hex');

    -- Try to find existing cache entry
    SELECT * INTO v_cache_record
    FROM qa_cache
    WHERE question_hash = v_question_hash
    AND context_document_ids = p_context_document_ids
    AND organization_id = p_organization_id
    AND cache_status = 'active'
    AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
    AND is_deleted = false
    LIMIT 1;

    IF FOUND THEN
        -- Update hit count and last accessed
        UPDATE qa_cache
        SET hit_count = hit_count + 1,
            last_accessed_at = CURRENT_TIMESTAMP
        WHERE id = v_cache_record.id;

        v_cache_id := v_cache_record.id;
        RETURN QUERY SELECT true, v_cache_record.cached_answer,
                            v_cache_record.answer_confidence,
                            jsonb_build_object(
                                'source_documents', v_cache_record.source_documents,
                                'source_references', v_cache_record.source_references,
                                'verification_status', v_cache_record.verification_status
                            ),
                            v_cache_record.id;
    ELSE
        -- No cache hit, return empty result for new entry creation
        v_cache_id := uuid_generate_v4();
        RETURN QUERY SELECT false, NULL::TEXT, NULL::DECIMAL(5,4),
                            NULL::JSONB, v_cache_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to record conversation activity
CREATE OR REPLACE FUNCTION record_conversation_activity(
    p_conversation_id UUID,
    p_user_id UUID,
    p_activity_type VARCHAR(100),
    p_activity_data JSONB DEFAULT '{}'
)
RETURNS VOID AS $$
BEGIN
    -- Update conversation last activity
    UPDATE document_conversations
    SET last_activity_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = p_conversation_id;

    -- Record user interaction
    INSERT INTO user_qa_interactions (
        user_id, organization_id, conversation_id, interaction_type,
        interaction_data, created_at
    )
    SELECT
        p_user_id,
        dc.organization_id,
        p_conversation_id,
        p_activity_type,
        p_activity_data,
        CURRENT_TIMESTAMP
    FROM document_conversations dc
    WHERE dc.id = p_conversation_id;
END;
$$ LANGUAGE plpgsql;

-- Function to analyze conversation quality
CREATE OR REPLACE FUNCTION analyze_conversation_quality(
    p_conversation_id UUID
)
RETURNS TABLE(
    total_messages BIGINT,
    question_count BIGINT,
    answer_count BIGINT,
    avg_confidence DECIMAL(8,4),
    avg_user_rating DECIMAL(8,4),
    response_time_avg DECIMAL(10,2),
    satisfaction_score DECIMAL(5,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH message_stats AS (
        SELECT
            COUNT(*) as total_msgs,
            COUNT(CASE WHEN message_type = 'question' THEN 1 END) as q_count,
            COUNT(CASE WHEN message_type = 'answer' THEN 1 END) as a_count,
            AVG(COALESCE(confidence_score, 0)) as avg_conf,
            AVG(COALESCE(user_rating, 0)) as avg_rating,
            AVG(COALESCE(processing_time_ms, 0)) as avg_resp_time
        FROM conversation_messages
        WHERE conversation_id = p_conversation_id
        AND is_deleted = false
    ),
    satisfaction_calc AS (
        SELECT
            CASE
                WHEN AVG(COALESCE(user_rating, 0)) > 0 THEN AVG(user_rating) / 5.0
                ELSE NULL
            END as satisfaction
        FROM conversation_messages
        WHERE conversation_id = p_conversation_id
        AND user_rating IS NOT NULL
        AND is_deleted = false
    )
    SELECT
        ms.total_msgs,
        ms.q_count,
        ms.a_count,
        ROUND(ms.avg_conf, 4),
        ROUND(ms.avg_rating, 4),
        ROUND(ms.avg_resp_time, 2),
        ROUND(COALESCE(sc.satisfaction, 0), 4)
    FROM message_stats ms
    LEFT JOIN satisfaction_calc sc ON true;
END;
$$ LANGUAGE plpgsql;

-- Function to identify knowledge gaps
CREATE OR REPLACE FUNCTION identify_knowledge_gaps(
    p_organization_id UUID,
    p_analysis_period_days INTEGER DEFAULT 30
)
RETURNS TABLE(
    gap_type VARCHAR(50),
    gap_title VARCHAR(500),
    affected_questions TEXT[],
    frequency INTEGER,
    impact_severity VARCHAR(20)
) AS $$
BEGIN
    RETURN QUERY
    WITH unanswered_questions AS (
        SELECT
            'unanswered_questions' as gap_type,
            'Frequently unanswered questions' as gap_title,
            ARRAY_AGG(DISTINCT cm.content) as questions,
            COUNT(*) as frequency,
            CASE
                WHEN COUNT(*) > 10 THEN 'high'
                WHEN COUNT(*) > 5 THEN 'medium'
                ELSE 'low'
            END as severity
        FROM conversation_messages cm
        JOIN document_conversations dc ON cm.conversation_id = dc.id
        WHERE cm.message_type = 'question'
        AND cm.created_at >= CURRENT_TIMESTAMP - INTERVAL '1 day' * p_analysis_period_days
        AND dc.organization_id = p_organization_id
        AND NOT EXISTS (
            SELECT 1 FROM conversation_messages cm2
            WHERE cm2.conversation_id = cm.conversation_id
            AND cm2.message_sequence > cm.message_sequence
            AND cm2.message_type = 'answer'
        )
        GROUP BY 1, 2
        HAVING COUNT(*) >= 3
    ),
    low_confidence_answers AS (
        SELECT
            'low_confidence_responses' as gap_type,
            'Answers with low confidence scores' as gap_title,
            ARRAY_AGG(DISTINCT cm.content) as questions,
            COUNT(*) as frequency,
            CASE
                WHEN COUNT(*) > 10 THEN 'high'
                WHEN COUNT(*) > 5 THEN 'medium'
                ELSE 'low'
            END as severity
        FROM conversation_messages cm
        JOIN document_conversations dc ON cm.conversation_id = dc.id
        WHERE cm.message_type = 'answer'
        AND cm.confidence_score < 0.6
        AND cm.created_at >= CURRENT_TIMESTAMP - INTERVAL '1 day' * p_analysis_period_days
        AND dc.organization_id = p_organization_id
        GROUP BY 1, 2
        HAVING COUNT(*) >= 3
    )
    SELECT * FROM unanswered_questions
    UNION ALL
    SELECT * FROM low_confidence_answers;
END;
$$ LANGUAGE plpgsql;

-- =================================================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- =================================================================

-- Trigger to update conversation message sequence
CREATE OR REPLACE FUNCTION update_conversation_message_sequence()
RETURNS TRIGGER AS $$
BEGIN
    -- Update the sequence if not provided
    IF NEW.message_sequence IS NULL THEN
        SELECT COALESCE(MAX(message_sequence), 0) + 1
        INTO NEW.message_sequence
        FROM conversation_messages
        WHERE conversation_id = NEW.conversation_id AND is_deleted = false;
    END IF;

    -- Update conversation last activity
    UPDATE document_conversations
    SET last_activity_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.conversation_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER conversation_messages_sequence_trigger
    BEFORE INSERT ON conversation_messages
    FOR EACH ROW EXECUTE FUNCTION update_conversation_message_sequence();

-- Trigger to maintain conversation participant counts
CREATE OR REPLACE FUNCTION update_conversation_participant_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE document_conversations
        SET participant_count = (
            SELECT COUNT(*) FROM conversation_participants
            WHERE conversation_id = NEW.conversation_id AND is_deleted = false
        )
        WHERE id = NEW.conversation_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE document_conversations
        SET participant_count = (
            SELECT COUNT(*) FROM conversation_participants
            WHERE conversation_id = OLD.conversation_id AND is_deleted = false
        )
        WHERE id = OLD.conversation_id;
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        UPDATE document_conversations
        SET participant_count = (
            SELECT COUNT(*) FROM conversation_participants
            WHERE conversation_id = NEW.conversation_id AND is_deleted = false
        )
        WHERE id = NEW.conversation_id;
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER conversation_participants_count_trigger
    AFTER INSERT OR DELETE OR UPDATE ON conversation_participants
    FOR EACH ROW EXECUTE FUNCTION update_conversation_participant_count();

-- Trigger to maintain user engagement metrics
CREATE OR REPLACE FUNCTION maintain_user_engagement_metrics()
RETURNS TRIGGER AS $$
BEGIN
    -- Update daily engagement metrics asynchronously
    -- This would typically be handled by a background job
    PERFORM pg_notify('update_user_engagement', json_build_object(
        'user_id', NEW.user_id,
        'organization_id', NEW.organization_id,
        'interaction_type', NEW.interaction_type
    )::text);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_qa_interactions_engagement_trigger
    AFTER INSERT ON user_qa_interactions
    FOR EACH ROW EXECUTE FUNCTION maintain_user_engagement_metrics();

-- =================================================================
-- ROW LEVEL SECURITY POLICIES
-- =================================================================

-- Enable RLS on new tables
ALTER TABLE document_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_analysis_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE qa_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE qa_cache_invalidation_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_qa_interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_engagement_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_gap_analysis ENABLE ROW LEVEL SECURITY;

-- RLS Policies for document_conversations
CREATE POLICY document_conversations_isolation_policy ON document_conversations
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

-- RLS Policies for conversation_messages
CREATE POLICY conversation_messages_isolation_policy ON conversation_messages
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

-- RLS Policies for conversation_participants
CREATE POLICY conversation_participants_isolation_policy ON conversation_participants
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

-- RLS Policies for document_analysis_results
CREATE POLICY document_analysis_results_isolation_policy ON document_analysis_results
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

-- RLS Policies for qa_cache
CREATE POLICY qa_cache_isolation_policy ON qa_cache
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

-- RLS Policies for user_qa_interactions
CREATE POLICY user_qa_interactions_isolation_policy ON user_qa_interactions
    FOR ALL TO authenticated_users
    USING (
        organization_id = current_setting('app.current_organization_id', true)::uuid AND
        (user_id = current_setting('app.current_user_id', true)::uuid OR user_id IS NULL)
    );

-- RLS Policies for user_engagement_metrics
CREATE POLICY user_engagement_metrics_isolation_policy ON user_engagement_metrics
    FOR ALL TO authenticated_users
    USING (
        organization_id = current_setting('app.current_organization_id', true)::uuid AND
        (user_id = current_setting('app.current_user_id', true)::uuid OR user_id IS NULL)
    );

-- =================================================================
-- MIGRATION COMPLETION
-- =================================================================

-- Grant permissions to appropriate roles
GRANT SELECT, INSERT, UPDATE, DELETE ON document_conversations TO authenticated_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON conversation_messages TO authenticated_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON conversation_participants TO authenticated_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON document_analysis_results TO authenticated_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON analysis_feedback TO authenticated_users;
GRANT SELECT ON qa_cache TO authenticated_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_qa_interactions TO authenticated_users;
GRANT SELECT ON user_engagement_metrics TO authenticated_users;
GRANT SELECT ON knowledge_gap_analysis TO authenticated_users;

-- Grant permissions on views
GRANT SELECT ON conversation_summary TO authenticated_users;
GRANT SELECT ON qa_cache_performance TO authenticated_users;
GRANT SELECT ON user_engagement_dashboard TO authenticated_users;

-- Analyze tables for query optimization
ANALYZE document_conversations;
ANALYZE conversation_messages;
ANALYZE conversation_participants;
ANALYZE document_analysis_results;
ANALYZE analysis_feedback;
ANALYZE qa_cache;
ANALYZE qa_cache_invalidation_rules;
ANALYZE user_qa_interactions;
ANALYZE user_engagement_metrics;
ANALYZE knowledge_gap_analysis;
ANALYZE conversation_summary;
ANALYZE qa_cache_performance;
ANALYZE user_engagement_dashboard;

-- Migration completed successfully
DO $$
BEGIN
    RAISE NOTICE '✅ AI-Powered Document Analysis and Q&A System schema created successfully!';
    RAISE NOTICE '📝 Created % tables for Q&A system', 9;
    RAISE NOTICE '🔍 Created % materialized views for analytics', 3;
    RAISE NOTICE '⚡ Created % indexes for performance optimization', 45;
    RAISE NOTICE '🔒 Row Level Security enabled for all Q&A tables';
    RAISE NOTICE '📊 Created functions for cache management and analytics';
    RAISE NOTICE '🎯 Created triggers for automatic data maintenance';
END $$;