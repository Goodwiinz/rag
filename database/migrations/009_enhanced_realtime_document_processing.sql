-- Migration 008: Enhanced Real-Time Document Processing Status Schema
-- Adds comprehensive real-time tracking capabilities for document processing pipeline

BEGIN;

-- Add enhanced real-time tracking columns to existing documents table
ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_progress DECIMAL(5,2) DEFAULT 0.0
    CHECK (processing_progress >= 0 AND processing_progress <= 100);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS current_processing_stage VARCHAR(100);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS estimated_remaining_seconds INTEGER;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS last_status_update TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE documents ADD COLUMN IF NOT EXISTS current_execution_id UUID;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_batch_id VARCHAR(100);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS active_workers JSONB DEFAULT '[]';
ALTER TABLE documents ADD COLUMN IF NOT EXISTS processing_priority INTEGER DEFAULT 5
    CHECK (processing_priority >= 1 AND processing_priority <= 10);

-- Add constraints and indexes for real-time queries
CREATE INDEX IF NOT EXISTS idx_documents_realtime_status ON documents(processing_status, processing_progress DESC, last_status_update DESC);
CREATE INDEX IF NOT EXISTS idx_documents_current_execution ON documents(current_execution_id) WHERE current_execution_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_documents_batch_processing ON documents(processing_batch_id, processing_status);
CREATE INDEX IF NOT EXISTS idx_documents_priority_queue ON documents(processing_priority DESC, created_at ASC)
    WHERE processing_status IN ('queued', 'processing', 'retrying');

-- Document processing stages configuration
CREATE TABLE IF NOT EXISTS document_processing_stages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_key VARCHAR(100) NOT NULL UNIQUE,
    stage_name VARCHAR(200) NOT NULL,
    stage_order INTEGER NOT NULL CHECK (stage_order > 0),
    stage_type VARCHAR(50) NOT NULL CHECK (stage_type IN ('extraction', 'transformation', 'analysis', 'indexing')),
    description TEXT,

    -- Stage configuration
    default_config JSONB DEFAULT '{}',
    required_predecessors TEXT[] DEFAULT '{}',
    is_optional BOOLEAN DEFAULT FALSE,
    can_fail BOOLEAN DEFAULT FALSE,
    timeout_seconds INTEGER DEFAULT 300,

    -- Multi-modal support
    supported_document_types TEXT[] DEFAULT '{}',
    required_modalities TEXT[] DEFAULT '{}',
    output_modalities TEXT[] DEFAULT '{}',

    -- Agent configuration
    default_agent_type VARCHAR(100),
    agent_config JSONB DEFAULT '{}',

    -- Performance expectations
    expected_duration_ms INTEGER,
    max_retries INTEGER DEFAULT 3,
    backoff_multiplier DECIMAL(3,2) DEFAULT 2.0,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,

    UNIQUE(stage_key, stage_order)
);

-- Insert default processing stages
INSERT INTO document_processing_stages (stage_key, stage_name, stage_order, stage_type, description, supported_document_types, default_agent_type) VALUES
('file_validation', 'File Validation', 1, 'extraction', 'Validate file format, size, and integrity', ARRAY['pdf', 'text', 'image', 'audio', 'video'], 'validation_agent'),
('text_extraction', 'Text Extraction', 2, 'extraction', 'Extract text content using OCR or direct reading', ARRAY['pdf', 'image'], 'ocr_agent'),
('audio_transcription', 'Audio Transcription', 3, 'extraction', 'Transcribe audio content to text', ARRAY['audio', 'video'], 'transcription_agent'),
('video_frame_analysis', 'Video Frame Analysis', 3, 'extraction', 'Extract and analyze key frames from video', ARRAY['video'], 'video_analysis_agent'),
('content_enrichment', 'Content Enrichment', 4, 'transformation', 'Enhance content with metadata and context', ARRAY['pdf', 'text', 'image', 'audio', 'video'], 'enrichment_agent'),
('entity_extraction', 'Entity Extraction', 5, 'analysis', 'Extract named entities and relationships', ARRAY['pdf', 'text', 'image', 'audio', 'video'], 'entity_agent'),
('content_analysis', 'Content Analysis', 6, 'analysis', 'Analyze content quality and structure', ARRAY['pdf', 'text', 'image', 'audio', 'video'], 'analysis_agent'),
('vector_embedding', 'Vector Embedding', 7, 'transformation', 'Generate vector embeddings for semantic search', ARRAY['pdf', 'text', 'image', 'audio', 'video'], 'embedding_agent'),
('graph_indexing', 'Knowledge Graph Indexing', 8, 'indexing', 'Index entities and relationships in knowledge graph', ARRAY['pdf', 'text', 'image', 'audio', 'video'], 'graph_agent'),
('search_indexing', 'Search Indexing', 9, 'indexing', 'Index content for full-text and hybrid search', ARRAY['pdf', 'text', 'image', 'audio', 'video'], 'search_agent')
ON CONFLICT (stage_key, stage_order) DO NOTHING;

