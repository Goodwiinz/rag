# Comprehensive Database Schema for Production Monitoring and Observability
# Multimodal Enterprise RAG System

-- =============================================
-- SLI/SLO Monitoring Schema
-- =============================================

-- Service Level Indicators (SLIs) table
CREATE TABLE IF NOT EXISTS service_level_indicators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sli_name VARCHAR(255) NOT NULL,
    sli_category VARCHAR(100) NOT NULL, -- 'availability', 'latency', 'throughput', 'error_rate', 'quality'
    description TEXT,
    organization_id UUID REFERENCES organizations(id),

    -- SLI configuration
    metric_source VARCHAR(100) NOT NULL, -- 'prometheus', 'application_logs', 'user_feedback', 'synthetic_tests'
    metric_query JSONB NOT NULL, -- Query/metric definition
    aggregation_window_minutes INTEGER NOT NULL DEFAULT 5,
    aggregation_function VARCHAR(50) NOT NULL DEFAULT 'avg', -- 'avg', 'p95', 'p99', 'sum', 'rate'

    -- SLO targets
    slo_target_percentile FLOAT NOT NULL, -- e.g., 99.5 for 99.5%
    slo_target_value FLOAT NOT NULL, -- Target value
    slo_target_unit VARCHAR(50) NOT NULL, -- 'ms', '%', 'requests/sec'
    slo_period_days INTEGER NOT NULL DEFAULT 30, -- Rolling period for SLO calculation

    -- Alerting configuration
    alert_burn_rate_threshold FLOAT DEFAULT 2.0, -- Multi-burn rate alerting
    alert_notification_channels JSONB, -- Slack, email, pagerduty configs

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,

    CONSTRAINT chk_sli_category CHECK (sli_category IN ('availability', 'latency', 'throughput', 'error_rate', 'quality', 'business')),
    CONSTRAINT chk_aggregation_function CHECK (aggregation_function IN ('avg', 'p95', 'p99', 'p999', 'sum', 'rate', 'count'))
);

-- SLI measurements with time-series optimization
CREATE TABLE IF NOT EXISTS sli_measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sli_id UUID NOT NULL REFERENCES service_level_indicators(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id),

    -- Measurement data
    measurement_time TIMESTAMP WITH TIME ZONE NOT NULL,
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end TIMESTAMP WITH TIME ZONE NOT NULL,
    measurement_value FLOAT NOT NULL,
    measurement_unit VARCHAR(50),

    -- SLI status
    meets_slo BOOLEAN NOT NULL,
    slo_budget_consumed FLOAT NOT NULL, -- Percentage of monthly budget consumed
    slo_budget_remaining FLOAT NOT NULL, -- Percentage of monthly budget remaining

    -- Data quality
    sample_size INTEGER NOT NULL,
    data_quality_score FLOAT CHECK (data_quality_score >= 0 AND data_quality_score <= 1),

    -- Context
    environment VARCHAR(50) DEFAULT 'production',
    region VARCHAR(50),
    node_id VARCHAR(100),

    -- Time partitioning fields
    measurement_date DATE NOT NULL GENERATED ALWAYS AS (DATE(measurement_time)) STORED,
    measurement_hour INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(HOUR FROM measurement_time)) STORED,
    measurement_month INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(MONTH FROM measurement_time)) STORED,
    measurement_year INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(YEAR FROM measurement_time)) STORED,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    batch_id VARCHAR(100),

    CONSTRAINT chk_measurement_window CHECK (window_end > window_start),
    CONSTRAINT chk_budget_ranges CHECK (
        slo_budget_consumed >= 0 AND slo_budget_consumed <= 100 AND
        slo_budget_remaining >= 0 AND slo_budget_remaining <= 100
    )
);

-- SLO breach events for detailed analysis
CREATE TABLE IF NOT EXISTS slo_breach_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sli_id UUID NOT NULL REFERENCES service_level_indicators(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id),

    -- Breach details
    breach_start TIMESTAMP WITH TIME ZONE NOT NULL,
    breach_end TIMESTAMP WITH TIME ZONE,
    breach_duration_minutes INTEGER,
    breach_severity VARCHAR(50) NOT NULL, -- 'minor', 'major', 'critical'
    sli_value_before_breach FLOAT,
    sli_value_during_breach FLOAT NOT NULL,
    slo_target_value FLOAT NOT NULL,

    -- Impact analysis
    affected_users_count INTEGER DEFAULT 0,
    affected_requests_count INTEGER DEFAULT 0,
    business_impact_score FLOAT CHECK (business_impact_score >= 0 AND business_impact_score <= 10),
    revenue_impact_estimate DECIMAL(12,2),

    -- Root cause analysis
    root_cause_category VARCHAR(100), -- 'infrastructure', 'application', 'third_party', 'network'
    root_cause_details TEXT,
    contributing_factors JSONB,

    -- Resolution
    resolution_status VARCHAR(50) DEFAULT 'open', -- 'open', 'investigating', 'resolved', 'post_mortem'
    resolution_actions JSONB,
    post_mortem_url VARCHAR(500),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_breach_severity CHECK (breach_severity IN ('minor', 'major', 'critical')),
    CONSTRAINT chk_resolution_status CHECK (resolution_status IN ('open', 'investigating', 'resolved', 'post_mortem'))
);

