# Database Schema Design for Multimodal Enterprise RAG System
## Evaluation and Analytics Platform

This document presents a comprehensive database schema design for the evaluation and analytics platform that complements the existing Neo4j-based knowledge graphs and Qdrant vector storage systems.

## Architecture Overview

The system uses a multi-database architecture:
- **PostgreSQL Analytics DB**: Primary analytics data warehouse (time-series, metrics, A/B testing)
- **Neo4j**: Knowledge graphs and entity relationships (existing)
- **Qdrant**: Vector storage for semantic search (existing)
- **Redis**: Real-time caching and session storage
- **InfluxDB**: High-frequency time-series metrics (optional)

## 1. Logical Data Model

### Core Entities

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Organization  │    │      User        │    │   Session       │
│─────────────────│    │──────────────────│    │─────────────────│
│ id (PK)         │◄──┤ id (PK)          │◄──┤ id (PK)         │
│ name            │    │ organization_id  │    │ user_id         │
│ settings        │    │ email            │    │ session_data    │
│ created_at      │    │ created_at       │    │ created_at      │
│ updated_at      │    │ updated_at       │    │ ended_at        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Document      │    │   SearchQuery    │    │   A/BTest       │
│─────────────────│    │──────────────────│    │─────────────────│
│ id (PK)         │    │ id (PK)          │    │ id (PK)         │
│ organization_id │    │ user_id          │    │ organization_id │
│ file_metadata   │    │ session_id       │    │ status          │
│ content_hash    │    │ query_text       │    │ variants        │
│ created_at      │    │ query_results    │    │ metrics         │
└─────────────────┘    │ created_at       │    │ created_at      │
         │              └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ EvaluationRun   │    │   PerformanceLog │    │   SystemHealth  │
│─────────────────│    │──────────────────│    │─────────────────│
│ id (PK)         │    │ id (PK)          │    │ id (PK)         │
│ query_id        │    │ metric_name      │    │ component       │
│ document_id     │    │ metric_value     │    │ status          │
│ rag_triad_score │    │ timestamp        │    │ metrics         │
│ custom_metrics  │    │ component        │    │ timestamp       │
│ created_at      │    │ organization_id  │    │ created_at      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Entity Relationships

1. **Organization → Users**: One-to-many (multi-tenancy)
2. **User → Sessions**: One-to-many (user tracking)
3. **Session → SearchQueries**: One-to-many (query history)
4. **SearchQuery → Documents**: Many-to-many (query-document interactions)
5. **SearchQuery → EvaluationRun**: One-to-one (evaluation results)
6. **Organization → A/BTests**: One-to-many (experiment management)
7. **A/BTest → Variants**: One-to-many (test configurations)
8. **SearchQuery → A/BTest**: Many-to-one (experiment assignment)
9. **PerformanceLog → Organization**: Many-to-one (organizational metrics)
10. **SystemHealth**: Global system monitoring

## 2. Physical Database Schema

### 2.1 Core Tables

#### Users and Organizations
```sql
-- Organizations table for multi-tenancy
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    settings JSONB DEFAULT '{}',
    subscription_plan VARCHAR(50) DEFAULT 'basic',
    max_documents INTEGER DEFAULT 10000,
    max_users INTEGER DEFAULT 100,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_organizations_plan ON organizations(subscription_plan);

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    email VARCHAR(255) NOT NULL,
    username VARCHAR(100) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'user',
    preferences JSONB DEFAULT '{}',
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    UNIQUE(organization_id, email),
    UNIQUE(organization_id, username)
);

CREATE INDEX idx_users_organization ON users(organization_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
```

#### Session Management
```sql
-- User sessions for tracking interactions
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    session_token VARCHAR(255) UNIQUE NOT NULL,
    session_data JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    device_info JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_token ON user_sessions(session_token);
CREATE INDEX idx_sessions_active ON user_sessions(is_active, expires_at);
CREATE INDEX idx_sessions_created ON user_sessions(created_at DESC);
```

### 2.2 Document and Search Tables

#### Document Analytics
```sql
-- Document usage and performance tracking
CREATE TABLE document_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id VARCHAR(255) NOT NULL, -- References external document store
    organization_id UUID NOT NULL REFERENCES organizations(id),
    file_metadata JSONB DEFAULT '{}',
    content_hash VARCHAR(64),
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),
    processing_status VARCHAR(50) DEFAULT 'pending',
    processing_time_ms INTEGER,
    quality_score DECIMAL(5,4),
    extraction_confidence DECIMAL(5,4),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    UNIQUE(organization_id, document_id)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE document_analytics_y2024m01 PARTITION OF document_analytics
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE INDEX idx_doc_analytics_org ON document_analytics(organization_id);
CREATE INDEX idx_doc_analytics_status ON document_analytics(processing_status);
CREATE INDEX idx_doc_analytics_quality ON document_analytics(quality_score);
CREATE INDEX idx_doc_analytics_created ON document_analytics(created_at DESC);
```

