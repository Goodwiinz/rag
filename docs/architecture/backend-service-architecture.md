# Backend Service Architecture: Multimodal Enterprise RAG System

**Version**: 1.0.0
**Date**: 2025-10-19
**Author**: Claude Code Assistant

## Executive Summary

The Multimodal Enterprise RAG System employs a microservices architecture with clear service boundaries, API-first design, and comprehensive observability. The system supports text, image, audio, and video processing with hybrid search capabilities, knowledge graph analysis, and real-time evaluation metrics.

## Architecture Overview

### Design Principles

1. **API-First Design**: All services expose OpenAPI 3.0 compliant REST APIs
2. **Microservices Architecture**: Clear service boundaries with independent scalability
3. **Event-Driven Processing**: Asynchronous processing with message queues
4. **Multi-Tenancy**: Complete data isolation between organizations
5. **Security-First**: Zero-trust architecture with defense-in-depth
6. **Observability**: Comprehensive monitoring, logging, and tracing
7. **Resilience**: Circuit breakers, retries, and graceful degradation

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            API Gateway & Load Balancer                         │
│                               (Kong/Nginx/Envoy)                              │
└─────────────────────────┬───────────────────────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────────────────────┐
│                            Authentication & Authorization                        │
│                     (JWT + RBAC + Rate Limiting + Audit)                        │
└─────────────────────────┬───────────────────────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────────────────────┐
│                              Message Queue Layer                                │
│                           (Redis Streams + RabbitMQ)                           │
└─────────────────────────┬───────────────────────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────────────────────┐
│                            Core Backend Services                                │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌─────────────────────┐ │
│  │  Document     │ │   Search      │ │  Knowledge    │ │   Evaluation        │ │
│  │  Management   │ │   Services    │ │   Graph       │ │   Services          │ │
│  │               │ │               │ │   Services    │ │                     │ │
│  └───────────────┘ └───────────────┘ └───────────────┘ └─────────────────────┘ │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌─────────────────────┐ │
│  │  Processing   │ │  Analytics    │ │   User        │ │   Real-time         │ │
│  │   Pipeline    │ │   Services    │ │  Management   │ │   Communications    │ │
│  │               │ │               │ │   Services    │ │   (WebSocket)       │ │
│  └───────────────┘ └───────────────┘ └───────────────┘ └─────────────────────┘ │
└─────────────────────────┬───────────────────────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────────────────────┐
│                            Data Storage Layer                                   │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌─────────────────────┐ │
│  │   PostgreSQL  │ │     Neo4j     │ │    Qdrant     │ │       Redis         │ │
│  │ (Metadata &  │ │  (Knowledge   │ │  (Vector      │ │    (Cache &         │ │
│  │  User Data)   │ │    Graph)     │ │   Store)      │ │  Message Queue)    │ │
│  └───────────────┘ └───────────────┘ └───────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Service Architecture

### 1. API Gateway Service
**Port**: 8080
**Responsibilities**:
- Request routing and load balancing
- Authentication and authorization
- Rate limiting and throttling
- Request/response transformation
- API versioning
- CORS handling
- SSL termination

**Key Endpoints**:
```
/api/v1/*  → Route to appropriate microservice
/auth/*    → Authentication service
/health    → Health check endpoint
/metrics   → Prometheus metrics
```

### 2. Document Management Service
**Port**: 8001
**Responsibilities**:
- File upload and validation
- Document metadata management
- Storage quota enforcement
- Document lifecycle management
- Multi-modal file processing
- Content extraction and indexing

**API Endpoints**:
```yaml
openapi: 3.0.3
info:
  title: Document Management API
  version: 1.0.0
paths:
  /api/v1/documents:
    post:
      summary: Upload documents
      requestBody:
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                files:
                  type: array
                  items:
                    type: string
                    format: binary
      responses:
        '201':
          description: Documents uploaded successfully
        '400':
          description: Invalid file format or size
        '409':
          description: Storage quota exceeded

    get:
      summary: List documents
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: limit
          in: query
          schema:
            type: integer
            default: 20
        - name: document_type
          in: query
          schema:
            type: string
            enum: [pdf, txt, jpg, png, mp3, mp4]
        - name: processing_status
          in: query
          schema:
            type: string
            enum: [queued, processing, indexed, failed]
      responses:
        '200':
          description: List of documents
          content:
            application/json:
              schema:
                type: object
                properties:
                  documents:
                    type: array
                    items:
                      $ref: '#/components/schemas/Document'
                  pagination:
                    $ref: '#/components/schemas/Pagination'

  /api/v1/documents/{document_id}:
    get:
      summary: Get document details
      parameters:
        - name: document_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Document details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DocumentDetail'
        '404':
          description: Document not found

    delete:
      summary: Delete document
      parameters:
        - name: document_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '204':
          description: Document deleted
        '404':
          description: Document not found

  /api/v1/documents/{document_id}/processing-status:
    get:
      summary: Get document processing status
      parameters:
        - name: document_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Processing status
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProcessingStatus'

components:
  schemas:
    Document:
      type: object
      properties:
        id:
          type: string
          format: uuid
        title:
          type: string
        filename:
          type: string
        document_type:
          type: string
          enum: [pdf, txt, jpg, png, mp3, mp4]
        file_size_bytes:
          type: integer
        file_size_mb:
          type: number
        mime_type:
          type: string
        processing_status:
          type: string
          enum: [queued, processing, indexed, failed]
        tags:
          type: array
          items:
            type: string
        is_public:
          type: boolean
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    DocumentDetail:
      allOf:
        - $ref: '#/components/schemas/Document'
        - type: object
          properties:
            content_text:
              type: string
            metadata:
              type: object
            processing_started_at:
              type: string
              format: date-time
            processing_completed_at:
              type: string
              format: date-time
            processing_error:
              type: string
            processing_retry_count:
              type: integer

    ProcessingStatus:
      type: object
      properties:
        document_id:
          type: string
        status:
          type: string
          enum: [queued, processing, indexed, failed]
        current_stage:
          type: string
          enum: [uploading, extracting, analyzing, embedding, indexing, completed, failed]
        progress_percentage:
          type: number
          minimum: 0
          maximum: 100
        estimated_completion:
          type: string
          format: date-time
        error_message:
          type: string
        retry_count:
          type: integer

    Pagination:
      type: object
      properties:
        page:
          type: integer
        limit:
          type: integer
        total:
          type: integer
        total_pages:
          type: integer
```

