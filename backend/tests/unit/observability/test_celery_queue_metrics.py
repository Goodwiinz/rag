"""Unit tests for the Celery queue-depth Prometheus collector (audit P1.6)."""

import importlib.util
import pathlib

from prometheus_client import CollectorRegistry, generate_latest

# Load the module directly from its file path rather than via
# ``src.observability`` — the package __init__ eagerly imports OpenTelemetry OTLP
# exporters that are absent from the local test venv (a known local-env gap).
# The module under test has no intra-package imports, so a standalone load is
# faithful to production behaviour while staying runnable everywhere.
_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[3]
    / "src"
    / "observability"
    / "celery_queue_metrics.py"
)
_spec = importlib.util.spec_from_file_location(
    "celery_queue_metrics_under_test", _MODULE_PATH
)
cqm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cqm)

CELERY_QUEUE_NAMES = cqm.CELERY_QUEUE_NAMES
CeleryQueueDepthCollector = cqm.CeleryQueueDepthCollector
register_celery_queue_depth_collector = cqm.register_celery_queue_depth_collector


class _StubRedis:
    """Minimal Redis stand-in exposing only ``llen``."""

    def __init__(self, depths):
        self._depths = depths
        self.calls = []

    def llen(self, key):
        self.calls.append(key)
        return self._depths.get(key, 0)


def _samples(collector):
    """Flatten a collector's samples into {queue: value}."""
    out = {}
    for metric in collector.collect():
        for sample in metric.samples:
            out[sample.labels["queue"]] = sample.value
    return out


def test_collect_reports_llen_per_queue():
    collector = CeleryQueueDepthCollector("redis://localhost:6379/0")
    collector._client = _StubRedis(
        {"celery": 3, "document_processing": 7, "high_priority": 1}
    )

    samples = _samples(collector)

    # Every configured queue is emitted (zero when absent from the stub).
    assert set(samples) == set(CELERY_QUEUE_NAMES)
    assert samples["celery"] == 3.0
    assert samples["document_processing"] == 7.0
    assert samples["high_priority"] == 1.0
    assert samples["low_priority"] == 0.0
    assert samples["entity_processing"] == 0.0
    assert samples["graph_processing"] == 0.0


def test_collect_metric_name_and_type():
    collector = CeleryQueueDepthCollector("redis://localhost:6379/0")
    collector._client = _StubRedis({})

    metrics = list(collector.collect())
    assert len(metrics) == 1
    family = metrics[0]
    assert family.name == "celery_queue_depth"
    assert family.type == "gauge"


def test_collect_skips_queue_on_redis_error_without_raising():
    class _FlakyRedis:
        def llen(self, key):
            if key == "celery":
                raise ConnectionError("broker down")
            return 5

    collector = CeleryQueueDepthCollector("redis://localhost:6379/0")
    collector._client = _FlakyRedis()

    # Must not raise even though the first queue errors.
    samples = _samples(collector)

    # The failing queue is omitted; the rest are still reported. No exception
    # escapes, so /metrics stays healthy.
    assert "celery" not in samples
    assert samples["document_processing"] == 5.0


def test_collect_never_raises_when_client_init_fails(monkeypatch):
    def _boom(_url):
        raise RuntimeError("cannot connect")

    monkeypatch.setattr(cqm, "_build_redis_client", _boom)
    collector = CeleryQueueDepthCollector("redis://localhost:6379/0")

    # No client can be built; collect yields an empty family, no exception.
    samples = _samples(collector)
    assert samples == {}


def test_register_is_idempotent_and_exposes_metric(monkeypatch):
    # Isolate the module-level singleton so this test is self-contained.
    monkeypatch.setattr(cqm, "_registered_collector", None)

    registry = CollectorRegistry()
    collector = register_celery_queue_depth_collector(
        "redis://localhost:6379/0", registry=registry
    )
    assert collector is not None
    collector._client = _StubRedis({"celery": 4})

    # Second call returns the same collector and does not double-register.
    again = register_celery_queue_depth_collector(
        "redis://localhost:6379/0", registry=registry
    )
    assert again is collector

    output = generate_latest(registry).decode("utf-8")
    assert "celery_queue_depth" in output
    assert 'queue="celery"' in output


def test_register_skips_when_no_redis_url(monkeypatch):
    monkeypatch.setattr(cqm, "_registered_collector", None)
    registry = CollectorRegistry()
    result = register_celery_queue_depth_collector("", registry=registry)
    assert result is None
    assert "celery_queue_depth" not in generate_latest(registry).decode("utf-8")


def test_build_redis_client_uses_tls_for_rediss(monkeypatch):
    captured = {}

    class _FakeRedisModule:
        @staticmethod
        def from_url(url, **kwargs):
            captured["url"] = url
            captured["kwargs"] = kwargs
            return object()

    import sys

    monkeypatch.setitem(sys.modules, "redis", _FakeRedisModule)

    cqm._build_redis_client("rediss://user:pw@host:6379/0")
    import ssl

    assert captured["kwargs"].get("ssl_cert_reqs") == ssl.CERT_NONE

    captured.clear()
    cqm._build_redis_client("redis://localhost:6379/0")
    assert captured["kwargs"] == {}
