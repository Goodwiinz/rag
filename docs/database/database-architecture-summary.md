# Complete Database Architecture Summary
## Multimodal Enterprise RAG System - Comprehensive Design Documentation

This document provides a complete overview of the database architecture designed for the Multimodal Enterprise RAG system, supporting multi-tenant operations with 5GB per user storage quotas, multi-modal document processing, real-time capabilities, and comprehensive evaluation metrics.

---

## Executive Summary

The database architecture comprises four integrated storage systems designed to handle enterprise-scale multimodal RAG operations:

- **PostgreSQL**: Primary relational database with time-series partitioning
- **Neo4j**: Knowledge graph for entities and relationships
- **Qdrant**: Vector database for semantic search
- **Redis**: Real-time caching and session management

The system supports:
- 50 concurrent users with 99% uptime target
- 2-second query response times
- Multi-modal document processing (PDF, TXT, JPG, PNG, MP3, MP4)
- 5GB storage quota per user with enforcement
- Comprehensive RAG Triad evaluation metrics
- Real-time WebSocket updates
- 30-day query history retention

---

## 1. PostgreSQL Schema Architecture

### 1.1 Core Multi-Tenant Tables

#### Organizations (`organizations`)
- **Purpose**: Multi-tenant isolation and subscription management
- **Key Features**: Subscription tiers, storage limits, feature flags, billing metrics
- **Constraints**: Storage quota enforcement, user count limits
- **Indexes**: slug, subscription_tier, is_deleted

#### Users (`users`)
- **Purpose**: User management with role-based access control
- **Key Features**: Email verification, role hierarchy, personal storage quotas
- **Constraints**: Unique email per organization, storage limits
- **Security**: Row-level security (RLS) enabled

#### User Sessions (`user_sessions`)
- **Purpose**: Session management and WebSocket tracking
- **Key Features**: JWT token storage, device fingerprinting, WebSocket connection mapping
- **Security**: TTL-based expiration, activity tracking

### 1.2 Document Management Tables

#### Documents (`documents`)
- **Purpose**: Multi-modal document storage with processing pipeline
- **Key Features**:
  - Support for 7 file types (PDF, text, image, audio, video, spreadsheet, presentation)
  - 50MB file size limit with enforcement
  - Processing status tracking with retry logic (3 attempts)
  - Quality scoring and extraction confidence
  - Full-text search with TSVECTOR
  - Multi-modal content classification
- **Constraints**: File size validation, processing retry limits
- **Indexes**: Composite indexes for organization, type, status, quality

#### Document Processing Jobs (`document_processing_jobs`)
- **Purpose**: Detailed tracking of processing pipeline steps
- **Key Features**: Job priority, progress tracking, resource usage metrics, worker assignment
- **Retry Logic**: Exponential backoff with configurable max retries
- **Monitoring**: CPU, memory, token usage, cost tracking

#### Document Quality Metrics (`document_quality_metrics`)
- **Purpose**: Automated quality assessment across modalities
- **Key Features**: Modality-specific quality scores, AI-generated recommendations
- **Metrics**: Text clarity, image resolution, audio clarity, video quality

### 1.3 Search and Analytics Tables

#### Search Queries (`search_queries`) - **PARTITIONED**
- **Purpose**: Comprehensive search tracking with performance metrics
- **Key Features**:
  - 5 search types (semantic, keyword, hybrid, graph, multimodal)
  - Performance breakdown (vector, graph, keyword, reranking timing)
  - User interaction tracking (clicks, satisfaction scores)
  - Cache hit monitoring
- **Partitioning**: Monthly partitions for time-series efficiency
- **Retention**: 30 days with automated archival

#### Search Results (`search_results`)
- **Purpose**: Detailed result tracking with user interaction
- **Key Features**: Relevance scoring, click tracking, dwell time measurement, multi-modal matching
- **Analytics**: Click-through rates, user satisfaction correlation

