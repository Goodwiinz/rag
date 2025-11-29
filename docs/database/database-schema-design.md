# Comprehensive Database Schema Design
## Multimodal Enterprise RAG UI System

This document provides a complete database architecture design for the Multimodal Enterprise RAG UI system with multi-tenant support, comprehensive evaluation metrics, and real-time capabilities.

## System Architecture Overview

### Database Components
- **PostgreSQL**: Primary data warehouse for user management, document metadata, query history, and analytics
- **Neo4j**: Knowledge graph for entities and relationships
- **Qdrant**: Vector embeddings and semantic search
- **Redis**: Real-time caching, WebSocket connections, and session management
- **Time-series optimization**: Partitioned tables for high-volume analytics data

---

## 1. PostgreSQL Schema Design

### 1.1 Core Tables

#### Organizations (Multi-Tenancy)
```sql
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,

    -- Subscription and limits
    subscription_tier VARCHAR(50) DEFAULT 'starter' CHECK (subscription_tier IN ('starter', 'professional', 'enterprise')),
    storage_limit_gb INTEGER DEFAULT 5 CHECK (storage_limit_gb >= 0),
    max_users INTEGER DEFAULT 10 CHECK (max_users >= 0),
    max_documents_per_user INTEGER DEFAULT 100 CHECK (max_documents_per_user >= 0),

    -- Feature flags
    features_enabled JSONB DEFAULT '{}',

    -- Billing and usage
    current_storage_gb DECIMAL(10,2) DEFAULT 0,
    current_user_count INTEGER DEFAULT 0,
    current_document_count INTEGER DEFAULT 0,

    -- Metadata
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,

    CONSTRAINT org_storage_check CHECK (current_storage_gb <= storage_limit_gb)
);

-- Indexes for organization lookups
CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_organizations_tier ON organizations(subscription_tier);
CREATE INDEX idx_organizations_active ON organizations(is_deleted, created_at);
```

#### Users and Authentication
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Basic information
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,

    -- Roles and permissions
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('admin', 'content_manager', 'user', 'analyst')),
    permissions JSONB DEFAULT '[]',

    -- Status and activity
    is_active BOOLEAN DEFAULT TRUE,
    is_email_verified BOOLEAN DEFAULT FALSE,
    last_login_at TIMESTAMPTZ,
    login_count INTEGER DEFAULT 0,

    -- Storage quota
    personal_storage_gb DECIMAL(10,2) DEFAULT 0,
    document_count INTEGER DEFAULT 0,

    -- Preferences
    preferences JSONB DEFAULT '{}',
    ui_settings JSONB DEFAULT '{}',

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,

    UNIQUE(organization_id, email)
);

-- User indexes
CREATE INDEX idx_users_organization ON users(organization_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(organization_id, role);
CREATE INDEX idx_users_active ON users(is_active, last_login_at);
```

#### User Sessions
```sql
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Session identifiers
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,

    -- Connection info
    ip_address INET,
    user_agent TEXT,
    device_fingerprint VARCHAR(255),

    -- Session data
    session_data JSONB DEFAULT '{}',
    websocket_connections JSONB DEFAULT '[]',

    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    CONSTRAINT valid_expires_at CHECK (expires_at > created_at)
);

-- Session indexes
CREATE INDEX idx_sessions_user ON user_sessions(user_id, last_activity DESC);
CREATE INDEX idx_sessions_token ON user_sessions(session_token);
CREATE INDEX idx_sessions_active ON user_sessions(is_active, expires_at);
CREATE INDEX idx_sessions_organization ON user_sessions(organization_id, last_activity DESC);
```

### 1.2 Document Management Tables

#### Documents (Multi-Modal Content)
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    uploaded_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Basic information
    title VARCHAR(500) NOT NULL,
    filename VARCHAR(500) NOT NULL,
    description TEXT,

    -- File information
    file_path VARCHAR(1000) NOT NULL,
    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes > 0),
    file_hash VARCHAR(64) NOT NULL, -- SHA-256 hash
    mime_type VARCHAR(100) NOT NULL,

    -- Document type and modality
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN ('pdf', 'text', 'image', 'audio', 'video', 'spreadsheet', 'presentation')),
    primary_modality VARCHAR(50) NOT NULL CHECK (primary_modality IN ('text', 'image', 'audio', 'video')),
    modalities JSONB DEFAULT '[]', -- Multiple modalities for complex documents

    -- Content
    content_text TEXT, -- Extracted text content
    content_summary TEXT, -- AI-generated summary
    extracted_metadata JSONB DEFAULT '{}',

    -- Processing pipeline
    processing_status VARCHAR(50) DEFAULT 'queued' CHECK (processing_status IN ('queued', 'processing', 'indexed', 'failed', 'retrying')),
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    processing_error TEXT,
    processing_retry_count INTEGER DEFAULT 0,
    processing_steps JSONB DEFAULT '{}', -- Track each processing step

    -- Search and retrieval
    embedding_id VARCHAR(255), -- Qdrant vector ID
    is_embedded BOOLEAN DEFAULT FALSE,
    is_indexed BOOLEAN DEFAULT FALSE,
    search_vector TSVECTOR, -- Full-text search vector

    -- Access control
    is_public BOOLEAN DEFAULT FALSE,
    tags TEXT[] DEFAULT '{}',
    categories TEXT[] DEFAULT '{}',

    -- Quality metrics
    quality_score DECIMAL(5,4) CHECK (quality_score >= 0 AND quality_score <= 1),
    extraction_confidence DECIMAL(5,4) CHECK (extraction_confidence >= 0 AND extraction_confidence <= 1),

    -- Usage analytics
    view_count INTEGER DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT valid_file_size CHECK (file_size_bytes <= 52428800), -- 50MB limit
    CONSTRAINT valid_retry_count CHECK (processing_retry_count <= 3)
);

-- Document indexes
CREATE INDEX idx_documents_organization ON documents(organization_id, created_at DESC);
CREATE INDEX idx_documents_user ON documents(uploaded_by_user_id, created_at DESC);
CREATE INDEX idx_documents_type ON documents(document_type, processing_status);
CREATE INDEX idx_documents_status ON documents(processing_status, created_at);
CREATE INDEX idx_documents_modality ON documents(primary_modality, is_indexed);
CREATE INDEX idx_documents_tags ON documents USING GIN(tags);
CREATE INDEX idx_documents_search ON documents USING GIN(search_vector);
CREATE INDEX idx_documents_quality ON documents(quality_score DESC);
CREATE INDEX idx_documents_file_hash ON documents(file_hash);
```