-- =============================================
-- Performance Monitoring Schema
-- =============================================

-- Application performance metrics with high-cardinality optimization
CREATE TABLE IF NOT EXISTS performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Metric identification
    metric_name VARCHAR(255) NOT NULL,
    metric_category VARCHAR(100) NOT NULL,
    component_name VARCHAR(255) NOT NULL, -- Service, endpoint, or component name
    organization_id UUID REFERENCES organizations(id),

    -- Measurement data
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    value FLOAT NOT NULL,
    unit VARCHAR(50),

    -- Performance percentiles (for aggregated data)
    p50 FLOAT,
    p90 FLOAT,
    p95 FLOAT,
    p99 FLOAT,
    p999 FLOAT,
    min_value FLOAT,
    max_value FLOAT,
    std_deviation FLOAT,

    -- Request/response data
    request_count INTEGER DEFAULT 1,
    error_count INTEGER DEFAULT 0,
    total_request_size_bytes BIGINT,
    total_response_size_bytes BIGINT,

    -- System context
    environment VARCHAR(50) DEFAULT 'production',
    node_id VARCHAR(100),
    pod_name VARCHAR(255),
    deployment_version VARCHAR(100),

    -- High-cardinality tags (JSONB for flexibility)
    tags JSONB,
    trace_id VARCHAR(255),
    span_id VARCHAR(255),

    -- Time partitioning fields
    metric_date DATE NOT NULL GENERATED ALWAYS AS (DATE(timestamp)) STORED,
    metric_hour INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(HOUR FROM timestamp)) STORED,

    -- Processing metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    batch_id VARCHAR(100),
    processed BOOLEAN DEFAULT FALSE,

    CONSTRAINT chk_metric_category CHECK (metric_category IN (
        'api', 'database', 'cache', 'search', 'ml_inference', 'file_processing',
        'external_service', 'queue', 'storage', 'network', 'system'
    ))
);

-- Database performance metrics
CREATE TABLE IF NOT EXISTS database_performance_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Database identification
    database_type VARCHAR(50) NOT NULL, -- 'postgresql', 'neo4j', 'qdrant', 'redis'
    database_instance VARCHAR(255) NOT NULL,
    organization_id UUID REFERENCES organizations(id),

    -- Connection metrics
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    active_connections INTEGER,
    idle_connections INTEGER,
    max_connections INTEGER,
    connection_utilization_percent FLOAT,

    -- Query performance
    queries_per_second FLOAT,
    slow_queries_count INTEGER DEFAULT 0,
    avg_query_time_ms FLOAT,
    p95_query_time_ms FLOAT,
    p99_query_time_ms FLOAT,

    -- Resource usage
    cpu_usage_percent FLOAT,
    memory_usage_bytes BIGINT,
    memory_usage_percent FLOAT,
    disk_usage_bytes BIGINT,
    disk_usage_percent FLOAT,
    disk_io_read_mb_per_sec FLOAT,
    disk_io_write_mb_per_sec FLOAT,

    -- Database-specific metrics (JSONB for flexibility)
    database_metrics JSONB,

    -- Time partitioning
    metric_date DATE NOT NULL GENERATED ALWAYS AS (DATE(timestamp)) STORED,
    metric_hour INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(HOUR FROM timestamp)) STORED,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Resource utilization metrics
CREATE TABLE IF NOT EXISTS resource_utilization_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Resource identification
    resource_type VARCHAR(50) NOT NULL, -- 'container', 'pod', 'vm', 'server'
    resource_id VARCHAR(255) NOT NULL,
    resource_name VARCHAR(255),
    organization_id UUID REFERENCES organizations(id),

    -- Measurement timestamp
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,

    -- CPU metrics
    cpu_usage_cores FLOAT,
    cpu_usage_percent FLOAT,
    cpu_limit_cores FLOAT,
    cpu_request_cores FLOAT,

    -- Memory metrics
    memory_usage_bytes BIGINT,
    memory_usage_percent FLOAT,
    memory_limit_bytes BIGINT,
    memory_request_bytes BIGINT,
    memory_cache_bytes BIGINT,

    -- Storage metrics
    disk_usage_bytes BIGINT,
    disk_usage_percent FLOAT,
    disk_io_reads_per_sec FLOAT,
    disk_io_writes_per_sec FLOAT,
    disk_read_bytes_per_sec BIGINT,
    disk_write_bytes_per_sec BIGINT,

    -- Network metrics
    network_rx_bytes_per_sec BIGINT,
    network_tx_bytes_per_sec BIGINT,
    network_rx_packets_per_sec FLOAT,
    network_tx_packets_per_sec FLOAT,
    network_connections_active INTEGER,

    -- GPU metrics (if applicable)
    gpu_usage_percent FLOAT,
    gpu_memory_usage_bytes BIGINT,
    gpu_memory_usage_percent FLOAT,
    gpu_utilization FLOAT,

    -- Metadata
    environment VARCHAR(50) DEFAULT 'production',
    node_name VARCHAR(255),
    namespace VARCHAR(255),
    labels JSONB,

    -- Time partitioning
    metric_date DATE NOT NULL GENERATED ALWAYS AS (DATE(timestamp)) STORED,
    metric_hour INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(HOUR FROM timestamp)) STORED,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- User Analytics and Session Management
