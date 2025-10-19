# Database Documentation - Multimodal Enterprise RAG System

This document provides comprehensive documentation for the four-database architecture of the Multimodal Enterprise RAG System.

## Overview

The system uses a polyglot persistence architecture with four specialized databases:

1. **PostgreSQL** - Primary relational database for structured data
2. **Neo4j** - Knowledge graph for entities and relationships
3. **Qdrant** - Vector database for semantic search
4. **Redis** - Cache and real-time data structures

## Architecture Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     Neo4j       │    │     Qdrant      │    │      Redis      │
│                 │    │                 │    │                 │    │                 │
│ • Users         │◄──►│ • Entities      │◄──►│ • Documents     │◄──►│ • Cache         │
│ • Organizations │    │ • Relationships │    │ • Embeddings    │    │ • Sessions      │
│ • Documents     │    │ • Graph Traversal│    │ • Similarity    │    │ • Rate Limits   │
│ • Audit Logs    │    │ • Path Finding  │    │ • Search        │    │ • Pub/Sub       │
│ • Analytics     │    │ • Communities   │    │ • Multimodal    │    │ • Metrics       │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Database Connections

### Environment Variables

```bash
# PostgreSQL
export DATABASE_URL="postgresql://raguser:rag_password_123@localhost:5432/ragdb"

# Neo4j
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="neo4j_password_123"

# Qdrant
export QDRANT_URL="http://localhost:6333"
export QDRANT_API_KEY="qdrant_api_key_123"

# Redis
export REDIS_URL="redis://:redis_password_123@localhost:6379/0"
```

### Connection Details

| Database | Host | Port | Database/Collection | Auth |
|----------|------|------|---------------------|------|
| PostgreSQL | localhost | 5432 | ragdb | raguser/rag_password_123 |
| Neo4j | localhost | 7687 (Bolt) | - | neo4j/neo4j_password_123 |
| Qdrant | localhost | 6333 | documents, entities, multimodal | qdrant_api_key_123 |
| Redis | localhost | 6379 | - | redis_password_123 |

## PostgreSQL Schema

### Core Tables

#### Organizations
- **Purpose**: Multi-tenant organization management
- **Key Fields**: id, name, slug, storage_tier, max_storage_gb, max_users
- **Features**: Row-level security, storage quotas

#### Users
- **Purpose**: User authentication and authorization
- **Key Fields**: id, email, password_hash, role, organization_id
- **Features**: Role-based access, login tracking

#### Documents
- **Purpose**: Multimodal document storage
- **Key Fields**: id, title, document_type, content_text, organization_id
- **Features**: Full-text search, versioning, metadata

#### Entities
- **Purpose**: Named entities extracted from documents
- **Key Fields**: id, name, entity_type, confidence_score, organization_id
- **Features**: Entity linking, canonicalization, aliases

#### Search Queries
- **Purpose**: Search analytics and optimization
- **Key Fields**: id, query_text, query_type, results_count, latency_ms
- **Features**: Query analysis, performance tracking

### Performance Optimizations

- **Indexes**: 69+ optimized indexes for common query patterns
- **Full-text Search**: trigram indexes for fuzzy matching
- **Partitioning**: Time-based partitioning for analytics tables
- **Row-Level Security**: Multi-tenant data isolation

### Views and Functions

```sql
-- Organization statistics
SELECT * FROM organization_stats;

-- User activity summary
SELECT * FROM user_activity_summary;

-- Entity importance calculation
SELECT * FROM calculate_entity_importance('entity_id');
```

## Neo4j Knowledge Graph

### Node Types

- **Entity**: People, organizations, locations, concepts
- **Document**: Documents with content metadata
- **User**: System users
- **Organization**: Multi-tenant organizations
- **MultimodalContent**: Images, tables, charts

### Relationship Types

- **RELATED_TO**: General entity relationships
- **EXTRACTED_FROM**: Document-entity extraction
- **PART_OF**: Hierarchical relationships
- **MEMBER_OF**: User-organization membership
- **UPLOADED**: User-document uploads

### Indexes and Constraints

```cypher
-- Unique constraints
CREATE CONSTRAINT entity_id_unique FOR (e:Entity) REQUIRE e.id IS UNIQUE;

-- Performance indexes
CREATE INDEX entity_name_index FOR (e:Entity) ON (e.name);
CREATE INDEX entity_type_index FOR (e:Entity) ON (e.type);

-- Full-text search
CREATE FULLTEXT INDEX entity_content_index FOR (e:Entity) ON EACH [e.name, e.description];
```

### Graph Algorithms

- **Path Finding**: Shortest paths between entities
- **Community Detection**: Entity clustering
- **Centrality Measures**: Importance scoring
- **Similarity**: Graph-based entity similarity

## Qdrant Vector Database

### Collections

#### Documents Collection
- **Vector Size**: 1536 dimensions
- **Distance**: Cosine similarity
- **Payload**: document_id, title, organization_id, document_type

