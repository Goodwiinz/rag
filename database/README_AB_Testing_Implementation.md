# A/B Testing System Implementation Guide

## Overview

This guide provides a complete implementation roadmap for the A/B testing system in your Multimodal Enterprise RAG system. The system is designed to handle high-volume query improvements testing with sub-10ms performance for user assignment and real-time experiment routing.

## Architecture Summary

### Logical Data Model

The A/B testing system consists of 9 core entities:

1. **Experiments** - A/B test configurations and metadata
2. **Variants** - Test variants (control vs treatment configurations)
3. **User Segments** - User targeting criteria
4. **User Assignments** - Consistent user-to-variant mapping
5. **Query Events** - Individual query interactions (time-series)
6. **Quality Metrics** - RAG triad and performance metrics
7. **Statistical Analyses** - Significance testing results
8. **Experiment Targeting** - Segment-experiment relationships

### Physical Design

- **PostgreSQL 15+** with partitioning for high-volume tables
- **Sub-10ms query performance** through optimized indexing
- **Time-series partitioning** for metrics collection (10K+ queries/hour)
- **Consistent hashing** for user assignment
- **Redis caching** for frequently accessed data

## Implementation Steps

### Phase 1: Database Schema Setup

1. **Execute Migration**
   ```bash
   # Apply the main migration
   psql -h localhost -U postgres -d multimodal_rag -f database/migrations/001_add_ab_testing_schema.sql

   # Verify migration success
   psql -h localhost -U postgres -d multimodal_rag -c "SELECT COUNT(*) FROM schema_migrations WHERE version='001';"
   ```

2. **Configure PostgreSQL**
   ```sql
   -- Update postgresql.conf for optimal performance
   ALTER SYSTEM SET shared_buffers = '4GB';
   ALTER SYSTEM SET effective_cache_size = '12GB';
   ALTER SYSTEM SET work_mem = '64MB';
   ALTER SYSTEM SET maintenance_work_mem = '256MB';
   SELECT pg_reload_conf();
   ```

3. **Setup Connection Pooling**
   ```bash
   # Install and configure PgBouncer
   sudo apt-get install pgbouncer

   # Copy configuration
   cp database/pgbouncer.ini /etc/pgbouncer/pgbouncer.ini
   sudo systemctl enable pgbouncer
   sudo systemctl start pgbouncer
   ```

### Phase 2: Application Integration

1. **Install SQLAlchemy Models**
   ```python
   # Add to backend/src/models/__init__.py
   from .ab_testing_models import *

   # Update requirements.txt
   sqlalchemy>=2.0.0
   asyncpg>=0.28.0
   redis>=4.5.0
   ```

2. **Configure Database Connection**
   ```python
   # backend/src/database.py
   from sqlalchemy import create_engine
   from sqlalchemy.orm import sessionmaker
   from src.models.ab_testing_models import Base

   # Create engine with optimized settings
   engine = create_engine(
       DATABASE_URL,
       pool_size=20,
       max_overflow=30,
       pool_pre_ping=True,
       pool_recycle=3600,
       echo=False
   )

   SessionLocal = sessionmaker(bind=engine)

   # Create tables (should be done by migration)
   # Base.metadata.create_all(bind=engine)
   ```

3. **Setup Redis Cache**
   ```python
   # backend/src/cache.py
   import redis
   from src.models.ab_testing_models import ABTestingCache

   redis_client = redis.Redis(
       host='localhost',
       port=6379,
       db=2,  # Dedicated DB for A/B testing
       decode_responses=True
   )

   ab_cache = ABTestingCache(redis_client)
   ```

### Phase 3: Core Services Implementation

1. **Assignment Engine**
   ```python
   # backend/src/services/ab_assignment.py
   from src.models.ab_testing_models import AssignmentEngine, Experiment, UserAssignment
   from src.cache import ab_cache
   from src.database import SessionLocal

   class ABTestingService:
       def __init__(self):
           self.assignment_engine = AssignmentEngine()
           self.cache = ab_cache

       async def get_user_variant(self, user_id: str, user_context: dict = None) -> Optional[str]:
           """Get variant for user with caching"""
           # Check cache first
           cached = self.cache.get_user_assignment(user_id)
           if cached:
               return cached['variant_id']

           # Database lookup
           with SessionLocal() as session:
               active_experiments = session.query(Experiment).filter(
                   Experiment.status == 'running',
                   Experiment.is_deleted == False
               ).all()

               for experiment in active_experiments:
                   if experiment.should_include_user(user_context or {}):
                       variant = self.assignment_engine.assign_user_to_variant(
                           user_id, experiment, user_context
                       )
                       if variant:
                           # Cache the result
                           self.cache.set_user_assignment(user_id, variant.id, {
                               'variant_id': variant.id,
                               'experiment_id': experiment.id
                           })
                           return variant.id

           return None
   ```

