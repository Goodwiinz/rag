"""
A/B Testing Metrics Collection Service
Handles high-volume metrics collection with async processing and minimal latency impact
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque
import queue

import redis.asyncio as redis
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from pydantic import BaseModel

from src.core.config import settings
from src.core.database import get_db
from src.models.ab_testing import (
    Experiment, Variant, ExperimentMetric, QueryRouting,
    MetricType, ExperimentAssignment
)
from src.models.search_schemas import SearchResponse, SearchResult
from src.models.analytics_event import AnalyticsEvent
from src.services.cache.analytics_cache import analytics_cache

logger = logging.getLogger(__name__)


class MetricCategory(Enum):
    """Categories of metrics for organization"""
    RELEVANCE = "relevance"
    PERFORMANCE = "performance"
    ENGAGEMENT = "engagement"
    BUSINESS = "business"
    QUALITY = "quality"


@dataclass
class MetricEvent:
    """Individual metric event data structure"""
    experiment_id: str
    variant_id: str
    metric_type: MetricType
    metric_value: float
    user_id: Optional[str]
    session_id: Optional[str]
    query_id: Optional[str]
    metric_metadata: Optional[Dict[str, Any]]
    timestamp: datetime
    processing_time_ms: Optional[float] = None


@dataclass
class BatchMetrics:
    """Batch of metrics for efficient processing"""
    events: List[MetricEvent]
    batch_id: str
    created_at: datetime
    priority: int = 1  # 1=normal, 2=high, 3=critical


class MetricsCollectionService:
    """
    High-performance metrics collection with async processing,
    batching, and intelligent routing
    """

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._metrics_queue = asyncio.Queue(maxsize=10000)
        self._batch_queue = asyncio.Queue(maxsize=1000)
        self._processing = False
        self._batch_size = 100
        self._batch_timeout = 5.0  # seconds
        self._flush_interval = 30  # seconds
        self._max_memory_batches = 50

        # Performance tracking
        self._metrics_count = defaultdict(int)
        self._processing_times = deque(maxlen=1000)
        self._error_count = defaultdict(int)

    async def initialize(self):
        """Initialize Redis connection and background processors"""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )

            # Test connection
            await self.redis_client.ping()
            logger.info("Metrics collection service initialized with Redis")

            # Start background processors
            asyncio.create_task(self._batch_processor())
            asyncio.create_task(self._flush_processor())
            asyncio.create_task(self._cleanup_processor())

        except Exception as e:
            logger.warning(f"Redis not available for metrics collection: {e}")
            self.redis_client = None

    async def collect_search_metrics(
        self,
        search_response: SearchResponse,
        assignment_result: Any,
        context: Dict[str, Any],
        start_time: float,
        db: Session
    ):
        """
        Collect metrics from search operation with minimal latency impact
        """
        try:
            processing_time = (time.time() - start_time) * 1000

            if not assignment_result or not assignment_result.assigned:
                return

            # Generate multiple metrics from single search
            metrics = await self._extract_search_metrics(
                search_response, assignment_result, context, processing_time
            )

            # Queue metrics for async processing
            for metric_event in metrics:
                await self._queue_metric_event(metric_event)

            logger.debug(f"Queued {len(metrics)} metrics for experiment {assignment_result.experiment_id}")

        except Exception as e:
            logger.error(f"Error collecting search metrics: {e}")

    async def collect_user_feedback_metrics(
        self,
        experiment_id: str,
        variant_id: str,
        user_id: str,
        feedback_type: str,
        feedback_value: Union[int, float],
        context: Dict[str, Any] = None
    ):
        """Collect user feedback metrics"""
        try:
            # Map feedback types to metric types
            metric_type_mapping = {
                'satisfaction': MetricType.USER_SATISFACTION,
                'relevance_rating': MetricType.RELEVANCE_SCORE,
                'click': None,  # Handled separately
                'conversion': MetricType.CONVERSION_RATE
            }

            metric_type = metric_type_mapping.get(feedback_type)
            if not metric_type:
                return

            metric_event = MetricEvent(
                experiment_id=experiment_id,
                variant_id=variant_id,
                metric_type=metric_type,
                metric_value=float(feedback_value),
                user_id=user_id,
                session_id=context.get('session_id') if context else None,
                query_id=context.get('query_id') if context else None,
                metric_metadata={
                    'feedback_type': feedback_type,
                    'context': context or {}
                },
                timestamp=datetime.utcnow()
            )

            await self._queue_metric_event(metric_event, priority=2)

        except Exception as e:
            logger.error(f"Error collecting user feedback metrics: {e}")

    async def collect_performance_metrics(
        self,
        experiment_id: str,
        variant_id: str,
        performance_data: Dict[str, Any],
        context: Dict[str, Any] = None
    ):
        """Collect performance metrics"""
        try:
            metrics = []

            # Response time metric
            if 'response_time_ms' in performance_data:
                metrics.append(MetricEvent(
                    experiment_id=experiment_id,
                    variant_id=variant_id,
                    metric_type=MetricType.RESPONSE_TIME,
                    metric_value=float(performance_data['response_time_ms']),
                    user_id=context.get('user_id') if context else None,
                    session_id=context.get('session_id') if context else None,
                    query_id=context.get('query_id') if context else None,
                    metric_metadata=performance_data,
                    timestamp=datetime.utcnow()
                ))

            # Result count metric
            if 'result_count' in performance_data:
                metrics.append(MetricEvent(
                    experiment_id=experiment_id,
                    variant_id=variant_id,
                    metric_type=MetricType.RESULT_COUNT,
                    metric_value=float(performance_data['result_count']),
                    user_id=context.get('user_id') if context else None,
                    session_id=context.get('session_id') if context else None,
                    query_id=context.get('query_id') if context else None,
                    metric_metadata=performance_data,
                    timestamp=datetime.utcnow()
                ))

            # Queue all performance metrics
            for metric_event in metrics:
                await self._queue_metric_event(metric_event, priority=1)

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")

    async def collect_click_metrics(
        self,
        experiment_id: str,
        variant_id: str,
        user_id: str,
        click_data: Dict[str, Any]
    ):
        """Collect click-through metrics"""
        try:
            metric_event = MetricEvent(
                experiment_id=experiment_id,
                variant_id=variant_id,
                metric_type=MetricType.CLICK_THROUGH_RATE,
                metric_value=1.0,  # Binary click event
                user_id=user_id,
                session_id=click_data.get('session_id'),
                query_id=click_data.get('query_id'),
                metric_metadata={
                    'click_position': click_data.get('position'),
                    'document_id': click_data.get('document_id'),
                    'click_data': click_data
                },
                timestamp=datetime.utcnow()
            )

            await self._queue_metric_event(metric_event, priority=2)

        except Exception as e:
            logger.error(f"Error collecting click metrics: {e}")

    async def _extract_search_metrics(
        self,
        search_response: SearchResponse,
        assignment_result: Any,
        context: Dict[str, Any],
        processing_time: float
    ) -> List[MetricEvent]:
        """Extract multiple metrics from search response"""
        metrics = []

        try:
            # Response time metric
            metrics.append(MetricEvent(
                experiment_id=assignment_result.experiment_id,
                variant_id=assignment_result.variant_id,
                metric_type=MetricType.RESPONSE_TIME,
                metric_value=processing_time,
                user_id=context.get('user_id'),
                session_id=context.get('session_id'),
                query_id=context.get('query_id'),
                metric_metadata={
                    'search_type': search_response.search_type.value if search_response.search_type else 'unknown',
                    'total_results': len(search_response.results),
                    'search_time_ms': search_response.search_time_ms
                },
                timestamp=datetime.utcnow(),
                processing_time_ms=processing_time
            ))

            # Result count metric
            metrics.append(MetricEvent(
                experiment_id=assignment_result.experiment_id,
                variant_id=assignment_result.variant_id,
                metric_type=MetricType.RESULT_COUNT,
                metric_value=float(len(search_response.results)),
                user_id=context.get('user_id'),
                session_id=context.get('session_id'),
                query_id=context.get('query_id'),
                metric_metadata={
                    'search_time_ms': search_response.search_time_ms,
                    'has_results': len(search_response.results) > 0
                },
                timestamp=datetime.utcnow()
            ))

            # Query success rate (binary - successful if we got results)
            success_value = 1.0 if len(search_response.results) > 0 else 0.0
            metrics.append(MetricEvent(
                experiment_id=assignment_result.experiment_id,
                variant_id=assignment_result.variant_id,
                metric_type=MetricType.QUERY_SUCCESS_RATE,
                metric_value=success_value,
                user_id=context.get('user_id'),
                session_id=context.get('session_id'),
                query_id=context.get('query_id'),
                metric_metadata={
                    'query_text': context.get('query_text', ''),
                    'result_count': len(search_response.results)
                },
                timestamp=datetime.utcnow()
            ))

            # Relevance score (if available in results)
            if search_response.results:
                avg_relevance = sum(
                    getattr(result, 'relevance_score', 0.0) for result in search_response.results
                ) / len(search_response.results)

                metrics.append(MetricEvent(
                    experiment_id=assignment_result.experiment_id,
                    variant_id=assignment_result.variant_id,
                    metric_type=MetricType.RELEVANCE_SCORE,
                    metric_value=avg_relevance,
                    user_id=context.get('user_id'),
                    session_id=context.get('session_id'),
                    query_id=context.get('query_id'),
                    metric_metadata={
                        'individual_scores': [
                            getattr(result, 'relevance_score', 0.0) for result in search_response.results
                        ],
                        'result_count': len(search_response.results)
                    },
                    timestamp=datetime.utcnow()
                ))

        except Exception as e:
            logger.error(f"Error extracting search metrics: {e}")

        return metrics

    async def _queue_metric_event(
        self,
        metric_event: MetricEvent,
        priority: int = 1
    ):
        """Queue metric event for processing with backpressure handling"""
        try:
            # Check queue size and apply backpressure
            if self._metrics_queue.qsize() >= 9000:  # 90% capacity
                logger.warning("Metrics queue approaching capacity, applying backpressure")
                # Could implement sampling or priority-based dropping here

            await self._metrics_queue.put((priority, metric_event))
            self._metrics_count[metric_event.metric_type.value] += 1

        except asyncio.QueueFull:
            logger.error("Metrics queue full, dropping metric event")
            self._error_count['queue_full'] += 1

    async def _batch_processor(self):
        """Background task to batch metrics for efficient processing"""
        self._processing = True

        while self._processing:
            try:
                batch_events = []
                batch_start = time.time()

                # Collect batch or timeout
                while (len(batch_events) < self._batch_size and
                       time.time() - batch_start < self._batch_timeout):
                    try:
                        priority, event = await asyncio.wait_for(
                            self._metrics_queue.get(), timeout=1.0
                        )
                        batch_events.append((priority, event))
                    except asyncio.TimeoutError:
                        break

                if batch_events:
                    # Sort by priority
                    batch_events.sort(key=lambda x: x[0], reverse=True)
                    events = [event for _, event in batch_events]

                    # Create batch
                    batch = BatchMetrics(
                        events=events,
                        batch_id=f"batch_{int(time.time() * 1000)}_{len(events)}",
                        created_at=datetime.utcnow(),
                        priority=max(priority for priority, _ in batch_events)
                    )

                    # Queue for processing
                    if self._batch_queue.qsize() < self._max_memory_batches:
                        await self._batch_queue.put(batch)
                    else:
                        logger.warning("Batch queue full, processing immediately")
                        await self._process_batch(batch)

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in batch processor: {e}")
                await asyncio.sleep(1.0)

    async def _flush_processor(self):
        """Background task to periodically flush metrics"""
        while self._processing:
            try:
                await asyncio.sleep(self._flush_interval)

                # Process any remaining batches
                batches_to_process = []
                while not self._batch_queue.empty():
                    batch = await self._batch_queue.get()
                    batches_to_process.append(batch)

                if batches_to_process:
                    logger.info(f"Flushing {len(batches_to_process)} batches")
                    await asyncio.gather(
                        *[self._process_batch(batch) for batch in batches_to_process],
                        return_exceptions=True
                    )

            except Exception as e:
                logger.error(f"Error in flush processor: {e}")

    async def _process_batch(self, batch: BatchMetrics):
        """Process a batch of metric events"""
        start_time = time.time()

        try:
            # Group events by experiment for efficient database operations
            events_by_experiment = defaultdict(list)
            for event in batch.events:
                events_by_experiment[event.experiment_id].append(event)

            # Process each experiment's events
            db = next(get_db())
            try:
                for experiment_id, events in events_by_experiment.items():
                    await self._persist_metrics(events, db)

                db.commit()

            except Exception as e:
                db.rollback()
                logger.error(f"Database error processing batch {batch.batch_id}: {e}")
                # Could implement retry logic or fallback to Redis here
                await self._fallback_persist(batch)

            finally:
                db.close()

            processing_time = time.time() - start_time
            self._processing_times.append(processing_time)

            logger.debug(f"Processed batch {batch.batch_id} with {len(batch.events)} events in {processing_time:.3f}s")

        except Exception as e:
            logger.error(f"Error processing batch {batch.batch_id}: {e}")
            self._error_count['batch_processing'] += 1

    async def _persist_metrics(self, events: List[MetricEvent], db: Session):
        """Persist metrics to database with bulk operations"""
        try:
            # Create metric records
            metric_records = []
            for event in events:
                metric_record = ExperimentMetric(
                    experiment_id=event.experiment_id,
                    variant_id=event.variant_id,
                    metric_type=event.metric_type,
                    metric_value=event.metric_value,
                    user_id=event.user_id,
                    session_id=event.session_id,
                    query_id=event.query_id,
                    metric_metadata=event.metric_metadata,
                    timestamp=event.timestamp
                )
                metric_records.append(metric_record)

            # Bulk insert
            db.add_all(metric_records)

            # Update variant metrics in real-time
            await self._update_variant_metrics(events, db)

        except Exception as e:
            logger.error(f"Error persisting metrics: {e}")
            raise

    async def _update_variant_metrics(self, events: List[MetricEvent], db: Session):
        """Update variant-level metrics in real-time"""
        try:
            # Group events by variant
            events_by_variant = defaultdict(list)
            for event in events:
                events_by_variant[event.variant_id].append(event)

            # Update each variant
            for variant_id, variant_events in events_by_variant.items():
                variant = db.query(Variant).filter(Variant.id == variant_id).first()
                if not variant:
                    continue

                # Update metrics based on event types
                for event in variant_events:
                    if event.metric_type == MetricType.RESPONSE_TIME:
                        # Update average response time
                        if variant.query_count > 0:
                            current_avg = variant.total_response_time_ms / variant.query_count
                            new_avg = ((current_avg * variant.query_count) + event.metric_value) / (variant.query_count + 1)
                            variant.total_response_time_ms = int(new_avg * (variant.query_count + 1))
                        else:
                            variant.total_response_time_ms = int(event.metric_value)

                    elif event.metric_type == MetricType.CLICK_THROUGH_RATE:
                        variant.click_count += int(event.metric_value)

                    elif event.metric_type == MetricType.CONVERSION_RATE:
                        variant.conversion_count += int(event.metric_value)

                    elif event.metric_type == MetricType.USER_SATISFACTION:
                        # Update satisfaction score (running average)
                        if variant.query_count > 0:
                            current_avg = variant.user_satisfaction_score or 0
                            new_avg = ((current_avg * variant.query_count) + event.metric_value) / (variant.query_count + 1)
                            variant.user_satisfaction_score = new_avg
                        else:
                            variant.user_satisfaction_score = event.metric_value

                    # Update query count for all events
                    variant.query_count += 1

                # Update primary metric value if it's the experiment's primary metric
                experiment = db.query(Experiment).filter(Experiment.id == events[0].experiment_id).first()
                if experiment and experiment.primary_metric:
                    primary_events = [e for e in variant_events if e.metric_type == experiment.primary_metric]
                    if primary_events:
                        # Calculate new primary metric value (simplified - could be more sophisticated)
                        primary_values = [e.metric_value for e in primary_events]
                        variant.primary_metric_value = sum(primary_values) / len(primary_values)

        except Exception as e:
            logger.error(f"Error updating variant metrics: {e}")

    async def _fallback_persist(self, batch: BatchMetrics):
        """Fallback persistence using Redis when database is unavailable"""
        try:
            if not self.redis_client:
                logger.error("Redis not available for fallback persistence")
                return

            # Store batch in Redis for later processing
            fallback_key = f"ab_metrics_fallback:{batch.batch_id}"
            batch_data = {
                'batch_id': batch.batch_id,
                'created_at': batch.created_at.isoformat(),
                'events': [asdict(event) for event in batch.events],
                'priority': batch.priority
            }

            await self.redis_client.setex(
                fallback_key,
                3600,  # 1 hour TTL
                json.dumps(batch_data)
            )

            logger.info(f"Stored batch {batch.batch_id} in Redis fallback")

        except Exception as e:
            logger.error(f"Error in fallback persist: {e}")

    async def _cleanup_processor(self):
        """Background task for cleanup operations"""
        while self._processing:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes

                # Clean up old fallback data
                if self.redis_client:
                    await self._cleanup_redis_fallback()

                # Log performance metrics
                await self._log_performance_metrics()

            except Exception as e:
                logger.error(f"Error in cleanup processor: {e}")

    async def _cleanup_redis_fallback(self):
        """Clean up old fallback data in Redis"""
        try:
            pattern = "ab_metrics_fallback:*"
            keys = await self.redis_client.keys(pattern)

            for key in keys:
                ttl = await self.redis_client.ttl(key)
                if ttl == -1:  # No TTL set
                    await self.redis_client.expire(key, 3600)  # Set 1 hour TTL
                elif ttl < 0:
                    await self.redis_client.delete(key)

        except Exception as e:
            logger.error(f"Error cleaning up Redis fallback: {e}")

    async def _log_performance_metrics(self):
        """Log performance metrics for monitoring"""
        try:
            if self._processing_times:
                avg_processing_time = sum(self._processing_times) / len(self._processing_times)
                max_processing_time = max(self._processing_times)

                logger.info(
                    f"Metrics Collection Performance: "
                    f"Avg batch time: {avg_processing_time:.3f}s, "
                    f"Max batch time: {max_processing_time:.3f}s, "
                    f"Queue size: {self._metrics_queue.qsize()}, "
                    f"Batch queue size: {self._batch_queue.qsize()}"
                )

            # Log metrics counts
            total_metrics = sum(self._metrics_count.values())
            if total_metrics > 0:
                logger.info(f"Total metrics collected: {total_metrics}")
                for metric_type, count in self._metrics_count.items():
                    logger.info(f"  {metric_type}: {count}")

            # Log error counts
            if self._error_count:
                logger.warning(f"Error counts: {dict(self._error_count)}")

        except Exception as e:
            logger.error(f"Error logging performance metrics: {e}")

    async def get_metrics_summary(
        self,
        experiment_id: str,
        time_range: timedelta = timedelta(hours=24)
    ) -> Dict[str, Any]:
        """Get summary of metrics for an experiment"""
        try:
            db = next(get_db())

            cutoff_time = datetime.utcnow() - time_range

            # Query metrics
            metrics_query = db.query(ExperimentMetric).filter(
                and_(
                    ExperimentMetric.experiment_id == experiment_id,
                    ExperimentMetric.timestamp >= cutoff_time
                )
            )

            # Group by metric type
            metrics_by_type = defaultdict(list)
            for metric in metrics_query.all():
                metrics_by_type[metric.metric_type.value].append(metric.metric_value)

            # Calculate statistics
            summary = {}
            for metric_type, values in metrics_by_type.items():
                if values:
                    summary[metric_type] = {
                        'count': len(values),
                        'mean': sum(values) / len(values),
                        'min': min(values),
                        'max': max(values),
                        'sum': sum(values)
                    }

            db.close()
            return summary

        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return {}

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down metrics collection service")
        self._processing = False

        # Process remaining batches
        batches_to_process = []
        while not self._batch_queue.empty():
            try:
                batch = self._batch_queue.get_nowait()
                batches_to_process.append(batch)
            except asyncio.QueueEmpty:
                break

        if batches_to_process:
            logger.info(f"Processing {len(batches_to_process)} remaining batches")
            await asyncio.gather(
                *[self._process_batch(batch) for batch in batches_to_process],
                return_exceptions=True
            )


# Global service instance
metrics_collection_service = MetricsCollectionService()