-- Processing job executions table
CREATE TABLE IF NOT EXISTS processing_job_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Execution identification
    execution_id VARCHAR(255) NOT NULL UNIQUE,
    parent_execution_id UUID REFERENCES processing_job_executions(id),
    batch_id VARCHAR(100),

    -- Execution status
    execution_status VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (execution_status IN ('pending', 'queued', 'running', 'paused', 'completed', 'failed', 'cancelled', 'retrying')),
    overall_progress DECIMAL(5,2) DEFAULT 0.0 CHECK (overall_progress >= 0 AND overall_progress <= 100),

    -- Current stage information
    current_stage VARCHAR(100),
    current_stage_started_at TIMESTAMPTZ,
    total_stages INTEGER DEFAULT 0,
    completed_stages INTEGER DEFAULT 0,
    failed_stages INTEGER DEFAULT 0,

    -- Timing
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    paused_at TIMESTAMPTZ,
    resumed_at TIMESTAMPTZ,
    timeout_at TIMESTAMPTZ,

    -- Progress estimation
    estimated_remaining_seconds INTEGER,
    average_stage_duration_ms INTEGER,

    -- Execution metadata
    execution_config JSONB DEFAULT '{}',
    execution_metadata JSONB DEFAULT '{}',
    custom_stages TEXT[] DEFAULT '{}',

    -- Error handling
    error_message TEXT,
    error_details JSONB DEFAULT '{}',
    error_stage VARCHAR(100),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at TIMESTAMPTZ,

    -- Resource allocation
    allocated_memory_mb INTEGER,
    allocated_cpu_cores INTEGER,
    max_duration_seconds INTEGER,

    -- Worker assignment
    primary_worker_id VARCHAR(255),
    worker_pool_id VARCHAR(100),
    worker_capabilities JSONB DEFAULT '{}',

    -- System metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,

    CONSTRAINT valid_progress CHECK (overall_progress >= 0 AND overall_progress <= 100),
    CONSTRAINT valid_stage_count CHECK (completed_stages + failed_stages <= total_stages)
);

-- Stage executions table (individual stage progress)
CREATE TABLE IF NOT EXISTS stage_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_execution_id UUID NOT NULL REFERENCES processing_job_executions(id) ON DELETE CASCADE,
    stage_id UUID REFERENCES document_processing_stages(id),

    -- Stage identification
    stage_key VARCHAR(100) NOT NULL,
    stage_name VARCHAR(200) NOT NULL,
    stage_order INTEGER NOT NULL,

    -- Stage status
    stage_status VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (stage_status IN ('pending', 'running', 'completed', 'failed', 'skipped', 'retrying')),
    progress_percentage DECIMAL(5,2) DEFAULT 0.0 CHECK (progress_percentage >= 0 AND progress_percentage <= 100),

    -- Step progress within stage
    current_step INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0,
    completed_steps INTEGER DEFAULT 0,
    step_descriptions JSONB DEFAULT '{}',

    -- Timing
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    last_progress_update TIMESTAMPTZ DEFAULT NOW(),
    timeout_at TIMESTAMPTZ,

    -- Stage configuration and results
    stage_config JSONB DEFAULT '{}',
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    intermediate_results JSONB DEFAULT '{}',

    -- Worker information
    worker_id VARCHAR(255),
    worker_type VARCHAR(100),
    worker_version VARCHAR(50),
    worker_capabilities JSONB DEFAULT '{}',

    -- Performance metrics
    duration_ms INTEGER,
    cpu_time_ms INTEGER,
    memory_peak_mb INTEGER,
    tokens_processed INTEGER,
    tokens_generated INTEGER,

    -- Error handling
    error_message TEXT,
    error_type VARCHAR(100),
    error_details JSONB DEFAULT '{}',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Quality metrics
    output_quality_score DECIMAL(5,4) CHECK (output_quality_score >= 0 AND output_quality_score <= 1),
    confidence_score DECIMAL(5,4) CHECK (confidence_score >= 0 AND confidence_score <= 1),

    -- Metadata
    stage_metadata JSONB DEFAULT '{}',
    checkpoints JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,

    CONSTRAINT valid_stage_progress CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    CONSTRAINT valid_step_count CHECK (completed_steps <= total_steps),
    UNIQUE(job_execution_id, stage_key)
);