#### RAG Evaluations (`rag_evaluations`)
- **Purpose**: DeepEval RAG Triad metrics implementation
- **Key Features**:
  - Answer Relevancy (>70% threshold)
  - Faithfulness (>90% threshold)
  - Contextual Relevancy (>70% threshold)
  - Automated threshold violation detection
  - Cost and performance tracking
- **Integration**: Links to search queries for complete evaluation pipeline

### 1.4 Knowledge Graph Tables

#### Entities (`entities`)
- **Purpose**: Extracted entity management with graph integration
- **Key Features**: 11 entity types, extraction method tracking, confidence scoring
- **Graph Integration**: Neo4j node ID mapping for knowledge graph
- **Quality**: Relevance scoring, extraction confidence tracking

#### Entity Relationships (`entity_relationships`)
- **Purpose**: Entity relationship mapping with confidence weighting
- **Key Features**: Relationship type classification, context preservation
- **Graph Integration**: Neo4j relationship ID mapping

#### Concepts (`concepts`)
- **Purpose**: Topic modeling and concept hierarchy management
- **Key Features**: Hierarchical organization, usage statistics, AI-generated summaries
- **Analytics**: Document frequency, mention counting, confidence aggregation

### 1.5 Monitoring and System Health

#### Performance Metrics (`performance_metrics`) - **PARTITIONED**
- **Purpose**: High-frequency performance monitoring
- **Key Features**: Time-series data with automatic alerting, threshold-based monitoring
- **Partitioning**: Weekly partitions for efficient querying
- **Alerting**: Automatic alert creation on threshold violations

#### System Health (`system_health`)
- **Purpose**: Component health monitoring and dependency tracking
- **Key Features**: Health scoring, consecutive failure tracking, resource usage monitoring
- **Dependencies**: Service dependency mapping with status propagation

#### Error Logs (`error_logs`) - **PARTITIONED**
- **Purpose**: Comprehensive error tracking and resolution management
- **Key Features**: Severity classification, resolution workflow, alerting integration
- **Analytics**: Error pattern analysis, MTTR tracking

---

## 2. Neo4j Knowledge Graph Schema

### 2.1 Node Structure

#### Document Nodes
```cypher
(:Document {
  id: UUID,              // PostgreSQL reference
  title: String,
  type: String,           // pdf, text, image, audio, video
  primary_modality: String,
  modalities: Array[String],
  content_hash: String,
  quality_score: Float,
  organization_id: UUID,
  created_at: DateTime,
  is_indexed: Boolean,
  embedding_id: String    // Qdrant reference
})
```

#### Entity Nodes
```cypher
(:Entity {
  id: UUID,              // PostgreSQL reference
  name: String,
  canonical_name: String,
  type: String,           // Person, Organization, Location, Concept, etc.
  aliases: Array[String],
  properties: Map,
  confidence: Float,
  extraction_method: String,
  organization_id: UUID,
  document_count: Integer,
  relationship_count: Integer
})
```

#### Concept Nodes
```cypher
(:Concept {
  name: String,
  type: String,           // Topic, Category, Domain, Technology
  description: String,
  document_frequency: Integer,
  total_mentions: Integer,
  avg_confidence: Float,
  organization_id: UUID
})
```

### 2.2 Relationship Types

#### Core Relationships
```cypher
// Document-Entity relationships
(:Document)-[:CONTAINS {confidence: Float, extraction_method: String}]->(:Entity)

// Entity-Entity relationships
(:Entity)-[:RELATED_TO {type: String, confidence: Float, source_document_id: UUID}]->(:Entity)

// Document-Concept relationships
(:Document)-[:ABOUT {relevance_score: Float, extraction_method: String}]->(:Concept)

// User interaction tracking
(:User)-[:ACCESSED {access_type: String, timestamp: DateTime}]->(:Document)

// Search query relationships
(:User)-[:EXECUTED {query_type: String, results_count: Integer}]->(:Query)
```

