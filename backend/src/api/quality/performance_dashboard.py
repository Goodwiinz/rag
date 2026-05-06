"""
Performance Metrics Dashboard API endpoints
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.user import User
from src.schemas.quality_metrics import (
    DashboardConfiguration,
    DashboardWidget,
    PerformanceMetrics,
)
from src.services.quality.performance_dashboard_service import (
    DashboardWidgetType,
    MetricTimeRange,
    performance_dashboard_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dashboard")
async def get_performance_dashboard(
    time_range: MetricTimeRange = Query(
        MetricTimeRange.LAST_24H, description="Time range for metrics"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get performance dashboard data"""
    try:
        dashboard = await performance_dashboard_service.get_dashboard_overview(
            organization_id=str(current_user.organization_id), time_range=time_range
        )

        # Transform data to match expected format from notebook
        return {
            "system_metrics": {
                "total_documents": dashboard.get("total_documents", 0),
                "total_searches": dashboard.get("total_searches", 0),
                "avg_response_time": dashboard.get("avg_response_time", 0),
                "uptime": dashboard.get("uptime", "99.9%"),
                "error_rate": dashboard.get("error_rate", 0),
                "active_users": dashboard.get("active_users", 0),
            },
            "performance_trends": dashboard.get("performance_trends", []),
            "alerts": dashboard.get("alerts", []),
            "timestamp": dashboard.get("timestamp", datetime.utcnow().isoformat()),
        }

    except Exception as e:
        logger.error(f"Failed to get performance dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview")
