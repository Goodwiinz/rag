"""
Celery tasks for evaluation processing and RAG Triad metrics calculation
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List

from celery import Task

# Add src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from celery import Celery, current_app

from src.core.config import settings
from src.core.database import SessionLocal, get_db
from src.models.document import Document
from src.models.evaluation import (
    EvaluationDataset,
    EvaluationJob,
    EvaluationMetric,
    EvaluationStatus,
    EvaluationType,
)
from src.services.evaluation.rag_evaluation_service import (
    EvaluationRequest,
    RAGEvaluationInput,
    rag_evaluation_service,
)

logger = logging.getLogger(__name__)


class EvaluationTask(Task):
    """Base class for evaluation tasks"""

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(f"Evaluation task {task_id} completed successfully")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(f"Evaluation task {task_id} failed: {str(exc)}")

        # Update job status if this is an evaluation job
        if args and len(args) > 0:
            job_id = args[0]
            db = SessionLocal()
            try:
                job = db.query(EvaluationJob).filter(EvaluationJob.id == job_id).first()

                if job:
                    job.fail_job(str(exc))
                    db.commit()
            except Exception as e:
                logger.error(f"Failed to update evaluation job status: {str(e)}")
            finally:
                db.close()


@current_app.task(base=EvaluationTask, bind=True)
def run_rag_triad_evaluation(self, job_id: str):
    """
    Run complete RAG Triad evaluation for a job
    """
    db = SessionLocal()
    try:
        # Get evaluation job
        job = db.query(EvaluationJob).filter(EvaluationJob.id == job_id).first()

        if not job:
            raise ValueError(f"Evaluation job {job_id} not found")

        # Get evaluation dataset
        dataset = (
            db.query(EvaluationDataset)
            .filter(EvaluationDataset.job_id == job_id)
            .first()
        )

        if not dataset:
            raise ValueError(f"Evaluation dataset for job {job_id} not found")

        # Start job
        job.start_job()
        job.update_progress(0)
        db.commit()

        logger.info(f"Starting RAG Triad evaluation for job {job_id}")

        # Process each evaluation item
        questions = dataset.questions or []
        reference_answers = dataset.reference_answers or []
        contexts = dataset.contexts or []

        total_items = len(questions)
        processed_items = 0
        metrics_results = []

        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for i, question in enumerate(questions):
                try:
                    # Create evaluation input
                    evaluation_input = RAGEvaluationInput(
                        query=question,
                        generated_answer="",  # Will be generated during evaluation
                        retrieved_context=contexts[i] if i < len(contexts) else [],
                        reference_answer=reference_answers[i]
                        if i < len(reference_answers)
                        else None,
                        metadata={"item_index": i, "total_items": total_items},
                    )

                    # If no provided context, perform search
                    if not evaluation_input.retrieved_context:
                        search_results = loop.run_until_complete(
                            rag_evaluation_service.evaluate_search_pipeline(
                                [question],
                                str(job.organization_id),
                                str(job.user_id) if job.user_id else "anonymous",
                                search_type=job.parameters.get("search_type", "hybrid"),
                                limit=job.parameters.get("search_limit", 5),
                            )
                        )

                        if search_results:
                            evaluation_input.generated_answer = search_results[
                                0
                            ].metadata.get("generated_answer", "")
                            evaluation_input.retrieved_context = search_results[
                                0
                            ].metadata.get("retrieved_context", [])
                    else:
                        # Generate simple answer from context
                        evaluation_input.generated_answer = (
                            rag_evaluation_service._generate_simple_answer(
                                question, evaluation_input.retrieved_context
                            )
                        )

                    # Calculate RAG Triad metrics
                    metrics = loop.run_until_complete(
                        rag_evaluation_service.run_rag_triad_evaluation(
                            evaluation_input, job_id, str(job.organization_id), db
                        )
                    )

                    metrics_results.append(metrics)
                    processed_items += 1

                    # Update progress
                    progress = int((processed_items / total_items) * 100)
                    job.update_progress(processed_items)
                    db.commit()

                    logger.info(f"Processed item {i+1}/{total_items} for job {job_id}")

                except Exception as item_error:
                    logger.error(
                        f"Error processing item {i} for job {job_id}: {str(item_error)}"
                    )
                    continue

        finally:
            loop.close()

        # Calculate overall metrics
        if metrics_results:
            overall_answer_relevancy = sum(
                m.answer_relevancy for m in metrics_results
            ) / len(metrics_results)
            overall_faithfulness = sum(m.faithfulness for m in metrics_results) / len(
                metrics_results
            )
            overall_contextual_relevancy = sum(
                m.contextual_relevancy for m in metrics_results
            ) / len(metrics_results)
            overall_score = sum(m.overall_score for m in metrics_results) / len(
                metrics_results
            )

            # Success rate (items with score > 0.5)
            successful_items = sum(1 for m in metrics_results if m.overall_score > 0.5)
            success_rate = (successful_items / len(metrics_results)) * 100

            # Complete job
            job.complete_job(overall_score=overall_score, success_rate=success_rate)
            db.commit()

            logger.info(f"RAG Triad evaluation completed for job {job_id}")
            logger.info(
                f"Overall score: {overall_score:.3f}, Success rate: {success_rate:.1f}%"
            )

            return {
                "status": "completed",
                "job_id": job_id,
                "processed_items": processed_items,
                "total_items": total_items,
                "overall_score": overall_score,
                "success_rate": success_rate,
                "duration_seconds": job.duration_seconds,
            }

        else:
            job.fail_job("No items were successfully processed")
            db.commit()
            raise ValueError("No items were successfully processed")

    except Exception as e:
        logger.error(f"RAG Triad evaluation failed for job {job_id}: {str(e)}")

        # Update job status
        try:
            if job:
                job.fail_job(str(e))
                db.commit()
        except Exception as update_error:
            logger.error(f"Failed to update job failure status: {str(update_error)}")

        raise

    finally:
        db.close()


@current_app.task(base=EvaluationTask, bind=True)
def run_batch_evaluation(self, job_id: str, queries: List[str]):
    """
    Run batch evaluation for a list of queries
    """
    db = SessionLocal()
    try:
        # Get evaluation job
        job = db.query(EvaluationJob).filter(EvaluationJob.id == job_id).first()

        if not job:
            raise ValueError(f"Evaluation job {job_id} not found")

        # Start job
        job.start_job()
        job.update_progress(0)
        db.commit()

        logger.info(
            f"Starting batch evaluation for job {job_id} with {len(queries)} queries"
        )

        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Run evaluation for all queries
            metrics_results = loop.run_until_complete(
                rag_evaluation_service.evaluate_search_pipeline(
                    queries,
                    str(job.organization_id),
                    str(job.user_id) if job.user_id else "anonymous",
                    search_type=job.parameters.get("search_type", "hybrid"),
                    limit=job.parameters.get("search_limit", 5),
                )
            )

            # Save metrics to database
            for i, metrics in enumerate(metrics_results):
                try:
                    metric = EvaluationMetric(
                        job_id=job_id,
                        metric_type="rag_triad_overall",
                        metric_name="Overall RAG Triad Score",
                        value=metrics.overall_score,
                        query=queries[i],
                        generated_answer=metrics.metadata.get("generated_answer", ""),
                        retrieved_context=metrics.metadata.get("retrieved_context", []),
                        metadata={
                            "answer_relevancy": metrics.answer_relevancy,
                            "faithfulness": metrics.faithfulness,
                            "contextual_relevancy": metrics.contextual_relevancy,
                            "hallucination_rate": metrics.hallucination_rate,
                            "response_time_ms": metrics.response_time_ms,
                        },
                    )

                    db.add(metric)

                except Exception as metric_error:
                    logger.error(
                        f"Error saving metric for query {i}: {str(metric_error)}"
                    )
                    continue

            db.commit()

            # Calculate overall metrics
            if metrics_results:
                overall_score = sum(m.overall_score for m in metrics_results) / len(
                    metrics_results
                )
                success_rate = (
                    sum(1 for m in metrics_results if m.overall_score > 0.5)
                    / len(metrics_results)
                    * 100
                )

                job.complete_job(overall_score=overall_score, success_rate=success_rate)
                db.commit()

                return {
                    "status": "completed",
                    "job_id": job_id,
                    "processed_queries": len(metrics_results),
                    "total_queries": len(queries),
                    "overall_score": overall_score,
                    "success_rate": success_rate,
                }

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Batch evaluation failed for job {job_id}: {str(e)}")

        # Update job status
        try:
            if job:
                job.fail_job(str(e))
                db.commit()
        except Exception as update_error:
            logger.error(f"Failed to update job failure status: {str(update_error)}")

        raise

    finally:
        db.close()


@current_app.task(base=EvaluationTask, bind=True)
def run_real_time_evaluation(
    self,
    query: str,
    generated_answer: str,
    retrieved_context: List[str],
    reference_answer: str = None,
    organization_id: str = None,
):
    """
    Run real-time evaluation for a single query-answer pair
    """
    db = SessionLocal()
    try:
        # Create a temporary evaluation job for real-time evaluation
        job = EvaluationJob(
            name=f"Real-time Evaluation: {query[:50]}...",
            evaluation_type=EvaluationType.REAL_TIME_EVALUATION.value,
            parameters={"real_time": True, "query": query},
            dataset_size=1,
            organization_id=organization_id,
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        logger.info(f"Starting real-time evaluation for query: {query[:100]}...")

        # Create evaluation input
        evaluation_input = RAGEvaluationInput(
            query=query,
            generated_answer=generated_answer,
            retrieved_context=retrieved_context,
            reference_answer=reference_answer,
            metadata={"real_time_evaluation": True},
        )

        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Calculate metrics
            metrics = loop.run_until_complete(
                rag_evaluation_service.run_rag_triad_evaluation(
                    evaluation_input, job.id, organization_id, db
                )
            )

            # Complete job
            job.complete_job(
                overall_score=metrics.overall_score,
                success_rate=100.0 if metrics.overall_score > 0.5 else 0.0,
            )
            db.commit()

            return {
                "status": "completed",
                "job_id": str(job.id),
                "metrics": {
                    "answer_relevancy": metrics.answer_relevancy,
                    "faithfulness": metrics.faithfulness,
                    "contextual_relevancy": metrics.contextual_relevancy,
                    "overall_score": metrics.overall_score,
                    "hallucination_rate": metrics.hallucination_rate,
                    "response_time_ms": metrics.response_time_ms,
                },
            }

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Real-time evaluation failed: {str(e)}")

        # Update job status
        try:
            if job:
                job.fail_job(str(e))
                db.commit()
        except Exception as update_error:
            logger.error(f"Failed to update job failure status: {str(update_error)}")

        raise

    finally:
        db.close()


@current_app.task(base=EvaluationTask, bind=True)
def run_comparison_evaluation(
    self,
    comparison_name: str,
    baseline_job_id: str,
    comparison_job_id: str,
    user_id: str,
    organization_id: str,
):
    """
    Run comparison between two evaluation jobs
    """
    db = SessionLocal()
    try:
        logger.info(f"Starting comparison evaluation: {comparison_name}")

        # Create event loop for async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Perform comparison
            comparison = loop.run_until_complete(
                rag_evaluation_service.compare_evaluations(
                    baseline_job_id,
                    comparison_job_id,
                    comparison_name,
                    user_id,
                    organization_id,
                    db,
                )
            )

            logger.info(f"Comparison evaluation completed: {comparison_name}")
            logger.info(f"Improvement: {comparison.improvement_percentage:.2f}%")

            return {
                "status": "completed",
                "comparison_id": str(comparison.id),
                "improvement_percentage": comparison.improvement_percentage,
                "statistical_significance": comparison.statistical_significance,
                "baseline_score": comparison.baseline_score,
                "comparison_score": comparison.comparison_score,
            }

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Comparison evaluation failed: {str(e)}")
        raise

    finally:
        db.close()


@current_app.task
def cleanup_old_evaluations():
    """
    Cleanup old evaluation jobs and metrics
    """
    db = SessionLocal()
    try:
        # Delete evaluation jobs older than 90 days
        cutoff_date = datetime.utcnow() - timedelta(days=90)

        old_jobs = (
            db.query(EvaluationJob)
            .filter(
                EvaluationJob.created_at < cutoff_date,
                EvaluationJob.status.in_(
                    [
                        EvaluationStatus.COMPLETED.value,
                        EvaluationStatus.FAILED.value,
                        EvaluationStatus.CANCELLED.value,
                    ]
                ),
            )
            .all()
        )

        deleted_count = 0
        for job in old_jobs:
            try:
                db.delete(job)
                deleted_count += 1
            except Exception as delete_error:
                logger.error(f"Error deleting job {job.id}: {str(delete_error)}")
                continue

        db.commit()
        logger.info(f"Cleaned up {deleted_count} old evaluation jobs")

        return {"cleaned_jobs": deleted_count}

    except Exception as e:
        logger.error(f"Evaluation cleanup failed: {str(e)}")
        raise

    finally:
        db.close()


@current_app.task
def generate_evaluation_report(job_id: str, report_type: str = "summary"):
    """
    Generate evaluation report for a completed job
    """
    db = SessionLocal()
    try:
        # Get evaluation job
        job = db.query(EvaluationJob).filter(EvaluationJob.id == job_id).first()

        if not job:
            raise ValueError(f"Evaluation job {job_id} not found")

        if job.status != EvaluationStatus.COMPLETED.value:
            raise ValueError(f"Evaluation job {job_id} is not completed")

        logger.info(f"Generating {report_type} report for job {job_id}")

        # Get evaluation summary
        summary = rag_evaluation_service.get_evaluation_summary(
            job_id, str(job.organization_id), db
        )

        # Generate report content
        if report_type == "summary":
            content = rag_evaluation_service._generate_summary_report(summary)
        elif report_type == "detailed":
            content = rag_evaluation_service._generate_detailed_report(job_id, db)
        else:
            raise ValueError(f"Unknown report type: {report_type}")

        # Create evaluation report record
        from src.models.evaluation import EvaluationReport

        report = EvaluationReport(
            title=f"{report_type.title()} Report: {job.name}",
            report_type=report_type,
            job_id=job_id,
            content=content,
            executive_summary=content[:500] + "..." if len(content) > 500 else content,
            key_findings=[
                f"Overall Score: {summary.get('overall_score', 'N/A')}",
                f"Success Rate: {summary.get('success_rate', 'N/A')}%",
                f"Total Metrics: {summary.get('total_metrics', 0)}",
                f"Threshold Violations: {summary.get('threshold_violations', 0)}",
            ],
            format_type="markdown",
            user_id=str(job.user_id) if job.user_id else None,
            organization_id=str(job.organization_id),
        )

        db.add(report)
        db.commit()

        logger.info(f"Report generated for job {job_id}: {report.id}")

        return {
            "status": "completed",
            "report_id": str(report.id),
            "report_type": report_type,
            "job_id": job_id,
        }

    except Exception as e:
        logger.error(f"Report generation failed for job {job_id}: {str(e)}")
        raise

    finally:
        db.close()


# Periodic tasks
from celery.schedules import crontab

current_app.conf.beat_schedule = {
    "cleanup-old-evaluations": {
        "task": "src.tasks.evaluation_tasks.cleanup_old_evaluations",
        "schedule": crontab(hour=3, minute=0),  # Run daily at 3 AM
    },
}