#### Search Query Tracking
```sql
-- Search queries and their performance
CREATE TABLE search_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    session_id UUID REFERENCES user_sessions(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    query_text TEXT NOT NULL,
    query_type VARCHAR(50) DEFAULT 'hybrid', -- hybrid, vector, graph, keyword
    query_metadata JSONB DEFAULT '{}',

    -- Search results
    result_count INTEGER DEFAULT 0,
    result_ids JSONB DEFAULT '[]', -- Document IDs returned
    result_scores JSONB DEFAULT '[]',

    -- Performance metrics
    query_time_ms INTEGER NOT NULL,
    vector_search_time_ms INTEGER,
    graph_search_time_ms INTEGER,
    ranking_time_ms INTEGER,

    -- User interaction
    clicked_result_ids JSONB DEFAULT '[]',
    clicked_positions JSONB DEFAULT '[]',
    user_satisfaction_score INTEGER, -- 1-5 rating

    -- A/B testing
    experiment_id UUID REFERENCES ab_experiments(id),
    variant_id UUID REFERENCES ab_variants(id),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE search_queries_y2024m01 PARTITION OF search_queries
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE INDEX idx_search_queries_user ON search_queries(user_id, created_at DESC);
CREATE INDEX idx_search_queries_session ON search_queries(session_id, created_at DESC);
CREATE INDEX idx_search_queries_org ON search_queries(organization_id, created_at DESC);
CREATE INDEX idx_search_queries_type ON search_queries(query_type, created_at DESC);
CREATE INDEX idx_search_queries_time ON search_queries(query_time_ms, created_at DESC);
CREATE INDEX idx_search_queries_experiment ON search_queries(experiment_id, variant_id, created_at DESC);
```

### 2.3 Evaluation Metrics Tables

#### RAG Triad Evaluation
```sql
-- RAG Triad metrics evaluation runs
CREATE TABLE evaluation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID NOT NULL REFERENCES search_queries(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    evaluation_type VARCHAR(50) DEFAULT 'rag_triad',

    -- RAG Triad metrics
    answer_relevancy_score DECIMAL(5,4), -- 0.0000 - 1.0000
    answer_relevancy_confidence DECIMAL(5,4),
    answer_relevancy_threshold DECIMAL(5,4) DEFAULT 0.7000,

    faithfulness_score DECIMAL(5,4), -- 0.0000 - 1.0000
    faithfulness_confidence DECIMAL(5,4),
    faithfulness_threshold DECIMAL(5,4) DEFAULT 0.9000,

    contextual_relevancy_score DECIMAL(5,4), -- 0.0000 - 1.0000
    contextual_relevancy_confidence DECIMAL(5,4),
    contextual_relevancy_threshold DECIMAL(5,4) DEFAULT 0.7000,

    -- Overall assessment
    overall_score DECIMAL(5,4),
    meets_thresholds BOOLEAN,

    -- Evaluation metadata
    evaluator_model VARCHAR(100),
    evaluation_config JSONB DEFAULT '{}',
    evaluation_time_ms INTEGER,
    cost_tokens INTEGER,
    cost_usd DECIMAL(10,6),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE evaluation_runs_y2024m01 PARTITION OF evaluation_runs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE INDEX idx_evaluation_runs_query ON evaluation_runs(query_id);
CREATE INDEX idx_evaluation_runs_org ON evaluation_runs(organization_id, created_at DESC);
CREATE INDEX idx_evaluation_runs_type ON evaluation_runs(evaluation_type, created_at DESC);
CREATE INDEX idx_evaluation_runs_overall ON evaluation_runs(overall_score, created_at DESC);
```

#### Custom Metrics
```sql
-- Custom evaluation metrics
CREATE TABLE custom_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_run_id UUID NOT NULL REFERENCES evaluation_runs(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),

    metric_name VARCHAR(255) NOT NULL,
    metric_category VARCHAR(100) NOT NULL, -- quality, performance, safety, etc.
    metric_value DECIMAL(10,6) NOT NULL,
    metric_unit VARCHAR(50),

    -- Thresholds
    threshold_min DECIMAL(10,6),
    threshold_max DECIMAL(10,6),
    threshold_target DECIMAL(10,6),
    meets_thresholds BOOLEAN,

    -- Assessment details
    confidence_score DECIMAL(5,4),
    assessment_method VARCHAR(100), -- automated, manual, hybrid
    metric_details JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(evaluation_run_id, metric_name)
) PARTITION BY RANGE (created_at);

CREATE INDEX idx_custom_metrics_run ON custom_metrics(evaluation_run_id);
CREATE INDEX idx_custom_metrics_org ON custom_metrics(organization_id, created_at DESC);
CREATE INDEX idx_custom_metrics_category ON custom_metrics(metric_category, created_at DESC);
CREATE INDEX idx_custom_metrics_name ON custom_metrics(metric_name, created_at DESC);
```

### 2.4 A/B Testing Tables

