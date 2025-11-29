# Knowledge Graph Analytics Dashboard - Database Schema

## Overview

This document outlines the comprehensive database schema for the Knowledge Graph Analytics Dashboard feature in the Multimodal Enterprise RAG System. The schema is designed for scalability, performance, and real-time analytics capabilities.

## Architecture Principles

### 1. Multi-Tenant Design
- All tables include `organization_id` for data isolation
- Row-Level Security (RLS) policies ensure tenant separation
- Partitioned tables for efficient time-series queries

### 2. Performance Optimization
- **Partitioning**: Time-series data partitioned by month/quarter
- **Indexing**: Comprehensive indexing strategy for common query patterns
- **Caching**: Materialized views and cache tables for expensive computations
- **Aggregation**: Pre-computed aggregations for dashboard performance

### 3. Scalability Considerations
- **Horizontal Scaling**: Partitioned tables enable parallel processing
- **Write Performance**: Efficient inserts with minimal locking
- **Read Performance**: Optimized for dashboard and reporting queries
- **Storage Optimization**: JSONB for flexible schema evolution

### 4. Real-Time Capabilities
- **Materialized Views**: Real-time dashboard metrics
- **Cache Tables**: Fast access to computed results
- **Trigger-Based Updates**: Automatic analytics updates on data changes
- **WebSocket Integration**: Live dashboard updates

## Logical Data Model

### Core Analytics Entities

```
┌─────────────────────────┐
│    EntityAnalytics      │
├─────────────────────────┤
│ organization_id         │
│ time_bucket             │
│ bucket_type             │
│ total_entities          │
│ new_entities            │
│ entity_growth_rate      │
│ entity_type_counts      │
│ avg_confidence_score    │
│ processing_success_rate │
│ entities_per_document   │
└─────────────────────────┘
```

```
┌─────────────────────────┐
│ RelationshipAnalytics    │
├─────────────────────────┤
│ organization_id         │
│ time_bucket             │
│ bucket_type             │
│ total_relationships     │
│ new_relationships       │
│ relationship_strength_  │
│   distribution          │
│ avg_connections_per_    │
│   entity                │
│ hub_entities            │
│ bidirectional_          │
│   percentage            │
└─────────────────────────┘
```

```
┌─────────────────────────┐
│ GraphMetricsAnalytics   │
├─────────────────────────┤
│ organization_id         │
│ computed_at             │
│ top_entities_by_        │
│   centrality            │
│ graph_density           │
│ clustering_coefficient  │
│ number_of_communities   │
│ component_analysis      │
│ temporal_evolution_     │
│   metrics               │
└─────────────────────────┘
```

### Dashboard Infrastructure

```
┌─────────────────────────┐
│ DashboardConfigurations │
├─────────────────────────┤
│ organization_id         │
│ user_id                 │
│ config_name             │
│ layout                  │
│ widgets                 │
│ filters                 │
│ auto_refresh_enabled    │
│ permissions             │
└─────────────────────────┘
```

```
┌─────────────────────────┐
│ WidgetDefinitions       │
├─────────────────────────┤
│ widget_name             │
│ widget_type             │
│ widget_category         │
│ data_source             │
│ data_query              │
│ default_config          │
│ chart_type              │
│ cache_duration          │
│ required_permissions    │
└─────────────────────────┘
```

### Reporting and Export

```
┌─────────────────────────┐
│ CustomAnalyticsReports  │
├─────────────────────────┤
│ organization_id         │
│ report_name             │
│ report_definition       │
│ schedule_config         │
│ auto_generate           │
│ output_formats          │
│ delivery_methods        │
│ access_control          │
└─────────────────────────┘
```

### Performance and Caching

```
┌─────────────────────────┐
│ AnalyticsCache          │
├─────────────────────────┤
│ organization_id         │
│ cache_key               │
│ cache_type              │
│ computation_parameters  │
│ cached_results          │
│ cache_ttl_seconds       │
│ hit_count               │
│ computation_time_ms     │
└─────────────────────────┘
```