#### Document Processing Jobs
```sql
CREATE TABLE document_processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Job configuration
    job_type VARCHAR(100) NOT NULL, -- ocr, transcription, embedding, entity_extraction, etc.
    job_priority INTEGER DEFAULT 5 CHECK (job_priority >= 1 AND job_priority <= 10),

    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    progress_percentage DECIMAL(5,2) DEFAULT 0 CHECK (progress_percentage >= 0 AND progress_percentage <= 100),

    -- Timing
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    timeout_at TIMESTAMPTZ,

    -- Results and errors
    result_data JSONB DEFAULT '{}',
    error_message TEXT,
    error_details JSONB DEFAULT '{}',

    -- Resource usage
    cpu_time_ms INTEGER,
    memory_peak_mb INTEGER,
    tokens_used INTEGER,
    cost_usd DECIMAL(10,6),

    -- Retry logic
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMPTZ,

    -- Worker assignment
    worker_id VARCHAR(255),
    worker_version VARCHAR(50),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_retry CHECK (retry_count <= max_retries)
);

-- Processing job indexes
CREATE INDEX idx_processing_jobs_document ON document_processing_jobs(document_id, job_type);
CREATE INDEX idx_processing_jobs_status ON document_processing_jobs(status, queued_at);
CREATE INDEX idx_processing_jobs_priority ON document_processing_jobs(job_priority DESC, queued_at);
CREATE INDEX idx_processing_jobs_retry ON document_processing_jobs(next_retry_at, status);
CREATE INDEX idx_processing_jobs_worker ON document_processing_jobs(worker_id, status);
```

### 1.3 Search and Query Tables

#### Search Queries
```sql
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

-- Create monthly partitions for time-series optimization
CREATE TABLE search_queries_y2024m01 PARTITION OF search_queries
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE search_queries_y2024m02 PARTITION OF search_queries
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- Search query indexes
CREATE INDEX idx_search_queries_user ON search_queries(user_id, created_at DESC);
CREATE INDEX idx_search_queries_session ON search_queries(session_id, created_at DESC);
CREATE INDEX idx_search_queries_organization ON search_queries(organization_id, created_at DESC);
CREATE INDEX idx_search_queries_type ON search_queries(query_type, created_at DESC);
CREATE INDEX idx_search_queries_performance ON search_queries(total_time_ms, created_at DESC);
CREATE INDEX idx_search_queries_text_fts ON search_queries USING GIN(to_tsvector('english', query_text));
```

#### Search Results (Detailed tracking)
```sql
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

-- Search result indexes
CREATE INDEX idx_search_results_query ON search_results(search_query_id, rank_position);
CREATE INDEX idx_search_results_document ON search_results(document_id, created_at DESC);
CREATE INDEX idx_search_results_score ON search_results(relevance_score DESC);
CREATE INDEX idx_search_results_clicked ON search_results(was_clicked, clicked_at DESC);
```

### 1.4 Knowledge Graph Integration

#### Entities (Extracted from Documents)
```sql
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Entity information
    entity_type VARCHAR(100) NOT NULL, -- person, organization, location, concept, etc.
    entity_name VARCHAR(500) NOT NULL,
    canonical_name VARCHAR(500),
    aliases JSONB DEFAULT '[]',

    -- Extraction details
    extraction_method VARCHAR(100), -- spacy, openai, regex, manual
    extraction_confidence DECIMAL(5,4) CHECK (extraction_confidence >= 0 AND extraction_confidence <= 1),
    extraction_model VARCHAR(100),

    -- Entity properties
    properties JSONB DEFAULT '{}',
    description TEXT,

    -- Graph integration
    graph_node_id VARCHAR(255), -- Neo4j node ID
    is_in_knowledge_graph BOOLEAN DEFAULT FALSE,

    -- Context
    text_span_start INTEGER,
    text_span_end INTEGER,
    context_window TEXT,

    -- Quality metrics
    relevance_score DECIMAL(5,4) DEFAULT 1.0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Entity indexes
CREATE INDEX idx_entities_document ON entities(document_id, entity_type);
CREATE INDEX idx_entities_organization ON entities(organization_id, entity_type);
CREATE INDEX idx_entities_name ON entities(entity_name, entity_type);
CREATE INDEX idx_entities_canonical ON entities(canonical_name, entity_type);
CREATE INDEX idx_entities_graph ON entities(graph_node_id) WHERE graph_node_id IS NOT NULL;
```

#### Entity Relationships
```sql
CREATE TABLE entity_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Relationship information
    relationship_type VARCHAR(100) NOT NULL, -- works_for, located_in, related_to, etc.
    relationship_description TEXT,

    -- Confidence and relevance
    confidence DECIMAL(5,4) CHECK (confidence >= 0 AND confidence <= 1),
    relevance_score DECIMAL(5,4) DEFAULT 1.0,

    -- Graph integration
    graph_relationship_id VARCHAR(255), -- Neo4j relationship ID

    -- Source and context
    source_context TEXT,
    extraction_method VARCHAR(100),

    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT no_self_relationship CHECK (source_entity_id != target_entity_id),
    CONSTRAINT valid_confidence CHECK (confidence >= 0 AND confidence <= 1)
);

-- Entity relationship indexes
CREATE INDEX idx_entity_relationships_source ON entity_relationships(source_entity_id, relationship_type);
CREATE INDEX idx_entity_relationships_target ON entity_relationships(target_entity_id, relationship_type);
CREATE INDEX idx_entity_relationships_org ON entity_relationships(organization_id, relationship_type);
CREATE INDEX idx_entity_relationships_graph ON entity_relationships(graph_relationship_id) WHERE graph_relationship_id IS NOT NULL;
```

### 1.5 Evaluation and Quality Metrics

#### RAG Triad Evaluation
```sql
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

-- RAG evaluation indexes
CREATE INDEX idx_rag_evaluations_query ON rag_evaluations(search_query_id);
CREATE INDEX idx_rag_evaluations_org ON rag_evaluations(organization_id, created_at DESC);
CREATE INDEX idx_rag_evaluations_overall ON rag_evaluations(overall_score DESC);
CREATE INDEX idx_rag_evaluations_thresholds ON rag_evaluations(meets_thresholds, created_at DESC);
```

#### Performance Metrics
```sql
CREATE TABLE performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,

    -- Metric identification
    metric_name VARCHAR(255) NOT NULL,
    metric_category VARCHAR(100) NOT NULL, -- system, search, processing, user_experience
    metric_type VARCHAR(50) NOT NULL, -- counter, gauge, histogram, timer

    -- Metric values
    value DECIMAL(15,6) NOT NULL,
    unit VARCHAR(50),

    -- Thresholds and alerts
    threshold_warning DECIMAL(15,6),
    threshold_critical DECIMAL(15,6),
    alert_triggered BOOLEAN DEFAULT FALSE,

    -- Context
    component VARCHAR(100), -- api_worker, search_engine, embedding_service, etc.
    environment VARCHAR(50) DEFAULT 'production',
    node_id VARCHAR(100),

    -- Additional data
    tags JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',

    -- Timing
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (timestamp);

-- Performance metrics indexes
CREATE INDEX idx_performance_metrics_name_time ON performance_metrics(metric_name, timestamp DESC);
CREATE INDEX idx_performance_metrics_category_time ON performance_metrics(metric_category, timestamp DESC);
CREATE INDEX idx_performance_metrics_org_time ON performance_metrics(organization_id, timestamp DESC) WHERE organization_id IS NOT NULL;
CREATE INDEX idx_performance_metrics_alert ON performance_metrics(alert_triggered, timestamp DESC);
```

### 1.6 System Monitoring and Health

