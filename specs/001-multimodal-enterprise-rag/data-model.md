# Data Model: Multimodal Enterprise RAG System

**Date**: 2025-10-07
**Purpose**: Entity definitions, relationships, and validation rules

## Entity Relationship Overview

```
User Account (1) -----> (N) Organization
User Account (1) -----> (N) Search Query
User Account (1) -----> (N) Document Upload
Organization (1) -----> (N) Storage Tier

Document (1) -----> (N) Processing Job
Document (1) -----> (N) Entity
Document (1) -----> (N) Search Result

Entity (N) -----> (N) Entity Relationship
Search Query (1) -----> (N) Search Result
Search Result (1) -----> (N) Quality Metric

Processing Job (1) -----> (N) Job Step
Job Step (N) -----> (1) Error Log
```

## Core Entities

### User Account

Represents authenticated users in the system.

**Fields**:
- `id`: UUID (Primary Key)
- `email`: string (Unique, Required)
- `password_hash`: string (Required)
- `first_name`: string (Required)
- `last_name`: string (Required)
- `role`: enum (admin, content_manager, user, analyst) (Required)
- `organization_id`: UUID (Foreign Key)
- `is_active`: boolean (Default: true)
- `last_login`: timestamp
- `created_at`: timestamp
- `updated_at`: timestamp

**Validation Rules**:
- Email format validation
- Password minimum 8 characters with complexity requirements
- Role-based permission validation
- Unique email constraint

**State Transitions**:
- `pending` → `active` → `suspended` → `deleted`

### Organization

Represents tenant organizations for multi-tenancy.

**Fields**:
- `id`: UUID (Primary Key)
- `name`: string (Required, Max 255 chars)
- `storage_tier`: enum (free, professional, enterprise) (Required)
- `storage_used_bytes`: integer (Default: 0)
- `storage_limit_bytes`: integer (Required)
- `is_active`: boolean (Default: true)
- `created_at`: timestamp
- `updated_at`: timestamp

**Validation Rules**:
- Organization name uniqueness
- Storage limits enforced per tier
- Cannot exceed storage quota

### Document

Represents uploaded files and their processed content.

**Fields**:
- `id`: UUID (Primary Key)
- `filename`: string (Required)
- `original_filename`: string (Required)
- `file_type`: enum (pdf, txt, jpg, png, mp3, wav, mp4, avi, mov) (Required)
- `modality`: enum (text, image, audio, video) (Required)
- `file_size_bytes`: integer (Required)
- `content_type`: string (MIME type)
- `storage_path`: string (Required)
- `uploaded_by`: UUID (Foreign Key to User Account)
- `organization_id`: UUID (Foreign Key)
- `processing_status`: enum (pending, processing, completed, failed) (Required)
- `extracted_text`: text
- `entity_count`: integer (Default: 0)
- `processing_started_at`: timestamp
- `processing_completed_at`: timestamp
- `created_at`: timestamp
- `updated_at`: timestamp

**Validation Rules**:
- File type validation against allowed formats
- File size limits (10MB for free tier)
- Content extraction validation
- Processing status state machine validation

**State Transitions**:
- `pending` → `processing` → `completed`
- `pending` → `processing` → `failed` → `pending` (retry)

### Entity

Represents named entities extracted from documents.

**Fields**:
- `id`: UUID (Primary Key)
- `name`: string (Required, Max 255 chars)
- `entity_type`: enum (person, organization, location, concept, product, date) (Required)
- `confidence_score`: float (0.0-1.0, Required)
- `document_id`: UUID (Foreign Key)
- `source_modality`: enum (text, image, audio, video) (Required)
- `context_snippet`: text
- `start_position`: integer
- `end_position`: integer
- `created_at`: timestamp

**Validation Rules**:
- Entity name required and non-empty
- Confidence score between 0.0 and 1.0
- Valid document reference
- Position validation within document content

### Search Query

Represents user search requests.

**Fields**:
- `id`: UUID (Primary Key)
- `query_text`: string (Required, Min 2 chars, Max 1000 chars)
- `user_id`: UUID (Foreign Key)
- `organization_id`: UUID (Foreign Key)
- `filters`: JSON object (Content type, date range, etc.)
- `result_count`: integer
- `execution_time_ms`: integer
- `created_at`: timestamp

**Validation Rules**:
- Query text length validation
- Filter schema validation
- User authentication required
- Organization access validation

### Search Result

Represents individual results from search queries.

**Fields**:
- `id`: UUID (Primary Key)
- `search_query_id`: UUID (Foreign Key)
- `document_id`: UUID (Foreign Key)
- `relevance_score`: float (0.0-1.0, Required)
- `result_summary`: text (2-3 sentences)
- `result_modality`: enum (text, image, audio, video)
- `rank_position`: integer
- `created_at`: timestamp

