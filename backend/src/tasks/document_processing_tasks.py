"""
Background tasks for document processing with async pipeline execution
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from celery.exceptions import Retry
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.core.database import get_db
from src.models.document import Document, ProcessingStatus
from src.models.processing import JobStatus, ProcessingJob
from src.services.documents.document_quality_service import DocumentQualityService
from src.services.documents.enhanced_file_service import EnhancedFileService
from src.services.processing.multimodal_processing_service import (
    MultimodalProcessingService,
)
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Database setup for background tasks
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session():
    """Get database session for background tasks"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Don't close here, let the task manage it


@celery_app.task(bind=True, max_retries=3)
def process_document_upload(self, job_id: str, upload_id: Optional[str] = None):
    """
    Process document upload with enhanced pipeline
    """
    # Lazy import to avoid circular dependency
    from src.api.documents.document_upload import upload_manager

    db = SessionLocal()
    task_id = self.request.id

    try:
        logger.info(f"Starting document processing for job {job_id}, task {task_id}")

        # Get processing job
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            logger.error(f"Processing job {job_id} not found")
            return {"status": "error", "message": "Job not found"}

        # Update job with task ID
        job.celery_task_id = task_id
        job.queue_job()

        # Get document
        document = db.query(Document).filter(Document.id == job.document_id).first()
        if not document:
            logger.error(f"Document {job.document_id} not found")
            job.fail_job("Document not found")
            db.commit()
            return {"status": "error", "message": "Document not found"}

        # Update document status
        document.processing_status = ProcessingStatus.PROCESSING
        document.processing_started_at = datetime.utcnow()
        db.commit()

        # Initialize processing service
        processing_service = MultimodalProcessingService(db)

        # Update upload progress if available
        if upload_id:
            asyncio.run(
                upload_manager.update_progress(
                    upload_id, 20.0, "Starting processing pipeline"
                )
            )

        # Process document
        processing_results = asyncio.run(
            processing_service.process_document(document, job, upload_id)
        )

        # Update upload progress if available
        if upload_id:
            if processing_results["success"]:
                asyncio.run(
                    upload_manager.update_progress(
                        upload_id, 100.0, "Processing completed"
                    )
                )
            else:
                error_msg = "; ".join(processing_results["errors"])
                asyncio.run(
                    upload_manager.update_progress(
                        upload_id, 0.0, error_message=f"Processing failed: {error_msg}"
                    )
                )

        # Log completion
        if processing_results["success"]:
            logger.info(f"Document processing completed successfully for job {job_id}")
        else:
            logger.error(
                f"Document processing failed for job {job_id}: {processing_results['errors']}"
            )

        return {
            "status": "completed" if processing_results["success"] else "failed",
            "job_id": job_id,
            "document_id": str(document.id),
            "processing_results": processing_results,
            "processing_time": processing_results.get("processing_time", 0),
        }

    except Exception as e:
        logger.error(f"Document processing task failed for job {job_id}: {str(e)}")

        # Update job status
        if "job" in locals():
            job.fail_job(str(e))
            db.commit()

        # Update upload progress if available
        if upload_id:
            try:
                asyncio.run(
                    upload_manager.update_progress(
                        upload_id, 0.0, error_message=f"Processing failed: {str(e)}"
                    )
                )
            except:
                pass

        # Retry if possible
        if self.request.retries < self.max_retries:
            logger.info(
                f"Retrying document processing task for job {job_id}, attempt {self.request.retries + 1}"
            )
            raise self.retry(
                countdown=60 * (2**self.request.retries)
            )  # Exponential backoff

        return {
            "status": "error",
            "job_id": job_id,
            "error": str(e),
            "retry_count": self.request.retries,
        }

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2)
def process_high_priority_document(self, job_id: str):
    """
    Process high-priority document with expedited handling
    """
    db = SessionLocal()
    task_id = self.request.id

    try:
        logger.info(f"Starting high-priority document processing for job {job_id}")

        # Get processing job
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            return {"status": "error", "message": "Job not found"}

        # Update job
        job.celery_task_id = task_id
        job.start_job(worker_id="high_priority_worker")

        # Get document
        document = db.query(Document).filter(Document.id == job.document_id).first()
        if not document:
            job.fail_job("Document not found")
            db.commit()
            return {"status": "error", "message": "Document not found"}

        # Update document status
        document.processing_status = ProcessingStatus.PROCESSING
        document.processing_started_at = datetime.utcnow()
        db.commit()

        # Process with high priority settings
        processing_service = MultimodalProcessingService(db)

        # Modify job configuration for high priority
        job.config = job.config or {}
        job.config["high_priority"] = True
        job.config["skip_optional_steps"] = True  # Skip non-essential steps for speed
        db.commit()

        processing_results = asyncio.run(
            processing_service.process_document(document, job)
        )

        return {
            "status": "completed" if processing_results["success"] else "failed",
            "job_id": job_id,
            "document_id": str(document.id),
            "priority": "high",
            "processing_results": processing_results,
        }

    except Exception as e:
        logger.error(
            f"High-priority document processing failed for job {job_id}: {str(e)}"
        )

        if "job" in locals():
            job.fail_job(str(e))
            db.commit()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30)  # Shorter retry delay for high priority

        return {
            "status": "error",
            "job_id": job_id,
            "error": str(e),
            "priority": "high",
        }

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1)
def process_low_priority_document(self, job_id: str):
    """
    Process low-priority document with resource-conscious handling
    """
    db = SessionLocal()

    try:
        logger.info(f"Starting low-priority document processing for job {job_id}")

        # Get processing job
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            return {"status": "error", "message": "Job not found"}

        # Update job
        job.celery_task_id = self.request.id
        job.start_job(worker_id="low_priority_worker")

        # Get document
        document = db.query(Document).filter(Document.id == job.document_id).first()
        if not document:
            job.fail_job("Document not found")
            db.commit()
            return {"status": "error", "message": "Document not found"}

        # Update document status
        document.processing_status = ProcessingStatus.PROCESSING
        document.processing_started_at = datetime.utcnow()
        db.commit()

        # Process with low priority settings
        processing_service = MultimodalProcessingService(db)

        # Modify job configuration for low priority
        job.config = job.config or {}
        job.config["low_priority"] = True
        job.config["extended_timeout"] = True
        db.commit()

        processing_results = asyncio.run(
            processing_service.process_document(document, job)
        )

        return {
            "status": "completed" if processing_results["success"] else "failed",
            "job_id": job_id,
            "document_id": str(document.id),
            "priority": "low",
            "processing_results": processing_results,
        }

    except Exception as e:
        logger.error(
            f"Low-priority document processing failed for job {job_id}: {str(e)}"
        )

        if "job" in locals():
            job.fail_job(str(e))
            db.commit()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)  # Longer retry delay for low priority

        return {"status": "error", "job_id": job_id, "error": str(e), "priority": "low"}

    finally:
        db.close()