#### System Health
```sql
CREATE TABLE system_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Component identification
    component_name VARCHAR(100) NOT NULL,
    component_type VARCHAR(50) NOT NULL, -- database, vector_store, cache, api, worker
    node_id VARCHAR(100),

    -- Health status
    status VARCHAR(50) NOT NULL CHECK (status IN ('healthy', 'degraded', 'critical', 'offline')),
    health_score DECIMAL(3,2) CHECK (health_score >= 0 AND health_score <= 1),

    -- Performance metrics
    response_time_ms INTEGER,
    success_rate DECIMAL(5,4),
    error_rate DECIMAL(5,4),

    -- Resource usage
    cpu_usage_percent DECIMAL(5,2),
    memory_usage_mb DECIMAL(10,2),
    memory_usage_percent DECIMAL(5,2),
    disk_usage_gb DECIMAL(10,2),
    disk_usage_percent DECIMAL(5,2),

    -- Dependencies
    dependencies JSONB DEFAULT '{}', -- Status of dependent services
    health_checks JSONB DEFAULT '{}', -- Individual health check results

    -- Status tracking
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    consecutive_failures INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(component_name, node_id)
);

-- System health indexes
CREATE INDEX idx_system_health_status ON system_health(status, health_score);
CREATE INDEX idx_system_health_component ON system_health(component_type, node_id);
CREATE INDEX idx_system_health_updated ON system_health(updated_at DESC);
```

#### Error Tracking
```sql
CREATE TABLE error_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Error identification
    error_id VARCHAR(100) UNIQUE NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_code VARCHAR(50),
    error_message TEXT NOT NULL,
    error_stack TEXT,

    -- Severity and classification
    severity VARCHAR(50) DEFAULT 'error' CHECK (severity IN ('warning', 'error', 'critical')),
    category VARCHAR(100), -- validation, authentication, processing, infrastructure

    -- Context
    component VARCHAR(100),
    function_name VARCHAR(255),
    line_number INTEGER,

    -- User and organization context
    organization_id UUID REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    session_id UUID REFERENCES user_sessions(id),

    -- Request context
    request_id VARCHAR(255),
    endpoint VARCHAR(255),
    http_method VARCHAR(10),
    http_status_code INTEGER,

    -- System context
    node_id VARCHAR(100),
    environment VARCHAR(50),
    version VARCHAR(50),

    -- Additional context
    context_data JSONB DEFAULT '{}',
    system_metadata JSONB DEFAULT '{}',

    -- Resolution tracking
    resolution_status VARCHAR(50) DEFAULT 'open' CHECK (resolution_status IN ('open', 'investigating', 'resolved', 'wont_fix')),
    resolved_by UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,

    occurred_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (occurred_at);

-- Error log indexes
CREATE INDEX idx_error_logs_type ON error_logs(error_type, occurred_at DESC);
CREATE INDEX idx_error_logs_severity ON error_logs(severity, occurred_at DESC);
CREATE INDEX idx_error_logs_component ON error_logs(component, occurred_at DESC);
CREATE INDEX idx_error_logs_status ON error_logs(resolution_status, occurred_at DESC);
CREATE INDEX idx_error_logs_organization ON error_logs(organization_id, occurred_at DESC);
```

---

## 2. Neo4j Graph Schema

### 2.1 Node Labels and Properties

#### Document Nodes
```cypher
// Document nodes with multimodal content
CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;

// Document nodes properties
// d.id: UUID (PostgreSQL document ID)
// d.title: String
// d.type: String (pdf, text, image, audio, video)
// d.primary_modality: String
// d.modalities: Array[String]
// d.content_hash: String
// d.quality_score: Float
// d.organization_id: UUID
// d.created_at: DateTime
// d.updated_at: DateTime
// d.is_indexed: Boolean
// d.embedding_id: String (Qdrant vector ID)
```

#### Entity Nodes
```cypher
// Entity nodes for knowledge graph
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT entity_name_type_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE;

// Entity nodes properties
// e.id: UUID (PostgreSQL entity ID)
// e.name: String
// e.canonical_name: String
// e.type: String (Person, Organization, Location, Concept, Product, Date, etc.)
// e.aliases: Array[String]
// e.properties: Map
// e.confidence: Float
// e.extraction_method: String
// e.organization_id: UUID
// e.created_at: DateTime
// e.document_count: Integer (derived)
// e.relationship_count: Integer (derived)
```

#### Concept/Topic Nodes
```cypher
// Concept nodes for topic modeling
CREATE CONSTRAINT concept_name_unique IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE;

// Concept nodes properties
// c.name: String
// c.type: String (Topic, Category, Domain, Technology)
// c.description: String
// c.document_frequency: Integer
// c.total_mentions: Integer
// c.avg_confidence: Float
// c.organization_id: UUID
// c.created_at: DateTime
```

#### User Nodes
```cypher
// User nodes for interaction tracking
CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;

// User nodes properties
// u.id: UUID (PostgreSQL user ID)
// u.email: String
// u.organization_id: UUID
// u.preferences: Map
// u.query_count: Integer (derived)
// u.document_count: Integer (derived)
// u.last_activity: DateTime
```

### 2.2 Relationship Types

#### Document-Entity Relationships
```cypher
// CONTAINS relationship: Document contains Entity
// r.confidence: Float
// r.extraction_method: String
// r.text_span: String
// r.context: String
// r.created_at: DateTime

// Example: (d:Document)-[:CONTAINS {confidence: 0.95, extraction_method: "spacy"}]->(e:Entity)
```

#### Entity-Entity Relationships
```cypher
// RELATED_TO relationship: General entity relationships
// r.type: String (works_for, located_in, related_to, part_of, etc.)
// r.confidence: Float
// r.source_document_id: UUID
// r.extraction_method: String
// r.created_at: DateTime

// Example: (e1:Entity)-[:RELATED_TO {type: "works_for", confidence: 0.9}]->(e2:Entity)
```

#### Document-Concept Relationships
```cypher
// ABOUT relationship: Document is about Concept
// r.relevance_score: Float
// r.extraction_method: String
// r.evidence: Array[String]
// r.created_at: DateTime

// Example: (d:Document)-[:ABOUT {relevance_score: 0.85}]->(c:Concept)
```

#### User-Document Relationships
```cypher
// ACCESSED relationship: User accessed Document
// r.access_type: String (viewed, downloaded, shared)
// r.timestamp: DateTime
// r.session_id: UUID
// r.query_id: UUID

// Example: (u:User)-[:ACCESSED {access_type: "viewed"}]->(d:Document)
```

#### User-Query Relationships
```cypher
// EXECUTED relationship: User executed Query
// r.query_text: String
// r.query_type: String
// r.results_count: Integer
// r.satisfaction_score: Integer
// r.timestamp: DateTime

// Example: (u:User)-[:EXECUTED {query_type: "hybrid"}]->(q:Query)
```

### 2.3 Graph Indexes

```cypher
// Performance indexes
CREATE INDEX document_type_index IF NOT EXISTS FOR (d:Document) ON (d.type, d.organization_id);
CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type, e.organization_id);
CREATE INDEX document_modality_index IF NOT EXISTS FOR (d:Document) ON (d.primary_modality, d.is_indexed);
CREATE INDEX entity_confidence_index IF NOT EXISTS FOR (e:Entity) ON (e.confidence);
CREATE INDEX concept_frequency_index IF NOT EXISTS FOR (c:Concept) ON (c.document_frequency);

// Full-text search indexes
CREATE FULLTEXT INDEX document_title_index IF NOT EXISTS FOR (d:Document) ON EACH [d.title];
CREATE FULLTEXT INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON EACH [e.name, e.canonical_name];
CREATE FULLTEXT INDEX concept_description_index IF NOT EXISTS FOR (c:Concept) ON EACH [c.name, c.description];

// Composite indexes for common queries
CREATE INDEX entity_document_index IF NOT EXISTS FOR (e:Entity)-[r:CONTAINS]->(d:Document) ON (e.type, d.type, r.confidence);
```

