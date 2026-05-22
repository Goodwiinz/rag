"""
Celery task for async thread summarization.
"""

import asyncio
import logging
import os
import sys
from typing import Optional
from uuid import UUID

# Add src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from celery import Task, current_app, group

from src.core.config import settings
from src.core.database import SessionLocal
from src.models.thread import Thread, ThreadStatus

logger = logging.getLogger(__name__)


class SummarizationTask(Task):
    """Base class for summarization tasks with error handling."""

    autoretry_for = (Exception,)
    retry_kwargs = {"max_retries": 3, "countdown": 5}
    retry_backoff = True

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Summarization task {task_id} completed successfully")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Summarization task {task_id} failed: {str(exc)}")

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(f"Summarization task {task_id} retrying: {str(exc)}")


@current_app.task(base=SummarizationTask, bind=True, name="tasks.summarize_thread")
def summarize_thread_task(self, thread_id: str, force: bool = False) -> Optional[str]:
    """
    Celery task to generate summary for a thread.

    Args:
        thread_id: Thread UUID as string
        force: Skip rate limit check if True

    Returns:
        Generated summary or None
    """
    db = SessionLocal()
    try:
        thread_uuid = UUID(thread_id)

        # Check thread exists
        thread = db.query(Thread).filter(Thread.id == thread_uuid).first()
        if not thread:
            logger.warning(f"Thread {thread_id} not found for summarization")
            return None

        # Import service here to avoid circular imports
        from src.services.threads.thread_summarization_service import (
            get_thread_summarization_service,
        )

        service = get_thread_summarization_service(db)

        # Run async summary generation using asyncio.run()
        # This properly handles event loop lifecycle (creation, running, cleanup)
        summary = asyncio.run(service.generate_summary(thread_uuid, force=force))

        if summary:
            logger.info(f"Generated summary for thread {thread_id}: {summary[:50]}...")
        else:
            logger.info(f"No summary generated for thread {thread_id}")

        return summary

    except Exception as e:
        logger.error(f"Failed to summarize thread {thread_id}: {e}")
        raise
    finally:
        db.close()


@current_app.task(
    base=SummarizationTask, bind=True, name="tasks.summarize_thread_on_resolve"
)
def summarize_thread_on_resolve_task(self, thread_id: str) -> None:
    """
    Generate final summary when thread is resolved.

    Always generates summary regardless of rate limit.
    """
    summarize_thread_task.delay(thread_id, force=True)


@current_app.task(name="tasks.batch_summarize_threads")
def batch_summarize_threads_task(thread_ids: list[str]) -> dict:
    """
    Batch summarize multiple threads in parallel.

    Uses Celery group to dispatch all summarization tasks concurrently,
    improving throughput and reducing total execution time.

    Args:
        thread_ids: List of thread UUIDs as strings

    Returns:
        Dict with success/failure counts
    """
    results = {
        "total": len(thread_ids),
        "success": 0,
        "failed": 0,
        "skipped": 0,
    }

    # Create parallel task group
    job = group(
        summarize_thread_task.s(thread_id, force=False) for thread_id in thread_ids
    )

    try:
        # Execute in parallel with 5 minute timeout
        group_result = job.apply_async()
        task_results = group_result.get(timeout=300)

        # Aggregate results
        for task_result in task_results:
            if task_result:  # Summary was generated
                results["success"] += 1
            else:  # Summary was skipped (e.g., already exists)
                results["skipped"] += 1

    except Exception as e:
        logger.error(f"Batch summarization failed: {e}")
        results["failed"] = len(thread_ids) - results["success"] - results["skipped"]

    logger.info(f"Batch summarization complete: {results}")
    return results