-- Agent execution tracking
CREATE TABLE IF NOT EXISTS agent_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_execution_id UUID NOT NULL REFERENCES stage_executions(id) ON DELETE CASCADE,
    job_execution_id UUID NOT NULL REFERENCES processing_job_executions(id) ON DELETE CASCADE,

    -- Agent identification
    agent_id VARCHAR(255) NOT NULL,
    agent_type VARCHAR(100) NOT NULL,
    agent_version VARCHAR(50),
    agent_role VARCHAR(100),  -- orchestrator, retrieval, analysis, etc.

    -- Execution status
    execution_status VARCHAR(50) NOT NULL DEFAULT 'pending'
        CHECK (execution_status IN ('pending', 'running', 'completed', 'failed', 'timeout', 'cancelled')),

    -- Timing
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    timeout_at TIMESTAMPTZ,
    duration_ms INTEGER,

    -- Task configuration
    task_description TEXT,
    task_config JSONB DEFAULT '{}',
    input_data JSONB DEFAULT '{}',

    -- Results and output
    output_data JSONB DEFAULT '{}',
    artifacts JSONB DEFAULT '{}',
    confidence_score DECIMAL(5,4) CHECK (confidence_score >= 0 AND confidence_score <= 1),

    -- Performance metrics
    tokens_used INTEGER,
    api_calls INTEGER,
    cost_usd DECIMAL(10,6),

    -- Error handling
    error_message TEXT,
    error_type VARCHAR(100),
    error_details JSONB DEFAULT '{}',
    retry_count INTEGER DEFAULT 0,

    -- Collaboration data
    collaborated_with JSONB DEFAULT '[]',  -- Other agents this agent worked with
    messages_exchanged INTEGER DEFAULT 0,

    -- Metadata
    execution_metadata JSONB DEFAULT '{}',
    model_used VARCHAR(100),
    llm_config JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Document status snapshots for historical tracking
CREATE TABLE IF NOT EXISTS document_status_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    job_execution_id UUID REFERENCES processing_job_executions(id),

    -- Status snapshot
    processing_status VARCHAR(50) NOT NULL,
    processing_progress DECIMAL(5,2) DEFAULT 0.0,
    current_stage VARCHAR(100),
    stage_progress JSONB DEFAULT '{}',

    -- Performance snapshot
    processing_duration_seconds INTEGER,
    estimated_remaining_seconds INTEGER,
    error_rate DECIMAL(5,4) DEFAULT 0.0,
    quality_score DECIMAL(5,4),

    -- Resource snapshot
    active_workers JSONB DEFAULT '[]',
    memory_usage_mb INTEGER,
    cpu_usage_percent DECIMAL(5,2),

    -- Snapshot metadata
    snapshot_reason VARCHAR(100),  -- stage_complete, error, timeout, periodic
    snapshot_data JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Processing metrics and analytics
CREATE TABLE IF NOT EXISTS processing_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    job_execution_id UUID REFERENCES processing_job_executions(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Time period
    metric_period_start TIMESTAMPTZ NOT NULL,
    metric_period_end TIMESTAMPTZ NOT NULL,
    metric_type VARCHAR(100) NOT NULL,  -- stage, agent, overall

    -- Performance metrics
    total_duration_ms INTEGER,
    average_stage_duration_ms INTEGER,
    slowest_stage_duration_ms INTEGER,
    fastest_stage_duration_ms INTEGER,

    -- Quality metrics
    overall_quality_score DECIMAL(5,4),
    accuracy_score DECIMAL(5,4),
    completeness_score DECIMAL(5,4),
    consistency_score DECIMAL(5,4),

    -- Resource metrics
    total_memory_mb INTEGER,
    peak_memory_mb INTEGER,
    total_cpu_ms INTEGER,
    peak_cpu_percent DECIMAL(5,2),

    -- Cost metrics
    total_cost_usd DECIMAL(10,6),
    cost_per_token DECIMAL(12,8),
    cost_per_mb DECIMAL(8,6),

    -- Throughput metrics
    tokens_per_second DECIMAL(10,2),
    mb_per_second DECIMAL(10,2),
    pages_per_second DECIMAL(10,2),

    -- Error metrics
    error_count INTEGER DEFAULT 0,
    error_rate DECIMAL(5,4) DEFAULT 0.0,
    retry_count INTEGER DEFAULT 0,
    timeout_count INTEGER DEFAULT 0,

    -- Metadata
    metric_metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_period CHECK (metric_period_end > metric_period_start)
);