### 2.4 Sample Graph Queries

```cypher
// Find related entities for a document
MATCH (d:Document {id: $document_id})-[:CONTAINS]->(e:Entity)-[:RELATED_TO]-(related:Entity)
WHERE e.type = $entity_type AND related.type = $related_type
RETURN e.name, related.name, relationship_type
ORDER BY e.confidence DESC
LIMIT 10;

// Find documents by entity relationships
MATCH (e1:Entity {name: $entity_name})-[:RELATED_TO]->(e2:Entity)<-[:CONTAINS]-(d:Document)
WHERE d.organization_id = $org_id AND d.is_indexed = true
RETURN DISTINCT d.title, d.id, e2.name
ORDER BY d.quality_score DESC;

// Get user's document interaction patterns
MATCH (u:User {id: $user_id})-[r:ACCESSED]->(d:Document)
WHERE r.timestamp >= datetime($date_from)
RETURN d.type, count(r) as access_count, avg(r.timestamp) as last_access
ORDER BY access_count DESC;

// Find concept clusters within organization
MATCH (c1:Concept)<-[:ABOUT]-(d:Document)-[:ABOUT]->(c2:Concept)
WHERE c1.organization_id = $org_id AND c2.organization_id = $org_id
AND id(c1) < id(c2)
RETURN c1.name, c2.name, count(d) as shared_documents
ORDER BY shared_documents DESC
LIMIT 20;
```

---

## 3. Qdrant Vector Collections

### 3.1 Collection Configuration

#### Primary Document Embeddings
```json
{
  "collection_name": "document_embeddings",
  "vectors": {
    "size": 1536,
    "distance": "Cosine"
  },
  "payload_schema": {
    "document_id": "keyword",
    "organization_id": "keyword",
    "title": "text",
    "document_type": "keyword",
    "primary_modality": "keyword",
    "modalities": "keyword",
    "quality_score": "float",
    "processing_status": "keyword",
    "is_indexed": "bool",
    "tags": "keyword",
    "categories": "keyword",
    "created_at": "integer",
    "updated_at": "integer"
  },
  "hnsw_config": {
    "m": 16,
    "ef_construct": 200,
    "full_scan_threshold": 20000
  },
  "quantization_config": {
    "quantization": "scalar",
    "scalar": {
      "type": "int8",
      "ram_usage": "0.2x"
    }
  }
}
```

#### Multi-Modal Embeddings
```json
{
  "collection_name": "multimodal_embeddings",
  "vectors": {
    "size": 1024,
    "distance": "Cosine"
  },
  "vectors_map": {
    "text": {
      "size": 1536,
      "distance": "Cosine"
    },
    "image": {
      "size": 512,
      "distance": "Cosine"
    }
  },
  "payload_schema": {
    "document_id": "keyword",
    "organization_id": "keyword",
    "modality": "keyword",
    "content_type": "keyword",
    "extraction_method": "keyword",
    "confidence": "float",
    "metadata": "json"
  }
}
```

#### Entity Embeddings
```json
{
  "collection_name": "entity_embeddings",
  "vectors": {
    "size": 768,
    "distance": "Cosine"
  },
  "payload_schema": {
    "entity_id": "keyword",
    "organization_id": "keyword",
    "entity_type": "keyword",
    "entity_name": "text",
    "canonical_name": "text",
    "extraction_method": "keyword",
    "confidence": "float",
    "document_count": "integer",
    "relationship_count": "integer"
  }
}
```

#### Query Embeddings (for caching)
```json
{
  "collection_name": "query_embeddings",
  "vectors": {
    "size": 1536,
    "distance": "Cosine"
  },
  "payload_schema": {
    "query_id": "keyword",
    "organization_id": "keyword",
    "query_text": "text",
    "query_type": "keyword",
    "user_id": "keyword",
    "session_id": "keyword",
    "result_count": "integer",
    "avg_score": "float",
    "created_at": "integer"
  }
}
```

### 3.2 Collection Indexes

```json
// Payload indexes for efficient filtering
{
  "field_name": "organization_id",
  "field_schema": "keyword",
  "field_type": "keyword"
}

{
  "field_name": "document_type",
  "field_schema": "keyword",
  "field_type": "keyword"
}

{
  "field_name": "primary_modality",
  "field_schema": "keyword",
  "field_type": "keyword"
}

{
  "field_name": "quality_score",
  "field_schema": "float",
  "field_type": "float"
}

{
  "field_name": "created_at",
  "field_schema": "integer",
  "field_type": "integer"
}
```

### 3.3 Search Configuration

#### Hybrid Search Parameters
```json
{
  "search_params": {
    "hnsw": {
      "ef": 128,
      "exact": false
    },
    "exact_search_threshold": 1000,
    "search_strategy": "hybrid"
  },
  "search_filters": {
    "must": [
      {
        "key": "organization_id",
        "match": {"value": "$org_id"}
      },
      {
        "key": "is_indexed",
        "match": {"value": true}
      }
    ],
    "should": [
      {
        "key": "quality_score",
        "range": {"gte": 0.7}
      }
    ]
  }
}
```

---

## 4. Redis Data Structures

### 4.1 Session Management

#### User Sessions
```redis
// Session data structure
session:{session_id} -> Hash {
  user_id: UUID,
  organization_id: UUID,
  email: string,
  role: string,
  created_at: timestamp,
  last_activity: timestamp,
  expires_at: timestamp,
  ip_address: string,
  user_agent: string,
  preferences: JSON,
  ui_settings: JSON
}

// Session TTL management
TTL session:{session_id} = 3600 (1 hour)

// Active sessions by user
user_sessions:{user_id} -> Set[session_id]

// Organization active sessions
org_sessions:{organization_id} -> Set[session_id]
```

#### WebSocket Connections
```redis
// WebSocket connection tracking
ws_connections:{session_id} -> Hash {
  connection_id: string,
  node_id: string,
  connected_at: timestamp,
  last_ping: timestamp,
  subscriptions: JSON
}

// User's active connections
user_ws:{user_id} -> Set[connection_id]

// Organization WebSocket channels
ws_org:{organization_id} -> Set[connection_id]
```

### 4.2 Caching Layers

#### Document Processing Cache
```redis
// Processing status cache
processing_status:{document_id} -> Hash {
  status: string,
  progress: integer,
  current_step: string,
  started_at: timestamp,
  estimated_completion: timestamp,
  error_message: string
}

// Document content cache
document_content:{document_id} -> Hash {
  text_content: string,
  summary: string,
  extracted_entities: JSON,
  metadata: JSON,
  quality_score: float
}

TTL document_content:{document_id} = 86400 (24 hours)
```

