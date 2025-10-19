-- Multimodal Enterprise RAG System - PostgreSQL Schema
-- This file creates the complete database schema for all components

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create schemas for multi-tenant organization
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS search;
CREATE SCHEMA IF NOT EXISTS evaluation;
CREATE SCHEMA IF NOT EXISTS security;

-- =================================================================
-- CORE ENTITIES
-- =================================================================

-- Organizations table for multi-tenancy
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    logo_url VARCHAR(500),
    storage_tier VARCHAR(50) DEFAULT 'standard' CHECK (storage_tier IN ('basic', 'standard', 'premium', 'enterprise')),
    max_storage_gb INTEGER DEFAULT 5,
    current_storage_gb INTEGER DEFAULT 0,
    max_users INTEGER DEFAULT 10,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Users table with authentication
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('admin', 'content_manager', 'user', 'analyst')),
    is_active BOOLEAN DEFAULT true,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    last_login TIMESTAMP WITH TIME ZONE,
    login_count INTEGER DEFAULT 0,
    email_verified BOOLEAN DEFAULT false,
    phone_number VARCHAR(20),
    avatar_url VARCHAR(500),
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- =================================================================
-- DOCUMENT MANAGEMENT
-- =================================================================

-- Documents table for multimodal content
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    filename VARCHAR(500) NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    mime_type VARCHAR(100) NOT NULL,
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN (
        'text', 'image', 'audio', 'video', 'pdf', 'spreadsheet', 'presentation', 'multimodal'
    )),
    content_text TEXT,
    content_summary TEXT,
    document_metadata JSONB DEFAULT '{}',
    processing_status VARCHAR(50) DEFAULT 'pending' CHECK (processing_status IN (
        'pending', 'processing', 'completed', 'failed', 'retrying'
    )),
    processing_error TEXT,
    upload_source VARCHAR(50) DEFAULT 'manual' CHECK (upload_source IN ('manual', 'api', 'batch', 'import')),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    uploaded_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    parent_document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    version_number INTEGER DEFAULT 1,
    is_public BOOLEAN DEFAULT false,
    tags TEXT[] DEFAULT '{}',
    language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Multimodal content table
CREATE TABLE IF NOT EXISTS multimodal_content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content_type VARCHAR(50) NOT NULL CHECK (content_type IN (
        'text', 'image', 'audio', 'video', 'chart', 'table', 'diagram'
    )),
    content_data JSONB NOT NULL,
    extraction_method VARCHAR(50) DEFAULT 'automatic',
    quality_score DECIMAL(5,4) CHECK (quality_score >= 0 AND quality_score <= 1),
    coordinates JSONB, -- For spatial content within documents
    temporal_data JSONB, -- For temporal content (audio/video timestamps)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Document versions for change tracking
CREATE TABLE IF NOT EXISTS document_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    changes_summary TEXT,
    file_path VARCHAR(1000),
    file_size_bytes INTEGER,
    content_diff TEXT,
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(document_id, version_number)
);

-- =================================================================
-- KNOWLEDGE GRAPH ENTITIES
-- =================================================================

-- Entities extracted from documents
CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(500) NOT NULL,
    entity_type VARCHAR(100) NOT NULL CHECK (entity_type IN (
        'person', 'organization', 'location', 'date', 'concept', 'product',
        'technology', 'event', 'metric', 'custom'
    )),
    canonical_name VARCHAR(500), -- Standardized name
    aliases TEXT[] DEFAULT '{}',
    description TEXT,
    confidence_score DECIMAL(5,4) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    extraction_method VARCHAR(50) DEFAULT 'ner',
    source_document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Entity relationships
CREATE TABLE IF NOT EXISTS entity_relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relationship_type VARCHAR(100) NOT NULL CHECK (relationship_type IN (
        'related_to', 'part_of', 'located_in', 'works_for', 'knows', 'mentions',
        'employs', 'owns', 'collaborates_with', 'precedes', 'follows', 'custom'
    )),
    relationship_strength DECIMAL(5,4) CHECK (relationship_strength >= 0 AND relationship_strength <= 1),
    source_document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE,
    CHECK(source_entity_id != target_entity_id)
);

-- =================================================================
-- SEARCH AND RETRIEVAL
-- =================================================================