-- =============================================

-- Enhanced user sessions with detailed tracking
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID REFERENCES organizations(id) NOT NULL,

    -- Session identification
    session_id VARCHAR(255) NOT NULL UNIQUE,
    session_token_hash VARCHAR(255), -- Hashed session token

    -- Session timing
    session_start TIMESTAMP WITH TIME ZONE NOT NULL,
    session_end TIMESTAMP WITH TIME ZONE,
    session_duration_seconds INTEGER,
    last_activity TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Session status
    session_status VARCHAR(50) NOT NULL DEFAULT 'active', -- 'active', 'expired', 'terminated', 'invalidated'
    termination_reason VARCHAR(100), -- 'logout', 'timeout', 'admin_action', 'security'

    -- Client information
    user_agent TEXT,
    ip_address INET,
    country VARCHAR(2),
    city VARCHAR(100),
    device_type VARCHAR(50), -- 'desktop', 'mobile', 'tablet', 'api_client'
    browser VARCHAR(100),
    os VARCHAR(100),

    -- Access method
    authentication_method VARCHAR(50), -- 'password', 'sso', 'api_key', 'oauth'
    mfa_verified BOOLEAN DEFAULT FALSE,

    -- Activity summary
    pages_viewed INTEGER DEFAULT 0,
    searches_performed INTEGER DEFAULT 0,
    documents_viewed INTEGER DEFAULT 0,
    api_requests_made INTEGER DEFAULT 0,
    data_uploaded_mb FLOAT DEFAULT 0,
    data_downloaded_mb FLOAT DEFAULT 0,

    -- Security metrics
    security_flags JSONB, -- Suspicious activities, security events
    risk_score FLOAT CHECK (risk_score >= 0 AND risk_score <= 100),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_session_status CHECK (session_status IN ('active', 'expired', 'terminated', 'invalidated'))
);

-- User activity events with time-series optimization
CREATE TABLE IF NOT EXISTS user_activity_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    organization_id UUID REFERENCES organizations(id) NOT NULL,
    session_id VARCHAR(255) NOT NULL,

    -- Event classification
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(100) NOT NULL,
    event_action VARCHAR(255) NOT NULL,
    event_description TEXT,

    -- Event timing
    event_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    event_duration_ms INTEGER,

    -- Event context
    page_url TEXT,
    api_endpoint VARCHAR(500),
    referrer_url TEXT,

    -- Event data (structured)
    event_properties JSONB,
    request_payload JSONB,
    response_payload JSONB,

    -- Performance metrics
    response_time_ms INTEGER,
    database_query_time_ms INTEGER,
    external_service_time_ms INTEGER,

    -- Business metrics
    business_value FLOAT, -- Business value score for this activity
    conversion_step VARCHAR(100), -- Where in conversion funnel

    -- Technical details
    user_agent TEXT,
    ip_address INET,
    device_fingerprint VARCHAR(255),

    -- Time partitioning
    event_date DATE NOT NULL GENERATED ALWAYS AS (DATE(event_timestamp)) STORED,
    event_hour INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(HOUR FROM event_timestamp)) STORED,

    -- Processing metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    batch_id VARCHAR(100),

    CONSTRAINT chk_event_category CHECK (event_category IN (
        'search', 'document', 'upload', 'download', 'view', 'interaction',
        'api', 'authentication', 'error', 'performance'
    ))
);

-- Feature usage tracking
CREATE TABLE IF NOT EXISTS feature_usage_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Feature identification
    feature_name VARCHAR(255) NOT NULL,
    feature_category VARCHAR(100) NOT NULL,
    feature_version VARCHAR(50),

    -- Usage timing
    usage_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    usage_duration_seconds INTEGER,

    -- Usage context
    usage_context JSONB, -- Context of feature usage
    feature_parameters JSONB, -- Parameters used with feature

    -- User interaction
    user_satisfaction_score INTEGER CHECK (user_satisfaction_score >= 1 AND user_satisfaction_score <= 5),
    user_feedback TEXT,

    -- Performance metrics
    feature_response_time_ms INTEGER,
    feature_error_occurred BOOLEAN DEFAULT FALSE,
    feature_error_message TEXT,

    -- Business impact
    business_outcome JSONB, -- Business results from feature usage
    revenue_impact DECIMAL(10,2),

    -- A/B testing context
    experiment_id VARCHAR(255),
    variant_name VARCHAR(100),
    is_control_group BOOLEAN DEFAULT FALSE,

    -- Time partitioning
    usage_date DATE NOT NULL GENERATED ALWAYS AS (DATE(usage_timestamp)) STORED,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- System Health and Status Monitoring
