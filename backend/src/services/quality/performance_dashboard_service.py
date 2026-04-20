"""
Performance metrics dashboard service for system monitoring and visualization
"""

import asyncio
import logging
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import text

# Try to import psutil, use fallback if not available
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available, using fallback system monitoring")

from src.cache.analytics_cache import CacheTTL, get_analytics_cache
from src.core.database import get_async_session

logger = logging.getLogger(__name__)


class MetricTimeRange(Enum):
    """Time ranges for dashboard metrics"""

    LAST_HOUR = "1h"
    LAST_24H = "24h"
    LAST_7D = "7d"
    LAST_30D = "30d"
    LAST_90D = "90d"


class DashboardWidgetType(Enum):
    """Types of dashboard widgets"""

    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    GAUGE = "gauge"
    TABLE = "table"
    STAT_CARD = "stat_card"
    HEATMAP = "heatmap"


class AlertLevel(Enum):
    """Alert severity levels for dashboard"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class DashboardMetric:
    """Dashboard metric data point"""

    name: str
    value: float
    unit: str
    timestamp: datetime
    trend: Optional[float] = None  # Percentage change
    status: str = "normal"  # normal, warning, critical
    threshold: Optional[float] = None


@dataclass
class SystemHealthMetrics:
    """System health metrics"""

    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, float]
    response_time_p50: float
    response_time_p95: float
    error_rate: float
    active_connections: int
    uptime: float
    timestamp: datetime


@dataclass
class SearchPerformanceMetrics:
    """Search performance metrics"""

    total_searches: int
    avg_response_time: float
    p95_response_time: float
    success_rate: float
    no_results_rate: float
    top_queries: List[Dict[str, Any]]
    search_types: Dict[str, int]
    errors: List[Dict[str, Any]]


@dataclass
class QualityMetricsSummary:
    """Quality metrics summary"""

    overall_score: float
    precision_avg: float
    recall_avg: float
    relevance_avg: float
    user_satisfaction: float
    active_alerts: int
    trends: Dict[str, float]
    top_issues: List[Dict[str, Any]]


@dataclass
class UserEngagementMetrics:
    """User engagement metrics"""

    active_users: int
    total_sessions: int
    avg_session_duration: float
    searches_per_user: float
    top_users: List[Dict[str, Any]]
    engagement_trend: str  # increasing, decreasing, stable


@dataclass
class DashboardWidget:
    """Dashboard widget configuration"""

    id: str
    title: str
    widget_type: DashboardWidgetType
    metrics: List[str]
    time_range: MetricTimeRange
    position: Dict[str, int]
    size: Dict[str, int]
    data: Optional[Dict[str, Any]] = None
    refresh_interval: int = 300  # seconds


class PerformanceDashboardService:
    """
    Service for generating performance metrics dashboard data
    """

    def __init__(self):
        self.system_monitor = SystemMonitor()

    async def get_dashboard_overview(
        self,
        organization_id: str,
        time_range: MetricTimeRange = MetricTimeRange.LAST_24H,
    ) -> Dict[str, Any]:
        """Get comprehensive dashboard overview"""

        cache = get_analytics_cache()
        cache_key = f"perf_dashboard:overview:{organization_id}:{time_range.value}"

        # Try Redis/in-memory cache first
        try:
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass  # cache miss or error — proceed to compute

        try:
            # Fetch all dashboard components in parallel
            (
                system_health,
                search_performance,
                quality_metrics,
                user_engagement,
                alerts,
            ) = await asyncio.gather(
                self.get_system_health_metrics(),
                self.get_search_performance_metrics(organization_id, time_range),
                self.get_quality_metrics_summary(organization_id, time_range),
                self.get_user_engagement_metrics(organization_id, time_range),
                self.get_active_alerts(organization_id),
            )

            overview = {
                "timestamp": datetime.utcnow().isoformat(),
                "time_range": time_range.value,
                "system_health": asdict(system_health),
                "search_performance": asdict(search_performance),
                "quality_metrics": asdict(quality_metrics),
                "user_engagement": asdict(user_engagement),
                "alerts": alerts,
            }

            # Cache in Redis (3 min TTL) with in-memory fallback
            try:
                await cache.set(cache_key, overview, ttl=CacheTTL.DASHBOARD_DATA)
            except Exception:
                pass  # non-fatal — cache write failure shouldn't break the endpoint

            return overview

        except Exception as e:
            logger.error(f"Failed to get dashboard overview: {e}")
            raise

    async def get_system_health_metrics(self) -> SystemHealthMetrics:
        """Get real-time system health metrics"""
        try:
            if PSUTIL_AVAILABLE:
                # Non-blocking CPU check (returns since-last-call average)
                cpu_percent = psutil.cpu_percent(interval=None)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage("/")
                network = psutil.net_io_counters()

                memory_percent = memory.percent
                disk_percent = disk.percent

                # Get uptime
                boot_time = psutil.boot_time()
                uptime = time.time() - boot_time

                network_io = {
                    "bytes_sent": float(network.bytes_sent),
                    "bytes_recv": float(network.bytes_recv),
                    "packets_sent": float(network.packets_sent),
                    "packets_recv": float(network.packets_recv),
                }
            else:
                # Fallback metrics when psutil is not available
                cpu_percent = 0.0
                memory_percent = 0.0
                disk_percent = 0.0
                uptime = 0.0
                network_io = {
                    "bytes_sent": 0.0,
                    "bytes_recv": 0.0,
                    "packets_sent": 0.0,
                    "packets_recv": 0.0,
                }

            # Get response time metrics, error rate, and active connections in parallel
            response_times, error_rate, active_connections = await asyncio.gather(
                self._get_response_time_metrics(),
                self._get_error_rate(),
                self._get_active_connections(),
            )

            return SystemHealthMetrics(
                cpu_usage=cpu_percent,
                memory_usage=memory_percent,
                disk_usage=disk_percent,
                network_io=network_io,
                response_time_p50=response_times["p50"],
                response_time_p95=response_times["p95"],
                error_rate=error_rate,
                active_connections=active_connections,
                uptime=uptime,
                timestamp=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Failed to get system health metrics: {e}")
            # Return default values if system monitoring fails
            return SystemHealthMetrics(
                cpu_usage=0.0,
                memory_usage=0.0,
                disk_usage=0.0,
                network_io={
                    "bytes_sent": 0.0,
                    "bytes_recv": 0.0,
                    "packets_sent": 0.0,
                    "packets_recv": 0.0,
                },
                response_time_p50=0.0,
                response_time_p95=0.0,
                error_rate=0.0,
                active_connections=0,
                uptime=0.0,
                timestamp=datetime.utcnow(),
            )

    async def get_search_performance_metrics(
        self, organization_id: str, time_range: MetricTimeRange
    ) -> SearchPerformanceMetrics:
        """Get search performance metrics"""

        async with get_async_session() as db:
            try:
                # Calculate time range
                cutoff_date = self._get_cutoff_date(time_range)

                # Get search performance data
                search_result = await db.execute(
                    text(
                        """
                    SELECT
                        COUNT(*) as total_searches,
                        AVG(search_duration_ms) as avg_response_time,
                        COUNT(CASE WHEN total_results = 0 THEN 1 END) as no_results_count,
                        0 as error_count
                    FROM search_queries
                    WHERE organization_id = CAST(:org_id AS UUID)
                        AND created_at >= :cutoff_date
                """
                    ),
                    {"org_id": organization_id, "cutoff_date": cutoff_date},
                )
                search_data = search_result.fetchone()

                # Get response time percentiles using percentile_cont
                p95_result = await db.execute(
                    text(
                        """
                    SELECT
                        percentile_cont(0.95) WITHIN GROUP (ORDER BY search_duration_ms) as p95
                    FROM search_queries
                    WHERE organization_id = CAST(:org_id AS UUID)
                        AND created_at >= :cutoff_date
                        AND search_duration_ms IS NOT NULL
                """
                    ),
                    {"org_id": organization_id, "cutoff_date": cutoff_date},
                )
                p95_row = p95_result.fetchone()
                response_times = p95_row.p95 if p95_row else None

                # Get top queries
                top_result = await db.execute(
                    text(
                        """
                    SELECT
                        query_text as query,
                        COUNT(*) as search_count,
                        AVG(search_duration_ms) as avg_response_time
                    FROM search_queries
                    WHERE organization_id = CAST(:org_id AS UUID)
                        AND created_at >= :cutoff_date
                    GROUP BY query_text
                    ORDER BY search_count DESC
                    LIMIT 10
                """
                    ),
                    {"org_id": organization_id, "cutoff_date": cutoff_date},
                )
                top_queries = top_result.fetchall()

                # Get search types distribution
                types_result = await db.execute(
                    text(
                        """
                    SELECT
                        search_type,
                        COUNT(*) as count
                    FROM search_queries
                    WHERE organization_id = CAST(:org_id AS UUID)
                        AND created_at >= :cutoff_date
                    GROUP BY search_type
                    ORDER BY count DESC
                """
                    ),
                    {"org_id": organization_id, "cutoff_date": cutoff_date},
                )
                search_types = types_result.fetchall()

                # Calculate metrics
                total_searches = search_data.total_searches or 0
                avg_response_time = float(search_data.avg_response_time or 0)
                p95_response_time = float(response_times or 0)
                no_results_rate = (
                    (search_data.no_results_count / total_searches)
                    if total_searches > 0
                    else 0
                )
                success_rate = (
                    1.0 - (search_data.error_count / total_searches)
                    if total_searches > 0
                    else 1.0
                )

                return SearchPerformanceMetrics(
                    total_searches=total_searches,
                    avg_response_time=avg_response_time,
                    p95_response_time=p95_response_time,
                    success_rate=success_rate,
                    no_results_rate=no_results_rate,
                    top_queries=[
                        {
                            "query": q.query,
                            "count": q.search_count,
                            "avg_response_time": float(q.avg_response_time or 0),
                        }
                        for q in top_queries
                    ],
                    search_types={st.search_type: st.count for st in search_types},
                    errors=[],
                )

            except Exception as e:
                logger.error(f"Failed to get search performance metrics: {e}")
                raise

    async def get_quality_metrics_summary(
        self, organization_id: str, time_range: MetricTimeRange
    ) -> QualityMetricsSummary:
        """Get quality metrics summary"""

        async with get_async_session() as db:
            try:
                cutoff_date = self._get_cutoff_date(time_range)

                # Get quality metrics
                quality_result = await db.execute(
                    text(
                        """
                    SELECT
                        AVG(qm.value) as avg_score,
                        qm.metric_type,
                        COUNT(*) as count
                    FROM quality_metrics qm
                    WHERE qm.organization_id = CAST(:org_id AS UUID)
                        AND qm.created_at >= :cutoff_date
                    GROUP BY qm.metric_type
                """
                    ),
                    {"org_id": organization_id, "cutoff_date": cutoff_date},
                )
                quality_data = quality_result.fetchall()

                # Calculate averages by metric type
                precision_avg = 0.0
                recall_avg = 0.0
                relevance_avg = 0.0
                user_satisfaction = 0.0

                for metric in quality_data:
                    if metric.metric_type == "precision":
                        precision_avg = float(metric.avg_score or 0)
                    elif metric.metric_type == "recall":
                        recall_avg = float(metric.avg_score or 0)
                    elif metric.metric_type == "relevance":
                        relevance_avg = float(metric.avg_score or 0)
                    elif metric.metric_type == "user_satisfaction":
                        user_satisfaction = float(metric.avg_score or 0)

                # Calculate overall score (weighted average)
                overall_score = (
                    precision_avg * 0.3
                    + recall_avg * 0.3
                    + relevance_avg * 0.2
                    + user_satisfaction * 0.2
                )

                # Get active alerts
                alerts_result = await db.execute(
                    text(
                        """
                    SELECT COUNT(*) as count
                    FROM quality_alerts qa
                    WHERE qa.organization_id = CAST(:org_id AS UUID)
                        AND qa.status = 'active'
                """
                    ),
                    {"org_id": organization_id},
                )
                active_alerts = alerts_result.scalar() or 0

                # Get trends (compare to previous period)
                previous_cutoff = cutoff_date - timedelta(
                    days=self._get_days_for_range(time_range)
                )
                trends = await self._calculate_quality_trends(
                    db, organization_id, cutoff_date, previous_cutoff
                )

                return QualityMetricsSummary(
                    overall_score=overall_score,
                    precision_avg=precision_avg,
                    recall_avg=recall_avg,
                    relevance_avg=relevance_avg,
                    user_satisfaction=user_satisfaction,
                    active_alerts=active_alerts,
                    trends=trends,
                    top_issues=[],
                )

            except Exception as e:
                logger.error(f"Failed to get quality metrics summary: {e}")
                raise

    async def get_user_engagement_metrics(
        self, organization_id: str, time_range: MetricTimeRange
    ) -> UserEngagementMetrics:
        """Get user engagement metrics"""

        async with get_async_session() as db:
            try:
                cutoff_date = self._get_cutoff_date(time_range)

                # Get user engagement data
                engagement_result = await db.execute(
                    text(
                        """
                    SELECT
                        COUNT(DISTINCT sq.user_id) as active_users,
                        COUNT(DISTINCT sq.session_id) as total_sessions,
                        0 as avg_duration,
                        COUNT(sq.id) as total_searches
                    FROM search_queries sq
                    WHERE sq.organization_id = CAST(:org_id AS UUID)
                        AND sq.created_at >= :cutoff_date
                """
                    ),
                    {"org_id": organization_id, "cutoff_date": cutoff_date},
                )
                engagement_data = engagement_result.fetchone()

                # Get top users
                top_result = await db.execute(
                    text(
                        """
                    SELECT
                        u.id,
                        u.first_name,
                        u.last_name,
                        COUNT(DISTINCT sq.session_id) as session_count,
                        COUNT(sq.id) as search_count,
                        AVG(sq.search_duration_ms) as avg_response_time
                    FROM users u
                    LEFT JOIN search_queries sq ON u.id = sq.user_id
                    WHERE u.organization_id = CAST(:org_id AS UUID)
                        AND sq.created_at >= :cutoff_date
                    GROUP BY u.id, u.first_name, u.last_name
                    ORDER BY search_count DESC
                    LIMIT 10
                """
                    ),
                    {"org_id": organization_id, "cutoff_date": cutoff_date},
                )
                top_users = top_result.fetchall()

                # Calculate metrics
                active_users = engagement_data.active_users or 0
                total_sessions = engagement_data.total_sessions or 0
                avg_session_duration = float(engagement_data.avg_duration or 0)
                total_searches = engagement_data.total_searches or 0
                searches_per_user = (
                    total_searches / active_users if active_users > 0 else 0
                )

                # Determine engagement trend (reuse the same session)
                engagement_trend = await self._calculate_engagement_trend(
                    db, organization_id, cutoff_date, time_range
                )

                return UserEngagementMetrics(
                    active_users=active_users,
                    total_sessions=total_sessions,
                    avg_session_duration=avg_session_duration,
                    searches_per_user=searches_per_user,
                    top_users=[
                        {
                            "user_id": str(u.id),
                            "name": f"{u.first_name} {u.last_name}",
                            "session_count": u.session_count,
                            "search_count": u.search_count,
                            "avg_response_time": float(u.avg_response_time or 0),
                        }
                        for u in top_users
                    ],
                    engagement_trend=engagement_trend,
                )

            except Exception as e:
                logger.error(f"Failed to get user engagement metrics: {e}")
                raise

    async def get_active_alerts(self, organization_id: str) -> List[Dict[str, Any]]:
        """Get active alerts for the organization"""

        async with get_async_session() as db:
            try:
                result = await db.execute(
                    text(
                        """
                    SELECT
                        qa.id,
                        qa.severity,
                        qa.title,
                        qa.message,
                        qa.created_at,
                        qa.metric_id,
                        qm.metric_type,
                        qm.value as current_value
                    FROM quality_alerts qa
                    LEFT JOIN quality_metrics qm ON qa.metric_id = qm.id
                    WHERE qa.organization_id = CAST(:org_id AS UUID)
                        AND qa.status = 'active'
                    ORDER BY qa.severity DESC, qa.created_at DESC
                    LIMIT 50
                """
                    ),
                    {"org_id": organization_id},
                )
                alerts = result.fetchall()

                return [
                    {
                        "id": str(alert.id),
                        "severity": alert.severity,
                        "title": alert.title,
                        "message": alert.message,
                        "created_at": alert.created_at.isoformat(),
                        "metric_type": alert.metric_type,
                        "current_value": float(alert.current_value or 0),
                    }
                    for alert in alerts
                ]

            except Exception as e:
                logger.error(f"Failed to get active alerts: {e}")
                return []

    async def get_metric_chart_data(
        self,
        organization_id: str,
        metric_name: str,
        time_range: MetricTimeRange,
        granularity: str = "hour",
    ) -> List[Dict[str, Any]]:
        """Get time-series data for metric charts"""

        async with get_async_session() as db:
            try:
                cutoff_date = self._get_cutoff_date(time_range)

                # Determine granularity based on time range
                if time_range in [MetricTimeRange.LAST_HOUR, MetricTimeRange.LAST_24H]:
                    granularity = "hour"
                elif time_range == MetricTimeRange.LAST_7D:
                    granularity = "day"
                else:
                    granularity = "week"

                # Get aggregated metric data
                if metric_name == "search_volume":
                    result = await db.execute(
                        text(  # nosec: B608 - granularity constrained to enum-derived literal values
                            f"""
                        SELECT
                            DATE_TRUNC('{granularity}', created_at) as period,
                            COUNT(id) as value
                        FROM search_queries
                        WHERE organization_id = CAST(:org_id AS UUID)
                            AND created_at >= :cutoff_date
                        GROUP BY period
                        ORDER BY period
                    """
                        ),
                        {"org_id": organization_id, "cutoff_date": cutoff_date},
                    )
                elif metric_name == "response_time":
                    result = await db.execute(
                        text(  # nosec: B608 - granularity constrained to enum-derived literal values
                            f"""
                        SELECT
                            DATE_TRUNC('{granularity}', created_at) as period,
                            AVG(search_duration_ms) as value
                        FROM search_queries
                        WHERE organization_id = CAST(:org_id AS UUID)
                            AND created_at >= :cutoff_date
                            AND search_duration_ms IS NOT NULL
                        GROUP BY period
                        ORDER BY period
                    """
                        ),
                        {"org_id": organization_id, "cutoff_date": cutoff_date},
                    )
                elif metric_name == "quality_score":
                    result = await db.execute(
                        text(  # nosec: B608 - granularity constrained to enum-derived literal values
                            f"""
                        SELECT
                            DATE_TRUNC('{granularity}', qm.created_at) as period,
                            AVG(qm.value) as value
                        FROM quality_metrics qm
                        WHERE qm.organization_id = CAST(:org_id AS UUID)
                            AND qm.created_at >= :cutoff_date
                            AND qm.metric_type = 'relevance'
                        GROUP BY period
                        ORDER BY period
                    """
                        ),
                        {"org_id": organization_id, "cutoff_date": cutoff_date},
                    )
                else:
                    # Default to system metrics
                    result = await db.execute(
                        text(  # nosec: B608 - granularity constrained to enum-derived literal values
                            f"""
                        SELECT
                            DATE_TRUNC('{granularity}', sm.created_at) as period,
                            AVG(sm.metric_value) as value
                        FROM system_metrics sm
                        WHERE sm.organization_id = CAST(:org_id AS UUID)
                            AND sm.created_at >= :cutoff_date
                            AND sm.metric_name = :metric_name
                        GROUP BY period
                        ORDER BY period
                    """
                        ),
                        {
                            "org_id": organization_id,
                            "cutoff_date": cutoff_date,
                            "metric_name": metric_name,
                        },
                    )

                data = result.fetchall()

                return [
                    {
                        "timestamp": row.period.isoformat(),
                        "value": float(row.value or 0),
                    }
                    for row in data
                ]

            except Exception as e:
                logger.error(f"Failed to get metric chart data: {e}")
                return []

    async def create_dashboard_widgets(
        self, organization_id: str, widget_configs: List[Dict[str, Any]]
    ) -> List[DashboardWidget]:
        """Create dashboard widgets with data"""

        widgets = []

        for config in widget_configs:
            try:
                # Get widget data based on type and metrics
                widget_data = await self._get_widget_data(organization_id, config)

                widget = DashboardWidget(
                    id=config.get("id", str(uuid.uuid4())),
                    title=config["title"],
                    widget_type=DashboardWidgetType(config["widget_type"]),
                    metrics=config["metrics"],
                    time_range=MetricTimeRange(config["time_range"]),
                    position=config["position"],
                    size=config["size"],
                    data=widget_data,
                    refresh_interval=config.get("refresh_interval", 300),
                )

                widgets.append(widget)

            except Exception as e:
                logger.error(
                    f"Failed to create widget {config.get('title', 'unknown')}: {e}"
                )
                continue

        return widgets

    async def _get_widget_data(
        self, organization_id: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get data for a specific widget"""

        widget_type = config["widget_type"]
        metrics = config["metrics"]
        time_range = MetricTimeRange(config["time_range"])

        if widget_type == "stat_card":
            # Single metric value with trend
            metric_name = metrics[0]
            chart_data = await self.get_metric_chart_data(
                organization_id, metric_name, time_range
            )

            if chart_data:
                current_value = chart_data[-1]["value"]
                previous_value = (
                    chart_data[-2]["value"] if len(chart_data) > 1 else current_value
                )
                trend = (
                    ((current_value - previous_value) / previous_value * 100)
                    if previous_value != 0
                    else 0
                )
            else:
                current_value = 0
                trend = 0

            return {
                "current_value": current_value,
                "trend": trend,
                "data_points": chart_data,
            }

        elif widget_type in ["line_chart", "bar_chart"]:
            # Time series data
            all_data = {}
            for metric in metrics:
                chart_data = await self.get_metric_chart_data(
                    organization_id, metric, time_range
                )
                all_data[metric] = chart_data

            return {"series": all_data}

        elif widget_type == "pie_chart":
            # Distribution data
            if metrics[0] == "search_types":
                async with get_async_session() as db:
                    cutoff_date = self._get_cutoff_date(time_range)
                    result = await db.execute(
                        text(
                            """
                        SELECT
                            search_type,
                            COUNT(*) as count
                        FROM search_queries
                        WHERE organization_id = CAST(:org_id AS UUID)
                            AND created_at >= :cutoff_date
                        GROUP BY search_type
                        ORDER BY count DESC
                    """
                        ),
                        {"org_id": organization_id, "cutoff_date": cutoff_date},
                    )
                    data = result.fetchall()

                    return {
                        "labels": [row.search_type for row in data],
                        "values": [row.count for row in data],
                    }

        elif widget_type == "table":
            # Tabular data
            if metrics[0] == "top_queries":
                search_performance = await self.get_search_performance_metrics(
                    organization_id, time_range
                )
                return {"rows": search_performance.top_queries}

        return {"data": []}

    def _get_cutoff_date(self, time_range: MetricTimeRange) -> datetime:
        """Get cutoff date for time range"""

        now = datetime.utcnow()

        if time_range == MetricTimeRange.LAST_HOUR:
            return now - timedelta(hours=1)
        elif time_range == MetricTimeRange.LAST_24H:
            return now - timedelta(days=1)
        elif time_range == MetricTimeRange.LAST_7D:
            return now - timedelta(days=7)
        elif time_range == MetricTimeRange.LAST_30D:
            return now - timedelta(days=30)
        else:  # LAST_90D
            return now - timedelta(days=90)

    def _get_days_for_range(self, time_range: MetricTimeRange) -> int:
        """Get number of days for time range"""

        mapping = {
            MetricTimeRange.LAST_HOUR: 0,
            MetricTimeRange.LAST_24H: 1,
            MetricTimeRange.LAST_7D: 7,
            MetricTimeRange.LAST_30D: 30,
            MetricTimeRange.LAST_90D: 90,
        }
        return mapping[time_range]

    async def _get_response_time_metrics(self) -> Dict[str, float]:
        """Get response time metrics from recent searches"""

        async with get_async_session() as db:
            try:
                result = await db.execute(
                    text(
                        """
                    SELECT
                        percentile_cont(0.5) WITHIN GROUP (ORDER BY search_duration_ms) as p50,
                        percentile_cont(0.95) WITHIN GROUP (ORDER BY search_duration_ms) as p95
                    FROM search_queries
                    WHERE created_at >= NOW() - INTERVAL '1 hour'
                        AND search_duration_ms IS NOT NULL
                """
                    )
                )
                row = result.fetchone()

                if not row or row.p50 is None:
                    return {"p50": 0.0, "p95": 0.0}

                return {
                    "p50": float(row.p50),
                    "p95": float(row.p95),
                }

            except Exception as e:
                logger.error(f"Failed to get response time metrics: {e}")
                return {"p50": 0.0, "p95": 0.0}

    async def _get_error_rate(self) -> float:
        """Get current error rate - currently returns 0 as error tracking is not implemented"""

        async with get_async_session() as db:
            try:
                result = await db.execute(
                    text(
                        """
                    SELECT
                        0 as errors,
                        COUNT(*) as total
                    FROM search_queries
                    WHERE created_at >= NOW() - INTERVAL '1 hour'
                """
                    )
                )
                row = result.fetchone()

                if row.total == 0:
                    return 0.0

                return (row.errors / row.total) * 100

            except Exception as e:
                logger.error(f"Failed to get error rate: {e}")
                return 0.0

    async def _get_active_connections(self) -> int:
        """Get estimated active connections"""

        async with get_async_session() as db:
            try:
                result = await db.execute(
                    text(
                        """
                    SELECT COUNT(DISTINCT session_id) as active_sessions
                    FROM search_sessions
                    WHERE start_time >= NOW() - INTERVAL '30 minutes'
                        AND end_time IS NULL
                """
                    )
                )
                row = result.fetchone()

                return row.active_sessions or 0

            except Exception as e:
                logger.error(f"Failed to get active connections: {e}")
                return 0

    async def _calculate_quality_trends(
        self, db, organization_id: str, current_cutoff: datetime, previous_cutoff: datetime
    ) -> Dict[str, float]:
        """Calculate quality metric trends. Accepts an existing async session."""

        try:
            # Current period metrics
            current_result = await db.execute(
                text(
                    """
                SELECT
                    metric_type,
                    AVG(value) as avg_value
                FROM quality_metrics
                WHERE organization_id = CAST(:org_id AS UUID)
                    AND measured_at >= :cutoff_date
                GROUP BY metric_type
            """
                ),
                {"org_id": organization_id, "cutoff_date": current_cutoff},
            )
            current_metrics = current_result.fetchall()

            # Previous period metrics
            previous_result = await db.execute(
                text(
                    """
                SELECT
                    metric_type,
                    AVG(value) as avg_value
                FROM quality_metrics
                WHERE organization_id = CAST(:org_id AS UUID)
                    AND measured_at >= :prev_cutoff
                    AND measured_at < :current_cutoff
                GROUP BY metric_type
            """
                ),
                {
                    "org_id": organization_id,
                    "prev_cutoff": previous_cutoff,
                    "current_cutoff": current_cutoff,
                },
            )
            previous_metrics = previous_result.fetchall()

            # Calculate trends
            current_by_type = {
                m.metric_type: float(m.avg_value or 0) for m in current_metrics
            }
            previous_by_type = {
                m.metric_type: float(m.avg_value or 0) for m in previous_metrics
            }

            trends = {}
            for metric_type, current_value in current_by_type.items():
                previous_value = previous_by_type.get(metric_type, current_value)
                if previous_value != 0:
                    trend = ((current_value - previous_value) / previous_value) * 100
                else:
                    trend = 0.0
                trends[metric_type] = trend

            return trends

        except Exception as e:
            logger.error(f"Failed to calculate quality trends: {e}")
            return {}

    async def _calculate_engagement_trend(
        self, db, organization_id: str, cutoff_date: datetime, time_range: MetricTimeRange
    ) -> str:
        """Calculate engagement trend. Accepts an existing async session."""

        try:
            # Current period
            current_result = await db.execute(
                text(
                    """
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM search_queries
                WHERE organization_id = CAST(:org_id AS UUID)
                    AND created_at >= :cutoff_date
            """
                ),
                {"org_id": organization_id, "cutoff_date": cutoff_date},
            )
            current_data = current_result.fetchone()

            # Previous period (same duration)
            days = self._get_days_for_range(time_range)
            prev_cutoff = cutoff_date - timedelta(days=days)

            previous_result = await db.execute(
                text(
                    """
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM search_queries
                WHERE organization_id = CAST(:org_id AS UUID)
                    AND created_at >= :prev_cutoff
                    AND created_at < :cutoff_date
            """
                ),
                {
                    "org_id": organization_id,
                    "prev_cutoff": prev_cutoff,
                    "cutoff_date": cutoff_date,
                },
            )
            previous_data = previous_result.fetchone()

            current_users = current_data.active_users or 0
            previous_users = previous_data.active_users or 0

            if current_users > previous_users * 1.1:
                return "increasing"
            elif current_users < previous_users * 0.9:
                return "decreasing"
            else:
                return "stable"

        except Exception as e:
            logger.error(f"Failed to calculate engagement trend: {e}")
            return "stable"


