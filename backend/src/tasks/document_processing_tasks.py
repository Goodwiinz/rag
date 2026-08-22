"""
Background tasks for document processing with async pipeline execution
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

from sqlalchemy import text

from src.core.database import SessionLocal
from src.models.document import Document, ProcessingStatus
from src.models.processing import JobStatus, ProcessingJob
from src.services.processing.multimodal_processing_service import (
    MultimodalProcessingService,
)
from src.tasks._async_utils import run_async
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def get_db_session():
    """Get database session for background tasks"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Don't close here, let the task manage it


@celery_app.task(bind=True)
def cleanup_processing_artifacts(self, days_old: int = 7):
    """
    Clean up old processing artifacts and temporary files
    """
    db = SessionLocal()

    try:
        logger.info(
            f"Starting cleanup of processing artifacts older than {days_old} days"
        )

        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        # Clean up old processing jobs
        old_jobs = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.created_at < cutoff_date,
                ProcessingJob.status == JobStatus.COMPLETED,
            )
            .limit(1000)
        )  # Limit to prevent overwhelming

        cleaned_count = 0
        for job in old_jobs:
            try:
                # Soft delete old completed jobs
                job.is_deleted = True
                job.deleted_at = datetime.utcnow()
                cleaned_count += 1
            except Exception as e:
                logger.error(f"Failed to cleanup job {job.id}: {str(e)}")

        db.commit()

        # Clean up temporary files
        import os
        import time
        from pathlib import Path

        from src.core.config import settings

        temp_dir = Path(settings.UPLOAD_DIR) / "temp"
        if temp_dir.exists():
            current_time = time.time()
            for temp_file in temp_dir.glob("*"):
                try:
                    if (
                        current_time - os.path.getctime(temp_file)
                        > days_old * 24 * 3600
                    ):
                        os.remove(temp_file)
                        logger.info(f"Removed temporary file: {temp_file}")
                except Exception as e:
                    logger.error(
                        f"Failed to remove temporary file {temp_file}: {str(e)}"
                    )

        logger.info(f"Cleanup completed. Cleaned {cleaned_count} processing jobs.")

        return {
            "status": "completed",
            "cleaned_jobs": cleaned_count,
            "days_old": days_old,
        }

    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        return {"status": "error", "error": str(e)}

    finally:
        db.close()


@celery_app.task(bind=True)
def retry_failed_processing(self, job_id: str):
    """
    Retry failed processing job with enhanced error handling
    """
    db = SessionLocal()

    try:
        logger.info(f"Retrying failed processing job {job_id}")

        # Get processing job
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            return {"status": "error", "message": "Job not found"}

        if job.status != JobStatus.FAILED:
            return {"status": "error", "message": "Job is not in failed state"}

        if not job.can_retry:
            return {
                "status": "error",
                "message": "Job cannot be retried (max retries reached)",
            }

        # Reset job for retry
        job.retry_job()
        job.celery_task_id = self.request.id
        db.commit()

        # Get document
        document = db.query(Document).filter(Document.id == job.document_id).first()
        if not document:
            job.fail_job("Document not found")
            db.commit()
            return {"status": "error", "message": "Document not found"}

        # Reset document status
        document.processing_status = ProcessingStatus.RETRYING
        document.processing_error = None
        db.commit()

        # Process document
        processing_service = MultimodalProcessingService(db)
        processing_results = run_async(
            processing_service.process_document(document, job)
        )

        return {
            "status": "completed" if processing_results["success"] else "failed",
            "job_id": job_id,
            "document_id": str(document.id),
            "retry_attempt": job.retry_count,
            "processing_results": processing_results,
        }

    except Exception as e:
        logger.error(f"Retry processing failed for job {job_id}: {str(e)}")

        if "job" in locals():
            job.fail_job(str(e))
            db.commit()

        return {
            "status": "error",
            "job_id": job_id,
            "error": str(e),
            "retry_attempt": job.retry_count if "job" in locals() else 0,
        }

    finally:
        db.close()