-- =============================================

-- Service health status with dependency tracking
CREATE TABLE IF NOT EXISTS service_health_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Service identification
    service_name VARCHAR(255) NOT NULL,
    service_type VARCHAR(100) NOT NULL, -- 'api', 'database', 'queue', 'cache', 'external'
    service_instance VARCHAR(255), -- Specific instance ID
    organization_id UUID REFERENCES organizations(id),

    -- Health status
    health_status VARCHAR(50) NOT NULL, -- 'healthy', 'degraded', 'unhealthy', 'unknown'
    status_reason VARCHAR(500),
    health_score FLOAT CHECK (health_score >= 0 AND health_score <= 100),

    -- Health check details
    check_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    check_duration_ms INTEGER,
    check_type VARCHAR(100), -- 'http', 'tcp', 'database_query', 'custom'
    check_url VARCHAR(500),
    check_status_code INTEGER,

    -- Dependencies
    dependencies JSONB, -- List of service dependencies
    dependency_status JSONB, -- Status of each dependency

    -- Performance metrics
    response_time_ms INTEGER,
    cpu_usage_percent FLOAT,
    memory_usage_percent FLOAT,
    error_rate_percent FLOAT,

    -- Metrics during health check
    active_connections INTEGER,
    queue_depth INTEGER,
    cache_hit_rate FLOAT,

    -- Environment context
    environment VARCHAR(50) DEFAULT 'production',
    region VARCHAR(50),
    availability_zone VARCHAR(50),
    node_id VARCHAR(100),

    -- Alerting
    alert_triggered BOOLEAN DEFAULT FALSE,
    alert_severity VARCHAR(50), -- 'info', 'warning', 'critical'
    last_alert_sent TIMESTAMP WITH TIME ZONE,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    first_failure_timestamp TIMESTAMP WITH TIME ZONE,
    failure_duration_minutes INTEGER,

    CONSTRAINT chk_health_status CHECK (health_status IN ('healthy', 'degraded', 'unhealthy', 'unknown')),
    CONSTRAINT chk_alert_severity CHECK (alert_severity IN ('info', 'warning', 'critical'))
);

-- System alerts and incidents
CREATE TABLE IF NOT EXISTS system_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Alert identification
    alert_name VARCHAR(255) NOT NULL,
    alert_type VARCHAR(100) NOT NULL, -- 'performance', 'availability', 'security', 'capacity'
    alert_severity VARCHAR(50) NOT NULL, -- 'info', 'warning', 'error', 'critical'
    organization_id UUID REFERENCES organizations(id),

    -- Alert timing
    triggered_at TIMESTAMP WITH TIME ZONE NOT NULL,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,

    -- Alert status
    alert_status VARCHAR(50) NOT NULL DEFAULT 'open', -- 'open', 'acknowledged', 'resolved', 'suppressed'

    -- Alert details
    alert_description TEXT,
    alert_details JSONB, -- Detailed alert data
    affected_services JSONB, -- List of affected services
    affected_components JSONB, -- List of affected components

    -- Metrics that triggered the alert
    metric_name VARCHAR(255),
    metric_value FLOAT,
    threshold_value FLOAT,
    threshold_operator VARCHAR(10),

    -- Impact assessment
    business_impact VARCHAR(500),
    affected_users_count INTEGER DEFAULT 0,
    estimated_revenue_impact DECIMAL(12,2),

    -- Response
    assigned_to VARCHAR(255), -- User or team assigned
    response_actions JSONB, -- Actions taken to resolve
    resolution_summary TEXT,

    -- Communication
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_channels JSONB, -- Channels used for notification
    stakeholders_notified JSONB,

    -- Post-incident analysis
    post_mortem_required BOOLEAN DEFAULT FALSE,
    post_mortem_completed BOOLEAN DEFAULT FALSE,
    post_mortem_url VARCHAR(500),
    lessons_learned TEXT,

    -- Prevention
    prevention_measures JSONB, -- Measures to prevent recurrence
    monitoring_improvements JSONB,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_alert_severity CHECK (alert_severity IN ('info', 'warning', 'error', 'critical')),
    CONSTRAINT chk_alert_status CHECK (alert_status IN ('open', 'acknowledged', 'resolved', 'suppressed'))
);

