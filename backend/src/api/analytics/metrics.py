"""
Metrics API routes
"""

import logging
import uuid
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks

from src.services.analytics.metrics_service import metrics_service
from src.models.analytics.analytics_models import (
    MetricCreate, MetricUpdate, MetricResponse,
    KPICreate, KPIResponse, MetricQuery, MetricQueryResult
)
from src.auth.dependencies import get_current_user
from src.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["analytics-metrics"])


# Metric endpoints

@router.post("/", response_model=MetricResponse, status_code=status.HTTP_201_CREATED)
async def create_metric(
    request: MetricCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new analytics metric"""
    try:
        metric = await metrics_service.create_metric(
            request=request,
            owner_id=current_user.id
        )
        return metric

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating metric: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create metric"
        )


@router.get("/", response_model=List[MetricResponse])
async def list_metrics(
    metric_type: Optional[str] = Query(None, description="Filter by metric type"),
    is_public: Optional[bool] = Query(None, description="Filter by public status"),
    search: Optional[str] = Query(None, description="Search by name or display name"),
    limit: int = Query(50, ge=1, le=100, description="Number of metrics to return"),
    offset: int = Query(0, ge=0, description="Number of metrics to skip"),
    current_user: User = Depends(get_current_user)
):
    """List analytics metrics"""
    try:
        # This is a simplified implementation
        # In production, you'd implement proper filtering and search
        async with get_async_session() as db:
            query = select(AnalyticsMetric).where(AnalyticsMetric.is_deleted == False)

            if metric_type:
                query = query.where(AnalyticsMetric.metric_type == metric_type)
            if is_public is not None:
                query = query.where(AnalyticsMetric.is_public == is_public)
            if search:
                query = query.where(
                    or_(
                        AnalyticsMetric.name.ilike(f"%{search}%"),
                        AnalyticsMetric.display_name.ilike(f"%{search}%")
                    )
                )

            query = query.order_by(AnalyticsMetric.created_at.desc()).offset(offset).limit(limit)
            result = await db.execute(query)
            metrics = result.scalars().all()

            return [await metrics_service._metric_to_response(metric) for metric in metrics]

    except Exception as e:
        logger.error(f"Error listing metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list metrics"
        )


@router.get("/{metric_id}", response_model=MetricResponse)
async def get_metric(
    metric_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """Get metric by ID"""
    try:
        metric = await metrics_service.get_metric(
            metric_id=metric_id,
            user_id=current_user.id
        )
        if not metric:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Metric not found"
            )
        return metric

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metric {metric_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get metric"
        )


@router.put("/{metric_id}", response_model=MetricResponse)
async def update_metric(
    metric_id: uuid.UUID,
    request: MetricUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update metric"""
    try:
        metric = await metrics_service.update_metric(
            metric_id=metric_id,
            request=request,
            user_id=current_user.id
        )
        if not metric:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Metric not found"
            )
        return metric

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating metric {metric_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update metric"
        )


@router.delete("/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_metric(
    metric_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """Delete metric"""
    try:
        success = await metrics_service.delete_metric(
            metric_id=metric_id,
            user_id=current_user.id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Metric not found"
            )

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting metric {metric_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete metric"
        )


@router.post("/{metric_id}/ingest", status_code=status.HTTP_200_OK)
async def ingest_metric_value(
    metric_id: uuid.UUID,
    value: float,
    timestamp: Optional[datetime] = Query(None, description="Timestamp (default: now)"),
    dimensions: Optional[Dict[str, Any]] = None,
    quality_score: Optional[float] = Query(None, ge=0, le=1, description="Data quality score"),
    current_user: User = Depends(get_current_user)
):
    """Ingest a single metric value"""
    try:
        # Get metric name first
        async with get_async_session() as db:
            query = select(AnalyticsMetric).where(AnalyticsMetric.id == metric_id)
            result = await db.execute(query)
            metric = result.scalar_one_or_none()

            if not metric:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Metric not found"
                )

        success = await metrics_service.ingest_metric_value(
            metric_name=metric.name,
            value=value,
            timestamp=timestamp,
            dimensions=dimensions,
            quality_score=quality_score,
            user_id=current_user.id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to ingest metric value"
            )

        return {"message": "Metric value ingested successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting metric value: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest metric value"
        )


@router.post("/ingest/batch", status_code=status.HTTP_200_OK)
async def ingest_batch_values(
    values: List[Dict[str, Any]],
    current_user: User = Depends(get_current_user)
):
    """Ingest multiple metric values in batch"""
    try:
        success_count = await metrics_service.ingest_batch_values(values)
        return {
            "message": f"Successfully ingested {success_count} out of {len(values)} values",
            "success_count": success_count,
            "total_count": len(values)
        }

    except Exception as e:
        logger.error(f"Error ingesting batch values: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest batch values"
        )


@router.post("/query", response_model=List[MetricQueryResult])
async def query_metrics(
    query: MetricQuery,
    current_user: User = Depends(get_current_user)
):
    """Query metrics with specified parameters"""
    try:
        results = await metrics_service.query_metrics(
            query=query,
            user_id=current_user.id
        )
        return results

    except Exception as e:
        logger.error(f"Error querying metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to query metrics"
        )