**Validation Rules**:
- Relevance score range validation
- Required document reference
- Unique rank per query
- Summary length validation (50-300 characters)

## Processing Entities

### Processing Job

Represents background processing tasks for documents.

**Fields**:
- `id`: UUID (Primary Key)
- `document_id`: UUID (Foreign Key)
- `job_type`: enum (text_extraction, ocr, transcription, image_analysis, video_processing)
- `status`: enum (queued, running, completed, failed, cancelled)
- `progress_percentage`: integer (0-100)
- `error_message`: text
- `retry_count`: integer (Default: 0)
- `max_retries`: integer (Default: 3)
- `started_at`: timestamp
- `completed_at`: timestamp
- `created_at`: timestamp

**Validation Rules**:
- Retry limit enforcement
- Progress range validation
- Status transition validation
- Job type compatibility with document modality

**State Transitions**:
- `queued` → `running` → `completed`
- `queued` → `running` → `failed` → `queued` (if retry_available)
- `any` → `cancelled`

### Quality Metric

Represents automated quality measurements.

**Fields**:
- `id`: UUID (Primary Key)
- `search_query_id`: UUID (Foreign Key)
- `metric_type`: enum (answer_relevancy, factual_accuracy, contextual_precision, response_time)
- `score`: float (0.0-1.0)
- `threshold_met`: boolean
- `measured_at`: timestamp

**Validation Rules**:
- Score range validation
- Threshold comparison logic
- Metric type validation
- Search query reference required

## Configuration Entities

### Storage Tier

Defines storage limits and features per tier.

**Fields**:
- `id`: UUID (Primary Key)
- `tier_name`: enum (free, professional, enterprise) (Required)
- `storage_limit_gb`: integer (Required)
- `max_file_size_mb`: integer (Required)
- `features`: JSON array (advanced_analytics, priority_processing, api_access)
- `price_monthly`: decimal
- `is_active`: boolean (Default: true)

**Validation Rules**:
- Tier name uniqueness
- Storage limit positive values
- Feature set validation per tier

## Indexes and Performance

### Primary Indexes

1. **User Account**: `email` (unique), `organization_id`
2. **Document**: `organization_id`, `processing_status`, `file_type`
3. **Entity**: `document_id`, `entity_type`, `name`
4. **Search Query**: `user_id`, `organization_id`, `created_at`
5. **Search Result**: `search_query_id`, `relevance_score`
6. **Processing Job**: `document_id`, `status`, `created_at`

### Full-Text Search Indexes

1. **Document**: `extracted_text` (PostgreSQL full-text)
2. **Entity**: `name`, `context_snippet`
3. **Search Query**: `query_text`

### Vector Indexes

1. **Document**: Embedding vectors in Qdrant
2. **Entity**: Entity embedding vectors in Qdrant

## Data Integrity Constraints

### Foreign Key Constraints

1. Document uploads require valid user and organization
2. Entities must reference existing documents
3. Search queries require authenticated users
4. Search results must reference existing queries and documents

### Business Logic Constraints

1. Storage quota enforcement per organization
2. File type compatibility with processing jobs
3. Search result ranking uniqueness per query
4. Processing job retry limits

### Cascade Rules

1. Deleting user cascades to their search queries
2. Deleting document cascades to entities and processing jobs
3. Deleting organization cascades to users and documents
4. Deleting search query cascades to search results

## Security Considerations

### Access Control

1. **Row-Level Security**: Users can only access their organization's data
2. **Role-Based Permissions**: Different access levels per user role
3. **API Rate Limiting**: Prevent abuse of search and upload endpoints

### Data Protection

1. **Encryption**: Sensitive fields encrypted at rest
2. **Audit Logging**: All data modifications logged
3. **Data Retention**: Automatic cleanup of old search queries and results

### Privacy

1. **User Data**: Personal information protected and anonymized where possible
2. **Content Access**: Document access restricted by organization boundaries
3. **Search Privacy**: Search queries not shared between organizations

## Migration Strategy

### Version 1.0 (Initial)

1. Core entities: User, Organization, Document, Entity
2. Basic search functionality
3. Simple processing pipeline

### Version 1.1 (Enhanced)

1. Quality metrics and evaluation
2. Advanced search filtering
3. Processing job management

### Version 2.0 (Scale)

1. Multi-modal relationship mapping
2. Advanced analytics
3. Enterprise features (SSO, advanced RBAC)

## Testing Strategy

### Unit Tests

1. Entity validation rules
2. Business logic constraints
3. State transition validation

### Integration Tests

1. Database relationship integrity
2. Cascade delete behavior
3. Performance with large datasets

### Contract Tests

1. API response schemas
2. Database contract compliance
3. External service integration