-- Queue and job monitoring
CREATE TABLE IF NOT EXISTS queue_monitoring_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Queue identification
    queue_name VARCHAR(255) NOT NULL,
    queue_type VARCHAR(100) NOT NULL, -- 'celery', 'redis', 'rabbitmq', 'sqs'
    service_name VARCHAR(255),
    organization_id UUID REFERENCES organizations(id),

    -- Measurement timestamp
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Queue metrics
    queue_depth INTEGER NOT NULL, -- Number of pending jobs
    queue_size_bytes BIGINT,

    -- Processing metrics
    workers_active INTEGER,
    workers_idle INTEGER,
    workers_total INTEGER,

    -- Throughput metrics
    jobs_processed_per_minute FLOAT,
    jobs_failed_per_minute FLOAT,
    jobs_successful_per_minute FLOAT,

    -- Performance metrics
    avg_processing_time_seconds FLOAT,
    p95_processing_time_seconds FLOAT,
    max_processing_time_seconds FLOAT,

    -- Error metrics
    error_rate_percent FLOAT,
    retry_count INTEGER,
    dead_letter_queue_size INTEGER,

    -- Resource usage
    memory_usage_mb FLOAT,
    cpu_usage_percent FLOAT,

    -- Queue-specific metrics (JSONB for flexibility)
    queue_metrics JSONB,

    -- Environment
    environment VARCHAR(50) DEFAULT 'production',
    node_id VARCHAR(100),

    -- Time partitioning
    metric_date DATE NOT NULL GENERATED ALWAYS AS (DATE(timestamp)) STORED,
    metric_hour INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(HOUR FROM timestamp)) STORED,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- Business and Quality Metrics
-- =============================================

-- Document processing metrics
CREATE TABLE IF NOT EXISTS document_processing_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Document identification
    document_id UUID,
    document_name VARCHAR(1000),
    document_type VARCHAR(100), -- 'pdf', 'image', 'audio', 'video', 'text'
    document_size_bytes BIGINT,
    file_extension VARCHAR(10),

    -- Processing timeline
    upload_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    processing_started TIMESTAMP WITH TIME ZONE,
    processing_completed TIMESTAMP WITH TIME ZONE,
    total_processing_time_seconds INTEGER,

    -- Processing stages with detailed timing
    upload_time_seconds INTEGER,
    validation_time_seconds INTEGER,
    ocr_time_seconds INTEGER,
    transcription_time_seconds INTEGER,
    embedding_time_seconds INTEGER,
    indexing_time_seconds INTEGER,
    quality_check_time_seconds INTEGER,

    -- Processing results
    processing_status VARCHAR(50) NOT NULL, -- 'success', 'failed', 'partial', 'timeout'
    failure_reason VARCHAR(500),
    failure_stage VARCHAR(100),
    retry_count INTEGER DEFAULT 0,

    -- Quality metrics
    ocr_quality_score FLOAT CHECK (ocr_quality_score >= 0 AND ocr_quality_score <= 1),
    transcription_quality_score FLOAT CHECK (transcription_quality_score >= 0 AND transcription_quality_score <= 1),
    overall_quality_score FLOAT CHECK (overall_quality_score >= 0 AND overall_quality_score <= 1),

    -- Extracted content metrics
    pages_processed INTEGER,
    text_extracted_chars INTEGER,
    entities_extracted INTEGER,
    metadata_extracted_fields INTEGER,

    -- Resource usage
    cpu_time_seconds FLOAT,
    memory_peak_mb FLOAT,
    gpu_time_seconds FLOAT,
    api_calls_made INTEGER,

    -- Cost tracking
    processing_cost_usd DECIMAL(10,4),
    storage_cost_usd_per_month DECIMAL(10,4),

    -- Environment
    processing_node VARCHAR(255),
    environment VARCHAR(50) DEFAULT 'production',

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    batch_id VARCHAR(100),

    CONSTRAINT chk_processing_status CHECK (processing_status IN ('success', 'failed', 'partial', 'timeout'))
);

-- Search quality metrics
CREATE TABLE IF NOT EXISTS search_quality_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id VARCHAR(255),

    -- Search identification
    search_id UUID,
    query_text TEXT NOT NULL,
    query_type VARCHAR(100), -- 'text', 'multimodal', 'hybrid'
    search_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Search execution metrics
    total_response_time_ms INTEGER,
    vector_search_time_ms INTEGER,
    graph_search_time_ms INTEGER,
    keyword_search_time_ms INTEGER,
    reranking_time_ms INTEGER,

    -- Search results
    total_results_count INTEGER,
    returned_results_count INTEGER,
    results_filtered_count INTEGER,

    -- Search quality scores
    relevance_score FLOAT CHECK (relevance_score >= 0 AND relevance_score <= 1),
    diversity_score FLOAT CHECK (diversity_score >= 0 AND diversity_score <= 1),
    freshness_score FLOAT CHECK (freshness_score >= 0 AND freshness_score <= 1),
    overall_quality_score FLOAT CHECK (overall_quality_score >= 0 AND overall_quality_score <= 1),

    -- User interaction metrics
    clicked_results INTEGER DEFAULT 0,
    clicked_result_positions JSONB, -- Array of clicked result positions
    time_to_first_click_ms INTEGER,
    session_search_position INTEGER, -- Position in user's search session

    -- User feedback
    user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),
    user_feedback TEXT,
    feedback_helpful BOOLEAN,

    -- Search context
    filters_applied JSONB,
    sort_order VARCHAR(100),
    search_scope VARCHAR(100), -- 'all', 'documents', 'images', etc.
    search_context JSONB,

    -- Performance metrics
    cache_hit BOOLEAN DEFAULT FALSE,
    cache_response_time_ms INTEGER,
    database_queries_count INTEGER,
    external_api_calls_count INTEGER,

    -- Business metrics
    conversion_event VARCHAR(100), -- Did this search lead to business outcome
    business_value DECIMAL(8,2),

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,

    -- Time partitioning
    search_date DATE NOT NULL GENERATED ALWAYS AS (DATE(search_timestamp)) STORED,
    search_hour INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(HOUR FROM search_timestamp)) STORED
);

