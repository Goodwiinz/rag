"""
Performance Analytics and Optimization Insights for Knowledge Graph Analytics Dashboard
Advanced performance monitoring, bottleneck detection, and optimization recommendations
"""

import asyncio
import json
import os
import statistics
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

from .logging import get_logger
from .metrics import business_metrics
from .opentelemetry import otel_manager

logger = get_logger(__name__)


class PerformanceIssueType(Enum):
    """Types of performance issues"""

    HIGH_LATENCY = "high_latency"
    HIGH_ERROR_RATE = "high_error_rate"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SLOW_QUERIES = "slow_queries"
    MEMORY_LEAK = "memory_leak"
    CPU_BOTTLENECK = "cpu_bottleneck"
    IO_BOTTLENECK = "io_bottleneck"
    CACHE_MISS = "cache_miss"
    INEFFICIENT_ALGORITHM = "inefficient_algorithm"
    SCALABILITY_ISSUE = "scalability_issue"


class Severity(Enum):
    """Severity levels for performance issues"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PerformanceMetric:
    """Performance metric data point"""

    name: str
    value: float
    timestamp: datetime
    unit: str
    labels: Dict[str, str] = field(default_factory=dict)
    component: str = ""
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class PerformanceIssue:
    """Performance issue detection result"""

    id: str
    type: PerformanceIssueType
    severity: Severity
    title: str
    description: str
    component: str
    metric_name: str
    current_value: float
    threshold_value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    recommendations: List[str] = field(default_factory=list)
    affected_metrics: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation"""

    id: str
    title: str
    description: str
    category: str
    priority: int
    estimated_impact: str
    implementation_effort: str
    component: str
    metrics_affected: List[str]
    steps: List[str] = field(default_factory=list)
    code_examples: Dict[str, str] = field(default_factory=dict)


@dataclass
class PerformanceBaseline:
    """Performance baseline for comparison"""

    name: str
    component: str
    metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    description: str = ""


