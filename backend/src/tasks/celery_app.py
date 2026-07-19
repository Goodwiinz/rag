"""
Unified Celery application configuration.

All task modules should import celery_app from this module:
    from src.tasks.celery_app import celery_app
"""

import logging
import ssl

from celery import Celery

from src.core.config import settings

logger = logging.getLogger(__name__)

# Build SSL config when using rediss:// (TLS) connections
_redis_uses_tls = settings.REDIS_URL.startswith("rediss://")
_broker_use_ssl = {"ssl_cert_reqs": ssl.CERT_NONE} if _redis_uses_tls else None

_backend_url = (
    f"{settings.REDIS_URL}?ssl_cert_reqs=CERT_NONE"
    if _redis_uses_tls
    else settings.REDIS_URL
)

celery_app = Celery(
    "nous",
    broker=settings.REDIS_URL,
    backend=_backend_url,
    include=[
        "src.tasks.processing_tasks",
        "src.tasks.document_processing_tasks",
        "src.tasks.summarize_thread_task",
        "src.tasks.evaluation_tasks",
        "src.tasks.research_tasks",
    ],
)

_ssl_conf = {}
if _redis_uses_tls:
    _ssl_conf = {
        "broker_use_ssl": _broker_use_ssl,
        "redis_backend_use_ssl": _broker_use_ssl,
    }

celery_app.conf.update(
    **_ssl_conf,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Bound worker memory to stop unbounded RSS growth from OOM-evicting the pod.
    # A child process is recycled after 100 tasks, or once its resident memory
    # crosses ~900MB (value is in KB). With --concurrency=2 this keeps total
    # worker RSS (2 x ~900MB) under the pod's 2Gi memory limit.
    worker_max_tasks_per_child=100,
    worker_max_memory_per_child=900000,
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