-- RAG system quality metrics
CREATE TABLE IF NOT EXISTS rag_quality_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Query identification
    query_id UUID,
    query_text TEXT NOT NULL,
    query_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    query_type VARCHAR(100), -- 'factual', 'analytical', 'creative', 'multimodal'

    -- RAG pipeline metrics
    retrieval_time_ms INTEGER,
    context_preparation_time_ms INTEGER,
    generation_time_ms INTEGER,
    total_pipeline_time_ms INTEGER,

    -- Context quality
    retrieved_documents_count INTEGER,
    context_relevance_score FLOAT CHECK (context_relevance_score >= 0 AND context_relevance_score <= 1),
    context_completeness_score FLOAT CHECK (context_completeness_score >= 0 AND context_completeness_score <= 1),
    context_freshness_score FLOAT CHECK (context_freshness_score >= 0 AND context_freshness_score <= 1),

    -- Generation quality
    answer_relevance_score FLOAT CHECK (answer_relevance_score >= 0 AND answer_relevance_score <= 1),
    answer_accuracy_score FLOAT CHECK (answer_accuracy_score >= 0 AND answer_accuracy_score <= 1),
    answer_completeness_score FLOAT CHECK (answer_completeness_score >= 0 AND answer_completeness_score <= 1),
    faithfulness_score FLOAT CHECK (faithfulness_score >= 0 AND faithfulness_score <= 1),

    -- Overall RAG quality (RAG Triad)
    rag_triad_score FLOAT CHECK (rag_triad_score >= 0 AND rag_triad_score <= 1),

    -- Multimodal metrics (if applicable)
    modality_types JSONB, -- ['text', 'image', 'audio', 'video']
    cross_modal_coherence_score FLOAT CHECK (cross_modal_coherence_score >= 0 AND cross_modal_coherence_score <= 1),
    multimodal_integration_score FLOAT CHECK (multimodal_integration_score >= 0 AND multimodal_integration_score <= 1),

    -- User satisfaction
    user_satisfaction_score INTEGER CHECK (user_satisfaction_score >= 1 AND user_satisfaction_score <= 5),
    user_feedback TEXT,
    helpful_vote BOOLEAN,

    -- Hallucination detection
    hallucination_detected BOOLEAN DEFAULT FALSE,
    hallucination_severity VARCHAR(50), -- 'minor', 'moderate', 'severe'
    factual_errors_count INTEGER DEFAULT 0,

    -- Source attribution
    sources_cited INTEGER,
    source_attribution_accuracy FLOAT CHECK (source_attribution_accuracy >= 0 AND source_attribution_accuracy <= 1),

    -- Model information
    retrieval_model VARCHAR(100),
    generation_model VARCHAR(100),
    embedding_model VARCHAR(100),

    -- Cost and resources
    api_cost_usd DECIMAL(10,4),
    token_count INTEGER,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    evaluation_batch_id VARCHAR(100),

    -- Time partitioning
    query_date DATE NOT NULL GENERATED ALWAYS AS (DATE(query_timestamp)) STORED,
    query_hour INTEGER NOT NULL GENERATED ALWAYS AS (EXTRACT(HOUR FROM query_timestamp)) STORED,

    CONSTRAINT chk_hallucination_severity CHECK (hallucination_severity IN ('minor', 'moderate', 'severe'))
);

-- =============================================
-- Monitoring Configuration and Metadata
-- =============================================

-- Monitoring dashboard configurations
CREATE TABLE IF NOT EXISTS monitoring_dashboards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),

    -- Dashboard identification
    dashboard_name VARCHAR(255) NOT NULL,
    dashboard_description TEXT,
    dashboard_type VARCHAR(100) NOT NULL, -- 'sli', 'performance', 'business', 'health'

    -- Dashboard configuration
    layout_config JSONB NOT NULL, -- Dashboard layout and widget configuration
    time_range_default VARCHAR(50) DEFAULT '1h', -- '15m', '1h', '6h', '24h', '7d', '30d'
    refresh_interval_seconds INTEGER DEFAULT 30,

    -- Access control
    is_public BOOLEAN DEFAULT FALSE,
    allowed_roles JSONB, -- Roles that can access this dashboard
    allowed_users JSONB, -- Specific users that can access

    -- Dashboard metadata
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed TIMESTAMP WITH TIME ZONE,
    access_count INTEGER DEFAULT 0,

    is_deleted BOOLEAN DEFAULT FALSE,

    CONSTRAINT chk_dashboard_type CHECK (dashboard_type IN ('sli', 'performance', 'business', 'health', 'custom'))
);

