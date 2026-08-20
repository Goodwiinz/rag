"""
Evaluation API endpoints for RAG Triad metrics and evaluation workflows
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from kombu.exceptions import OperationalError
from pydantic import BaseModel, Field
from sqlalchemy import Integer, func

from src.core.database import get_db_sync
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
    queries: List[str] = Field(
        ..., min_length=1, max_length=100, description="List of queries to evaluate"
    )
    search_type: str = Field("hybrid", description="Search type to use")
    search_limit: int = Field(
        5, ge=1, le=50, description="Number of search results to retrieve"
    )
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
    # R5-L14: same unbounded-list/unbounded-limit hazard as BatchEvaluationRequest.
    questions: List[str] = Field(
        ..., min_length=1, max_length=100, description="List of questions"
    )
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
        5, ge=1, le=50, description="Search results limit if contexts not provided"
    )


def _fail_job_quietly(db, job, job_id_str: str) -> None:
    """Best-effort "the queue rejected this" marker on an already-committed row.

    The sync ``SessionLocal`` leaves ``expire_on_commit=True`` (unlike
    ``AsyncSessionLocal``), so ``job`` is expired here and ``fail_job`` reads
    ``started_at`` — a lazy refresh. When the outage is shared infrastructure
    rather than Redis alone, that refresh (or the commit) raises *inside* the
    except block, escapes to the outer 500 handler, and the caller loses the
    503 this path exists to deliver. Swallow it: an unmarked row is a smaller
    problem than a misreported status.
    """
    logger.exception(
        "evaluation enqueue failed for job %s — marking failed", job_id_str
    )
    try:
        job.fail_job("Evaluation queue unavailable; the job was not started.")
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("could not mark evaluation job %s failed", job_id_str)


# Evaluation job endpoints
@router.post("/jobs", response_model=Dict[str, Any])
async def create_evaluation_job(
    request: DatasetEvaluationRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
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

        # R5-L13: EvaluationType(...) raises ValueError on an unrecognized
        # free-string evaluation_type — surface it as a 400, not a 500.
        try:
            parsed_evaluation_type = EvaluationType(request.evaluation_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown evaluation_type: {request.evaluation_type!r}",
            )

        # R5-H6: build the real dataset items here so create_evaluation_job
        # persists ONE EvaluationDataset row with the actual questions —
        # this endpoint used to pass dataset=[] and then insert a SECOND,
        # populated EvaluationDataset itself. The task fetched whichever of
        # the two rows `.first()` happened to return; the empty one usually
        # won and the job failed with "No items were successfully processed".
        dataset_items = [
            RAGEvaluationInput(
                query=question,
                generated_answer="",
                retrieved_context=(request.contexts[i] if request.contexts else []),
                reference_answer=(
                    request.reference_answers[i] if request.reference_answers else None
                ),
                search_type=request.search_type,
            )
            for i, question in enumerate(request.questions)
        ]

        # Create evaluation request
        evaluation_request = EvaluationRequest(
            name=request.name,
            description=request.description,
            evaluation_type=parsed_evaluation_type,
            dataset=dataset_items,
            parameters={
                "search_type": request.search_type,
                "search_limit": request.search_limit,
            },
            user_id=str(current_user.id),
            organization_id=str(current_user.organization_id),
        )

        # Create evaluation job — this also persists the single
        # EvaluationDataset row built from dataset_items above.
        job = await rag_evaluation_service.create_evaluation_job(evaluation_request, db)

        # Enqueue inline so a broker failure reaches the caller — see the note
        # in create_batch_evaluation_job.
        job_id_str = str(job.id)
        try:
            run_rag_triad_evaluation.delay(job_id_str)
        except OperationalError:
            _fail_job_quietly(db, job, job_id_str)
            raise HTTPException(
                status_code=503,
                detail="Evaluation queue unavailable. Please retry.",
            )

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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/jobs/batch", response_model=Dict[str, Any])
async def create_batch_evaluation_job(
    request: BatchEvaluationRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
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

        # Enqueue LAST, inline, and inside try — the row is durable first, so
        # the worker's claim always finds it. Going through
        # ``background_tasks.add_task`` deferred the enqueue until after the
        # response was sent, so a broker failure could not be reported: the
        # caller received a job_id for a job that would never run and would
        # poll a "pending" row forever. Mirrors the dispatch in
        # ``api/agent/execute.py`` and the sibling ``/real-time`` endpoint.
        job_id_str = str(job.id)
        try:
            run_batch_evaluation.delay(job_id_str, request.queries)
        except OperationalError:
            _fail_job_quietly(db, job, job_id_str)
            raise HTTPException(
                status_code=503,
                detail="Evaluation queue unavailable. Please retry.",
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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/real-time", response_model=Dict[str, Any])
async def evaluate_real_time(
    request: RealTimeEvaluationRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
):
    """
    Perform real-time evaluation of a single query-answer pair
    """
    try:
        # Start real-time evaluation task
        try:
            task = run_real_time_evaluation.delay(
                request.query,
                request.generated_answer,
                request.retrieved_context,
                request.reference_answer,
                str(current_user.organization_id),
            )
        except OperationalError:
            logger.exception("real-time evaluation enqueue failed")
            raise HTTPException(
                status_code=503,
                detail="Evaluation queue unavailable. Please retry.",
            )

        logger.info(f"Started real-time evaluation for user {current_user.id}")

        return {
            "task_id": task.id,
            "status": "started",
            "message": "Real-time evaluation started",
        }

    # R5-M14: this was the only endpoint in the file missing this
    # re-raise, so the 503 raised above fell into the except Exception
    # below and was reported to the caller as a 500 (a permanent-defect
    # code) instead of the retryable outage it actually is.
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting real-time evaluation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_evaluation_job(
    job_id: str, current_user: User = Depends(get_current_user), db=Depends(get_db_sync)
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
                EvaluationJob.is_deleted.is_(False),
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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jobs", response_model=List[Dict[str, Any]])
async def list_evaluation_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    evaluation_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
):
    """
    List evaluation jobs for the current user's organization
    """
    try:
        query = db.query(EvaluationJob).filter(
            EvaluationJob.organization_id == current_user.organization_id,
            EvaluationJob.is_deleted.is_(False),
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
                "completed_at": (
                    job.completed_at.isoformat() if job.completed_at else None
                ),
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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/jobs/{job_id}/metrics", response_model=List[Dict[str, Any]])
async def get_evaluation_metrics(
    job_id: str,
    metric_types: Optional[List[str]] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
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
                EvaluationJob.is_deleted.is_(False),
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
                # R5-H5: the model column is metric_metadata — .metadata on
                # a SQLAlchemy declarative instance is the class-level
                # MetaData object, not this row's data, and .get() on it
                # raised AttributeError (500).
                "calculation_method": (
                    metric.metric_metadata.get("calculation_method")
                    if metric.metric_metadata
                    else None
                ),
                "model_used": (
                    metric.metric_metadata.get("model_used")
                    if metric.metric_metadata
                    else None
                ),
                "created_at": metric.created_at.isoformat(),
            }
            for metric in metrics
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting evaluation metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Comparison endpoints
@router.post("/comparisons", response_model=Dict[str, Any])
async def create_evaluation_comparison(
    request: ComparisonRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
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
                EvaluationJob.is_deleted.is_(False),
            )
            .first()
        )

        comparison_job = (
            db.query(EvaluationJob)
            .filter(
                EvaluationJob.id == request.comparison_job_id,
                EvaluationJob.organization_id == current_user.organization_id,
                EvaluationJob.is_deleted.is_(False),
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

        # Enqueue inline: this endpoint reports "started", so a deferred
        # enqueue that fails post-response would report a comparison that
        # never runs. See the note in create_batch_evaluation_job.
        try:
            run_comparison_evaluation.delay(
                request.name,
                request.baseline_job_id,
                request.comparison_job_id,
                str(current_user.id),
                str(current_user.organization_id),
            )
        except OperationalError:
            logger.exception("comparison enqueue failed for %s", request.name)
            raise HTTPException(
                status_code=503,
                detail="Evaluation queue unavailable. Please retry.",
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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/comparisons", response_model=List[Dict[str, Any]])
async def list_evaluation_comparisons(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
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
        raise HTTPException(status_code=500, detail="Internal server error")


# Report endpoints
# NOTE: the endpoint must NOT be named `generate_evaluation_report` — that
# rebinds the module global imported from evaluation_tasks, so the
# `generate_evaluation_report.delay(...)` call below would resolve to this
# endpoint function (no .delay → AttributeError inside BackgroundTasks,
# swallowed post-response) and reports would never be generated.
@router.post("/jobs/{job_id}/reports/{report_type}", response_model=Dict[str, Any])
async def trigger_evaluation_report(
    job_id: str,
    report_type: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
):
    """
    Generate a report for an evaluation job
    """
    try:
        # R5-L13: report_type is a free string the task later matches against
        # {"summary", "detailed"}, raising ValueError (post-200, inside the
        # worker) for anything else. Reject it here instead.
        if report_type not in ("summary", "detailed"):
            raise HTTPException(
                status_code=400,
                detail=f"Unknown report_type: {report_type!r} (expected 'summary' or 'detailed')",
            )

        # Verify job exists and user has access
        job = (
            db.query(EvaluationJob)
            .filter(
                EvaluationJob.id == job_id,
                EvaluationJob.organization_id == current_user.organization_id,
                EvaluationJob.is_deleted.is_(False),
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

        # Enqueue inline: the endpoint reports "started". Only broker errors
        # become 503 — the module-global shadowing hazard noted above raises
        # AttributeError, which must reach the 500 handler rather than be
        # reported to the caller as a retryable outage.
        try:
            generate_evaluation_report.delay(job_id, report_type)
        except OperationalError:
            logger.exception("report enqueue failed for job %s", job_id)
            raise HTTPException(
                status_code=503,
                detail="Report queue unavailable. Please retry.",
            )

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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/reports", response_model=List[Dict[str, Any]])
async def list_evaluation_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
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
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/reports/{report_id}", response_model=Dict[str, Any])
async def get_evaluation_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
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
        raise HTTPException(status_code=500, detail="Internal server error")


# Metrics and analytics endpoints
@router.get("/metrics/summary", response_model=Dict[str, Any])
async def get_metrics_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db_sync),
):
    """
    Get summary of evaluation metrics for the organization
    """
    try:
        from datetime import timedelta

        start_date = datetime.utcnow() - timedelta(days=days)

        # R5-L15: aggregate in SQL (count/avg/min/max grouped by metric_type)
        # instead of pulling every EvaluationMetric row — including its Text
        # columns (query, generated_answer, retrieved_context) and JSON
        # columns (metric_metadata, additional_data) — into Python only to
        # throw them away. std_dev still needs the raw values (portable
        # across the sync-engine's SQLite test config and Postgres, unlike
        # func.stddev_samp), so that one query selects just the float column,
        # not full ORM rows.
        base_filter = (
            EvaluationJob.organization_id == current_user.organization_id,
            EvaluationJob.created_at >= start_date,
            EvaluationJob.status == EvaluationStatus.COMPLETED.value,
            EvaluationJob.is_deleted.is_(False),
        )

        aggregates = (
            db.query(
                EvaluationMetric.metric_type,
                func.count(EvaluationMetric.id),
                func.avg(EvaluationMetric.value),
                func.min(EvaluationMetric.value),
                func.max(EvaluationMetric.value),
                func.sum(func.cast(EvaluationMetric.is_threshold_violation, Integer)),
            )
            .join(EvaluationJob, EvaluationMetric.job_id == EvaluationJob.id)
            .filter(*base_filter)
            .group_by(EvaluationMetric.metric_type)
            .all()
        )

        if not aggregates:
            return {
                "period_days": days,
                "total_metrics": 0,
                "metric_summary": {},
                "threshold_violations": 0,
                "average_scores": {},
            }

        # Only the float values, only for the std_dev calculation.
        values_by_type: Dict[str, List[float]] = {}
        for metric_type, value in (
            db.query(EvaluationMetric.metric_type, EvaluationMetric.value)
            .join(EvaluationJob, EvaluationMetric.job_id == EvaluationJob.id)
            .filter(*base_filter)
            .all()
        ):
            values_by_type.setdefault(metric_type, []).append(value)

        import statistics

        metric_summary = {}
        average_scores = {}
        total_metrics = 0
        total_violations = 0

        for (
            metric_type,
            count,
            avg_value,
            min_value,
            max_value,
            violations,
        ) in aggregates:
            values = values_by_type.get(metric_type, [])
            metric_summary[metric_type] = {
                "count": count,
                "mean": float(avg_value) if avg_value is not None else 0.0,
                "min": float(min_value) if min_value is not None else 0.0,
                "max": float(max_value) if max_value is not None else 0.0,
                "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
            }
            average_scores[metric_type] = (
                float(avg_value) if avg_value is not None else 0.0
            )
            total_metrics += count
            total_violations += violations or 0

        return {
            "period_days": days,
            "total_metrics": total_metrics,
            "metric_summary": metric_summary,
            "threshold_violations": total_violations,
            "average_scores": average_scores,
            "violation_rate": (
                (total_violations / total_metrics) * 100 if total_metrics else 0
            ),
        }

    except Exception as e:
        logger.error(f"Error getting metrics summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/jobs/{job_id}")
async def delete_evaluation_job(
    job_id: str, current_user: User = Depends(get_current_user), db=Depends(get_db_sync)
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
                EvaluationJob.is_deleted.is_(False),
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
        raise HTTPException(status_code=500, detail="Internal server error")


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
