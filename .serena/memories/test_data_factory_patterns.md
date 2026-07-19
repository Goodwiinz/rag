# Test Data Factory Implementation Patterns

## Overview
Complete factory for generating realistic test data across multiple document types and processing job types.

## File Structure: `tests/factories/document_factory.py`

### Config Dataclasses (Top-Level)
1. **DocumentConfig** - Customize document creation
   - Fields: title, filename, file_type, file_size_bytes, processing_status, etc.
   - All fields optional with sensible defaults
   - Enables easy customization while maintaining defaults

2. **ProcessingJobConfig** - Customize job parameters
   - Fields: job_type, status, priority, document_id, parameters, config, etc.
   - Includes timestamps for realistic job lifecycles

3. **QualityMetricConfig** - Customize quality assessments
   - Fields: overall_score, readability_score, content_quality_score, etc.
   - Supports custom recommendations and issues

### FILE_TYPE_CONFIGS Dictionary

Maps DocumentType to metadata configurations:

```python
{
    DocumentType.PDF: {
        'extensions': ['.pdf'],
        'mime_types': ['application/pdf'],
        'size_range': (50 * 1024, 50 * 1024 * 1024),
        'has_pages': True,
        'has_duration': False
    },
    DocumentType.AUDIO: {
        'extensions': ['.mp3', '.wav', '.ogg', '.m4a'],
        'mime_types': ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg'],
        'size_range': (100 * 1024, 100 * 1024 * 1024),
        'has_pages': False,
        'has_duration': True
    },
    # ... similar for TEXT, IMAGE, VIDEO
}
```

### Core Factory Methods

#### 1. create_document(config) -> Document
- Generates unique ID (uuid4)
- Creates realistic filename from title
- Generates file size in type-specific range
- Generates MIME type from config
- Creates type-specific metadata (pages for PDF, resolution for Image, etc.)
- Generates thumbnail URL for PDF and Image
- Returns fully populated Document instance

#### 2. create_batch_documents(count, config) -> List[Document]
- Creates `count` documents
- Adds variation in processing_status across batch
- Adds variation in file_type if base config allows
- Appends index to title (Document 1, Document 2, etc.)
- Respects config overrides while varying others

#### 3. create_processing_job(config) -> ProcessingJob
- Generates realistic timestamps (now, started_at, completed_at)
- Creates job-type-specific parameters (see `_generate_job_parameters`)
- Creates job-type-specific config (see `_generate_job_config`)
- Handles job lifecycle (PENDING -> IN_PROGRESS -> COMPLETED)
- Includes progress tracking (completed_steps/total_steps)

#### 4. create_quality_assessment(config) -> QualityMetric
- Generates 4 quality scores: overall, readability, content, technical
- Score-based recommendations (lower score = more recommendations)
- Score-based issues (lower score = more issues)
- Generates processing time (500-5000ms)

#### 5. create_document_with_job_and_quality() -> Dict
- Creates integrated pipeline: Document + ProcessingJob + QualityMetric
- Links Job to Document by ID
- Aligns Job status with Document processing_status
- Creates Quality assessment only if Document is COMPLETED
- Returns dict with all three entities

### Helper Methods

#### _generate_title(file_type) -> str
- Type-specific title templates (PDF, TEXT, IMAGE, AUDIO, VIDEO)
- Faker-based realistic values (catch_phrases, names, dates)
- Examples:
  - PDF: "Annual Report 2023", "Technical Documentation: Machine Learning"
  - Audio: "Meeting Recording 2026-01-27", "Podcast Episode 42"
  - Video: "Product Demo MacBook", "Tutorial Introduction to Python"

#### _generate_filename(title, file_type) -> str
- Cleans title (lowercase, replace spaces with underscores)
- Adds type-appropriate extension
- Adds random suffix for uniqueness
- Example: "technical_documentation_machine_learning_7382.pdf"

#### _generate_custom_metadata(file_type) -> Dict
- Base metadata: upload_source, device, client_version, timezone, language
- Type-specific metadata:
  - PDF: pdf_version, has_forms, has_annotations, is_encrypted, creation_tool
  - Text: encoding, line_endings, word_count, character_count
  - Image: camera_make, resolution, color_space, has_exif, bit_depth
  - Audio: bitrate, sample_rate, codec, has_album_art
  - Video: resolution, frame_rate, codec, has_audio, file_size_mb

#### _generate_job_parameters(job_type) -> Dict
- Base params: retry_count, timeout_seconds, worker_id, queue_name
- DOCUMENT_INGESTION: enable_ocr, enable_entity_extraction, chunk_size, ocr_languages
- QUALITY_ASSESSMENT: assessment_model, include_detailed_analysis
- INDEXING: index_type, embedding_model, vector_dimension, index_name

#### _generate_job_config(job_type) -> Dict
- Base config: max_retries, priority_weight, resource_allocation, logging_level
- DOCUMENT_INGESTION: ocr_engine, entity_extraction_model, chunking_strategy
- QUALITY_ASSESSMENT: quality_threshold, detailed_logging, cache_results
- INDEXING: index_strategy, bulk_size, refresh_interval, number_of_shards

#### _generate_recommendations(overall_score) -> List[str]
- Number of recommendations inversely proportional to score
- Formula: `int((1.0 - score) * 10)` recommendations
- Examples: "Improve document structure", "Add more descriptive sections", etc.

#### _generate_quality_issues(overall_score) -> List[Dict]
- Number of issues inversely proportional to score
- Each issue has: type, severity, description, suggestion, id, location
- Severity levels: low, medium, high

### Convenience Functions

#### create_sample_document_collection(org_id, user_id, count) -> List[Document]
- Quick way to create test collection
- Uses provided org_id and user_id for all documents
- Sets is_public=False, is_deleted=False by default

#### create_document_processing_pipeline(doc_id, org_id, user_id) -> Dict
- Creates Document with PROCESSING status
- Creates ProcessingJob with IN_PROGRESS status (3/8 steps done)
- Returns dict with both entities

#### create_failed_document_processing(doc_id, org_id, user_id) -> Dict
- Creates Document with FAILED status
- Creates ProcessingJob with FAILED status and error message
- Simulates OCR failure scenario

## Usage Examples

```python
# Simple document
doc = DocumentFactory.create_document()

# Custom document
config = DocumentConfig(
    title="My Custom PDF",
    file_type=DocumentType.PDF,
    processing_status=ProcessingStatus.COMPLETED
)
doc = DocumentFactory.create_document(config)

# Batch with variations
docs = DocumentFactory.create_batch_documents(10)

# Complete pipeline
pipeline = DocumentFactory.create_document_with_job_and_quality()
doc = pipeline['document']
job = pipeline['processing_job']
quality = pipeline['quality_assessment']
```

## Key Design Principles

1. **Realistic Data**: All generated data matches real-world ranges and formats
2. **Type Safety**: Specific metadata for each file type
3. **Customizable**: Config pattern allows overrides while maintaining defaults
4. **Variation**: Batch creation adds variation across items
5. **Linked Entities**: Job links to Document, Quality links to both
6. **Score-Based Generation**: Recommendations/issues correlate with scores

Tags: #pattern #testing #factory #document #job
