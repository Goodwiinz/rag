# A/B Testing System Performance Optimization Guide

## Overview

This guide provides comprehensive performance optimization recommendations for the A/B testing system in your Multimodal Enterprise RAG system. The design targets sub-10ms query performance for 10,000+ queries per hour.

## Performance Targets

- **Query routing latency**: < 10ms (99th percentile)
- **User assignment lookup**: < 5ms (99th percentile)
- **Metrics insertion**: < 50ms per event
- **Statistical analysis**: < 1 second for typical experiments
- **Concurrent queries**: 1,000+ simultaneous queries

## 1. Database Configuration

### PostgreSQL Settings

```sql
-- Memory Configuration
SET shared_buffers = '4GB';                    -- 25% of RAM
SET effective_cache_size = '12GB';             -- 75% of RAM
SET work_mem = '64MB';                         -- Per query sort memory
SET maintenance_work_mem = '256MB';            -- Maintenance operations

-- Connection Pooling
SET max_connections = 200;
SET shared_preload_libraries = 'pg_stat_statements';

-- WAL Configuration for high write throughput
SET wal_buffers = '64MB';
SET checkpoint_completion_target = 0.9;
SET max_wal_size = '4GB';
SET min_wal_size = '1GB';

-- Query Planning
SET random_page_cost = 1.1;                   -- Favor index scans
SET effective_io_concurrency = 200;           -- SSD optimization
```

### Connection Pooling (PgBouncer)

```ini
[databases]
multimodal_rag = host=localhost port=5432 dbname=multimodal_rag

[pgbouncer]
listen_port = 6432
listen_addr = 127.0.0.1
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
logfile = /var/log/pgbouncer/pgbouncer.log
pidfile = /var/run/pgbouncer/pgbouncer.pid
admin_users = postgres
stats_users = stats, postgres

# Pool settings
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 100
min_pool_size = 20
reserve_pool_size = 10
reserve_pool_timeout = 5
max_db_connections = 50
max_user_connections = 50

# Timeouts
server_reset_query = DISCARD ALL
server_check_delay = 30
server_check_query = select 1
server_lifetime = 3600
server_idle_timeout = 600
```

## 2. Query Optimization

### Critical Query Patterns

#### User Assignment Lookup (Most Critical)

```sql
-- Optimized user assignment query
EXPLAIN (ANALYZE, BUFFERS)
SELECT variant_id, assignment_context
FROM ab_user_assignments
WHERE user_id = $1
  AND experiment_id = $2
  AND is_active = true;

-- Expected: Index Only Scan with < 1ms execution time
```

#### Active Experiment Discovery

```sql
-- Optimized active experiment query
EXPLAIN (ANALYZE, BUFFERS)
SELECT e.id, e.name, v.id as variant_id, v.traffic_weight
FROM ab_experiments e
JOIN ab_variants v ON e.id = v.experiment_id
WHERE e.status = 'running'
  AND e.is_deleted = false
  AND v.is_deleted = false
  AND v.status = 'active'
  AND (e.start_time IS NULL OR e.start_time <= CURRENT_TIMESTAMP)
  AND (e.end_time IS NULL OR e.end_time > CURRENT_TIMESTAMP)
ORDER BY e.id, v.is_control DESC, v.traffic_weight DESC;

-- Expected: Bitmap Index Scan with < 5ms execution time
```

### Index Usage Analysis

```sql
-- Monitor index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
  AND tablename LIKE 'ab_%'
ORDER BY idx_scan DESC;

-- Identify unused indexes
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid::regclass)) as index_size
FROM pg_stat_user_indexes psi
JOIN pg_class pc ON psi.indexrelid = pc.oid
WHERE psi.schemaname = 'public'
  AND psi.tablename LIKE 'ab_%'
  AND psi.idx_scan = 0
ORDER BY pg_relation_size(indexrelid::regclass) DESC;
```

## 3. Partition Management

### Automated Partition Creation

