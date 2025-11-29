-- Migration 006: Simple Document Upload Processing Schema
-- This migration adds processing tables to work with existing documents table

-- Create custom UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Document Processing Jobs Table
CREATE TABLE IF NOT EXISTS document_processing_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL CHECK (job_type IN (
        'text_extraction', 'entity_extraction', 'vector_indexing',
        'knowledge_graph_population', 'multimodal_processing', 'quality_assessment'
    )),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN (
        'pending', 'running', 'completed', 'failed', 'cancelled'
    )),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    priority INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    worker_id VARCHAR(100),
    progress_percentage DECIMAL(5,2) DEFAULT 0.0 CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    estimated_remaining_seconds INTEGER,
    error_message TEXT,
    error_details JSONB,
    result_data JSONB DEFAULT '{}',
    job_parameters JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT processing_jobs_retry_count_valid CHECK (retry_count >= 0 AND retry_count <= max_retries)
);

-- 2. Processing Logs Table
CREATE TABLE IF NOT EXISTS processing_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    job_id UUID REFERENCES document_processing_jobs(id) ON DELETE CASCADE,
    log_level VARCHAR(10) NOT NULL CHECK (log_level IN (
        'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    )),
    message TEXT NOT NULL,
    details JSONB,
    component VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT processing_logs_message_not_empty CHECK (length(trim(message)) > 0)
);

-- 3. Document Metrics Table
CREATE TABLE IF NOT EXISTS document_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC,
    metric_unit VARCHAR(50),
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',

    CONSTRAINT document_metrics_name_not_empty CHECK (length(trim(metric_name)) > 0),
    UNIQUE(document_id, metric_name, recorded_at)
);

-- Create Indexes for Performance

-- Document Processing Jobs indexes
CREATE INDEX IF NOT EXISTS idx_processing_jobs_document_id ON document_processing_jobs(document_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON document_processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_job_type ON document_processing_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_priority ON document_processing_jobs(priority DESC);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_created_at ON document_processing_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_updated_at ON document_processing_jobs(updated_at);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_worker_id ON document_processing_jobs(worker_id);

-- Processing Logs indexes
CREATE INDEX IF NOT EXISTS idx_processing_logs_document_id ON processing_logs(document_id);
CREATE INDEX IF NOT EXISTS idx_processing_logs_job_id ON processing_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_processing_logs_level ON processing_logs(log_level);
CREATE INDEX IF NOT EXISTS idx_processing_logs_created_at ON processing_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_processing_logs_component ON processing_logs(component);

-- Document Metrics indexes
CREATE INDEX IF NOT EXISTS idx_document_metrics_document_id ON document_metrics(document_id);
CREATE INDEX IF NOT EXISTS idx_document_metrics_name ON document_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_document_metrics_recorded_at ON document_metrics(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_document_metrics_document_name ON document_metrics(document_id, metric_name);

-- Create Updated At Trigger Function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to document_processing_jobs table
CREATE TRIGGER update_processing_jobs_updated_at
    BEFORE UPDATE ON document_processing_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Add Comments for Documentation
COMMENT ON TABLE document_processing_jobs IS 'Tracks individual processing jobs for each document';
COMMENT ON TABLE processing_logs IS 'Detailed logs for document processing operations';
COMMENT ON TABLE document_metrics IS 'Performance and quality metrics for documents';

-- Migration completed successfully
-- Run ANALYZE to update table statistics
ANALYZE document_processing_jobs;
ANALYZE processing_logs;
ANALYZE document_metrics;