### 3. Search Service
**Port**: 8002
**Responsibilities**:
- Hybrid search orchestration (vector + graph + keyword)
- Query parsing and intent detection
- Result ranking and relevance scoring
- Search analytics and performance tracking
- Faceted search and filtering

**API Endpoints**:
```yaml
openapi: 3.0.3
info:
  title: Search API
  version: 1.0.0
paths:
  /api/v1/search:
    post:
      summary: Perform hybrid search
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SearchQuery'
      responses:
        '200':
          description: Search results
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/SearchResponse'

  /api/v1/search/suggestions:
    get:
      summary: Get search suggestions
      parameters:
        - name: q
          in: query
          required: true
          schema:
            type: string
        - name: limit
          in: query
          schema:
            type: integer
            default: 5
      responses:
        '200':
          description: Search suggestions
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/SearchSuggestion'

components:
  schemas:
    SearchQuery:
      type: object
      properties:
        query:
          type: string
          description: Natural language search query
        search_type:
          type: string
          enum: [hybrid, vector, graph, keyword]
          default: hybrid
        filters:
          $ref: '#/components/schemas/SearchFilters'
        limit:
          type: integer
          default: 10
          maximum: 50
        offset:
          type: integer
          default: 0
        include_metadata:
          type: boolean
          default: true
        sort_by:
          type: string
          enum: [relevance, date, title]
          default: relevance

    SearchFilters:
      type: object
      properties:
        document_types:
          type: array
          items:
            type: string
            enum: [pdf, txt, jpg, png, mp3, mp4]
        date_range:
          type: object
          properties:
            start:
              type: string
              format: date
            end:
              type: string
              format: date
        tags:
          type: array
          items:
            type: string
        file_size_range:
          type: object
          properties:
            min_mb:
              type: number
            max_mb:
              type: number

    SearchResponse:
      type: object
      properties:
        query:
          type: string
        search_id:
          type: string
          format: uuid
        total_results:
          type: integer
        search_time_ms:
          type: number
        results:
          type: array
          items:
            $ref: '#/components/schemas/SearchResult'
        facets:
          type: object
        query_classification:
          $ref: '#/components/schemas/QueryClassification'

    SearchResult:
      type: object
      properties:
        document_id:
          type: string
        title:
          type: string
        content_snippet:
          type: string
        relevance_score:
          type: number
          minimum: 0
          maximum: 1
        document_type:
          type: string
        matched_content:
          type: array
          items:
            type: object
            properties:
              content:
                type: string
              content_type:
                type: string
              relevance_score:
                type: number
        metadata:
          type: object

    QueryClassification:
      type: object
      properties:
        intent:
          type: string
          enum: [lookup, reasoning, comparison, temporal, causal]
        confidence:
          type: number
          minimum: 0
          maximum: 1
        entities:
          type: array
          items:
            type: object
            properties:
              text:
                type: string
              type:
                type: string
              confidence:
                type: number

    SearchSuggestion:
      type: object
      properties:
        text:
          type: string
        type:
          type: string
          enum: [autocomplete, correction, expansion]
        score:
          type: number
```

### 4. Knowledge Graph Service
**Port**: 8003
**Responsibilities**:
- Entity extraction and relationship mapping
- Graph algorithms (centrality, pathfinding, clustering)
- Knowledge graph visualization data
- Entity-based search and navigation
- Graph analytics and insights

