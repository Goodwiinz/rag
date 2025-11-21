# Real-Time Status Database Optimization Guide

This guide provides comprehensive documentation for the database optimizations implemented for real-time status queries in the Multimodal Enterprise RAG System.

## Overview

The real-time status optimization provides sub-100ms query performance for dashboard displays through:

- **Optimized indexing strategy** for common query patterns
- **Materialized views** for pre-computed dashboard metrics
- **Stored procedures** for atomic status updates
- **Performance monitoring** and alerting
- **Table partitioning** for high-volume data
- **Connection pooling** optimization

## Architecture

### Key Components

1. **Enhanced Indexing**: Composite and partial indexes optimized for real-time queries
2. **Materialized Views**: Pre-computed dashboard summaries with automatic refresh
3. **Stored Procedures**: Atomic operations for status management and batch processing
4. **Monitoring System**: Real-time performance metrics and alerting
5. **Partitioning Strategy**: Time-based partitioning for high-volume tables

## File Structure

```
database/
├── migrations/
│   └── 009_realtime_status_optimizations.sql    # Main migration script
├── queries/
│   └── realtime_dashboard_queries.sql           # Optimized dashboard queries
├── procedures/
│   └── realtime_status_procedures.sql           # Stored procedures
├── views/
│   └── realtime_materialized_views.sql          # Materialized views
├── indexing/
│   └── realtime_status_indexing.sql             # Indexing strategy
├── monitoring/
│   └── realtime_performance_monitoring.sql      # Performance monitoring
└── deployment/
    ├── realtime_status_deployment.sql           # Deployment script
    └── realtime_status_rollback.sql             # Rollback script
```

## Deployment

### Prerequisites

1. PostgreSQL 14+ with required extensions:
   ```sql
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
   CREATE EXTENSION IF NOT EXISTS "pg_trgm";
   CREATE EXTENSION IF NOT EXISTS "btree_gin";
   ```

2. Existing database schema with core tables:
   - `documents`
   - `processing_job_executions`
   - `stage_executions`
   - `organizations`

### Deployment Steps

1. **Run the main migration**:
   ```bash
   psql -h localhost -U postgres -d multimodal_rag_dev -f database/migrations/009_realtime_status_optimizations.sql
   ```

2. **Execute deployment script**:
   ```bash
   psql -h localhost -U postgres -d multimodal_rag_dev -f database/deployment/realtime_status_deployment.sql
   ```

3. **Verify deployment**:
   ```sql
   SELECT * FROM deployment_history ORDER BY started_at DESC LIMIT 1;
   ```

### Rollback Procedure

If issues arise, rollback using:
```bash
psql -h localhost -U postgres -d multimodal_rag_dev -f database/deployment/realtime_status_rollback.sql
```

## Usage Examples

### 1. Real-Time Dashboard Queries

**Organization Dashboard Overview**:
```sql
-- Get real-time organization dashboard data (sub-100ms)
SELECT * FROM get_realtime_dashboard_data('your-org-uuid');

-- Alternative: Direct materialized view query
SELECT * FROM realtime_org_dashboard_summary
WHERE organization_id = 'your-org-uuid';
```

**Processing Queue Status**:
```sql
-- Get current processing queue with worker assignments
SELECT * FROM get_processing_queue_status(100) LIMIT 50;

-- Alternative: Materialized view
SELECT * FROM realtime_processing_queue
WHERE organization_id = 'your-org-uuid'
ORDER BY queue_priority_rank ASC;
```

**Worker Performance Dashboard**:
```sql
-- Get comprehensive worker performance metrics
SELECT * FROM realtime_worker_performance
WHERE worker_id = 'your-worker-id';

-- Get all workers sorted by efficiency
SELECT worker_id, active_jobs, efficiency_score, worker_status
FROM realtime_worker_performance
ORDER BY efficiency_score DESC;
```

### 2. Status Management Operations