```sql
-- A/B Test experiments
CREATE TABLE ab_experiments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    hypothesis TEXT NOT NULL,

    experiment_type VARCHAR(100) NOT NULL, -- search_algorithm, ranking_model, etc.
    status VARCHAR(50) DEFAULT 'draft', -- draft, running, completed, etc.

    -- Timing
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    scheduled_start TIMESTAMPTZ,
    scheduled_end TIMESTAMPTZ,

    -- Traffic configuration
    traffic_split_type VARCHAR(50) DEFAULT 'uniform', -- uniform, weighted, bandit
    traffic_percentage DECIMAL(5,2) DEFAULT 100.00,
    max_participants INTEGER,

    -- Statistical configuration
    confidence_level DECIMAL(3,2) DEFAULT 0.95,
    minimum_sample_size INTEGER DEFAULT 1000,
    statistical_test VARCHAR(50) DEFAULT 'z_test',
    expected_effect_size DECIMAL(5,4),

    -- Success criteria
    primary_metric VARCHAR(100) NOT NULL,
    success_criteria VARCHAR(50) DEFAULT 'higher_is_better',
    target_improvement DECIMAL(5,4),

    -- Results
    winning_variant_id UUID REFERENCES ab_variants(id),
    statistical_significance DECIMAL(10,8),
    effect_size DECIMAL(10,8),
    confidence_interval_lower DECIMAL(10,8),
    confidence_interval_upper DECIMAL(10,8),

    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,

    UNIQUE(organization_id, name)
);

CREATE INDEX idx_ab_experiments_org_status ON ab_experiments(organization_id, status);
CREATE INDEX idx_ab_experiments_type_status ON ab_experiments(experiment_type, status);
CREATE INDEX idx_ab_experiments_timing ON ab_experiments(start_time, end_time);

-- A/B Test variants
CREATE TABLE ab_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES ab_experiments(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_control BOOLEAN DEFAULT FALSE,

    configuration JSONB NOT NULL,
    traffic_weight DECIMAL(5,2) DEFAULT 1.00,

    -- Performance metrics
    participant_count INTEGER DEFAULT 0,
    query_count INTEGER DEFAULT 0,
    primary_metric_value DECIMAL(10,6),
    conversion_count INTEGER DEFAULT 0,
    click_count INTEGER DEFAULT 0,
    total_response_time_ms BIGINT DEFAULT 0,

    -- Statistical metrics
    standard_error DECIMAL(10,8),
    confidence_interval_lower DECIMAL(10,8),
    confidence_interval_upper DECIMAL(10,8),
    p_value DECIMAL(10,8),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,

    UNIQUE(experiment_id, name)
);

CREATE INDEX idx_ab_variants_experiment ON ab_variants(experiment_id);
CREATE INDEX idx_ab_variants_control ON ab_variants(experiment_id, is_control);

-- A/B Test assignments
CREATE TABLE ab_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    session_id UUID REFERENCES user_sessions(id),
    experiment_id UUID NOT NULL REFERENCES ab_experiments(id),
    variant_id UUID NOT NULL REFERENCES ab_variants(id),

    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    assignment_source VARCHAR(100),
    user_segment JSONB,

    UNIQUE(user_id, experiment_id),
    UNIQUE(session_id, experiment_id)
);

CREATE INDEX idx_ab_assignments_user ON ab_assignments(user_id, experiment_id);
CREATE INDEX idx_ab_assignments_variant ON ab_assignments(variant_id, assigned_at);

-- A/B Test metrics
CREATE TABLE ab_experiment_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    experiment_id UUID NOT NULL REFERENCES ab_experiments(id),
    variant_id UUID NOT NULL REFERENCES ab_variants(id),

    metric_type VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10,6) NOT NULL,

    user_id UUID REFERENCES users(id),
    session_id UUID REFERENCES user_sessions(id),
    query_id UUID REFERENCES search_queries(id),

    metric_metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMPTZ DEFAULT NOW(),

    -- Aggregation helpers
    date_hour VARCHAR(13) NOT NULL, -- YYYY-MM-DDTHH
    date_day VARCHAR(10) NOT NULL,  -- YYYY-MM-DD
) PARTITION BY RANGE (timestamp);

CREATE INDEX idx_ab_metrics_experiment_variant ON ab_experiment_metrics(experiment_id, variant_id, metric_type);
CREATE INDEX idx_ab_metrics_variant_time ON ab_experiment_metrics(variant_id, timestamp);
CREATE INDEX idx_ab_metrics_type_time ON ab_experiment_metrics(metric_type, timestamp);
```

### 2.5 Performance Monitoring Tables