**API Endpoints**:
```yaml
openapi: 3.0.3
info:
  title: Knowledge Graph API
  version: 1.0.0
paths:
  /api/v1/knowledge-graph/entities:
    get:
      summary: Get entities with filters
      parameters:
        - name: entity_type
          in: query
          schema:
            type: string
        - name: limit
          in: query
          schema:
            type: integer
            default: 100
        - name: min_connections
          in: query
          schema:
            type: integer
            default: 1
      responses:
        '200':
          description: List of entities
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Entity'

  /api/v1/knowledge-graph/graph:
    get:
      summary: Get knowledge graph data
      parameters:
        - name: center_entity_id
          in: query
          schema:
            type: string
        - name: depth
          in: query
          schema:
            type: integer
            default: 2
            maximum: 5
        - name: entity_types
          in: query
          schema:
            type: array
            items:
              type: string
        - name: relationship_types
          in: query
          schema:
            type: array
            items:
              type: string
      responses:
        '200':
          description: Graph data
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GraphData'

  /api/v1/knowledge-graph/entities/{entity_id}:
    get:
      summary: Get entity details
      parameters:
        - name: entity_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Entity details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/EntityDetail'

  /api/v1/knowledge-graph/analytics:
    get:
      summary: Get graph analytics
      parameters:
        - name: analysis_type
          in: query
          schema:
            type: string
            enum: [centrality, communities, paths, clusters]
        - name: document_ids
          in: query
          schema:
            type: array
            items:
              type: string
      responses:
        '200':
          description: Graph analytics
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/GraphAnalytics'

components:
  schemas:
    Entity:
      type: object
      properties:
        id:
          type: string
        name:
          type: string
        type:
          type: string
        confidence:
          type: number
          minimum: 0
          maximum: 1
        document_count:
          type: integer
        connection_count:
          type: integer
        created_at:
          type: string
          format: date-time

    EntityDetail:
      allOf:
        - $ref: '#/components/schemas/Entity'
        - type: object
          properties:
            description:
              type: string
            aliases:
              type: array
              items:
                type: string
            attributes:
              type: object
            related_entities:
              type: array
              items:
                $ref: '#/components/schemas/RelatedEntity'
            temporal_data:
              type: object
              properties:
                first_mentioned:
                  type: string
                  format: date-time
                last_mentioned:
                  type: string
                  format: date-time
                mention_frequency:
                  type: integer

    RelatedEntity:
      type: object
      properties:
        entity:
          $ref: '#/components/schemas/Entity'
        relationship_type:
          type: string
        relationship_strength:
          type: number
          minimum: 0
          maximum: 1
        context_snippets:
          type: array
          items:
            type: string

    GraphData:
      type: object
      properties:
        nodes:
          type: array
          items:
            type: object
            properties:
              id:
                type: string
              label:
                type: string
              type:
                type: string
              size:
                type: number
              color:
                type: string
              metadata:
                type: object
        edges:
          type: array
          items:
            type: object
            properties:
              source:
                type: string
              target:
                type: string
              label:
                type: string
              weight:
                type: number
              strength:
                type: number
        layout:
          type: object
          properties:
            algorithm:
              type: string
            positions:
              type: object
        statistics:
          $ref: '#/components/schemas/GraphStatistics'

    GraphStatistics:
      type: object
      properties:
        total_nodes:
          type: integer
        total_edges:
          type: integer
        average_degree:
          type: number
        density:
          type: number
        connected_components:
          type: integer
        largest_component_size:
          type: integer

    GraphAnalytics:
      type: object
      properties:
        analysis_type:
          type: string
        results:
          type: object
        generated_at:
          type: string
          format: date-time
        confidence_scores:
          type: object
```

### 5. Evaluation Service
**Port**: 8004
**Responsibilities**:
- RAG Triad metrics calculation (Answer Relevancy, Faithfulness, Contextual Relevancy)
- Query performance evaluation
- Quality trend analysis
- Benchmark testing
- A/B testing framework

**API Endpoints**:
```yaml
openapi: 3.0.3
info:
  title: Evaluation API
  version: 1.0.0
paths:
  /api/v1/evaluation/metrics:
    post:
      summary: Calculate RAG Triad metrics
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/EvaluationRequest'
      responses:
        '200':
          description: Evaluation metrics
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/EvaluationMetrics'

  /api/v1/evaluation/performance:
    get:
      summary: Get system performance metrics
      parameters:
        - name: time_range
          in: query
          schema:
            type: string
            enum: [1h, 24h, 7d, 30d]
            default: 24h
        - name: metric_types
          in: query
          schema:
            type: array
            items:
              type: string
              enum: [latency, accuracy, relevance, throughput]
      responses:
        '200':
          description: Performance metrics
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PerformanceMetrics'

  /api/v1/evaluation/benchmarks:
    post:
      summary: Run benchmark tests
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/BenchmarkRequest'
      responses:
        '202':
          description: Benchmark started
          content:
            application/json:
              schema:
                type: object
                properties:
                  benchmark_id:
                    type: string
                    format: uuid
                  estimated_duration:
                    type: string

components:
  schemas:
    EvaluationRequest:
      type: object
      properties:
        query_id:
          type: string
        question:
          type: string
        answer:
          type: string
        retrieved_context:
          type: array
          items:
            type: object
            properties:
              content:
                type: string
              source:
                type: string
              relevance_score:
                type: number
        ground_truth:
          type: string
          description: Optional ground truth answer for comparison

    EvaluationMetrics:
      type: object
      properties:
        query_id:
          type: string
        evaluation_id:
          type: string
          format: uuid
        rag_triad:
          $ref: '#/components/schemas/RAGTriadMetrics'
        quality_metrics:
          $ref: '#/components/schemas/QualityMetrics'
        performance_metrics:
          $ref: '#/components/schemas/QueryPerformanceMetrics'
        generated_at:
          type: string
          format: date-time

    RAGTriadMetrics:
      type: object
      properties:
        answer_relevancy:
          type: object
          properties:
            score:
              type: number
              minimum: 0
              maximum: 1
            threshold:
              type: number
              default: 0.7
            status:
              type: string
              enum: [pass, fail, warning]
        faithfulness:
          type: object
          properties:
            score:
              type: number
              minimum: 0
              maximum: 1
            threshold:
              type: number
              default: 0.9
            status:
              type: string
              enum: [pass, fail, warning]
        contextual_relevancy:
          type: object
          properties:
            score:
              type: number
              minimum: 0
              maximum: 1
            threshold:
              type: number
              default: 0.7
            status:
              type: string
              enum: [pass, fail, warning]

    QualityMetrics:
      type: object
      properties:
        coherence:
          type: number
          minimum: 0
          maximum: 1
        completeness:
          type: number
          minimum: 0
          maximum: 1
        conciseness:
          type: number
          minimum: 0
          maximum: 1
        hallucination_rate:
          type: number
          minimum: 0
          maximum: 1
        source_diversity:
          type: number
          minimum: 0
          maximum: 1

    QueryPerformanceMetrics:
      type: object
      properties:
        total_latency_ms:
          type: number
        search_latency_ms:
          type: number
        generation_latency_ms:
          type: number
        retrieval_count:
          type: integer
        model_tokens_used:
          type: object
          properties:
            input:
              type: integer
            output:
              type: integer
            total:
              type: integer
        cache_hit_rate:
          type: number
          minimum: 0
          maximum: 1

    PerformanceMetrics:
      type: object
      properties:
        time_range:
          type: string
        metrics:
          type: object
          properties:
            avg_latency_ms:
              type: number
            p95_latency_ms:
              type: number
            p99_latency_ms:
              type: number
            throughput_qps:
              type: number
            error_rate:
              type: number
            availability:
              type: number
        trends:
          type: array
          items:
            type: object
            properties:
              timestamp:
                type: string
                format: date-time
              metric_name:
                type: string
              value:
                type: number

    BenchmarkRequest:
      type: object
      properties:
        benchmark_type:
          type: string
          enum: [rag_triad, performance, stress, scalability]
        test_dataset:
          type: string
          description: Name of test dataset to use
        parameters:
          type: object
          properties:
            concurrent_users:
              type: integer
            duration_minutes:
              type: integer
            query_types:
              type: array
              items:
                type: string
```