#### Search Results Cache
```redis
// Search query cache
search_cache:{query_hash} -> Hash {
  query_text: string,
  organization_id: UUID,
  results: JSON,
  total_count: integer,
  execution_time_ms: integer,
  cached_at: timestamp
}

TTL search_cache:{query_hash} = 1800 (30 minutes)

// Popular queries tracking
popular_queries:{organization_id} -> SortedSet {
  query_text: score (frequency)
}

// User recent searches
user_recent_searches:{user_id} -> List[query_hash]
LTRIM user_recent_searches:{user_id} 0 49 (keep last 50)
```

#### Embedding Cache
```redis
// Text embedding cache
embedding:text:{text_hash} -> Hash {
  embedding: JSON (array),
  model: string,
  created_at: timestamp
}

TTL embedding:text:{text_hash} = 604800 (7 days)

// Image embedding cache
embedding:image:{image_hash} -> Hash {
  embedding: JSON (array),
  model: string,
  created_at: timestamp
}

TTL embedding:image:{image_hash} = 604800 (7 days)
```

### 4.3 Real-Time Analytics

#### Performance Metrics
```redis
// Performance metrics buffer
metrics:performance -> Stream {
  timestamp: timestamp,
  metric_name: string,
  value: float,
  organization_id: UUID,
  component: string
}

// Real-time aggregation
metrics:current:{metric_name}:{organization_id} -> Hash {
  current_value: float,
  count: integer,
  sum: float,
  min: float,
  max: float,
  last_updated: timestamp
}

EXPIRE metrics:current:{metric_name}:{organization_id} = 300 (5 minutes)
```

#### User Activity Tracking
```redis
// User activity stream
activity:user:{user_id} -> Stream {
  event_type: string,
  timestamp: timestamp,
  data: JSON
}

// Organization activity aggregation
activity:org:{organization_id}:count -> Hash {
  active_users: integer,
  total_queries: integer,
  total_documents: integer,
  last_updated: timestamp
}

EXPIRE activity:org:{organization_id}:count = 300 (5 minutes)
```

#### Document Processing Queue
```redis
// High priority processing queue
queue:processing:high -> List[JSON {
  document_id: UUID,
  job_type: string,
  priority: integer,
  queued_at: timestamp,
  max_retries: integer
}]

// Normal priority processing queue
queue:processing:normal -> List[JSON]

// Failed job retry queue
queue:processing:retry -> SortedSet {
  job_id: score (retry_timestamp)
}
```

### 4.4 Rate Limiting

#### API Rate Limiting
```redis
// User rate limiting
rate_limit:user:{user_id}:{endpoint} -> Integer (request count)
EXPIRE rate_limit:user:{user_id}:{endpoint} = 60 (1 minute)

// Organization rate limiting
rate_limit:org:{organization_id}:{endpoint} -> Integer
EXPIRE rate_limit:org:{organization_id}:{endpoint} = 60

// IP-based rate limiting
rate_limit:ip:{ip_address}:{endpoint} -> Integer
EXPIRE rate_limit:ip:{ip_address}:{endpoint} = 60
```

#### Upload Rate Limiting
```redis
// File upload limits
upload_limit:user:{user_id} -> Integer (files uploaded)
EXPIRE upload_limit:user:{user_id} = 3600 (1 hour)

upload_limit:org:{organization_id} -> Integer
EXPIRE upload_limit:org:{organization_id} = 3600

// Storage quota tracking
storage_quota:user:{user_id} -> Hash {
  used_gb: float,
  document_count: integer,
  last_updated: timestamp
}
```

### 4.5 Real-Time Notifications

#### Notification System
```redis
// User notifications
notifications:{user_id} -> List[JSON {
  id: string,
  type: string,
  title: string,
  message: string,
  data: JSON,
  created_at: timestamp,
  read: boolean
}]

// Unread notification count
notifications:unread:{user_id} -> Integer

// Organization-wide notifications
notifications:org:{organization_id} -> List[JSON]
```

#### Document Processing Updates
```redis
// Processing status updates
processing_updates:{document_id} -> Stream {
  timestamp: timestamp,
  status: string,
  progress: integer,
  message: string,
  step: string
}

// User's subscribed documents
processing_subscriptions:{user_id} -> Set[document_id]
```

---

## 5. Migration Strategy

### 5.1 Migration Phases

#### Phase 1: Core User and Organization Tables
```sql
-- Migration 001: Create core tables
BEGIN;

-- Create organizations table
CREATE TABLE organizations ( ... );

-- Create users table
CREATE TABLE users ( ... );

-- Create user_sessions table
CREATE TABLE user_sessions ( ... );

-- Insert initial data
INSERT INTO organizations (name, slug, subscription_tier)
VALUES ('Default Organization', 'default', 'starter');

-- Create indexes
CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_users_email ON users(email);

COMMIT;
```

#### Phase 2: Document Management
```sql
-- Migration 002: Add document tables
BEGIN;

-- Create documents table
CREATE TABLE documents ( ... );

-- Create document_processing_jobs table
CREATE TABLE document_processing_jobs ( ... );

-- Migrate existing document data if any
INSERT INTO documents (id, title, filename, organization_id, uploaded_by_user_id)
SELECT gen_random_uuid(), title, filename, org_id, user_id
FROM legacy_documents;

COMMIT;
```

#### Phase 3: Search and Analytics
```sql
-- Migration 003: Add search and analytics
BEGIN;

-- Create search tables (partitioned)
CREATE TABLE search_queries ( ... ) PARTITION BY RANGE (created_at);
CREATE TABLE search_results ( ... );

-- Create initial partitions
CREATE TABLE search_queries_y2024m01 PARTITION OF search_queries
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Create evaluation tables
CREATE TABLE rag_evaluations ( ... );

COMMIT;
```

### 5.2 Data Validation Scripts

```sql
-- Validate user data integrity
CREATE OR REPLACE FUNCTION validate_user_data()
RETURNS TABLE(validation_type TEXT, status TEXT, details TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT 'email_uniqueness'::TEXT,
           CASE WHEN COUNT(*) = COUNT(DISTINCT email) THEN 'PASS' ELSE 'FAIL' END::TEXT,
           'Email addresses must be unique within organization'::TEXT
    FROM users WHERE is_deleted = FALSE;

    RETURN QUERY
    SELECT 'storage_quota'::TEXT,
           CASE WHEN EVERY(personal_storage_gb <= 5) THEN 'PASS' ELSE 'FAIL' END::TEXT,
           'All users within personal storage quota'::TEXT
    FROM users;

    RETURN QUERY
    SELECT 'orphaned_sessions'::TEXT,
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END::TEXT,
           format('Found %s sessions without valid users', COUNT(*))::TEXT
    FROM user_sessions s
    LEFT JOIN users u ON s.user_id = u.id
    WHERE u.id IS NULL;
END;
$$ LANGUAGE plpgsql;
```

### 5.3 Performance Optimization