### 2.3 Graph Optimization

#### Indexes for Performance
```cypher
// Performance indexes
CREATE INDEX document_type_index FOR (d:Document) ON (d.type, d.organization_id);
CREATE INDEX entity_type_index FOR (e:Entity) ON (e.type, e.organization_id);
CREATE INDEX entity_confidence_index FOR (e:Entity) ON (e.confidence);

// Full-text search indexes
CREATE FULLTEXT INDEX document_title_index FOR (d:Document) ON EACH [d.title];
CREATE FULLTEXT INDEX entity_name_index FOR (e:Entity) ON EACH [e.name, e.canonical_name];
```

#### Sample Graph Queries
```cypher
// Find related entities for semantic search
MATCH (d:Document {id: $document_id})-[:CONTAINS]->(e1:Entity)-[:RELATED_TO]-(e2:Entity)
WHERE e1.type = $entity_type AND e2.type = $related_type
RETURN e1.name, e2.name, relationship_type
ORDER BY e1.confidence DESC
LIMIT 10;

// Find concept clusters within organization
MATCH (c1:Concept)<-[:ABOUT]-(d:Document)-[:ABOUT]->(c2:Concept)
WHERE c1.organization_id = $org_id AND c2.organization_id = $org_id
RETURN c1.name, c2.name, count(d) as shared_documents
ORDER BY shared_documents DESC
LIMIT 20;
```

---

## 3. Qdrant Vector Collections

### 3.1 Primary Document Embeddings Collection
```json
{
  "collection_name": "document_embeddings",
  "vectors": {
    "size": 1536,
    "distance": "Cosine"
  },
  "payload_schema": {
    "document_id": "keyword",
    "organization_id": "keyword",
    "title": "text",
    "document_type": "keyword",
    "primary_modality": "keyword",
    "modalities": "keyword",
    "quality_score": "float",
    "processing_status": "keyword",
    "is_indexed": "bool",
    "tags": "keyword",
    "categories": "keyword",
    "created_at": "integer"
  },
  "hnsw_config": {
    "m": 16,
    "ef_construct": 200,
    "full_scan_threshold": 20000
  },
  "quantization_config": {
    "quantization": "scalar",
    "scalar": {
      "type": "int8",
      "ram_usage": "0.2x"
    }
  }
}
```

### 3.2 Multi-Modal Embeddings Collection
```json
{
  "collection_name": "multimodal_embeddings",
  "vectors": {
    "size": 1024,
    "distance": "Cosine"
  },
  "vectors_map": {
    "text": {"size": 1536, "distance": "Cosine"},
    "image": {"size": 512, "distance": "Cosine"}
  },
  "payload_schema": {
    "document_id": "keyword",
    "organization_id": "keyword",
    "modality": "keyword",
    "content_type": "keyword",
    "extraction_method": "keyword",
    "confidence": "float",
    "metadata": "json"
  }
}
```

### 3.3 Entity Embeddings Collection
```json
{
  "collection_name": "entity_embeddings",
  "vectors": {
    "size": 768,
    "distance": "Cosine"
  },
  "payload_schema": {
    "entity_id": "keyword",
    "organization_id": "keyword",
    "entity_type": "keyword",
    "entity_name": "text",
    "canonical_name": "text",
    "extraction_method": "keyword",
    "confidence": "float",
    "document_count": "integer",
    "relationship_count": "integer"
  }
}
```

### 3.4 Search Configuration
```json
{
  "search_params": {
    "hnsw": {"ef": 128, "exact": false},
    "exact_search_threshold": 1000
  },
  "search_filters": {
    "must": [
      {"key": "organization_id", "match": {"value": "$org_id"}},
      {"key": "is_indexed", "match": {"value": true}}
    ],
    "should": [
      {"key": "quality_score", "range": {"gte": 0.7}}
    ]
  }
}
```

---

## 4. Redis Data Structures

