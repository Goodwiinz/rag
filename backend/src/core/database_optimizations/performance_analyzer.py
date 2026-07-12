"""
Advanced Performance Analysis and Monitoring Tools for Multimodal Enterprise RAG System

This module provides comprehensive performance analysis, query optimization,
and real-time monitoring across all databases with intelligent alerting and
automated performance tuning.
"""

import asyncio
import json
import logging
import statistics
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Performance metric types"""

    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    RESOURCE_USAGE = "resource_usage"
    QUERY_PERFORMANCE = "query_performance"
    CACHE_HIT_RATE = "cache_hit_rate"
    CONNECTION_UTILIZATION = "connection_utilization"


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OptimizationSuggestion(str, Enum):
    """Optimization suggestion types"""

    INDEX_CREATION = "index_creation"
    QUERY_REWRITE = "query_rewrite"
    CONFIG_CHANGE = "config_change"
    SCHEMA_CHANGE = "schema_change"
    CACHE_OPTIMIZATION = "cache_optimization"
    CONNECTION_TUNING = "connection_tuning"


@dataclass
class PerformanceMetric:
    """Individual performance metric"""

    metric_type: MetricType
    value: float
    unit: str
    timestamp: datetime
    database_type: str
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceAlert:
    """Performance alert definition"""

    alert_id: str
    metric_type: MetricType
    severity: AlertSeverity
    threshold_value: float
    comparison_operator: str  # >, <, >=, <=, ==
    duration_minutes: int
    description: str
    notification_channels: List[str] = field(default_factory=list)
    is_active: bool = False
    triggered_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation"""

    recommendation_id: str
    suggestion_type: OptimizationSuggestion
    database_type: str
    priority: int  # 1-10, 10 being highest
    description: str
    estimated_improvement: str
    implementation_complexity: str  # low, medium, high
    sql_commands: List[str] = field(default_factory=list)
    config_changes: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QueryPerformanceProfile:
    """Query performance profile"""

    query_id: str
    query_text: str
    database_type: str
    execution_count: int = 0
    total_exec_time_ms: float = 0.0
    avg_exec_time_ms: float = 0.0
    min_exec_time_ms: float = float("inf")
    max_exec_time_ms: float = 0.0
    std_dev_exec_time_ms: float = 0.0
    rows_examined: int = 0
    rows_returned: int = 0
    index_usage_info: Dict[str, Any] = field(default_factory=dict)
    execution_plan: Dict[str, Any] = field(default_factory=dict)
    last_executed: Optional[datetime] = None
    performance_score: float = 0.0  # 0-100, higher is better