```sql
-- Create partial indexes for common queries
CREATE INDEX CONCURRENTLY idx_documents_active
ON documents(organization_id, created_at DESC)
WHERE is_deleted = FALSE AND is_indexed = TRUE;

CREATE INDEX CONCURRENTLY idx_search_queries_recent
ON search_queries(user_id, created_at DESC)
WHERE created_at >= NOW() - INTERVAL '30 days';

-- Create composite indexes for analytics
CREATE INDEX CONCURRENTLY idx_rag_evaluations_composite
ON rag_evaluations(organization_id, overall_score, created_at DESC);

-- Enable parallel query processing
ALTER TABLE search_queries SET (parallel_workers = 4);
ALTER TABLE rag_evaluations SET (parallel_workers = 2);
```

---

## 6. Data Access Patterns

### 6.1 Common Query Patterns

#### Multi-Tenant Data Isolation
```sql
-- All queries must include organization_id filter
CREATE OR REPLACE FUNCTION enforce_organization_access()
RETURNS TRIGGER AS $$
BEGIN
    -- Ensure all queries have organization_id in WHERE clause
    IF TG_OP = 'SELECT' AND NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = TG_RELID
        AND conname = 'organization_filter'
    ) THEN
        RAISE EXCEPTION 'Organization filter required for table %', TG_TABLE_NAME;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Row Level Security (RLS) policies
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY document_organization_policy ON documents
    FOR ALL TO authenticated_users
    USING (organization_id = current_organization_id());

CREATE POLICY document_user_access ON documents
    FOR SELECT TO authenticated_users
    USING (organization_id = current_organization_id() OR is_public = TRUE);
```

#### Optimized Search Query Pattern
```sql
-- Efficient search query with organization isolation
WITH search_context AS (
    SELECT
        q.id,
        q.query_text,
        q.query_type,
        q.total_time_ms,
        -- Calculate click-through rate
        CASE
            WHEN q.total_results > 0 THEN
                ROUND(COUNT(sr.id)::DECIMAL / q.total_results, 4)
            ELSE 0
        END as click_through_rate
    FROM search_queries q
    LEFT JOIN search_results sr ON q.id = sr.search_query_id AND sr.was_clicked = TRUE
    WHERE q.organization_id = $org_id
      AND q.created_at >= $date_from
      AND q.created_at < $date_to
    GROUP BY q.id, q.query_text, q.query_type, q.total_time_ms, q.total_results
)
SELECT
    query_type,
    COUNT(*) as query_count,
    AVG(total_time_ms) as avg_response_time,
    AVG(click_through_rate) as avg_ctr,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_time_ms) as p95_response_time
FROM search_context
GROUP BY query_type
ORDER BY query_count DESC;
```

#### Document Performance Analytics
```sql
-- Document quality and usage analysis
WITH document_metrics AS (
    SELECT
        d.id,
        d.title,
        d.document_type,
        d.quality_score,
        d.processing_status,
        -- Usage metrics
        COUNT(DISTINCT sr.search_query_id) as query_count,
        COUNT(DISTINCT CASE WHEN sr.was_clicked THEN sr.search_query_id END) as click_count,
        AVG(sr.relevance_score) as avg_relevance_score,
        -- Processing metrics
        d.processing_completed_at - d.processing_started_at as processing_duration
    FROM documents d
    LEFT JOIN search_results sr ON d.id = sr.document_id
    LEFT JOIN search_queries sq ON sr.search_query_id = sq.id
    WHERE d.organization_id = $org_id
      AND d.created_at >= $date_from
    GROUP BY d.id, d.title, d.document_type, d.quality_score, d.processing_status,
             d.processing_completed_at, d.processing_started_at
)
SELECT
    document_type,
    processing_status,
    COUNT(*) as document_count,
    AVG(quality_score) as avg_quality,
    AVG(processing_duration) as avg_processing_time,
    AVG(query_count) as avg_query_count,
    ROUND(AVG(click_count::DECIMAL / NULLIF(query_count, 0)), 4) as avg_click_rate
FROM document_metrics
GROUP BY document_type, processing_status
ORDER BY document_type, processing_status;
```

### 6.2 Caching Strategy

#### Multi-Level Cache Architecture
```python
# Cache hierarchy implementation
class CacheManager:
    def __init__(self):
        self.redis_client = Redis()
        self.local_cache = {}

    async def get_document_content(self, document_id: str):
        # Level 1: Local memory cache (fastest)
        if document_id in self.local_cache:
            return self.local_cache[document_id]

        # Level 2: Redis cache (fast)
        cached = await self.redis_client.hgetall(f"document_content:{document_id}")
        if cached:
            self.local_cache[document_id] = cached
            return cached

        # Level 3: Database (slowest)
        document = await self.get_document_from_db(document_id)
        if document:
            # Cache in Redis with TTL
            await self.redis_client.hset(
                f"document_content:{document_id}",
                mapping=document
            )
            await self.redis_client.expire(f"document_content:{document_id}", 86400)

            # Cache in local memory
            self.local_cache[document_id] = document

        return document
```

#### Cache Invalidation Strategy
```python
# Intelligent cache invalidation
class CacheInvalidator:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def invalidate_document_cache(self, document_id: str, organization_id: str):
        # Invalidate specific document cache
        await self.redis.delete(f"document_content:{document_id}")

        # Invalidate related search caches
        pattern = f"search_cache:*:{organization_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

        # Notify WebSocket subscribers
        await self.notify_document_update(document_id, organization_id)

    async def invalidate_user_cache(self, user_id: str, organization_id: str):
        # Invalidate user-specific caches
        await self.redis.delete(f"user_preferences:{user_id}")
        await self.redis.delete(f"user_recent_searches:{user_id}")

        # Clear local cache entries
        pattern = f"local_cache:user:{user_id}:*"
        # Clear local cache implementation-specific
```

---

## 7. Security Considerations

### 7.1 Multi-Tenant Data Isolation

#### Database-Level Security
```sql
-- Row Level Security (RLS) for all tables
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_queries ENABLE ROW LEVEL SECURITY;

-- Organization-based access policies
CREATE POLICY org_isolation ON organizations
    FOR ALL TO application_role
    USING (id = current_setting('app.current_organization_id')::UUID);

CREATE POLICY user_org_isolation ON users
    FOR ALL TO application_role
    USING (organization_id = current_setting('app.current_organization_id')::UUID);

CREATE POLICY document_org_isolation ON documents
    FOR ALL TO application_role
    USING (organization_id = current_setting('app.current_organization_id')::UUID);
```

#### Application-Level Security
```python
# Middleware for organization context
async def set_organization_context(request: Request):
    user_id = get_current_user_id(request)
    org_id = await get_user_organization_id(user_id)

    # Set organization context for database session
    await set_database_context("app.current_organization_id", org_id)

    # Set Redis context
    await redis.set(f"current_org:{user_id}", org_id, ex=3600)

# Data access validation
def validate_organization_access(table_name: str, organization_id: str):
    query = f"""
    SELECT EXISTS(
        SELECT 1 FROM information_schema.columns
        WHERE table_name = '{table_name}'
        AND column_name = 'organization_id'
    )
    """
    return execute_query(query)
```

### 7.2 Data Encryption

