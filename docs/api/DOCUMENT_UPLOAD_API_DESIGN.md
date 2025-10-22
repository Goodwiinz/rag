# Document Upload API Design

## Overview

RESTful API design for document upload with automatic knowledge graph population, built on FastAPI with async processing capabilities.

## API Endpoints

### 1. Document Upload Management

#### POST /api/v1/documents/upload
**Description**: Upload one or multiple documents for processing

**Request**: multipart/form-data
```
files: File[] (required) - Array of files to upload
title: string[] (optional) - Custom titles for each file
tags: string[][] (optional) - Tags for each file
batch_id: string (optional) - Group files in a batch
process_immediately: boolean (default: true) - Start processing immediately
```

**Response**: 202 Accepted
```json
{
  "batch_id": "uuid-string",
  "documents": [
    {
      "id": "uuid-string",
      "title": "Document Title",
      "filename": "example.pdf",
      "file_type": "pdf",
      "file_size_bytes": 1024000,
      "status": "uploaded",
      "processing_status": "pending",
      "upload_url": "/api/v1/documents/uuid-string",
      "uploaded_at": "2024-01-01T12:00:00Z"
    }
  ],
  "message": "Documents uploaded successfully and processing started"
}
```

#### GET /api/v1/documents
**Description**: List documents with filtering and pagination

**Query Parameters**:
```
page: int = 1
size: int = 20
status: string[] = ['uploaded', 'processing', 'processed', 'failed']
file_type: string[] = ['pdf', 'txt', 'docx', 'jpg', 'png', 'mp3', 'mp4']
tags: string[] = []
search: string = ""
sort_by: string = "uploaded_at"
sort_order: string = "desc"
uploaded_by: string = ""
date_from: string = ""
date_to: string = ""
```

**Response**: 200 OK
```json
{
  "documents": [
    {
      "id": "uuid-string",
      "title": "Document Title",
      "filename": "example.pdf",
      "file_type": "pdf",
      "file_size_bytes": 1024000,
      "status": "processed",
      "uploaded_at": "2024-01-01T12:00:00Z",
      "uploaded_by": "user-uuid",
      "tags": ["research", "ai"],
      "processing_summary": {
        "entities_extracted": 15,
        "relationships_found": 8,
        "processing_time_seconds": 45
      }
    }
  ],
  "pagination": {
    "page": 1,
    "size": 20,
    "total": 150,
    "pages": 8
  }
}
```

#### GET /api/v1/documents/{document_id}
**Description**: Get detailed document information

**Response**: 200 OK
```json
{
  "id": "uuid-string",
  "title": "Document Title",
  "filename": "example.pdf",
  "original_filename": "research_paper.pdf",
  "file_type": "pdf",
  "file_size_bytes": 1024000,
  "mime_type": "application/pdf",
  "status": "processed",
  "uploaded_at": "2024-01-01T12:00:00Z",
  "uploaded_by": "user-uuid",
  "tags": ["research", "ai"],
  "metadata": {
    "author": "John Doe",
    "created_date": "2024-01-01",
    "page_count": 15
  },
  "processing_jobs": [
    {
      "job_type": "text_extraction",
      "status": "completed",
      "started_at": "2024-01-01T12:01:00Z",
      "completed_at": "2024-01-01T12:02:00Z",
      "result_data": {
        "pages_processed": 15,
        "text_length": 5000
      }
    },
    {
      "job_type": "entity_extraction",
      "status": "completed",
      "started_at": "2024-01-01T12:02:00Z",
      "completed_at": "2024-01-01T12:03:00Z",
      "result_data": {
        "entities_found": 15,
        "relationships_found": 8
      }
    }
  ],
  "download_url": "/api/v1/documents/uuid-string/download",
  "preview_url": "/api/v1/documents/uuid-string/preview"
}
```

#### DELETE /api/v1/documents/{document_id}
**Description**: Delete a document and its processed data

**Response**: 204 No Content

### 2. Processing Status Management

