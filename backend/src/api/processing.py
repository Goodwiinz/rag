"""
Processing pipeline API endpoints
"""

from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.core.database import get_db
from src.core.dependencies import get_current_user, get_current_organization, require_admin
from src.models.user import User
from src.models.organization import Organization
from src.models.document import Document
from src.models.processing import ProcessingJob, JobStatus
from src.services.processing_service import ProcessingPipeline, get_processing_service

router = APIRouter(prefix="/processing", tags=["processing"])

# Request/Response Models
class ProcessingJobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    progress_percentage: float
    current_step: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_seconds: Optional[float]
    error_message: Optional[str]

class ProcessingStatusResponse(BaseModel):
    document_id: str
    processing_status: str
    is_embedded: bool
    is_indexed: bool
    processing_error: Optional[str]
    jobs: List[ProcessingJobResponse]

class BatchProcessingRequest(BaseModel):
    document_ids: List[str]
    priority: Optional[str] = "normal"

class RetryProcessingRequest(BaseModel):
    job_ids: Optional[List[str]] = None
    organization_wide: bool = False

@router.post("/documents/{document_id}/process")
async def start_document_processing(
    document_id: str,
    current_user: User = Depends(get_current_user),
    processing_service: ProcessingPipeline = Depends(get_processing_service)
):
    """Start processing for a document"""
    try:
        job = await processing_service.process_document(
            document_id=document_id,
            user_id=str(current_user.id)
        )

        return {
            "message": "Document processing started",
            "job_id": str(job.id),
            "status": job.status.value
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start processing: {str(e)}"
        )

@router.get("/documents/{document_id}/status", response_model=ProcessingStatusResponse)
async def get_document_processing_status(
    document_id: str,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    processing_service: ProcessingPipeline = Depends(get_processing_service)
):
    """Get processing status for a document"""
    # Check if document belongs to user's organization
    document = processing_service.db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == organization.id,
        Document.is_deleted == False
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    status_info = processing_service.get_processing_status(document_id)

    return ProcessingStatusResponse(**status_info)

@router.get("/jobs/{job_id}", response_model=ProcessingJobResponse)
async def get_processing_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """Get status of a specific processing job"""
    job = db.query(ProcessingJob).filter(
        ProcessingJob.id == job_id,
        ProcessingJob.organization_id == organization.id
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found"
        )

    return ProcessingJobResponse(**job.to_dict())

@router.get("/jobs")
async def list_processing_jobs(
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """List processing jobs for the organization"""
    query = db.query(ProcessingJob).filter(
        ProcessingJob.organization_id == organization.id
    )

    if status:
        try:
            job_status = JobStatus(status)
            query = query.filter(ProcessingJob.status == job_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}"
            )

    if job_type:
        from src.models.processing import JobType
        try:
            job_type_enum = JobType(job_type)
            query = query.filter(ProcessingJob.job_type == job_type_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid job type: {job_type}"
            )

    total = query.count()
    jobs = query.order_by(ProcessingJob.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "jobs": [ProcessingJobResponse(**job.to_dict()) for job in jobs],
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.post("/batch", response_model=dict)
async def start_batch_processing(
    request: BatchProcessingRequest,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    processing_service: ProcessingPipeline = Depends(get_processing_service)
):
    """Start batch processing for multiple documents"""
    results = []
    errors = []

    # Verify all documents belong to the organization
    documents = processing_service.db.query(Document).filter(
        Document.id.in_(request.document_ids),
        Document.organization_id == organization.id,
        Document.is_deleted == False
    ).all()

    found_document_ids = {str(doc.id) for doc in documents}
    missing_document_ids = set(request.document_ids) - found_document_ids

    if missing_document_ids:
        errors.extend([
            {"document_id": doc_id, "error": "Document not found"}
            for doc_id in missing_document_ids
        ])

    # Process found documents
    for document in documents:
        try:
            job = await processing_service.process_document(
                document_id=str(document.id),
                user_id=str(current_user.id)
            )
            results.append({
                "document_id": str(document.id),
                "job_id": str(job.id),
                "status": "queued"
            })
        except Exception as e:
            errors.append({
                "document_id": str(document.id),
                "error": str(e)
            })

    return {
        "message": f"Batch processing initiated for {len(results)} documents",
        "successful": results,
        "errors": errors,
        "total_requested": len(request.document_ids),
        "successful_count": len(results),
        "error_count": len(errors)
    }

@router.post("/retry", response_model=dict)
async def retry_failed_jobs(
    request: RetryProcessingRequest,
    current_user: User = Depends(require_admin),
    organization: Organization = Depends(get_current_organization),
    processing_service: ProcessingPipeline = Depends(get_processing_service)
):
    """Retry failed processing jobs"""
    try:
        if request.organization_wide:
            # Retry all failed jobs for the organization
            retried_count = processing_service.retry_failed_jobs(
                organization_id=str(organization.id)
            )
            message = f"Retried {retried_count} failed jobs organization-wide"
        elif request.job_ids:
            # Retry specific jobs
            retried_count = 0
            for job_id in request.job_ids:
                job = processing_service.db.query(ProcessingJob).filter(
                    ProcessingJob.id == job_id,
                    ProcessingJob.organization_id == organization.id
                ).first()

                if job and job.can_retry:
                    job.retry_job()
                    processing_service.db.commit()
                    processing_service.queue_processing_job(job_id)
                    retried_count += 1

            message = f"Retried {retried_count} specified jobs"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either job_ids or organization_wide must be specified"
            )

        return {
            "message": message,
            "retried_count": retried_count
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry jobs: {str(e)}"
        )