#### Sensitive Data Encryption
```sql
-- Encryption for sensitive fields
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Encrypt user PII
ALTER TABLE users ADD COLUMN email_encrypted BYTEA;
UPDATE users SET email_encrypted = pgp_sym_encrypt(email, current_setting('app.encryption_key'));

-- Encrypt document file paths
ALTER TABLE documents ADD COLUMN file_path_encrypted BYTEA;
UPDATE documents SET file_path_encrypted = pgp_sym_encrypt(file_path, current_setting('app.encryption_key'));

-- Create secure views
CREATE VIEW users_secure AS
SELECT
    id,
    organization_id,
    pgp_sym_decrypt(email_encrypted, current_setting('app.encryption_key')) as email,
    first_name,
    last_name,
    role,
    is_active,
    created_at
FROM users;
```

#### API Security
```python
# JWT token with organization context
class SecureTokenGenerator:
    def __init__(self, secret_key: str):
        self.secret = secret_key

    def create_token(self, user_id: str, organization_id: str, permissions: list):
        payload = {
            'user_id': user_id,
            'organization_id': organization_id,
            'permissions': permissions,
            'exp': datetime.utcnow() + timedelta(hours=1),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, self.secret, algorithm='HS256')

    def verify_token(self, token: str):
        try:
            payload = jwt.decode(token, self.secret, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            raise UnauthorizedException("Token has expired")
        except jwt.InvalidTokenError:
            raise UnauthorizedException("Invalid token")
```

### 7.3 Audit Logging

#### Comprehensive Audit Trail
```sql
-- Audit log table
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event information
    event_type VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL, -- CREATE, READ, UPDATE, DELETE
    table_name VARCHAR(100),
    record_id UUID,

    -- User context
    user_id UUID REFERENCES users(id),
    organization_id UUID REFERENCES organizations(id),
    session_id UUID REFERENCES user_sessions(id),

    -- Request context
    ip_address INET,
    user_agent TEXT,
    endpoint VARCHAR(255),

    -- Data changes
    old_values JSONB,
    new_values JSONB,

    -- Metadata
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT
) PARTITION BY RANGE (timestamp);

-- Create audit trigger function
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_logs (
        event_type, action, table_name, record_id,
        user_id, organization_id, ip_address, user_agent,
        old_values, new_values, timestamp, success
    ) VALUES (
        TG_ARGV[0], TG_OP, TG_TABLE_NAME, COALESCE(NEW.id, OLD.id),
        current_setting('app.current_user_id', true)::UUID,
        current_setting('app.current_organization_id', true)::UUID,
        current_setting('app.client_ip', true),
        current_setting('app.user_agent', true),
        row_to_json(OLD), row_to_json(NEW),
        NOW(), TRUE
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Apply audit triggers to sensitive tables
CREATE TRIGGER users_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function('user_management');

CREATE TRIGGER documents_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON documents
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function('document_management');
```

---

## 8. Performance Optimization

### 8.1 Query Optimization

#### Materialized Views for Analytics
```sql
-- Daily analytics summary
CREATE MATERIALIZED VIEW daily_analytics_summary AS
SELECT
    DATE_TRUNC('day', created_at) as date,
    organization_id,

    -- Document metrics
    COUNT(DISTINCT id) as total_documents,
    AVG(file_size_bytes) as avg_file_size,
    SUM(file_size_bytes) as total_storage_used,

    -- Processing metrics
    AVG(processing_time_ms) as avg_processing_time,
    COUNT(CASE WHEN processing_status = 'completed' THEN 1 END) as completed_documents,
    COUNT(CASE WHEN processing_status = 'failed' THEN 1 END) as failed_documents,

    -- Quality metrics
    AVG(quality_score) as avg_quality_score,
    COUNT(CASE WHEN quality_score >= 0.8 THEN 1 END) as high_quality_docs

FROM documents
WHERE is_deleted = FALSE
GROUP BY DATE_TRUNC('day', created_at), organization_id;

CREATE INDEX idx_daily_analytics_date_org ON daily_analytics_summary(date, organization_id);

-- Refresh strategy
CREATE OR REPLACE FUNCTION refresh_daily_analytics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY daily_analytics_summary;
END;
$$ LANGUAGE plpgsql;

-- Schedule refresh (using pg_cron)
SELECT cron.schedule('refresh-daily-analytics', '0 2 * * *', 'SELECT refresh_daily_analytics();');
```

#### Query Performance Monitoring
```sql
-- Slow query logging
ALTER SYSTEM SET log_min_duration_statement = 1000; -- Log queries > 1s
ALTER SYSTEM SET log_statement = 'all';
SELECT pg_reload_conf();

-- Query statistics table
CREATE TABLE query_performance_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    query_hash VARCHAR(64),
    query_text TEXT,
    execution_plan JSONB,

    execution_time_ms INTEGER,
    rows_returned INTEGER,
    rows_examined INTEGER,

    organization_id UUID,
    user_id UUID,

    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Performance analysis function
CREATE OR REPLACE FUNCTION analyze_query_performance(query_hash TEXT)
RETURNS TABLE (
    avg_execution_time DECIMAL,
    max_execution_time INTEGER,
    total_executions BIGINT,
    recent_trend TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        AVG(execution_time_ms) as avg_execution_time,
        MAX(execution_time_ms) as max_execution_time,
        COUNT(*) as total_executions,
        CASE
            WHEN AVG(CASE WHEN timestamp >= NOW() - INTERVAL '1 day' THEN execution_time_ms END) >
                 AVG(CASE WHEN timestamp >= NOW() - INTERVAL '7 day' THEN execution_time_ms END)
            THEN 'Degrading'
            WHEN AVG(CASE WHEN timestamp >= NOW() - INTERVAL '1 day' THEN execution_time_ms END) <
                 AVG(CASE WHEN timestamp >= NOW() - INTERVAL '7 day' THEN execution_time_ms END) * 0.8
            THEN 'Improving'
            ELSE 'Stable'
        END as recent_trend
    FROM query_performance_stats
    WHERE query_hash = $1
      AND timestamp >= NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;
```

### 8.2 Connection Pooling

#### Database Connection Management
```python
# Advanced connection pooling
class DatabasePool:
    def __init__(self):
        self.pool = create_engine(
            DATABASE_URL,
            pool_size=20,           # Base connection pool size
            max_overflow=30,        # Additional connections under load
            pool_pre_ping=True,     # Validate connections
            pool_recycle=3600,      # Recycle connections hourly
            echo=False
        )

    async def execute_query(self, query: str, params: dict = None):
        async with self.pool.connect() as conn:
            try:
                result = await conn.execute(text(query), params or {})
                return result.fetchall()
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                raise

    async def execute_transaction(self, queries: List[tuple]):
        async with self.pool.begin() as conn:
            try:
                results = []
                for query, params in queries:
                    result = await conn.execute(text(query), params or {})
                    results.append(result)
                return results
            except Exception as e:
                await conn.rollback()
                raise
```

---

## 9. Monitoring and Alerting

### 9.1 Database Health Monitoring

