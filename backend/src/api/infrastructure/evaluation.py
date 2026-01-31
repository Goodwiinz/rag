"""
Evaluation API endpoints for RAG Triad metrics and evaluation workflows
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.core.database import get_db
from src.core.dependencies import get_current_user
from src.models.evaluation import (
    EvaluationComparison,
    EvaluationJob,
    EvaluationMetric,
    EvaluationReport,
    EvaluationStatus,
    EvaluationType,
    MetricType,
)
from src.models.user import User
from src.services.evaluation.rag_evaluation_service import (
    EvaluationRequest,
    RAGEvaluationInput,
    rag_evaluation_service,
)
from src.tasks.evaluation_tasks import (
    generate_evaluation_report,
    run_batch_evaluation,
    run_comparison_evaluation,
    run_rag_triad_evaluation,
    run_real_time_evaluation,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


# Pydantic models for API requests/responses
class EvaluationInput(BaseModel):
    """Input for evaluation"""

    query: str = Field(..., description="Query to evaluate")
    generated_answer: str = Field(..., description="Generated answer")
    retrieved_context: List[str] = Field(..., description="Retrieved context passages")
    reference_answer: Optional[str] = Field(
        None, description="Reference answer for comparison"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class BatchEvaluationRequest(BaseModel):
    """Request for batch evaluation"""

    name: str = Field(..., description="Name of the evaluation job")
    description: Optional[str] = Field(
        None, description="Description of the evaluation"
    )
    queries: List[str] = Field(..., description="List of queries to evaluate")
    search_type: str = Field("hybrid", description="Search type to use")
    search_limit: int = Field(5, description="Number of search results to retrieve")
    reference_answers: Optional[List[str]] = Field(
        None, description="Reference answers for queries"
    )


class RealTimeEvaluationRequest(BaseModel):
    """Request for real-time evaluation"""

    query: str = Field(..., description="Query to evaluate")
    generated_answer: str = Field(..., description="Generated answer")
    retrieved_context: List[str] = Field(..., description="Retrieved context passages")
    reference_answer: Optional[str] = Field(
        None, description="Reference answer for comparison"
    )


class ComparisonRequest(BaseModel):
    """Request for evaluation comparison"""

    name: str = Field(..., description="Name of the comparison")
    baseline_job_id: str = Field(..., description="ID of baseline evaluation job")
    comparison_job_id: str = Field(..., description="ID of comparison evaluation job")


class DatasetEvaluationRequest(BaseModel):
    """Request for dataset-based evaluation"""

    name: str = Field(..., description="Name of the evaluation job")
    description: Optional[str] = Field(
        None, description="Description of the evaluation"
    )
    evaluation_type: str = Field("rag_triad", description="Type of evaluation")
    questions: List[str] = Field(..., description="List of questions")
    reference_answers: Optional[List[str]] = Field(
        None, description="Reference answers"
    )
    contexts: Optional[List[List[str]]] = Field(
        None, description="Expected contexts for each question"
    )
    search_type: str = Field(
        "hybrid", description="Search type if contexts not provided"
    )
    search_limit: int = Field(
        5, description="Search results limit if contexts not provided"
    )


# Evaluation job endpoints
@router.post("/jobs", response_model=Dict[str, Any])
async def create_evaluation_job(
    request: DatasetEvaluationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Create a new evaluation job and start processing
    """
    try:
        # Validate input
        if not request.questions:
            raise HTTPException(
                status_code=400, detail="Questions list cannot be empty"
            )

        if request.reference_answers and len(request.reference_answers) != len(
            request.questions
        ):
            raise HTTPException(
                status_code=400,
                detail="Reference answers length must match questions length",
            )

        if request.contexts and len(request.contexts) != len(request.questions):
            raise HTTPException(
                status_code=400, detail="Contexts length must match questions length"
            )

        # Create evaluation request
        evaluation_request = EvaluationRequest(
            name=request.name,
            description=request.description,
            evaluation_type=EvaluationType(request.evaluation_type),
            dataset=[],  # Will be populated from questions/answers
            parameters={
                "search_type": request.search_type,
                "search_limit": request.search_limit,
            },
            user_id=str(current_user.id),
            organization_id=str(current_user.organization_id),
        )

        # Create evaluation job
        job = await rag_evaluation_service.create_evaluation_job(evaluation_request, db)

        # Create dataset entries
        from src.models.evaluation import EvaluationDataset

        dataset = EvaluationDataset(
            job_id=job.id,
            name=request.name,
            description=request.description,
            questions=request.questions,
            reference_answers=request.reference_answers,
            contexts=request.contexts,
            dataset_type="qa_pairs",
        )

        db.add(dataset)
        db.commit()

        # Start evaluation task in background
        background_tasks.add_task(run_rag_triad_evaluation.delay, str(job.id))

        logger.info(f"Created evaluation job {job.id} for user {current_user.id}")

        return {
            "job_id": str(job.id),
            "name": job.name,
            "status": job.status,
            "dataset_size": len(request.questions),
            "created_at": job.created_at.isoformat(),
            "message": "Evaluation job created and started",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating evaluation job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/batch", response_model=Dict[str, Any])
async def create_batch_evaluation_job(
    request: BatchEvaluationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Create a batch evaluation job for a list of queries
    """
    try:
        if not request.queries:
            raise HTTPException(status_code=400, detail="Queries list cannot be empty")

        # Create evaluation job
        job = EvaluationJob(
            name=request.name,
            description=request.description,
            evaluation_type=EvaluationType.BATCH_EVALUATION.value,
            parameters={
                "search_type": request.search_type,
                "search_limit": request.search_limit,
            },
            dataset_size=len(request.queries),
            user_id=str(current_user.id),
            organization_id=str(current_user.organization_id),
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        # Start batch evaluation task in background
        background_tasks.add_task(
            run_batch_evaluation.delay, str(job.id), request.queries
        )

        logger.info(f"Created batch evaluation job {job.id} for user {current_user.id}")

        return {
            "job_id": str(job.id),
            "name": job.name,
            "status": job.status,
            "dataset_size": len(request.queries),
            "created_at": job.created_at.isoformat(),
            "message": "Batch evaluation job created and started",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating batch evaluation job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/real-time", response_model=Dict[str, Any])
async def evaluate_real_time(
    request: RealTimeEvaluationRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Perform real-time evaluation of a single query-answer pair
    """
    try:
        # Start real-time evaluation task
        task = run_real_time_evaluation.delay(
            request.query,
            request.generated_answer,
            request.retrieved_context,
            request.reference_answer,
            str(current_user.organization_id),
        )

        logger.info(f"Started real-time evaluation for user {current_user.id}")

        return {
            "task_id": task.id,
            "status": "started",
            "message": "Real-time evaluation started",
        }

    except Exception as e:
        logger.error(f"Error starting real-time evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_evaluation_job(
    job_id: str, current_user: User = Depends(get_current_user), db=Depends(get_db)
):
    """
    Get details of an evaluation job
    """
    try:
        job = (
            db.query(EvaluationJob)
            .filter(
                EvaluationJob.id == job_id,
                EvaluationJob.organization_id == current_user.organization_id,
            )
            .first()
        )

        if not job:
            raise HTTPException(status_code=404, detail="Evaluation job not found")

        # Get evaluation summary
        summary = rag_evaluation_service.get_evaluation_summary(
            job_id, str(current_user.organization_id), db
        )

        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting evaluation job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs", response_model=List[Dict[str, Any]])
async def list_evaluation_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    evaluation_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    List evaluation jobs for the current user's organization
    """
    try:
        query = db.query(EvaluationJob).filter(
            EvaluationJob.organization_id == current_user.organization_id
        )

        if status:
            query = query.filter(EvaluationJob.status == status)

        if evaluation_type:
            query = query.filter(EvaluationJob.evaluation_type == evaluation_type)

        jobs = (
            query.order_by(EvaluationJob.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            {
                "id": str(job.id),
                "name": job.name,
                "description": job.description,
                "status": job.status,
                "evaluation_type": job.evaluation_type,
                "created_at": job.created_at.isoformat(),
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat()
                if job.completed_at
                else None,
                "duration_seconds": job.duration_seconds,
                "dataset_size": job.dataset_size,
                "processed_count": job.processed_count,
                "overall_score": job.overall_score,
                "success_rate": job.success_rate,
                "error_message": job.error_message,
            }
            for job in jobs
        ]

    except Exception as e:
        logger.error(f"Error listing evaluation jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}/metrics", response_model=List[Dict[str, Any]])
async def get_evaluation_metrics(
    job_id: str,
    metric_types: Optional[List[str]] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get metrics for a specific evaluation job
    """
    try:
        # Verify job exists and user has access
        job = (
            db.query(EvaluationJob)
            .filter(
                EvaluationJob.id == job_id,
                EvaluationJob.organization_id == current_user.organization_id,
            )
            .first()
        )

        if not job:
            raise HTTPException(status_code=404, detail="Evaluation job not found")

        # Get metrics
        metrics = rag_evaluation_service.get_evaluation_metrics(
            job_id, str(current_user.organization_id), metric_types, limit, db
        )

        return [
            {
                "id": str(metric.id),
                "metric_type": metric.metric_type,
                "metric_name": metric.metric_name,
                "value": metric.value,
                "min_value": metric.min_value,
                "max_value": metric.max_value,
                "mean_value": metric.mean_value,
                "threshold_min": metric.threshold_min,
                "threshold_max": metric.threshold_max,
                "is_threshold_violation": metric.is_threshold_violation,
                "query": metric.query,
                "calculation_method": metric.metadata.get("calculation_method")
                if metric.metadata
                else None,
                "model_used": metric.metadata.get("model_used")
                if metric.metadata
                else None,
                "created_at": metric.created_at.isoformat(),
            }
            for metric in metrics
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting evaluation metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Comparison endpoints
@router.post("/comparisons", response_model=Dict[str, Any])
async def create_evaluation_comparison(
    request: ComparisonRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Create a comparison between two evaluation jobs
    """
    try:
        # Verify jobs exist and user has access
        baseline_job = (
            db.query(EvaluationJob)
            .filter(
                EvaluationJob.id == request.baseline_job_id,
                EvaluationJob.organization_id == current_user.organization_id,
            )
            .first()
        )

        comparison_job = (
            db.query(EvaluationJob)
            .filter(
                EvaluationJob.id == request.comparison_job_id,
                EvaluationJob.organization_id == current_user.organization_id,
            )
            .first()
        )

        if not baseline_job:
            raise HTTPException(
                status_code=404, detail="Baseline evaluation job not found"
            )

        if not comparison_job:
            raise HTTPException(
                status_code=404, detail="Comparison evaluation job not found"
            )

        # Start comparison task in background
        background_tasks.add_task(
            run_comparison_evaluation.delay,
            request.name,
            request.baseline_job_id,
            request.comparison_job_id,
            str(current_user.id),
            str(current_user.organization_id),
        )

        logger.info(f"Started evaluation comparison: {request.name}")

        return {
            "status": "started",
            "message": "Evaluation comparison started",
            "baseline_job": request.baseline_job_id,
            "comparison_job": request.comparison_job_id,
            "name": request.name,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating evaluation comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparisons", response_model=List[Dict[str, Any]])
async def list_evaluation_comparisons(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    List evaluation comparisons for the current user's organization
    """
    try:
        comparisons = (
            db.query(EvaluationComparison)
            .filter(
                EvaluationComparison.organization_id == current_user.organization_id
            )
            .order_by(EvaluationComparison.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            {
                "id": str(comparison.id),
                "name": comparison.name,
                "description": comparison.description,
                "baseline_job_id": str(comparison.baseline_job_id),
                "comparison_job_id": str(comparison.comparison_job_id),
                "baseline_score": comparison.baseline_score,
                "comparison_score": comparison.comparison_score,
                "improvement_percentage": comparison.improvement_percentage,
                "statistical_significance": comparison.statistical_significance,
                "created_at": comparison.created_at.isoformat(),
            }
            for comparison in comparisons
        ]

    except Exception as e:
        logger.error(f"Error listing evaluation comparisons: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Report endpoints
@router.post("/jobs/{job_id}/reports/{report_type}", response_model=Dict[str, Any])
async def generate_evaluation_report(
    job_id: str,
    report_type: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Generate a report for an evaluation job
    """
    try:
        # Verify job exists and user has access
        job = (
            db.query(EvaluationJob)
            .filter(
                EvaluationJob.id == job_id,
                EvaluationJob.organization_id == current_user.organization_id,
            )
            .first()
        )

        if not job:
            raise HTTPException(status_code=404, detail="Evaluation job not found")

        if job.status != EvaluationStatus.COMPLETED.value:
            raise HTTPException(
                status_code=400,
                detail="Evaluation job must be completed to generate report",
            )

        # Start report generation task in background
        background_tasks.add_task(generate_evaluation_report.delay, job_id, report_type)

        logger.info(f"Started {report_type} report generation for job {job_id}")

        return {
            "status": "started",
            "message": f"{report_type.title()} report generation started",
            "job_id": job_id,
            "report_type": report_type,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating evaluation report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports", response_model=List[Dict[str, Any]])
async def list_evaluation_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    List evaluation reports for the current user's organization
    """
    try:
        reports = (
            db.query(EvaluationReport)
            .filter(EvaluationReport.organization_id == current_user.organization_id)
            .order_by(EvaluationReport.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            {
                "id": str(report.id),
                "title": report.title,
                "report_type": report.report_type,
                "job_id": str(report.job_id),
                "format_type": report.format_type,
                "file_size_bytes": report.file_size_bytes,
                "created_at": report.created_at.isoformat(),
                "executive_summary": report.executive_summary,
            }
            for report in reports
        ]

    except Exception as e:
        logger.error(f"Error listing evaluation reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{report_id}", response_model=Dict[str, Any])
async def get_evaluation_report(
    report_id: str, current_user: User = Depends(get_current_user), db=Depends(get_db)
):
    """
    Get details of an evaluation report
    """
    try:
        report = (
            db.query(EvaluationReport)
            .filter(
                EvaluationReport.id == report_id,
                EvaluationReport.organization_id == current_user.organization_id,
            )
            .first()
        )

        if not report:
            raise HTTPException(status_code=404, detail="Evaluation report not found")

        return {
            "id": str(report.id),
            "title": report.title,
            "report_type": report.report_type,
            "content": report.content,
            "executive_summary": report.executive_summary,
            "key_findings": report.key_findings,
            "recommendations": report.recommendations,
            "format_type": report.format_type,
            "template_used": report.template_used,
            "generated_by_model": report.generated_by_model,
            "file_path": report.file_path,
            "file_size_bytes": report.file_size_bytes,
            "created_at": report.created_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting evaluation report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Metrics and analytics endpoints
@router.get("/metrics/summary", response_model=Dict[str, Any])
async def get_metrics_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Get summary of evaluation metrics for the organization
    """
    try:
        from datetime import timedelta

        start_date = datetime.utcnow() - timedelta(days=days)

        # Get metrics for the period
        metrics = (
            db.query(EvaluationMetric)
            .join(EvaluationJob)
            .filter(
                EvaluationJob.organization_id == current_user.organization_id,
                EvaluationJob.created_at >= start_date,
                EvaluationJob.status == EvaluationStatus.COMPLETED.value,
            )
            .all()
        )

        if not metrics:
            return {
                "period_days": days,
                "total_metrics": 0,
                "metric_summary": {},
                "threshold_violations": 0,
                "average_scores": {},
            }

        # Group metrics by type
        metrics_by_type = {}
        total_violations = 0

        for metric in metrics:
            metric_type = metric.metric_type
            if metric_type not in metrics_by_type:
                metrics_by_type[metric_type] = []
            metrics_by_type[metric_type].append(metric.value)

            if metric.is_threshold_violation:
                total_violations += 1

        # Calculate statistics for each metric type
        import statistics

        metric_summary = {}
        average_scores = {}

        for metric_type, values in metrics_by_type.items():
            if values:
                metric_summary[metric_type] = {
                    "count": len(values),
                    "mean": statistics.mean(values),
                    "min": min(values),
                    "max": max(values),
                    "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
                }
                average_scores[metric_type] = statistics.mean(values)

        return {
            "period_days": days,
            "total_metrics": len(metrics),
            "metric_summary": metric_summary,
            "threshold_violations": total_violations,
            "average_scores": average_scores,
            "violation_rate": (total_violations / len(metrics)) * 100 if metrics else 0,
        }

    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/jobs/{job_id}")
async def delete_evaluation_job(
    job_id: str, current_user: User = Depends(get_current_user), db=Depends(get_db)
):
    """
    Delete an evaluation job (soft delete)
    """
    try:
        job = (
            db.query(EvaluationJob)
            .filter(
                EvaluationJob.id == job_id,
                EvaluationJob.organization_id == current_user.organization_id,
            )
            .first()
        )

        if not job:
            raise HTTPException(status_code=404, detail="Evaluation job not found")

        # Soft delete the job
        job.soft_delete()
        db.commit()

        logger.info(f"Deleted evaluation job {job_id} for user {current_user.id}")

        return {"message": "Evaluation job deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting evaluation job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def evaluation_health_check():
    """
    Health check for evaluation services
    """
    try:
        health_status = {
            "status": "healthy",
            "services": {
                "evaluation_service": {
                    "status": "healthy",
                    "message": "RAG evaluation service is available",
                }
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        return health_status

    except Exception as e:
        logger.error(f"Evaluation health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
