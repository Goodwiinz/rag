"""
Analytics recommendation generator
Generates intelligent recommendations based on analytics data
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models.analytics_event import AnalyticsEvent, EventType
from src.models.organization import Organization
from src.models.performance_log import MetricCategory, PerformanceLevel, PerformanceLog
from src.models.user import User
from src.models.user_session import SessionStatus, UserSession

logger = logging.getLogger(__name__)


class RecommendationType(str, Enum):
    """Types of recommendations"""

    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    USER_ENGAGEMENT = "user_engagement"
    SEARCH_QUALITY = "search_quality"
    CONTENT_OPTIMIZATION = "content_optimization"
    SYSTEM_HEALTH = "system_health"
    COST_OPTIMIZATION = "cost_optimization"
    SECURITY_IMPROVEMENT = "security_improvement"


class RecommendationPriority(str, Enum):
    """Priority levels for recommendations"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Recommendation:
    """Analytics recommendation"""

    type: RecommendationType
    title: str
    description: str
    priority: RecommendationPriority
    impact_score: float  # 0-100
    effort_estimate: str  # low, medium, high
    metrics: List[str]  # Metrics that triggered this recommendation
    suggested_actions: List[str]
    expected_outcome: str
    data_evidence: Dict[str, Any]
    created_at: datetime


