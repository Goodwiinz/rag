"""
Quality metrics collection and monitoring service
"""

import asyncio
import logging
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_, func

from src.core.database import get_db
from src.models.quality import QualityMetric
from src.models.quality_metrics import (
    QualityAlert, MetricAggregation,
    SearchSession, SearchEvent, SystemMetric, QualityThreshold,
    MetricType, AlertSeverity
)
from src.models.search_schemas import SearchResponse, SearchResult
from src.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class MetricCalculation:
    """Metric calculation result"""
    metric_type: str
    value: float
    unit: str
    threshold_min: Optional[float] = None
    threshold_max: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class QualityMetricsService:
    """
    Service for collecting, processing, and monitoring quality metrics
    """

    def __init__(self):
        self.background_tasks = set()
        self.alert_cooldowns = {}  # Track alert cooldowns

    async def collect_search_metrics(
        self,
        search_response: SearchResponse,
        search_query: str,
        search_type: str,
        user_id: str,
        organization_id: str,
        query_id: str = None
    ) -> List[QualityMetric]:
        """
        Collect quality metrics for a search query
        """
        try:
            db = next(get_db())
            metrics = []

            # Calculate various quality metrics
            metric_calculations = self._calculate_search_quality_metrics(
                search_response, search_query, search_type
            )

            for calc in metric_calculations:
                # Get threshold configuration
                threshold = self._get_threshold(
                    db, calc.metric_type, organization_id, search_type
                )

                # Create quality metric record
                metric = QualityMetric(
                    metric_type=calc.metric_type,
                    metric_value=calc.value,
                    metric_unit=calc.unit,
                    search_query_id=query_id,
                    query=search_query,
                    search_type=search_type,
                    user_id=user_id if user_id != "anonymous" else None,
                    organization_id=organization_id,
                    metadata=calc.metadata,
                    threshold_min=threshold.threshold_min if threshold else None,
                    threshold_max=threshold.threshold_max if threshold else None,
                    measured_at=datetime.utcnow()
                )

                # Check for threshold violations
                if threshold:
                    metric.is_threshold_violation = self._check_threshold_violation(
                        calc.value, threshold.threshold_min, threshold.threshold_max
                    )

                db.add(metric)
                metrics.append(metric)

                # Create alert if threshold violated
                if metric.is_threshold_violation:
                    await self._create_threshold_alert(db, metric, threshold)

            db.commit()

            # Schedule background processing for this metric set
            task = asyncio.create_task(
                self._process_metrics_background(metrics)
            )
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

            return metrics

        except Exception as e:
            logger.error(f"Error collecting search metrics: {e}")
            db.rollback()
            raise

    def _calculate_search_quality_metrics(
        self,
        search_response: SearchResponse,
        query: str,
        search_type: str
    ) -> List[MetricCalculation]:
        """
        Calculate various quality metrics for search results
        """
        calculations = []

        # Response time metric
        calculations.append(MetricCalculation(
            metric_type=MetricType.RESPONSE_TIME.value,
            value=getattr(search_response, 'query_time_ms', 0.0),
            unit="ms",
            metadata={"search_type": search_type, "result_count": len(search_response.results)}
        ))

        # Result count metric
        calculations.append(MetricCalculation(
            metric_type="result_count",
            value=len(search_response.results),
            unit="count",
            metadata={"search_type": search_type}
        ))

        # Result diversity metric (if we have results)
        if search_response.results:
            diversity_score = self._calculate_result_diversity(search_response.results)
            calculations.append(MetricCalculation(
                metric_type=MetricType.RESULT_DIVERSITY.value,
                value=diversity_score,
                unit="score",
                metadata={
                    "search_type": search_type,
                    "result_count": len(search_response.results),
                    "calculation_method": "content_type_diversity"
                }
            ))

        # Average relevance score
        if search_response.results:
            relevance_scores = [r.relevance_score for r in search_response.results if r.relevance_score is not None]
            if relevance_scores:
                avg_relevance = statistics.mean(relevance_scores)
                calculations.append(MetricCalculation(
                    metric_type="avg_relevance_score",
                    value=avg_relevance,
                    unit="score",
                    metadata={
                        "search_type": search_type,
                        "result_count": len(relevance_scores),
                        "min_score": min(relevance_scores),
                        "max_score": max(relevance_scores)
                    }
                ))

        # Freshness metric (based on document creation dates)
        if search_response.results:
            freshness_score = self._calculate_freshness_score(search_response.results)
            calculations.append(MetricCalculation(
                metric_type=MetricType.FRESHNESS.value,
                value=freshness_score,
                unit="days",
                metadata={
                    "search_type": search_type,
                    "result_count": len(search_response.results)
                }
            ))

        return calculations

    def _calculate_result_diversity(self, results: List[SearchResult]) -> float:
        """
        Calculate diversity score based on result characteristics
        """
        if not results:
            return 0.0

        # Simple diversity based on document types
        doc_types = set()
        for result in results:
            if result.document_type:
                doc_types.add(result.document_type.value)

        # Normalize diversity score (0-1)
        max_possible_types = 10  # Assuming max 10 different document types
        diversity_score = len(doc_types) / max_possible_types

        return min(diversity_score, 1.0)

    def _calculate_freshness_score(self, results: List[SearchResult]) -> float:
        """
        Calculate freshness score based on document ages
        """
        if not results:
            return 0.0

        current_time = datetime.utcnow()
        ages = []

        for result in results:
            if result.created_at:
                age_days = (current_time - result.created_at).days
                ages.append(age_days)

        if not ages:
            return 0.0

        # Return average age in days (lower is fresher)
        avg_age = statistics.mean(ages)
        return avg_age

    def _get_threshold(
        self,
        db: Session,
        metric_type: str,
        organization_id: str,
        search_type: str = None
    ) -> Optional[QualityThreshold]:
        """
        Get threshold configuration for a metric
        """
        return db.query(QualityThreshold).filter(
            and_(
                QualityThreshold.metric_type == metric_type,
                or_(
                    QualityThreshold.organization_id == organization_id,
                    QualityThreshold.organization_id.is_(None)
                ),
                or_(
                    QualityThreshold.search_type == search_type,
                    QualityThreshold.search_type.is_(None)
                ),
                QualityThreshold.is_enabled == True
            )
        ).order_by(
            QualityThreshold.organization_id.desc().nullslast(),
            QualityThreshold.search_type.desc().nullslast()
        ).first()

    def _check_threshold_violation(
        self,
        value: float,
        threshold_min: Optional[float],
        threshold_max: Optional[float]
    ) -> bool:
        """
        Check if a metric value violates threshold conditions
        """
        if threshold_min is not None and value < threshold_min:
            return True
        if threshold_max is not None and value > threshold_max:
            return True
        return False

    async def _create_threshold_alert(
        self,
        db: Session,
        metric: QualityMetric,
        threshold: QualityThreshold
    ):
        """
        Create an alert for threshold violation
        """
        try:
            # Check cooldown
            cooldown_key = f"{metric.organization_id}_{metric.metric_type}"
            if cooldown_key in self.alert_cooldowns:
                if datetime.utcnow() < self.alert_cooldowns[cooldown_key]:
                    return  # Still in cooldown period

            # Determine violation type and create message
            if metric.threshold_min is not None and metric.metric_value < metric.threshold_min:
                violation_type = "below minimum"
                expected_range = f"≥ {metric.threshold_min}"
            elif metric.threshold_max is not None and metric.metric_value > metric.threshold_max:
                violation_type = "above maximum"
                expected_range = f"≤ {metric.threshold_max}"
            else:
                return

            # Create alert
            alert = QualityAlert(
                metric_id=metric.id,
                severity=threshold.alert_severity,
                title=f"Quality Threshold Violation: {metric.metric_type}",
                message=(
                    f"The {metric.metric_type} metric has violated its threshold. "
                    f"Current value: {metric.metric_value:.2f} {metric.metric_unit or ''}. "
                    f"Expected range: {expected_range}. "
                    f"Query: \"{metric.query[:100]}{'...' if len(metric.query) > 100 else ''}\""
                ),
                organization_id=metric.organization_id,
                status="active"
            )

            db.add(alert)

            # Set cooldown
            cooldown_minutes = threshold.alert_cooldown_minutes or 60
            self.alert_cooldowns[cooldown_key] = datetime.utcnow() + timedelta(minutes=cooldown_minutes)

            # Log alert
            logger.warning(
                f"Quality alert created: {alert.title} for organization {metric.organization_id}"
            )

        except Exception as e:
            logger.error(f"Error creating threshold alert: {e}")

    async def _process_metrics_background(self, metrics: List[QualityMetric]):
        """
        Background processing for metrics (aggregation, analytics, etc.)
        """
        try:
            db = next(get_db())

            # Update aggregations for each metric
            for metric in metrics:
                await self._update_metric_aggregation(db, metric)

            db.commit()

        except Exception as e:
            logger.error(f"Error in background metrics processing: {e}")

    async def _update_metric_aggregation(self, db: Session, metric: QualityMetric):
        """
        Update hourly aggregation for a metric
        """
        try:
            # Calculate aggregation period (hourly)
            period_start = metric.measured_at.replace(
                minute=0, second=0, microsecond=0
            )
            period_end = period_start + timedelta(hours=1)

            # Check if aggregation exists
            aggregation = db.query(MetricAggregation).filter(
                and_(
                    MetricAggregation.metric_type == metric.metric_type,
                    MetricAggregation.aggregation_type == "hourly",
                    MetricAggregation.aggregation_period_start == period_start,
                    MetricAggregation.organization_id == metric.organization_id,
                    MetricAggregation.search_type == metric.search_type
                )
            ).first()

            if aggregation:
                # Update existing aggregation
                values = [aggregation.min_value, aggregation.max_value, metric.metric_value]
                aggregation.count_values += 1
                aggregation.sum_values += metric.metric_value
                aggregation.avg_value = aggregation.sum_values / aggregation.count_values
                aggregation.min_value = min(values)
                aggregation.max_value = max(values)
                aggregation.updated_at = datetime.utcnow()
            else:
                # Create new aggregation
                aggregation = MetricAggregation(
                    metric_type=metric.metric_type,
                    aggregation_type="hourly",
                    aggregation_period_start=period_start,
                    aggregation_period_end=period_end,
                    avg_value=metric.metric_value,
                    min_value=metric.metric_value,
                    max_value=metric.metric_value,
                    count_values=1,
                    sum_values=metric.metric_value,
                    organization_id=metric.organization_id,
                    search_type=metric.search_type
                )
                db.add(aggregation)

        except Exception as e:
            logger.error(f"Error updating metric aggregation: {e}")

    async def track_search_session(
        self,
        session_id: str,
        user_id: Optional[str],
        organization_id: str,
        user_agent: str = None,
        ip_address: str = None,
        referrer: str = None
    ) -> SearchSession:
        """
        Create or update a search session
        """
        try:
            db = next(get_db())

            # Look for existing session
            session = db.query(SearchSession).filter(
                SearchSession.session_id == session_id
            ).first()

            if session:
                # Update existing session
                session.updated_at = datetime.utcnow()
            else:
                # Create new session
                session = SearchSession(
                    session_id=session_id,
                    user_id=user_id if user_id != "anonymous" else None,
                    organization_id=organization_id,
                    user_agent=user_agent,
                    ip_address=ip_address,
                    referrer=referrer,
                    start_time=datetime.utcnow()
                )
                db.add(session)

            db.commit()
            db.refresh(session)
            return session

        except Exception as e:
            logger.error(f"Error tracking search session: {e}")
            db.rollback()
            raise

    async def record_search_event(
        self,
        session_id: str,
        query: str,
        search_type: str,
        results_count: int,
        response_time: float,
        user_id: Optional[str],
        organization_id: str,
        search_query_id: str = None,
        page_number: int = 1,
        filters_applied: Dict[str, Any] = None,
        sort_order: str = None
    ) -> SearchEvent:
        """
        Record a search event for analytics
        """
        try:
            db = next(get_db())

            # Create search event
            event = SearchEvent(
                session_id=session_id,
                search_query_id=search_query_id,
                query=query,
                search_type=search_type,
                results_count=results_count,
                response_time=response_time,
                user_id=user_id if user_id != "anonymous" else None,
                organization_id=organization_id,
                page_number=page_number,
                filters_applied=filters_applied,
                sort_order=sort_order
            )

            db.add(event)

            # Update session statistics
            session = db.query(SearchSession).filter(
                SearchSession.session_id == session_id
            ).first()

            if session:
                session.search_count += 1
                session.total_response_time += response_time
                session.avg_response_time = session.total_response_time / session.search_count
                session.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(event)
            return event

        except Exception as e:
            logger.error(f"Error recording search event: {e}")
            db.rollback()
            raise

    def get_quality_metrics(
        self,
        organization_id: str,
        metric_types: List[str] = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 1000
    ) -> List[QualityMetric]:
        """
        Get quality metrics for analytics
        """
        try:
            db = next(get_db())

            query = db.query(QualityMetric).filter(
                QualityMetric.organization_id == organization_id
            )

            if metric_types:
                query = query.filter(QualityMetric.metric_type.in_(metric_types))

            if start_time:
                query = query.filter(QualityMetric.measured_at >= start_time)

            if end_time:
                query = query.filter(QualityMetric.measured_at <= end_time)

            return query.order_by(QualityMetric.measured_at.desc()).limit(limit).all()

        except Exception as e:
            logger.error(f"Error getting quality metrics: {e}")
            return []

    def get_metric_aggregations(
        self,
        organization_id: str,
        metric_types: List[str] = None,
        aggregation_type: str = "hourly",
        start_time: datetime = None,
        end_time: datetime = None
    ) -> List[MetricAggregation]:
        """
        Get aggregated metrics for dashboard
        """
        try:
            db = next(get_db())

            query = db.query(MetricAggregation).filter(
                and_(
                    MetricAggregation.organization_id == organization_id,
                    MetricAggregation.aggregation_type == aggregation_type
                )
            )

            if metric_types:
                query = query.filter(MetricAggregation.metric_type.in_(metric_types))

            if start_time:
                query = query.filter(MetricAggregation.aggregation_period_start >= start_time)

            if end_time:
                query = query.filter(MetricAggregation.aggregation_period_end <= end_time)

            return query.order_by(MetricAggregation.aggregation_period_start.desc()).all()

        except Exception as e:
            logger.error(f"Error getting metric aggregations: {e}")
            return []

    def get_active_alerts(
        self,
        organization_id: str,
        severity: str = None
    ) -> List[QualityAlert]:
        """
        Get active quality alerts
        """
        try:
            db = next(get_db())

            query = db.query(QualityAlert).filter(
                and_(
                    QualityAlert.organization_id == organization_id,
                    QualityAlert.status == "active"
                )
            )

            if severity:
                query = query.filter(QualityAlert.severity == severity)

            return query.order_by(QualityAlert.created_at.desc()).all()

        except Exception as e:
            logger.error(f"Error getting active alerts: {e}")
            return []

    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str
    ) -> bool:
        """
        Acknowledge a quality alert
        """
        try:
            db = next(get_db())

            alert = db.query(QualityAlert).filter(
                QualityAlert.id == alert_id
            ).first()

            if alert:
                alert.status = "acknowledged"
                alert.acknowledged_at = datetime.utcnow()
                alert.acknowledged_by = acknowledged_by
                alert.updated_at = datetime.utcnow()

                db.commit()
                return True

            return False

        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            db.rollback()
            return False

    def get_search_analytics(
        self,
        organization_id: str,
        start_time: datetime = None,
        end_time: datetime = None
    ) -> Dict[str, Any]:
        """
        Get search analytics summary
        """
        try:
            db = next(get_db())

            # Default to last 7 days if no time range specified
            if not end_time:
                end_time = datetime.utcnow()
            if not start_time:
                start_time = end_time - timedelta(days=7)

            # Basic search statistics
            total_searches = db.query(SearchEvent).filter(
                and_(
                    SearchEvent.organization_id == organization_id,
                    SearchEvent.created_at >= start_time,
                    SearchEvent.created_at <= end_time
                )
            ).count()

            # Average response time
            avg_response_time = db.query(func.avg(SearchEvent.response_time)).filter(
                and_(
                    SearchEvent.organization_id == organization_id,
                    SearchEvent.created_at >= start_time,
                    SearchEvent.created_at <= end_time
                )
            ).scalar() or 0

            # Unique users
            unique_users = db.query(func.count(func.distinct(SearchEvent.user_id))).filter(
                and_(
                    SearchEvent.organization_id == organization_id,
                    SearchEvent.created_at >= start_time,
                    SearchEvent.created_at <= end_time,
                    SearchEvent.user_id.is_not(None)
                )
            ).scalar() or 0

            # Top queries
            top_queries = db.query(
                SearchEvent.query,
                func.count(SearchEvent.id).label('count')
            ).filter(
                and_(
                    SearchEvent.organization_id == organization_id,
                    SearchEvent.created_at >= start_time,
                    SearchEvent.created_at <= end_time
                )
            ).group_by(SearchEvent.query).order_by(
                func.count(SearchEvent.id).desc()
            ).limit(10).all()

            # Search type distribution
            search_types = db.query(
                SearchEvent.search_type,
                func.count(SearchEvent.id).label('count')
            ).filter(
                and_(
                    SearchEvent.organization_id == organization_id,
                    SearchEvent.created_at >= start_time,
                    SearchEvent.created_at <= end_time
                )
            ).group_by(SearchEvent.search_type).all()

            return {
                "period": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                },
                "total_searches": total_searches,
                "avg_response_time_ms": float(avg_response_time),
                "unique_users": unique_users,
                "top_queries": [{"query": q[0], "count": q[1]} for q in top_queries],
                "search_types": [{"type": st[0], "count": st[1]} for st in search_types]
            }

        except Exception as e:
            logger.error(f"Error getting search analytics: {e}")
            return {}


# Global instance
quality_metrics_service = QualityMetricsService()