2. **Metrics Collection Service**
   ```python
   # backend/src/services/ab_metrics.py
   from src.models.ab_testing_models import MetricsCollector, QueryEvent, ABQualityMetric
   from src.database import SessionLocal
   import uuid

   class ABMetricsService:
       def __init__(self):
           self.collector = MetricsCollector()
           self._batch_queue = []
           self._batch_size = 100

       async def record_query_event(self, event_data: dict):
           """Record query event with metrics"""
           event_id = str(uuid.uuid4())

           # Create query event
           query_event = self.collector.create_query_event(
               event_id=event_id,
               **event_data
           )

           # Create quality metrics if provided
           if 'metrics' in event_data:
               quality_metrics = self.collector.create_quality_metrics(
                   query_event_id=query_event.id,
                   **event_data['metrics']
               )
               self._batch_queue.append((query_event, quality_metrics))
           else:
               self._batch_queue.append((query_event, None))

           # Flush batch if needed
           if len(self._batch_queue) >= self._batch_size:
               await self._flush_batch()

       async def _flush_batch(self):
           """Flush accumulated events to database"""
           if not self._batch_queue:
               return

           with SessionLocal() as session:
               try:
                   for query_event, quality_metrics in self._batch_queue:
                       session.add(query_event)
                       if quality_metrics:
                           quality_metrics.query_event_id = query_event.id
                           session.add(quality_metrics)

                   session.commit()
                   self._batch_queue.clear()
               except Exception as e:
                   session.rollback()
                   # Log error and handle retry logic
                   raise e
   ```

3. **Statistical Analysis Service**
   ```python
   # backend/src/services/ab_analysis.py
   from src.models.ab_testing_models import StatisticalAnalysis, Experiment, ABQualityMetric
   from src.database import SessionLocal
   from scipy import stats
   import numpy as np

   class ABAnalysisService:
       def __init__(self):
           pass

       async def calculate_experiment_significance(
           self,
           experiment_id: str,
           metric_name: str = 'answer_relevancy'
       ) -> StatisticalAnalysis:
           """Calculate statistical significance for experiment"""
           with SessionLocal() as session:
               experiment = session.query(Experiment).filter(
                   Experiment.id == experiment_id
               ).first()

               if not experiment:
                   raise ValueError(f"Experiment {experiment_id} not found")

               control_variant = experiment.control_variant
               treatment_variants = experiment.treatment_variants

               if not control_variant or not treatment_variants:
                   raise ValueError("Experiment must have control and treatment variants")

               # Get metrics for control and treatment
               control_metrics = self._get_variant_metrics(
                   session, control_variant.id, metric_name
               )
               treatment_metrics = self._get_variant_metrics(
                   session, treatment_variants[0].id, metric_name
               )

               # Perform statistical test
               t_stat, p_value = stats.ttest_ind(
                   control_metrics, treatment_metrics, equal_var=False
               )

               # Calculate effect size (Cohen's d)
               effect_size = self._calculate_effect_size(
                   control_metrics, treatment_metrics
               )

               # Create analysis record
               analysis = StatisticalAnalysis(
                   experiment_id=experiment_id,
                   metric_name=metric_name,
                   control_mean=np.mean(control_metrics),
                   control_std_dev=np.std(control_metrics),
                   control_sample_size=len(control_metrics),
                   treatment_mean=np.mean(treatment_metrics),
                   treatment_std_dev=np.std(treatment_metrics),
                   treatment_sample_size=len(treatment_metrics),
                   effect_size=effect_size,
                   p_value=p_value,
                   is_significant=p_value < (1 - experiment.confidence_level),
                   is_positive_impact=np.mean(treatment_metrics) > np.mean(control_metrics),
                   relative_improvement=self._calculate_relative_improvement(
                       control_metrics, treatment_metrics
                   )
               )

               session.add(analysis)
               session.commit()

               return analysis

       def _get_variant_metrics(self, session, variant_id: str, metric_name: str) -> list:
           """Get quality metrics for a specific variant"""
           # Implementation depends on your specific metric retrieval logic
           pass

       def _calculate_effect_size(self, control: list, treatment: list) -> float:
           """Calculate Cohen's d effect size"""
           control_mean, control_std = np.mean(control), np.std(control)
           treatment_mean = np.mean(treatment)
           return (treatment_mean - control_mean) / control_std if control_std > 0 else 0

       def _calculate_relative_improvement(self, control: list, treatment: list) -> float:
           """Calculate relative improvement percentage"""
           control_mean, treatment_mean = np.mean(control), np.mean(treatment)
           return ((treatment_mean - control_mean) / control_mean * 100) if control_mean > 0 else 0
   ```