#### Entities Collection
- **Vector Size**: 1536 dimensions
- **Distance**: Cosine similarity
- **Payload**: entity_id, name, entity_type, confidence_score

#### Multimodal Collection
- **Vector Size**: 1536 dimensions
- **Distance**: Cosine similarity
- **Payload**: content_id, modality, coordinates, temporal_data

### Search Operations

```python
# Semantic search
client.search(
    collection_name="documents",
    query_vector=query_embedding,
    query_filter={
        "must": [
            {"key": "organization_id", "match": {"value": org_id}}
        ]
    },
    limit=10
)
```

### Performance Features

- **Quantization**: Scalar quantization for memory efficiency
- **Disk Storage**: On-disk vector storage for large datasets
- **Indexing**: HNSW indexing for fast approximate search

## Redis Cache System

### Data Structures

#### Cache Configuration
```redis
HSET cache_configs search_ttl 3600
HSET cache_configs document_ttl 7200
HSET cache_configs entity_ttl 1800
```

#### Rate Limiting
```redis
HSET rate_limits search_per_minute 60
HSET rate_limits upload_per_hour 100
HSET rate_limits api_requests_per_minute 1000
```

#### Session Management
```redis
HMSET session:user123 user_id 123 organization_id org456 ...
EXPIRE session:user123 3600
```

### Real-time Features

- **Pub/Sub**: Real-time updates and notifications
- **Metrics**: Performance counters and analytics
- **Locks**: Distributed locking for critical operations
- **Queues**: Job processing queues

## Database Initialization

### Quick Start

1. **Ensure Docker containers are running**:
   ```bash
   docker-compose ps
   ```

2. **Run database initialization**:
   ```bash
   chmod +x database/init/05_database_init.sh
   ./database/init/05_database_init.sh
   ```

3. **Verify health status**:
   ```bash
   python3 database/health_checks.py
   ```

### Manual Setup Steps

#### PostgreSQL
```bash
# Create schema
psql -h localhost -p 5432 -U raguser -d ragdb -f database/init/01_schema.sql

# Verify tables
psql -h localhost -p 5432 -U raguser -d ragdb -c "\dt"
```

#### Neo4j
```bash
# Run Cypher setup
cypher-shell -a bolt://localhost:7687 -u neo4j -p neo4j_password_123 -f database/init/02_neo4j_setup.cypher

# Verify nodes
cypher-shell -a bolt://localhost:7687 -u neo4j -p neo4j_password_123 "MATCH (n) RETURN count(n) as node_count"
```

#### Qdrant
```bash
# Create collections
curl -X PUT "http://localhost:6333/collections/documents" \
  -H "api-key: qdrant_api_key_123" \
  -H "Content-Type: application/json" \
  -d '{"vectors": {"size": 1536, "distance": "Cosine"}}'
```

#### Redis
```bash
# Configure Redis
redis-cli -h localhost -p 6379 -a redis_password_123 CONFIG SET maxmemory 256mb
redis-cli -h localhost -p 6379 -a redis_password_123 CONFIG SET maxmemory-policy allkeys-lru
```

## Health Monitoring

### Health Check Script

```bash
python3 database/health_checks.py
```

### Manual Health Checks

#### PostgreSQL
```sql
-- Check connection
SELECT 1;

-- Check table counts
SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';

-- Check database size
SELECT pg_size_pretty(pg_database_size('ragdb'));
```

#### Neo4j
```cypher
-- Check connectivity
RETURN 1;

-- Check node counts
MATCH (n) RETURN labels(n) as type, count(n) as count;

-- Check relationship counts
MATCH ()-[r]->() RETURN type(r) as type, count(r) as count;
```

#### Qdrant
```bash
# Check health
curl http://localhost:6333/health

# List collections
curl http://localhost:6333/collections -H "api-key: qdrant_api_key_123"
```

#### Redis
```bash
# Check connectivity
redis-cli -h localhost -p 6379 -a redis_password_123 ping

# Check memory usage
redis-cli -h localhost -p 6379 -a redis_password_123 info memory
```

## Performance Optimization

### PostgreSQL

- **Connection Pooling**: Use connection pools (10-20 connections)
- **Query Optimization**: Use EXPLAIN ANALYZE for slow queries
- **Indexing**: Composite indexes for complex queries
- **Vacuuming**: Regular autovacuum configuration

### Neo4j

- **Memory Configuration**: Adequate heap and page cache
- **Index Usage**: Query plan analysis
- **Query Optimization**: PROFILE command for query analysis
- **Batch Operations**: Use UNWIND for bulk operations

### Qdrant

- **Vector Quantization**: Enable scalar quantization
- **Collection Optimization**: Configure search parameters
- **Memory Management**: On-disk storage for large datasets
- **Batch Processing**: Upsert multiple vectors at once

### Redis

- **Memory Management**: LRU eviction policy
- **Connection Pooling**: Reuse connections
- **Pipeline Commands**: Batch Redis operations
- **Key Expiration**: Set TTL for cache entries

