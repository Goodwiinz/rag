"""
Analytics background job processor
Handles async processing of heavy analytics computations and data aggregation
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import json

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case

from src.core.database import get_db
from src.models.processing import ProcessingJob, JobType, JobStatus, JobPriority
from src.models.analytics_event import AnalyticsEvent, EventType
from src.models.user_session import UserSession
from src.models.performance_log import PerformanceLog, MetricCategory, PerformanceLevel
from src.models.user import User
from src.models.organization import Organization
from src.config.analytics_config import AnalyticsConfig

logger = logging.getLogger(__name__)


class AnalyticsJobType(str, Enum):
    """Analytics-specific job types"""
    DATA_AGGREGATION = "data_aggregation"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_REPORT = "weekly_report"
    METRIC_COMPUTATION = "metric_computation"
    USER_BEHAVIOR_ANALYSIS = "user_behavior_analysis"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    QUALITY_METRICS_UPDATE = "quality_metrics_update"
    CACHE_WARMING = "cache_warming"
    DATA_RETENTION = "data_retention"
    ALERT_PROCESSING = "alert_processing"


@dataclass
class AnalyticsJobConfig:
    """Configuration for analytics jobs"""
    job_type: AnalyticsJobType
    organization_id: Optional[str] = None
    date_range: Optional[Dict[str, datetime]] = None
    parameters: Optional[Dict[str, Any]] = None
    priority: JobPriority = JobPriority.NORMAL
    max_retries: int = 3
    timeout_seconds: int = 3600


class AnalyticsDataAggregator:
    """Handles data aggregation for analytics"""

    def __init__(self, db: Session):
        self.db = db

    async def aggregate_daily_metrics(self, organization_id: str, date: datetime) -> Dict[str, Any]:
        """Aggregate daily metrics for an organization"""
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)

        # User behavior metrics
        user_metrics = await self._aggregate_user_metrics(organization_id, start_date, end_date)

        # Performance metrics
        performance_metrics = await self._aggregate_performance_metrics(organization_id, start_date, end_date)

        # Event metrics
        event_metrics = await self._aggregate_event_metrics(organization_id, start_date, end_date)

        return {
            "date": date.date().isoformat(),
            "organization_id": organization_id,
            "user_metrics": user_metrics,
            "performance_metrics": performance_metrics,
            "event_metrics": event_metrics,
            "aggregated_at": datetime.utcnow().isoformat()
        }

    async def _aggregate_user_metrics(self, org_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Aggregate user behavior metrics"""
        # Active sessions
        active_sessions = self.db.query(UserSession).filter(
            and_(
                UserSession.organization_id == org_id,
                UserSession.started_at >= start_date,
                UserSession.started_at < end_date,
                UserSession.status == 'active'
            )
        ).count()

        # Average session duration
        avg_duration = self.db.query(func.avg(UserSession.duration_seconds)).filter(
            and_(
                UserSession.organization_id == org_id,
                UserSession.started_at >= start_date,
                UserSession.started_at < end_date,
                UserSession.duration_seconds.isnot(None)
            )
        ).scalar() or 0

        # Total searches
        total_searches = self.db.query(func.sum(UserSession.total_searches)).filter(
            and_(
                UserSession.organization_id == org_id,
                UserSession.started_at >= start_date,
                UserSession.started_at < end_date
            )
        ).scalar() or 0

        # Engagement metrics
        avg_engagement = self.db.query(func.avg(UserSession.engagement_score)).filter(
            and_(
                UserSession.organization_id == org_id,
                UserSession.started_at >= start_date,
                UserSession.started_at < end_date
            )
        ).scalar() or 0

        return {
            "active_sessions": active_sessions,
            "avg_session_duration_seconds": float(avg_duration),
            "total_searches": int(total_searches),
            "avg_engagement_score": float(avg_engagement)
        }

    async def _aggregate_performance_metrics(self, org_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Aggregate performance metrics"""
        # Average response time
        avg_response_time = self.db.query(func.avg(PerformanceLog.response_time_ms)).filter(
            and_(
                PerformanceLog.organization_id == org_id,
                PerformanceLog.timestamp >= start_date,
                PerformanceLog.timestamp < end_date,
                PerformanceLog.response_time_ms.isnot(None)
            )
        ).scalar() or 0

        # Error rate
        total_logs = self.db.query(PerformanceLog).filter(
            and_(
                PerformanceLog.organization_id == org_id,
                PerformanceLog.timestamp >= start_date,
                PerformanceLog.timestamp < end_date
            )
        ).count()

        error_logs = self.db.query(PerformanceLog).filter(
            and_(
                PerformanceLog.organization_id == org_id,
                PerformanceLog.timestamp >= start_date,
                PerformanceLog.timestamp < end_date,
                PerformanceLog.performance_level.in_(['poor', 'critical'])
            )
        ).count()

        error_rate = (error_logs / total_logs * 100) if total_logs > 0 else 0

        # System health
        health_score = self.db.query(func.avg(
            case([
                (PerformanceLog.performance_level == PerformanceLevel.EXCELLENT, 100),
                (PerformanceLog.performance_level == PerformanceLevel.GOOD, 80),
                (PerformanceLog.performance_level == PerformanceLevel.FAIR, 60),
                (PerformanceLog.performance_level == PerformanceLevel.POOR, 40),
                (PerformanceLog.performance_level == PerformanceLevel.CRITICAL, 20)
            ], else_=50)
        )).filter(
            and_(
                PerformanceLog.organization_id == org_id,
                PerformanceLog.timestamp >= start_date,
                PerformanceLog.timestamp < end_date
            )
        ).scalar() or 50

        return {
            "avg_response_time_ms": float(avg_response_time),
            "error_rate_percentage": float(error_rate),
            "health_score": float(health_score),
            "total_logs": total_logs
        }

    async def _aggregate_event_metrics(self, org_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Aggregate event metrics"""
        from sqlalchemy import case

        # Event counts by type
        event_counts = self.db.query(
            AnalyticsEvent.event_type,
            func.count(AnalyticsEvent.id).label('count')
        ).filter(
            and_(
                AnalyticsEvent.organization_id == org_id,
                AnalyticsEvent.event_timestamp >= start_date,
                AnalyticsEvent.event_timestamp < end_date
            )
        ).group_by(AnalyticsEvent.event_type).all()

        # Search events
        search_events = self.db.query(AnalyticsEvent).filter(
            and_(
                AnalyticsEvent.organization_id == org_id,
                AnalyticsEvent.event_type == EventType.SEARCH_QUERY,
                AnalyticsEvent.event_timestamp >= start_date,
                AnalyticsEvent.event_timestamp < end_date
            )
        ).count()

        # Document views
        doc_views = self.db.query(AnalyticsEvent).filter(
            and_(
                AnalyticsEvent.organization_id == org_id,
                AnalyticsEvent.event_type == EventType.DOCUMENT_VIEW,
                AnalyticsEvent.event_timestamp >= start_date,
                AnalyticsEvent.event_timestamp < end_date
            )
        ).count()

        return {
            "event_counts": {event.event_type.value: event.count for event in event_counts},
            "search_events": search_events,
            "document_views": doc_views
        }


class AnalyticsJobProcessor:
    """Main analytics job processor"""

    def __init__(self):
        self.aggregator = None
        self.config = AnalyticsConfig()

    async def process_job(self, job_id: str) -> Dict[str, Any]:
        """Process an analytics job"""
        db = next(get_db())
        try:
            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")

            # Update job status to running
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            job.current_step = "Initializing analytics processor"
            db.commit()

            # Initialize aggregator
            self.aggregator = AnalyticsDataAggregator(db)

            # Process based on job type
            result = None
            analytics_job_type = AnalyticsJobType(job.job_type.value)

            if analytics_job_type == AnalyticsJobType.DATA_AGGREGATION:
                result = await self._process_data_aggregation(job, db)
            elif analytics_job_type == AnalyticsJobType.DAILY_SUMMARY:
                result = await self._process_daily_summary(job, db)
            elif analytics_job_type == AnalyticsJobType.WEEKLY_REPORT:
                result = await self._process_weekly_report(job, db)
            elif analytics_job_type == AnalyticsJobType.METRIC_COMPUTATION:
                result = await self._process_metric_computation(job, db)
            elif analytics_job_type == AnalyticsJobType.USER_BEHAVIOR_ANALYSIS:
                result = await self._process_user_behavior_analysis(job, db)
            elif analytics_job_type == AnalyticsJobType.PERFORMANCE_ANALYSIS:
                result = await self._process_performance_analysis(job, db)
            elif analytics_job_type == AnalyticsJobType.QUALITY_METRICS_UPDATE:
                result = await self._process_quality_metrics_update(job, db)
            elif analytics_job_type == AnalyticsJobType.CACHE_WARMING:
                result = await self._process_cache_warming(job, db)
            elif analytics_job_type == AnalyticsJobType.DATA_RETENTION:
                result = await self._process_data_retention(job, db)
            elif analytics_job_type == AnalyticsJobType.ALERT_PROCESSING:
                result = await self._process_alert_processing(job, db)
            else:
                raise ValueError(f"Unknown analytics job type: {analytics_job_type}")

            # Mark job as completed
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            job.current_step = "Completed"
            job.result = result
            job.progress_percentage = 100
            db.commit()

            logger.info(f"Analytics job {job_id} completed successfully")
            return result

        except Exception as e:
            # Handle job failure
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()

            logger.error(f"Analytics job {job_id} failed: {str(e)}")
            raise

        finally:
            db.close()

    async def _process_data_aggregation(self, job: ProcessingJob, db: Session) -> Dict[str, Any]:
        """Process data aggregation job"""
        params = job.parameters or {}
        organization_id = params.get('organization_id')
        date_range = params.get('date_range')

        if not organization_id:
            raise ValueError("Organization ID required for data aggregation")

        # Update progress
        job.current_step = "Aggregating user metrics"
        job.progress_percentage = 25
        db.commit()

        # Process aggregation
        if date_range:
            start_date = datetime.fromisoformat(date_range['start'])
            end_date = datetime.fromisoformat(date_range['end'])

            results = []
            current_date = start_date
            while current_date < end_date:
                job.current_step = f"Processing {current_date.date()}"
                job.progress_percentage = 25 + (current_date - start_date).days / (end_date - start_date).days * 50
                db.commit()

                daily_result = await self.aggregator.aggregate_daily_metrics(organization_id, current_date)
                results.append(daily_result)
                current_date += timedelta(days=1)

        else:
            # Default to last 7 days
            results = []
            for i in range(7):
                date = datetime.utcnow() - timedelta(days=i)
                job.current_step = f"Processing {date.date()}"
                job.progress_percentage = 25 + (i / 7) * 50
                db.commit()

                daily_result = await self.aggregator.aggregate_daily_metrics(organization_id, date)
                results.append(daily_result)

        job.current_step = "Finalizing aggregation"
        job.progress_percentage = 90
        db.commit()

        return {
            "job_type": "data_aggregation",
            "organization_id": organization_id,
            "results": results,
            "processed_days": len(results),
            "completed_at": datetime.utcnow().isoformat()
        }

    async def _process_daily_summary(self, job: ProcessingJob, db: Session) -> Dict[str, Any]:
        """Process daily summary job"""
        params = job.parameters or {}
        organization_id = params.get('organization_id')
        target_date = datetime.fromisoformat(params.get('target_date', datetime.utcnow().date().isoformat()))

        job.current_step = "Generating daily summary"
        job.progress_percentage = 50
        db.commit()

        summary = await self.aggregator.aggregate_daily_metrics(organization_id, target_date)

        job.current_step = "Daily summary completed"
        job.progress_percentage = 90
        db.commit()

        return {
            "job_type": "daily_summary",
            "summary": summary,
            "target_date": target_date.date().isoformat()
        }

    async def _process_weekly_report(self, job: ProcessingJob, db: Session) -> Dict[str, Any]:
        """Process weekly report job"""
        params = job.parameters or {}
        organization_id = params.get('organization_id')
        end_date = datetime.fromisoformat(params.get('end_date', datetime.utcnow().date().isoformat()))
        start_date = end_date - timedelta(days=7)

        job.current_step = "Generating weekly report"
        job.progress_percentage = 30
        db.commit()

        weekly_data = []
        for i in range(7):
            current_date = start_date + timedelta(days=i)
            job.progress_percentage = 30 + (i / 7) * 50
            db.commit()

            daily_data = await self.aggregator.aggregate_daily_metrics(organization_id, current_date)
            weekly_data.append(daily_data)

        # Aggregate weekly metrics
        total_sessions = sum(day["user_metrics"]["active_sessions"] for day in weekly_data)
        avg_engagement = sum(day["user_metrics"]["avg_engagement_score"] for day in weekly_data) / 7
        avg_response_time = sum(day["performance_metrics"]["avg_response_time_ms"] for day in weekly_data) / 7

        job.current_step = "Finalizing weekly report"
        job.progress_percentage = 90
        db.commit()

        return {
            "job_type": "weekly_report",
            "organization_id": organization_id,
            "week_start": start_date.date().isoformat(),
            "week_end": end_date.date().isoformat(),
            "summary": {
                "total_active_sessions": total_sessions,
                "avg_engagement_score": avg_engagement,
                "avg_response_time_ms": avg_response_time,
                "daily_breakdown": weekly_data
            }
        }

    async def _process_metric_computation(self, job: ProcessingJob, db: Session) -> Dict[str, Any]:
        """Process custom metric computation job"""
        params = job.parameters or {}
        organization_id = params.get('organization_id')
        metric_type = params.get('metric_type')
        computation_config = params.get('config', {})

        job.current_step = f"Computing {metric_type} metrics"
        job.progress_percentage = 50
        db.commit()

        # Implementation would depend on specific metric type
        # This is a placeholder for custom metric computations
        result = {
            "job_type": "metric_computation",
            "metric_type": metric_type,
            "organization_id": organization_id,
            "config": computation_config,
            "computed_at": datetime.utcnow().isoformat()
        }

        job.current_step = "Metric computation completed"
        job.progress_percentage = 90
        db.commit()

        return result

    async def _process_user_behavior_analysis(self, job: ProcessingJob, db: Session) -> Dict[str, Any]:
        """Process user behavior analysis job"""
        params = job.parameters or {}
        organization_id = params.get('organization_id')
        analysis_type = params.get('analysis_type', 'engagement_patterns')

        job.current_step = "Analyzing user behavior"
        job.progress_percentage = 50
        db.commit()

        # Placeholder for user behavior analysis
        result = {
            "job_type": "user_behavior_analysis",
            "analysis_type": analysis_type,
            "organization_id": organization_id,
            "analyzed_at": datetime.utcnow().isoformat()
        }

        job.current_step = "User behavior analysis completed"
        job.progress_percentage = 90
        db.commit()

        return result

    async def _process_performance_analysis(self, job: ProcessingJob, db: Session) -> Dict[str, Any]:
        """Process performance analysis job"""
        params = job.parameters or {}
        organization_id = params.get('organization_id')
        analysis_period = params.get('period', '24h')

        job.current_step = "Analyzing performance metrics"
        job.progress_percentage = 50
        db.commit()

        # Placeholder for performance analysis
        result = {
            "job_type": "performance_analysis",
            "analysis_period": analysis_period,
            "organization_id": organization_id,
            "analyzed_at": datetime.utcnow().isoformat()
        }

        job.current_step = "Performance analysis completed"
        job.progress_percentage = 90
        db.commit()

        return result

    async def _process_quality_metrics_update(self, job: ProcessingJob, db: Session) -> Dict[str, Any]:
        """Process quality metrics update job"""
        params = job.parameters or {}
        organization_id = params.get('organization_id')

        job.current_step = "Updating quality metrics"
        job.progress_percentage = 50
        db.commit()

        # Placeholder for quality metrics update
        result = {
            "job_type": "quality_metrics_update",
            "organization_id": organization_id,
            "updated_at": datetime.utcnow().isoformat()
        }

        job.current_step = "Quality metrics update completed"
        job.progress_percentage = 90
        db.commit()

        return result

    async def _process_cache_warming(self, job: ProcessingJob, db: Session) -> Dict[str, Any]:
        """Process cache warming job"""
        params = job.parameters or {}
        cache_keys = params.get('cache_keys', [])

        job.current_step = "Warming cache"
        job.progress_percentage = 50
        db.commit()

        # Placeholder for cache warming
        result = {
            "job_type": "cache_warming",
            "warmed_keys": cache_keys,
            "warmed_at": datetime.utcnow().isoformat()
        }

        job.current_step = "Cache warming completed"
        job.progress_percentage = 90
        db.commit()

        return result

    async def _process_data_retention(self, job: ProcessingJob, db: Session) -> Dict[str, Any]:
        """Process data retention job"""
        params = job.parameters or {}
        retention_days = params.get('retention_days', 365)

        job.current_step = "Applying data retention policies"
        job.progress_percentage = 50
        db.commit()

        # Placeholder for data retention processing
        result = {
            "job_type": "data_retention",
            "retention_days": retention_days,
            "processed_at": datetime.utcnow().isoformat()
        }

        job.current_step = "Data retention completed"
        job.progress_percentage = 90
        db.commit()

        return result

    async def _process_alert_processing(self, job: ProcessingJob, db: Session) -> Dict[str, Any]:
        """Process alert generation job"""
        params = job.parameters or {}
        organization_id = params.get('organization_id')
        alert_types = params.get('alert_types', [])

        job.current_step = "Processing alerts"
        job.progress_percentage = 50
        db.commit()

        # Placeholder for alert processing
        result = {
            "job_type": "alert_processing",
            "alert_types": alert_types,
            "organization_id": organization_id,
            "processed_at": datetime.utcnow().isoformat()
        }

        job.current_step = "Alert processing completed"
        job.progress_percentage = 90
        db.commit()

        return result

    def create_job(self, config: AnalyticsJobConfig) -> str:
        """Create an analytics processing job"""
        db = next(get_db())
        try:
            # Add analytics job types to the existing JobType enum if not present
            # For now, we'll use the existing job_type field as a string

            job = ProcessingJob(
                job_type=JobType(config.job_type.value) if hasattr(JobType, config.job_type.value) else JobType.BATCH_PROCESSING,
                status=JobStatus.PENDING,
                priority=config.priority,
                organization_id=config.organization_id,
                parameters=config.parameters or {},
                max_retries=config.max_retries,
                config={
                    "timeout_seconds": config.timeout_seconds,
                    "date_range": config.date_range
                }
            )

            db.add(job)
            db.commit()
            db.refresh(job)

            logger.info(f"Created analytics job {job.id} of type {config.job_type.value}")
            return str(job.id)

        finally:
            db.close()

    async def schedule_recurring_jobs(self):
        """Schedule recurring analytics jobs"""
        db = next(get_db())
        try:
            # Get all active organizations
            organizations = db.query(Organization).filter(Organization.is_active == True).all()

            for org in organizations:
                org_id = str(org.id)

                # Schedule daily summary
                daily_config = AnalyticsJobConfig(
                    job_type=AnalyticsJobType.DAILY_SUMMARY,
                    organization_id=org_id,
                    parameters={"target_date": datetime.utcnow().date().isoformat()},
                    priority=JobPriority.NORMAL
                )
                self.create_job(daily_config)

                # Schedule weekly report (run on Mondays)
                if datetime.utcnow().weekday() == 0:  # Monday
                    weekly_config = AnalyticsJobConfig(
                        job_type=AnalyticsJobType.WEEKLY_REPORT,
                        organization_id=org_id,
                        parameters={"end_date": datetime.utcnow().date().isoformat()},
                        priority=JobPriority.NORMAL
                    )
                    self.create_job(weekly_config)

            logger.info(f"Scheduled recurring jobs for {len(organizations)} organizations")

        finally:
            db.close()


# Global processor instance
analytics_processor = AnalyticsJobProcessor()