### 4.1 Session Management
```redis
// User sessions with WebSocket support
session:{session_id} -> Hash {
  user_id: UUID,
  organization_id: UUID,
  email: string,
  role: string,
  created_at: ISO8601_timestamp,
  last_activity: ISO8601_timestamp,
  expires_at: ISO8601_timestamp,
  websocket_connections: JSON
}
TTL: 1 hour

// WebSocket connection tracking
ws_connections:{session_id} -> Hash {
  connection_id: string,
  node_id: string,
  subscriptions: JSON,
  last_ping: ISO8601_timestamp
}
```

### 4.2 Document Processing Cache
```redis
// Real-time processing status
processing_status:{document_id} -> Hash {
  status: string,
  progress_percentage: integer,
  current_step: string,
  started_at: ISO8601_timestamp,
  estimated_completion: ISO8601_timestamp,
  error_message: string
}
TTL: 24 hours

// Document content cache
document_content:{document_id} -> Hash {
  text_content: string,
  summary: string,
  extracted_entities: JSON,
  quality_score: float
}
TTL: 24 hours
```

### 4.3 Search Result Caching
```redis
// Search query cache
search_cache:{query_hash} -> Hash {
  query_text: string,
  organization_id: UUID,
  results: JSON,
  execution_time_ms: integer,
  hit_count: integer
}
TTL: 30 minutes

// Popular queries tracking
popular_queries:{organization_id} -> SortedSet {
  query_text: score (frequency * recency_factor)
}
```

### 4.4 Real-Time Analytics
```redis
// Performance metrics streaming
metrics:performance -> Stream {
  timestamp: ISO8601_timestamp,
  metric_name: string,
  value: float,
  organization_id: UUID,
  component: string
}

// Current metrics aggregation
metrics:current:{metric_name}:{organization_id} -> Hash {
  current_value: float,
  avg_1m: float,
  avg_5m: float,
  last_updated: ISO8601_timestamp
}
TTL: 5 minutes
```

### 4.5 Rate Limiting
```redis
// User-based rate limiting
rate_limit:user:{user_id}:{endpoint} -> SortedSet {
  timestamp: score,
  request_id: member
}

// Storage quota tracking
storage_quota:user:{user_id} -> Hash {
  used_gb: float,
  document_count: integer,
  quota_limit_gb: float,
  available_gb: float
}
```

---

## 5. Security Architecture

### 5.1 Multi-Tenant Data Isolation

#### Row-Level Security (RLS)
```sql
-- Organization-based isolation policies
CREATE POLICY document_org_policy ON documents
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Public document access
CREATE POLICY document_public_read ON documents
    FOR SELECT TO authenticated_users
    USING (is_public = TRUE OR organization_id = current_setting('app.current_organization_id', true)::UUID);
```

#### Application-Level Security
```python
# Middleware for organization context enforcement
async def set_organization_context(request: Request):
    user_id = get_current_user_id(request)
    org_id = await get_user_organization_id(user_id)

    # Set organization context for database session
    await set_database_context("app.current_organization_id", org_id)

    # Validate organization access for all operations
    request.state.organization_id = org_id
```

### 5.2 Data Encryption

#### Sensitive Field Encryption
```sql
-- Encrypt user PII
ALTER TABLE users ADD COLUMN email_encrypted BYTEA;
UPDATE users SET email_encrypted = pgp_sym_encrypt(email, current_setting('app.encryption_key'));

-- Encrypt file paths
ALTER TABLE documents ADD COLUMN file_path_encrypted BYTEA;
UPDATE documents SET file_path_encrypted = pgp_sym_encrypt(file_path, current_setting('app.encryption_key'));
```

#### API Security
```python
# JWT tokens with organization context
class SecureTokenGenerator:
    def create_token(self, user_id: str, organization_id: str, permissions: list):
        payload = {
            'user_id': user_id,
            'organization_id': organization_id,
            'permissions': permissions,
            'exp': datetime.utcnow() + timedelta(hours=1)
        }
        return jwt.encode(payload, self.secret, algorithm='HS256')
```