@router.get("/{metric_id}/statistics", response_model=Dict[str, Any])
async def get_metric_statistics(
    metric_id: uuid.UUID,
    time_range: str = Query("1d", description="Time range (e.g., 1h, 1d, 1w)"),
    aggregation: str = Query("avg", description="Aggregation type"),
    current_user: User = Depends(get_current_user)
):
    """Get statistical summary for a metric"""
    try:
        from src.models.analytics.analytics_models import AggregationType
        agg_type = AggregationType(aggregation)

        stats = await metrics_service.get_metric_statistics(
            metric_id=metric_id,
            time_range=time_range,
            aggregation=agg_type
        )
        return stats

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting metric statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get metric statistics"
        )


# KPI endpoints

@router.post("/kpis", response_model=KPIResponse, status_code=status.HTTP_201_CREATED)
async def create_kpi(
    request: KPICreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new KPI"""
    try:
        kpi = await metrics_service.create_kpi(
            request=request,
            owner_id=current_user.id
        )
        return kpi

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating KPI: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create KPI"
        )


@router.get("/kpis", response_model=List[KPIResponse])
async def list_kpis(
    metric_id: Optional[uuid.UUID] = Query(None, description="Filter by metric ID"),
    is_critical: Optional[bool] = Query(None, description="Filter by critical status"),
    limit: int = Query(50, ge=1, le=100, description="Number of KPIs to return"),
    offset: int = Query(0, ge=0, description="Number of KPIs to skip"),
    current_user: User = Depends(get_current_user)
):
    """List KPIs"""
    try:
        # This is a simplified implementation
        async with get_async_session() as db:
            query = select(AnalyticsKPI).where(AnalyticsKPI.is_active == True)

            if metric_id:
                query = query.where(AnalyticsKPI.metric_id == metric_id)
            if is_critical is not None:
                query = query.where(AnalyticsKPI.is_critical == is_critical)

            query = query.order_by(AnalyticsKPI.created_at.desc()).offset(offset).limit(limit)
            result = await db.execute(query)
            kpis = result.scalars().all()

            kpi_responses = []
            for kpi in kpis:
                current_value = await metrics_service._calculate_kpi_value(kpi)
                status = metrics_service._determine_kpi_status(current_value, kpi)

                kpi_response = KPIResponse(
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
                    status=status
                )
                kpi_responses.append(kpi_response)

            return kpi_responses

    except Exception as e:
        logger.error(f"Error listing KPIs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list KPIs"
        )


@router.get("/kpis/{kpi_id}", response_model=KPIResponse)
async def get_kpi(
    kpi_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """Get KPI by ID"""
    try:
        async with get_async_session() as db:
            query = select(AnalyticsKPI).where(
                and_(
                    AnalyticsKPI.id == kpi_id,
                    AnalyticsKPI.is_active == True
                )
            )
            result = await db.execute(query)
            kpi = result.scalar_one_or_none()

            if not kpi:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="KPI not found"
                )

            current_value = await metrics_service._calculate_kpi_value(kpi)
            status = metrics_service._determine_kpi_status(current_value, kpi)

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
                status=status
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting KPI {kpi_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get KPI"
        )


@router.post("/events", status_code=status.HTTP_200_OK)
async def ingest_event(
    event_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Ingest analytics event"""
    try:
        # Add user context if not provided
        if "user_id" not in event_data:
            event_data["user_id"] = current_user.id

        success = await metrics_service.ingest_event(event_data)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to ingest event"
            )

        return {"message": "Event ingested successfully"}

    except Exception as e:
        logger.error(f"Error ingesting event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest event"
        )


@router.get("/types", response_model=Dict[str, Any])
async def get_metric_types(
    current_user: User = Depends(get_current_user)
):
    """Get available metric types and their configurations"""
    try:
        from src.models.analytics.analytics_models import MetricType, AggregationType

        metric_types = {
            "counter": {
                "display_name": "Counter",
                "description": "Cumulative count that only goes up",
                "aggregations": ["sum", "rate"]
            },
            "gauge": {
                "display_name": "Gauge",
                "description": "Value that can go up or down",
                "aggregations": ["sum", "avg", "min", "max", "last"]
            },
            "histogram": {
                "display_name": "Histogram",
                "description": "Distribution of values",
                "aggregations": ["sum", "avg", "min", "max", "count"]
            },
            "timer": {
                "display_name": "Timer",
                "description": "Duration measurements",
                "aggregations": ["sum", "avg", "min", "max", "p95", "p99"]
            }
        }

        aggregation_types = {
            "sum": "Sum of all values",
            "avg": "Average of values",
            "min": "Minimum value",
            "max": "Maximum value",
            "count": "Count of values",
            "rate": "Rate per second",
            "p95": "95th percentile",
            "p99": "99th percentile"
        }

        return {
            "metric_types": metric_types,
            "aggregation_types": aggregation_types,
            "time_ranges": ["1m", "5m", "15m", "30m", "1h", "6h", "12h", "1d", "1w", "1M"]
        }

    except Exception as e:
        logger.error(f"Error getting metric types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get metric types"
        )