### Phase 4: API Integration

1. **Middleware for A/B Testing**
   ```python
   # backend/src/middleware/ab_testing.py
   from fastapi import Request, HTTPException
   from src.services.ab_assignment import ABTestingService
   import time

   class ABTestingMiddleware:
       def __init__(self, app):
           self.app = app
           self.ab_service = ABTestingService()

       async def __call__(self, scope, receive, send):
           if scope["type"] == "http":
               request = Request(scope, receive)

               # Extract user context
               user_id = request.headers.get("X-User-ID")
               if not user_id:
                   # Generate session ID for anonymous users
                   user_id = request.headers.get("X-Session-ID", f"anon_{int(time.time())}")

               user_context = {
                   "user_id": user_id,
                   "user_agent": request.headers.get("User-Agent"),
                   "ip_address": request.client.host
               }

               # Get variant assignment
               variant_id = await self.ab_service.get_user_variant(user_id, user_context)

               if variant_id:
                   # Add to request state
                   request.state.ab_variant_id = variant_id
                   request.state.ab_user_id = user_id

           await self.app(scope, receive, send)
   ```

2. **API Endpoints**
   ```python
   # backend/src/api/ab_testing.py
   from fastapi import APIRouter, Depends, HTTPException
   from src.models.ab_testing_models import Experiment, Variant, StatisticalAnalysis
   from src.services.ab_assignment import ABTestingService
   from src.services.ab_analysis import ABAnalysisService
   from src.services.ab_metrics import ABMetricsService
   from src.database import SessionLocal

   router = APIRouter(prefix="/api/ab-testing", tags=["ab-testing"])

   @router.get("/experiments")
   async def get_active_experiments():
       """Get all active experiments"""
       with SessionLocal() as session:
           experiments = session.query(Experiment).filter(
               Experiment.status == 'running',
               Experiment.is_deleted == False
           ).all()
           return [exp.to_dict() for exp in experiments]

   @router.get("/experiments/{experiment_id}/results")
   async def get_experiment_results(experiment_id: str):
       """Get experiment results and statistical analysis"""
       analysis_service = ABAnalysisService()

       try:
           analysis = await analysis_service.calculate_experiment_significance(experiment_id)
           return analysis.to_dict()
       except Exception as e:
           raise HTTPException(status_code=404, detail=str(e))

   @router.post("/events")
   async def record_query_event(event_data: dict):
       """Record query event for A/B testing"""
       metrics_service = ABMetricsService()
       await metrics_service.record_query_event(event_data)
       return {"status": "recorded"}
   ```

### Phase 5: Frontend Integration

1. **React Component for Experiment Display**
   ```typescript
   // frontend/src/components/ABTesting/ExperimentBadge.tsx
   import React, { useState, useEffect } from 'react';

   interface ExperimentBadgeProps {
     userId?: string;
     sessionId?: string;
   }

   export const ExperimentBadge: React.FC<ExperimentBadgeProps> = ({ userId, sessionId }) => {
     const [experiments, setExperiments] = useState<any[]>([]);

     useEffect(() => {
       const fetchExperiments = async () => {
         try {
           const response = await fetch('/api/ab-testing/experiments', {
             headers: {
               'X-User-ID': userId || '',
               'X-Session-ID': sessionId || ''
             }
           });
           const data = await response.json();
           setExperiments(data);
         } catch (error) {
           console.error('Failed to fetch experiments:', error);
         }
       };

       fetchExperiments();
     }, [userId, sessionId]);

     if (experiments.length === 0) return null;

     return (
       <div className="ab-testing-badge">
         <span className="text-xs text-gray-500">
           Testing: {experiments.map(exp => exp.name).join(', ')}
         </span>
       </div>
     );
   };
   ```

### Phase 6: Testing and Validation