```sql
-- System performance logs
CREATE TABLE performance_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    metric_name VARCHAR(255) NOT NULL,
    metric_category VARCHAR(100) NOT NULL,
    performance_level VARCHAR(50) NOT NULL,

    organization_id UUID REFERENCES organizations(id),

    -- Metric values
    value DECIMAL(15,6) NOT NULL,
    unit VARCHAR(50),
    baseline_value DECIMAL(15,6),
    threshold_warning DECIMAL(15,6),
    threshold_critical DECIMAL(15,6),

    -- System resources
    cpu_usage_percent DECIMAL(5,2),
    memory_usage_mb DECIMAL(10,2),
    memory_usage_percent DECIMAL(5,2),
    disk_usage_gb DECIMAL(10,2),
    disk_usage_percent DECIMAL(5,2),

    -- Application metrics
    response_time_ms INTEGER,
    request_count INTEGER,
    error_count INTEGER,
    active_connections INTEGER,

    -- Database metrics
    db_connections INTEGER,
    db_query_time_ms INTEGER,
    db_slow_queries INTEGER,
    db_cache_hit_rate DECIMAL(5,4),

    -- Search metrics
    search_query_time_ms INTEGER,
    index_size_mb DECIMAL(10,2),
    search_results_count INTEGER,

    -- Context
    component VARCHAR(100),
    environment VARCHAR(50),
    version VARCHAR(50),
    node_id VARCHAR(100),

    -- Additional data
    tags JSONB DEFAULT '{}',
    event_metadata JSONB DEFAULT '{}',
    alert_triggered BOOLEAN DEFAULT FALSE,

    timestamp TIMESTAMPTZ DEFAULT NOW(),
    date_hour VARCHAR(13) NOT NULL,
    date_day VARCHAR(10) NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    batch_id VARCHAR(100)
) PARTITION BY RANGE (timestamp);

-- Create weekly partitions for performance logs
CREATE TABLE performance_logs_y2024w01 PARTITION OF performance_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-01-08');

CREATE INDEX idx_performance_logs_metric_time ON performance_logs(metric_name, timestamp);
CREATE INDEX idx_performance_logs_category_time ON performance_logs(metric_category, timestamp);
CREATE INDEX idx_performance_logs_org_time ON performance_logs(organization_id, timestamp);
CREATE INDEX idx_performance_logs_level_time ON performance_logs(performance_level, timestamp);
CREATE INDEX idx_performance_logs_component_time ON performance_logs(component, timestamp);
CREATE INDEX idx_performance_logs_alert ON performance_logs(alert_triggered, timestamp);
```

### 2.6 System Health and Error Tracking

```sql
-- System health monitoring
CREATE TABLE system_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    component VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL, -- healthy, degraded, critical, offline

    health_check_url VARCHAR(500),
    response_time_ms INTEGER,
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,

    error_count_24h INTEGER DEFAULT 0,
    error_rate_24h DECIMAL(5,4),

    dependencies JSONB DEFAULT '{}',
    health_metrics JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(component)
);

CREATE INDEX idx_system_health_status ON system_health(status);
CREATE INDEX idx_system_health_component ON system_health(component);

-- Error tracking
CREATE TABLE error_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    error_id VARCHAR(100) UNIQUE NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_code VARCHAR(50),
    error_message TEXT NOT NULL,
    error_stack TEXT,

    severity VARCHAR(50) DEFAULT 'error', -- warning, error, critical
    component VARCHAR(100),

    organization_id UUID REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    session_id UUID REFERENCES user_sessions(id),

    request_context JSONB DEFAULT '{}',
    system_context JSONB DEFAULT '{}',

    resolution_status VARCHAR(50) DEFAULT 'open', -- open, investigating, resolved
    resolved_by UUID REFERENCES users(id),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,

    occurred_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (occurred_at);

CREATE TABLE error_logs_y2024m01 PARTITION OF error_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE INDEX idx_error_logs_type ON error_logs(error_type, occurred_at DESC);
CREATE INDEX idx_error_logs_severity ON error_logs(severity, occurred_at DESC);
CREATE INDEX idx_error_logs_component ON error_logs(component, occurred_at DESC);
CREATE INDEX idx_error_logs_status ON error_logs(resolution_status, occurred_at DESC);
```

### 2.7 User Analytics and Interaction Tracking