### 5.3 Audit Logging

#### Comprehensive Audit Trail
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100),
    action VARCHAR(100),
    table_name VARCHAR(100),
    record_id UUID,
    user_id UUID REFERENCES users(id),
    organization_id UUID REFERENCES organizations(id),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    timestamp TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (timestamp);
```

---

## 6. Performance Optimization

### 6.1 Database Optimization

#### Partitioning Strategy
```sql
-- Monthly partitions for time-series data
CREATE TABLE search_queries ( ... ) PARTITION BY RANGE (created_at);
CREATE TABLE search_queries_y2024m01 PARTITION OF search_queries
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Weekly partitions for high-frequency metrics
CREATE TABLE performance_metrics ( ... ) PARTITION BY RANGE (timestamp);
CREATE TABLE performance_metrics_y2024w01 PARTITION OF performance_metrics
    FOR VALUES FROM ('2024-01-01') TO ('2024-01-08');
```

#### Indexing Strategy
```sql
-- Composite indexes for common query patterns
CREATE INDEX idx_documents_org_type_status ON documents(organization_id, document_type, processing_status);
CREATE INDEX idx_search_queries_user_time ON search_queries(user_id, created_at DESC);
CREATE INDEX idx_rag_evaluations_org_score ON rag_evaluations(organization_id, overall_score DESC);

-- Partial indexes for recent data
CREATE INDEX idx_search_queries_recent ON search_queries(created_at DESC)
WHERE created_at >= NOW() - INTERVAL '30 days';
```

#### Materialized Views
```sql
-- Daily analytics summary
CREATE MATERIALIZED VIEW daily_analytics_summary AS
SELECT
    DATE_TRUNC('day', created_at) as date,
    organization_id,
    COUNT(*) as total_documents,
    AVG(quality_score) as avg_quality_score,
    SUM(file_size_bytes) as total_storage
FROM documents
WHERE is_deleted = FALSE
GROUP BY DATE_TRUNC('day', created_at), organization_id;

-- Auto-refresh every hour
SELECT cron.schedule('refresh-daily-analytics', '0 * * * *', 'REFRESH MATERIALIZED VIEW daily_analytics_summary;');
```

### 6.2 Caching Strategy

#### Multi-Level Cache Architecture
```python
# Cache hierarchy: Local Memory -> Redis -> Database
class CacheManager:
    async def get_document_content(self, document_id: str):
        # Level 1: Local memory cache (fastest)
        if document_id in self.local_cache:
            return self.local_cache[document_id]

        # Level 2: Redis cache (fast)
        cached = await self.redis.hgetall(f"document_content:{document_id}")
        if cached:
            self.local_cache[document_id] = cached
            return cached

        # Level 3: Database (slowest)
        document = await self.get_document_from_db(document_id)
        if document:
            # Cache in Redis with TTL
            await self.redis.hset(f"document_content:{document_id}", mapping=document)
            await self.redis.expire(f"document_content:{document_id}", 86400)
            self.local_cache[document_id] = document

        return document
```

#### Intelligent Cache Invalidation
```python
# Context-aware cache invalidation
class CacheInvalidator:
    async def invalidate_document_cache(self, document_id: str, organization_id: str):
        # Invalidate specific document cache
        await self.redis.delete(f"document_content:{document_id}")

        # Invalidate related search caches
        pattern = f"search_cache:*:{organization_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

        # Notify WebSocket subscribers
        await self.notify_document_update(document_id, organization_id)
