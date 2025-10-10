"""
Performance metrics dashboard service for system monitoring and visualization
"""

import asyncio
import logging
import statistics
import time
from datetime import datetime, timedelta

# Try to import psutil, use fallback if not available
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning("psutil not available, using fallback system monitoring")
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
import json

from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_, func, desc, asc

from src.core.database import get_db
from src.models.quality_metrics import MetricAggregation, SystemMetric, QualityAlert
from src.models.quality import QualityMetric
from src.models.processing import ProcessingJob
from src.models.search import SearchQuery
from src.core.config import settings

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
        self.metric_cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.system_monitor = SystemMonitor()

    async def get_dashboard_overview(
        self,
        organization_id: str,
        time_range: MetricTimeRange = MetricTimeRange.LAST_24H
    ) -> Dict[str, Any]:
        """Get comprehensive dashboard overview"""

        cache_key = f"overview_{organization_id}_{time_range.value}"
        if cache_key in self.metric_cache:
            cached_data = self.metric_cache[cache_key]
            if time.time() - cached_data["timestamp"] < self.cache_ttl:
                return cached_data["data"]

        try:
            # Get all dashboard components
            system_health = await self.get_system_health_metrics()
            search_performance = await self.get_search_performance_metrics(
                organization_id, time_range
            )
            quality_metrics = await self.get_quality_metrics_summary(
                organization_id, time_range
            )
            user_engagement = await self.get_user_engagement_metrics(
                organization_id, time_range
            )

            overview = {
                "timestamp": datetime.utcnow().isoformat(),
                "time_range": time_range.value,
                "system_health": asdict(system_health),
                "search_performance": asdict(search_performance),
                "quality_metrics": asdict(quality_metrics),
                "user_engagement": asdict(user_engagement),
                "alerts": await self.get_active_alerts(organization_id)
            }

            # Cache the result
            self.metric_cache[cache_key] = {
                "data": overview,
                "timestamp": time.time()
            }

            return overview

        except Exception as e:
            logger.error(f"Failed to get dashboard overview: {e}")
            raise

    async def get_system_health_metrics(self) -> SystemHealthMetrics:
        """Get real-time system health metrics"""
        try:
            if PSUTIL_AVAILABLE:
                # Get system metrics from psutil
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                network = psutil.net_io_counters()

                # Get uptime
                boot_time = psutil.boot_time()
                uptime = time.time() - boot_time

                network_io = {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                }
            else:
                # Fallback metrics when psutil is not available
                cpu_percent = 0.0
                memory_percent = 0.0
                disk_percent = 0.0
                uptime = 0.0
                network_io = {
                    "bytes_sent": 0,
                    "bytes_recv": 0,
                    "packets_sent": 0,
                    "packets_recv": 0
                }

            # Get response time metrics from database
            response_times = await self._get_response_time_metrics()

            # Get error rate
            error_rate = await self._get_error_rate()

            # Get active connections (estimate)
            active_connections = await self._get_active_connections()

            return SystemHealthMetrics(
                cpu_usage=cpu_percent,
                memory_usage=memory_percent if PSUTIL_AVAILABLE else 0.0,
                disk_usage=disk_percent if PSUTIL_AVAILABLE else 0.0,
                network_io=network_io,
                response_time_p50=response_times["p50"],
                response_time_p95=response_times["p95"],
                error_rate=error_rate,
                active_connections=active_connections,
                uptime=uptime,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Failed to get system health metrics: {e}")
            # Return default values if system monitoring fails
            return SystemHealthMetrics(
                cpu_usage=0.0,
                memory_usage=0.0,
                disk_usage=0.0,
                network_io={"bytes_sent": 0, "bytes_recv": 0, "packets_sent": 0, "packets_recv": 0},
                response_time_p50=0.0,
                response_time_p95=0.0,
                error_rate=0.0,
                active_connections=0,
                uptime=0.0,
                timestamp=datetime.utcnow()
            )

    async def get_search_performance_metrics(
        self,
        organization_id: str,
        time_range: MetricTimeRange
    ) -> SearchPerformanceMetrics:
        """Get search performance metrics"""

        db = next(get_db())
        try:
            # Calculate time range
            cutoff_date = self._get_cutoff_date(time_range)

            # Get search performance data
            search_data = db.execute(text("""
                SELECT
                    COUNT(*) as total_searches,
                    AVG(response_time) as avg_response_time,
                    COUNT(CASE WHEN results_count = 0 THEN 1 END) as no_results_count,
                    COUNT(CASE WHEN error IS NOT NULL THEN 1 END) as error_count
                FROM search_queries sq
                JOIN search_sessions s ON sq.session_id = s.id
                WHERE s.organization_id = :org_id
                    AND s.start_time >= :cutoff_date
            """), {
                "org_id": organization_id,
                "cutoff_date": cutoff_date
            }).fetchone()

            # Get response time percentiles
            response_times = db.execute(text("""
                SELECT response_time
                FROM search_queries sq
                JOIN search_sessions s ON sq.session_id = s.id
                WHERE s.organization_id = :org_id
                    AND s.start_time >= :cutoff_date
                    AND response_time IS NOT NULL
                ORDER BY response_time
                OFFSET (SELECT COUNT(*) * 95 / 100 FROM
                    search_queries sq2 JOIN search_sessions s2 ON sq2.session_id = s2.id
                    WHERE s2.organization_id = :org_id AND s2.start_time >= :cutoff_date)
                LIMIT 1
            """), {
                "org_id": organization_id,
                "cutoff_date": cutoff_date
            }).scalar()

            # Get top queries
            top_queries = db.execute(text("""
                SELECT
                    sq.query,
                    COUNT(*) as search_count,
                    AVG(sq.response_time) as avg_response_time
                FROM search_queries sq
                JOIN search_sessions s ON sq.session_id = s.id
                WHERE s.organization_id = :org_id
                    AND s.start_time >= :cutoff_date
                GROUP BY sq.query
                ORDER BY search_count DESC
                LIMIT 10
            """), {
                "org_id": organization_id,
                "cutoff_date": cutoff_date
            }).fetchall()

            # Get search types distribution
            search_types = db.execute(text("""
                SELECT
                    sq.search_type,
                    COUNT(*) as count
                FROM search_queries sq
                JOIN search_sessions s ON sq.session_id = s.id
                WHERE s.organization_id = :org_id
                    AND s.start_time >= :cutoff_date
                GROUP BY sq.search_type
                ORDER BY count DESC
            """), {
                "org_id": organization_id,
                "cutoff_date": cutoff_date
            }).fetchall()

            # Calculate metrics
            total_searches = search_data.total_searches or 0
            avg_response_time = float(search_data.avg_response_time or 0)
            p95_response_time = float(response_times or 0)
            no_results_rate = (search_data.no_results_count / total_searches) if total_searches > 0 else 0
            success_rate = 1.0 - (search_data.error_count / total_searches) if total_searches > 0 else 1.0

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
                        "avg_response_time": float(q.avg_response_time or 0)
                    }
                    for q in top_queries
                ],
                search_types={st.search_type: st.count for st in search_types},
                errors=[]  # TODO: Implement error tracking
            )

        except Exception as e:
            logger.error(f"Failed to get search performance metrics: {e}")
            raise
        finally:
            db.close()

    async def get_quality_metrics_summary(
        self,
        organization_id: str,
        time_range: MetricTimeRange
    ) -> QualityMetricsSummary:
        """Get quality metrics summary"""

        db = next(get_db())
        try:
            cutoff_date = self._get_cutoff_date(time_range)

            # Get quality metrics
            quality_data = db.execute(text("""
                SELECT
                    AVG(qm.value) as avg_score,
                    qm.metric_type,
                    COUNT(*) as count
                FROM quality_metrics qm
                WHERE qm.organization_id = :org_id
                    AND qm.measured_at >= :cutoff_date
                GROUP BY qm.metric_type
            """), {
                "org_id": organization_id,
                "cutoff_date": cutoff_date
            }).fetchall()

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
            overall_score = (precision_avg * 0.3 + recall_avg * 0.3 +
                           relevance_avg * 0.2 + user_satisfaction * 0.2)

            # Get active alerts
            active_alerts = db.execute(text("""
                SELECT COUNT(*) as count
                FROM quality_alerts qa
                WHERE qa.organization_id = :org_id
                    AND qa.status = 'active'
            """), {
                "org_id": organization_id
            }).scalar() or 0

            # Get trends (compare to previous period)
            previous_cutoff = cutoff_date - timedelta(days=self._get_days_for_range(time_range))
            trends = await self._calculate_quality_trends(
                organization_id, cutoff_date, previous_cutoff
            )

            return QualityMetricsSummary(
                overall_score=overall_score,
                precision_avg=precision_avg,
                recall_avg=recall_avg,
                relevance_avg=relevance_avg,
                user_satisfaction=user_satisfaction,
                active_alerts=active_alerts,
                trends=trends,
                top_issues=[]  # TODO: Implement issue detection
            )

        except Exception as e:
            logger.error(f"Failed to get quality metrics summary: {e}")
            raise
        finally:
            db.close()

    async def get_user_engagement_metrics(
        self,
        organization_id: str,
        time_range: MetricTimeRange
    ) -> UserEngagementMetrics:
        """Get user engagement metrics"""

        db = next(get_db())
        try:
            cutoff_date = self._get_cutoff_date(time_range)

            # Get user engagement data
            engagement_data = db.execute(text("""
                SELECT
                    COUNT(DISTINCT s.user_id) as active_users,
                    COUNT(s.id) as total_sessions,
                    AVG(EXTRACT(EPOCH FROM (s.end_time - s.start_time))) as avg_duration,
                    COUNT(sq.id) as total_searches
                FROM search_sessions s
                LEFT JOIN search_queries sq ON s.id = sq.session_id
                WHERE s.organization_id = :org_id
                    AND s.start_time >= :cutoff_date
            """), {
                "org_id": organization_id,
                "cutoff_date": cutoff_date
            }).fetchone()

            # Get top users
            top_users = db.execute(text("""
                SELECT
                    u.id,
                    u.first_name,
                    u.last_name,
                    COUNT(DISTINCT s.id) as session_count,
                    COUNT(sq.id) as search_count,
                    AVG(sq.response_time) as avg_response_time
                FROM users u
                JOIN search_sessions s ON u.id = s.user_id
                LEFT JOIN search_queries sq ON s.id = sq.session_id
                WHERE u.organization_id = :org_id
                    AND s.start_time >= :cutoff_date
                GROUP BY u.id, u.first_name, u.last_name
                ORDER BY search_count DESC
                LIMIT 10
            """), {
                "org_id": organization_id,
                "cutoff_date": cutoff_date
            }).fetchall()

            # Calculate metrics
            active_users = engagement_data.active_users or 0
            total_sessions = engagement_data.total_sessions or 0
            avg_session_duration = float(engagement_data.avg_duration or 0)
            total_searches = engagement_data.total_searches or 0
            searches_per_user = total_searches / active_users if active_users > 0 else 0

            # Determine engagement trend
            engagement_trend = await self._calculate_engagement_trend(
                organization_id, cutoff_date, time_range
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
                        "avg_response_time": float(u.avg_response_time or 0)
                    }
                    for u in top_users
                ],
                engagement_trend=engagement_trend
            )

        except Exception as e:
            logger.error(f"Failed to get user engagement metrics: {e}")
            raise
        finally:
            db.close()

    async def get_active_alerts(self, organization_id: str) -> List[Dict[str, Any]]:
        """Get active alerts for the organization"""

        db = next(get_db())
        try:
            alerts = db.execute(text("""
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
                WHERE qa.organization_id = :org_id
                    AND qa.status = 'active'
                ORDER BY qa.severity DESC, qa.created_at DESC
                LIMIT 50
            """), {
                "org_id": organization_id
            }).fetchall()

            return [
                {
                    "id": str(alert.id),
                    "severity": alert.severity,
                    "title": alert.title,
                    "message": alert.message,
                    "created_at": alert.created_at.isoformat(),
                    "metric_type": alert.metric_type,
                    "current_value": float(alert.current_value or 0)
                }
                for alert in alerts
            ]

        except Exception as e:
            logger.error(f"Failed to get active alerts: {e}")
            return []
        finally:
            db.close()

    async def get_metric_chart_data(
        self,
        organization_id: str,
        metric_name: str,
        time_range: MetricTimeRange,
        granularity: str = "hour"
    ) -> List[Dict[str, Any]]:
        """Get time-series data for metric charts"""

        db = next(get_db())
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
                data = db.execute(text(f"""
                    SELECT
                        DATE_TRUNC('{granularity}', s.start_time) as period,
                        COUNT(sq.id) as value
                    FROM search_sessions s
                    LEFT JOIN search_queries sq ON s.id = sq.session_id
                    WHERE s.organization_id = :org_id
                        AND s.start_time >= :cutoff_date
                    GROUP BY period
                    ORDER BY period
                """), {
                    "org_id": organization_id,
                    "cutoff_date": cutoff_date
                }).fetchall()
            elif metric_name == "response_time":
                data = db.execute(text(f"""
                    SELECT
                        DATE_TRUNC('{granularity}', sq.created_at) as period,
                        AVG(sq.response_time) as value
                    FROM search_queries sq
                    JOIN search_sessions s ON sq.session_id = s.id
                    WHERE s.organization_id = :org_id
                        AND sq.created_at >= :cutoff_date
                        AND sq.response_time IS NOT NULL
                    GROUP BY period
                    ORDER BY period
                """), {
                    "org_id": organization_id,
                    "cutoff_date": cutoff_date
                }).fetchall()
            elif metric_name == "quality_score":
                data = db.execute(text(f"""
                    SELECT
                        DATE_TRUNC('{granularity}', qm.measured_at) as period,
                        AVG(qm.value) as value
                    FROM quality_metrics qm
                    WHERE qm.organization_id = :org_id
                        AND qm.measured_at >= :cutoff_date
                        AND qm.metric_type = 'relevance'
                    GROUP BY period
                    ORDER BY period
                """), {
                    "org_id": organization_id,
                    "cutoff_date": cutoff_date
                }).fetchall()
            else:
                # Default to system metrics
                data = db.execute(text(f"""
                    SELECT
                        DATE_TRUNC('{granularity}', sm.measured_at) as period,
                        AVG(sm.metric_value) as value
                    FROM system_metrics sm
                    WHERE sm.organization_id = :org_id
                        AND sm.measured_at >= :cutoff_date
                        AND sm.metric_name = :metric_name
                    GROUP BY period
                    ORDER BY period
                """), {
                    "org_id": organization_id,
                    "cutoff_date": cutoff_date,
                    "metric_name": metric_name
                }).fetchall()

            return [
                {
                    "timestamp": row.period.isoformat(),
                    "value": float(row.value or 0)
                }
                for row in data
            ]

        except Exception as e:
            logger.error(f"Failed to get metric chart data: {e}")
            return []
        finally:
            db.close()

    async def create_dashboard_widgets(
        self,
        organization_id: str,
        widget_configs: List[Dict[str, Any]]
    ) -> List[DashboardWidget]:
        """Create dashboard widgets with data"""

        widgets = []

        for config in widget_configs:
            try:
                # Get widget data based on type and metrics
                widget_data = await self._get_widget_data(
                    organization_id, config
                )

                widget = DashboardWidget(
                    id=config.get("id", str(uuid.uuid4())),
                    title=config["title"],
                    widget_type=DashboardWidgetType(config["widget_type"]),
                    metrics=config["metrics"],
                    time_range=MetricTimeRange(config["time_range"]),
                    position=config["position"],
                    size=config["size"],
                    data=widget_data,
                    refresh_interval=config.get("refresh_interval", 300)
                )

                widgets.append(widget)

            except Exception as e:
                logger.error(f"Failed to create widget {config.get('title', 'unknown')}: {e}")
                continue

        return widgets

    async def _get_widget_data(
        self,
        organization_id: str,
        config: Dict[str, Any]
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
                previous_value = chart_data[-2]["value"] if len(chart_data) > 1 else current_value
                trend = ((current_value - previous_value) / previous_value * 100) if previous_value != 0 else 0
            else:
                current_value = 0
                trend = 0

            return {
                "current_value": current_value,
                "trend": trend,
                "data_points": chart_data
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
                db = next(get_db())
                try:
                    cutoff_date = self._get_cutoff_date(time_range)
                    data = db.execute(text("""
                        SELECT
                            sq.search_type,
                            COUNT(*) as count
                        FROM search_queries sq
                        JOIN search_sessions s ON sq.session_id = s.id
                        WHERE s.organization_id = :org_id
                            AND s.created_at >= :cutoff_date
                        GROUP BY sq.search_type
                        ORDER BY count DESC
                    """), {
                        "org_id": organization_id,
                        "cutoff_date": cutoff_date
                    }).fetchall()

                    return {
                        "labels": [row.search_type for row in data],
                        "values": [row.count for row in data]
                    }
                finally:
                    db.close()

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
            MetricTimeRange.LAST_90D: 90
        }
        return mapping[time_range]

    async def _get_response_time_metrics(self) -> Dict[str, float]:
        """Get response time metrics from recent searches"""

        db = next(get_db())
        try:
            # Get recent response times
            response_times = db.execute(text("""
                SELECT response_time
                FROM search_queries
                WHERE created_at >= NOW() - INTERVAL '1 hour'
                    AND response_time IS NOT NULL
                ORDER BY response_time
            """)).fetchall()

            if not response_times:
                return {"p50": 0.0, "p95": 0.0}

            times = [row[0] for row in response_times]

            # Calculate percentiles
            p50_index = int(len(times) * 0.5)
            p95_index = int(len(times) * 0.95)

            return {
                "p50": times[p50_index] if p50_index < len(times) else times[-1],
                "p95": times[p95_index] if p95_index < len(times) else times[-1]
            }

        except Exception as e:
            logger.error(f"Failed to get response time metrics: {e}")
            return {"p50": 0.0, "p95": 0.0}
        finally:
            db.close()

    async def _get_error_rate(self) -> float:
        """Get current error rate"""

        db = next(get_db())
        try:
            result = db.execute(text("""
                SELECT
                    COUNT(CASE WHEN error IS NOT NULL THEN 1 END) as errors,
                    COUNT(*) as total
                FROM search_queries
                WHERE created_at >= NOW() - INTERVAL '1 hour'
            """)).fetchone()

            if result.total == 0:
                return 0.0

            return (result.errors / result.total) * 100

        except Exception as e:
            logger.error(f"Failed to get error rate: {e}")
            return 0.0
        finally:
            db.close()

    async def _get_active_connections(self) -> int:
        """Get estimated active connections"""

        # This is a simplified estimate - in production you'd use proper connection tracking
        db = next(get_db())
        try:
            result = db.execute(text("""
                SELECT COUNT(DISTINCT session_id) as active_sessions
                FROM search_sessions
                WHERE start_time >= NOW() - INTERVAL '30 minutes'
                    AND end_time IS NULL
            """)).fetchone()

            return result.active_sessions or 0

        except Exception as e:
            logger.error(f"Failed to get active connections: {e}")
            return 0
        finally:
            db.close()

    async def _calculate_quality_trends(
        self,
        organization_id: str,
        current_cutoff: datetime,
        previous_cutoff: datetime
    ) -> Dict[str, float]:
        """Calculate quality metric trends"""

        db = next(get_db())
        try:
            # Current period metrics
            current_metrics = db.execute(text("""
                SELECT
                    metric_type,
                    AVG(value) as avg_value
                FROM quality_metrics
                WHERE organization_id = :org_id
                    AND measured_at >= :cutoff_date
                GROUP BY metric_type
            """), {
                "org_id": organization_id,
                "cutoff_date": current_cutoff
            }).fetchall()

            # Previous period metrics
            previous_metrics = db.execute(text("""
                SELECT
                    metric_type,
                    AVG(value) as avg_value
                FROM quality_metrics
                WHERE organization_id = :org_id
                    AND measured_at >= :prev_cutoff
                    AND measured_at < :current_cutoff
                GROUP BY metric_type
            """), {
                "org_id": organization_id,
                "prev_cutoff": previous_cutoff,
                "current_cutoff": current_cutoff
            }).fetchall()

            # Calculate trends
            current_by_type = {m.metric_type: float(m.avg_value or 0) for m in current_metrics}
            previous_by_type = {m.metric_type: float(m.avg_value or 0) for m in previous_metrics}

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
        finally:
            db.close()

    async def _calculate_engagement_trend(
        self,
        organization_id: str,
        cutoff_date: datetime,
        time_range: MetricTimeRange
    ) -> str:
        """Calculate engagement trend"""

        db = next(get_db())
        try:
            # Current period
            current_data = db.execute(text("""
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM search_sessions
                WHERE organization_id = :org_id
                    AND start_time >= :cutoff_date
            """), {
                "org_id": organization_id,
                "cutoff_date": cutoff_date
            }).fetchone()

            # Previous period (same duration)
            days = self._get_days_for_range(time_range)
            prev_cutoff = cutoff_date - timedelta(days=days)

            previous_data = db.execute(text("""
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM search_sessions
                WHERE organization_id = :org_id
                    AND start_time >= :prev_cutoff
                    AND start_time < :cutoff_date
            """), {
                "org_id": organization_id,
                "prev_cutoff": prev_cutoff,
                "cutoff_date": cutoff_date
            }).fetchone()

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
        finally:
            db.close()


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
                bytes_sent_per_sec = (current_stats.bytes_sent - self.last_network_stats["bytes_sent"]) / time_delta
                bytes_recv_per_sec = (current_stats.bytes_recv - self.last_network_stats["bytes_recv"]) / time_delta

                self.last_network_stats = {
                    "bytes_sent": current_stats.bytes_sent,
                    "bytes_recv": current_stats.bytes_recv,
                    "timestamp": time.time()
                }

                return {
                    "bytes_sent_per_sec": bytes_sent_per_sec,
                    "bytes_recv_per_sec": bytes_recv_per_sec
                }

        self.last_network_stats = {
            "bytes_sent": current_stats.bytes_sent,
            "bytes_recv": current_stats.bytes_recv,
            "timestamp": time.time()
        }

        return {"bytes_sent_per_sec": 0, "bytes_recv_per_sec": 0}


# Global service instance
performance_dashboard_service = PerformanceDashboardService()