```sql
-- Create scheduled job for partition management
CREATE OR REPLACE FUNCTION manage_ab_testing_partitions()
RETURNS void AS $$
DECLARE
    current_month text;
    next_month text;
    current_date date;
    partition_name text;
BEGIN
    current_date := CURRENT_DATE;

    -- Create next month's user assignment partition
    current_month := to_char(current_date, 'YYYY"m"MM');
    next_month := to_char(current_date + INTERVAL '1 month', 'YYYY"m"MM');
    partition_name := 'ab_user_assignments_y' || next_month;

    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF ab_user_assignments FOR VALUES FROM (%L) TO (%L)',
                  partition_name,
                  date_trunc('month', current_date + INTERVAL '1 month'),
                  date_trunc('month', current_date + INTERVAL '2 months'));

    -- Create query event partitions for next 7 days
    FOR i IN 0..6 LOOP
        partition_name := 'ab_query_events_y' || to_char(current_date + i, 'YYYY"m"MM"d"DD');
        EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF ab_query_events FOR VALUES FROM (%L) TO (%L)',
                      partition_name,
                      current_date + i,
                      current_date + i + 1);
    END LOOP;

    -- Clean up old partitions (keep 3 months)
    FOR i IN 4..12 LOOP
        partition_name := 'ab_user_assignments_y' || to_char(current_date - INTERVAL '1 month' * i, 'YYYY"m"MM');
        EXECUTE 'DROP TABLE IF EXISTS ' || partition_name || ' CASCADE';
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Schedule with pg_cron (requires pg_cron extension)
SELECT cron.schedule('manage-ab-partitions', '0 2 * * *', 'SELECT manage_ab_testing_partitions();');
```

### Partition Pruning

```sql
-- Verify partition pruning is working
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*)
FROM ab_query_events
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
  AND created_at < CURRENT_DATE;

-- Expected: Partition Pruning with only relevant partitions scanned
```

## 4. Caching Strategy

### Redis Configuration

```python
# Redis configuration for A/B testing cache
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 2,  # Separate database for A/B testing
    'decode_responses': True,
    'max_connections': 100,
    'socket_timeout': 5,
    'socket_connect_timeout': 5,
    'retry_on_timeout': True,
    'health_check_interval': 30
}

# Cache TTL settings
CACHE_TTL = {
    'user_assignments': 3600,      # 1 hour
    'active_experiments': 300,     # 5 minutes
    'experiment_config': 1800,     # 30 minutes
    'user_segments': 7200,         # 2 hours
    'statistical_results': 600     # 10 minutes
}
```

### Cache Implementation

```python
import redis
import json
import hashlib
from typing import Optional, Dict, Any

class ABTestingCache:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def get_user_assignment(self, user_id: str, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Get cached user assignment"""
        key = f"user_assignment:{user_id}:{experiment_id}"
        cached = self.redis.get(key)
        return json.loads(cached) if cached else None

    def set_user_assignment(self, user_id: str, experiment_id: str, assignment: Dict[str, Any]) -> None:
        """Cache user assignment"""
        key = f"user_assignment:{user_id}:{experiment_id}"
        self.redis.setex(key, CACHE_TTL['user_assignments'], json.dumps(assignment))

    def get_active_experiments(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached active experiments"""
        cached = self.redis.get('active_experiments')
        return json.loads(cached) if cached else None

    def set_active_experiments(self, experiments: List[Dict[str, Any]]) -> None:
        """Cache active experiments"""
        self.redis.setex('active_experiments', CACHE_TTL['active_experiments'], json.dumps(experiments))

    def invalidate_user_assignments(self, user_id: str) -> None:
        """Invalidate all assignments for a user"""
        pattern = f"user_assignment:{user_id}:*"
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)
```

## 5. Application-Level Optimizations

### Assignment Engine Optimization

```python
import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

class OptimizedAssignmentEngine:
    def __init__(self, cache: ABTestingCache, db_session_factory):
        self.cache = cache
        self.db_session_factory = db_session_factory
        self.executor = ThreadPoolExecutor(max_workers=10)
        self._experiment_cache = {}
        self._cache_timestamp = 0

    async def get_user_variant_batch(self, user_contexts: List[Dict[str, Any]]) -> List[Optional[str]]:
        """Batch process user variant assignments"""
        # Group by user to minimize database lookups
        user_assignments = {}

        # Check cache first
        for context in user_contexts:
            user_id = context['user_id']
            cache_key = f"{user_id}:{context.get('experiment_id', 'all')}"

            cached = self.cache.get_user_assignment(user_id, context.get('experiment_id'))
            if cached:
                user_assignments[user_id] = cached['variant_id']

        # Batch fetch uncached assignments
        uncached_users = [ctx for ctx in user_contexts if ctx['user_id'] not in user_assignments]
        if uncached_users:
            db_results = await self._batch_fetch_assignments(uncached_users)
            user_assignments.update(db_results)

        return [user_assignments.get(ctx['user_id']) for ctx in user_contexts]

    async def _batch_fetch_assignments(self, contexts: List[Dict[str, Any]]) -> Dict[str, str]:
        """Batch fetch from database"""
        loop = asyncio.get_event_loop()

        def fetch_from_db():
            with self.db_session_factory() as session:
                user_ids = [ctx['user_id'] for ctx in contexts]
                experiment_ids = list(set(ctx.get('experiment_id') for ctx in contexts if 'experiment_id' in ctx))

                # Single query for all assignments
                assignments = session.query(UserAssignment).filter(
                    UserAssignment.user_id.in_(user_ids),
                    UserAssignment.experiment_id.in_(experiment_ids),
                    UserAssignment.is_active == True
                ).all()

                return {ua.user_id: ua.variant_id for ua in assignments}

        return await loop.run_in_executor(self.executor, fetch_from_db)
```