class SystemMonitor:
    """System monitoring utilities"""

    def __init__(self):
        self.last_network_stats = None

    def get_network_speed(self) -> Dict[str, float]:
        """Get network speed in bytes per second"""
        if not PSUTIL_AVAILABLE:
            return {"bytes_sent_per_sec": 0, "bytes_recv_per_sec": 0}

        current_stats = psutil.net_io_counters()

        if self.last_network_stats:
            time_delta = time.time() - self.last_network_stats["timestamp"]
            if time_delta > 0:
                bytes_sent_per_sec = (
                    current_stats.bytes_sent - self.last_network_stats["bytes_sent"]
                ) / time_delta
                bytes_recv_per_sec = (
                    current_stats.bytes_recv - self.last_network_stats["bytes_recv"]
                ) / time_delta

                self.last_network_stats = {
                    "bytes_sent": current_stats.bytes_sent,
                    "bytes_recv": current_stats.bytes_recv,
                    "timestamp": time.time(),
                }

                return {
                    "bytes_sent_per_sec": bytes_sent_per_sec,
                    "bytes_recv_per_sec": bytes_recv_per_sec,
                }

        self.last_network_stats = {
            "bytes_sent": current_stats.bytes_sent,
            "bytes_recv": current_stats.bytes_recv,
            "timestamp": time.time(),
        }

        return {"bytes_sent_per_sec": 0, "bytes_recv_per_sec": 0}


# Global service instance
performance_dashboard_service = PerformanceDashboardService()