@celery_app.task(bind=True)
def batch_process_documents(
    self, job_ids: list, batch_config: Optional[Dict[str, Any]] = None
):
    """
    Process multiple documents as a batch
    """
    db = SessionLocal()
    batch_id = self.request.id

    try:
        logger.info(
            f"Starting batch document processing for {len(job_ids)} jobs, batch {batch_id}"
        )

        batch_config = batch_config or {}
        max_concurrent = batch_config.get("max_concurrent", 3)
        delay_between_jobs = batch_config.get("delay_between_jobs", 5)

        # Update all jobs to queued status
        jobs = db.query(ProcessingJob).filter(ProcessingJob.id.in_(job_ids)).all()
        for job in jobs:
            job.celery_task_id = f"batch_{batch_id}"
            job.queue_job()
        db.commit()

        # Process jobs with concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_single_job(job_id: str):
            async with semaphore:
                # Add delay between jobs if configured
                if delay_between_jobs > 0:
                    await asyncio.sleep(delay_between_jobs)

                # Call the individual processing task
                try:
                    result = process_document_upload.delay(job_id)
                    return {"job_id": job_id, "task_id": result.id, "status": "queued"}
                except Exception as e:
                    logger.error(f"Failed to queue job {job_id}: {str(e)}")
                    return {"job_id": job_id, "status": "error", "error": str(e)}

        # Execute batch processing
        results = asyncio.run(process_single_job(job_id) for job_id in job_ids)

        return {
            "status": "batch_queued",
            "batch_id": batch_id,
            "total_jobs": len(job_ids),
            "results": results,
        }

    except Exception as e:
        logger.error(f"Batch processing failed: {str(e)}")
        return {"status": "error", "batch_id": batch_id, "error": str(e)}

    finally:
        db.close()


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
        processing_results = asyncio.run(
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
def generate_processing_report(self, organization_id: str, date_range_days: int = 30):
    """
    Generate processing report for organization
    """
    db = SessionLocal()

    try:
        logger.info(f"Generating processing report for organization {organization_id}")

        from datetime import timedelta

        from sqlalchemy import func

        cutoff_date = datetime.utcnow() - timedelta(days=date_range_days)

        # Get processing statistics
        stats = (
            db.query(
                ProcessingJob.status,
                func.count(ProcessingJob.id).label("count"),
                func.avg(ProcessingJob.duration_seconds).label("avg_duration"),
            )
            .filter(
                ProcessingJob.organization_id == organization_id,
                ProcessingJob.created_at >= cutoff_date,
            )
            .group_by(ProcessingJob.status)
            .all()
        )

        # Get document type statistics
        doc_stats = (
            db.query(Document.document_type, func.count(Document.id).label("count"))
            .filter(
                Document.organization_id == organization_id,
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
                ProcessingJob.organization_id == organization_id,
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
                    "avg_duration_seconds": float(stat.avg_duration)
                    if stat.avg_duration
                    else 0,
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
    try:
        db = SessionLocal()

        # Check database connectivity
        db.execute(text("SELECT 1"))

        # Check Redis connectivity
        celery_app.backend.result_backend.ping()

        db.close()

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


# Schedule periodic tasks
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
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
        "args": ("default_organization_id", 30),  # This should be configurable
    },
}


# Task monitoring and metrics
@celery_app.task
def update_processing_metrics():
    """
    Update processing metrics for monitoring
    """
    try:
        db = SessionLocal()

        # Get current queue lengths
        from src.models.processing import ProcessingJob

        queue_stats = {}
        for queue_name in ["document_processing", "high_priority", "low_priority"]:
            queue_length = (
                db.query(ProcessingJob)
                .filter(
                    ProcessingJob.queue_name == queue_name,
                    ProcessingJob.status == JobStatus.QUEUED,
                )
                .count()
            )
            queue_stats[queue_name] = queue_length

        # Get active workers (approximation)
        active_jobs = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.status == JobStatus.RUNNING)
            .count()
        )

        db.close()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "queue_lengths": queue_stats,
            "active_jobs": active_jobs,
        }

    except Exception as e:
        logger.error(f"Metrics update failed: {str(e)}")
        return {"timestamp": datetime.utcnow().isoformat(), "error": str(e)}