#### GET /api/v1/documents/{document_id}/processing-status
**Description**: Get real-time processing status

**Response**: 200 OK
```json
{
  "document_id": "uuid-string",
  "overall_status": "processing",
  "progress_percentage": 65.0,
  "estimated_remaining_seconds": 30,
  "jobs": [
    {
      "job_type": "text_extraction",
      "status": "completed",
      "progress_percentage": 100.0,
      "started_at": "2024-01-01T12:01:00Z",
      "completed_at": "2024-01-01T12:02:00Z"
    },
    {
      "job_type": "entity_extraction",
      "status": "running",
      "progress_percentage": 60.0,
      "started_at": "2024-01-01T12:02:00Z",
      "estimated_remaining_seconds": 20
    },
    {
      "job_type": "knowledge_graph_population",
      "status": "pending",
      "progress_percentage": 0.0
    }
  ],
  "last_updated": "2024-01-01T12:02:30Z"
}
```

#### POST /api/v1/documents/{document_id}/retry-processing
**Description**: Retry failed processing jobs

**Request Body**:
```json
{
  "job_types": ["entity_extraction", "knowledge_graph_population"],
  "force_retry": false
}
```

**Response**: 202 Accepted
```json
{
  "message": "Processing retry initiated",
  "jobs_retried": ["entity_extraction"],
  "retry_id": "uuid-string"
}
```

#### POST /api/v1/documents/{document_id}/cancel-processing
**Description**: Cancel ongoing processing

**Response**: 200 OK
```json
{
  "message": "Processing cancelled",
  "cancelled_jobs": ["entity_extraction", "knowledge_graph_population"]
}
```

### 3. Entity and Relationship Management

#### GET /api/v1/documents/{document_id}/entities
**Description**: Get extracted entities for a document

**Query Parameters**:
```
entity_type: string = ""
min_confidence: float = 0.0
include_context: boolean = false
page: int = 1
size: int = 50
```

**Response**: 200 OK
```json
{
  "entities": [
    {
      "id": "uuid-string",
      "entity_text": "Artificial Intelligence",
      "entity_type": "CONCEPT",
      "confidence_score": 0.9500,
      "start_position": 150,
      "end_position": 170,
      "context_text": "The field of Artificial Intelligence has evolved rapidly...",
      "neo4j_node_id": "neo4j-node-123",
      "extraction_method": "spacy_ner",
      "created_at": "2024-01-01T12:03:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "size": 50,
    "total": 15,
    "pages": 1
  }
}
```

#### GET /api/v1/documents/{document_id}/relationships
**Description**: Get extracted relationships for a document

**Response**: 200 OK
```json
{
  "relationships": [
    {
      "id": "uuid-string",
      "source_entity": {
        "id": "uuid-string",
        "entity_text": "Artificial Intelligence",
        "entity_type": "CONCEPT"
      },
      "target_entity": {
        "id": "uuid-string",
        "entity_text": "Machine Learning",
        "entity_type": "CONCEPT"
      },
      "relationship_type": "INCLUDES",
      "confidence_score": 0.8700,
      "context_text": "Artificial Intelligence includes Machine Learning...",
      "neo4j_relationship_id": "neo4j-rel-456",
      "created_at": "2024-01-01T12:03:00Z"
    }
  ]
}
```

### 4. Batch Operations

#### POST /api/v1/documents/batch-process
**Description**: Start batch processing for multiple documents

**Request Body**:
```json
{
  "document_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "job_types": ["entity_extraction", "knowledge_graph_population"],
  "priority": 5
}
```

**Response**: 202 Accepted
```json
{
  "batch_id": "uuid-string",
  "jobs_created": 6,
  "message": "Batch processing started"
}
```

#### GET /api/v1/batches/{batch_id}/status
**Description**: Get batch processing status

**Response**: 200 OK
```json
{
  "batch_id": "uuid-string",
  "status": "processing",
  "total_jobs": 6,
  "completed_jobs": 2,
  "failed_jobs": 0,
  "running_jobs": 2,
  "pending_jobs": 2,
  "progress_percentage": 33.3,
  "estimated_completion": "2024-01-01T12:05:00Z"
}
```