## Physical Data Model

### Table Structure Details

#### 1. Entity Analytics (`entity_analytics`)

**Purpose**: Time-series aggregation of entity-related metrics

**Partitioning**: By month (`PARTITION BY RANGE (time_bucket)`)

**Key Features**:
- Supports multiple time bucket types (hour, day, week, month)
- Tracks entity growth, quality metrics, and processing performance
- JSONB fields for flexible entity type breakdowns
- Efficient for trend analysis and historical comparisons

**Storage Size**: ~500KB per organization per day (estimated)

**Query Patterns**:
```sql
-- Entity growth trend
SELECT time_bucket, total_entities, new_entities, entity_growth_rate
FROM entity_analytics
WHERE organization_id = $1
  AND bucket_type = 'day'
  AND time_bucket >= NOW() - INTERVAL '30 days'
ORDER BY time_bucket DESC;

-- Entity type distribution
SELECT entity_type_counts, entity_type_percentages
FROM entity_analytics
WHERE organization_id = $1
  AND bucket_type = 'day'
  AND time_bucket = DATE_TRUNC('day', NOW());
```

#### 2. Relationship Analytics (`relationship_analytics`)

**Purpose**: Aggregated metrics for entity relationships and graph connectivity

**Partitioning**: By month (`PARTITION BY RANGE (time_bucket)`)

**Key Features**:
- Tracks relationship strength and connectivity patterns
- Identifies hub entities and network structure
- Monitors bidirectional relationships
- JSONB for flexible relationship type analysis

**Storage Size**: ~300KB per organization per day (estimated)

#### 3. Graph Metrics Analytics (`graph_metrics_analytics`)

**Purpose**: Cached results of expensive graph algorithm computations

**Non-Partitioned**: Computed on-demand with versioning

**Key Features**:
- Stores centrality calculations (betweenness, closeness, PageRank)
- Community detection results
- Component analysis
- Temporal evolution metrics
- Expensive computations cached for dashboard performance

**Storage Size**: ~2MB per computation (varies by graph size)

#### 4. Real-Time Dashboard Metrics (`real_time_dashboard_metrics`)

**Purpose**: Materialized view for real-time KPI display

**Refresh Strategy**: Every 5 minutes or on-demand

**Key Features**:
- Single source of truth for dashboard metrics
- Joins multiple source tables for comprehensive view
- Optimized for dashboard rendering
- Supports real-time WebSocket updates

**Storage Size**: ~50KB per organization

#### 5. Dashboard Configurations (`dashboard_configurations`)

**Purpose**: User and organization dashboard customizations

**Key Features**:
- Hierarchical configuration (user > role > organization defaults)
- JSONB layout storage for flexible widget arrangements
- Permission-based access control
- Auto-refresh settings

**Storage Size**: ~10KB per configuration

## Indexing Strategy

### Primary Indexes

1. **Time-based queries**: `(organization_id, time_bucket DESC)`
2. **Metric-based queries**: `(metric_name, metric_value DESC)`
3. **Status queries**: `(status, created_at DESC)`
4. **Cache lookups**: `(cache_key, organization_id)`

### Composite Indexes

```sql
-- Entity analytics trend queries
CREATE INDEX idx_entity_analytics_org_time
ON entity_analytics(organization_id, time_bucket DESC);

-- Relationship analytics by connectivity
CREATE INDEX idx_relationship_analytics_connectivity
ON relationship_analytics(avg_connections_per_entity DESC, time_bucket DESC);

-- Graph metrics by computation time
CREATE INDEX idx_graph_metrics_analytics_computed
ON graph_metrics_analytics(organization_id, computed_at DESC);

-- Report execution tracking
CREATE INDEX idx_report_executions_status_time
ON report_executions(execution_status, started_at DESC);
```

### JSONB Indexes