@router.post("/jobs/{job_id}/cancel")
async def cancel_processing_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """Cancel a processing job"""
    job = db.query(ProcessingJob).filter(
        ProcessingJob.id == job_id,
        ProcessingJob.organization_id == organization.id
    ).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processing job not found"
        )

    if not job.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is not active and cannot be cancelled"
        )

    # Check permissions (job owner or admin)
    if (job.created_by_user_id != current_user.id and
        not current_user.has_permission(UserRole.ADMIN)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only cancel your own jobs or require admin role"
        )

    try:
        # Cancel the job
        job.cancel_job()
        db.commit()

        # Also try to cancel the Celery task if it exists
        if job.celery_task_id:
            from src.tasks.processing_tasks import current_app
            current_app.control.revoke(job.celery_task_id, terminate=True)

        return {
            "message": "Job cancelled successfully",
            "job_id": str(job.id),
            "status": job.status.value
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel job: {str(e)}"
        )

@router.get("/queue/status")
async def get_queue_status(
    current_user: User = Depends(require_admin),  # Admin only
    organization: Organization = Depends(get_current_organization),
    processing_service: ProcessingPipeline = Depends(get_processing_service)
):
    """Get processing queue status (admin only)"""
    try:
        from src.models.processing import JobStatus, JobType

        # Get queue statistics
        queue_stats = {}

        for job_type in JobType:
            queued_count = processing_service.db.query(ProcessingJob).filter(
                ProcessingJob.job_type == job_type,
                ProcessingJob.status == JobStatus.QUEUED,
                ProcessingJob.organization_id == organization.id
            ).count()

            running_count = processing_service.db.query(ProcessingJob).filter(
                ProcessingJob.job_type == job_type,
                ProcessingJob.status == JobStatus.RUNNING,
                ProcessingJob.organization_id == organization.id
            ).count()

            queue_stats[job_type.value] = {
                "queued": queued_count,
                "running": running_count,
                "total": queued_count + running_count
            }

        # Get overall statistics
        total_queued = processing_service.db.query(ProcessingJob).filter(
            ProcessingJob.status == JobStatus.QUEUED,
            ProcessingJob.organization_id == organization.id
        ).count()

        total_running = processing_service.db.query(ProcessingJob).filter(
            ProcessingJob.status == JobStatus.RUNNING,
            ProcessingJob.organization_id == organization.id
        ).count()

        total_failed = processing_service.db.query(ProcessingJob).filter(
            ProcessingJob.status == JobStatus.FAILED,
            ProcessingJob.organization_id == organization.id
        ).count()

        return {
            "queue_stats": queue_stats,
            "overall_stats": {
                "queued": total_queued,
                "running": total_running,
                "failed": total_failed,
                "total": total_queued + total_running + total_failed
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get queue status: {str(e)}"
        )

@router.delete("/jobs/cleanup")
async def cleanup_old_jobs(
    days: int = 30,
    current_user: User = Depends(require_admin),
    organization: Organization = Depends(get_current_organization),
    db: Session = Depends(get_db)
):
    """Clean up old processing jobs (admin only)"""
    try:
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        old_jobs = db.query(ProcessingJob).filter(
            ProcessingJob.created_at < cutoff_date,
            ProcessingJob.organization_id == organization.id,
            ProcessingJob.status.in_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED])
        ).all()

        for job in old_jobs:
            db.delete(job)

        db.commit()

        return {
            "message": f"Cleaned up {len(old_jobs)} old processing jobs",
            "cleaned_count": len(old_jobs),
            "cutoff_days": days
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup jobs: {str(e)}"
        )