```sql
-- User interaction events
CREATE TABLE user_interaction_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID REFERENCES users(id),
    session_id UUID REFERENCES user_sessions(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),

    event_type VARCHAR(100) NOT NULL, -- click, hover, scroll, download, share, etc.
    event_action VARCHAR(100) NOT NULL,

    -- Event context
    component VARCHAR(100), -- search_results, document_viewer, etc.
    element_id VARCHAR(255),
    element_type VARCHAR(100),

    -- Document/Query context
    document_id VARCHAR(255),
    query_id UUID REFERENCES search_queries(id),
    result_position INTEGER,

    -- Event data
    event_data JSONB DEFAULT '{}',
    coordinates JSONB, -- x, y coordinates for UI events

    client_timestamp TIMESTAMPTZ,
    server_timestamp TIMESTAMPTZ DEFAULT NOW(),

    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (server_timestamp);

CREATE TABLE user_interaction_events_y2024m01 PARTITION OF user_interaction_events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE INDEX idx_interaction_events_user ON user_interaction_events(user_id, server_timestamp DESC);
CREATE INDEX idx_interaction_events_session ON user_interaction_events(session_id, server_timestamp DESC);
CREATE INDEX idx_interaction_events_type ON user_interaction_events(event_type, server_timestamp DESC);
CREATE INDEX idx_interaction_events_component ON user_interaction_events(component, server_timestamp DESC);

-- User analytics aggregation
CREATE TABLE user_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL REFERENCES users(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),

    date_trunc_date DATE NOT NULL,

    -- Daily activity
    queries_count INTEGER DEFAULT 0,
    documents_viewed INTEGER DEFAULT 0,
    documents_downloaded INTEGER DEFAULT 0,
    clicks_count INTEGER DEFAULT 0,
    session_duration_seconds INTEGER DEFAULT 0,

    -- Quality metrics
    avg_query_time_ms DECIMAL(8,2),
    avg_satisfaction_score DECIMAL(3,2),
    bounce_rate DECIMAL(5,4),

    -- Feature usage
    features_used JSONB DEFAULT '{}',
    search_types_used JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, date_trunc_date)
);

CREATE INDEX idx_user_analytics_user ON user_analytics(user_id, date_trunc_date DESC);
CREATE INDEX idx_user_analytics_org ON user_analytics(organization_id, date_trunc_date DESC);
```

## 3. Indexing Strategy

### 3.1 Time-Series Data Optimization

```sql
-- Time-series indexes for efficient querying
CREATE INDEX CONCURRENTLY idx_search_queries_time_gin
ON search_queries USING GIN (created_at)
WHERE created_at >= NOW() - INTERVAL '30 days';

-- Composite indexes for common query patterns
CREATE INDEX CONCURRENTLY idx_evaluation_runs_composite
ON evaluation_runs (organization_id, evaluation_type, created_at DESC, overall_score);

CREATE INDEX CONCURRENTLY idx_performance_logs_composite
ON performance_logs (metric_category, organization_id, date_day DESC, value);

-- Partial indexes for recent data
CREATE INDEX CONCURRENTLY idx_search_queries_recent
ON search_queries (user_id, created_at DESC)
WHERE created_at >= NOW() - INTERVAL '7 days';

CREATE INDEX CONCURRENTLY idx_performance_logs_recent
ON performance_logs (component, timestamp DESC)
WHERE timestamp >= NOW() - INTERVAL '24 hours';
```

### 3.2 JSON Metadata Indexing

```sql
-- GIN indexes for JSONB columns
CREATE INDEX CONCURRENTLY idx_search_queries_metadata_gin
ON search_queries USING GIN (query_metadata);

CREATE INDEX CONCURRENTLY idx_document_analytics_metadata_gin
ON document_analytics USING GIN (file_metadata);

CREATE INDEX CONCURRENTLY idx_performance_logs_tags_gin
ON performance_logs USING GIN (tags);

-- JSONB path expressions for specific fields
CREATE INDEX CONCURRENTLY idx_search_queries_query_vector_gin
ON search_queries USING GIN ((query_metadata->'vector_config'));

CREATE INDEX CONCURRENTLY idx_evaluation_runs_config_gin
ON evaluation_runs USING GIN (evaluation_config);
```

### 3.3 Full-Text Search Indexes

```sql
-- Full-text search indexes
CREATE INDEX CONCURRENTLY idx_search_queries_text_fts
ON search_queries USING GIN (to_tsvector('english', query_text));

CREATE INDEX CONCURRENTLY idx_error_logs_message_fts
ON error_logs USING GIN (to_tsvector('english', error_message));

-- Trigram indexes for fuzzy matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY idx_search_queries_text_trgm
ON search_queries USING GIN (query_text gin_trgm_ops);

CREATE INDEX CONCURRENTLY idx_users_email_trgm
ON users USING GIN (email gin_trgm_ops);
```

## 4. Data Retention and Archiving Strategy

### 4.1 Partitioning Configuration

```sql
-- Enable automatic partition management
CREATE EXTENSION IF NOT EXISTS pg_partman;

-- Configure partition management for time-series tables
SELECT partman.run_maintenance();

-- Set retention policies
ALTER TABLE search_queries
SET (autovacuum_vacuum_scale_factor = 0.1,
     autovacuum_analyze_scale_factor = 0.05);

ALTER TABLE performance_logs
SET (autovacuum_vacuum_scale_factor = 0.05,
     autovacuum_analyze_scale_factor = 0.02);
```

### 4.2 Archive Tables