-- Search queries for analytics and optimization
CREATE TABLE IF NOT EXISTS search_queries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    query_type VARCHAR(50) DEFAULT 'semantic' CHECK (query_type IN (
        'semantic', 'keyword', 'hybrid', 'graph', 'multimodal'
    )),
    filters JSONB DEFAULT '{}',
    results_count INTEGER DEFAULT 0,
    latency_ms INTEGER,
    session_id UUID,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Search results for analytics
CREATE TABLE IF NOT EXISTS search_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    search_query_id UUID NOT NULL REFERENCES search_queries(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    result_type VARCHAR(50) NOT NULL CHECK (result_type IN ('document', 'entity', 'hybrid')),
    relevance_score DECIMAL(5,4) CHECK (relevance_score >= 0 AND relevance_score <= 1),
    rank_position INTEGER NOT NULL,
    click_count INTEGER DEFAULT 0,
    feedback_score DECIMAL(3,2) CHECK (feedback_score >= -1 AND feedback_score <= 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- =================================================================
-- PROCESSING AND ASYNC JOBS
-- =================================================================

-- Processing jobs for background tasks
CREATE TABLE IF NOT EXISTS processing_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_type VARCHAR(50) NOT NULL CHECK (job_type IN (
        'document_ingestion', 'entity_extraction', 'vector_embedding',
        'quality_evaluation', 'batch_processing', 'content_analysis'
    )),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN (
        'pending', 'running', 'completed', 'failed', 'cancelled', 'retrying'
    )),
    priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    progress_percentage INTEGER DEFAULT 0 CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    estimated_completion TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    created_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    worker_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Processing history for audit trail
CREATE TABLE IF NOT EXISTS processing_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES processing_jobs(id) ON DELETE CASCADE,
    stage_name VARCHAR(100) NOT NULL,
    stage_status VARCHAR(50) NOT NULL CHECK (stage_status IN ('started', 'completed', 'failed')),
    stage_input JSONB DEFAULT '{}',
    stage_output JSONB DEFAULT '{}',
    stage_duration_ms INTEGER,
    error_details TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- =================================================================
-- QUALITY AND EVALUATION
-- =================================================================

-- Quality metrics for documents and search results
CREATE TABLE IF NOT EXISTS quality_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_type VARCHAR(50) NOT NULL CHECK (metric_type IN (
        'answer_relevancy', 'faithfulness', 'contextual_relevancy',
        'entity_precision', 'entity_recall', 'content_quality',
        'processing_quality', 'user_satisfaction'
    )),
    evaluation_type VARCHAR(50) DEFAULT 'automated' CHECK (evaluation_type IN (
        'automated', 'human', 'hybrid'
    )),
    scope_type VARCHAR(50) NOT NULL CHECK (scope_type IN (
        'document', 'query', 'session', 'system', 'user', 'organization'
    )),
    scope_id UUID NOT NULL,
    metric_value DECIMAL(5,4) NOT NULL CHECK (metric_value >= 0 AND metric_value <= 1),
    threshold_value DECIMAL(5,4) CHECK (threshold_value >= 0 AND threshold_value <= 1),
    passes_threshold BOOLEAN,
    evaluation_details JSONB DEFAULT '{}',
    evaluator_id UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Search sessions for user interaction tracking
CREATE TABLE IF NOT EXISTS search_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    session_start TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    session_end TIMESTAMP WITH TIME ZONE,
    query_count INTEGER DEFAULT 0,
    total_results INTEGER DEFAULT 0,
    average_relevance DECIMAL(5,4),
    user_satisfaction_score DECIMAL(3,2) CHECK (user_satisfaction_score >= 1 AND user_satisfaction_score <= 5),
    session_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- =================================================================
-- ANALYTICS AND MONITORING
-- =================================================================

-- User sessions for tracking
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    session_start TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    session_end TIMESTAMP WITH TIME ZONE,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    page_views INTEGER DEFAULT 0,
    actions_count INTEGER DEFAULT 0,
    session_status VARCHAR(50) DEFAULT 'active' CHECK (session_status IN ('active', 'expired', 'terminated')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Analytics events for tracking user interactions
CREATE TABLE IF NOT EXISTS analytics_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL CHECK (event_type IN (
        'page_view', 'search_query', 'document_upload', 'document_download',
        'entity_click', 'result_click', 'filter_change', 'login', 'logout',
        'error', 'performance_metric', 'feature_usage'
    )),
    event_severity VARCHAR(20) DEFAULT 'info' CHECK (event_severity IN ('debug', 'info', 'warning', 'error', 'critical')),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    session_id UUID REFERENCES user_sessions(id) ON DELETE SET NULL,
    event_data JSONB DEFAULT '{}',
    page_url VARCHAR(1000),
    ip_address INET,
    user_agent TEXT,
    referrer_url VARCHAR(1000),
    event_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Performance logs for system monitoring
CREATE TABLE IF NOT EXISTS performance_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_category VARCHAR(50) NOT NULL CHECK (metric_category IN (
        'database', 'api', 'search', 'processing', 'cache', 'external_service'
    )),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,6) NOT NULL,
    metric_unit VARCHAR(50),
    performance_level VARCHAR(20) DEFAULT 'normal' CHECK (performance_level IN ('excellent', 'good', 'normal', 'slow', 'critical')),
    threshold_value DECIMAL(15,6),
    context_data JSONB DEFAULT '{}',
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    request_id VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- =================================================================
-- SECURITY AND AUDIT
-- =================================================================

-- Audit events for compliance and security
CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL CHECK (event_type IN (
        'user_login', 'user_logout', 'password_change', 'permission_change',
        'data_access', 'data_modification', 'data_deletion', 'system_config',
        'security_incident', 'compliance_violation'
    )),
    severity VARCHAR(20) DEFAULT 'info' CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    resource_type VARCHAR(100),
    resource_id UUID,
    action VARCHAR(100) NOT NULL,
    details JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN DEFAULT true,
    failure_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Document access logs for tracking
CREATE TABLE IF NOT EXISTS document_access_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    access_type VARCHAR(50) NOT NULL CHECK (access_type IN (
        'view', 'download', 'edit', 'share', 'delete', 'print'
    )),
    access_granted BOOLEAN DEFAULT true,
    access_reason VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    access_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT false,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- =================================================================
-- INDEXES FOR PERFORMANCE OPTIMIZATION
-- =================================================================

-- Organization indexes
CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);
CREATE INDEX IF NOT EXISTS idx_organizations_active ON organizations(is_active) WHERE is_active = true;