**Update Document Processing Status**:
```sql
CALL update_document_processing_status_comprehensive(
    'document-uuid',
    'processing',
    75.5,
    'entity_extraction',
    'execution-uuid',
    120,
    NULL,
    '{"batch_id": "batch_001"}'::jsonb
);
```

**Start Batch Processing**:
```sql
CALL start_batch_processing(
    'org-uuid',
    ARRAY['doc1-uuid', 'doc2-uuid', 'doc3-uuid'],
    '{"priority": "high", "workers": 3}'::jsonb,
    8,
    'high_priority_batch'
);
```

**Assign Worker to Job**:
```sql
CALL assign_worker_to_job(
    'job-execution-uuid',
    'worker-001',
    '{"cpu_cores": 4, "memory_mb": 8192}'::jsonb
);
```

### 3. Performance Monitoring

**Database Performance Overview**:
```sql
-- Real-time database performance metrics
SELECT * FROM realtime_database_performance;

-- Performance score calculation
SELECT
    overall_health_status,
    active_connections,
    cache_hit_ratio_percent
FROM realtime_database_performance;
```

**Processing Performance Metrics**:
```sql
-- Comprehensive processing performance
SELECT * FROM realtime_processing_performance;

-- Key metrics extraction
SELECT
    jobs_completed_hour,
    success_rate_percent,
    avg_cpu_usage_percent,
    system_performance_status,
    performance_score
FROM realtime_processing_performance;
```

**Connection Pool Monitoring**:
```sql
-- Connection pool status and utilization
SELECT * FROM connection_pool_status;

-- Application-specific connection breakdown
SELECT
    pool_health_status,
    total_connections,
    utilization_percent,
    application_breakdown
FROM connection_pool_status;
```

### 4. Error Analysis and Alerting

**Critical Errors Monitoring**:
```sql
-- Recent critical errors
SELECT * FROM realtime_error_analysis
WHERE severity = 'critical'
ORDER BY last_occurrence DESC;

-- Error patterns and trends
SELECT
    error_type,
    error_count,
    critical_count,
    risk_level,
    trend_indicator
FROM realtime_error_analysis
WHERE risk_level IN ('high', 'critical');
```

**Performance Alerts**:
```sql
-- Generate performance alerts
SELECT * FROM generate_performance_alerts()
WHERE severity IN ('warning', 'critical');

-- Alert categories
SELECT
    alert_type,
    severity,
    COUNT(*) as alert_count
FROM generate_performance_alerts()
GROUP BY alert_type, severity
ORDER BY alert_count DESC;
```

## Performance Tuning

### Materialized View Refresh Strategy

Set up automated refresh using pg_cron:
```sql
-- Refresh dashboard views every 5 minutes
SELECT cron.schedule('refresh-realtime-views', '*/5 * * * *',
    'REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_org_dashboard_summary;');

-- Refresh high-frequency views every minute
SELECT cron.schedule('refresh-processing-views', '* * * * *',
    'REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_processing_queue;');
```

### Index Maintenance

Monitor and maintain index performance:
```sql
-- Analyze index usage
SELECT * FROM realtime_index_usage_monitor;

-- Identify unused indexes
SELECT * FROM identify_unused_realtime_indexes();

-- Rebuild fragmented indexes
CALL rebuild_fragmented_realtime_indexes();
```

### Connection Pool Configuration

Configure application connection pool:
```python
# Example connection pool settings
DATABASE_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'multimodal_rag_dev',
    'user': 'postgres',
    'password': 'password',
    'pool_size': 20,
    'max_overflow': 30,
    'pool_timeout': 30,
    'pool_recycle': 3600,
    'pool_pre_ping': True
}
```

## Query Performance Targets

### Dashboard Queries

- **Organization Overview**: < 100ms
- **Processing Queue**: < 50ms
- **Worker Performance**: < 100ms
- **Error Analysis**: < 50ms

### Status Update Operations

- **Document Status Update**: < 10ms
- **Batch Processing Start**: < 200ms
- **Worker Assignment**: < 50ms

### Monitoring Queries

- **Performance Overview**: < 50ms
- **Alert Generation**: < 30s
- **Connection Pool Status**: < 20ms

