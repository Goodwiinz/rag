-- Migration 006: Document Upload and Processing Schema
-- This migration adds comprehensive document management, processing tracking,
-- and entity extraction capabilities to support the document upload feature

-- Create custom UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Documents Table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(100),
    file_path VARCHAR(1000) NOT NULL,
    checksum_md5 VARCHAR(32),
    checksum_sha256 VARCHAR(64),
    uploaded_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    parent_document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'uploaded' CHECK (status IN (
        'uploaded', 'processing', 'processed', 'failed', 'archived'
    )),
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    processing_error_message TEXT,
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT documents_title_not_empty CHECK (length(trim(title)) > 0),
    CONSTRAINT documents_filename_not_empty CHECK (length(trim(filename)) > 0),
    CONSTRAINT documents_file_size_positive CHECK (file_size_bytes > 0),
    CONSTRAINT documents_version_positive CHECK (version > 0)
);

-- 2. Document Processing Jobs Table
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

    -- Constraints
    CONSTRAINT processing_jobs_retry_count_valid CHECK (retry_count >= 0 AND retry_count <= max_retries)
);

-- 3. Extracted Entities Table
CREATE TABLE IF NOT EXISTS extracted_entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_text VARCHAR(1000) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    confidence_score DECIMAL(5,4) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    start_position INTEGER,
    end_position INTEGER,
    context_text TEXT,
    extraction_method VARCHAR(50),
    model_version VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    neo4j_node_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT extracted_entities_text_not_empty CHECK (length(trim(entity_text)) > 0),
    CONSTRAINT extracted_entities_type_not_empty CHECK (length(trim(entity_type)) > 0),
    CONSTRAINT extracted_entities_positions_valid CHECK (
        (start_position IS NULL AND end_position IS NULL) OR
        (start_position IS NOT NULL AND end_position IS NOT NULL AND start_position <= end_position)
    ),

    -- Unique constraint to prevent duplicate entities
    UNIQUE(document_id, entity_text, entity_type, COALESCE(start_position, -1))
);

-- 4. Extracted Relationships Table
CREATE TABLE IF NOT EXISTS extracted_relationships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    source_entity_id UUID NOT NULL REFERENCES extracted_entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES extracted_entities(id) ON DELETE CASCADE,
    relationship_type VARCHAR(100) NOT NULL,
    confidence_score DECIMAL(5,4) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    context_text TEXT,
    extraction_method VARCHAR(50),
    model_version VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    neo4j_relationship_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT extracted_relationships_type_not_empty CHECK (length(trim(relationship_type)) > 0),
    CONSTRAINT extracted_relationships_no_self_reference CHECK (source_entity_id != target_entity_id),

    -- Unique constraint to prevent duplicate relationships
    UNIQUE(document_id, source_entity_id, target_entity_id, relationship_type)
);

-- 5. Document-Entity Mappings Table (for Neo4j integration)
CREATE TABLE IF NOT EXISTS document_entity_mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    neo4j_node_id VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_name VARCHAR(1000) NOT NULL,
    relationship_strength DECIMAL(5,4) DEFAULT 1.0 CHECK (relationship_strength > 0),
    mapping_source VARCHAR(50) DEFAULT 'entity_extraction',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT doc_entity_mappings_name_not_empty CHECK (length(trim(entity_name)) > 0),

    -- Unique constraint
    UNIQUE(document_id, neo4j_node_id)
);

-- 6. Processing Logs Table
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

    -- Constraints
    CONSTRAINT processing_logs_message_not_empty CHECK (length(trim(message)) > 0)
);

-- 7. Document Metrics Table
CREATE TABLE IF NOT EXISTS document_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC,
    metric_unit VARCHAR(50),
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',

    -- Constraints
    CONSTRAINT document_metrics_name_not_empty CHECK (length(trim(metric_name)) > 0),

    -- Unique constraint
    UNIQUE(document_id, metric_name, recorded_at)
);

-- 8. Document Batches Table (for batch uploads)
CREATE TABLE IF NOT EXISTS document_batches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_name VARCHAR(200),
    uploaded_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'processing' CHECK (status IN (
        'processing', 'completed', 'failed', 'cancelled'
    )),
    total_documents INTEGER DEFAULT 0,
    completed_documents INTEGER DEFAULT 0,
    failed_documents INTEGER DEFAULT 0,
    processing_config JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Constraints
    CONSTRAINT document_batches_name_length CHECK (batch_name IS NULL OR length(trim(batch_name)) > 0),
    CONSTRAINT document_batches_counts_valid CHECK (
        total_documents >= 0 AND
        completed_documents >= 0 AND
        failed_documents >= 0 AND
        completed_documents + failed_documents <= total_documents
    )
);