## Security

### Authentication

- **PostgreSQL**: Role-based access with RLS policies
- **Neo4j**: User authentication with role-based permissions
- **Qdrant**: API key authentication
- **Redis**: Password authentication

### Data Isolation

- **Multi-tenancy**: Row-level security in PostgreSQL
- **Organization Scoping**: All queries filtered by organization_id
- **Network Security**: Database network isolation
- **Audit Logging**: Complete audit trail

## Backup and Recovery

### PostgreSQL

```bash
# Backup
pg_dump -h localhost -p 5432 -U raguser ragdb > backup.sql

# Restore
psql -h localhost -p 5432 -U raguser ragdb < backup.sql
```

### Neo4j

```bash
# Backup
neo4j-admin database backup --database=neo4j --to-path=/backup

# Restore
neo4j-admin database restore --from-path=/backup --database=neo4j
```

### Qdrant

```bash
# Backup collection
curl http://localhost:6333/collections/documents/snapshots -H "api-key: qdrant_api_key_123"
```

### Redis

```bash
# Backup
redis-cli -h localhost -p 6379 -a redis_password_123 BGSAVE

# Restore
redis-server --appendonly yes
```

## Troubleshooting

### Common Issues

#### PostgreSQL Connection Issues
- Check user permissions: `\du` in psql
- Verify database exists: `\l` in psql
- Check network connectivity: `telnet localhost 5432`

#### Neo4j Performance Issues
- Check memory usage: `CALL dbms.listConnections()`
- Monitor query performance: Use PROFILE keyword
- Verify index usage: `EXPLAIN` query plans

#### Qdrant Collection Issues
- Check collection status: `/collections/{name}`
- Monitor memory usage: `/telemetry`
- Verify vector dimensions match

#### Redis Memory Issues
- Monitor memory usage: `INFO memory`
- Check eviction policy: `CONFIG GET maxmemory-policy`
- Analyze key distribution: `INFO keyspace`

### Performance Tuning

#### PostgreSQL Configuration
```ini
# postgresql.conf
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
```

#### Neo4j Configuration
```properties
# neo4j.conf
dbms.memory.heap.initial_size=1G
dbms.memory.heap.max_size=2G
dbms.memory.pagecache.size=1G
```

#### Redis Configuration
```bash
# redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

## API Integration

### Connection Libraries

```python
# PostgreSQL
import asyncpg
conn = await asyncpg.connect(DATABASE_URL)

# Neo4j
from neo4j import AsyncGraphDatabase
driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# Qdrant
from qdrant_client import QdrantClient
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Redis
import redis.asyncio as redis
redis_client = redis.Redis(host='localhost', port=6379, password=REDIS_PASSWORD)
```

### Example Query Patterns

```python
# Multi-database search
async def search_documents(query_text, organization_id):
    # 1. Get query embedding
    embedding = await get_embedding(query_text)

    # 2. Search Qdrant for similar documents
    qdrant_results = qdrant_client.search(
        collection_name="documents",
        query_vector=embedding,
        query_filter={"must": [{"key": "organization_id", "match": {"value": organization_id}}]},
        limit=10
    )

    # 3. Get document details from PostgreSQL
    document_ids = [point.payload["document_id"] for point in qdrant_results]
    documents = await postgres_conn.fetch(
        "SELECT * FROM documents WHERE id = ANY($1) AND organization_id = $2",
        document_ids, organization_id
    )

    # 4. Get related entities from Neo4j
    entity_results = []
    for doc in documents:
        entities = await neo4j_session.run(
            "MATCH (d:Document {id: $doc_id})-[:EXTRACTED_FROM]-(e:Entity) RETURN e",
            doc_id=doc["id"]
        )
        entity_results.extend([record["e"] for record in entities])

    return {
        "documents": documents,
        "entities": entity_results,
        "search_metadata": {
            "query": query_text,
            "results_count": len(documents),
            "entities_found": len(entity_results)
        }
    }
```

## Monitoring and Analytics

### Key Metrics

#### PostgreSQL
- Connection count
- Query latency
- Database size
- Table sizes
- Index usage

#### Neo4j
- Node/relationship counts
- Query performance
- Memory usage
- Cache hit rates

#### Qdrant
- Collection sizes
- Search latency
- Memory usage
- Index status

#### Redis
- Memory usage
- Hit rates
- Connection count
- Operations per second

### Alerting

Set up alerts for:
- Database connection failures
- High query latency (>2 seconds)
- Low cache hit rates (<80%)
- Memory usage (>90%)

## Future Enhancements

### Scalability
- Read replicas for PostgreSQL
- Neo4j clustering
- Qdrant sharding
- Redis clustering

### Performance
- Materialized views
- Graph embeddings
- Advanced caching strategies
- Query optimization

### Features
- Real-time synchronization
- Advanced analytics
- Machine learning integration
- Automated backups

---

*Last updated: October 2024*