```sql
-- Widget definition filtering
CREATE INDEX idx_widget_definitions_categories
ON widget_definitions USING GIN((widget_category, widget_type));

-- Configuration searches
CREATE INDEX idx_dashboard_configurations_widgets
ON dashboard_configurations USING GIN(widgets);
```

## Query Performance Optimization

### Materialized Views

1. **Real-Time Dashboard Metrics**: Refreshed every 5 minutes
2. **Entity Growth Trends**: Daily aggregations for trend analysis
3. **System Health Dashboard**: Combined view of system metrics

### Common Query Patterns

#### Dashboard Loading
```sql
-- Optimized dashboard query (uses materialized view)
SELECT * FROM real_time_dashboard_metrics
WHERE organization_id = $1;

-- Recent trends (pre-aggregated data)
SELECT time_bucket, total_entities, entity_growth_rate
FROM entity_analytics
WHERE organization_id = $1
  AND bucket_type = 'day'
  AND time_bucket >= NOW() - INTERVAL '7 days'
ORDER BY time_bucket DESC;
```

#### Historical Analysis
```sql
-- Year-over-year comparison
SELECT
    DATE_TRUNC('month', time_bucket) as month,
    SUM(total_entities) as monthly_entities,
    SUM(new_entities) as monthly_new_entities
FROM entity_analytics
WHERE organization_id = $1
  AND bucket_type = 'day'
  AND time_bucket >= NOW() - INTERVAL '2 years'
GROUP BY DATE_TRUNC('month', time_bucket)
ORDER BY month DESC;
```

#### Performance Monitoring
```sql
-- Processing performance trends
SELECT
    time_bucket,
    processing_success_rate,
    avg_processing_time_ms,
    avg_quality_score
FROM document_analytics
WHERE organization_id = $1
  AND bucket_type = 'hour'
  AND time_bucket >= NOW() - INTERVAL '24 hours'
ORDER BY time_bucket DESC;
```

## Caching Strategy

### Multi-Level Caching

1. **Application Level**: Redis for frequently accessed metrics
2. **Database Level**: `analytics_cache` table for expensive computations
3. **Materialized Views**: Pre-computed dashboard metrics
4. **Query Result Caching**: PostgreSQL query cache

### Cache Invalidation

```sql
-- Function to invalidate cache on data changes
CREATE OR REPLACE FUNCTION invalidate_analytics_cache(
    p_organization_id UUID,
    p_cache_type VARCHAR(100)
) RETURNS VOID AS $$
BEGIN
    DELETE FROM analytics_cache
    WHERE organization_id = p_organization_id
      AND cache_type = p_cache_type;

    -- Refresh materialized view
    REFRESH MATERIALIZED VIEW CONCURRENTLY real_time_dashboard_metrics;
END;
$$ LANGUAGE plpgsql;
```

## Data Consistency and Integrity

### Constraints and Validation

1. **Foreign Keys**: All organization references validated
2. **Check Constraints**: Metric ranges and valid values
3. **Unique Constraints**: Prevent duplicate aggregations
4. **Non-Null Constraints**: Essential analytics fields

### Transaction Management

```sql
-- Atomic analytics updates
BEGIN;
    -- Update entity counts
    INSERT INTO entity_analytics (...) VALUES (...);

    -- Update relationship counts
    INSERT INTO relationship_analytics (...) VALUES (...);

    -- Invalidate cache
    PERFORM invalidate_analytics_cache(org_id, 'entity_analytics');
COMMIT;
```

## Scaling Considerations

### Horizontal Scaling

1. **Partition Pruning**: Queries only scan relevant partitions
2. **Parallel Query Execution**: PostgreSQL parallelizes across partitions
3. **Read Replicas**: Analytics queries directed to read replicas
4. **Connection Pooling**: PgBouncer for efficient connection management

### Vertical Scaling

1. **Memory Optimization**: Work_mem settings for large aggregations
2. **CPU Allocation**: Dedicated analytics query workers
3. **I/O Optimization**: SSD storage for time-series data
4. **Network**: 10GbE for fast data transfer