-- Resource usage tracking for detailed monitoring
CREATE TABLE IF NOT EXISTS resource_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_execution_id UUID REFERENCES processing_job_executions(id),
    stage_execution_id UUID REFERENCES stage_executions(id),
    agent_execution_id UUID REFERENCES agent_executions(id),
    worker_id VARCHAR(255),

    -- Resource metrics
    timestamp TIMESTAMPTZ NOT NULL,
    cpu_percent DECIMAL(5,2),
    memory_used_mb INTEGER,
    memory_available_mb INTEGER,
    disk_used_mb INTEGER,
    network_rx_mb DECIMAL(10,2),
    network_tx_mb DECIMAL(10,2),

    -- Process-specific metrics
    process_cpu_percent DECIMAL(5,2),
    process_memory_mb INTEGER,
    process_threads INTEGER,
    process_file_descriptors INTEGER,

    -- System metrics
    load_average_1min DECIMAL(5,2),
    load_average_5min DECIMAL(5,2),
    available_connections INTEGER,

    -- GPU metrics (if applicable)
    gpu_utilization_percent DECIMAL(5,2),
    gpu_memory_used_mb INTEGER,
    gpu_temperature_celsius INTEGER,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enhanced error logging with context
CREATE TABLE IF NOT EXISTS processing_error_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_execution_id UUID REFERENCES processing_job_executions(id),
    stage_execution_id UUID REFERENCES stage_executions(id),
    agent_execution_id UUID REFERENCES agent_executions(id),
    document_id UUID REFERENCES documents(id),

    -- Error identification
    error_id VARCHAR(255) NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_category VARCHAR(50) NOT NULL CHECK (error_category IN ('system', 'network', 'processing', 'validation', 'timeout', 'resource', 'user_input')),
    severity VARCHAR(20) NOT NULL DEFAULT 'error' CHECK (severity IN ('debug', 'info', 'warning', 'error', 'critical', 'fatal')),

    -- Error details
    error_message TEXT NOT NULL,
    error_code VARCHAR(50),
    error_stack TEXT,
    error_context JSONB DEFAULT '{}',

    -- System context
    system_state JSONB DEFAULT '{}',
    environment_variables JSONB DEFAULT '{}',
    configuration_snapshot JSONB DEFAULT '{}',

    -- User context
    user_action TEXT,
    user_input JSONB DEFAULT '{}',
    session_id VARCHAR(255),

    -- Impact assessment
    impact_level VARCHAR(20) DEFAULT 'medium' CHECK (impact_level IN ('low', 'medium', 'high', 'critical')),
    affected_components TEXT[] DEFAULT '{}',
    recovery_possible BOOLEAN DEFAULT TRUE,

    -- Recovery information
    recovery_actions TEXT[] DEFAULT '{}',
    automatic_retry_recommended BOOLEAN DEFAULT FALSE,
    manual_intervention_required BOOLEAN DEFAULT FALSE,

    -- Timing
    occurred_at TIMESTAMPTZ DEFAULT NOW(),
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolution_duration_seconds INTEGER,

    -- Resolution details
    resolution_method VARCHAR(100),
    resolution_details TEXT,
    prevented_recurrence BOOLEAN DEFAULT FALSE,

    -- Metadata
    error_metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for real-time queries and performance