### 6. Processing Pipeline Service
**Port**: 8005
**Responsibilities**:
- Multi-modal file processing orchestration
- OCR, transcription, and content extraction
- Entity extraction and relationship mapping
- Vector embedding generation
- Progress tracking and error handling
- Retry logic with exponential backoff

**API Endpoints**:
```yaml
openapi: 3.0.3
info:
  title: Processing Pipeline API
  version: 1.0.0
paths:
  /api/v1/processing/jobs:
    post:
      summary: Submit processing job
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ProcessingJobRequest'
      responses:
        '201':
          description: Job submitted successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProcessingJob'

    get:
      summary: List processing jobs
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [queued, running, completed, failed]
        - name: document_id
          in: query
          schema:
            type: string
        - name: limit
          in: query
          schema:
            type: integer
            default: 20
      responses:
        '200':
          description: List of processing jobs

  /api/v1/processing/jobs/{job_id}:
    get:
      summary: Get job details
      parameters:
        - name: job_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: Job details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProcessingJobDetail'

  /api/v1/processing/jobs/{job_id}/retry:
    post:
      summary: Retry failed job
      parameters:
        - name: job_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '202':
          description: Job retry initiated

components:
  schemas:
    ProcessingJobRequest:
      type: object
      properties:
        document_id:
          type: string
        processing_options:
          type: object
          properties:
            extract_entities:
              type: boolean
              default: true
            generate_embeddings:
              type: boolean
              default: true
            extract_metadata:
              type: boolean
              default: true
            ocr_enabled:
              type: boolean
              default: true
            transcription_enabled:
              type: boolean
              default: true

    ProcessingJob:
      type: object
      properties:
        id:
          type: string
          format: uuid
        document_id:
          type: string
        status:
          type: string
          enum: [queued, running, completed, failed, cancelled]
        current_stage:
          type: string
        progress_percentage:
          type: number
          minimum: 0
          maximum: 100
        created_at:
          type: string
          format: date-time
        started_at:
          type: string
          format: date-time
        completed_at:
          type: string
          format: date-time
        estimated_completion:
          type: string
          format: date-time

    ProcessingJobDetail:
      allOf:
        - $ref: '#/components/schemas/ProcessingJob'
        - type: object
          properties:
            stages:
              type: array
              items:
                $ref: '#/components/schemas/ProcessingStage'
            error_message:
              type: string
            retry_count:
              type: integer
            max_retries:
              type: integer
            processing_metadata:
              type: object

    ProcessingStage:
      type: object
      properties:
        name:
          type: string
        status:
          type: string
          enum: [pending, running, completed, failed, skipped]
        started_at:
          type: string
          format: date-time
        completed_at:
          type: string
          format: date-time
        duration_ms:
          type: number
        output_metadata:
          type: object
        error_message:
          type: string
```

### 7. Analytics Service
**Port**: 8006
**Responsibilities**:
- User behavior analytics
- System performance monitoring
- Usage statistics and trends
- Business intelligence metrics
- Real-time dashboard data