## Monitoring and Maintenance

### Automated Maintenance

```sql
-- Cleanup old partitions (90-day retention)
CREATE OR REPLACE FUNCTION cleanup_old_partitions() RETURNS VOID AS $$
BEGIN
    -- Drop partitions older than 90 days
    FOR partition_name IN
        SELECT tablename
        FROM pg_tables
        WHERE tablename LIKE '%_y2024%'
          AND tablename < format('analytics_%s', to_char(NOW() - INTERVAL '90 days', 'YYYYmm'))
    LOOP
        EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', partition_name);
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Scheduled cleanup (run daily)
SELECT cron.schedule('cleanup-analytics-partitions', '0 2 * * *', 'SELECT cleanup_old_partitions();');
```

### Performance Monitoring

```sql
-- Query performance tracking
SELECT
    query,
    calls,
    total_time,
    mean_time,
    rows
FROM pg_stat_statements
WHERE query LIKE '%analytics_%'
ORDER BY total_time DESC;

-- Index usage analysis
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND tablename LIKE '%analytics%'
ORDER BY idx_scan DESC;
```

## Migration Strategy

### Schema Evolution

1. **Backward Compatibility**: New columns added with DEFAULT values
2. **Feature Flags**: Analytics features controlled by configuration
3. **Gradual Rollout**: Organizations can opt-in to new analytics features
4. **Data Migration**: Existing data processed and migrated in batches

### Rollback Plan

```sql
-- Rollback migration
BEGIN;
    -- Drop new tables
    DROP TABLE IF EXISTS entity_analytics CASCADE;
    DROP TABLE IF EXISTS relationship_analytics CASCADE;
    -- ... other tables

    -- Remove triggers
    DROP TRIGGER IF EXISTS entity_analytics_update_trigger ON entities;

    -- Restore previous state
    -- ... restoration logic
COMMIT;
```

## Security Considerations

### Data Privacy

1. **Row-Level Security**: Tenant isolation enforced at database level
2. **Column-Level Security**: Sensitive metrics restricted by role
3. **Audit Logging**: All analytics queries logged for compliance
4. **Data Retention**: Configurable retention policies for analytics data

### Access Control

```sql
-- Role-based access to analytics
CREATE ROLE analytics_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_reader;

CREATE ROLE analytics_admin;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO analytics_admin;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO analytics_admin;
```

## Performance Benchmarks

### Expected Performance

- **Dashboard Load**: <500ms for typical dashboard
- **Analytics Query**: <2s for 30-day trend analysis
- **Graph Metrics**: <30s for medium-sized graphs (10K entities)
- **Report Generation**: <60s for monthly reports

### Scaling Limits

- **Organizations**: 10,000+ tenants supported
- **Time Series Data**: Efficient up to 5 years of history
- **Concurrent Users**: 1,000+ simultaneous dashboard users
- **Data Volume**: 100TB+ analytics data with partitioning

## Best Practices

### Query Optimization

1. **Use Partition Pruning**: Always include time_bucket in WHERE clauses
2. **Materialized Views**: Use for frequently accessed aggregations
3. **Prepared Statements**: Parameterize all analytics queries
4. **Connection Pooling**: Reuse database connections

### Data Modeling

1. **Normalization**: Balance normalization with query performance
2. **JSONB Usage**: Use for flexible schema, index appropriately
3. **Time Series**: Use appropriate bucket sizes for data volume
4. **Caching**: Cache expensive computations at appropriate levels

### Monitoring

1. **Query Performance**: Monitor slow queries regularly
2. **Cache Hit Rates**: Ensure effective caching strategy
3. **Partition Usage**: Monitor partition sizes and pruning
4. **Resource Usage**: Track CPU, memory, and I/O patterns

This comprehensive schema provides a robust foundation for the Knowledge Graph Analytics Dashboard, supporting real-time metrics, historical analysis, custom reporting, and scalable multi-tenant operations.