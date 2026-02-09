"""
Monitoring API Endpoints

Main API endpoints for the observability manager and overall system monitoring.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from src.auth.rbac_decorator import require_roles

from ..config.monitoring_config import get_monitoring_config
from ..services.observability_manager import (
    ObservabilityManager,
    get_observability_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


class HealthResponse(BaseModel):
    """Health check response model"""

    status: str
    manager: Dict[str, Any]
    services: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MetricsRequest(BaseModel):
    """Metrics query request model"""

    service: Optional[str] = None
    metric_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    labels: Optional[Dict[str, str]] = None


class TracesRequest(BaseModel):
    """Traces query request model"""

    trace_id: Optional[str] = None
    service: Optional[str] = None
    operation: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)


class LogsRequest(BaseModel):
    """Logs query request model"""

    level: Optional[str] = None
    service: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    search: Optional[str] = None
    limit: int = Field(default=100, ge=1, le=1000)


class AlertsRequest(BaseModel):
    """Alerts query request model"""

    severity: Optional[str] = None
    status: Optional[str] = None
    service: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)


class AlertRuleRequest(BaseModel):
    """Alert rule creation request model"""

    name: str = Field(..., min_length=1, max_length=255)
    conditions: Dict[str, Any] = Field(..., min_items=1)
    severity: str = Field(default="medium", regex="^(low|medium|high|critical)$")
    channels: Optional[List[str]] = Field(default_factory=list)
    description: Optional[str] = None
    category: Optional[str] = None


class AlertActionRequest(BaseModel):
    """Alert action request model"""

    message: Optional[str] = None


class CorrelationResponse(BaseModel):
    """Correlation ID response model"""

    correlation_id: str


@router.get("/health", response_model=HealthResponse)
@require_roles(["admin", "monitoring", "user"])
async def get_health(
    manager: ObservabilityManager = Depends(get_observability_manager),
):
    """
    Get comprehensive health status of all monitoring services
    """
    try:
        health_status = await manager.health_check()
        return HealthResponse(
            status=health_status["manager"]["status"],
            manager=health_status["manager"],
            services=health_status["services"],
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics")
@require_roles(["admin", "monitoring"])
async def get_metrics(
    request: MetricsRequest,
    manager: ObservabilityManager = Depends(get_observability_manager),
):
    """
    Get metrics data with optional filters
    """
    try:
        return await manager.get_metrics(
            service=request.service,
            metric_name=request.metric_name,
            start_time=request.start_time,
            end_time=request.end_time,
            labels=request.labels,
        )
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prometheus", response_class=PlainTextResponse)
@require_roles(["admin", "monitoring"])
async def get_prometheus_metrics(
    manager: ObservabilityManager = Depends(get_observability_manager),
):
    """
    Get Prometheus metrics in text format
    """
    try:
        return await manager.metrics_collector.get_prometheus_metrics()
    except Exception as e:
        logger.error(f"Error getting Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/traces")
@require_roles(["admin", "monitoring"])
async def get_traces(
    request: TracesRequest,
    manager: ObservabilityManager = Depends(get_observability_manager),
):
    """
    Get trace data with optional filters
    """
    try:
        return await manager.get_traces(
            trace_id=request.trace_id,
            service=request.service,
            operation=request.operation,
            start_time=request.start_time,
            end_time=request.end_time,
            limit=request.limit,
        )
    except Exception as e:
        logger.error(f"Error getting traces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logs")
@require_roles(["admin", "monitoring"])
async def get_logs(
    request: LogsRequest,
    manager: ObservabilityManager = Depends(get_observability_manager),
):
    """
    Get log data with optional filters
    """
    try:
        return await manager.get_logs(
            level=request.level,
            service=request.service,
            start_time=request.start_time,
            end_time=request.end_time,
            search=request.search,
            limit=request.limit,
        )
    except Exception as e:
        logger.error(f"Error getting logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts")
@require_roles(["admin", "monitoring"])
async def get_alerts(
    request: AlertsRequest,
    manager: ObservabilityManager = Depends(get_observability_manager),
):
    """
    Get alert data with optional filters
    """
    try:
        return await manager.get_alerts(
            severity=request.severity,
            status=request.status,
            service=request.service,
            start_time=request.start_time,
            end_time=request.end_time,
            limit=request.limit,
        )
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alert-rules")
@require_roles(["admin", "monitoring"])
async def create_alert_rule(
    request: AlertRuleRequest,
    manager: ObservabilityManager = Depends(get_observability_manager),
):
    """
    Create a new alert rule
    """
    try:
        rule_id = await manager.create_alert_rule(
            name=request.name,
            conditions=request.conditions,
            severity=request.severity,
            channels=request.channels,
            description=request.description,
            category=request.category,
        )
        return {"rule_id": rule_id, "message": "Alert rule created successfully"}
    except Exception as e:
        logger.error(f"Error creating alert rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/acknowledge")
@require_roles(["admin", "monitoring"])
async def acknowledge_alert(
    alert_id: str,
    request: AlertActionRequest,
    manager: ObservabilityManager = Depends(get_observability_manager),
):
    """
    Acknowledge an alert
    """
    try:
        success = await manager.acknowledge_alert(
            alert_id=alert_id,
            user="current_user",  # In real implementation, get from auth context
            message=request.message,
        )
        if success:
            return {"message": "Alert acknowledged successfully"}
        else:
            raise HTTPException(status_code=404, detail="Alert not found")
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/resolve")
@require_roles(["admin", "monitoring"])
async def resolve_alert(
    alert_id: str,
    request: AlertActionRequest,
    manager: ObservabilityManager = Depends(get_observability_manager),
):
    """
    Resolve an alert
    """
    try:
        success = await manager.resolve_alert(
            alert_id=alert_id,
            user="current_user",  # In real implementation, get from auth context
            message=request.message,
        )
        if success:
            return {"message": "Alert resolved successfully"}
        else:
            raise HTTPException(status_code=404, detail="Alert not found")
    except Exception as e:
        logger.error(f"Error resolving alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/service-health")
@require_roles(["admin", "monitoring"])
async def get_service_health(
    manager: ObservabilityManager = Depends(get_observability_manager),
):
    """
    Get health status of all monitored services
    """
    try:
        return await manager.get_service_health()
    except Exception as e:
        logger.error(f"Error getting service health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/correlation-id", response_model=CorrelationResponse)
async def create_correlation_id(
    manager: ObservabilityManager = Depends(get_observability_manager),
):
    """
    Create a new correlation ID for request tracking
    """
    try:
        correlation_id = await manager.create_correlation_id()
        return CorrelationResponse(correlation_id=correlation_id)
    except Exception as e:
        logger.error(f"Error creating correlation ID: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
@require_roles(["admin"])
async def get_monitoring_config():
    """
    Get current monitoring configuration
    """
    try:
        config = get_monitoring_config()
        return config.dict()
    except Exception as e:
        logger.error(f"Error getting monitoring config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
@require_roles(["admin", "monitoring"])
async def get_dashboard_data(
    manager: ObservabilityManager = Depends(get_observability_manager),
):
    """
    Get dashboard data with overview metrics
    """
    try:
        # Get health status
        health = await manager.health_check()

        # Get recent metrics (last hour)
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)

        metrics_data = await manager.get_metrics(
            start_time=start_time, end_time=end_time
        )

        # Get recent alerts
        alerts_data = await manager.get_alerts(
            start_time=start_time, end_time=end_time, limit=10
        )

        # Get system health
        service_health = await manager.get_service_health()

        return {
            "health": health,
            "metrics_summary": {
                "total_metrics": len(metrics_data.get("metrics", {})),
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                },
            },
            "recent_alerts": alerts_data.get("alerts", {}),
            "service_health": service_health,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-metric")
@require_roles(["admin", "monitoring"])
async def create_test_metric(
    metric_name: str = Query(..., description="Metric name"),
    value: float = Query(..., description="Metric value"),
    manager: ObservabilityManager = Depends(get_observability_manager),
):
    """
    Create a test metric for monitoring system validation
    """
    try:
        await manager.record_metric(
            name=metric_name,
            value=value,
            labels={"test": "true", "source": "api"},
            source="test_api",
        )
        return {
            "message": f"Test metric {metric_name} with value {value} created successfully"
        }
    except Exception as e:
        logger.error(f"Error creating test metric: {e}")
        raise HTTPException(status_code=500, detail=str(e))