async def get_dashboard_overview(
    time_range: MetricTimeRange = Query(
        MetricTimeRange.LAST_24H, description="Time range for metrics"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get comprehensive dashboard overview"""
    try:
        overview = await performance_dashboard_service.get_dashboard_overview(
            organization_id=str(current_user.organization_id), time_range=time_range
        )

        return overview

    except Exception as e:
        logger.error(f"Failed to get dashboard overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system-health")
async def get_system_health_metrics(current_user: User = Depends(get_current_user)):
    """Get real-time system health metrics"""
    try:
        # Check permissions - system health metrics are admin-only
        from src.models.user import UserRole

        if current_user.role not in [UserRole.ADMIN]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        system_health = await performance_dashboard_service.get_system_health_metrics()

        return {
            "cpu_usage": system_health.cpu_usage,
            "memory_usage": system_health.memory_usage,
            "disk_usage": system_health.disk_usage,
            "network_io": system_health.network_io,
            "response_time_p50": system_health.response_time_p50,
            "response_time_p95": system_health.response_time_p95,
            "error_rate": system_health.error_rate,
            "active_connections": system_health.active_connections,
            "uptime": system_health.uptime,
            "timestamp": system_health.timestamp.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get system health metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search-performance")
async def get_search_performance_metrics(
    time_range: MetricTimeRange = Query(
        MetricTimeRange.LAST_24H, description="Time range for metrics"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get search performance metrics"""
    try:
        performance = (
            await performance_dashboard_service.get_search_performance_metrics(
                organization_id=str(current_user.organization_id), time_range=time_range
            )
        )

        return {
            "total_searches": performance.total_searches,
            "avg_response_time": performance.avg_response_time,
            "p95_response_time": performance.p95_response_time,
            "success_rate": performance.success_rate,
            "no_results_rate": performance.no_results_rate,
            "top_queries": performance.top_queries,
            "search_types": performance.search_types,
            "errors": performance.errors,
        }

    except Exception as e:
        logger.error(f"Failed to get search performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quality-metrics")
async def get_quality_metrics_summary(
    time_range: MetricTimeRange = Query(
        MetricTimeRange.LAST_24H, description="Time range for metrics"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get quality metrics summary"""
    try:
        quality_metrics = (
            await performance_dashboard_service.get_quality_metrics_summary(
                organization_id=str(current_user.organization_id), time_range=time_range
            )
        )

        return {
            "overall_score": quality_metrics.overall_score,
            "precision_avg": quality_metrics.precision_avg,
            "recall_avg": quality_metrics.recall_avg,
            "relevance_avg": quality_metrics.relevance_avg,
            "user_satisfaction": quality_metrics.user_satisfaction,
            "active_alerts": quality_metrics.active_alerts,
            "trends": quality_metrics.trends,
            "top_issues": quality_metrics.top_issues,
        }

    except Exception as e:
        logger.error(f"Failed to get quality metrics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user-engagement")
async def get_user_engagement_metrics(
    time_range: MetricTimeRange = Query(
        MetricTimeRange.LAST_24H, description="Time range for metrics"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get user engagement metrics"""
    try:
        # Check permissions - user engagement metrics are admin/manager only
        from src.models.user import UserRole

        if current_user.role not in [UserRole.ADMIN]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        engagement = await performance_dashboard_service.get_user_engagement_metrics(
            organization_id=str(current_user.organization_id), time_range=time_range
        )

        return {
            "active_users": engagement.active_users,
            "total_sessions": engagement.total_sessions,
            "avg_session_duration": engagement.avg_session_duration,
            "searches_per_user": engagement.searches_per_user,
            "top_users": engagement.top_users,
            "engagement_trend": engagement.engagement_trend,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user engagement metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_active_alerts(
    severity: Optional[str] = Query(None, regex="^(critical|high|medium|low|info)$"),
    limit: int = Query(50, ge=1, le=200, description="Maximum alerts to return"),
    current_user: User = Depends(get_current_user),
):
    """Get active alerts for the organization"""
    try:
        alerts = await performance_dashboard_service.get_active_alerts(
            organization_id=str(current_user.organization_id)
        )

        # Filter by severity if specified
        if severity:
            alerts = [alert for alert in alerts if alert["severity"] == severity]

        # Apply limit
        alerts = alerts[:limit]

        return {
            "alerts": alerts,
            "total_count": len(alerts),
            "severity_filter": severity,
        }

    except Exception as e:
        logger.error(f"Failed to get active alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/charts/{metric_name}")
async def get_metric_chart_data(
    metric_name: str,
    time_range: MetricTimeRange = Query(
        MetricTimeRange.LAST_24H, description="Time range for metrics"
    ),
    granularity: str = Query(
        "hour", regex="^(minute|hour|day|week|month)$", description="Data granularity"
    ),
    current_user: User = Depends(get_current_user),
):
    """Get time-series data for metric charts"""
    try:
        # Validate metric name
        valid_metrics = [
            "search_volume",
            "response_time",
            "quality_score",
            "cpu_usage",
            "memory_usage",
            "disk_usage",
            "error_rate",
            "throughput",
            "latency",
        ]

        if metric_name not in valid_metrics:
            raise HTTPException(
                status_code=400, detail=f"Invalid metric name: {metric_name}"
            )

        chart_data = await performance_dashboard_service.get_metric_chart_data(
            organization_id=str(current_user.organization_id),
            metric_name=metric_name,
            time_range=time_range,
            granularity=granularity,
        )

        return {
            "metric_name": metric_name,
            "time_range": time_range.value,
            "granularity": granularity,
            "data": chart_data,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get metric chart data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/widgets")
async def create_dashboard_widgets(
    widget_configs: List[Dict[str, Any]], current_user: User = Depends(get_current_user)
):
    """Create dashboard widgets with data"""
    try:
        # Validate widget configurations
        for config in widget_configs:
            required_fields = [
                "title",
                "widget_type",
                "metrics",
                "time_range",
                "position",
                "size",
            ]
            for field in required_fields:
                if field not in config:
                    raise HTTPException(
                        status_code=400, detail=f"Missing required field: {field}"
                    )

            # Validate widget type
            valid_types = [t.value for t in DashboardWidgetType]
            if config["widget_type"] not in valid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid widget type: {config['widget_type']}",
                )

            # Validate time range
            valid_ranges = [r.value for r in MetricTimeRange]
            if config["time_range"] not in valid_ranges:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid time range: {config['time_range']}",
                )

        widgets = await performance_dashboard_service.create_dashboard_widgets(
            organization_id=str(current_user.organization_id),
            widget_configs=widget_configs,
        )

        return {
            "widgets": [
                {
                    "id": widget.id,
                    "title": widget.title,
                    "widget_type": widget.widget_type.value,
                    "metrics": widget.metrics,
                    "time_range": widget.time_range.value,
                    "position": widget.position,
                    "size": widget.size,
                    "data": widget.data,
                    "refresh_interval": widget.refresh_interval,
                }
                for widget in widgets
            ],
            "total_count": len(widgets),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create dashboard widgets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/widgets/defaults")
async def get_default_widget_configurations(
    current_user: User = Depends(get_current_user),
):
    """Get default widget configurations for common dashboard layouts"""
    try:
        default_widgets = [
            {
                "id": "search_volume_card",
                "title": "Search Volume",
                "widget_type": "stat_card",
                "metrics": ["search_volume"],
                "time_range": "24h",
                "position": {"x": 0, "y": 0},
                "size": {"width": 3, "height": 2},
                "refresh_interval": 300,
            },
            {
                "id": "response_time_card",
                "title": "Avg Response Time",
                "widget_type": "stat_card",
                "metrics": ["response_time"],
                "time_range": "24h",
                "position": {"x": 3, "y": 0},
                "size": {"width": 3, "height": 2},
                "refresh_interval": 300,
            },
            {
                "id": "quality_score_card",
                "title": "Quality Score",
                "widget_type": "stat_card",
                "metrics": ["quality_score"],
                "time_range": "24h",
                "position": {"x": 6, "y": 0},
                "size": {"width": 3, "height": 2},
                "refresh_interval": 300,
            },
            {
                "id": "search_trend_chart",
                "title": "Search Trends",
                "widget_type": "line_chart",
                "metrics": ["search_volume"],
                "time_range": "7d",
                "position": {"x": 0, "y": 2},
                "size": {"width": 6, "height": 4},
                "refresh_interval": 600,
            },
            {
                "id": "response_time_chart",
                "title": "Response Time Trends",
                "widget_type": "line_chart",
                "metrics": ["response_time"],
                "time_range": "7d",
                "position": {"x": 6, "y": 2},
                "size": {"width": 6, "height": 4},
                "refresh_interval": 600,
            },
            {
                "id": "search_types_pie",
                "title": "Search Types Distribution",
                "widget_type": "pie_chart",
                "metrics": ["search_types"],
                "time_range": "24h",
                "position": {"x": 0, "y": 6},
                "size": {"width": 4, "height": 4},
                "refresh_interval": 900,
            },
            {
                "id": "top_queries_table",
                "title": "Top Queries",
                "widget_type": "table",
                "metrics": ["top_queries"],
                "time_range": "24h",
                "position": {"x": 4, "y": 6},
                "size": {"width": 8, "height": 4},
                "refresh_interval": 900,
            },
        ]

        return {
            "default_widgets": default_widgets,
            "available_metrics": [
                {"name": "search_volume", "label": "Search Volume", "type": "counter"},
                {"name": "response_time", "label": "Response Time", "type": "duration"},
                {
                    "name": "quality_score",
                    "label": "Quality Score",
                    "type": "percentage",
                },
                {"name": "cpu_usage", "label": "CPU Usage", "type": "percentage"},
                {"name": "memory_usage", "label": "Memory Usage", "type": "percentage"},
                {"name": "error_rate", "label": "Error Rate", "type": "percentage"},
                {"name": "throughput", "label": "Throughput", "type": "counter"},
                {"name": "latency", "label": "Latency", "type": "duration"},
            ],
            "available_widget_types": [
                {
                    "type": "stat_card",
                    "label": "Stat Card",
                    "description": "Single metric with trend",
                },
                {
                    "type": "line_chart",
                    "label": "Line Chart",
                    "description": "Time series visualization",
                },
                {
                    "type": "bar_chart",
                    "label": "Bar Chart",
                    "description": "Categorical comparison",
                },
                {
                    "type": "pie_chart",
                    "label": "Pie Chart",
                    "description": "Distribution breakdown",
                },
                {
                    "type": "table",
                    "label": "Table",
                    "description": "Tabular data display",
                },
            ],
        }

    except Exception as e:
        logger.error(f"Failed to get default widget configurations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/available")
async def get_available_metrics(current_user: User = Depends(get_current_user)):
    """Get list of available metrics for dashboard widgets"""
    try:
        metrics = {
            "search_metrics": [
                {
                    "name": "search_volume",
                    "label": "Search Volume",
                    "unit": "count",
                    "description": "Number of searches performed",
                },
                {
                    "name": "response_time",
                    "label": "Response Time",
                    "unit": "ms",
                    "description": "Average search response time",
                },
                {
                    "name": "quality_score",
                    "label": "Quality Score",
                    "unit": "score",
                    "description": "Overall search quality score",
                },
                {
                    "name": "precision",
                    "label": "Precision",
                    "unit": "percentage",
                    "description": "Search result precision",
                },
                {
                    "name": "recall",
                    "label": "Recall",
                    "unit": "percentage",
                    "description": "Search result recall",
                },
                {
                    "name": "relevance",
                    "label": "Relevance",
                    "unit": "score",
                    "description": "Result relevance score",
                },
                {
                    "name": "user_satisfaction",
                    "label": "User Satisfaction",
                    "unit": "score",
                    "description": "User satisfaction rating",
                },
                {
                    "name": "click_through_rate",
                    "label": "Click-through Rate",
                    "unit": "percentage",
                    "description": "Search result CTR",
                },
            ],
            "system_metrics": [
                {
                    "name": "cpu_usage",
                    "label": "CPU Usage",
                    "unit": "percentage",
                    "description": "System CPU utilization",
                },
                {
                    "name": "memory_usage",
                    "label": "Memory Usage",
                    "unit": "percentage",
                    "description": "System memory utilization",
                },
                {
                    "name": "disk_usage",
                    "label": "Disk Usage",
                    "unit": "percentage",
                    "description": "Disk space utilization",
                },
                {
                    "name": "network_io",
                    "label": "Network I/O",
                    "unit": "bytes",
                    "description": "Network traffic",
                },
                {
                    "name": "error_rate",
                    "label": "Error Rate",
                    "unit": "percentage",
                    "description": "System error rate",
                },
                {
                    "name": "active_connections",
                    "label": "Active Connections",
                    "unit": "count",
                    "description": "Number of active connections",
                },
                {
                    "name": "throughput",
                    "label": "Throughput",
                    "unit": "req/sec",
                    "description": "Requests per second",
                },
                {
                    "name": "latency",
                    "label": "Latency",
                    "unit": "ms",
                    "description": "Request latency",
                },
            ],
            "user_metrics": [
                {
                    "name": "active_users",
                    "label": "Active Users",
                    "unit": "count",
                    "description": "Number of active users",
                },
                {
                    "name": "user_sessions",
                    "label": "User Sessions",
                    "unit": "count",
                    "description": "Number of user sessions",
                },
                {
                    "name": "session_duration",
                    "label": "Session Duration",
                    "unit": "seconds",
                    "description": "Average session duration",
                },
                {
                    "name": "searches_per_user",
                    "label": "Searches per User",
                    "unit": "count",
                    "description": "Average searches per user",
                },
                {
                    "name": "user_retention",
                    "label": "User Retention",
                    "unit": "percentage",
                    "description": "User retention rate",
                },
            ],
        }

        return metrics

    except Exception as e:
        logger.error(f"Failed to get available metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
async def export_dashboard_data(
    format: str = Query("json", regex="^(json|csv|xlsx)$", description="Export format"),
    time_range: MetricTimeRange = Query(
        MetricTimeRange.LAST_24H, description="Time range for export"
    ),
    metrics: List[str] = Query([], description="Metrics to include in export"),
    current_user: User = Depends(get_current_user),
):
    """Export dashboard data in various formats"""
    try:
        # Get dashboard overview data
        overview = await performance_dashboard_service.get_dashboard_overview(
            organization_id=str(current_user.organization_id), time_range=time_range
        )

        # Filter metrics if specified
        if metrics:
            filtered_overview = {
                "timestamp": overview["timestamp"],
                "time_range": overview["time_range"],
            }

            for metric in metrics:
                if metric in overview:
                    filtered_overview[metric] = overview[metric]

            overview = filtered_overview

        # Export based on format
        if format == "json":
            return overview
        elif format == "csv":
            # Convert to CSV format (simplified)
            csv_data = _convert_to_csv(overview)
            return JSONResponse(
                content=csv_data,
                headers={
                    "Content-Disposition": f"attachment; filename=dashboard_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                },
            )
        elif format == "xlsx":
            # Would need openpyxl or similar for Excel export
            return JSONResponse(
                content={"error": "Excel export not implemented"}, status_code=501
            )

    except Exception as e:
        logger.error(f"Failed to export dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _convert_to_csv(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert dashboard data to CSV format"""
    # Simplified CSV conversion - in production, use proper CSV library
    csv_rows = []

    def flatten_dict(d, parent_key="", sep="_"):
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                items.append((new_key, len(v)))  # List length as metric
            else:
                items.append((new_key, v))
        return dict(items)

    flattened = flatten_dict(data)

    # Create CSV rows
    headers = ["metric", "value"]
    rows = [headers]

    for key, value in flattened.items():
        if isinstance(value, (int, float)):
            rows.append([key, str(value)])

    return {
        "filename": f"dashboard_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
        "headers": headers,
        "rows": rows[1:],  # Exclude header row
        "total_rows": len(rows) - 1,
    }


@router.get("/health")
async def performance_dashboard_health():
    """Health check for performance dashboard service"""
    return {
        "status": "healthy",
        "service": "performance_dashboard",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }
