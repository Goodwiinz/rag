# Document Upload Database Schema Design

## Overview

This document extends the existing RAG system database schema to support document upload with automatic knowledge graph population.

## Database Schema Extensions

### 1. Document Management Tables

#### documents
```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(100),
    file_path VARCHAR(1000) NOT NULL,
    checksum_md5 VARCHAR(32),
    checksum_sha256 VARCHAR(64),
    uploaded_by UUID NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    parent_document_id UUID REFERENCES documents(id),
    status VARCHAR(20) DEFAULT 'uploaded' CHECK (status IN (
        'uploaded', 'processing', 'processed', 'failed', 'archived'
    )),
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    processing_error_message TEXT,
    metadata JSONB DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for performance
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_uploaded_by ON documents(uploaded_by);
CREATE INDEX idx_documents_file_type ON documents(file_type);
CREATE INDEX idx_documents_uploaded_at ON documents(uploaded_at);
CREATE INDEX idx_documents_metadata_gin ON documents USING gin(metadata);
CREATE INDEX idx_documents_tags_gin ON documents USING gin(tags);
```

#### document_processing_jobs
```sql
CREATE TABLE document_processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL CHECK (job_type IN (
        'text_extraction', 'entity_extraction', 'vector_indexing',
        'knowledge_graph_population', 'multimodal_processing'
    )),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN (
        'pending', 'running', 'completed', 'failed', 'cancelled'
    )),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    priority INTEGER DEFAULT 5,
    worker_id VARCHAR(100),
    progress_percentage DECIMAL(5,2) DEFAULT 0.0,
    estimated_remaining_seconds INTEGER,
    error_message TEXT,
    error_details JSONB,
    result_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_processing_jobs_document_id ON document_processing_jobs(document_id);
CREATE INDEX idx_processing_jobs_status ON document_processing_jobs(status);
CREATE INDEX idx_processing_jobs_job_type ON document_processing_jobs(job_type);
CREATE INDEX idx_processing_jobs_priority ON document_processing_jobs(priority DESC);
CREATE INDEX idx_processing_jobs_created_at ON document_processing_jobs(created_at);
```

### 2. Entity Extraction Results

#### extracted_entities
```sql
CREATE TABLE extracted_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_text VARCHAR(1000) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    confidence_score DECIMAL(5,4),
    start_position INTEGER,
    end_position INTEGER,
    context_text TEXT,
    extraction_method VARCHAR(50),
    model_version VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(document_id, entity_text, entity_type, start_position)
);

-- Indexes
CREATE INDEX idx_extracted_entities_document_id ON extracted_entities(document_id);
CREATE INDEX idx_extracted_entities_type ON extracted_entities(entity_type);
CREATE INDEX idx_extracted_entities_text_gin ON extracted_entities USING gin(to_tsvector('english', entity_text));
CREATE INDEX idx_extracted_entities_confidence ON extracted_entities(confidence_score);
```

#### extracted_relationships
```sql
CREATE TABLE extracted_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    source_entity_id UUID NOT NULL REFERENCES extracted_entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES extracted_entities(id) ON DELETE CASCADE,
    relationship_type VARCHAR(100) NOT NULL,
    confidence_score DECIMAL(5,4),
    context_text TEXT,
    extraction_method VARCHAR(50),
    model_version VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(document_id, source_entity_id, target_entity_id, relationship_type)
);

-- Indexes
CREATE INDEX idx_extracted_relationships_document_id ON extracted_relationships(document_id);
CREATE INDEX idx_extracted_relationships_source ON extracted_relationships(source_entity_id);
CREATE INDEX idx_extracted_relationships_target ON extracted_relationships(target_entity_id);
CREATE INDEX idx_extracted_relationships_type ON extracted_relationships(relationship_type);
```

### 3. Knowledge Graph Integration