-- Alerting rules configuration
CREATE TABLE IF NOT EXISTS alerting_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),

    -- Rule identification
    rule_name VARCHAR(255) NOT NULL,
    rule_description TEXT,
    rule_category VARCHAR(100) NOT NULL, -- 'sli', 'performance', 'health', 'business'

    -- Rule conditions
    metric_name VARCHAR(255) NOT NULL,
    metric_source VARCHAR(100) NOT NULL, -- 'prometheus', 'database', 'application'
    condition_operator VARCHAR(10) NOT NULL, -- '>', '<', '>=', '<=', '==', '!='
    threshold_value FLOAT NOT NULL,
    threshold_duration_minutes INTEGER DEFAULT 5,

    -- Advanced conditions (JSONB for flexibility)
    advanced_conditions JSONB,

    -- Rule configuration
    rule_enabled BOOLEAN DEFAULT TRUE,
    rule_severity VARCHAR(50) NOT NULL DEFAULT 'warning',

    -- Notification configuration
    notification_channels JSONB, -- Slack, email, PagerDuty, webhook
    notification_template JSONB,
    notification_cooldown_minutes INTEGER DEFAULT 60,

    -- Suppression rules
    suppression_rules JSONB, -- When to suppress alerts
    maintenance_windows JSONB, -- Scheduled maintenance windows

    -- Metadata
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_triggered TIMESTAMP WITH TIME ZONE,
    trigger_count INTEGER DEFAULT 0,

    is_deleted BOOLEAN DEFAULT FALSE,

    CONSTRAINT chk_rule_severity CHECK (rule_severity IN ('info', 'warning', 'error', 'critical')),
    CONSTRAINT chk_condition_operator CHECK (condition_operator IN ('>', '<', '>=', '<=', '==', '!=')),
    CONSTRAINT chk_rule_category CHECK (rule_category IN ('sli', 'performance', 'health', 'business', 'security'))
);

-- Data retention policies
CREATE TABLE IF NOT EXISTS data_retention_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),

    -- Policy identification
    policy_name VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL,

    -- Retention configuration
    detailed_retention_days INTEGER NOT NULL DEFAULT 30, -- High-resolution data
    hourly_retention_days INTEGER DEFAULT 90, -- Hourly aggregated data
    daily_retention_days INTEGER DEFAULT 365, -- Daily aggregated data
    monthly_retention_years INTEGER DEFAULT 7, -- Monthly aggregated data

    -- Archival configuration
    archive_after_days INTEGER DEFAULT 365,
    archive_storage VARCHAR(100), -- 's3', 'glacier', 'local'
    archive_compression BOOLEAN DEFAULT TRUE,

    -- Purge configuration
    auto_purge_enabled BOOLEAN DEFAULT TRUE,
    purge_after_days INTEGER,
    purge_confirmation_required BOOLEAN DEFAULT TRUE,

    -- Policy status
    policy_enabled BOOLEAN DEFAULT TRUE,
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE,
    run_status VARCHAR(50), -- 'success', 'failed', 'running'
    run_error_message TEXT,

    -- Statistics
    total_records_processed BIGINT DEFAULT 0,
    total_records_archived BIGINT DEFAULT 0,
    total_records_purged BIGINT DEFAULT 0,
    storage_saved_gb FLOAT DEFAULT 0,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT chk_run_status CHECK (run_status IN ('success', 'failed', 'running', 'scheduled'))
);

-- =============================================
-- Indexes for Performance Optimization
-- =============================================

-- SLI measurement indexes
CREATE INDEX IF NOT EXISTS idx_sli_measurements_sli_time ON sli_measurements(sli_id, measurement_time DESC);
CREATE INDEX IF NOT EXISTS idx_sli_measurements_org_time ON sli_measurements(organization_id, measurement_time DESC);
CREATE INDEX IF NOT EXISTS idx_sli_measurements_date ON sli_measurements(measurement_date, measurement_hour);
CREATE INDEX IF NOT EXISTS idx_sli_measurements_slo_status ON sli_measurements(meets_slo, measurement_time DESC);

