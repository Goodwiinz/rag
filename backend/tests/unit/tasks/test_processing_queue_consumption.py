"""Every processing dispatch queue must be consumed by the Helm worker."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

BACKEND_DIR = Path(__file__).resolve().parents[3]
PROCESSING_SERVICE = BACKEND_DIR / "src/services/processing/processing_service.py"
CELERY_WORKER = (
    BACKEND_DIR.parent
    / "infrastructure/helm/knowledge-graph-analytics/templates/celery-worker-deployment.yaml"
)


def test_processing_dispatch_queues_are_consumed_by_worker() -> None:
    service_source = PROCESSING_SERVICE.read_text(encoding="utf-8")
    worker_source = CELERY_WORKER.read_text(encoding="utf-8")

    dispatched = set(
        re.findall(
            r"JobType\.\w+:\s*\(\s*\"[^\"]+\"\s*,\s*\"([^\"]+)\"",
            service_source,
        )
    )
    worker_line = next(
        line.strip()
        for line in worker_source.splitlines()
        if line.strip().startswith("- celery,")
    )
    consumed = set(worker_line.removeprefix("- ").split(","))

    assert dispatched <= consumed, (
        f"processing queues are not consumed by the worker: "
        f"{sorted(dispatched - consumed)}"
    )
