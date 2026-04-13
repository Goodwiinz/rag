"""
Unified Celery application configuration.

All task modules should import celery_app from this module:
    from src.tasks.celery_app import celery_app
"""

import logging

from celery import Celery

from src.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "nous",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "src.tasks.processing_tasks",
        "src.tasks.document_processing_tasks",
        "src.tasks.summarize_thread_task",
        "src.tasks.evaluation_tasks",
        "src.tasks.research_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="celery",
    task_queues={
        "celery": {"exchange": "celery", "routing_key": "celery"},
        "document_processing": {
            "exchange": "document_processing",
            "routing_key": "document_processing",
        },
        "high_priority": {
            "exchange": "high_priority",
            "routing_key": "high_priority",
        },
        "low_priority": {
            "exchange": "low_priority",
            "routing_key": "low_priority",
        },
    },
    task_routes={
        "src.tasks.document_processing_tasks.process_document_upload": {
            "queue": "document_processing",
        },
        "src.tasks.document_processing_tasks.process_high_priority_document": {
            "queue": "high_priority",
        },
        "src.tasks.document_processing_tasks.process_low_priority_document": {
            "queue": "low_priority",
        },
    },
    task_default_retry_delay=60,
    task_max_retries=3,
    task_soft_time_limit=300,
    task_time_limit=600,
)

logger.info(f"Celery app configured with broker: {settings.REDIS_URL[:20]}...")