### 5. File Management

#### GET /api/v1/documents/{document_id}/download
**Description**: Download original document file

**Query Parameters**:
```
version: int = 1 (for versioned documents)
```

**Response**: 200 OK (file stream)

#### GET /api/v1/documents/{document_id}/preview
**Description**: Get document preview (first page or snippet)

**Response**: 200 OK
```json
{
  "preview_type": "text",
  "content": "This is the first 500 characters of the document...",
  "page_count": 15,
  "preview_image_url": "/api/v1/documents/uuid-string/preview-image" (for PDFs/images)
}
```

#### GET /api/v1/documents/{document_id}/preview-image
**Description**: Get document preview as image

**Response**: 200 OK (image stream)

## WebSocket API

### /ws/documents/{document_id}/processing-status
**Description**: Real-time processing status updates

**Message Format**:
```json
{
  "type": "processing_update",
  "document_id": "uuid-string",
  "job_type": "entity_extraction",
  "status": "running",
  "progress_percentage": 45.0,
  "message": "Extracting entities from page 3 of 15",
  "timestamp": "2024-01-01T12:02:30Z"
}
```

## Authentication & Authorization

### Authentication
- JWT Bearer tokens required for all endpoints
- Token includes user_id, permissions, and session info

### Authorization
- Users can only access their own documents
- Admin users can access all documents
- Permissions: `documents:read`, `documents:write`, `documents:delete`, `processing:manage`

## Error Handling

### Standard Error Response Format
```json
{
  "error": {
    "type": "validation_error",
    "message": "Invalid file format",
    "details": {
      "field": "files",
      "allowed_types": ["pdf", "txt", "docx", "jpg", "png", "mp3", "mp4"],
      "received_type": "exe"
    },
    "error_code": "INVALID_FILE_TYPE",
    "timestamp": "2024-01-01T12:00:00Z"
  }
}
```

### Common Error Codes
- `INVALID_FILE_TYPE`: Unsupported file format
- `FILE_TOO_LARGE`: File exceeds size limit
- `DOCUMENT_NOT_FOUND`: Document ID doesn't exist
- `PROCESSING_FAILED`: Background job failed
- `INSUFFICIENT_PERMISSIONS`: User lacks required permissions
- `RATE_LIMIT_EXCEEDED`: Too many requests

## Rate Limiting

### Upload Limits
- 100 files per hour per user
- 1GB total size per hour per user
- 10 concurrent processing jobs per user

### API Limits
- 1000 requests per hour per user
- 100 requests per minute per IP

## Data Models

### DocumentUploadRequest
```python
from pydantic import BaseModel
from typing import List, Optional

class DocumentUploadRequest(BaseModel):
    title: Optional[str] = None
    tags: List[str] = []
    batch_id: Optional[str] = None
    process_immediately: bool = True
```

### DocumentResponse
```python
class DocumentResponse(BaseModel):
    id: str
    title: str
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    uploaded_at: datetime
    uploaded_by: str
    tags: List[str] = []
    processing_summary: Optional[Dict] = None
```

### ProcessingStatusResponse
```python
class ProcessingStatusResponse(BaseModel):
    document_id: str
    overall_status: str
    progress_percentage: float
    estimated_remaining_seconds: Optional[int]
    jobs: List[ProcessingJobResponse]
    last_updated: datetime
```

## Implementation Notes

### File Storage
- Use streaming uploads for large files
- Store files in MinIO/S3 with metadata
- Implement checksum validation
- Support resumable uploads for large files

### Background Processing
- Use Celery with Redis broker
- Implement job priorities and retries
- Monitor job queue health
- Support graceful shutdown

### Monitoring & Metrics
- Track upload success rates
- Monitor processing times
- Alert on failed jobs
- Log performance metrics

This API design provides comprehensive document upload and processing capabilities with real-time status tracking and seamless integration with the knowledge graph system.