class PerformanceAnalyzer:
    """Performance analyzer for detecting issues and providing insights"""

    def __init__(self):
        self.metrics_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=10000)
        )
        self.performance_issues: List[PerformanceIssue] = []
        self.baselines: Dict[str, PerformanceBaseline] = {}
        self.recommendations: List[OptimizationRecommendation] = []
        self.analysis_rules = self._initialize_analysis_rules()
        self._last_analysis: Optional[datetime] = None

    def _initialize_analysis_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize performance analysis rules"""
        return {
            "latency_analysis": {
                "threshold_p95": 2000.0,  # 2 seconds
                "threshold_p99": 5000.0,  # 5 seconds
                "window_minutes": 15,
                "min_samples": 10,
            },
            "error_rate_analysis": {
                "threshold_warning": 0.01,  # 1%
                "threshold_critical": 0.05,  # 5%
                "window_minutes": 5,
                "min_requests": 100,
            },
            "resource_usage_analysis": {
                "cpu_warning": 70.0,
                "cpu_critical": 90.0,
                "memory_warning": 80.0,
                "memory_critical": 95.0,
                "disk_warning": 85.0,
                "disk_critical": 95.0,
            },
            "query_performance_analysis": {
                "slow_query_threshold": 1.0,  # 1 second
                "complex_query_threshold": 5.0,  # 5 seconds
                "failing_query_rate": 0.1,  # 10%
            },
            "cache_analysis": {
                "hit_rate_warning": 0.7,  # 70%
                "hit_rate_critical": 0.5,  # 50%
                "window_minutes": 10,
            },
            "memory_leak_detection": {
                "growth_rate_threshold": 0.1,  # 10% growth per hour
                "window_hours": 2,
                "min_samples": 20,
            },
        }

    async def add_metric(self, metric: PerformanceMetric):
        """Add a performance metric for analysis"""
        metric_key = f"{metric.component}:{metric.name}"

        # Add to history
        self.metrics_history[metric_key].append(metric)

        # Trigger analysis if enough data is available
        await self._analyze_metric(metric_key)

    async def _analyze_metric(self, metric_key: str):
        """Analyze a specific metric for performance issues"""
        metrics = list(self.metrics_history[metric_key])

        if len(metrics) < 5:  # Need minimum samples for analysis
            return

        component, metric_name = metric_key.split(":", 1)

        # Determine analysis type based on metric name
        if "latency" in metric_name.lower() or "duration" in metric_name.lower():
            await self._analyze_latency(component, metric_name, metrics)
        elif "error" in metric_name.lower():
            await self._analyze_error_rate(component, metric_name, metrics)
        elif "cpu" in metric_name.lower():
            await self._analyze_cpu_usage(component, metric_name, metrics)
        elif "memory" in metric_name.lower():
            await self._analyze_memory_usage(component, metric_name, metrics)
        elif "cache" in metric_name.lower():
            await self._analyze_cache_performance(component, metric_name, metrics)

    async def _analyze_latency(
        self, component: str, metric_name: str, metrics: List[PerformanceMetric]
    ):
        """Analyze latency metrics"""
        values = [m.value for m in metrics]

        if len(values) < self.analysis_rules["latency_analysis"]["min_samples"]:
            return

        # Calculate percentiles
        p95 = np.percentile(values, 95)
        p99 = np.percentile(values, 99)

        # Check against thresholds
        p95_threshold = self.analysis_rules["latency_analysis"]["threshold_p95"]
        p99_threshold = self.analysis_rules["latency_analysis"]["threshold_p99"]

        if p99 > p99_threshold:
            severity = Severity.CRITICAL
            description = f"99th percentile latency ({p99:.2f}ms) exceeds critical threshold ({p99_threshold}ms)"
        elif p95 > p95_threshold:
            severity = Severity.HIGH
            description = f"95th percentile latency ({p95:.2f}ms) exceeds warning threshold ({p95_threshold}ms)"
        else:
            return  # No issue detected

        # Create performance issue
        issue = PerformanceIssue(
            id=f"latency_{component}_{metric_name}_{int(time.time())}",
            type=PerformanceIssueType.HIGH_LATENCY,
            severity=severity,
            title=f"High latency detected in {component}",
            description=description,
            component=component,
            metric_name=metric_name,
            current_value=p99,
            threshold_value=p99_threshold,
            context={
                "p95": p95,
                "p99": p99,
                "sample_count": len(values),
                "avg": statistics.mean(values),
            },
        )

        # Add recommendations
        issue.recommendations = self._get_latency_recommendations(
            component, metric_name, p99
        )

        self.performance_issues.append(issue)
        await self._notify_performance_issue(issue)

    async def _analyze_error_rate(
        self, component: str, metric_name: str, metrics: List[PerformanceMetric]
    ):
        """Analyze error rate metrics"""
        values = [m.value for m in metrics]

        if len(values) < 10:
            return

        avg_error_rate = statistics.mean(values)

        # Check against thresholds
        critical_threshold = self.analysis_rules["error_rate_analysis"][
            "threshold_critical"
        ]
        warning_threshold = self.analysis_rules["error_rate_analysis"][
            "threshold_warning"
        ]

        if avg_error_rate > critical_threshold:
            severity = Severity.CRITICAL
            description = f"Error rate ({avg_error_rate:.2%}) exceeds critical threshold ({critical_threshold:.2%})"
        elif avg_error_rate > warning_threshold:
            severity = Severity.HIGH
            description = f"Error rate ({avg_error_rate:.2%}) exceeds warning threshold ({warning_threshold:.2%})"
        else:
            return  # No issue detected

        # Create performance issue
        issue = PerformanceIssue(
            id=f"error_rate_{component}_{metric_name}_{int(time.time())}",
            type=PerformanceIssueType.HIGH_ERROR_RATE,
            severity=severity,
            title=f"High error rate detected in {component}",
            description=description,
            component=component,
            metric_name=metric_name,
            current_value=avg_error_rate,
            threshold_value=warning_threshold,
            context={
                "avg_error_rate": avg_error_rate,
                "sample_count": len(values),
                "max_error_rate": max(values),
            },
        )

        # Add recommendations
        issue.recommendations = self._get_error_rate_recommendations(
            component, metric_name, avg_error_rate
        )

        self.performance_issues.append(issue)
        await self._notify_performance_issue(issue)

    async def _analyze_cpu_usage(
        self, component: str, metric_name: str, metrics: List[PerformanceMetric]
    ):
        """Analyze CPU usage metrics"""
        values = [m.value for m in metrics]

        if len(values) < 10:
            return

        avg_cpu = statistics.mean(values)
        max_cpu = max(values)

        # Check against thresholds
        critical_threshold = self.analysis_rules["resource_usage_analysis"][
            "cpu_critical"
        ]
        warning_threshold = self.analysis_rules["resource_usage_analysis"][
            "cpu_warning"
        ]

        if max_cpu > critical_threshold:
            severity = Severity.CRITICAL
            description = f"CPU usage ({max_cpu:.1f}%) exceeds critical threshold ({critical_threshold:.1f}%)"
        elif avg_cpu > warning_threshold:
            severity = Severity.HIGH
            description = f"Average CPU usage ({avg_cpu:.1f}%) exceeds warning threshold ({warning_threshold:.1f}%)"
        else:
            return  # No issue detected

        # Create performance issue
        issue = PerformanceIssue(
            id=f"cpu_{component}_{metric_name}_{int(time.time())}",
            type=PerformanceIssueType.CPU_BOTTLENECK,
            severity=severity,
            title=f"CPU bottleneck detected in {component}",
            description=description,
            component=component,
            metric_name=metric_name,
            current_value=max_cpu,
            threshold_value=warning_threshold,
            context={
                "avg_cpu": avg_cpu,
                "max_cpu": max_cpu,
                "sample_count": len(values),
            },
        )

        # Add recommendations
        issue.recommendations = self._get_cpu_recommendations(component, max_cpu)

        self.performance_issues.append(issue)
        await self._notify_performance_issue(issue)

    async def _analyze_memory_usage(
        self, component: str, metric_name: str, metrics: List[PerformanceMetric]
    ):
        """Analyze memory usage metrics"""
        values = [m.value for m in metrics]

        if len(values) < 20:
            return

        # Check for memory leaks
        time_values = [(m.timestamp, m.value) for m in metrics]
        time_values.sort(key=lambda x: x[0])

        # Calculate growth rate
        if len(time_values) >= 2:
            start_time, start_value = time_values[0]
            end_time, end_value = time_values[-1]

            time_diff_hours = (end_time - start_time).total_seconds() / 3600
            if time_diff_hours > 0:
                growth_rate = (end_value - start_value) / start_value / time_diff_hours
            else:
                growth_rate = 0
        else:
            growth_rate = 0

        # Check current usage
        current_usage = values[-1]
        critical_threshold = self.analysis_rules["resource_usage_analysis"][
            "memory_critical"
        ]
        warning_threshold = self.analysis_rules["resource_usage_analysis"][
            "memory_warning"
        ]

        issues = []

        # Check for high memory usage
        if current_usage > critical_threshold:
            issues.append(
                (
                    Severity.CRITICAL,
                    f"Memory usage ({current_usage:.1f}%) exceeds critical threshold ({critical_threshold:.1f}%)",
                    PerformanceIssueType.RESOURCE_EXHAUSTION,
                )
            )
        elif current_usage > warning_threshold:
            issues.append(
                (
                    Severity.HIGH,
                    f"Memory usage ({current_usage:.1f}%) exceeds warning threshold ({warning_threshold:.1f}%)",
                    PerformanceIssueType.RESOURCE_EXHAUSTION,
                )
            )

        # Check for memory leak
        leak_threshold = self.analysis_rules["memory_leak_detection"][
            "growth_rate_threshold"
        ]
        if growth_rate > leak_threshold:
            leak_severity = (
                Severity.CRITICAL if growth_rate > leak_threshold * 2 else Severity.HIGH
            )
            issues.append(
                (
                    leak_severity,
                    f"Potential memory leak detected - growth rate: {growth_rate:.2%}/hour",
                    PerformanceIssueType.MEMORY_LEAK,
                )
            )

        # Create issues
        for severity, description, issue_type in issues:
            issue = PerformanceIssue(
                id=f"memory_{component}_{metric_name}_{int(time.time())}_{len(issues)}",
                type=issue_type,
                severity=severity,
                title=f"Memory issue detected in {component}",
                description=description,
                component=component,
                metric_name=metric_name,
                current_value=current_usage,
                threshold_value=warning_threshold,
                context={
                    "current_usage": current_usage,
                    "growth_rate": growth_rate,
                    "sample_count": len(values),
                },
            )

            issue.recommendations = self._get_memory_recommendations(
                component, current_usage, growth_rate
            )
            self.performance_issues.append(issue)
            await self._notify_performance_issue(issue)

    async def _analyze_cache_performance(
        self, component: str, metric_name: str, metrics: List[PerformanceMetric]
    ):
        """Analyze cache performance metrics"""
        if "hit_rate" not in metric_name.lower():
            return

        values = [m.value for m in metrics]

        if len(values) < 10:
            return

        avg_hit_rate = statistics.mean(values)

        # Check against thresholds
        critical_threshold = self.analysis_rules["cache_analysis"]["hit_rate_critical"]
        warning_threshold = self.analysis_rules["cache_analysis"]["hit_rate_warning"]

        if avg_hit_rate < critical_threshold:
            severity = Severity.CRITICAL
            description = f"Cache hit rate ({avg_hit_rate:.2%}) below critical threshold ({critical_threshold:.2%})"
        elif avg_hit_rate < warning_threshold:
            severity = Severity.HIGH
            description = f"Cache hit rate ({avg_hit_rate:.2%}) below warning threshold ({warning_threshold:.2%})"
        else:
            return  # No issue detected

        # Create performance issue
        issue = PerformanceIssue(
            id=f"cache_{component}_{metric_name}_{int(time.time())}",
            type=PerformanceIssueType.CACHE_MISS,
            severity=severity,
            title=f"Low cache hit rate in {component}",
            description=description,
            component=component,
            metric_name=metric_name,
            current_value=avg_hit_rate,
            threshold_value=warning_threshold,
            context={"avg_hit_rate": avg_hit_rate, "sample_count": len(values)},
        )

        # Add recommendations
        issue.recommendations = self._get_cache_recommendations(component, avg_hit_rate)

        self.performance_issues.append(issue)
        await self._notify_performance_issue(issue)

    def _get_latency_recommendations(
        self, component: str, metric_name: str, latency_ms: float
    ) -> List[str]:
        """Get latency optimization recommendations"""
        recommendations = []

        if latency_ms > 5000:  # > 5 seconds
            recommendations.extend(
                [
                    "Investigate timeout configurations and increase if necessary",
                    "Check for blocking operations in the critical path",
                    "Consider implementing circuit breakers for external dependencies",
                    "Review and optimize database queries with EXPLAIN ANALYZE",
                ]
            )
        elif latency_ms > 2000:  # > 2 seconds
            recommendations.extend(
                [
                    "Add database indexes for frequently queried fields",
                    "Implement request/response caching where appropriate",
                    "Consider connection pooling for database connections",
                    "Review and optimize algorithm complexity",
                ]
            )
        else:  # > 1 second
            recommendations.extend(
                [
                    "Enable query result caching",
                    "Optimize database queries and add missing indexes",
                    "Consider implementing async processing for non-critical operations",
                    "Monitor and optimize network latency",
                ]
            )

        return recommendations

    def _get_error_rate_recommendations(
        self, component: str, metric_name: str, error_rate: float
    ) -> List[str]:
        """Get error rate optimization recommendations"""
        recommendations = []

        if error_rate > 0.05:  # > 5%
            recommendations.extend(
                [
                    "Immediate investigation required - system stability at risk",
                    "Implement circuit breakers to prevent cascading failures",
                    "Add comprehensive error logging and monitoring",
                    "Review recent deployments for potential issues",
                ]
            )
        elif error_rate > 0.01:  # > 1%
            recommendations.extend(
                [
                    "Investigate error patterns and root causes",
                    "Implement retry logic with exponential backoff",
                    "Add input validation to prevent invalid requests",
                    "Review resource limits and capacity planning",
                ]
            )

        recommendations.extend(
            [
                "Set up automated alerts for error rate thresholds",
                "Implement chaos engineering to test system resilience",
                "Add comprehensive error handling and recovery mechanisms",
                "Consider implementing request timeouts and retries",
            ]
        )

        return recommendations

    def _get_cpu_recommendations(self, component: str, cpu_usage: float) -> List[str]:
        """Get CPU optimization recommendations"""
        recommendations = []

        if cpu_usage > 90:
            recommendations.extend(
                [
                    "Immediate action required - CPU usage critically high",
                    "Scale horizontally by adding more instances",
                    "Implement CPU-intensive task offloading to background workers",
                    "Profile the application to identify CPU bottlenecks",
                ]
            )
        elif cpu_usage > 70:
            recommendations.extend(
                [
                    "Monitor CPU trends and prepare for scaling",
                    "Optimize CPU-intensive algorithms and operations",
                    "Consider implementing caching to reduce computational load",
                    "Review thread pool configurations and concurrency settings",
                ]
            )

        recommendations.extend(
            [
                "Use async/await patterns for I/O-bound operations",
                "Implement proper connection pooling",
                "Consider using more efficient data structures",
                "Profile the application to identify optimization opportunities",
            ]
        )

        return recommendations

    def _get_memory_recommendations(
        self, component: str, memory_usage: float, growth_rate: float
    ) -> List[str]:
        """Get memory optimization recommendations"""
        recommendations = []

        if growth_rate > 0.1:  # > 10% growth per hour
            recommendations.extend(
                [
                    "Potential memory leak detected - investigate immediately",
                    "Use memory profiling tools to identify leak sources",
                    "Review object lifecycle and cleanup procedures",
                    "Implement memory usage monitoring and alerts",
                ]
            )

        if memory_usage > 90:
            recommendations.extend(
                [
                    "Critical memory usage - immediate action required",
                    "Scale vertically by increasing available memory",
                    "Implement memory caching and cleanup strategies",
                    "Review memory-intensive operations and optimize them",
                ]
            )
        elif memory_usage > 80:
            recommendations.extend(
                [
                    "Monitor memory usage trends and plan accordingly",
                    "Optimize memory usage through better data structures",
                    "Implement memory pooling for frequently allocated objects",
                    "Review garbage collection settings and tuning",
                ]
            )

        recommendations.extend(
            [
                "Use memory-efficient data structures and algorithms",
                "Implement proper object disposal and cleanup",
                "Consider using streaming for large data processing",
                "Regularly profile memory usage to identify optimization opportunities",
            ]
        )

        return recommendations

    def _get_cache_recommendations(self, component: str, hit_rate: float) -> List[str]:
        """Get cache optimization recommendations"""
        recommendations = []

        if hit_rate < 0.5:  # < 50%
            recommendations.extend(
                [
                    "Critically low cache hit rate - review caching strategy",
                    "Increase cache size if memory allows",
                    "Review cache key generation and invalidation logic",
                    "Consider implementing multi-level caching",
                ]
            )
        elif hit_rate < 0.7:  # < 70%
            recommendations.extend(
                [
                    "Low cache hit rate - optimization needed",
                    "Review cache TTL settings and expiration policies",
                    "Implement cache warming strategies",
                    "Analyze cache access patterns for optimization",
                ]
            )

        recommendations.extend(
            [
                "Implement cache prefetching for frequently accessed data",
                "Use appropriate cache eviction policies (LRU, LFU, etc.)",
                "Monitor cache size and memory usage",
                "Consider implementing distributed caching for scalability",
            ]
        )

        return recommendations

    async def _notify_performance_issue(self, issue: PerformanceIssue):
        """Notify about detected performance issue"""
        logger.warning(
            f"Performance issue detected: {issue.title}",
            context={
                "issue_id": issue.id,
                "severity": issue.severity.value,
                "type": issue.type.value,
                "component": issue.component,
                "current_value": issue.current_value,
                "threshold_value": issue.threshold_value,
            },
        )

        # Record metrics
        business_metrics.increment_counter(
            "performance_issues_total",
            {
                "type": issue.type.value,
                "severity": issue.severity.value,
                "component": issue.component,
            },
        )

        # Add to OpenTelemetry
        otel_manager.set_span_attribute("performance.issue.id", issue.id)
        otel_manager.set_span_attribute(
            "performance.issue.severity", issue.severity.value
        )

    def create_baseline(
        self, name: str, component: str, description: str = ""
    ) -> PerformanceBaseline:
        """Create a performance baseline"""
        baseline = PerformanceBaseline(
            name=name, component=component, description=description
        )

        # Calculate baseline metrics from recent history
        for metric_key, metrics in self.metrics_history.items():
            key_component, metric_name = metric_key.split(":", 1)
            if key_component == component and len(metrics) >= 10:
                values = [m.value for m in list(metrics)[-100:]]  # Last 100 values

                baseline.metrics[metric_name] = {
                    "avg": statistics.mean(values),
                    "p50": np.percentile(values, 50),
                    "p95": np.percentile(values, 95),
                    "p99": np.percentile(values, 99),
                    "min": min(values),
                    "max": max(values),
                    "std": statistics.stdev(values) if len(values) > 1 else 0,
                }

        self.baselines[name] = baseline
        return baseline

    def compare_with_baseline(self, baseline_name: str) -> Dict[str, Any]:
        """Compare current performance with baseline"""
        if baseline_name not in self.baselines:
            raise ValueError(f"Baseline '{baseline_name}' not found")

        baseline = self.baselines[baseline_name]
        comparison = {
            "baseline_name": baseline_name,
            "baseline_created": baseline.created_at.isoformat(),
            "component": baseline.component,
            "comparisons": {},
            "overall_degradation": 0.0,
            "issues_found": [],
        }

        total_degradation = 0
        metric_count = 0

        for metric_name, baseline_stats in baseline.metrics.items():
            metric_key = f"{baseline.component}:{metric_name}"

            if (
                metric_key in self.metrics_history
                and len(self.metrics_history[metric_key]) >= 10
            ):
                recent_metrics = list(self.metrics_history[metric_key])[-50:]
                recent_values = [m.value for m in recent_metrics]

                current_avg = statistics.mean(recent_values)
                baseline_avg = baseline_stats["avg"]

                # Calculate percentage change
                if baseline_avg > 0:
                    change_percent = ((current_avg - baseline_avg) / baseline_avg) * 100
                else:
                    change_percent = 0

                # Determine if it's a degradation
                is_degradation = False
                if (
                    "latency" in metric_name.lower()
                    or "duration" in metric_name.lower()
                ):
                    is_degradation = (
                        change_percent > 20
                    )  # 20% increase in latency is bad
                elif "error" in metric_name.lower():
                    is_degradation = (
                        change_percent > 50
                    )  # 50% increase in error rate is bad
                elif "hit_rate" in metric_name.lower():
                    is_degradation = (
                        change_percent < -20
                    )  # 20% decrease in hit rate is bad

                comparison["comparisons"][metric_name] = {
                    "baseline_avg": baseline_avg,
                    "current_avg": current_avg,
                    "change_percent": change_percent,
                    "is_degradation": is_degradation,
                    "baseline_p95": baseline_stats.get("p95"),
                    "current_p95": np.percentile(recent_values, 95),
                }

                if is_degradation:
                    total_degradation += abs(change_percent)
                    metric_count += 1
                    comparison["issues_found"].append(
                        {
                            "metric": metric_name,
                            "change_percent": change_percent,
                            "baseline_avg": baseline_avg,
                            "current_avg": current_avg,
                        }
                    )

        # Calculate overall degradation score
        if metric_count > 0:
            comparison["overall_degradation"] = total_degradation / metric_count

        return comparison

    def generate_optimization_recommendations(self) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations based on performance analysis"""
        recommendations = []

        # Analyze recent performance issues
        recent_issues = [
            issue
            for issue in self.performance_issues
            if (datetime.utcnow() - issue.timestamp).total_seconds() < 3600  # Last hour
        ]

        # Group issues by component
        issues_by_component = defaultdict(list)
        for issue in recent_issues:
            issues_by_component[issue.component].append(issue)

        # Generate recommendations for each component
        for component, issues in issues_by_component.items():
            if not issues:
                continue

            # Determine most common issue types
            issue_types = defaultdict(int)
            for issue in issues:
                issue_types[issue.type] += 1

            # Generate recommendations based on issue types
            for issue_type, count in issue_types.items():
                recommendation = self._create_optimization_recommendation(
                    component, issue_type, issues
                )
                if recommendation:
                    recommendations.append(recommendation)

        # Sort by priority (higher priority first)
        recommendations.sort(key=lambda x: x.priority, reverse=True)
        self.recommendations = recommendations[:20]  # Keep top 20 recommendations

        return recommendations

    def _create_optimization_recommendation(
        self,
        component: str,
        issue_type: PerformanceIssueType,
        issues: List[PerformanceIssue],
    ) -> Optional[OptimizationRecommendation]:
        """Create optimization recommendation for specific issue type"""
        if issue_type == PerformanceIssueType.HIGH_LATENCY:
            return OptimizationRecommendation(
                id=f"latency_opt_{component}_{int(time.time())}",
                title=f"Optimize latency for {component}",
                description=f"Reduce latency in {component} by implementing caching and query optimization",
                category="performance",
                priority=8,
                estimated_impact="20-40% latency reduction",
                implementation_effort="medium",
                component=component,
                metrics_affected=["response_time", "p95_latency", "p99_latency"],
                steps=[
                    "Profile the application to identify bottlenecks",
                    "Add appropriate database indexes",
                    "Implement response caching",
                    "Optimize algorithm complexity",
                    "Add connection pooling",
                ],
                code_examples={
                    "database_indexing": "-- Add index for frequently queried column\nCREATE INDEX idx_user_email ON users(email);",
                    "caching": "# Redis caching example\n@cache.memoize(timeout=300)\ndef get_user_data(user_id):\n    return database.query_user(user_id)",
                },
            )

        elif issue_type == PerformanceIssueType.CPU_BOTTLENECK:
            return OptimizationRecommendation(
                id=f"cpu_opt_{component}_{int(time.time())}",
                title=f"Optimize CPU usage for {component}",
                description=f"Reduce CPU usage in {component} through algorithm optimization and async processing",
                category="resource",
                priority=7,
                estimated_impact="30-50% CPU usage reduction",
                implementation_effort="medium",
                component=component,
                metrics_affected=["cpu_usage", "request_duration"],
                steps=[
                    "Profile CPU usage to identify hotspots",
                    "Implement async/await for I/O operations",
                    "Optimize algorithms and data structures",
                    "Consider using compiled extensions for critical paths",
                    "Implement background processing for heavy tasks",
                ],
                code_examples={
                    "async_processing": "# Async processing example\nasync def process_data(data):\n    async with aiohttp.ClientSession() as session:\n        tasks = [fetch_item(session, item) for item in data]\n        return await asyncio.gather(*tasks)"
                },
            )

        elif issue_type == PerformanceIssueType.CACHE_MISS:
            return OptimizationRecommendation(
                id=f"cache_opt_{component}_{int(time.time())}",
                title=f"Improve caching strategy for {component}",
                description=f"Optimize cache hit rate in {component} by improving caching strategy",
                category="caching",
                priority=6,
                estimated_impact="40-60% cache hit rate improvement",
                implementation_effort="low",
                component=component,
                metrics_affected=["cache_hit_rate", "response_time", "database_load"],
                steps=[
                    "Analyze cache access patterns",
                    "Optimize cache TTL settings",
                    "Implement cache warming",
                    "Use appropriate cache eviction policies",
                    "Consider multi-level caching",
                ],
                code_examples={
                    "cache_warming": "# Cache warming example\nasync def warm_cache():\n    popular_items = await get_popular_items()\n    for item in popular_items:\n        await cache.set(f'item:{item.id}', item)"
                },
            )

        return None

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        now = datetime.utcnow()

        # Recent issues (last 24 hours)
        recent_issues = [
            issue
            for issue in self.performance_issues
            if (now - issue.timestamp).total_seconds() < 86400
        ]

        # Issues by severity
        issues_by_severity = defaultdict(int)
        for issue in recent_issues:
            issues_by_severity[issue.severity.value] += 1

        # Issues by type
        issues_by_type = defaultdict(int)
        for issue in recent_issues:
            issues_by_type[issue.type.value] += 1

        # Issues by component
        issues_by_component = defaultdict(int)
        for issue in recent_issues:
            issues_by_component[issue.component] += 1

        return {
            "timestamp": now.isoformat(),
            "total_metrics_tracked": len(self.metrics_history),
            "recent_issues_24h": len(recent_issues),
            "issues_by_severity": dict(issues_by_severity),
            "issues_by_type": dict(issues_by_type),
            "issues_by_component": dict(issues_by_component),
            "baselines_created": len(self.baselines),
            "recommendations_count": len(self.recommendations),
            "last_analysis": self._last_analysis.isoformat()
            if self._last_analysis
            else None,
            "top_performing_components": self._get_top_performing_components(),
            "components_needing_attention": self._get_components_needing_attention(),
        }

    def _get_top_performing_components(self) -> List[Dict[str, Any]]:
        """Get top performing components based on metrics"""
        component_scores = defaultdict(list)

        # Calculate performance scores for each component
        for metric_key, metrics in self.metrics_history.items():
            if len(metrics) < 10:
                continue

            component = metric_key.split(":")[0]
            recent_values = [m.value for m in list(metrics)[-50:]]

            # Calculate score based on metric type
            if "latency" in metric_key.lower() or "duration" in metric_key.lower():
                # Lower is better for latency
                avg_value = statistics.mean(recent_values)
                score = max(0, 100 - (avg_value / 100))  # Normalize to 0-100
            elif "error" in metric_key.lower():
                # Lower is better for error rate
                avg_value = statistics.mean(recent_values)
                score = max(0, 100 - (avg_value * 100))
            elif "hit_rate" in metric_key.lower():
                # Higher is better for hit rate
                avg_value = statistics.mean(recent_values)
                score = avg_value * 100
            else:
                # Assume higher is better
                avg_value = statistics.mean(recent_values)
                score = min(100, avg_value)

            component_scores[component].append(score)

        # Calculate average scores
        component_avg_scores = {}
        for component, scores in component_scores.items():
            component_avg_scores[component] = statistics.mean(scores)

        # Return top 5 components
        sorted_components = sorted(
            component_avg_scores.items(), key=lambda x: x[1], reverse=True
        )
        return [
            {"component": component, "score": score}
            for component, score in sorted_components[:5]
        ]

    def _get_components_needing_attention(self) -> List[Dict[str, Any]]:
        """Get components that need attention based on performance issues"""
        now = datetime.utcnow()

        # Count recent issues by component
        component_issues = defaultdict(list)
        for issue in self.performance_issues:
            if (now - issue.timestamp).total_seconds() < 86400:  # Last 24 hours
                component_issues[issue.component].append(issue)

        # Calculate attention score
        components_needing_attention = []
        for component, issues in component_issues.items():
            if not issues:
                continue

            # Calculate attention score based on issue severity and count
            score = 0
            for issue in issues:
                if issue.severity == Severity.CRITICAL:
                    score += 10
                elif issue.severity == Severity.HIGH:
                    score += 5
                elif issue.severity == Severity.MEDIUM:
                    score += 2
                else:
                    score += 1

            components_needing_attention.append(
                {
                    "component": component,
                    "attention_score": score,
                    "issue_count": len(issues),
                    "critical_issues": len(
                        [i for i in issues if i.severity == Severity.CRITICAL]
                    ),
                    "most_common_issue": max(
                        set(i.type.value for i in issues),
                        key=lambda x: sum(1 for i in issues if i.type.value == x),
                    ),
                }
            )

        # Sort by attention score (highest first)
        components_needing_attention.sort(
            key=lambda x: x["attention_score"], reverse=True
        )
        return components_needing_attention[:10]


# Global performance analyzer instance
performance_analyzer = PerformanceAnalyzer()


# Convenience functions
async def add_performance_metric(
    name: str,
    value: float,
    unit: str,
    component: str = "",
    labels: Optional[Dict[str, str]] = None,
):
    """Add a performance metric for analysis"""
    metric = PerformanceMetric(
        name=name,
        value=value,
        timestamp=datetime.utcnow(),
        unit=unit,
        component=component,
        labels=labels or {},
    )
    await performance_analyzer.add_metric(metric)


def create_performance_baseline(
    name: str, component: str, description: str = ""
) -> PerformanceBaseline:
    """Create a performance baseline"""
    return performance_analyzer.create_baseline(name, component, description)


def get_performance_summary() -> Dict[str, Any]:
    """Get comprehensive performance summary"""
    return performance_analyzer.get_performance_summary()