-- Performance metrics indexes
CREATE INDEX IF NOT EXISTS idx_performance_metrics_name_time ON performance_metrics(metric_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_category_time ON performance_metrics(metric_category, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_component_time ON performance_metrics(component_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_org_time ON performance_metrics(organization_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_date ON performance_metrics(metric_date, metric_hour);
CREATE INDEX IF NOT EXISTS idx_performance_metrics_tags ON performance_metrics USING GIN(tags);

-- Database performance indexes
CREATE INDEX IF NOT EXISTS idx_db_perf_type_instance_time ON database_performance_metrics(database_type, database_instance, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_db_perf_date ON database_performance_metrics(metric_date, metric_hour);

-- Resource utilization indexes
CREATE INDEX IF NOT EXISTS idx_resource_util_type_id_time ON resource_utilization_metrics(resource_type, resource_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_resource_util_date ON resource_utilization_metrics(metric_date, metric_hour);

-- User session indexes
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_time ON user_sessions(user_id, session_start DESC);
CREATE INDEX IF NOT EXISTS idx_user_sessions_org_time ON user_sessions(organization_id, session_start DESC);
CREATE INDEX IF NOT EXISTS idx_user_sessions_status ON user_sessions(session_status, last_activity DESC);

-- User activity indexes
CREATE INDEX IF NOT EXISTS idx_user_activity_user_time ON user_activity_events(user_id, event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_user_activity_session_time ON user_activity_events(session_id, event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_user_activity_org_time ON user_activity_events(organization_id, event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_user_activity_type_time ON user_activity_events(event_type, event_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_user_activity_date ON user_activity_events(event_date, event_hour);

-- Service health indexes
CREATE INDEX IF NOT EXISTS idx_service_health_service_time ON service_health_status(service_name, check_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_service_health_status_time ON service_health_status(health_status, check_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_service_health_org_time ON service_health_status(organization_id, check_timestamp DESC);

-- Alert indexes
CREATE INDEX IF NOT EXISTS idx_system_alerts_status_time ON system_alerts(alert_status, triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_alerts_severity_time ON system_alerts(alert_severity, triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_alerts_org_time ON system_alerts(organization_id, triggered_at DESC);

-- Document processing indexes
CREATE INDEX IF NOT EXISTS idx_doc_proc_org_time ON document_processing_metrics(organization_id, upload_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_doc_proc_status_time ON document_processing_metrics(processing_status, upload_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_doc_proc_type_time ON document_processing_metrics(document_type, upload_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_doc_proc_date ON document_processing_metrics(CASE WHEN upload_timestamp IS NOT NULL THEN DATE(upload_timestamp) ELSE NULL END);

-- Search quality indexes
CREATE INDEX IF NOT EXISTS idx_search_quality_org_time ON search_quality_metrics(organization_id, search_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_search_quality_user_time ON search_quality_metrics(user_id, search_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_search_quality_session_time ON search_quality_metrics(session_id, search_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_search_quality_date ON search_quality_metrics(search_date, search_hour);

-- RAG quality indexes
CREATE INDEX IF NOT EXISTS idx_rag_quality_org_time ON rag_quality_metrics(organization_id, query_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_rag_quality_user_time ON rag_quality_metrics(user_id, query_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_rag_quality_score_time ON rag_quality_metrics(rag_triad_score, query_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_rag_quality_date ON rag_quality_metrics(query_date, query_hour);

-- Queue monitoring indexes
CREATE INDEX IF NOT EXISTS idx_queue_monitor_queue_time ON queue_monitoring_metrics(queue_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_queue_monitor_org_time ON queue_monitoring_metrics(organization_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_queue_monitor_date ON queue_monitoring_metrics(metric_date, metric_hour);

-- Feature usage indexes
CREATE INDEX IF NOT EXISTS idx_feature_usage_feature_time ON feature_usage_metrics(feature_name, usage_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_feature_usage_org_time ON feature_usage_metrics(organization_id, usage_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_feature_usage_date ON feature_usage_metrics(usage_date);

-- Comment on tables for documentation
COMMENT ON TABLE service_level_indicators IS 'Defines Service Level Indicators (SLIs) and Service Level Objectives (SLOs) for monitoring system performance against targets';
COMMENT ON TABLE sli_measurements IS 'Time-series measurements of SLI values with SLO compliance tracking';
COMMENT ON TABLE slo_breach_events IS 'Records SLO breach events with impact analysis and root cause information';
COMMENT ON TABLE performance_metrics IS 'High-frequency application performance metrics with percentile tracking';
COMMENT ON TABLE database_performance_metrics IS 'Database-specific performance metrics for all data stores';
COMMENT ON TABLE resource_utilization_metrics IS 'System resource utilization metrics (CPU, memory, disk, network, GPU)';
COMMENT ON TABLE user_sessions IS 'User session tracking with detailed analytics and security metrics';
COMMENT ON TABLE user_activity_events IS 'Granular user activity events for behavior analytics and business intelligence';
COMMENT ON TABLE feature_usage_metrics IS 'Feature adoption and usage tracking with A/B testing support';
COMMENT ON TABLE service_health_status IS 'Real-time service health monitoring with dependency tracking';
COMMENT ON TABLE system_alerts IS 'System alerts and incident management with post-mortem tracking';
COMMENT ON TABLE queue_monitoring_metrics IS 'Queue and job processing metrics for async task monitoring';
COMMENT ON TABLE document_processing_metrics IS 'End-to-end document processing pipeline metrics with quality scores';
COMMENT ON TABLE search_quality_metrics IS 'Search performance and quality metrics with user feedback tracking';
COMMENT ON TABLE rag_quality_metrics IS 'RAG system quality metrics including faithfulness, relevance, and hallucination detection';
COMMENT ON TABLE monitoring_dashboards IS 'Configurable monitoring dashboards with access control';
COMMENT ON TABLE alerting_rules IS 'Alert rule configuration with notification and suppression settings';
COMMENT ON TABLE data_retention_policies IS 'Data retention and archival policies for compliance and storage optimization';