```sql
-- Archive tables for long-term storage
CREATE TABLE search_queries_archive (
    LIKE search_queries INCLUDING ALL
) PARTITION BY RANGE (created_at);

CREATE TABLE evaluation_runs_archive (
    LIKE evaluation_runs INCLUDING ALL
) PARTITION BY RANGE (created_at);

-- Archive older partitions
CREATE OR REPLACE FUNCTION archive_old_data()
RETURNS void AS $$
DECLARE
    cutoff_date DATE := CURRENT_DATE - INTERVAL '2 years';
BEGIN
    -- Archive search queries
    EXECUTE format('ALTER TABLE search_queries DETACH PARTITION search_queries_%s',
                   to_char(cutoff_date, 'YYYY"m"MM'));

    -- Archive evaluation runs
    EXECUTE format('ALTER TABLE evaluation_runs DETACH PARTITION evaluation_runs_%s',
                   to_char(cutoff_date, 'YYYY"m"MM'));

    -- Move to archive schema
    EXECUTE 'ALTER TABLE search_queries_' || to_char(cutoff_date, 'YYYY"m"MM') ||
            ' SET SCHEMA archive';
    EXECUTE 'ALTER TABLE evaluation_runs_' || to_char(cutoff_date, 'YYYY"m"MM') ||
            ' SET SCHEMA archive';
END;
$$ LANGUAGE plpgsql;
```

## 5. Sample SQL Queries for Key Analytics Use Cases

### 5.1 RAG Triad Performance Analysis

```sql
-- RAG Triad metrics dashboard query
WITH rag_metrics AS (
    SELECT
        DATE_TRUNC('day', er.created_at) as date,
        AVG(er.answer_relevancy_score) as avg_answer_relevancy,
        AVG(er.faithfulness_score) as avg_faithfulness,
        AVG(er.contextual_relevancy_score) as avg_contextual_relevancy,
        AVG(er.overall_score) as avg_overall_score,
        COUNT(*) as evaluation_count,
        COUNT(CASE WHEN er.meets_thresholds THEN 1 END) as passing_evaluations,
        o.name as organization_name
    FROM evaluation_runs er
    JOIN organizations o ON er.organization_id = o.id
    WHERE er.created_at >= CURRENT_DATE - INTERVAL '30 days'
      AND er.evaluation_type = 'rag_triad'
    GROUP BY DATE_TRUNC('day', er.created_at), o.name
)
SELECT
    date,
    organization_name,
    ROUND(avg_answer_relevancy::numeric, 4) as answer_relevancy,
    ROUND(avg_faithfulness::numeric, 4) as faithfulness,
    ROUND(avg_contextual_relevancy::numeric, 4) as contextual_relevancy,
    ROUND(avg_overall_score::numeric, 4) as overall_score,
    evaluation_count,
    ROUND((passing_evaluations::decimal / evaluation_count) * 100, 2) as pass_rate_percent
FROM rag_metrics
ORDER BY date DESC, organization_name;

-- Trend analysis for RAG metrics
SELECT
    metric_name,
    DATE_TRUNC('week', created_at) as week,
    AVG(metric_value) as avg_value,
    STDDEV(metric_value) as stddev_value,
    COUNT(*) as sample_count,
    (AVG(metric_value) - LAG(AVG(metric_value)) OVER (PARTITION BY metric_name ORDER BY DATE_TRUNC('week', created_at))) /
    LAG(AVG(metric_value)) OVER (PARTITION BY metric_name ORDER BY DATE_TRUNC('week', created_at)) * 100 as trend_percentage
FROM (
    SELECT 'answer_relevancy' as metric_name, answer_relevancy_score as metric_value, created_at
    FROM evaluation_runs WHERE answer_relevancy_score IS NOT NULL
    UNION ALL
    SELECT 'faithfulness' as metric_name, faithfulness_score as metric_value, created_at
    FROM evaluation_runs WHERE faithfulness_score IS NOT NULL
    UNION ALL
    SELECT 'contextual_relevancy' as metric_name, contextual_relevancy_score as metric_value, created_at
    FROM evaluation_runs WHERE contextual_relevancy_score IS NOT NULL
) metrics
WHERE created_at >= CURRENT_DATE - INTERVAL '12 weeks'
GROUP BY metric_name, DATE_TRUNC('week', created_at)
ORDER BY metric_name, week DESC;
```

### 5.2 Performance Monitoring Queries

```sql
-- System performance dashboard
SELECT
    DATE_TRUNC('hour', timestamp) as hour,
    metric_category,
    component,
    AVG(value) as avg_metric_value,
    MIN(value) as min_metric_value,
    MAX(value) as max_metric_value,
    STDDEV(value) as stddev_value,
    COUNT(*) as measurement_count,
    COUNT(CASE WHEN alert_triggered THEN 1 END) as alert_count
FROM performance_logs
WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
  AND performance_level IN ('poor', 'critical')
GROUP BY DATE_TRUNC('hour', timestamp), metric_category, component
ORDER BY hour DESC, avg_metric_value DESC;

-- Resource utilization trends
SELECT
    DATE_TRUNC('hour', timestamp) as hour,
    AVG(cpu_usage_percent) as avg_cpu_usage,
    MAX(cpu_usage_percent) as max_cpu_usage,
    AVG(memory_usage_percent) as avg_memory_usage,
    MAX(memory_usage_percent) as max_memory_usage,
    AVG(response_time_ms) as avg_response_time,
    MAX(response_time_ms) as max_response_time,
    COUNT(CASE WHEN alert_triggered THEN 1 END) as alert_count
FROM performance_logs
WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
  AND metric_category = 'system'
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY hour DESC;

-- Database performance analysis
SELECT
    DATE_TRUNC('hour', timestamp) as hour,
    AVG(db_query_time_ms) as avg_query_time,
    MAX(db_query_time_ms) as max_query_time,
    AVG(db_cache_hit_rate) as avg_cache_hit_rate,
    SUM(db_slow_queries) as total_slow_queries,
    AVG(db_connections) as avg_connections,
    MAX(db_connections) as max_connections
FROM performance_logs
WHERE timestamp >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
  AND metric_category = 'database'
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY hour DESC;
```

