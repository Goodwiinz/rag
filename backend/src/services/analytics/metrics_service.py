"""
Metrics Aggregation Service for analytics metrics
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import redis.asyncio as redis
from sqlalchemy import and_, delete, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.core.database import get_async_session
from src.models.analytics.analytics_models import (
    AggregationType,
    AnalyticsEvent,
    AnalyticsKPI,
    AnalyticsMetric,
    EventType,
    KPICreate,
    KPIResponse,
    MetricAggregation,
    MetricCreate,
    MetricQuery,
    MetricQueryResult,
    MetricResponse,
    MetricType,
    MetricUpdate,
    TimeSeriesData,
)
from src.models.base import GUID

logger = logging.getLogger(__name__)


class MetricResolution(Enum):
    """Time resolution for metrics"""

    MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    HOUR = "1h"
    SIX_HOURS = "6h"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1M"


@dataclass
class MetricValue:
    """Single metric value with metadata"""

    value: float
    timestamp: datetime
    count: int = 1
    quality_score: Optional[float] = None
    dimensions: Optional[Dict[str, Any]] = None


@dataclass
class AggregatedMetric:
    """Aggregated metric result"""

    metric_id: str
    metric_name: str
    aggregation_type: AggregationType
    time_window: str
    timestamp: datetime
    value: float
    count: int
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    sum_value: Optional[float] = None
    sample_rate: float = 1.0
    dimensions: Optional[Dict[str, Any]] = None


class MetricsService:
    """Service for metrics aggregation and querying"""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.aggregation_queue = asyncio.Queue()
        self.running = False
        self.batch_size = 1000
        self.max_aggregation_time_seconds = 300

        # Time windows in seconds
        self.time_windows = {
            MetricResolution.MINUTE: 60,
            MetricResolution.FIVE_MINUTES: 300,
            MetricResolution.FIFTEEN_MINUTES: 900,
            MetricResolution.HOUR: 3600,
            MetricResolution.SIX_HOURS: 21600,
            MetricResolution.DAY: 86400,
            MetricResolution.WEEK: 604800,
            MetricResolution.MONTH: 2592000,
        }

        # Cache TTL in seconds
        self.cache_ttl = {
            MetricResolution.MINUTE: 300,
            MetricResolution.FIVE_MINUTES: 900,
            MetricResolution.FIFTEEN_MINUTES: 1800,
            MetricResolution.HOUR: 7200,
            MetricResolution.SIX_HOURS: 21600,
            MetricResolution.DAY: 86400,
            MetricResolution.WEEK: 604800,
            MetricResolution.MONTH: 2592000,
        }

    async def initialize(self):
        """Initialize the metrics service"""
        try:
            # Initialize Redis connection
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                retry_on_timeout=True,
            )

            # Test Redis connection
            await self.redis_client.ping()
            self.running = True

            # Start background aggregation task
            asyncio.create_task(self._aggregation_loop())

            logger.info("Metrics service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize metrics service: {e}")
            raise

    async def shutdown(self):
        """Shutdown the metrics service"""
        self.running = False
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Metrics service shut down")

    async def create_metric(
        self, request: MetricCreate, owner_id: uuid.UUID
    ) -> MetricResponse:
        """Create a new analytics metric"""
        try:
            async with get_async_session() as db:
                # Check if metric name already exists
                existing_query = select(AnalyticsMetric).where(
                    and_(
                        AnalyticsMetric.name == request.name,
                        AnalyticsMetric.is_deleted == False,
                    )
                )
                result = await db.execute(existing_query)
                if result.scalar_one_or_none():
                    raise ValueError(
                        f"Metric with name '{request.name}' already exists"
                    )

                # Create metric
                metric = AnalyticsMetric(
                    name=request.name,
                    display_name=request.display_name,
                    description=request.description,
                    metric_type=request.metric_type,
                    unit=request.unit,
                    data_source=request.data_source,
                    calculation_config=request.calculation_config,
                    default_aggregation=request.default_aggregation,
                    available_aggregations=request.available_aggregations,
                    dimensions=request.dimensions,
                    default_filters=request.default_filters,
                    visualization_type=request.visualization_type,
                    color_scheme=request.color_scheme,
                    is_public=request.is_public,
                )
                db.add(metric)
                await db.commit()
                await db.refresh(metric)

                return await self._metric_to_response(metric)

        except Exception as e:
            logger.error(f"Error creating metric: {e}")
            raise

    async def get_metric(
        self, metric_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[MetricResponse]:
        """Get metric by ID"""
        try:
            async with get_async_session() as db:
                query = select(AnalyticsMetric).where(
                    and_(
                        AnalyticsMetric.id == metric_id,
                        AnalyticsMetric.is_deleted == False,
                    )
                )
                result = await db.execute(query)
                metric = result.scalar_one_or_none()

                if not metric:
                    return None

                # Check permissions (simplified)
                if not metric.is_public:
                    # Would need proper permission checking
                    pass

                return await self._metric_to_response(metric)

        except Exception as e:
            logger.error(f"Error getting metric {metric_id}: {e}")
            return None

    async def update_metric(
        self, metric_id: uuid.UUID, request: MetricUpdate, user_id: uuid.UUID
    ) -> Optional[MetricResponse]:
        """Update metric"""
        try:
            async with get_async_session() as db:
                query = select(AnalyticsMetric).where(
                    and_(
                        AnalyticsMetric.id == metric_id,
                        AnalyticsMetric.is_deleted == False,
                    )
                )
                result = await db.execute(query)
                metric = result.scalar_one_or_none()

                if not metric:
                    return None

                # Check permissions
                # Would need proper ownership/permission checking

                # Update fields
                update_data = request.model_dump(exclude_unset=True)
                for field, value in update_data.items():
                    setattr(metric, field, value)

                await db.commit()
                await db.refresh(metric)

                return await self._metric_to_response(metric)

        except Exception as e:
            logger.error(f"Error updating metric {metric_id}: {e}")
            return None

    async def delete_metric(self, metric_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Delete metric"""
        try:
            async with get_async_session() as db:
                query = select(AnalyticsMetric).where(
                    and_(
                        AnalyticsMetric.id == metric_id,
                        AnalyticsMetric.is_deleted == False,
                    )
                )
                result = await db.execute(query)
                metric = result.scalar_one_or_none()

                if not metric:
                    return False

                # Check permissions
                # Would need proper ownership/permission checking

                # Soft delete
                metric.soft_delete()
                await db.commit()

                return True

        except Exception as e:
            logger.error(f"Error deleting metric {metric_id}: {e}")
            return False

    async def create_kpi(
        self,
        request: KPICreate,
        owner_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None,
    ) -> KPIResponse:
        """Create a new KPI"""
        try:
            async with get_async_session() as db:
                # Check if metric exists
                metric_query = select(AnalyticsMetric).where(
                    AnalyticsMetric.id == request.metric_id
                )
                result = await db.execute(metric_query)
                metric = result.scalar_one_or_none()

                if not metric:
                    raise ValueError(f"Metric not found: {request.metric_id}")

                # Create KPI
                kpi = AnalyticsKPI(
                    name=request.name,
                    display_name=request.display_name,
                    description=request.description,
                    metric_id=request.metric_id,
                    organization_id=organization_id,
                    target_value=request.target_value,
                    warning_threshold=request.warning_threshold,
                    critical_threshold=request.critical_threshold,
                    aggregation_type=request.aggregation_type,
                    time_window=request.time_window,
                    filters=request.filters,
                    dimensions=request.dimensions,
                    is_critical=request.is_critical,
                )
                db.add(kpi)
                await db.commit()
                await db.refresh(kpi)

                # Calculate current value
                current_value = await self._calculate_kpi_value(kpi)
                kpi_status = self._determine_kpi_status(current_value, kpi)

                return KPIResponse(
                    id=kpi.id,
                    name=kpi.name,
                    display_name=kpi.display_name,
                    description=kpi.description,
                    metric_id=kpi.metric_id,
                    target_value=kpi.target_value,
                    warning_threshold=kpi.warning_threshold,
                    critical_threshold=kpi.critical_threshold,
                    aggregation_type=kpi.aggregation_type,
                    time_window=kpi.time_window,
                    filters=kpi.filters,
                    dimensions=kpi.dimensions,
                    is_active=kpi.is_active,
                    is_critical=kpi.is_critical,
                    created_at=kpi.created_at,
                    updated_at=kpi.updated_at,
                    current_value=current_value,
                    status=kpi_status,
                )

        except Exception as e:
            logger.error(f"Error creating KPI: {e}")
            raise

    async def query_metrics(
        self, query: MetricQuery, user_id: uuid.UUID
    ) -> List[MetricQueryResult]:
        """Query metrics with specified parameters"""
        try:
            results = []

            for metric_id in query.metric_ids:
                # Get metric
                async with get_async_session() as db:
                    metric_query = select(AnalyticsMetric).where(
                        and_(
                            AnalyticsMetric.id == metric_id,
                            AnalyticsMetric.is_deleted == False,
                        )
                    )
                    result = await db.execute(metric_query)
                    metric = result.scalar_one_or_none()

                    if not metric:
                        continue

                # Get metric data
                time_series_data = await self._get_metric_data(
                    metric,
                    query.aggregation,
                    query.time_range,
                    query.filters,
                    query.dimensions,
                    query.group_by,
                )

                # Convert to result format
                query_result = MetricQueryResult(
                    metric_id=metric_id,
                    metric_name=metric.name,
                    aggregation=query.aggregation,
                    time_range=query.time_range,
                    data=time_series_data,
                    total_count=len(time_series_data),
                    has_more=len(time_series_data) >= (query.limit or 10000),
                )
                results.append(query_result)

            return results

        except Exception as e:
            logger.error(f"Error querying metrics: {e}")
            raise

    async def ingest_metric_value(
        self,
        metric_name: str,
        value: float,
        timestamp: Optional[datetime] = None,
        dimensions: Optional[Dict[str, Any]] = None,
        quality_score: Optional[float] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """Ingest a single metric value"""
        try:
            if timestamp is None:
                timestamp = datetime.utcnow()

            # Get metric
            async with get_async_session() as db:
                metric_query = select(AnalyticsMetric).where(
                    and_(
                        AnalyticsMetric.name == metric_name,
                        AnalyticsMetric.is_deleted == False,
                    )
                )
                result = await db.execute(metric_query)
                metric = result.scalar_one_or_none()

                if not metric:
                    logger.warning(f"Metric not found: {metric_name}")
                    return False

            # Store raw value in Redis for immediate access
            if self.redis_client:
                redis_key = f"metric:{metric_name}:raw:{timestamp.timestamp()}"
                await self.redis_client.setex(redis_key, 3600, str(value))  # 1 hour TTL

                # Store in aggregation queue
                await self.aggregation_queue.put(
                    {
                        "metric_id": str(metric.id),
                        "metric_name": metric_name,
                        "value": value,
                        "timestamp": timestamp,
                        "dimensions": dimensions or {},
                        "quality_score": quality_score or 1.0,
                        "user_id": str(user_id) if user_id else None,
                    }
                )

            return True

        except Exception as e:
            logger.error(f"Error ingesting metric value: {e}")
            return False

    async def ingest_batch_values(self, values: List[Dict[str, Any]]) -> int:
        """Ingest multiple metric values in batch"""
        success_count = 0

        for value_data in values:
            try:
                success = await self.ingest_metric_value(
                    metric_name=value_data["metric_name"],
                    value=value_data["value"],
                    timestamp=value_data.get("timestamp"),
                    dimensions=value_data.get("dimensions"),
                    quality_score=value_data.get("quality_score"),
                    user_id=value_data.get("user_id"),
                )
                if success:
                    success_count += 1
            except Exception as e:
                logger.error(f"Error ingesting batch value: {e}")

        return success_count

    async def ingest_event(self, event_data: Dict[str, Any]) -> bool:
        """Ingest analytics event"""
        try:
            async with get_async_session() as db:
                event = AnalyticsEvent(
                    event_type=event_data["event_type"],
                    event_name=event_data["event_name"],
                    event_category=event_data.get("event_category"),
                    user_id=event_data.get("user_id"),
                    session_id=event_data.get("session_id"),
                    request_id=event_data.get("request_id"),
                    properties=event_data.get("properties"),
                    value=event_data.get("value"),
                    tags=event_data.get("tags"),
                    country=event_data.get("country"),
                    city=event_data.get("city"),
                    timezone=event_data.get("timezone"),
                )
                db.add(event)
                await db.commit()

            # Extract metrics from event if configured
            await self._extract_metrics_from_event(event_data)

            return True

        except Exception as e:
            logger.error(f"Error ingesting event: {e}")
            return False

    async def get_metric_statistics(
        self,
        metric_id: uuid.UUID,
        time_range: str = "1d",
        aggregation: AggregationType = AggregationType.AVERAGE,
    ) -> Dict[str, Any]:
        """Get statistical summary for a metric"""
        try:
            # Get time series data
            async with get_async_session() as db:
                metric_query = select(AnalyticsMetric).where(
                    AnalyticsMetric.id == metric_id
                )
                result = await db.execute(metric_query)
                metric = result.scalar_one_or_none()

                if not metric:
                    raise ValueError(f"Metric not found: {metric_id}")

            time_series_data = await self._get_metric_data(
                metric, aggregation, time_range
            )

            if not time_series_data:
                return {
                    "count": 0,
                    "mean": 0,
                    "min": 0,
                    "max": 0,
                    "stddev": 0,
                    "sum": 0,
                }

            values = [d.value for d in time_series_data]

            # Calculate statistics
            import statistics

            stats = {
                "count": len(values),
                "mean": statistics.mean(values),
                "min": min(values),
                "max": max(values),
                "sum": sum(values),
            }

            if len(values) > 1:
                stats["stddev"] = statistics.stdev(values)
            else:
                stats["stddev"] = 0

            # Add percentiles
            sorted_values = sorted(values)
            n = len(sorted_values)
            stats["median"] = statistics.median(values)
            stats["p95"] = sorted_values[int(0.95 * n)] if n > 0 else 0
            stats["p99"] = sorted_values[int(0.99 * n)] if n > 0 else 0

            return stats

        except Exception as e:
            logger.error(f"Error getting metric statistics: {e}")
            raise

    async def _get_metric_data(
        self,
        metric: AnalyticsMetric,
        aggregation: AggregationType,
        time_range: str,
        filters: Optional[List[Dict[str, Any]]] = None,
        dimensions: Optional[List[str]] = None,
        group_by: Optional[List[str]] = None,
    ) -> List[TimeSeriesData]:
        """Get time series data for a metric"""
        try:
            # Calculate time window
            end_time = datetime.utcnow()
            start_time = self._calculate_start_time(time_range, end_time)

            # Determine appropriate time resolution
            resolution = self._determine_resolution(time_range)

            # Try cache first
            cache_key = f"metric:{metric.id}:{aggregation}:{resolution}:{time_range}"
            if self.redis_client:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    import json

                    cached_values = json.loads(cached_data)
                    return [
                        TimeSeriesData(
                            timestamp=datetime.fromisoformat(v["timestamp"]),
                            value=v["value"],
                            count=v.get("count"),
                            metadata=v.get("metadata"),
                        )
                        for v in cached_values
                    ]

            # Get data from database
            async with get_async_session() as db:
                query = (
                    select(MetricAggregation)
                    .where(
                        and_(
                            MetricAggregation.metric_id == metric.id,
                            MetricAggregation.aggregation_type == aggregation,
                            MetricAggregation.time_window == resolution.value,
                            MetricAggregation.timestamp >= start_time,
                            MetricAggregation.timestamp <= end_time,
                        )
                    )
                    .order_by(MetricAggregation.timestamp)
                )

                result = await db.execute(query)
                aggregations = result.scalars().all()

            # Convert to time series data
            time_series_data = []
            for agg in aggregations:
                time_series_data.append(
                    TimeSeriesData(
                        timestamp=agg.timestamp,
                        value=agg.value,
                        count=agg.count,
                        metadata={
                            "min_value": agg.min_value,
                            "max_value": agg.max_value,
                            "sum_value": agg.sum_value,
                            "sample_rate": agg.sample_rate,
                            "dimensions": agg.dimensions,
                        },
                    )
                )

            # Cache the result
            if self.redis_client and time_series_data:
                cache_data = [
                    {
                        "timestamp": ts.timestamp.isoformat(),
                        "value": ts.value,
                        "count": ts.count,
                        "metadata": ts.metadata,
                    }
                    for ts in time_series_data
                ]
                await self.redis_client.setex(
                    cache_key, self.cache_ttl[resolution], json.dumps(cache_data)
                )

            return time_series_data

        except Exception as e:
            logger.error(f"Error getting metric data: {e}")
            return []

    async def _calculate_kpi_value(self, kpi: AnalyticsKPI) -> Optional[float]:
        """Calculate current value for a KPI"""
        try:
            # Get metric
            async with get_async_session() as db:
                metric_query = select(AnalyticsMetric).where(
                    AnalyticsMetric.id == kpi.metric_id
                )
                result = await db.execute(metric_query)
                metric = result.scalar_one_or_none()

                if not metric:
                    return None

            # Get recent data
            time_series_data = await self._get_metric_data(
                metric, kpi.aggregation_type, kpi.time_range
            )

            if not time_series_data:
                return None

            # Get the most recent value
            return time_series_data[-1].value

        except Exception as e:
            logger.error(f"Error calculating KPI value: {e}")
            return None

    def _determine_kpi_status(
        self, current_value: Optional[float], kpi: AnalyticsKPI
    ) -> str:
        """Determine KPI status based on thresholds"""
        if current_value is None:
            return "unknown"

        if kpi.critical_threshold is not None:
            if current_value <= kpi.critical_threshold:
                return "critical"

        if kpi.warning_threshold is not None:
            if current_value <= kpi.warning_threshold:
                return "warning"

        if kpi.target_value is not None:
            if current_value >= kpi.target_value:
                return "good"

        return "normal"

    def _calculate_start_time(self, time_range: str, end_time: datetime) -> datetime:
        """Calculate start time from time range string"""
        if time_range.endswith("m"):
            minutes = int(time_range[:-1])
            return end_time - timedelta(minutes=minutes)
        elif time_range.endswith("h"):
            hours = int(time_range[:-1])
            return end_time - timedelta(hours=hours)
        elif time_range.endswith("d"):
            days = int(time_range[:-1])
            return end_time - timedelta(days=days)
        elif time_range.endswith("w"):
            weeks = int(time_range[:-1])
            return end_time - timedelta(weeks=weeks)
        elif time_range.endswith("M"):
            months = int(time_range[:-1])
            return end_time - timedelta(days=months * 30)
        else:
            # Default to 1 day
            return end_time - timedelta(days=1)

    def _determine_resolution(self, time_range: str) -> MetricResolution:
        """Determine appropriate time resolution based on time range"""
        if time_range.endswith("m"):
            minutes = int(time_range[:-1])
            if minutes <= 60:
                return MetricResolution.MINUTE
            elif minutes <= 300:
                return MetricResolution.FIVE_MINUTES
            else:
                return MetricResolution.FIFTEEN_MINUTES
        elif time_range.endswith("h"):
            hours = int(time_range[:-1])
            if hours <= 6:
                return MetricResolution.HOUR
            else:
                return MetricResolution.SIX_HOURS
        elif time_range.endswith("d"):
            days = int(time_range[:-1])
            if days <= 7:
                return MetricResolution.DAY
            else:
                return MetricResolution.WEEK
        else:
            return MetricResolution.HOUR

    async def _aggregation_loop(self):
        """Background loop for aggregating metrics"""
        while self.running:
            try:
                # Process batch of values
                batch = []
                for _ in range(self.batch_size):
                    try:
                        value = await asyncio.wait_for(
                            self.aggregation_queue.get(), timeout=1.0
                        )
                        batch.append(value)
                    except asyncio.TimeoutError:
                        break

                if batch:
                    await self._process_aggregation_batch(batch)

                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in aggregation loop: {e}")
                await asyncio.sleep(1)

    async def _process_aggregation_batch(self, batch: List[Dict[str, Any]]) -> None:
        """Process a batch of metric values for aggregation"""
        try:
            # Group by metric and time windows
            grouped = defaultdict(list)
            for value in batch:
                metric_id = value["metric_id"]
                timestamp = value["timestamp"]
                dimensions = value.get("dimensions", {})

                # Group by different time windows
                for resolution in [
                    MetricResolution.MINUTE,
                    MetricResolution.HOUR,
                    MetricResolution.DAY,
                ]:
                    bucket_time = self._bucket_timestamp(timestamp, resolution)
                    key = f"{metric_id}:{resolution.value}:{bucket_time.isoformat()}:{hash(str(dimensions)) % 10000}"
                    grouped[key].append(value)

            # Process each group
            async with get_async_session() as db:
                for key, values in grouped.items():
                    await self._aggregate_and_store(key, values, db)

        except Exception as e:
            logger.error(f"Error processing aggregation batch: {e}")

    async def _aggregate_and_store(
        self, key: str, values: List[Dict[str, Any]], db: AsyncSession
    ) -> None:
        """Aggregate values for a specific key and store in database"""
        try:
            if not values:
                return

            # Parse key
            parts = key.split(":")
            metric_id = uuid.UUID(parts[0])
            resolution = parts[1]
            bucket_time = datetime.fromisoformat(parts[2])

            # Get metric
            metric_query = select(AnalyticsMetric).where(
                AnalyticsMetric.id == metric_id
            )
            result = await db.execute(metric_query)
            metric = result.scalar_one_or_none()

            if not metric:
                return

            # Calculate aggregations
            numeric_values = [
                v["value"] for v in values if isinstance(v["value"], (int, float))
            ]
            if not numeric_values:
                return

            # Store different aggregation types
            aggregations = [
                (AggregationType.SUM, sum(numeric_values)),
                (AggregationType.AVERAGE, sum(numeric_values) / len(numeric_values)),
                (AggregationType.MIN, min(numeric_values)),
                (AggregationType.MAX, max(numeric_values)),
                (AggregationType.COUNT, len(numeric_values)),
            ]

            for agg_type, agg_value in aggregations:
                # Check if aggregation already exists
                existing_query = select(MetricAggregation).where(
                    and_(
                        MetricAggregation.metric_id == metric_id,
                        MetricAggregation.aggregation_type == agg_type,
                        MetricAggregation.time_window == resolution,
                        MetricAggregation.timestamp == bucket_time,
                        MetricAggregation.dimensions_hash
                        == str(hash(str(values[0].get("dimensions", {}))) % 10000),
                    )
                )
                existing_result = await db.execute(existing_query)
                existing_agg = existing_result.scalar_one_or_none()

                if existing_agg:
                    # Update existing aggregation
                    existing_agg.value = agg_value
                    existing_agg.count = len(numeric_values)
                    existing_agg.min_value = min(numeric_values)
                    existing_agg.max_value = max(numeric_values)
                    existing_agg.sum_value = sum(numeric_values)
                else:
                    # Create new aggregation
                    dimensions = values[0].get("dimensions", {})
                    new_agg = MetricAggregation(
                        metric_id=metric_id,
                        aggregation_type=agg_type,
                        time_window=resolution,
                        timestamp=bucket_time,
                        dimensions_hash=str(hash(str(dimensions)) % 10000),
                        dimensions=dimensions,
                        value=agg_value,
                        count=len(numeric_values),
                        min_value=min(numeric_values),
                        max_value=max(numeric_values),
                        sum_value=sum(numeric_values),
                        sample_rate=1.0,
                        data_quality_score=sum(
                            v.get("quality_score", 1.0) for v in values
                        )
                        / len(values),
                    )
                    db.add(new_agg)

            await db.commit()

        except Exception as e:
            logger.error(f"Error aggregating and storing values: {e}")

    def _bucket_timestamp(
        self, timestamp: datetime, resolution: MetricResolution
    ) -> datetime:
        """Bucket timestamp to specified resolution"""
        if resolution == MetricResolution.MINUTE:
            return timestamp.replace(second=0, microsecond=0)
        elif resolution == MetricResolution.FIVE_MINUTES:
            minute = (timestamp.minute // 5) * 5
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif resolution == MetricResolution.FIFTEEN_MINUTES:
            minute = (timestamp.minute // 15) * 15
            return timestamp.replace(minute=minute, second=0, microsecond=0)
        elif resolution == MetricResolution.HOUR:
            return timestamp.replace(minute=0, second=0, microsecond=0)
        elif resolution == MetricResolution.SIX_HOURS:
            hour = (timestamp.hour // 6) * 6
            return timestamp.replace(hour=hour, minute=0, second=0, microsecond=0)
        elif resolution == MetricResolution.DAY:
            return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        elif resolution == MetricResolution.WEEK:
            # Start of week (Monday)
            days_since_monday = timestamp.weekday()
            start_of_week = timestamp - timedelta(days=days_since_monday)
            return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        elif resolution == MetricResolution.MONTH:
            return timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return timestamp

    async def _extract_metrics_from_event(self, event_data: Dict[str, Any]) -> None:
        """Extract metrics from event data"""
        # This is a simplified implementation
        # In production, you'd have configurable metric extraction rules

        try:
            # Example: extract value as a metric
            if "value" in event_data and isinstance(event_data["value"], (int, float)):
                await self.ingest_metric_value(
                    metric_name=f"event.{event_data['event_type']}.value",
                    value=event_data["value"],
                    timestamp=event_data.get("timestamp", datetime.utcnow()),
                    dimensions={
                        "event_name": event_data.get("event_name"),
                        "event_category": event_data.get("event_category"),
                    },
                )

            # Example: count events by type
            await self.ingest_metric_value(
                metric_name=f"event.{event_data['event_type']}.count",
                value=1,
                timestamp=event_data.get("timestamp", datetime.utcnow()),
                dimensions={
                    "event_name": event_data.get("event_name"),
                    "event_category": event_data.get("event_category"),
                },
            )

        except Exception as e:
            logger.error(f"Error extracting metrics from event: {e}")

    async def _metric_to_response(self, metric: AnalyticsMetric) -> MetricResponse:
        """Convert metric model to response"""
        return MetricResponse(
            id=metric.id,
            name=metric.name,
            display_name=metric.display_name,
            description=metric.description,
            metric_type=metric.metric_type,
            unit=metric.unit,
            data_source=metric.data_source,
            calculation_config=metric.calculation_config,
            default_aggregation=metric.default_aggregation,
            available_aggregations=metric.available_aggregations,
            dimensions=metric.dimensions,
            default_filters=metric.default_filters,
            visualization_type=metric.visualization_type,
            color_scheme=metric.color_scheme,
            is_active=metric.is_active,
            is_public=metric.is_public,
            created_at=metric.created_at,
            updated_at=metric.updated_at,
        )


# Global instance
metrics_service = MetricsService()
