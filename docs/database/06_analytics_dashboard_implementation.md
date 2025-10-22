# Phase 6: Database Implementation & Optimization - Analytics Dashboard

## Overview

This document covers the complete database implementation and optimization for the Knowledge Graph Analytics Dashboard. This implementation provides a high-performance, scalable, and secure foundation for real-time analytics and reporting in the Multimodal Enterprise RAG System.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Optimized Schema Design](#optimized-schema-design)
3. [Performance Optimizations](#performance-optimizations)
4. [Security Implementation](#security-implementation)
5. [Monitoring & Maintenance](#monitoring--maintenance)
6. [Query Optimization](#query-optimization)
7. [Deployment Guide](#deployment-guide)
8. [Troubleshooting](#troubleshooting)

## Architecture Overview

### Core Components

The analytics dashboard database consists of several key components:

```
┌─────────────────────────────────────────────────────────────┐
│                    Analytics Dashboard                      │
├─────────────────────────────────────────────────────────────┤
│  Real-time Metrics    │  Historical Analytics               │
│  - Live Counts       │  - Time Series Aggregations         │
│  - Performance KPIs  │  - Trend Analysis                   │
│  - Health Status     │  - Growth Metrics                   │
├─────────────────────────────────────────────────────────────┤
│  Caching Layer       │  Materialized Views                 │
│  - Query Results     │  - Pre-computed Aggregations        │
│  - Computation Cache │  - Dashboard Snapshots             │
│  - Session Data      │  - Performance Reports             │
├─────────────────────────────────────────────────────────────┤
│  Security Layer      │  Monitoring & Maintenance          │
│  - RLS Policies      │  - Health Checks                    │
│  - Row-level Access  │  - Performance Monitoring          │
│  - Audit Logging     │  - Automated Cleanup               │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Source Data → Triggers → Cache → Analytics Procedures → Materialized Views → Dashboard
     ↓              ↓         ↓              ↓                    ↓
  Entities/      Real-time   Query         Background          Real-time
  Relationships   Updates    Caching       Computation          API
  Documents       ↓           ↓              ↓                   ↓
  User Sessions   Audit Log  Hit/Miss      Scheduled Jobs      Cached
```

## Optimimized Schema Design

### Core Analytics Tables

#### Entity Analytics (`entity_analytics_optimized`)
```sql
CREATE TABLE entity_analytics_optimized (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    time_bucket TIMESTAMPTZ NOT NULL,
    bucket_type VARCHAR(20) NOT NULL CHECK (bucket_type IN ('hour', 'day', 'week', 'month')),

    -- Core metrics
    total_entities INTEGER DEFAULT 0,
    new_entities INTEGER DEFAULT 0,
    entity_growth_rate DECIMAL(10,6) DEFAULT 0,

    -- Type breakdown (JSONB for flexibility)
    entity_type_counts JSONB DEFAULT '{}',
    entity_type_percentages JSONB DEFAULT '{}',

    -- Quality metrics
    avg_confidence_score DECIMAL(5,4) DEFAULT 0,
    high_quality_entities INTEGER DEFAULT 0,
    low_quality_entities INTEGER DEFAULT 0,

    -- Processing analytics
    processing_success_rate DECIMAL(5,4) DEFAULT 0,
    avg_processing_time_ms INTEGER DEFAULT 0,

    -- Optimization fields
    data_freshness_at TIMESTAMPTZ DEFAULT NOW(),
    cache_key VARCHAR(255),

    -- Partitioning
    UNIQUE(organization_id, time_bucket, bucket_type)
) PARTITION BY RANGE (time_bucket);
```

**Key Features:**
- **Partitioning**: Time-based partitioning for efficient queries
- **JSONB Columns**: Flexible type breakdown without schema changes
- **Optimization Fields**: Cache keys and freshness timestamps
- **BRIN Indexes**: Efficient for time-series data

#### Relationship Analytics (`relationship_analytics_optimized`)
```sql
CREATE TABLE relationship_analytics_optimized (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    time_bucket TIMESTAMPTZ NOT NULL,
    bucket_type VARCHAR(20) NOT NULL,

    -- Relationship metrics
    total_relationships INTEGER DEFAULT 0,
    new_relationships INTEGER DEFAULT 0,
    relationship_growth_rate DECIMAL(10,6) DEFAULT 0,

    -- Type and strength distribution
    relationship_type_counts JSONB DEFAULT '{}',
    relationship_strength_distribution JSONB DEFAULT '{}',

    -- Graph connectivity metrics
    avg_connections_per_entity DECIMAL(8,4) DEFAULT 0,
    isolated_entities INTEGER DEFAULT 0,
    hub_entities INTEGER DEFAULT 0,
    bridge_entities INTEGER DEFAULT 0,

    -- Bidirectional analysis
    bidirectional_relationships INTEGER DEFAULT 0,
    bidirectional_percentage DECIMAL(5,4) DEFAULT 0
) PARTITION BY RANGE (time_bucket);
```

#### Document Analytics (`document_analytics_optimized`)
```sql
CREATE TABLE document_analytics_optimized (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    time_bucket TIMESTAMPTZ NOT NULL,
    bucket_type VARCHAR(20) NOT NULL,

    -- Processing metrics
    total_documents INTEGER DEFAULT 0,
    processed_documents INTEGER DEFAULT 0,
    processing_success_rate DECIMAL(5,4) DEFAULT 0,
    avg_processing_time_ms INTEGER DEFAULT 0,

    -- Quality and storage analytics
    avg_quality_score DECIMAL(5,4) DEFAULT 0,
    total_storage_gb DECIMAL(10,2) DEFAULT 0,
    storage_growth_rate DECIMAL(10,6) DEFAULT 0,

    -- Extraction analytics
    avg_entities_extracted DECIMAL(8,4) DEFAULT 0,
    extraction_success_rates JSONB DEFAULT '{}',

    -- Performance optimization
    processing_efficiency_score DECIMAL(5,4) DEFAULT 0,
    storage_utilization_rate DECIMAL(5,4) DEFAULT 0
) PARTITION BY RANGE (time_bucket);
```

### Caching Infrastructure

#### Analytics Cache (`analytics_cache`)
```sql
CREATE TABLE analytics_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID,
    cache_key VARCHAR(255) NOT NULL,
    cache_type VARCHAR(100) NOT NULL,

    -- Cache metadata
    computation_parameters JSONB DEFAULT '{}',
    data_freshness_at TIMESTAMPTZ,

    -- Cached results
    cached_results JSONB NOT NULL,
    result_size_bytes INTEGER,

    -- Cache management
    cache_ttl_seconds INTEGER DEFAULT 3600,
    hit_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),
    computation_time_ms INTEGER,

    -- Expiration
    expires_at TIMESTAMPTZ NOT NULL,

    UNIQUE(cache_key, organization_id, cache_type)
);
```

### Supporting Tables

#### Security & Audit (`analytics_security_log`)
```sql
CREATE TABLE analytics_security_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    user_id UUID,
    action_type VARCHAR(100) NOT NULL,
    table_name VARCHAR(255),
    record_id UUID,
    security_level VARCHAR(50) DEFAULT 'medium',
    action_details JSONB DEFAULT '{}',
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT NOW()
) PARTITION BY RANGE (created_at);
```

#### Maintenance Log (`analytics_maintenance_log`)
```sql
CREATE TABLE analytics_maintenance_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    maintenance_type VARCHAR(100) NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'pending',
    details JSONB DEFAULT '{}',
    error_message TEXT
);
```

## Performance Optimizations

### Indexing Strategy

#### BRIN Indexes for Time-Series
```sql
-- Efficient for time-based queries on large datasets
CREATE INDEX CONCURRENTLY idx_entity_analytics_org_time_brin
    ON entity_analytics_optimized USING BRIN (organization_id, time_bucket);

CREATE INDEX CONCURRENTLY idx_relationship_analytics_org_time_brin
    ON relationship_analytics_optimized USING BRIN (organization_id, time_bucket);
```

#### GIN Indexes for JSONB
```sql
-- Fast JSONB queries for type distributions
CREATE INDEX CONCURRENTLY idx_entity_analytics_gin_entity_types
    ON entity_analytics_optimized USING GIN (entity_type_counts);

CREATE INDEX CONCURRENTLY idx_relationship_analytics_gin_strength
    ON relationship_analytics_optimized USING GIN (relationship_strength_distribution);
```

#### Composite Indexes for Common Queries
```sql
-- Optimized for dashboard queries
CREATE INDEX CONCURRENTLY idx_entity_analytics_composite_lookup
    ON entity_analytics_optimized (organization_id, bucket_type, time_bucket DESC);

CREATE INDEX CONCURRENTLY idx_analytics_cache_expires
    ON analytics_cache (expires_at, organization_id);
```

#### Partial Indexes for Performance
```sql
-- Index only frequently accessed data
CREATE INDEX CONCURRENTLY idx_entity_analytics_growth_rate
    ON entity_analytics_optimized (entity_growth_rate DESC, time_bucket DESC)
    WHERE entity_growth_rate > 0;

CREATE INDEX CONCURRENTLY idx_analytics_cache_hot
    ON analytics_cache (last_accessed_at DESC, hit_count DESC)
    WHERE hit_count > 10;
```

### Materialized Views

#### Real-time Dashboard Metrics
```sql
CREATE MATERIALIZED VIEW real_time_dashboard_metrics_optimized AS
WITH org_stats AS (
    SELECT id, name, current_storage_gb, storage_limit_gb
    FROM organizations WHERE is_active = TRUE
),
-- Complex joins and aggregations for dashboard
SELECT
    os.id as organization_id,
    os.name as organization_name,
    -- Entity metrics
    COALESCE(em.total_entities, 0) as total_entities,
    COALESCE(em.new_entities_today, 0) as new_entities_today,
    -- Document metrics
    COALESCE(dm.total_documents, 0) as total_documents,
    COALESCE(dm.processing_success_rate, 0) as processing_success_rate,
    -- User metrics
    COALESCE(um.active_users_today, 0) as active_users_today,
    -- Calculated metrics
    CASE
        WHEN COALESCE(dm.total_documents, 0) = 0 THEN 0
        ELSE COALESCE(em.total_entities, 0)::DECIMAL / COALESCE(dm.total_documents, 1)
    END as entities_per_document_ratio,
    -- System health score
    LEAST(1.0, GREATEST(0,
        (COALESCE(em.avg_confidence, 0) * 0.3 +
         COALESCE(dm.avg_quality_score, 0) * 0.3 +
         COALESCE(um.search_success_rate, 0) * 0.2 +
         (1 - COALESCE(pm.avg_error_rate, 0)) * 0.2)
    )) as system_health_score
FROM org_stats os
LEFT JOIN entity_metrics em ON os.id = em.organization_id
LEFT JOIN document_metrics dm ON os.id = dm.organization_id
LEFT JOIN user_metrics um ON os.id = um.organization_id;
```

#### Performance Monitoring Views
```sql
CREATE MATERIALIZED VIEW query_performance_metrics AS
SELECT
    query_type,
    COUNT(*) as execution_count,
    AVG(execution_time_ms) as avg_execution_time,
    MAX(execution_time_ms) as max_execution_time,
    SUM(execution_time_ms) as total_execution_time,
    AVG(rows_returned) as avg_rows_returned
FROM analytics_query_log
WHERE executed_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY query_type;
```

### Query Optimization Techniques

#### Session Configuration
```sql
-- Configure optimal settings for different query types
SELECT configure_analytics_session('analytics_heavy', 512);
-- Sets: work_mem=512MB, maintenance_work_mem=2GB, max_parallel_workers=8

SELECT configure_analytics_session('real_time', 64);
-- Sets: work_mem=64MB, enable_seqscan=off, optimize for speed
```

#### Query Patterns
```sql
-- Optimized time-series query using partitioning
SELECT time_bucket, total_entities, new_entities
FROM entity_analytics_optimized
WHERE organization_id = $1
  AND time_bucket >= $2
  AND time_bucket < $3
  AND bucket_type = 'day'
ORDER BY time_bucket DESC
LIMIT 1000;
-- Uses partition pruning, index-only scans
```

## Security Implementation

### Row-Level Security (RLS)

#### Organization-based Data Isolation
```sql
-- Enable RLS on all analytics tables
ALTER TABLE entity_analytics_optimized ENABLE ROW LEVEL SECURITY;

-- Create organization-scoped policies
CREATE POLICY entity_analytics_org_policy ON entity_analytics_optimized
    FOR ALL TO analytics_viewer
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);
```

#### Role-based Access Control
```sql
-- Create analytics roles
CREATE ROLE analytics_viewer;   -- Read-only access
CREATE ROLE analytics_editor;   -- Read + write
CREATE ROLE analytics_admin;    -- Full permissions

-- Grant role hierarchy
GRANT analytics_viewer TO analytics_editor;
GRANT analytics_editor TO analytics_admin;
```

#### Session Context Management
```sql
-- Set secure session context
SELECT set_analytics_session_context(
    organization_id => 'org-uuid',
    user_id => 'user-uuid',
    user_role => 'editor'
);

-- Check permissions in functions
CREATE OR REPLACE FUNCTION check_analytics_access(
    p_organization_id UUID,
    p_required_permission TEXT DEFAULT 'read'
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN current_setting('app.current_organization_id', true)::UUID = p_organization_id
           AND has_privilege(current_user, p_required_permission);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### Data Masking

#### Privacy-Preserving Views
```sql
CREATE OR REPLACE VIEW user_analytics_privacy_preserving AS
SELECT
    organization_id,
    time_bucket,
    total_sessions,
    avg_session_duration_seconds,
    search_success_rate,
    -- Remove personally identifiable information
    CASE
        WHEN avg_user_satisfaction_score >= 4.5 THEN 'excellent'
        WHEN avg_user_satisfaction_score >= 3.5 THEN 'good'
        ELSE 'needs_improvement'
    END as satisfaction_category
FROM user_interaction_analytics_optimized
WHERE organization_id = current_setting('app.current_organization_id', true)::UUID;
```

#### Sensitive Data Masking Function
```sql
CREATE OR REPLACE FUNCTION mask_user_analytics_data(
    p_data JSONB,
    p_masking_level TEXT DEFAULT 'standard'
) RETURNS JSONB AS $$
BEGIN
    CASE p_masking_level
        WHEN 'strict' THEN
            RETURN p_data - ARRAY['user_id', 'email', 'ip_address'];
        WHEN 'standard' THEN
            RETURN jsonb_build_object(
                'user_count', (p_data->>'user_count')::INTEGER,
                'anonymized_patterns', p_data - ARRAY['user_id', 'email']
            );
        ELSE
            RETURN p_data;
    END CASE;
END;
$$ LANGUAGE plpgsql;
```

### Audit Logging

#### Comprehensive Security Audit
```sql
CREATE TRIGGER analytics_security_audit_trigger
    AFTER INSERT OR UPDATE OR DELETE ON analytics_tables
    FOR EACH ROW
    EXECUTE FUNCTION trigger_analytics_security_audit();

-- Log structure includes:
- organization_id, user_id, action_type
- table_name, record_id, security_level
- old_values, new_values, ip_address, timestamp
```

## Monitoring & Maintenance

### Health Monitoring

#### System Health Dashboard
```sql
SELECT * FROM analytics_health_check(detailed => true);
-- Returns:
-- - Database connectivity status
-- - Table sizes and bloat analysis
-- - Index usage statistics
-- - Cache performance metrics
-- - Recent activity levels
```

#### Performance Metrics
```sql
-- Get slow analytics queries
SELECT * FROM get_slow_analytics_queries(
    p_min_exec_time_ms => 1000,
    p_min_calls => 5
);

-- Analyze query patterns
SELECT * FROM analyze_analytics_query_patterns();
-- Returns optimization suggestions for:
-- - Time-series queries
-- - Join operations
-- - JSONB aggregations
-- - Materialized view usage
```

### Automated Maintenance

#### Comprehensive Maintenance Procedure
```sql
SELECT * FROM run_analytics_maintenance(
    p_maintenance_type => 'full',
    p_organization_id => NULL, -- All organizations
    p_dry_run => FALSE
);
-- Performs:
-- 1. Cache cleanup
-- 2. Analytics aggregation updates
-- 3. Statistics optimization
-- 4. Partition maintenance
-- 5. Index maintenance
-- 6. Data validation
-- 7. Performance monitoring
```

#### Scheduled Maintenance Tasks
```sql
-- Daily maintenance (2 AM)
SELECT run_analytics_maintenance('daily');

-- Weekly maintenance (Sunday 3 AM)
SELECT run_analytics_maintenance('weekly');

-- Monthly maintenance (First day of month)
SELECT run_analytics_maintenance('monthly');
```

### Partition Management

#### Automatic Partition Creation
```sql
-- Creates partitions for next 6 months
SELECT create_entity_analytics_partitions();

-- Drops old partitions beyond retention
SELECT maintain_analytics_partitions(
    p_retention_months => 24,
    p_future_months => 6
);
```

## Query Optimization

### Connection Pooling

#### PgBouncer Configuration
```ini
[databases]
analytics_db = host=localhost port=5432 dbname=rag_analytics

[pgbouncer]
pool_mode = transaction
max_client_conn = 200
default_pool_size = 25
min_pool_size = 5
reserve_pool_size = 5
server_reset_query = DISCARD ALL
server_lifetime = 3600
```

#### Session Configuration
```sql
-- Configure session for optimal analytics performance
SELECT configure_analytics_session(
    p_session_type => 'analytics_heavy',
    p_work_mem_mb => 512
);
```

### Query Performance

#### Optimized Query Templates
```sql
-- Time-series analytics query
SELECT * FROM get_analytics_time_series_optimized(
    p_organization_id => 'org-uuid',
    p_start_time => NOW() - INTERVAL '30 days',
    p_end_time => NOW(),
    p_bucket_type => 'day',
    p_analytics_type => 'entity'
);

-- Top N analysis query
SELECT * FROM get_top_entities_optimized(
    p_organization_id => 'org-uuid',
    p_limit => 100,
    p_metric => 'centrality',
    p_entity_type => 'person'
);
```

#### Performance Monitoring
```sql
-- Enable query monitoring
SELECT setup_query_monitoring();

-- Monitor slow queries
SELECT * FROM get_slow_analytics_queries();

-- Analyze query patterns for optimization
SELECT * FROM analyze_analytics_query_patterns();
```

### Dynamic Index Management

#### Missing Index Detection
```sql
-- Suggest indexes based on query patterns
SELECT * FROM suggest_missing_indexes();
-- Returns:
-- - table_name, column_names, index_type
-- - estimated_benefit, suggestion_reason

-- Create recommended indexes
SELECT * FROM create_recommended_indexes(p_dry_run => FALSE);
```

## Deployment Guide

### Prerequisites

1. **PostgreSQL 14+** with required extensions
2. **Sufficient disk space** for partitions and indexes
3. **Appropriate memory configuration** for analytics workloads
4. **Backup strategy** before deployment

### Deployment Steps

1. **Pre-deployment Checklist**
   ```sql
   -- Check PostgreSQL version
   SELECT version();

   -- Verify extensions
   SELECT * FROM pg_extension WHERE extname IN (
       'pg_stat_statements', 'btree_gin', 'btree_gist', 'pg_trgm'
   );

   -- Check available disk space
   SELECT pg_size_pretty(pg_database_size(current_database()));
   ```

2. **Run Deployment Script**
   ```bash
   # Dry run first
   psql -d rag_analytics -c "SET deployment.dry_run = TRUE;"
   psql -d rag_analytics -f database/deployment/deploy_analytics_dashboard.sql

   # Actual deployment
   psql -d rag_analytics -f database/deployment/deploy_analytics_dashboard.sql
   ```

3. **Post-deployment Validation**
   ```sql
   -- Verify deployment
   SELECT * FROM analytics_deployment_log
   ORDER BY started_at DESC LIMIT 1;

   -- Run health check
   SELECT * FROM analytics_health_check(detailed => TRUE);

   -- Test analytics functions
   SELECT compute_entity_analytics_aggregated(
       'org-uuid',
       NOW() - INTERVAL '7 days',
       NOW()
   );
   ```

4. **Configure Connection Pooling**
   ```bash
   # Install PgBouncer
   sudo apt-get install pgbouncer

   # Configure PgBouncer
   sudo cp /etc/pgbouncer/pgbouncer.ini /etc/pgbouncer/pgbouncer.ini.backup
   # Update configuration with provided settings

   # Restart PgBouncer
   sudo systemctl restart pgbouncer
   ```

5. **Set Up Scheduled Maintenance**
   ```bash
   # Add to crontab
   0 2 * * * psql -d rag_analytics -c "SELECT run_analytics_maintenance('daily');"
   0 3 * * 0 psql -d rag_analytics -c "SELECT run_analytics_maintenance('weekly');"
   ```

### Configuration Tuning

#### PostgreSQL Configuration
```ini
# Memory settings
shared_buffers = 4GB                    # 25% of RAM
work_mem = 256MB                        # For analytics queries
maintenance_work_mem = 1GB
effective_cache_size = 12GB             # 75% of RAM

# Parallelism
max_parallel_workers = 8
max_parallel_workers_per_gather = 4
parallel_tuple_cost = 0.1
parallel_setup_cost = 1000.0

# Analytics optimization
random_page_cost = 1.1                  # SSD optimization
effective_io_concurrency = 200           # SSD concurrent I/O
jit = off                               # Disable JIT for analytics

# Logging
log_min_duration_statement = 5000        # Log slow queries
log_checkpoints = on
log_connections = on
log_disconnections = on
```

## Troubleshooting

### Common Issues

#### Slow Query Performance
```sql
-- Identify slow queries
SELECT * FROM get_slow_analytics_queries();

-- Check missing indexes
SELECT * FROM suggest_missing_indexes();

-- Analyze query plan
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM entity_analytics_optimized
WHERE organization_id = $1 AND time_bucket >= $2;
```

#### High Memory Usage
```sql
-- Check current memory usage
SELECT * FROM monitor_connection_health();

-- Reduce work_mem for high concurrency
SELECT configure_analytics_session('analytics_light', 64);

-- Monitor cache usage
SELECT
    cache_type,
    COUNT(*) as cache_entries,
    SUM(result_size_bytes) / (1024^2) as total_size_mb,
    AVG(hit_count) as avg_hit_count
FROM analytics_cache
GROUP BY cache_type;
```

#### Storage Issues
```sql
-- Check table sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) -
                   pg_relation_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables
WHERE tablename LIKE '%analytics%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check partition status
SELECT * FROM maintain_analytics_partitions(p_dry_run => TRUE);
```

#### Cache Performance
```sql
-- Check cache hit rates
SELECT
    cache_type,
    COUNT(*) as total_entries,
    SUM(hit_count) as total_hits,
    SUM(hit_count)::DECIMAL / COUNT(*) as avg_hit_rate,
    COUNT(*) FILTER (WHERE expires_at < NOW()) as expired_entries
FROM analytics_cache
GROUP BY cache_type;

-- Clean up expired cache
SELECT * FROM cleanup_expired_cache();
```

### Performance Tuning

#### Query Optimization
```sql
-- Rebuild indexes if fragmented
SELECT * FROM maintain_analytics_indexes();

-- Update statistics
SELECT * FROM optimize_analytics_statistics();

-- Check for table bloat
SELECT
    tablename,
    pg_size_pretty(bloat_size) as bloat,
    pg_size_pretty(total_size) as total_size
FROM (
    SELECT
        tablename,
        (pg_total_relation_size(schemaname||'.'||tablename) *
         CASE WHEN avg_tup_len > 0 THEN (fillfactor/100.0) ELSE 0.9 END -
         pg_relation_size(schemaname||'.'||tablename)) as bloat_size,
        pg_total_relation_size(schemaname||'.'||tablename) as total_size
    FROM pg_stats
    WHERE schemaname = 'public'
      AND tablename LIKE '%analytics%'
) bloat_analysis
WHERE bloat_size > 0
ORDER BY bloat_size DESC;
```

### Monitoring Queries

#### System Health
```sql
-- Overall system health
SELECT * FROM system_health_dashboard_optimized;

-- Recent performance
SELECT
    time_bucket,
    avg_response_time_ms,
    error_rate,
    timeout_rate,
    user_engagement_score
FROM user_interaction_analytics_optimized
WHERE time_bucket >= NOW() - INTERVAL '24 hours'
  AND bucket_type = 'hour'
ORDER BY time_bucket DESC;
```

#### Cache Metrics
```sql
-- Cache performance
SELECT
    date_trunc('hour', created_at) as hour,
    COUNT(*) as cache_entries_created,
    SUM(hit_count) as total_hits,
    AVG(computation_time_ms) as avg_computation_time
FROM analytics_cache
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY date_trunc('hour', created_at)
ORDER BY hour DESC;
```

This comprehensive implementation provides a robust, scalable, and secure foundation for the Knowledge Graph Analytics Dashboard, with built-in performance optimizations, monitoring capabilities, and automated maintenance procedures.