#### Health Check Queries
```sql
-- Comprehensive health check
CREATE OR REPLACE FUNCTION system_health_check()
RETURNS TABLE (
    component TEXT,
    status TEXT,
    response_time_ms INTEGER,
    details JSONB
) AS $$
BEGIN
    -- Database connectivity
    RETURN QUERY
    SELECT
        'database'::TEXT as component,
        CASE WHEN pg_is_in_recovery() = false THEN 'healthy' ELSE 'replicating' END::TEXT as status,
        EXTRACT(EPOCH FROM (NOW() - (SELECT stats_reset FROM pg_stat_database WHERE datname = current_database()))) * 1000 as response_time_ms,
        jsonb_build_object(
            'connections_active', (SELECT count(*) FROM pg_stat_activity WHERE state = 'active'),
            'connections_total', (SELECT count(*) FROM pg_stat_activity),
            'database_size', pg_size_pretty(pg_database_size(current_database()))
        ) as details;

    -- Table sizes and growth
    RETURN QUERY
    SELECT
        'table_storage'::TEXT as component,
        CASE
            WHEN pg_total_relation_size(schemaname||'.'||tablename) < 1073741824 THEN 'healthy'
            WHEN pg_total_relation_size(schemaname||'.'||tablename) < 10737418240 THEN 'warning'
            ELSE 'critical'
        END::TEXT as status,
        0 as response_time_ms,
        jsonb_build_object(
            'table_name', schemaname||'.'||tablename,
            'size_bytes', pg_total_relation_size(schemaname||'.'||tablename),
            'size_human', pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)),
            'row_count', n_tup_ins + n_tup_upd + n_tup_del
        ) as details
    FROM pg_stat_user_tables
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
    LIMIT 5;
END;
$$ LANGUAGE plpgsql;
```

### 9.2 Performance Metrics Collection

#### Metrics Collection Pipeline
```python
# Metrics collection service
class MetricsCollector:
    def __init__(self, db_pool, redis_client):
        self.db = db_pool
        self.redis = redis_client

    async def collect_database_metrics(self):
        metrics = await self.db.execute_query("""
            SELECT
                schemaname,
                tablename,
                n_tup_ins as inserts,
                n_tup_upd as updates,
                n_tup_del as deletes,
                n_live_tup as live_tuples,
                n_dead_tup as dead_tuples,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze
            FROM pg_stat_user_tables
        """)

        # Store metrics in Redis for real-time monitoring
        for metric in metrics:
            await self.redis.hset(
                f"db_metrics:{metric.tablename}",
                mapping={
                    'inserts': metric.inserts,
                    'updates': metric.updates,
                    'deletes': metric.deletes,
                    'live_tuples': metric.live_tuples,
                    'dead_tuples': metric.dead_tuples,
                    'timestamp': datetime.utcnow().timestamp()
                }
            )

    async def collect_query_performance(self):
        slow_queries = await self.db.execute_query("""
            SELECT
                query,
                calls,
                total_exec_time,
                mean_exec_time,
                rows
            FROM pg_stat_statements
            WHERE mean_exec_time > 1000  -- Queries slower than 1 second
            ORDER BY mean_exec_time DESC
            LIMIT 10
        """)

        # Alert on slow queries
        for query in slow_queries:
            await self.redis.xadd(
                'slow_queries',
                {
                    'query': query.query[:500],  # Truncate long queries
                    'mean_time_ms': int(query.mean_exec_time * 1000),
                    'total_calls': query.calls,
                    'timestamp': datetime.utcnow().timestamp()
                }
            )
```

---

## 10. Disaster Recovery and Backup

### 10.1 Backup Strategy

#### Automated Backup Configuration
```bash
#!/bin/bash
# backup_database.sh

# Database backup configuration
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="multimodal_rag"
BACKUP_DIR="/backups/postgresql"
RETENTION_DAYS=30

# Create backup with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/multimodal_rag_backup_$TIMESTAMP.sql"

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Perform database backup
pg_dump -h $DB_HOST -p $DB_PORT -U postgres -d $DB_NAME \
    --format=custom \
    --compress=9 \
    --verbose \
    --file=$BACKUP_FILE

# Verify backup integrity
pg_restore --list $BACKUP_FILE > /dev/null
if [ $? -eq 0 ]; then
    echo "Backup completed successfully: $BACKUP_FILE"

    # Compress backup
    gzip $BACKUP_FILE
    BACKUP_FILE="${BACKUP_FILE}.gz"

    # Upload to cloud storage (AWS S3 example)
    aws s3 cp $BACKUP_FILE s3://multimodal-rag-backups/database/

    # Clean up local files older than retention period
    find $BACKUP_DIR -name "*.gz" -mtime +$RETENTION_DAYS -delete

else
    echo "Backup verification failed for: $BACKUP_FILE"
    exit 1
fi
```

#### Point-in-Time Recovery Setup
```sql
-- Enable WAL archiving for point-in-time recovery
ALTER SYSTEM SET wal_level = replica;
ALTER SYSTEM SET archive_mode = on;
ALTER SYSTEM SET archive_command = 'cp %p /wal_archive/%f';
ALTER SYSTEM SET max_wal_senders = 3;
ALTER SYSTEM SET wal_keep_segments = 32;

SELECT pg_reload_conf();

-- Create restore function
CREATE OR REPLACE FUNCTION restore_database(
    target_time TIMESTAMPTZ,
    backup_file TEXT
) RETURNS BOOLEAN AS $$
DECLARE
    restore_result BOOLEAN;
BEGIN
    -- This would be executed by a restore script, not directly in SQL
    -- The actual restore process involves:
    -- 1. Stop PostgreSQL
    -- 2. Restore from backup
    -- 3. Apply WAL logs up to target_time
    -- 4. Restart PostgreSQL

    RAISE NOTICE 'Database restore initiated for timestamp: %', target_time;
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;
```

### 10.2 High Availability Configuration

#### Streaming Replication Setup
```sql
-- Primary server configuration
ALTER SYSTEM SET synchronous_commit = on;
ALTER SYSTEM SET synchronous_standby_names = 'standby1,standby2';

-- Create replication user
CREATE USER replicator REPLICATION LOGIN CONNECTION LIMIT 3 ENCRYPTED PASSWORD 'secure_password';

-- Monitor replication lag
CREATE OR REPLACE FUNCTION check_replication_lag()
RETURNS TABLE (
    standby_name TEXT,
    lag_seconds INTEGER,
    status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        application_name as standby_name,
        EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))::INTEGER as lag_seconds,
        CASE
            WHEN EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) < 10 THEN 'synced'
            WHEN EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) < 60 THEN 'lagging'
            ELSE 'critical'
        END as status
    FROM pg_stat_replication
    WHERE state = 'streaming';
END;
$$ LANGUAGE plpgsql;
```

---

## Summary

This comprehensive database schema design provides:

1. **Complete PostgreSQL schema** with optimized tables, indexes, and constraints
2. **Neo4j graph structure** for knowledge graph entities and relationships
3. **Qdrant collections** for multi-modal vector embeddings
4. **Redis data structures** for caching, sessions, and real-time features
5. **Multi-tenant security** with row-level security and data isolation
6. **Performance optimization** through partitioning, indexing, and caching
7. **Monitoring and alerting** for system health and performance
8. **Backup and recovery** strategies for high availability

The schema supports all specified requirements:
- 5GB storage quota per user with enforcement
- Multi-modal document processing with status tracking
- Real-time WebSocket updates via Redis
- RAG Triad evaluation metrics
- 99% uptime targets with 2-second query response goals
- 50 concurrent user capacity with proper resource management
- 30-day query retention with automated archival

The design scales horizontally, maintains data security across tenants, and provides the foundation for a production-ready multimodal enterprise RAG system.