#### document_entity_mappings
```sql
CREATE TABLE document_entity_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    neo4j_node_id VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_name VARCHAR(1000) NOT NULL,
    relationship_strength DECIMAL(5,4) DEFAULT 1.0,
    mapping_source VARCHAR(50) DEFAULT 'entity_extraction',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(document_id, neo4j_node_id)
);

-- Indexes
CREATE INDEX idx_doc_entity_mappings_document ON document_entity_mappings(document_id);
CREATE INDEX idx_doc_entity_mappings_neo4j_node ON document_entity_mappings(neo4j_node_id);
CREATE INDEX idx_doc_entity_mappings_type ON document_entity_mappings(entity_type);
```

### 4. Processing Logs and Metrics

#### processing_logs
```sql
CREATE TABLE processing_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    job_id UUID REFERENCES document_processing_jobs(id) ON DELETE CASCADE,
    log_level VARCHAR(10) NOT NULL CHECK (log_level IN (
        'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    )),
    message TEXT NOT NULL,
    details JSONB,
    component VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_processing_logs_document_id ON processing_logs(document_id);
CREATE INDEX idx_processing_logs_job_id ON processing_logs(job_id);
CREATE INDEX idx_processing_logs_level ON processing_logs(log_level);
CREATE INDEX idx_processing_logs_created_at ON processing_logs(created_at);
```

#### document_metrics
```sql
CREATE TABLE document_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC,
    metric_unit VARCHAR(50),
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(document_id, metric_name, recorded_at)
);

-- Indexes
CREATE INDEX idx_document_metrics_document_id ON document_metrics(document_id);
CREATE INDEX idx_document_metrics_name ON document_metrics(metric_name);
CREATE INDEX idx_document_metrics_recorded_at ON document_metrics(recorded_at);
```

## Migration Strategy

### Migration 001: Create Document Management Tables
```sql
-- File: database/migrations/006_document_upload_schema.sql
-- This migration adds the document upload and processing schema

-- Add document management tables
-- (Include all CREATE TABLE statements from above)

-- Add foreign key constraints to existing users table
ALTER TABLE documents
ADD CONSTRAINT fk_documents_uploaded_by
FOREIGN KEY (uploaded_by) REFERENCES users(id);
```

### Migration 002: Add Processing Queues
```sql
-- File: database/migrations/007_processing_queue_schema.sql
-- This migration adds processing queue support for async operations

-- Create queue tables for Celery/Redis integration
CREATE TABLE processing_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id VARCHAR(255) UNIQUE,
    task_name VARCHAR(255),
    args JSONB,
    kwargs JSONB,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Data Access Patterns

### Common Queries

1. **Document Status Tracking**
```sql
SELECT d.id, d.filename, d.status, dpj.job_type, dpj.status as job_status
FROM documents d
LEFT JOIN document_processing_jobs dpj ON d.id = dpj.document_id
WHERE d.uploaded_by = $1
ORDER BY d.uploaded_at DESC;
```

2. **Entity Extraction Results**
```sql
SELECT de.entity_text, de.entity_type, de.confidence_score
FROM extracted_entities de
WHERE de.document_id = $1
ORDER BY de.confidence_score DESC;
```

3. **Processing Job Monitoring**
```sql
SELECT dpj.*, d.filename
FROM document_processing_jobs dpj
JOIN documents d ON dpj.document_id = d.id
WHERE dpj.status IN ('pending', 'running')
ORDER BY dpj.priority DESC, dpj.created_at ASC;
```

### Performance Considerations

1. **Partitioning**: Consider partitioning `processing_logs` by date for large datasets
2. **Indexing**: Add composite indexes for common query patterns
3. **Cleanup**: Implement archival strategy for old logs and completed jobs
4. **Connection Pooling**: Configure appropriate pool sizes for high-volume uploads

## Integration Points

### Neo4j Knowledge Graph
- Use `document_entity_mappings` to track relationships between documents and graph entities
- Implement triggers to update Neo4j when entities are extracted
- Store Neo4j node IDs for efficient lookups

### Vector Database (Qdrant)
- Link documents to vector embeddings via metadata
- Track vector indexing status in processing jobs
- Store similarity search results in metrics tables

### File Storage
- Use `file_path` to reference object storage (S3, MinIO)
- Implement cleanup procedures for deleted documents
- Track file versions and deltas for version control

This schema provides a comprehensive foundation for document upload, processing, and knowledge graph integration while maintaining scalability and performance.