-- User indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_organization ON users(organization_id);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Document indexes
CREATE INDEX IF NOT EXISTS idx_documents_organization ON documents(organization_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON documents(uploaded_by_user_id);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_documents_tags ON documents USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING GIN(document_metadata);
CREATE INDEX IF NOT EXISTS idx_documents_title_trgm ON documents USING GIN(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_documents_content_trgm ON documents USING GIN(content_text gin_trgm_ops) WHERE content_text IS NOT NULL;

-- Entity indexes
CREATE INDEX IF NOT EXISTS idx_entities_organization ON entities(organization_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_canonical ON entities(canonical_name);
CREATE INDEX IF NOT EXISTS idx_entities_source_doc ON entities(source_document_id);
CREATE INDEX IF NOT EXISTS idx_entities_aliases ON entities USING GIN(aliases);

-- Search indexes
CREATE INDEX IF NOT EXISTS idx_search_queries_user ON search_queries(user_id);
CREATE INDEX IF NOT EXISTS idx_search_queries_organization ON search_queries(organization_id);
CREATE INDEX IF NOT EXISTS idx_search_queries_created_at ON search_queries(created_at);
CREATE INDEX IF NOT EXISTS idx_search_results_query ON search_results(search_query_id);
CREATE INDEX IF NOT EXISTS idx_search_results_document ON search_results(document_id);
CREATE INDEX IF NOT EXISTS idx_search_results_score ON search_results(relevance_score);

-- Processing indexes
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_type ON processing_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_priority ON processing_jobs(priority DESC);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_organization ON processing_jobs(organization_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_created_at ON processing_jobs(created_at);

-- Analytics indexes
CREATE INDEX IF NOT EXISTS idx_analytics_events_user ON analytics_events(user_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_organization ON analytics_events(organization_id);
CREATE INDEX IF NOT EXISTS idx_analytics_events_type ON analytics_events(event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_events_timestamp ON analytics_events(event_timestamp);
CREATE INDEX IF NOT EXISTS idx_analytics_events_session ON analytics_events(session_id);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_performance_logs_timestamp ON performance_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_performance_logs_category ON performance_logs(metric_category);
CREATE INDEX IF NOT EXISTS idx_performance_logs_organization ON performance_logs(organization_id);

-- Audit indexes
CREATE INDEX IF NOT EXISTS idx_audit_events_user ON audit_events(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_organization ON audit_events(organization_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_type ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events(created_at);

-- Document access logs indexes
CREATE INDEX IF NOT EXISTS idx_doc_access_document ON document_access_logs(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_access_user ON document_access_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_doc_access_timestamp ON document_access_logs(access_timestamp);

-- =================================================================
-- ROW LEVEL SECURITY POLICIES (Multi-tenant isolation)
-- =================================================================

-- Enable RLS on key tables
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_queries ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE quality_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_access_logs ENABLE ROW LEVEL SECURITY;

-- RLS Policies

-- Organizations: Users can see their own organization
CREATE POLICY organization_isolation_policy ON organizations
    FOR ALL TO authenticated_users
    USING (id = current_setting('app.current_organization_id', true)::uuid);

-- Users: Users can see users in their organization
CREATE POLICY user_isolation_policy ON users
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

-- Documents: Users can see documents in their organization
CREATE POLICY document_isolation_policy ON documents
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

-- Entities: Users can see entities in their organization
CREATE POLICY entity_isolation_policy ON entities
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

-- Search queries: Users can see their own queries and their organization's queries
CREATE POLICY search_query_isolation_policy ON search_queries
    FOR ALL TO authenticated_users
    USING (
        organization_id = current_setting('app.current_organization_id', true)::uuid AND
        (user_id = current_setting('app.current_user_id', true)::uuid OR user_id IS NULL)
    );

-- Analytics events: Users can see events in their organization
CREATE POLICY analytics_isolation_policy ON analytics_events
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::uuid);

-- =================================================================
-- TRIGGERS FOR AUTOMATIC TIMESTAMP UPDATES
-- =================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers to tables with updated_at columns
CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_entities_updated_at BEFORE UPDATE ON entities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_entity_relationships_updated_at BEFORE UPDATE ON entity_relationships
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_search_queries_updated_at BEFORE UPDATE ON search_queries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processing_jobs_updated_at BEFORE UPDATE ON processing_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_quality_metrics_updated_at BEFORE UPDATE ON quality_metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_search_sessions_updated_at BEFORE UPDATE ON search_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_sessions_updated_at BEFORE UPDATE ON user_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_analytics_events_updated_at BEFORE UPDATE ON analytics_events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =================================================================
-- VIEWS FOR COMMON QUERIES
-- =================================================================

-- Organization statistics view
CREATE OR REPLACE VIEW organization_stats AS
SELECT
    o.id as organization_id,
    o.name as organization_name,
    COUNT(DISTINCT u.id) as user_count,
    COUNT(DISTINCT d.id) as document_count,
    COUNT(DISTINCT CASE WHEN d.processing_status = 'completed' THEN d.id END) as processed_documents,
    COUNT(DISTINCT CASE WHEN d.processing_status = 'failed' THEN d.id END) as failed_documents,
    COALESCE(SUM(d.file_size_bytes), 0) as total_storage_bytes,
    AVG(d.file_size_bytes) as avg_document_size,
    COUNT(DISTINCT sq.id) as search_count,
    COUNT(DISTINCT e.id) as entity_count,
    MAX(d.created_at) as last_document_upload,
    MAX(sq.created_at) as last_search_query
FROM organizations o
LEFT JOIN users u ON o.id = u.organization_id AND u.is_active = true
LEFT JOIN documents d ON o.id = d.organization_id AND d.is_deleted = false
LEFT JOIN search_queries sq ON o.id = sq.organization_id AND sq.is_deleted = false
LEFT JOIN entities e ON o.id = e.organization_id AND e.is_deleted = false
WHERE o.is_active = true AND o.is_deleted = false
GROUP BY o.id, o.name;

-- User activity view
CREATE OR REPLACE VIEW user_activity_summary AS
SELECT
    u.id as user_id,
    u.email,
    u.first_name,
    u.last_name,
    o.name as organization_name,
    COUNT(DISTINCT d.id) as uploaded_documents,
    COUNT(DISTINCT sq.id) as search_queries,
    COUNT(DISTINCT us.id) as sessions,
    COUNT(DISTINCT da.id) as document_accesses,
    MAX(sq.created_at) as last_search,
    MAX(us.session_start) as last_session,
    COALESCE(AVG(sq.latency_ms), 0) as avg_search_latency
FROM users u
JOIN organizations o ON u.organization_id = o.id
LEFT JOIN documents d ON u.id = d.uploaded_by_user_id AND d.is_deleted = false
LEFT JOIN search_queries sq ON u.id = sq.user_id AND sq.is_deleted = false
LEFT JOIN user_sessions us ON u.id = us.user_id AND us.is_deleted = false
LEFT JOIN document_access_logs da ON u.id = da.user_id AND da.is_deleted = false
WHERE u.is_active = true AND u.is_deleted = false
GROUP BY u.id, u.email, u.first_name, u.last_name, o.name;

-- =================================================================
-- FUNCTIONS FOR COMMON OPERATIONS
-- =================================================================

-- Function to get organization storage usage
CREATE OR REPLACE FUNCTION get_organization_storage_usage(org_id UUID)
RETURNS TABLE(
    total_documents BIGINT,
    total_storage_bytes BIGINT,
    storage_gb DECIMAL(10,2),
    storage_percentage DECIMAL(5,2),
    documents_by_type JSONB,
    upload_trend JSONB
) AS $$
BEGIN
    RETURN QUERY
    WITH storage_stats AS (
        SELECT
            COUNT(*) as total_docs,
            COALESCE(SUM(file_size_bytes), 0) as total_bytes,
            jsonb_object_agg(document_type, type_count) as by_type
        FROM documents
        WHERE organization_id = org_id AND is_deleted = false
    ),
    org_limits AS (
        SELECT max_storage_gb FROM organizations WHERE id = org_id
    )
    SELECT
        ss.total_docs,
        ss.total_bytes,
        ROUND(ss.total_bytes / (1024.0^3), 2) as storage_gb,
        CASE
            WHEN ol.max_storage_gb > 0
            THEN ROUND((ss.total_bytes / (1024.0^3)) / ol.max_storage_gb * 100, 2)
            ELSE 0
        END as storage_percentage,
        ss.by_type,
        jsonb_build_object() as upload_trend -- TODO: Implement trend calculation
    FROM storage_stats ss, org_limits ol;
END;
$$ LANGUAGE plpgsql;

-- Function to check if user can access document
CREATE OR REPLACE FUNCTION can_access_document(user_id_param UUID, document_id_param UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM documents d
        JOIN users u ON d.organization_id = u.organization_id
        WHERE d.id = document_id_param
        AND u.id = user_id_param
        AND d.is_deleted = false
        AND u.is_active = true
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to record document access
CREATE OR REPLACE FUNCTION record_document_access(
    document_id_param UUID,
    user_id_param UUID,
    access_type_param VARCHAR(50),
    ip_address_param INET DEFAULT NULL,
    user_agent_param TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO document_access_logs (
        document_id, user_id, organization_id, access_type,
        ip_address, user_agent, access_timestamp
    )
    SELECT
        d.id, user_id_param, d.organization_id, access_type_param,
        ip_address_param, user_agent_param, CURRENT_TIMESTAMP
    FROM documents d
    WHERE d.id = document_id_param;
END;
$$ LANGUAGE plpgsql;

-- =================================================================
-- SAMPLE DATA (for development)
-- =================================================================

-- Insert sample organization
INSERT INTO organizations (id, name, slug, description, storage_tier, max_storage_gb, max_users)
VALUES (
    uuid_generate_v4(),
    'Demo Organization',
    'demo-org',
    'A demonstration organization for the Multimodal Enterprise RAG System',
    'standard',
    5,
    10
) ON CONFLICT DO NOTHING;

-- =================================================================
-- COMPLETION MESSAGE
-- =================================================================

DO $$
BEGIN
    RAISE NOTICE '✅ Multimodal Enterprise RAG System database schema created successfully!';
    RAISE NOTICE '📊 Created % tables', (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public');
    RAISE NOTICE '🔍 Created % indexes', (SELECT count(*) FROM pg_indexes WHERE schemaname = 'public');
    RAISE NOTICE '🔒 Row Level Security enabled for multi-tenant isolation';
    RAISE NOTICE '⚡ Performance optimizations applied';
END $$;