**API Endpoints**:
```yaml
openapi: 3.0.3
info:
  title: Analytics API
  version: 1.0.0
paths:
  /api/v1/analytics/usage:
    get:
      summary: Get usage statistics
      parameters:
        - name: time_range
          in: query
          schema:
            type: string
            enum: [1h, 24h, 7d, 30d, 90d]
            default: 7d
        - name: granularity
          in: query
          schema:
            type: string
            enum: [minute, hour, day, week]
            default: day
        - name: metrics
          in: query
          schema:
            type: array
            items:
              type: string
              enum: [searches, uploads, users, storage, processing_time]
      responses:
        '200':
          description: Usage statistics
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UsageStatistics'

  /api/v1/analytics/performance:
    get:
      summary: Get system performance metrics
      parameters:
        - name: time_range
          in: query
          schema:
            type: string
            enum: [1h, 24h, 7d, 30d]
            default: 24h
        - name: service
          in: query
          schema:
            type: string
      responses:
        '200':
          description: Performance metrics
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PerformanceAnalytics'

  /api/v1/analytics/dashboards:
    get:
      summary: Get dashboard data
      parameters:
        - name: dashboard_id
          in: query
          schema:
            type: string
        - name: refresh
          in: query
          schema:
            type: boolean
            default: false
      responses:
        '200':
          description: Dashboard data
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/DashboardData'

components:
  schemas:
    UsageStatistics:
      type: object
      properties:
        time_range:
          type: string
        granularity:
          type: string
        metrics:
          type: object
          properties:
            total_searches:
              type: integer
            unique_users:
              type: integer
            total_uploads:
              type: integer
            storage_used_gb:
              type: number
            avg_processing_time_ms:
              type: number
        trend_data:
          type: array
          items:
            type: object
            properties:
              timestamp:
                type: string
                format: date-time
              searches:
                type: integer
              uploads:
                type: integer
              users:
                type: integer

    PerformanceAnalytics:
      type: object
      properties:
        service_name:
          type: string
        time_range:
          type: string
        metrics:
          type: object
          properties:
            avg_response_time_ms:
              type: number
            p95_response_time_ms:
              type: number
            p99_response_time_ms:
              type: number
            error_rate:
              type: number
            throughput:
              type: number
            cpu_usage:
              type: number
            memory_usage:
              type: number
        alerts:
          type: array
          items:
            $ref: '#/components/schemas/PerformanceAlert'

    PerformanceAlert:
      type: object
      properties:
        alert_type:
          type: string
          enum: [high_latency, error_spike, resource_exhaustion, service_down]
        severity:
          type: string
          enum: [low, medium, high, critical]
        message:
          type: string
        triggered_at:
          type: string
          format: date-time
        resolved_at:
          type: string
          format: date-time

    DashboardData:
      type: object
      properties:
        dashboard_id:
          type: string
        title:
          type: string
        widgets:
          type: array
          items:
            $ref: '#/components/schemas/DashboardWidget'
        last_updated:
          type: string
          format: date-time

    DashboardWidget:
      type: object
      properties:
        widget_id:
          type: string
        type:
          type: string
          enum: [metric_chart, table, gauge, alert_list]
        title:
          type: string
        data:
          type: object
        position:
          type: object
          properties:
            x:
              type: integer
            y:
              type: integer
            width:
              type: integer
            height:
              type: integer
```

### 8. User Management Service
**Port**: 8007
**Responsibilities**:
- User authentication and authorization
- Organization management
- Role-based access control (RBAC)
- Multi-tenant data isolation
- User preferences and settings

**API Endpoints**:
```yaml
openapi: 3.0.3
info:
  title: User Management API
  version: 1.0.0
paths:
  /api/v1/auth/login:
    post:
      summary: User login
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                email:
                  type: string
                  format: email
                password:
                  type: string
      responses:
        '200':
          description: Login successful
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LoginResponse'
        '401':
          description: Invalid credentials

  /api/v1/auth/logout:
    post:
      summary: User logout
      security:
        - bearerAuth: []
      responses:
        '200':
          description: Logout successful

  /api/v1/auth/refresh:
    post:
      summary: Refresh access token
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                refresh_token:
                  type: string
      responses:
        '200':
          description: Token refreshed
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TokenResponse'

  /api/v1/users:
    get:
      summary: List users (admin only)
      security:
        - bearerAuth: []
      parameters:
        - name: organization_id
          in: query
          schema:
            type: string
        - name: role
          in: query
          schema:
            type: string
            enum: [admin, user, viewer]
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: limit
          in: query
          schema:
            type: integer
            default: 20
      responses:
        '200':
          description: List of users
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/User'

    post:
      summary: Create new user
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateUserRequest'
      responses:
        '201':
          description: User created successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/User'

  /api/v1/users/{user_id}:
    get:
      summary: Get user details
      security:
        - bearerAuth: []
      parameters:
        - name: user_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: User details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/UserDetail'

    put:
      summary: Update user
      security:
        - bearerAuth: []
      parameters:
        - name: user_id
          in: path
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/UpdateUserRequest'
      responses:
        '200':
          description: User updated

    delete:
      summary: Delete user
      security:
        - bearerAuth: []
      parameters:
        - name: user_id
          in: path
          required: true
          schema:
            type: string
      responses:
        '204':
          description: User deleted

components:
  schemas:
    LoginResponse:
      type: object
      properties:
        access_token:
          type: string
        refresh_token:
          type: string
        token_type:
          type: string
          default: bearer
        expires_in:
          type: integer
        user:
          $ref: '#/components/schemas/User'

    TokenResponse:
      type: object
      properties:
        access_token:
          type: string
        token_type:
          type: string
          default: bearer
        expires_in:
          type: integer

    User:
      type: object
      properties:
        id:
          type: string
          format: uuid
        email:
          type: string
          format: email
        first_name:
          type: string
        last_name:
          type: string
        role:
          type: string
          enum: [admin, user, viewer]
        organization_id:
          type: string
        is_active:
          type: boolean
        created_at:
          type: string
          format: date-time
        last_login:
          type: string
          format: date-time

    UserDetail:
      allOf:
        - $ref: '#/components/schemas/User'
        - type: object
          properties:
            storage_quota_mb:
              type: integer
            storage_used_mb:
              type: number
            preferences:
              type: object
            permissions:
              type: array
              items:
                type: string

    CreateUserRequest:
      type: object
      properties:
        email:
          type: string
          format: email
        first_name:
          type: string
        last_name:
          type: string
        password:
          type: string
          minLength: 8
        role:
          type: string
          enum: [admin, user, viewer]
        organization_id:
          type: string

    UpdateUserRequest:
      type: object
      properties:
        first_name:
          type: string
        last_name:
          type: string
        role:
          type: string
          enum: [admin, user, viewer]
        is_active:
          type: boolean
        preferences:
          type: object

  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

### 9. Real-time Communications Service
**Port**: 8008
**Responsibilities**:
- WebSocket connection management
- Real-time status updates
- Live notifications
- Streaming responses
- Connection authentication

**WebSocket Events**:
```yaml
WebSocket Events:

# Connection Management
connect:
  description: Client initiates WebSocket connection
  payload:
    type: object
    properties:
      token:
        type: string
        description: JWT access token
      client_id:
        type: string
        description: Unique client identifier

connected:
  description: Server confirms connection
  payload:
    type: object
    properties:
      session_id:
        type: string
      user_id:
        type: string
      server_time:
        type: string
        format: date-time

disconnect:
  description: Client disconnects
  payload:
    type: object
    properties:
      reason:
        type: string
        enum: [normal, error, timeout]

# Processing Updates
processing_status_update:
  description: Real-time processing status updates
  payload:
    type: object
    properties:
      document_id:
        type: string
      job_id:
        type: string
      status:
        type: string
        enum: [queued, processing, completed, failed]
      current_stage:
        type: string
      progress_percentage:
        type: number
        minimum: 0
        maximum: 100
      estimated_completion:
        type: string
        format: date-time
      error_message:
        type: string

# Search Updates
search_progress:
  description: Real-time search progress updates
  payload:
    type: object
    properties:
      search_id:
        type: string
      stage:
        type: string
        enum: [query_parsing, vector_search, graph_search, ranking, completion]
      progress_percentage:
        type: number
      intermediate_results:
        type: array
        items:
          type: object

# System Notifications
system_notification:
  description: System-wide notifications
  payload:
    type: object
    properties:
      notification_id:
        type: string
      type:
        type: string
        enum: [info, warning, error, maintenance]
      title:
        type: string
      message:
        type: string
      timestamp:
        type: string
        format: date-time
      actions:
        type: array
        items:
          type: object
          properties:
            label:
              type: string
            action:
              type: string
            url:
              type: string

# Error Events
error_occurred:
  description: Error event notification
  payload:
    type: object
    properties:
      error_id:
        type: string
      error_type:
        type: string
      message:
        type: string
      context:
        type: object
      timestamp:
        type: string
        format: date-time
      user_friendly_message:
        type: string
```

## Authentication & Authorization

### JWT Token Structure
```json
{
  "header": {
    "alg": "HS256",
    "typ": "JWT"
  },
  "payload": {
    "sub": "user_uuid",
    "email": "user@example.com",
    "role": "user",
    "organization_id": "org_uuid",
    "permissions": ["read:documents", "write:documents", "read:analytics"],
    "iat": 1640995200,
    "exp": 1641081600,
    "jti": "token_uuid"
  }
}
```

### Role-Based Access Control (RBAC)

**Roles**:
- **Super Admin**: System-wide access to all resources
- **Organization Admin**: Full access within organization
- **User**: Standard user access to own resources
- **Viewer**: Read-only access to shared resources

**Permissions**:
```
Document Management:
  - read:documents (own documents)
  - read:documents:all (organization documents)
  - write:documents (upload, edit own)
  - delete:documents (own documents)
  - manage:documents:all (admin)

Search:
  - read:search (perform searches)
  - read:search:analytics (view search analytics)

Knowledge Graph:
  - read:graph (view graph)
  - read:graph:analytics (graph analytics)

Evaluation:
  - read:evaluation (view metrics)
  - write:evaluation (run evaluations)

System:
  - read:system:health (health checks)
  - read:system:metrics (system metrics)
  - manage:users (user management)
  - manage:organizations (organization management)
```

### Multi-Tenant Data Isolation

**Row-Level Security**:
```sql
-- PostgreSQL Row Level Security Policy
CREATE POLICY user_document_isolation ON documents
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id')::uuid)
       AND (
           uploaded_by_user_id = current_setting('app.current_user_id')::uuid
           OR is_public = true
           OR current_setting('app.user_role') = 'admin'
       );
```

**Neo4j Database Isolation**:
```cypher
// Node labels with organization prefix
(:Document {organization_id: $org_id})
(:Entity {organization_id: $org_id})
(:User {organization_id: $org_id})

// Query filtering
MATCH (d:Document {organization_id: $org_id})
WHERE d.uploaded_by_user_id = $user_id OR d.is_public = true
RETURN d
```

## Event-Driven Architecture

### Message Queue Design

**Redis Streams Configuration**:
```yaml
streams:
  document_processing:
    max_length: 10000
    consumer_groups:
      - name: processing_workers
        consumers: 5
      - name: analytics_processors
        consumers: 2

  search_events:
    max_length: 50000
    consumer_groups:
      - name: analytics_consumers
        consumers: 3
      - name: monitoring_consumers
        consumers: 1

  user_events:
    max_length: 20000
    consumer_groups:
      - name: analytics_processors
        consumers: 2
      - name: audit_processors
        consumers: 1