1. **Unit Tests**
   ```python
   # tests/test_ab_testing.py
   import pytest
   from src.models.ab_testing_models import Experiment, Variant, AssignmentEngine
   from src.database import SessionLocal

   class TestAssignmentEngine:
       def test_user_assignment_consistency(self):
           """Test that same user always gets same variant"""
           engine = AssignmentEngine()
           user_id = "test_user_123"

           # Create test experiment
           with SessionLocal() as session:
               experiment = Experiment(
                   name="Test Experiment",
                   status="running",
                   traffic_percentage=100
               )
               session.add(experiment)

               control = Variant(
                   experiment_id=experiment.id,
                   name="Control",
                   is_control=True,
                   traffic_weight=1
               )
               treatment = Variant(
                   experiment_id=experiment.id,
                   name="Treatment",
                   is_control=False,
                   traffic_weight=1
               )
               session.add_all([control, treatment])
               session.commit()

               # Test multiple assignments
               variants = []
               for _ in range(10):
                   variant = engine.assign_user_to_variant(user_id, experiment)
                   variants.append(variant.id)

               # All assignments should be the same
               assert len(set(variants)) == 1
   ```

2. **Load Testing**
   ```python
   # tests/load_test_ab_testing.py
   import asyncio
   from tests.test_ab_testing import TestAssignmentEngine

   async def test_concurrent_assignments():
       """Test concurrent user assignments"""
       engine = TestAssignmentEngine()

       async def assign_users(start_id: int, count: int):
           for i in range(count):
               user_id = f"user_{start_id + i}"
               await engine.assign_user_to_variant(user_id)

       # Run 1000 concurrent assignments
       tasks = []
       for i in range(0, 1000, 100):
           tasks.append(assign_users(i, 100))

       await asyncio.gather(*tasks)

   if __name__ == "__main__":
       asyncio.run(test_concurrent_assignments())
   ```

## Performance Monitoring

### Key Metrics to Monitor

1. **Query Routing Latency**
   - Target: < 10ms (99th percentile)
   - Monitor: `ab_testing_assignment_duration_seconds`

2. **User Assignment Cache Hit Rate**
   - Target: > 95%
   - Monitor: `ab_testing_cache_hit_rate`

3. **Database Connection Pool Usage**
   - Target: < 80%
   - Monitor: `pgbouncer_pool_connections_active / pgbouncer_pool_connections_max`

4. **Metrics Insertion Throughput**
   - Target: 10,000+ events/hour
   - Monitor: `ab_testing_events_inserted_total`

### Health Checks

```python
# backend/src/health.py
from fastapi import APIRouter
from sqlalchemy import text
from src.database import SessionLocal
import redis

router = APIRouter()

@router.get("/health")
async def health_check():
    """System health check"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }

    # Check PostgreSQL
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
            health_status["services"]["database"] = "healthy"
    except Exception as e:
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"

    # Check Redis
    try:
        redis_client.ping()
        health_status["services"]["cache"] = "healthy"
    except Exception as e:
        health_status["services"]["cache"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    return health_status
```

## Rollback Plan

If issues arise during implementation:

1. **Database Rollback**
   ```bash
   psql -h localhost -U postgres -d multimodal_rag -f database/migrations/001_rollback_ab_testing_schema.sql
   ```

2. **Application Rollback**
   ```bash
   # Revert to previous version
   git checkout HEAD~1 -- backend/src/models/
   git checkout HEAD~1 -- backend/src/services/
   git checkout HEAD~1 -- backend/src/middleware/
   ```

3. **Configuration Rollback**
   ```bash
   # Restore original PostgreSQL settings
   sudo systemctl restart postgresql
   ```

## Next Steps

1. **Implement Phase 1** (Database Setup) - Week 1
2. **Implement Phase 2** (Application Integration) - Week 1-2
3. **Implement Phase 3** (Core Services) - Week 2-3
4. **Implement Phase 4** (API Integration) - Week 3
5. **Implement Phase 5** (Frontend Integration) - Week 4
6. **Implement Phase 6** (Testing & Validation) - Week 4-5

## Support and Maintenance

- **Daily**: Monitor partition creation and cache performance
- **Weekly**: Review query performance and index usage
- **Monthly**: Analyze experiment results and system scalability
- **Quarterly**: Review and optimize database configuration

For technical support or questions about implementation, refer to the detailed documentation in:
- `/database/ab_testing_schema.sql` - Complete schema definition
- `/database/ab_testing_performance_guide.md` - Performance optimization guide
- `/backend/src/models/ab_testing_models.py` - SQLAlchemy models
- `/database/migrations/001_add_ab_testing_schema.sql` - Migration script