### Metrics Collection Optimization

```python
import asyncio
from asyncio import Queue
from typing import List, Dict, Any

class MetricsCollector:
    def __init__(self, db_session_factory, batch_size: int = 100, flush_interval: int = 5):
        self.db_session_factory = db_session_factory
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.queue = Queue(maxsize=1000)
        self._running = False

    async def start(self):
        """Start the metrics collector"""
        self._running = True
        asyncio.create_task(self._process_queue())
        asyncio.create_task(self._periodic_flush())

    async def stop(self):
        """Stop the metrics collector"""
        self._running = False
        await self._flush_remaining()

    async def add_query_event(self, event_data: Dict[str, Any]):
        """Add query event to processing queue"""
        try:
            self.queue.put_nowait(event_data)
        except asyncio.QueueFull:
            # Log warning and drop oldest event
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(event_data)
            except asyncio.QueueEmpty:
                pass

    async def _process_queue(self):
        """Process events from queue"""
        batch = []

        while self._running or not self.queue.empty():
            try:
                # Wait for events with timeout
                event = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                batch.append(event)

                if len(batch) >= self.batch_size:
                    await self._flush_batch(batch)
                    batch = []

            except asyncio.TimeoutError:
                # Timeout occurred, flush what we have
                if batch:
                    await self._flush_batch(batch)
                    batch = []

    async def _flush_batch(self, batch: List[Dict[str, Any]]):
        """Flush batch to database"""
        if not batch:
            return

        loop = asyncio.get_event_loop()

        def flush_to_db():
            with self.db_session_factory() as session:
                # Bulk insert query events
                query_events = []
                for event_data in batch:
                    event = QueryEvent(
                        event_id=event_data['event_id'],
                        user_id=event_data.get('user_id'),
                        experiment_id=event_data.get('experiment_id'),
                        variant_id=event_data.get('variant_id'),
                        query_text=event_data['query_text'],
                        query_type=event_data.get('query_type', 'search'),
                        **{k: v for k, v in event_data.items()
                           if k not in ['event_id', 'user_id', 'experiment_id', 'variant_id', 'query_text', 'query_type']}
                    )
                    query_events.append(event)

                session.bulk_save_objects(query_events)
                session.commit()

        await loop.run_in_executor(None, flush_to_db)
```

## 6. Monitoring and Alerting

### Performance Monitoring

```sql
-- Query performance monitoring
SELECT
    query,
    calls,
    total_exec_time,
    mean_exec_time,
    rows,
    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
FROM pg_stat_statements
WHERE query LIKE '%ab_%'
ORDER BY total_exec_time DESC
LIMIT 20;

-- Partition size monitoring
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE 'ab_%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Lock monitoring
SELECT
    pid,
    state,
    query,
    wait_event_type,
    wait_event,
    age(clock_timestamp(), xact_start) AS xact_age
FROM pg_stat_activity
WHERE state != 'idle'
  AND query LIKE '%ab_%'
ORDER BY xact_start;
```

### Alerting Rules (Prometheus)

```yaml
groups:
  - name: ab_testing_performance
    rules:
      - alert: ABTestingHighLatency
        expr: histogram_quantile(0.99, rate(ab_testing_query_duration_seconds_bucket[5m])) > 0.01
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "A/B testing query latency is high"
          description: "99th percentile latency is {{ $value }}s"

      - alert: ABTestingConnectionPoolExhaustion
        expr: pgbouncer_pool_connections_active / pgbouncer_pool_connections_max > 0.9
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "PgBouncer connection pool nearly exhausted"
          description: "Pool utilization is {{ $value | humanizePercentage }}"

      - alert: ABTestingHighErrorRate
        expr: rate(ab_testing_query_errors_total[5m]) / rate(ab_testing_queries_total[5m]) > 0.01
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "A/B testing error rate is high"
          description: "Error rate is {{ $value | humanizePercentage }}"
```

## 7. Scaling Considerations

### Read Replicas

```sql
-- Configure read replicas for reporting queries
-- Primary handles writes (assignments, events)
-- Replicas handle read queries (analytics, reporting)

-- Connection routing configuration
-- Application should route queries as follows:
# Write queries: PRIMARY
# User assignment lookups: PRIMARY (for consistency)
# Analytics queries: REPLICA
# Statistical analysis: REPLICA
```

### Database Sharding (Future)