```

### 6.3 Connection Pooling

#### Database Connection Management
```python
# Advanced connection pooling with health checks
class DatabasePool:
    def __init__(self):
        self.pool = create_engine(
            DATABASE_URL,
            pool_size=20,           # Base connection pool size
            max_overflow=30,        # Additional connections under load
            pool_pre_ping=True,     # Validate connections
            pool_recycle=3600,      # Recycle connections hourly
            echo=False
        )

    async def execute_query(self, query: str, params: dict = None):
        async with self.pool.connect() as conn:
            try:
                result = await conn.execute(text(query), params or {})
                return result.fetchall()
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                raise
```

---

## 7. Monitoring and Observability

### 7.1 Health Monitoring

#### Database Health Checks
```sql
CREATE OR REPLACE FUNCTION system_health_check()
RETURNS TABLE (
    component TEXT,
    status TEXT,
    response_time_ms INTEGER,
    details JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        'database'::TEXT as component,
        CASE WHEN pg_is_in_recovery() = false THEN 'healthy' ELSE 'replicating' END::TEXT as status,
        EXTRACT(EPOCH FROM (NOW() - stats_reset)) * 1000 as response_time_ms,
        jsonb_build_object(
            'connections_active', (SELECT count(*) FROM pg_stat_activity WHERE state = 'active'),
            'database_size', pg_size_pretty(pg_database_size(current_database()))
        ) as details
    FROM pg_stat_database WHERE datname = current_database();
END;
$$ LANGUAGE plpgsql;
```

#### System Metrics Collection
```python
# Comprehensive metrics collection
class MetricsCollector:
    async def collect_database_metrics(self):
        metrics = await self.db.execute_query("""
            SELECT
                schemaname,
                tablename,
                n_tup_ins as inserts,
                n_tup_upd as updates,
                n_dead_tup as dead_tuples
            FROM pg_stat_user_tables
        """)

        # Store in Redis for real-time monitoring
        for metric in metrics:
            await self.redis.hset(
                f"db_metrics:{metric.tablename}",
                mapping={
                    'inserts': metric.inserts,
                    'updates': metric.updates,
                    'dead_tuples': metric.dead_tuples,
                    'timestamp': datetime.utcnow().timestamp()
                }
            )
```

### 7.2 Alerting System

#### Threshold-Based Alerting
```python
# Automated alert creation on threshold violations
async def check_metric_thresholds():
    critical_metrics = await redis.hgetall("metrics:thresholds")

    for metric_name, threshold in critical_metrics.items():
        current_value = await redis.hget(f"metrics:current:{metric_name}", "current_value")

        if current_value and float(current_value) > float(threshold):
            await create_system_alert(
                alert_type="performance",
                metric_name=metric_name,
                current_value=current_value,
                threshold_value=threshold,
                severity="critical"
            )
```

#### Alert Management
```sql
CREATE TABLE system_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_name VARCHAR(255) NOT NULL,
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    alert_details JSONB DEFAULT '{}'
);
```

---

## 8. Migration and Deployment Strategy

### 8.1 Migration Phases

#### Phase 1: Core Infrastructure (Migration 001)
```sql
-- Organizations, Users, Sessions
-- Multi-tenant foundation
-- Row-level security setup
-- Basic indexes
```

#### Phase 2: Document Management (Migration 002)
```sql
-- Documents, Processing Jobs, Quality Metrics
-- Multi-modal content support
-- Processing pipeline tracking
-- Performance monitoring
```

#### Phase 3: Search and Analytics (Migration 003)
```sql
-- Search Queries, Results, RAG Evaluations
-- Time-series partitioning
-- Performance tracking
-- User analytics
```

#### Phase 4: Knowledge Graph (Migration 004)
```sql
-- Entities, Relationships, Concepts
-- Graph integration
-- Canonicalization
-- Analytics tracking
```

#### Phase 5: Monitoring (Migration 005)
```sql
-- Performance Metrics, System Health, Error Logs
-- Alerting system
-- Real-time monitoring
-- Historical analytics
```

### 8.2 Migration Runner Features

#### Advanced Migration Management
```python
# Modern migration runner with comprehensive features
class MigrationRunner:
    async def migrate(self, target_version: Optional[str] = None):
        # Progress tracking with rich UI
        # Automatic rollback on failure
        # Migration validation
        # Performance benchmarking
        # Schema validation
        pass

    async def rollback(self, version: str):
        # Safe rollback with validation
        # Data integrity checks
        # Rollback confirmation
        pass