class PerformanceAnalyzer:
    """Advanced performance analyzer for database systems"""

    def __init__(self):
        self.metrics_buffer: deque = deque(maxlen=10000)
        self.query_profiles: Dict[str, QueryPerformanceProfile] = {}
        self.active_alerts: Dict[str, PerformanceAlert] = {}
        self.alert_rules: List[PerformanceAlert] = []
        self.recommendations: List[OptimizationRecommendation] = []
        self.baseline_metrics: Dict[str, Dict[str, float]] = {}
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.analysis_task: Optional[asyncio.Task] = None

    async def start_monitoring(self, monitoring_interval_seconds: int = 60):
        """Start continuous performance monitoring"""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(
            self._monitoring_loop(monitoring_interval_seconds)
        )
        self.analysis_task = asyncio.create_task(self._analysis_loop())
        logger.info("Performance monitoring started")

    async def stop_monitoring(self):
        """Stop performance monitoring"""
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
        if self.analysis_task:
            self.analysis_task.cancel()
        logger.info("Performance monitoring stopped")

    async def _monitoring_loop(self, interval_seconds: int):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                await self._collect_metrics()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(interval_seconds)

    async def _analysis_loop(self):
        """Performance analysis loop"""
        while self.is_monitoring:
            try:
                await self._analyze_performance()
                await self._check_alerts()
                await self._generate_recommendations()
                await asyncio.sleep(300)  # Analyze every 5 minutes
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Analysis loop error: {e}")
                await asyncio.sleep(300)

    async def _collect_metrics(self):
        """Collect performance metrics from all databases"""
        # This would collect actual metrics from database optimizers
        # For now, we'll simulate metric collection
        current_time = datetime.utcnow()

        # Simulate metrics for different database types
        for db_type in ["postgresql", "neo4j", "redis", "qdrant"]:
            # Response time metrics
            response_time = np.random.normal(50, 10)  # Mean 50ms, std 10ms
            await self._add_metric(
                MetricType.RESPONSE_TIME,
                response_time,
                "ms",
                current_time,
                db_type,
                tags={"operation": "query"},
            )

            # Throughput metrics
            throughput = np.random.normal(1000, 200)  # Mean 1000 ops/sec
            await self._add_metric(
                MetricType.THROUGHPUT,
                throughput,
                "ops/sec",
                current_time,
                db_type,
                tags={"operation": "read"},
            )

            # Error rate metrics
            error_rate = np.random.uniform(0, 2)  # 0-2% error rate
            await self._add_metric(
                MetricType.ERROR_RATE, error_rate, "percent", current_time, db_type
            )

            # Connection utilization
            utilization = np.random.uniform(40, 80)  # 40-80% utilization
            await self._add_metric(
                MetricType.CONNECTION_UTILIZATION,
                utilization,
                "percent",
                current_time,
                db_type,
            )

    async def _add_metric(
        self,
        metric_type: MetricType,
        value: float,
        unit: str,
        timestamp: datetime,
        database_type: str,
        tags: Dict[str, str] = None,
    ):
        """Add performance metric to buffer"""
        metric = PerformanceMetric(
            metric_type=metric_type,
            value=value,
            unit=unit,
            timestamp=timestamp,
            database_type=database_type,
            tags=tags or {},
        )
        self.metrics_buffer.append(metric)

    async def _analyze_performance(self):
        """Analyze collected performance metrics"""
        if len(self.metrics_buffer) < 100:  # Need sufficient data
            return

        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(minutes=60)

        # Filter recent metrics
        recent_metrics = [m for m in self.metrics_buffer if m.timestamp >= cutoff_time]

        # Analyze by database type and metric type
        for db_type in ["postgresql", "neo4j", "redis", "qdrant"]:
            for metric_type in MetricType:
                await self._analyze_metric_type(db_type, metric_type, recent_metrics)

    async def _analyze_metric_type(
        self,
        database_type: str,
        metric_type: MetricType,
        metrics: List[PerformanceMetric],
    ):
        """Analyze specific metric type for a database"""
        # Filter metrics for this database and type
        filtered_metrics = [
            m
            for m in metrics
            if m.database_type == database_type and m.metric_type == metric_type
        ]

        if len(filtered_metrics) < 10:
            return

        values = [m.value for m in filtered_metrics]

        # Calculate statistics
        stats = {
            "count": len(values),
            "avg": statistics.mean(values),
            "min": min(values),
            "max": max(values),
            "median": statistics.median(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
            "p95": np.percentile(values, 95),
            "p99": np.percentile(values, 99),
        }

        # Detect anomalies
        anomalies = await self._detect_anomalies(
            database_type, metric_type, filtered_metrics, stats
        )

        # Store in baseline if not exists
        baseline_key = f"{database_type}_{metric_type.value}"
        if baseline_key not in self.baseline_metrics:
            self.baseline_metrics[baseline_key] = {
                "avg": stats["avg"],
                "std_dev": stats["std_dev"],
                "created_at": datetime.utcnow().isoformat(),
            }

    async def _detect_anomalies(
        self,
        database_type: str,
        metric_type: MetricType,
        metrics: List[PerformanceMetric],
        stats: Dict[str, float],
    ) -> List[PerformanceMetric]:
        """Detect performance anomalies using statistical methods"""
        anomalies = []
        baseline_key = f"{database_type}_{metric_type.value}"

        if baseline_key not in self.baseline_metrics:
            return anomalies

        baseline = self.baseline_metrics[baseline_key]
        threshold = baseline["avg"] + (2 * baseline["std_dev"])  # 2-sigma rule

        for metric in metrics:
            if metric.value > threshold:
                anomalies.append(metric)
                logger.warning(
                    f"Performance anomaly detected: {database_type} {metric_type.value} = {metric.value} "
                    f"(threshold: {threshold:.2f})"
                )

        return anomalies

    async def _check_alerts(self):
        """Check performance alerts against current metrics"""
        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(minutes=60)

        for alert_rule in self.alert_rules:
            if alert_rule.metric_type not in MetricType:
                continue

            # Get recent metrics for this alert rule
            recent_metrics = [
                m
                for m in self.metrics_buffer
                if (
                    m.metric_type == alert_rule.metric_type
                    and m.timestamp >= cutoff_time
                )
            ]

            if len(recent_metrics) < alert_rule.duration_minutes:
                continue

            # Check if alert condition is met
            values = [m.value for m in recent_metrics]
            condition_met = self._evaluate_alert_condition(values, alert_rule)

            if condition_met and not alert_rule.is_active:
                # Trigger alert
                alert_rule.is_active = True
                alert_rule.triggered_at = current_time
                self.active_alerts[alert_rule.alert_id] = alert_rule
                await self._send_alert_notification(alert_rule)

            elif not condition_met and alert_rule.is_active:
                # Resolve alert
                alert_rule.is_active = False
                alert_rule.resolved_at = current_time
                if alert_rule.alert_id in self.active_alerts:
                    del self.active_alerts[alert_rule.alert_id]

    def _evaluate_alert_condition(
        self, values: List[float], alert_rule: PerformanceAlert
    ) -> bool:
        """Evaluate alert condition against metric values"""
        if not values:
            return False

        avg_value = statistics.mean(values)

        if alert_rule.comparison_operator == ">":
            return avg_value > alert_rule.threshold_value
        elif alert_rule.comparison_operator == "<":
            return avg_value < alert_rule.threshold_value
        elif alert_rule.comparison_operator == ">=":
            return avg_value >= alert_rule.threshold_value
        elif alert_rule.comparison_operator == "<=":
            return avg_value <= alert_rule.threshold_value
        elif alert_rule.comparison_operator == "==":
            return avg_value == alert_rule.threshold_value

        return False

    async def _send_alert_notification(self, alert: PerformanceAlert):
        """Send alert notification"""
        logger.warning(
            f"ALERT TRIGGERED: {alert.description} - "
            f"{alert.metric_type.value} {alert.comparison_operator} {alert.threshold_value}"
        )

        # Implementation would send to configured notification channels
        # (email, Slack, PagerDuty, etc.)

    async def _generate_recommendations(self):
        """Generate performance optimization recommendations"""
        current_time = datetime.utcnow()
        cutoff_time = current_time - timedelta(hours=24)

        # Analyze recent metrics for optimization opportunities
        recent_metrics = [m for m in self.metrics_buffer if m.timestamp >= cutoff_time]

        # Generate recommendations for each database type
        for db_type in ["postgresql", "neo4j", "redis", "qdrant"]:
            await self._generate_database_recommendations(db_type, recent_metrics)

    async def _generate_database_recommendations(
        self, database_type: str, metrics: List[PerformanceMetric]
    ):
        """Generate recommendations for specific database"""
        db_metrics = [m for m in metrics if m.database_type == database_type]

        # Analyze response times
        response_times = [
            m.value for m in db_metrics if m.metric_type == MetricType.RESPONSE_TIME
        ]
        if response_times and statistics.mean(response_times) > 100:  # > 100ms average
            await self._create_response_time_recommendation(
                database_type, response_times
            )

        # Analyze error rates
        error_rates = [
            m.value for m in db_metrics if m.metric_type == MetricType.ERROR_RATE
        ]
        if error_rates and statistics.mean(error_rates) > 5:  # > 5% error rate
            await self._create_error_rate_recommendation(database_type, error_rates)

        # Analyze connection utilization
        utilizations = [
            m.value
            for m in db_metrics
            if m.metric_type == MetricType.CONNECTION_UTILIZATION
        ]
        if utilizations and statistics.mean(utilizations) > 80:  # > 80% utilization
            await self._create_connection_recommendation(database_type, utilizations)

    async def _create_response_time_recommendation(
        self, database_type: str, response_times: List[float]
    ):
        """Create response time optimization recommendation"""
        recommendation = OptimizationRecommendation(
            recommendation_id=str(uuid.uuid4()),
            suggestion_type=OptimizationSuggestion.INDEX_CREATION,
            database_type=database_type,
            priority=7,
            description=f"High response times detected (avg: {statistics.mean(response_times):.1f}ms). "
            f"Consider adding missing indexes or optimizing slow queries.",
            estimated_improvement="20-40% response time reduction",
            implementation_complexity="medium",
            sql_commands=[
                "-- Example: Add index for frequently queried columns",
                "CREATE INDEX CONCURRENTLY idx_table_column ON table_name(column_name);",
                "-- Analyze slow queries using:",
                "SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;",
            ],
        )
        self.recommendations.append(recommendation)

    async def _create_error_rate_recommendation(
        self, database_type: str, error_rates: List[float]
    ):
        """Create error rate optimization recommendation"""
        recommendation = OptimizationRecommendation(
            recommendation_id=str(uuid.uuid4()),
            suggestion_type=OptimizationSuggestion.CONFIG_CHANGE,
            database_type=database_type,
            priority=9,
            description=f"High error rate detected (avg: {statistics.mean(error_rates):.1f}%). "
            f"Investigate connection issues and increase timeout settings.",
            estimated_improvement="Significant reduction in failed requests",
            implementation_complexity="low",
            config_changes={
                "connection_timeout": 30,
                "query_timeout": 60,
                "retry_attempts": 3,
                "retry_delay": 1.0,
            },
        )
        self.recommendations.append(recommendation)

    async def _create_connection_recommendation(
        self, database_type: str, utilizations: List[float]
    ):
        """Create connection pool optimization recommendation"""
        recommendation = OptimizationRecommendation(
            recommendation_id=str(uuid.uuid4()),
            suggestion_type=OptimizationSuggestion.CONNECTION_TUNING,
            database_type=database_type,
            priority=6,
            description=f"High connection utilization detected (avg: {statistics.mean(utilizations):.1f}%). "
            f"Consider increasing connection pool size or implementing connection pooling.",
            estimated_improvement="Improved throughput and reduced wait times",
            implementation_complexity="low",
            config_changes={
                "min_connections": 20,
                "max_connections": 100,
                "connection_timeout": 30,
                "idle_timeout": 300,
            },
        )
        self.recommendations.append(recommendation)

    async def analyze_query_performance(
        self, query_text: str, database_type: str, execution_plan: Dict[str, Any] = None
    ) -> QueryPerformanceProfile:
        """Analyze individual query performance"""
        query_id = str(hash(query_text))

        # Create or update query profile
        if query_id not in self.query_profiles:
            self.query_profiles[query_id] = QueryPerformanceProfile(
                query_id=query_id, query_text=query_text, database_type=database_type
            )

        profile = self.query_profiles[query_id]

        # Simulate execution metrics (in real implementation, would get actual metrics)
        exec_time = np.random.normal(50, 15)  # Random execution time
        profile.execution_count += 1
        profile.total_exec_time_ms += exec_time
        profile.avg_exec_time_ms = profile.total_exec_time_ms / profile.execution_count
        profile.min_exec_time_ms = min(profile.min_exec_time_ms, exec_time)
        profile.max_exec_time_ms = max(profile.max_exec_time_ms, exec_time)
        profile.last_executed = datetime.utcnow()

        # Calculate performance score (0-100)
        if profile.avg_exec_time_ms < 10:
            profile.performance_score = 100
        elif profile.avg_exec_time_ms < 50:
            profile.performance_score = 80
        elif profile.avg_exec_time_ms < 100:
            profile.performance_score = 60
        elif profile.avg_exec_time_ms < 500:
            profile.performance_score = 40
        else:
            profile.performance_score = 20

        # Analyze execution plan if provided
        if execution_plan:
            profile.execution_plan = execution_plan
            await self._analyze_execution_plan(profile, execution_plan)

        return profile

    async def _analyze_execution_plan(
        self, profile: QueryPerformanceProfile, execution_plan: Dict[str, Any]
    ):
        """Analyze query execution plan for optimization opportunities"""
        # Look for sequential scans, missing indexes, etc.
        plan_text = str(execution_plan)

        if "Seq Scan" in plan_text:
            # Create index recommendation
            recommendation = OptimizationRecommendation(
                recommendation_id=str(uuid.uuid4()),
                suggestion_type=OptimizationSuggestion.INDEX_CREATION,
                database_type=profile.database_type,
                priority=8,
                description=f"Sequential scan detected in query. Consider adding appropriate indexes.",
                estimated_improvement="50-90% query speed improvement",
                implementation_complexity="low",
                sql_commands=[
                    "-- Add index for columns used in WHERE clause",
                    "CREATE INDEX CONCURRENTLY idx_table_column ON table_name(column_name);",
                ],
            )
            self.recommendations.append(recommendation)

        if "Sort" in plan_text and "Index Scan" not in plan_text:
            # Create index for ORDER BY optimization
            recommendation = OptimizationRecommendation(
                recommendation_id=str(uuid.uuid4()),
                suggestion_type=OptimizationSuggestion.INDEX_CREATION,
                database_type=profile.database_type,
                priority=7,
                description="Sorting operation detected. Consider adding index for ORDER BY clause.",
                estimated_improvement="30-70% sorting performance improvement",
                implementation_complexity="low",
                sql_commands=[
                    "-- Add index for ORDER BY optimization",
                    "CREATE INDEX CONCURRENTLY idx_table_order BY ON table_name(order_column);",
                ],
            )
            self.recommendations.append(recommendation)

    def add_alert_rule(self, alert_rule: PerformanceAlert):
        """Add performance alert rule"""
        self.alert_rules.append(alert_rule)
        logger.info(f"Added alert rule: {alert_rule.description}")

    def remove_alert_rule(self, alert_id: str):
        """Remove performance alert rule"""
        self.alert_rules = [a for a in self.alert_rules if a.alert_id != alert_id]
        if alert_id in self.active_alerts:
            del self.active_alerts[alert_id]
        logger.info(f"Removed alert rule: {alert_id}")

    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance summary for specified time period"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_metrics = [m for m in self.metrics_buffer if m.timestamp >= cutoff_time]

        summary = {
            "time_period_hours": hours,
            "total_metrics": len(recent_metrics),
            "database_performance": {},
            "active_alerts": len(self.active_alerts),
            "pending_recommendations": len(self.recommendations),
            "top_slow_queries": [],
            "performance_trends": {},
        }

        # Aggregate by database type
        for db_type in ["postgresql", "neo4j", "redis", "qdrant"]:
            db_metrics = [m for m in recent_metrics if m.database_type == db_type]
            if db_metrics:
                summary["database_performance"][
                    db_type
                ] = self._calculate_db_performance_summary(db_metrics)

        # Get top slow queries
        slow_queries = sorted(
            self.query_profiles.values(), key=lambda q: q.avg_exec_time_ms, reverse=True
        )[:10]

        summary["top_slow_queries"] = [
            {
                "query_id": q.query_id,
                "database_type": q.database_type,
                "avg_exec_time_ms": q.avg_exec_time_ms,
                "execution_count": q.execution_count,
                "performance_score": q.performance_score,
            }
            for q in slow_queries
        ]

        # Calculate performance trends
        summary["performance_trends"] = self._calculate_performance_trends(
            recent_metrics
        )

        return summary

    def _calculate_db_performance_summary(
        self, metrics: List[PerformanceMetric]
    ) -> Dict[str, Any]:
        """Calculate performance summary for a database"""
        summary = {}

        for metric_type in MetricType:
            type_metrics = [m for m in metrics if m.metric_type == metric_type]
            if type_metrics:
                values = [m.value for m in type_metrics]
                summary[metric_type.value] = {
                    "avg": statistics.mean(values),
                    "min": min(values),
                    "max": max(values),
                    "p95": np.percentile(values, 95),
                    "count": len(values),
                }

        return summary

    def _calculate_performance_trends(
        self, metrics: List[PerformanceMetric]
    ) -> Dict[str, Any]:
        """Calculate performance trends over time"""
        if len(metrics) < 100:
            return {"message": "Insufficient data for trend analysis"}

        trends = {}
        current_time = datetime.utcnow()

        # Compare recent performance to older performance
        recent_cutoff = current_time - timedelta(hours=6)
        older_cutoff = current_time - timedelta(hours=24)

        recent_metrics = [m for m in metrics if m.timestamp >= recent_cutoff]
        older_metrics = [
            m for m in metrics if older_cutoff <= m.timestamp < recent_cutoff
        ]

        for metric_type in MetricType:
            recent_values = [
                m.value for m in recent_metrics if m.metric_type == metric_type
            ]
            older_values = [
                m.value for m in older_metrics if m.metric_type == metric_type
            ]

            if recent_values and older_values:
                recent_avg = statistics.mean(recent_values)
                older_avg = statistics.mean(older_values)

                trend_direction = "improving" if recent_avg < older_avg else "degrading"
                trend_percentage = (
                    ((recent_avg - older_avg) / older_avg * 100)
                    if older_avg != 0
                    else 0
                )

                trends[metric_type.value] = {
                    "direction": trend_direction,
                    "percentage_change": trend_percentage,
                    "recent_avg": recent_avg,
                    "older_avg": older_avg,
                }

        return trends

    def get_recommendations(
        self,
        database_type: Optional[str] = None,
        priority_min: int = 1,
        priority_max: int = 10,
    ) -> List[OptimizationRecommendation]:
        """Get optimization recommendations"""
        recommendations = self.recommendations

        if database_type:
            recommendations = [
                r for r in recommendations if r.database_type == database_type
            ]

        recommendations = [
            r for r in recommendations if priority_min <= r.priority <= priority_max
        ]

        return sorted(recommendations, key=lambda r: r.priority, reverse=True)

    def clear_recommendations(self):
        """Clear all recommendations"""
        self.recommendations.clear()
        logger.info("Cleared all optimization recommendations")

    def get_active_alerts(self) -> List[PerformanceAlert]:
        """Get currently active alerts"""
        return list(self.active_alerts.values())


# Utility functions
async def create_performance_analyzer() -> PerformanceAnalyzer:
    """Create and configure performance analyzer"""
    analyzer = PerformanceAnalyzer()

    # Add default alert rules
    alert_rules = [
        PerformanceAlert(
            alert_id="high_response_time",
            metric_type=MetricType.RESPONSE_TIME,
            severity=AlertSeverity.HIGH,
            threshold_value=500,
            comparison_operator=">",
            duration_minutes=5,
            description="High response time detected",
            notification_channels=["email", "slack"],
        ),
        PerformanceAlert(
            alert_id="high_error_rate",
            metric_type=MetricType.ERROR_RATE,
            severity=AlertSeverity.CRITICAL,
            threshold_value=10,
            comparison_operator=">",
            duration_minutes=2,
            description="High error rate detected",
            notification_channels=["email", "slack", "pagerduty"],
        ),
        PerformanceAlert(
            alert_id="high_connection_utilization",
            metric_type=MetricType.CONNECTION_UTILIZATION,
            severity=AlertSeverity.MEDIUM,
            threshold_value=90,
            comparison_operator=">",
            duration_minutes=10,
            description="High connection utilization detected",
            notification_channels=["email"],
        ),
    ]

    for alert_rule in alert_rules:
        analyzer.add_alert_rule(alert_rule)

    return analyzer