### 5.3 A/B Testing Analytics

```sql
-- A/B test results analysis
WITH test_results AS (
    SELECT
        e.id as experiment_id,
        e.name as experiment_name,
        v.id as variant_id,
        v.name as variant_name,
        v.is_control,
        COUNT(a.id) as participant_count,
        COUNT(DISTINCT a.user_id) as unique_users,
        COUNT(q.id) as total_queries,
        AVG(q.query_time_ms) as avg_response_time,
        AVG(q.user_satisfaction_score) as avg_satisfaction,
        SUM(CASE WHEN q.clicked_result_ids IS NOT NULL AND json_array_length(q.clicked_result_ids) > 0 THEN 1 ELSE 0 END)::float /
        NULLIF(COUNT(q.id), 0) as click_through_rate,
        v.primary_metric_value,
        v.confidence_interval_lower,
        v.confidence_interval_upper
    FROM ab_experiments e
    JOIN ab_variants v ON e.id = v.experiment_id
    LEFT JOIN ab_assignments a ON v.id = a.variant_id
    LEFT JOIN search_queries q ON a.session_id = q.session_id AND q.experiment_id = e.id
    WHERE e.status = 'completed'
      AND e.created_at >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY e.id, e.name, v.id, v.name, v.is_control, v.primary_metric_value,
             v.confidence_interval_lower, v.confidence_interval_upper
)
SELECT
    experiment_name,
    variant_name,
    is_control,
    participant_count,
    unique_users,
    total_queries,
    ROUND(avg_response_time::numeric, 2) as avg_response_time_ms,
    ROUND(avg_satisfaction::numeric, 2) as avg_satisfaction_score,
    ROUND(click_through_rate::numeric, 4) as click_through_rate,
    ROUND(primary_metric_value::numeric, 4) as primary_metric,
    ROUND(confidence_interval_lower::numeric, 4) as ci_lower,
    ROUND(confidence_interval_upper::numeric, 4) as ci_upper
FROM test_results
ORDER BY experiment_name, is_control DESC, primary_metric_value DESC;

-- Statistical significance calculation
SELECT
    e.name as experiment_name,
    control.name as control_variant,
    treatment.name as treatment_variant,
    control.primary_metric_value as control_value,
    treatment.primary_metric_value as treatment_value,
    ROUND((treatment.primary_metric_value - control.primary_metric_value) /
          NULLIF(control.primary_metric_value, 0) * 100, 2) as relative_improvement_percent,
    treatment.p_value,
    treatment.confidence_interval_lower,
    treatment.confidence_interval_upper,
    CASE
        WHEN treatment.p_value < 0.05 THEN 'Statistically Significant'
        ELSE 'Not Significant'
    END as significance_status
FROM ab_experiments e
JOIN ab_variants control ON e.id = control.experiment_id AND control.is_control = true
JOIN ab_variants treatment ON e.id = treatment.experiment_id AND treatment.is_control = false
WHERE e.status = 'completed'
  AND treatment.p_value IS NOT NULL
ORDER BY relative_improvement_percent DESC;
```

### 5.4 User Behavior Analytics