```

#### Migration Commands
```bash
# Run all migrations
python migration_runner.py migrate

# Run specific version
python migration_runner.py migrate --version 003

# Rollback to version
python migration_runner.py rollback --version 002

# Check migration status
python migration_runner.py status

# Validate schema
python migration_runner.py validate
```

### 8.3 Data Validation

#### Comprehensive Validation
```sql
-- Data consistency checks
CREATE OR REPLACE FUNCTION validate_data_integrity()
RETURNS TABLE (
    validation_type TEXT,
    status TEXT,
    issues_found INTEGER,
    details JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT 'orphaned_documents'::TEXT,
           CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END::TEXT,
           COUNT(*) as issues_found,
           jsonb_build_object('orphaned_count', COUNT(*)) as details
    FROM documents d
    LEFT JOIN organizations o ON d.organization_id = o.id
    WHERE o.id IS NULL AND d.is_deleted = FALSE;
END;
$$ LANGUAGE plpgsql;
```

---

## 9. Scaling and Capacity Planning

### 9.1 Performance Targets

#### Query Performance Requirements
- **Search Queries**: < 2000ms average, < 500ms P95
- **Document Upload**: < 5000ms processing start time
- **User Authentication**: < 500ms
- **WebSocket Updates**: < 100ms message delivery
- **Cache Hits**: < 50ms response time

#### Concurrent User Support
- **Target**: 50 concurrent users
- **Peak Load**: 100 concurrent users (2x safety factor)
- **Query Rate**: 10 queries/minute per user average
- **Upload Rate**: 5 documents/hour per user average

### 9.2 Resource Requirements

#### PostgreSQL Resources
```yaml
postgresql:
  # Production configuration
  max_connections: 200
  shared_buffers: 256MB
  effective_cache_size: 1GB
  work_mem: 4MB
  maintenance_work_mem: 64MB

  # Partitioning configuration
  autovacuum_max_workers: 3
  autovacuum_naptime: 1min

  # Performance optimization
  random_page_cost: 1.1
  effective_io_concurrency: 200
```

#### Redis Resources
```yaml
redis:
  # Memory configuration
  maxmemory: 512MB
  maxmemory_policy: allkeys-lru

  # Persistence
  save: "900 1 300 10 60 10000"

  # Performance
  tcp-keepalive: 300
  timeout: 0
```

#### Neo4j Resources
```yaml
neo4j:
  # Memory configuration
  dbms.memory.heap.initial_size: 512m
  dbms.memory.heap.max_size: 2G
  dbms.memory.pagecache.size: 1G

  # Performance
  dbms.tx_log.rotation.retention_policy: 100M size
```

### 9.3 Monitoring Thresholds

#### Database Performance
- **Connection Usage**: < 80% of max_connections
- **Query Duration**: < 2000ms average, < 5000ms P95
- **Dead Tuples**: < 10% of total tuples
- **Cache Hit Rate**: > 95%

#### System Health
- **CPU Usage**: < 70% average, < 90% peak
- **Memory Usage**: < 80% of available memory
- **Disk Usage**: < 80% of available disk space
- **Disk I/O**: < 80% of maximum IOPS

#### Application Metrics
- **Error Rate**: < 1% of total requests
- **Response Time**: < 2000ms average
- **Uptime**: > 99% availability
- **Queue Length**: < 100 items

---

## 10. Disaster Recovery and Backup

### 10.1 Backup Strategy

#### Automated Backups
```bash
#!/bin/bash
# Daily database backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="multimodal_rag_backup_$TIMESTAMP.sql"

pg_dump -h localhost -p 5432 -U postgres -d multimodal_rag \
    --format=custom \
    --compress=9 \
    --verbose \
    --file=$BACKUP_FILE

# Upload to cloud storage
aws s3 cp $BACKUP_FILE s3://multimodal-rag-backups/database/

# Compress and cleanup
gzip $BACKUP_FILE
find /backups -name "*.gz" -mtime +30 -delete
```

#### Point-in-Time Recovery
```sql
-- Enable WAL archiving
ALTER SYSTEM SET wal_level = replica;
ALTER SYSTEM SET archive_mode = on;
ALTER SYSTEM SET archive_command = 'cp %p /wal_archive/%f';
SELECT pg_reload_conf();
```

### 10.2 High Availability

#### Streaming Replication
```sql
-- Primary server configuration
ALTER SYSTEM SET synchronous_commit = on;
ALTER SYSTEM SET synchronous_standby_names = 'standby1,standby2';

-- Replication monitoring
CREATE OR REPLACE FUNCTION check_replication_lag()
RETURNS TABLE (
    standby_name TEXT,
    lag_seconds INTEGER,
    status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        application_name as standby_name,
        EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))::INTEGER as lag_seconds,
        CASE
            WHEN EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) < 10 THEN 'synced'
            WHEN EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) < 60 THEN 'lagging'
            ELSE 'critical'
        END as status
    FROM pg_stat_replication
    WHERE state = 'streaming';
