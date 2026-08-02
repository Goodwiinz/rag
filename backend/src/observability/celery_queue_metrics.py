"""Prometheus collector exporting Celery broker (Redis) queue depths.

Audit finding X5 (remediation item P1.6): the ``celery-worker`` HPA
(``infrastructure/helm/knowledge-graph-analytics/templates/hpa.yaml``) scales on
CPU + memory only, which is backlog-blind for the I/O-bound LLM/ingestion tasks
the worker runs — a queue of pending jobs can build up while CPU/RAM stay low,
so the HPA never adds replicas.

This module exports the raw signal a backlog-aware autoscaler (KEDA
``redisStreams``/``redis`` scaler, or ``prometheus-adapter`` external metric)
would eventually consume:

    celery_queue_depth{queue="<name>"}  -> pending tasks in that Redis broker list

HPA *wiring* is intentionally deferred (no KEDA / prometheus-adapter is deployed
in the cluster today — see the PR body and the values-level TODO in
``values-dev.yaml``). This lands the metric so the scaling pipeline can be built
on a real, observed signal rather than guesswork.

Design notes:
- Implemented as a pull-based ``Collector`` registered on the global
  ``prometheus_client`` REGISTRY — the same registry the agent metrics
  (``agent_execution_duration_seconds`` etc.) use. ``generate_latest`` invokes
  ``collect()`` at scrape time, so each scrape reads a fresh ``LLEN`` with no
  background loop or beat task to keep alive.
- Redis errors are swallowed (the affected series is simply omitted for that
  scrape) so a broker blip can never turn the ``/metrics`` endpoint into a 500.
- Celery's Redis broker stores pending tasks for a queue in a plain Redis LIST
  keyed by the queue name; ``LLEN`` is the pending backlog. This is accurate
  because no priority transport options (``priority_steps``/``sep``) are
  configured on ``celery_app`` — priority queues would otherwise shard across
  suffixed keys.
"""

from __future__ import annotations

import ssl
from typing import Iterable, Optional

import structlog
from prometheus_client import REGISTRY
from prometheus_client.core import GaugeMetricFamily

logger = structlog.get_logger(__name__)

# Queues the celery-worker deployment drains. Kept explicit (rather than derived
# from ``celery_app.conf.task_queues``) so the exported series set is stable and
# includes the queues declared only on the worker ``-Q`` flag
# (``entity_processing``/``graph_processing``). Must stay in sync with the ``-Q``
# list in templates/celery-worker-deployment.yaml.
CELERY_QUEUE_NAMES = (
    "celery",
    "document_processing",
    "high_priority",
    "low_priority",
    "entity_processing",
    "graph_processing",
    "agent_runs",
)

_METRIC_NAME = "celery_queue_depth"

# Module-level singleton guard so repeated registration (dev hot-reload, double
# ``configure_metrics`` calls) does not raise ``ValueError: Duplicated`` from the
# global registry.
_registered_collector: Optional["CeleryQueueDepthCollector"] = None


def _build_redis_client(redis_url: str):
    """Create a sync Redis client, mirroring celery_app's TLS handling.

    DO Managed Redis uses ``rediss://`` (TLS); Celery is configured with
    ``ssl_cert_reqs=CERT_NONE`` for it, so we match that here to avoid cert
    verification failures against the managed endpoint.
    """
    import redis

    if redis_url.startswith("rediss://"):
        return redis.from_url(redis_url, ssl_cert_reqs=ssl.CERT_NONE)
    return redis.from_url(redis_url)


class CeleryQueueDepthCollector:
    """Pull-based Prometheus collector for the Celery/Redis broker backlog."""

    def __init__(
        self,
        redis_url: str,
        queue_names: Iterable[str] = CELERY_QUEUE_NAMES,
    ) -> None:
        self._redis_url = redis_url
        self._queue_names = tuple(queue_names)
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = _build_redis_client(self._redis_url)
        return self._client

    def collect(self):
        gauge = GaugeMetricFamily(
            _METRIC_NAME,
            "Number of pending Celery tasks in each Redis broker queue (LLEN).",
            labels=["queue"],
        )

        try:
            client = self._get_client()
        except Exception:  # noqa: BLE001 - never break /metrics on a broker issue
            logger.debug("celery_queue_depth_client_init_failed", exc_info=True)
            # Reset so a later scrape can retry building the client.
            self._client = None
            yield gauge
            return

        for queue in self._queue_names:
            try:
                depth = client.llen(queue)
            except Exception:  # noqa: BLE001 - skip this queue, keep the rest
                logger.debug(
                    "celery_queue_depth_llen_failed", queue=queue, exc_info=True
                )
                # Drop the cached client so a fresh connection is used next scrape.
                self._client = None
                continue
            gauge.add_metric([queue], float(depth))

        yield gauge


def register_celery_queue_depth_collector(
    redis_url: str,
    registry=REGISTRY,
    queue_names: Iterable[str] = CELERY_QUEUE_NAMES,
) -> Optional[CeleryQueueDepthCollector]:
    """Register the queue-depth collector on ``registry`` (idempotent).

    Returns the collector (existing or newly created). Safe to call multiple
    times; only the first call registers.
    """
    global _registered_collector

    if _registered_collector is not None:
        return _registered_collector

    if not redis_url:
        logger.info("celery_queue_depth_collector_skipped_no_redis_url")
        return None

    collector = CeleryQueueDepthCollector(redis_url, queue_names=queue_names)
    try:
        registry.register(collector)
    except ValueError:
        # Already registered (e.g. duplicate metric name) — treat as success.
        logger.debug("celery_queue_depth_collector_already_registered")
        _registered_collector = collector
        return collector

    _registered_collector = collector
    logger.info(
        "celery_queue_depth_collector_registered", queues=list(collector._queue_names)
    )
    return collector