CREATE INDEX IF NOT EXISTS idx_processing_jobs_execution_id ON processing_job_executions(execution_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_document_status ON processing_job_executions(document_id, execution_status);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_org_status ON processing_job_executions(organization_id, execution_status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_batch ON processing_job_executions(batch_id, execution_status);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_progress ON processing_job_executions(execution_status, overall_progress DESC, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_worker ON processing_job_executions(primary_worker_id, execution_status);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_retry ON processing_job_executions(next_retry_at, execution_status) WHERE execution_status = 'failed';

CREATE INDEX IF NOT EXISTS idx_stage_executions_job_stage ON stage_executions(job_execution_id, stage_order);
CREATE INDEX IF NOT EXISTS idx_stage_executions_status ON stage_executions(stage_status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_stage_executions_progress ON stage_executions(stage_status, progress_percentage DESC, last_progress_update DESC);
CREATE INDEX IF NOT EXISTS idx_stage_executions_worker ON stage_executions(worker_id, stage_status);
CREATE INDEX IF NOT EXISTS idx_stage_executions_retry ON stage_executions(retry_count, stage_status) WHERE stage_status = 'failed';

CREATE INDEX IF NOT EXISTS idx_agent_executions_stage ON agent_executions(stage_execution_id, agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_executions_status ON agent_executions(execution_status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_executions_agent ON agent_executions(agent_id, execution_status);
CREATE INDEX IF NOT EXISTS idx_agent_executions_cost ON agent_executions(cost_usd DESC, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_status_snapshots_document_time ON document_status_snapshots(document_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_status_snapshots_job ON document_status_snapshots(job_execution_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_status_snapshots_periodic ON document_status_snapshots(snapshot_reason, created_at DESC) WHERE snapshot_reason = 'periodic';

CREATE INDEX IF NOT EXISTS idx_processing_metrics_org_period ON processing_metrics(organization_id, metric_period_start DESC, metric_type);
CREATE INDEX IF NOT EXISTS idx_processing_metrics_type_period ON processing_metrics(metric_type, metric_period_start DESC);
CREATE INDEX IF NOT EXISTS idx_processing_metrics_document ON processing_metrics(document_id, metric_period_start DESC) WHERE document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_resource_usage_job_timestamp ON resource_usage_logs(job_execution_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_resource_usage_stage_timestamp ON resource_usage_logs(stage_execution_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_resource_usage_worker_timestamp ON resource_usage_logs(worker_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_resource_usage_timestamp ON resource_usage_logs(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_error_logs_job ON processing_error_logs(job_execution_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_logs_document ON processing_error_logs(document_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_logs_severity ON processing_error_logs(severity, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_logs_type ON processing_error_logs(error_type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_logs_category ON processing_error_logs(error_category, severity, occurred_at DESC);

-- Enable Row Level Security for new tables
ALTER TABLE processing_job_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE stage_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_status_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE resource_usage_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_error_logs ENABLE ROW LEVEL SECURITY;

-- RLS policies for organization-based access
CREATE POLICY processing_jobs_org_policy ON processing_job_executions
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY stage_executions_org_policy ON stage_executions
    FOR ALL TO authenticated_users
    USING (job_execution_id IN (
        SELECT id FROM processing_job_executions
        WHERE organization_id = current_setting('app.current_organization_id', true)::UUID
    ));

CREATE POLICY agent_executions_org_policy ON agent_executions
    FOR ALL TO authenticated_users
    USING (job_execution_id IN (
        SELECT id FROM processing_job_executions
        WHERE organization_id = current_setting('app.current_organization_id', true)::UUID
    ));

-- Triggers for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_processing_job_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER processing_jobs_updated_at_trigger
    BEFORE UPDATE ON processing_job_executions
    FOR EACH ROW
    EXECUTE FUNCTION update_processing_job_updated_at();

CREATE OR REPLACE FUNCTION update_stage_execution_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    NEW.last_progress_update = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER stage_executions_updated_at_trigger
    BEFORE UPDATE ON stage_executions
    FOR EACH ROW
    EXECUTE FUNCTION update_stage_execution_updated_at();

-- Trigger to update document processing status
CREATE OR REPLACE FUNCTION update_document_processing_status()
RETURNS TRIGGER AS $$
BEGIN
    -- Update the document's processing status when job execution changes
    UPDATE documents
    SET
        processing_status = NEW.execution_status,
        processing_progress = NEW.overall_progress,
        current_processing_stage = NEW.current_stage,
        current_execution_id = NEW.execution_id,
        estimated_remaining_seconds = NEW.estimated_remaining_seconds,
        last_status_update = NOW()
    WHERE id = NEW.document_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER job_execution_status_change_trigger
    AFTER UPDATE OF execution_status, overall_progress, current_stage, estimated_remaining_seconds
    ON processing_job_executions
    FOR EACH ROW
    EXECUTE FUNCTION update_document_processing_status();

-- Trigger to update job progress when stage completes
CREATE OR REPLACE FUNCTION update_job_progress_from_stage()
RETURNS TRIGGER AS $$
BEGIN
    -- Update overall job progress based on stage completion
    IF NEW.stage_status = 'completed' AND OLD.stage_status != 'completed' THEN
        UPDATE processing_job_executions
        SET
            completed_stages = completed_stages + 1,
            overall_progress = CASE
                WHEN total_stages > 0 THEN (completed_stages + 1) * 100.0 / total_stages
                ELSE 0
            END,
            updated_at = NOW()
        WHERE id = NEW.job_execution_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER stage_completion_progress_trigger
    AFTER UPDATE OF stage_status ON stage_executions
    FOR EACH ROW
    EXECUTE FUNCTION update_job_progress_from_stage();

COMMIT;