-- 9. Document Batch Items Table
CREATE TABLE IF NOT EXISTS document_batch_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id UUID NOT NULL REFERENCES document_batches(id) ON DELETE CASCADE,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    original_filename VARCHAR(255) NOT NULL,
    upload_status VARCHAR(20) DEFAULT 'pending' CHECK (upload_status IN (
        'pending', 'uploading', 'uploaded', 'failed', 'skipped'
    )),
    error_message TEXT,
    processing_time_ms INTEGER,
    file_size_bytes BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    CONSTRAINT document_batch_items_filename_not_empty CHECK (length(trim(original_filename)) > 0),
    CONSTRAINT document_batch_items_size_valid CHECK (file_size_bytes IS NULL OR file_size_bytes > 0),
    CONSTRAINT document_batch_items_time_valid CHECK (processing_time_ms IS NULL OR processing_time_ms >= 0)
);

-- Create Indexes for Performance

-- Documents table indexes
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_by ON documents(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_documents_file_type ON documents(file_type);
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_at ON documents(uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_metadata_gin ON documents USING gin(metadata);
CREATE INDEX IF NOT EXISTS idx_documents_tags_gin ON documents USING gin(tags);
CREATE INDEX IF NOT EXISTS idx_documents_deleted_at ON documents(deleted_at) WHERE is_deleted = TRUE;
CREATE INDEX IF NOT EXISTS idx_documents_parent_document ON documents(parent_document_id);
CREATE INDEX IF NOT EXISTS idx_documents_checksum_md5 ON documents(checksum_md5);
CREATE INDEX IF NOT EXISTS idx_documents_checksum_sha256 ON documents(checksum_sha256);

-- Document Processing Jobs indexes
CREATE INDEX IF NOT EXISTS idx_processing_jobs_document_id ON document_processing_jobs(document_id);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON document_processing_jobs(status);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_job_type ON document_processing_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_priority ON document_processing_jobs(priority DESC);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_created_at ON document_processing_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_updated_at ON document_processing_jobs(updated_at);
CREATE INDEX IF NOT EXISTS idx_processing_jobs_worker_id ON document_processing_jobs(worker_id);

-- Extracted Entities indexes
CREATE INDEX IF NOT EXISTS idx_extracted_entities_document_id ON extracted_entities(document_id);
CREATE INDEX IF NOT EXISTS idx_extracted_entities_type ON extracted_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_extracted_entities_text_gin ON extracted_entities USING gin(to_tsvector('english', entity_text));
CREATE INDEX IF NOT EXISTS idx_extracted_entities_confidence ON extracted_entities(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_extracted_entities_neo4j_node ON extracted_entities(neo4j_node_id);
CREATE INDEX IF NOT EXISTS idx_extracted_entities_extraction_method ON extracted_entities(extraction_method);

-- Extracted Relationships indexes
CREATE INDEX IF NOT EXISTS idx_extracted_relationships_document_id ON extracted_relationships(document_id);
CREATE INDEX IF NOT EXISTS idx_extracted_relationships_source ON extracted_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_extracted_relationships_target ON extracted_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_extracted_relationships_type ON extracted_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_extracted_relationships_confidence ON extracted_relationships(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_extracted_relationships_neo4j_rel ON extracted_relationships(neo4j_relationship_id);

-- Document-Entity Mappings indexes
CREATE INDEX IF NOT EXISTS idx_doc_entity_mappings_document ON document_entity_mappings(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_entity_mappings_neo4j_node ON document_entity_mappings(neo4j_node_id);
CREATE INDEX IF NOT EXISTS idx_doc_entity_mappings_type ON document_entity_mappings(entity_type);
CREATE INDEX IF NOT EXISTS idx_doc_entity_mappings_strength ON document_entity_mappings(relationship_strength DESC);

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

-- Document Batches indexes
CREATE INDEX IF NOT EXISTS idx_document_batches_uploaded_by ON document_batches(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_document_batches_status ON document_batches(status);
CREATE INDEX IF NOT EXISTS idx_document_batches_created_at ON document_batches(created_at DESC);

-- Document Batch Items indexes
CREATE INDEX IF NOT EXISTS idx_document_batch_items_batch_id ON document_batch_items(batch_id);
CREATE INDEX IF NOT EXISTS idx_document_batch_items_document_id ON document_batch_items(document_id);
CREATE INDEX IF NOT EXISTS idx_document_batch_items_status ON document_batch_items(upload_status);

-- Create Updated At Triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to tables with updated_at columns
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processing_jobs_updated_at
    BEFORE UPDATE ON document_processing_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_batch_items_updated_at
    BEFORE UPDATE ON document_batch_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create Row Level Security (RLS) Policies
-- Enable RLS on tables that need user-specific access
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_processing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_batch_items ENABLE ROW LEVEL SECURITY;

-- Documents RLS Policies
CREATE POLICY documents_user_policy ON documents
    FOR ALL
    TO authenticated_users
    USING (uploaded_by = current_user_id() OR is_public = true)
    WITH CHECK (uploaded_by = current_user_id());

-- Processing Jobs RLS Policies
CREATE POLICY processing_jobs_user_policy ON document_processing_jobs
    FOR ALL
    TO authenticated_users
    USING (EXISTS (
        SELECT 1 FROM documents d
        WHERE d.id = document_processing_jobs.document_id
        AND d.uploaded_by = current_user_id()
    ));

-- Extracted Entities RLS Policies
CREATE POLICY extracted_entities_user_policy ON extracted_entities
    FOR SELECT
    TO authenticated_users
    USING (EXISTS (
        SELECT 1 FROM documents d
        WHERE d.id = extracted_entities.document_id
        AND (d.uploaded_by = current_user_id() OR d.is_public = true)
    ));

-- Document Batches RLS Policies
CREATE POLICY document_batches_user_policy ON document_batches
    FOR ALL
    TO authenticated_users
    USING (uploaded_by = current_user_id())
    WITH CHECK (uploaded_by = current_user_id());

-- Document Batch Items RLS Policies
CREATE POLICY document_batch_items_user_policy ON document_batch_items
    FOR ALL
    TO authenticated_users
    USING (EXISTS (
        SELECT 1 FROM document_batches db
        WHERE db.id = document_batch_items.batch_id
        AND db.uploaded_by = current_user_id()
    ));

-- Grant Permissions
GRANT ALL ON documents TO authenticated_users;
GRANT ALL ON document_processing_jobs TO authenticated_users;
GRANT SELECT ON extracted_entities TO authenticated_users;
GRANT SELECT ON extracted_relationships TO authenticated_users;
GRANT ALL ON document_batches TO authenticated_users;
GRANT ALL ON document_batch_items TO authenticated_users;
GRANT SELECT ON document_entity_mappings TO authenticated_users;
GRANT SELECT ON processing_logs TO authenticated_users;
GRANT SELECT ON document_metrics TO authenticated_users;

-- Create Views for Common Queries

-- Document Processing Summary View
CREATE OR REPLACE VIEW document_processing_summary AS
SELECT
    d.id,
    d.title,
    d.filename,
    d.file_type,
    d.file_size_bytes,
    d.status,
    d.uploaded_at,
    d.processing_started_at,
    d.processing_completed_at,
    d.tags,
    u.email as uploaded_by_email,
    u.full_name as uploaded_by_name,
    COUNT(dpj.id) as total_jobs,
    COUNT(CASE WHEN dpj.status = 'completed' THEN 1 END) as completed_jobs,
    COUNT(CASE WHEN dpj.status = 'failed' THEN 1 END) as failed_jobs,
    COUNT(CASE WHEN dpj.status = 'running' THEN 1 END) as running_jobs,
    MAX(dpj.progress_percentage) as max_progress,
    CASE
        WHEN COUNT(dpj.id) = 0 THEN 'no_jobs'
        WHEN COUNT(CASE WHEN dpj.status IN ('pending', 'running') THEN 1 END) > 0 THEN 'processing'
        WHEN COUNT(CASE WHEN dpj.status = 'failed' THEN 1 END) > 0 THEN 'has_failures'
        ELSE 'completed'
    END as processing_summary_status
FROM documents d
JOIN users u ON d.uploaded_by = u.id
LEFT JOIN document_processing_jobs dpj ON d.id = dpj.document_id
WHERE d.is_deleted = FALSE
GROUP BY d.id, d.title, d.filename, d.file_type, d.file_size_bytes,
         d.status, d.uploaded_at, d.processing_started_at, d.processing_completed_at,
         d.tags, u.email, u.full_name;

-- Entity Extraction Summary View
CREATE OR REPLACE VIEW entity_extraction_summary AS
SELECT
    d.id as document_id,
    d.title,
    d.filename,
    COUNT(DISTINCT ee.id) as total_entities,
    COUNT(DISTINCT ee.entity_type) as unique_entity_types,
    COUNT(DISTINCT er.id) as total_relationships,
    AVG(ee.confidence_score) as avg_entity_confidence,
    MAX(ee.created_at) as last_extraction_time
FROM documents d
LEFT JOIN extracted_entities ee ON d.id = ee.document_id
LEFT JOIN extracted_relationships er ON d.id = er.document_id
WHERE d.is_deleted = FALSE
GROUP BY d.id, d.title, d.filename;

-- Add Comments for Documentation
COMMENT ON TABLE documents IS 'Core table for storing document metadata and processing status';
COMMENT ON TABLE document_processing_jobs IS 'Tracks individual processing jobs for each document';
COMMENT ON TABLE extracted_entities IS 'Stores entities extracted from documents';
COMMENT ON TABLE extracted_relationships IS 'Stores relationships between extracted entities';
COMMENT ON TABLE document_entity_mappings IS 'Maps documents to Neo4j knowledge graph nodes';
COMMENT ON TABLE processing_logs IS 'Detailed logs for document processing operations';
COMMENT ON TABLE document_metrics IS 'Performance and quality metrics for documents';
COMMENT ON TABLE document_batches IS 'Manages batch upload operations';
COMMENT ON TABLE document_batch_items IS 'Individual items within batch uploads';

-- Migration completed successfully
-- Run ANALYZE to update table statistics
ANALYZE documents;
ANALYZE document_processing_jobs;
ANALYZE extracted_entities;
ANALYZE extracted_relationships;
ANALYZE document_entity_mappings;
ANALYZE processing_logs;
ANALYZE document_metrics;
ANALYZE document_batches;
ANALYZE document_batch_items;