END;
$$ LANGUAGE plpgsql;
```

---

## 11. Summary and Key Benefits

### 11.1 Architecture Benefits

#### Scalability
- **Multi-database architecture** for specialized workloads
- **Time-series partitioning** for efficient data management
- **Horizontal scaling** with connection pooling
- **Intelligent caching** for optimal performance

#### Security
- **Multi-tenant isolation** with RLS and organization context
- **Data encryption** for sensitive information
- **Comprehensive audit logging** for compliance
- **Role-based access control** with fine-grained permissions

#### Performance
- **Sub-second query responses** through intelligent caching
- **99% uptime** with high availability configuration
- **Real-time updates** via WebSocket integration
- **Comprehensive monitoring** with automated alerting

#### Data Management
- **Multi-modal content support** (text, image, audio, video)
- **Automated quality assessment** with AI-powered metrics
- **Knowledge graph integration** for entity relationships
- **Comprehensive evaluation** with RAG Triad metrics

### 11.2 Operational Excellence

#### Monitoring and Observability
- **Real-time metrics** collection and aggregation
- **Automated health checks** with alerting
- **Performance benchmarking** and optimization
- **Error tracking** with resolution workflow

#### Maintenance and Operations
- **Automated migrations** with rollback capability
- **Data validation** and integrity checks
- **Backup and recovery** with point-in-time restore
- **Resource monitoring** and capacity planning

#### Development Experience
- **Comprehensive schema** with clear relationships
- **Migration tooling** for safe deployments
- **Documentation** for all components
- **Testing support** with sample data

This comprehensive database architecture provides a solid foundation for the Multimodal Enterprise RAG system, supporting enterprise-scale operations with excellent performance, security, and reliability. The design scales to meet the specified requirements while maintaining flexibility for future enhancements.

---

**File References:**
- `/docs/database-schema-design.md` - Complete schema design documentation
- `/backend/src/migrations/001_create_core_tables.sql` - Core tables migration
- `/backend/src/migrations/002_create_document_tables.sql` - Document management migration
- `/backend/src/migrations/003_create_search_tables.sql` - Search and analytics migration
- `/backend/src/migrations/004_create_knowledge_graph_tables.sql` - Knowledge graph migration
- `/backend/src/migrations/005_create_monitoring_tables.sql` - Monitoring and health migration
- `/backend/src/migrations/new_migration_runner.py` - Migration management tool
- `/docs/redis-data-structures.md` - Redis caching and real-time data structures