```python
# Consider sharding strategy for very high volume
SHARDING_STRATEGY = {
    'user_assignments': 'user_id_hash',  # Shard by user_id
    'query_events': 'date_range',         # Shard by date range
    'quality_metrics': 'date_range',      # Shard by date range
}

# Shard key function
def get_shard_key(table_name: str, **kwargs) -> str:
    if table_name == 'ab_user_assignments':
        user_id = kwargs.get('user_id')
        return f"shard_{hash(user_id) % 8}"  # 8 shards
    elif table_name in ['ab_query_events', 'ab_quality_metrics']:
        date = kwargs.get('created_at', datetime.utcnow())
        return f"shard_{date.strftime('%Y_%m')}"  # Monthly shards
    return "default"
```

## 8. Disaster Recovery

### Backup Strategy

```bash
#!/bin/bash
# Backup script for A/B testing data

# Daily backup with WAL archiving
pg_dump -h localhost -U postgres -d multimodal_rag \
    --schema=public \
    --table=ab_experiments \
    --table=ab_variants \
    --table=ab_user_segments \
    --format=custom \
    --compress=9 \
    --file=/backups/ab_testing_config_$(date +%Y%m%d).dump

# Hourly incremental backup for time-series data
pg_dump -h localhost -U postgres -d multimodal_rag \
    --schema=public \
    --table=ab_query_events \
    --where="created_at >= NOW() - INTERVAL '1 hour'" \
    --format=custom \
    --compress=9 \
    --file=/backups/ab_testing_events_hourly_$(date +%Y%m%d_%H).dump
```

### Point-in-Time Recovery

```sql
-- Restore to specific point in time
CREATE DATABASE multimodal_rag_restore TEMPLATE multimodal_rag;

-- Apply WAL until specific timestamp
pg_ctl start -D /var/lib/postgresql/data -o "-c recovery_target_time='2024-10-17 14:30:00'"
```

## 9. Performance Testing

### Load Testing Script

```python
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor

async def simulate_user_query(user_id: str, query_text: str, session: aiohttp.ClientSession):
    """Simulate a single user query with A/B testing"""
    start_time = time.time()

    async with session.post('/api/search', json={
        'query': query_text,
        'user_id': user_id,
        'include_ab_testing': True
    }) as response:
        data = await response.json()
        latency = (time.time() - start_time) * 1000

        return {
            'user_id': user_id,
            'latency_ms': latency,
            'variant_assigned': data.get('ab_testing', {}).get('variant_id'),
            'status': response.status
        }

async def load_test(concurrent_users: int = 100, duration_seconds: int = 60):
    """Run load test for A/B testing system"""
    async with aiohttp.ClientSession() as session:
        tasks = []
        start_time = time.time()

        while time.time() - start_time < duration_seconds:
            # Create batch of concurrent requests
            batch = []
            for i in range(concurrent_users):
                user_id = f"user_{i % 1000}"  # 1000 unique users
                query_text = f"test query {i}"
                batch.append(simulate_user_query(user_id, query_text, session))

            # Wait for batch to complete
            results = await asyncio.gather(*batch, return_exceptions=True)
            tasks.extend(results)

            # Brief pause between batches
            await asyncio.sleep(0.1)

        # Analyze results
        successful_results = [r for r in tasks if not isinstance(r, Exception)]
        latencies = [r['latency_ms'] for r in successful_results]

        print(f"Completed {len(successful_results)} requests")
        print(f"Average latency: {sum(latencies)/len(latencies):.2f}ms")
        print(f"95th percentile: {sorted(latencies)[int(len(latencies)*0.95)]:.2f}ms")
        print(f"99th percentile: {sorted(latencies)[int(len(latencies)*0.99)]:.2f}ms")

# Run the test
asyncio.run(load_test(concurrent_users=100, duration_seconds=60))
```

## 10. Maintenance Tasks

### Daily Maintenance

```sql
-- Update statistics
ANALYZE ab_experiments;
ANALYZE ab_variants;
ANALYZE ab_user_assignments;
ANALYZE ab_query_events;
ANALYZE ab_quality_metrics;

-- Reindex fragmented indexes
REINDEX INDEX CONCURRENTLY idx_ab_user_assignments_user_id;
REINDEX INDEX CONCURRENTLY idx_ab_query_events_created_at;

-- Clean up old partitions (keep 3 months)
DELETE FROM ab_user_assignments WHERE assigned_at < CURRENT_DATE - INTERVAL '3 months';
```

### Weekly Maintenance

```sql
-- Full vacuum for tables with high churn
VACUUM FULL ab_query_events;

-- Check for table bloat
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    (pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) / pg_total_relation_size(schemaname||'.'||tablename) * 100 as index_bloat_percentage
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename LIKE 'ab_%'
ORDER BY index_bloat_percentage DESC;
```

This comprehensive performance optimization guide should help you achieve sub-10ms query performance while handling 10,000+ queries per hour in your A/B testing system.