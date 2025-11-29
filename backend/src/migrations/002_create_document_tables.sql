-- Migration 002: Create document management and processing tables
-- Supports multi-modal content with comprehensive processing pipeline

BEGIN;

-- Documents table for multi-modal content storage
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

-- Document processing jobs for tracking pipeline steps
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

-- Document versions for change tracking
CREATE TABLE document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Version information
    version_number INTEGER NOT NULL,
    change_description TEXT,

    -- File information at this version
    file_path VARCHAR(1000),
    file_size_bytes BIGINT,
    file_hash VARCHAR(64),

    -- Content snapshot
    content_text TEXT,
    content_summary TEXT,
    extracted_metadata JSONB DEFAULT '{}',

    -- Processing status at this version
    processing_status VARCHAR(50),
    processing_completed_at TIMESTAMPTZ,

    -- Change metadata
    created_by_user_id UUID REFERENCES users(id),
    change_type VARCHAR(50) CHECK (change_type IN ('upload', 'update', 'reprocess', 'metadata_update')),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(document_id, version_number)
);

-- Multimodal content extraction results
CREATE TABLE multimodal_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Content identification
    content_type VARCHAR(50) NOT NULL, -- text, image, audio, video
    extraction_method VARCHAR(100), -- ocr, whisper, frame_extraction, etc.

    -- Content data
    content_data JSONB NOT NULL, -- Different structure based on content_type
    raw_content TEXT, -- Raw extracted content (text, transcription, etc.)

    -- Quality and confidence
    confidence_score DECIMAL(5,4) CHECK (confidence_score >= 0 AND confidence_score <= 1),
    quality_metrics JSONB DEFAULT '{}',

    -- Temporal/Spatial information
    timestamp_offset_ms INTEGER, -- For audio/video
    spatial_coordinates JSONB, -- For images

    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Document quality metrics
CREATE TABLE document_quality_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Quality dimensions
    text_clarity_score DECIMAL(5,4) CHECK (text_clarity_score >= 0 AND text_clarity_score <= 1),
    image_resolution_score DECIMAL(5,4) CHECK (image_resolution_score >= 0 AND image_resolution_score <= 1),
    audio_clarity_score DECIMAL(5,4) CHECK (audio_clarity_score >= 0 AND audio_clarity_score <= 1),
    video_quality_score DECIMAL(5,4) CHECK (video_quality_score >= 0 AND video_quality_score <= 1),

    -- Overall quality
    overall_quality_score DECIMAL(5,4) CHECK (overall_quality_score >= 0 AND overall_quality_score <= 1),
    quality_grade VARCHAR(10) CHECK (quality_grade IN ('A', 'B', 'C', 'D', 'F')),

    -- Issues and recommendations
    quality_issues JSONB DEFAULT '[]',
    improvement_recommendations JSONB DEFAULT '[]',

    -- Evaluation metadata
    evaluation_model VARCHAR(100),
    evaluation_version VARCHAR(50),
    evaluation_config JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(document_id)
);

-- Document access logs
CREATE TABLE document_access_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id),

    -- Access information
    user_id UUID REFERENCES users(id),
    session_id UUID REFERENCES user_sessions(id),
    access_type VARCHAR(50) NOT NULL CHECK (access_type IN ('view', 'download', 'share', 'embed', 'search_hit')),

    -- Request context
    ip_address INET,
    user_agent TEXT,
    referrer TEXT,

    -- Query context (if accessed via search)
    search_query_id UUID,
    result_position INTEGER,

    -- Timing
    access_time_ms INTEGER, -- Time to fulfill the request
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for document tables
CREATE INDEX idx_documents_organization ON documents(organization_id, created_at DESC);
CREATE INDEX idx_documents_user ON documents(uploaded_by_user_id, created_at DESC);
CREATE INDEX idx_documents_type ON documents(document_type, processing_status);
CREATE INDEX idx_documents_status ON documents(processing_status, created_at);
CREATE INDEX idx_documents_modality ON documents(primary_modality, is_indexed);
CREATE INDEX idx_documents_tags ON documents USING GIN(tags);
CREATE INDEX idx_documents_search ON documents USING GIN(search_vector);
CREATE INDEX idx_documents_quality ON documents(quality_score DESC);
CREATE INDEX idx_documents_file_hash ON documents(file_hash);
CREATE INDEX idx_documents_public ON documents(is_public, quality_score DESC);
CREATE INDEX idx_documents_embedding ON documents(embedding_id) WHERE embedding_id IS NOT NULL;

CREATE INDEX idx_processing_jobs_document ON document_processing_jobs(document_id, job_type);
CREATE INDEX idx_processing_jobs_status ON document_processing_jobs(status, queued_at);
CREATE INDEX idx_processing_jobs_priority ON document_processing_jobs(job_priority DESC, queued_at);
CREATE INDEX idx_processing_jobs_retry ON document_processing_jobs(next_retry_at, status);
CREATE INDEX idx_processing_jobs_worker ON document_processing_jobs(worker_id, status);
CREATE INDEX idx_processing_jobs_org ON document_processing_jobs(organization_id, status);

CREATE INDEX idx_document_versions_document ON document_versions(document_id, version_number DESC);
CREATE INDEX idx_document_versions_created ON document_versions(created_at DESC);

CREATE INDEX idx_multimodal_content_document ON multimodal_content(document_id, content_type);
CREATE INDEX idx_multimodal_content_type ON multimodal_content(content_type, confidence_score DESC);
CREATE INDEX idx_multimodal_content_org ON multimodal_content(organization_id, created_at DESC);

CREATE INDEX idx_document_quality_document ON document_quality_metrics(document_id);
CREATE INDEX idx_document_quality_score ON document_quality_metrics(overall_quality_score DESC);
CREATE INDEX idx_document_quality_grade ON document_quality_metrics(quality_grade, organization_id);

CREATE INDEX idx_document_access_document ON document_access_logs(document_id, created_at DESC);
CREATE INDEX idx_document_access_user ON document_access_logs(user_id, created_at DESC);
CREATE INDEX idx_document_access_type ON document_access_logs(access_type, created_at DESC);
CREATE INDEX idx_document_access_org ON document_access_logs(organization_id, created_at DESC);

-- Enable Row Level Security
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_processing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE multimodal_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_quality_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_access_logs ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
CREATE POLICY document_org_policy ON documents
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY document_public_read ON documents
    FOR SELECT TO authenticated_users
    USING (is_public = TRUE OR organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Triggers for automatic updates
CREATE OR REPLACE FUNCTION update_document_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER documents_updated_at_trigger
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_document_updated_at();

CREATE OR REPLACE FUNCTION update_organization_document_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE organizations
        SET current_document_count = current_document_count + 1
        WHERE id = NEW.organization_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE organizations
        SET current_document_count = GREATEST(current_document_count - 1, 0)
        WHERE id = OLD.organization_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER document_count_trigger
    AFTER INSERT OR DELETE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_organization_document_count();

COMMIT;