```

**Event Schema**:
```json
{
  "event_id": "uuid",
  "event_type": "document.uploaded",
  "event_version": "1.0",
  "timestamp": "2025-10-19T10:00:00Z",
  "source_service": "document-service",
  "user_id": "user_uuid",
  "organization_id": "org_uuid",
  "correlation_id": "request_uuid",
  "data": {
    "document_id": "doc_uuid",
    "filename": "document.pdf",
    "file_size": 1024000,
    "mime_type": "application/pdf"
  },
  "metadata": {
    "user_agent": "Mozilla/5.0...",
    "ip_address": "192.168.1.1",
    "request_id": "req_uuid"
  }
}
```

## Caching Strategy

### Redis Caching Layers

**Application-Level Caching**:
```yaml
cache_configuration:
  user_sessions:
    ttl: 1800  # 30 minutes
    pattern: "session:{user_id}"

  search_results:
    ttl: 300   # 5 minutes
    pattern: "search:{query_hash}"
    max_size: 1000

  document_metadata:
    ttl: 3600  # 1 hour
    pattern: "doc:meta:{doc_id}"

  knowledge_graph_nodes:
    ttl: 7200  # 2 hours
    pattern: "graph:node:{node_id}"

  evaluation_metrics:
    ttl: 86400 # 24 hours
    pattern: "eval:metrics:{query_id}"

  api_rate_limits:
    ttl: 3600  # 1 hour
    pattern: "rate_limit:{user_id}:{endpoint}"
```

**Cache Invalidation Strategy**:
```python
# Cache invalidation on document update
def invalidate_document_cache(document_id: str, user_id: str):
    patterns = [
        f"doc:meta:{document_id}",
        f"search:*:{document_id}",
        f"graph:doc:{document_id}",
        f"eval:*:{document_id}"
    ]

    for pattern in patterns:
        redis.delete_pattern(pattern)
```

## Error Handling & Resilience

### Circuit Breaker Pattern
```yaml
circuit_breaker_config:
  default:
    failure_threshold: 5
    recovery_timeout: 30
    expected_exception: [ConnectionError, TimeoutError]

  database_connections:
    failure_threshold: 3
    recovery_timeout: 10
    expected_exception: [DatabaseError, ConnectionPoolError]

  external_apis:
    failure_threshold: 5
    recovery_timeout: 60
    expected_exception: [HTTPError, TimeoutError]
```

### Retry Strategy
```python
retry_config = {
    'max_attempts': 3,
    'backoff_strategy': 'exponential',
    'initial_delay': 1.0,
    'max_delay': 30.0,
    'jitter': True,
    'retry_on': [
        ConnectionError,
        TimeoutError,
        HTTP5xxError
    ]
}
```

### Error Response Format
```json
{
  "error": {
    "code": "PROCESSING_FAILED",
    "message": "Document processing failed due to corrupted file",
    "type": "processing_error",
    "severity": "error",
    "timestamp": "2025-10-19T10:00:00Z",
    "request_id": "req_uuid",
    "details": {
      "document_id": "doc_uuid",
      "stage": "ocr_extraction",
      "retry_count": 2,
      "max_retries": 3
    },
    "suggestions": [
      "Re-upload the document",
      "Check if file is corrupted",
      "Contact support if issue persists"
    ],
    "support_reference": "SUPPORT-12345"
  }
}
```

## Performance Optimization

### Database Optimization

**PostgreSQL Indexes**:
```sql
-- Document search indexes
CREATE INDEX CONCURRENTLY idx_documents_org_user
ON documents(organization_id, uploaded_by_user_id);

CREATE INDEX CONCURRENTLY idx_documents_type_status
ON documents(document_type, processing_status);

CREATE INDEX CONCURRENTLY idx_documents_created_at
ON documents(created_at DESC);

-- Full-text search index
CREATE INDEX CONCURRENTLY idx_documents_fulltext
ON documents USING gin(to_tsvector('english', title || ' ' || content_text));

-- Analytics indexes
CREATE INDEX CONCURRENTLY idx_analytics_user_time
ON analytics_events(user_id, timestamp DESC);

CREATE INDEX CONCURRENTLY idx_analytics_event_type_time
ON analytics_events(event_type, timestamp DESC);
```

**Neo4j Indexes**:
```cypher
// Entity name search
CREATE INDEX entity_name_index FOR (e:Entity) ON (e.name);

// Organization filtering
CREATE INDEX entity_org_index FOR (e:Entity) ON (e.organization_id);

// Document relationship indexing
CREATE INDEX doc_entity_index FOR ()-[r:CONTAINS_ENTITY]-() ON (r.strength);

// Full-text search
CREATE FULLTEXT INDEX entity_fulltext FOR (e:Entity) ON EACH [e.name, e.description];
```

**Qdrant Optimization**:
```python
# Collection configuration
collection_config = {
    "vectors": {
        "size": 768,  # Embedding dimension
        "distance": "Cosine"
    },
    "payload_schema": {
        "document_id": "keyword",
        "organization_id": "keyword",
        "content_type": "keyword",
        "created_at": "integer"
    },
    "hnsw_config": {
        "m": 16,
        "ef_construct": 200,
        "full_scan_threshold": 10000
    }
}
```

### Load Balancing Strategy

**Service Load Balancing**:
```yaml
load_balancing:
  algorithm: round_robin
  health_check:
    interval: 30
    timeout: 5
    healthy_threshold: 2
    unhealthy_threshold: 3
    path: /health

  services:
    document_service:
      replicas: 3
      cpu_limit: 1000m
      memory_limit: 2Gi

    search_service:
      replicas: 5
      cpu_limit: 2000m
      memory_limit: 4Gi

    graph_service:
      replicas: 2
      cpu_limit: 1500m
      memory_limit: 3Gi
```

## Monitoring & Observability

### Metrics Collection

**Prometheus Metrics**:
```yaml
metrics:
  system_metrics:
    - cpu_usage_percent
    - memory_usage_bytes
    - disk_usage_bytes
    - network_io_bytes

  application_metrics:
    - http_requests_total{method, endpoint, status}
    - http_request_duration_seconds{method, endpoint}
    - active_users_total
    - documents_processed_total{status, document_type}
    - search_queries_total{search_type}
    - search_latency_seconds{search_type}

  business_metrics:
    - user_registration_rate
    - document_upload_rate
    - query_success_rate
    - system_availability_percent
    - storage_utilization_percent
