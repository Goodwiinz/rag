"""
Data aggregation service for analytics
Handles batch processing and aggregation of analytics data
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, asc

from src.core.database import get_db
from src.models.analytics_event import AnalyticsEvent, EventType, EventSeverity
from src.models.user_session import UserSession, SessionStatus
from src.models.performance_log import PerformanceLog, MetricCategory, PerformanceLevel
from src.models.user import User
from src.models.organization import Organization

logger = logging.getLogger(__name__)


class AggregationGranularity(str, Enum):
    """Data aggregation granularity levels"""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class MetricType(str, Enum):
    """Types of metrics that can be aggregated"""
    COUNT = "count"
    SUM = "sum"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"
    PERCENTILE_95 = "percentile_95"
    PERCENTILE_99 = "percentile_99"
    RATE = "rate"
    RATIO = "ratio"


@dataclass
class AggregationConfig:
    """Configuration for data aggregation"""
    metric_type: MetricType
    granularity: AggregationGranularity
    field_name: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    group_by: Optional[List[str]] = None
    time_range: Optional[Tuple[datetime, datetime]] = None
    organization_id: Optional[str] = None


class AnalyticsDataAggregator:
    """High-performance data aggregation for analytics"""

    def __init__(self, db: Session):
        self.db = db

    async def aggregate_events(
        self,
        config: AggregationConfig,
        event_types: Optional[List[EventType]] = None
    ) -> Dict[str, Any]:
        """Aggregate analytics events"""
        query = self.db.query(AnalyticsEvent)

        # Apply filters
        if config.organization_id:
            query = query.filter(AnalyticsEvent.organization_id == config.organization_id)

        if config.time_range:
            start_date, end_date = config.time_range
            query = query.filter(
                and_(
                    AnalyticsEvent.event_timestamp >= start_date,
                    AnalyticsEvent.event_timestamp < end_date
                )
            )

        if event_types:
            query = query.filter(AnalyticsEvent.event_type.in_(event_types))

        if config.filters:
            for field, value in config.filters.items():
                if hasattr(AnalyticsEvent, field):
                    query = query.filter(getattr(AnalyticsEvent, field) == value)

        # Apply aggregation
        if config.metric_type == MetricType.COUNT:
            result = await self._aggregate_count(query, config)
        elif config.metric_type == MetricType.SUM:
            result = await self._aggregate_sum(query, config)
        elif config.metric_type == MetricType.AVERAGE:
            result = await self._aggregate_average(query, config)
        elif config.metric_type == MetricType.RATE:
            result = await self._aggregate_rate(query, config)
        else:
            raise ValueError(f"Unsupported metric type: {config.metric_type}")

        return result

    async def aggregate_sessions(
        self,
        config: AggregationConfig
    ) -> Dict[str, Any]:
        """Aggregate user sessions"""
        query = self.db.query(UserSession)

        # Apply filters
        if config.organization_id:
            query = query.filter(UserSession.organization_id == config.organization_id)

        if config.time_range:
            start_date, end_date = config.time_range
            query = query.filter(
                and_(
                    UserSession.started_at >= start_date,
                    UserSession.started_at < end_date
                )
            )

        if config.filters:
            for field, value in config.filters.items():
                if hasattr(UserSession, field):
                    query = query.filter(getattr(UserSession, field) == value)

        # Apply aggregation
        if config.metric_type == MetricType.COUNT:
            result = await self._aggregate_session_count(query, config)
        elif config.metric_type == MetricType.AVERAGE:
            result = await self._aggregate_session_average(query, config)
        elif config.metric_type == MetricType.SUM:
            result = await self._aggregate_session_sum(query, config)
        else:
            raise ValueError(f"Unsupported metric type for sessions: {config.metric_type}")

        return result

    async def aggregate_performance(
        self,
        config: AggregationConfig,
        metric_categories: Optional[List[MetricCategory]] = None
    ) -> Dict[str, Any]:
        """Aggregate performance metrics"""
        query = self.db.query(PerformanceLog)

        # Apply filters
        if config.organization_id:
            query = query.filter(PerformanceLog.organization_id == config.organization_id)

        if config.time_range:
            start_date, end_date = config.time_range
            query = query.filter(
                and_(
                    PerformanceLog.timestamp >= start_date,
                    PerformanceLog.timestamp < end_date
                )
            )

        if metric_categories:
            query = query.filter(PerformanceLog.metric_category.in_(metric_categories))

        if config.filters:
            for field, value in config.filters.items():
                if hasattr(PerformanceLog, field):
                    query = query.filter(getattr(PerformanceLog, field) == value)

        # Apply aggregation
        if config.metric_type == MetricType.AVERAGE:
            result = await self._aggregate_performance_average(query, config)
        elif config.metric_type == MetricType.COUNT:
            result = await self._aggregate_performance_count(query, config)
        elif config.metric_type == MetricType.RATE:
            result = await self._aggregate_performance_rate(query, config)
        else:
            raise ValueError(f"Unsupported metric type for performance: {config.metric_type}")

        return result

    async def _aggregate_count(self, query, config: AggregationConfig) -> Dict[str, Any]:
        """Aggregate count metrics"""
        base_query = query

        if config.group_by:
            # Group by specified fields
            group_fields = [getattr(AnalyticsEvent, field) for field in config.group_by]
            results = base_query.with_entities(
                *group_fields,
                func.count(AnalyticsEvent.id).label('count')
            ).group_by(*group_fields).all()

            # Format results
            formatted_results = []
            for result in results:
                group_values = result[:-1]  # All but last element (count)
                count = result[-1]

                group_dict = dict(zip(config.group_by, group_values))
                group_dict['count'] = count
                formatted_results.append(group_dict)

            return {
                "metric_type": "count",
                "granularity": config.granularity,
                "group_by": config.group_by,
                "results": formatted_results,
                "total_count": len(formatted_results)
            }
        else:
            # Simple count
            count = base_query.count()
            return {
                "metric_type": "count",
                "granularity": config.granularity,
                "count": count,
                "results": [{"count": count}]
            }

    async def _aggregate_sum(self, query, config: AggregationConfig) -> Dict[str, Any]:
        """Aggregate sum metrics"""
        if not config.field_name:
            raise ValueError("Field name required for sum aggregation")

        field = getattr(AnalyticsEvent, config.field_name)
        base_query = query.filter(field.isnot(None))

        if config.group_by:
            group_fields = [getattr(AnalyticsEvent, field) for field in config.group_by]
            results = base_query.with_entities(
                *group_fields,
                func.sum(field).label('sum')
            ).group_by(*group_fields).all()

            formatted_results = []
            for result in results:
                group_values = result[:-1]
                sum_value = float(result[-1]) if result[-1] else 0

                group_dict = dict(zip(config.group_by, group_values))
                group_dict['sum'] = sum_value
                formatted_results.append(group_dict)

            return {
                "metric_type": "sum",
                "field": config.field_name,
                "granularity": config.granularity,
                "group_by": config.group_by,
                "results": formatted_results
            }
        else:
            sum_result = base_query.with_entities(func.sum(field)).scalar()
            sum_value = float(sum_result) if sum_result else 0

            return {
                "metric_type": "sum",
                "field": config.field_name,
                "granularity": config.granularity,
                "sum": sum_value,
                "results": [{"sum": sum_value}]
            }

    async def _aggregate_average(self, query, config: AggregationConfig) -> Dict[str, Any]:
        """Aggregate average metrics"""
        if not config.field_name:
            raise ValueError("Field name required for average aggregation")

        field = getattr(AnalyticsEvent, config.field_name)
        base_query = query.filter(field.isnot(None))

        if config.group_by:
            group_fields = [getattr(AnalyticsEvent, field) for field in config.group_by]
            results = base_query.with_entities(
                *group_fields,
                func.avg(field).label('average')
            ).group_by(*group_fields).all()

            formatted_results = []
            for result in results:
                group_values = result[:-1]
                avg_value = float(result[-1]) if result[-1] else 0

                group_dict = dict(zip(config.group_by, group_values))
                group_dict['average'] = avg_value
                formatted_results.append(group_dict)

            return {
                "metric_type": "average",
                "field": config.field_name,
                "granularity": config.granularity,
                "group_by": config.group_by,
                "results": formatted_results
            }
        else:
            avg_result = base_query.with_entities(func.avg(field)).scalar()
            avg_value = float(avg_result) if avg_result else 0

            return {
                "metric_type": "average",
                "field": config.field_name,
                "granularity": config.granularity,
                "average": avg_value,
                "results": [{"average": avg_value}]
            }

    async def _aggregate_rate(self, query, config: AggregationConfig) -> Dict[str, Any]:
        """Aggregate rate metrics (e.g., error rate)"""
        if not config.filters or 'success_condition' not in config.filters:
            raise ValueError("Success condition required for rate aggregation")

        # Count total and successful
        total_count = query.count()

        success_condition = config.filters['success_condition']
        success_query = query

        # Apply success condition
        for field, value in success_condition.items():
            if hasattr(AnalyticsEvent, field):
                if isinstance(value, list):
                    success_query = success_query.filter(getattr(AnalyticsEvent, field).in_(value))
                else:
                    success_query = success_query.filter(getattr(AnalyticsEvent, field) == value)

        success_count = success_query.count()

        rate = (success_count / total_count * 100) if total_count > 0 else 0

        return {
            "metric_type": "rate",
            "granularity": config.granularity,
            "total_count": total_count,
            "success_count": success_count,
            "rate_percentage": rate,
            "results": [{"rate": rate, "total": total_count, "success": success_count}]
        }

    async def _aggregate_session_count(self, query, config: AggregationConfig) -> Dict[str, Any]:
        """Aggregate session count"""
        if config.group_by:
            group_fields = [getattr(UserSession, field) for field in config.group_by]
            results = query.with_entities(
                *group_fields,
                func.count(UserSession.id).label('count')
            ).group_by(*group_fields).all()

            formatted_results = []
            for result in results:
                group_values = result[:-1]
                count = result[-1]

                group_dict = dict(zip(config.group_by, group_values))
                group_dict['count'] = count
                formatted_results.append(group_dict)

            return {
                "metric_type": "session_count",
                "granularity": config.granularity,
                "group_by": config.group_by,
                "results": formatted_results
            }
        else:
            count = query.count()
            return {
                "metric_type": "session_count",
                "granularity": config.granularity,
                "count": count,
                "results": [{"count": count}]
            }

    async def _aggregate_session_average(self, query, config: AggregationConfig) -> Dict[str, Any]:
        """Aggregate session averages"""
        if not config.field_name:
            raise ValueError("Field name required for session average aggregation")

        field = getattr(UserSession, config.field_name)
        base_query = query.filter(field.isnot(None))

        if config.group_by:
            group_fields = [getattr(UserSession, field) for field in config.group_by]
            results = base_query.with_entities(
                *group_fields,
                func.avg(field).label('average')
            ).group_by(*group_fields).all()

            formatted_results = []
            for result in results:
                group_values = result[:-1]
                avg_value = float(result[-1]) if result[-1] else 0

                group_dict = dict(zip(config.group_by, group_values))
                group_dict['average'] = avg_value
                formatted_results.append(group_dict)

            return {
                "metric_type": "session_average",
                "field": config.field_name,
                "granularity": config.granularity,
                "group_by": config.group_by,
                "results": formatted_results
            }
        else:
            avg_result = base_query.with_entities(func.avg(field)).scalar()
            avg_value = float(avg_result) if avg_result else 0

            return {
                "metric_type": "session_average",
                "field": config.field_name,
                "granularity": config.granularity,
                "average": avg_value,
                "results": [{"average": avg_value}]
            }

    async def _aggregate_session_sum(self, query, config: AggregationConfig) -> Dict[str, Any]:
        """Aggregate session sums"""
        if not config.field_name:
            raise ValueError("Field name required for session sum aggregation")

        field = getattr(UserSession, config.field_name)
        base_query = query.filter(field.isnot(None))

        if config.group_by:
            group_fields = [getattr(UserSession, field) for field in config.group_by]
            results = base_query.with_entities(
                *group_fields,
                func.sum(field).label('sum')
            ).group_by(*group_fields).all()

            formatted_results = []
            for result in results:
                group_values = result[:-1]
                sum_value = float(result[-1]) if result[-1] else 0

                group_dict = dict(zip(config.group_by, group_values))
                group_dict['sum'] = sum_value
                formatted_results.append(group_dict)

            return {
                "metric_type": "session_sum",
                "field": config.field_name,
                "granularity": config.granularity,
                "group_by": config.group_by,
                "results": formatted_results
            }
        else:
            sum_result = base_query.with_entities(func.sum(field)).scalar()
            sum_value = float(sum_result) if sum_result else 0

            return {
                "metric_type": "session_sum",
                "field": config.field_name,
                "granularity": config.granularity,
                "sum": sum_value,
                "results": [{"sum": sum_value}]
            }

    async def _aggregate_performance_average(self, query, config: AggregationConfig) -> Dict[str, Any]:
        """Aggregate performance averages"""
        if not config.field_name:
            raise ValueError("Field name required for performance average aggregation")

        field = getattr(PerformanceLog, config.field_name)
        base_query = query.filter(field.isnot(None))

        if config.group_by:
            group_fields = [getattr(PerformanceLog, field) for field in config.group_by]
            results = base_query.with_entities(
                *group_fields,
                func.avg(field).label('average')
            ).group_by(*group_fields).all()

            formatted_results = []
            for result in results:
                group_values = result[:-1]
                avg_value = float(result[-1]) if result[-1] else 0

                group_dict = dict(zip(config.group_by, group_values))
                group_dict['average'] = avg_value
                formatted_results.append(group_dict)

            return {
                "metric_type": "performance_average",
                "field": config.field_name,
                "granularity": config.granularity,
                "group_by": config.group_by,
                "results": formatted_results
            }
        else:
            avg_result = base_query.with_entities(func.avg(field)).scalar()
            avg_value = float(avg_result) if avg_result else 0

            return {
                "metric_type": "performance_average",
                "field": config.field_name,
                "granularity": config.granularity,
                "average": avg_value,
                "results": [{"average": avg_value}]
            }

    async def _aggregate_performance_count(self, query, config: AggregationConfig) -> Dict[str, Any]:
        """Aggregate performance counts"""
        if config.group_by:
            group_fields = [getattr(PerformanceLog, field) for field in config.group_by]
            results = query.with_entities(
                *group_fields,
                func.count(PerformanceLog.id).label('count')
            ).group_by(*group_fields).all()

            formatted_results = []
            for result in results:
                group_values = result[:-1]
                count = result[-1]

                group_dict = dict(zip(config.group_by, group_values))
                group_dict['count'] = count
                formatted_results.append(group_dict)

            return {
                "metric_type": "performance_count",
                "granularity": config.granularity,
                "group_by": config.group_by,
                "results": formatted_results
            }
        else:
            count = query.count()
            return {
                "metric_type": "performance_count",
                "granularity": config.granularity,
                "count": count,
                "results": [{"count": count}]
            }

    async def _aggregate_performance_rate(self, query, config: AggregationConfig) -> Dict[str, Any]:
        """Aggregate performance rates (e.g., error rate)"""
        # Count total and critical/poor performance
        total_count = query.count()

        critical_poor_query = query.filter(
            PerformanceLog.performance_level.in_([PerformanceLevel.CRITICAL, PerformanceLevel.POOR])
        )
        critical_poor_count = critical_poor_query.count()

        error_rate = (critical_poor_count / total_count * 100) if total_count > 0 else 0

        return {
            "metric_type": "performance_error_rate",
            "granularity": config.granularity,
            "total_count": total_count,
            "critical_poor_count": critical_poor_count,
            "error_rate_percentage": error_rate,
            "results": [{"error_rate": error_rate, "total": total_count, "errors": critical_poor_count}]
        }

    def get_time_buckets(self, granularity: AggregationGranularity, start_date: datetime, end_date: datetime) -> List[Tuple[datetime, datetime]]:
        """Generate time buckets for aggregation"""
        buckets = []
        current_start = start_date

        if granularity == AggregationGranularity.MINUTE:
            delta = timedelta(minutes=1)
        elif granularity == AggregationGranularity.HOUR:
            delta = timedelta(hours=1)
        elif granularity == AggregationGranularity.DAY:
            delta = timedelta(days=1)
        elif granularity == AggregationGranularity.WEEK:
            delta = timedelta(weeks=1)
        elif granularity == AggregationGranularity.MONTH:
            delta = timedelta(days=30)
        elif granularity == AggregationGranularity.QUARTER:
            delta = timedelta(days=90)
        elif granularity == AggregationGranularity.YEAR:
            delta = timedelta(days=365)
        else:
            delta = timedelta(hours=1)  # Default to hour

        while current_start < end_date:
            current_end = min(current_start + delta, end_date)
            buckets.append((current_start, current_end))
            current_start = current_end

        return buckets

    async def aggregate_time_series(
        self,
        config: AggregationConfig,
        data_source: str = "events"
    ) -> Dict[str, Any]:
        """Aggregate data into time series"""
        if not config.time_range:
            raise ValueError("Time range required for time series aggregation")

        start_date, end_date = config.time_range
        time_buckets = self.get_time_buckets(config.granularity, start_date, end_date)

        time_series_data = []

        for bucket_start, bucket_end in time_buckets:
            bucket_config = AggregationConfig(
                metric_type=config.metric_type,
                granularity=config.granularity,
                field_name=config.field_name,
                filters=config.filters,
                group_by=config.group_by,
                time_range=(bucket_start, bucket_end),
                organization_id=config.organization_id
            )

            # Aggregate data for this time bucket
            if data_source == "events":
                bucket_data = await self.aggregate_events(bucket_config)
            elif data_source == "sessions":
                bucket_data = await self.aggregate_sessions(bucket_config)
            elif data_source == "performance":
                bucket_data = await self.aggregate_performance(bucket_config)
            else:
                raise ValueError(f"Unknown data source: {data_source}")

            # Extract the value from results
            if bucket_data["results"]:
                if config.metric_type == MetricType.COUNT:
                    value = bucket_data["results"][0].get("count", 0)
                elif config.metric_type == MetricType.SUM:
                    value = bucket_data["results"][0].get("sum", 0)
                elif config.metric_type == MetricType.AVERAGE:
                    value = bucket_data["results"][0].get("average", 0)
                elif config.metric_type == MetricType.RATE:
                    value = bucket_data["results"][0].get("rate", 0)
                else:
                    value = 0
            else:
                value = 0

            time_series_data.append({
                "timestamp": bucket_start.isoformat(),
                "bucket_start": bucket_start.isoformat(),
                "bucket_end": bucket_end.isoformat(),
                "value": value
            })

        return {
            "metric_type": config.metric_type,
            "field": config.field_name,
            "granularity": config.granularity,
            "data_source": data_source,
            "time_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "data_points": time_series_data,
            "total_points": len(time_series_data)
        }