class AnalyticsRecommendationGenerator:
    """Generates recommendations based on analytics data"""

    def __init__(self, db: Session):
        self.db = db

    async def generate_recommendations(
        self,
        organization_id: str,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        recommendation_types: Optional[List[RecommendationType]] = None,
    ) -> List[Recommendation]:
        """Generate recommendations for an organization"""
        if not time_range:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)  # Default to last 30 days
            time_range = (start_date, end_date)

        recommendations = []

        # Generate different types of recommendations
        if (
            not recommendation_types
            or RecommendationType.PERFORMANCE_OPTIMIZATION in recommendation_types
        ):
            perf_recs = await self._generate_performance_recommendations(
                organization_id, time_range
            )
            recommendations.extend(perf_recs)

        if (
            not recommendation_types
            or RecommendationType.USER_ENGAGEMENT in recommendation_types
        ):
            engagement_recs = await self._generate_engagement_recommendations(
                organization_id, time_range
            )
            recommendations.extend(engagement_recs)

        if (
            not recommendation_types
            or RecommendationType.SEARCH_QUALITY in recommendation_types
        ):
            search_recs = await self._generate_search_quality_recommendations(
                organization_id, time_range
            )
            recommendations.extend(search_recs)

        if (
            not recommendation_types
            or RecommendationType.SYSTEM_HEALTH in recommendation_types
        ):
            health_recs = await self._generate_system_health_recommendations(
                organization_id, time_range
            )
            recommendations.extend(health_recs)

        # Sort by impact score and priority
        recommendations.sort(
            key=lambda r: (r.priority.value, r.impact_score), reverse=True
        )

        return recommendations

    async def _generate_performance_recommendations(
        self, organization_id: str, time_range: Tuple[datetime, datetime]
    ) -> List[Recommendation]:
        """Generate performance optimization recommendations"""
        recommendations = []
        start_date, end_date = time_range

        # Check for slow response times
        avg_response_time = (
            self.db.query(func.avg(PerformanceLog.response_time_ms))
            .filter(
                and_(
                    PerformanceLog.organization_id == organization_id,
                    PerformanceLog.timestamp >= start_date,
                    PerformanceLog.timestamp < end_date,
                    PerformanceLog.response_time_ms.isnot(None),
                )
            )
            .scalar()
            or 0
        )

        if avg_response_time > 2000:  # > 2 seconds
            impact_score = min((avg_response_time - 2000) / 50, 100)  # Scale to 0-100
            priority = (
                RecommendationPriority.CRITICAL
                if avg_response_time > 5000
                else RecommendationPriority.HIGH
            )

            recommendations.append(
                Recommendation(
                    type=RecommendationType.PERFORMANCE_OPTIMIZATION,
                    title="Optimize API Response Times",
                    description=f"Average response time is {avg_response_time:.0f}ms, which is significantly above the optimal range.",
                    priority=priority,
                    impact_score=impact_score,
                    effort_estimate="medium",
                    metrics=["response_time_ms"],
                    suggested_actions=[
                        "Implement database query optimization",
                        "Add caching for frequently accessed data",
                        "Review and optimize slow API endpoints",
                        "Consider implementing CDN for static assets",
                    ],
                    expected_outcome="Reduce average response time to under 1 second",
                    data_evidence={
                        "avg_response_time_ms": avg_response_time,
                        "period": f"{start_date.date()} to {end_date.date()}",
                        "threshold_ms": 2000,
                    },
                    created_at=datetime.utcnow(),
                )
            )

        # Check for high error rates
        total_logs = (
            self.db.query(PerformanceLog)
            .filter(
                and_(
                    PerformanceLog.organization_id == organization_id,
                    PerformanceLog.timestamp >= start_date,
                    PerformanceLog.timestamp < end_date,
                )
            )
            .count()
        )

        error_logs = (
            self.db.query(PerformanceLog)
            .filter(
                and_(
                    PerformanceLog.organization_id == organization_id,
                    PerformanceLog.timestamp >= start_date,
                    PerformanceLog.timestamp < end_date,
                    PerformanceLog.performance_level.in_(
                        [PerformanceLevel.CRITICAL, PerformanceLevel.POOR]
                    ),
                )
            )
            .count()
        )

        if total_logs > 0:
            error_rate = (error_logs / total_logs) * 100
            if error_rate > 5:  # > 5% error rate
                impact_score = min(error_rate * 10, 100)
                priority = (
                    RecommendationPriority.CRITICAL
                    if error_rate > 15
                    else RecommendationPriority.HIGH
                )

                recommendations.append(
                    Recommendation(
                        type=RecommendationType.PERFORMANCE_OPTIMIZATION,
                        title="Reduce System Error Rate",
                        description=f"Error rate is {error_rate:.1f}%, indicating system instability.",
                        priority=priority,
                        impact_score=impact_score,
                        effort_estimate="high",
                        metrics=["error_rate"],
                        suggested_actions=[
                            "Implement comprehensive error logging and monitoring",
                            "Add circuit breakers for external service calls",
                            "Improve input validation to prevent errors",
                            "Conduct root cause analysis for frequent errors",
                        ],
                        expected_outcome="Reduce error rate to under 2%",
                        data_evidence={
                            "error_rate_percentage": error_rate,
                            "total_errors": error_logs,
                            "total_requests": total_logs,
                            "period": f"{start_date.date()} to {end_date.date()}",
                        },
                        created_at=datetime.utcnow(),
                    )
                )

        # Check memory usage
        avg_memory_usage = (
            self.db.query(func.avg(PerformanceLog.memory_usage_percent))
            .filter(
                and_(
                    PerformanceLog.organization_id == organization_id,
                    PerformanceLog.timestamp >= start_date,
                    PerformanceLog.timestamp < end_date,
                    PerformanceLog.memory_usage_percent.isnot(None),
                )
            )
            .scalar()
            or 0
        )

        if avg_memory_usage > 80:  # > 80% memory usage
            impact_score = min((avg_memory_usage - 80) * 5, 100)
            priority = (
                RecommendationPriority.HIGH
                if avg_memory_usage > 90
                else RecommendationPriority.MEDIUM
            )

            recommendations.append(
                Recommendation(
                    type=RecommendationType.PERFORMANCE_OPTIMIZATION,
                    title="Optimize Memory Usage",
                    description=f"Average memory usage is {avg_memory_usage:.1f}%, approaching system limits.",
                    priority=priority,
                    impact_score=impact_score,
                    effort_estimate="medium",
                    metrics=["memory_usage_percent"],
                    suggested_actions=[
                        "Implement memory profiling to identify leaks",
                        "Optimize data structures and algorithms",
                        "Implement memory caching strategies",
                        "Consider horizontal scaling",
                    ],
                    expected_outcome="Reduce memory usage to under 70%",
                    data_evidence={
                        "avg_memory_usage_percent": avg_memory_usage,
                        "period": f"{start_date.date()} to {end_date.date()}",
                    },
                    created_at=datetime.utcnow(),
                )
            )

        return recommendations

    async def _generate_engagement_recommendations(
        self, organization_id: str, time_range: Tuple[datetime, datetime]
    ) -> List[Recommendation]:
        """Generate user engagement recommendations"""
        recommendations = []
        start_date, end_date = time_range

        # Check average session duration
        avg_duration = (
            self.db.query(func.avg(UserSession.duration_seconds))
            .filter(
                and_(
                    UserSession.organization_id == organization_id,
                    UserSession.started_at >= start_date,
                    UserSession.started_at < end_date,
                    UserSession.duration_seconds.isnot(None),
                )
            )
            .scalar()
            or 0
        )

        if avg_duration < 120:  # Less than 2 minutes
            impact_score = max(100 - (avg_duration / 2), 20)
            priority = (
                RecommendationPriority.HIGH
                if avg_duration < 60
                else RecommendationPriority.MEDIUM
            )

            recommendations.append(
                Recommendation(
                    type=RecommendationType.USER_ENGAGEMENT,
                    title="Increase User Session Duration",
                    description=f"Average session duration is {avg_duration:.0f} seconds, indicating low engagement.",
                    priority=priority,
                    impact_score=impact_score,
                    effort_estimate="medium",
                    metrics=["session_duration_seconds"],
                    suggested_actions=[
                        "Improve onboarding experience for new users",
                        "Add interactive features and engaging content",
                        "Implement personalized recommendations",
                        "Optimize user interface and navigation",
                    ],
                    expected_outcome="Increase average session duration to over 5 minutes",
                    data_evidence={
                        "avg_session_duration_seconds": avg_duration,
                        "period": f"{start_date.date()} to {end_date.date()}",
                    },
                    created_at=datetime.utcnow(),
                )
            )

        # Check bounce rate (sessions with very short duration)
        short_sessions = (
            self.db.query(UserSession)
            .filter(
                and_(
                    UserSession.organization_id == organization_id,
                    UserSession.started_at >= start_date,
                    UserSession.started_at < end_date,
                    UserSession.duration_seconds < 30,
                )
            )
            .count()
        )

        total_sessions = (
            self.db.query(UserSession)
            .filter(
                and_(
                    UserSession.organization_id == organization_id,
                    UserSession.started_at >= start_date,
                    UserSession.started_at < end_date,
                )
            )
            .count()
        )

        if total_sessions > 0:
            bounce_rate = (short_sessions / total_sessions) * 100
            if bounce_rate > 40:  # > 40% bounce rate
                impact_score = min(bounce_rate * 1.5, 100)
                priority = (
                    RecommendationPriority.CRITICAL
                    if bounce_rate > 60
                    else RecommendationPriority.HIGH
                )

                recommendations.append(
                    Recommendation(
                        type=RecommendationType.USER_ENGAGEMENT,
                        title="Reduce Bounce Rate",
                        description=f"Bounce rate is {bounce_rate:.1f}%, indicating users are leaving quickly.",
                        priority=priority,
                        impact_score=impact_score,
                        effort_estimate="high",
                        metrics=["bounce_rate"],
                        suggested_actions=[
                            "Improve page load performance",
                            "Enhance content relevance and quality",
                            "Implement better navigation and search functionality",
                            "Add engaging calls-to-action",
                        ],
                        expected_outcome="Reduce bounce rate to under 25%",
                        data_evidence={
                            "bounce_rate_percentage": bounce_rate,
                            "short_sessions": short_sessions,
                            "total_sessions": total_sessions,
                            "period": f"{start_date.date()} to {end_date.date()}",
                        },
                        created_at=datetime.utcnow(),
                    )
                )

        # Check search frequency
        total_searches = (
            self.db.query(func.sum(UserSession.total_searches))
            .filter(
                and_(
                    UserSession.organization_id == organization_id,
                    UserSession.started_at >= start_date,
                    UserSession.started_at < end_date,
                )
            )
            .scalar()
            or 0
        )

        if total_sessions > 0:
            searches_per_session = total_searches / total_sessions
            if searches_per_session < 1:  # Less than 1 search per session
                impact_score = 100 - (searches_per_session * 100)
                priority = RecommendationPriority.MEDIUM

                recommendations.append(
                    Recommendation(
                        type=RecommendationType.USER_ENGAGEMENT,
                        title="Increase Search Engagement",
                        description=f"Users average {searches_per_session:.1f} searches per session.",
                        priority=priority,
                        impact_score=impact_score,
                        effort_estimate="medium",
                        metrics=["searches_per_session"],
                        suggested_actions=[
                            "Improve search visibility and accessibility",
                            "Implement search suggestions and autocomplete",
                            "Enhance search result quality and relevance",
                            "Add advanced search features",
                        ],
                        expected_outcome="Increase to 2+ searches per session",
                        data_evidence={
                            "searches_per_session": searches_per_session,
                            "total_searches": total_searches,
                            "total_sessions": total_sessions,
                            "period": f"{start_date.date()} to {end_date.date()}",
                        },
                        created_at=datetime.utcnow(),
                    )
                )

        return recommendations

    async def _generate_search_quality_recommendations(
        self, organization_id: str, time_range: Tuple[datetime, datetime]
    ) -> List[Recommendation]:
        """Generate search quality recommendations"""
        recommendations = []
        start_date, end_date = time_range

        # Check zero-result searches
        search_events = (
            self.db.query(AnalyticsEvent)
            .filter(
                and_(
                    AnalyticsEvent.organization_id == organization_id,
                    AnalyticsEvent.event_type == EventType.SEARCH_QUERY,
                    AnalyticsEvent.event_timestamp >= start_date,
                    AnalyticsEvent.event_timestamp < end_date,
                )
            )
            .all()
        )

        if search_events:
            zero_result_searches = 0
            total_searches = len(search_events)

            for event in search_events:
                if event.event_data and event.event_data.get("results_count", 0) == 0:
                    zero_result_searches += 1

            if total_searches > 0:
                zero_result_rate = (zero_result_searches / total_searches) * 100
                if zero_result_rate > 15:  # > 15% zero results
                    impact_score = min(zero_result_rate * 4, 100)
                    priority = (
                        RecommendationPriority.HIGH
                        if zero_result_rate > 25
                        else RecommendationPriority.MEDIUM
                    )

                    recommendations.append(
                        Recommendation(
                            type=RecommendationType.SEARCH_QUALITY,
                            title="Reduce Zero-Result Searches",
                            description=f"{zero_result_rate:.1f}% of searches return no results.",
                            priority=priority,
                            impact_score=impact_score,
                            effort_estimate="high",
                            metrics=["zero_result_rate"],
                            suggested_actions=[
                                "Improve content coverage and indexing",
                                "Implement search query expansion and synonyms",
                                "Add spell checking and suggestions",
                                "Improve content metadata and tagging",
                            ],
                            expected_outcome="Reduce zero-result searches to under 5%",
                            data_evidence={
                                "zero_result_rate_percentage": zero_result_rate,
                                "zero_result_searches": zero_result_searches,
                                "total_searches": total_searches,
                                "period": f"{start_date.date()} to {end_date.date()}",
                            },
                            created_at=datetime.utcnow(),
                        )
                    )

        return recommendations

    async def _generate_system_health_recommendations(
        self, organization_id: str, time_range: Tuple[datetime, datetime]
    ) -> List[Recommendation]:
        """Generate system health recommendations"""
        recommendations = []
        start_date, end_date = time_range

        # Check for performance alerts
        recent_alerts = (
            self.db.query(PerformanceLog)
            .filter(
                and_(
                    PerformanceLog.organization_id == organization_id,
                    PerformanceLog.timestamp >= start_date,
                    PerformanceLog.timestamp < end_date,
                    PerformanceLog.alert_triggered == True,
                )
            )
            .count()
        )

        if recent_alerts > 10:  # More than 10 alerts in the period
            impact_score = min(recent_alerts * 5, 100)
            priority = (
                RecommendationPriority.CRITICAL
                if recent_alerts > 50
                else RecommendationPriority.HIGH
            )

            recommendations.append(
                Recommendation(
                    type=RecommendationType.SYSTEM_HEALTH,
                    title="Address System Performance Alerts",
                    description=f"{recent_alerts} performance alerts detected in the analysis period.",
                    priority=priority,
                    impact_score=impact_score,
                    effort_estimate="high",
                    metrics=["performance_alerts"],
                    suggested_actions=[
                        "Implement proactive monitoring and alerting",
                        "Investigate root causes of performance issues",
                        "Add automated scaling and load balancing",
                        "Establish performance baselines and thresholds",
                    ],
                    expected_outcome="Reduce performance alerts by 80%",
                    data_evidence={
                        "alert_count": recent_alerts,
                        "period": f"{start_date.date()} to {end_date.date()}",
                    },
                    created_at=datetime.utcnow(),
                )
            )

        return recommendations

    def format_recommendations(
        self, recommendations: List[Recommendation]
    ) -> Dict[str, Any]:
        """Format recommendations for API response"""
        return {
            "recommendations": [
                {
                    "id": idx,
                    "type": rec.type.value,
                    "title": rec.title,
                    "description": rec.description,
                    "priority": rec.priority.value,
                    "impact_score": rec.impact_score,
                    "effort_estimate": rec.effort_estimate,
                    "metrics": rec.metrics,
                    "suggested_actions": rec.suggested_actions,
                    "expected_outcome": rec.expected_outcome,
                    "data_evidence": rec.data_evidence,
                    "created_at": rec.created_at.isoformat(),
                }
                for idx, rec in enumerate(recommendations)
            ],
            "summary": {
                "total_recommendations": len(recommendations),
                "by_priority": {
                    priority.value: len(
                        [r for r in recommendations if r.priority == priority]
                    )
                    for priority in RecommendationPriority
                },
                "by_type": {
                    rec_type.value: len(
                        [r for r in recommendations if r.type == rec_type]
                    )
                    for rec_type in RecommendationType
                },
                "avg_impact_score": sum(r.impact_score for r in recommendations)
                / len(recommendations)
                if recommendations
                else 0,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def save_recommendations(
        self, organization_id: str, recommendations: List[Recommendation]
    ) -> str:
        """Save recommendations to database or storage"""
        # This would typically save to a recommendations table
        # For now, return a summary
        summary = self.format_recommendations(recommendations)

        logger.info(
            f"Generated {len(recommendations)} recommendations for organization {organization_id}"
        )

        return json.dumps(summary, default=str)


# Global recommendation generator
recommendation_generator = AnalyticsRecommendationGenerator