```

**Distributed Tracing**:
```yaml
tracing:
  provider: jaeger
  sampling_rate: 0.1  # 10% sampling
  service_name: multimodal-rag

  spans:
    - name: document_processing
      tags: [document_id, document_type, user_id]

    - name: search_query
      tags: [search_type, query_length, result_count]

    - name: knowledge_graph_analysis
      tags: [entity_count, relationship_count, algorithm]
```

### Alerting Rules

**Prometheus Alert Rules**:
```yaml
groups:
  - name: system_health
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service {{ $labels.job }} is down"

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High error rate on {{ $labels.job }}"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High latency on {{ $labels.job }}"

  - name: business_metrics
    rules:
      - alert: LowQuerySuccessRate
        expr: rate(search_queries_total{status="success"}[5m]) / rate(search_queries_total[5m]) < 0.8
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low query success rate"

      - alert: StorageQuotaApproaching
        expr: storage_utilization_percent > 90
        for: 15m
        labels:
          severity: info
        annotations:
          summary: "Storage quota approaching limit"
```

## Security Architecture

### Security Layers

**Network Security**:
- TLS 1.3 encryption for all communications
- VPN/Private network for service-to-service communication
- Web Application Firewall (WAF) at edge
- DDoS protection and rate limiting

**Application Security**:
- JWT-based authentication with short-lived tokens
- Role-based access control (RBAC)
- Input validation and sanitization
- SQL injection prevention
- XSS protection

**Data Security**:
- Encryption at rest (AES-256)
- Encryption in transit (TLS 1.3)
- Data anonymization for analytics
- Regular security scans and penetration testing

**Compliance**:
- GDPR compliance for EU users
- Data retention policies
- Audit logging for all sensitive operations
- Right to deletion implementation

## Deployment Architecture

### Container Orchestration
```yaml
kubernetes_deployment:
  api_version: apps/v1
  kind: Deployment

  spec:
    replicas: 3
    selector:
      matchLabels:
        app: document-service

    template:
      metadata:
        labels:
          app: document-service

      spec:
        containers:
        - name: document-service
          image: multimodal-rag/document-service:1.0.0
          ports:
          - containerPort: 8001

          resources:
            requests:
              cpu: 500m
              memory: 1Gi
            limits:
              cpu: 1000m
              memory: 2Gi

          env:
          - name: DATABASE_URL
            valueFrom:
              secretKeyRef:
                name: db-credentials
                key: url
          - name: REDIS_URL
            valueFrom:
              configMapKeyRef:
                name: infrastructure
                key: redis-url

          livenessProbe:
            httpGet:
              path: /health
              port: 8001
            initialDelaySeconds: 30
            periodSeconds: 10

          readinessProbe:
            httpGet:
              path: /ready
              port: 8001
            initialDelaySeconds: 5
            periodSeconds: 5
```

### Infrastructure as Code
```yaml
# Terraform configuration
resource "aws_eks_cluster" "rag_cluster" {
  name     = "multimodal-rag-cluster"
  role_arn = aws_iam_role.cluster_role.arn
  version  = "1.28"

  vpc_config {
    subnet_ids = aws_subnet.private[*].id
  }
}

resource "aws_rds_cluster" "postgres" {
  engine         = "aurora-postgresql"
  engine_version = "15.4"
  instance_class = "db.r6g.large"

  database_name = "multimodal_rag"
  username     = "postgres"

  skip_final_snapshot = false
  final_snapshot_identifier = "final-snapshot"
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "rag-redis"
  engine               = "redis"
  node_type            = "cache.r6g.large"
  num_cache_nodes      = 3
  parameter_group_name = "default.redis7"
}

resource "aws_neptune_cluster" "graph_db" {
  cluster_identifier = "rag-neptune"
  engine_version     = "1.3.0.0"

  backup_retention_period = 7
  preferred_backup_window = "03:00-04:00"
  skip_final_snapshot     = false
}
```

## Implementation Timeline

### Phase 1: Foundation (4 weeks)
- API Gateway implementation
- Authentication service development
- Basic document management service
- Database schema optimization
- CI/CD pipeline setup

### Phase 2: Core Services (6 weeks)
- Search service implementation
- Knowledge graph service development
- Processing pipeline service
- Basic evaluation metrics
- Real-time communications

### Phase 3: Advanced Features (4 weeks)
- Advanced analytics service
- Comprehensive evaluation framework
- Performance optimization
- Security hardening
- Monitoring and alerting

### Phase 4: Production Readiness (2 weeks)
- Load testing and optimization
- Security audit and penetration testing
- Documentation completion
- Production deployment preparation

## Success Metrics

### Technical Metrics
- **API Response Time**: <200ms (95th percentile)
- **System Availability**: >99.9%
- **Error Rate**: <0.1%
- **Search Latency**: <2 seconds
- **Document Processing**: <5 minutes for 10MB file

### Business Metrics
- **User Satisfaction Score**: >4.5/5
- **Query Success Rate**: >85%
- **Document Processing Success Rate**: >95%
- **Knowledge Graph Accuracy**: >90%
- **System Adoption Rate**: >80% within 6 months

This comprehensive backend service architecture provides a solid foundation for the Multimodal Enterprise RAG System, addressing the identified inconsistencies in the original plan and establishing clear service boundaries with API-first design principles.