## Troubleshooting

### Common Issues

1. **Slow Dashboard Queries**:
   ```sql
   -- Check if materialized views need refresh
   SELECT * FROM generate_performance_alerts()
   WHERE alert_type = 'cache_hit_ratio_low';

   -- Refresh manually
   REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_org_dashboard_summary;
   ```

2. **High Connection Pool Usage**:
   ```sql
   -- Monitor connection utilization
   SELECT * FROM connection_pool_status
   WHERE utilization_percent > 80;

   -- Check for connection leaks
   SELECT count(*), state FROM pg_stat_activity
   WHERE datname = current_database()
   GROUP BY state;
   ```

3. **Index Performance Issues**:
   ```sql
   -- Analyze slow queries
   SELECT * FROM get_slow_processing_queries(500);

   -- Check index usage
   SELECT * FROM realtime_index_usage_monitor
   WHERE usage_category = 'LOW_USAGE';
   ```

### Performance Degradation

If performance degrades after deployment:

1. **Check deployment history**:
   ```sql
   SELECT * FROM deployment_history
   ORDER BY started_at DESC LIMIT 5;
   ```

2. **Run performance benchmarks**:
   ```sql
   SELECT * FROM get_performance_summary();
   ```

3. **Consider rollback** if critical issues persist:
   ```bash
   psql -h localhost -U postgres -d multimodal_rag_dev -f database/deployment/realtime_status_rollback.sql
   ```

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Query Performance**:
   - Dashboard query response times
   - Materialized view refresh times
   - Index usage statistics

2. **System Health**:
   - Database connection utilization
   - Cache hit ratios
   - Memory usage patterns

3. **Processing Metrics**:
   - Job completion rates
   - Error rates and patterns
   - Worker efficiency scores

### Alert Configuration

Set up alerts for:
- Query response times > 100ms
- Cache hit ratio < 95%
- Connection pool utilization > 80%
- Error rates > 5%
- Materialized view refresh failures

## Best Practices

1. **Use Stored Procedures**: Always use provided procedures for status updates to ensure atomicity
2. **Query Materialized Views**: Use materialized views for dashboard queries instead of base tables
3. **Monitor Performance**: Regularly check performance metrics and alerts
4. **Maintain Indexes**: Periodically analyze and maintain index performance
5. **Connection Pooling**: Configure appropriate connection pool sizes for your workload
6. **Regular Backups**: Ensure regular backups before and after deployment

## API Integration

The database optimizations can be integrated with your application backend:

```python
# Example FastAPI integration
from fastapi import FastAPI, Depends
import asyncpg

app = FastAPI()

@app.get("/api/v1/dashboard/{organization_id}")
async def get_dashboard_data(organization_id: str):
    conn = await asyncpg.connect(DATABASE_URL)

    # Use materialized view for fast dashboard data
    query = """
        SELECT * FROM realtime_org_dashboard_summary
        WHERE organization_id = $1
    """

    result = await conn.fetchrow(query, organization_id)
    await conn.close()

    return dict(result)

@app.post("/api/v1/documents/{document_id}/status")
async def update_document_status(document_id: str, status_update: dict):
    conn = await asyncpg.connect(DATABASE_URL)

    # Use stored procedure for atomic update
    await conn.execute(
        "CALL update_document_processing_status_comprehensive($1, $2, $3, $4, $5, $6, $7, $8)",
        document_id,
        status_update['status'],
        status_update.get('progress'),
        status_update.get('stage'),
        status_update.get('execution_id'),
        status_update.get('remaining_seconds'),
        status_update.get('error_message'),
        status_update.get('metadata', {})
    )

    await conn.close()
    return {"status": "updated"}
```

## Conclusion

The real-time status database optimization provides enterprise-grade performance for dashboard queries and status management. By following this guide and implementing the recommended monitoring practices, you can ensure optimal performance and reliability for your Multimodal Enterprise RAG System.

For additional support or questions about the implementation, refer to the database migration scripts and stored procedure documentation.