```sql
-- User engagement analysis
WITH user_activity AS (
    SELECT
        u.id as user_id,
        u.full_name,
        u.organization_id,
        o.name as organization_name,
        COUNT(DISTINCT DATE_TRUNC('day', sq.created_at)) as active_days,
        COUNT(sq.id) as total_queries,
        AVG(sq.query_time_ms) as avg_query_time,
        AVG(sq.user_satisfaction_score) as avg_satisfaction,
        COUNT(DISTINCT sq.session_id) as total_sessions,
        MAX(sq.created_at) as last_query_date,
        COUNT(CASE WHEN sq.clicked_result_ids IS NOT NULL THEN 1 END) as queries_with_clicks,
        SUM(CASE WHEN sq.clicked_result_ids IS NOT NULL THEN json_array_length(sq.clicked_result_ids) ELSE 0 END) as total_clicks
    FROM users u
    JOIN organizations o ON u.organization_id = o.id
    LEFT JOIN search_queries sq ON u.id = sq.user_id
        AND sq.created_at >= CURRENT_DATE - INTERVAL '30 days'
    WHERE u.is_deleted = false
    GROUP BY u.id, u.full_name, u.organization_id, o.name
)
SELECT
    organization_name,
    full_name,
    active_days,
    total_queries,
    total_sessions,
    ROUND(avg_query_time::numeric, 2) as avg_response_time_ms,
    ROUND(avg_satisfaction::numeric, 2) as avg_satisfaction_score,
    ROUND(total_clicks::decimal / NULLIF(total_queries, 0), 2) as clicks_per_query,
    ROUND(total_queries::decimal / NULLIF(active_days, 0), 2) as queries_per_day,
    CASE
        WHEN last_query_date >= CURRENT_DATE - INTERVAL '7 days' THEN 'Active'
        WHEN last_query_date >= CURRENT_DATE - INTERVAL '14 days' THEN 'Moderately Active'
        WHEN last_query_date >= CURRENT_DATE - INTERVAL '30 days' THEN 'Less Active'
        ELSE 'Inactive'
    END as activity_status
FROM user_activity
WHERE total_queries > 0
ORDER BY total_queries DESC, organization_name;

-- Feature usage analysis
SELECT
    event_type,
    event_action,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(*) as total_events,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM user_interaction_events
                              WHERE server_timestamp >= CURRENT_DATE - INTERVAL '30 days'), 2) as usage_percentage
FROM user_interaction_events
WHERE server_timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY event_type, event_action
ORDER BY total_events DESC;

-- Search pattern analysis
SELECT
    DATE_TRUNC('hour', created_at) as hour,
    query_type,
    COUNT(*) as query_count,
    AVG(query_time_ms) as avg_response_time,
    AVG(result_count) as avg_results,
    COUNT(CASE WHEN clicked_result_ids IS NOT NULL THEN 1 END)::float / COUNT(*) as click_rate
FROM search_queries
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE_TRUNC('hour', created_at), query_type
ORDER BY hour DESC, query_count DESC;
```

### 5.5 Document Performance Analytics

```sql
-- Document quality and performance metrics
SELECT
    DATE_TRUNC('day', da.created_at) as date,
    processing_status,
    COUNT(*) as document_count,
    AVG(processing_time_ms) as avg_processing_time,
    AVG(quality_score) as avg_quality_score,
    AVG(extraction_confidence) as avg_confidence,
    SUM(file_size_bytes) as total_size_mb
FROM document_analytics da
WHERE da.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', da.created_at), processing_status
ORDER BY date DESC, processing_status;

-- Most accessed documents
SELECT
    sq.document_id,
    COUNT(DISTINCT sq.user_id) as unique_users,
    COUNT(*) as total_views,
    AVG(sq.query_time_ms) as avg_response_time,
    AVG(sq.user_satisfaction_score) as avg_satisfaction,
    MAX(sq.created_at) as last_accessed,
    da.file_metadata
FROM search_queries sq
JOIN document_analytics da ON sq.document_id = da.document_id
WHERE sq.created_at >= CURRENT_DATE - INTERVAL '30 days'
  AND sq.document_id IS NOT NULL
GROUP BY sq.document_id, da.file_metadata
ORDER BY total_views DESC
LIMIT 50;

-- Document correlation with search quality
WITH document_performance AS (
    SELECT
        sq.document_id,
        AVG(sq.query_time_ms) as avg_query_time,
        AVG(sq.user_satisfaction_score) as avg_satisfaction,
        COUNT(*) as query_count,
        COUNT(CASE WHEN sq.clicked_result_ids IS NOT NULL THEN 1 END) as click_count
    FROM search_queries sq
    WHERE sq.created_at >= CURRENT_DATE - INTERVAL '30 days'
      AND sq.document_id IS NOT NULL
    GROUP BY sq.document_id
)
SELECT
    dp.document_id,
    da.quality_score,
    da.processing_status,
    dp.avg_query_time,
    dp.avg_satisfaction,
    dp.query_count,
    ROUND(dp.click_count::decimal / NULLIF(dp.query_count, 0), 4) as click_rate
FROM document_performance dp
JOIN document_analytics da ON dp.document_id = da.document_id
ORDER BY da.quality_score DESC NULLS LAST, dp.avg_satisfaction DESC NULLS LAST;
```

This comprehensive database schema design provides:

1. **Scalable time-series data handling** through partitioning and efficient indexing
2. **Comprehensive RAG Triad evaluation** tracking with detailed metrics
3. **A/B testing framework** with statistical analysis capabilities
4. **Performance monitoring** for system health and optimization
5. **User analytics** for understanding usage patterns and improving UX
6. **Data retention policies** and archiving strategies
7. **Optimized queries** for common analytics use cases

The schema is designed to complement the existing Neo4j knowledge graphs and Qdrant vector storage, providing the analytics backbone for a production-ready multimodal RAG system.