@celery_app.task(bind=True)
def generate_processing_report(
    self, organization_id: Optional[str], date_range_days: int = 30
):
    """
    Generate processing report for one organization, or across all
    organizations when organization_id is None (the scheduled beat mode).

    R2-L19 / R6-M13: the schedule previously passed a literal
    "default_organization_id" that never matches any UUID PK, so the daily
    job always produced empty reports. None now means every org.
    """
    from datetime import timedelta

    from sqlalchemy import func, true

    db = SessionLocal()

    try:
        logger.info(
            f"Generating processing report for "
            f"{organization_id or 'ALL_ORGANIZATIONS'}"
        )

        cutoff_date = datetime.utcnow() - timedelta(days=date_range_days)

        def _org_filter(model):
            if organization_id:
                return model.organization_id == organization_id
            return true()

        # Get processing statistics
        stats = (
            db.query(
                ProcessingJob.status,
                func.count(ProcessingJob.id).label("count"),
                func.avg(ProcessingJob.duration_seconds).label("avg_duration"),
            )
            .filter(
                _org_filter(ProcessingJob),
                ProcessingJob.created_at >= cutoff_date,
            )
            .group_by(ProcessingJob.status)
            .all()
        )

        # Get document type statistics
        doc_stats = (
            db.query(Document.document_type, func.count(Document.id).label("count"))
            .filter(
                _org_filter(Document),
                Document.created_at >= cutoff_date,
            )
            .group_by(Document.document_type)
            .all()
        )

        # Get error statistics
        error_stats = (
            db.query(
                ProcessingJob.error_message, func.count(ProcessingJob.id).label("count")
            )
            .filter(
                _org_filter(ProcessingJob),
                ProcessingJob.created_at >= cutoff_date,
                ProcessingJob.status == JobStatus.FAILED,
            )
            .group_by(ProcessingJob.error_message)
            .limit(10)
            .all()
        )

        report = {
            "organization_id": organization_id,
            "report_period_days": date_range_days,
            "generated_at": datetime.utcnow().isoformat(),
            "processing_statistics": [
                {
                    "status": stat.status.value,
                    "count": stat.count,
                    "avg_duration_seconds": (
                        float(stat.avg_duration) if stat.avg_duration else 0
                    ),
                }
                for stat in stats
            ],
            "document_type_statistics": [
                {"document_type": stat.document_type.value, "count": stat.count}
                for stat in doc_stats
            ],
            "top_errors": [
                {"error_message": error.error_message, "count": error.count}
                for error in error_stats
            ],
        }

        return report

    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        return {"status": "error", "organization_id": organization_id, "error": str(e)}

    finally:
        db.close()


# Periodic tasks
@celery_app.task
def health_check():
    """
    Health check task for monitoring system status
    """
    db = SessionLocal()
    try:
        # Check database connectivity. Wrap in text() so SQLAlchemy 2.x accepts
        # the literal SQL — passing a raw string here used to fail every minute.
        db.execute(text("SELECT 1"))

        # Check Redis connectivity. The result backend exposes its redis client
        # as `.client`; `.result_backend` does not exist (AttributeError every
        # run made health_check report unhealthy unconditionally).
        celery_app.backend.client.ping()

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "redis": "connected",
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
        }

    finally:
        db.close()


# Schedule periodic tasks
from celery.schedules import crontab

# Merge (not assign) — a full `= {...}` is clobbered by the task module Celery
# imports last; .update() lets every module's schedule coexist on the shared conf.
celery_app.conf.beat_schedule.update(
    {
        "cleanup-artifacts": {
            "task": "src.tasks.document_processing_tasks.cleanup_processing_artifacts",
            "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
            "args": (7,),  # Clean up artifacts older than 7 days
        },
        "health-check": {
            "task": "src.tasks.document_processing_tasks.health_check",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
        },
        "generate-reports": {
            "task": "src.tasks.document_processing_tasks.generate_processing_report",
            "schedule": crontab(hour=1, minute=0),  # Daily at 1 AM
            # organization_id=None → aggregate across every org. The old
            # literal "default_organization_id" never matched any UUID PK,
            # so this job silently produced empty reports daily (R2-L19).
            "args": (None, 30),
        },
    }
)
